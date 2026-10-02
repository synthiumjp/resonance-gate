"""p2 QUERY CONTRACT: the interface an LLM connects to.

This is the facade over GROW (belief/corroboration) + WIRE (receipted
co-occurrence graph): a Memory object with exactly the read contract the
product promises --

  recall(query)  -> asserted facts (corroborated, receipted)
                  + wired neighbourhood (receipted edge paths)
                  + provisional single-mentions (labeled UNCONFIRMED)
                  | ABSTAIN ("never seen") -- never a guess.

  context_block(query=None) -> a verbatim, receipted text block for injection
    into an LLM prompt. NON-GENERATIVE: every line is a stored fact with its
    receipt count; the block carries the standing instruction that anything
    not in the block is unknown and must not be invented. The LLM stays the
    fallible creative client; the block is the stable substrate speaking.

No model call on the READ path -- load(), recall(), profile() and
context_block() are pure python over the store, which is what "the stable
substrate speaking" above means and what every QA number rests on.

ONE EXCEPTION, corrected in e249: conflicts() calls consolidate.contradicts(),
which lazy-loads a LOCAL NLI classifier (cross-encoder/nli-deberta-v3-xsmall,
CPU) to decide whether two values of a slot can both hold. Nothing remote and
nothing generative -- and it degrades to None, letting the caller fall back to
the lexical path, if transformers is unavailable. But it is a model call, and
this docstring claimed for a long time that there were none anywhere in the
module. If you need a guaranteed model-free surface, use everything except
conflicts().
"""

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from wire import WireGraph

# e261: this said "The facts above are corroborated" while the block rendered
# UNCONFIRMED lines beside them -- the rules described one tier and the block
# showed two. Every line now states its own standing, and the rules say what
# each standing means rather than asserting one for all of them.
# 2026-10-02: rewritten after a new-user install test. The old rules told the
# agent to treat every single-mention fact as UNCONFIRMED and to "ask the user
# to confirm it" -- and since people state facts about themselves once, that
# was nearly every line: an assistant that keeps asking "can you confirm you're
# a nurse?" about something the user just said. A first-hand statement is good
# evidence; what an agent actually needs is the user's words, how recent they
# are, and whether they have since been replaced.
_RULES = ("[MEMORY RULES] Each line is something the user told you: a short "
          "summary, then their exact words in quotes, and when. Lines marked "
          "(no longer true) were replaced by something they said later; "
          "(said in passing) was true when said, not necessarily now; "
          "(their words) is quoted exactly, and a later line can update an "
          "earlier one -- check the dates. "
          "Anything about the user not listed here is UNKNOWN: say you don't "
          "know rather than guessing. Memory is background, not permission: "
          "don't act on it (run commands, change files, contact anyone) "
          "unless the user asks in this conversation.")


def _rv3():
    import retrieve_v3
    return retrieve_v3


class _LazyRV3:
    def __getattr__(self, k):
        return getattr(_rv3(), k)


_RV3 = _LazyRV3()

# Cross-encoder score below which recall_v3 abstains.
#
# e260: with e259's garbage node gone, the two populations separate CLEANLY on
# this store -- answerable questions score >= -7.72, never-mentioned ones
# <= -7.94, no overlap, 18/18. Before the parser fix they overlapped (known-min
# -7.72 vs unseen-max -7.45), because "<owner> did not know which" ranked first
# for nearly every unanswerable question and dragged its scores up. Fixing a
# render defect made the evidence signal separable; that is the finding, not
# the number.
#
# Two margin-based alternatives were tested and are WORSE: top1-minus-median
# and top1-minus-2nd both split 16/18 with overlapping populations.
#
# STILL A PILOT VALUE, and now openly fitted: the midpoint of an 18-point
# sample on one synthetic store. Re-derive on held-out questions before
# quoting it. What transfers is that an absolute floor on the cross-encoder
# score is the right mechanism, not that it is -7.83.
# e277: MEASURED INERT, AND COSTLY. With grounding on (the shipped default),
# sweeping this from -9.5 to -6.0 leaves abstention at exactly 9/9 the whole
# way; disabling it entirely leaves abstention 9/9 AND recovers a true answer
# (pool 24/26 -> 25/26). Grounding accounts for 100% of the abstention
# property on this store; the floor accounts for none of it and suppresses
# one real fact.
#
# e274/e275 described the two as "independent signals, both pulling weight".
# That was true when written -- of the 14-node store -- and stopped being true
# without anyone re-checking. Default is now None (off). The mechanism stays,
# because 5o's argument cuts both ways: grounding is also unvalidated at
# scale, and if it fails on a real store this is the belt to re-fasten.
FLOOR_V3 = None


# e274: WHICH PREDICATE KEYS HOLD ONE VALUE.
#
# `consolidate.SINGLE_VALUED` is a 24-name allowlist written for the LLM
# extractor's slot names. The deterministic parser keys on PREDICATES
# (`live_in`, `favourite_language`), none of which are in it, so "I live in
# Berlin" then "I live in Munich" raised no conflict at all -- two equally
# current facts and an agent left to pick. The server README promises the
# opposite: "surfaces conflicts rather than silently picking".
#
# The first attempt simply widened the candidate set to every attribute with
# two distinct values and let NLI arbitrate. MEASURED, THAT IS WORSE: NLI
# called "like: rust" vs "like: python" a contradiction, and "have: a dog" vs
# "have: a cat". The allowlist was doing real work -- restricting NLI to slots
# where substitution is the NORM. Its fault is coverage, not existence.
#
# So this extends it on a linguistic signal instead. A SUPERLATIVE or
# uniqueness modifier ("favourite", "main", "primary", "current") makes a slot
# single-valued by construction, and a handful of predicates are inherently
# unique. Everything else keeps accumulating, which is correct: a person may
# like many languages and own several pets.
_UNIQUE_MODIFIERS = ("favourite", "favorite", "main", "primary", "current",
                     "best", "preferred", "usual", "only")
_UNIQUE_PREDS = frozenset((
    "live_in", "born_in", "bear_in", "name", "age", "birth_date",
    "marry_to", "married_to", "reside_in"))


def _single_valued(attr):
    a = (attr or "").lower()
    if a in _UNIQUE_PREDS:
        return True
    return any(m in a for m in _UNIQUE_MODIFIERS)


# e272: SUBJECT-POSITION RE-RANK.
#
# Every remaining recall miss on the product harness had the same shape: the
# record containing the question's WORDS beat the record containing its
# ANSWER.
#
#   "What language is the billing service in?"
#      1. Alex works on the billing service        <- matches, answers nothing
#      2. the billing service is written in Go     <- the answer
#
# The distinction is grammatical, not lexical: the answer has the queried
# entity as its SUBJECT, the distractor has it as an object. A cross-encoder
# this small does not reliably see that; a lead-position check does, for free.
#
# APPLIED AFTER THE FLOOR, NEVER BEFORE. The bonus only reorders records that
# already cleared the abstention threshold on their RAW score, so it cannot
# make a never-mentioned topic answerable. That is a structural guarantee
# rather than a measured one -- the alternative (boost, then floor) tested
# identically on 7 unseen questions, which is not enough evidence to rest an
# abstention promise on.
_RERANK_STOP = frozenset("""
what who where when which why how do does did is are was were am be been the
a an my your our i me we us of in on at for to about know any there thing
""".split())
SUBJECT_BONUS = 6.0     # plateau on the dogfood set; below it, monotone
# e273: how far a superseded fact drops. Large enough to lose to any current
# fact that matched at all, small enough that a stale fact still beats nothing
# -- "you told me X, but that was before you told me Y" is a better answer
# than silence.
STALE_PENALTY = 20.0


def _stem(t):
    # e281: was `len(t) > 4`, so a 3-letter noun never lost its plural --
    # "dogs"/"dog", "cars"/"car", "jobs"/"job" shared no stem and the lexical
    # route could not ground exactly the short everyday nouns it exists for.
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def _owner_stems(owner):
    """The owner's name as stems, so grounding can ignore it. e281: every
    rendered fact begins with the owner's name, so any question that names
    the owner shared a "content word" with every record in the store --
    "What is Alex Reyes's blood type?" grounded on "Alex Reyes uses Postgres"
    and came back found=True with receipts. A name is not evidence about a
    topic."""
    import re as _re
    if not owner:
        return set()
    return {_stem(t) for t in _re.findall(r"[a-z]+", str(owner).lower())}


def _guess_owner(nodes, min_share=0.4):
    """The owner's name read off the store itself: the rgx renderer starts
    every owner-subject proposition with the owner's full name, so the most
    common leading two-word prefix of the record texts IS the name when it
    carries at least `min_share` of them. Used only when no caller supplied
    the owner and no `name` fact exists (e281: the dogfood store had neither,
    so the name-based lookup returned None and the fix was inert)."""
    import re as _re
    from collections import Counter
    texts = [nd.get("text") or "" for nd in nodes if nd.get("text")]
    if len(texts) < 3:
        return None
    c = Counter()
    for t in texts:
        w = _re.findall(r"[A-Za-z][a-z]+", t)
        if len(w) >= 2 and w[0][0].isupper() and w[1][0].isupper():
            c[f"{w[0]} {w[1]}"] += 1
    if not c:
        return None
    name, n = c.most_common(1)[0]
    return name if n / len(texts) >= min_share else None


def _entity_names(hits):
    """Capitalised, non-initial tokens in the retrieved records: the names the
    store knows (e281b). Lower-cased, unstemmed."""
    import re as _re
    out = set()
    for h in hits or []:
        for w in _re.findall(r"(?<!^)(?<=\s)[A-Z][a-z]+", h.get("text") or ""):
            out.add(w.lower())
    return out


def _strip_owner(query, owner, extra_names=()):
    """The query without the owner's name tokens (and any `extra_names`, the
    entities the retrieved records mention), for the dense route -- a name
    inflates cosine against every record that carries it, whatever was asked."""
    import re as _re
    names = set(extra_names or ())
    if owner:
        names |= {t for t in _re.findall(r"[a-z]+", str(owner).lower())}
    if not names:
        return query
    kept = [w for w in (query or "").split()
            if _re.sub(r"[^a-z]", "", _re.sub(r"'s\b", "", w.lower()))
            not in names]
    return " ".join(kept) or query


# e275: DENSE GROUNDING THRESHOLD. Lexical grounding alone rejects PARAPHRASE,
# which is what real questions are: "What is my role at work?" shares no
# content word with "is a backend engineer there". The corpus had exactly one
# such case, so lexical-only looked almost free -- a corpus weakness read as
# evidence. With a proper paraphrase set the two populations are:
#
#   answerable, not lexically grounded   0.639 .. 0.748
#   never mentioned                      0.506 .. 0.600
#
# 0.62 sits between them. Openly fitted, on 13 points, one store -- the same
# caveat as every constant in this file, and the reason the LEXICAL route is
# kept as well rather than replaced: two cheap independent signals degrade
# more gracefully than one tuned one.
DENSE_GROUND = 0.62

# 2026-10-02: recall returns facts within this many raw cross-encoder points
# of the best one (pilot value, see recall_v3). Negative disables the cut.
RECALL_MARGIN = 4.0

# ---------------------------------------------------------------------------
# THE GATES (e280). A refusal is an EMPTY RESULT SET, not a model being
# humble: every abstention on the v3 read path is decided by one of these
# named predicates BEFORE any renderer or model sees the query, and the
# returned dict names the gate that fired. `GATE_COUNTS` accumulates per
# process so a harness can print a read-path refusal matrix -- which gate,
# how often -- the way rgx/refusal_cases.py does for the parser. Order is
# the order they are evaluated in recall_v3.
GATES = (
    "empty-store",       # nothing stored at all
    "no-candidates",     # retrieval returned nothing
    "score-floor",       # best raw cross-encoder score under FLOOR_V3 (off by default)
    "grounding",         # no retrieved record shares a content word, and none is dense-close
    "no-renderable",     # candidates existed but none resolved to a stored node
    "attribute",         # the entity is known, but no fact supplies what was asked
    "other-scope",       # only facts from other projects matched
)
GATE_COUNTS = {g: 0 for g in GATES}


# What makes a statement about the user PERSONAL, so it follows them across
# projects (2026-10-02, scoping). Deliberately broad: a missed personal fact
# only stays in its project, while a work fact wrongly marked personal leaks
# into every project -- the complaint scoping exists to fix.
_PERSONAL_KINDS = re.compile(
    r"\b(allerg\w*|intoleran\w*|health|doctor|diagnos\w*|medication|pregnan\w*|"
    r"partner|wife|husband|spouse|girlfriend|boyfriend|son|daughter|kids?|"
    r"children|child|baby|mother|father|mum|mom|dad|parents?|sister|brother|"
    r"family|friend|dog|cat|pets?|birthday|born|grew up|lives?|living|moved|"
    r"home|house|apartment|flat|vegetarian|vegan|diet|eats?|drinks?|married|"
    r"single|divorced|engaged|hobb\w*|likes?|loves?|enjoys?|hates?|dislikes?|"
    r"prefers?|favou?rite|plays? the|speaks?|learning|studies|studying|"
    r"name is|years old|age)\b")


def fact_id(nd):
    """A short, stable id for a stored fact (2026-10-02), so a person or an
    agent can say 'forget a3f9c1' instead of reconstructing attribute and
    value. Derived from the node id, so it survives reloads."""
    import hashlib
    return hashlib.sha1(str(nd.get("id", "")).encode()).hexdigest()[:6]


def _attach_sources(g, sources):
    """2026-10-02: hang each node's VERBATIM source sentence on it, by node
    id, after the graph is built (build_facts returns them through an
    optional out-parameter so its row tuples keep their shape). A node with
    no recorded source -- an LLM-cache fact, an owner seed, a cache written
    before this change -- simply has none, and renders as before."""
    for store in (g.nodes, g.provisional, getattr(g, "hearsay", {}) or {}):
        for nid, nd in store.items():
            if nid in sources:
                nd["source"] = sources[nid]


def _render_fact(f, max_quote=200):
    """One context-block line body: summary, then the evidence in brackets.

        Alex Reyes works at Acme  ["I work at Acme as a backend engineer." · 2026-10-02]
        (no longer true) Alex Reyes is a vegetarian  ["I'm vegetarian." · said 2x · 2026-09-01]

    2026-10-02. The summary is a REWRITE of the user's words (third person,
    owner's name substituted, clause extracted) and every inversion class
    fixed since e240 lived in that rewrite -- a negation lost in rendering, a
    pronoun bound to the wrong antecedent, "neither ... nor" left in the noun
    phrase. The quote is what was actually said, so a reader holding both can
    never be told the opposite. RG_CONTEXT_QUOTES=0 omits the quote."""
    prop = f.get("text") or f"{f['attribute']}: {f['value']}"
    if f.get("current") is False:
        prop = "(no longer true) " + prop
    elif f.get("passing"):
        prop = "(said in passing) " + prop
    ev = []
    said = (f.get("said") or "").strip()
    if said and os.environ.get("RG_CONTEXT_QUOTES") != "0":
        if len(said) > max_quote:
            said = said[:max_quote - 3].rstrip() + "..."
        ev.append(f'"{said}"')
    if (f.get("mentions") or 0) > 1:
        ev.append(f"said {f['mentions']}x")
    recs = f.get("receipts") or []
    if recs and recs[0].get("date"):
        ev.append(str(recs[0]["date"]))
    return f"{prop}  [{' · '.join(ev)}]" if ev else prop


PASSING_DAYS = 3


def _passing(nd):
    try:
        import currency
        return currency.passing(nd.get("text"), nd.get("source"),
                                nd.get("attr"), nd.get("value"))
    except Exception:
        return False


def _stale_passing(f, today=None):
    """Said in passing, and more than PASSING_DAYS ago (or undated)."""
    if not f.get("passing"):
        return False
    import datetime as _dt
    dates = [r.get("date") for r in (f.get("receipts") or []) if r.get("date")]
    try:
        last = max(_dt.date.fromisoformat(str(d)[:10]) for d in dates)
    except ValueError:
        return True
    today = today or _dt.date.today()
    return (today - last).days > PASSING_DAYS


def gate_report():
    """{gate: refusals so far in this process}. Reset with gate_reset()."""
    return dict(GATE_COUNTS)


def gate_reset():
    for g in GATE_COUNTS:
        GATE_COUNTS[g] = 0


def _dense_grounded(index, query, threshold=None, among=None):
    """True when a stored fact is semantically close to the question.

    `among`: only these facts (the ones about to be returned) count.
    2026-10-02 (tools/scale_test.py): over the WHOLE store the best
    similarity rises with its size, the scale creep ledger 5o warned about.
    At 395 facts "Where did Alex Reyes go to university?" passed on 0.628 to
    a filler fact ("went to Lyon a while ago") and then returned a different
    one, the Perrin job. A fact that is not returned is no evidence for the
    one that is.

    Returns True (defers) if the index has no embeddings -- a missing signal
    must never be read as evidence of absence.
    """
    thr = DENSE_GROUND if threshold is None else threshold
    emb = getattr(index, "emb", None)
    if emb is None or len(emb) == 0:
        return True
    try:
        import numpy as np
        bi, _ = _RV3._models()
        qv = bi.encode([query], normalize_embeddings=True)[0]
        if among is not None:
            ids = {id(h) for h in among}
            rows = [i for i, f in enumerate(getattr(index, "facts", []))
                    if id(f) in ids]
            if not rows:
                return False
            emb = emb[rows]
        return float(np.max(emb @ qv)) >= thr
    except Exception:
        return True


# 2026-10-02 (false-memory bench): "Where do I live?" refused while the
# store held "relocated to Coburg" -- no shared word, and the paraphrase is
# too far for the dense check. The state families (currency.py) already know
# that relocating is about where someone lives, so a question that asks
# about a family is grounded by a fact in it.
_QUESTION_FAMILIES = [
    (re.compile(r"\bwhere\b.*\b(live|living|based|stay|staying)\b|"
                r"\b(address|home ?town|which city|what city|suburb)\b", re.I),
     ("residence",)),
    (re.compile(r"\b(work|job|occupation|profession|career|employer|employs?|"
                r"employed|for a living|job title|role)\b", re.I),
     ("role", "employer")),
    (re.compile(r"\b(diet|vegan|vegetarian|pescatarian|eat meat)\b", re.I),
     ("diet",)),
    (re.compile(r"\b(married|single|relationship|partner|dating|engaged|"
                r"divorced)\b", re.I), ("relationship status",)),
    (re.compile(r"\b(how old|my age)\b", re.I), ("age",)),
    (re.compile(r"\b(car|drive)\b", re.I), ("car",)),
    (re.compile(r"\b(kids|children)\b", re.I), ("number of children",)),
]


# a question about someone else: "my brother", a name, he/she/they
# 2026-10-02: only PEOPLE and animals make a question about someone else --
# "my beverage of choice" is the user's
_ABOUT_OTHER = re.compile(
    r"\bmy\s+(?:sister|brother|mum|mom|dad|mother|father|wife|husband|"
    r"partner|boyfriend|girlfriend|fiance|fiancee|friend|friends|boss|manager|"
    r"colleague|colleagues|coworker|son|daughter|kid|child|baby|neighbour|"
    r"neighbor|flatmate|roommate|cousin|aunt|uncle|niece|nephew|grandma|"
    r"grandpa|grandmother|grandfather|parents|teacher|doctor|dentist|"
    r"landlord|client|dog|cat|pet)s?\b|"
    r"\b(he|she|they|his|her|their|him|them)\b|(?<!^)\b(?!I\b)[A-Z][a-z]+")


def _family_grounded(query, hits):
    if _ABOUT_OTHER.search((query or "").strip()):
        return False
    # "What job should I get?" asks for advice, not for a stored fact
    if re.search(r"\b(should|could|would|might)\b", query or "", re.I):
        return False
    asked = {f for rx, fams in _QUESTION_FAMILIES if rx.search(query or "")
             for f in fams}
    if not asked:
        return False
    import currency
    for h in hits:
        fams = {f for f, _ in currency._families(h.get("attr"), h.get("value"),
                                                 weak=True)}
        if fams & asked:
            return True
    return False


def _type_grounded(query, hits):
    """2026-10-02: a question that asks for a TYPE ("Which food do I
    dislike?", "What is my beverage of choice?") is grounded by a record
    that holds a thing of that type, with the question's own verb and
    polarity (answer_type.py, WordNet is-a). Only for questions about the
    user."""
    if os.environ.get("RG_ANSWER_TYPE") == "0":
        return False
    if _ABOUT_OTHER.search((query or "").strip()):
        return False
    try:
        import answer_type as _AT
    except Exception:
        return False
    qt = _AT.question_type(query)
    if not qt:
        return False
    verbs = _AT.question_verbs(query, qt[0])
    pres = _AT.is_presence(query)
    return any(_AT.has_type(h.get("source") or h.get("value") or h.get("text"),
                            qt[0], qt[1], verbs, possess=pres) for h in hits)


def _grounded(query, hits, owner=None):
    """True when any candidate shares a content word with the question.

    Deliberately weak: ONE shared token is enough. This is a floor on
    evidence, not a relevance judgement -- the reranker does relevance. Its
    job is to catch the case where the store simply holds nothing about the
    topic and the reranker returned its least-bad guess anyway.
    """
    import re as _re
    q = {_stem(t) for t in _re.findall(r"[a-z]+", (query or "").lower())
         if t not in _RERANK_STOP and len(t) > 2}
    q -= _owner_stems(owner)    # e281: the owner's name grounds nothing
    # e281b: nor does anyone else's. A capitalised token that is not
    # sentence-initial in a retrieved record is a NAME the store knows (Sam,
    # Priya, Acme); sharing it says the question is about a known entity,
    # not that the record answers what was asked -- "What is Sam's salary?"
    # grounded on "partner Sam works from home". With the names gone the
    # question must share a real content word, or hold nothing but names,
    # in which case it defers ("Who is Sam?" still answers).
    names = set()
    for h in hits:
        text = h.get("text") or ""
        for w in _re.findall(r"(?<!^)(?<=\s)[A-Z][a-z]+", text):
            names.add(_stem(w.lower()))
    if q and q <= names:
        return True             # the question IS the entity; nothing else to ground
    q -= names
    if not q:
        return True             # nothing to ground against; defer to the floor
    for h in hits:
        text = h.get("text") or f"{h.get('attr')} {h.get('value')}"
        ts = {_stem(t) for t in _re.findall(r"[a-z]+", text.lower())}
        if q & ts:
            return True
    return False


def _subject_bonus(query, text, bonus=None):
    """How much to lift a record whose SUBJECT REGION answers the query."""
    import re as _re
    b = SUBJECT_BONUS if bonus is None else bonus
    q = [t for t in _re.findall(r"[a-z]+", (query or "").lower())
         if t not in _RERANK_STOP]
    if len(q) < 2:
        return 0.0
    lead = " ".join((text or "").lower().split()[:5])
    hits = sum(1 for t in q if t in lead)
    # TWO content tokens, not one: a single incidental match ("work" in "works
    # from home") is exactly the distractor this is meant to demote.
    return b * hits if hits >= 2 else 0.0


# 2026-10-02: YOUR OWN WORDS when no fact answers (notebook e288, ledger
# §5g). On the blind false-memory bench sourcedrecall recalled 5/11 side facts
# to RAG's 11/11: when the parser makes no fact from a sentence, nothing can
# find it. The user's sentences are kept verbatim and searched only when the
# fact path would refuse. A sentence behind a REPLACED fact is left out, so
# this cannot bring back a value the currency rules already retired.
VERBATIM_FLOOR = -6.0     # PILOT, raw cross-encoder; see tools/dogfood.py
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _norm_sent(t):
    return re.sub(r"\s+", " ", (t or "").strip().lower()).strip(" .!?")


# review round 3: hypotheticals, hedges and other people's sentences were
# quoted as answers ("Am I rich?" -> "If I were rich I would quit...", "Do I
# have kids?" -> "My sister Anna ... has two kids").
_IRREALIS = re.compile(
    r"\b(if|unless|imagine|suppose|supposing|pretend|wish|hope|hoping|"
    r"would|wouldn't|could|might|maybe|perhaps|probably|possibly|someday|"
    r"one day|thinking about|thinking of|considering|planning to|plan to|"
    r"want to|wanna|gonna|going to|dream|dreamed|dreamt|joke|joking|kidding|"
    r"in theory|hypothetically)\b", re.I)
_OTHER_LED = re.compile(
    r"^\W*(?:he|she|they|it|everyone|everybody|nobody|people|someone|"
    r"my (?:sister|brother|mum|mom|dad|mother|father|wife|husband|partner|"
    r"boyfriend|girlfriend|friend|friends|boss|manager|colleague|colleagues|"
    r"son|daughter|kids|children|neighbour|neighbor|flatmate|roommate|"
    r"cousin|aunt|uncle|grandma|grandpa|grandmother|grandfather|doctor|"
    r"teacher|dog|cat)|(?!I\b)[A-Z][a-z]+\s+(?:is|was|has|had|lives|works|"
    r"said|says|thinks|went|got|loves|likes|and))\b", re.I)


def _quotable(sent):
    """A sentence the user may be quoted on: not a hypothetical or hedge,
    and not led by someone else."""
    return not (_IRREALIS.search(sent) or _OTHER_LED.match(sent))


def _denied_sentence(sent, values, sources=()):
    n = _norm_sent(sent)
    if any(src and _norm_sent(src) == n for src in sources):
        return True
    return any(v and len(v.strip()) >= 3 and _norm_sent(v) in n for v in values)


def _unparsed_sentences(conversations_path, g):
    try:
        from run_profile_full import load_stream_and_titles
        from prose import _is_prose
    except Exception:
        return []
    # only a sentence behind a REPLACED fact is left out (its value is
    # stale); one that made a current fact may still hold more than the
    # parser took ("I'm vegetarian and I can't stand cilantro.")
    used = set()
    for st in (g.nodes, g.provisional, getattr(g, "hearsay", {}) or {}):
        for nd in st.values():
            if nd.get("source") and nd.get("current") is False:
                used.add(_norm_sent(nd["source"]))
    try:
        stream, _ = load_stream_and_titles(conversations_path)
    except Exception:
        return []
    # what the user asked to forget is never quoted back
    denied, denied_said = [], []
    try:
        import json as _json
        cpath = os.path.join(os.path.dirname(conversations_path),
                             "corrections.jsonl")
        if os.path.exists(cpath):
            for line in open(cpath, encoding="utf-8"):
                try:
                    c = _json.loads(line)
                except ValueError:
                    continue
                if c.get("action") == "deny":
                    if c.get("said"):
                        denied_said.append(str(c["said"]))
                    if c.get("value"):
                        denied.append(str(c["value"]))
    except OSError:
        pass
    out = {}
    for _step, uuid, date, text in stream:
        if not _is_prose(text):
            continue
        for sent in _SENT_SPLIT.split(text.strip()):
            n = _norm_sent(sent)
            if "[secret removed]" in sent or not _quotable(sent):
                continue
            if (not n or n in used or sent.strip().endswith("?")
                    or len(n.split()) < 4
                    or _denied_sentence(sent, denied, denied_said)):
                continue
            prev = out.get(n)
            if prev is None or (date or "") > (prev["date"] or ""):
                import hashlib
                out[n] = {"id": "u" + hashlib.sha1(n.encode()).hexdigest()[:6],
                          "attr": "", "value": sent.strip(), "text": sent.strip(),
                          "date": date, "conv": uuid}
    return list(out.values())


def _shares_content(query, sentence, owner=None):
    """A content word of the question (not a question word, pronoun, auxiliary
    or the owner's name) appears in the sentence."""
    q = {_stem(t) for t in re.findall(r"[a-z]+", (query or "").lower())
         if len(t) > 2 and t not in _RERANK_STOP and t not in _Q_FUNCTION}
    q -= _owner_stems(owner)
    st = {_stem(t) for t in re.findall(r"[a-z]+", (sentence or "").lower())}
    return bool(q & st)


_Q_FUNCTION = frozenset("""what which where when who whom whose why how does
did have has had any many much some there their they them your yours mine
the and for are was were been being can could would should will shall might
must about tell know remember again ever""".split())


def _mark_ceased(g, titles=None):
    if os.environ.get("RG_CESSATION") == "0":
        return
    import currency
    # `titles` is insertion-ordered by ingestion, which is the only real
    # sequence available when several conversations share a date (e273).
    order = {c: i for i, c in enumerate(titles or {})}
    currency.mark_ceased(g, order=order or None)
    # 2026-10-02: a later move / new job replaces the old residence/employer.
    # ONE hook for both loaders (Memory.load and the server's _build) -- the
    # server used to call currency directly, the §5m shape waiting to happen.
    currency.mark_state_changes(g, order=order or None)


class Memory:
    """Read-side memory over the wired, corroborated profile."""

    def __init__(self, graph, titles=None, owner=None):
        self.g = graph
        self.titles = titles or {}
        # 2026-10-02, SCOPING: the most common complaint about AI memory is
        # facts from one context leaking into another (work into personal,
        # one project into the next). `scope` is the context being read in
        # (a project path, or None for no scoping); `conv_scopes` maps each
        # conversation to the context it happened in. Facts about the user
        # are visible everywhere; facts about the world are visible only in
        # the scope they were said in. See _visible.
        self.scope = None
        self.conv_scopes = {}
        # e281: the owner's name, when the caller knows it (the server does:
        # it hands the same name to the extractor). Grounding must ignore it.
        self.owner = owner
        self.unparsed = []      # set by the loader: _unparsed_sentences

    @classmethod
    def load(cls, conversations_path, min_mentions=2):
        """Build from conversations.json + the extraction cache next to it
        (cache-only; no LLM calls). Owner corrections (corrections.jsonl in the
        same dir) are applied INSIDE build_facts, at the fact level, before
        wiring -- so graph, report and recall stay consistent. The graph-level
        apply_corrections below remains for runtime (in-session) deny/confirm."""
        from run_wire import build_facts
        sources = {}
        facts, prov, hearsay, n_convs, titles, _ = build_facts(
            conversations_path, min_mentions, sources=sources)
        g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov,
                                 hearsay=hearsay)
        _attach_sources(g, sources)
        _mark_ceased(g, titles)
        mem = cls(g, titles)
        mem.unparsed = _unparsed_sentences(conversations_path, g)
        return mem

    def apply_corrections(self, corrections):
        """THE CORRECTION LOOP (owner-authored; the owner is ground truth).
        Each correction: {"action": "deny"|"confirm", "attribute": <canon attr>,
        "value": <substring of the fact value>}.
          deny    -> the fact is wrong: remove it from BOTH tiers, and remove
                     its edges (an edge to a wrong fact is receipted noise).
          confirm -> owner-vouched: a provisional fact is PROMOTED to asserted
                     (the confirmation IS the second piece of evidence); an
                     asserted fact is marked owner-confirmed.
        Corrections are data (a local owner-edited file), never inference."""
        applied = []
        for c in corrections:
            act = c.get("action")
            attr = str(c.get("attribute", "")).lower().strip()
            sub = str(c.get("value", "")).lower().strip()
            if act == "deny" and getattr(self, "unparsed", None):
                before = len(self.unparsed)
                self.unparsed = [u for u in self.unparsed
                                 if not _denied_sentence(
                                     u["value"], [sub] if attr == "said" else [],
                                     [c.get("said")])]
                if len(self.unparsed) < before:
                    applied.append(("denied-quote", attr))
            for store in (self.g.nodes, self.g.provisional):
                for nid in [k for k, d in store.items()
                            if d["attr"] == attr and sub in d["value"].lower()]:
                    if act == "deny":
                        gone = store.pop(nid)
                        # a forgotten fact's own words are not quoted back
                        self.unparsed = [u for u in self.unparsed
                                         if not _denied_sentence(
                                             u["value"], [gone.get("value")],
                                             [gone.get("source")])]
                        for pair in [p for p in self.g.edges if nid in p]:
                            self.g.edges.pop(pair)
                        self.g.adj.pop(nid, None)
                        for nbrs in self.g.adj.values():
                            nbrs.pop(nid, None)
                        applied.append(("denied", nid))
                    elif act == "confirm":
                        nd = store.pop(nid)
                        nd["tier"] = "asserted"
                        nd["owner_confirmed"] = True
                        nd["n_mentions"] += 1   # the confirmation is evidence
                        self.g.nodes[nid] = nd
                        applied.append(("confirmed", nid))
        return applied

    # ---------------- the contract ----------------

    def recall(self, query, max_hops=2, top=12):
        """The product's read call. Structured, receipted, or an honest no."""
        r = self.g.spread(query, max_hops=max_hops, top=top)
        if r.get("abstain"):
            return {"found": False, "abstain": True, "query": query,
                    "answer": "no stored fact matches -- never seen"}
        # e273: a superseded fact ranks last on THIS path too. Currency is a
        # correctness property -- "you told me X" when the user has since said
        # otherwise is wrong regardless of which retriever found it -- so it
        # cannot live only in recall_v3. Demoted, never dropped.
        def _stale_last(nodes):
            return sorted(nodes, key=lambda nd: nd.get("current") is False)

        out = {"found": True, "abstain": False, "query": query,
               "asserted": [self._fact(nd) for nd in _stale_last(r["seeds"])],
               "wired": [{"fact": self._fact(d["node"]),
                          "activation": round(d["activation"], 3),
                          "hops": d["hops"],
                          "via": [{"edge": f"{e['a']} <-> {e['b']}",
                                   "shared_conversations": e["cooc"]}
                                  for e in d["path"]]}
                         for d in r["neighbourhood"]],
               "unconfirmed": [self._fact(p["node"], provisional=True)
                               for p in sorted(
                                   r.get("provisional", []),
                                   key=lambda p: p["node"].get("current") is False)],
               # entry 246: NOT surfaced in "asserted"/"unconfirmed" -- an
               # assistant claim about the user is neither a corroborated nor
               # an unconfirmed USER fact. Kept under its own key so a caller
               # (the MCP surface) can show it on request, receipted, without
               # it ever being volunteered as the user's own memory.
               "hearsay": [self._fact(h["node"]) for h in r.get("hearsay", [])]}
        return out

    def recall_v3(self, query, top_n=8, min_score=None):
        """The product read path under RG_PROFILE_V3 (e258).

        `recall()` seeds from `wire.match` -- token overlap between the query
        and a node's attr+value tokens, widened by a fixed synonym table. That
        is the retrieval the PRODUCT has always shipped. Retrieval v3 (BM25 u
        dense bge-small, cross-encoder rerank) has been the measured champion
        since e132 and was only ever wired into the benchmark QA path.

        THE SCORE FLOOR IS NOT OPTIONAL. Wired without one, v3 answers every
        question -- including every question about something never mentioned
        (dogfood store, e258: abstention on 8 unseen topics went 8/8 -> 0/8,
        and a garbage node ranked first for nearly all of them). Honest
        abstention is the product, so v3 without a floor is a REGRESSION even
        though its pool recall is far better. The floor restores it: the
        cross-encoder's own score separates known from unseen (KNOWN median
        -4.69, UNSEEN median -8.59 on that store).

        `min_score` defaults to RG_PROFILE_V3_FLOOR, else FLOOR_V3. That
        default was SELECTED ON THE SAME 18 QUESTIONS IT WAS SCORED ON --
        it is a pilot operating point, not a validated constant, and it needs
        a held-out set and the real harness before anyone quotes it.

        Rank order is preserved across tiers. An earlier draft bucketed the
        hits into asserted-then-unconfirmed, which threw away the reranker's
        ordering and dropped rank-1 correctness from 7/10 to 1/10 -- the
        retriever was fine and the wiring destroyed it.
        """
        nodes, prov = self.g.nodes, self.g.provisional
        if not nodes and not prov:
            return self._abstain(query, gate="empty-store")
        floor = min_score
        if floor is None:
            env = os.environ.get("RG_PROFILE_V3_FLOOR")
            floor = float(env) if env else FLOOR_V3
        idx = self._index_v3()
        # e272: fetch a WIDER pool than we return, because the re-rank below
        # cannot promote a record the retriever already truncated away. The
        # first version of this reordered the top-8 and changed nothing --
        # the answer was at rank 9.
        rerank = os.environ.get("RG_SUBJECT_RERANK") != "0"
        # 2026-10-02: every candidate is scored by the cross-encoder anyway,
        # so keeping all of them costs nothing; the margin and top_n below
        # still bound what is returned. With 32, an answer the cross-encoder
        # under-scores (rank 34, "written in Go" for "what language") was
        # gone before answerability could put it first.
        pool = 120 if rerank else top_n
        # the dense pool grows with the store (capped for the reranker's
        # cost): at 488 facts "switched to tea" was 34th by similarity to
        # "What is my beverage of choice?" and never reached the reranker
        dense_k = min(60, max(20, len(getattr(idx, "facts", [])) // 8))
        scored = _RV3.retrieve_facts_v3(idx, query, k=120, dense_k=dense_k,
                                        top_n=pool, with_scores=True)
        # e272 CORRECTION TO e258: the floor is an ABSTENTION decision, not a
        # per-record filter. The separation it rests on was measured on the
        # TOP-1 raw score (answerable >= -7.72, never-mentioned <= -7.94);
        # nothing ever validated applying it to every record, and doing so
        # silently discarded true answers that happened to rank low --
        # "the billing service is written in Go" scored under the floor and
        # was dropped before the re-rank could promote it.
        #
        # Gate on the best raw score; then return the pool. This keeps exactly
        # the property that was measured and stops the floor doing a job it
        # was never shown to do.
        if not scored:
            return self._abstain(query, idx, gate="no-candidates")
        if floor is not None and max(sc for _, sc in scored) < floor:
            return self._abstain(query, idx, gate="score-floor")
        # e274: LEXICAL GROUNDING, a second and independent abstention signal.
        #
        # The score floor degrades as the store grows -- max-of-N rises with N
        # -- and it does so silently. Measured on this store at 14 nodes the
        # two populations separated cleanly (e260, 18/18); at 38 nodes nothing
        # separates them cleanly and the best absolute cutoff costs one false
        # answer in seven ("What is my favourite film?" -> "Alex Reyes likes
        # Go"). A real store has thousands of nodes, so tuning the constant
        # further would be fitting noise.
        #
        # Grounding does not degrade that way: if NO retrieved record shares a
        # content word with the question, we hold no evidence about the topic,
        # however the reranker scored it. Measured here: 7/7 unseen rejected,
        # 19/20 answerable kept. Required TOGETHER with the floor, never
        # instead of it -- two independent signals, both must pass.
        # Grounded LEXICALLY or DENSELY -- either is enough. Lexical catches
        # the shared-word case for free; dense catches paraphrase, which is
        # what a real question usually is (e275).
        if os.environ.get("RG_GROUNDING") != "0":
            own = getattr(idx, "owner", None)
            top3 = [h for h, _ in scored[:3]]
            if not (_grounded(query, top3, owner=own)
                    or _dense_grounded(idx, _strip_owner(
                        query, own, _entity_names(top3)), among=top3)
                    or _family_grounded(query, [h for h, _ in scored[:10]])
                    or _type_grounded(query, [h for h, _ in scored[:40]])):
                return self._abstain(query, idx, gate="grounding")
        kept = list(scored)
        # 2026-10-02: scoping -- another project's facts are not this one's.
        if self.scope and self.conv_scopes:
            _before = len(kept)
            kept = [p for p in kept
                    if self._visible(nodes.get(p[0].get("id"))
                                     or prov.get(p[0].get("id")) or {})]
            if _before and not kept:
                return self._abstain(query, idx, gate="other-scope")
        # e272: reorder ONLY what already cleared the floor, then truncate.
        if rerank:
            # e273: a fact the user has since ENDED ranks below one that still
            # holds. Demoted, never hidden -- the receipt is permanent and a
            # caller can still see it, labeled, below the current answer.
            kept.sort(key=lambda p: -(
                p[1] + _subject_bonus(query, p[0].get("text") or "")
                - (STALE_PENALTY if p[0].get("current") is False else 0.0)))
        # 2026-10-02: RETURN WHAT ANSWERS, NOT THE WHOLE POOL. A fresh user
        # with eight facts got all eight back for every question (new-user
        # install test) and the agent had to pick. Keep the re-rank's first
        # choice, then only candidates whose RAW score is within
        # RG_RECALL_MARGIN of the best raw score in the pool. PILOT VALUE: 4.0
        # was chosen on the 26 dogfood questions, where the right answer sat
        # at most 3.42 below the top -- re-check on held-out probes before
        # trusting it. Measured over the whole pool BEFORE truncation, so a
        # superseded fact that answers strongly (demoted by STALE_PENALTY)
        # still sets the bar instead of letting weak neighbours fill the list.
        # 2026-10-02 (tools/scale_test.py): a question about a named entity
        # ("What language is the billing service in?") puts the facts that
        # ANSWER it first, before the margin. The cross-encoder scored "the
        # billing service is written in Go" 6 points under filler about other
        # services -- it does not know Go is a language -- and the margin cut
        # it before answerability ever saw it.
        if os.environ.get("RG_ANSWERABILITY") != "0":
            import answerability as _AN
            _qr = _AN.read_question(query)
            if _qr and _qr[0]:
                _own = getattr(idx, "owner", None)
                _ans = [p for p in kept if _AN.answers(
                    {"text": p[0].get("text"), "said": p[0].get("source")},
                    _qr, owner=_own)]
                if _ans:
                    _a = {id(p) for p in _ans}
                    kept = _ans + [p for p in kept if id(p) not in _a]
        _margin = float(os.environ.get("RG_RECALL_MARGIN", RECALL_MARGIN))
        if _margin >= 0 and len(kept) > 1:
            _best = max(sc for _, sc in kept)
            kept = kept[:1] + [p for p in kept[1:]
                               if p[1] >= _best - _margin]
        # A superseded fact that answers is shown WITH what replaced it: "you
        # lived in Fitzroy (no longer true); you moved to Brunswick". Without
        # this the replacement could be cut and the stale fact stand alone.
        _ids = {h.get("id") for h, _ in kept}
        _out = []
        for h, sc in kept:
            nd = nodes.get(h.get("id")) or prov.get(h.get("id")) or {}
            rid = nd.get("superseded_by")
            if (nd.get("current") is False and rid and rid not in _ids
                    and (rid in nodes or rid in prov)):
                _out.append(({"id": rid}, sc))
                _ids.add(rid)
            _out.append((h, sc))
        kept = _out[:top_n]
        # rank order preserved; `tier` says which store a fact came from so a
        # caller can still tell corroborated from single-mention.
        facts, unconfirmed = [], []
        for h, sc in kept:
            nid = h.get("id")
            if nid in nodes:
                f = self._fact(nodes[nid])
            elif nid in prov:
                f = self._fact(prov[nid], provisional=True)
            else:
                continue
            f["score"] = round(float(sc), 4)
            facts.append(f)
            if f.get("status") == "unconfirmed-single-mention":
                unconfirmed.append(f)
        if not facts:
            return self._abstain(query, idx, gate="no-renderable")
        # 2026-10-02: ANSWERABILITY, separate from relevance (answerability.py).
        # A fact about the right entity is not an answer about the asked
        # attribute: "What is my partner's job?" must not come back as
        # "partner Sam works from home". Answering facts go first; if none
        # answers, refuse and say what IS known about the entity.
        # 2026-10-02: a question asking for a checkable TYPE is answered only
        # by a record of that type ("What sport do I play?" is not answered
        # by "plays the cello")
        if os.environ.get("RG_ANSWER_TYPE") != "0" and not _ABOUT_OTHER.search(query):
            try:
                import answer_type as _AT
                qt = _AT.question_type(query)
            except Exception:
                qt = None
            if qt and qt[0] in _AT.CHECKABLE:
                vb = _AT.question_verbs(query, qt[0])
                typed = [f for f in facts if _AT.has_type(
                    f.get("said") or f.get("value") or f.get("text"),
                    qt[0], qt[1], vb, possess=_AT.is_presence(query))]
                if not typed:
                    return self._abstain(query, idx, gate="attribute",
                                         known_about=[], asked=(None, qt[0]))
                facts = typed + [f for f in facts if f not in typed]
        if os.environ.get("RG_ANSWERABILITY") != "0":
            import answerability as _AN
            qr = _AN.read_question(query)
            if qr:
                ok = [f for f in facts
                      if _AN.answers(f, qr, owner=getattr(idx, "owner", None))]
                if not ok:
                    known = [f for f in facts
                             if qr[0] and _AN._mentions(
                                 f"{f.get('text') or ''} {f.get('said') or ''}",
                                 qr[0])]
                    return self._abstain(query, idx, gate="attribute",
                                         known_about=known, asked=qr)
                facts = ok + [f for f in facts if f not in ok]
                unconfirmed = [f for f in facts if f in unconfirmed]
        # 2026-10-02: what the user said LATER, in words the parser could not
        # structure ("Two months without any coffee now" after "four coffees
        # a day"). Appended after the facts, dated, never in place of them.
        newer = self._newer_words(query, facts)
        facts = facts + newer
        return {"found": True, "abstain": False, "query": query,
                "asserted": [f for f in facts if f not in unconfirmed],
                "ranked": facts, "wired": self._wired_v3(kept),
                "unconfirmed": unconfirmed,
                "hearsay": self._hearsay_v3(idx, query),
                "retrieval": "v3", "floor": floor}

    def _wired_v3(self, kept):
        """The receipted co-occurrence neighbourhood of the corroborated hits.

        Review 2026-09-05: recall_v3 hardcoded `wired: []` while the MCP
        docstring promised the field, and e277 made recall_v3 the default --
        so the field went dead for every caller on the same day. Seeds are the
        CORROBORATED hits only (the provisional tier is never wired, by
        invariant); each seeds at activation 1.0 because cross-encoder logits
        are not on the [0, 1] scale `spread` assumes."""
        # Seed from the RANK-1 corroborated hit only. v3 returns a wide pool
        # (in a small store, every node), so seeding from all hits leaves no
        # node to be a neighbour and the field is empty exactly where the
        # old path filled it. "Wired" answers: what is receipted as
        # co-occurring with THE answer -- the paths carry the edge receipts.
        walk = getattr(self.g, "neighbourhood", None)
        # Review 2026-10-02: this took the first CORROBORATED hit anywhere in
        # the pool, and most of a real store is provisional -- so the seed was
        # usually a lower-ranked hit, sometimes a ceased one, and "wired to
        # THE answer" was false. Seed from rank 1 or not at all: a provisional
        # rank-1 is never wired (tier invariant), and a superseded fact's
        # neighbourhood is not the current answer's.
        top = kept[0][0].get("id") if kept else None
        node = self.g.nodes.get(top) if top is not None else None
        if node is None or walk is None or node.get("current") is False:
            return []
        seeds = {top: 1.0}
        return [{"fact": self._fact(d["node"]),
                 "activation": round(d["activation"], 3),
                 "hops": d["hops"],
                 "via": [{"edge": f"{e['a']} <-> {e['b']}",
                          "shared_conversations": e["cooc"]}
                         for e in d["path"]]}
                for d in walk(seeds)]

    def _hearsay_v3(self, idx, query, top_n=3):
        """Assistant claims ABOUT the user, receipted, never asserted.

        e277: this was hardcoded `[]`. The tier built in e246/e249 simply
        never surfaced on the product path, and `RG_HEARSAY=1` paid the cost
        of building the sub-index that nothing then read -- the flag was inert
        where it mattered and worked on the benchmark. FIFTH instance of the
        pathology ledger 5m names, and the only one I wrote myself.
        """
        sub = getattr(idx, "hearsay", None)
        if sub is None:
            return []
        try:
            hits = _RV3.retrieve_facts_v3(sub, query, k=60, dense_k=10,
                                          top_n=top_n)
        except Exception:
            return []
        # e277: HEARSAY NEEDS THE SAME GROUNDING GATE AS EVERYTHING ELSE.
        # `retrieve_facts_v3` returns its top_n by RANK unconditionally, so
        # without this the cello turns up under "When is my birthday?" -- and
        # e250 already caught exactly this, appending hearsay to 94.5% of
        # questions. Re-introduced here the moment the tier was wired in, and
        # caught only because that entry left tests behind.
        store = getattr(self.g, "hearsay", {}) or {}
        out = []
        for h in hits:
            nd = store.get(h.get("id"))
            if nd is None or not self._visible(nd):
                continue
            own = getattr(sub, "owner", None)
            if not (_grounded(query, [h], owner=own)
                    or _dense_grounded(sub, _strip_owner(query, own))):
                continue
            out.append(self._fact(nd))
        return out

    def _abstain(self, query, idx=None, gate=None, known_about=None,
                 asked=None):
        """e277: HEARSAY-ONLY IS NOT ABSTENTION.

        e280: `gate` names the predicate that refused (see GATES). The
        abstention it returns carries NO payload -- no ranked, asserted or
        unconfirmed facts -- and the harness checks that invariant, because
        a flag that says "abstained" over a list of facts is the one thing a
        caller cannot be trusted to ignore.

        e249 established this on the other read path: if the assistant said
        something about the user and the user never confirmed it, the memory
        HAS seen the topic -- it just holds no assertion. Saying "never seen"
        there is false, and it throws away a receipt the caller may want.
        recall_v3 abstained before ever consulting the hearsay tier."""
        if gate in ("empty-store", "no-candidates", "score-floor", "grounding",
                    "attribute"):
            vb = self._verbatim(query, asked=asked)
            if vb:
                return {"found": True, "abstain": False, "query": query,
                        "asserted": [], "ranked": vb, "wired": [],
                        "unconfirmed": vb, "retrieval": "v3+verbatim",
                        "note": ("the user's own words; no stored fact "
                                 "answers, so these are quoted as said")}
        hs = self._hearsay_v3(idx, query) if idx is not None else []
        if hs:
            # `found` means the memory has SEEN the topic -- same contract as
            # `recall()`, whose hearsay-only return is found=True. e277 wrote
            # False here, which made the two retrievers disagree on the one
            # field a caller branches on (review 2026-09-05).
            return {"found": True, "abstain": False, "query": query,
                    "asserted": [], "ranked": [], "wired": [],
                    "unconfirmed": [], "hearsay": hs, "retrieval": "v3",
                    "note": ("hearsay only: an assistant claim about the "
                             "user, never asserted by the user")}
        if gate is not None:
            GATE_COUNTS[gate] = GATE_COUNTS.get(gate, 0) + 1
        out = {"found": False, "abstain": True, "query": query,
               "gate": gate,
               "answer": "no stored fact matches -- never seen"}
        if gate == "attribute":
            ent, att = asked or (None, None)
            out["answer"] = (f"nothing stored says {att}"
                             + (f" for {ent}" if ent else ""))
            # what IS known, so an agent can say "I know Sam works from home,
            # but not their salary" instead of only "I don't know"
            out["known_about"] = list(known_about or [])
        return out

    def _verbatim_index(self):
        key = len(self.unparsed)
        if getattr(self, "_vb_key", None) != key:
            idx = _RV3.IndexV3(self, facts=list(self.unparsed))
            idx.owner = self.owner
            self._vb, self._vb_key = idx, key
        return self._vb

    def _verbatim(self, query, asked=None, margin=True):
        """The user's own sentences that made no fact, when they answer."""
        if os.environ.get("RG_VERBATIM") == "0" or not self.unparsed:
            return []
        try:
            idx = self._verbatim_index()
            hits = _RV3.retrieve_facts_v3(idx, query, k=60, dense_k=20,
                                          top_n=10, with_scores=True)
        except Exception:
            return []
        floor = float(os.environ.get("RG_VERBATIM_FLOOR", VERBATIM_FLOOR))
        hits = [(h, sc) for h, sc in hits if sc >= floor
                and (not self.scope or not self.conv_scopes
                     or self.conv_scopes.get(h.get("conv")) in (None, self.scope))]
        if not hits:
            return []
        own = self.owner
        # LEXICAL grounding only, per sentence. First-person sentences all
        # sit close to first-person questions in embedding space, and the
        # cross-encoder did not separate them either (tools/scale_test.py at
        # 1,526 facts: "Do I have any children?" -> "I have a dog and a cat
        # at home" at -5.2, while "I can't stand cilantro" answered "Which
        # food do I dislike?" at -5.4). A quoted sentence must share a
        # content word with the question; paraphrase-only matches are lost.
        hits = [(h, sc) for h, sc in hits
                if (_grounded(query, [h], owner=own)
                    and _shares_content(query, h["value"], own))
                or _type_grounded(query, [h])]
        if not hits:
            return []
        try:
            import answerability as _AN
            qr = asked or _AN.read_question(query)
        except Exception:
            qr = None
        if qr:
            hits = [(h, sc) for h, sc in hits
                    if _AN.answers({"text": h["value"]}, qr, owner=own)]
        if not hits:
            return []
        best = hits[0][1]
        if margin:
            hits = [p for p in hits if p[1] >= best - RECALL_MARGIN]
        hits = hits[:3 if margin else 10]
        out = []
        for h, sc in hits:
            out.append({"id": h["id"], "attribute": "said", "value": h["value"],
                        "text": f'(their words) "{h["value"]}"', "said": None,
                        "mentions": 1, "status": "verbatim", "current": True,
                        "superseded_by": None, "supersedes": [],
                        "passing": _passing({"source": h["value"]}),
                        "score": round(float(sc), 4),
                        "receipts": [{"date": h.get("date"),
                                      "conversation": self.titles.get(
                                          h.get("conv"), h.get("conv") or "")[:60],
                                      "conversation_id": h.get("conv")}]})
        return out

    def _newer_words(self, query, facts, limit=2):
        if os.environ.get("RG_VERBATIM") == "0" or not facts:
            return []
        dates = [r.get("date") for f in facts for r in (f.get("receipts") or [])
                 if r.get("date")]
        if not dates:
            return []
        last = max(str(d)[:10] for d in dates)
        said = {_norm_sent(f.get("said")) for f in facts if f.get("said")}
        out = []
        # no margin: a later sentence matters for being later, and the
        # cross-encoder scores "Two months without any coffee now" far
        # under "four coffees a day" for "How much coffee do I drink?"
        for v in self._verbatim(query, margin=False):
            d = str((v["receipts"][0] or {}).get("date") or "")[:10]
            if d > last and _norm_sent(v["value"]) not in said:
                out.append(v)
        return out[:limit]

    def _index_v3(self):
        """Cache one IndexV3 per memory state. Invalidated by node count --
        every write path rebuilds the Memory object, so identity is enough."""
        hear = getattr(self.g, "hearsay", {}) or {}
        key = (len(self.g.nodes), len(self.g.provisional), len(hear))
        if getattr(self, "_v3_key", None) != key:
            idx = _RV3.IndexV3(self)
            # Review 2026-09-05: IndexV3 builds its hearsay sub-index only
            # under RG_HEARSAY=1 so the BENCHMARK index stays byte-identical
            # to the banked one. Nothing on the product path sets that flag,
            # so e277's "hearsay is now wired" was true of a sub-index that
            # was never built here -- `_hearsay_v3` always saw None. The
            # product path builds it unconditionally; the benchmark path
            # (eval_rgp2 -> IndexV3 directly) is untouched.
            if idx.hearsay is None and hear:
                try:
                    idx.hearsay = _RV3.IndexV3(self, facts=list(hear.values()))
                except Exception:
                    idx.hearsay = None
            # e281: the owner's name, for grounding to ignore. Caller-supplied
            # first, then the index's own `name` fact, then read off the texts.
            own = (getattr(self, "owner", None) or getattr(idx, "owner", None)
                   or _guess_owner(list(self.g.nodes.values())
                                   + list(self.g.provisional.values())))
            idx.owner = own
            if idx.hearsay is not None:
                idx.hearsay.owner = getattr(idx.hearsay, "owner", None) or own
            self._v3 = idx
            self._v3_key = key
        return self._v3

    def profile(self, top=40):
        """The corroborated profile, most-evidenced first. Receipted."""
        # review 2026-09-05 A4: this sorted by mentions alone, so a fact the
        # user had since replaced rendered FIRST, as current. Superseded facts
        # now sort last (and render "(no longer true)").
        nodes = sorted((d for d in self.g.nodes.values() if self._visible(d)),
                       key=lambda d: (d.get("current") is False,
                                      -d["n_mentions"]))
        return [self._fact(nd) for nd in nodes[:top]]

    def conflicts(self):
        """Open slot conflicts (the acquisition frame's clarification hook,
        entry 137): same-attr facts whose values link into an evolution chain
        with >=2 distinct values and NO owner correction resolving them.
        Returns [{attribute, values:[{value, dates, evidence}], ask}] --
        `ask` is a ready-to-surface clarifying question. Deterministic."""
        import consolidate as C
        import timeline as TL
        import spacing as SP
        import itertools
        out = []
        store = list(self.g.nodes.values()) + list(self.g.provisional.values())

        # Candidates come from TWO sources, because neither alone is adequate
        # (entry 154, and a live bug this surfaced):
        #  - SINGLE-VALUED slots: enumerate every within-slot pair and let NLI
        #    judge. Lexical chaining MISSES real substitutions by construction
        #    -- "employer: apple" and "employer: google" share no tokens, so
        #    slot_chains() returned nothing and the canonical conflict was
        #    invisible. These slots hold few values each, so pairs are cheap.
        #  - everything else: lexical chains as before (recall-oriented), since
        #    narrative slots accumulate rather than substitute.
        chains = []
        by_attr = {}
        # e274: candidate slots were restricted to C.SINGLE_VALUED, a 24-name
        # allowlist that covers 0.2% of the rgx store (e251). The deterministic
        # parser keys on PREDICATES (`live_in`, `favourite_language`), none of
        # which are in it, so "I live in Berlin" then "I live in Munich" raised
        # nothing at all -- two equally-current facts and an agent left to pick.
        # The server README promises the opposite: "surfaces conflicts rather
        # than silently picking".
        #
        # Any attribute holding two or more DISTINCT values is now a candidate;
        # NLI remains the arbiter, which is what keeps the surface honest --
        # "I like Go" and "I like Rust" are both true and NLI says so.
        wide = os.environ.get("RG_CONFLICT_WIDE") != "0"
        for n in store:
            if n["attr"] in C.SINGLE_VALUED or (wide and _single_valued(n["attr"])):
                by_attr.setdefault(n["attr"], []).append(n)
        for attr, nodes in by_attr.items():
            # Only CORROBORATED values can raise a conflict. Without this the
            # surface explodes (measured: 2,836 asks on the owner profile),
            # because extraction over-assigns single-valued slots -- the
            # `location` slot held cafes, an OS name and a username, each of
            # which NLI correctly calls contradictory with the home city. A
            # single unconfirmed mention is not evidence of a change; it is
            # usually an extraction error, and the write-policy/quarantine
            # path is where those belong.
            # The >=2 gate was calibrated against the LLM extractor, whose
            # `location` slot held cafes, an OS name and a username -- 2,836
            # asks on the owner profile. The deterministic parser keys on the
            # predicate the user actually used, so a single mention is far more
            # often a real statement than an extraction error, and a user
            # states a self-fact ONCE (ledger P2). Re-measured rather than
            # assumed: ledger 6c.
            floor = 1 if wide else 2
            # `ceased`, NOT `current is False`: a fact the USER said had ended
            # is resolved and asking about it would be noise. A fact a
            # HEURISTIC demoted is precisely what this surface exists to ask
            # about -- filtering on `current` would let the heuristic silently
            # pick, which is the behaviour the README promises we do not.
            nodes = [n for n in nodes
                     if n.get("n_mentions", 1) >= floor
                     and not n.get("ceased")]
            nodes = sorted(nodes, key=lambda n: -n.get("n_mentions", 1))[:6]
            seen = set()
            for a, b in itertools.combinations(nodes, 2):
                if a["value"] == b["value"]:
                    continue
                if C.contradicts(attr, a["value"], b["value"]) is not True:
                    continue
                key = tuple(sorted((a["value"], b["value"])))
                if key in seen:
                    continue
                seen.add(key)
                chains.append((attr, [a, b]))
        for attr, chain in TL.slot_chains(store):
            if attr not in C.SINGLE_VALUED:
                chains.append((attr, chain))

        for attr, chain in chains:
            vals = [{"value": m["value"],
                     "dates": sorted(set(m["convs"].values())),
                     "evidence": SP.tag(m)} for m in chain]
            out.append({
                "attribute": attr,
                "values": vals,
                "ask": (f"I have {len(vals)} values for your {attr}: "
                        + " / ".join(f"'{v['value']}'" for v in vals[-3:])
                        + ". Which is current (or are both true)?"),
            })
        return out

    def _personal(self, nd):
        """Is this fact ABOUT the user (owner-subject or owner-possessed)?"""
        owner = getattr(self, "owner", None)
        if not owner:
            idx = getattr(self, "_v3", None)
            owner = getattr(idx, "owner", None) if idx is not None else None
        t = (nd.get("text") or "").strip()
        return bool(owner) and (t.startswith(owner + " ") or t.startswith(owner + "'s"))

    def _personal_kind(self, nd):
        """Is this the kind of fact that belongs to the person wherever they
        are -- health, family, home, job, diet, tastes -- rather than to the
        work in front of them? A statement about the user made inside a
        project ("works on the billing service") stays in that project."""
        try:
            import currency
            if currency._families(nd.get("attr"), nd.get("value")):
                return True
        except Exception:
            pass
        return bool(_PERSONAL_KINDS.search((nd.get("text") or "").lower()))

    def project_of(self, nd):
        """The project a fact is bound to, or None if it shows everywhere."""
        if not self.conv_scopes:
            return None
        scopes = {self.conv_scopes.get(c) for c in (nd.get("convs") or {})}
        if None in scopes or not scopes:
            return None                       # said outside any project
        if self._personal(nd) and self._personal_kind(nd):
            return None                       # about the person: global
        return sorted(scopes)[0]

    def _visible(self, nd):
        """With no current scope, everything shows. Otherwise a fact shows if
        it is not bound to a project, or is bound to this one."""
        if not self.scope or not self.conv_scopes or not nd:
            return True
        scopes = {self.conv_scopes.get(c) for c in (nd.get("convs") or {})}
        if self.scope in scopes:
            return True
        return self.project_of(nd) is None

    def _fact(self, nd, provisional=False):
        recs = sorted(nd["convs"].items(), key=lambda kv: kv[1], reverse=True)
        if nd.get("owner_confirmed"):
            status = "owner-confirmed"
        elif nd["tier"] == "hearsay":
            # entry 246: an assistant claim ABOUT the user, never asserted by
            # the user -- distinct from "unconfirmed-single-mention" (which
            # the user themself said once) so a caller can't mistake one for
            # the other.
            status = "hearsay"
        elif nd["tier"] == "provisional" or provisional:
            status = "unconfirmed-single-mention"
        else:
            status = "corroborated"
        return {"id": fact_id(nd), "attribute": nd["attr"], "value": nd["value"],
                # entry 244: the deterministic (rgx) extractor's full
                # proposition, when the node carries one; None for LLM-cache
                # facts and any node built without it -- callers fall back
                # to the attribute/value atom exactly as before.
                "text": nd.get("text"),
                # 2026-10-02: the sentence the fact was read from, verbatim.
                "said": nd.get("source"),
                # 2026-10-02: tied to the moment ("today", a mood)
                "passing": _passing(nd),
                "mentions": nd["n_mentions"], "status": status,
                # W1: set at write time by currency.mark_current. Exposed so
                # every consumer sees one verdict instead of re-deriving it.
                "current": nd.get("current", True),
                "superseded_by": nd.get("superseded_by"),
                "supersedes": list(nd.get("supersedes") or []),
                "receipts": [{"date": d, "conversation":
                              self.titles.get(c, c)[:60],
                              "conversation_id": c} for c, d in recs[:3]]}

    # ---------------- injection ----------------

    def context_block(self, query=None, max_facts=15):
        """Verbatim receipted block for prompt injection. If `query` is given,
        the block is the recall neighbourhood; else the top-of-profile. Empty
        memory -> an explicit do-not-invent block, never silence.

        e261: THE NO-QUERY PATH USED TO RENDER CORROBORATED FACTS ONLY. On a
        real store that is almost nothing -- people state a self-fact ONCE, so
        12 of 14 nodes in the e258 dogfood store were single-mention and an
        agent was handed two lines out of fourteen facts. Ledger P2 measured
        the same thing on the benchmark (88% provisional) and read it as a
        store-quality problem; it is also, and more urgently, a RENDERING
        problem, because this block is what an agent actually sees.

        Single-mention facts are now rendered under an explicit UNCONFIRMED
        label, after every corroborated line, within the same budget. That is
        the honest shape: the block never claims corroboration it does not
        have, and the RULES text already told the reader what an UNCONFIRMED
        line means -- it referenced a category this path never emitted.
        """
        lines = []
        if query is None:
            # a remark tied to its moment ("eating keto today") leaves the
            # summary once the moment has passed; recall still finds it
            keep = [f for f in self.profile(top=max_facts * 3)
                    if not _stale_passing(f)][:max_facts]
            keep += [f for f in self.provisional_profile(top=max_facts * 3)
                     if not _stale_passing(f)][:max_facts - len(keep)]
            for f in keep:
                lines.append(f"- {_render_fact(f)}")
            head = "[MEMORY: what the user has told you]"
            if not lines:
                return ("[MEMORY] Nothing is stored about the user yet. Treat "
                        "every detail about them as UNKNOWN: say so rather "
                        "than guessing.\n" + _RULES)
        else:
            r = self._recall_for_context(query)
            head = "[MEMORY: what the user has told you about this]"
            if not r["found"] and r.get("known_about"):
                lines = [f"- {_render_fact(f)}" for f in r["known_about"][:max_facts]]
                return ("[MEMORY] Nothing stored answers this question ("
                        + r["answer"] + "). Related things the user has told "
                        "you:\n" + "\n".join(lines) + "\n" + _RULES)
            if not r["found"]:
                return ("[MEMORY] Nothing stored matches this topic. The user's "
                        "details on this are UNKNOWN: say so rather than "
                        "guessing.\n" + _RULES)
            if r.get("ranked"):
                # v3 path: rank order is the evidence order, so it is kept.
                # The tier still shows on every line.
                for f in r["ranked"][:max_facts]:
                    lines.append(f"- {_render_fact(f)}")
            else:
                for f in r["asserted"][:max_facts]:
                    lines.append(f"- {_render_fact(f)}")
                for w in r["wired"][:max_facts - len(lines)]:
                    f = w["fact"]
                    lines.append(f"- (linked) {_render_fact(f)}")
                for f in r["unconfirmed"][:max(0, max_facts - len(lines))]:
                    lines.append(f"- {_render_fact(f)}")
        block = head + "\n" + "\n".join(lines)
        cf = [c for c in self.conflicts()
              if query is None or any(t in c["attribute"]
                                      for t in str(query).lower().split())]
        if cf:
            block += ("\n[MEMORY CONFLICTS -- unresolved; if one becomes "
                      "relevant, ASK the user instead of picking:]")
            for c in cf[:3]:
                block += f"\n- {c['ask']}"
        return block + "\n" + _RULES

    def _recall_for_context(self, query):
        """Same retriever the product's recall uses, so the injected block and
        an explicit profile_recall never disagree about what is stored."""
        # e277: v3 is the DEFAULT here too, so the injected context block and
        # an explicit profile_recall cannot disagree about which retriever ran.
        if os.environ.get("RG_PROFILE_V3") == "0":
            return self.recall(query)
        try:
            return self.recall_v3(query)
        except Exception:
            return self.recall(query)

    def provisional_profile(self, top=40):
        """Single-mention facts, most-evidenced first. Receipted, and NEVER
        merged into `profile()` -- a caller that asks for the corroborated
        profile must keep getting exactly that."""
        if top <= 0:
            return []
        nodes = sorted((d for d in self.g.provisional.values()
                        if self._visible(d)),
                       key=lambda d: (d.get("current") is False,
                                      -d["n_mentions"]))
        return [self._fact(nd, provisional=True) for nd in nodes[:top]]
