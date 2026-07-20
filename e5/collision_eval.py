"""E5.2 collision fix — BEFORE (frozen key-identity) vs AFTER (semantic
stored-margin) on a HELD-OUT seed (6662001, disjoint from the dev seed used
to set TAU_COLLIDE). Reports the P1 gate:
  - collision-detection AUROC on near-synonyms (BEFORE stored-d vs AFTER c_sem)
  - answers-both-ways rate on collide_syn pairs (the 54% defect)
  - false-collision rate on distinct-attribute pairs (the FP guard)
  - collide_key (near-dup subject surface) reported as the deferred case.
EXIT: both-ways < 5% AND near-synonym detection AUROC > 0.90.
"""

import os

import _env
_env.patch_cache()

import numpy as np

from collision_corpus import CollisionConfig, build_collision
from l2_ambiguity import C_L2, S_L2, TAU_COLLIDE
from opinion import sigmoid
from type2 import auroc2

HERE = os.path.dirname(os.path.abspath(__file__))
HELDOUT = 6662001


def run_mode(c, mode):
    mem = c.memory
    mem.collision_mode = mode
    out = {}
    for it in c.items:
        q = mem.query(it.subj_term, it.rel)
        subj = mem.ent.resolve(it.subj_term, top=1)[0][0]
        rel = mem.rel.resolve(it.rel, top=1)[0][0]
        _, _, top1 = mem._unbind(subj, rel)
        out[id(it)] = {"it": it, "action": q.action, "tag": q.tag,
                       "conflict": q.conflict, "answer": top1,
                       "m_l2": q.m_l2, "c_sem": q.c_sem}
    return out


def both_ways_rate(pairs, res):
    """fraction of collision pairs where BOTH member queries route ANSWER
    with DIFFERENT answers (the 'answers both ways' defect)."""
    n = bad = 0
    for a, b in pairs:
        ra, rb = res[id(a)], res[id(b)]
        n += 1
        if ra["action"] == "answer" and rb["action"] == "answer" \
                and ra["answer"] != rb["answer"]:
            bad += 1
    return bad, n


def detect_rate(pairs, res, key="conflict"):
    """fraction of pairs where the gate flags a stored conflict on either member."""
    n = det = 0
    for a, b in pairs:
        n += 1
        if res[id(a)][key] or res[id(b)][key]:
            det += 1
    return det, n


def main():
    c = build_collision(CollisionConfig(seed=HELDOUT))
    before = run_mode(c, "key")
    after = run_mode(c, "semantic")
    items = c.items
    fam = {id(it): it.family for it in items}

    # ---- detection AUROC on NEAR-SYNONYM collisions vs clean negatives
    pos_mask = [it for it in items if it.family == "collide_syn"]
    neg_mask = [it for it in items
                if it.family in ("clean_single", "distinct_attr")]
    def auroc(signal):  # signal: id(it)->score
        y = np.array([1] * len(pos_mask) + [0] * len(neg_mask))
        s = np.array([signal[id(it)] for it in pos_mask]
                     + [signal[id(it)] for it in neg_mask])
        return auroc2(s, y)
    before_sig = {id(it): float(1.0 - sigmoid((after[id(it)]["m_l2"] - C_L2) / S_L2))
                  for it in items}   # frozen stored-d signal (m_l2 mode-invariant)
    after_sig = {id(it): float(after[id(it)]["c_sem"]) for it in items}
    auroc_before = auroc(before_sig)
    auroc_after = auroc(after_sig)

    # ---- both-ways + detection per collision family
    L = [f"# E5.2 collision fix — BEFORE/AFTER (held-out seed {HELDOUT})",
         f"corpus: k={c.memory.k} items={len(items)} "
         f"families={ {f: sum(1 for it in items if it.family==f) for f in sorted(set(fam.values()))} }",
         f"TAU_COLLIDE={TAU_COLLIDE}", "",
         "## Collision detection AUROC (near-synonym collide_syn vs clean_single+distinct_attr)",
         f"  BEFORE (frozen key-identity stored-d, from m_l2): {auroc_before:.4f}",
         f"  AFTER  (semantic collision score c_sem):          {auroc_after:.4f}",
         "", "## Answers-both-ways rate (the 54% §5.4 defect)"]
    for f in ("collide_syn", "collide_key"):
        pairs = c.pairs[f]
        bwb, nb = both_ways_rate(pairs, before)
        bwa, na = both_ways_rate(pairs, after)
        note = "" if f == "collide_syn" else "  (DEFERRED: near-dup subject surface)"
        L.append(f"  {f}: BEFORE {bwb}/{nb} = {bwb/max(nb,1):.3f}  ->  "
                 f"AFTER {bwa}/{na} = {bwa/max(na,1):.3f}{note}")
    L += ["", "## Conflict-detection rate per family (AFTER)"]
    for f in ("collide_syn", "collide_key"):
        det, n = detect_rate(c.pairs[f], after)
        L.append(f"  {f}: {det}/{n} pairs flagged = {det/max(n,1):.3f}")

    # ---- false-collision rate: distinct-attribute pairs wrongly flagged
    dpairs = c.pairs["distinct_attr"]
    fc_after, nd = detect_rate(dpairs, after)
    fc_before, _ = detect_rate(dpairs, before)
    # also per-ITEM false flag among all negatives (clean_single has no pairs)
    neg_items = [it for it in items if it.family in ("clean_single", "distinct_attr")]
    fitem = sum(1 for it in neg_items if after[id(it)]["conflict"])
    L += ["", "## False-collision rate (FP guard — must stay ~0)",
          f"  distinct_attr pairs flagged: BEFORE {fc_before}/{nd} -> "
          f"AFTER {fc_after}/{nd} = {fc_after/max(nd,1):.3f}",
          f"  ALL negative items (clean_single+distinct_attr) flagged AFTER: "
          f"{fitem}/{len(neg_items)} = {fitem/max(len(neg_items),1):.3f}"]

    # ---- exit criteria
    bwa, na = both_ways_rate(c.pairs["collide_syn"], after)
    bw_rate = bwa / max(na, 1)
    exit_ok = (bw_rate < 0.05) and (auroc_after > 0.90)
    L += ["", "## EXIT CRITERIA",
          f"  near-synonym answers-both-ways AFTER = {bw_rate:.3f}  "
          f"(< 0.05 required) -> {'PASS' if bw_rate < 0.05 else 'FAIL'}",
          f"  near-synonym detection AUROC AFTER  = {auroc_after:.4f} "
          f"(> 0.90 required) -> {'PASS' if auroc_after > 0.90 else 'FAIL'}",
          f"  false-collision rate (distinct_attr) = {fc_after/max(nd,1):.3f} "
          f"(guard: ~0) -> {'PASS' if fc_after == 0 else 'CHECK'}",
          f"  ==> E5.2 EXIT {'GREEN' if exit_ok else 'NOT MET'}"]
    out = "\n".join(L)
    print(out)
    with open(os.path.join(HERE, "collision_eval.md"), "w") as f:
        f.write(out + "\n")


if __name__ == "__main__":
    main()
