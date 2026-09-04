"""Ingest-time cross-session entity linking: match-or-create against the
canonical entity store, gated conservatively because a wrong merge (two
different people treated as one) is worse than a missed one for a
contradiction-detection memory -- it manufactures a false contradiction
instead of just losing a fact.

Requires BOTH a high absolute similarity AND a clear margin over the
second-best candidate before auto-merging -- a Fellegi-Sunter-style
three-way match/possible-match/non-match decision
(https://en.wikipedia.org/wiki/Record_linkage), built directly on the
raw-cosine primitives already in encoder/registry.py (Registry.resolve(),
Registry.m_ref()) rather than a new similarity model.

`registry` is duck-typed to any object exposing `__len__` and
`.resolve(term, top=k) -> [(name, cosine), ...]` best-first -- in
production this is an encoder.registry.Registry instance (the same one
service.py already uses for query-time resolution, at the same 0.60
cosine floor as RECALL_RESOLVE_MIN).
"""

from enum import Enum

LINK_MIN_COS = 0.60      # mirrors service.py's RECALL_RESOLVE_MIN
LINK_MIN_MARGIN = 0.05   # reject near-ties as possible-matches, not merges


class Link(Enum):
    CONFIDENT = "confident"   # merge into the existing canonical entity
    POSSIBLE = "possible"     # ambiguous -- don't auto-merge, don't feed
                               # into contradiction detection
    NEW = "new"                # register mention_name as a new entity


def link_entity(registry, mention_name,
                 min_cos=LINK_MIN_COS, min_margin=LINK_MIN_MARGIN):
    """Returns (Link, canonical_name_or_None, margin_or_None)."""
    if len(registry) == 0:
        return Link.NEW, None, None
    hits = registry.resolve(mention_name, top=2)
    if not hits or hits[0][1] < min_cos:
        return Link.NEW, None, None
    margin = hits[0][1] - hits[1][1] if len(hits) > 1 else 1.0
    if margin < min_margin:
        return Link.POSSIBLE, hits[0][0], margin
    return Link.CONFIDENT, hits[0][0], margin
