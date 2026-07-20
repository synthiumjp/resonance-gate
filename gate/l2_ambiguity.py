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

# Calibrated at the freeze (instruments/calibrate_l2.py, seed 880, 4 trials,
# 240 singletons / 60 collisions, lambda=0.75): singleton m_l2 0.9056+-0.0684,
# collision m_l2 exactly 0 (identical keys -> zero variance, so the variance-
# weighted crossing is degenerate; class-mean midpoint used instead).
C_L2 = 0.4528
S_L2 = 0.0342
BETA_L2 = 1.0

# ---------------------------------------------------------------------------
# product-p0 / rg-1.1 SEMANTIC stored-collision detection (notebook E5.2).
#
# The frozen artifact detects stored collisions by KEY IDENTITY (identical
# whitened (subj,rel) vectors -> L2 margin 0), so near-synonym contradictions
# ("Maria lives in Lisbon" vs "Maria resides in Boston") are invisible and the
# system answers both ways. The semantic detector fixes this. It compares two
# stored (subject, relation) keys and calls them the SAME question iff:
#   (i)  the subjects are near-duplicates by RAW registry-embedding cosine
#        >= TAU_COLLIDE  (Maria/Maria's 0.85, Tom Fischer/Fisher 0.75; distinct
#        people ~0.24 -- this axis separates cleanly, so it IS the embedding
#        threshold the fix is built on), AND
#   (ii) the relations are EQUIVALENT (identical, or same synonym class).
#
# Relation equivalence is NOT thresholded on embedding cosine, on purpose:
# measured on the frozen MiniLM registry, raw relation cosine cannot separate
# synonyms from merely-related relations -- "works at"/"is employed by" (true
# synonyms) sit at 0.43, BELOW "studied at"/"works at" (distinct attributes)
# at 0.56 and "lives in"/"was born in" at 0.52. No single cosine threshold
# exists (E5.2 dev study, collision_dev.md). So relation synonymy uses an
# explicit class table; in a product this table is populated from a paraphrase
# resource, and swapping in a relation-paraphrase embedding would let (ii) also
# be a cosine test. The SUBJECT axis is the raw-embedding mechanism the brief
# specified; the relation axis is where the measurement forced an honest
# adaptation (flagged in notebook E5.2 for the registrant's call).
RELATION_SYNONYMS = [
    frozenset({"works at", "is employed by"}),
    frozenset({"lives in", "resides in"}),
]
TAU_COLLIDE = 0.90   # subject raw-embedding cosine threshold (E5.2 dev). Set
                     # structurally ABOVE the measured confusable-distinct-name
                     # ceiling (Tom Baker/Barker 0.78, Chen/Cheng 0.77, ...) so
                     # cross-subject false collisions are excluded by
                     # construction; genuine same-subject collisions sit at
                     # cos 1.0. Near-dup SUBJECT surface forms ("Maria"/
                     # "Maria's", 0.85) fall BELOW this and are deferred to
                     # write-time canonicalization -- no threshold separates
                     # them from confusable distinct surnames (E5.2).
S_COLLIDE = 0.03     # sigmoid slope for the semantic stored d-source


def relation_equiv(r_a, r_b):
    """True iff two relation surfaces denote the same attribute (identical, or
    members of one RELATION_SYNONYMS class)."""
    if r_a == r_b:
        return True
    for cls in RELATION_SYNONYMS:
        if r_a in cls and r_b in cls:
            return True
    return False


def semantic_collision(store, ent_reg, rel_reg, subj, rel, tau=TAU_COLLIDE):
    """Detect a stored collision for the resolved query key (subj, rel).

    Scans ACTIVE L2 records; the 'primary' is the highest-subject-cosine
    equivalent-relation record (the one the system would answer with). A
    conflict is any active record whose relation is EQUIVALENT to rel, whose
    subject raw-embedding cosine to subj is >= tau, and whose object differs
    from the primary's. Returns:
      score      float in [0,1] -- max subject cosine over equivalent-relation
                 records carrying a DIFFERENT object (0 if none); the
                 continuous collision signal (AUROC / gate d-source).
      conflicts  [(triple, provenance, store_idx, subj_cos)] with subj_cos>=tau
                 and object != primary, most-similar first.
      primary    (triple, provenance, store_idx) or None.
    """
    import numpy as np
    e_subj_q = ent_reg.raw_vector(subj)
    cand = []
    for i, meta in enumerate(store.meta):
        if not (store.active[i] and meta):
            continue
        s_i, r_i, o_i = meta["triple"]
        if not relation_equiv(rel, r_i):
            continue
        sc = float(np.dot(e_subj_q, ent_reg.raw_vector(s_i)))
        cand.append((sc, i, (s_i, r_i, o_i), meta["provenance"]))
    if not cand:
        return 0.0, [], None
    cand.sort(reverse=True, key=lambda x: x[0])
    sc0, i0, tr0, pv0 = cand[0]
    primary_obj = tr0[2]
    diff = [(sc, i, tr, pv) for sc, i, tr, pv in cand if tr[2] != primary_obj]
    score = max((sc for sc, *_ in diff), default=0.0)
    conflicts = [(tr, pv, i, sc) for sc, i, tr, pv in diff if sc >= tau]
    conflicts.sort(reverse=True, key=lambda x: x[3])
    return score, conflicts, (tr0, pv0, i0)


class L2Store:
    """Exact per-record store, measurement version (in-memory)."""

    def __init__(self, dim):
        self.dim = dim
        self._keys = []
        self.objs = []
        self.meta = []      # per-record metadata (e.g. provenance) — E3.2
        self.active = []    # tombstone flags: False = retracted/superseded
        self._K = None

    def append(self, subj_vec, rel_vec, obj_id, meta=None):
        self._keys.append(bind(subj_vec, permute(rel_vec, 1)))
        self.objs.append(obj_id)
        self.meta.append(meta)
        self.active.append(True)
        self._K = None
        return len(self.objs) - 1

    def tombstone(self, idx):
        """Mark a record inactive (retraction/supersede); append-only store,
        the entry stays for provenance history."""
        self.active[idx] = False
        self._K = None

    def n_active(self):
        return int(sum(self.active))

    def _key_matrix(self):
        if self._K is None:
            self._K = np.stack(self._keys).astype(np.float32)
        return self._K

    def top2_batch(self, subj_mat, rel_mat):
        """Top-2 L2 key cosines among ACTIVE records for each query row.
        Returns (c1, c2, obj1, obj2); c2/obj2 fall back to 0/-1 when fewer
        than two active records exist."""
        Q = (subj_mat.astype(np.int32)
             * np.roll(rel_mat.astype(np.int32), 1, axis=1)).astype(np.float32)
        cos = (Q @ self._key_matrix().T) / self.dim  # (n_queries, n_records)
        inactive = ~np.asarray(self.active, dtype=bool)
        if inactive.any():
            cos[:, inactive] = -np.inf
        if self.n_active() < 2 or cos.shape[1] < 2:
            best = np.argmax(cos, axis=1)
            c1 = cos[np.arange(len(best)), best].astype(np.float64)
            c1[~np.isfinite(c1)] = 0.0
            return c1, np.zeros_like(c1), np.array(self.objs)[best], np.full(len(c1), -1)
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
