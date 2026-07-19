"""E4 type-2 apparatus. docs/ contains no apparatus spec or worked example
(checked 2026-07-19 — only the project plan), so this is implemented from
the standard literature and validated by synthetic-known-answer tests
(simulated observer with specified meta-sensitivity; recover it), as the
stage brief directs. Reconcile against the Synthium apparatus doc if it
lands before the freeze.

Components:
  - pseudo_2afc: seeded mapping of (confidence, correctness) single-interval
    data into 2AFC pairs (one correct + one incorrect item per pair, interval
    order randomised) — the construction the AUROC2 and meta-d' fits consume.
  - auroc2: type-2 AUC (P(conf_correct > conf_incorrect), ties half) —
    computed rank-based; identical in expectation to pseudo-2AFC pc.
  - paired_bootstrap: B resamples over ITEMS shared by all sources ->
    per-source CIs and pairwise-difference CIs. Reports B and seed.
  - ece: expected calibration error, 10 equal-width bins on [0, 1].
  - meta_d_prime: response-conditional meta-d' (Maniscalco & Lau 2012 form),
    equal-variance Gaussian, symmetric criteria, MLE via Nelder-Mead, on
    SINGLE-INTERVAL data: type-1 d' from the system's real accuracy;
    ratings = confidence quantile bins (4) conditioned on correctness.
    (Pairing by confidence would conflate type-1 and type-2 — validated by
    the known-answer tests.) M-ratio = meta-d'/d'.
    Eligibility window: 0.55 <= accuracy <= 0.95. Guggenmos low-d'
    EXCLUSION (d' < 0.2 or degenerate rating table) — items are excluded,
    never force-fit; the return marks ineligibility explicitly.
"""

import numpy as np

_SQRT2 = np.sqrt(2.0)


def _norm_cdf(x):
    from math import erf
    x = np.asarray(x, dtype=np.float64)
    return 0.5 * (1.0 + np.vectorize(erf)(x / _SQRT2))


def _norm_ppf(p):
    # Acklam's rational approximation; adequate far beyond our precision needs
    p = np.asarray(p, dtype=np.float64)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p = np.clip(p, 1e-12, 1 - 1e-12)
    out = np.empty_like(p)
    lo, hi = p < 0.02425, p > 1 - 0.02425
    mid = ~(lo | hi)
    if mid.any():
        q = p[mid] - 0.5
        r = q * q
        out[mid] = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
                    / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1))
    for mask, sign in ((lo, 1.0), (hi, -1.0)):
        if mask.any():
            q = np.sqrt(-2 * np.log(np.where(sign > 0, p[mask], 1 - p[mask])))
            out[mask] = sign * (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) \
                / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    return out


def auroc2(conf, correct):
    """Type-2 AUC: P(conf on a correct item > conf on an incorrect item)."""
    conf = np.asarray(conf, dtype=np.float64)
    correct = np.asarray(correct, dtype=bool)
    pos, neg = conf[correct], conf[~correct]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    both = np.concatenate([pos, neg])
    order = both.argsort(kind="mergesort")
    ranks = np.empty(len(both))
    ranks[order] = np.arange(1, len(both) + 1)
    sv = both[order]
    i = 0
    while i < len(both):
        j = i
        while j + 1 < len(both) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def pseudo_2afc(conf, correct, seed, n_pairs=None):
    """Seeded pseudo-2AFC mapping: pair each correct item with a random
    incorrect item (with replacement over the smaller class), randomise
    interval order. Returns dict with stimulus (0=correct-in-A), response,
    acc, and |conf difference| for rating construction."""
    rng = np.random.default_rng(seed)
    conf = np.asarray(conf, dtype=np.float64)
    correct = np.asarray(correct, dtype=bool)
    pos, neg = conf[correct], conf[~correct]
    if len(pos) == 0 or len(neg) == 0:
        return None
    n = n_pairs or max(len(pos), len(neg))
    ci = pos[rng.integers(len(pos), size=n)]
    wi = neg[rng.integers(len(neg), size=n)]
    stim = rng.integers(2, size=n)              # 0: correct in interval A
    conf_a = np.where(stim == 0, ci, wi)
    conf_b = np.where(stim == 0, wi, ci)
    diff = conf_a - conf_b
    # ties broken by a seeded coin — deterministic given seed
    resp = np.where(diff > 0, 0, np.where(diff < 0, 1, rng.integers(2, size=n)))
    return {"stim": stim, "resp": resp, "acc": (resp == stim),
            "evidence": diff, "rating_raw": np.abs(diff)}


def ece(conf, correct, n_bins=10):
    """Expected calibration error; conf must already live on [0, 1]."""
    conf = np.clip(np.asarray(conf, dtype=np.float64), 0, 1)
    correct = np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, n_bins + 1)
    out, n = 0.0, len(conf)
    for i in range(n_bins):
        m = (conf >= edges[i]) & (conf < edges[i + 1] if i < n_bins - 1 else conf <= 1)
        if m.any():
            out += m.sum() / n * abs(correct[m].mean() - conf[m].mean())
    return out


def _quantile_ratings(raw, n_bins=4):
    qs = np.quantile(raw, np.linspace(0, 1, n_bins + 1)[1:-1])
    return np.searchsorted(qs, raw, side="right")  # 0..n_bins-1


def _nelder_mead(f, x0, steps, iters=400):
    n = len(x0)
    simplex = [np.array(x0, dtype=np.float64)]
    for i in range(n):
        p = np.array(x0, dtype=np.float64)
        p[i] += steps[i]
        simplex.append(p)
    vals = [f(p) for p in simplex]
    for _ in range(iters):
        order = np.argsort(vals)
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        centroid = np.mean(simplex[:-1], axis=0)
        xr = centroid + (centroid - simplex[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = centroid + 2 * (centroid - simplex[-1])
            fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = centroid + 0.5 * (simplex[-1] - centroid)
            fc = f(xc)
            if fc < vals[-1]:
                simplex[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    simplex[i] = simplex[0] + 0.5 * (simplex[i] - simplex[0])
                    vals[i] = f(simplex[i])
    order = np.argsort(vals)
    return simplex[order[0]], vals[order[0]]


def meta_d_prime(conf, correct, seed, n_rating_bins=4,
                 acc_window=(0.55, 0.95), d_min=0.2):
    """Response-conditional meta-d' on SINGLE-INTERVAL data: the type-1 axis
    is the system's real accuracy (never a confidence-derived pick — pairing
    by confidence would conflate type-1 and type-2); ratings are confidence
    quantile bins conditioned on actual correctness. seed reserved for
    resolving degenerate quantile ties deterministically.

    Returns dict: eligible (bool), reason, d_prime, meta_d, m_ratio.
    Eligibility window and the Guggenmos low-d' rule are EXCLUSIONS: an
    ineligible sample returns eligible=False and no fitted values."""
    conf = np.asarray(conf, dtype=np.float64)
    correct = np.asarray(correct, dtype=bool)
    if correct.all() or not correct.any():
        return {"eligible": False, "reason": "single-class sample"}
    acc = float(correct.mean())
    if not (acc_window[0] <= acc <= acc_window[1]):
        return {"eligible": False, "reason": f"accuracy {acc:.3f} outside window",
                "accuracy": acc}
    # d' on the SAME balanced-evidence axis the meta fit uses (accuracy =
    # Phi(d'/2), i.e. d' = 2 z(pc)); the convention cancels in M-ratio.
    d_prime = float(2.0 * _norm_ppf(acc))
    if d_prime < d_min:
        return {"eligible": False, "reason": f"d'={d_prime:.3f} < {d_min} (Guggenmos exclusion)",
                "accuracy": acc, "d_prime": d_prime}

    ratings = _quantile_ratings(conf, n_rating_bins)
    # counts[correct_response, rating]
    counts = np.zeros((2, n_rating_bins))
    for corr in (0, 1):
        m = correct == bool(corr)
        for r in range(n_rating_bins):
            counts[corr, r] = np.sum(ratings[m] == r)
    if (counts.sum(axis=1) == 0).any():
        return {"eligible": False, "reason": "degenerate rating table",
                "accuracy": acc, "d_prime": d_prime}

    # SDT model on the balanced 2AFC axis: evidence x ~ N(+-meta_d/2, 1),
    # type-1 criterion at 0; type-2 criteria t_1 < ... < t_{k-1} (>0,
    # symmetric) partition |x| into ratings. Fit by multinomial MLE.
    def nll(params):
        md = params[0]
        ts = np.sort(np.abs(params[1:]))
        if md < 0 or md > 6:
            return 1e9
        edges = np.concatenate([[0.0], ts, [np.inf]])
        tot = 0.0
        mu = md / 2.0
        # response correct: x on the stimulus side; incorrect: opposite side
        for corr in (0, 1):
            sign = 1.0 if corr else -1.0
            probs = []
            for r in range(n_rating_bins):
                lo, hi = edges[r], edges[r + 1]
                pr = (_norm_cdf(hi - sign * mu) - _norm_cdf(lo - sign * mu))
                probs.append(max(float(pr), 1e-12))
            probs = np.array(probs)
            probs /= probs.sum()
            tot -= float(np.sum(counts[corr] * np.log(probs)))
        return tot

    x0 = [d_prime] + list(d_prime / 2.0 * np.linspace(0.5, 1.5, n_rating_bins - 1))
    best, _ = _nelder_mead(nll, x0, [0.25] + [0.1] * (n_rating_bins - 1))
    meta_d = float(best[0])
    return {"eligible": True, "reason": "", "accuracy": acc,
            "d_prime": d_prime, "meta_d": meta_d,
            "m_ratio": meta_d / d_prime if d_prime > 0 else np.nan}


def paired_bootstrap(sources, correct, B=2000, seed=1234):
    """Bootstrap over items, shared across all sources (paired). Returns per-
    source AUROC2 with 95% CI and per-pair difference CIs. Reports B, seed."""
    rng = np.random.default_rng(seed)
    names = list(sources)
    correct = np.asarray(correct, dtype=bool)
    n = len(correct)
    point = {k: auroc2(sources[k], correct) for k in names}
    boots = {k: [] for k in names}
    diffs = {(a, b): [] for i, a in enumerate(names) for b in names[i + 1:]}
    for _ in range(B):
        idx = rng.integers(n, size=n)
        c = correct[idx]
        if c.all() or (~c).any() is False or not c.any():
            continue
        vals = {k: auroc2(np.asarray(sources[k])[idx], c) for k in names}
        for k in names:
            boots[k].append(vals[k])
        for (a, b) in diffs:
            diffs[(a, b)].append(vals[a] - vals[b])
    out = {"B": B, "seed": seed, "point": point, "ci": {}, "diff_ci": {}, "diff_sd": {}}
    for k in names:
        v = np.array(boots[k])
        out["ci"][k] = (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))
    for pair, v in diffs.items():
        v = np.array(v)
        out["diff_ci"][pair] = (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))
        out["diff_sd"][pair] = float(np.std(v, ddof=1))
    return out
