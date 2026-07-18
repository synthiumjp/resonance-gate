"""(b, d, u) opinion from normalised retrieval geometry (plan §4.4 mapping).

    u = 1 - sigmoid(alpha * (z(a) - theta))      # ignorance
    b = (1 - u) * sigmoid(beta * m_z)            # belief   (clean resolution)
    d = (1 - u) * (1 - sigmoid(beta * m_z))      # disbelief/ambiguity (contested)

b + d + u = 1 by construction. Exploratory tunables (values + rationale in
notebook entry 4; tune freely, log every change):

THETA = 0.0 — z_resolution is already zeroed at the hit/null variance-weighted
    crossing, so the natural decision boundary is 0. Load-invariance means this
    single value works at every (k, N) — that is what the normalisation buys.
ALPHA = 1.0 — one pooled-sigma of resolution moves u by the full sigmoid slope;
    hits sit several sigma above 0 below the paging threshold, so u saturates
    cleanly without being twitchy at the boundary.
BETA = 1.0 — same logic on the margin axis: collisions sit ~2 sigma below the
    z_margin zero, singletons ~2 sigma above, so beta=1 separates without
    hand-tuning.
"""

from typing import NamedTuple

import numpy as np

from normalisation import DEFAULT_D, z_margin, z_resolution

THETA = 0.0
ALPHA = 1.0
BETA = 1.0

# Two-source C3 normalisation (E3.2, notebook entries 7-8). Referential
# margins live in raw-embedding space: constants from the Part-0c
# measurement (underspecified mean 0.066, specific mean 0.315).
C_REF = 0.19
S_REF = 0.08


class Opinion(NamedTuple):
    b: float
    d: float
    u: float
    z: float    # normalised resolution (diagnostic)
    m_z: float  # normalised margin (diagnostic)


class Opinion2(NamedTuple):
    """Two-source opinion (E3.2): d carries a source tag so the controller
    can distinguish 'which one do you mean?' from 'two facts on file'."""
    b: float
    d: float
    u: float
    z: float
    tag: str  # 'referential' | 'stored' | 'l1-hint' | 'none'


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=np.float64)))


def opinion(a, m, k, N, D=DEFAULT_D, theta=THETA, alpha=ALPHA, beta=BETA,
            null_moments=None, hit_moments=None):
    """Map raw cleanup geometry (a = s1, m = s1 - s2) at known load k and
    codebook size N to a (b, d, u) opinion. Vectorises over a, m.
    null_moments / hit_moments: EMBEDDED-mode measured calibrations
    (calibrate_null / calibrate_hit); None = analytic + E1-empirical."""
    z = z_resolution(a, k, N, D, null_moments, hit_moments)
    m_z = z_margin(m, k, N, D, null_moments, hit_moments)
    u = 1.0 - sigmoid(alpha * (z - theta))
    pb = sigmoid(beta * m_z)
    b = (1.0 - u) * pb
    d = (1.0 - u) * (1.0 - pb)
    return Opinion(b=b, d=d, u=u, z=z, m_z=m_z)


def opinion_two_source(a, k, N, m_ref=None, m_l2=None, m_l1=None, D=DEFAULT_D,
                       theta=THETA, alpha=ALPHA, beta=BETA,
                       null_moments=None, hit_moments=None):
    """E3.2 two-source (b, d, u): u from L1 resolution as always; the
    ambiguity split takes the MAXIMUM of the available d-sources, each
    z-normalised in its own space:
      - referential: registry top-2 raw-cosine margin m_ref ("which Tom?"),
      - stored: L2 top-2 key margin m_l2 ("two facts on file"),
      - l1-hint: the bundle margin, fast-path only, used when neither
        authoritative source is supplied.
    Scalar inputs only (the interactive path); returns Opinion2 with the
    winning source tag."""
    from l2_ambiguity import C_L2, S_L2  # local import: avoids module cycle

    z = z_resolution(a, k, N, D, null_moments, hit_moments)
    u = float(1.0 - sigmoid(alpha * (z - theta)))
    sources = {}
    if m_ref is not None:
        sources["referential"] = float(1.0 - sigmoid((m_ref - C_REF) / S_REF))
    if m_l2 is not None:
        sources["stored"] = float(1.0 - sigmoid((m_l2 - C_L2) / S_L2))
    if not sources:
        if m_l1 is not None:
            m_z = z_margin(m_l1, k, N, D, null_moments, hit_moments)
            sources["l1-hint"] = float(1.0 - sigmoid(beta * m_z))
        else:
            sources["none"] = 0.0
    tag, p_amb = max(sources.items(), key=lambda kv: kv[1])
    d = (1.0 - u) * p_amb
    b = (1.0 - u) - d
    return Opinion2(b=b, d=d, u=u, z=float(z), tag=tag)
