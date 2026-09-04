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
FLOOR_V3 = -7.83


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

    def __init__(self, graph, titles=None):
        self.g = graph
        self.titles = titles or {}

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
            return self._abstain(query)
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
        if not scored or max(sc for _, sc in scored) < floor:
            return self._abstain(query)
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
            return self._abstain(query)
        return {"found": True, "abstain": False, "query": query,
                "asserted": [f for f in facts if f not in unconfirmed],
                "ranked": facts, "wired": [],
                "unconfirmed": unconfirmed, "hearsay": [],
                "retrieval": "v3", "floor": floor}

    def _abstain(self, query):
        return {"found": False, "abstain": True, "query": query,
                "answer": "no stored fact matches -- never seen"}

    def _index_v3(self):
        """Cache one IndexV3 per memory state. Invalidated by node count --
        every write path rebuilds the Memory object, so identity is enough."""
        key = (len(self.g.nodes), len(self.g.provisional))
        if getattr(self, "_v3_key", None) != key:
            self._v3 = _RV3.IndexV3(self)
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
        for n in store:
            if n["attr"] in C.SINGLE_VALUED:
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
            nodes = [n for n in nodes if n.get("n_mentions", 1) >= 2]
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
        if os.environ.get("RG_PROFILE_V3") == "1":
            return self.recall_v3(query)
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
