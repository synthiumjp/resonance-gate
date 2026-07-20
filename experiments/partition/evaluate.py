"""E7 evaluation: four conditions x the four measurements that matter.

A. KUMAR PROBE — single-hop retrieval accuracy of the HIGH-DEGREE 2nd/3rd-hop
   chain facts, posed as standalone atomic queries, against TYPICAL degree-1
   facts in the SAME store at the same k and N. Ratio = high/typical. COND-0
   must show the degradation or the corpus is not in the regime and nothing
   downstream is interpretable.
B. MULTI-HOP ACCURACY vs chance, per hop-length, per condition, intact chains.
C. CONFIDENCE HONESTY, per condition: intact-vs-broken AUROC, and the
   distribution of confidence on WRONG answers.
D. HOW MUCH SUPERPOSITION SURVIVES — k per store and the fraction of issued
   queries whose routed store held more than one fact. This is the
   "did we just build a hashmap" check.

Run:  .venv/bin/python experiments/partition/evaluate.py            (EVAL)
      .venv/bin/python experiments/partition/evaluate.py --dev      (DEV calib)
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

from e31_common import auc                      # repo's tie-aware rank AUROC
from corpus import (PartitionConfig, build, chance_baseline, degree_summary,
                    HOPS, ARMS)
from stores import build_conditions, echo_reject_rate, CONDITIONS
from traverse import run_chain, probe_atomic, to_row, CONF_KEYS

N_BINS = 5


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p, den = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def describe(v):
    v = np.asarray(v, float)
    if len(v) == 0:
        nan = float("nan")
        return {"n": 0, "mean": nan, "sd": nan, "p10": nan, "median": nan, "p90": nan}
    return {"n": int(len(v)), "mean": float(v.mean()),
            "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
            "p10": float(np.percentile(v, 10)), "median": float(np.median(v)),
            "p90": float(np.percentile(v, 90))}


def sel(rows, **kw):
    out = rows
    for k, v in kw.items():
        out = [r for r in out if r[k] == v]
    return out


# ----------------------------------------------------------- A. Kumar probe

def kumar_probe(probes):
    """Per condition: retrieval accuracy on high-degree vs typical facts."""
    out = {}
    for cond in CONDITIONS:
        hi = [p for p in probes if p["condition"] == cond and p["class"] == "kumar"]
        ty = [p for p in probes if p["condition"] == cond and p["class"] == "typical"]
        a_hi = float(np.mean([p["retrieved"] for p in hi])) if hi else float("nan")
        a_ty = float(np.mean([p["retrieved"] for p in ty])) if ty else float("nan")
        lo_h, hi_h = wilson(sum(p["retrieved"] for p in hi), len(hi))
        lo_t, hi_t = wilson(sum(p["retrieved"] for p in ty), len(ty))
        out[cond] = {
            "n_high": len(hi), "n_typical": len(ty),
            "acc_high_degree": a_hi, "ci95_high": [lo_h, hi_h],
            "acc_typical": a_ty, "ci95_typical": [lo_t, hi_t],
            "ratio": (a_hi / a_ty) if a_ty else float("nan"),
            "k_store_high": describe([p["k_store"] for p in hi]),
            "k_store_typical": describe([p["k_store"] for p in ty]),
            # routing-level secondary (retrieval is the primary measure)
            "answered_correct_high": float(np.mean([p["answered_correct"] for p in hi])) if hi else float("nan"),
            "answered_correct_typical": float(np.mean([p["answered_correct"] for p in ty])) if ty else float("nan"),
        }
    return out


# ------------------------------------------------------- B. multi-hop accuracy

def accuracy_by_hop(rows, chance):
    out = {}
    for cond in CONDITIONS:
        cell = {}
        for L in HOPS:
            items = sel(rows, condition=cond, arm="intact", hops=L)
            n = len(items)
            k = sum(r["correct"] for r in items)
            lo, hi = wilson(k, n)
            c = chance[L]
            cell[L] = {"n": n, "correct": k,
                       "accuracy": k / n if n else float("nan"),
                       "ci95": [lo, hi], "chance_typed": c["chance_typed"],
                       "answer_type": c["answer_type"],
                       "at_chance": bool(n and lo <= c["chance_typed"]),
                       "per_hop_link_accuracy": [
                           float(np.mean([h["correct_link"] for r in items
                                          for h in r["hop_detail"]
                                          if h["i"] == i and h["correct_link"] is not None]))
                           for i in range(L)]}
        out[cond] = cell
    return out


# ------------------------------------------------------ C. confidence honesty

def confidence(rows, key):
    out = {}
    for cond in CONDITIONS:
        cell = {}
        for L in HOPS:
            intact = sel(rows, condition=cond, arm="intact", hops=L)
            good = [r[key] for r in intact if r["correct"]]
            bad = [r[key] for r in intact if not r["correct"]]
            broken = [r[key] for r in sel(rows, condition=cond, arm="broken", hops=L)]
            distr = [r[key] for r in sel(rows, condition=cond, arm="distractor", hops=L)]
            cell[L] = {
                "auroc_intact_vs_broken": float(auc(good, broken)) if good and broken else float("nan"),
                "auroc_intact_vs_distractor": float(auc(good, distr)) if good and distr else float("nan"),
                "auroc_correct_vs_wrong": float(auc(good, bad)) if good and bad else float("nan"),
                "conf_correct": describe(good), "conf_wrong": describe(bad),
                "conf_broken": describe(broken), "conf_distractor": describe(distr),
            }
        out[cond] = cell
    return out


def calibration(rows, key, n_bins=N_BINS):
    out = {}
    for cond in CONDITIONS:
        cell = {}
        for L in HOPS:
            items = sel(rows, condition=cond, arm="intact", hops=L)
            if not items:
                cell[L] = {"bins": [], "spearman_rho": float("nan")}
                continue
            conf = np.array([r[key] for r in items], float)
            corr = np.array([r["correct"] for r in items], bool)
            edges = np.unique(np.quantile(conf, np.linspace(0, 1, n_bins + 1)))
            if len(edges) < 2:
                cell[L] = {"bins": [], "spearman_rho": float("nan")}
                continue
            idx = np.clip(np.searchsorted(edges, conf, side="right") - 1,
                          0, len(edges) - 2)
            bins, mids, accs = [], [], []
            for b in range(len(edges) - 1):
                mask = idx == b
                if not mask.any():
                    continue
                bins.append({"conf_mean": float(conf[mask].mean()),
                             "n": int(mask.sum()),
                             "accuracy": float(corr[mask].mean())})
                mids.append(float(conf[mask].mean()))
                accs.append(float(corr[mask].mean()))
            rho = float(np.corrcoef(mids, accs)[0, 1]) if len(mids) >= 3 and np.std(mids) and np.std(accs) else float("nan")
            cell[L] = {"bins": bins, "spearman_rho": rho}
        out[cond] = cell
    return out


# --------------------------------------------- D. how much superposition left

def superposition(rows, probes, store_stats):
    out = {}
    for cond in CONDITIONS:
        ks = [h["k_store"] for r in sel(rows, condition=cond) for h in r["hop_detail"]]
        ks += [p["k_store"] for p in probes if p["condition"] == cond]
        v = np.asarray(ks) if ks else np.array([0])
        st = store_stats[cond]
        out[cond] = {
            "store_k": {kk: float(np.mean([s[kk] for s in st])) for kk in
                        ("n_stores", "k_mean", "k_median", "k_p90", "k_max",
                         "frac_stores_multifact")},
            "queries_k_mean": float(v.mean()),
            "queries_k_median": float(np.median(v)),
            "frac_queries_multifact_store": float(np.mean(v > 1)),
            "frac_queries_empty_store": float(np.mean(v == 0)),
            "frac_queries_single_fact_store": float(np.mean(v == 1)),
        }
    return out


# ------------------------------------------------------------------- driver

def generate(cfg):
    rows, probes, store_stats = [], [], defaultdict(list)
    degrees, echo_rates, chance = [], [], None
    for w in build(cfg):
        parts, ent, rel = build_conditions(w, cfg)
        if chance is None:
            chance = chance_baseline(w, cfg)
        degrees.append(degree_summary(w))
        calib = parts["COND-0"].calib
        echo_rates.append(echo_reject_rate(w, cfg, ent, rel, calib, seed=w.seed))
        for cond, part in parts.items():
            store_stats[cond].append(part.k_distribution())
            for cls, pset in (("kumar", w.kumar_probe), ("typical", w.typical_probe)):
                for s, r, g in pset:
                    p = probe_atomic(part, s, r, g)
                    p.update(condition=cond, world=w.index, **{"class": cls})
                    probes.append(p)
            for ch in w.chains:
                rows.append(to_row(run_chain(part, ch)))
        d = degrees[-1]
        print(f"  world {w.index}: facts={d['n_facts']} entities={d['n_entities']} "
              f"out-deg mean={d['out_degree']['mean']:.1f} max={d['out_degree']['max']} "
              f"chain-rel-deg mean={d['chain_relation_degree']['mean']:.0f} "
              f"cold-rel-deg mean={d['cold_relation_degree']['mean']:.0f} "
              f"echo-reject={echo_rates[-1]:.2f}", flush=True)
        del parts, ent, rel
    return rows, probes, dict(store_stats), degrees, echo_rates, chance


def main():
    dev = "--dev" in sys.argv
    base = PartitionConfig()
    cfg = PartitionConfig(seed=base.seed + 7 if dev else base.seed,
                          n_worlds=2 if dev else base.n_worlds)
    tag = "_dev" if dev else ""
    rows_path = os.path.join(_HERE, f"rows{tag}.jsonl")
    probes_path = os.path.join(_HERE, f"probes{tag}.jsonl")
    report_path = os.path.join(_HERE, f"report{tag}.json")

    if os.path.exists(rows_path) and "--regen" not in sys.argv:
        rows = [json.loads(l) for l in open(rows_path)]
        probes = [json.loads(l) for l in open(probes_path)]
        meta = json.load(open(report_path))
        store_stats, degrees = meta["_store_stats"], meta["degree_per_world"]
        echo_rates, chance = meta["echo_reject_rate_per_world"], {int(k): v for k, v in meta["chance"].items()}
        print(f"loaded {len(rows)} traversals / {len(probes)} probes")
    else:
        print(f"building {cfg.n_worlds} worlds (seed {cfg.seed}, "
              f"{'DEV calibration' if dev else 'EVAL'}) ...")
        rows, probes, store_stats, degrees, echo_rates, chance = generate(cfg)
        with open(rows_path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        with open(probes_path, "w") as f:
            for p in probes:
                f.write(json.dumps(p) + "\n")

    report = {
        "config": cfg.__dict__, "dev": dev,
        "n_traversals": len(rows), "n_probes": len(probes),
        "degree_per_world": degrees,
        "echo_reject_rate_per_world": echo_rates,
        "chance": {str(L): chance[L] for L in HOPS},
        "A_kumar_probe": kumar_probe(probes),
        "B_accuracy_by_hop": accuracy_by_hop(rows, chance),
        "C_confidence": {k: confidence(rows, k) for k in CONF_KEYS},
        "C_calibration": {k: calibration(rows, k) for k in CONF_KEYS},
        "D_superposition": superposition(rows, probes, store_stats),
        "_store_stats": store_stats,
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=1, default=float)
    print_report(report)
    print(f"\nfull report -> {report_path}")


def print_report(rep):
    d0 = rep["degree_per_world"][0]
    print(f"\nREGIME: {d0['n_facts']} facts, {d0['n_entities']} entities; "
          f"out-degree mean {d0['out_degree']['mean']:.1f} / max {d0['out_degree']['max']}; "
          f"in-degree mean {d0['in_degree']['mean']:.1f} / max {d0['in_degree']['max']}; "
          f"chain-relation degree mean {d0['chain_relation_degree']['mean']:.0f} vs "
          f"cold {d0['cold_relation_degree']['mean']:.0f}")

    print("\n=== A. KUMAR PROBE (single-hop retrieval, same store, same k/N) ===")
    print(f"{'cond':>8} {'high-deg':>9} {'typical':>9} {'ratio':>7} "
          f"{'k(high)':>9} {'k(typ)':>8}")
    for c in CONDITIONS:
        a = rep["A_kumar_probe"][c]
        print(f"{c:>8} {a['acc_high_degree']:>9.3f} {a['acc_typical']:>9.3f} "
              f"{a['ratio']:>7.3f} {a['k_store_high']['mean']:>9.1f} "
              f"{a['k_store_typical']['mean']:>8.1f}")

    print("\n=== B. MULTI-HOP ACCURACY vs CHANCE (intact) ===")
    for c in CONDITIONS:
        line = []
        for L in HOPS:
            b = rep["B_accuracy_by_hop"][c][L]
            line.append(f"L{L}={b['accuracy']:.3f}{'*' if b['at_chance'] else ' '}")
        ch = " ".join(f"{rep['chance'][str(L)]['chance_typed']:.4f}" for L in HOPS)
        print(f"{c:>8}  " + "  ".join(line) + f"   (chance {ch})   * = at chance")

    key = "conf_min_1mu"
    print(f"\n=== C. CONFIDENCE HONESTY ({key}) ===")
    print(f"{'cond':>8} {'L':>2} {'AUROC i-v-broken':>17} {'corr-v-wrong':>13} "
          f"{'conf correct':>13} {'conf WRONG':>11} {'conf broken':>12}")
    for c in CONDITIONS:
        for L in HOPS:
            x = rep["C_confidence"][key][c][L]
            print(f"{c:>8} {L:>2} {x['auroc_intact_vs_broken']:>17.3f} "
                  f"{x['auroc_correct_vs_wrong']:>13.3f} "
                  f"{x['conf_correct'].get('mean', float('nan')):>13.3f} "
                  f"{x['conf_wrong'].get('mean', float('nan')):>11.3f}"
                  f"(n={x['conf_wrong'].get('n', 0)}) "
                  f"{x['conf_broken'].get('mean', float('nan')):>10.3f}")

    print("\n=== D. HOW MUCH SUPERPOSITION SURVIVES ===")
    print(f"{'cond':>8} {'stores':>7} {'k mean':>8} {'k med':>6} {'k max':>7} "
          f"{'q:multi-fact':>13} {'q:single':>9} {'q:empty':>8}")
    for c in CONDITIONS:
        s = rep["D_superposition"][c]
        print(f"{c:>8} {s['store_k']['n_stores']:>7.0f} {s['store_k']['k_mean']:>8.1f} "
              f"{s['store_k']['k_median']:>6.0f} {s['store_k']['k_max']:>7.0f} "
              f"{s['frac_queries_multifact_store']:>13.3f} "
              f"{s['frac_queries_single_fact_store']:>9.3f} "
              f"{s['frac_queries_empty_store']:>8.3f}")





# --------------------------------------------------- COND-0 load sweep (A')
# Traces the Kumar ratio against store load with the degree structure of both
# probe classes held FIXED. If the ratio stays ~1 while both classes fall
# together, degradation is a function of k alone and degree is not the
# mechanism. Run: evaluate.py --sweep
def sweep():
    from corpus import build_world
    from stores import Partition, MODE_OF
    from registry import Registry
    from write_path import default_calibration
    from corpus import ALL_RELS, registry_names
    base = PartitionConfig()
    calib = default_calibration()
    print(f"{'k':>6} {'N':>5} {'high-deg':>9} {'typical':>9} {'ratio':>7} "
          f"{'ratio CI95':>18} {'hub/typ deg':>12}")
    out = []
    for filler in (0, 300, 800, 1600, 3000):
        cfg = PartitionConfig(seed=base.seed + 7, n_worlds=3, n_person=2000,
                              n_load_filler=filler)
        hi_all, ty_all, ks, Ns, degr = [], [], [], [], []
        for i in range(cfg.n_worlds):
            w = build_world(cfg, i)
            ent = Registry(registry_names(cfg, w))
            rel = Registry(ALL_RELS)
            part = Partition("COND-0", MODE_OF["COND-0"], ent, rel, calib).load(w.facts)
            for s, r, g in w.kumar_probe:
                hi_all.append(probe_atomic(part, s, r, g)["retrieved"])
            for s, r, g in w.typical_probe:
                ty_all.append(probe_atomic(part, s, r, g)["retrieved"])
            ks.append(len(w.facts)); Ns.append(len(ent))
            degr.append(degree_summary(w)["degree_ratio_hub_vs_typical"])
            del part, ent, rel
        a_h = float(np.mean(hi_all)); a_t = float(np.mean(ty_all))
        lo_h, hi_h = wilson(int(np.sum(hi_all)), len(hi_all))
        lo_t, hi_t = wilson(int(np.sum(ty_all)), len(ty_all))
        # ratio CI by the delta method on the two Wilson bounds (conservative)
        rlo = lo_h / hi_t if hi_t else float("nan")
        rhi = hi_h / lo_t if lo_t else float("nan")
        row = {"k": float(np.mean(ks)), "N": float(np.mean(Ns)),
               "acc_high": a_h, "acc_typical": a_t,
               "ratio": a_h / a_t if a_t else float("nan"),
               "ratio_ci95": [rlo, rhi], "n_high": len(hi_all),
               "n_typical": len(ty_all),
               "degree_ratio": float(np.mean(degr))}
        out.append(row)
        print(f"{row['k']:>6.0f} {row['N']:>5.0f} {a_h:>9.3f} {a_t:>9.3f} "
              f"{row['ratio']:>7.3f} [{rlo:>7.3f},{rhi:>7.3f}] {row['degree_ratio']:>12.2f}",
              flush=True)
    with open(os.path.join(_HERE, "sweep.json"), "w") as f:
        json.dump(out, f, indent=1, default=float)
    return out


if __name__ == "__main__":
    if "--sweep" in sys.argv:
        sweep()
    else:
        main()
