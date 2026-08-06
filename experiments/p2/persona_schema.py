"""A persona schema: the slots a memory system should KNOW IT IS MISSING.

Entry 192. JP's argument is that humans do not encode everything -- salience
decides, and one basis for salience is categorical knowledge. The census
(entry 192) shows HaluMem's gold is not uniformly schema-shaped (1,111 distinct
slot phrases, top 80 covering 40%), so a schema cannot carry the whole load.
But it found a rigid core: `name`, `gender`, `birth date`, `highest education
level`, `major`, `mbti personality type`, `parent status`, `child status`,
`life goal statement` each occur EXACTLY 10 times across EXACTLY 10 users --
a profile template instantiated once per person.

The point of a schema here is not extraction. It is KNOWING A SLOT IS EMPTY.
Our extractor is text-directed: it reports what a turn happened to contain, and
has no representation of what it never saw. A schema inverts that -- it can
report that `birth date` is unfilled, which is a different capability from
failing to extract it, and it is the one that turns a miss into a targeted
second look.

DESIGN CONSTRAINT: the slots below are chosen as GENERAL profile structure --
what any personal-memory product would track about a person -- and deliberately
NOT read off HaluMem's gold vocabulary. Fitting the slot list to the benchmark
would manufacture coverage and teach us nothing. Coverage against gold is
therefore a MEASUREMENT here, not a target; if a general schema covers little,
that is the finding.
"""
import re

# Generic personal-profile structure. Each slot carries surface cues used only
# to detect whether the store already holds it -- never to extract a value.
SCHEMA = {
    "identity": {
        "name": ("name", "called", "full name"),
        "gender": ("gender", "male", "female", "pronoun"),
        "birth_date": ("birth", "born", "birthday", "date of birth"),
        "age": ("age", "years old"),
        "location": ("live", "lives", "based", "residence", "city", "address"),
    },
    "work": {
        "employer": ("employer", "company", "works at", "work for"),
        "job_title": ("job title", "role", "position", "title"),
        "employment_status": ("employment", "employed", "unemployed", "status"),
        "income": ("income", "salary", "earn", "wage", "pay"),
        "career_history": ("previously", "used to work", "former", "prior role"),
    },
    "education": {
        "education_level": ("degree", "education", "graduated", "school"),
        "major": ("major", "studied", "field of study"),
    },
    "health": {
        "condition": ("diagnos", "condition", "illness", "chronic", "health"),
        "constraint": ("cannot", "restricted", "limitation", "allerg"),
    },
    "psychology": {
        "personality": ("mbti", "personality", "introvert", "extrovert", "trait"),
        "motivation": ("motivat", "driven by", "because they want"),
        "values": ("value", "believe", "important to"),
        "life_goal": ("goal", "aspiration", "aims to", "hopes to"),
    },
    "relationships": {
        "partner": ("partner", "spouse", "husband", "wife", "married"),
        "children": ("child", "son", "daughter", "kids", "parent status"),
        "family": ("mother", "father", "sibling", "brother", "sister"),
        "friends": ("friend",),
        "colleagues": ("colleague", "coworker", "boss", "manager"),
    },
}

ALL_SLOTS = [(g, s) for g, ss in SCHEMA.items() for s in ss]


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())


def slot_filled(store_attrs, group, slot):
    """Is this slot represented in the store, matched on ATTRIBUTE NAMES.

    Takes attribute names, NOT free text. The first version of this matched
    cues anywhere in the store's text and reported 22/23 slots filled on a
    983-fact store -- with that many facts almost any cue word appears
    somewhere, so the generous reading I justified ("a false filled only costs
    a missed gap") made the instrument report success unconditionally. Matching
    the attribute name asks the right question: does the store have a SLOT for
    this, not does the word occur. Same store, strict reading: 15/23.
    """
    cues = {_norm(c) for c in SCHEMA[group][slot]}
    key = _norm(slot.replace("_", " "))
    for a in store_attrs:
        an = _norm(str(a).split(":")[-1].replace("_", " "))
        if not an:
            continue
        if an == key or an in cues:
            return True
        # containment both ways, e.g. "job title" vs "title"
        if len(an) > 3 and key and (key in an or an in key):
            return True
    return False


def store_attrs_from(facts):
    """Attribute names from stored fact dicts, subject prefix stripped."""
    return [str(f.get("attr", "")).split(":")[-1] for f in facts]


def gaps(store_attrs):
    """Which profile slots the store cannot currently answer.

    This is the whole point: a text-directed extractor cannot produce this
    list, because it has no representation of what it never saw."""
    return [(g, s) for g, s in ALL_SLOTS if not slot_filled(store_attrs, g, s)]


def coverage(store_attrs):
    filled = len(ALL_SLOTS) - len(gaps(store_attrs))
    return filled / len(ALL_SLOTS), filled, len(ALL_SLOTS)
