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
import os
import re

NEG_LEMMAS = {"not", "n't", "never", "no", "nor", "neither"}
# "not only ... but also" is emphasis on the SECOND conjunct, not polarity on
# the first -- e240. "I am not only enhancing X" inverted to "is not
# enhancing X", the worst class of defect here: the record states the
# opposite of what was said, and shares every content word with the truth.
NOT_ONLY = {"only", "just", "merely", "simply"}
FIRST = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours"}
SECOND = {"you", "your", "yours", "yourself", "yourselves"}
# e242: HaluMem's "interference" memories are the assistant FALSELY
# remembering things about the user. On user 0, 29/66 stored-but-wrong
# records sit under one of these three frames in the source sentence
# (18/162 for legitimate assistant-sourced facts) -- the assistant is not
# asserting, it is reporting a claim, a guess, or someone else's belief. The
# clause is still extracted (dropping it would lose real content when the
# hedge is accurate) but tagged `evidential="report"` so a consumer can
# choose to discount or drop it.
REPORT_VERBS = {"remember", "recall", "notice", "hear", "think", "believe",
                 "imagine", "understand", "see", "know", "guess", "suppose",
                 "feel", "sense", "gather", "assume", "suspect", "wonder"}
GENERIC_SUBJ = {"people", "some", "others", "many", "one", "everyone",
                "someone"}
HEDGE_ADV = {"interestingly", "curiously", "apparently", "supposedly",
             "reportedly", "perhaps"}

# e271: EPISTEMIC adverbs are not discourse adverbs. `_fronted` drops a
# sentence-initial advmod outright because "Interestingly"/"However" carry no
# content for a memory record -- true for those, false for these, which change
# the speaker's COMMITMENT. "Perhaps I will switch to Rust" was stored as
# "<owner> will switch to Rust": a plain future the speaker never asserted.
# Found by the refusal suite's modal INVARIANCE row, which is the row that
# exists to catch one phrasing of an operator being handled and another not.
EPISTEMIC_ADV = {"perhaps", "maybe", "possibly", "probably", "likely",
                 "presumably", "potentially", "conceivably", "seemingly",
                 "arguably"}
CLAUSE_DEPS = ("root", "parataxis", "conj", "advcl", "acl", "acl:relcl",
               "ccomp", "xcomp", "csubj")
# e242: "It seems that you have been sleeping better" parses the embedded
# clause as `csubj` of "seems", not `ccomp` -- a clausal subject, not a
# clausal complement, for a raising verb with an expletive subject. Folded
# into the same embedding chain the evidentiality climb walks below.
REPORT_CHAIN = ("ccomp", "xcomp", "advcl", "csubj")
# Arguments only. `aux`/`cop` are realised in the verb phrase and `cc`/`mark`
# are function words, so including them put the auxiliary and the negation
# into the TAIL as well -- "Martin Mark does not like do n't boxing". And
# `conj`/`parataxis` are SEPARATE CLAUSES that the walker extracts in their
# own right, so absorbing them duplicates one clause into another, which is
# the same defect the spaCy version had with comma splices.
ARG_DEPS = ("obj", "iobj", "obl", "obl:agent", "xcomp", "ccomp", "advmod",
            "nmod", "case", "compound", "amod", "det", "nummod", "fixed",
            "flat", "advcl", "acl", "nmod:poss", "expl",
            # 2026-10-02: Stanza labels a bare time phrase obl:unmarked ("I
            # retired LAST YEAR"). Left out, the time was lost from every
            # record, and a verb with only a time after it was dropped.
            "obl:unmarked", "obl:tmod", "obl:npmod")
# 2026-10-02: a verb with nothing after it is dropped ("I agree", "I see" are
# talk, not facts), but these are life events that are complete on their
# own: "I retired", "I got divorced", "I'm engaged!", "We broke up".
LIFE_EVENTS = {"retire", "divorce", "marry", "remarry", "engage", "separate",
               "graduate", "resign", "quit", "emigrate", "relocate", "fire",
               "hire", "promote", "widow", "propose"}
# "They promoted me": an unnamed employer acting on the owner
AGENTLESS_EMPLOY = {"promote", "hire", "fire", "sack", "lay", "transfer",
                    "appoint", "demote", "rehire"}
LIFE_PHRASAL = {("break", "up"), ("split", "up"), ("lay", "off"),
                ("pass", "away"), ("move", "out")}
SEPARATE = ("conj", "parataxis", "cc")
SAME_PAST = {"quit", "put", "cut", "set", "hit", "let", "shut", "split",
             "hurt", "bet", "upset"}
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
    # 2026-10-02: "I quit" is past as often as present and the spelling is
    # the same; Stanza guessed present and the record read "Dana Cole
    # quits", a habit. Kept as typed, the record is right on either reading.
    if w in SAME_PAST and lemma and w == lemma.lower():
        return word
    if feats:
        # e238: the OLD guard was `endswith("ed") or endswith("s")`, a
        # spelling test that misfired on ordinary present-tense verbs that
        # happen to end that way -- "need", "focus", "discuss", "address",
        # "process", "assess" all fell through UNINFLECTED ("Martin Mark
        # need to..."). Stanza already labels tense/aspect/agreement; read
        # THAT instead of guessing from the letters. Kept as a fallback,
        # below, only for the rare token with no feats at all.
        if ("Tense=Past" in feats or "VerbForm=Part" in feats
                or "VerbForm=Ger" in feats):   # a gerund is not finite (e243)
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


_CLITIC_WORD = {"'ve": "have", "'ll": "will", "'m": "am", "'re": "are"}


def _expand_clitic(text, lemma=None):
    """A detached clitic ("'ve", "'ll", "n't", ...) rendered as literal
    punctuation survives the person shift's `\\b` word-boundary match on the
    pronoun it once trailed -- the apostrophe is not a word character, so
    `\\bI\\b` still matches the "I" inside "I've", producing "Martin
    Mark've" (render_defects: clitic_residue). Expand it to a real word
    wherever it is still raw by the time it reaches the page.

    `_third` already handles the one spot that needed AGREEMENT as well as
    expansion (the clause's own finite aux, e.g. "I've" -> "has"), so this
    is a no-op there. It only catches what `_third` left alone -- an
    embedded clause's own aux/negator, kept verbatim as part of a larger
    span ("the fact that they do n't exhibit...", "the support I've
    received... is a force").
    """
    w = text.lower()
    if w == "n't":
        return "not"
    if w in _CLITIC_WORD:
        return _CLITIC_WORD[w]
    if w == "'d":
        # Stanza lemmatises BOTH readings ("I'd like" / "I'd already left")
        # as "would" (verified against real parses) -- "had" is not
        # reliably recoverable from the parse, so this defaults to the
        # modal reading, matching what `_third`'s own clitic branch (below)
        # already assumed.
        return "would" if lemma in (None, "would") else lemma
    return text


_PRONOUN_OBJ = {"his": "him", "her": "her", "their": "them"}


def _pronominalize(text, owner_str, pronoun, pronoun_obj=None):
    """Collapse every owner mention in `text` AFTER THE FIRST down to a
    pronoun. The person shift (`_shift`, below) always writes out the
    owner's full name, with no memory of what it already wrote earlier in
    the SAME proposition -- each of the (up to a dozen) constituents making
    up one rendered clause is shifted independently. The result repeats a
    two-word name three, four, sometimes five times in one sentence
    (render_defects: repeated_owner_possessive/repeated_owner_name), which
    reads as broken regardless of any benchmark.

    Opt-in (`pronoun` is None by default at every call site) and text-level:
    it does not re-parse the clause, so "object position" is approximated
    as "not the first mention" -- true for how this renderer actually
    builds a proposition (the lead/subject slot is filled first, in every
    branch), and confirmed against the real repeated-name examples in the
    u0 cache.

    One shape is deliberately EXEMPTED even after the first mention: an
    IDENTITY statement, "Martin Mark's name is Martin Mark", uses the
    owner's own name as the VALUE being asserted, not as a further
    reference to them -- pronominalising it produces "name is them",
    nonsense that (before the `him`/`them` STOP fix in check.py) used to
    fail the grounding filter and vanish silently instead. Recognised by
    shape: the mention is the last thing in the proposition, directly after
    a copula, with nothing after it.
    """
    if not pronoun or not owner_str:
        return text
    obj = pronoun_obj or _PRONOUN_OBJ.get(pronoun, pronoun)
    pat = re.compile(rf"\b{re.escape(owner_str)}(?:'s)?\b")
    seen = []

    def repl(m):
        if not seen:
            seen.append(True)
            return m.group(0)
        before = text[:m.start()].rstrip()
        after = text[m.end():].strip(" .,;:")
        if not after and re.search(r"\b(?:is|was|are|were|be)$", before, re.I):
            return m.group(0)                      # identity value, not a mention
        return pronoun if m.group(0).endswith("'s") else obj

    return pat.sub(repl, text)


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
        # e259: per-clause relative-pronoun substitution, set by the clause
        # walk. Empty for every clause that is not a relative clause, so the
        # default render path is byte-identical to before.
        self._swap = {}
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

    def text(self, word, stop=(), owner=None, second=False, swap=None):
        """`swap`: {token id -> replacement string}. Used to substitute a
        relative pronoun for its antecedent (e259) -- the token is still in
        the span, so grounding and agreement are unaffected, but what it
        renders as comes from elsewhere in the sentence."""
        toks = [t for t in self.subtree(word, stop) if t.upos != "PUNCT"]
        if not toks:
            return ""
        if swap is None:
            swap = self._swap
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
            if swap and t.id in swap:
                parts.append(swap[t.id])
                continue
            if owner and t.upos in ("VERB", "AUX"):
                sub = next(iter(self.children(t, ("nsubj", "nsubj:pass"))),
                           None)
                # e264: AN AUX HAS NO nsubj OF ITS OWN -- UD attaches the
                # subject to the head VERB. The rule below asks for the
                # token's own nsubj, so a finite aux inside a span was never
                # agreed: "The support you've received" shifted to "The
                # support Martin Mark have received". e243 saw this and
                # queued it ("agreement inside relative clauses is not
                # done"); it is 1.31% of u0 records.
                # Review 2026-09-05: a COPULA has the same shape -- its
                # subject hangs off the predicate, not off it -- and was
                # never agreed: "My mom says I'm lazy" rendered "... says
                # <owner> am lazy".
                if sub is None and t.deprel in ("aux", "aux:pass", "cop"):
                    headw = self.w.get(t.head)
                    if headw is not None:
                        hsub = next(iter(self.children(
                            headw, ("nsubj", "nsubj:pass"))), None)
                        if (hsub is not None
                                and hsub.text.lower() in shifted):
                            parts.append(_expand_clitic(
                                _third(t.text, t.lemma, t.feats), t.lemma))
                            continue
                # An auxiliary carries the finiteness, so the verb under it
                # stays bare: "how I might measure" must not become "might
                # measures". The aux itself is agreed if it needs it, and
                # every modal is already third-singular.
                aux = self.children(t, ("aux", "aux:pass"))
                if sub is not None and not aux and sub.text.lower() in shifted:
                    txt = _third(t.text, t.lemma, t.feats)
            txt = _expand_clitic(txt, t.lemma)
            parts.append(txt)
        s = " ".join(p for p in parts if p)      # a swap may delete a token
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
    drop_ids, tail, hedge = set(), [], []
    for c in s.children(head, ("advmod",)):
        if c.id < subj.id:
            drop_ids.add(c.id)
            # e271: dropped from its fronted POSITION either way, but an
            # epistemic adverb is handed back so the caller can re-place it
            # rather than lose it.
            if (c.lemma or c.text).lower() in EPISTEMIC_ADV:
                hedge.append(c)
    for c in s.children(head, ("advcl", "obl", "nmod")):
        if c.id < subj.id:
            drop_ids.add(c.id)
            tail.append(c)
    return drop_ids, sorted(tail, key=lambda c: c.id), \
        sorted(hedge, key=lambda c: c.id)


# e265: IRREALIS. "If I moved to Berlin I'd need to learn German, but that's
# not happening any time soon" stored "<owner> moved to Berlin" -- a flat
# fabrication of the thing the user explicitly said was NOT happening. A
# conditional is not an assertion, and neither is its consequent.
#
# Keyed on the `mark` lemma, which is what separates a hypothetical from a
# presupposition. "Since you moved to Albi" (mark=since) and "When I moved to
# Berlin" (advmod=when, no mark at all) are both FACTUAL and must survive --
# same shape in the tree, different word, opposite meaning.
# "whenever"/"when" are deliberately absent: they are HABITUAL, not
# hypothetical. "Whenever I travel I get anxious" asserts a real pattern, and
# suppressing it would lose a fact rather than prevent a fabrication.
CONDITIONAL_MARKS = frozenset(("if", "unless", "whether"))

# e270: "Supposing/Provided/Assuming I moved to Berlin" carries NO `mark` at
# all -- Stanza reads the word as a VERB heading the advcl, with the
# conditional clause as its `ccomp`. Listing those words as marks (which is
# what e265 did) therefore never fired, and the refusal suite's INVARIANCE
# row caught it: the "if" phrasing was suppressed and three paraphrases of the
# same operator were not. That is exactly what an invariance test is for.
CONDITIONAL_PREDICATES = frozenset((
    "suppose", "provide", "assume", "imagine", "pretend"))

# ANTI-VERIDICAL predicates: the speaker asserts the NEGATION of their
# complement, so the complement must never be stored as a fact. "I doubt that
# I will move to Berlin" stored "<owner> will move to Berlin" -- the opposite
# of what was said. Distinct from a merely NON-factive predicate ("I think
# X"), which is a hedged assertion we do keep. CommitmentBank's factivity
# dimension is what separates them.
ANTIVERIDICAL_VERBS = frozenset((
    "doubt", "deny", "dispute", "disbelieve", "refute", "contest"))


def _conditional(s, head):
    """True when this clause is inside a hypothetical -- it IS the if-clause,
    it is the consequent that hangs one off itself, or it sits under a
    conditional PREDICATE ("Supposing I moved...")."""
    def _concessive(w):
        """"EVEN if X, Y" ASSERTS Y -- it is a concession, not a hypothesis.
        e276: "Even if it is raining, I always go for a run every morning"
        produced NOTHING, because the main clause was suppressed along with
        the if-clause."""
        return any((c.lemma or c.text).lower() == "even"
                   for c in s.children(w, ("advmod",)))

    def _cond(w):
        if any((c.lemma or c.text).lower() in CONDITIONAL_MARKS
               for c in s.children(w, ("mark",))):
            return True
        return (w.deprel in ("advcl", "advcl:relcl")
                and (w.lemma or "").lower() in CONDITIONAL_PREDICATES)

    # e276: the head's OWN mark is checked whatever its deprel. A conditional
    # with no separate main clause is a ROOT carrying the mark itself, and it
    # was never examined: "If only I had studied medicine instead of law"
    # asserted "<owner> had studied medicine" -- the exact opposite of the
    # regret being expressed.
    if _cond(head):
        return True
    # 2026-10-02: "In case I get the bonus, ..." stored "<owner> gets the
    # bonus". "in case" makes only its OWN clause hypothetical -- "I packed
    # an umbrella in case it rains" still packed the umbrella.
    for m in s.children(head, ("mark",)):
        if (m.lemma or "").lower() == "in" and any(
                (f.lemma or "").lower() == "case"
                for f in s.children(m, ("fixed",))):
            return True
    for c in s.children(head, ("advcl", "advcl:relcl")):
        if _cond(c) and not _concessive(c):
            return True
    # the complement OF a conditional predicate is the hypothesis itself
    if head.deprel in ("ccomp", "xcomp"):
        parent = s.w.get(head.head)
        if parent is not None and _cond(parent):
            return True
    return False


# Review 2026-09-05: FACTIVE predicates presuppose their complement, so it
# survives negation of the matrix ("I don't regret that I left Perrin" still
# commits to leaving). Everything NOT on this list is treated as non-factive
# under negation -- including "know", whose first-person negated use ("I
# don't know that I'm a good cook") is a hedge, not a presupposition.
FACTIVE_VERBS = frozenset((
    "regret", "realize", "realise", "remember", "forget", "notice",
    "discover", "admit", "acknowledge", "appreciate", "resent", "mind",
    "recognize", "recognise"))


def _negated_matrix(s, head):
    """True when this clause is the complement of a NEGATED non-factive
    matrix predicate. CommitmentBank's central case: negation on the matrix
    cancels the complement's entailment. The complement was being emitted as
    its own record regardless -- "I wouldn't say I'm a vegetarian" stored
    "<owner> is a vegetarian", "It's not true that I moved to Berlin" stored
    "<owner> moved to Berlin", "I never said I was a vegetarian" stored
    "<owner> was a vegetarian". Three inversions, one missing rule (review
    2026-09-05). The matrix record itself ("<owner> would not say ...") is
    untouched: it is the honest hedge.

    `csubj` covers the extraposed form ("It's not true THAT ..."), where UD
    hangs the complement off the predicate adjective as a clausal subject."""
    if head.deprel not in ("ccomp", "xcomp", "csubj"):
        return False
    parent = s.w.get(head.head)
    if parent is None:
        return False
    lem = (parent.lemma or parent.text or "").lower()
    if lem in FACTIVE_VERBS:
        return False
    # Review 2026-10-02: two negated matrices PRESUPPOSE their complement and
    # were cancelling it, so the store kept nothing at all:
    #   incredulity  "I can't believe I got the job"    -- the job was got
    #   past ignorance "I never knew I had a brother"   -- the brother exists
    # Present-tense "I don't know that I'm a good cook" stays a hedge: it is
    # the PAST tense of "know" that presupposes (you can only fail to have
    # known something that was true).
    if lem == "believe" and any(
            (a.lemma or a.text or "").lower() in ("can", "could")
            for a in s.children(parent, ("aux",))):
        return False
    if lem == "know" and (
            "Tense=Past" in (parent.feats or "")
            or any("Tense=Past" in (a.feats or "")
                   for a in s.children(parent, ("aux",)))):
        return False
    neg, _ = _negated(s, parent)
    return neg


# Non-veridical attitude / report predicates: the speaker does not commit to
# the complement by using them. Deliberately excludes the semi-factives
# ("know", "remember", "notice", "see", "understand"), which presuppose.
ATTITUDE_VERBS = frozenset((
    "say", "tell", "think", "believe", "feel", "claim", "insist", "suggest",
    "argue", "reckon", "assume", "suspect", "guess", "suppose", "imagine",
    "hear", "expect", "hope", "want", "wish", "figure", "bet"))


def _third_party_matrix(s, head, allow, role):
    """True when this clause is the complement of a non-veridical attitude
    verb whose subject is someone OTHER than the owner, in a user turn.
    "My mom says I'm lazy" stored "<owner> is lazy"; "My friend thinks I
    should quit my job" stored the bare "<owner> should quit <owner>'s job",
    a friend's advice indistinguishable from the owner's own plan (review
    2026-09-05). The matrix record ("<owner>'s mom says ...") is the honest
    form and is unaffected. The owner's OWN attitude ("I'd say I'm a
    vegetarian") still lets its complement through -- that is their hedge
    to make. Assistant turns are handled by e242's report frame, not here."""
    if role != "user" or head.deprel not in ("ccomp", "xcomp"):
        return False
    parent = s.w.get(head.head)
    if parent is None:
        return False
    if (parent.lemma or parent.text or "").lower() not in ATTITUDE_VERBS:
        return False
    psubj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
    # 2026-10-03 (false-memory bench a04): "My dad KEEPS telling me I'm too
    # stubborn" -- the attitude verb is itself a complement and its subject
    # sits on the verb above it, so climb the xcomp/ccomp chain
    up = parent
    while psubj is None and up is not None and up.deprel in ("xcomp", "ccomp"):
        up = s.w.get(up.head)
        if up is not None:
            psubj = next(iter(s.children(up, ("nsubj", "nsubj:pass"))), None)
    if psubj is None:
        return False
    return psubj.text.lower() not in allow


def _preconj_negation(s, subj):
    """-> (is_negated, swap). Negation carried on the SUBJECT: "Neither my
    wife nor I like horror movies" rendered "<owner>'s Neither wife nor
    <owner> like horror movies" -- an un-negated verb with the negators left
    lying in the noun phrase. UD attaches "neither" as `cc:preconj` of the
    first conjunct and "nor" as `cc` of the second; `_negated` only looks at
    the verb's own advmod/det children. Report the polarity so the verb is
    negated, and swap the markers so the subject reads "X and Y" (review
    2026-09-05)."""
    pre = [c for c in s.children(subj, ("cc:preconj",))
           if (c.lemma or c.text).lower() == "neither"]
    if not pre:
        return False, {}
    swap = {c.id: "" for c in pre}
    for conj in s.children(subj, ("conj",)):
        for cc in s.children(conj, ("cc",)):
            if (cc.lemma or cc.text).lower() == "nor":
                swap[cc.id] = "and"
    return True, swap


# Review 2026-10-02: once life events could stand alone ("I retired"), every
# frame that used to drop them for having nothing after the verb had to
# refuse them for the right reason. "I dreamed I got divorced", "I hope I
# get promoted", "I joked that I quit" -- the owner's OWN non-veridical
# attitude: unlike "I think X" (a hedged assertion, kept), the speaker is
# not committing to X. The matrix record ("<owner> hopes ...") is kept.
NONVERIDICAL_OWN = frozenset((
    "dream", "hope", "fear", "wish", "worry", "wonder", "fantasize",
    "fantasise", "joke", "kid", "afraid", "scared", "worried", "hopeful",
    "pretend", "imagine"))
# "Suppose I quit", "Let's say I retire at 60": an imperative supposition
FUTURE_TEMPORAL = frozenset(("when", "once", "after", "before", "until"))


def _irrealis_frame(s, head):
    """True when the clause is (1) under the owner's own non-veridical
    attitude or an imperative supposition, at any depth of complements;
    (2) a temporal clause whose main clause is future ("When I retire I will
    travel"); or (3) one side of an either/or between clauses."""
    w = head
    while w.deprel in ("ccomp", "xcomp"):
        p = s.w.get(w.head)
        if p is None:
            break
        lem = (p.lemma or "").lower()
        if lem in NONVERIDICAL_OWN:
            return True
        if (lem in CONDITIONAL_PREDICATES or lem == "say") and not any(
                s.children(p, ("nsubj", "nsubj:pass"))):
            return True
        w = p
    if head.deprel in ("advcl",):
        marks = {(c.lemma or c.text).lower()
                 for c in s.children(head, ("mark", "advmod"))}
        p = s.w.get(head.head)
        if marks & FUTURE_TEMPORAL and p is not None and any(
                (a.lemma or "").lower() in ("will", "shall", "be")
                and a.xpos == "MD" or (a.text or "").lower() in ("will", "'ll", "shall")
                for a in s.children(p, ("aux",))):
            return True
    # An explicit "either", or "or" between predicates of ONE subject ("I'm
    # vegan or vegetarian", "I got the job or I didn't"). "My dog needs a
    # walk or she goes feral" asserts its first clause: the "or" joins a
    # clause with a different subject, and means "otherwise".
    def _subj_text(w):
        sb = next(iter(s.children(w, ("nsubj", "nsubj:pass"))), None)
        return sb.text.lower() if sb is not None else None

    def _disj(w):
        if any((c.lemma or c.text).lower() == "either"
               for c in s.children(w, ("cc:preconj",))):
            return True
        for c in s.children(w, ("conj",)):
            if not any((x.lemma or x.text).lower() == "or"
                       for x in s.children(c, ("cc",))):
                continue
            cs = _subj_text(c)
            if cs is None or cs == _subj_text(w):
                return True
        return False
    if _disj(head):
        return True
    p = s.w.get(head.head) if head.deprel == "conj" else None
    return p is not None and _disj(p)


def _antiveridical(s, head):
    """True when this clause is the complement of a predicate whose speaker
    asserts its NEGATION -- "I doubt that I will move to Berlin"."""
    if head.deprel not in ("ccomp", "xcomp"):
        return False
    parent = s.w.get(head.head)
    if parent is None:
        return False
    if (parent.lemma or "").lower() not in ANTIVERIDICAL_VERBS:
        return False
    subj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
    return subj is not None


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
    # e264: a SUBJECT-POSITION wh-question has no inversion to detect and the
    # wh-word is a DETERMINER of the subject, not the subject itself: "What
    # specific aspects of relaxation are most important to you?" stored the
    # question verbatim as a fact.
    if is_question and any("PronType=Int" in (c.feats or "")
                           for c in s.children(subj)):
        return True
    # e276: an INDIRECT question carries no "?" -- "I wonder what city I moved
    # to when I was a kid" stored "<owner> moved what city to".
    #
    # NARROW ON PURPOSE. The first version fired on ANY interrogative word in
    # an argument and broke FIVE existing tests: this codebase deliberately
    # keeps wh-clauses that sit under a declarative ("I know what I want",
    # "When I moved to Berlin I learned German"), and e235/e237 tested that
    # intent explicitly. One adversarial example is not grounds for
    # overturning it. So this fires only under a WONDERING matrix verb, where
    # the speaker is stating that they do NOT know.
    if head.deprel in ("ccomp", "xcomp"):
        matrix = s.w.get(head.head)
        if (matrix is not None
                and (matrix.lemma or "").lower() in WONDER_VERBS
                and any("PronType=Int" in (t.feats or "")
                        for a in s.children(head, ARG_DEPS)
                        for t in s.subtree(a))):
            return True
    if is_question:
        av = s.children(head, ("aux", "aux:pass", "cop"))
        if av and min(a.id for a in av) < subj.id:
            return True
        # e264: in an EXISTENTIAL question the inverted element IS the head
        # verb -- "Are there specific workshops...?" has no separate aux for
        # the test above to find, so the matrix clause itself was emitted as
        # "Are there specific workshops ... <owner> are particularly
        # interested in attending". Head precedes subject, plus an expletive,
        # is the inversion.
        if head.id < subj.id and next(iter(s.children(head, ("expl",))), None):
            return True
    return False


# e264: a relative or adverbial clause hanging off a QUESTION is not an
# assertion either. The climb used to cover complements only (ccomp/xcomp),
# so "Are there specific workshops [that] you're interested in?" leaked its
# relative clause out as a fact about the user. This is the same class the
# e242 frame rule exists for -- the assistant's words becoming the user's
# memories -- and it is the most serious defect class in the store, because
# what it produces is not noise but a plausible FALSE fact.
# NOT advcl: an adverbial clause under a question is a PRESUPPOSITION and
# must survive it -- "Since you moved to Albi, how are you settling in?" still
# yields "<owner> moved to Albi" (e235's designed behaviour, see
# _interrogative). A relative clause is different: "Are there specific
# workshops you're interested in?" QUESTIONS the noun phrase its relative
# clause modifies, so the clause is asked, not presupposed.
INTERROG_CHAIN = ("ccomp", "xcomp", "acl", "acl:relcl")


def _ancestor_interrogative(s, head, is_question):
    """G (e237): a ccomp/xcomp under an interrogative matrix inherits the
    question. "do you THINK you'll take" asks about the thinking, so its
    complement "you'll take What steps" is not an assertion either, even
    though the complement clause itself shows no subject-aux inversion --
    that inversion happened one clause up, on "think"."""
    node = head
    for _ in range(6):                      # bounded: chat clauses are shallow
        parent = s.w.get(node.head)
        if parent is None:
            return False
        psubj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
        if psubj is not None and _interrogative(s, parent, psubj, is_question):
            return True
        # e264: an EXISTENTIAL interrogative matrix ("Are there specific
        # workshops...?") has `there` as an expletive, not an nsubj, so the
        # inversion check above never sees a subject to compare against.
        if is_question and next(iter(s.children(parent, ("expl",))), None):
            return True
        # An advcl ancestor is a presupposition boundary -- do not inherit a
        # question across one.
        if parent.deprel == "advcl":
            return False
        node = parent
    return False


def _report_frame(s, head):
    """e242, rule (a): is `head` a ccomp/xcomp/advcl, at any depth, under a
    verb whose own nsubj is first person and whose lemma is a REPORT_VERB --
    "I remember you mentioned...", "I've noticed that your preference has
    evolved...". Climbs the same way `_ancestor_interrogative` does, because
    the embedding can be more than one clause deep."""
    node = head
    while node.deprel in REPORT_CHAIN:
        parent = s.w.get(node.head)
        if parent is None:
            return False
        nsubj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
        if (nsubj is not None and nsubj.text.lower() in FIRST
                and parent.lemma.lower() in REPORT_VERBS):
            return True
        node = parent
    return False


def _generic_or_expl_frame(s, head):
    """e242, rule (b): is `head` a ccomp/xcomp/advcl, at any depth, under a
    verb with a GENERIC subject ("people say...", "some think...") or an
    expletive construction ("it seems that...", "it's fascinating to
    consider that..." -- the governing clause has an `expl` child)."""
    node = head
    while node.deprel in REPORT_CHAIN:
        parent = s.w.get(node.head)
        if parent is None:
            return False
        nsubj = next(iter(s.children(parent, ("nsubj", "nsubj:pass"))), None)
        if nsubj is not None and nsubj.lemma.lower() in GENERIC_SUBJ:
            return True
        if s.children(parent, ("expl",)):
            return True
        node = parent
    return False


def _hedge_sentence(s, sent):
    """e242, rule (c): does the sentence open on a hedge adverb --
    "Interestingly, your health status seems to have changed..."? Checked
    once per sentence (like `_fronted`'s discourse-adverb drop), not per
    clause."""
    if not sent.words:
        return False
    first_id = sent.words[0].id
    root = next((w for w in sent.words if w.deprel == "root"), None)
    if root is None:
        return False
    return any(c.lemma.lower() in HEDGE_ADV and c.id == first_id
               for c in s.children(root, ("advmod",)))


_STANDING = re.compile(r"\b(from now on|every time|in future|going forward|"
                       r"whenever)\b", re.I)


def _standing_instruction(s, head, role, sent):
    """An imperative to the assistant that holds beyond this request: its
    verb has no subject, and it says always / never / don't, or "from now
    on", "every time". At the start of a sentence, or a conjunct with
    "please"."""
    if role != "user" or head.upos != "VERB":
        return False
    if s.children(head, ("nsubj", "nsubj:pass", "csubj", "expl")):
        return False
    if head.deprel == "conj":
        if not any((c.text or "").lower() == "please"
                   for c in s.children(head, ("discourse",))):
            return False
    elif head.deprel == "root":
        lead = [w for w in sent.words if w.id < head.id and w.upos != "PUNCT"]
        lead_text = " ".join(w.text for w in lead)
        if not _STANDING.match(lead_text) and any(
                w.head != head.id or w.deprel not in ("advmod", "aux", "discourse")
                for w in lead):
            return False
    else:
        return False
    marks = {(c.text or "").lower() for c in s.children(head, ("advmod", "aux"))}
    return bool(marks & {"always", "never", "n't", "not"}) or bool(
        _STANDING.search(" ".join(w.text for w in sent.words)))


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
    # 2026-10-04: "I prefer tabs and please never add comments to my code"
    # -- a conjunct with "please" is addressed to the assistant; it borrowed
    # "I" and stored "<owner> does not add comments to <owner>'s code"
    if any((c.text or "").lower() == "please"
           for c in s.children(head, ("discourse",))):
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


# e259: relative pronouns. A relative clause is walked as a clause in its own
# right (CLAUSE_DEPS contains "acl:relcl"), so its relative pronoun rendered
# LITERALLY as an argument -- "It's in Go, which I didn't know before I
# joined" produced "<owner> did not know which". The pronoun's referent is the
# clause head's own UD parent (the antecedent), so it is recoverable, and
# resolving beats dropping: the record becomes "<owner> did not know Go".
RELPRON = frozenset(("which", "that", "who", "whom"))

# e276: matrix verbs whose complement is a question the speaker is NOT
# answering. Distinct from "know"/"remember", where the complement IS asserted.
WONDER_VERBS = frozenset((
    "wonder", "ask", "unsure", "question", "guess", "forget"))


def _cop_form(s, head):
    """The copula to render for an owner-subject copular clause.

    e263: the copular branch drops every `aux` child along with the copula,
    so a PERFECT lost its aspect -- "I've been at Lumen Health for about three
    years now" rendered as "<owner> IS at Lumen Health for about three years
    now", which is not English and reads as a location rather than a tenure.
    The verbal branch never had this bug ("I've worked at Acme" -> "has worked
    at Acme"); only the copular one, which rebuilds its copula from a literal.

    Same family as e256's `bare_been` (that branch un-dropped subj/cop and
    forgot the aux). Returns "has been" for a perfect, else "is".
    """
    for c in s.children(head, ("aux", "aux:pass")):
        lem = (c.lemma or c.text).lower()
        if lem in ("have", "has", "'ve", "had"):
            return "has been"
        # e276: a FUTURE copular collapsed to the present -- "I will be a
        # manager next year" stored "<owner> IS a manager next year", a claim
        # about now that the speaker made about later.
        if lem in ("will", "'ll", "shall"):
            return "will be"
        if lem == "would":
            return "would be"
        # Review 2026-09-05: every other modal collapsed to "is" -- "I might
        # be interested in learning Swift" stored "<owner> IS interested in
        # learning Swift". The verbal branch keeps its modal ("might switch
        # to Rust", tested since e270); only the rebuilt copula lost it.
        if lem in ("might", "may", "could", "should", "must", "can", "ought"):
            return f"{lem} be"
    # e276: and so did the PAST. "I was very anxious during college" stored
    # "<owner> IS very anxious during college" -- sitting beside "feels much
    # calmer now" from the same turn, two contradictory present-tense claims.
    # e263 handled only the perfect; its docstring documented that scope, but
    # a documented gap that inverts a truth value is still an inversion.
    cop = next(iter(s.children(head, ("cop",))), None)
    if cop is not None and "Tense=Past" in (cop.feats or ""):
        return "was"
    return "is"

# Dependents that belong to an antecedent's NOUN PHRASE. Anything else (a
# copula, a subject, a case marker, another clause) belongs to the clause the
# antecedent happens to head, not to the referent being substituted in.
NP_MODS = ("det", "amod", "compound", "nummod", "flat", "nmod:poss",
           "nmod:tmod", "goeswith")


def _relcl_swap(s, head):
    """{relative-pronoun id -> antecedent text} for an `acl:relcl` clause.

    Returns {} when the clause is not a relative clause, carries no relative
    pronoun, or the antecedent cannot be rendered -- callers then behave
    exactly as before. The antecedent is rendered WITHOUT the relative clause
    itself (stop={head.id}), otherwise "a book, which I enjoyed" would expand
    the pronoun into a copy of its own clause.
    """
    if head.deprel != "acl:relcl":
        return {}
    ante = s.w.get(head.head)
    if ante is None:
        return {}
    rels = [c for c in s.children(head)
            if c.upos == "PRON" and c.text.lower() in RELPRON]
    if not rels:
        return {}
    # Render the antecedent as a NOUN PHRASE, not as whatever clause it may
    # head. "It's in Go, which I didn't know" has `Go` as the copular ROOT, so
    # its subtree is the whole clause and an unrestricted render produced
    # "<owner> did not know It's in Go". Only nominal modifiers come along.
    stop = {head.id}
    stop |= {c.id for c in s.children(ante) if c.deprel not in NP_MODS}
    saved, s._swap = s._swap, {}
    try:
        text = s.text(ante, stop=stop)
    finally:
        s._swap = saved
    if not text:
        return {}
    return {c.id: text for c in rels}


# e267: SAME-TURN PRONOUN SUBJECTS with an owner-POSSESSED antecedent.
# "My car is a Volvo. It is very reliable." stored the first clause and threw
# the second away: `It` is a bare pronoun subject, which the walker refuses
# (rightly -- rendering an unresolved antecedent misattributes it).
#
# Restricted to the ONLY case where the antecedent is unambiguous and the
# rendering is honest:
#   * same TURN (one speaker, adjacent sentences -- not cross-turn, where a
#     wrong antecedent becomes a confident false memory, e262);
#   * the antecedent is OWNER-POSSESSED ("my car"), so the resolved subject
#     is "<owner>'s car" -- a fact about the user's world by construction;
#   * EXACTLY ONE such antecedent is in scope. Two candidates decline.
# A common-noun antecedent the owner merely mentioned ("the billing service")
# is deliberately NOT in scope: resolving it produces a fact about a thing
# rather than about the user, which is a change to what the store is FOR and
# not a defect fix.
_PRON_SUBJ = frozenset(("it", "they", "this", "that", "these", "those"))

# e269: THE USER'S WORLD, not the user's profile.
#
# JP: "most people rely on facts about their world. they KNOW the facts on
# themselves." A store keyed on owner-subject clauses keeps "Alex works on the
# billing service" -- which the user already knows -- and throws away "the
# billing service is written in Go", which is the thing they would actually
# forget and ask for.
#
# An entity joins the user's world when the OWNER links themselves to it: it
# is the object/oblique of a clause the owner is the subject of ("I work on
# the billing service"), or it is owner-possessed ("my car"). Only USER turns
# establish, so an assistant's generic ("Cats are independent animals",
# "There are several good databases available") never creates one and can
# never attach to one.
#
# This is a change to what the store is FOR, made deliberately and on the
# owner's instruction -- not a defect fix. RG_WORLD=0 disables it.
_WORLD_LINK_DEPS = ("obj", "iobj", "obl", "obl:unmarked", "nmod")


def _np_text(s, w):
    """The entity's own noun phrase -- head plus nominal modifiers only.
    Storing the bare head lost the modifier: "I work on the billing service"
    yielded the entity "service", and the record read "service is written in
    Go" instead of "the billing service is written in Go"."""
    stop = {c.id for c in s.children(w) if c.deprel not in NP_MODS}
    saved, s._swap = s._swap, {}
    try:
        return s.text(w, stop=stop)
    finally:
        s._swap = saved


def _collect_world(s, head, subj, is_self, sp, out):
    """Record entities this clause links the owner to.

    COORDINATION COUNTS AS SEPARATE CANDIDATES. "I have a dog and a cat" must
    put BOTH in scope, so a following "It is friendly" sees two candidates and
    declines. Collecting only the `obj` head left one candidate and produced a
    confident wrong guess -- caught by testing the coordination case."""
    if not (is_self or sp is not None):
        return
    deps = _WORLD_LINK_DEPS + (("obj", "iobj") if sp is not None else ())
    for c in s.children(head, deps):
        if c.upos not in ("NOUN", "PROPN") or not c.lemma:
            continue
        out.setdefault(c.lemma.lower(), _np_text(s, c))
        for sib in s.children(c, ("conj",)):
            if sib.upos in ("NOUN", "PROPN") and sib.lemma:
                out.setdefault(sib.lemma.lower(), _np_text(s, sib))


def _link(s, rel, name, out):
    """2026-10-04 (LoCoMo dev, multi-hop): "my home country, Sweden" links
    the phrase "home country" to "Sweden", stored in the world map under
    "=home country". A later "since I moved from my home country" can then
    be read with the name (memory_api adds the note)."""
    mods = sorted([c for c in s.children(rel, ("compound", "amod"))
                   if c.id < rel.id], key=lambda c: c.id)
    phrase = " ".join([c.text for c in mods] + [rel.text]).lower()
    full = sorted([name] + [c for c in s.children(name, ("flat", "compound"))],
                  key=lambda c: c.id)
    value = " ".join(c.text for c in full)
    if phrase and value[:1].isupper():
        out["=" + phrase] = value


def _collect_names(s, allow, out):
    """2026-10-02 (false-memory bench): a name the owner introduced with a
    relation -- "My dog Biscuit", "my girlfriend Elise" -- joins their world,
    so a later "Biscuit died on Tuesday" is kept. Stanza tags a sentence-
    initial "Biscuit" as a common noun, so the name is otherwise invisible."""
    for w in s.w.values():
        if w.upos not in ("NOUN", "PROPN") or not w.text[:1].isupper():
            continue
        # "My dog Biscuit": the name heads, the relation is a compound
        if (_poss(s, w, allow) is not None
                and any(c.upos == "NOUN" for c in s.children(w, ("compound",)))):
            out.setdefault(w.lemma.lower(), w.text)
        # "my girlfriend Elise": the name is an apposition of the relation
        p = s.w.get(w.head)
        if (w.deprel in ("appos", "flat") and p is not None
                and _poss(s, p, allow) is not None):
            out.setdefault(w.lemma.lower(), w.text)
            if w.deprel == "appos" and p.upos == "NOUN":
                _link(s, p, w, out)
        # "My hometown is Ballarat": the name is the predicate of a copula
        # whose subject is the owner's relation
        if (w.upos == "PROPN" and w.deprel == "root"
                and any(c.deprel == "cop" for c in s.children(w))):
            subj = next(iter(s.children(w, ("nsubj",))), None)
            if (subj is not None and subj.upos == "NOUN"
                    and _poss(s, subj, allow) is not None):
                _link(s, subj, w, out)
        # "We adopted a beagle called Waffles"
        if (w.deprel in ("xcomp", "obj") and p is not None
                and (p.lemma or "").lower() in ("call", "name")
                and p.deprel == "acl"):
            out.setdefault(w.lemma.lower(), w.text)


def _world_subject(s, subj, world, role):
    """True when this clause's subject is an entity the owner established."""
    if role != "user" or not world:
        return False
    if subj.upos not in ("NOUN", "PROPN"):
        return False
    return bool(subj.lemma) and subj.lemma.lower() in world


# Review 2026-10-02: "I took the train. It is raining." stored "the train is
# raining"; "I quit my job. It was the right call." stored "<owner>'s job was
# the right call"; "I called the plumber. It is leaking." stored "the plumber
# is leaking". Weather and evaluative "it" point at no noun, and "it" never
# points at a person.
WEATHER_IT = frozenset("""rain snow pour drizzle hail storm thunder freeze
raining snowing pouring sunny cloudy windy rainy foggy humid cold hot warm
chilly freezing dark late early rumour rumor""".split())
# After an ACTION on an object ("I quit my job. It was the right call."),
# an evaluation is about the action. After "My commute is long. It is
# exhausting." it is about the commute -- so these block only an object.
EVAL_IT = frozenset("""call decision choice idea mistake move thing time day week experience relief
shame pity nightmare blast disaster success failure struggle journey ride
hard tough easy difficult great fun awful terrible amazing weird crazy nice
good bad sad scary stressful worth long short quick rough brutal fine okay ok
painful emotional exhausting intense surreal wild lovely horrible perfect
right wrong worse better best interesting boring annoying frustrating
schedule quiet busy""".split())
PERSON_NOUNS = frozenset("""mother father mom mum dad parent parents brother
sister son daughter wife husband partner boyfriend girlfriend fiance fiancee
friend boss manager colleague coworker teacher doctor dentist nurse plumber
electrician lawyer ceo cto cfo founder landlord landlady neighbour neighbor
client customer therapist coach mentor uncle aunt cousin grandma grandpa
grandmother grandfather baby kid child person guy woman man girl boy
recruiter engineer developer designer accountant mechanic vet surgeon physio
tutor student roommate flatmate housemate niece nephew stepdad stepmom
stepmum lead director founder owner""".split())


def _ambient_it(s, head, subj, cop, eval_too=False):
    if subj.text.lower() not in ("it", "this", "that"):
        return False
    words = {(head.lemma or "").lower(), (head.text or "").lower()}
    if cop is not None:
        words |= {(c.lemma or "").lower()
                  for c in s.children(head, ("amod", "compound"))}
    return bool(words & WEATHER_IT) or (eval_too and bool(words & EVAL_IT))


def _is_person(lemma):
    l = (lemma or "").lower()
    return l in PERSON_NOUNS or (l.endswith(("ist", "ian"))
                                 and not l.endswith("list"))


def _poss_antecedent(carry, subj):
    """-> the carried antecedent for this pronoun subject, or None.

    `carry` holds candidates established EARLIER IN THIS TURN only. Cross-turn
    pronoun resolution is deliberately not attempted: a wrong antecedent is a
    confident false memory (e262). An explicit noun-phrase subject matches
    across turns (e269) because that is string identity, not a guess.
    """
    if subj.upos != "PRON" or subj.text.lower() not in _PRON_SUBJ:
        return None
    if len(carry) != 1:
        return None
    return next(iter(carry.values()))


def _collect_poss(s, allow, out):
    """Record candidate antecedents for a later pronoun.

    e276: this recorded only OWNER-POSSESSED nominals, so "My friend has a
    cat. It is very playful." saw exactly one candidate ("friend") and
    confidently attributed the CAT's playfulness to the FRIEND. A direct
    object is a perfectly good antecedent for "it" -- usually a better one --
    so it counts as a COMPETING candidate and the ambiguity check declines.

    A copular complement is deliberately NOT counted: in "My car is a Volvo"
    the Volvo IS the car, not a second entity, and counting it would break
    the case this rule exists for.
    """
    for w in s.w.values():
        if w.upos not in ("NOUN", "PROPN") or not w.lemma:
            continue
        if _poss(s, w, allow) is not None:
            out[w.lemma.lower()] = w
        elif w.deprel in ("obj", "iobj", "conj"):
            # `conj` included so "a dog and a cat" yields TWO candidates and
            # the ambiguity check declines -- collecting only the obj head
            # left one and produced a confident wrong guess (the same defect
            # _collect_world already guards, e269).
            out.setdefault(w.lemma.lower(), w)


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


# e243, RULE 1: on user 0, 132/315 judged misses were the gold fact buried
# inside a longer clause -- "dislikes formal wear because finds it
# restrictive and prefer clothing that..." vs gold "dislikes formal wear".
# Surplus records are precision-free on this benchmark, so both the atomic
# CORE and the FULL clause are emitted when the clause has a periphery: an
# adverbial/relative/complement clause or comma splice hanging off the
# clause head, or an obl/nmod introduced by a subordinator-like case/mark
# word ("because of the rain", "due to stress").
PERIPHERY_DEPS = ("advcl", "acl", "acl:relcl", "ccomp", "parataxis")
PERIPHERY_MARK_LEMMAS = {"because", "since", "although", "though", "while",
                          "whereas", "so", "unless", "despite", "due"}


def _life_event(s, head):
    lem = (head.lemma or "").lower()
    if lem in LIFE_EVENTS:
        return True
    return any((lem, c.text.lower()) in LIFE_PHRASAL
               for c in s.children(head, ("compound:prt",)))


def _periphery(s, head):
    """-> set of ids of `head`'s children that make up the clause's
    PERIPHERY (e243). These carry real content -- dropping them would lose
    information a full-clause record still needs -- but they are not the
    clause's core assertion, so a value filed under a slot should exclude
    them even when the record's own text keeps them."""
    ids = {c.id for c in s.children(head, PERIPHERY_DEPS)}
    for c in s.children(head, ("obl", "nmod")):
        markers = s.children(c, ("case", "mark"))
        if any(m.lemma.lower() in PERIPHERY_MARK_LEMMAS for m in markers):
            ids.add(c.id)
    return ids


# e243, RULE 3: 52/154 (u0) and 78/256 (u1) judged misses have a NAMED third
# party as the source sentence's subject, in USER turns, with the owner
# nowhere in the clause -- "WilsonRobert recommended a yoga class near the
# office". Rule E (`_third_party_owner`, e240) does not fire here: the owner
# is not elsewhere in the clause, so the record was simply dropped. A bare
# common noun ("Cats are independent animals") must not fire -- only a
# genuinely NAMED subject does.
def _propn_subject(s, subj):
    """Is `subj` (the clause's own subject) a NAMED entity -- PROPN itself,
    or carrying a PROPN through `flat`/`compound`/`nmod:poss` ("my friend
    Thomas" -> Thomas is nmod:poss of "friend", but here the search is on
    the SUBJECT itself, e.g. "Thomas Jones" flat/compound, or "Thomas's
    class" nmod:poss)."""
    if subj.upos == "PROPN":
        return True
    return any(c.upos == "PROPN"
               for c in s.children(subj, ("flat", "compound", "nmod:poss")))


def extract(text, nlp, owner=None, role="user"):
    """-> [(proposition, kind)]. Deterministic, no model call."""
    return [(b, k) for b, k, _, _, _ in extract_keyed(text, nlp, owner, role)]


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


def extract_keyed(text, nlp, owner=None, role="user",
                   owner_pronoun=None, owner_pronoun_obj=None, world=None,
                   with_source=False):
    """-> [(proposition, kind, predicate_key, value, evidential)].
    `predicate_key` is the attribute name a slot store files the record
    under and `value` the complement it stores there; `extract` drops all
    three. `evidential` is "report" (e242) when an ASSISTANT-turn clause
    sits under a report verb, a generic subject, an expletive, or a
    sentence-initial hedge adverb, else None -- the assistant is relaying a
    claim, not asserting one of its own.

    `owner_pronoun`: default None means UNCHANGED behaviour -- the owner's
    full name every mention, exactly as always. Set it (e.g. "his"/"her"/
    "their") to collapse every mention after the first, in a given
    proposition, down to a pronoun (see `_pronominalize`). Never inferred
    from the owner's name -- that is a decision only a caller may make, and
    the caller must make it explicitly."""
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

    poss_carry = {}          # e267: owner-possessed nominals seen so far
    turn_world = {}          # e269: entities established in THIS turn only --
                             # the only ones a PRONOUN may resolve to
    if world is None:        # e269: the owner's world, carried across TURNS
        world = {}
    for sent in nlp(text).sentences:
        s = _S(sent)
        # Stanza breaks sentences at terminal punctuation, so the "?" -- if
        # there is one -- is at the end. Allow for a trailing quote.
        is_q = any(w.text == "?" for w in sent.words[-3:])
        hedge = second and _hedge_sentence(s, sent)
        sent_poss = {}
        _collect_poss(s, allow, sent_poss)
        if role == "user" and os.environ.get("RG_WORLD") != "0":
            _collect_names(s, allow, world)
        for head in sent.words:
            s._swap = {}
            if head.deprel not in CLAUSE_DEPS:
                continue
            # nsubj:outer: "My art is about expressing my trans experience"
            # (LoCoMo dev audit, 2026-10-02) -- the subject of a copula whose
            # predicate is itself a clause
            subj = next(iter(s.children(head, ("nsubj", "nsubj:pass",
                                                "nsubj:outer"))), None)
            if subj is None and role == "user":
                # a clause as subject, the user as object: "Bringing others
                # comfort ... brings me such joy"
                cs = next(iter(s.children(head, ("csubj",))), None)
                # needs something besides the user ("Cooking makes me." says
                # nothing) and no hedge ("Maybe cooking makes me happy")
                if (cs is not None and any(
                        c.text.lower() in allow
                        for c in s.children(head, ("obj", "iobj")))
                        and any(c.text.lower() not in allow for c in
                                s.children(head, ("obj", "xcomp", "obl")))
                        and not any((c.lemma or "").lower() in
                                    ("maybe", "perhaps", "probably",
                                     "possibly") for c in
                                    s.children(head, ("advmod",)))):
                    subj = cs
            donor = None
            obj_ctrl = False
            if subj is None and head.deprel == "conj":
                # A (e240): borrow the subject (and, below, the aux) from
                # the nearest ancestor along the conj chain that has one.
                donor = _conj_donor(s, head)
                if donor is not None:
                    subj = next(iter(s.children(
                        donor, ("nsubj", "nsubj:pass"))), None)
            if subj is None and head.deprel in ("xcomp", "ccomp"):
                # e243, RULE 2: OBJECT CONTROL. "I remember you expressing
                # skepticism..." -- "expressing" has no nsubj of its own;
                # UD attaches the logical subject as the matrix verb's
                # OBJECT instead. Restricted to a gerund/participial
                # complement -- an infinitival xcomp ("I want to go", "I
                # told my team to focus") is control of a DIFFERENT,
                # unstated subject and must not gain a record here.
                feats = head.feats or ""
                if "VerbForm=Ger" in feats or "VerbForm=Part" in feats:
                    matrix = s.w.get(head.head)
                    if matrix is not None:
                        mobj = next(iter(s.children(matrix, ("obj",))), None)
                        if mobj is not None:
                            subj = mobj
                            obj_ctrl = True
            if subj is None and _standing_instruction(s, head, role, sent):
                # 2026-10-04: "Always run the tests", "Don't use semicolons
                # in my JavaScript", "please never add comments to my code"
                # -- a standing instruction to the assistant is the user's
                # own, wherever they work (a one-off "Fix the failing test"
                # has no always/never/don't and stores nothing)
                stop = {c.id for c in s.children(
                    head, ("conj", "cc", "discourse", "punct", "parataxis"))}
                span = re.sub(r"\s+", " ", s.text(head, stop=stop, owner=o,
                                                   second=second)).strip(" ,.;:!")
                body = f"{o} asked the assistant: {span}"
                if span and body.lower()[:90] not in seen:
                    seen.add(body.lower()[:90])
                    out.append((body, "attr", "instruction", span, None, sent.text)
                               if with_source else
                               (body, "attr", "instruction", span, None))
                continue
            if subj is None:
                continue
            if _interrogative(s, head, subj, is_q):
                continue
            if _conditional(s, head):
                continue
            if _antiveridical(s, head):
                continue
            if _irrealis_frame(s, head):
                continue
            if _negated_matrix(s, head):
                continue
            if _third_party_matrix(s, head, allow, role):
                continue
            if head.deprel in INTERROG_CHAIN and \
                    _ancestor_interrogative(s, head, is_q):
                continue
            cop = next(iter(s.children(head, ("cop",))), None)
            neg, negdrop = _negated(s, head)
            pneg, pswap = _preconj_negation(s, subj)
            neg = neg or pneg
            sp = _poss(s, subj, allow)
            # e267: a bare pronoun subject with exactly ONE owner-possessed
            # antecedent carried from an earlier sentence of THIS turn.
            carried = None
            world_carried = None
            if sp is None:
                anc = (None if _ambient_it(s, head, subj, cop)
                       else _poss_antecedent(poss_carry, subj))
                if anc is not None and (
                        (subj.text.lower() == "it" and _is_person(anc.lemma))
                        or (anc.deprel in ("obj", "iobj")
                            and _ambient_it(s, head, subj, cop, eval_too=True))):
                    anc = None
                    poss_blocked = True
                else:
                    # world entities are always objects/obliques of an action
                    poss_blocked = _ambient_it(s, head, subj, cop, eval_too=True)
                if anc is not None:
                    carried = anc.text
                    # 2026-10-02: a DIRECT OBJECT the owner linked to themselves
                    # ("I maintain the checkout service. It is written in
                    # Rust.") is the one candidate, but the possessive render
                    # below exists only for copular clauses, so a verbal or
                    # passive follow-up was dropped. Render the entity itself,
                    # as e269 does for "I work on the billing service".
                    lem = (anc.lemma or "").lower()
                    if (cop is None and anc.deprel in ("obj", "iobj")
                            and lem in turn_world and role == "user"
                            and os.environ.get("RG_WORLD") != "0"):
                        world_carried = re.sub(r"^(?:a|an)\s+", "the ",
                                               turn_world[lem], flags=re.I)
                        carried = None
                elif not poss_carry and not poss_blocked:
                    # e269: no owner-possessed candidate, but the owner may
                    # have established exactly one world entity this turn.
                    # Renders as the entity itself ("The billing service is
                    # written in Go"), not as "<owner>'s ..." -- the owner
                    # linked to it, they do not own it.
                    if (subj.upos == "PRON"
                            and subj.text.lower() in _PRON_SUBJ
                            and len(turn_world) == 1
                            and os.environ.get("RG_WORLD") != "0"
                            and role == "user"):
                        lem, np = next(iter(turn_world.items()))
                        if not (subj.text.lower() == "it" and _is_person(lem)):
                            world_carried = np
            is_self = subj.text.lower() in allow
            fdrop, ftail, fhedge = _fronted(s, head, subj)
            # e243, RULE 3: a NAMED third party as subject, with the owner
            # nowhere in the clause -- "WilsonRobert recommended a yoga
            # class near the office" -- fires in USER turns only. Computed
            # once; shared by the copular and verbal branches below.
            tpo = _third_party_owner(s, head, subj, allow)
            named_tpo = (not tpo and role == "user"
                         and _propn_subject(s, subj))
            # e269: a subject the OWNER established as part of their world.
            world_subj = (not tpo and not named_tpo
                          and os.environ.get("RG_WORLD") != "0"
                          and (_world_subject(s, subj, world, role)
                               or world_carried is not None))

            # e259: resolve this clause's relative pronoun to its antecedent
            # before ANY render call below reads it.
            s._swap = _relcl_swap(s, head)
            if pswap:
                s._swap = dict(s._swap)
                s._swap.update(pswap)
            if fhedge:
                # e271: the adverb was SENTENCE-INITIAL, so its capital is
                # positional, not lexical -- mid-record it must be lower case
                # ("Alex Reyes Perhaps will switch"). Reuses e259's swap.
                s._swap = dict(s._swap)
                for c in fhedge:
                    s._swap[c.id] = c.text.lower()
            if world_carried is not None:
                # e269: render the resolved world entity in place of the
                # pronoun, so the record reads "The billing service is
                # written in Go" rather than "It is written in Go".
                #
                # e276 [FACT INVERSION]: this used to overwrite whatever
                # _relcl_swap had just decided. "that" is both a RELPRON and a
                # _PRON_SUBJ, so in a SUBJECT relative clause ("a disease THAT
                # affects millions") the ids collide and the world entity
                # replaced the correct antecedent:
                #     "I met a doctor who treats a disease that affects
                #      millions of people"  ->  "a doctor affects millions"
                # e259's antecedent is read off THIS clause and always wins;
                # the world carry is a fallback for an unresolved pronoun.
                if subj.id not in s._swap:
                    s._swap = dict(s._swap)
                    s._swap[subj.id] = world_carried
                else:
                    world_carried = None

            # e269: whatever this clause links the owner to joins their world
            # and can be the SUBJECT of a later clause, in this turn or a
            # later one. Collected before the branches so a clause can
            # establish and use in one pass ("I work on the billing service.
            # It is written in Go").
            if role == "user":
                _collect_world(s, head, subj, is_self, sp, world)
                _collect_world(s, head, subj, is_self, sp, turn_world)

            records = []  # [(body, kind, pred, value), ...] for this clause

            # ---- copular: the PREDICATE heads the clause, `cop` hangs off it
            if cop is not None:
                # review round 3: "My only regret is that I NEVER went to
                # college" -- a negation inside a clausal predicate (after
                # its own mark) belongs to that clause; lifting it to the
                # copula gave "regret is not that ... went", an inversion.
                inner_mark = [c for c in s.children(head, ("mark",))
                              if c.id > cop.id]
                if neg and inner_mark and head.upos == "VERB" and not pneg:
                    neg, negdrop = False, set()
                drop = {subj.id, cop.id}
                drop |= {c.id for c in s.children(head, SEPARATE)}
                drop |= {c.id for c in s.children(head, ("aux", "aux:pass"))}
                # stray_complementizer: a `mark` child of `head` is the
                # connective ("that"/"like") introducing THIS clause as a
                # complement of some OUTER verb ("I believe THAT my journey
                # is...") -- it is not part of the clause's own predicate,
                # but nothing excluded it from the walk, so it leaked into
                # the rendered span right after the copula: "is that a
                # testament". The outer verb itself is never in play here
                # (subtree only descends FROM head), only its connective.
                # 2026-10-02: only a mark BEFORE the copula is that outer
                # connective; one after it is the predicate's own -- "My goal
                # is TO finish the marathon", "My art is ABOUT expressing..."
                # rendered "is finish", "is expressing".
                drop |= {c.id for c in s.children(head, ("mark",))
                         if c.id < cop.id}
                drop |= negdrop
                drop |= fdrop
                # e243, RULE 1: ATOM + FULL. The clause's PERIPHERY (an
                # advcl/acl/ccomp/parataxis, or a because-like obl/nmod) is
                # excluded from the CORE render but kept in the FULL one.
                peri = _periphery(s, head)
                val_full = s.text(head, stop=drop, owner=o, second=second)
                val_core = (s.text(head, stop=drop | peri, owner=o, second=second)
                            if peri else val_full)
                ftxt = None
                if ftail:
                    ftxt = " ".join(s.text(c, owner=o, second=second)
                                     for c in ftail)
                    val_full = f"{val_full} {ftxt}".strip()
                    val_core = f"{val_core} {ftxt}".strip()
                if not val_full:
                    continue
                if not val_core:                       # core guard, e243
                    val_core, peri = val_full, set()

                cform = _cop_form(s, head)
                # "I have never been to Paris" read "has been not to Paris"
                if neg and " " in cform:
                    first, rest = cform.split(" ", 1)
                    cform = f"{first} not {rest}"
                    neg = False
                if fhedge:      # e271
                    cform = (" ".join(c.text.lower() for c in fhedge)
                             + " " + cform)   # swap keeps case consistent
                if sp is not None or carried is not None:   # "my job is X"
                    slot = (carried if carried is not None
                            else s.text(subj, stop={sp.id}, owner=o,
                                        second=second))
                    kind = "attr"
                    pred = _slug(slot)
                    npfx = "not " if neg else ""
                    value = npfx + val_core             # (a): core, e243
                    if peri and val_core != val_full:
                        records.append((f"{o}'s {slot} {cform} {npfx}{val_core}",
                                         kind, pred, value))
                    records.append((f"{o}'s {slot} {cform} {npfx}{val_full}",
                                     kind, pred, value))
                elif is_self:                          # "I am X"
                    kind = "attr"
                    pred = "is"
                    npfx = "not " if neg else ""
                    value = npfx + val_core             # (a): core, e243
                    if peri and val_core != val_full:
                        records.append((f"{o} {cform} {npfx}{val_core}",
                                         kind, pred, value))
                    records.append((f"{o} {cform} {npfx}{val_full}",
                                     kind, pred, value))
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
                    records.append((body, kind, pred, value))
                elif tpo or named_tpo or world_subj:
                    # E (e240) / RULE 3 (e243): the subject is a third
                    # party -- either the owner sits elsewhere in the
                    # clause (E), or, in a user turn, the subject is
                    # itself NAMED and the clause is kept regardless of
                    # whether the owner appears at all (Rule 3). The
                    # subject's own agreement is already correct (it is
                    # not the owner), so render the clause as Stanza gave
                    # it, subject included, with no re-inflection.
                    # bare_been: `drop` unconditionally excludes the head's
                    # aux (needed by the is_self/sp branches below, which
                    # hardcode their own "is"/"is not"), but THIS branch has
                    # no hardcoded copula -- it renders the real one, so
                    # dropping the aux orphaned "been" with no perfect
                    # auxiliary ("Networking always been a key part...").
                    # Put it back; `mark` (stray_complementizer) stays out.
                    # e276 [FACT INVERSION]: `drop` carries `negdrop`, and
                    # the two branches above compensate by re-adding a literal
                    # "not " prefix (`npfx`). THIS branch renders the clause
                    # as Stanza gave it and has no such prefix -- so the
                    # negation was simply deleted and the store asserted the
                    # OPPOSITE of what was said:
                    #     "WilsonRobert is not a fan of jazz"
                    #        -> "WilsonRobert is a fan of jazz"
                    #     "The billing service is not written in Go"
                    #        -> "The billing service is written in Go"
                    # Ledger 5l calls this the worst class there is: the false
                    # record shares every content word with the true one, so
                    # no overlap metric can see it. Un-drop the negation here;
                    # it renders in place, which is what this branch is for.
                    full_drop = (drop - {subj.id, cop.id} - negdrop
                                 - {c.id for c in
                                    s.children(head, ("aux", "aux:pass"))})
                    body = s.text(head, stop=full_drop, owner=o, second=second)
                    if ftail:
                        body = f"{body} {ftxt}".strip()
                    if body:
                        kind = ("relationship" if named_tpo or
                                any(t.upos == "PROPN" for t in s.subtree(subj))
                                else "event")
                        pred = f"{_slug(subj.lemma)}_{cop.lemma.lower()}"
                        value = val_full
                        records.append((body, kind, pred, value))
            else:
                # ---- verbal, including passive: one path, not three
                args = [c for c in s.children(head)
                        if c.deprel in ARG_DEPS and c.id != head.id
                        and c.id not in negdrop and c.id not in fdrop]
                # review 2026-10-02: "They might fire me" is not "was
                # fired" -- no modal, no hedge, no dream or game
                hedged = (any(a.xpos == "MD" or (a.lemma or "").lower() in
                              ("will", "would", "could", "might", "may",
                               "should", "can", "must")
                              for a in s.children(head, ("aux",)))
                          or any((c.lemma or "").lower() in
                                 ("maybe", "probably", "perhaps", "possibly",
                                  "hopefully")
                                 for c in s.children(head, ("advmod",)))
                          or any((w.lemma or "").lower() in
                                 ("dream", "hypothetical", "game", "story",
                                  "novel", "discord", "server")
                                 for w in s.subtree(head)))
                # 2026-10-03 (stale dev set): "They made me a senior
                # designer" -- "make" with the owner as object and a noun
                # complement is the same unnamed employer
                made_x = ((head.lemma or "").lower() == "make"
                          and any(c.upos == "NOUN"
                                  for c in s.children(head, ("xcomp",))))
                owner_obj = (role == "user" and subj.upos == "PRON"
                             and subj.text.lower() == "they" and not hedged
                             and ((head.lemma or "").lower() in AGENTLESS_EMPLOY
                                  or made_x)
                             and next((c for c in s.children(head, ("obj",))
                                       if c.text.lower() in allow), None))
                if sp is None and not is_self and owner_obj and not neg:
                    # 2026-10-02 (false-memory bench): "They promoted me to
                    # senior analyst" is "I was promoted to senior analyst";
                    # "they" is the employer, unnamed. Dropped before.
                    rest = sorted((c for c in args if c.id != owner_obj.id),
                                  key=lambda c: c.id)
                    tail = " ".join(s.text(c, owner=o, second=second)
                                    for c in rest)
                    tail = re.sub(r"\s+", " ", tail).strip(" ,.;:!")
                    be = "was" if "Tense=Past" in (head.feats or "") else "is"
                    prt = " ".join(c.text for c in
                                   s.children(head, ("compound:prt",)))
                    body = f"{o} {be} {head.text} {prt} {tail}"
                    records.append((body, "event",
                                    _pred_key(s, head, rest), tail))
                elif sp is None and not is_self:
                    # review round 3: "Maybe cooking makes me happy" lost
                    # its hedge here, and "Cooking makes me." said nothing
                    hedged_tp = any((c.lemma or c.text).lower() in
                                    ("maybe", "perhaps", "probably", "possibly")
                                    for c in (list(fhedge or [])
                                              + list(s.children(head, ("advmod",)))))
                    only_owner = (tpo and not any(
                        c.text.lower() not in allow for c in args
                        if c.upos not in ("PUNCT", "CCONJ", "SCONJ")))
                    if (tpo or named_tpo or world_subj) and (hedged_tp or only_owner):
                        pass
                    elif tpo or named_tpo or world_subj:
                        # E (e240) / RULE 3 (e243), verbal predicate.
                        full_drop = {c.id for c in s.children(head, SEPARATE)}
                        full_drop |= {c.id for c in
                                      s.children(head, ("mark",))}  # stray_complementizer
                        # e276 [FACT INVERSION]: negdrop was here too, with
                        # no `npfx` to compensate -- same defect as the
                        # copular branch above, on the passive/verbal path:
                        #   "The billing service is not written in Go"
                        #      -> "The billing service is written in Go"
                        # This branch renders the clause verbatim, so the
                        # negation must stay in it.
                        full_drop |= fdrop
                        body = s.text(head, stop=full_drop, owner=o, second=second)
                        tail = " ".join(s.text(c, owner=o, second=second)
                                         for c in sorted(args, key=lambda c: c.id))
                        if ftail:
                            ftxt = " ".join(s.text(c, owner=o, second=second)
                                             for c in ftail)
                            body = f"{body} {ftxt}".strip()
                            tail = f"{tail} {ftxt}".strip()
                        if body:
                            kind = ("relationship" if named_tpo or
                                    any(t.upos == "PROPN" for t in s.subtree(subj))
                                    else "event")
                            pred = _pred_key(s, head, args, slot=subj.lemma)
                            value = tail
                            records.append((body, kind, pred, value))
                else:
                    # e243, RULE 1: ATOM + FULL, same split as the copular
                    # branch above, on the clause's own ARG_DEPS children.
                    peri = _periphery(s, head)
                    args_sorted = sorted(args, key=lambda c: c.id)
                    # advmod_between_verb_and_obj: `lead` (the owner's
                    # stand-in) is always rendered before `verb`, and every
                    # arg after that -- so an adverb that sat BEFORE the
                    # verb in the source ("I RECENTLY visited a sanctuary")
                    # got shoved to the far end ("visited RECENTLY a
                    # sanctuary"), because nothing distinguished it from a
                    # genuinely post-verbal one. Pull it out of the arg list
                    # and put it back where the subject/verb boundary was.
                    preverb = sorted((c for c in args_sorted
                                       if c.deprel == "advmod"
                                       and subj.id < c.id < head.id),
                                      key=lambda c: c.id)
                    if fhedge:  # e271: re-placed, not dropped
                        preverb = list(fhedge) + preverb
                    if preverb:
                        args_sorted = [c for c in args_sorted
                                       if c not in preverb]
                    args_core = ([c for c in args_sorted if c.id not in peri]
                                 if peri else args_sorted)
                    tail_full = " ".join(s.text(c, owner=o, second=second)
                                          for c in args_sorted)
                    tail_core = (" ".join(s.text(c, owner=o, second=second)
                                           for c in args_core)
                                 if peri else tail_full)
                    if ftail:
                        ftxt = " ".join(s.text(c, owner=o, second=second)
                                         for c in ftail)
                        tail_full = f"{tail_full} {ftxt}".strip()
                        tail_core = f"{tail_core} {ftxt}".strip()
                    tail_full = re.sub(r"\s+", " ", tail_full).strip(" ,.;:")
                    tail_core = re.sub(r"\s+", " ", tail_core).strip(" ,.;:")
                    if not tail_full and not _life_event(s, head):
                        continue
                    if len(tail_full.split()) > 24:
                        continue
                    if (not tail_core and tail_full) or len(tail_core.split()) > 24:
                        tail_core, peri = tail_full, set()  # core guard

                    if obj_ctrl:
                        # e243, RULE 2: the inherited subject is an OBJECT
                        # CONTROL construction, not a finite clause -- the
                        # aux/agreement machinery below assumes a subject
                        # this clause's own verb agrees with, which does
                        # not apply to a bare gerund/participle. Best-
                        # effort past-tense inflection is not attempted;
                        # the gerund/participle is kept as Stanza gave it.
                        verb = ("not " + head.text) if neg else head.text
                    else:
                        aux = [c for c in s.children(head, ("aux", "aux:pass"))]
                        if not aux and donor is not None:
                            # A (e240): the conjunct that borrowed its SUBJECT
                            # from the donor also has no aux of its own when
                            # the donor's tense/aspect is what it is
                            # coordinated under -- "I am ... enhancing X but
                            # also contributing to Y" needs the donor's "am"
                            # (-> "is") to say "is contributing", not
                            # "contributing".
                            aux = s.children(donor, ("aux", "aux:pass"))
                        # plural_head_singular_agr: re-agreeing to 3rd-
                        # singular is only correct when the OWNER'S NAME is
                        # itself the rendered subject (`is_self`, sp is
                        # None) -- when the subject is a POSSESSED noun
                        # ("my friends", "my colleague's insights"), the
                        # clause's real subject is that noun, whose number
                        # the source sentence already agreed correctly.
                        # Forcing singular turned "friends ... have played"
                        # into "... has played".
                        agree = is_self
                        if aux and neg and (aux[0].lemma or "").lower() == "get":
                            # "I never got divorced" read "got not divorced";
                            # "did not get" is not in the turn and failed the
                            # grounding check, so keep the user's own words
                            if any((c.lemma or "").lower() == "never"
                                   for c in s.children(head, ("advmod",))):
                                verb = f"never {aux[0].text}"
                            else:
                                d = ("did" if "Tense=Past" in (aux[0].feats or "")
                                     else "does" if agree else "do")
                                verb = f"{d} not get"
                            verb += " " + " ".join(
                                _expand_clitic(a.text, a.lemma)
                                if a.text.startswith("'") else a.text
                                for a in aux[1:] if a is not aux[0])
                            verb = verb.strip() + " " + head.text
                        elif aux:
                            verb = (_third(aux[0].text, aux[0].lemma, aux[0].feats)
                                    if agree else aux[0].text)
                            verb = _expand_clitic(verb, aux[0].lemma)
                            if neg:
                                verb += " not"
                            verb += " " + " ".join(
                                # same clitic problem as `_third`, one slot along
                                _expand_clitic(a.text, a.lemma)
                                if a.text.startswith("'") else a.text
                                for a in aux[1:] if a is not aux[0])
                            verb = verb.strip() + " " + head.text
                        else:
                            verb = (_third(head.text, head.lemma, head.feats)
                                    if agree else head.text)
                            if neg:
                                # "I never retired" read "does not retire"
                                if "Tense=Past" in (head.feats or ""):
                                    verb = f"did not {head.lemma}"
                                else:
                                    verb = (f"does not {head.lemma}" if agree
                                            else f"do not {head.lemma}")
                    slot_txt = (s.text(subj, stop={sp.id}, owner=o, second=second)
                                if sp is not None else None)
                    lead = o if sp is None else f"{o}'s {slot_txt}"
                    if preverb:
                        # 2026-10-02: "I'm still nursing" rendered "<owner>
                        # still is nursing". An adverb that sat AFTER the
                        # first auxiliary goes back there, just before the
                        # verb ("is still nursing", "does not really like");
                        # one before it stays in front ("really does not").
                        auxs = s.children(head, ("aux", "aux:pass"))
                        a0 = min((a.id for a in auxs), default=None)
                        inner = ([c for c in preverb if c.id > a0]
                                 if a0 is not None and not obj_ctrl else [])
                        outer = [c for c in preverb if c not in inner]
                        if inner and " " in verb:
                            vparts = verb.rsplit(" ", 1)
                            verb = f"{vparts[0]} " + " ".join(
                                s.text(c, owner=o, second=second)
                                for c in inner) + f" {vparts[1]}"
                        else:
                            outer = preverb
                        if outer:
                            lead = f"{lead} " + " ".join(
                                s.text(c, owner=o, second=second) for c in outer)
                        lead = re.sub(r"\s+", " ", lead).strip()
                    # E (e240): the owner-possession chain can pass through a
                    # named third party -- "my FRIEND THOMAS's support" -- in
                    # which case the fact is a relationship, not a bare event.
                    kind = ("relationship"
                            if sp is not None and
                            any(t.upos == "PROPN"
                                for t in s.subtree(subj, stop={sp.id}))
                            else "event")
                    pred = _pred_key(s, head, args, slot=slot_txt)
                    # 2026-10-02: a phrasal verb keeps its particle -- "I grew
                    # up in Leeds" rendered "grew in Leeds", "I gave up
                    # smoking" lost the "up" that carries the meaning.
                    prt = [c for c in s.children(head, ("compound:prt",))
                           if c.text.lower() not in verb.lower().split()]
                    if prt:
                        verb = f"{verb} {' '.join(c.text for c in prt)}"
                    npfx = "not " if neg else ""
                    # 2026-10-03 (stale dev set): "I no longer work at Acme"
                    # had the value "at Acme" and was merged into "works at
                    # Acme Logistics" as a repeat -- the ending vanished and
                    # the old job looked as recent as the new one. An
                    # ending marker belongs to the value.
                    if not neg and (any(
                            (c.lemma or "").lower() == "long"
                            and any((g.lemma or "").lower() == "no"
                                    for g in s.children(c, ("advmod",)))
                            for c in s.children(head, ("advmod",)))
                            or any((c.text or "").lower() in ("anymore",)
                                   for c in s.children(head, ("advmod",)))):
                        npfx = "no longer "
                    value = npfx + tail_core             # (a): core, e243
                    if peri and tail_core != tail_full:
                        records.append((f"{lead} {verb} {tail_core}",
                                         kind, pred, value))
                    records.append((f"{lead} {verb} {tail_full}",
                                     kind, pred, value))

            for body, kind, pred, value in records:
                body = re.sub(r"\s+", " ", body).strip(" ,.;:")
                # "won't" / "can't" split as "wo" / "ca" + "n't"
                body = re.sub(r"\bwo not\b", "will not", body)
                body = re.sub(r"\bca not\b", "cannot", body)
                body = re.sub(r"\bsha not\b", "shall not", body)
                # D (e240): a record that STILL carries a bare first-person
                # token in an assistant turn is the assistant talking about
                # itself, not the user -- the safety net for whatever a
                # clause structure this walker did not anticipate lets
                # through.
                if second and _FIRST_RESIDUE.search(body):
                    continue
                if owner_pronoun:
                    body = _pronominalize(body, o, owner_pronoun,
                                           owner_pronoun_obj)
                key = body.lower()[:90]
                if body and key not in seen:
                    seen.add(key)
                    # e242: evidentiality is assistant-turn only -- a user's
                    # own "I remember I used to..." is not the assistant
                    # relaying a claim about the user, it is the user's own
                    # report.
                    evidential = None
                    if second and (hedge or _report_frame(s, head)
                                   or _generic_or_expl_frame(s, head)):
                        evidential = "report"
                    value = re.sub(r"\s+", " ", value).strip(" ,.;:")
                    if owner_pronoun:
                        value = _pronominalize(value, o, owner_pronoun,
                                                owner_pronoun_obj)
                    if with_source:
                        # 2026-10-02: the sentence this record was read
                        # from, VERBATIM. The proposition is a rewrite and
                        # every inversion class since e240 lived in the
                        # rewrite; the source sentence cannot be inverted.
                        out.append((body, kind, pred, value, evidential,
                                    sent.text))
                    else:
                        out.append((body, kind, pred, value, evidential))
        # e267_CARRY_UPDATE: only AFTER the whole sentence is walked, so a
        # pronoun never resolves to a noun from its own sentence.
        poss_carry.update(sent_poss)
    return out
