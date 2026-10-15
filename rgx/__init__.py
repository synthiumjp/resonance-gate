"""rgx -- deterministic memory extraction from dialogue. No LLM required.

Extracts durable facts from a conversation using a dependency parse and a
person-shift transformation. Every record carries the turn it came from, so
nothing in the store is unattributable.

    from rgx import extract

    records = extract(dialogue, owner="Martin Mark")
    for r in records:
        print(r.text, "<-", r.role, "turn", r.turn)

Measured against HaluMem-Medium on held-out users, judged by the benchmark's
own harness, on HaluMem's OFFICIAL recall definition (non-interference gold
only): u0 F1 0.6544 / u1 0.5647, against a prompted 14B's 0.3860 / 0.3477,
with zero model calls at extraction time. (Earlier drafts of this docstring
quoted R 0.4609 vs 0.2122; those counted interference points, which the
official definition excludes -- corrected in e240, see the handover.) Numbers, method and the
things that did NOT work are in docs/EXPERIMENT_LEDGER.md -- including six
instrument defects found along the way, five of which flattered the results.

Design commitments, in order of how much they cost to keep:

  NEVER INVENT CONTENT.  Every content word in a record must trace to the
      source turn. A slot NAME may come from our schema; a VALUE may not.
      Enforced as a THRESHOLD, not an absolute: check.prefilter defaults to
      min_grounded=0.85, so a value of seven content words tolerates one
      ungrounded token and two fail it. Tighten that default before quoting
      this line as a guarantee.
  NEVER INVERT A FACT.   Negation is preserved. "I don't like boxing" is not
      stored as "does like boxing" -- a defect that shipped here for a while
      and is invisible to token-overlap metrics, because the inverted sentence
      shares every content word with the true one.
  ALWAYS CARRY A RECEIPT. Session, turn index and role on every record.
  NO MODEL AT EXTRACTION TIME. A model may CHECK or REPAIR later; it does not
      write the memory.
"""
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence
from .normalize import normalize

__all__ = ["Record", "Extractor", "extract"]
__version__ = "0.1.0"


# Review 2026-10-02: "I got fired. Not really, it's a joke." -- the next
# sentence takes the previous one back.
_RETRACT = re.compile(r"^\W*(not really|just kidding|only kidding|kidding|jk\b|"
                      r"joking|i'?m joking|lol,? no|haha,? no|not true)", re.I)


def _retracted(text, sentence):
    i = text.find(sentence)
    if i < 0:
        return False
    return bool(_RETRACT.match(text[i + len(sentence):].lstrip()))


@dataclass(frozen=True)
class Record:
    """One extracted memory, with its provenance."""
    text: str
    kind: str                      # attr | event | relationship
    session: int
    turn: int
    role: str
    quality: float = 0.0           # 0-1: grounding, brevity, shape
    subject: Optional[str] = None
    predicate: Optional[str] = None  # attribute key: head lemma (+case) / slot
    value: Optional[str] = None      # what sits under that key
    evidential: Optional[str] = None  # "report" (e242): hearsay, not assertion
    source: Optional[str] = None      # the sentence it was read from, verbatim

    def __str__(self):
        return self.text


# 2026-10-09 (adversarial review): a hedge or report frame left its
# complement behind as a plain fact: "I guess I live in Leeds now" stored
# "lives in Leeds now" beside "guesses ... lives in Leeds now"; so did "I
# heard I'm getting promoted", "I'm told I work in Finance", "I said I work
# at Google as a joke". The frame is kept (it is what was said); the bare
# complement is not. A sentence opened by a hedge ("allegedly", "let's say",
# "yeah right, like ...") stores nothing.
# "I think" / "I believe" mostly state the user's own view ("I think I'll go
# with pnpm") and keep their complement; "used to think" does not.
_FRAME_PREDS = {"guess", "suppose", "reckon", "hear", "tell",
                "say", "claim", "imagine", "assume", "suspect", "doubt", "wonder",
                "hope", "wish", "pretend", "joke", "dream", "bet", "figure",
                "fear", "worry", "joke", "lie", "rumour", "rumor"}
_HEDGE_OPEN = re.compile(
    r"^\W*(?:allegedly|supposedly|apparently|reportedly|hypothetically|in theory|"
    # not "like I": "Like I said, I live in Leeds" is the user's own
    r"let'?s say|say|suppose|imagine|pretend|yeah right|as if)\b", re.I)


# "Never again will I use that vendor" kept "will use that vendor": a fronted
# negative with the auxiliary before the subject negates the clause
_NEG_INVERSION = re.compile(
    r"^\W*(?:never(?: again| ever)?|not once|at no time|under no circumstances|"
    r"in no way|no way|nowhere|seldom|rarely|hardly ever)\b,?\s+(?:will|would|do|does|"
    r"did|have|has|had|can|could|shall|should|am|is|are|was|were)\s+(?:i|we)\b", re.I)
# "Explain it like I'm five" stored "is five"
_LIKE_I = re.compile(r"\b(?:like|as if|as though)\s+(?:i'm|i am|i was|i were)\s+(\w+)", re.I)


def _drop_framed(records):
    frames = [r for r in records
              if any(t in _FRAME_PREDS for t in (r.predicate or "").split("_"))
              or re.search(r"\b(?:used to think|used to believe|told|tells|says|said)\b",
                           r.text or "")]
    framed = {(r.value or "").strip().lower() for r in frames if r.value}
    keep = []
    for r in records:
        t = (r.text or "").strip().lower()
        if r not in frames and (t in framed or any(
                t and t != (f.text or "").strip().lower()
                and t.split(" ", 2)[-1] in (f.text or "").lower() for f in frames)):
            continue
        if r.source and (_HEDGE_OPEN.match(r.source) or _NEG_INVERSION.match(r.source)):
            continue
        m = _LIKE_I.search(r.source or "")
        if m and t.endswith(" " + m.group(1).lower()):
            continue
        keep.append(r)
    return keep


# 2026-10-14 (JP's first real Claude Code session; dev set
# cases_dev_worksession): a work chat is full of sentences that are not facts
# about the person. The summary said "<user> dies quickly" ("if we don't
# have it perfect we die quickly"), "<user> is competing against ..." ("we",
# the team), "<user> is going to bed", "<user> needs you to keep
# progressing overnight", and "the reader often says <user> does not know"
# (an "I" inside a quotation).
_QUOTED = re.compile(r"[\"“]([^\"”]{2,300})[\"”]")
_Q_FIRST = re.compile(r"\b(?:i|i'm|i’m|i've|i'd|i'll|me|my|mine|we|we're|our|us)\b", re.I)
_CONDITIONAL = re.compile(
    r"\b(?:if|unless|in case|what if|whether|otherwise|maybe|perhaps|should i|"
    # a worry only with what it is about ("concerned if we ...", "afraid
    # that ..."); "I was very anxious during college" is a fact
    r"(?:concerned|worried|afraid|scared|nervous|anxious)\s+(?:that|if|about|we|i)\b)", re.I)
_I_FORMS = re.compile(r"\b(?:i|i'm|i’m|i've|i’ve|i'd|i’d|i'll|i’ll|me|my|mine|myself)\b", re.I)
_WE_FORMS = re.compile(r"\b(?:we|we're|we’re|we've|we’ve|we'd|we'll|us|our|ours)\b", re.I)
# what "we" shares with a partner or family: where they live, moving,
# marriage, children, pets, a home
_HOUSEHOLD = re.compile(
    r"\b(?:live[sd]?|living|move[sd]?|moving|relocat\w*|married|marry|marries|engaged|divorc\w*|"
    r"wedding|kids?|children|child|baby|babies|son|daughter|twins|dog|cat|pets?|puppy|kitten|"
    r"house|flat|apartment|home|bought|buy|rent\w*|mortgage|garden)\b", re.I)
# ... or something "we" did, in the past: a family's picnic, a trip
# ("we had a picnic last week", "we both helped with the painting"); a work
# chat's "we" is mostly present or future ("we need", "we are competing")
_WE_EVENT = re.compile(
    r"\bwe\s+(?:\w+ly\s+|both\s+|all\s+|even\s+|just\s+|finally\s+)?(?:went|had|visited|took|made|saw|did|"
    r"got|found|helped|painted|bought|watched|played|tried|started|finished|celebrated|spent|ate|"
    r"cooked|baked|walked|hiked|drove|flew|met|stayed|camped|danced|sang|built|planted|adopted|"
    r"travell?ed)\b|\b(?:last (?:week|weekend|month|year|night)|yesterday|ago)\b", re.I)
# ... or a family's plans and outings (LoCoMo dev: "we're thinking about
# going camping next month" was dropped and its question lost); rare in a
# work chat
_LEISURE = re.compile(
    r"\b(?:camping|camp|trip|holiday|vacation|beach|hike|hiking|picnic|concert|party|birthday|"
    r"wedding|anniversary|museum|park|zoo|restaurant|dinner|lunch|brunch|festival|road trip|"
    r"cruise|movie|cinema|game night|barbecue|bbq|christmas|thanksgiving|easter)\b", re.I)
# a fact with a time is an event, even when it is told to "you" ("I wanted
# to tell you about my school event last week")
_WHEN = re.compile(r"\b(?:last (?:week|weekend|month|year|night|time)|yesterday|today|tonight|"
                   r"tomorrow|this (?:week|weekend|month|morning|evening)|next (?:week|weekend|month|year)|"
                   r"ago|on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b", re.I)
# credit, not a request ("taking your advice, I'm sprucing up my biz plan")
_CREDIT = re.compile(r"\b(?:taking|thanks to|with|after|following|because of)\s+your\s+"
                     r"(?:advice|help|support|tips?|suggestions?|ideas?|encouragement)\b", re.I)
_MOMENT = re.compile(
    r"\b(?:going to (?:bed|sleep)|go to (?:bed|sleep)|off to bed|heading (?:off|out|to bed)|"
    r"signing off|logging off|back now|i'?m back|i am back|be right back|brb|afk|"
    r"tired|exhausted|sleepy|knackered|ran out of (?:usage|tokens|credits|context|time)|"
    r"on my phone|hold(?:s|ing)? off|for now|stepping out|step out|for lunch|back in \d+|"
    r"battery|check back)\b", re.I)


_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "for", "is", "are", "was",
         "be", "it", "this", "that", "with", "s", "has", "have", "had", "will", "would"}


def _content(words_text, owner):
    o = {w.lower() for w in re.findall(r"[A-Za-z]+", owner or "")}
    return [w for w in re.findall(r"[a-z0-9]+", (words_text or "").lower())
            if w not in _STOP and w not in o and len(w) > 2]


def _after_marker(src, text, owner, rx):
    """Most of the fact's own words come after a condition or worry marker
    and few before it: the fact sits inside that clause."""
    m = rx.search(src)
    if not m:
        return False
    words = _content(text, owner)
    if not words:
        return False
    before, after = src[:m.start()].lower(), src[m.end():].lower()
    # a condition opening the sentence ends at its comma: "Even if it is
    # raining, I always go for a run" asserts the run
    if not re.sub(r"\W|even", "", before) and "," in after:
        cut = after.index(",")
        before, after = before + after[cut:], after[:cut]
    n_after = sum(1 for w in words if re.search(rf"\b{re.escape(w)}", after))
    n_before = sum(1 for w in words if re.search(rf"\b{re.escape(w)}", before))
    return n_after >= max(1, (len(words) + 1) // 2) and n_after > n_before


def _work_filters(records, role, owner=None):
    """Records a user's turn should not yield (see the comment above).
    RGX_WORK_FILTERS=0 turns them off."""
    if os.environ.get("RGX_WORK_FILTERS") == "0" or role != "user":
        return records
    # "you" is the assistant and "we" mostly the user's team only in a chat
    # WITH an assistant; between two people (LoCoMo) "you" is the friend and
    # "we" often the family (LoCoMo dev: 160 -> 156 of 233 with these rules
    # on). The product's entry points set RGX_ASSISTANT_CHAT=1.
    assistant_chat = os.environ.get("RGX_ASSISTANT_CHAT") == "1"
    keep = []
    for r in records:
        src = r.source or ""
        text = r.text or ""
        val = (r.value or "").lower()
        # a moment, not a lasting fact, an instruction included ("on my
        # phone so keep it short")
        if _MOMENT.search(src):
            continue
        if r.predicate != "instruction":
            # still addressed to the assistant: a request, not a fact
            if (assistant_chat and re.search(r"\byou(?:r|rs|rself)?\b", _CREDIT.sub("", text), re.I)
                    and not _WHEN.search(text)):
                continue
            # an "I" or "we" inside a quotation is the quoted speaker's
            # (the quote's own words in the fact: "the reader often says "I
            # don't know"" stored "the reader often says <owner> does not know")
            if any(_Q_FIRST.search(q) and ((val and val in q.lower())
                                           or set(_content(q, owner)) & set(_content(text, owner)))
                   for q in _QUOTED.findall(src)):
                continue
            # inside a condition, a musing or a worry
            if _after_marker(src, text, owner, _CONDITIONAL):
                continue
            # "we" with no "I": the team, unless it is a household fact
            if (assistant_chat and _WE_FORMS.search(src) and not _I_FORMS.search(src)
                    and not _HOUSEHOLD.search(text)
                    and not _WE_EVENT.search(src) and not _LEISURE.search(src)):
                continue
            # the introduction to a paste ("my friend sent me this")
            if re.search(r"\b(?:sent|forwarded|shared|pasted|got|wrote)\b.*\b(?:this|that|these|the following)\W*$",
                         text, re.I):
                continue
        keep.append(r)
    return keep


@dataclass
class Extractor:
    """Deterministic extractor. Loads a parser once and reuses it.

    owner_name: the profile owner. The extractor never has the model produce a
        name -- records are written in the third person and the owner's name is
        substituted here, so a name it has never seen cannot be invented.
    check: apply the deterministic filters (grounding, well-formedness). Off
        only for debugging what the parser produced before filtering.
    owner_pronoun: default None -- COMPLETELY UNCHANGED behaviour, the
        owner's full name every mention. Set to "his"/"her"/"their" (etc.)
        to collapse repeated owner mentions within one proposition down to
        a pronoun after the first (render_defects: repeated_owner_
        possessive/repeated_owner_name -- 29% of every u0 record). NEVER
        inferred from `owner_name`: a caller that wants pronominalisation
        without knowing the owner's gender should pass "their" explicitly
        (tools/build_rgx_cache.py's --owner-pronoun does this when given
        with no value), not leave this to guess from the name.
    owner_pronoun_obj: the matching object-position pronoun ("him"/"her"/
        "them"). Derived from `owner_pronoun` when left None.
    """
    owner_name: Optional[str] = None
    check: bool = True
    owner_pronoun: Optional[str] = None
    owner_pronoun_obj: Optional[str] = None
    _nlp: object = field(default=None, repr=False)
    # e269: entities the owner has linked themselves to, carried ACROSS turns
    # so "I work on the billing service" in turn 3 lets "The billing service
    # is written in Go" in turn 9 be stored. Per-Extractor, and an Extractor
    # is per-owner; call reset_world() to process a different person.
    _world: dict = field(default_factory=dict, repr=False)

    def prefetch(self, texts, batch=64):
        """Parse many texts in batches ahead of extract_turn (2026-10-05).
        Stanza run one message at a time spends its time on tiny LSTM calls
        (0.25 s a message); 64 at a time is 0.04 s a message, and the parses
        are the same (300/300 LoCoMo messages, every field). extract_turn
        uses a prefetched parse when it is asked for exactly that text and
        parses anything else as before. The previous batch is dropped."""
        parser = self._parser()
        parser.cache = {}
        Document = parser.Document
        todo = [t for t in dict.fromkeys(texts) if t and t.strip()]
        for i in range(0, len(todo), batch):
            chunk = todo[i:i + batch]
            for t, d in zip(chunk, parser.nlp.bulk_process(
                    [Document([], text=t) for t in chunk])):
                parser.cache[t] = normalize(d)

    def _parser(self):
        if self._nlp is None:
            models = ort_models_dir()
            if models:
                # 2026-10-05: stanza_ort, the same Stanza 1.14.0 English
                # models run on ONNX Runtime without PyTorch (identical
                # parses on 7,755 texts, every field; tools/stanza_ort)
                import stanza_ort
                self._nlp = _CachedParser(stanza_ort.Pipeline(models),
                                          stanza_ort.Document)
                return self._nlp
            try:
                import stanza
            except ImportError as e:
                raise RuntimeError(
                    "The English parser is not installed. Run "
                    "`sourcedrecall-setup` once (it downloads the parser "
                    "models), or install Stanza: pip install stanza==1.14.0") from e
            # 2026-10-02: REUSE_RESOURCES -- never touch the network at
            # runtime. Stanza's default re-fetches resources.json on every
            # Pipeline() (a network call per server start) and downloads
            # missing models silently; a memory server that promises nothing
            # leaves the machine cannot do either. Models are installed once
            # by `sourcedrecall-setup`.
            try:
                self._nlp = _CachedParser(stanza.Pipeline(
                    "en", processors="tokenize,pos,lemma,depparse",
                    use_gpu=False, verbose=False,
                    download_method=stanza.DownloadMethod.REUSE_RESOURCES),
                    stanza.Document)
            except Exception as e:
                raise RuntimeError(
                    "The English parser models are not installed. Run "
                    "`sourcedrecall-setup` once (or, without the server: "
                    "python -c \"import stanza; stanza.download('en', "
                    "processors='tokenize,pos,lemma,depparse')\")") from e
        return self._nlp

    def extract_turn(self, text, role="user", session=0, turn=0, prev=None):
        """`prev`: the assistant message just before this turn, if any. It
        decides whether a subjectless fragment opening the turn is about the
        user (see rgx.fragments)."""
        from . import check as C
        from . import parse as G
        from . import fragments as F
        # 2026-10-14: the tags a client wraps around pasted text are not words
        text = re.sub(r"</?pasted_content\b[^>]*>", "\n\n", text or "").strip()
        # a bulleted list is one item per line, not one sentence ("- Keep the
        # handover current\n- Commit at stage boundaries" was one instruction)
        if re.search(r"^[ \t]*[-*•][ \t]+", text, flags=re.M):
            text = re.sub(r"(?<=[A-Za-z0-9)\"”])[ \t]*\n(?=\s*\S)", ".\n", text)
            text = re.sub(r"^[ \t]*[-*•][ \t]+", "", text, flags=re.M)
        orig = {}
        out = []
        if role == "user":
            # 2026-10-06: a proposal the user accepts is the user's decision
            from . import decisions as D
            dec = D.decision(text, prev)
            if dec and self.owner_name:
                val, _src = dec
                out.append(Record(text=f"{self.owner_name} decided with the assistant: {val}",
                                  kind="attr", session=session, turn=turn, role=role,
                                  predicate="decision", value=val, evidential=None,
                                  source=text, quality=1.0))
            text, orig = F.rewrite(text, self._parser(), prev=prev)
        for prop, kind, pred, val, evi, src in G.extract_keyed(
                text, self._parser(), self.owner_name, role=role,
                owner_pronoun=self.owner_pronoun,
                owner_pronoun_obj=self.owner_pronoun_obj,
                world=self._world, with_source=True):
            if self.check:
                # an instruction record's frame ("<owner> asked the
                # assistant:") is ours, not the user's words; the
                # instruction itself is what must be grounded
                ok, _why = C.prefilter(val if pred == "instruction" else prop,
                                       text, self.owner_name,
                                       value=val, kind=kind)
                if not ok:
                    continue
                # 2026-10-02: an assistant's report FRAME is not a fact --
                # "I remember you mentioning you play the cello" yielded both
                # "<owner> plays the cello" (the claim, kept as hearsay) and
                # "<owner> mentioning <owner> plays the cello" (the frame).
                if (role == "assistant" and self.owner_name
                        and re.match(rf"^{re.escape(self.owner_name)}\s+"
                                     r"(mentioning|saying|telling|noting|"
                                     r"suggesting|asking)\b", prop)):
                    continue
            if src and _retracted(text, src):
                continue
            out.append(Record(text=prop, kind=kind, session=session,
                              turn=turn, role=role, predicate=pred, value=val,
                              evidential=evi, source=orig.get(src, src),
                              quality=C.quality(prop, text, self.owner_name)))
        return _work_filters(_drop_framed(out), role, self.owner_name)

    def reset_world(self):
        """Forget the accumulated world (e269). Call between owners."""
        self._world = {}

    def extract(self, dialogue, session=0):
        """dialogue: [{"role": ..., "content": ...}] for ONE session."""
        out = []
        prev = None
        for i, t in enumerate(dialogue):
            content = str(t.get("content", "")).strip()
            if not content:
                continue
            role = t.get("role", "user")
            out.extend(self.extract_turn(content, role, session, i,
                                         prev=prev if role == "user" else None))
            prev = content if role == "assistant" else None
        return out


def ort_models_dir():
    """The stanza_ort model folder when it is installed and usable, else
    None (then Stanza on PyTorch is used). RGX_PARSER=stanza forces Stanza;
    RGX_PARSER_MODELS names the folder (sourcedrecall sets it to the one
    its setup installed)."""
    if os.environ.get("RGX_PARSER", "").lower() == "stanza":
        return None
    d = os.environ.get("RGX_PARSER_MODELS")
    if not d or not os.path.exists(os.path.join(d, "config.json")):
        return None
    try:
        import stanza_ort  # noqa: F401
    except ImportError:
        return None
    return d


class _CachedParser:
    """The Stanza pipeline, answering from Extractor.prefetch's parses when
    it has one for exactly this text. The parser only reads a parse, never
    changes it, so one can be used more than once. Every parse goes through
    normalize.normalize first (2026-10-15: the rules read one analysis of a
    construction whichever parser made it)."""

    def __init__(self, nlp, document_cls):
        self.nlp = nlp
        self.Document = document_cls
        self.cache = {}

    def __call__(self, text):
        doc = self.cache.get(text)
        return doc if doc is not None else normalize(self.nlp(text))

    def __getattr__(self, name):
        return getattr(self.nlp, name)


def extract(dialogue, owner=None, session=0, check=True):
    """One-shot convenience wrapper. Builds a parser per call -- use
    `Extractor` directly when processing more than one session."""
    return Extractor(owner_name=owner, check=check).extract(dialogue, session)
