"""E9 (product-directed): can relation cardinality be INFERRED from the store,
cheaply, LLM-free, and accurately enough to drive the update/contradiction/
multi-value decision?

WHY THIS MATTERS. A second object arriving under an existing (subject,
relation) key is one of three completely different events:
    UPDATE        functional relation, later value supersedes
    CONTRADICTION functional relation, both asserted for the same time
    MULTI-VALUE   non-functional relation, both simply true
rg-1.1 collapses all three into "passive collision, return both", which is
safe and unusable -- it nags on every legitimately multi-valued fact and can
never update. Relation cardinality is what separates them.

THE STATISTIC IS NOT OURS. PARIS (Suchanek et al., VLDB 2012) defines
    fun(r) = #distinct subjects having >=1 object under r
             ---------------------------------------------
                     #total (subject, object) facts under r
fun(r) = 1 iff r is a strict function; AMIE/AMIE+ reuse it to orient rule
mining. We adopt it rather than invent one.

WHAT IS ACTUALLY MISSING FROM THE LITERATURE, and what this measures: those
papers use fun(r) as a heuristic feeding a downstream task. None of them
evaluate it as a standalone classifier -- there is no reported precision or
recall for "is this relation functional". E8's corpus lets us supply that,
because there the cardinality of every relation is known BY CONSTRUCTION:
FUNC_RELS carry exactly one object per subject, MANY_RELS carry exactly F.

THE SECOND, SHARPER CLAIM. For a fan-out relation of width F, fun(r) = 1/F.
E8 measured that specific-target retrieval accuracy is also 1/F (all nine
cells, CI containing 1/F). So fun(r) should predict, from a statistic the
store can maintain in O(1) and without touching the geometry, the accuracy
the substrate will actually achieve on a specific-answer query for that
relation. If that holds, the store can declare "this relation is
multi-valued, expect to enumerate, do not expect a unique answer" BEFORE
answering -- which is the mechanism the product needs.

Run: .venv/bin/python experiments/cardinality/infer.py
"""

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/experiments/relalg", f"{_R}/substrate",
           f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from corpus import (RelAlgConfig, CONDITIONS, condition_name, build_world,
                    FUNC_RELS, MANY_RELS, F_VALUES)

RELALG = os.path.join(_R, "experiments", "relalg")


def fun_score(facts):
    """PARIS functionality per relation, computed exactly as a store would:
    distinct subjects / total facts, per relation. Also returns the raw
    counts so sparse relations can be down-weighted."""
    subj = defaultdict(set)
    total = defaultdict(int)
    for f in facts:
        subj[f.rel].add(f.subj)
        total[f.rel] += 1
    return {r: {"fun": len(subj[r]) / total[r], "n_facts": total[r],
                "n_subjects": len(subj[r])} for r in total}


def ground_truth(condition, F, fanout_hop):
    """Known-by-construction cardinality for every chain relation in a
    condition. Returns rel -> true cardinality (1 = functional, F = fan-out)."""
    gt = {}
    for h in (1, 2, 3):
        for r in (FUNC_RELS[h],):
            gt[r] = 1
        for r in (MANY_RELS[h],):
            gt.setdefault(r, 1)
    if fanout_hop is not None and not condition.startswith("scrambled"):
        gt[MANY_RELS[fanout_hop + 1]] = F
    return gt


def main():
    cfg = RelAlgConfig()
    rows = []
    print("computing fun(r) per condition (corpus only, no substrate) ...")
    for base, F, fanout_hop, pad in CONDITIONS:
        name = condition_name(base, F, fanout_hop)
        agg = defaultdict(lambda: {"subj": set(), "total": 0})
        for i in range(cfg.n_worlds):
            w = build_world(cfg, base, i, F=F, fanout_hop=fanout_hop, pad=pad)
            for f in w.facts:
                # world-scoped subjects: entities are disjoint across worlds,
                # so pooling is equivalent to one large store
                agg[f.rel]["subj"].add((i, f.subj))
                agg[f.rel]["total"] += 1
        gt = ground_truth(base, F, fanout_hop)
        for r, a in agg.items():
            if r not in gt:
                continue  # filler relations: no designed cardinality
            rows.append({
                "condition": name, "relation": r,
                "fun": len(a["subj"]) / a["total"],
                "n_facts": a["total"], "n_subjects": len(a["subj"]),
                "true_card": gt[r],
                "is_functional": gt[r] == 1,
                "fanout_hop": fanout_hop, "F": F,
            })

    # ---- 1. does fun(r) separate functional from multi-valued?
    func = [x["fun"] for x in rows if x["is_functional"]]
    many = [x["fun"] for x in rows if not x["is_functional"]]
    print("\n=== 1. SEPARATION ===")
    print(f"  functional relations   n={len(func):>4}  fun mean={np.mean(func):.4f}  "
          f"min={np.min(func):.4f}")
    print(f"  multi-valued relations n={len(many):>4}  fun mean={np.mean(many):.4f}  "
          f"max={np.max(many):.4f}")
    gap = np.min(func) - np.max(many)
    print(f"  margin between classes: {gap:+.4f} "
          f"({'SEPARABLE' if gap > 0 else 'OVERLAPPING'})")

    # ---- 2. classifier precision/recall across thresholds (the gap the
    # PARIS/AMIE line of work never reports)
    print("\n=== 2. FUNCTIONAL-vs-MULTIVALUED CLASSIFIER ===")
    print(f"{'threshold':>10} {'precision':>10} {'recall':>8} {'F1':>7} {'accuracy':>9}")
    best = None
    for thr in (0.60, 0.75, 0.90, 0.95, 0.99, 0.999):
        tp = sum(1 for x in rows if x["fun"] >= thr and x["is_functional"])
        fp = sum(1 for x in rows if x["fun"] >= thr and not x["is_functional"])
        fn = sum(1 for x in rows if x["fun"] < thr and x["is_functional"])
        tn = sum(1 for x in rows if x["fun"] < thr and not x["is_functional"])
        p = tp / (tp + fp) if tp + fp else float("nan")
        rc = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * p * rc / (p + rc) if p + rc else float("nan")
        a = (tp + tn) / len(rows)
        print(f"{thr:>10.3f} {p:>10.3f} {rc:>8.3f} {f1:>7.3f} {a:>9.3f}")
        if best is None or (f1 == f1 and f1 > best[1]):
            best = (thr, f1)
    print(f"  best threshold {best[0]} (F1 {best[1]:.3f})")

    # ---- 3. does fun(r) PREDICT the measured specific-answer accuracy?
    print("\n=== 3. fun(r) vs E8's MEASURED specific accuracy (1/F prediction) ===")
    e8 = os.path.join(RELALG, "report.json")
    pred_pairs = []
    if os.path.exists(e8):
        rep = json.load(open(e8))
        print(f"{'condition':>22} {'fun(r) at fanout rel':>21} {'measured spec acc':>18} {'1/F':>6}")
        for base, F, fanout_hop, pad in CONDITIONS:
            if fanout_hop is None or base.startswith("scrambled") or not pad:
                continue
            name = condition_name(base, F, fanout_hop)
            fr = MANY_RELS[fanout_hop + 1]
            got = [x for x in rows if x["condition"] == name and x["relation"] == fr]
            if not got or name not in rep["A_composition"]:
                continue
            fun = got[0]["fun"]
            meas = rep["A_composition"][name]["specific"]["acc"]
            pred_pairs.append((fun, meas))
            print(f"{name:>22} {fun:>21.4f} {meas:>18.3f} {1.0/F:>6.3f}")
        if len(pred_pairs) >= 3:
            a = np.array(pred_pairs)
            mae = float(np.mean(np.abs(a[:, 0] - a[:, 1])))
            r = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
            print(f"\n  fun(r) as a predictor of specific-answer accuracy: "
                  f"MAE={mae:.3f}  r={r:.3f}  (n={len(a)})")
    else:
        print("  (E8 report.json not found — run experiments/relalg first)")

    with open(os.path.join(_HERE, "cardinality.json"), "w") as f:
        json.dump({"rows": rows, "prediction_pairs": pred_pairs}, f, indent=1,
                  default=float)
    mixed = mixed_cardinality()
    with open(os.path.join(_HERE, "cardinality.json"), "w") as f2:
        json.dump({"rows": rows, "prediction_pairs": pred_pairs,
                   "mixed_cardinality": mixed}, f2, indent=1, default=float)
    print(f"\n-> {os.path.join(_HERE, 'cardinality.json')}")


# ---------------------------------------------------------------------------
# The honest follow-up. E8's corpus gives EVERY subject under a fan-out
# relation exactly F objects, so fun(r) takes only the values {1, 1/F} and any
# threshold separates perfectly. Real relations are heterogeneous: most people
# have one employer, some have three. Two things break, and both are checked
# here rather than assumed:
#
#   (a) CLASSIFICATION. With a spread of per-subject cardinalities, fun(r)
#       becomes a continuum and the functional/multi-valued boundary may stop
#       being separable at all.
#   (b) PREDICTION, and this one is structural. fun(r) = S / sum(F_s) =
#       1/mean(F_s), but the accuracy of a specific-answer query, averaged over
#       subjects, is mean(1/F_s). By Jensen's inequality mean(1/F_s) >=
#       1/mean(F_s), with equality ONLY when F_s is constant. So fun(r) must
#       systematically UNDER-predict accuracy on heterogeneous relations, and
#       E8's corpus is precisely the degenerate case where the bias vanishes.
def mixed_cardinality(seed=20260723, n_subjects=400, trials=200):
    rng = np.random.default_rng(seed)
    print("\n\n=== 4. HETEROGENEOUS CARDINALITY (the realistic case) ===")
    print(f"{'relation profile':>34} {'fun(r)':>8} {'E[1/F_s]':>9} "
          f"{'Jensen gap':>11} {'mean F':>7}")
    profiles = {
        "strictly functional (F=1)":          lambda n: np.ones(n, int),
        "mostly 1, 10% have 2":               lambda n: np.where(rng.random(n) < .10, 2, 1),
        "mostly 1, 30% have 2-3":             lambda n: np.where(rng.random(n) < .30, rng.integers(2, 4, n), 1),
        "geometric, mean~2":                  lambda n: 1 + rng.geometric(0.5, n) - 1 + rng.integers(0, 2, n),
        "zipf-ish, heavy tail":               lambda n: np.minimum(rng.zipf(1.8, n), 20),
        "uniformly multi-valued (F=4)":       lambda n: np.full(n, 4),
        "uniformly multi-valued (F=8)":       lambda n: np.full(n, 8),
    }
    out = []
    for label, gen in profiles.items():
        Fs = np.maximum(gen(n_subjects), 1)
        fun = n_subjects / Fs.sum()
        exp_acc = float(np.mean(1.0 / Fs))
        out.append({"profile": label, "fun": float(fun), "expected_acc": exp_acc,
                    "jensen_gap": exp_acc - float(fun), "mean_F": float(Fs.mean()),
                    "frac_multi": float(np.mean(Fs > 1))})
        print(f"{label:>34} {fun:>8.3f} {exp_acc:>9.3f} "
              f"{exp_acc - fun:>+11.3f} {Fs.mean():>7.2f}")

    print("\n  Consequence for the WRITE-TIME decision (the one that matters):")
    print("  a relation that is functional for 90% of subjects still scores")
    print("  fun(r) well below 1.0, so a single relation-level flag mislabels")
    print("  the majority case. Reported per profile above as frac_multi.")
    for o in out:
        if 0 < o["frac_multi"] < 1:
            print(f"    {o['profile']:>34}: fun={o['fun']:.3f} but only "
                  f"{o['frac_multi']*100:.0f}% of subjects are actually multi-valued")
    return out


if __name__ == "__main__":
    main()
