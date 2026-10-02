"""Is a chat turn prose, or pasted code/terminal output?

Moved out of run_belief.py (2026-10-02). The product read/write path needed
only this helper, but importing it from run_belief also imported eight
research modules and, at import time, READ a gitignored research cache
(experiments/p2/extract_cache.jsonl) and opened it for APPENDING. A fresh
clone has no such file, so the server crashed on its first ingest -- the
new-user install test hit exactly that. run_belief re-exports it, so every
existing import keeps working.
"""
import re


_FIRST_PERSON = re.compile(r"^(?:i|i'm|i’m|i am|i've|i’ve|my|we|we're|we’re)\s+\w",
                           re.I)


def _is_prose(text):
    """False if the turn is dominated by pasted code/terminal/telemetry rather
    than first-person prose. Real user data (entry 60) is full of pasted vm_stat/
    logs/code that the extractors misread as personal facts; those turns carry no
    life-fact and are skipped. Conversational prose (LongMemEval, personal chat)
    passes untouched."""
    if "```" in text:
        return False
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return True
    codey = 0
    for ln in lines:
        s = ln.strip()
        nonalnum = sum(1 for c in s if not c.isalnum() and not c.isspace())
        digits = sum(1 for c in s if c.isdigit())
        L = max(1, len(s))
        # 2026-10-02: "I'm 34." is 2 digits in 7 characters and read as
        # telemetry, so the user's age never reached the parser. A line that
        # opens like a first-person sentence is prose if it has at most three
        # digits. Review 2026-10-02: "My PIN is 4821 5512 9930 1123" opens
        # like a sentence too, and a PIN must not reach the memory.
        if _FIRST_PERSON.match(s) and digits <= 3:
            continue
        # symbol-heavy, digit-heavy, or a "label: number" telemetry/config line
        # ("Swapins:  1245194", "pageins: 342...") -- command output, not prose.
        if (nonalnum / L > 0.30 or digits / L > 0.22
                or re.match(r"^[\w./+-]+\s*[:=]\s*[\d,]", s)):
            codey += 1
    return codey / len(lines) < 0.40
