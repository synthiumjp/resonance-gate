"""p2 WIRE layer: Hebbian co-occurrence edges + spreading-activation retrieval.

GROW (belief.py) made each memory a posterior that concentrates with corroboration.
WIRE makes the memory a GRAPH: facts that fire together wire together. An edge is
NOT an inference -- it is a receipted observation: "these two corroborated facts
were asserted in the same conversation c times", and the edge carries those
conversations as its receipts. Links are never invented.

NON-HALLUCINATION, structurally (the same four properties as the node layer):
  1. NON-GENERATIVE -- retrieval returns stored nodes over stored edges; a query
     that matches no corroborated node returns ABSTAIN, never a guess.
  2. CORROBORATION-GATED -- an edge needs >= MIN_COOC shared conversations (one
     co-occurrence is coincidence, same principle as node assertion) AND a
     positive weight of evidence for association (above-chance co-occurrence).
  3. RECEIPTED -- an edge's receipt set IS the intersection of its endpoints'
     receipt sets, by construction. audit() verifies this exhaustively.
  4. ABSTAINS -- no matching node, or no wired neighbourhood, is said plainly.

EDGE WEIGHT (Good's weight of evidence, the same framing as belief.py). Over N
conversations, facts a and b appear in k_a, k_b of them and share c. The weight is
the log-likelihood ratio of association vs independence at the observed base rates
-- smoothed PMI with a Jeffreys constant:
    w = log( (c+s)(N+s) / ((k_a+s)(k_b+s)) ),  s = 0.5
w <= 0 means co-occurrence at or below chance (two ubiquitous facts overlap a lot
by base rate alone) -> no edge. This is a measured association, not a raw count.

SPREADING ACTIVATION. Seed nodes get activation = match score; each hop multiplies
by edge strength (1 - e^-w, a monotone squash of the weight into (0,1)) and a hop
decay. Every returned neighbour carries its full PATH of receipted edges, so a
2-hop association shows the two real co-occurrences that carried it.

VSA RESONANCE (rg-1.1 substrate) -- proposer, never authority. Each node gets a
Hebbian wiring hypervector: the bundle of its neighbours' item vectors, copies
proportional to edge strength. Cleanup over the codebook PROPOSES associates by
resonance; every proposal is VERIFIED against the receipted edge table and
crosstalk is BLOCKED (and counted -- the measured hallucination pressure the gate
absorbs). Same shape as the extraction layer: a noisy proposer + a model-free gate.
"""

import math
import re
from collections import defaultdict

MIN_COOC = 2        # an edge, like a node, must be corroborated
SMOOTH = 0.5        # Jeffreys smoothing for the association weight
DECAY = 0.5         # per-hop activation decay
A_MIN = 0.05        # activation floor -- below this a node is not returned
MATCH_MIN = 0.5     # a query token-grounding score below this is no match

_STOP = {"the", "a", "an", "my", "of", "and", "in", "at", "to", "for", "with",
         "is", "was", "i", "am", "me", "current", "currently", "new", "some"}


def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", str(s).lower())
            if t not in _STOP and len(t) > 1}


def strength(w):
    """Monotone squash of a positive weight into (0,1) for activation. Not a
    probability -- an activation gain."""
    return 1.0 - math.exp(-max(w, 0.0))


class WireGraph:
    """Receipted co-occurrence graph over corroborated facts.

    nodes: id -> {id, attr, value, n_mentions, convs: {conv_id: date}}
    edges: (a, b) sorted tuple -> {a, b, cooc, weight, convs: [conv_id...]}
    """

    def __init__(self, min_cooc=MIN_COOC):
        self.min_cooc = min_cooc
        self.n_convs = 1
        self.nodes = {}
        self.edges = {}
        self.adj = defaultdict(dict)   # id -> {neighbour_id: edge}

    # ---------------- construction ----------------

    @classmethod
    def from_facts(cls, facts, n_convs, min_cooc=MIN_COOC):
        """facts: [(n_mentions, attr, value_label, receipts)] with receipts a list
        of (date, conv_id) -- exactly the GROW layer's corroborated readout.
        n_convs: total conversations in the stream (the association base rate)."""
        g = cls(min_cooc)
        g.n_convs = max(int(n_convs), 1)
        for n, attr, label, recs in facts:
            nid = f"{attr}={label}"
            convs = {}
            for date, cid in recs:
                convs.setdefault(cid, date)
            g.nodes[nid] = {"id": nid, "attr": attr, "value": label,
                            "n_mentions": int(n), "convs": convs}
        ids = sorted(g.nodes)
        for i, a in enumerate(ids):
            ca = g.nodes[a]["convs"]
            for b in ids[i + 1:]:
                cb = g.nodes[b]["convs"]
                shared = sorted(set(ca) & set(cb))
                if len(shared) < min_cooc:
                    continue
                w = g.assoc_weight(len(ca), len(cb), len(shared))
                if w <= 0:
                    continue
                e = {"a": a, "b": b, "cooc": len(shared), "weight": w,
                     "convs": shared}
                g.edges[(a, b)] = e
                g.adj[a][b] = e
                g.adj[b][a] = e
        return g

    def assoc_weight(self, ka, kb, c):
        N, s = self.n_convs, SMOOTH
        return math.log(((c + s) * (N + s)) / ((ka + s) * (kb + s)))

    # ---------------- retrieval ----------------

    def match(self, query):
        """Non-generative query resolution: token grounding between the query and
        a node's attr+value tokens, scored over the SMALLER token set so query
        framing words ("what is ... connected to") do not dilute a real match,
        while a query sharing nothing with a node can never match it.
        Returns [(score, node_id)] best-first; [] means the memory has no
        corroborated fact matching the query."""
        q = _tokens(query)
        if not q:
            return []
        hits = []
        for nid, nd in self.nodes.items():
            nt = _tokens(nd["attr"] + " " + nd["value"])
            if not nt:
                continue
            ov = len(q & nt) / min(len(q), len(nt))
            if ov >= MATCH_MIN:
                hits.append((ov, nd["n_mentions"], nid))
        hits.sort(reverse=True)
        return [(sc, nid) for sc, _, nid in hits]

    def spread(self, query, max_hops=2, decay=DECAY, a_min=A_MIN, top=20):
        """Spreading-activation retrieval. Returns either
          {"abstain": True, "reason": ...}                       -- no matching node
        or
          {"seeds": [node...], "neighbourhood": [{node, activation, hops,
            path: [edge...]}...]}
        Every neighbourhood item carries the full path of receipted edges that
        activated it. An empty neighbourhood is an honest 'nothing is wired to
        this yet', with the seed's own receipts still returned."""
        seeds = self.match(query)
        if not seeds:
            return {"abstain": True, "query": query,
                    "reason": "no corroborated fact matches the query"}
        act = {nid: sc for sc, nid in seeds}
        path = {nid: [] for _, nid in seeds}
        hops = {nid: 0 for _, nid in seeds}
        frontier = [nid for _, nid in seeds]
        seed_ids = set(frontier)
        for hop in range(1, max_hops + 1):
            nxt = []
            for nid in frontier:
                for nbr, e in self.adj[nid].items():
                    a = act[nid] * strength(e["weight"]) * decay
                    if a >= a_min and a > act.get(nbr, 0.0):
                        act[nbr] = a
                        path[nbr] = path[nid] + [e]
                        hops[nbr] = hop
                        nxt.append(nbr)
            frontier = nxt
        neigh = [{"node": self.nodes[nid], "activation": act[nid],
                  "hops": hops[nid], "path": path[nid]}
                 for nid in act if nid not in seed_ids]
        neigh.sort(key=lambda d: -d["activation"])
        return {"seeds": [self.nodes[nid] for _, nid in seeds],
                "neighbourhood": neigh[:top]}

    # ---------------- the acceptance test ----------------

    def audit(self):
        """Exhaustive non-hallucination audit of the wiring. Checks EVERY edge:
          - its receipt set equals the TRUE intersection of its endpoints'
            conversation sets (no invented, dropped, or annotated-in receipts)
          - cooc >= min_cooc and cooc == len(receipts)
          - the stored weight recomputes from the receipts and is > 0
        and EVERY non-edge pair: it genuinely fails a gate (cooc < min_cooc or
        w <= 0) -- nothing supported was silently dropped, nothing unsupported
        was let in. Returns {"pass": bool, "violations": [...], ...}."""
        v = []
        ids = sorted(self.nodes)
        n_pairs = 0
        for i, a in enumerate(ids):
            ca = set(self.nodes[a]["convs"])
            for b in ids[i + 1:]:
                n_pairs += 1
                cb = set(self.nodes[b]["convs"])
                true_shared = sorted(ca & cb)
                e = self.edges.get((a, b))
                if e is not None:
                    if sorted(e["convs"]) != true_shared:
                        v.append((a, b, "receipts != true co-occurrence"))
                    if e["cooc"] != len(e["convs"]) or e["cooc"] < self.min_cooc:
                        v.append((a, b, "cooc below gate or inconsistent"))
                    w = self.assoc_weight(len(ca), len(cb), len(true_shared))
                    if abs(w - e["weight"]) > 1e-9 or w <= 0:
                        v.append((a, b, "weight does not recompute from receipts"))
                else:
                    if len(true_shared) >= self.min_cooc and \
                       self.assoc_weight(len(ca), len(cb), len(true_shared)) > 0:
                        v.append((a, b, "supported pair missing an edge"))
        return {"pass": not v, "violations": v,
                "n_nodes": len(self.nodes), "n_edges": len(self.edges),
                "n_pairs_checked": n_pairs}


class ResonanceIndex:
    """rg-1.1 VSA substrate as the associative PROPOSER; the receipted edge table
    as the VERIFIER. Each node's wiring hypervector is the MAP bundle of its
    neighbours' item vectors, copies proportional to edge strength (Hebbian: the
    more evidence for the association, the more of the neighbour in the bundle).
    retrieve() partitions cleanup proposals into verified (receipted edge exists)
    and blocked crosstalk (no edge -> NEVER surfaced, only counted)."""

    def __init__(self, graph, dim=8192, seed=0, max_copies=5):
        import numpy as np
        from substrate.map_ops import Codebook, bundle
        self.graph = graph
        self.ids = sorted(graph.nodes)
        self.cb = Codebook(self.ids, dim=dim, seed=seed)
        self.wiring = {}
        for nid in self.ids:
            vecs = []
            for nbr, e in graph.adj[nid].items():
                copies = 1 + int(round((max_copies - 1) * strength(e["weight"])))
                vecs.extend([self.cb[nbr]] * copies)
            if vecs:
                self.wiring[nid] = bundle(vecs, seed=seed)
        self._np = np

    def propose(self, nid, top_k=8, cos_min=0.02):
        """Raw resonance candidates -- UNVERIFIED, internal use."""
        if nid not in self.wiring:
            return []
        cos = self.cb.cosines(self.wiring[nid])
        order = self._np.argsort(-cos)[:top_k + 1]
        return [(self.ids[i], float(cos[i])) for i in order
                if self.ids[i] != nid and cos[i] >= cos_min][:top_k]

    def retrieve(self, nid, top_k=8):
        """Resonance proposals gated by the receipted edge table. Only verified
        associations are surfaced; crosstalk is blocked and counted."""
        verified, blocked = [], []
        for cand, cos in self.propose(nid, top_k=top_k):
            e = self.graph.adj[nid].get(cand)
            if e is not None:
                verified.append({"node": self.graph.nodes[cand], "cos": cos,
                                 "edge": e})
            else:
                blocked.append((cand, cos))
        return {"verified": verified, "blocked_crosstalk": blocked}

    def crosstalk_audit(self, top_k=8):
        """Over every node: how many raw resonance proposals lacked a receipted
        edge (the hallucination pressure), and confirmation that the gate blocked
        all of them from the verified set."""
        proposed = blocked = leaked = 0
        for nid in self.ids:
            r = self.retrieve(nid, top_k=top_k)
            proposed += len(r["verified"]) + len(r["blocked_crosstalk"])
            blocked += len(r["blocked_crosstalk"])
            for item in r["verified"]:
                pair = tuple(sorted((nid, item["node"]["id"])))
                if pair not in self.graph.edges:
                    leaked += 1
        return {"proposed": proposed, "blocked": blocked, "leaked": leaked,
                "pass": leaked == 0}
