"""p2 REALTIME profile prototype: does LLM extraction (feeding the same belief
machinery) produce a CLEAN profile on real chat, and is it realtime-viable?

Entry 64 decision test. Samples the user's own turns spread across the timeline,
runs the per-turn LLM profile extractor (simulating realtime: one call per turn as
it would arrive), feeds the belief memory, and reports BOTH:
  - QUALITY: the current-state profile (corroborated self-facts, receipts) -- is it
    clean now, vs the ~10-15% precision of the model-free profile (entry 64)?
  - LATENCY: per-turn extraction time (median / p90) -- the realtime budget.

PRIVACY: input is the quarantined export; output redacts identifiers. Nothing
committed but generic code.

Usage: run_profile_sample.py <conversations.json> [n_turns=250]
"""

import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from belief import BeliefMemory
from run_belief import _is_prose
import run_crosssession as RC
from run_crosssession import load_stream, redact
from llm_profile import extract_profile_facts


def main():
    path = sys.argv[1]
    n_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 250

    # load account name tokens for redaction (never printed)
    try:
        u = json.load(open(os.path.join(os.path.dirname(path), "users.json")))[0]
        import re
        for tok in re.findall(r"[A-Za-z]{3,}", u.get("full_name", "")):
            RC._EXTRA_REDACT.append(tok)
    except Exception:
        pass

    stream = load_stream(path)                       # (step, uuid, date, text) time-ordered
    prose = [s for s in stream if _is_prose(s[3])]
    # spread the sample across the whole 13-month timeline (every k-th prose turn)
    k = max(1, len(prose) // n_turns)
    sample = prose[::k][:n_turns]
    print(f"prose turns: {len(prose)}; sampling {len(sample)} spread across timeline\n")

    mem = BeliefMemory()
    lat = []
    n_facts = 0
    for i, (step, uuid, date, text) in enumerate(sample):
        t0 = time.time()
        facts = extract_profile_facts(text)
        lat.append(time.time() - t0)
        for f in facts:
            mem.observe("@speaker", f["attribute"], f["value"], step, reliability=0.75)
            n_facts += 1
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(sample)} turns, {n_facts} facts so far")

    lat.sort()
    med = lat[len(lat)//2] if lat else 0
    p90 = lat[int(len(lat)*0.9)] if lat else 0
    print(f"\n=== LATENCY (realtime budget) ===")
    print(f"  per-turn extraction: median {med*1000:.0f} ms, p90 {p90*1000:.0f} ms "
          f"(qwen3:14b; a smaller model would be faster)")

    # profile grouped by attribute; show corroborated facts (the trust surface)
    print(f"\n=== CURRENT-STATE PROFILE via LLM extraction (identifiers redacted) ===")
    asserts = mem.assertions(min_prob=0.60)
    asserts.sort(key=lambda a: (-a["n_evidence"], -a["confidence"]))
    print(f"{len(asserts)} profile facts (P>=0.60); those with >=2 mentions are corroborated:\n")
    for a in asserts[:60]:
        star = "*" if a["n_evidence"] >= 2 else " "
        print(f" {star}[{a['confidence']:.2f} x{a['n_evidence']}] "
              f"{redact(str(a['attribute']))[:24]:24s} : {redact(str(a['value']))[:50]}")


if __name__ == "__main__":
    main()
