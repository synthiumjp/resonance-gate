"""p2 change-of-state extraction: the high-precision categorical-update path.

Categorical updates ("moved to Chicago" -> "moved back to the suburbs", "now
works at Google", "switched from Android to iPhone") are 39 of 78 LongMemEval
knowledge-updates and the numeric detector cannot touch them.

LINGUISTIC BASIS (change-of-state agent, this session; Vendler/Dowty/Levin,
some points textbook-but-UNVERIFIED-this-session). A change-of-state verb
lexically entails, via the BECOME operator, that the entity was PREVIOUSLY in
the complementary state. So "moved to X" ENTAILS the location changed; two
different goals of the same COS verb about the same subject are therefore a
reliable change WITHOUT reasoning about whether the two values are taxonomically
incompatible -- the verb supplies the exclusivity. This is the categorical
analogue of the exact-count rule (entry 44).

Deliberately HIGH-PRECISION and conservative. The second agent established that
BARE-VALUE exclusivity (two stative mentions, no COS verb, e.g. "lives in
Chicago" vs "the suburbs") is unreliable without a knowledge base -- embedding
cosine actively fails on it (co-hyponyms score highest), reliable co-hyponymy
needs supervision. So bare-value divergence is NOT handled here; only
language-marked change fires. Better to miss a categorical change than
false-alarm.

CONSTRUCTIONS:
  FROM-TO:  "<cos> from X to Y"  -> old=X, new=Y in one utterance (deterministic)
  USED-TO:  "used to <P>, now <Q>" / "used to <P>" -> marked cessation
  GOAL:     "<cos> to/at GOAL"   -> (subject, attribute, goal); two different
            goals across mentions = a change (the verb entails it)
SUPPRESSION: "still" / "not yet" assert continuation -> no COS reading.

No model call.
"""

import re

_SENT = re.compile(r"(?<=[.!?])\s+")
_SUPPRESS = re.compile(r"\b(still|not yet|haven'?t (?:moved|switched|changed|left))\b", re.I)

# ONE ordered list of (attribute, verb+goal-preposition) patterns. First match
# for a given verb span wins, so "moved to X" yields ONE triple, not three.
_COS_GOAL = [
    ("location", r"\bmoved?\s+back\s+to\b"),
    ("location", r"\b(?:moved?|moving|relocated?|relocating)\s+(?:to|into)\b"),
    ("location", r"\bnow\s+(?:live|living|based|staying)\s+(?:in|at)\b"),
    ("employer", r"\bnow\s+(?:work(?:ing)?|employed)\s+(?:at|for|with)\b"),
    ("employer", r"\b(?:started|joined)\s+(?:at|for|with)\s+"),
]
_COS_GOAL = [(a, re.compile(p, re.I)) for a, p in _COS_GOAL]

_FROM_TO = re.compile(
    r"\b(?:moved?|switched|changed|relocated?|went|upgraded|going)\s+"
    r"from\s+(.+?)\s+to\s+(.+?)(?:[.,;!?]|\s+(?:last|in|on|since|back)\b|$)", re.I)

_USED_TO = re.compile(r"\bused to\s+(.+?)(?:[,.;]|\s+but\b|$)(?:.*?\bnow\s+(.+?)(?:[.,;!?]|$))?", re.I)

_GOAL_STOP = {"a", "an", "the", "another", "new", "some", "there", "here",
              "that", "this", "my", "our"}
_NAME = re.compile(r"\b([A-Z][a-z]{2,})\b")
_NOT_NAME = {"By", "The", "That", "This", "Do", "Can", "Oh", "So", "And", "But",
             "She", "He", "They", "We", "My", "I"}


def _clean_value(v):
    v = v.strip(" .,!?\"'")
    words = v.split()
    while words and words[0].lower() in _GOAL_STOP:
        words = words[1:]
    # drop a trailing temporal/adverbial tail
    out = []
    for w in words[:6]:
        if w.lower() in ("again", "recently", "lately", "now", "last", "this", "since"):
            break
        out.append(w)
    return " ".join(out).strip()


def _subject(sent, verb_start):
    """Nearest genuine subject of the COS verb: a third-party NAME if one
    governs the clause (incl. 'Name who moved'), else the speaker. Pronoun
    'she/he' resolves to the nearest prior name in the sentence."""
    pre = sent[:verb_start]
    names = [n for n in _NAME.findall(pre) if n not in _NOT_NAME]
    # "she/he moved" -> nearest prior name
    if re.search(r"\b(she|he)\b\s*$", pre.strip()[-12:], re.I) and names:
        return names[-1]
    if names:
        return names[-1]                 # "Rachel who moved", "Rachel ... moved"
    if re.search(r"\b(i|my|we|our)\b", pre, re.I):
        return "I"
    if re.search(r"\b(she|he|they)\b", pre, re.I):
        return "they"                    # unresolved pronoun; kept but unscoped
    return None


def extract_cos(text):
    """(subject, attribute, value, role) tuples, role in {from,to}. Every tuple
    is a language-MARKED change (the construction entails it)."""
    out, seen = [], set()
    for sent in _SENT.split(text):
        if _SUPPRESS.search(sent):
            continue
        # from-X-to-Y (both values, deterministic)
        for m in _FROM_TO.finditer(sent):
            subj = _subject(sent, m.start()) or "I"
            for val, role in ((_clean_value(m.group(1)), "from"),
                              (_clean_value(m.group(2)), "to")):
                k = (subj.lower(), "cos", val.lower())
                if val and k not in seen:
                    seen.add(k); out.append((subj, "cos:change", val, role))
        # used to P (now Q)
        for m in _USED_TO.finditer(sent):
            subj = "I"
            old = _clean_value(m.group(1))
            new = _clean_value(m.group(2)) if m.group(2) else None
            for val, role in ((old, "from"), (new, "to")):
                if val:
                    k = (subj.lower(), "cos", val.lower())
                    if k not in seen:
                        seen.add(k); out.append((subj, "cos:change", val, role))
        # goal-only COS: first matching pattern per position wins
        for attr, rx in _COS_GOAL:
            for m in rx.finditer(sent):
                subj = _subject(sent, m.start())
                if not subj:
                    continue
                val = _clean_value(sent[m.end():].split(",")[0].split(" and ")[0]
                                   .split(" who ")[0])
                if not val or len(val) < 2:
                    continue
                k = (subj.lower(), attr, val.lower())
                # skip if this span already produced a value (pattern overlap)
                span_k = (subj.lower(), val.lower())
                if k in seen or span_k in {(s[0], s[2]) for s in
                                          [(x[0].lower(), x[1], x[2].lower()) for x in out]}:
                    continue
                seen.add(k); out.append((subj, f"cos:{attr}", val, "to"))
    return out
