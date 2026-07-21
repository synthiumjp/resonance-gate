"""p2 THE REAL TEST: run the whole memory pipeline on a REAL human transcript.

Everything until now is LongMemEval. This points the actual product surface --
extraction -> belief memory (numeric) + consistency audit (categorical,
grounding-verified) -> change disclosure with receipts -- at a genuinely real,
scraped human conversation. No labels, no benchmark to overfit. The question is
only: on messy real chat, what does the memory ASSERT, and what CHANGES does it
disclose, and are the disclosures honest (real change, real receipts) or noise?

Usage: .venv/bin/python experiments/p2/run_real.py experiments/p2/real/transcript_01.json
Transcript format: JSON list of {"role": "user"|"assistant", "content": "..."}.
Only USER turns are memory evidence; each user turn is one time-ordered span.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from belief import BeliefMemory
from schema import Scope
from resolve import resolve_pronouns
from run_belief import evidence_from_span, changes
from consistency import audit, verify


def load_user_turns(path):
    """Return the user's utterances in time order from a transcript file."""
    data = json.load(open(path))
    # accept a flat list of turns, or {"conversations": [...]}, or a list of convs
    if isinstance(data, dict):
        data = data.get("conversations") or data.get("turns") or data.get("messages") or []
    turns = []
    for t in data:
        if not isinstance(t, dict):
            continue
        role = (t.get("role") or t.get("from") or "").lower()
        content = t.get("content") or t.get("value") or t.get("text") or ""
        if role in ("user", "human") and content.strip():
            turns.append(content.strip())
    return turns


def build_memory(user_turns):
    mem = BeliefMemory()
    sc = Scope()
    # real chat contains pasted documents (a resume, long specs) that blow the
    # extractor's context window and are not conversational memory anyway. Cap
    # each turn to a normal-utterance length before extraction (a fact stated in
    # a 3000-word paste is not the kind of thing this memory targets).
    resolved = [resolve_pronouns(u[:1800]) for u in user_turns]
    # first pass: populate scope orbit (who/what is in this person's world)
    for txt in resolved:
        from run_belief import cached
        for tr in cached(txt):
            sc.observe(tr)
    # second pass: feed gated evidence into the belief state, in time order
    for si, txt in enumerate(resolved):
        for slot, value, r in evidence_from_span(txt, sc):
            mem.observe(slot, "_", value, si, reliability=r)
    return mem


def main():
    if len(sys.argv) < 2:
        print("usage: run_real.py <transcript.json>")
        return
    path = sys.argv[1]
    user_turns = load_user_turns(path)
    print(f"=== REAL TRANSCRIPT: {os.path.basename(path)} ===")
    print(f"user turns: {len(user_turns)}\n")

    # ---- numeric / functional path: the belief state
    mem = build_memory(user_turns)
    asserts = mem.assertions(min_prob=0.60)
    print(f"--- BELIEF MEMORY asserts {len(asserts)} resolved fact(s) (P>=0.60):")
    for a in sorted(asserts, key=lambda x: -x["confidence"])[:25]:
        print(f"   [{a['confidence']:.2f} n={a['n_evidence']}] {a['subject']} / {a['attribute']} = {a['value']}")

    ch = changes(mem)
    print(f"\n--- BELIEF-NATIVE CHANGES disclosed: {len(ch)}")
    for c in ch:
        recs = [(str(v)[:32], round(p, 2)) for v, p in c["history"]]
        print(f"   slot {c['slot']}")
        print(f"      receipts (value, P over time): {recs}")

    # ---- categorical path: the LLM-as-energy audit, grounding-verified
    print(f"\n--- CONSISTENCY AUDIT (LLM proposes, grounding+model-free verify):")
    # cap each statement so a long real conversation fits the audit context
    # window (real chat overflows 8192 raw). This is the crude stand-in for the
    # proper neighbourhood-scoping still owed -- but it lets the audit RUN.
    audit_input = [t[:220] for t in user_turns]
    try:
        proposals = audit(audit_input)
        verified = [c for c in proposals if verify(c, audit_input)]
        print(f"   LLM proposed {len(proposals)}, {len(verified)} survived verification")
        for c in verified:
            print(f"      * {c.get('attribute')}: {c.get('old')!r} -> {c.get('new')!r}")
    except Exception as e:
        print(f"   [audit skipped: {e}]")

    print("\n(honest read: are the disclosed changes REAL in the transcript, with")
    print(" correct receipts? or noise? that judgement is the actual test.)")


if __name__ == "__main__":
    main()
