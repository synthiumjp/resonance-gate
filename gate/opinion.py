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


class Opinion(NamedTuple):
    b: float
    d: float
    u: float
    z: float    # normalised resolution (diagnostic)
    m_z: float  # normalised margin (diagnostic)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=np.float64)))


def opinion(a, m, k, N, D=DEFAULT_D, theta=THETA, alpha=ALPHA, beta=BETA,
            null_moments=None):
    """Map raw cleanup geometry (a = s1, m = s1 - s2) at known load k and
    codebook size N to a (b, d, u) opinion. Vectorises over a, m.
    null_moments: EMBEDDED-mode measured (mu, sigma) of the null floor;
    None = analytic (synthetic substrates)."""
    z = z_resolution(a, k, N, D, null_moments)
    m_z = z_margin(m, k, N, D, null_moments)
    u = 1.0 - sigmoid(alpha * (z - theta))
    pb = sigmoid(beta * m_z)
    b = (1.0 - u) * pb
    d = (1.0 - u) * (1.0 - pb)
    return Opinion(b=b, d=d, u=u, z=z, m_z=m_z)
