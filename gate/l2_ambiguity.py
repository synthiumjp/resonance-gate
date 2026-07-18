"""E3.1 task 3 (fork a): L2 top-2 ambiguity detection.

The L2 cleanup store holds every written record EXACTLY (append-only, no
bundle, no crosstalk): key = subj * permute(rel, 1), value = the record's
object. An ambiguity is then a fact about the STORE — two records under the
same key — not about bundle geometry, so the d signal should not degrade
with load. The L1 margin remains a fast-path hint only; nothing in the
default gate changes (this module is opt-in).

Measurement mapping (same (b,d,u) shape as opinion.py):
    u  — unchanged, from the L1 resolution z(a).
    d  = (1 - u) * (1 - sigmoid(BETA_L2 * (m_l2 - C_L2) / S_L2))
    b  = (1 - u) - d
with m_l2 = top1 - top2 of the L2 KEY cosines. Exact-match keys give cosine
1.0, so a collision pair gives m_l2 = 0; a singleton's top2 is its most
confusable stored neighbour (partial match ~ cos(subj_i, subj) *
cos(rel_i, rel)). C_L2/S_L2/BETA_L2 are exploratory tunables (notebook
entry 6); AUC-based measurements are insensitive to them.
"""

import numpy as np

from map_ops import bind, permute
from opinion import sigmoid

C_L2 = 0.15   # midpoint between collision margin (0) and typical singleton margin
S_L2 = 0.08   # spread of singleton margins under confusable neighbours
BETA_L2 = 1.0


class L2Store:
    """Exact per-record store, measurement version (in-memory)."""

    def __init__(self, dim):
        self.dim = dim
        self._keys = []
        self.objs = []
        self._K = None

    def append(self, subj_vec, rel_vec, obj_id):
        self._keys.append(bind(subj_vec, permute(rel_vec, 1)))
        self.objs.append(obj_id)
        self._K = None

    def _key_matrix(self):
        if self._K is None:
            self._K = np.stack(self._keys).astype(np.float32)
        return self._K

    def top2_batch(self, subj_mat, rel_mat):
        """Top-2 L2 key cosines for each query row. Returns (c1, c2, obj1,
        obj2) arrays; c2/obj2 fall back to 0/-1 for a single-record store."""
        Q = (subj_mat.astype(np.int32)
             * np.roll(rel_mat.astype(np.int32), 1, axis=1)).astype(np.float32)
        cos = (Q @ self._key_matrix().T) / self.dim  # (n_queries, n_records)
        if cos.shape[1] == 1:
            c1 = cos[:, 0].astype(np.float64)
            return c1, np.zeros_like(c1), np.array(self.objs)[np.zeros(len(c1), int)], \
                np.full(len(c1), -1)
        top2 = np.argpartition(-cos, 1, axis=1)[:, :2]
        rows = np.arange(cos.shape[0])
        pair = cos[rows[:, None], top2]
        order = np.argsort(-pair, axis=1)
        srt = pair[rows[:, None], order]
        idx = top2[rows[:, None], order]
        objs = np.array(self.objs)
        return (srt[:, 0].astype(np.float64), srt[:, 1].astype(np.float64),
                objs[idx[:, 0]], objs[idx[:, 1]])


def l2_opinion_parts(u, m_l2, c_l2=C_L2, s_l2=S_L2, beta=BETA_L2):
    """Split (1-u) into (b, d) using the L2 margin instead of the L1 margin."""
    pb = sigmoid(beta * (np.asarray(m_l2, dtype=np.float64) - c_l2) / s_l2)
    b = (1.0 - u) * pb
    d = (1.0 - u) * (1.0 - pb)
    return b, d
