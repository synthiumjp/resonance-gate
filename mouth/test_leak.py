"""E3 Part 2: the leak measurement (plan exit: ungrounded leak <= 2%).

200 turns: 100 grounded (gate cleared a record -> ANSWER with rendered
slots), 100 ungrounded (60 ABSTAIN, 20 DELIBERATE-referential, 20
DELIBERATE-stored). The mouth adds its connective lead-in (temperature 0.7,
seeded per turn). A leak = any factual assertion in the output not present
in the rendered slots. Detector: after removing the allowed body verbatim,
the remainder is scanned for entity vocabulary, relation keywords, and
digits. The detector's own error rate is measured on a hand-checked sample
of 30 (printed; verdicts recorded in notebook entry 9)."""

import re

import numpy as np
import pytest

from speak import ABSTAIN_TEXT, deliberate_text, render, speak

FIRST = ["Tom", "Anna", "James", "Maria", "David", "Sarah", "Michael", "Emma",
         "John", "Sofia", "Robert", "Laura", "Daniel", "Alice", "Peter", "Nina"]
LAST = ["Baker", "Chen", "Fischer", "Garcia", "Hansen", "Kim", "Meyer",
        "Nguyen", "Patel", "Rios", "Schmidt", "Silva", "Diaz", "Wong",
        "Yang", "Vogel"]
PLACES = ["Geneva", "Lisbon", "Boston", "Dublin", "Verona", "Madrid",
          "Oakville", "Fairview", "Salem", "Bristol"]
ORGS = ["Acme Labs", "Vertex Robotics", "Harbor Energy", "Beacon Media",
        "Summit Consulting", "Nova Systems"]
RELS = ["works at", "lives in", "was born in", "manages", "reports to",
        "is married to", "studied at"]

KEYWORD_RE = re.compile(
    r"\d|works?|lives?|born|manages?|reports?|married|sibling|stud(y|ied)|"
    r"employ|schedul|resides?", re.IGNORECASE)


def _vocab():
    v = set(PLACES) | set(ORGS) | set(f"{f} {l}" for f in FIRST for l in LAST)
    v |= set(FIRST) | set(LAST)
    return v


def find_leaks(output, allowed_bodies):
    """Factual content in output beyond the allowed rendered slots."""
    rem = output
    for body in allowed_bodies:
        rem = rem.replace(body, " ")
    hits = [w for w in _vocab() if re.search(rf"\b{re.escape(w)}\b", rem)]
    if KEYWORD_RE.search(rem):
        hits.append(f"keyword:{KEYWORD_RE.search(rem).group(0)}")
    return hits


def _fact(rng):
    s = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    r = str(rng.choice(RELS))
    if r in ("manages", "reports to", "is married to"):
        o = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    elif r in ("works at",):
        o = str(rng.choice(ORGS))
    else:
        o = str(rng.choice(PLACES))
    return (s, r, o)


def test_leak_rates():
    rng = np.random.default_rng(4242)
    turns = []
    for i in range(100):  # grounded
        rec = _fact(rng)
        prov = "assistant-inferred" if i % 5 == 0 else "user-stated"
        turns.append(("grounded", "answer", None, (rec, prov)))
    for i in range(60):
        turns.append(("ungrounded", "abstain", None, None))
    for i in range(20):
        a, b = _fact(rng), _fact(rng)
        turns.append(("ungrounded", "deliberate", "referential", [a[0], b[0]]))
    for i in range(20):
        rec = _fact(rng)
        rec2 = (rec[0], rec[1], str(rng.choice(PLACES + ORGS)))
        turns.append(("ungrounded", "deliberate", "stored",
                      [(rec, "user-stated"), (rec2, "user-stated")]))

    from speak import gen_leadin, verify_leadin
    raw_leaks = {"grounded": 0, "ungrounded": 0}
    leaks = {"grounded": 0, "ungrounded": 0}
    counts = {"grounded": 0, "ungrounded": 0}
    rejected = 0
    samples = []
    for i, (kind, action, tag, payload) in enumerate(turns):
        if action == "answer":
            allowed = [render(*payload)]
        elif action == "deliberate":
            allowed = [deliberate_text(tag, payload)]
        else:
            allowed = [ABSTAIN_TEXT]
        raw_lead = gen_leadin(allowed[0], llm_seed=1000 + i)
        lead = verify_leadin(raw_lead)
        rejected += lead == "" and raw_lead != ""
        out = (lead + " " + allowed[0]).strip()
        raw_hits = find_leaks(raw_lead, [])   # the mouth's raw contribution
        hits = find_leaks(out, allowed)       # what actually gets emitted
        counts[kind] += 1
        raw_leaks[kind] += bool(raw_hits)
        leaks[kind] += bool(hits)
        if len(samples) < 30 and (kind == "ungrounded" or len(samples) < 15):
            samples.append((i, kind, raw_lead, out, hits))

    print("\n[leak] hand-check sample (15 grounded + 15 ungrounded):")
    for i, kind, raw_lead, out, hits in samples:
        flag = f" LEAK{hits}" if hits else ""
        print(f"[leak]  #{i:03d} {kind:>10} raw_lead={raw_lead!r}")
        print(f"[leak]        emitted={out!r}{flag}")
    print(f"[leak] raw mouth lead-ins flagged: grounded "
          f"{raw_leaks['grounded']}/{counts['grounded']}, ungrounded "
          f"{raw_leaks['ungrounded']}/{counts['ungrounded']} "
          f"(pre-verify; the reason verify_leadin exists)")
    print(f"[leak] lead-ins rejected by verify_leadin: {rejected}/{len(turns)}")
    g = leaks["grounded"] / counts["grounded"]
    u = leaks["ungrounded"] / counts["ungrounded"]
    print(f"[leak] emitted grounded: {leaks['grounded']}/{counts['grounded']} = {g:.3f}")
    print(f"[leak] emitted UNGROUNDED: {leaks['ungrounded']}/{counts['ungrounded']} = {u:.3f} "
          f"(exit bar <= 0.02)")
    assert u <= 0.02, f"ungrounded leak rate {u:.3f} exceeds 2%"
