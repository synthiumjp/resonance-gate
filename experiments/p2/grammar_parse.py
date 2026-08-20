"""Extraction from a DEPENDENCY PARSE. The LLM's job is to check, not to write.

JP's architecture: grammar carries the structure, so extract from the
structure and let a model only verify or repair. Two independent lines support
it. Ours: S3c typed relations at 98.9% vs a 64.9% null by grammatical binding
alone (e203), and section 4b's record that every extraction win came from
deterministic post-processing while prompting is 0-for-3. And the outside
literature: MiniCheck-class verifiers at 770M match GPT-4-turbo on entailment
at ~400x lower cost -- checking is cheap, generating is not.

What the transformation actually is, on HaluMem's own data:

    "My name is Martin Mark, and I am a Male."
      -> User's name is Martin Mark
      -> Martin Mark's gender is Male

    "I shared anecdotes of resolving past conflicts through teamwork."
      -> Martin Mark shared anecdotes of resolving past conflicts through
         teamwork

Both are a PERSON SHIFT -- first person to third, with verb agreement. That is
morphology and dependency structure, not semantics.

The regex prototype (grammar_extract.py) reached 24-39% of COPULAR gold and
1.7% overall, and the reason is the denominator: only 29 of user 0's 576 gold
points are copular. e217 measured gold at 96% prose. So the narrow reading of
"structure" is not enough -- a parser is needed to reach the discursive
majority, which is what this file tests.

Deterministic. No model call anywhere in extraction. Every proposition carries
the turn it came from, which is the receipt.
"""
import re

_BE = {"be", "is", "am", "are", "was", "were"}
_FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our"}
_IRREG = {"have": "has", "do": "does", "go": "goes", "am": "is", "are": "is",
          "was": "was", "were": "was", "'m": "is", "'ve": "has"}


# already third-person singular, or person-invariant -- inflecting these again
# produced "ises looking" and "hases", which is the kind of error that makes
# otherwise-correct extraction unusable.
_ALREADY_3SG = {"is", "was", "has", "does", "goes", "had", "did", "were",
                "will", "would", "can", "could", "should", "may", "might",
                "must", "shall"}


def _third(verb_text, lemma):
    """First-person present -> third-person singular. Morphology, not lookup."""
    v = verb_text.lower()
    if v in _ALREADY_3SG:
        return v
    if v in _IRREG:
        return _IRREG[v]
    if lemma in _IRREG:
        return _IRREG[lemma]
    # past tense and modals are already person-invariant
    if v.endswith("ed") or v in ("will", "would", "can", "could", "should",
                                 "may", "might", "must", "shall", "had", "did"):
        return verb_text
    if v.endswith(("s", "sh", "ch", "x", "z")):
        return v + "es"
    if v.endswith("y") and len(v) > 1 and v[-2] not in "aeiou":
        return v[:-1] + "ies"
    return v + "s"


_CONTRACT = {"'d": "would", "'ll": "will", "'ve": "has", "'m": "is",
             "'re": "is", "n't": "not"}


def _shift_person(text, owner):
    """First person INSIDE a span -> third.

    Without this the subject is rewritten and the span still says "my basic
    personal information ... understand me", which is neither the speaker's
    voice nor the store's. The person shift has to be total or it is not a
    shift."""
    o = owner or "the user"
    subs = [(r"\bmy\b", f"{o}'s"), (r"\bmine\b", f"{o}'s"),
            (r"\bmyself\b", o), (r"\bme\b", o), (r"\bI\b", o),
            (r"\bour\b", f"{o}'s"), (r"\bus\b", o), (r"\bwe\b", o)]
    out = text
    for rx, rep in subs:
        out = re.sub(rx, rep, out)
    return re.sub(r"\s+", " ", out).strip()


def _span(tok, doc, drop=(), owner=None):
    """The subtree of tok as surface text, minus dropped tokens."""
    ids = sorted(t.i for t in tok.subtree if t.i not in drop)
    if not ids:
        return ""
    txt = doc[ids[0]:ids[-1] + 1].text.strip(" ,.;:")
    for c, full in _CONTRACT.items():
        txt = txt.replace(c + " ", full + " ")
    return _shift_person(txt, owner) if owner else txt


def extract(text, nlp, owner=None):
    """-> [(proposition, kind)] from one turn. Deterministic."""
    o = owner or "The user"
    out, seen = [], set()
    doc = nlp(text)

    for sent in doc.sents:
        for tok in sent:
            # --- copular: "my <attr> is <value>" / "I am <value>" -----------
            if tok.lemma_ in _BE and tok.pos_ in ("AUX", "VERB"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                comp = next((c for c in tok.children
                             if c.dep_ in ("attr", "acomp", "prep", "oprd")), None)
                if subj is None or comp is None:
                    continue
                poss = next((c for c in subj.children
                             if c.dep_ == "poss" and c.text.lower() in _FIRST), None)
                if poss is not None:
                    slot = _span(subj, doc, drop={poss.i})
                    val = _span(comp, doc, owner=o)
                    if slot and val:
                        key = ("attr", slot.lower())
                        if key not in seen:
                            seen.add(key)
                            # gold writes this one point literally as
                            # "User's name is X" -- the name IS the fact
                            lead = "User" if slot.lower() == "name" else o
                            out.append((f"{lead}'s {slot} is {val}", "attr"))
                elif subj.text.lower() in _FIRST:
                    val = _span(comp, doc, owner=o)
                    if val:
                        key = ("self", val.lower())
                        if key not in seen:
                            seen.add(key)
                            out.append((f"{o} is {val}", "attr"))

            # --- eventive: "I <verb> <complement>" -------------------------
            elif tok.pos_ in ("VERB", "AUX"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                if subj is None or subj.text.lower() not in _FIRST:
                    continue
                rest = [c for c in tok.children
                        if c.dep_ in ("dobj", "obj", "prep", "attr", "acomp",
                                      "xcomp", "ccomp", "advmod", "dative",
                                      "oprd", "npadvmod")]
                if not rest:
                    continue
                tail = " ".join(_span(c, doc, owner=o)
                                for c in sorted(rest, key=lambda c: c.i))
                tail = re.sub(r"\s+", " ", tail).strip(" ,.;:")
                if not tail or len(tail.split()) > 24:
                    continue
                # An auxiliary CHAIN carries the tense; only the first
                # element takes person. "I have been reflecting" -> "has been
                # reflecting", not "has reflecting", which is what taking only
                # the nearest aux produced.
                auxes = sorted([c for c in tok.children
                                if c.dep_ in ("aux", "auxpass")],
                               key=lambda c: c.i)
                if auxes:
                    head = _CONTRACT.get(auxes[0].text.lower(), auxes[0].text)
                    verb = " ".join([_third(head, auxes[0].lemma_)]
                                    + [a.text for a in auxes[1:]] + [tok.text])
                else:
                    verb = _third(tok.text, tok.lemma_)
                key = ("evt", verb.lower(), tail.lower()[:40])
                if key in seen:
                    continue
                seen.add(key)
                out.append((f"{o} {verb} {tail}", "event"))
    return out
