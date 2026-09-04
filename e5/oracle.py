"""E5.1 registered-null-to-be: the audit's zero-parameter exact-key
store-membership oracle, plus a one-parameter variant.

ORACLE      — 1.0 if any ACTIVE L2 record exists under the exact resolved
              (subject, relation) key, else 0.0. Computable by the system
              itself (the L2 store is exact); zero fitted parameters.
ORACLE+cos  — membership + top-1 cleanup cosine: score = member + a, with
              a in [0, ~0.15] at these loads, so members always rank above
              non-members and ties within each class break by retrieval
              strength. One "parameter" in the sense that it consumes one
              geometry scalar; nothing is fitted.

These are the comparators that make "endogenous" a claim: a gate that
cannot beat ORACLE on a confusable corpus is a membership test with extra
steps (audit A1)."""

import numpy as np


def membership(mem, subj, rel):
    """True iff an ACTIVE record exists under the exact (subj, rel) key.
    subj/rel must already be registry-resolved names (the same resolution
    the query path applies)."""
    for i, meta in enumerate(mem.store.meta):
        if not (mem.store.active[i] and meta):
            continue
        s, r, _ = meta["triple"]
        if s == subj and r == rel:
            return True
    return False


def oracle_scores(mem, rows):
    """(oracle, oracle_plus_cos) arrays for phase-c-style row dicts that
    carry resolved 'subj', 'rel' and the cleanup resolution 'a'."""
    member = np.array([float(membership(mem, r["subj"], r["rel"]))
                       for r in rows])
    a = np.array([float(r["a"]) for r in rows])
    return member, member + a
