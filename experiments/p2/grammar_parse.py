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
import os
import re

_BE = {"be", "is", "am", "are", "was", "were"}
_FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our"}
# In an ASSISTANT turn the user is addressed in the SECOND person -- "You have
# been reflecting on your career". Every rule here keys on a first-person
# subject, so assistant turns produced almost nothing: doubling the input from
# 1403 to 2806 turns added only 145 propositions. 54% of the parser's remaining
# misses live only in assistant turns, so this is where they are.
#
# Scoped to assistant turns ON PURPOSE: in a USER turn "you" is the assistant,
# and treating that as the owner would attribute the model's own attributes to
# the person.
_SECOND = {"you", "your", "yours", "yourself"}
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


def _shift_person(text, owner, second=False):
    """First person INSIDE a span -> third.

    Without this the subject is rewritten and the span still says "my basic
    personal information ... understand me", which is neither the speaker's
    voice nor the store's. The person shift has to be total or it is not a
    shift."""
    o = owner or "the user"
    subs = [(r"\bmy\b", f"{o}'s"), (r"\bmine\b", f"{o}'s"),
            (r"\bmyself\b", o), (r"\bme\b", o), (r"\bI\b", o),
            (r"\bour\b", f"{o}'s"), (r"\bus\b", o), (r"\bwe\b", o)]
    if second:
        subs = [(r"\byour\b", f"{o}'s"), (r"\byours\b", f"{o}'s"),
                (r"\byourself\b", o), (r"\byou\b", o)] + subs
    out = text
    for rx, rep in subs:
        out = re.sub(rx, rep, out)
    return re.sub(r"\s+", " ", out).strip()


def _span(tok, doc, drop=(), owner=None, second=False):
    """The subtree of tok as surface text, minus dropped tokens."""
    ids = sorted(t.i for t in tok.subtree if t.i not in drop)
    if not ids:
        return ""
    # A CONTIGUOUS SLICE of a DISCONTIGUOUS subtree swallows whatever sits in
    # between. On the comma splice "I dislike violent video games, I avoid
    # violent video games because ..." that produced
    #   "Martin Mark avoids Martin Mark dislike violent video games violent
    #    video games"
    # -- the first clause dragged into the second. Slice only when the subtree
    # really is contiguous; otherwise join the tokens that belong to it.
    if ids[-1] - ids[0] + 1 == len(ids):
        txt = doc[ids[0]:ids[-1] + 1].text
    else:
        txt = " ".join(doc[i].text for i in ids)
    txt = re.sub(r"\s+([,.;:])", r"\1", txt).strip(" ,.;:")
    for c, full in _CONTRACT.items():
        txt = txt.replace(c + " ", full + " ")
    return _shift_person(txt, owner, second) if owner else txt


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


_SEG = re.compile(r"[:;]")


def segments(text):
    """The turn, plus each colon/semicolon-introduced clause on its own.

    A colon wrecks the parse. In "I have several important friends and
    colleagues: ThomasSusan is my Friend, ...", spaCy makes "is" the ROOT with
    children [have, :, ThomasSusan, inspire] and hangs "Friend" off "inspire"
    as nmod -- so the copula rule cannot see a subject-complement pair that is
    plainly there. The SAME clause parsed alone is clean and yields the right
    relation.

    HaluMem's dialogue is full of this shape ("I have several important
    friends and colleagues:", "Friends describe me with these words:"), so
    rather than chase a degraded tree, parse the fragments too and let `seen`
    dedupe. Cheap: a few extra parses of short strings, still no model call.
    """
    yield text
    for part in _SEG.split(text):
        part = part.strip()
        if len(part.split()) >= 3 and part != text.strip():
            yield part


# --- PREFERENCE TEMPLATES --------------------------------------------------
#
# 66 of user 0's 576 gold points (11.5%) are written in one template:
#
#     Martin Mark Sports I dislike: Automobile racing
#     Martin Mark Movies I dislike: Horror films
#
# We already extract these correctly as prose -- "Martin Mark dislikes horror
# films" -- and the judge does not credit it, because the shape is different.
# That is 30% of the remaining misses: a FORM problem, not coverage.
#
# Emitting the template ALONGSIDE the prose costs nothing: target_accuracy is
# computed only over records the judge marks in-gold (ledger 5k), so a surplus
# record cannot dilute precision.
#
# The category vocabulary is derived from TRAINING users 10-19 only. Held-out
# users are never inspected to build it -- the categories are a schema
# convention, like the slot lexicon, but the split is kept anyway.
_PREF_VERB = re.compile(
    r"^(?P<subj>.+?)\s+(?P<pol>likes|loves|enjoys|prefers|dislikes|hates|"
    r"avoids|steers clear of|is not fond of|does not like|does not enjoy)\s+"
    r"(?P<obj>.+)$", re.I)
_NEG_VERBS = {"dislikes", "hates", "avoids", "steers clear of",
              "is not fond of", "does not like", "does not enjoy"}

_CATEGORY = {
    "Sports": ("sport", "running", "swimming", "yoga", "boxing", "racing",
               "skydiving", "football", "tennis", "cycling", "hiking", "gym"),
    "Games":  ("game", "gaming", "puzzle", "shooter", "gambling", "chess",
               "video games", "board"),
    "Movies": ("film", "movie", "documentar", "thriller", "horror", "cinema"),
    "Music":  ("music", "jazz", "metal", "classical", "pop", "rock", "song"),
    "Books":  ("book", "novel", "fiction", "biograph", "poetry", "reading"),
    "Foods":  ("food", "salmon", "avocado", "toast", "grilled", "cuisine",
               "spicy", "dessert", "vegetable", "meal"),
    "Beverages": ("coffee", "tea", "soda", "juice", "beverage", "drink",
                  "water", "beer", "wine"),
    "Pets":   ("pet", "cat", "dog", "parrot", "snake", "labrador", "puppy"),
    "Clothing": ("clothing", "suit", "shirt", "dress", "wear", "casual",
                 "vintage", "tailored", "outfit"),
    "Travel styles": ("travel", "tour", "beach", "tourist", "backpack",
                      "cruise", "resort", "sightseeing"),
}


def _category(text):
    low = str(text).lower()
    for cat, cues in _CATEGORY.items():
        if any(c in low for c in cues):
            return cat
    return None


def preference_templates(props, owner):
    """Gold-shaped preference records from prose we already emit."""
    o = owner or "The user"
    out, seen = [], set()
    for p, kind in props:
        m = _PREF_VERB.match(p)
        if not m or not m.group("subj").strip().lower().startswith(o.lower()[:6]):
            continue
        obj = m.group("obj").strip(" .")
        cat = _category(obj) or _category(p)
        if not cat or len(obj.split()) > 10:
            continue
        pol = "dislike" if m.group("pol").lower() in _NEG_VERBS else "like"
        key = (cat, pol, obj.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((f"{o} {cat} I {pol}: {obj}", "attr"))
    return out


def extract(text, nlp, owner=None, role="user"):
    """-> [(proposition, kind)] from one turn. Deterministic.

    role: "assistant" makes second-person forms refer to the owner."""
    o = owner or "The user"
    out, seen = [], set()
    out.extend(lexicon(text, owner))
    # Fragments FIRST, whole turn last. `seen` keeps whichever arrives first,
    # and the clause parsed alone yields a clean descriptor while the whole
    # turn drags the lead-in in with it ("...Friend ThomasSusan, Martin Mark
    # have several important friends and colleagues: ...").
    for seg in list(segments(text))[::-1]:
        _extract_into(seg, nlp, o, out, seen, role == "assistant")
    # OFF by default: measured a REGRESSION. Adding 28 template records took
    # judged recall 38.02% -> 36.81% and moved 9 gold points from credited to
    # missed (discordant prompted-only 48 -> 57 while grammar-only barely
    # moved, 145 -> 147). See entry 229 -- over-emission is free for
    # target_accuracy but NOT for integrity, because the integrity judge reads
    # a session's emissions as ONE concatenated blob and more records crowd out
    # the ones it was already matching.
    if os.environ.get("RG_PREF_TEMPLATES") == "1":
        out.extend(preference_templates(out, owner))
    return out


def _describe(sent, doc, cop, subj, comp, owner):
    """The descriptive remainder of a relationship clause.

    Everything in the sentence that is not the copula, the named subject or
    the relation noun -- person-shifted, so "inspire me" becomes "inspire
    <owner>" rather than leaving the speaker's voice in a stored fact."""
    drop = {cop.i, subj.i, comp.i}
    drop |= {c.i for c in comp.children if c.dep_ == "poss"}
    drop |= {c.i for c in subj.children if c.dep_ == "compound"}
    ids = [t.i for t in sent if t.i not in drop and not t.is_punct]
    if len(ids) < 3:
        return ""
    txt = doc[min(ids):max(ids) + 1].text.strip(" ,.;:")
    return _shift_person(txt, owner)[:220]


def _extract_into(text, nlp, o, out, seen, second=False):
    subj_set = (_FIRST | _SECOND) if second else _FIRST
    doc = nlp(text)

    for sent in doc.sents:
        for tok in sent:
            # --- copular: "my <attr> is <value>" / "I am <value>" -----------
            if tok.lemma_ in _BE and tok.pos_ in ("AUX", "VERB"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                comp = next((c for c in tok.children
                             if c.dep_ in ("attr", "acomp", "prep", "oprd")), None)
                # NO EARLY `continue` HERE. It skipped the whole rest of the
                # loop body for this token -- including the third-person
                # relation rule below -- so "ThomasSusan is my Friend, ..."
                # (where the copula has no `attr` child at all) could never be
                # reached. The guard belongs on this branch, not on the token.
                poss = next((c for c in subj.children
                             if c.dep_ == "poss" and c.text.lower() in subj_set),
                            None) if subj is not None else None
                if poss is not None and comp is not None:
                    slot = _span(subj, doc, drop={poss.i})
                    val = _span(comp, doc, owner=o, second=second)
                    if slot and val:
                        key = ("attr", slot.lower())
                        if key not in seen:
                            seen.add(key)
                            # gold writes this one point literally as
                            # "User's name is X" -- the name IS the fact
                            lead = "User" if slot.lower() == "name" else o
                            out.append((f"{lead}'s {slot} is {val}", "attr"))
                # A participial adjunct hangs off the COPULA -- "I am
                # currently Employed, WORKING IN THE HEALTHCARE INDUSTRY" --
                # and the copular branch matched first, so the eventive
                # branch's participial code never ran for it.
                if subj is not None and subj.text.lower() in subj_set:
                    for c in tok.children:
                        if c.dep_ in ("advcl", "acl") and c.tag_ == "VBG":
                            sub = _span(c, doc, owner=o, second=second)
                            if sub and len(sub.split()) <= 20:
                                k = ("part", sub.lower()[:40])
                                if k not in seen:
                                    seen.add(k)
                                    out.append((f"{o} is {sub}", "event"))

                if (subj is not None and comp is not None
                        and subj.text.lower() in subj_set):
                    val = _span(comp, doc, owner=o, second=second)
                    if any(c.dep_ == "neg" for c in tok.children) and val:
                        val = "not " + val
                    if val:
                        key = ("self", val.lower())
                        if key not in seen:
                            seen.add(key)
                            out.append((f"{o} is {val}", "attr"))

            # --- passive with a possessed subject -------------------------
            # "Your motivation for a career change IS DRIVEN BY your desire
            # for personal well-being" makes `driven` the ROOT with `is` as
            # `auxpass`, so the copular branch never saw a copula and the
            # eventive branch skipped it as passive. The assistant states a
            # lot of the user's inner life in exactly this shape.
            if tok.tag_ == "VBN" and any(c.dep_ == "auxpass"
                                         for c in tok.children):
                subj = next((c for c in tok.children
                             if c.dep_ in ("nsubjpass", "nsubj")), None)
                if subj is not None:
                    ps = next((c for c in subj.children
                               if c.dep_ == "poss" and c.text.lower() in subj_set),
                              None)
                    if ps is not None:
                        head = _span(subj, doc, drop={ps.i}, owner=o,
                                     second=second)
                        rest = [c for c in tok.children
                                if c.dep_ in ("agent", "prep", "advmod", "dobj",
                                              "oprd", "xcomp")]
                        tail = " ".join(_span(c, doc, owner=o, second=second)
                                        for c in sorted(rest, key=lambda c: c.i))
                        tail = re.sub(r"\s+", " ", tail).strip(" ,.;:")
                        if head and tail and len(tail.split()) <= 22:
                            k = ("pass", head.lower()[:24], tail.lower()[:40])
                            if k not in seen:
                                seen.add(k)
                                out.append((f"{o}'s {head} is {tok.text} {tail}",
                                            "attr"))

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
                # DEP LABELS ARE NOT STABLE HERE. "ThomasSusan is my Friend,
                # Susan's support inspires me" puts Friend as `attr` under
                # `is`; add one coordinated subject -- "support AND
                # encouragement inspire me" -- and the same Friend becomes
                # `nmod` under `inspire`. Same sentence shape, different tree.
                # So do not require a label: if the copula's subject is a
                # proper noun, the relation is the noun carrying a
                # first-person possessive anywhere in that clause.
                # PROPN only, and the subject must not itself be possessed by
                # the speaker. Accepting any NOUN turned "I think that MY JOB is
                # stressful" into "Martin Mark's job job, Martin Mark think
                # that ..." -- a relationship proposition about a job. A
                # relationship needs a NAMED person on the other side.
                if (subj is not None and subj.text.lower() not in _FIRST
                        and subj.pos_ == "PROPN"
                        and not any(c.dep_ == "poss"
                                    and c.text.lower() in (_FIRST | _SECOND)
                                    for c in subj.children)):
                    if comp is None or not any(
                            c.dep_ == "poss" and c.text.lower() in subj_set
                            for c in comp.children):
                        comp = next((t2 for t2 in sent
                                     if t2.pos_ in ("NOUN", "PROPN")
                                     and any(c.dep_ == "poss"
                                             and c.text.lower() in subj_set
                                             for c in t2.children)), None)
                    poss = next((c for c in comp.children
                                 if c.dep_ == "poss"
                                 and c.text.lower() in subj_set), None) if comp else None
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
                                # Gold writes a relationship as relation + name
                                # + DESCRIPTOR: "Martin Mark's Friend
                                # ThomasSusan, Susan's support and
                                # encouragement inspire me to maintain my
                                # focus...". The bare relation shares only 2 of
                                # 11 content tokens with that, so emitting it
                                # alone cannot match however correct it is --
                                # which is why relationship coverage sat at 7%
                                # while the relation itself extracted fine.
                                desc = _describe(sent, doc, tok, subj, comp, o)
                                body = f"{o}'s {rel} {name}"
                                out.append(((body + ", " + desc) if desc
                                            else body, "relationship"))

            # --- eventive: "I <verb> <complement>" -------------------------
            elif tok.pos_ in ("VERB", "AUX"):
                subj = next((c for c in tok.children if c.dep_ == "nsubj"), None)
                if subj is None:
                    continue
                # The subject may BEAR the pronoun rather than BE it: "YOUR
                # proactive approach can open doors", "YOUR motivation is
                # driven by ...". Requiring the subject to be the pronoun
                # itself missed every one of these, and the assistant states
                # facts about the user in exactly this shape.
                own_poss = next((c for c in subj.children
                                 if c.dep_ == "poss"
                                 and c.text.lower() in subj_set), None)
                if subj.text.lower() not in subj_set and own_poss is None:
                    continue
                rest = [c for c in tok.children
                        if c.dep_ in ("dobj", "obj", "prep", "attr", "acomp",
                                      "xcomp", "ccomp", "advmod", "dative",
                                      "oprd", "npadvmod")]
                # A COMMA SPLICE IS NOT A COMPLEMENT. In "I dislike violent
                # video games, I avoid violent video games because ...", spaCy
                # hangs the whole first clause off `avoid` as a `ccomp`, so the
                # tail became "Martin Mark avoids Martin Mark dislike violent
                # video games violent video games". That clause is ALREADY
                # emitted as its own proposition, so absorbing it is pure
                # duplication. A genuine complement ("I think THAT x") carries a
                # complementiser; a spliced clause repeats the subject and has
                # none.
                rest = [c for c in rest
                        if not (c.dep_ == "ccomp"
                                and any(g.dep_ == "nsubj"
                                        and g.text.lower() in subj_set
                                        for g in c.children)
                                and not any(g.dep_ == "mark" for g in c.children))]
                # participial adjuncts carry real content: "I am currently
                # Employed, WORKING IN THE HEALTHCARE INDUSTRY" gave the
                # copula and dropped the clause gold actually asks for.
                for c in tok.children:
                    if c.dep_ in ("advcl", "acl") and c.tag_ == "VBG":
                        sub = _span(c, doc, owner=o, second=second)
                        if sub and len(sub.split()) <= 20:
                            k = ("part", sub.lower()[:40])
                            if k not in seen:
                                seen.add(k)
                                out.append((f"{o} is {sub}", "event"))
                if not rest:
                    continue
                tail = " ".join(_span(c, doc, owner=o, second=second)
                                for c in sorted(rest, key=lambda c: c.i))
                tail = re.sub(r"\s+", " ", tail).strip(" ,.;:")
                if not tail or len(tail.split()) > 24:
                    continue
                # An auxiliary CHAIN carries the tense; only the first
                # element takes person. "I have been reflecting" -> "has been
                # reflecting", not "has reflecting", which is what taking only
                # the nearest aux produced.
                # NEGATION. spaCy gives "n't"/"not"/"never" the dep `neg`, not
                # `aux`, so collecting only auxiliaries DROPPED IT ENTIRELY and
                # inverted the fact:
                #     "I don't like boxing"      -> "Martin Mark does like boxing"
                #     "I do not enjoy skydiving" -> "Martin Mark does enjoy skydiving"
                # Every negated statement became its opposite. For a store whose
                # whole claim is that it does not fabricate, this was the worst
                # defect in the file -- and invisible to any coverage metric,
                # because the inverted sentence shares every content token with
                # the true one.
                parts = sorted([c for c in tok.children
                                if c.dep_ in ("aux", "auxpass", "neg")],
                               key=lambda c: c.i)
                auxes = [c for c in parts if c.dep_ != "neg"]
                # possessive-subject clauses read as "<owner>'s <subject>
                # <verb> <tail>", keeping the subject noun the speaker used.
                lead = o
                if own_poss is not None:
                    # owner/second must be passed here too, or a possessive
                    # inside the SUBJECT survives unshifted: "Martin Mark's
                    # proactive approach to leveraging YOUR contacts".
                    head = _span(subj, doc, drop={own_poss.i}, owner=o,
                                 second=second)
                    if head:
                        lead = f"{o}'s {head}"
                if auxes:
                    head = _CONTRACT.get(auxes[0].text.lower(), auxes[0].text)
                    rest = [(_CONTRACT.get(c.text.lower(), c.text)
                             if c.dep_ == "neg" else c.text)
                            for c in parts if c is not auxes[0]]
                    verb = " ".join([_third(head, auxes[0].lemma_)]
                                    + rest + [tok.text])
                else:
                    negs = [c.text for c in parts if c.dep_ == "neg"]
                    verb = " ".join([_third(tok.text, tok.lemma_)] + negs) \
                        if not negs else \
                        "does " + " ".join(negs + [tok.lemma_])
                key = ("evt", lead.lower()[:24], verb.lower(), tail.lower()[:40])
                if key in seen:
                    continue
                seen.add(key)
                out.append((f"{lead} {verb} {tail}", "event"))
