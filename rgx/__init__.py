"""rgx -- deterministic memory extraction from dialogue. No LLM required.

Extracts durable facts from a conversation using a dependency parse and a
person-shift transformation. Every record carries the turn it came from, so
nothing in the store is unattributable.

    from rgx import extract

    records = extract(dialogue, owner="Martin Mark")
    for r in records:
        print(r.text, "<-", r.role, "turn", r.turn)

Measured against HaluMem-Medium on a held-out user, judged by the benchmark's
own harness: recall 0.4609 against a prompted 14B's 0.2122 (+24.9pt, McNemar
p=4.8e-23), with zero model calls at extraction time. Numbers, method and the
things that did NOT work are in docs/EXPERIMENT_LEDGER.md -- including six
instrument defects found along the way, five of which flattered the results.

Design commitments, in order of how much they cost to keep:

  NEVER INVENT CONTENT.  Every content word in a record must trace to the
      source turn. A slot NAME may come from our schema; a VALUE may not.
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
    """
    owner_name: Optional[str] = None
    check: bool = True
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
        for prop, kind, pred, val in G.extract_keyed(text, self._parser(),
                                                self.owner_name, role=role):
            if self.check:
                ok, _why = C.prefilter(prop, text, self.owner_name)
                if not ok:
                    continue
            out.append(Record(text=prop, kind=kind, session=session,
                              turn=turn, role=role, predicate=pred, value=val,
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
