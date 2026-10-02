"""Credentials never enter the memory.

2026-10-02: "My password for the staging server is hunter2" became a fact,
went into MEMORY.md and the session summary, and was the answer to "What is
my API key?". Messages pass through `scrub` before anything is written, so
the stored transcript, the parsed facts and the quoted sentences all see the
same "[secret removed]".

Review round 3 (same day) broke the first version, which removed one token
after "<label> is". "pw: hunter2", "hunter2 is my password", "I set my
password to hunter2", "the wifi password? it's tulip99", multi-word
passphrases, "bob / hunter2", connection strings and door codes all got
through. So the unit is now the SENTENCE:
  * a sentence that names a credential and gives something that could be
    its value (a separator, a digit, or the label after the value) is
    removed whole;
  * a sentence that names a credential without a value removes the next
    sentence too when it is short ("...password? It's tulip99.");
  * values recognisable on their own (provider key formats, private key
    blocks, credentials in URLs, Luhn-valid card numbers, SSN patterns, long
    random tokens) are removed wherever they appear.
Losing "My password is too short" is the accepted cost.
"""
import re

MARK = "[secret removed]"

_KEYWORD = re.compile(
    r"\b(?:pass(?:word|words|wd|code|codes|phrase|phrases)?|pw|pwd|mdp|"
    r"pins?|pin codes?|logins?|credentials?|creds|username and password|"
    r"api[ _-]?keys?|access[ _-]?keys?|secret[ _-]?keys?|private[ _-]?keys?|"
    r"ssh[ _-]?keys?|(?:wifi|wi-fi|product|licen[cs]e|encryption|recovery|"
    r"door|gate|alarm|garage|lock|safe)[ _-]?(?:keys?|codes?|combination)|"
    r"(?:auth|access|bearer|refresh|session|api|github|personal access)"
    r"[ _-]?tokens?|tokens?\s*[:=]|bearer|authorization|"
    r"ssn|social security(?: numbers?)?|my social|"
    r"(?:credit |debit |bank )?card(?: numbers?)?|cvv|cvc|security codes?|"
    r"(?:bank )?account numbers?|bank account|routing numbers?|sort codes?|"
    r"iban|swift|bsb|seed phrases?|recovery (?:phrases?|codes?)|"
    r"backup codes?|2fa codes?|otp|one[- ]time (?:codes?|passwords?)|"
    r"passport(?: numbers?)?|(?:driver'?s? )?licen[cs]e numbers?|"
    r"national insurance(?: numbers?)?|ni number|tax file number|tfn|sin|"
    r"aadhaar|medicare number|code to the \w+|combination to the \w+|"
    r"key(?=\s+(?:is|was|:|=)\s+\S*\d))\b",
    re.I)
# not credentials, though they share a word
_HARMLESS = re.compile(
    r"\b(?:password manager|passport photo|pin(?:s)? (?:down|up|it|them|in "
    r"the)|pinned|card game|birthday card|business card|gift card shop|"
    r"forgot (?:my|the) password|reset (?:my|the) password|change(?:d)? "
    r"(?:my|the) password)\b", re.I)
_VALUE_HINT = re.compile(r"\d|[:=/]|\b(?:is|was|are|to|as|'s)\b|\w+[@#$%^&*!]")

_FORMATS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
               re.S),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@\S+", re.I),
    re.compile(r"\b(?:sk|pk|rk)[-_](?:proj-|live[-_]|test[-_])?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\baws_secret_access_key\s*[=:]\s*\S+", re.I),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}=*", re.I),
    re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b"),
    # long random-looking tokens: letters AND digits, 24+ characters
    re.compile(r"\b(?=[A-Za-z0-9_+/-]*\d)(?=[A-Za-z0-9_+/-]*[A-Za-z])"
               r"[A-Za-z0-9_+/-]{24,}={0,2}"),
]
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
# the credential sentence leaves its value for the next one
_POINTS_AHEAD = re.compile(r"[?:]\s*$|\b(?:following|below|here it is|"
                           r"here's|this one|as follows)\b", re.I)
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")


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


def _formats(s):
    for rx in _FORMATS:
        s = rx.sub(MARK, s)

    def card(m):
        digits = re.sub(r"\D", "", m.group(0))
        return MARK if 13 <= len(digits) <= 19 and _luhn(digits) else m.group(0)
    return _CARD.sub(card, s)


def scrub(text):
    """-> text with credentials removed (whole sentences where a credential
    is named with a value)."""
    if not text:
        return text
    s = _formats(str(text))
    parts = _SENT.split(s)
    seps = _SENT.findall(s)
    out = []
    carry = False
    for i, sent in enumerate(parts):
        named = bool(_KEYWORD.search(sent)) and not _HARMLESS.search(sent)
        if carry and len(sent.split()) <= 8:
            out.append(MARK)
            carry = False
            continue
        carry = False
        if named and _VALUE_HINT.search(sent):
            out.append(MARK)
        else:
            out.append(sent)
        # the value may come in the next sentence: "the wifi password?
        # It's tulip99", "My password is the following. hunter2"
        carry = named and bool(_POINTS_AHEAD.search(sent))
    rebuilt = ""
    for i, sent in enumerate(out):
        rebuilt += sent + (seps[i] if i < len(seps) else "")
    return rebuilt
