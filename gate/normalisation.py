"""Load-normalised resolution for the E2 gate.

Analytic anchors (validated against the E1 capacity curves, notebook entry 3):
- mu_hit(k)  = sqrt(2/(pi*k))       — bundling attenuation of a written record.
- mu_null(N) = sqrt(2*ln(N)/D)      — extreme-value statistic of the cleanup
  null over an N-entry codebook. Load-invariant, rises with N. (First-order
  form; it overshoots the measured floor by ~1 null-sd, which is a known
  extreme-value correction — tolerated, see the validation test.)

Sigma terms are empirical, interpolated from substrate/capacity_curves.csv
(measured at D=8192, N=500; re-derivable by rerunning the sweep). For other D
they are rescaled by sqrt(8192/D), the crosstalk scaling.

z(a) is referenced to BOTH anchors: the zero point is the variance-weighted
crossing between the hit and null distributions,
    c(k, N) = (mu_hit*sigma_null + mu_null*sigma_hit) / (sigma_hit + sigma_null),
scaled by the pooled sigma. k and N are always known exactly — the substrate
wrote every item — so this is not an estimate, it is bookkeeping.

Capacity law: separability dies at k_max(D, N) = D/(pi*ln N) (where
mu_hit(k) = mu_null(N)). paging_threshold(D, N, safety=0.5) keeps the live
bundle in the high-separability regime (safety fraction is a tunable, logged
in the notebook). is_saturated flags k where mu_hit is within gamma null-sd
of the floor — past that the gate must not emit confident belief.
"""

import csv
import os
import numpy as np

DEFAULT_D = 8192
_SWEEP_D = 8192  # D at which capacity_curves.csv was measured
CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "substrate", "capacity_curves.csv"
)

_sigma_table = None


def _sigmas(path=None):
    global _sigma_table
    if _sigma_table is None or path is not None:
        with open(path or CSV_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
        _sigma_table = {
            "k": np.array([float(r["k"]) for r in rows]),
            "a_hit_mean": np.array([float(r["a_hit_mean"]) for r in rows]),
            "a_hit_sd": np.array([float(r["a_hit_sd"]) for r in rows]),
            "a_miss_mean": np.array([float(r["a_miss_mean"]) for r in rows]),
            "a_miss_sd": np.array([float(r["a_miss_sd"]) for r in rows]),
            "m_hit_sd": np.array([float(r["m_hit_sd"]) for r in rows]),
        }
    return _sigma_table


def mu_hit(k):
    """Expected resolution of a written record at load k: sqrt(2/(pi*k))."""
    return np.sqrt(2.0 / (np.pi * np.asarray(k, dtype=np.float64)))


def mu_null(N, D=DEFAULT_D):
    """Expected null floor for an N-entry codebook at dimension D."""
    return np.sqrt(2.0 * np.log(N) / D)


def sigma_hit(k, D=DEFAULT_D):
    """Empirical sd of a on hits, interpolated over the E1 k grid."""
    t = _sigmas()
    return np.interp(k, t["k"], t["a_hit_sd"]) * np.sqrt(_SWEEP_D / D)


def sigma_null(D=DEFAULT_D):
    """Empirical sd of a on misses (load-invariant in E1)."""
    return float(np.mean(_sigmas()["a_miss_sd"])) * np.sqrt(_SWEEP_D / D)


def sigma_margin(k, D=DEFAULT_D):
    """Empirical sd of the margin m on hits, interpolated over the E1 k grid."""
    t = _sigmas()
    return np.interp(k, t["k"], t["m_hit_sd"]) * np.sqrt(_SWEEP_D / D)


def _null_moments(N, D, null_moments=None):
    """ANALYTIC mode (default): first-order extreme-value anchors, correct for
    synthetic i.i.d. codebooks. EMBEDDED mode: pass null_moments=(mu, sigma)
    measured on the actual codebook via calibrate_null — correlated embeddings
    elevate the floor beyond the analytic form (E3, notebook entry 5). The
    k side and all downstream logic are unchanged."""
    if null_moments is not None:
        return float(null_moments[0]), float(null_moments[1])
    return float(mu_null(N, D)), sigma_null(D)


def _hit_moments(k, D, hit_moments=None):
    """ANALYTIC/E1-empirical hit moments by default. EMBEDDED full-measured
    mode (E3.1): pass hit_moments=(scale, k_refs, sd_refs) from calibrate_hit —
    mean model scale*sqrt(2/(pi*k)) (analytic shape scaled to fit), sd
    interpolated over the measured reference loads."""
    if hit_moments is None:
        return mu_hit(k), sigma_hit(k, D)
    scale, k_refs, sd_refs = hit_moments
    return float(scale) * mu_hit(k), np.interp(k, k_refs, sd_refs)


def _crossing(k, N, D=DEFAULT_D, null_moments=None, hit_moments=None):
    mn, sn = _null_moments(N, D, null_moments)
    mh, sh = _hit_moments(k, D, hit_moments)
    return (mh * sn + mn * sh) / (sh + sn)


def z_resolution(a, k, N, D=DEFAULT_D, null_moments=None, hit_moments=None):
    """Normalised resolution: 0 at the hit/null variance-weighted crossing,
    unit = pooled sigma. Positive → written-signal side, negative → null side.
    Load- and codebook-invariant by construction: the same threshold means the
    same thing at every (k, N)."""
    _, sn = _null_moments(N, D, null_moments)
    _, sh = _hit_moments(k, D, hit_moments)
    s = 0.5 * (sh + sn)
    return (np.asarray(a, dtype=np.float64)
            - _crossing(k, N, D, null_moments, hit_moments)) / s


def z_margin(m, k, N, D=DEFAULT_D, null_moments=None, hit_moments=None):
    """Normalised margin: 0 midway between the expected clean-singleton margin
    (mu_hit - mu_null) and the expected collision margin (~0). Positive →
    singleton-like, negative → ambiguity-like."""
    mn, _ = _null_moments(N, D, null_moments)
    mh, _ = _hit_moments(k, D, hit_moments)
    c = 0.5 * (mh - mn)
    return (np.asarray(m, dtype=np.float64) - c) / sigma_margin(k, D)


def calibrate_hit(subj_matrix, rel_matrix, obj_codebook, k_refs=(25, 50, 100),
                  trials=3, seed=98):
    """EMBEDDED full-measured hit moments: plant known records at each
    reference load, retrieve them, and fit scale in mu = scale*sqrt(2/(pi*k))
    by least squares; sd measured per reference load (interpolate between,
    clamp beyond). Recompute alongside calibrate_null when the codebook grows."""
    from map_ops import bundle, encode_record

    rng = np.random.default_rng(seed)
    dim = obj_codebook.matrix.shape[1]
    n_obj = len(obj_codebook)
    means, sds = [], []
    for k in k_refs:
        a_all = []
        for _ in range(trials):
            subj_idx = rng.permutation(subj_matrix.shape[0])[:k]
            rel_idx = rng.integers(rel_matrix.shape[0], size=k)
            obj_idx = rng.integers(n_obj, size=k)
            B = bundle(
                [encode_record(subj_matrix[subj_idx[i]], rel_matrix[rel_idx[i]],
                               obj_codebook.matrix[obj_idx[i]]) for i in range(k)],
                seed=int(rng.integers(2**31)),
            )
            noisy = np.roll(
                B.astype(np.int32) * subj_matrix[subj_idx].astype(np.int32)
                * np.roll(rel_matrix[rel_idx].astype(np.int32), 1, axis=1),
                -2, axis=1,
            )
            cos = (noisy.astype(np.float32) @ obj_codebook.matrix.T.astype(np.float32)) / dim
            a_all.append(cos.max(axis=1).astype(np.float64))
        a_all = np.concatenate(a_all)
        means.append(a_all.mean())
        sds.append(a_all.std(ddof=1))
    mh = mu_hit(np.asarray(k_refs, dtype=np.float64))
    scale = float(np.dot(means, mh) / np.dot(mh, mh))
    return scale, np.asarray(k_refs, dtype=np.float64), np.asarray(sds)


def calibrate_null(subj_matrix, rel_matrix, obj_codebook, k=100, trials=4, seed=99):
    """EMBEDDED-mode null calibration, measured on the ACTUAL codebook.

    Builds `trials` fresh substrates from the supplied item-vector pools
    (k written records each), queries never-written (subj, rel) pairs, and
    returns (mean, sd) of the a_miss statistic. Recompute whenever the
    codebook grows; k and N logic elsewhere are unchanged. a_miss was
    load-invariant in E1, so one k suffices."""
    from map_ops import bundle, encode_record  # substrate stays a separate module

    rng = np.random.default_rng(seed)
    dim = obj_codebook.matrix.shape[1]
    n_subj, n_rel = subj_matrix.shape[0], rel_matrix.shape[0]
    n_obj = len(obj_codebook)
    if n_subj < 2 * k:
        raise ValueError("need at least 2k subject vectors to calibrate")
    a_miss = []
    for _ in range(trials):
        subj_idx = rng.permutation(n_subj)[: 2 * k]
        writers, probes = subj_idx[:k], subj_idx[k:]
        rel_idx = rng.integers(n_rel, size=2 * k)
        obj_idx = rng.integers(n_obj, size=k)
        B = bundle(
            [
                encode_record(subj_matrix[writers[i]], rel_matrix[rel_idx[i]],
                              obj_codebook.matrix[obj_idx[i]])
                for i in range(k)
            ],
            seed=int(rng.integers(2**31)),
        )
        noisy = np.roll(
            B.astype(np.int32) * subj_matrix[probes].astype(np.int32)
            * np.roll(rel_matrix[rel_idx[k:]].astype(np.int32), 1, axis=1),
            -2, axis=1,
        )
        cos = (noisy.astype(np.float32) @ obj_codebook.matrix.T.astype(np.float32)) / dim
        a_miss.append(cos.max(axis=1).astype(np.float64))
    a_miss = np.concatenate(a_miss)
    return float(np.mean(a_miss)), float(np.std(a_miss, ddof=1))


def k_max(D, N):
    """Capacity law: load at which mu_hit(k) = mu_null(N); separability dies."""
    return D / (np.pi * np.log(N))


def paging_threshold(D, N, safety=0.5):
    """Max live-bundle load before paging to L2. safety=0.5 keeps the bundle in
    the high-separability regime (tunable; logged in notebook entry 4)."""
    return safety * k_max(D, N)


def k_sat(D=DEFAULT_D, N=500, gamma=1.0, null_moments=None, hit_moments=None):
    """Load beyond which the expected hit signal is within gamma null-sd of
    the null floor: solve scale*sqrt(2/(pi*k)) = mu_null + gamma*sigma_null."""
    mn, sn = _null_moments(N, D, null_moments)
    scale = 1.0 if hit_moments is None else float(hit_moments[0])
    a_star = mn + gamma * sn
    return 2.0 * scale**2 / (np.pi * a_star**2)


def is_saturated(k, N, D=DEFAULT_D, gamma=1.0, null_moments=None, hit_moments=None):
    """True when the expected hit signal at load k is within gamma null-sd of
    the null floor — the gate must flag this instead of emitting confident b."""
    mn, sn = _null_moments(N, D, null_moments)
    mh, _ = _hit_moments(k, D, hit_moments)
    return bool(mh <= mn + gamma * sn)
