"""The CHECK layer over parser candidates. Deterministic first, model last.

JP's architecture: grammar extracts, the model only checks or fixes. That
makes the checker two stages, not one, and the order matters -- every
candidate the free stage kills is a model call not spent.

  STAGE 1  deterministic, no model:
      GROUNDED      every content word must trace to the source turn. This is
                    an EXTRACTIVE system, so a word that is not in the turn
                    was invented -- and that is the evidence-layer claim
                    stated as a filter rather than a slogan.
      WELLFORMED    morphology the parser is known to get wrong ("ises
                    looking", "has reflecting"), first-person residue where
                    the person shift failed, degenerate self-reference.
      SUBSTANTIVE   a proposition has to assert something: a bare subject, a
                    one-word tail or a pure discourse marker is not a memory.
  STAGE 2  model entailment: does the turn SUPPORT this proposition. One
      yes/no per surviving candidate, no generation. MiniCheck-class verifiers
      at 770M match GPT-4-turbo at ~400x lower cost, so this is the cheap half
      of the system, not the expensive one.
      NOT WIRED IN (e249). `verify()` below is implemented but nothing in the
      shipped path calls it -- Extractor.extract_turn runs `prefilter` and
      `quality` only, and every number in the ledger is STAGE 1 alone. Read
      this section as the design, not as what runs.

Why the order is not arbitrary: the parser emits 2.57 records per gold point
against gold's ~1.0, so most candidates are surplus. Paying a model to read
all of them would put the cost back exactly where this architecture removes
it.
"""
import re

STOP = set("the a an is are was were be been being of to in on at for and or "
           "with his her their its it he she they him them as by from that "
           "this what which who i my me we our us you your not no do does "
           "did have has had will would can could should may might "
           "must".split())
# "him"/"them" were missing here (only "his"/"her"/"their"/"its" -- the
# POSSESSIVE forms, already needed elsewhere). `owner_pronoun` (Extractor)
# can introduce either as the OBJECT-position pronoun ("his" -> "him",
# "their" -> "them"), a token the source turn never contained -- ungrounded
# by construction. Without this, a short proposition whose only remaining
# content after pronominalising was the introduced pronoun ("Martin Mark's
# name is them") failed the grounding check and was silently DROPPED, not
# just reworded.

_BAD_MORPH = re.compile(r"\b\w+ises\b|\bhas \w+ing\b|\bises\b|\b(?:is|has) "
                        r"(?:is|has|was)\b", re.I)
_FIRST_RESIDUE = re.compile(r"\b(?:I|my|me|mine|myself|we|us|our)\b")
_GOLD_TEMPLATE_VAL = re.compile(r"\bI\s+(?:like|dislike)\s*:?\s*(.+)$", re.I)
_GOLD_TEMPLATE = re.compile(r"\b[A-Z][\w ]{2,20}\s+I\s+(?:like|dislike)\b")
_DISCOURSE = {"absolutely", "of course", "sure", "okay", "ok", "yes", "no",
              "hello", "hi", "thanks", "thank you", "well", "so", "actually"}


def _content(s):
    """Content words, with possessives normalised.

    The possessive matters: the parser writes "Martin Mark's major", whose
    tokens are {martin, mark's}, while the owner strip-list holds {martin,
    mark}. Leaving "'s" attached made the owner's own surname read as
    ungrounded invented content and killed four of the five best propositions
    in the store -- including "User's name is Martin Mark", which is verbatim
    gold."""
    out = []
    for w in re.findall(r"[a-z0-9']+", str(s).lower()):
        w = w.rstrip("'").removesuffix("'s")
        # a number is content at any length: "I'm 34" is the whole fact
        if w and w not in STOP and (len(w) > 2 or w.isdigit()):
            out.append(w)
    return out


def _short_source(s):
    """Short source tokens (2 chars) that `_content` excludes. Source side
    only -- these are never treated as record content."""
    return [w for w in re.findall(r"[a-z]+", str(s).lower())
            if len(w) == 2 and w not in STOP]


def _stems(words):
    """Crude stemming so inflected forms match their source ("lives"/"live")."""
    out = set()
    for w in words:
        out.add(w)
        for suf in ("ing", "ed", "es", "s", "ly"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                out.add(w[:-len(suf)])
        if w.endswith("ies"):
            out.add(w[:-3] + "y")
    return out


# e262: DEICTIC-EMPTY VALUES. "I like it a lot actually" stores "<owner> likes
# it a lot actually" -- a fact whose complement is an unresolved referent. It
# is not merely useless: it competes for retrieval rank against real facts,
# and it invites a reader to supply the missing referent themselves, which is
# the one failure this system exists to prevent (ledger 5l: a store that ships
# the negation of a fact is worse than one that ships nothing; an unresolvable
# referent is the same argument).
#
# Cross-turn resolution is the better answer and is NOT attempted here -- a
# wrong antecedent produces a confident false memory, the worst possible
# outcome for an evidence layer. Rejecting is the honest floor, and the
# disposition is logged so a future coref effort has a measured target.
#
# Measured: 16.67% of a real conversational store, 0.71% of the HaluMem u0
# corpus. The 23x gap is the e259 pattern again -- natural speech is full of
# deixis and the benchmark's prose is not.
_DEICTIC = frozenset("""
it its this that these those them they there then here one ones
""".split())

# Words that cannot carry the content of a fact on their own.
_VALUE_FILLER = _DEICTIC | frozenset("""
a an the of to in on at for with and or but not no very much lot lots
actually really quite too also now still just so more most well
""".split())


def _deictic_empty(value):
    """True when a value's only content is an unresolved referent."""
    v = str(value or "").lower()
    toks = re.findall(r"[a-z']+", v)
    if not toks:
        return False
    if not any(t in _DEICTIC for t in toks):
        return False
    return not [t for t in toks if t not in _VALUE_FILLER]


_STRANDED = re.compile(r"\b(on|in|at|to|with|for|about|from|of|by|into|"
                       r"onto|after|over|under|through)\s*[.!?]?$", re.I)


def prefilter(prop, turn, owner=None, min_grounded=0.85, min_content=1,
              value=None, kind=None):
    """-> (keep: bool, reason: str). No model call.

    `value` and `kind` are the record's complement and type when the caller
    has them (rgx.Extractor does). Supplied, they enable the deictic-empty
    check above; omitted, behaviour is exactly as before.

    RELATIONSHIP records are EXEMPT, and measuring is what found that: a
    relationship's content is its PARTICIPANTS, not its complement. "<owner>'s
    manager Priya suggested it" has a deictic-empty value and is the only
    record in its store carrying the manager relation. Rejecting it cost more
    than every empty record it removed was worth -- rank-1 7/10 -> 6/10,
    pool 9/10 -> 7/10 on the dogfood set."""
    text = str(prop).strip()
    if not text:
        return False, "empty"
    if (value is not None and kind != "relationship"
            and _deictic_empty(value)):
        return False, "deictic-empty value (unresolved referent)"
    # 2026-10-02 (seen in the first rendered MEMORY.md): a relative clause
    # whose object was extracted leaves the verb with a stranded preposition
    # -- "The ward I work on has 30 beds" also yielded "<owner> works on".
    # A record ending in a bare preposition says nothing.
    if _STRANDED.search(text):
        return False, "stranded preposition (object was extracted)"

    # "user" is a subject token too -- gold writes the name point as "User's
    # name is X", and counting "user" as content made it ungrounded.
    own = set(_content(owner or "")) | {"user"}
    pc = [w for w in _content(text) if w not in own]
    if len(pc) < min_content:
        # one content word can be the whole fact -- "Male", "Bachelor" --
        # and requiring two dropped "Martin Mark is a Male" against gold
        # "Martin Mark's gender is Male".
        return False, "not substantive (no content beyond the subject)"
    if text.lower().strip(" .") in _DISCOURSE:
        return False, "discourse marker"

    if _BAD_MORPH.search(text):
        return False, "malformed morphology"
    # Gold's own preference template CONTAINS the first person -- "Martin Mark
    # Sports I dislike: Automobile racing". The residue check exists to catch a
    # FAILED person shift, not to ban the pronoun, and without this exemption it
    # silently dropped 28 of the template records the moment they were added.
    if not _GOLD_TEMPLATE.search(text) and _FIRST_RESIDUE.search(text):
        return False, "first-person residue (person shift incomplete)"
    if owner and re.search(rf"{re.escape(owner)}'s .* is {re.escape(owner)}'s",
                           text, re.I):
        return False, "degenerate self-reference"

    # GROUND THE VALUE, NOT THE SLOT NAME.
    #
    # A slot name is a LABEL we supply from our own schema; a value is CONTENT
    # that must come from the source. Gold calls it "birth date" where the
    # speaker said "born on", and "parent status" where they said "Both
    # parents are alive" -- so grounding the whole string rejects exactly the
    # canonical naming the lexicon exists to add, which is what happened: every
    # lexicon proposition was dropped as "ungrounded (birth, date)".
    #
    # The evidence-layer claim is that we never invent CONTENT. It was never
    # that we may only use the speaker's own words for our field names.
    body = text
    m = re.search(r"'s .{0,40}? (?:is|are|include[s]?)\s+(.*)$", text)
    if not m:
        m = re.search(r"'s .{0,40}?:\s*(.*)$", text)
    if not m:
        # the preference template: "<Owner> <Category> I dislike: <value>".
        # The CATEGORY is a label we supply, exactly like a slot name -- it is
        # not in the source and must not be grounded, or every template record
        # is rejected as "ungrounded (sports)".
        m = _GOLD_TEMPLATE_VAL.search(text)
    if m:
        body = m.group(1)
    vc = [w for w in _content(body) if w not in own] or pc

    # e276: `_content` drops tokens of 2 characters or fewer, which is right
    # for deciding what in the RECORD counts as content to check -- but wrong
    # for the SOURCE side, which should represent everything the speaker
    # actually said. "go", "do", "be" were invisible, so the person shift's
    # "goes"/"does" read as invented content and the record was dropped.
    # The length filter belongs on the candidate, not on the evidence.
    src = _stems(_content(turn) + _short_source(turn))
    # e276: `_stems` refuses to strip a suffix that would leave fewer than 3
    # characters, so "goes" never reduced to "go" and a correctly person-
    # shifted verb was rejected as INVENTED CONTENT -- "Even if it is raining,
    # I always go for a run" produced nothing at all, blamed on the
    # conditional rule until the filter was checked.
    #
    # Stripped from the CANDIDATE, not added to the source: growing `src`
    # makes grounding more permissive, which is the wrong direction for a
    # filter whose job is to catch invented content.
    def _ok(w):
        if w in src or w[:-1] in src or (w + "s") in src:
            return True
        return w.endswith("es") and w[:-2] in src

    ungrounded = [w for w in vc if not _ok(w)]
    pc = vc
    frac = 1.0 - (len(ungrounded) / max(1, len(pc)))
    if frac < min_grounded:
        return False, f"ungrounded ({', '.join(ungrounded[:4])})"
    return True, "kept"


VERIFY_PROMPT = (
    "Does the MESSAGE support the STATEMENT?\n\n"
    "MESSAGE:\n{turn}\n\nSTATEMENT:\n{prop}\n\n"
    "Answer with one word, YES or NO. Answer NO if the statement adds any "
    "detail the message does not state, or misattributes something."
)


def verify(prop, turn, ask):
    """Model entailment. `ask(prompt) -> str`. One yes/no, never generation."""
    out = ask(VERIFY_PROMPT.format(turn=str(turn)[:1500], prop=prop))
    return str(out).strip().upper().startswith("Y")


def quality(prop, turn, owner=None):
    """A deterministic 0-1 score for RANKING records when pruning.

    CAUTION (e249): the original rationale here cited e229's "crowding"
    mechanism -- the integrity judge reads a session's emissions as one blob,
    so surplus records crowd out matches. That mechanism is RETRACTED (e230,
    ledger 5k): capping to 25 records/session cut 67% of records and cost
    12.15pt of recall. If crowding were real, pruning would have helped; it
    did the opposite. Over-emission does not cost precision either
    (`target_accuracy` scores each record alone).

    So this score is NOT a justification for pruning, and nothing in the
    shipped path prunes on it. It survives as a cheap deterministic ORDERING
    for callers that need one (display, tie-breaks, triage). Do not
    reintroduce a cap on the strength of the retracted mechanism.

    Three signals, all cheap and all defensible:
      grounded   what fraction of the record's value words are in the source.
                 An extractive record that is fully grounded is the kind we
                 most want to keep.
      brevity    gold points are short (median ~10 content tokens). A very long
                 record is usually a swallowed clause, and it also eats more of
                 the judge's attention than a short one.
      shape      a record with a recognisable slot or relation is closer to
                 gold's form than a bare verb phrase.
    """
    text = str(prop)
    own = set(_content(owner or "")) | {"user"}
    pc = [w for w in _content(text) if w not in own]
    if not pc:
        return 0.0
    src = _stems(_content(turn))
    grounded = sum(1 for w in pc if w in src or w[:-1] in src
                   or (w + "s") in src) / len(pc)
    n = len(pc)
    brevity = 1.0 if n <= 12 else max(0.0, 1.0 - (n - 12) / 24.0)
    shape = 1.0 if re.search(r"'s [\w ]{2,30} (?:is|are)\b|'s (?:Friend|Colleague|"
                             r"Partner|Family|Mother|Father|Brother|Sister)\b",
                             text) else 0.6
    return 0.5 * grounded + 0.3 * brevity + 0.2 * shape
