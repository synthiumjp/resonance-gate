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
        (cache-only; no LLM calls)."""
        from run_wire import build_facts
        facts, prov, n_convs, titles, _ = build_facts(conversations_path,
                                                      min_mentions)
        g = WireGraph.from_facts(facts, n_convs=n_convs, provisional=prov)
        return cls(g, titles)

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
        return {"attribute": nd["attr"], "value": nd["value"],
                "mentions": nd["n_mentions"],
                "status": "unconfirmed-single-mention" if provisional else "corroborated",
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
