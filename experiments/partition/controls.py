"""E7 artifact controls: the three checks that decide whether the partition
result is a real effect or a construction artefact.

C1. DEGREE STRATIFICATION. Retrieval accuracy as a continuous function of the
    subject's OUT-degree and IN-degree, per condition. The A-measurement only
    compared two pre-labelled classes; this asks the same question without
    relying on the labels, and it is what shows whether COND-E won on the
    high-out-degree bottleneck entities specifically or only on the easy
    degree-1 cells.
C2. SUPERPOSITION SURVIVAL, by cell size (measurement D, re-cut per cell
    rather than per query).
C3. STRUCTURAL vs GEOMETRIC rejection in the negative arms: how much of the
    broken/distractor confidence collapse is the dictionary finding an empty
    cell, and how much is the geometry separating a populated one.

Degrees are recomputed from the corpus (pure Python/numpy, no substrate, no
embeddings) and joined to the stored probe rows by (world, subject).

Run:  .venv/bin/python experiments/partition/controls.py
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

from corpus import PartitionConfig, build_world
from stores import CONDITIONS
from evaluate import wilson


def degree_tables(cfg):
    """(world, entity) -> (out_degree, in_degree), rebuilt from the corpus."""
    out, inn = {}, {}
    for i in range(cfg.n_worlds):
        w = build_world(cfg, i)
        for e, c in w.degree["out_degree"].items():
            out[(i, e)] = c
        for e, c in w.degree["in_degree"].items():
            inn[(i, e)] = c
    return out, inn


def _acc(vals):
    n = len(vals)
    k = int(np.sum(vals))
    lo, hi = wilson(k, n)
    return {"n": n, "acc": k / n if n else float("nan"), "ci": [lo, hi]}


def stratify(probes, degree, label, bins):
    """Retrieval accuracy per condition, binned by a degree value."""
    out = {}
    for cond in CONDITIONS:
        rows = [p for p in probes if p["condition"] == cond]
        cells = {}
        for lo, hi in bins:
            v = [p["retrieved"] for p in rows
                 if lo <= degree.get((p["world"], p["subj"]), 0) <= hi]
            if v:
                cells[f"{lo}-{hi}" if lo != hi else f"{lo}"] = _acc(v)
        out[cond] = cells
    return out, label


def main():
    cfg = PartitionConfig()
    probes = [json.loads(l) for l in open(os.path.join(_HERE, "probes.jsonl"))]
    rows = [json.loads(l) for l in open(os.path.join(_HERE, "rows.jsonl"))]

    print("rebuilding corpus degrees (no substrate) ...", flush=True)
    outd, ind = degree_tables(cfg)

    report = {}

    # ---------------------------------------------------- C1 out-degree
    obins = [(1, 1), (2, 3), (4, 5), (6, 8)]
    s_out, _ = stratify(probes, outd, "out_degree", obins)
    report["C1_by_out_degree"] = s_out
    print("\n=== C1a. RETRIEVAL vs SUBJECT OUT-DEGREE ===")
    print("(in COND-E the subject's out-degree IS its store's k)")
    hdr = [f"{lo}" if lo == hi else f"{lo}-{hi}" for lo, hi in obins]
    print(f"{'cond':>8} " + " ".join(f"{h:>16}" for h in hdr))
    for cond in CONDITIONS:
        cells = s_out[cond]
        print(f"{cond:>8} " + " ".join(
            f"{cells[h]['acc']:.3f}(n={cells[h]['n']:>4})" if h in cells else f"{'-':>16}"
            for h in hdr))

    # ---------------------------------------------------- C1 in-degree
    ibins = [(0, 0), (1, 1), (2, 3), (4, 20)]
    s_in, _ = stratify(probes, ind, "in_degree", ibins)
    report["C1_by_in_degree"] = s_in
    print("\n=== C1b. RETRIEVAL vs SUBJECT IN-DEGREE ===")
    print("(in-degree never changes store size under subject partitioning)")
    hdr = [f"{lo}" if lo == hi else f"{lo}-{hi}" for lo, hi in ibins]
    print(f"{'cond':>8} " + " ".join(f"{h:>16}" for h in hdr))
    for cond in CONDITIONS:
        cells = s_in[cond]
        print(f"{cond:>8} " + " ".join(
            f"{cells[h]['acc']:.3f}(n={cells[h]['n']:>4})" if h in cells else f"{'-':>16}"
            for h in hdr))

    # ---------------------------------------------------- C2 cell sizes
    print("\n=== C2. CELL-SIZE DISTRIBUTION (per cell, not per query) ===")
    cell = {}
    for cond in CONDITIONS:
        ks = [h["k_store"] for r in rows if r["condition"] == cond
              for h in r["hop_detail"]]
        ks += [p["k_store"] for p in probes if p["condition"] == cond]
        v = np.asarray(ks)
        cell[cond] = {
            "frac_queries_k_gt1": float(np.mean(v > 1)),
            "frac_queries_k_ge5": float(np.mean(v >= 5)),
            "frac_queries_k_eq1": float(np.mean(v == 1)),
            "frac_queries_k_eq0": float(np.mean(v == 0)),
            "k_mean": float(v.mean()), "k_max": int(v.max()),
        }
        c = cell[cond]
        print(f"  {cond:>8}  k>1 {c['frac_queries_k_gt1']:.3f}   k>=5 {c['frac_queries_k_ge5']:.3f}"
              f"   k==1 {c['frac_queries_k_eq1']:.3f}   k==0 {c['frac_queries_k_eq0']:.3f}"
              f"   mean {c['k_mean']:.1f}  max {c['k_max']}")
    report["C2_cell_sizes"] = cell

    # ------------------------------------- C3 structural vs geometric reject
    print("\n=== C3. NEGATIVE-ARM REJECTION: structural vs geometric ===")
    c3 = {}
    for cond in CONDITIONS:
        neg = [r for r in rows if r["condition"] == cond
               and r["arm"] in ("broken", "distractor")]
        struct = [r for r in neg if any(h["k_store"] == 0 for h in r["hop_detail"])]
        geo = [r for r in neg if not any(h["k_store"] == 0 for h in r["hop_detail"])]
        intact = [r for r in rows if r["condition"] == cond and r["arm"] == "intact"]
        c3[cond] = {
            "n_negative": len(neg),
            "frac_structural": len(struct) / len(neg) if neg else float("nan"),
            "n_geometric": len(geo),
            "conf_geometric_negatives": float(np.mean([r["conf_min_1mu"] for r in geo])) if geo else float("nan"),
            "conf_intact": float(np.mean([r["conf_min_1mu"] for r in intact])) if intact else float("nan"),
        }
        x = c3[cond]
        print(f"  {cond:>8}  structural {x['frac_structural']:.3f}  "
              f"geometric n={x['n_geometric']:>4}  "
              f"conf(geometric negatives) {x['conf_geometric_negatives']:.3f}  "
              f"vs intact {x['conf_intact']:.3f}")
    report["C3_structural_vs_geometric"] = c3

    with open(os.path.join(_HERE, "controls.json"), "w") as f:
        json.dump(report, f, indent=1, default=float)
    print(f"\n-> {os.path.join(_HERE, 'controls.json')}")


if __name__ == "__main__":
    main()
