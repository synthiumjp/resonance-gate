"""p2 functional-attribute extraction: the pattern-infers-the-knowledge path.

The insight (user, this session): you do NOT need a large knowledge base to
detect categorical change. You need to know, for a small set of RELATION
PATTERNS, (a) the TYPE of the value and (b) whether the relation is FUNCTIONAL
(takes one current value). Both are inferable FROM THE PATTERN itself -- "trip
to X" makes X a location, "class on X" makes X a day, and both relations are
functional (one most-recent trip, one class day). Then two different values of
a functional-typed relation are a change BY the uniqueness presupposition
(agent-2 Factor A, the primary reliable factor) -- without ever proving the two
values are taxonomically incompatible, and without enumerating values.

So the "knowledge base" is a ~30-entry PATTERN TABLE (pattern -> type,
functional) plus a TINY containment list for the location veto (Chicago is in
Illinois -> not a relocation). The pattern carries the knowledge; the list is
small and finite.

FUNCTIONALITY comes from two sources, both in the table:
  INHERENT  -- the relation takes one value by its meaning ("where I keep X",
              "my class day", "my employer").
  MARKED    -- a definite/superlative/current adverbial supplies uniqueness
              ("MOST RECENT trip", "CURRENTLY obsessed with", "my CURRENT X").
Non-functional relations (restaurants I've tried, bands I like) are NOT in the
table, so they never fire -- the multi-valued cases stay silent, which is the
precision guard.

Complements cos_extract.py (language-MARKED change via change-of-state verbs).
This module handles STATIVE functional attributes that change without a change
verb. No model call.
"""

import re

_SENT = re.compile(r"(?<=[.!?])\s+")

# pattern table: (attribute-name, compiled pattern with a VALUE group, requires
# a functionality marker in the sentence?). attribute-name is the stable key so
# two mentions of the same functional attribute pair regardless of value.
_MARK = re.compile(r"\b(most recent|current|currently|latest)\b", re.I)

_PATTERNS = [
    # object storage location -- inherently functional (one place a thing is kept)
    ("keep_location", re.compile(
        r"\bkeep(?:ing|s)?\s+(?:my |the |them |it )?(.{0,25}?)\s+"
        r"(?:in|under|on|at|inside)\s+(.+?)(?:[.,;!?]|\s+for\b|$)", re.I), False, "obj_loc"),
    # trip/vacation destination -- functional with a recency marker
    ("trip_dest", re.compile(
        r"\b(?:most recent|latest)\s+(?:family\s+)?"
        r"(?:trip|vacation|holiday|getaway)\s+to\s+(.+?)(?:[.,;!?]|\s+(?:and|with|was)\b|$)", re.I),
     False, "loc"),   # pattern already carries the recency word; no extra gate
    # recurring event day -- inherently functional (one day for THE class)
    ("event_day", re.compile(
        r"\b(class|appointment|session|meeting|lesson)\s+(?:is\s+)?on\s+"
        r"([A-Z][a-z]+day)s?\b", re.I), False, "day"),
    # frequency of a recurring appointment -- functional
    ("see_freq", re.compile(
        r"\bsee\s+(?:my |our )?(.+?)\s+(every\s+\w+(?:\s+weeks?|\s+days?)?)", re.I),
     False, "freq"),
    # current preference -- functional via 'current(ly)'
    ("current_pref", re.compile(
        r"\bcurrently\s+(?:obsessed with|into|using|loving|reading|watching)\s+"
        r"(.+?)(?:[.,;!?]|\s+for\b|$)", re.I), False, "pref"),
    # residence -- functional
    ("residence", re.compile(
        r"\b(?:i(?:'m| am)?\s+(?:currently\s+)?(?:living|based|residing)|i live)\s+"
        r"(?:in|at)\s+(.+?)(?:[.,;!?]|\s+(?:and|with|now)\b|$)", re.I), False, "loc"),
]

# tiny containment list for the location veto: a value naming a larger region
# does not contradict a value naming a place within it (Chicago vs Illinois).
# INFORMATIONAL-keep guard: "keep you updated / posted / in the loop / up to
# date" is not physical object-storage -- it over-matched the keep_location
# pattern on real chat and produced a false "storage location" slot (entry 55).
_INFORMATIONAL = re.compile(
    r"\b(updated|posted|informed|abreast|in the loop|up to date|in touch|"
    r"in mind|track of|record of)\b", re.I)

_BIG_REGIONS = {"illinois", "california", "texas", "new york", "the us", "usa",
                "the united states", "the uk", "england", "the country",
                "the city", "the area", "the region", "the state", "the suburbs",
                "downtown", "abroad", "overseas"}
_VAL_STOP = {"a", "an", "the", "my", "our", "some", "his", "her", "their"}


def _clean(v):
    v = re.sub(r"\s+", " ", str(v)).strip(" .,!?\"'")
    words = v.split()
    while words and words[0].lower() in _VAL_STOP:
        words = words[1:]
    return " ".join(words[:5]).strip()


def contains(a, b):
    """True if one value is a containment region of the other (so they do NOT
    contradict). Tiny list + substring, per the pattern-infers-knowledge design
    -- not a gazetteer."""
    a, b = a.lower().strip(), b.lower().strip()
    if a in b or b in a:
        return True
    return a in _BIG_REGIONS or b in _BIG_REGIONS


def extract_functional(text):
    """(subject, attribute, value, vtype) for functional-typed stative
    attributes. subject is the speaker (these patterns are first-person);
    two different values of one attribute = a categorical change downstream."""
    out, seen = [], set()
    for sent in _SENT.split(text):
        marked = bool(_MARK.search(sent))
        for attr, rx, needs_mark, vtype in _PATTERNS:
            for m in rx.finditer(sent):
                if needs_mark and not marked:
                    continue
                groups = [g for g in m.groups() if g]
                val = _clean(groups[-1])          # the value is the last group
                # object-storage: attribute keyed by the OBJECT so "sneakers"
                # kept in two places pairs; value is the location
                akey = attr
                if attr == "keep_location" and len(m.groups()) >= 2:
                    # informational "keep X updated/posted/in the loop" is not
                    # physical storage -> not a trackable location attribute
                    if _INFORMATIONAL.search(m.group(0)):
                        continue
                    obj = _clean(m.group(1))
                    akey = f"keep:{obj.lower()}"
                    val = _clean(m.group(2))
                if not val or len(val) < 2:
                    continue
                k = (akey, val.lower())
                if k in seen:
                    continue
                seen.add(k)
                out.append(("I", akey, val, vtype))
    return out
