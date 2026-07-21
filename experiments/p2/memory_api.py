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

No model call anywhere in this module.
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


class Memory:
    """Read-side memory over the wired, corroborated profile."""

    def __init__(self, graph, titles=None):
        self.g = graph
        self.titles = titles or {}

    @classmethod
    def load(cls, conversations_path, min_mentions=2):
        """Build from conversations.json + the extraction cache next to it
        (cache-only; no LLM calls). Owner corrections (corrections.jsonl in the
        same quarantine dir) are applied last -- the owner is ground truth."""
        from run_wire import build_facts
        facts, prov, n_convs, titles, _ = build_facts(conversations_path,
                                                      min_mentions)
        g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov)
        m = cls(g, titles)
        corr = os.path.join(os.path.dirname(conversations_path),
                            "corrections.jsonl")
        if os.path.exists(corr):
            import json
            m.apply_corrections([json.loads(l) for l in open(corr)
                                 if l.strip()])
        return m

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
                               for p in r.get("provisional", [])]}
        return out

    def profile(self, top=40):
        """The corroborated profile, most-evidenced first. Receipted."""
        nodes = sorted(self.g.nodes.values(), key=lambda d: -d["n_mentions"])
        return [self._fact(nd) for nd in nodes[:top]]

    def _fact(self, nd, provisional=False):
        recs = sorted(nd["convs"].items(), key=lambda kv: kv[1], reverse=True)
        if nd.get("owner_confirmed"):
            status = "owner-confirmed"
        elif nd["tier"] == "provisional" or provisional:
            status = "unconfirmed-single-mention"
        else:
            status = "corroborated"
        return {"attribute": nd["attr"], "value": nd["value"],
                "mentions": nd["n_mentions"], "status": status,
                "receipts": [{"date": d, "conversation":
                              self.titles.get(c, c)[:60]} for c, d in recs[:3]]}

    # ---------------- injection ----------------

    def context_block(self, query=None, max_facts=15):
        """Verbatim receipted block for prompt injection. If `query` is given,
        the block is the recall neighbourhood; else the top-of-profile. Empty
        memory -> an explicit do-not-invent block, never silence."""
        lines = []
        if query is None:
            for f in self.profile(top=max_facts):
                lines.append(f"- {f['attribute']}: {f['value']}  "
                             f"(x{f['mentions']} mentions)")
            head = "[MEMORY: corroborated profile of the user]"
        else:
            r = self.recall(query)
            head = f"[MEMORY: stored facts relevant to the current message]"
            if not r["found"]:
                return ("[MEMORY] Nothing stored matches this topic. The user's "
                        "details on this are UNKNOWN: say so rather than "
                        "guessing.\n" + _RULES)
            for f in r["asserted"][:max_facts]:
                lines.append(f"- {f['attribute']}: {f['value']}  "
                             f"(x{f['mentions']} mentions)")
            for w in r["wired"][:max_facts - len(lines)]:
                f = w["fact"]
                lines.append(f"- (linked) {f['attribute']}: {f['value']}  "
                             f"(x{f['mentions']}, co-occurs with the above)")
            for f in r["unconfirmed"][:3]:
                lines.append(f"- UNCONFIRMED (seen once): {f['attribute']}: "
                             f"{f['value']}")
        return head + "\n" + "\n".join(lines) + "\n" + _RULES
