"""Which value of a changing attribute is the CURRENT one.

The defect this fixes, seen by reading user 10's store rather than scoring it:
twenty-five job records sit flat with equal standing, so "what do you do?" has
eighteen answers. The striking part is that the store is RIGHT -- in
conversation order it holds a coherent career:

    s1   senior data scientist (apple)
    s3   lead data analyst (google)
    s11  part-time role
    s29  freelance career
    s39  founder and ceo
    s56  chief visionary officer (innovative ai corp)

Nothing is missing and nothing is wrong. The information needed to answer is
present and unreachable, because a memory that never supersedes anything is a
log, not a memory. For a product whose claim is LIVING memory of the user's
world, that is the defect, not the extraction.

WHAT IS AND IS NOT SINGLE-VALUED. Superseding the wrong attribute destroys
real knowledge: a person has one current employer but many hobbies, and
"latest wins" applied to `hobby` would throw away everything but the most
recent. So the set is explicit, small, and only contains attributes where a
person can hold exactly one value at a time. Everything else accumulates,
which is the safe default -- an over-eager supersession loses data, a missed
one only leaves clutter.

HISTORY IS KEPT, NEVER DELETED. Superseded values stay, marked, with the
position that replaced them. "Where did I work before Google?" is a question
a memory product must answer, and it is the same data.
"""
import re

# A person holds exactly one of these at a time. Deliberately conservative:
# adding an attribute here silently discards competing values, so the bar is
# "could a reasonable person hold two of these at once?" -- if yes, it stays out.
SINGLE_VALUED = {
    "occupation", "job_title", "employer", "workplace", "company",
    "location", "residence", "city", "country",
    "income", "monthly_income", "salary", "savings",
    "age", "birth_date", "gender", "name",
    "marital_status", "relationship_status",
    "lifestyle", "employment_status",
}

# Subjects that are not people and must not carry personal attributes.
# "Ai works as empathetic interaction", "Friends works as provide diverse
# perspectives", "Team works as instrumental in overcoming challenges" are all
# in the shipped store; they are extraction noise wearing a person's schema.
NON_PERSON = {"ai", "team", "friends", "colleagues", "family", "people",
              "everyone", "others", "society", "work", "company", "group",
              "community", "world", "technology"}


def _norm(v):
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def is_non_person_subject(subject):
    return _norm(subject) in NON_PERSON


def resolve(facts):
    """Order-aware supersession over a list of stored facts.

    facts: dicts with at least `attr` and `value`, in the order they were
    learned; an optional `session` is used for reporting when present.

    Returns the same dicts, each with three keys added:
        current        True unless a later fact spoke to the same
                       subject+attribute
        superseded_by  index of the fact that CHANGED this value, else None
        restated_by    index of the fact that REPEATED this value, else None

    The two are distinguished deliberately. Restating a value is corroboration
    and changing it is supersession -- they mean opposite things about
    confidence, and collapsing them would make a fact look revised every time
    the user simply mentioned it again. Either way only the newest record
    surfaces as current, or "what do you do?" answers three times.

    Nothing is dropped. Multi-valued attributes are all current.
    """
    from propositions import split_subject

    out = []
    latest = {}
    for i, f in enumerate(facts):
        subj, attr = split_subject(f.get("attr", ""))
        key = (_norm(subj), attr)
        g = dict(f)
        g["current"] = True
        g["superseded_by"] = None
        g["restated_by"] = None
        out.append(g)
        if attr not in SINGLE_VALUED:
            continue
        prev = latest.get(key)
        if prev is not None:
            out[prev]["current"] = False
            if _norm(out[prev]["value"]) == _norm(f.get("value")):
                out[prev]["restated_by"] = i
            else:
                out[prev]["superseded_by"] = i
        latest[key] = i
    return out


def current(facts):
    """Just the facts that still hold."""
    return [f for f in resolve(facts) if f["current"]]


def history(facts, attr, subject=None):
    """Every value an attribute has held for ONE subject, oldest first -- the
    answer to "where did I work before?", which is the same data read the
    other way.

    subject=None means the profile owner, i.e. facts stored without a subject
    prefix. Scoping is not optional: without it a mentor's job and a
    colleague's job land in the owner's career history, which is how the first
    version of this read -- Sophia's "mentor" appearing in Michelle's job
    timeline."""
    from propositions import split_subject
    want = _norm(subject) if subject else None
    out = []
    for f in resolve(facts):
        subj, a = split_subject(f.get("attr", ""))
        if a != attr or _norm(subj) != (want or ""):
            continue
        out.append((f.get("value"), f.get("session"), f["current"]))
    return out


def subjects(facts):
    """Every subject the store holds facts about, with a flag for the ones
    that are not people. Reporting only -- resolve() never drops anything."""
    from propositions import split_subject
    seen = {}
    for f in facts:
        subj, _ = split_subject(f.get("attr", ""))
        name = subj or ""
        seen.setdefault(name, [0, is_non_person_subject(name)])
        seen[name][0] += 1
    return seen


# --- write-time supersession (W1) -----------------------------------------
#
# resolve() above answers the question at READ time, over a list of facts. That
# is the wrong place. Every system that scores well on HaluMem's UPDATING axis
# -- MOSAIC's write-time conflict detection, Zep's bitemporal valid_at/
# invalid_at edges, Eywa's "at most one active state fact per key" -- decides
# at INGESTION whether a new fact replaces an old one. The systems that leave
# it to the retriever score 5-25% on updating; ours scores 2.9%, worst on the
# board (e211).
#
# So the same rule runs once, when the store is built, and the answer is
# recorded on the node. Read-time then costs nothing and every consumer --
# retrieval, the artifact, the QA context -- sees the same verdict instead of
# each re-deriving it (or, today, not deriving it at all).

def _session_ord(conv_id):
    """Sort key for a receipt's conversation id. HaluMem ingestion writes
    's12'; other paths write real conversation uuids, which carry no order --
    those fall back to date, handled by the caller."""
    cid = str(conv_id)
    if cid.startswith("s") and cid[1:].isdigit():
        return int(cid[1:])
    return None


def _node_position(nd):
    """(session_index, date) for the LATEST mention of a node -- the point at
    which the store last saw this value asserted."""
    best_s, best_d = None, ""
    for cid, date in (nd.get("convs") or {}).items():
        si = _session_ord(cid)
        if si is not None and (best_s is None or si > best_s):
            best_s = si
        if str(date) > best_d:
            best_d = str(date)
    return (best_s if best_s is not None else -1, best_d)


def mark_current(nodes):
    """Mark write-time supersession on wire node dicts, in place.

    nodes: an iterable of node dicts as built by WireGraph._mk_node -- each has
    `attr` (which may carry a 'subject:' prefix), `value`, and `convs`.

    Adds to every node:
        current        False if a LATER node gave the same subject+attribute a
                       different value
        superseded_by  the id of the node that replaced it, else None

    Non-destructive by design: nothing is dropped and history stays queryable.
    Only attributes in SINGLE_VALUED participate -- see the note there on why
    that set is deliberately small.

    Returns the number of nodes marked superseded.
    """
    from propositions import split_subject

    groups = {}
    for nd in nodes:
        nd.setdefault("current", True)
        nd.setdefault("superseded_by", None)
        subj, attr = split_subject(nd.get("attr", ""))
        if attr not in SINGLE_VALUED:
            continue
        groups.setdefault((_norm(subj), attr), []).append(nd)

    n = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=_node_position)
        winner = members[-1]
        for nd in members[:-1]:
            # A repeat of the same value is corroboration, not revision; it is
            # already one node here (the cluster merged it), so any DIFFERENT
            # value reaching this point is a genuine change.
            if _norm(nd.get("value")) == _norm(winner.get("value")):
                continue
            nd["current"] = False
            nd["superseded_by"] = winner.get("id")
            n += 1
    return n
