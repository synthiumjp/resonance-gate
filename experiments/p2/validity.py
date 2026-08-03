"""Validity screening + paired-change testing for RG's own claims
(entry 145). Both methods are Cacioli's, applied to this project's data.

validity_screen()  -- arXiv:2604.17714 portable protocol. Screens a
    confidence signal from one 2x2 contingency table (correctness x
    binarised confidence). If the signal screens INVALID, the protocol
    designates type-2 AUROC, risk-coverage curves and selective-prediction
    /abstention systems built on it as unsafe to interpret -- which is
    precisely what RG's trust dial is. Run this before publishing the dial.

mcnemar()          -- the correct test for OUR data. "Beyond the Mean"
    (arXiv:2604.27405) shows greedy single-shot comparison misses 42% of
    reliable changes and falsely flags 25% of stable items, and its RCI
    needs K stochastic samples per item to form a continuous per-item
    score. Every RG screen ran greedy at T=0, so RCI is not computable
    from what we hold; McNemar's exact test on discordant pairs is the
    honest instrument for paired binary verdicts. The K-sampling debt is
    recorded rather than papered over.
"""
import math
from collections import Counter


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def validity_screen(correct, confident):
    """correct, confident: equal-length boolean sequences.
    Returns indices, CIs and the three-tier verdict."""
    a = sum(1 for c, f in zip(correct, confident) if c and f)
    b = sum(1 for c, f in zip(correct, confident) if not c and f)
    c_ = sum(1 for c, f in zip(correct, confident) if c and not f)
    d = sum(1 for c, f in zip(correct, confident) if not c and not f)
    n = a + b + c_ + d
    out = {"a": a, "b": b, "c": c_, "d": d, "n": n}
    if min(a, b, c_, d) < 5:
        out["tier"] = "Insufficient data"
        return out
    n_corr, n_inc = a + c_, b + d
    L = b / n_inc                       # P(confident | incorrect)
    Fp = c_ / n_corr                    # P(not confident | correct)
    RBS = Fp - (1 - L)
    TRIN = max(a + b, c_ + d) / n
    L_lo, _ = _wilson(b, n_inc)
    Fp_lo, _ = _wilson(c_, n_corr)
    se = math.sqrt(Fp * (1 - Fp) / n_corr + L * (1 - L) / n_inc)
    RBS_lo = RBS - 1.96 * se
    flags = []
    if Fp >= 0.50:
        flags.append(("Fp", "invalid" if Fp_lo > 0.40 else "indeterminate"))
    if L >= 0.95:
        flags.append(("L", "invalid" if L_lo > 0.90 else "indeterminate"))
    if RBS > 0:
        flags.append(("RBS", "invalid" if RBS_lo > 0 else "indeterminate"))
    tier = ("Invalid" if any(f[1] == "invalid" for f in flags)
            else "Indeterminate" if flags else "Valid")
    out.update({"L": L, "Fp": Fp, "RBS": RBS, "TRIN": TRIN,
                "L_ci_lo": L_lo, "Fp_ci_lo": Fp_lo, "RBS_ci_lo": RBS_lo,
                "flags": flags, "tier": tier,
                "trin_warning": TRIN >= 0.95})
    return out


def mcnemar(base, cand):
    """Exact McNemar on paired binary outcomes (base/cand: bool sequences).
    Returns discordant counts and the two-sided exact binomial p."""
    b01 = sum(1 for x, y in zip(base, cand) if not x and y)   # base wrong -> cand right
    b10 = sum(1 for x, y in zip(base, cand) if x and not y)   # base right -> cand wrong
    n = b01 + b10
    if n == 0:
        return {"gained": 0, "lost": 0, "p": 1.0, "reliable": False}
    k = min(b01, b10)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))
    return {"gained": b01, "lost": b10, "net": b01 - b10, "p": p,
            "reliable": p < 0.05}
