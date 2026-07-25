"""_cluster (run_profile_full.py) regression tests -- entry 95's clustering fix.

Ground the fix in the failure it actually caused: run_profile_full._cluster
merged same-slot values on ANY shared content token. Fine for short values
("melbourne" / "melbourne australia" -- both readings ARE the same place),
destructive for v5's long narrative values (up to ~15 words): two distinct
facts sharing one generic tail token ("ai", "understanding", "focus")
collided, and the absorbed fact's specific wording was silently discarded
(measured on real cached v5 extraction, see cache_u10_v5_17b.jsonl -- e.g.
"belief in the power of AI to enhance understanding of human behavior" and
"emotional motivation to seek companionship and empathetic interaction
through AI" shared only the token "ai" and were merging into one cluster
under the old rule).

Fix: merge only when token-overlap is a MAJORITY of the SMALLER token set --
len(toks & cl["core"]) / min(len(toks), len(cl["core"])) >= 0.5 -- where
cl["core"] is the FIRST (highest-mention) variant's token set, fixed for the
life of the cluster. cl["toks"] keeps accumulating the UNION of every merged
variant (unchanged; wire nodes read cl["toks"] downstream) -- but the ratio
test uses cl["core"], NOT cl["toks"], specifically to prevent snowballing:
if the union were used as the comparison set, each merge would grow it,
making the NEXT candidate's overlap ratio easier to clear even though the
candidate shares nothing with the cluster's ORIGINAL meaning.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for p in (_HERE, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from run_profile_full import _cluster


def _entries(*vals_and_n):
    """[(value, n), ...] -> the {value: {"n":.., "recs":[...]}} shape _cluster
    takes. recs are dummy (date, uuid) pairs, one per mention, so cl["n"]
    and len(cl["recs"]) can both be checked."""
    out = {}
    for val, n in vals_and_n:
        out[val] = {"n": n, "recs": [(f"2026-01-{i+1:02d}", f"c{i}") for i in range(n)]}
    return out


def _labels(clusters):
    return {c["label"] for c in clusters}


# --------------------------------------------------------------------------
# short-value merging preserved (the ANY-shared-token case still holds when
# the shared content genuinely is most of the smaller value)
# --------------------------------------------------------------------------

def test_short_values_still_merge():
    entries = _entries(("melbourne", 3), ("melbourne australia", 1))
    clusters = _cluster(entries)
    assert len(clusters) == 1
    cl = clusters[0]
    assert cl["label"] == "melbourne"          # higher-n variant sorts first
    assert cl["n"] == 4
    assert len(cl["recs"]) == 4
    # downstream (wire) query matching still sees the UNION of tokens
    assert cl["toks"] >= {"melbourne", "australia"}


def test_short_values_merge_either_mention_order():
    # same pair, "melbourne australia" mentioned more -> becomes the core;
    # "melbourne" alone (1 token) is still a majority-overlap subset of it.
    entries = _entries(("melbourne australia", 3), ("melbourne", 1))
    clusters = _cluster(entries)
    assert len(clusters) == 1
    assert clusters[0]["n"] == 4


def test_near_duplicate_short_values_merge():
    entries = _entries(("sydney", 2), ("sydney australia", 2), ("sydney nsw", 1))
    clusters = _cluster(entries)
    assert len(clusters) == 1
    assert clusters[0]["n"] == 5


# --------------------------------------------------------------------------
# narrative non-collision: distinct long values sharing one generic tail
# token must NOT merge (the bug this fix targets, reproduced from real
# cache_u10_v5_17b.jsonl values)
# --------------------------------------------------------------------------

def test_narrative_values_do_not_collide_on_shared_tail_token():
    entries = _entries(
        ("belief in the power of ai to enhance understanding of human behavior", 2),
        ("emotional motivation to seek companionship and empathetic interaction "
         "through ai", 1),
    )
    clusters = _cluster(entries)
    assert len(clusters) == 2
    assert _labels(clusters) == {
        "belief in the power of ai to enhance understanding of human behavior",
        "emotional motivation to seek companionship and empathetic interaction "
        "through ai",
    }
    # each cluster keeps its OWN mention count/receipts -- nothing absorbed
    ns = sorted(c["n"] for c in clusters)
    assert ns == [1, 2]


def test_narrative_values_do_not_collide_example_two():
    entries = _entries(
        ("solitude for recharging and gaining clarity", 2),
        ("coffee for alertness and focus", 1),
    )
    clusters = _cluster(entries)
    assert len(clusters) == 2


def test_narrative_values_with_genuine_majority_overlap_still_merge():
    # a real near-restatement (same value, one word added) SHOULD still merge
    # -- the fix narrows the criterion, it does not disable clustering.
    entries = _entries(
        ("strategic planning and delegation for effective communication", 2),
        ("strategic planning and delegation", 1),
    )
    clusters = _cluster(entries)
    assert len(clusters) == 1
    assert clusters[0]["n"] == 3


# --------------------------------------------------------------------------
# snowball prevention: A merges B (majority overlap); C shares one token
# with B's tail but not with A's core -> C must stay separate, even though
# the OLD union-based comparison (or a naive "compare against the growing
# cluster") would have let C in via B's contribution to the union.
# --------------------------------------------------------------------------

def test_snowball_is_prevented():
    # A (core={creative, writing}, highest n): merges with B, which shares
    # exactly 1 of A's 2 core tokens ("writing") -> ratio 1/2 = 0.5, merges.
    # B also contributes NEW tokens {meditation, retreat} to the UNION.
    # C shares those NEW tokens with B's tail, but shares NOTHING with A's
    # own core -- it must stay separate. (Sanity, worked out by hand: judged
    # against the UNION {creative, writing, meditation, retreat} instead of
    # A's core, C's overlap would be {meditation, retreat} = 2 of its own 3
    # tokens = ratio 0.67 >= 0.5 -- i.e. the union WOULD have snowballed C
    # in. Judged against the fixed core, overlap is 0 -- C stays out.)
    a = "creative writing"
    b = "writing meditation retreat"
    c = "meditation retreat planning"
    entries = _entries((a, 3), (b, 2), (c, 1))
    clusters = _cluster(entries)
    assert len(clusters) == 2
    by_label = {cl["label"]: cl for cl in clusters}
    assert a in by_label
    ab = by_label[a]
    assert ab["n"] == 5                       # A + B merged
    assert ab["toks"] >= {"meditation", "retreat"}  # union carries B's tokens...
    # ...but C was judged against A's CORE (fixed at A's own tokens), not the
    # union, so it never saw meditation/retreat as shared-with-core.
    assert c in by_label
    assert by_label[c]["n"] == 1


def test_cluster_core_never_grows_after_first_merge():
    a = "creative writing"
    b = "writing meditation retreat"
    entries = _entries((a, 3), (b, 2))
    clusters = _cluster(entries)
    assert len(clusters) == 1
    cl = clusters[0]
    # core == the FIRST (highest-n) variant's own tokens only, never the union
    assert cl["core"] == {"creative", "writing"}
    assert cl["toks"] >= {"creative", "writing", "meditation", "retreat"}
    assert "meditation" not in cl["core"]


# --------------------------------------------------------------------------
# empty-token edge case (division-by-zero guard)
# --------------------------------------------------------------------------

def test_all_stopword_value_does_not_crash():
    entries = _entries(("the", 2), ("a", 1))
    clusters = _cluster(entries)
    # both values tokenize to nothing but stopwords -> core is the empty set
    # for the first; `or 1` guards the division, and an empty set can never
    # satisfy >=0.5 overlap against another empty set via len(&)==0, so they
    # stay separate rather than crashing.
    assert len(clusters) == 2
