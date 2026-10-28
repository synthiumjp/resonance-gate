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

# 2026-10-09 (security review): the left edge was \b, and "_" is a word
# character, so DB_PASSWORD=hunter2 and STRIPE_SECRET_KEY=... got through;
# the edges are now "not a letter or digit".
_KEYWORD = re.compile(
    r"(?<![A-Za-z0-9])(?:(?:my)?pass(?:word|words|wd|code|codes|phrase|phrases)|pass(?=\s*[:=])|pw|pwd|mdp|"
    # 2026-10-12 (review 3.17): "my pass is hunter2", and the common words
    # for a password in other languages (the filter is otherwise English)
    r"pass(?=\s+(?:is|was)\s+(?=\w*\d)(?=\w*[A-Za-z])\w{4,}\b)|passwort|kennwort|mot de passe|contrase[ñn]a|senha|wachtwoord|"
    r"pin codes?|credentials?|username and password|"
    r"api[ _-]?keys?|access[ _-]?keys?|secret[ _-]?keys?|private[ _-]?keys?|"
    r"ssh[ _-]?keys?|(?:wifi|wi-fi|product|licen[cs]e|encryption|recovery|"
    r"door|gate|alarm|garage|lock|safe)[ _-]?(?:keys?|codes?|combination)|"
    r"(?:auth|access|bearer|refresh|session|api|github|personal access)"
    r"[ _-]?tokens?|tokens?\s*[:=]|"
    r"ssn|social security(?: numbers?)?|"
    r"card numbers?|cvv|cvc|security codes?|"
    r"(?:bank )?account numbers?|routing numbers?|sort codes?|"
    r"iban|swift(?: codes?|/bic)|bic codes?|bsb(?: numbers?)?|seed phrases?|recovery (?:phrases?|codes?)|"
    r"backup codes?|2fa codes?|one[- ]time (?:codes?|passwords?)|"
    r"passport numbers?|(?:driver'?s? )?licen[cs]e numbers?|"
    r"national insurance(?: numbers?)?|ni number|tax file number|tfn|sin numbers?|"
    r"aadhaar|medicare number|code to the \w+|combination to the \w+|"
    r"key(?=\s+(?:is|was|:|=)\s+\S*\d)|"
    r"key(?=\s*[:=]\s*['\"]?(?=[^\s'\"]*\d)(?=[^\s'\"]*[A-Za-z])[^\s'\"]{8,}))(?![A-Za-z0-9])",
    re.I)
# 2026-10-10 (held-out v8: "recipe card:" removed a pasted recipe's
# introduction and the sentence after it; "I code in Swift", "My login is
# slow today", "that was a sin" were removed whole). Everyday words that can
# also name a credential count only with a value that looks like one: a
# digit, or "word: value" / "word = value". They never take the next
# sentence with them.
_WEAK = re.compile(r"(?<![A-Za-z0-9])(?:pins?|logins?|creds|otp|bearer|authorization|bank accounts?|"
                   r"(?:credit|debit|bank) cards?|passports?|my social|"
                   r"(?-i:SIN|BSB|SWIFT))(?![A-Za-z0-9])", re.I)
_WEAK_WORD = (r"(?<![A-Za-z0-9])(?:pins?|logins?|creds|otp|bank accounts?|(?:credit|debit|bank) cards?|"
              r"passports?|sin|bsb|swift|my social)")
_WEAK_VALUE = re.compile(_WEAK_WORD + r"\W{0,3}(?:(?:is|was|are|number|no\.?|code|#)\W{0,3}){0,2}"
                         r"[A-Za-z]{0,3}[\d][\d\s-]{2,}|" + _WEAK_WORD + r"\s*[:=]\s*\S|"
                         # "my login is bob / hunter2"
                         + _WEAK_WORD + r"\W{0,3}(?:is|was|are)\b[^.!?\n]{0,25}?"
                         r"\b(?=\w*\d)(?=\w*[A-Za-z])\w{4,}", re.I)
# not credentials, though they share a word
_HARMLESS = re.compile(
    r"\b(?:password manager|passport photo|pin(?:s)? (?:down|up|it|them|in "
    r"the)|pinned|card game|birthday card|business card|gift card shop|"
    r"forgot (?:my|the) password|reset (?:my|the) password|change(?:d)? "
    r"(?:my|the) password|"
    # a count of tokens, not a token (max_tokens: 512, "tokens: 30000")
    r"(?:max|num|n|total|input|output|prompt|completion|context)?[_ ]?tokens?"
    r"\s*[:=]\s*\d[\d,_]*(?![\w-])"
    r")\b", re.I)
# (\w then the symbol: the same matches as \w+, without rescanning a long word)
_VALUE_HINT = re.compile(r"\d|[:=/]|\b(?:is|was|are|to|as|'s)\b|\w[@#$%^&*!]")

# 2026-10-21 (review): the key-block patterns were ".*?" to the END line,
# so text with many BEGIN lines and no END took quadratic time (336 KB: 11 s,
# on every stored message). Key blocks are now found in one pass (_keys).
_KEY_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----")
_KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----")


def _keys(s):
    out, pos = [], 0
    while True:
        b = _KEY_BEGIN.search(s, pos)
        if not b:
            out.append(s[pos:])
            return "".join(out)
        out.append(s[pos:b.start()])
        e = _KEY_END.search(s, b.end())
        out.append(MARK)
        if not e:               # a block cut off before its END line
            return "".join(out)
        pos = e.end()


_FORMATS = [
    # 2026-10-12 (review 3.17): "Authorization: Basic dXNlcjpwYXNz..."
    re.compile(r"(?i)\bauthorization\s*:\s*(?:basic|bearer|token|digest)?\s*[A-Za-z0-9._~+/=-]{8,}"),
    # 2026-10-09: an assignment whose name says what it is, as in a pasted
    # .env or config file (DB_PASSWORD=..., client_secret = '...',
    # STRIPE_SECRET_KEY: ...). 2026-10-12 (review 3.16): the runs around the
    # name are bounded; unbounded, a long run of "a-a-a-..." or dotted names
    # was rescanned from every word boundary (8 KB took 8 s).
    re.compile(r"(?i)\b(?![\w.-]{0,60}(?:error|exception|warning)\s*:)[\w.-]{0,60}(?:password|passwd|pwd|secret|token|api[_-]?key|"
               r"access[_-]?key|private[_-]?key)[\w.-]{0,60}\s*[:=]\s*"
               # a value, not a count ("max_tokens: 512")
               r"(?=['\"]?[^\s'\"]*[A-Za-z]|['\"]?[^\s'\"]{6,})"
               r"(?:'[^'\n]*'|\"[^\"\n]*\"|[^\s,;]+)"),
    re.compile(r"\b[a-z][a-z0-9+.-]{0,30}://[^\s/:@]+:[^\s/@]+@\S+", re.I),
    # 2026-10-28 (review M8): command-line flags ("--password hunter2",
    # "--token=abc"), user:password@host without a scheme, webhook secrets
    re.compile(r"(?i)(?<![\w-])--(?:password|passwd|pass|pwd|token|auth-token|api[-_]?key|secret|"
               r"access[-_]?key|client[-_]secret)(?:=|\s+)(?!-)\S+"),
    re.compile(r"(?<![\w/:@.-])[A-Za-z0-9._-]{1,40}:[^\s/@:]{3,}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
    re.compile(r"\bwhsec_[A-Za-z0-9+/=]{16,}"),
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
    # (the checks look 300 characters ahead, not to the end of the run)
    re.compile(r"\b(?=[A-Za-z0-9_+/-]{0,300}\d)(?=[A-Za-z0-9_+/-]{0,300}[A-Za-z])"
               r"(?![A-Za-z0-9_+/-]{0,300}[a-z]{3,}_[a-z]{3,})(?![a-z0-9_/-]{0,300}/[a-z0-9_-]*\b)"
               r"[A-Za-z0-9_+/-]{24,}={0,2}"),
]
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
# the credential sentence leaves its value for the next one
_POINTS_AHEAD = re.compile(r"[?:=]\s*$|\b(?:following|below|here it is|"
                           r"here's|this one|as follows)\b", re.I)
# 2026-10-12 (review 3.17): "my password is" or "The password" ending a line,
# the value on the next. Wrapped prose ends lines the same way ("Never reuse
# a password / across sites."), so the next line goes only when it looks
# like a value: at most four words, no sentence ending.
_AFTER_NAME = re.compile(r"\s*(?:(?:is|was|are)\s*)?", re.I)
_LOOKS_LIKE_VALUE = re.compile(r"^\s*\S+(?:[ \t]+\S+){0,3}\s*$(?<![.!?])")
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
    s = _keys(s)
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
        weak = (not named and bool(_WEAK.search(sent)) and not _HARMLESS.search(sent)
                and bool(_WEAK_VALUE.search(sent)))
        if carry and len(sent.split()) <= 8:
            out.append(MARK)
            carry = False
            continue
        carry = False
        if weak or (named and _VALUE_HINT.search(sent)):
            out.append(MARK)
        else:
            out.append(sent)
        # the value may come in the next sentence: "the wifi password?
        # It's tulip99", "My password is the following. hunter2"
        carry = named and bool(_POINTS_AHEAD.search(sent))
        if (named and not carry and i + 1 < len(parts) and "\n" in seps[i]
                and any(_AFTER_NAME.fullmatch(sent[m.end():]) for m in _KEYWORD.finditer(sent))
                and _LOOKS_LIKE_VALUE.match(parts[i + 1])):
            carry = True
    rebuilt = ""
    for i, sent in enumerate(out):
        rebuilt += sent + (seps[i] if i < len(seps) else "")
    return rebuilt
