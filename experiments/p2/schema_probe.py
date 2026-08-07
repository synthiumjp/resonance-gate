"""Gap-directed extraction: go looking for what the schema says is missing.

Entry 193. Our extractor is TEXT-DIRECTED -- it walks turns and reports what
each happened to contain. It therefore has no representation of what it never
saw, and a missing birth date is indistinguishable from an absent one.

persona_schema.gaps() inverts that: it names the slots the store cannot answer.
This module acts on them. For each gap it finds the turns most likely to carry
that slot and asks a SLOT-DIRECTED question of just those turns.

Three properties that make this different from "extract harder":

  * It is a SCOPE-directed prompt ("does this state the user's birth date?"),
    not an assertion-calibration one. Entry 191 established that scope rules
    hold in this codebase while calibration rules never have.
  * Cost scales with what is MISSING, not with transcript length. A store with
    no gaps costs nothing; one missing three slots pays for three small sweeps.
  * It can only ADD to slots known to be empty, so it cannot inflate the
    precision problem the way a broader extraction pass would -- the failure
    mode of entry 185, where we extracted more of the wrong thing.

Cheap candidate selection first, LLM second: only turns whose surface cues match
the missing slot are ever sent to a model.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from persona_schema import SCHEMA, gaps  # noqa: E402

SLOT_QUESTION = (
    "Does this message state the user's {slot}?\n\n"
    "Answer with ONLY a JSON array. If it states it, output one object:\n"
    '[{{"attribute": "{attr}", "value": "<the value, short>"}}]\n'
    "If the message does not state the user's {slot}, output exactly: []\n\n"
    "Take the value only if this message actually states it. Do not infer it, "
    "do not guess from context, and do not carry it over from what you assume "
    "the user is like. If unsure, output [].\n\nMESSAGE:\n{text}"
)


def candidate_turns(turns, group, slot, limit=6):
    """Turns whose surface cues suggest they might carry this slot.

    Purely lexical and deliberately cheap -- its only job is to keep the LLM
    pass proportional to the gap rather than to the transcript. Ranked by cue
    count so the most promising turns are asked first."""
    cues = [c.lower() for c in SCHEMA[group][slot]]
    key = slot.replace("_", " ").lower()
    scored = []
    for i, t in enumerate(turns):
        low = str(t).lower()
        n = sum(1 for c in cues if c in low) + (2 if key in low else 0)
        if n:
            scored.append((n, i))
    scored.sort(key=lambda z: (-z[0], z[1]))
    return [i for _, i in scored[:limit]]


# Slots that name ANOTHER person. A value equal to the profile owner is the
# self-reference failure S3b measured (partner = the user's own first name).
_PERSON_SLOTS = {"partner", "children", "family", "friends", "colleagues"}
# Slots that hold exactly one value. A comma list here is the conflation
# failure: "Both parents are deceased, Married, Two children" merges three
# separate gold memory points into one unusable string.
_SINGULAR = {"name", "gender", "birth_date", "age", "job_title", "employer",
             "employment_status", "income", "education_level", "major",
             "personality", "partner"}
# Slots that legitimately hold MANY values. Gold stores one memory point per
# person ("Michelle Hernandez's Colleague BrownKaren, ..."), so a comma list
# here is not an error -- it is several facts in one string, and storing it
# whole is why the colleagues value scored 0.25 against gold in S3b. Split it.
_MULTI = {"children", "family", "friends", "colleagues", "career_history"}


def split_multi(slot, value):
    """One value string -> the separate facts it actually contains."""
    if slot not in _MULTI:
        return [value]
    parts = [p.strip(" .;") for p in re.split(r",| and ", str(value))]
    return [p for p in parts if len(p) > 1] or [value]


# --- S3c: relation typing (entry 195 named this as an open defect) ----------
# The probe asks one slot at a time and files whatever it recovers under the
# slot it ASKED about. So probing `colleagues` and finding Elizabeth stores
# "colleagues: elizabeth" even when the text says "my friend Elizabeth" --
# gold's "Michelle Hernandez's Friend AndersonElizabeth". The person is right
# and the relation is invented, and the coverage metric cannot see the
# difference because it scores the person token.
#
# Read the relation from the TEXT instead of assuming it from the question.
# Deterministic rather than a second model call, per the ledger's 4b rule:
# every extraction win in this codebase came from scope-of-input or
# deterministic post-processing, and prompt-level fixes are 0 for 3.
_RELATION_SLOT = {}
for _slot, _words in {
    "partner": ("wife", "husband", "spouse", "partner", "girlfriend",
                "boyfriend", "fiance", "fiancee", "fiancé", "fiancée"),
    "children": ("son", "daughter", "kid", "kids", "child", "children",
                 "stepson", "stepdaughter"),
    "family": ("mother", "father", "mom", "mum", "dad", "parent", "parents",
               "sister", "brother", "sibling", "aunt", "uncle", "cousin",
               "grandmother", "grandfather", "grandma", "grandpa", "niece",
               "nephew", "mother-in-law", "father-in-law", "sister-in-law",
               "brother-in-law", "stepmother", "stepfather"),
    "friends": ("friend", "friends", "bestie", "buddy", "pal", "mate",
                "housemate", "roommate", "flatmate", "neighbour", "neighbor"),
    "colleagues": ("colleague", "colleagues", "coworker", "coworkers",
                   "co-worker", "co-workers", "boss", "manager", "supervisor",
                   "teammate", "teammates", "workmate", "intern", "mentor",
                   "client", "direct report"),
}.items():
    for _w in _words:
        _RELATION_SLOT[_w] = _slot

_REL_RX = re.compile(r"\b(" + "|".join(
    sorted((re.escape(w) for w in _RELATION_SLOT), key=len, reverse=True)
) + r")\b", re.I)

# How far from the name a relation word still counts as describing it. Wide
# enough for "my colleague Sarah Chen" and "Sarah, a friend from work", narrow
# enough that the next sentence's relation word does not bleed across.
_REL_WINDOW = 60

# Constructions that BIND a relation to a name, as opposed to merely sitting
# near one. These are checked before proximity because proximity gets the
# common HaluMem phrasing exactly backwards:
#
#   "I have several important friends and colleagues: ThomasSusan is my
#    Friend, Susan's support ..."
#
# `colleagues` is two characters before the name and `Friend` is thirteen
# after, so nearest-word picks colleagues -- but "friends and colleagues:" is
# a LIST HEADER that describes no one in particular, while "is my Friend"
# names this person's relation outright. Every one of the 16 errors in the
# first S3c measurement was this one shape, all in the same direction.
_HEDGE = r"(?:close|good|old|dear|former|long-?time|best|new|younger|elder)\s+"
_AFTER = re.compile(
    r"^\W{0,3}(?:is|was|are|were)\s+(?:my|his|her|their|a|an)\s+"
    r"(?:" + _HEDGE + r")?(\w[\w-]*)", re.I)
_APPOS = re.compile(
    r"^\s*,\s*(?:my|his|her|their|a|an)\s+(?:" + _HEDGE + r")?(\w[\w-]*)", re.I)
_BEFORE = re.compile(
    r"(?:my|his|her|their)\s+(?:" + _HEDGE + r")?(\w[\w-]*)\W{0,3}$", re.I)


def _bound_relation(low, ns, ne):
    """A relation grammatically attached to the name at [ns:ne), or None."""
    for rx, seg in ((_AFTER, low[ne:ne + 60]),
                    (_APPOS, low[ne:ne + 60]),
                    (_BEFORE, low[max(0, ns - 40):ns])):
        m = rx.search(seg)
        if m and m.group(1).lower() in _RELATION_SLOT:
            return _RELATION_SLOT[m.group(1).lower()]
    return None


def relation_for(text, value):
    """Which relation the SOURCE TEXT gives this person, or None.

    Two readings, in order: a relation grammatically BOUND to the name ("X is
    my friend", "my colleague X", "X, a friend from work"), then -- only if
    none is found -- the nearest relation word within _REL_WINDOW.

    Returns None rather than a guess when neither finds anything. None is a
    real answer here: it means we found a person and the text did not say who
    they are to the user, which is exactly the case the probe used to paper
    over by reusing the slot it asked about."""
    low = str(text or "").lower()
    # HaluMem writes surnames CamelCased ("AndersonElizabeth") while the
    # transcript spells them out ("Anderson Elizabeth"), so split on the case
    # boundary before matching or the name is never found in its own source.
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value))
    name_tokens = [w for w in re.findall(r"[a-z][a-z'-]{2,}", spaced.lower())
                   if w not in ("the", "and", "her", "his", "their")]
    if not low or not name_tokens:
        return None
    spans = [m.span() for tok in name_tokens
             for m in re.finditer(r"\b" + re.escape(tok), low)]
    if not spans:
        return None
    for ns, ne in spans:
        bound = _bound_relation(low, ns, ne)
        if bound:
            return bound
    best, best_d = None, None
    for m in _REL_RX.finditer(low):
        rs, re_ = m.span()
        for ns, ne in spans:
            d = 0 if (rs < ne and ns < re_) else min(abs(ns - re_), abs(rs - ne))
            if d <= _REL_WINDOW and (best_d is None or d < best_d):
                best_d, best = d, _RELATION_SLOT[m.group(1).lower()]
    return best


def reject(slot, value, owner_tokens):
    """Why this recovered value must not enter the store, or None to accept.

    A slot-directed question PRESUPPOSES the slot has a value and invites the
    model to find one, so "if unsure output []" does not hold -- S3b measured
    50% clean precision without these guards. A wrong value in a previously
    EMPTY slot is worse than the empty slot, because nothing downstream can
    tell it was guessed."""
    v = str(value or "").strip()
    if not v:
        return "empty"
    vt = {w for w in re.findall(r"[a-z0-9]+", v.lower()) if len(w) > 2}
    if slot in _PERSON_SLOTS and owner_tokens and (vt & owner_tokens):
        return "self-reference"
    if slot in _SINGULAR and ("," in v or " and " in v.lower()):
        return "conflated (singular slot, list value)"
    if len(v.split()) > 12:
        return "too long for a slot value"
    return None


def probe_gaps(store_texts, turns, extract_fn, limit_per_slot=6, max_slots=None,
               owner_tokens=None):
    """Fill what the schema says is missing.

    extract_fn(prompt) -> list[{attribute, value}]; injected so this module
    stays testable without a model and so the caller controls which endpoint
    pays for it.

    Returns (found, report) where report records EVERY slot attempted and how
    many turns it cost -- a gap we looked for and did not find is as much a
    result as one we filled, and silently dropping those would make the pass
    look more effective than it is.
    """
    missing = gaps(store_texts)
    if max_slots:
        missing = missing[:max_slots]
    found, report, rejected = [], [], []
    for group, slot in missing:
        cands = candidate_turns(turns, group, slot, limit_per_slot)
        got, retyped = [], 0
        for i in cands:
            prompt = SLOT_QUESTION.format(slot=slot.replace("_", " "),
                                          attr=slot, text=str(turns[i])[:1200])
            try:
                facts = extract_fn(prompt) or []
            except Exception:
                continue
            for f in facts:
                v = re.sub(r"\s+", " ", str(f.get("value", "")).strip())
                if not v or len(v) >= 160:
                    continue
                for piece in split_multi(slot, v):
                    # S3c: file the person under the relation the TEXT states,
                    # not the one we happened to ask about. An unreadable
                    # relation is a rejection, not a fallback to the probed
                    # slot -- that fallback IS the defect, and a wrong relation
                    # in a previously empty slot is unauditable downstream.
                    tgt = slot
                    if slot in _PERSON_SLOTS:
                        rel = relation_for(turns[i], piece)
                        if rel is None:
                            rejected.append({"slot": slot, "value": piece,
                                             "why": "relation not stated"})
                            continue
                        if rel != slot:
                            retyped += 1
                        tgt = rel
                    why = reject(tgt, piece, owner_tokens or set())
                    if why:
                        rejected.append({"slot": tgt, "value": piece,
                                         "why": why})
                        continue
                    got.append({"attribute": tgt, "value": piece,
                                "group": group, "turn": i,
                                "probed_slot": slot,
                                "source": "schema_probe"})
            if got:
                break                      # first hit wins; stop paying
        report.append({"group": group, "slot": slot,
                       "candidates": len(cands), "filled": bool(got),
                       "retyped": retyped})
        found.extend(got)
    # Rejections are returned, not swallowed: a guard that silently drops
    # values would make the pass look cleaner than it is.
    return found, report, rejected
