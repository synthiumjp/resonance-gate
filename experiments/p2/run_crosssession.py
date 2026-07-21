"""p2 CROSS-SESSION test: the axis entry 58 said actually matters.

Real fact-change is a cross-SESSION phenomenon (people contradict themselves over
weeks, across separate chats), not a within-conversation one. This runs the belief
memory over an ENTIRE Claude/assistant export as one time-ordered stream of the
user's own first-person utterances, and surfaces facts that changed across
sessions -- with receipts (which conversation, when).

Model-free only (use_llm=False): 18k+ turns is far too many for per-turn LLM
extraction, but the value/cos/functional extractors are regex and fast. This is
the cheap first pass; an entity-scoped LLM audit is the categorical follow-up.

PRIVACY: input is the user's OWN quarantined export (scratchpad, never git). This
script prints only COUNTS and, for the user's own review, its detected changes
with identifiers (names/emails/phones) REDACTED even from stdout -- defence in
depth. Nothing here is committed.

Usage: run_crosssession.py <conversations.json> [max_convos]
"""

import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from belief import BeliefMemory
from schema import Scope
from run_belief import evidence_from_span, changes

# redaction for stdout (the export's own identity fields are read separately)
_REDACT = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(\+?\d[\d\-\.\s()]{7,}\d)(?!\d)"), "[PHONE]"),
]
_EXTRA_REDACT = []          # filled with the account's own name tokens


def redact(s):
    s = str(s)
    for rx, rep in _REDACT:
        s = rx.sub(rep, s)
    for tok in _EXTRA_REDACT:
        if tok:
            s = re.sub(rf"\b{re.escape(tok)}\b", "[NAME]", s, flags=re.I)
    return s


def load_stream(path):
    """All human utterances across all conversations, sorted by timestamp.
    Returns [(step_index, conv_uuid, created_at, text)]."""
    conv = json.load(open(path))
    conv.sort(key=lambda c: c.get("created_at", ""))
    stream = []
    for i, c in enumerate(conv):
        for m in (c.get("chat_messages") or []):
            if (m.get("sender") or "").lower() != "human":
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x)
                               for x in txt)
            if txt.strip():
                stream.append((i, c.get("uuid", ""), c.get("created_at", "")[:10],
                               txt.strip()[:1800]))
    return stream


def main():
    path = sys.argv[1]
    max_convos = int(sys.argv[2]) if len(sys.argv) > 2 else None

    # capture the account's own name tokens for redaction (never printed)
    udir = os.path.dirname(path)
    try:
        u = json.load(open(os.path.join(udir, "users.json")))[0]
        for tok in re.findall(r"[A-Za-z]{3,}", u.get("full_name", "")):
            _EXTRA_REDACT.append(tok)
    except Exception:
        pass

    stream = load_stream(path)
    if max_convos:
        keep = set(sorted({s[0] for s in stream})[:max_convos])
        stream = [s for s in stream if s[0] in keep]
    n_steps = len({s[0] for s in stream})
    print(f"cross-session stream: {len(stream)} user turns over {n_steps} conversations")

    mem = BeliefMemory()
    sc = Scope()
    for step, uuid, date, text in stream:
        for slot, value, r in evidence_from_span(text, sc, span_id=step, use_llm=False):
            mem.observe(slot, "_", value, step, reliability=r)

    ch = changes(mem)
    # a CROSS-SESSION change = the >=2 values were observed in DIFFERENT conversations
    cross = []
    for c in ch:
        b = mem.slots[c["slot"]]
        steps = {v: b.last_step[v] for v in b.posterior() if b.n_evidence[v] > 0}
        if len(set(steps.values())) >= 2:            # spans >=2 conversations
            cross.append((c, steps))

    print(f"belief changes detected: {len(ch)} total, {len(cross)} span >=2 conversations\n")
    print("=== cross-session changes (identifiers redacted) ===")
    for c, steps in cross[:40]:
        key = c["slot"][0]
        attr = key[1] if len(key) > 1 else key
        vals = [(redact(v)[:40], round(p, 2)) for v, p in c["history"]]
        print(f"  attr={redact(str(attr))[:50]}")
        print(f"     values over sessions: {vals}")

    # ---- CURRENT-STATE picture: what the memory RELIABLY believes about you now.
    # The likely real product surface (entry 63): an accurate receipted portrait,
    # not the rare change events. Show named PROFILE facts (functional + cos)
    # that crossed the belief threshold, with corroboration count as the trust
    # signal. Numeric quantity slots are summarised, not listed (mostly counts).
    import re as _re
    asserts = mem.assertions(min_prob=0.70)
    profile, numeric_ct = [], 0
    for a in asserts:
        slot = a["subject"]                       # the full slot key
        attr = slot[1] if isinstance(slot, tuple) and len(slot) > 1 else slot
        if isinstance(attr, frozenset):
            numeric_ct += 1
            continue
        if _re.match(r"cos@\d+$", str(attr)):     # transient within-conversation
            continue
        profile.append((a["confidence"], a["n_evidence"], str(attr), a["value"]))
    profile.sort(reverse=True)
    print(f"\n=== CURRENT-STATE PROFILE (what the memory reliably believes about you) ===")
    print(f"{len(profile)} named profile facts (P>=0.70), {numeric_ct} quantity slots\n")
    for conf, n, attr, val in profile[:50]:
        print(f"  [{conf:.2f} x{n} mentions] {redact(attr)[:26]:26s} : {redact(str(val))[:52]}")


if __name__ == "__main__":
    main()
