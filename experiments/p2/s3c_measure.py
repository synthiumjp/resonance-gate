"""Measure S3c relation typing against gold, offline and with a null.

Entry 195 named the defect: the gap probe files a recovered person under
whichever slot it happened to ASK about, so gold's "Michelle Hernandez's
Friend AndersonElizabeth" was stored as `colleagues`. The person is right and
the relation is invented, and the coverage proxy cannot see the difference
because it scores the person token.

This scores the fix on the only thing that can settle it -- gold's own
relation labels for user 10's Relationship Memory points:

    recovered   relation_for() read a relation from the source turn
    correct     ... and it matches gold's label
    wrong       ... and it does not
    unstated    no relation word near the name; we now reject instead of
                inventing one

THE NULL. "Right most of the time" is not the claim -- gold's relationships
for this user are 61% colleague, so a constant `colleagues` guess scores well
by doing nothing. The baseline reported here is exactly that: the OLD
behaviour, which files every person under the probed slot. The fix has to beat
what it replaced, not beat chance. Entries 151-153 are the reason this is not
optional.

No model calls: relation_for is deterministic, so this runs while the GPU is
busy with something else.
"""
import json
import os
import re
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from schema_probe import relation_for  # noqa: E402

DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")

# gold's own relation words -> our schema slots
GOLD_SLOT = {
    "friend": "friends", "colleague": "colleagues", "mentor": "colleagues",
    "wife": "partner", "husband": "partner", "partner": "partner",
    "son": "children", "daughter": "children",
    "mother": "family", "father": "family", "sister": "family",
    "brother": "family",
}
# "<Owner>'s <Relation> <PersonName>, ..." is how HaluMem writes a typed
# relationship point. Anything else (the "relationship with X" restatements)
# carries no relation label and is skipped -- it cannot score the fix.
#
# The relation word is matched case-insensitively; the NAME is not, and the
# scoping matters. A plain re.I on the whole pattern also lowercases [A-Z],
# so "'s friend invited her to dinner" parsed `invited` as the person and the
# fix was scored against a verb. Caught in the miss list, which is the only
# reason to print one.
GOLD_RX = re.compile(
    r"'s\s+(?i:(" + "|".join(GOLD_SLOT) + r"))\s+([A-Z][A-Za-z]+)\b")


def gold_pairs(user):
    """[(relation_slot, person, session_index)] from typed gold points."""
    out = []
    for si, s in enumerate(user["sessions"]):
        for mp in s.get("memory_points", []):
            if mp.get("memory_type") != "Relationship Memory":
                continue
            m = GOLD_RX.search(mp.get("memory_content", ""))
            if m:
                out.append((GOLD_SLOT[m.group(1).lower()], m.group(2), si))
    return out


def session_text(user, si, window=2):
    """The turns a probe would have seen for this session, plus a small
    window either side -- a relationship is often introduced a session before
    the gold point that summarises it."""
    lo, hi = max(0, si - window), min(len(user["sessions"]), si + window + 1)
    parts = []
    for s in user["sessions"][lo:hi]:
        for t in s.get("dialogue", []) or []:
            parts.append(str(t.get("content", "")))
    return "\n".join(parts)


def main(user_idx=10):
    """user_idx: an index, or -1 for every user pooled.

    Pooling matters: a single HaluMem user carries only a handful of TYPED
    relationship points (user 10 has 5), and 4/5 against a 3/5 null is one
    item of difference. Any conclusion drawn at that n would be noise, so the
    default reporting unit is all 20 users together."""
    users = [json.loads(l) for l in open(DATA)]
    if user_idx < 0:
        pairs, texts = [], {}
        for ui, u in enumerate(users):
            for rel, person, si in gold_pairs(u):
                pairs.append((rel, person, (ui, si)))
                texts[(ui, si)] = session_text(u, si)
        return score(pairs, lambda key: texts[key], "all 20 users")
    user = users[user_idx]
    pairs = [(r, p, si) for r, p, si in gold_pairs(user)]
    if not pairs:
        print("no typed gold relationship points for this user")
        return
    return score(pairs, lambda si: session_text(user, si), f"user {user_idx}")


def score(pairs, text_for, label):

    dist = Counter(r for r, _, _ in pairs)
    majority = dist.most_common(1)[0]
    print(f"{label}: {len(pairs)} typed gold relationships")
    print(f"  gold distribution: {dict(dist)}")
    print(f"  majority class:    {majority[0]} "
          f"({majority[1]}/{len(pairs)} = {majority[1]/len(pairs):.1%})\n")

    got = Counter()
    misses = []
    for rel, person, si in pairs:
        text = text_for(si)
        pred = relation_for(text, person)
        if pred is None:
            got["unstated"] += 1
            misses.append(("unstated", rel, person))
        elif pred == rel:
            got["correct"] += 1
        else:
            got["wrong"] += 1
            misses.append((f"wrong->{pred}", rel, person))

    n = len(pairs)
    recovered = got["correct"] + got["wrong"]
    print("S3c relation typing (reads the relation from the source turn)")
    print(f"  recovered  {recovered:3d}/{n}  ({recovered/n:.1%})")
    print(f"  correct    {got['correct']:3d}/{n}  ({got['correct']/n:.1%} of all, "
          f"{got['correct']/max(1,recovered):.1%} of recovered)")
    print(f"  wrong      {got['wrong']:3d}/{n}  ({got['wrong']/n:.1%})")
    print(f"  unstated   {got['unstated']:3d}/{n}  ({got['unstated']/n:.1%}) "
          "-- now rejected rather than guessed\n")

    # THE NULL: the old behaviour. The probe asked about one slot at a time,
    # so every person it found was filed under that slot. Score each probed
    # slot as if it had been asked, which is the best case for the old code.
    print("NULL -- old behaviour (file every person under the probed slot)")
    for probed in ("colleagues", "friends", "family", "partner", "children"):
        hit = sum(1 for r, _, _ in pairs if r == probed)
        print(f"  probed as {probed:11s} -> {hit:3d}/{n} correct ({hit/n:5.1%})")
    best = max(dist.values())
    print(f"\n  best single-slot null: {best}/{n} = {best/n:.1%}")
    print(f"  S3c:                   {got['correct']}/{n} = {got['correct']/n:.1%}"
          f"   ({got['correct']-best:+d} vs the null)")

    if misses:
        print("\n  first misses:")
        for kind, rel, person in misses[:10]:
            print(f"    {kind:16s} gold={rel:11s} {person}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else -1)
