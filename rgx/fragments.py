"""Subjectless fragments at the start of a user turn (2026-10-02).

People drop the subject in chat: "Still nursing at St Vincent's though",
"Vegetarian now, for about a year". The parser needs a subject, so these
produced nothing. A fragment that opens a user turn is about the speaker
only when it opens the conversation or answers a question put to the user
that mentions nobody else ("What do you do?"). After "What does your sister
do?", "How's the family?" or a draft about someone else it is skipped.

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


_THIRD = re.compile(r"\byour\s+(?!own\b)\w+|\b(he|she|they|him|her|them|his|"
                    r"their|the (?:family|kids?|baby|dog|cat|team|boss|"
                    r"landlord|doctors?|new hire|character|story|draft))\b",
                    re.I)
_NAME = re.compile(r"(?<!^)(?<![.!?]\s)\b[A-Z][a-z]+")


def _about_user(prev):
    """Is a fragment answering `prev` about the user?

    Review 2026-10-02: a fragment answers whatever was just raised, and
    "How's the family?", "What's the dog up to?", "Tell me about your wife."
    or a draft bio for someone else all raise someone else. So the rule
    fires only at the start of a conversation, or right after a question
    put to the user ("What do you do?") that mentions nobody else."""
    if not prev:
        return True
    sents = re.split(r"(?<=[.!?])\s+", prev.strip())
    if _THIRD.search(prev) or any(_NAME.search(x) for x in sents[-2:]):
        return False
    qs = [q for q in sents if q.endswith("?")]
    return bool(qs) and bool(re.search(r"\byou\b", qs[-1], re.I))


_DENIAL = re.compile(r"^\W*(no\b|nope|not\b|nah|just kidding|kidding|jk\b|"
                     r"joking|lol\b|haha)", re.I)


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
    rest = first[1] if len(first) > 1 else ""
    if not _candidate(head) or not _about_user(prev):
        return text, {}
    # "Married? No." is a question; "Pregnant. Just kidding." takes it back;
    # "Reading: War and Peace" is a heading; "Sending you the file" is about
    # this conversation, not the user's life.
    if (head.rstrip().endswith("?") or ":" in head or _DENIAL.match(rest)
            or re.search(r"\byou(r)?\b", head, re.I)):
        return text, {}
    # A fragment has no finite verb and no subject of its own. "Pregnant
    # women should avoid sushi", "Married with Children is my favourite
    # show", "Stealing cars is wrong" all do -- they are sentences.
    orig = nlp(head).sentences[0].words
    if any(w.deprel.startswith(("nsubj", "csubj", "expl"))
           or (w.upos in ("VERB", "AUX") and "VerbForm=Fin" in (w.feats or ""))
           for w in orig):
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
    # "Nursing at St Vincent's, my sister." -- the nurse is the sister
    if any(w.deprel in ("appos", "dislocated", "vocative", "parataxis", "list")
           for w in words):
        return text, {}
    if root.xpos == "VBG":
        ok = any(w.head == root.id and w.deprel in _ARG_DEPS
                 and w.upos in ("NOUN", "PROPN") for w in words)
    else:
        ok = root.text.lower() in STATE_ADJ
    if not ok:
        return text, {}
    return (new + (" " + rest if rest else "")), {new: head}
