"""Compose gold-shaped RELATIONSHIP propositions from stored parts.

HaluMem's Relationship Memory gold is written as one compound sentence per
person:

    Michelle Hernandez's Friend AndersonElizabeth, Elizabeth is a close
    friend who challenges my perspectives and encourages me to think
    critically, which strengthens my analytical skills.

Our store already holds everything that sentence needs -- the person (as a
subject-scoped attr, "andersonelizabeth:relationship"), a relation
(recoverable from the source text via schema_probe.relation_for, measured at
98.9% against gold labels), and descriptive facts (propositions.render). It
just emits them as separate records. The official judge credits RECORDS, not
stores, and measured late-missed gold has 50.0% coverage by the UNION of a
session's emissions but only 15.1% by any SINGLE record -- the single-record
column is what predicts being credited. So the lever is assembling the parts
that are already there into one gold-shaped record, not extracting more.

This module does exactly that assembly and nothing else:
  * deterministic, no LLM calls -- prompt-based fixes are 0-for-3 in this
    project; every extraction win came from deterministic post-processing;
  * a relation is only ever READ from the source text, never guessed. A
    relation invented from the slot the extractor happened to file the
    person under was a real, shipped defect (S3c, entry 195) -- this must
    not repeat it for the opposite reason (inventing one to look complete);
  * non-person subjects ("friends", "team", "colleagues" as a bare group
    reference) must not produce a relationship proposition about a specific
    person who does not exist.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from propositions import owner_name, render, split_subject, titlecase_person  # noqa: E402
from run_profile_full import _NON_PERSON_SUBJECT, reject_subject_attr  # noqa: E402
from schema_probe import relation_for  # noqa: E402

# schema_probe's relation slots -> the noun gold itself uses ("...'s Friend
# X", "...'s Colleague Y"). Coarse on purpose: relation_for returns one of
# these five slots, never a finer familial role (mother/sister/...), so this
# is the finest label the pipeline actually has evidence for. Inventing a
# sharper one from nothing would be exactly the defect this module exists to
# avoid.
_RELATION_LABEL = {
    "partner": "Partner",
    "children": "Child",
    "family": "Family",
    "friends": "Friend",
    "colleagues": "Colleague",
}

# render()'s own default subject when no owner/subj_prefix is supplied. Used
# below to strip the subject back off a rendered fact and keep only the
# predicate -- see _clause.
_BARE_SUBJECT = "The user"
# Non-greedy up to " is " rather than \S+ for the attribute -- render()'s
# possessive fallback uses the READABLE attr name ("relationship dynamic",
# not "relationship_dynamic"), which is often two words, and a single-token
# match here silently left "'s relationship dynamic is X" unrewritten.
_POSSESSIVE_RX = re.compile(r"^'s\s+(.+?)\s+is\s+(.*)$")


def _clause(fact):
    """One (bare-attribute) fact -> a predicate clause with the subject
    stripped, e.g. {"attr": "occupation", "value": "data scientist"} ->
    "works as data scientist".

    Reuses propositions.render rather than re-implementing its verb-phrase
    table (occupation -> "works as", plan -> "plans to", ...): render()
    defaults to subject "The user" when given no owner and no subject
    prefix, so stripping that fixed, known prefix recovers exactly the
    predicate render() already built, whatever shape it chose. Never edits
    propositions.py, only calls it.
    """
    rendered = render({"attr": fact.get("attr", ""), "value": fact.get("value", "")})
    if not rendered:
        return ""
    rest = (rendered[len(_BARE_SUBJECT):].lstrip()
            if rendered.startswith(_BARE_SUBJECT) else rendered)
    m = _POSSESSIVE_RX.match(rest)
    if m:
        # "'s occupation is data scientist" -> "has occupation data scientist"
        return f"has {m.group(1).replace('_', ' ')} {m.group(2)}"
    return rest


def _display_name(subject_key, session_text=None):
    """The related person's display name, read from the SOURCE TEXT exactly
    as it spells them -- never invented.

    HaluMem writes these names CamelCase-concatenated ("AndersonElizabeth"),
    identically in its own gold memory points AND in the dialogue that
    introduces them, and our subject key is that same string lowercased at
    extraction time ("andersonelizabeth"). So the faithful way to recover the
    real spelling is not to GUESS where one word ends and the next begins --
    it is to find the substring already sitting in the source text and reuse
    its casing verbatim.

    Falls back to a plain capitalised form (no boundary invented) when no
    source text is available or the key is not found in it -- an honest,
    slightly ugly answer rather than a fabricated split.
    """
    raw = str(subject_key or "").strip()
    if not raw:
        return ""
    if " " in raw or "-" in raw:
        return titlecase_person(raw)
    key = re.sub(r"[^a-z]", "", raw.lower())
    if not key:
        return titlecase_person(raw)
    if session_text:
        m = re.search(re.escape(key), str(session_text), re.I)
        if m:
            return m.group(0)
    return titlecase_person(key)


def compose(facts, owner=None, session_text=None):
    """Store facts -> one gold-shaped relationship proposition per related
    person.

    facts: dicts with at least "attr" and "value". Subject-scoped facts look
        like "andersonelizabeth:occupation"; unprefixed facts are the
        owner's own and are skipped -- this module only ever describes
        someone ELSE.
    owner: the profile owner's display name. Falls back to propositions'
        own owner_name() detection, then "The user".
    session_text: the dialogue text these facts came from, used ONLY to type
        the relation via schema_probe.relation_for and to recover a
        person's real-cased name (see _display_name). Optional -- with no
        text, no relation is invented and no name is guessed; the person
        still gets a proposition, just without a relation word.

    Deterministic, no LLM calls anywhere.
    """
    raw_owner = owner or owner_name(list(facts or []))
    owner_disp = titlecase_person(raw_owner) if raw_owner else "The user"
    # Self-reference guard: the extractor sometimes files the OWNER's own
    # facts under a subject key that is just her own first name
    # ("michelle:current_employer" alongside plain "current_employer"),
    # which would otherwise render as "Michelle Hernandez's Michelle" --
    # the same self-reference failure schema_probe.reject() guards for the
    # gap probe (S3b), here for composition instead. Only checked against a
    # REAL resolved owner name, never the "The user" fallback, which would
    # wrongly match any subject key sharing a common word.
    owner_tokens = ({t for t in re.findall(r"[a-z]+", raw_owner.lower()) if len(t) > 2}
                    if raw_owner else set())

    groups, order = {}, []
    for f in facts or []:
        subj, attr = split_subject(f.get("attr", ""))
        if not subj:
            continue                              # the owner's own fact
        key = subj.strip().lower()
        if not key or key in _NON_PERSON_SUBJECT:
            continue                              # a group, not a person
        key_tokens = set(re.findall(r"[a-z]+", key))
        if owner_tokens and key_tokens and key_tokens <= owner_tokens:
            continue                              # the owner, mislabeled as a subject
        if reject_subject_attr(subj, attr):
            continue                              # non-person subject + personal attr
        value = str(f.get("value", "")).strip()
        if not value:
            continue
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append({"attr": attr, "value": value})

    out = []
    for key in order:
        display = _display_name(key, session_text)
        if not display:
            continue
        rel = relation_for(session_text, display)
        rel_label = _RELATION_LABEL.get(rel)      # None if unreadable -- never guessed

        clauses, seen = [], set()
        for pf in groups[key]:
            c = _clause(pf)
            if c and c.lower() not in seen:
                seen.add(c.lower())
                clauses.append(c)

        head = (f"{owner_disp}'s {rel_label} {display}" if rel_label
                else f"{owner_disp}'s {display}")
        out.append(f"{head}, who {' and '.join(clauses)}" if clauses else head)
    return out


# compose_integrity_ab.py's documented usage is `compose_relationship:compose`
# -- keep both names live so either spelling finds the same function.
compose_relationship = compose


if __name__ == "__main__":
    # Measurement: does composing beat the union-vs-single-record gap the
    # module docstring cites? For user 10's 51 Relationship Memory gold
    # points, what fraction is covered at >=0.5 (swept 0.4/0.5/0.6)
    # content-token overlap by a SINGLE composed proposition, vs a single
    # existing atomic record -- WITH a null (composed propositions shuffled
    # across subjects), because a containment number with no null is not
    # trustworthy in this codebase (three past findings were retracted for
    # exactly that).
    #
    # No GPU, no model calls: the store is built entirely from an existing,
    # complete extraction cache (every turn is a cache hit), and everything
    # below is pure token arithmetic.
    #
    # Run with:
    #   cd ~/rg_private/halumem/official/HaluMem/eval
    #   RG_EXTRACT_V5=1 RG_INGEST_ALL_TURNS=1 \
    #     ~/rg_private/halumem/official/.venv/bin/python \
    #     /home/jp/rg/experiments/p2/compose_relationship.py
    import json
    import random
    from collections import defaultdict

    EVAL_DIR = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
    DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
    CACHE = os.path.expanduser("~/rg_private/halumem/dev/cache_u10_v5_14b.jsonl")
    for _p in (EVAL_DIR, _HERE):
        if _p not in sys.path:
            sys.path.insert(0, _p)

    import halumem_run as H  # noqa: E402

    def _tokens(s):
        return {t for t in re.findall(r"[a-z0-9]+", str(s).lower()) if len(t) > 1}

    def _session_text(user, si, window=2):
        """Dialogue for session si plus a small window either side -- a
        relationship is often introduced a session before the gold point
        that summarises it (same window s3c_measure.py uses)."""
        lo, hi = max(0, si - window), min(len(user["sessions"]), si + window + 1)
        parts = []
        for s in user["sessions"][lo:hi]:
            for t in s.get("dialogue", []) or []:
                parts.append(str(t.get("content", "")))
        return "\n".join(parts)

    def _covered(gold_tokens, records, threshold):
        return any(len(gold_tokens & _tokens(r)) / len(gold_tokens) >= threshold
                   for r in records)

    users = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    user = users[10]

    if not os.path.exists(CACHE):
        print(f"FAIL: cache not found at {CACHE} -- cannot build the store "
              "without model calls.")
        sys.exit(1)

    mem, n_turns = H.ingest_user(user, cache_path=CACHE)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    if not nodes:
        print("FAIL: store built with zero nodes -- check RG_EXTRACT_V5 / "
              "RG_INGEST_ALL_TURNS are set and the cache is complete for "
              "this ingestion config.")
        sys.exit(1)
    owner = owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes],
                       default="The user")

    per_session = defaultdict(list)
    for nd in nodes:
        for cid in (nd.get("convs") or {}):
            if str(cid).startswith("s") and str(cid)[1:].isdigit():
                per_session[int(str(cid)[1:])].append(nd)
                break

    _REL_WORDS = tuple(_RELATION_LABEL.values())
    composed_all = []          # (head, body) pairs, body "" if no clauses
    atomic_all = []            # rendered single atomic records
    n_typed = 0                # composed heads that carry a relation word
    for si in range(len(user["sessions"])):
        session_nodes = per_session.get(si, [])
        facts = [{"attr": nd["attr"], "value": nd["value"]} for nd in session_nodes]
        text = _session_text(user, si)
        for prop in compose(facts, owner=owner, session_text=text):
            head, _, body = prop.partition(", who ")
            composed_all.append((head, body))
            if any(f" {w} " in f" {head} " for w in _REL_WORDS):
                n_typed += 1
        for f in facts:
            r = render(f, owner=owner)
            if r:
                atomic_all.append(r)

    def _join(pair):
        head, body = pair
        return f"{head}, who {body}" if body else head

    composed_recs = [_join(p) for p in composed_all]

    rng = random.Random(0)
    heads = [h for h, _ in composed_all]
    bodies = [b for _, b in composed_all]
    shuffled_bodies = list(bodies)
    rng.shuffle(shuffled_bodies)
    shuffled_recs = [_join((h, b)) for h, b in zip(heads, shuffled_bodies)]

    gold_points = [mp for s in user["sessions"] for mp in s.get("memory_points", [])
                   if mp.get("memory_type") == "Relationship Memory"]

    print(f"user 10: {n_turns} turns ingested, {len(nodes)} nodes "
          f"({len(mem.g.nodes)} asserted + {len(mem.g.provisional)} provisional)")
    print(f"composed propositions: {len(composed_recs)}  "
          f"(relation typed: {n_typed}/{len(composed_recs)})")
    print(f"atomic records: {len(atomic_all)}")
    print(f"{len(gold_points)} Relationship Memory gold points\n")

    print(f"{'thr':>5}  {'composed':>10}  {'shuffled-null':>14}  {'atomic single-record':>22}")
    for threshold in (0.4, 0.5, 0.6):
        n = len(gold_points)
        c_cov = sum(1 for mp in gold_points
                    if _covered(_tokens(mp["memory_content"]), composed_recs, threshold))
        s_cov = sum(1 for mp in gold_points
                    if _covered(_tokens(mp["memory_content"]), shuffled_recs, threshold))
        a_cov = sum(1 for mp in gold_points
                    if _covered(_tokens(mp["memory_content"]), atomic_all, threshold))
        print(f"{threshold:>5.1f}  {c_cov:>4}/{n} {c_cov/n:6.1%}  "
              f"{s_cov:>4}/{n} {s_cov/n:6.1%}    "
              f"{a_cov:>4}/{n} {a_cov/n:6.1%}")
