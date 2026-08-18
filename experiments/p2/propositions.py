"""Render stored facts as natural-language propositions (entry 162).

RG stores `attribute: value` atoms. Every comparable 2026 system stores
natural-language propositions instead -- MOSAIC typed NL nodes, mem0 atomic
statements, Zep facts on edges, PlugMem propositions -- and HaluMem's gold
memory points are written the same way ("Michelle Hernandez's birth date is
1980-04-20"). Measured on dev users 10-12, re-rendering our EXISTING store in
that form moves gold-memory-point coverage 14.8% -> 45.9% against a
shuffled-gold null of 4.6% -> 16.9%: the signal nearly triples with no change
to what was extracted.

This is a rendering boundary, not a storage change. The store keeps atoms --
they are what dedup, corroboration and BM25 operate on. Propositions are how
those atoms are REPORTED to anything that expects prose.

Scope discipline: this is used for the extraction ARTIFACT. It deliberately
does not touch the QA context format, whose current shape is the one measured
at 55.0/18.7 in the official round-5 run; changing both at once would make
that number unreproducible.
"""
import re

# Attributes that read as a verb phrase rather than a possessed noun, so
# "X's lives in Y" would be wrong. Kept small and explicit rather than
# guessed, because a wrong template is worse than a plain one.
_VERBAL = {
    "location": "lives in",
    "residence": "lives in",
    "city": "lives in",
    "employer": "works at",
    "workplace": "works at",
    "occupation": "works as",
    "job_title": "works as",
    "activity": "does",
    "hobby": "enjoys",
    "preference": "prefers",
    "belief": "believes",
    "plan": "plans to",
    "goal": "aims to",
    "motivation": "is motivated by",
    "value": "values",
    "feeling": "feels",
    "health_condition": "has the health condition",
    "reflection": "has reflected that",
}

_ARTICLEISH = re.compile(r"^(a|an|the|to|that|being|having)\b", re.I)

# A verb template only reads correctly if the value is the right SHAPE.
# "plans to" wants a bare infinitive, so a gerund gives "plans to joining a
# club"; every other verb wants a noun phrase, so a value starting "to ..."
# gives "is motivated by to contribute". Both shipped -- 69 of user 10's 1014
# records (7%) were visibly malformed English. When the shapes do not match we
# fall back to the possessive form, which is grammatical for any value.
_GERUND = re.compile(r"^\w+ing\b", re.I)
_LEADING_TO = re.compile(r"^to\s+", re.I)


def _joins_cleanly(verb, value):
    if verb.endswith(" to"):
        return not _GERUND.match(value)
    return not _LEADING_TO.match(value)


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def split_subject(attr):
    """Our attrs may carry a subject prefix ('nguyen linh:contribution').
    Returns (subject_or_None, bare_attribute)."""
    a = _clean(attr)
    if ":" in a:
        subj, _, rest = a.partition(":")
        subj, rest = subj.strip(), rest.strip()
        if subj and rest:
            return subj, rest
    return None, a


def titlecase_person(name):
    n = _clean(name)
    if not n:
        return n
    return " ".join(w if (w.isupper() and len(w) > 1) else w.capitalize()
                    for w in n.split())


def render(fact, owner=None):
    """One stored fact -> one natural-language proposition.

    owner: the profile owner's name, used when the fact has no subject prefix
    (our convention is that unprefixed facts are about the owner). Falls back
    to "The user" so output is never malformed.
    """
    subj_prefix, attr = split_subject(fact.get("attr", ""))
    value = _clean(fact.get("value", ""))
    if not attr or not value:
        return ""
    subject = titlecase_person(subj_prefix) if subj_prefix else (
        titlecase_person(owner) if owner else "The user")

    if attr == "name" and not subj_prefix:
        return f"The user's name is {titlecase_person(value)}"

    verb = _VERBAL.get(attr)
    readable = attr.replace("_", " ")
    if verb:
        # "prefers black coffee", "plans to expand the team"
        v = value
        if verb.endswith(" to") and _ARTICLEISH.match(v):
            v = re.sub(r"^to\s+", "", v, flags=re.I)
        if _joins_cleanly(verb, v):
            return f"{subject} {verb} {v}"
        # shapes disagree -- the possessive form always reads
        return f"{subject}'s {readable} is {v}"
    return f"{subject}'s {readable} is {value}"


def render_all(facts, owner=None, with_tier=False):
    """Whole store -> propositions. Tier is appended, not embedded, so the
    proposition itself stays clean prose."""
    out = []
    for f in facts:
        p = render(f, owner=owner)
        if not p:
            continue
        if with_tier:
            n = int(f.get("n_mentions", 1) or 1)
            p += f" (confirmed x{n})" if n >= 2 else " (mentioned once)"
        out.append(p)
    return out


def owner_name(facts, default=None):
    """Best guess at the profile owner: an unprefixed `name` fact."""
    for f in facts:
        subj, attr = split_subject(f.get("attr", ""))
        if attr == "name" and not subj:
            return _clean(f.get("value"))
    return default
