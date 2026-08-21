"""Extraction from UNIVERSAL DEPENDENCIES (Stanza), replacing the spaCy rules.

Why the port. spaCy's `en_core_web_sm` scores **61.45% LAS on CHILDES
conversational data** against Stanza's 85.19% off-the-shelf (CAIT,
arXiv:2605.19718). Our text is chat dialogue, not newswire. So the rule
instability I have been patching all session -- `attr` flipping to `nmod` when
a subject is coordinated, a colon making the copula the ROOT, a comma splice
arriving as `ccomp` -- was not chiefly bad rules. It was a parse that is wrong
about a third of the time.

UD also happens to encode the distinctions this task needs, where the
ClearNLP-style scheme did not:

    copula      the PREDICATE is the head and `cop` is its dependent, so the
                head does not move when the subject is coordinated -- the
                exact failure that broke the relation rule
    parataxis   a comma splice is labelled as a separate clause instead of
                arriving as a complement, so the splice guard is unnecessary
    nmod:poss   possession is one label, so "your motivation" and "my job"
                are the same shape
    nsubj:pass  passives are marked, with the agent at `obl:agent`, so the
                passive is not a special case bolted on afterwards

Consequence: one clause walker replaces the copular / eventive / passive /
participial / third-person branches that were written separately in
grammar_parse.py for what is really one phenomenon -- a predicate with
arguments.

NEGATION IS NOT A DEPENDENCY LABEL IN UD. It is `advmod` whose lemma is
not/n't/never. The spaCy version keyed on dep `neg` and dropping that inverted
every negated fact (e228). Here it is read by lemma, and tested.

Deterministic. No model call. Stanza runs on CPU at ~0.16s/sentence.
"""
import re

NEG_LEMMAS = {"not", "n't", "never", "no", "nor", "neither"}
FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
SECOND = {"you", "your", "yours", "yourself", "yourselves"}
CLAUSE_DEPS = ("root", "parataxis", "conj", "advcl", "acl", "acl:relcl",
               "ccomp", "xcomp")
# Arguments only. `aux`/`cop` are realised in the verb phrase and `cc`/`mark`
# are function words, so including them put the auxiliary and the negation
# into the TAIL as well -- "Martin Mark does not like do n't boxing". And
# `conj`/`parataxis` are SEPARATE CLAUSES that the walker extracts in their
# own right, so absorbing them duplicates one clause into another, which is
# the same defect the spaCy version had with comma splices.
ARG_DEPS = ("obj", "iobj", "obl", "obl:agent", "xcomp", "ccomp", "advmod",
            "nmod", "case", "compound", "amod", "det", "nummod", "fixed",
            "flat", "advcl", "acl", "nmod:poss", "expl")
SEPARATE = ("conj", "parataxis", "cc")
IRREG = {"have": "has", "do": "does", "be": "is", "go": "goes"}
ALREADY_3SG = {"is", "was", "has", "does", "did", "had", "were", "will",
               "would", "can", "could", "should", "may", "might", "must"}
# Pronouns that the person shift rewrites to the owner's NAME. A verb whose
# subject is one of these therefore needs third-singular agreement, wherever
# in the span it sits -- see `_S.text`.
SHIFTED = {"i", "me", "we", "us"}
SHIFTED_2 = SHIFTED | {"you"}


def _third(word, lemma):
    w = word.lower()
    # A detached clitic ("I'd like" -> ["I", "'d"]) is not a word we can
    # inflect: appending -s to it produced "Martin Mark 'ds like". Stanza
    # gives the lemma, so agree THAT and let it print in full.
    if w.startswith("'") and lemma:
        word, w = lemma, lemma.lower()
    if lemma == "be" and w == "were":
        return "was"          # the subject is singular now
    if w in ALREADY_3SG or w in ("to", "not", "n't"):
        return word
    if lemma in IRREG:
        return IRREG[lemma]
    if w.endswith("ed") or w.endswith("s"):
        return word
    if w.endswith(("sh", "ch", "x", "z")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"


def _shift(text, owner, second):
    o = owner or "the user"
    subs = [(r"\bmy\b", f"{o}'s"), (r"\bmine\b", f"{o}'s"),
            (r"\bmyself\b", o), (r"\bme\b", o), (r"\bI\b", o),
            (r"\bour\b", f"{o}'s"), (r"\bus\b", o), (r"\bwe\b", o)]
    if second:
        subs = [(r"\byour\b", f"{o}'s"), (r"\byours\b", f"{o}'s"),
                (r"\byourself\b", o), (r"\byou\b", o)] + subs
    out = text
    for rx, rep in subs:
        out = re.sub(rx, rep, out, flags=re.I)
    return re.sub(r"\s+", " ", out).strip()


class _S:
    """Sentence view: id -> word, and head -> children."""

    def __init__(self, sent):
        self.w = {x.id: x for x in sent.words}
        self.kids = {}
        for x in sent.words:
            self.kids.setdefault(x.head, []).append(x)

    def children(self, word, deps=None):
        cs = self.kids.get(word.id, [])
        return [c for c in cs if deps is None or c.deprel in deps]

    def subtree(self, word, stop=()):
        out, stack = [], [word]
        while stack:
            n = stack.pop()
            if n.id in stop:
                continue
            out.append(n)
            stack.extend(self.kids.get(n.id, []))
        return sorted(out, key=lambda x: x.id)

    def text(self, word, stop=(), owner=None, second=False):
        toks = [t for t in self.subtree(word, stop) if t.upos != "PUNCT"]
        if not toks:
            return ""
        # The person shift is a string pass and cannot see that it has just
        # made a verb's subject singular, so "because I find" became
        # "because Martin Mark find". Agreement is decided HERE, where the
        # dependency is still visible: a verb whose own nsubj is a pronoun
        # the shift will rewrite. Verbs with no nsubj of their own (an
        # infinitive under xcomp, a participle) are left alone.
        shifted = SHIFTED_2 if second else SHIFTED
        parts = []
        for t in toks:
            txt = t.text
            if owner and t.upos in ("VERB", "AUX"):
                sub = next(iter(self.children(t, ("nsubj", "nsubj:pass"))),
                           None)
                if sub is not None and sub.text.lower() in shifted:
                    txt = _third(t.text, t.lemma)
            parts.append(txt)
        s = " ".join(parts)
        s = re.sub(r"\s+([',.;:])", r"\1", s).strip(" ,.;:")
        return _shift(s, owner, second) if owner else s


def _negated(s, head):
    return any(c.lemma.lower() in NEG_LEMMAS
               for c in s.children(head, ("advmod", "det")))


def _poss(s, word, allow):
    return next((c for c in s.children(word, ("nmod:poss",))
                 if c.text.lower() in allow), None)


def extract(text, nlp, owner=None, role="user"):
    """-> [(proposition, kind)]. Deterministic, no model call."""
    o = owner or "The user"
    second = role == "assistant"
    allow = (FIRST | SECOND) if second else FIRST
    out, seen = [], set()

    for sent in nlp(text).sentences:
        s = _S(sent)
        for head in sent.words:
            if head.deprel not in CLAUSE_DEPS:
                continue
            subj = next(iter(s.children(head, ("nsubj", "nsubj:pass"))), None)
            if subj is None:
                continue
            cop = next(iter(s.children(head, ("cop",))), None)
            neg = _negated(s, head)
            sp = _poss(s, subj, allow)
            is_self = subj.text.lower() in allow

            # ---- copular: the PREDICATE heads the clause, `cop` hangs off it
            if cop is not None:
                drop = {subj.id, cop.id}
                drop |= {c.id for c in s.children(head, SEPARATE)}
                drop |= {c.id for c in s.children(head, ("aux", "aux:pass"))}
                drop |= {c.id for c in s.children(head, ("advmod", "det"))
                         if c.lemma.lower() in NEG_LEMMAS}
                val = s.text(head, stop=drop, owner=o, second=second)
                if not val:
                    continue
                if sp is not None:                    # "my job is X"
                    slot = s.text(subj, stop={sp.id}, owner=o, second=second)
                    body = f"{o}'s {slot} is {'not ' if neg else ''}{val}"
                    kind = "attr"
                elif is_self:                          # "I am X"
                    body = f"{o} is {'not ' if neg else ''}{val}"
                    kind = "attr"
                elif subj.upos == "PROPN" and _poss(s, head, allow) is not None:
                    # "ThomasSusan is my Friend" -- the relation is the
                    # predicate noun, the named person is the subject
                    rel = head.text
                    desc = s.text(head, stop={subj.id, cop.id, head.id}
                                  | {c.id for c in s.children(head, ("nmod:poss",))},
                                  owner=o, second=second)
                    body = f"{o}'s {rel} {s.text(subj, owner=o, second=second)}"
                    if desc:
                        body += ", " + desc
                    kind = "relationship"
                else:
                    continue
            else:
                # ---- verbal, including passive: one path, not three
                if sp is None and not is_self:
                    continue
                args = [c for c in s.children(head)
                        if c.deprel in ARG_DEPS and c.id != head.id
                        and not (c.deprel in ("advmod", "det")
                                 and c.lemma.lower() in NEG_LEMMAS)]
                tail = " ".join(s.text(c, owner=o, second=second)
                                for c in sorted(args, key=lambda c: c.id))
                tail = re.sub(r"\s+", " ", tail).strip(" ,.;:")
                if not tail or len(tail.split()) > 24:
                    continue
                aux = [c for c in s.children(head, ("aux", "aux:pass"))]
                if aux:
                    verb = _third(aux[0].text, aux[0].lemma)
                    if neg:
                        verb += " not"
                    verb += " " + " ".join(
                        # same clitic problem as `_third`, one slot along
                        a.lemma if a.text.startswith("'") else a.text
                        for a in aux[1:] if a is not aux[0])
                    verb = verb.strip() + " " + head.text
                else:
                    verb = _third(head.text, head.lemma)
                    if neg:
                        verb = f"does not {head.lemma}"
                lead = (o if sp is None else
                        f"{o}'s {s.text(subj, stop={sp.id}, owner=o, second=second)}")
                body = f"{lead} {verb} {tail}"
                kind = "event"

            body = re.sub(r"\s+", " ", body).strip(" ,.;:")
            key = body.lower()[:90]
            if body and key not in seen:
                seen.add(key)
                out.append((body, kind))
    return out
