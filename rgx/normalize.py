"""Parse normalisation before the rules (2026-10-15, the EWT-only parser).

Parsers disagree on a few constructions sentence by sentence, and the rules
were written against one reading of each. Rewriting the other reading into
the first here keeps every rule working whichever parser produced the
parse. Each rewrite turns one valid UD analysis into another of the same
sentence; it never adds or drops a word.

- get-passive. "I got divorced", "Got promoted to team lead": Stanza's
  combined models usually make the participle the root with "got" as
  aux:pass; the EWT-only models often make "got" the root with the
  participle as its xcomp. The rules read the first.
- "neither ... nor" on the subject (_preconj), "do not <phrase> <verb>"
  (_neg_before_obl), a subject pronoun read as an object (_pron_subject),
  "tea, never coffee" (_neg_conjunct), "I'm married" (_state_participle),
  verb lemmas (_lemmas).
"""


def _get_passive(words):
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    for g in words:
        if (g.lemma or "").lower() != "get" or g.upos not in ("VERB", "AUX"):
            continue
        cs = kids.get(g.id, [])
        v = next((c for c in cs if c.deprel == "xcomp" and c.xpos == "VBN"
                  and c.id > g.id), None)
        if v is None:
            continue
        # "got it fixed", "got him promoted", "got told that ...": not a passive of the subject
        if any(c.deprel in ("obj", "iobj", "ccomp", "expl") for c in cs):
            continue
        if any(c.deprel.startswith(("nsubj", "csubj"))
               for c in kids.get(v.id, [])):
            continue
        # only adverbs between "got" and the participle ("got finally promoted")
        if any(w.upos != "ADV" for w in words if g.id < w.id < v.id):
            continue
        v.head, v.deprel = g.head, g.deprel
        for c in cs:
            if c is v:
                continue
            c.head = v.id
            if c.deprel == "nsubj":
                c.deprel = "nsubj:pass"
        g.head, g.deprel, g.upos = v.id, "aux:pass", "AUX"


def _preconj(words):
    """"Neither my wife nor I like ...": the combined models attach
    "neither" to the first conjunct as cc:preconj, the EWT-only models
    often to the verb as cc. The rules (_preconj_negation) read the first."""
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    for n in words:
        if (n.lemma or "").lower() not in ("neither", "either", "both") or n.deprel != "cc":
            continue
        pair = {"neither": ("nor",), "either": ("or",), "both": ("and",)}[(n.lemma or "").lower()]
        # the first nominal after it with a "nor"/"or"/"and" conjunct,
        # before the verb it hangs on
        for x in sorted(words, key=lambda w: w.id):
            if x.id <= n.id or x.upos not in ("NOUN", "PROPN", "PRON"):
                continue
            if n.head > n.id and x.id >= n.head:
                break
            if any(c.deprel == "conj" and any((d.lemma or "").lower() in pair
                                              for d in kids.get(c.id, []) if d.deprel == "cc")
                   for c in kids.get(x.id, [])):
                n.head, n.deprel = x.id, "cc:preconj"
                break


def _neg_before_obl(words):
    """"Do not under any circumstances touch the prod db": the EWT-only
    models attach "not" to "circumstances"; it negates the verb, as the
    combined models have it (the instruction rule reads the verb's own
    "not")."""
    by = {w.id: w for w in words}
    for n in words:
        if (n.lemma or "").lower() != "not":
            continue
        h, prev = by.get(n.head), by.get(n.id - 1)
        if (h is not None and h.upos in ("NOUN", "PROPN") and h.deprel in ("obl", "nmod")
                and prev is not None and prev.upos == "AUX"
                and (prev.lemma or "").lower() == "do" and prev.head == h.head):
            n.head = h.head


_NOM = frozenset(("i", "you", "he", "she", "we", "they"))


def _pron_subject(words):
    """"... mentioning you play the cello": the EWT-only models can make
    "you" the object of "mentioning" and leave "play" (its ccomp, the next
    word) with no subject. A subject pronoun right before a subjectless
    ccomp verb is that verb's subject."""
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    for p in words:
        if p.deprel != "obj" or p.upos != "PRON" or p.text.lower() not in _NOM:
            continue
        c = next((k for k in kids.get(p.head, []) if k.deprel == "ccomp"
                  and k.id == p.id + 1 and k.upos in ("VERB", "AUX")), None)
        if c is not None and not any(k.deprel.startswith("nsubj") for k in kids.get(c.id, [])):
            p.head, p.deprel = c.id, "nsubj"


def _neg_conjunct(words):
    """"I drink tea, never coffee": the EWT-only models make "coffee" a
    conjunct of "tea", so the object read "tea never coffee" and "drinks
    coffee" was found in it. A conjunct that carries its own "never"/"not"
    is a contrast, not part of the object: it hangs on the verb as a
    separate remark (parataxis), as the combined models have it."""
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    by = {w.id: w for w in words}
    for c in words:
        h = by.get(c.head)
        if (c.deprel != "conj" or h is None or c.upos not in ("NOUN", "PROPN")
                or h.deprel not in ("obj", "obl", "nsubj")):
            continue
        if any((k.lemma or "").lower() in ("never", "not") and k.deprel == "advmod"
               for k in kids.get(c.id, [])):
            c.head, c.deprel = h.head, "parataxis"


def _state_participle(words):
    """"I'm married": the EWT-only models read a passive (aux:pass "'m",
    VBN "married", lemma "marry"), the combined models an adjective with a
    copula; the rules file the second as a state ("is married") and the
    first as an event, so "I got divorced" no longer replaced it. A
    participle the rules list as a state adjective (fragments.STATE_ADJ),
    passive with "be" and with no agent or object, is that adjective."""
    from .fragments import STATE_ADJ
    kids = {}
    for w in words:
        kids.setdefault(w.head, []).append(w)
    for v in words:
        if v.xpos != "VBN" or v.text.lower() not in STATE_ADJ:
            continue
        cs = kids.get(v.id, [])
        be = [c for c in cs if c.deprel == "aux:pass" and (c.lemma or "").lower() == "be"]
        if not be or any(c.deprel in ("obl:agent", "obj", "iobj") for c in cs):
            continue
        v.upos, v.xpos, v.lemma, v.feats = "ADJ", "JJ", v.text.lower(), "Degree=Pos"
        for c in be:
            c.deprel = "cop"
        for c in cs:
            if c.deprel == "nsubj:pass":
                c.deprel = "nsubj"


_VOCAB = None


def _vocab():
    """Every word in the rules' own word lists (module-level sets of
    strings in rgx.parse and rgx.fragments)."""
    global _VOCAB
    if _VOCAB is None:
        from . import fragments, parse
        v = set()
        for mod in (parse, fragments):
            for x in vars(mod).values():
                if isinstance(x, (set, frozenset)):
                    v |= {w for w in x if isinstance(w, str) and w.isalpha()}
                elif isinstance(x, dict):
                    v |= {w for w in x if isinstance(w, str) and w.isalpha()}
        _VOCAB = v
    return _VOCAB


def _stems(form):
    """Base-form candidates of an -ed / -ing form, most likely first."""
    out = []
    for suf in ("ed", "ing"):
        if form.endswith(suf) and len(form) > len(suf) + 2:
            b = form[:-len(suf)]
            out += [b + "e", b]
            if len(b) > 2 and b[-1] == b[-2]:
                out.append(b[:-1])                      # stopped -> stop
            if suf == "ed" and b.endswith("i"):
                out.append(b[:-1] + "y")                # married -> marry
    if form.endswith("ied"):
        out.insert(0, form[:-3] + "y")
    return out


def _lemmas(words):
    """- verb lemmas. "divorced" lemmatised as "divorced" (the EWT-only
      lemmatiser, 2026-10-15) missed the rules' LIFE_EVENTS "divorce". A
      verb (VERB/AUX, VBD/VBN/VBG) whose lemma is its own -ed/-ing form
      takes the base form when the lists have it ("divorced" is also in
      the lists, as a state adjective)."""
    vocab = _vocab()
    for w in words:
        if w.upos not in ("VERB", "AUX") or w.xpos not in ("VBD", "VBN", "VBG"):
            continue
        lem = (w.lemma or "").lower()
        if lem != w.text.lower():
            continue
        base = next((c for c in _stems(lem) if c in vocab), None)
        if base:
            w.lemma = base


def normalize(doc):
    """-> doc, rewritten in place (idempotent)."""
    for s in doc.sentences:
        _get_passive(s.words)
        _preconj(s.words)
        _neg_before_obl(s.words)
        _pron_subject(s.words)
        _neg_conjunct(s.words)
        _state_participle(s.words)
        _lemmas(s.words)
    return doc
