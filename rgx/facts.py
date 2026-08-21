"""rgx -> slot-store adapter.

The product memory (experiments/p2/memory_api via run_wire.build_facts) and
the HaluMem harness (halumem_run.ingest_user) both read ONE cache shape:

    {"h": sha1(turn_text), "f": [{"attribute": ..., "value": ...}, ...]}

one line per turn. This module writes that shape from rgx records, so a
store that was built from a prompted extractor's facts builds from the
parser's instead, with nothing else changed and no model in the write path.

The attribute is the record's predicate key (head lemma + case marker, or
the possessed slot, or the relation noun); the value is its complement.
"""
import hashlib
import json

from . import Extractor


def to_fact(rec):
    """One rgx Record -> {"attribute", "value"} or None if it has no slot."""
    if not rec.predicate or not rec.value:
        return None
    return {"attribute": rec.predicate, "value": rec.value,
            "text": rec.text, "kind": rec.kind, "turn": rec.turn,
            "role": rec.role}


def turn_hash(text, namespace=None):
    """Same hash the consumers use: bare sha1 of the turn text."""
    t = text if namespace is None else f"{namespace}:{text}"
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def write_cache(sessions, path, owner=None, roles=("user", "assistant"),
                max_chars=1800, extractor=None, progress=None):
    """sessions: iterable of [{"role","content"}] dialogues (one per
    session). Writes one cache line per non-empty turn. Returns the count
    of (turns, facts) written.

    `max_chars` mirrors halumem_run.ingest_user's truncation so the hash
    matches what that harness looks up."""
    ex = extractor or Extractor(owner_name=owner)
    n_turns = n_facts = 0
    with open(path, "w", encoding="utf-8") as fh:
        for si, dialogue in enumerate(sessions):
            for ti, t in enumerate(dialogue):
                role = t.get("role", "user")
                if role not in roles:
                    continue
                text = str(t.get("content", "")).strip()[:max_chars]
                if not text:
                    continue
                facts = [f for f in (to_fact(r) for r in
                                     ex.extract_turn(text, role, si, ti))
                         if f is not None]
                fh.write(json.dumps({"h": turn_hash(text), "f": facts}) + "\n")
                n_turns += 1
                n_facts += len(facts)
            if progress:
                progress(si, n_turns, n_facts)
    return n_turns, n_facts
