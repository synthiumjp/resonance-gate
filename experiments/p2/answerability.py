"""Does a stored fact ANSWER the question, or only share its topic?

2026-10-02. "What is my partner's job?" retrieved "partner Sam works from
home" and came back as an answer. Retrieval scores similarity, and a fact
about the right entity is similar to any question about it, so similarity
alone cannot tell "Sam's job" from "something about Sam". The same failure
appears in JP's "Repetition Without Exclusivity" (child-scale LMs show
repetition priming, never mutual exclusivity): without a mechanism in which
candidate referents COMPETE, the familiar item wins. RINSE (arXiv
2609.37469) names the missing signal for retrieval -- coverage of the
question's components -- and "Two Axes of LLM Abstention" (arXiv 2607.08456)
shows answerability needs its own decision, separate from relevance.

This module is that decision, deterministic and cheap:
  * read from the question WHAT is asked (an attribute: job, colour, name, a
    number, a reason, a place) and ABOUT WHAT (my partner, my dog, Sam);
  * a fact answers only if it mentions the entity AND supplies that kind of
    answer.
When the question has no recognisable asked attribute ("Do I own any
pets?", "What do I eat?") nothing is decided here and retrieval stands.
"""
import re

# --- what kind of answer an attribute needs ---------------------------------

_COLOURS = set("""red orange yellow green blue purple violet pink brown black
white grey gray silver gold beige navy teal maroon cream""".split())
_NUMBER_WORDS = set("""zero one two three four five six seven eight nine ten
eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen
twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million
dozen half few several couple""".split())
_LANGUAGES = set("""go rust python java javascript typescript ruby php kotlin
swift scala haskell elixir erlang perl lua sql c c++ c# english german french
spanish italian portuguese mandarin chinese japanese korean arabic hindi dutch
greek russian""".split())
_REASON = re.compile(r"\b(because|since|due to|so that|as it|as the|in order to"
                     r"|thanks to|which is why)\b")
_PREFERENCE = re.compile(r"\b(favou?rite|prefer\w*|love\w*|like\w*|enjoy\w*|"
                         r"best)\b")
_PLACE = re.compile(r"\b(in|at|from|near|based|located|lives?|moved|"
                    r"headquartered)\b\s+[A-Z]|\b(live|lives|living|based|"
                    r"located)\b")

# attribute words -> answer kind
_KIND = {}
for k, words in {
    "role": "job occupation profession role title work career position",
    "employer": "employer company workplace firm",
    "place": "address city town suburb country location home live based "
             "located",
    "colour": "colour color",
    "name": "name called",
    "number": "salary earn earns income cost price age old long often fast "
              "tall big many much years year",
    "time": "year when date birthday",
    "reason": "why reason",
    "language": "language languages",
    "preference": "favourite favorite",
}.items():
    for w in words.split():
        _KIND.setdefault(w, k)

_ROLE_WORDS = None


def _roles():
    global _ROLE_WORDS
    if _ROLE_WORDS is None:
        try:
            from currency import _ROLES
            _ROLE_WORDS = set(_ROLES)
        except Exception:
            _ROLE_WORDS = set()
    return _ROLE_WORDS


# --- reading the question ---------------------------------------------------

_DET = r"(?:my|our|the|your|his|her|their)"
_PATTERNS = [
    # what is my partner's job / what's Sam's salary / what is Priya's last name
    re.compile(rf"^(?:what|who)(?:'s| is| was| are)\s+(?:{_DET}\s+)?"
               r"(?P<ent>[\w ]+?)'s\s+(?P<att>[\w ]+?)\??$"),
    # how much does Sam earn / how old is my dog / how fast is my scooter
    re.compile(rf"^how\s+(?P<att>\w+)\s+(?:is|are|was|does|do|did)\s+"
               rf"(?:{_DET}\s+)?(?P<ent>[\w ]+?)(?:\s+\w+)?\??$"),
    # what colour is my car / what breed is my dog / what year did I buy my car
    re.compile(rf"^(?:what|which)\s+(?P<att>\w+)\s+(?:is|are|was|were)\s+"
               rf"(?:{_DET}\s+)?(?P<ent>[\w ]+?)\??$"),
    re.compile(rf"^(?:what|which)\s+(?P<att>year|colour|color|breed|brand|"
               rf"model|size|name)\s+(?:did|do|does)\s+i\s+\w+\s+"
               rf"(?:{_DET}\s+)?(?P<ent>[\w ]+?)\??$"),
    # where is acme based / where does lee live
    re.compile(r"^where\s+(?:is|are|does|do)\s+(?:my\s+|the\s+)?"
               r"(?P<ent>(?!i\b)[\w ]+?)\s+(?P<att>based|located|live|work)\??$"),
    # what is my job title / what is my favourite database / my salary
    re.compile(r"^what(?:'s| is| was)\s+my\s+(?P<att>[\w ]+?)\??$"),
]
_TRIM = re.compile(r"\s+(?:at work|now|these days|currently|again)$")


def read_question(q):
    """-> (entity or None, attribute words) or None when nothing is asked
    that this module can check. entity None means the owner."""
    s = re.sub(r"\s+", " ", (q or "").strip().lower())
    s = s.replace("’", "'")
    for i, rx in enumerate(_PATTERNS):
        m = rx.match(s)
        if not m:
            continue
        att = _TRIM.sub("", m.group("att").strip())
        ent = m.groupdict().get("ent")
        ent = _TRIM.sub("", ent.strip()) if ent else None
        if ent:
            # "the billing service in" -> "the billing service"
            ent = re.sub(r"\s+(in|at|on|to|for|from|of|with|by)$", "", ent)
            # "i born in", "i buy" -> the owner
            if re.match(r"^(i|me|myself)\b", ent):
                ent = None
        if ent in ("i", "me", ""):
            ent = None
        if i == 5:                       # "what is my X": X may be "favourite Y"
            words = att.split()
            if words and words[0] in ("favourite", "favorite") and len(words) > 1:
                return (" ".join(words[1:]), "favourite")
            if not any(w in _KIND for w in words):
                return None              # "what is my car like" etc.
        return (ent, att)
    return None


def _kind(att):
    words = att.split()
    for w in reversed(words):            # "job title" -> role, "last name" -> name
        if w in _KIND:
            return _KIND[w]
    return None


def _mentions(text, ent):
    if not ent:
        return True
    words = [w for w in re.findall(r"[a-z]+", ent) if len(w) > 2]
    tl = text.lower()
    return any(re.search(rf"\b{re.escape(w)}s?\b", tl) for w in words) if words else True


def answers(fact, q_read):
    """Does this fact (a recall dict with text/said/attribute/value) supply
    what the question asks?"""
    ent, att = q_read
    text = " ".join(str(fact.get(k) or "") for k in ("text", "said"))
    tl = text.lower()
    if not _mentions(text, ent):
        return False
    kind = _kind(att)
    toks = set(re.findall(r"[a-z+#]+", tl))
    if kind == "role":
        return bool(toks & _roles()) or "works as" in tl
    if kind == "employer":
        return bool(re.search(r"\b(works? (?:at|for)|joined|employ\w*|"
                              r"job at)\b", tl))
    if kind == "place":
        return bool(_PLACE.search(text))
    if kind == "colour":
        return bool(toks & _COLOURS)
    if kind == "name":
        caps = set(re.findall(r"(?<!^)(?<=\s)[A-Z][a-z]+", text))
        return bool(re.search(r"\b(called|named|name is)\b", tl)) or len(caps) > 1
    if kind == "number":
        return bool(re.search(r"\d", tl) or toks & _NUMBER_WORDS)
    if kind == "time":
        return bool(re.search(r"\b(19|20)\d\d\b|\b(january|february|march|april|"
                              r"may|june|july|august|september|october|"
                              r"november|december|last|ago|since)\b", tl))
    if kind == "reason":
        return bool(_REASON.search(tl))
    if kind == "language":
        return bool(toks & _LANGUAGES)
    if kind == "preference":
        return bool(_PREFERENCE.search(tl))
    # no known kind: the attribute word itself must appear
    words = [w for w in re.findall(r"[a-z]+", att) if len(w) > 2]
    return bool(words) and all(re.search(rf"\b{re.escape(w)}", tl) for w in words)
