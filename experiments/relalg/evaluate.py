"""E8 evaluation: is fan-out failure a relation-structure effect, or load?

A. COMPOSITION FIDELITY at matched k: functional vs fanout vs the two
   controls. Because k is padded to a constant, `functional` IS the
   load-matched control; `scrambled_*` is the algebra-scrambled control with
   the same fact count, same relation, same k, and no shared key. The
   unpadded arm shows the confounded comparison the controls remove.
B. FAILURE LOCALISATION: per-hop (b, d, u) by chain position, stratified by
   where the fan-out sits. The prediction is a collapse that MOVES with the
   fan-out hop.
C. (b, d, u) DECOMPOSITION at underdetermined vs functional hops, with the
   winning d-source tag. A d-rise means the geometry reports "conflict here";
   a u-rise would mean it reports "nothing here". Only the former is honest.
D. IS IT JUST UNDERDETERMINATION? Decided on the numbers, not asserted.

Run:  .venv/bin/python experiments/relalg/evaluate.py [--regen]
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

from registry import Registry
from write_path import Memory, default_calibration

from corpus import (RelAlgConfig, CONDITIONS, condition_name, build_world,
                    registry_names, chance_baseline, ALL_RELS, F_VALUES)
from traverse import run_chain, to_row, CONF_KEYS

ROWS = os.path.join(_HERE, "rows.jsonl")
REPORT = os.path.join(_HERE, "report.json")


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
        n = float("nan")
        return {"n": 0, "mean": n, "sd": n}
    return {"n": int(len(v)), "mean": float(v.mean()),
            "sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0}


def sel(rows, **kw):
    out = rows
    for k, v in kw.items():
        out = [r for r in out if r[k] == v]
    return out


def acc(rows, field):
    n = len(rows)
    k = sum(bool(r[field]) for r in rows)
    lo, hi = wilson(k, n)
    return {"n": n, "acc": k / n if n else float("nan"), "ci95": [lo, hi]}


# ------------------------------------------------------------------ generate

def generate(cfg):
    rows, meta = [], {}
    calib = default_calibration()
    for base, F, fanout_hop, pad in CONDITIONS:
        name = condition_name(base, F, fanout_hop)
        ks, chances = [], []
        for i in range(cfg.n_worlds):
            w = build_world(cfg, base, i, F=F, fanout_hop=fanout_hop, pad=pad)
            ent = Registry(registry_names(w))
            rel = Registry(ALL_RELS)
            mem = Memory(ent, rel, calib=calib)
            for f in w.facts:
                mem.write(f.subj, f.rel, f.obj, echo=False)
            for ch in w.chains:
                rows.append(to_row(run_chain(mem, ch), name, int(mem.k)))
            ks.append(int(mem.k))
            chances.append(chance_baseline(w)["chance_typed"])
            del mem, ent, rel
        meta[name] = {"k_mean": float(np.mean(ks)), "chance": float(np.mean(chances)),
                      "F": F, "fanout_hop": fanout_hop, "padded": pad}
        print(f"  {name:>24} k={np.mean(ks):>5.0f} chains={cfg.n_worlds*cfg.chains_per_world}",
              flush=True)
    return rows, meta


# ------------------------------------------------------------- measurement A

def composition_fidelity(rows, meta):
    out = {}
    for name in meta:
        r = sel(rows, condition=name)
        out[name] = {
            "k": meta[name]["k_mean"], "chance": meta[name]["chance"],
            "specific": acc(r, "correct_specific"),
            "any_valid": acc(r, "correct_any_valid"),
            "all_hops_valid": acc(r, "all_hops_valid"),
        }
    return out


# ------------------------------------------------------------- measurement B

def localisation(rows, meta):
    """Per-hop mean (b, d, u) by chain position, per condition."""
    out = {}
    for name in meta:
        r = sel(rows, condition=name)
        cell = {}
        for i in range(3):
            hs = [h for x in r for h in x["hop_detail"] if h["i"] == i]
            cell[i] = {
                "b": float(np.mean([h["b"] for h in hs])),
                "d": float(np.mean([h["d"] for h in hs])),
                "u": float(np.mean([h["u"] for h in hs])),
                "link_valid": float(np.mean([h["link_valid"] for h in hs
                                             if h["link_valid"] is not None]))
                if any(h["link_valid"] is not None for h in hs) else float("nan"),
                "underdet_frac": float(np.mean([h["underdetermined"] for h in hs])),
            }
        out[name] = cell
    return out


# ------------------------------------------------------------- measurement C

def bdu_decomposition(rows):
    """(b,d,u) at underdetermined hops vs functional hops, plus d-source tag."""
    und, fun = [], []
    tags = defaultdict(lambda: defaultdict(int))
    for r in rows:
        for h in r["hop_detail"]:
            (und if h["underdetermined"] else fun).append(h)
            tags["underdetermined" if h["underdetermined"] else "functional"][str(h["tag"])] += 1
    def pack(hs):
        return {"n": len(hs),
                "b": describe([h["b"] for h in hs]),
                "d": describe([h["d"] for h in hs]),
                "u": describe([h["u"] for h in hs]),
                "a": describe([h["a"] for h in hs]),
                "m": describe([h["m"] for h in hs]),
                "action_mix": dict(_count([h["action"] for h in hs]))}
    return {"underdetermined": pack(und), "functional": pack(fun),
            "d_source_tags": {k: dict(v) for k, v in tags.items()}}


def bdu_by_F(rows):
    """(b,d,u) at the fan-out hop as a function of F -- the dose-response."""
    out = {}
    for F in F_VALUES:
        hs = [h for r in rows if r["F"] == F and r["condition"].startswith("fanout")
              for h in r["hop_detail"] if h["underdetermined"]]
        if hs:
            out[F] = {"n": len(hs),
                      "b": float(np.mean([h["b"] for h in hs])),
                      "d": float(np.mean([h["d"] for h in hs])),
                      "u": float(np.mean([h["u"] for h in hs])),
                      "link_valid": float(np.mean([h["link_valid"] for h in hs
                                                   if h["link_valid"] is not None])),
                      "link_intended": float(np.mean([h["link_intended"] for h in hs
                                                      if h["link_intended"] is not None])),
                      "expected_if_uniform": 1.0 / F}
    return out


def _count(xs):
    c = defaultdict(int)
    for x in xs:
        c[x] += 1
    return c


# ------------------------------------------------------------------- driver

def main():
    cfg = RelAlgConfig()
    if os.path.exists(ROWS) and "--regen" not in sys.argv:
        rows = [json.loads(l) for l in open(ROWS)]
        meta = json.load(open(REPORT))["meta"]
        print(f"loaded {len(rows)} chains")
    else:
        print(f"building {len(CONDITIONS)} conditions x {cfg.n_worlds} worlds "
              f"(seed {cfg.seed}) ...")
        rows, meta = generate(cfg)
        with open(ROWS, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

    report = {"config": cfg.__dict__, "meta": meta, "n_chains": len(rows),
              "A_composition": composition_fidelity(rows, meta),
              "B_localisation": localisation(rows, meta),
              "C_bdu": bdu_decomposition(rows),
              "C_bdu_by_F": bdu_by_F(rows)}
    with open(REPORT, "w") as f:
        json.dump(report, f, indent=1, default=float)
    print_report(report)
    print(f"\n-> {REPORT}")


def print_report(rep):
    A = rep["A_composition"]
    print("\n=== A. COMPOSITION FIDELITY (k constant = load-matched by design) ===")
    print(f"{'condition':>24} {'k':>5} {'specific':>18} {'any-valid':>18} {'path-legal':>11}")
    order = ["functional", "symmetric", "symmetric_baseline"]
    order += [f"fanout_h{h}_F{F}" for h in (1, 2, 3) for F in F_VALUES]
    order += [f"scrambled_h{h}_F{F}" for h in (1, 2, 3) for F in F_VALUES]
    order += [f"fanout_h2_unpadded_F{F}" for F in F_VALUES]
    for name in order:
        if name not in A:
            continue
        a = A[name]
        print(f"{name:>24} {a['k']:>5.0f} "
              f"{a['specific']['acc']:>6.3f}[{a['specific']['ci95'][0]:.2f},{a['specific']['ci95'][1]:.2f}] "
              f"{a['any_valid']['acc']:>6.3f}[{a['any_valid']['ci95'][0]:.2f},{a['any_valid']['ci95'][1]:.2f}] "
              f"{a['all_hops_valid']['acc']:>11.3f}")

    print("\n=== B. FAILURE LOCALISATION: per-hop b / d / u ===")
    print(f"{'condition':>24} " + " ".join(f"{'hop'+str(i):>22}" for i in range(3)))
    for name in order:
        if name not in rep["B_localisation"]:
            continue
        c = rep["B_localisation"][name]
        cells = []
        for i in range(3):
            x = c[str(i)] if str(i) in c else c[i]
            mark = "*" if x["underdet_frac"] > 0.5 else " "
            cells.append(f"{mark}b{x['b']:.2f} d{x['d']:.2f} u{x['u']:.2f}")
        print(f"{name:>24} " + " ".join(f"{s:>22}" for s in cells))
    print("  (* = the structurally underdetermined hop)")

    print("\n=== C. (b,d,u) AT UNDERDETERMINED vs FUNCTIONAL HOPS ===")
    c = rep["C_bdu"]
    for k in ("underdetermined", "functional"):
        x = c[k]
        print(f"  {k:>17} n={x['n']:>5}  b={x['b']['mean']:.3f}  d={x['d']['mean']:.3f}  "
              f"u={x['u']['mean']:.3f}  a={x['a']['mean']:.4f}  m={x['m']['mean']:.4f}")
        print(f"  {'':>17} actions {x['action_mix']}")
    print(f"  d-source tags: {c['d_source_tags']}")

    print("\n=== C'. DOSE-RESPONSE AT THE FAN-OUT HOP (by F) ===")
    print(f"{'F':>3} {'n':>6} {'b':>7} {'d':>7} {'u':>7} {'link valid':>11} "
          f"{'link intended':>14} {'1/F':>7}")
    for F, x in rep["C_bdu_by_F"].items():
        print(f"{F:>3} {x['n']:>6} {x['b']:>7.3f} {x['d']:>7.3f} {x['u']:>7.3f} "
              f"{x['link_valid']:>11.3f} {x['link_intended']:>14.3f} "
              f"{x['expected_if_uniform']:>7.3f}")


if __name__ == "__main__":
    main()
