"""p2 numeric TRACKABILITY gate: the real-data noise filter for the numeric path.

Entry 55, the first real-transcript test, exposed the numeric belief path's
failure mode that LongMemEval's pre-segmented one-fact gold spans had hidden: on
raw chat it treats EVERY number as a candidate fact-value, so it asserted 22
"facts" that were mostly incidental numbers -- a year parsed as a count, an ID
digit-string from a pasted resume, enumeration counts ("10 ideas", "1 product").

The gate encodes what makes a numeric mention a TRACKABLE personal fact rather
than incidental arithmetic. It mirrors the functional-attribute insight (a fact
is trackable only if it is the singular value of a persistent attribute), applied
to quantities. It is a NEGATIVE filter -- it only removes clear non-facts, so it
cannot invent a fact; the risk it must not take is rejecting a REAL count, so the
rejections are deliberately narrow and are measured against LongMemEval to prove
they do not cost recall.

REJECTS (count scale only; time/money magnitudes are kept -- they were not noisy):
  - YEAR values: an integer 1900-2099 read as a count is a date, not a quantity.
  - PROPER-NOUN counted noun: the "counted thing" appears only Capitalised in the
    text (a name/place/ID label -- "6265 Spence"), not a common noun.
  - ENUMERATION nouns: ideas/apps/ways/tips/... -- counts of enumerated items
    (usually the ASSISTANT's list), not attributes of the user's life.
  - malformed noun: empty or a bare stopword (extraction produced no real head).

No model call.
"""

import re

# abstract enumeration nouns: a count of these is an enumerated set (often the
# assistant's own output), never a persistent personal quantity. Kept TIGHT and
# measured -- deliberately excludes points/tops/bikes/restaurants/pages/postcards
# and other real LongMemEval counted nouns.
_ENUM_NOUNS = {
    "idea", "ideas", "app", "apps", "way", "ways", "reason", "reasons",
    "tip", "tips", "step", "steps", "example", "examples", "option", "options",
    "sentence", "sentences", "trend", "trends", "product", "products",
    "list", "lists", "word", "words", "result", "results", "question", "questions",
    "thing", "things",
    # NB: 'point(s)', 'top(s)', 'bike(s)', 'page(s)' deliberately EXCLUDED --
    # they are real LongMemEval counted nouns (Hilton points, tops 3->5).
}
_STOP_NOUN = {"", "a", "an", "the", "my", "of", "and", "in", "on", "at", "to",
              "for", "so", "far", "just", "now", "some", "above", "below"}


def _counted_noun(scale):
    """The head noun of a 'count:<noun phrase>' scale tag (last token)."""
    if not scale.startswith("count:"):
        return None
    phrase = scale[len("count:"):].strip()
    toks = phrase.split()
    return toks[-1] if toks else ""


def _is_proper_noun(noun, span):
    """True if `noun` appears in the span ONLY capitalised -- i.e. it is a proper
    name/label, not a common noun. A common counted noun (bikes, points) appears
    lowercase; a name (Spence) appears only Capitalised."""
    if not noun:
        return False
    occ = re.findall(rf"\b{re.escape(noun)}\b", span, re.I)   # every occurrence, any case
    if not occ:
        return False
    has_cap = any(o[:1].isupper() for o in occ)
    has_lower = any(o[:1].islower() for o in occ)
    return has_cap and not has_lower


def trackable_numeric(magnitude, scale, span=""):
    """True if a (magnitude, scale) numeric mention is a trackable personal fact.
    NEGATIVE filter: returns False only for clear non-facts (year/ID/enumeration/
    malformed counts). time_s and money scales are always kept."""
    if not scale.startswith("count:"):
        return True                                   # durations, money: keep
    noun = _counted_noun(scale)
    # a bare stopword head ("above", "below") is not a real counted thing. An
    # EMPTY head is NOT rejected: the scale parser often misses the noun on a
    # real count ("three different ones", "17 new") -- rejecting empty cost 2
    # genuine LongMemEval facts (entry 55 regression check).
    if noun and noun in _STOP_NOUN:
        return False
    # a year read as a count is a date, not a quantity
    if float(magnitude) == int(magnitude) and 1900 <= int(magnitude) <= 2099:
        return False
    # enumeration item count (assistant lists, brainstorming), not a life fact
    if noun.lower() in _ENUM_NOUNS:
        return False
    # proper-noun "counted thing" -> an ID/name label, not a countable attribute
    if _is_proper_noun(noun, span):
        return False
    return True
