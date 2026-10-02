"""Subjectless fragments at the start of a user turn (2026-10-02).

People drop the subject in chat: "Still nursing at St Vincent's though",
"Vegetarian now, for about a year". The parser needs a subject, so these
produced nothing. A fragment that opens a user turn is about the speaker
unless the assistant has just asked about someone else ("What does your
sister do?" -- "Nursing at St Vincent's"), so the rule is skipped then.

Two shapes only, both checked on the parse:
  * an -ing verb with a noun argument: "Loving the new job", "Training for
    a marathon". "Looking good", "Getting there", "Working on it" have no
    noun argument (or only a pronoun) and are left alone;
  * an adjective from a closed list of states: "Vegetarian now", "Pregnant!".
The fragment is parsed as "I'm <fragment>"; the record keeps the original
sentence as its source.
"""
import os
import re

STATE_ADJ = {"vegetarian", "vegan", "pescatarian", "pregnant", "single",
             "married", "divorced", "engaged", "separated", "widowed",
             "retired", "unemployed", "sober", "allergic", "freelance",
             "self-employed"}
_ARG_DEPS = ("obj", "obl", "iobj")
_FIRST_WORD = re.compile(r"^\W*(?:still|now|currently|just|recently|mostly|"
                         r"finally|also|actually)?\s*([A-Za-z-]+)", re.I)


def _third_party_question(prev):
    """Was the assistant's last question about someone other than the user?
    A question with "you" in it is about the user; one naming a person,
    "your <someone>", or he/she/they is not; anything else ("Any news?")
    is taken as open."""
    if not prev:
        return False
    qs = [q for q in re.split(r"(?<=[.!?])\s+", prev.strip()) if q.endswith("?")]
    if not qs:
        return False
    q = qs[-1]
    if re.search(r"\byou\b", q, re.I):
        return False
    # "How is Sam?", "What does your sister do?", "Is she still there?"
    return bool(re.search(r"\byour\s+\w+|\b(he|she|they|him|her|them|his|"
                          r"their)\b", q, re.I)
                or re.search(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+", q))


def _candidate(sentence):
    m = _FIRST_WORD.match(sentence)
    if not m:
        return False
    w = m.group(1).lower()
    return w.endswith("ing") or w in STATE_ADJ


def rewrite(text, nlp, prev=None):
    """-> (text to parse, {rewritten sentence: original}) -- unchanged text
    and an empty map when the turn does not open with an accepted
    fragment."""
    if os.environ.get("RG_FRAGMENTS") == "0":
        return text, {}
    first = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    head = first[0]
    if not _candidate(head) or _third_party_question(prev):
        return text, {}
    new = "I'm " + head[0].lower() + head[1:]
    # Judged on the rewritten sentence: without a subject Stanza often tags
    # the -ing word as a noun ("Nursing at St Vincent's" -> NN root).
    words = nlp(new).sentences[0].words
    root = next((w for w in words if w.deprel == "root"), None)
    if root is None:
        return text, {}
    subj = [w for w in words if w.head == root.id and w.deprel.startswith("nsubj")]
    if len(subj) != 1 or subj[0].text != "I":
        return text, {}
    if root.xpos == "VBG":
        ok = any(w.head == root.id and w.deprel in _ARG_DEPS
                 and w.upos in ("NOUN", "PROPN") for w in words)
    else:
        ok = root.text.lower() in STATE_ADJ
    if not ok:
        return text, {}
    rest = first[1] if len(first) > 1 else ""
    return (new + (" " + rest if rest else "")), {new: head}
