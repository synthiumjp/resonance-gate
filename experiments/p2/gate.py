"""p2 write-side gate, v1. Three sequential stages, no model call.

Stage 1  WELL-FORMED    is this a coherent (subj, rel, obj) proposition?
Stage 2  MODALITY       does the sentence it came from assert it as true?
Stage 3  TIER           SPAN / PROVISIONAL / PROMOTED

The design decision behind stage 2 is that modality is RECORDED, not filtered.
Every well-formed triple is kept with its modality label; only ACTUAL ones are
eligible for promotion and for firing a contradiction alert. So an intention
stays retrievable as an intention, nothing is discarded, and a gate mistake is
recoverable rather than lossy.

Modality is scoped to the SENTENCE the triple came from, not the whole span.
A span routinely contains both a hedge and a fact ("I think I'll wait. I got a
new lens last week"), so whole-span cue matching would poison every triple in
it.

No LLM call anywhere in here. The extractor already costs one call on the write
path; this adds nothing.

Status: exploratory. Tuned against experiments/p2/split_dev.json only.
split_heldout.json is untouched.
"""

import re

# ---------------------------------------------------------------- stage 1

_BAD_REL = {"the", "a", "an", "none", "and", "to", "on", "or", "of", "by",
            "with", "for", "in", "at", "that", "think", "see", "know", "am",
            "is the topic of the conversation", "none.", "every", "usually"}

_REL_VERB = re.compile(
    r"^(is|are|was|were|has|have|had|works?|lives?|resides?|manages?|reports?|"
    r"studied|born|married|sibling|joined|started|transferred|signed|commutes?|"
    r"prefers?|costs?|tracks?|organi[sz]es?|allows?|helps?|protects?|visited|"
    r"attended|separated|saw|seen|taking|took|owns?|likes?|loves?|uses?|bought|"
    r"got|moved|left|founded|leads?|advises?|chairs?|audits?|employs?|consults?|"
    r"interned|contracts?|belongs?|holds?|runs?|teaches?|coaches?|mentors?|"
    r"supplies|licenses?|partners?|competes?|acquired|banks?|ships?|insures?)\b",
    re.I)

# leading adverbs / negated auxiliaries before the predicate ("just started at",
# "isn't married to"). Stripped before the predicate test so the triple reaches
# stage 2, where NEGATED is RECORDED rather than silently dropped as malformed.
_REL_PREFIX = re.compile(
    r"^((just|recently|already|currently|still|now|also|previously|formerly)\s+|"
    r"(is|are|was|were|does|do|did|has|have|had)n'?t\s+)+", re.I)
_FIRST_PERSON = re.compile(r"^i(\s|'|$)", re.I)

_CLAUSE_SUBJ = re.compile(
    r"\b(i'?ll|i'?ve|i'?m|i'?d|do you|can you|would|should|maybe|suppose|there|it|"
    r"this|that|none|utterance|need advice)\b", re.I)


def wellformed(triple):
    """Is this a coherent proposition at all? Pure surface form."""
    s, r, o = [str(x).strip() for x in triple]
    if not s or not r or not o:
        return False, "empty field"
    if o.lower() in ("none", "") or s.lower() in ("none", "", "utterance"):
        return False, "null field"
    if r.lower() in _BAD_REL:
        return False, "relation is not a relation"
    if len(r.split()) > 4:
        return False, "relation is a clause"
    if len(s.split()) > 6:
        return False, "subject is a clause"
    # first-person parse artefacts ("I'm actually", "I've been") normalise to
    # the speaker; tense is stage 2's job, not stage 1's
    if _FIRST_PERSON.match(s) and len(s.split()) <= 3:
        s = "I"
    if _CLAUSE_SUBJ.search(s):
        return False, "subject is not an entity"
    if not _REL_VERB.search(_REL_PREFIX.sub("", r)):
        return False, "relation has no recognised predicate"
    return True, "ok"


# --------------------------------------------------------------- stage 1.5

_STOP = {"the","a","an","of","in","at","to","for","and","or","my","your","his",
         "her","their","our","its","this","that","these","those","is","was",
         "are","were","be","been","new","some","any","one"}


def _content(x):
    return {t for t in re.findall(r"\w+", str(x).lower())
            if len(t) > 2 and t not in _STOP}


_ROLE_QUAL = re.compile(r"\s*\([^)]*\)\s*$")
_FIRST = re.compile(r"^\s*(i|we|my|our|me|myself)\b", re.I)


def subject_contiguous(span, triple):
    """A non-first-person subject must occur as a contiguous phrase in the span
    (role qualifier stripped), else it is a fabricated nominalisation the
    extractor assembled from scattered span tokens. First-person subjects are
    exempt (never literal). Returns (ok, reason)."""
    s = str(triple[0]).strip()
    if _FIRST.match(s):
        return True, "first-person subject"
    core = _ROLE_QUAL.sub("", s).strip().lower()
    if not core:
        return False, "empty subject"
    sp = re.sub(r"\s+", " ", str(span).lower())
    if re.sub(r"\s+", " ", core) in sp:
        return True, "contiguous"
    return False, f"fabricated subject: {core!r} not contiguous in span"


def grounded(span, triple):
    """Do the subject and object actually occur in the source span?

    This is what catches FEW-SHOT LEAKAGE: the extractor regurgitating its own
    prompt examples as facts about the user ((Dana | works at | Orion Foods)
    emitted from a span about dairy farming). Those triples are perfectly
    well-formed and carry no modality cue, so neither stage 1 nor stage 2 can
    see them -- but their arguments appear nowhere in the text. Cheap, lexical,
    no model call.

    First person is grounded by any first-person marker in the span, since "I"
    is rarely a literal token match for the speaker's own reference.
    """
    low = span.lower()
    for field in (triple[0], triple[2]):
        f = str(field).strip()
        if _FIRST_PERSON.match(f) and re.search(r"\b(i|i'?m|i'?ve|my|me|mine)\b", low):
            continue
        toks = _content(f)
        if not toks:
            continue                      # nothing checkable; defer to other stages
        if not (toks & _content(span)):
            return False, f"ungrounded: '{f}' does not occur in the span"
    return True, "ok"


# ---------------------------------------------------------------- stage 2

_CUES = [
    ("QUESTION",   re.compile(r"\?\s*$|^\s*(do|does|did|is|are|was|were|can|could|"
                              r"would|should|will|what|where|who|whom|when|how|why)\b", re.I)),
    ("NEGATED",    re.compile(r"\b(don'?t|doesn'?t|didn'?t|isn'?t|aren'?t|wasn'?t|"
                              r"weren'?t|won'?t|never|no longer|not\b|any ?more)\b", re.I)),
    ("CONDITIONAL", re.compile(r"\b(if|suppose|supposing|unless|in case|were i|"
                               r"would (?:need|have|be))\b", re.I)),
    ("ATTRIBUTED", re.compile(r"\b(says|said|according to|i heard|i'?ve heard|"
                              r"told me|apparently|supposedly)\b", re.I)),
    ("FUTURE",     re.compile(r"\b(thinking of|think i'?ll|planning to|plan to|"
                              r"going to|hoping to|hope to|considering|i'?ll\b|"
                              r"want to|wanted to|intend|about to|soon|next (?:year|month|week))\b", re.I)),
    ("HEDGED",     re.compile(r"\b(i think|i guess|i believe|might|maybe|perhaps|"
                              r"probably|possibly|not sure|i'?d say|seems?|"
                              r"i'?m not certain|can'?t remember)\b", re.I)),
    ("PAST_ONLY",  re.compile(r"\b(used to|back then|at the time|until the|"
                              r"before the|formerly|previously)\b", re.I)),
]

_SENT = re.compile(r"(?<=[.!?])\s+")


def _locate_sentence(span, triple):
    """The sentence the triple most likely came from: best token overlap with
    the object, then the subject. Whole-span cue matching would poison every
    triple in a span that contains one hedge."""
    sents = [s for s in _SENT.split(span) if s.strip()]
    if len(sents) <= 1:
        return span
    def toks(x):
        return {t for t in re.findall(r"\w+", str(x).lower()) if len(t) > 2}
    # numeric objects ("27:12", "4", "$350,000") tokenise to short/no word
    # tokens and would leave `want` empty -> whole-span fallback -> spurious
    # modality from an unrelated sentence. Match their digit literals instead.
    nums = set(re.findall(r"\d[\d,:.]*", str(triple[2])))
    want = toks(triple[2]) | toks(triple[0]) | nums
    if not want:
        return span
    def sent_has(sent):
        low = sent.lower()
        return len(toks(triple[2]) & toks(sent)) + len(toks(triple[0]) & toks(sent)) \
               + sum(1 for n in nums if n in sent)
    best, score = span, -1
    for sent in sents:
        v = sent_has(sent)
        if v > score:
            best, score = sent, v
    return best


def modality(span, triple):
    """ACTUAL, or the first non-actual cue that fires in the source sentence.
    Recorded, not used to discard."""
    sent = _locate_sentence(span, triple)
    rel_and_sent = f"{triple[1]} {sent}"
    # a sentence that supersedes within itself ("... until the reorg, NOW she
    # reports to him") asserts the post-state; the past cue belongs to the
    # subordinate clause, not to the triple
    supersedes_to_present = re.search(r"\bnow\b|\bcurrently\b|\bthese days\b",
                                      sent, re.I)
    for name, rx in _CUES:
        if name == "PAST_ONLY" and supersedes_to_present:
            continue
        if rx.search(sent if name == "QUESTION" else rel_and_sent):
            return name, sent
    return "ACTUAL", sent


# ---------------------------------------------------------------- stage 3

SPAN, PROVISIONAL, PROMOTED = "SPAN", "PROVISIONAL", "PROMOTED"


def assess(span, triple, corroborations=0):
    """Full gate. Returns dict with tier, modality and why.

    SPAN        not well-formed -- the raw text is kept, the triple is not
                stored as a triple at all.
    PROVISIONAL well-formed but either non-ACTUAL modality, or ACTUAL and not
                yet corroborated. Retrievable. MAY NOT fire a contradiction
                alert.
    PROMOTED    well-formed, ACTUAL, and independently restated at least once.
                Assertable.
    """
    ok, why = wellformed(triple)
    if not ok:
        return {"tier": SPAN, "modality": None, "wellformed": False, "why": why}
    ok_g, why_g = grounded(span, triple)
    if not ok_g:
        return {"tier": SPAN, "modality": None, "wellformed": True,
                "grounded": False, "why": why_g}
    ok_c, why_c = subject_contiguous(span, triple)
    if not ok_c:
        return {"tier": SPAN, "modality": None, "wellformed": True,
                "grounded": True, "structural": False, "why": why_c}
    mod, sent = modality(span, triple)
    if mod != "ACTUAL":
        return {"tier": PROVISIONAL, "modality": mod, "wellformed": True,
                "why": f"modality={mod}", "sentence": sent}
    tier = PROMOTED if corroborations >= 1 else PROVISIONAL
    return {"tier": tier, "modality": "ACTUAL", "wellformed": True,
            "why": "actual, corroborated" if corroborations else "actual, uncorroborated",
            "sentence": sent}
