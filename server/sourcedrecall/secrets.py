"""Credentials never enter the memory.

2026-10-02: "My password for the staging server is hunter2" became a fact,
went into MEMORY.md and the session summary, and was the answer to "What is
my API key?". Messages pass through `scrub` before anything is written, so
the stored transcript, the parsed facts and the quoted sentences all see the
same "[secret removed]".

Two kinds of match:
  * a labelled value: "<password | PIN | API key | card number | ...>
    [for <something>] is/was/=/: <value>";
  * a value that is recognisable on its own: provider key formats, private
    key blocks, card numbers that pass the Luhn check, US social security
    numbers.
"""
import re

MARK = "[secret removed]"

_LABEL = re.compile(
    r"(?P<label>\b(?:passwords?|passcodes?|passphrases?|pins?|pin codes?|"
    r"api[ _-]?keys?|access[ _-]?keys?|secret[ _-]?keys?|auth(?:entication)? "
    r"tokens?|access tokens?|tokens?|secrets?|ssn|social security numbers?|"
    r"(?:credit |debit )?card numbers?|cvv|cvc|security codes?|"
    r"account numbers?|routing numbers?|sort codes?|iban|seed phrases?|"
    r"recovery phrases?|private keys?|2fa codes?|otp|one[- ]time codes?)\b"
    r"(?:\s+(?:for|to|on|at|of)\s+[\w .'-]{1,40}?)?"
    r"\s*(?:is|was|are|=|:)\s*)(?P<value>[\"']?[^\s\"']+[\"']?)",
    re.I)

_FORMATS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
               re.S),
    re.compile(r"\b(?:sk|pk|rk)-(?:proj-|live-|test-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
]
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def _luhn(digits):
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def scrub(text):
    """-> text with credentials replaced by MARK."""
    if not text:
        return text
    s = str(text)
    for rx in _FORMATS:
        s = rx.sub(MARK, s)

    def card(m):
        digits = re.sub(r"\D", "", m.group(0))
        return MARK if 13 <= len(digits) <= 19 and _luhn(digits) else m.group(0)
    s = _CARD.sub(card, s)

    def labelled(m):
        v = m.group("value")
        if v.startswith("[secret"):
            return m.group(0)
        # keep sentence punctuation after the value
        tail = re.search(r"[.,;!?)]+$", v)
        return m.group("label") + MARK + (tail.group(0) if tail else "")
    return _LABEL.sub(labelled, s)
