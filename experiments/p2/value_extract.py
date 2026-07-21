"""p2 value-anchored extraction: a targeted, model-free second pass for the
COMPARISON path, aimed at the facts knowledge-updates are actually about.

Entry 41's dominant recall miss: the value-bearing side of an update often is
not produced by the 3B extractor -- "I've put in 10-12 hours", "using my Fitbit
for 9 months", "on page 220", "my personal best of 25:50". Measured this
session: 26/39 update instances have the answer value in no extracted triple,
though the value IS in the text.

These share a shape: a SPEAKER-anchored predication ending in a MAGNITUDE.
Updates are almost always about a countable/measurable attribute of the user,
so a pass that finds "<speaker thing> <relation> <value>" has high leverage and
stays model-free. It ADDS candidates to the COMPARISON path only (never the
assertion path), so it cannot lower assertion precision, and it fires only on
speaker-scoped subjects so it does not reintroduce topic junk.

DESIGN: two steps, not spliced regexes (the spliced version mis-grabbed numbers
and truncated objects). 1) find value spans. 2) anchor each to the nearest
preceding speaker subject and take the connecting words as the relation.

No model call.
"""

import re

# a VALUE the RCI scale parser can place. Ordered so multi-token units win over
# a bare number ("9 months" beats the "3" in "Charge 3").
_VALUE_ALTS = [
    r"\$\s?\d[\d,]*(?:\.\d+)?",                                  # $350,000
    r"\d{1,3}:\d{2}(?::\d{2})?",                                 # 27:12
    r"\d+\s*-\s*\d+\s*(?:hours?|hrs?|minutes?|mins?|miles?|pages?)",  # 10-12 hours
    r"\d+\s*(?:hours?|hrs?|minutes?|mins?|seconds?|months?|weeks?|days?|"
    r"years?|miles?|km|pounds?|kg|times?|stars?|pages?|engineers?|sessions?)",
    r"(?:page|chapter|level|session|episode)\s+\d+",             # page 220
    r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|forty|fifty)\s+[a-z]{3,}",                   # four restaurants
    r"\d+\s+[a-z]{3,}",                                          # 17 postcards
]
_VALUE = re.compile(r"(" + "|".join(_VALUE_ALTS) + r")(?![\d,])", re.I)

# speaker anchor: "I", "my <NP>", within a short window before the value
_ANCHOR = re.compile(
    r"\b(my (?:[a-z][a-z'-]* ){0,4}[a-z][a-z'-]*|I)\b", re.I)

_REL_STOP = {"a", "an", "the", "been", "also", "really", "actually", "just",
             "now", "so", "far", "already", "still", "currently", "of", "to",
             "for", "with", "and", "that", "which", "is", "was", "am", "are",
             "ve", "m", "s", "on", "at", "in", "this", "time", "around"}


def _relation(between):
    """The connecting words between subject and value -> a short relation."""
    words = [w for w in re.findall(r"[a-z]+", between.lower())
             if w not in _REL_STOP]
    return " ".join(words[:3]) if words else "is"


def extract_values(text, window=60):
    """Speaker-anchored (subject, relation, value) triples. Additive, deduped.
    For each value, take the NEAREST speaker anchor within `window` chars before
    it; the words in between become the relation."""
    out, seen = [], set()
    for vm in _VALUE.finditer(text):
        val = vm.group(1).strip()
        vstart = vm.start()
        pre = text[max(0, vstart - window):vstart]
        anchors = list(_ANCHOR.finditer(pre))
        if not anchors:
            continue
        a = anchors[-1]                       # nearest preceding anchor
        subj = a.group(1)
        subj = "I" if subj.lower() == "i" else subj.lower()
        between = pre[a.end():]
        rel = _relation(between)
        # a "my <NP>" subject usually already names the attribute; relation "is"
        if subj.startswith("my ") and rel in ("is", ""):
            rel = "is"
        key = (subj.lower(), rel, val.lower())
        if key in seen:
            continue
        seen.add(key)
        # a definite-description ("my <NP>") value fact is PRESUPPOSED and
        # projects through matrix-clause modality (hedge/future/question), so
        # the comparison path may keep it despite a FUTURE veto.
        presupposed = subj.lower().startswith("my ")
        out.append((subj, rel, val, presupposed))
    return out
