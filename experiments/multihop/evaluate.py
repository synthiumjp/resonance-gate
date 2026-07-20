"""E6 evaluation: the two measurements that matter.

A. ACCURACY vs CHANCE per hop-length on INTACT chains. Chance = a random
   codebook entry of the correct type (the untyped 1/N floor is reported too,
   since cleanup searches the whole registry). "Indistinguishable from chance"
   = the Wilson 95% lower bound on accuracy sits at or below the chance rate.

B. CONFIDENCE CALIBRATION per hop-length:
   B1. AUROC of chain confidence separating INTACT-CORRECT from BROKEN, and
       from DISTRACTOR. Can the signal tell a resolvable chain from an
       unresolvable one?
   B2. THE KILLER QUESTION: on wrong answers specifically, does confidence
       collapse (honest failure) or stay high (confident nonsense)? Reported
       as the confidence distribution on intact-WRONG vs intact-CORRECT, and
       the AUROC of confidence separating them (this is the error-detection
       question E5.1 answered 0.52 — chance — for single-hop).
   B3. Calibration curve: bin by chain confidence, empirical accuracy per bin.
       A usable signal is monotonic; Spearman rho over bins reports it.

Plus the derived HALT-AT-FIRST-NON-ANSWER policy, recoverable because every
hop's routing action was logged under force-continue traversal.

Run:  .venv/bin/python experiments/multihop/evaluate.py
"""

import json
import os
import sys
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from e31_common import auc  # the repo's tie-aware rank AUROC — reused, not rebuilt
from corpus import MultihopConfig, build, chance_baseline, HOPS, ARMS
from traverse import run_world, to_row, CONF_KEYS

ROWS_PATH = os.path.join(_HERE, "rows.jsonl")
REPORT_PATH = os.path.join(_HERE, "report.json")
N_BINS = 5


# ------------------------------------------------------------------ helpers

def wilson(k, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def spearman(x, y):
    """Rank correlation, ties averaged. NaN if either side is constant."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    if len(x) < 3:
        return float("nan")

    def rank(v):
        order = v.argsort(kind="mergesort")
        r = np.empty(len(v), float)
        r[order] = np.arange(1, len(v) + 1)
        sv = v[order]
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and sv[j + 1] == sv[i]:
                j += 1
            if j > i:
                r[order[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def describe(v):
    v = np.asarray(v, float)
    if len(v) == 0:
        return {"n": 0}
    return {"n": int(len(v)), "mean": float(v.mean()), "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
            "p10": float(np.percentile(v, 10)), "median": float(np.median(v)),
            "p90": float(np.percentile(v, 90))}


def sel(rows, **kw):
    out = rows
    for k, v in kw.items():
        out = [r for r in out if r[k] == v]
    return out


# ------------------------------------------------------------- measurements

def accuracy_by_hop(rows, chance):
    """A. final-answer accuracy on intact chains, per hop-length, vs chance."""
    out = {}
    for L in HOPS:
        items = sel(rows, arm="intact", hops=L)
        n = len(items)
        k = sum(r["correct"] for r in items)
        lo, hi = wilson(k, n)
        c = chance[L]
        out[L] = {
            "n": n, "correct": k, "accuracy": k / n if n else float("nan"),
            "ci95": [lo, hi], "answer_type": c["answer_type"],
            "chance_typed": c["chance_typed"], "chance_untyped": c["chance_untyped"],
            "at_chance": bool(n and lo <= c["chance_typed"]),
            # where the chain actually broke: per-hop link accuracy
            "per_hop_link_accuracy": [
                float(np.mean([h["correct_link"] for r in items
                               for h in r["hop_detail"] if h["i"] == i
                               and h["correct_link"] is not None]))
                for i in range(L)
            ],
        }
    return out


def confidence_auroc(rows, key):
    """B1/B2. AUROC of one chain-confidence composition, per hop-length."""
    out = {}
    for L in HOPS:
        intact = sel(rows, arm="intact", hops=L)
        good = [r[key] for r in intact if r["correct"]]
        bad = [r[key] for r in intact if not r["correct"]]
        broken = [r[key] for r in sel(rows, arm="broken", hops=L)]
        distr = [r[key] for r in sel(rows, arm="distractor", hops=L)]
        out[L] = {
            "n_intact_correct": len(good), "n_intact_wrong": len(bad),
            "n_broken": len(broken), "n_distractor": len(distr),
            "auroc_intact_correct_vs_broken":
                float(auc(good, broken)) if good and broken else float("nan"),
            "auroc_intact_correct_vs_distractor":
                float(auc(good, distr)) if good and distr else float("nan"),
            # the error-detection question: correct vs WRONG among intact
            "auroc_correct_vs_wrong":
                float(auc(good, bad)) if good and bad else float("nan"),
        }
    return out


def confidence_on_wrong(rows, key):
    """B2. The critical distribution: confidence when the answer is wrong."""
    out = {}
    for L in HOPS:
        intact = sel(rows, arm="intact", hops=L)
        out[L] = {
            "intact_correct": describe([r[key] for r in intact if r["correct"]]),
            "intact_wrong": describe([r[key] for r in intact if not r["correct"]]),
            "broken": describe([r[key] for r in sel(rows, arm="broken", hops=L)]),
            "distractor": describe([r[key] for r in sel(rows, arm="distractor", hops=L)]),
        }
    return out


def calibration_curve(rows, key, n_bins=N_BINS):
    """B3. Bin intact chains by chain confidence; empirical accuracy per bin."""
    out = {}
    for L in HOPS:
        items = sel(rows, arm="intact", hops=L)
        if not items:
            out[L] = {"bins": [], "spearman_rho": float("nan")}
            continue
        conf = np.array([r[key] for r in items], float)
        corr = np.array([r["correct"] for r in items], bool)
        # equal-count bins (quantile) so every bin carries mass
        edges = np.unique(np.quantile(conf, np.linspace(0, 1, n_bins + 1)))
        idx = np.clip(np.searchsorted(edges, conf, side="right") - 1, 0, len(edges) - 2)
        bins, mids, accs = [], [], []
        for bnum in range(max(1, len(edges) - 1)):
            m = idx == bnum
            if not m.any():
                continue
            lo, hi = wilson(int(corr[m].sum()), int(m.sum()))
            bins.append({"bin": bnum, "conf_lo": float(edges[bnum]),
                         "conf_hi": float(edges[bnum + 1]),
                         "conf_mean": float(conf[m].mean()), "n": int(m.sum()),
                         "accuracy": float(corr[m].mean()), "ci95": [lo, hi]})
            mids.append(float(conf[m].mean()))
            accs.append(float(corr[m].mean()))
        out[L] = {"bins": bins, "spearman_rho": spearman(mids, accs)}
    return out


def halt_policy(rows):
    """Derived: what the alternative 'halt at first non-ANSWER' policy would do.

    Free from the force-continue run because every hop's action was logged.
    For a negative arm, halting is the DESIRED behaviour, so 'halt rate' there
    is a hit rate; on intact chains it is a false-refusal rate.
    """
    out = {}
    for L in HOPS:
        cell = {}
        for arm in ARMS:
            items = sel(rows, arm=arm, hops=L)
            if not items:
                continue
            halted = [r for r in items if not r["all_answered"]]
            cell[arm] = {
                "n": len(items),
                "halt_rate": len(halted) / len(items),
                "answered_through_rate": 1 - len(halted) / len(items),
                "mean_first_non_answer_hop": (
                    float(np.mean([r["first_non_answer"] for r in halted]))
                    if halted else float("nan")),
            }
        # among intact chains that answered all the way through, how accurate?
        intact = sel(rows, arm="intact", hops=L)
        through = [r for r in intact if r["all_answered"]]
        cell["intact_accuracy_given_all_answered"] = (
            float(np.mean([r["correct"] for r in through])) if through else float("nan"))
        out[L] = cell
    return out


def answered_only(rows, key):
    """The E5.1-COMPARABLE metric, and the honest counterweight to B1.

    B1's correct-vs-wrong AUROC is computed over ALL intact chains under
    force-continue, which includes chains the gate would have refused. E5.1
    (entry 19) measured error-ranking only among items the system actually
    ANSWERED and got 0.52 — chance. The analogue here is: restrict to chains
    where every hop routed ANSWER, then ask whether confidence ranks correct
    above wrong. Reported WITH the error count, because if the gate answers
    few chains there may be too few errors to measure anything.
    """
    out = {}
    for L in HOPS:
        intact = [r for r in sel(rows, arm="intact", hops=L) if r["all_answered"]]
        good = [r[key] for r in intact if r["correct"]]
        bad = [r[key] for r in intact if not r["correct"]]
        out[L] = {
            "n_answered": len(intact), "n_correct": len(good), "n_errors": len(bad),
            "accuracy": len(good) / len(intact) if intact else float("nan"),
            "auroc_correct_vs_wrong": (float(auc(good, bad))
                                       if len(good) and len(bad) else float("nan")),
            "measurable": bool(len(bad) >= 10 and len(good) >= 10),
        }
    return out


def action_mix(rows):
    """Diagnostic: routing action distribution per arm, per hop index."""
    out = defaultdict(lambda: defaultdict(int))
    for r in rows:
        for h in r["hop_detail"]:
            out[f"{r['arm']}/L{r['hops']}/hop{h['i']}"][h["action"]] += 1
    return {k: dict(v) for k, v in out.items()}


# ------------------------------------------------------------------- driver

def generate(cfg):
    rows = []
    for w in build(cfg):
        wrows = [to_row(tr) for tr in run_world(w)]
        rows.extend(wrows)
        print(f"  world {w.index}: k={w.memory.k} N={len(w.memory.ent)} "
              f"chains={len(w.chains)} filler={w.n_filler} "
              f"rejected={w.n_rejected}", flush=True)
    return rows


def _arg(flag, default, cast=int):
    return cast(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


def main():
    global REPORT_PATH
    base = MultihopConfig()
    k = _arg("--k", base.k_facts)
    cfg = MultihopConfig(k_facts=k, n_worlds=_arg("--worlds", base.n_worlds))
    # load-sweep runs get their own artefacts so the k=200 primary is never
    # overwritten by a stress point
    suffix = "" if k == base.k_facts else f"_k{k}"
    rows_path = ROWS_PATH.replace(".jsonl", f"{suffix}.jsonl")
    report_path = REPORT_PATH.replace(".json", f"{suffix}.json")

    if os.path.exists(rows_path) and "--regen" not in sys.argv:
        rows = [json.loads(l) for l in open(rows_path)]
        print(f"loaded {len(rows)} chains from {rows_path}")
    else:
        print(f"building {cfg.n_worlds} worlds (seed {cfg.seed}, k={cfg.k_facts}) ...")
        rows = generate(cfg)
        with open(rows_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {len(rows)} chains -> {rows_path}")
    REPORT_PATH = report_path

    chance = chance_baseline(cfg)
    report = {
        "config": cfg.__dict__,
        "n_chains": len(rows),
        "cell_counts": {f"{a}/L{L}": len(sel(rows, arm=a, hops=L))
                        for a in ARMS for L in HOPS},
        "chance": {str(L): chance[L] for L in HOPS},
        "A_accuracy_by_hop": accuracy_by_hop(rows, chance),
        "B_auroc": {k: confidence_auroc(rows, k) for k in CONF_KEYS},
        "B_confidence_on_wrong": {k: confidence_on_wrong(rows, k) for k in CONF_KEYS},
        "B_calibration": {k: calibration_curve(rows, k) for k in CONF_KEYS},
        "B_answered_only": {k: answered_only(rows, k) for k in CONF_KEYS},
        "halt_policy": halt_policy(rows),
        "action_mix": action_mix(rows),
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=1, default=float)
    print_report(report)
    print(f"\nfull report -> {REPORT_PATH}")


def print_report(rep):
    print("\n=== A. ACCURACY vs CHANCE (intact chains) ===")
    print(f"{'L':>2} {'n':>4} {'acc':>7} {'95% CI':>16} {'type':>7} "
          f"{'chance':>8}  at-chance")
    for L in HOPS:
        a = rep["A_accuracy_by_hop"][L]
        print(f"{L:>2} {a['n']:>4} {a['accuracy']:>7.3f} "
              f"[{a['ci95'][0]:.3f},{a['ci95'][1]:.3f}] {a['answer_type']:>7} "
              f"{a['chance_typed']:>8.4f}  {'YES' if a['at_chance'] else 'no'}")
        print(f"     per-hop link accuracy: "
              f"{[round(x, 3) for x in a['per_hop_link_accuracy']]}")

    for key in CONF_KEYS:
        print(f"\n=== B1. AUROC, chain confidence = {key} ===")
        print(f"{'L':>2} {'intact-vs-broken':>17} {'intact-vs-distr':>16} "
              f"{'correct-vs-wrong':>17}")
        for L in HOPS:
            b = rep["B_auroc"][key][L]
            print(f"{L:>2} {b['auroc_intact_correct_vs_broken']:>17.4f} "
                  f"{b['auroc_intact_correct_vs_distractor']:>16.4f} "
                  f"{b['auroc_correct_vs_wrong']:>17.4f}")

    print("\n=== B2. CONFIDENCE ON WRONG ANSWERS (the critical number) ===")
    for key in CONF_KEYS:
        print(f"-- {key}")
        for L in HOPS:
            c = rep["B_confidence_on_wrong"][key][L]
            g, w = c["intact_correct"], c["intact_wrong"]
            br = c["broken"]
            print(f"  L={L}  correct {g.get('mean', float('nan')):.3f}"
                  f"(n={g.get('n', 0)})   WRONG {w.get('mean', float('nan')):.3f}"
                  f"(n={w.get('n', 0)})   broken {br.get('mean', float('nan')):.3f}"
                  f"(n={br.get('n', 0)})")

    print("\n=== B3. CALIBRATION (monotonicity, Spearman rho over bins) ===")
    for key in CONF_KEYS:
        rhos = [rep["B_calibration"][key][L]["spearman_rho"] for L in HOPS]
        print(f"  {key:>16}: " + "  ".join(
            f"L{L}={r:.3f}" if r == r else f"L{L}=nan" for L, r in zip(HOPS, rhos)))

    print("\n=== B2b. ANSWERED-ONLY error ranking (E5.1-comparable) ===")
    for key in ("conf_min_1mu", "conf_min_b"):
        print(f"-- {key}")
        for L in HOPS:
            a = rep["B_answered_only"][key][L]
            print(f"  L={L}  n_answered={a['n_answered']:>3} errors={a['n_errors']:>3} "
                  f"acc={a['accuracy']:.3f}  AUROC={a['auroc_correct_vs_wrong']:.4f}"
                  f"  {'' if a['measurable'] else '(too few errors to measure)'}")

    print("\n=== DERIVED: halt-at-first-non-ANSWER policy ===")
    for L in HOPS:
        h = rep["halt_policy"][L]
        parts = " ".join(f"{a}={h[a]['halt_rate']:.2f}" for a in ARMS if a in h)
        print(f"  L={L} halt-rate  {parts}   "
              f"intact acc|all-answered={h['intact_accuracy_given_all_answered']:.3f}")


if __name__ == "__main__":
    main()
