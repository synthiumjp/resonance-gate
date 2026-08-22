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
# "not only ... but also" is emphasis on the SECOND conjunct, not polarity on
# the first -- e240. "I am not only enhancing X" inverted to "is not
# enhancing X", the worst class of defect here: the record states the
# opposite of what was said, and shares every content word with the truth.
NOT_ONLY = {"only", "just", "merely", "simply"}
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
# D (e240): a record still carrying one of these, in an ASSISTANT turn, is
# the assistant talking about itself -- `_shift` no longer rewrites first
# person there (see below), so this is the safety net for whatever slips
# through some other path (an embedded clause, a whole-clause render).
_FIRST_RESIDUE = re.compile(r"\b(?:I|me|my|we|us|our)\b")


def _third(word, lemma, feats=None):
    w = word.lower()
    # Past tense is already agreement-neutral. The surface test below
    # (`endswith("ed")`) only catches the REGULAR ones, so "I said" became
    # "Martin Mark saids" and "I told" became "tolds" -- shipped in 0.1.0.
    # UD marks the tense; read it rather than guessing from the spelling.
    if lemma == "be" and w == "were":
        return "was"          # the subject is singular now; past or not
    if feats:
        # e238: the OLD guard was `endswith("ed") or endswith("s")`, a
        # spelling test that misfired on ordinary present-tense verbs that
        # happen to end that way -- "need", "focus", "discuss", "address",
        # "process", "assess" all fell through UNINFLECTED ("Martin Mark
        # need to..."). Stanza already labels tense/aspect/agreement; read
        # THAT instead of guessing from the letters. Kept as a fallback,
        # below, only for the rare token with no feats at all.
        if "Tense=Past" in feats or "VerbForm=Part" in feats:
            return word
        if "Person=3" in feats and "Number=Sing" in feats:
            return word       # already third-singular; nothing to do
    # A detached clitic ("I'd like" -> ["I", "'d"]) is not a word we can
    # inflect: appending -s to it produced "Martin Mark 'ds like". Stanza
    # gives the lemma, so agree THAT and let it print in full.
    if w.startswith("'") and lemma:
        word, w = lemma, lemma.lower()
    if w in ALREADY_3SG or w in ("to", "not", "n't"):
        return word
    if lemma in IRREG:
        return IRREG[lemma]
    if feats is None and (w.endswith("ed") or w.endswith("s")):
        return word
    # e238: this branch was dead before -- the old spelling guard above
    # ("ed"/"s") returned first for every word that could ever reach it, so
    # "focus" and "go" never got their -es. "s" and "o" added: "focuses",
    # "goes" (though "go" is also in IRREG above and never gets here).
    if w.endswith(("sh", "ch", "x", "z", "s", "o")):
        return w + "es"
    if w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        return w[:-1] + "ies"
    return w + "s"


def _shift(text, owner, second):
    o = owner or "the user"
    # D (e240): the assistant's own "I" is not the user's. Assistant-turn
    # records used to run BOTH substitution lists, so "I think X" became
    # "Martin Mark thinks X" -- the assistant's opinion, stored as the
    # user's. In an assistant turn only the SECOND-person pronouns refer to
    # the user; first person is the assistant, and is left alone (a record
    # that still carries it is dropped downstream, in `extract_keyed`).
    if second:
        subs = [(r"\byour\b", f"{o}'s"), (r"\byours\b", f"{o}'s"),
                (r"\byourself\b", o), (r"\byou\b", o)]
    else:
        subs = [(r"\bmy\b", f"{o}'s"), (r"\bmine\b", f"{o}'s"),
                (r"\bmyself\b", o), (r"\bme\b", o), (r"\bI\b", o),
                (r"\bour\b", f"{o}'s"), (r"\bus\b", o), (r"\bwe\b", o)]
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

    def clause_span(self, word):
        """Like `subtree`, but does not cross into a coordinate/parataxis
        child -- those are SEPARATE clauses (see `SEPARATE`), so descending
        into one would count the other clause's tokens as this clause's own
        (e240, used by the third-party-owner test in `extract_keyed`)."""
        out, stack = [], [word]
        while stack:
            n = stack.pop()
            out.append(n)
            for c in self.kids.get(n.id, []):
                if c.deprel not in SEPARATE:
                    stack.append(c)
        return out

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
                # An auxiliary carries the finiteness, so the verb under it
                # stays bare: "how I might measure" must not become "might
                # measures". The aux itself is agreed if it needs it, and
                # every modal is already third-singular.
                aux = self.children(t, ("aux", "aux:pass"))
                if sub is not None and not aux and sub.text.lower() in shifted:
                    txt = _third(t.text, t.lemma, t.feats)
            parts.append(txt)
        s = " ".join(parts)
        s = re.sub(r"\s+([',.;:])", r"\1", s).strip(" ,.;:")
        return _shift(s, owner, second) if owner else s


def _negated(s, head):
    """-> (is_negated, drop_ids). NEGATION IS NOT A DEPENDENCY LABEL IN UD; it
    is `advmod`/`det` whose lemma is not/n't/never/... (e228). But "not" is
    not always negation: "not only enhancing X but also contributing to Y"
    inverted to "is not enhancing X" (e240) -- worse than a missed record,
    because it states the opposite of what was said. A "not" immediately
    followed (by id) by a focus particle ("only"/"just"/"merely"/"simply")
    is emphasis, not polarity; both tokens are then excluded from the
    rendered span so the record reads "is enhancing X", not "is not
    enhancing X" or "is only enhancing X".
    """
    neg, drop = False, set()
    for c in s.children(head, ("advmod", "det")):
        if c.lemma.lower() not in NEG_LEMMAS:
            continue
        drop.add(c.id)
        nxt = s.w.get(c.id + 1)
        if nxt is not None and nxt.lemma.lower() in NOT_ONLY:
            drop.add(nxt.id)
        else:
            neg = True
    return neg, drop


def _fronted(s, head, subj):
    """-> (drop_ids, tail_children). B (e240): a modifier UD attaches BEFORE
    the subject still gets rendered after the verb, because `subtree` walks
    by id -- "Interestingly, I was curious" became "is Interestingly
    curious", and "By integrating X, I am enhancing Y" became "is enhancing
    By integrating X Y". Two different fixes for two different things:

      a sentence-initial DISCOURSE adverb (advmod, id before the subject's)
          carries no content for a memory record, so it is dropped outright
          -- "Interestingly", "However", "Additionally".
      a substantive pre-subject CLAUSE (advcl/obl/nmod, id before the
          subject's) is kept, but moved to the record's end in its original
          relative order, so "By integrating eco-friendly practices..."
          lands after the predicate instead of splitting it in two.

    A post-subject adverb ("was ALSO curious") is already in a sane position
    and is untouched.
    """
    drop_ids, tail = set(), []
    for c in s.children(head, ("advmod",)):
        if c.id < subj.id:
            drop_ids.add(c.id)
    for c in s.children(head, ("advcl", "obl", "nmod")):
        if c.id < subj.id:
            drop_ids.add(c.id)
            tail.append(c)
    return drop_ids, sorted(tail, key=lambda c: c.id)


def _interrogative(s, head, subj, is_question):
    """A clause that ASKS is not a clause that ASSERTS.

    The parser found a subject and a verb in "What kind of personality do you
    have?" and emitted "Martin Mark does have What kind of personality" -- a
    claim nobody made. ~12% of every record on users 0 and 1 (e235).

    Decided per CLAUSE, not per sentence, so a presupposition survives the
    question that carries it: in "Since you moved to Albi, how are you
    settling in?" the `advcl` is not inverted and still yields "Martin Mark
    moved to Albi".

    Three signals, each read off a real UD parse:
      * the clause head IS the wh-word   -- "What are your life goals?"
        (root=What, PronType=Int, with `goals` as its nsubj and a cop)
      * the SUBJECT is the wh-word       -- "Who told you that?"
      * subject-auxiliary inversion      -- "do you have", "Can you tell",
        "are you considering": the first aux/cop precedes the nsubj. Only
        trusted inside a sentence that ends in "?", because declarative
        fronting ("Never have I been so sure") inverts too.
    """
    if "PronType=Int" in (head.feats or "") or "PronType=Int" in (subj.feats or ""):
        return True
    if is_question:
        av = s.children(head, ("aux", "aux:pass", "cop"))
        if av and min(a.id for a in av) < subj.id:
            return True
    return False


def _ancestor_interrogative(s, head, is_question):
    """G (e237): a ccomp/xcomp under an interrogative matrix inherits the
    question. "do you THINK you'll take" asks about the thinking, so its
    complement "you'll take What steps" is not an assertion either, even
    though the complement clause itself shows no subject-aux inversion --
    that inversion happened one clause up, on "think"."""
    node = head
    while node.deprel in ("ccomp", "xcomp"):
        parent = s.w.get(node.head)
        if parent is None:
            return False
        psubj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
        if psubj is not None and _interrogative(s, parent, psubj, is_question):
            return True
        node = parent
    return False


def _conj_donor(s, head):
    """A (e240): UD basic deps do not propagate a subject to a `conj` head,
    so "I am not only enhancing my well-being but also contributing to the
    planet" never emitted the second conjunct -- it has no nsubj of its own,
    and the walker just skipped it. Climb the conj chain to the nearest
    ancestor that HAS a subject and lend it. Guarded to VERB/AUX heads (or a
    head with its own `cop`) so NP-internal coordination is left alone: "a
    teacher and a writer" must not produce a second record for "writer".
    """
    if head.upos not in ("VERB", "AUX") and not s.children(head, ("cop",)):
        return None
    node = head
    seen = set()
    while node.deprel == "conj" and node.id not in seen:
        seen.add(node.id)
        parent = s.w.get(node.head)
        if parent is None:
            return None
        if s.children(parent, ("nsubj", "nsubj:pass")):
            return parent
        node = parent
    return None


def _poss(s, word, allow):
    """The owner may sit more than one `nmod:poss` link deep: "my friend
    Thomas's support" is subj(support) -nmod:poss-> friend -nmod:poss-> my
    (e240). Without following the chain, "Susan's support inspires me" and
    "my friend Thomas's support inspires me" look the same to the walker --
    neither reaches the owner-possessed branches below -- and Relationship-
    kind facts were the worst-scoring kind because of it."""
    direct = next((c for c in s.children(word, ("nmod:poss",))
                   if c.text.lower() in allow), None)
    if direct is not None:
        return direct
    for c in s.children(word, ("nmod:poss",)):
        found = _poss(s, c, allow)
        if found is not None:
            return found
    return None


def _third_party_owner(s, head, subj, allow):
    """E (e240): the SUBJECT need not be the owner, or owner-possessed, for
    a clause to be about the owner's world -- "Susan's emotional
    encouragement was crucial during MY entrepreneurial venture" is a fact
    about the owner even though Susan is the grammatical subject. Fires only
    when the owner turns up somewhere else in the clause's OWN span
    (`clause_span` -- not a coordinate sibling clause), and never when the
    subject is a bare pronoun: "she works with me" is unresolved coreference,
    not a third party the parser can name, and rendering it verbatim would
    misattribute the antecedent.
    """
    if subj.upos == "PRON":
        return False
    return any(t.upos == "PRON" and t.text.lower() in allow and t.id != subj.id
               for t in s.clause_span(head))


def extract(text, nlp, owner=None, role="user"):
    """-> [(proposition, kind)]. Deterministic, no model call."""
    return [(b, k) for b, k, _, _ in extract_keyed(text, nlp, owner, role)]


def _pred_key(s, head, args, slot=None):
    """The attribute KEY for a verbal clause: head lemma, plus the case
    marker of its first oblique when there is no direct object
    ("live in", "work at", "move to"). Closed and deterministic -- the
    prompted extractor invented 161 attribute names for one user (W2a);
    the lemma+case of the predicate is the same string every time."""
    lem = head.lemma.lower()
    has_obj = any(c.deprel in ("obj", "iobj") for c in args)
    case = None
    if not has_obj:
        for c in args:
            if c.deprel in ("obl", "nmod"):
                cs = next(iter(s.children(c, ("case",))), None)
                if cs is not None:
                    case = cs.lemma.lower()
                    break
    key = lem if case is None else f"{lem}_{case}"
    if slot:
        key = f"{_slug(slot)}_{key}"
    return key


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def extract_keyed(text, nlp, owner=None, role="user"):
    """-> [(proposition, kind, predicate_key, value)]. `predicate_key` is the
    attribute name a slot store files the record under and `value` the
    complement it stores there; `extract` drops both."""
    o = owner or "The user"
    second = role == "assistant"
    # D (e240): in an assistant turn "I" is the ASSISTANT, not the user --
    # `allow` used to be FIRST|SECOND here, so "I think X" and "I remember Y
    # expressing Z" were owner-possessed by construction and came out
    # "Martin Mark thinks X" / "Martin Mark remembers Martin Mark
    # expressing Z". Only the second person is the user in an assistant
    # turn; a clause whose subject is first person is left for the "is_self"
    # check to fail, which sends it to `continue` below.
    allow = SECOND if second else FIRST
    out, seen = [], set()

    for sent in nlp(text).sentences:
        s = _S(sent)
        # Stanza breaks sentences at terminal punctuation, so the "?" -- if
        # there is one -- is at the end. Allow for a trailing quote.
        is_q = any(w.text == "?" for w in sent.words[-3:])
        for head in sent.words:
            if head.deprel not in CLAUSE_DEPS:
                continue
            subj = next(iter(s.children(head, ("nsubj", "nsubj:pass"))), None)
            donor = None
            if subj is None and head.deprel == "conj":
                # A (e240): borrow the subject (and, below, the aux) from
                # the nearest ancestor along the conj chain that has one.
                donor = _conj_donor(s, head)
                if donor is not None:
                    subj = next(iter(s.children(
                        donor, ("nsubj", "nsubj:pass"))), None)
            if subj is None:
                continue
            if _interrogative(s, head, subj, is_q):
                continue
            if head.deprel in ("ccomp", "xcomp") and \
                    _ancestor_interrogative(s, head, is_q):
                continue
            cop = next(iter(s.children(head, ("cop",))), None)
            neg, negdrop = _negated(s, head)
            sp = _poss(s, subj, allow)
            is_self = subj.text.lower() in allow
            fdrop, ftail = _fronted(s, head, subj)

            # ---- copular: the PREDICATE heads the clause, `cop` hangs off it
            if cop is not None:
                drop = {subj.id, cop.id}
                drop |= {c.id for c in s.children(head, SEPARATE)}
                drop |= {c.id for c in s.children(head, ("aux", "aux:pass"))}
                drop |= negdrop
                drop |= fdrop
                val = s.text(head, stop=drop, owner=o, second=second)
                if ftail:
                    ftxt = " ".join(s.text(c, owner=o, second=second)
                                     for c in ftail)
                    val = f"{val} {ftxt}".strip()
                if not val:
                    continue
                if sp is not None:                    # "my job is X"
                    slot = s.text(subj, stop={sp.id}, owner=o, second=second)
                    body = f"{o}'s {slot} is {'not ' if neg else ''}{val}"
                    kind = "attr"
                    pred = _slug(slot)
                    value = ("not " if neg else "") + val
                elif is_self:                          # "I am X"
                    body = f"{o} is {'not ' if neg else ''}{val}"
                    kind = "attr"
                    pred = "is"
                    value = ("not " if neg else "") + val
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
                    pred = _slug(rel)
                    value = s.text(subj, owner=o, second=second) + (
                        ", " + desc if desc else "")
                elif _third_party_owner(s, head, subj, allow):
                    # E (e240): the subject is a third party, but the owner
                    # sits elsewhere in the clause -- "Susan's emotional
                    # encouragement was crucial during MY venture". The
                    # subject's own agreement is already correct (it is not
                    # the owner), so render the clause as Stanza gave it,
                    # subject included, with no re-inflection.
                    full_drop = (drop - {subj.id, cop.id})
                    body = s.text(head, stop=full_drop, owner=o, second=second)
                    if ftail:
                        body = f"{body} {ftxt}".strip()
                    if not body:
                        continue
                    kind = ("relationship"
                            if any(t.upos == "PROPN" for t in s.subtree(subj))
                            else "event")
                    pred = f"{_slug(subj.lemma)}_{cop.lemma.lower()}"
                    value = val
                else:
                    continue
            else:
                # ---- verbal, including passive: one path, not three
                args = [c for c in s.children(head)
                        if c.deprel in ARG_DEPS and c.id != head.id
                        and c.id not in negdrop and c.id not in fdrop]
                if sp is None and not is_self:
                    if not _third_party_owner(s, head, subj, allow):
                        continue
                    # E (e240): same third-party rule, verbal predicate.
                    full_drop = {c.id for c in s.children(head, SEPARATE)}
                    full_drop |= negdrop | fdrop
                    body = s.text(head, stop=full_drop, owner=o, second=second)
                    tail = " ".join(s.text(c, owner=o, second=second)
                                     for c in sorted(args, key=lambda c: c.id))
                    if ftail:
                        ftxt = " ".join(s.text(c, owner=o, second=second)
                                         for c in ftail)
                        body = f"{body} {ftxt}".strip()
                        tail = f"{tail} {ftxt}".strip()
                    if not body:
                        continue
                    kind = ("relationship"
                            if any(t.upos == "PROPN" for t in s.subtree(subj))
                            else "event")
                    pred = _pred_key(s, head, args, slot=subj.lemma)
                    value = tail
                else:
                    tail = " ".join(s.text(c, owner=o, second=second)
                                     for c in sorted(args, key=lambda c: c.id))
                    if ftail:
                        tail += " " + " ".join(
                            s.text(c, owner=o, second=second) for c in ftail)
                    tail = re.sub(r"\s+", " ", tail).strip(" ,.;:")
                    if not tail or len(tail.split()) > 24:
                        continue
                    aux = [c for c in s.children(head, ("aux", "aux:pass"))]
                    if not aux and donor is not None:
                        # A (e240): the conjunct that borrowed its SUBJECT
                        # from the donor also has no aux of its own when the
                        # donor's tense/aspect is what it is coordinated
                        # under -- "I am ... enhancing X but also
                        # contributing to Y" needs the donor's "am" (-> "is")
                        # to say "is contributing", not "contributing".
                        aux = s.children(donor, ("aux", "aux:pass"))
                    if aux:
                        verb = _third(aux[0].text, aux[0].lemma, aux[0].feats)
                        if neg:
                            verb += " not"
                        verb += " " + " ".join(
                            # same clitic problem as `_third`, one slot along
                            a.lemma if a.text.startswith("'") else a.text
                            for a in aux[1:] if a is not aux[0])
                        verb = verb.strip() + " " + head.text
                    else:
                        verb = _third(head.text, head.lemma, head.feats)
                        if neg:
                            verb = f"does not {head.lemma}"
                    slot_txt = (s.text(subj, stop={sp.id}, owner=o, second=second)
                                if sp is not None else None)
                    lead = o if sp is None else f"{o}'s {slot_txt}"
                    body = f"{lead} {verb} {tail}"
                    # E (e240): the owner-possession chain can pass through a
                    # named third party -- "my FRIEND THOMAS's support" -- in
                    # which case the fact is a relationship, not a bare event.
                    kind = ("relationship"
                            if sp is not None and
                            any(t.upos == "PROPN"
                                for t in s.subtree(subj, stop={sp.id}))
                            else "event")
                    pred = _pred_key(s, head, args, slot=slot_txt)
                    value = ("not " if neg else "") + tail

            body = re.sub(r"\s+", " ", body).strip(" ,.;:")
            # D (e240): a record that STILL carries a bare first-person
            # token in an assistant turn is the assistant talking about
            # itself, not the user -- the safety net for whatever a clause
            # structure this walker did not anticipate lets through.
            if second and _FIRST_RESIDUE.search(body):
                continue
            key = body.lower()[:90]
            if body and key not in seen:
                seen.add(key)
                out.append((body, kind, pred,
                            re.sub(r"\s+", " ", value).strip(" ,.;:")))
    return out
