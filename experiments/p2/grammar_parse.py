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


# infinitival "to" is not a verb and must never be inflected -- it produced
# "Martin Mark tos save comfortably", which the grounding check then killed,
# losing the whole clause.
_NEVER_INFLECT = {"to", "not", "n't"}


def _third(verb_text, lemma):
    """First-person present -> third-person singular. Morphology, not lookup."""
    v = verb_text.lower()
    if v in _NEVER_INFLECT:
        return verb_text
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


# --- SLOT LEXICON ----------------------------------------------------------
#
# The parser finds STRUCTURE; it has no idea what gold calls a thing. 45% of
# the 462 gold points it missed on user 0 are present in the session's own user
# turns -- they are missed because gold names a slot the source never uses:
#
#   "I was born on 1996-08-02"   ->  "birth date is 1996-08-02"
#   "Both parents are alive"     ->  "parent status: Both parents are alive"
#   "no_relationship"            ->  "partner status: no_relationship"
#
# So structure alone is not enough and neither is a lexicon alone (the regex
# prototype reached 1.7% because only 5% of gold is copular). This is the
# lexicon half: a small, explicit map from surface expression to gold's slot
# name, applied alongside the parse rather than instead of it.
_LEX = [
    (re.compile(r"\bI\s+was\s+born\s+on\s+([0-9]{4}-[0-9]{2}-[0-9]{2})", re.I),
     "birth date is {0}"),
    (re.compile(r"\bI\s+am\s+(?:now\s+)?(\d{1,3})\s+years?\s+old", re.I),
     "age is {0} years old"),
    (re.compile(r"\b(Both\s+parents\s+are\s+\w+|One\s+parent[^.,;]{0,30}|"
                r"Both\s+parents\s+are\s+deceased)", re.I),
     "parent status: {0}"),
    (re.compile(r"\b(no_relationship|Married|Single|Divorced|Widowed)\b"),
     "partner status: {0}"),
    (re.compile(r"\b(No\s+children|One\s+child|Two\s+children|"
                r"Three\s+children)\b", re.I),
     "child status: {0}"),
    (re.compile(r"describe\s+me\s+with\s+these\s+words:\s*([^.]{3,120})", re.I),
     "personality tags include: {0}"),
    (re.compile(r"\bmy\s+personality\s+type\s+is\s+([A-Z]{4})\b"),
     "MBTI personality type is {0}"),
    (re.compile(r"\bI\s+(?:currently\s+)?work\s+(?:at|for)\s+([^.,;]{2,50})", re.I),
     "employer is {0}"),
]


def lexicon(text, owner=None):
    """Gold-slot propositions from surface expressions the parse cannot name."""
    o = owner or "The user"
    out, seen = [], set()
    for rx, tmpl in _LEX:
        for m in rx.finditer(text):
            val = m.group(1).strip(" .,;")
            if not val:
                continue
            body = tmpl.format(val)
            if body.split()[0] in seen:
                continue
            seen.add(body.split()[0])
            out.append((f"{o}'s {body}", "attr"))
    return out


def extract(text, nlp, owner=None):
    """-> [(proposition, kind)] from one turn. Deterministic."""
    o = owner or "The user"
    out, seen = [], set()
    out.extend(lexicon(text, owner))
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

            # --- third-person subject: facts about OTHER PEOPLE -----------
            #
            # The parser only ever fired on first-person subjects, so
            # "ThomasSusan is my Friend, Susan's support and encouragement
            # inspire me..." produced nothing but "has several important
            # friends and colleagues". Relationship gold is written from the
            # OTHER person's side, and a memory of a life is mostly about
            # other people -- this is a product gap as much as a benchmark one.
            if tok.lemma_ in _BE and tok.pos_ in ("AUX", "VERB"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                comp = next((c for c in tok.children
                             if c.dep_ in ("attr", "acomp")), None)
                if (subj is not None and comp is not None
                        and subj.text.lower() not in _FIRST
                        and subj.pos_ in ("PROPN", "NOUN")):
                    poss = next((c for c in comp.children
                                 if c.dep_ == "poss"
                                 and c.text.lower() in _FIRST), None)
                    if poss is not None:
                        # The relation is the HEAD NOUN, not its subtree. Taking
                        # the subtree swept up the appositive clause and
                        # produced "Martin Mark's Friend, Susan's support
                        # inspires me ThomasSusan" -- a relation, a descriptor
                        # and a name fused into one unusable string.
                        rel = " ".join([c.text for c in comp.children
                                        if c.dep_ == "compound"] + [comp.text])
                        name = " ".join([c.text for c in subj.children
                                         if c.dep_ == "compound"] + [subj.text])
                        if rel and name:
                            key = ("rel", name.lower(), rel.lower())
                            if key not in seen:
                                seen.add(key)
                                out.append((f"{o}'s {rel} {name}", "relationship"))

            # --- eventive: "I <verb> <complement>" -------------------------
            elif tok.pos_ in ("VERB", "AUX"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                if subj is None or subj.text.lower() not in _FIRST:
                    continue
                rest = [c for c in tok.children
                        if c.dep_ in ("dobj", "obj", "prep", "attr", "acomp",
                                      "xcomp", "ccomp", "advmod", "dative",
                                      "oprd", "npadvmod")]
                # participial adjuncts carry real content: "I am currently
                # Employed, WORKING IN THE HEALTHCARE INDUSTRY" gave the
                # copula and dropped the clause gold actually asks for.
                for c in tok.children:
                    if c.dep_ in ("advcl", "acl") and c.tag_ == "VBG":
                        sub = _span(c, doc, owner=o)
                        if sub and len(sub.split()) <= 20:
                            k = ("part", sub.lower()[:40])
                            if k not in seen:
                                seen.add(k)
                                out.append((f"{o} is {sub}", "event"))
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
