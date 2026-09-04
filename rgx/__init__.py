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
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

__all__ = ["Record", "Extractor", "extract"]
__version__ = "0.1.0"


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

    def __str__(self):
        return self.text


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

    def _parser(self):
        if self._nlp is None:
            import stanza
            self._nlp = stanza.Pipeline(
                "en", processors="tokenize,pos,lemma,depparse",
                use_gpu=False, verbose=False)
        return self._nlp

    def extract_turn(self, text, role="user", session=0, turn=0):
        from . import check as C
        from . import parse as G
        out = []
        for prop, kind, pred, val, evi in G.extract_keyed(
                text, self._parser(), self.owner_name, role=role,
                owner_pronoun=self.owner_pronoun,
                owner_pronoun_obj=self.owner_pronoun_obj):
            if self.check:
                ok, _why = C.prefilter(prop, text, self.owner_name,
                                       value=val, kind=kind)
                if not ok:
                    continue
            out.append(Record(text=prop, kind=kind, session=session,
                              turn=turn, role=role, predicate=pred, value=val,
                              evidential=evi,
                              quality=C.quality(prop, text, self.owner_name)))
        return out

    def extract(self, dialogue, session=0):
        """dialogue: [{"role": ..., "content": ...}] for ONE session."""
        out = []
        for i, t in enumerate(dialogue):
            content = str(t.get("content", "")).strip()
            if not content:
                continue
            out.extend(self.extract_turn(content, t.get("role", "user"),
                                         session, i))
        return out


def extract(dialogue, owner=None, session=0, check=True):
    """One-shot convenience wrapper. Builds a parser per call -- use
    `Extractor` directly when processing more than one session."""
    return Extractor(owner_name=owner, check=check).extract(dialogue, session)
