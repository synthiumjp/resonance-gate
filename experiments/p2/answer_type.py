"""What TYPE of thing a question asks for, and whether a sentence has one.

2026-10-02. Recall was the gap on the blind bench: the answer was often in a
sentence that shares no word with the question ("Which food do I dislike?"
-- "I can't stand cilantro"; "What is my beverage of choice?" -- "I
switched to tea"). Similarity could not separate those from leaks (word
pairs: true 0.57-0.96, false 0.55-0.71; "children" ~ "dog" 0.58). An is-a
relation can: WordNet says cilantro is a food, tea a beverage, Leeds a city,
a daughter a child -- and a dog is not a child.

  question_type("Which food do I dislike?") -> ("food", "neg")
  has_type("I can't stand cilantro.", "food") -> True

Brands and titles are mostly not in WordNet; cars and programming languages
use the closed lists the rest of p2 already keeps. When WordNet is not
installed every check returns False, so nothing is grounded by it.
"""
import re

_WN = None


def _wn():
    global _WN
    if _WN is None:
        try:
            from nltk.corpus import wordnet as wn
            wn.synsets("food")
            _WN = wn
        except Exception:
            _WN = False
    return _WN or None


_Q_TYPE = [
    re.compile(r"^(?:which|what)\s+(?:kind of\s+|type of\s+|sort of\s+)?"
               r"(?P<t>[a-z]+)\s+(?:do|did|does|is|are|was|were|have|has|had|"
               r"can|would|should|will)\b"),
    re.compile(r"^what(?:'s| is| are| was)\s+my\s+(?:favou?rite\s+)(?P<t>[a-z]+)"),
    re.compile(r"^what(?:'s| is| are| was)\s+my\s+(?P<t>[a-z]+)\s+of\s+choice"),
    re.compile(r"^(?:do|did|have)\s+i\s+(?:have|own|keep|got)\s+(?:any\s+|a\s+|an\s+)?"
               r"(?P<t>[a-z]+)"),
]
# question nouns that are not types of THING (handled elsewhere or too vague)
_NOT_TYPES = frozenset("""time year day date month week thing things way kind
sort type name one ones much many reason job work""".split())
_NEG_Q = re.compile(r"\b(dislike|hate|can't stand|cannot stand|avoid|"
                    r"don't like|do not like|detest|loathe|allergic)\b")
_POS_Q = re.compile(r"\b(like|love|enjoy|prefer|favou?rite|adore|of choice)\b")
_NEG_S = re.compile(r"\b(hate|dislike|can't stand|cannot stand|can not stand|"
                    r"don't like|do not like|not a fan|avoid|detest|loathe|"
                    r"allergic|can't eat|cannot eat|gross|disgusting)\b", re.I)
_POS_S = re.compile(r"\b(love|like|enjoy|adore|prefer|favou?rite|fan of|"
                    r"switched to|into)\b", re.I)

_EXTRA = {}          # type -> closed list, filled lazily


def _closed(typ):
    if not _EXTRA:
        try:
            from currency import _CAR_BRANDS
            _EXTRA["car"] = set(_CAR_BRANDS)
        except Exception:
            pass
        try:
            from answerability import _LANGUAGES
            _EXTRA["language"] = set(_LANGUAGES)
        except Exception:
            pass
    return _EXTRA.get(typ, set())


def _singular(w):
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ren"):            # children
        return w[:-3]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


_GENERIC_V = frozenset("""do does did is are was were be been have has had
get got own keep i me my myself the a an any some in on at to of for with from about like
love enjoy prefer dislike hate stand avoid choice favourite favorite usually
often ever currently now still really""".split())


def _verb_lemma(w):
    wn = _wn()
    if wn is None:
        return w
    return wn.morphy(w, wn.VERB) or wn.morphy(w) or w


def question_verbs(q, typ):
    """The question's own content words after the type noun ("born",
    "play", "drive"), lemmatised; empty for generic questions."""
    # only the USER's own action: "What city was I BORN in?", "What car do
    # I DRIVE?" -- not the entity in "What language is the billing service
    # in?"
    s = re.sub(r"\s+", " ", (q or "").lower())
    m = re.search(r"\b(?:do|did|does|was|were|am|have|had|can|would|will)\s+i\s+"
                  r"((?:[a-z]+\s*){1,3})", s)
    if not m:
        return set()
    t = {typ, typ + "s", typ + "es", typ + "ren"}
    return {_verb_lemma(w) for w in re.findall(r"[a-z]+", m.group(1))
            if w not in _GENERIC_V and len(w) > 1 and w not in t
            and _singular(w) != typ}


def question_type(q):
    """-> (type noun, polarity "pos"/"neg"/None) or None."""
    s = re.sub(r"\s+", " ", (q or "").strip().lower()).replace("’", "'")
    for rx in _Q_TYPE:
        m = rx.match(s)
        if m:
            t = _singular(m.group("t"))
            if t in _NOT_TYPES or len(t) < 3:
                return None
            pol = "neg" if _NEG_Q.search(s) else "pos" if _POS_Q.search(s) else None
            return t, pol
    return None


def _is_a(word, typ):
    wn = _wn()
    if wn is None:
        return False
    tsyn = set(wn.synsets(typ, pos=wn.NOUN))
    if not tsyn:
        return False
    for syn in wn.synsets(word, pos=wn.NOUN)[:8]:
        if syn in tsyn:
            return True
        for path in syn.hypernym_paths():
            if tsyn & set(path):
                return True
    return False


_STOP = frozenset("""the and for are was were been have has had this that with
from they them their there what when where which while about into over just
really very much more most some any every lot lots also still now then than
because since after before during my your our his her its""".split())


# WordNet files dogs under "domestic animal", not "pet"
_ALIAS = {"pet": "animal", "drink": "beverage", "color": "colour"}


# 2026-10-03 (stale dev set): getting a thing makes it the user's -- "We
# adopted a kitten", "bought a used Corolla", "Picked up a rescue greyhound"
_POSSESS = re.compile(r"\b(my|our|i have|i've|i've got|i own|we have|we've|"
                      r"i got|we got)\b|(?:\b(?:i|we)\s+(?:just\s+|finally\s+)?|^\W*)"
                      r"(?:adopted|bought|picked up|rescued|purchased|leased|"
                      r"inherited|took in)\b", re.I)


def has_type(sentence, typ, pol=None, verbs=(), possess=False):
    """Does the sentence contain a thing of this type (and, for like/dislike
    questions, the matching polarity, and the question's own verbs)?
    "What city was I born in?" is not answered by "I went to Lyon"."""
    if not sentence or not typ:
        return False
    typ = _ALIAS.get(typ, typ)
    if verbs:
        sv = {_verb_lemma(w.lower()) for w in re.findall(r"[A-Za-z]+", sentence)}
        if not set(verbs) & sv:
            return False
    if pol == "neg" and not _NEG_S.search(sentence):
        return False
    if pol == "pos" and _NEG_S.search(sentence):
        return False
    closed = _closed(typ)
    for m in re.finditer(r"[A-Za-z][A-Za-z'-]+", sentence):
        w = m.group(0).lower().strip("'")
        hit = w in closed            # closed lists may hold short words ("Go")
        if not hit and (len(w) < 3 or w in _STOP):
            continue
        hit = hit or w == typ or _singular(w) == typ or (
            _is_a(w, typ) or _is_a(_singular(w), typ))
        if not hit:
            continue
        # "Do I have any children?" is not answered by "...recipes for the
        # kids": the thing must be the user's
        if possess and not _POSSESS.search(sentence[max(0, m.start() - 40):m.start()]):
            continue
        return True
    return False


def is_presence(q):
    return bool(re.match(r"^\s*(?:do|did|have)\s+i\s+(?:have|own|keep|got)\b",
                         (q or "").lower()))


# types WordNet (or a closed list) covers well enough that a record NOT of
# the type can be said not to answer: "What sport do I play?" is not
# answered by "plays the cello"
CHECKABLE = frozenset("""food beverage drink sport instrument animal pet city
country language car fruit vegetable dish meal herb spice flower tree bird
fish child colour color music genre""".split())


# ---- semantic grounding (2026-10-03) ---------------------------------------
# The dev paraphrase set (bench/false_memory/cases_dev_paraphrase.jsonl) found
# 30 of 64 questions refused while the answering fact WAS stored: "Do I have
# any siblings?" / "my sister Priya", "What health conditions do I have?" /
# "type 2 diabetes", "Which country did I visit?" / "Peru". A WordNet
# relation between a question word and a fact word -- same meaning, or the
# fact's word is a kind (or an instance) of the question's -- grounds the
# question, with the same guard as answer types: the user's own action verb
# in the question ("born", "attend") must be in the fact too.
_LIGHT = frozenset("""do does did done doing have has had having get got go
goes went gone going make made take took be is am are was were been being
thing things stuff kind sort type way time times lot lots one ones bit
something anything everything nothing what which who whom whose where when
why how my mine me myself i you your our we us the a an any some much many
more most less few""".split())


def _syn(word, pos=None):
    wn = _wn()
    if wn is None:
        return []
    try:
        return wn.synsets(word, pos=pos)[:6]
    except Exception:
        return []


def related(q, s):
    """Is fact word s the same as, a kind of, or an instance of question
    word q (or derivationally the same: study / student)?"""
    if q == s or _singular(q) == _singular(s):
        return True
    q = _ALIAS.get(_singular(q), q)
    qs = set(_syn(q)) | set(_syn(_singular(q)))
    if not qs:
        return False
    qn = _singular(q)
    for syn in _syn(s) + _syn(_singular(s)):
        if syn in qs:
            return True
        for path in syn.hypernym_paths():
            if qs & set(path):
                return True
            # WordNet files a sister under "female_sibling", apart from
            # "sibling": a broader term NAMED with the question word counts
            if any(qn in l.name().lower().split("_") for x in path[:-1]
                   for l in x.lemmas()):
                return True
        for inst in syn.instance_hypernyms():
            for path in inst.hypernym_paths():
                if qs & set(path):
                    return True
    # derivation: "studying" / "student", "married" / "marriage"
    qlem = {l.name().lower() for x in qs for l in x.lemmas()}
    for syn in _syn(s):
        for l in syn.lemmas():
            for d in l.derivationally_related_forms():
                if d.name().lower() in qlem:
                    return True
    return False


def _main_verb(query):
    """The user's own action: the first word after "do/did/was ... I", if it
    is a verb that is not a light one ("born", "attend", "purchase")."""
    m = re.search(r"\b(?:do|did|does|was|were|am|have|had|can|would|will)\s+i\s+"
                  r"([a-z]+)", (query or "").lower())
    if not m:
        return None
    w = m.group(1)
    if w in _LIGHT or w in _GENERIC_V:
        return None
    wn = _wn()
    if wn is None or not wn.synsets(w, pos=wn.VERB):
        return None
    return w


def _verb_related(v, w):
    wn = _wn()
    if _verb_lemma(v) == _verb_lemma(w):
        return True
    a = set(wn.synsets(v, pos=wn.VERB)[:3])
    b = set(wn.synsets(w, pos=wn.VERB)[:3])
    return bool(a & b)


def semantic_grounded(query, text):
    if not query or not text or _wn() is None:
        return False
    swords = [w for w in re.findall(r"[a-z]+", text.lower())
              if w not in _LIGHT and w not in _STOP and len(w) > 2]
    if not swords:
        return False
    verb = _main_verb(query)
    if verb:
        if not any(_verb_related(verb, w) for w in swords):
            return False
    qwords = [w for w in re.findall(r"[a-z]+", query.lower())
              if w not in _LIGHT and w not in _GENERIC_V and len(w) > 2
              and w != verb]
    nouns = [w for w in qwords if _wn().synsets(w, pos=_wn().NOUN)
             or _wn().synsets(_singular(w), pos=_wn().NOUN)]
    if not nouns:
        # "What did I purchase recently?" -- the verb is the whole question
        return bool(verb)
    return any(related(q, s) for q in nouns for s in swords)
