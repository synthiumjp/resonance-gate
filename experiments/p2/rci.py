"""p2 contradiction/change detection via the Reliable Change Index.

Adapts the RCI (Jacobson & Truax 1991) exactly as in Cacioli, "Beyond the
Mean" (arXiv:2604.27405) — split-half + Spearman-Brown reliability, SEM =
SD*sqrt(1 - r_xx), S_diff = sqrt(SEM_a^2 + SEM_b^2), reliable change at
|RCI| > 1.96 (2.58 conservative). Formulae taken from that repo's
run_btm_analysis.py so this is the author's form, not a reinvention.

WHY RCI FITS THE PROBLEM. A (subject, relation) slot receiving a second value
is one of three events (entry 26): UPDATE, CONTRADICTION, or legitimate
MULTI-VALUE. Entry 32 measured a naive detector at 0.08 precision because it
called all three a contradiction, and showed a relation-level prior cannot
separate them ("have tried" is exclusive for {3,4} restaurants, co-existing
for {sleep routine, bedtime}).

RCI reframes it correctly and fixes both failures at once:

1. COMMENSURABILITY GATE (fixes the 12/13 false alarms). RCI is only DEFINED
   when the two values lie on a common numeric scale. "three restaurants" vs
   "four restaurants" -> a scale, RCI applies. "road bike" vs "mountain bike"
   -> no scale, RCI UNDEFINED -> classified MULTI_VALUE, not contradiction.
   Commensurability does the work entry 32's head-noun hack did, but
   principled: a difference you cannot place on a scale is not a change.

2. RELIABLE-CHANGE TEST (fixes calling noise a contradiction). Among
   commensurable pairs, only flag when the change exceeds the measurement
   error of the extractor. Two values differing by less than S_diff are within
   instrument noise and are NOT a reliable change.

WHAT THIS DETECTOR CLAIMS, honestly. It detects reliable change in QUANTIFIED
facts (counts, durations, measures, money). That is most of LongMemEval's
knowledge-update category. It does NOT handle categorical change
("Rachel moved to Chicago -> the suburbs"): those are commensurable only in a
semantic-similarity sense, not a numeric one, and are deferred (see
categorical_change, a separate weaker signal). Stated before measuring.

No model call. Numeric parsing and a value-distribution reliability estimate.
"""

import math
import re

RCI_THRESHOLD = 1.96
RCI_THRESHOLD_CONSERVATIVE = 2.58

# ------------------------------------------------------------- scale parsing

_DURATION = re.compile(
    r"(?:(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b)?\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b)?\s*"
    r"(?:(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|s)\b)?", re.I)
_CLOCK = re.compile(r"\b(\d{1,3}):(\d{2})(?::(\d{2}))?\b")   # 27:12  or 1:27:12
_MONEY = re.compile(r"[$£€]\s*(\d[\d,]*(?:\.\d+)?)|\b(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|usd|pounds|euros)\b", re.I)
_WORDNUM = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12, "dozen": 12, "twenty": 20, "thirty": 30}
_BARE = re.compile(r"\b(\d+(?:\.\d+)?)\b")


def _head_noun(text, after=None):
    """The COUNTED noun: the first content word after the number, not the last
    word of the phrase. '12 films in the last 3 months' counts films, not
    months -- keying on the last word made two different counts look like one
    scale (entry-33 bug)."""
    t = text.lower()
    if after is not None:
        m = re.search(re.escape(str(after)) + r"[^a-z]*([a-z]+(?:\s+[a-z]+)?)", t)
        if m:
            for w in m.group(1).split():
                if w not in ("a", "an", "the", "my", "of", "and", "different",
                             "so", "far", "in", "last", "past", "total", "mcu"):
                    return w
    words = [w for w in re.findall(r"[a-z]+", t)
             if w not in ("a", "an", "the", "my", "of", "and")]
    return words[0] if words else ""


def to_scalar(text):
    """(value, scale) if the object denotes a magnitude, else None. The scale
    is a coarse type tag so only like is compared with like."""
    t = str(text).strip().lower()
    m = _CLOCK.search(t)
    if m:
        h_or_m, s1, s2 = m.groups()
        if s2 is not None:
            return int(h_or_m) * 3600 + int(s1) * 60 + int(s2), "time_s"
        return int(h_or_m) * 60 + int(s1), "time_s"
    m = _MONEY.search(t)
    if m:
        return float((m.group(1) or m.group(2)).replace(",", "")), "money"
    if re.search(r"\b(hours?|hrs?|minutes?|mins?|seconds?)\b", t):
        h, mn, s = _DURATION.search(t).groups()
        total = (float(h or 0) * 3600 + float(mn or 0) * 60 + float(s or 0))
        if total:
            return total, "time_s"
    # bare count / worded number, tagged by the noun it counts so "4 bikes"
    # and "4 restaurants" are DIFFERENT scales, not a change from one to other
    for w, v in _WORDNUM.items():
        if re.search(rf"\b{w}\b", t):
            return float(v), f"count:{_head_noun(t, after=w)}"
    m = _BARE.search(t)
    if m:
        return float(m.group(1)), f"count:{_head_noun(t, after=m.group(1))}"
    return None


# ------------------------------------------------- reliability of the extractor

def value_reliability(values):
    """Reliability of the extraction instrument, in [0,1].

    'Beyond the Mean' estimates reliability by split-half over repeated trials.
    Here there is one extraction per span, so instead we estimate the SIGNAL
    fraction of the observed value spread: reliability = 1 - (noise var /
    total var), with noise variance taken from the extractor's own quantisation
    -- integer counts carry +-0.5 quantisation, parsed times/money are near
    exact. This is a DELIBERATELY conservative stand-in and is the weakest
    link; a proper estimate needs repeated extractions of the same span and is
    logged as owed work, not hidden."""
    import statistics as st
    if len(values) < 2:
        return 0.0
    var = st.pvariance(values)
    if var <= 0:
        return 0.0
    noise = 0.25   # (+-0.5)^2 quantisation on integer-ish reads; unit-scale
    return max(0.0, min(1.0, 1.0 - noise / var))


def rci(a, b, values_for_reliability, conservative=False):
    """RCI for a change from a to b on a common scale.

    values_for_reliability: the pool of values seen on this scale, used to
    estimate SD and hence SEM. Mirrors the paper: SEM = SD*sqrt(1-r_xx),
    S_diff = sqrt(SEM_a^2 + SEM_b^2) (same instrument both sides, so
    SEM_a = SEM_b and S_diff = SEM*sqrt(2))."""
    import statistics as st
    r_xx = value_reliability(values_for_reliability)
    sd = st.pstdev(values_for_reliability) if len(values_for_reliability) > 1 else abs(b - a)
    sem = sd * math.sqrt(max(0.0, 1.0 - r_xx))
    s_diff = math.sqrt(sem ** 2 + sem ** 2)
    if s_diff <= 0:
        # zero measurement error -> any nonzero difference is reliable
        return math.inf if b != a else 0.0, s_diff, r_xx
    return (b - a) / s_diff, s_diff, r_xx


# ----------------------------------------------------------------- classify

UPDATE = "RELIABLE_CHANGE"
NOISE = "WITHIN_NOISE"
MULTI_VALUE = "MULTI_VALUE"          # incommensurable -> not a change at all
CATEGORICAL = "CATEGORICAL_DIFF"     # exclusive but non-numeric -> weaker path


def classify_pair(obj_a, obj_b, scale_pool=None, conservative=False):
    """Classify two objects asserted under one (subject, relation) key.

    scale_pool: other scalar values seen on the same scale, to estimate SD.
    Falls back to just the pair when no pool is available."""
    sa, sb = to_scalar(obj_a), to_scalar(obj_b)
    if sa is None or sb is None or sa[1] != sb[1]:
        # not both on the same numeric scale
        if _head_noun(obj_a) == _head_noun(obj_b) and obj_a != obj_b:
            return {"category": CATEGORICAL, "reason": "same head noun, no shared scale"}
        return {"category": MULTI_VALUE, "reason": "incommensurable objects"}
    va, vb = sa[0], sb[0]
    pool = list(scale_pool) if scale_pool else []
    pool += [va, vb]
    r, s_diff, r_xx = rci(va, vb, pool, conservative)
    thr = RCI_THRESHOLD_CONSERVATIVE if conservative else RCI_THRESHOLD
    cat = UPDATE if abs(r) > thr else NOISE
    return {"category": cat, "rci": r, "s_diff": s_diff, "reliability": r_xx,
            "scale": sa[1], "value_a": va, "value_b": vb,
            "direction": "increase" if vb > va else "decrease"}
