"""Regular expressions copied from stanza.models.tokenization.{utils,data} (Stanza 1.14.0, Apache-2.0)."""
import re
EMAIL_RAW_RE = r"""(?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:(?:2(?:5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9]))\.){3}(?:(?:2(?:5[0-5]|[0-4][0-9])|1[0-9][0-9]|[1-9]?[0-9])|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""

# https://stackoverflow.com/questions/3809401/what-is-a-good-regular-expression-to-match-a-url
# modification: disallow " as opposed to all ^\s
URL_RAW_RE = r"""(?:https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s"]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s"]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s"]{2,}|www\.[a-zA-Z0-9]+\.[^\s"]{2,})|[a-zA-Z0-9]+\.(?:gov|org|edu|net|com|co)(?:\.[^\s"]{2,})"""

MASK_RE = re.compile(f"(?:{EMAIL_RAW_RE}|{URL_RAW_RE})")
SPACE_SPLIT_RE = re.compile(r'( *[^ ]+)')
NEWLINE_WHITESPACE_RE = re.compile(r'\n[\s\u0080-\u009f]*\n')
# this was (r'^([\d]+[,\.]*)+$')
# but the runtime on that can explode exponentially
# for example, on 111111111111111111111111a
NUMERIC_RE = re.compile(r'^[\d]+([,\.]+[\d]+)*[,\.]*$')
WHITESPACE_RE = re.compile(r'[\s\u0080-\u009f]')
STRUCTURAL_LABELED_FIELD_RE = re.compile(
    r'\b[A-Z][a-zA-Z]*(?:\s[A-Z][a-zA-Z]*){0,2}\s*:'
)

# Phone-number-like or short ID-like digit groups: (713) 571-9571,
# 713-654-0365, x365. Deliberately narrow (hyphen/paren/x-prefixed digit
# groups only) to avoid firing on ordinary numeric expressions like page
# counts or years.
STRUCTURAL_PHONE_ID_RE = re.compile(
    r'\(\d{3}\)\s?\d{3}-\d{4}'      # (713) 571-9571
    r'|\b\d{3}-\d{3}-\d{4}\b'       # 713-654-0365
    r'|\bx\d{3,5}\b'                # x365
)

# Numeric dates: 28/10/2004, 16/11/2004, or "November 5, 1999" style.
STRUCTURAL_DATE_RE = re.compile(
    r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'
    r'|\b(?:January|February|March|April|May|June|July|August|September'
    r'|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
)

# Currency amounts: $62,500 / $47,500.00
STRUCTURAL_CURRENCY_RE = re.compile(
    r'\$\s?\d[\d,]*(?:\.\d+)?'
)

STRUCTURAL_FEATURES = {
    'labeled_field': STRUCTURAL_LABELED_FIELD_RE,
    'phone_id': STRUCTURAL_PHONE_ID_RE,
    'date_pattern': STRUCTURAL_DATE_RE,
    'currency': STRUCTURAL_CURRENCY_RE,
}
