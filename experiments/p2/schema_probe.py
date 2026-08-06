"""Gap-directed extraction: go looking for what the schema says is missing.

Entry 193. Our extractor is TEXT-DIRECTED -- it walks turns and reports what
each happened to contain. It therefore has no representation of what it never
saw, and a missing birth date is indistinguishable from an absent one.

persona_schema.gaps() inverts that: it names the slots the store cannot answer.
This module acts on them. For each gap it finds the turns most likely to carry
that slot and asks a SLOT-DIRECTED question of just those turns.

Three properties that make this different from "extract harder":

  * It is a SCOPE-directed prompt ("does this state the user's birth date?"),
    not an assertion-calibration one. Entry 191 established that scope rules
    hold in this codebase while calibration rules never have.
  * Cost scales with what is MISSING, not with transcript length. A store with
    no gaps costs nothing; one missing three slots pays for three small sweeps.
  * It can only ADD to slots known to be empty, so it cannot inflate the
    precision problem the way a broader extraction pass would -- the failure
    mode of entry 185, where we extracted more of the wrong thing.

Cheap candidate selection first, LLM second: only turns whose surface cues match
the missing slot are ever sent to a model.
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from persona_schema import SCHEMA, gaps  # noqa: E402

SLOT_QUESTION = (
    "Does this message state the user's {slot}?\n\n"
    "Answer with ONLY a JSON array. If it states it, output one object:\n"
    '[{{"attribute": "{attr}", "value": "<the value, short>"}}]\n'
    "If the message does not state the user's {slot}, output exactly: []\n\n"
    "Take the value only if this message actually states it. Do not infer it, "
    "do not guess from context, and do not carry it over from what you assume "
    "the user is like. If unsure, output [].\n\nMESSAGE:\n{text}"
)


def candidate_turns(turns, group, slot, limit=6):
    """Turns whose surface cues suggest they might carry this slot.

    Purely lexical and deliberately cheap -- its only job is to keep the LLM
    pass proportional to the gap rather than to the transcript. Ranked by cue
    count so the most promising turns are asked first."""
    cues = [c.lower() for c in SCHEMA[group][slot]]
    key = slot.replace("_", " ").lower()
    scored = []
    for i, t in enumerate(turns):
        low = str(t).lower()
        n = sum(1 for c in cues if c in low) + (2 if key in low else 0)
        if n:
            scored.append((n, i))
    scored.sort(key=lambda z: (-z[0], z[1]))
    return [i for _, i in scored[:limit]]


def probe_gaps(store_texts, turns, extract_fn, limit_per_slot=6, max_slots=None):
    """Fill what the schema says is missing.

    extract_fn(prompt) -> list[{attribute, value}]; injected so this module
    stays testable without a model and so the caller controls which endpoint
    pays for it.

    Returns (found, report) where report records EVERY slot attempted and how
    many turns it cost -- a gap we looked for and did not find is as much a
    result as one we filled, and silently dropping those would make the pass
    look more effective than it is.
    """
    missing = gaps(store_texts)
    if max_slots:
        missing = missing[:max_slots]
    found, report = [], []
    for group, slot in missing:
        cands = candidate_turns(turns, group, slot, limit_per_slot)
        got = []
        for i in cands:
            prompt = SLOT_QUESTION.format(slot=slot.replace("_", " "),
                                          attr=slot, text=str(turns[i])[:1200])
            try:
                facts = extract_fn(prompt) or []
            except Exception:
                continue
            for f in facts:
                v = re.sub(r"\s+", " ", str(f.get("value", "")).strip())
                if v and len(v) < 160:
                    got.append({"attribute": slot, "value": v,
                                "group": group, "turn": i,
                                "source": "schema_probe"})
            if got:
                break                      # first hit wins; stop paying
        report.append({"group": group, "slot": slot,
                       "candidates": len(cands), "filled": bool(got)})
        found.extend(got)
    return found, report
