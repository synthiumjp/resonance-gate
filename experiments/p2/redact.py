"""Redaction for anything printed to stdout (2026-10-02, moved out of
run_crosssession.py so the product path does not import that research
script -- which imports run_belief, which read and opened a gitignored cache
file at import time and crashed a fresh install). run_crosssession
re-exports these names; `_EXTRA_REDACT` is the SAME list object everywhere,
so a caller that appends the account's own name tokens affects every
`redact` call."""
import re

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
