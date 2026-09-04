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

_RULES = ("[MEMORY RULES] The facts above are corroborated from the user's own "
          "history; each shows its mention count. Lines marked UNCONFIRMED were "
          "seen once and are not established -- if one matters, ask the user to "
          "confirm it. Anything about the user NOT listed here is UNKNOWN to "
          "you: say you don't know rather than guessing.")


def _rv3():
    import retrieve_v3
    return retrieve_v3


class _LazyRV3:
    def __getattr__(self, k):
        return getattr(_rv3(), k)


_RV3 = _LazyRV3()

# Cross-encoder score below which recall_v3 abstains. PILOT VALUE (e258):
# fitted on the same 18 dogfood questions it was scored on, so it is an
# operating point to re-derive on held-out data, not a constant to trust.
FLOOR_V3 = -7.7


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
        out = {"found": True, "abstain": False, "query": query,
               "asserted": [self._fact(nd) for nd in r["seeds"]],
               "wired": [{"fact": self._fact(d["node"]),
                          "activation": round(d["activation"], 3),
                          "hops": d["hops"],
                          "via": [{"edge": f"{e['a']} <-> {e['b']}",
                                   "shared_conversations": e["cooc"]}
                                  for e in d["path"]]}
                         for d in r["neighbourhood"]],
               "unconfirmed": [self._fact(p["node"], provisional=True)
                               for p in r.get("provisional", [])],
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
        scored = _RV3.retrieve_facts_v3(idx, query, k=120, dense_k=20,
                                        top_n=top_n, with_scores=True)
        kept = [(h, sc) for h, sc in scored if sc >= floor]
        if not kept:
            return self._abstain(query)
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
        memory -> an explicit do-not-invent block, never silence."""
        lines = []
        if query is None:
            for f in self.profile(top=max_facts):
                prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                lines.append(f"- {prop}  (x{f['mentions']} mentions)")
            head = "[MEMORY: corroborated profile of the user]"
        else:
            r = self.recall(query)
            head = f"[MEMORY: stored facts relevant to the current message]"
            if not r["found"]:
                return ("[MEMORY] Nothing stored matches this topic. The user's "
                        "details on this are UNKNOWN: say so rather than "
                        "guessing.\n" + _RULES)
            for f in r["asserted"][:max_facts]:
                prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                lines.append(f"- {prop}  (x{f['mentions']} mentions)")
            for w in r["wired"][:max_facts - len(lines)]:
                f = w["fact"]
                prop = f.get("text") or f"{f['attribute']}: {f['value']}"
                lines.append(f"- (linked) {prop}  "
                             f"(x{f['mentions']}, co-occurs with the above)")
            for f in r["unconfirmed"][:3]:
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
