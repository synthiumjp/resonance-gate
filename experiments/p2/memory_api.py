"""p2 QUERY CONTRACT: the interface an LLM connects to.

This is the facade over GROW (belief/corroboration) + WIRE (receipted
co-occurrence graph): a Memory object with exactly the read contract the
product promises --

  recall(query)  -> asserted facts (corroborated, receipted)
                  + wired neighbourhood (receipted edge paths)
                  + provisional single-mentions (labeled UNCONFIRMED)
                  | ABSTAIN ("never seen") -- never a guess.

  context_block(query=None) -> a verbatim, receipted text block for injection
    into an LLM prompt. NON-GENERATIVE: every line is a stored fact with its
    receipt count; the block carries the standing instruction that anything
    not in the block is unknown and must not be invented. The LLM stays the
    fallible creative client; the block is the stable substrate speaking.

No model call on the READ path -- load(), recall(), profile() and
context_block() are pure python over the store, which is what "the stable
substrate speaking" above means and what every QA number rests on.

ONE EXCEPTION, corrected in e249: conflicts() calls consolidate.contradicts(),
which lazy-loads a LOCAL NLI classifier (cross-encoder/nli-deberta-v3-xsmall,
CPU) to decide whether two values of a slot can both hold. Nothing remote and
nothing generative -- and it degrades to None, letting the caller fall back to
the lexical path, if transformers is unavailable. But it is a model call, and
this docstring claimed for a long time that there were none anywhere in the
module. If you need a guaranteed model-free surface, use everything except
conflicts().
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from wire import WireGraph

# e261: this said "The facts above are corroborated" while the block rendered
# UNCONFIRMED lines beside them -- the rules described one tier and the block
# showed two. Every line now states its own standing, and the rules say what
# each standing means rather than asserting one for all of them.
_RULES = ("[MEMORY RULES] Every line above is a stored fact from the user's own "
          "history, never an inference. A line with a mention count is "
          "CORROBORATED (the user said it more than once). A line marked "
          "UNCONFIRMED was seen once and is not established -- you may use it, "
          "but do not state it back as settled; if it matters, ask the user to "
          "confirm it. Anything about the user NOT listed here is UNKNOWN to "
          "you: say you don't know rather than guessing.")


def _rv3():
    import retrieve_v3
    return retrieve_v3


class _LazyRV3:
    def __getattr__(self, k):
        return getattr(_rv3(), k)


_RV3 = _LazyRV3()

# Cross-encoder score below which recall_v3 abstains.
#
# e260: with e259's garbage node gone, the two populations separate CLEANLY on
# this store -- answerable questions score >= -7.72, never-mentioned ones
# <= -7.94, no overlap, 18/18. Before the parser fix they overlapped (known-min
# -7.72 vs unseen-max -7.45), because "<owner> did not know which" ranked first
# for nearly every unanswerable question and dragged its scores up. Fixing a
# render defect made the evidence signal separable; that is the finding, not
# the number.
#
# Two margin-based alternatives were tested and are WORSE: top1-minus-median
# and top1-minus-2nd both split 16/18 with overlapping populations.
#
# STILL A PILOT VALUE, and now openly fitted: the midpoint of an 18-point
# sample on one synthetic store. Re-derive on held-out questions before
# quoting it. What transfers is that an absolute floor on the cross-encoder
# score is the right mechanism, not that it is -7.83.
# e277: MEASURED INERT, AND COSTLY. With grounding on (the shipped default),
# sweeping this from -9.5 to -6.0 leaves abstention at exactly 9/9 the whole
# way; disabling it entirely leaves abstention 9/9 AND recovers a true answer
# (pool 24/26 -> 25/26). Grounding accounts for 100% of the abstention
# property on this store; the floor accounts for none of it and suppresses
# one real fact.
#
# e274/e275 described the two as "independent signals, both pulling weight".
# That was true when written -- of the 14-node store -- and stopped being true
# without anyone re-checking. Default is now None (off). The mechanism stays,
# because 5o's argument cuts both ways: grounding is also unvalidated at
# scale, and if it fails on a real store this is the belt to re-fasten.
FLOOR_V3 = None


# e274: WHICH PREDICATE KEYS HOLD ONE VALUE.
#
# `consolidate.SINGLE_VALUED` is a 24-name allowlist written for the LLM
# extractor's slot names. The deterministic parser keys on PREDICATES
# (`live_in`, `favourite_language`), none of which are in it, so "I live in
# Berlin" then "I live in Munich" raised no conflict at all -- two equally
# current facts and an agent left to pick. The server README promises the
# opposite: "surfaces conflicts rather than silently picking".
#
# The first attempt simply widened the candidate set to every attribute with
# two distinct values and let NLI arbitrate. MEASURED, THAT IS WORSE: NLI
# called "like: rust" vs "like: python" a contradiction, and "have: a dog" vs
# "have: a cat". The allowlist was doing real work -- restricting NLI to slots
# where substitution is the NORM. Its fault is coverage, not existence.
#
# So this extends it on a linguistic signal instead. A SUPERLATIVE or
# uniqueness modifier ("favourite", "main", "primary", "current") makes a slot
# single-valued by construction, and a handful of predicates are inherently
# unique. Everything else keeps accumulating, which is correct: a person may
# like many languages and own several pets.
_UNIQUE_MODIFIERS = ("favourite", "favorite", "main", "primary", "current",
                     "best", "preferred", "usual", "only")
_UNIQUE_PREDS = frozenset((
    "live_in", "born_in", "bear_in", "name", "age", "birth_date",
    "marry_to", "married_to", "reside_in"))


def _single_valued(attr):
    a = (attr or "").lower()
    if a in _UNIQUE_PREDS:
        return True
    return any(m in a for m in _UNIQUE_MODIFIERS)


# e272: SUBJECT-POSITION RE-RANK.
#
# Every remaining recall miss on the product harness had the same shape: the
# record containing the question's WORDS beat the record containing its
# ANSWER.
#
#   "What language is the billing service in?"
#      1. Alex works on the billing service        <- matches, answers nothing
#      2. the billing service is written in Go     <- the answer
#
# The distinction is grammatical, not lexical: the answer has the queried
# entity as its SUBJECT, the distractor has it as an object. A cross-encoder
# this small does not reliably see that; a lead-position check does, for free.
#
# APPLIED AFTER THE FLOOR, NEVER BEFORE. The bonus only reorders records that
# already cleared the abstention threshold on their RAW score, so it cannot
# make a never-mentioned topic answerable. That is a structural guarantee
# rather than a measured one -- the alternative (boost, then floor) tested
# identically on 7 unseen questions, which is not enough evidence to rest an
# abstention promise on.
_RERANK_STOP = frozenset("""
what who where when which why how do does did is are was were am be been the
a an my your our i me we us of in on at for to about know any there thing
""".split())
SUBJECT_BONUS = 6.0     # plateau on the dogfood set; below it, monotone
# e273: how far a superseded fact drops. Large enough to lose to any current
# fact that matched at all, small enough that a stale fact still beats nothing
# -- "you told me X, but that was before you told me Y" is a better answer
# than silence.
STALE_PENALTY = 20.0


def _stem(t):
    # e281: was `len(t) > 4`, so a 3-letter noun never lost its plural --
    # "dogs"/"dog", "cars"/"car", "jobs"/"job" shared no stem and the lexical
    # route could not ground exactly the short everyday nouns it exists for.
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def _owner_stems(owner):
    """The owner's name as stems, so grounding can ignore it. e281: every
    rendered fact begins with the owner's name, so any question that names
    the owner shared a "content word" with every record in the store --
    "What is Alex Reyes's blood type?" grounded on "Alex Reyes uses Postgres"
    and came back found=True with receipts. A name is not evidence about a
    topic."""
    import re as _re
    if not owner:
        return set()
    return {_stem(t) for t in _re.findall(r"[a-z]+", str(owner).lower())}


def _guess_owner(nodes, min_share=0.4):
    """The owner's name read off the store itself: the rgx renderer starts
    every owner-subject proposition with the owner's full name, so the most
    common leading two-word prefix of the record texts IS the name when it
    carries at least `min_share` of them. Used only when no caller supplied
    the owner and no `name` fact exists (e281: the dogfood store had neither,
    so the name-based lookup returned None and the fix was inert)."""
    import re as _re
    from collections import Counter
    texts = [nd.get("text") or "" for nd in nodes if nd.get("text")]
    if len(texts) < 3:
        return None
    c = Counter()
    for t in texts:
        w = _re.findall(r"[A-Za-z][a-z]+", t)
        if len(w) >= 2 and w[0][0].isupper() and w[1][0].isupper():
            c[f"{w[0]} {w[1]}"] += 1
    if not c:
        return None
    name, n = c.most_common(1)[0]
    return name if n / len(texts) >= min_share else None


def _entity_names(hits):
    """Capitalised, non-initial tokens in the retrieved records: the names the
    store knows (e281b). Lower-cased, unstemmed."""
    import re as _re
    out = set()
    for h in hits or []:
        for w in _re.findall(r"(?<!^)(?<=\s)[A-Z][a-z]+", h.get("text") or ""):
            out.add(w.lower())
    return out


def _strip_owner(query, owner, extra_names=()):
    """The query without the owner's name tokens (and any `extra_names`, the
    entities the retrieved records mention), for the dense route -- a name
    inflates cosine against every record that carries it, whatever was asked."""
    import re as _re
    names = set(extra_names or ())
    if owner:
        names |= {t for t in _re.findall(r"[a-z]+", str(owner).lower())}
    if not names:
        return query
    kept = [w for w in (query or "").split()
            if _re.sub(r"[^a-z]", "", _re.sub(r"'s\b", "", w.lower()))
            not in names]
    return " ".join(kept) or query


# e275: DENSE GROUNDING THRESHOLD. Lexical grounding alone rejects PARAPHRASE,
# which is what real questions are: "What is my role at work?" shares no
# content word with "is a backend engineer there". The corpus had exactly one
# such case, so lexical-only looked almost free -- a corpus weakness read as
# evidence. With a proper paraphrase set the two populations are:
#
#   answerable, not lexically grounded   0.639 .. 0.748
#   never mentioned                      0.506 .. 0.600
#
# 0.62 sits between them. Openly fitted, on 13 points, one store -- the same
# caveat as every constant in this file, and the reason the LEXICAL route is
# kept as well rather than replaced: two cheap independent signals degrade
# more gracefully than one tuned one.
DENSE_GROUND = 0.62

# ---------------------------------------------------------------------------
# THE GATES (e280). A refusal is an EMPTY RESULT SET, not a model being
# humble: every abstention on the v3 read path is decided by one of these
# named predicates BEFORE any renderer or model sees the query, and the
# returned dict names the gate that fired. `GATE_COUNTS` accumulates per
# process so a harness can print a read-path refusal matrix -- which gate,
# how often -- the way rgx/refusal_cases.py does for the parser. Order is
# the order they are evaluated in recall_v3.
GATES = (
    "empty-store",       # nothing stored at all
    "no-candidates",     # retrieval returned nothing
    "score-floor",       # best raw cross-encoder score under FLOOR_V3 (off by default)
    "grounding",         # no retrieved record shares a content word, and none is dense-close
    "no-renderable",     # candidates existed but none resolved to a stored node
)
GATE_COUNTS = {g: 0 for g in GATES}


def gate_report():
    """{gate: refusals so far in this process}. Reset with gate_reset()."""
    return dict(GATE_COUNTS)


def gate_reset():
    for g in GATE_COUNTS:
        GATE_COUNTS[g] = 0


def _dense_grounded(index, query, threshold=None):
    """True when the best stored fact is semantically close to the question.

    Returns True (defers) if the index has no embeddings -- a missing signal
    must never be read as evidence of absence.
    """
    thr = DENSE_GROUND if threshold is None else threshold
    emb = getattr(index, "emb", None)
    if emb is None or len(emb) == 0:
        return True
    try:
        import numpy as np
        bi, _ = _RV3._models()
        qv = bi.encode([query], normalize_embeddings=True)[0]
        return float(np.max(emb @ qv)) >= thr
    except Exception:
        return True


def _grounded(query, hits, owner=None):
    """True when any candidate shares a content word with the question.

    Deliberately weak: ONE shared token is enough. This is a floor on
    evidence, not a relevance judgement -- the reranker does relevance. Its
    job is to catch the case where the store simply holds nothing about the
    topic and the reranker returned its least-bad guess anyway.
    """
    import re as _re
    q = {_stem(t) for t in _re.findall(r"[a-z]+", (query or "").lower())
         if t not in _RERANK_STOP and len(t) > 2}
    q -= _owner_stems(owner)    # e281: the owner's name grounds nothing
    # e281b: nor does anyone else's. A capitalised token that is not
    # sentence-initial in a retrieved record is a NAME the store knows (Sam,
    # Priya, Acme); sharing it says the question is about a known entity,
    # not that the record answers what was asked -- "What is Sam's salary?"
    # grounded on "partner Sam works from home". With the names gone the
    # question must share a real content word, or hold nothing but names,
    # in which case it defers ("Who is Sam?" still answers).
    names = set()
    for h in hits:
        text = h.get("text") or ""
        for w in _re.findall(r"(?<!^)(?<=\s)[A-Z][a-z]+", text):
            names.add(_stem(w.lower()))
    if q and q <= names:
        return True             # the question IS the entity; nothing else to ground
    q -= names
    if not q:
        return True             # nothing to ground against; defer to the floor
    for h in hits:
        text = h.get("text") or f"{h.get('attr')} {h.get('value')}"
        ts = {_stem(t) for t in _re.findall(r"[a-z]+", text.lower())}
        if q & ts:
            return True
    return False


def _subject_bonus(query, text, bonus=None):
    """How much to lift a record whose SUBJECT REGION answers the query."""
    import re as _re
    b = SUBJECT_BONUS if bonus is None else bonus
    q = [t for t in _re.findall(r"[a-z]+", (query or "").lower())
         if t not in _RERANK_STOP]
    if len(q) < 2:
        return 0.0
    lead = " ".join((text or "").lower().split()[:5])
    hits = sum(1 for t in q if t in lead)
    # TWO content tokens, not one: a single incidental match ("work" in "works
    # from home") is exactly the distractor this is meant to demote.
    return b * hits if hits >= 2 else 0.0


def _mark_ceased(g, titles=None):
    if os.environ.get("RG_CESSATION") == "0":
        return
    import currency
    # `titles` is insertion-ordered by ingestion, which is the only real
    # sequence available when several conversations share a date (e273).
    order = {c: i for i, c in enumerate(titles or {})}
    currency.mark_ceased(g, order=order or None)


class Memory:
    """Read-side memory over the wired, corroborated profile."""

    def __init__(self, graph, titles=None, owner=None):
        self.g = graph
        self.titles = titles or {}
        # e281: the owner's name, when the caller knows it (the server does:
        # it hands the same name to the extractor). Grounding must ignore it.
        self.owner = owner

    @classmethod
    def load(cls, conversations_path, min_mentions=2):
        """Build from conversations.json + the extraction cache next to it
        (cache-only; no LLM calls). Owner corrections (corrections.jsonl in the
        same dir) are applied INSIDE build_facts, at the fact level, before
        wiring -- so graph, report and recall stay consistent. The graph-level
        apply_corrections below remains for runtime (in-session) deny/confirm."""
        from run_wire import build_facts
        facts, prov, hearsay, n_convs, titles, _ = build_facts(
            conversations_path, min_mentions)
        g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov,
                                 hearsay=hearsay)
        _mark_ceased(g, titles)
        return cls(g, titles)

    def apply_corrections(self, corrections):
        """THE CORRECTION LOOP (owner-authored; the owner is ground truth).
        Each correction: {"action": "deny"|"confirm", "attribute": <canon attr>,
        "value": <substring of the fact value>}.
          deny    -> the fact is wrong: remove it from BOTH tiers, and remove
                     its edges (an edge to a wrong fact is receipted noise).
          confirm -> owner-vouched: a provisional fact is PROMOTED to asserted
                     (the confirmation IS the second piece of evidence); an
                     asserted fact is marked owner-confirmed.
        Corrections are data (a local owner-edited file), never inference."""
        applied = []
        for c in corrections:
            act = c.get("action")
            attr = str(c.get("attribute", "")).lower().strip()
            sub = str(c.get("value", "")).lower().strip()
            for store in (self.g.nodes, self.g.provisional):
                for nid in [k for k, d in store.items()
                            if d["attr"] == attr and sub in d["value"].lower()]:
                    if act == "deny":
                        store.pop(nid)
                        for pair in [p for p in self.g.edges if nid in p]:
                            self.g.edges.pop(pair)
                        self.g.adj.pop(nid, None)
                        for nbrs in self.g.adj.values():
                            nbrs.pop(nid, None)
                        applied.append(("denied", nid))
                    elif act == "confirm":
                        nd = store.pop(nid)
                        nd["tier"] = "asserted"
                        nd["owner_confirmed"] = True
                        nd["n_mentions"] += 1   # the confirmation is evidence
                        self.g.nodes[nid] = nd
                        applied.append(("confirmed", nid))
        return applied

    # ---------------- the contract ----------------

    def recall(self, query, max_hops=2, top=12):
        """The product's read call. Structured, receipted, or an honest no."""
        r = self.g.spread(query, max_hops=max_hops, top=top)
        if r.get("abstain"):
            return {"found": False, "abstain": True, "query": query,
                    "answer": "no stored fact matches -- never seen"}
        # e273: a superseded fact ranks last on THIS path too. Currency is a
        # correctness property -- "you told me X" when the user has since said
        # otherwise is wrong regardless of which retriever found it -- so it
        # cannot live only in recall_v3. Demoted, never dropped.
        def _stale_last(nodes):
            return sorted(nodes, key=lambda nd: nd.get("current") is False)

        out = {"found": True, "abstain": False, "query": query,
               "asserted": [self._fact(nd) for nd in _stale_last(r["seeds"])],
               "wired": [{"fact": self._fact(d["node"]),
                          "activation": round(d["activation"], 3),
                          "hops": d["hops"],
                          "via": [{"edge": f"{e['a']} <-> {e['b']}",
                                   "shared_conversations": e["cooc"]}
                                  for e in d["path"]]}
                         for d in r["neighbourhood"]],
               "unconfirmed": [self._fact(p["node"], provisional=True)
                               for p in sorted(
                                   r.get("provisional", []),
                                   key=lambda p: p["node"].get("current") is False)],
               # entry 246: NOT surfaced in "asserted"/"unconfirmed" -- an
               # assistant claim about the user is neither a corroborated nor
               # an unconfirmed USER fact. Kept under its own key so a caller
               # (the MCP surface) can show it on request, receipted, without
               # it ever being volunteered as the user's own memory.
               "hearsay": [self._fact(h["node"]) for h in r.get("hearsay", [])]}
        return out

    def recall_v3(self, query, top_n=8, min_score=None):
        """The product read path under RG_PROFILE_V3 (e258).

        `recall()` seeds from `wire.match` -- token overlap between the query
        and a node's attr+value tokens, widened by a fixed synonym table. That
        is the retrieval the PRODUCT has always shipped. Retrieval v3 (BM25 u
        dense bge-small, cross-encoder rerank) has been the measured champion
        since e132 and was only ever wired into the benchmark QA path.

        THE SCORE FLOOR IS NOT OPTIONAL. Wired without one, v3 answers every
        question -- including every question about something never mentioned
        (dogfood store, e258: abstention on 8 unseen topics went 8/8 -> 0/8,
        and a garbage node ranked first for nearly all of them). Honest
        abstention is the product, so v3 without a floor is a REGRESSION even
        though its pool recall is far better. The floor restores it: the
        cross-encoder's own score separates known from unseen (KNOWN median
        -4.69, UNSEEN median -8.59 on that store).

        `min_score` defaults to RG_PROFILE_V3_FLOOR, else FLOOR_V3. That
        default was SELECTED ON THE SAME 18 QUESTIONS IT WAS SCORED ON --
        it is a pilot operating point, not a validated constant, and it needs
        a held-out set and the real harness before anyone quotes it.

        Rank order is preserved across tiers. An earlier draft bucketed the
        hits into asserted-then-unconfirmed, which threw away the reranker's
        ordering and dropped rank-1 correctness from 7/10 to 1/10 -- the
        retriever was fine and the wiring destroyed it.
        """
        nodes, prov = self.g.nodes, self.g.provisional
        if not nodes and not prov:
            return self._abstain(query, gate="empty-store")
        floor = min_score
        if floor is None:
            env = os.environ.get("RG_PROFILE_V3_FLOOR")
            floor = float(env) if env else FLOOR_V3
        idx = self._index_v3()
        # e272: fetch a WIDER pool than we return, because the re-rank below
        # cannot promote a record the retriever already truncated away. The
        # first version of this reordered the top-8 and changed nothing --
        # the answer was at rank 9.
        rerank = os.environ.get("RG_SUBJECT_RERANK") != "0"
        pool = max(top_n * 4, 24) if rerank else top_n
        scored = _RV3.retrieve_facts_v3(idx, query, k=120, dense_k=20,
                                        top_n=pool, with_scores=True)
        # e272 CORRECTION TO e258: the floor is an ABSTENTION decision, not a
        # per-record filter. The separation it rests on was measured on the
        # TOP-1 raw score (answerable >= -7.72, never-mentioned <= -7.94);
        # nothing ever validated applying it to every record, and doing so
        # silently discarded true answers that happened to rank low --
        # "the billing service is written in Go" scored under the floor and
        # was dropped before the re-rank could promote it.
        #
        # Gate on the best raw score; then return the pool. This keeps exactly
        # the property that was measured and stops the floor doing a job it
        # was never shown to do.
        if not scored:
            return self._abstain(query, idx, gate="no-candidates")
        if floor is not None and max(sc for _, sc in scored) < floor:
            return self._abstain(query, idx, gate="score-floor")
        # e274: LEXICAL GROUNDING, a second and independent abstention signal.
        #
        # The score floor degrades as the store grows -- max-of-N rises with N
        # -- and it does so silently. Measured on this store at 14 nodes the
        # two populations separated cleanly (e260, 18/18); at 38 nodes nothing
        # separates them cleanly and the best absolute cutoff costs one false
        # answer in seven ("What is my favourite film?" -> "Alex Reyes likes
        # Go"). A real store has thousands of nodes, so tuning the constant
        # further would be fitting noise.
        #
        # Grounding does not degrade that way: if NO retrieved record shares a
        # content word with the question, we hold no evidence about the topic,
        # however the reranker scored it. Measured here: 7/7 unseen rejected,
        # 19/20 answerable kept. Required TOGETHER with the floor, never
        # instead of it -- two independent signals, both must pass.
        # Grounded LEXICALLY or DENSELY -- either is enough. Lexical catches
        # the shared-word case for free; dense catches paraphrase, which is
        # what a real question usually is (e275).
        if os.environ.get("RG_GROUNDING") != "0":
            own = getattr(idx, "owner", None)
            top3 = [h for h, _ in scored[:3]]
            if not (_grounded(query, top3, owner=own)
                    or _dense_grounded(idx, _strip_owner(
                        query, own, _entity_names(top3)))):
                return self._abstain(query, idx, gate="grounding")
        kept = list(scored)
        # e272: reorder ONLY what already cleared the floor, then truncate.
        if rerank:
            # e273: a fact the user has since ENDED ranks below one that still
            # holds. Demoted, never hidden -- the receipt is permanent and a
            # caller can still see it, labeled, below the current answer.
            kept.sort(key=lambda p: -(
                p[1] + _subject_bonus(query, p[0].get("text") or "")
                - (STALE_PENALTY if p[0].get("current") is False else 0.0)))
        kept = kept[:top_n]
        # rank order preserved; `tier` says which store a fact came from so a
        # caller can still tell corroborated from single-mention.
        facts, unconfirmed = [], []
        for h, sc in kept:
            nid = h.get("id")
            if nid in nodes:
                f = self._fact(nodes[nid])
            elif nid in prov:
                f = self._fact(prov[nid], provisional=True)
            else:
                continue
            f["score"] = round(float(sc), 4)
            facts.append(f)
            if f.get("status") == "unconfirmed-single-mention":
                unconfirmed.append(f)
        if not facts:
            return self._abstain(query, idx, gate="no-renderable")
        return {"found": True, "abstain": False, "query": query,
                "asserted": [f for f in facts if f not in unconfirmed],
                "ranked": facts, "wired": self._wired_v3(kept),
                "unconfirmed": unconfirmed,
                "hearsay": self._hearsay_v3(idx, query),
                "retrieval": "v3", "floor": floor}

    def _wired_v3(self, kept):
        """The receipted co-occurrence neighbourhood of the corroborated hits.

        Review 2026-09-05: recall_v3 hardcoded `wired: []` while the MCP
        docstring promised the field, and e277 made recall_v3 the default --
        so the field went dead for every caller on the same day. Seeds are the
        CORROBORATED hits only (the provisional tier is never wired, by
        invariant); each seeds at activation 1.0 because cross-encoder logits
        are not on the [0, 1] scale `spread` assumes."""
        # Seed from the RANK-1 corroborated hit only. v3 returns a wide pool
        # (in a small store, every node), so seeding from all hits leaves no
        # node to be a neighbour and the field is empty exactly where the
        # old path filled it. "Wired" answers: what is receipted as
        # co-occurring with THE answer -- the paths carry the edge receipts.
        walk = getattr(self.g, "neighbourhood", None)
        # Review 2026-10-02: this took the first CORROBORATED hit anywhere in
        # the pool, and most of a real store is provisional -- so the seed was
        # usually a lower-ranked hit, sometimes a ceased one, and "wired to
        # THE answer" was false. Seed from rank 1 or not at all: a provisional
        # rank-1 is never wired (tier invariant), and a superseded fact's
        # neighbourhood is not the current answer's.
        top = kept[0][0].get("id") if kept else None
        node = self.g.nodes.get(top) if top is not None else None
        if node is None or walk is None or node.get("current") is False:
            return []
        seeds = {top: 1.0}
        return [{"fact": self._fact(d["node"]),
                 "activation": round(d["activation"], 3),
                 "hops": d["hops"],
                 "via": [{"edge": f"{e['a']} <-> {e['b']}",
                          "shared_conversations": e["cooc"]}
                         for e in d["path"]]}
                for d in walk(seeds)]

    def _hearsay_v3(self, idx, query, top_n=3):
        """Assistant claims ABOUT the user, receipted, never asserted.

        e277: this was hardcoded `[]`. The tier built in e246/e249 simply
        never surfaced on the product path, and `RG_HEARSAY=1` paid the cost
        of building the sub-index that nothing then read -- the flag was inert
        where it mattered and worked on the benchmark. FIFTH instance of the
        pathology ledger 5m names, and the only one I wrote myself.
        """
        sub = getattr(idx, "hearsay", None)
        if sub is None:
            return []
        try:
            hits = _RV3.retrieve_facts_v3(sub, query, k=60, dense_k=10,
                                          top_n=top_n)
        except Exception:
            return []
        # e277: HEARSAY NEEDS THE SAME GROUNDING GATE AS EVERYTHING ELSE.
        # `retrieve_facts_v3` returns its top_n by RANK unconditionally, so
        # without this the cello turns up under "When is my birthday?" -- and
        # e250 already caught exactly this, appending hearsay to 94.5% of
        # questions. Re-introduced here the moment the tier was wired in, and
        # caught only because that entry left tests behind.
        store = getattr(self.g, "hearsay", {}) or {}
        out = []
        for h in hits:
            nd = store.get(h.get("id"))
            if nd is None:
                continue
            own = getattr(sub, "owner", None)
            if not (_grounded(query, [h], owner=own)
                    or _dense_grounded(sub, _strip_owner(query, own))):
                continue
            out.append(self._fact(nd))
        return out

    def _abstain(self, query, idx=None, gate=None):
        """e277: HEARSAY-ONLY IS NOT ABSTENTION.

        e280: `gate` names the predicate that refused (see GATES). The
        abstention it returns carries NO payload -- no ranked, asserted or
        unconfirmed facts -- and the harness checks that invariant, because
        a flag that says "abstained" over a list of facts is the one thing a
        caller cannot be trusted to ignore.

        e249 established this on the other read path: if the assistant said
        something about the user and the user never confirmed it, the memory
        HAS seen the topic -- it just holds no assertion. Saying "never seen"
        there is false, and it throws away a receipt the caller may want.
        recall_v3 abstained before ever consulting the hearsay tier."""
        hs = self._hearsay_v3(idx, query) if idx is not None else []
        if hs:
            # `found` means the memory has SEEN the topic -- same contract as
            # `recall()`, whose hearsay-only return is found=True. e277 wrote
            # False here, which made the two retrievers disagree on the one
            # field a caller branches on (review 2026-09-05).
            return {"found": True, "abstain": False, "query": query,
                    "asserted": [], "ranked": [], "wired": [],
                    "unconfirmed": [], "hearsay": hs, "retrieval": "v3",
                    "note": ("hearsay only: an assistant claim about the "
                             "user, never asserted by the user")}
        if gate is not None:
            GATE_COUNTS[gate] = GATE_COUNTS.get(gate, 0) + 1
        return {"found": False, "abstain": True, "query": query,
                "gate": gate,
                "answer": "no stored fact matches -- never seen"}

    def _index_v3(self):
        """Cache one IndexV3 per memory state. Invalidated by node count --
        every write path rebuilds the Memory object, so identity is enough."""
        hear = getattr(self.g, "hearsay", {}) or {}
        key = (len(self.g.nodes), len(self.g.provisional), len(hear))
        if getattr(self, "_v3_key", None) != key:
            idx = _RV3.IndexV3(self)
            # Review 2026-09-05: IndexV3 builds its hearsay sub-index only
            # under RG_HEARSAY=1 so the BENCHMARK index stays byte-identical
            # to the banked one. Nothing on the product path sets that flag,
            # so e277's "hearsay is now wired" was true of a sub-index that
            # was never built here -- `_hearsay_v3` always saw None. The
            # product path builds it unconditionally; the benchmark path
            # (eval_rgp2 -> IndexV3 directly) is untouched.
            if idx.hearsay is None and hear:
                try:
                    idx.hearsay = _RV3.IndexV3(self, facts=list(hear.values()))
                except Exception:
                    idx.hearsay = None
            # e281: the owner's name, for grounding to ignore. Caller-supplied
            # first, then the index's own `name` fact, then read off the texts.
            own = (getattr(self, "owner", None) or getattr(idx, "owner", None)
                   or _guess_owner(list(self.g.nodes.values())
                                   + list(self.g.provisional.values())))
            idx.owner = own
            if idx.hearsay is not None:
                idx.hearsay.owner = getattr(idx.hearsay, "owner", None) or own
            self._v3 = idx
            self._v3_key = key
        return self._v3

    def profile(self, top=40):
        """The corroborated profile, most-evidenced first. Receipted."""
        nodes = sorted(self.g.nodes.values(), key=lambda d: -d["n_mentions"])
        return [self._fact(nd) for nd in nodes[:top]]

    def conflicts(self):
        """Open slot conflicts (the acquisition frame's clarification hook,
        entry 137): same-attr facts whose values link into an evolution chain
        with >=2 distinct values and NO owner correction resolving them.
        Returns [{attribute, values:[{value, dates, evidence}], ask}] --
        `ask` is a ready-to-surface clarifying question. Deterministic."""
        import consolidate as C
        import timeline as TL
        import spacing as SP
        import itertools
        out = []
        store = list(self.g.nodes.values()) + list(self.g.provisional.values())

        # Candidates come from TWO sources, because neither alone is adequate
        # (entry 154, and a live bug this surfaced):
        #  - SINGLE-VALUED slots: enumerate every within-slot pair and let NLI
        #    judge. Lexical chaining MISSES real substitutions by construction
        #    -- "employer: apple" and "employer: google" share no tokens, so
        #    slot_chains() returned nothing and the canonical conflict was
        #    invisible. These slots hold few values each, so pairs are cheap.
        #  - everything else: lexical chains as before (recall-oriented), since
        #    narrative slots accumulate rather than substitute.
        chains = []
        by_attr = {}
        # e274: candidate slots were restricted to C.SINGLE_VALUED, a 24-name
        # allowlist that covers 0.2% of the rgx store (e251). The deterministic
        # parser keys on PREDICATES (`live_in`, `favourite_language`), none of
        # which are in it, so "I live in Berlin" then "I live in Munich" raised
        # nothing at all -- two equally-current facts and an agent left to pick.
        # The server README promises the opposite: "surfaces conflicts rather
        # than silently picking".
        #
        # Any attribute holding two or more DISTINCT values is now a candidate;
        # NLI remains the arbiter, which is what keeps the surface honest --
        # "I like Go" and "I like Rust" are both true and NLI says so.
        wide = os.environ.get("RG_CONFLICT_WIDE") != "0"
        for n in store:
            if n["attr"] in C.SINGLE_VALUED or (wide and _single_valued(n["attr"])):
                by_attr.setdefault(n["attr"], []).append(n)
        for attr, nodes in by_attr.items():
            # Only CORROBORATED values can raise a conflict. Without this the
            # surface explodes (measured: 2,836 asks on the owner profile),
            # because extraction over-assigns single-valued slots -- the
            # `location` slot held cafes, an OS name and a username, each of
            # which NLI correctly calls contradictory with the home city. A
            # single unconfirmed mention is not evidence of a change; it is
            # usually an extraction error, and the write-policy/quarantine
            # path is where those belong.
            # The >=2 gate was calibrated against the LLM extractor, whose
            # `location` slot held cafes, an OS name and a username -- 2,836
            # asks on the owner profile. The deterministic parser keys on the
            # predicate the user actually used, so a single mention is far more
            # often a real statement than an extraction error, and a user
            # states a self-fact ONCE (ledger P2). Re-measured rather than
            # assumed: ledger 6c.
            floor = 1 if wide else 2
            # `ceased`, NOT `current is False`: a fact the USER said had ended
            # is resolved and asking about it would be noise. A fact a
            # HEURISTIC demoted is precisely what this surface exists to ask
            # about -- filtering on `current` would let the heuristic silently
            # pick, which is the behaviour the README promises we do not.
            nodes = [n for n in nodes
                     if n.get("n_mentions", 1) >= floor
                     and not n.get("ceased")]
            nodes = sorted(nodes, key=lambda n: -n.get("n_mentions", 1))[:6]
            seen = set()
            for a, b in itertools.combinations(nodes, 2):
                if a["value"] == b["value"]:
                    continue
                if C.contradicts(attr, a["value"], b["value"]) is not True:
                    continue
                key = tuple(sorted((a["value"], b["value"])))
                if key in seen:
                    continue
                seen.add(key)
                chains.append((attr, [a, b]))
        for attr, chain in TL.slot_chains(store):
            if attr not in C.SINGLE_VALUED:
                chains.append((attr, chain))

        for attr, chain in chains:
            vals = [{"value": m["value"],
                     "dates": sorted(set(m["convs"].values())),
                     "evidence": SP.tag(m)} for m in chain]
            out.append({
                "attribute": attr,
                "values": vals,
                "ask": (f"I have {len(vals)} values for your {attr}: "
                        + " / ".join(f"'{v['value']}'" for v in vals[-3:])
                        + ". Which is current (or are both true)?"),
            })
        return out

    def _fact(self, nd, provisional=False):
        recs = sorted(nd["convs"].items(), key=lambda kv: kv[1], reverse=True)
        if nd.get("owner_confirmed"):
            status = "owner-confirmed"
        elif nd["tier"] == "hearsay":
            # entry 246: an assistant claim ABOUT the user, never asserted by
            # the user -- distinct from "unconfirmed-single-mention" (which
            # the user themself said once) so a caller can't mistake one for
            # the other.
            status = "hearsay"
        elif nd["tier"] == "provisional" or provisional:
            status = "unconfirmed-single-mention"
        else:
            status = "corroborated"
        return {"attribute": nd["attr"], "value": nd["value"],
                # entry 244: the deterministic (rgx) extractor's full
                # proposition, when the node carries one; None for LLM-cache
                # facts and any node built without it -- callers fall back
                # to the attribute/value atom exactly as before.
                "text": nd.get("text"),
                "mentions": nd["n_mentions"], "status": status,
                # W1: set at write time by currency.mark_current. Exposed so
                # every consumer sees one verdict instead of re-deriving it.
                "current": nd.get("current", True),
                "superseded_by": nd.get("superseded_by"),
                "supersedes": list(nd.get("supersedes") or []),
                "receipts": [{"date": d, "conversation":
                              self.titles.get(c, c)[:60],
                              "conversation_id": c} for c, d in recs[:3]]}

    # ---------------- injection ----------------

    def context_block(self, query=None, max_facts=15):
        """Verbatim receipted block for prompt injection. If `query` is given,
        the block is the recall neighbourhood; else the top-of-profile. Empty
        memory -> an explicit do-not-invent block, never silence.

        e261: THE NO-QUERY PATH USED TO RENDER CORROBORATED FACTS ONLY. On a
        real store that is almost nothing -- people state a self-fact ONCE, so
        12 of 14 nodes in the e258 dogfood store were single-mention and an
        agent was handed two lines out of fourteen facts. Ledger P2 measured
        the same thing on the benchmark (88% provisional) and read it as a
        store-quality problem; it is also, and more urgently, a RENDERING
        problem, because this block is what an agent actually sees.

        Single-mention facts are now rendered under an explicit UNCONFIRMED
        label, after every corroborated line, within the same budget. That is
        the honest shape: the block never claims corroboration it does not
        have, and the RULES text already told the reader what an UNCONFIRMED
        line means -- it referenced a category this path never emitted.
        """
        lines = []
        if query is None:
            for f in self.profile(top=max_facts):
                prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                lines.append(f"- {prop}  (x{f['mentions']} mentions)")
            n_corr = len(lines)
            for f in self.provisional_profile(top=max_facts - len(lines)):
                prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                lines.append(f"- UNCONFIRMED (seen once): {prop}")
            head = ("[MEMORY: profile of the user]" if len(lines) > n_corr
                    else "[MEMORY: corroborated profile of the user]")
            if not lines:
                return ("[MEMORY] Nothing is stored about the user yet. Treat "
                        "every detail about them as UNKNOWN: say so rather "
                        "than guessing.\n" + _RULES)
        else:
            r = self._recall_for_context(query)
            head = f"[MEMORY: stored facts relevant to the current message]"
            if not r["found"]:
                return ("[MEMORY] Nothing stored matches this topic. The user's "
                        "details on this are UNKNOWN: say so rather than "
                        "guessing.\n" + _RULES)
            if r.get("ranked"):
                # v3 path: rank order is the evidence order, so it is kept.
                # The tier still shows on every line.
                for f in r["ranked"][:max_facts]:
                    prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                    if f.get("status") == "unconfirmed-single-mention":
                        lines.append(f"- UNCONFIRMED (seen once): {prop}")
                    else:
                        lines.append(f"- {prop}  (x{f['mentions']} mentions)")
            else:
                for f in r["asserted"][:max_facts]:
                    prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                    lines.append(f"- {prop}  (x{f['mentions']} mentions)")
                for w in r["wired"][:max_facts - len(lines)]:
                    f = w["fact"]
                    prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                    lines.append(f"- (linked) {prop}  "
                                 f"(x{f['mentions']}, co-occurs with the above)")
                for f in r["unconfirmed"][:max(0, max_facts - len(lines))]:
                    prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                    lines.append(f"- UNCONFIRMED (seen once): {prop}")
        block = head + "\n" + "\n".join(lines)
        cf = [c for c in self.conflicts()
              if query is None or any(t in c["attribute"]
                                      for t in str(query).lower().split())]
        if cf:
            block += ("\n[MEMORY CONFLICTS -- unresolved; if one becomes "
                      "relevant, ASK the user instead of picking:]")
            for c in cf[:3]:
                block += f"\n- {c['ask']}"
        return block + "\n" + _RULES

    def _recall_for_context(self, query):
        """Same retriever the product's recall uses, so the injected block and
        an explicit profile_recall never disagree about what is stored."""
        # e277: v3 is the DEFAULT here too, so the injected context block and
        # an explicit profile_recall cannot disagree about which retriever ran.
        if os.environ.get("RG_PROFILE_V3") == "0":
            return self.recall(query)
        try:
            return self.recall_v3(query)
        except Exception:
            return self.recall(query)

    def provisional_profile(self, top=40):
        """Single-mention facts, most-evidenced first. Receipted, and NEVER
        merged into `profile()` -- a caller that asks for the corroborated
        profile must keep getting exactly that."""
        if top <= 0:
            return []
        nodes = sorted(self.g.provisional.values(),
                       key=lambda d: -d["n_mentions"])
        return [self._fact(nd, provisional=True) for nd in nodes[:top]]
