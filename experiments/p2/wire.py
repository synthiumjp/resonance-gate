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

THE HYBRID (single-mention facts). Corroboration gates ASSERTION, but a single
mention is not deleted -- it is PROVISIONAL: stored with its receipt, never
volunteered, never wired (an edge needs >= 2 shared conversations, which a
1-conversation fact cannot have), never merged into the profile. On a DIRECT
query match it is returned as a labeled, receipted quote ("seen once,
unconfirmed"), never as an assertion. So ABSTAIN now means "never seen", the
honest meaning; and one user confirmation is a second piece of evidence that
promotes a provisional fact to asserted through the normal GROW path.

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

# QUERY-TIME SYNONYM BRIDGE (Fix 1). A static lexical table, not semantic
# search: common question words map to the canonical attribute token a stored
# fact would actually carry ("work" question, "occupation" node). This is
# non-generative by construction -- it only widens the set of tokens a query
# is allowed to match against, from a fixed hand-authored table; it never
# invents, scores, or embeds anything. See match() for how it is used: it may
# only ADD candidate overlap, never dilute the match denominator.
_QUERY_SYNONYMS = {
    "work": "occupation", "job": "occupation", "career": "occupation",
    "employed": "occupation", "profession": "occupation",
    "live": "location", "lives": "location", "home": "location",
    "city": "location", "where": "location", "reside": "location",
    "married": "relationship", "wife": "relationship",
    "husband": "relationship", "partner": "relationship",
    "earn": "income", "salary": "income", "income": "income",
    "paid": "income",
    "use": "tool", "uses": "tool", "software": "tool", "app": "tool",
    "studied": "education", "degree": "education",
    "university": "education", "school": "education",
    "own": "possession", "owns": "possession", "bought": "possession",
    "called": "name", "name": "name",
    "happened": "event", "attended": "event", "went": "event",
    "visited": "event", "did": "event",
    "planning": "plan", "plans": "plan", "will": "plan",
    "title": "occupation", "pet": "pet", "pets": "pet",
    "cuisine": "food", "food": "food", "hobby": "hobby", "hobbies": "hobby",
    "favorite": "preference", "favourite": "preference",
    # narrow-bucket additions (entry: firewalled dev-set retrieval fix) --
    # verified against the v5.1 extractor's own narrative-ontology attribute
    # vocabulary; each maps to a LOW-count, unambiguous bucket (unlike the
    # mega-buckets "preference"/"motivation"/"plan"/"belief"/"value" with
    # hundreds of facts each, where an attribute bridge alone cannot
    # discriminate one fact -- see halumem_run.py's plain-surface value
    # fallback for that case).
    "disease": "health_condition", "diagnosed": "health_condition",
    "condition": "health_condition", "illness": "health_condition",
    "medical": "health_condition", "chronic": "health_condition",
    "birth": "birth_date", "birthday": "birth_date", "born": "birth_date",
    "mental": "mental_health",
    "gender": "gender",
    "goal": "goal", "aim": "goal", "objective": "goal",
    "field": "discipline", "discipline": "discipline",
}

# question-framing words that never name a value; used by the synonym-only
# match guard to decide whether a query token is genuinely UNEXPLAINED
_QWORDS = {"what", "who", "when", "whats", "which", "how", "does", "do",
           "type", "kind",
           "did", "he", "she", "they", "his", "her", "their", "them", "it",
           "its", "about", "tell", "know", "user", "you", "your"}

# date-framing prepositions ("as of <date>", "on <date>", "by <date>") --
# carry no content of their own; forgiven the same way _QWORDS is in the
# synonym-only match guard (Fix 1) so a question naming a date doesn't get
# treated as having UNEXPLAINED content merely for including "as"/"on"/"by".
_DATE_PREP = {"as", "on", "by"}

# DATE SCOPING (Fix 2). Pure regex, no lookup beyond a fixed month table --
# non-generative extraction of the dates a piece of text NAMES, used to keep
# an answer scoped to the date actually asked about.
_MONTHS = {
    "jan": "jan", "january": "jan",
    "feb": "feb", "february": "feb",
    "mar": "mar", "march": "mar",
    "apr": "apr", "april": "apr",
    "may": "may",
    "jun": "jun", "june": "jun",
    "jul": "jul", "july": "jul",
    "aug": "aug", "august": "aug",
    "sep": "sep", "sept": "sep", "september": "sep",
    "oct": "oct", "october": "oct",
    "nov": "nov", "november": "nov",
    "dec": "dec", "december": "dec",
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))
_YEAR_RX = re.compile(r"\b(19\d{2}|20\d{2})\b")
_MONTH_RX = re.compile(r"\b(" + _MONTH_ALT + r")\b", re.I)
_MONTH_DAY_RX = re.compile(r"\b(" + _MONTH_ALT + r")\.?\s+(\d{1,2})\b", re.I)


def extract_dates(text):
    """Static regex extraction of the date tokens a piece of text NAMES --
    NOT date arithmetic, NOT a calendar, nothing inferred. Returns a set of:
      - 4-digit years in 1900-2099, as strings ("2026")
      - month names, full or 3-letter, normalized to the 3-letter form
        ("november" and "nov" both -> "nov")
      - month-day pairs ("jan 06", "january 6") normalized to "mon-D" with
        the day as an int (no leading zero): "jan-6"
    Used to SCOPE which stored facts an answer draws on to the date actually
    asked about; it never manufactures a date that wasn't in the text."""
    s = str(text).lower()
    out = set()
    out.update(m.group(1) for m in _YEAR_RX.finditer(s))
    out.update(_MONTHS[m.group(1)] for m in _MONTH_RX.finditer(s))
    for m in _MONTH_DAY_RX.finditer(s):
        out.add(f"{_MONTHS[m.group(1)]}-{int(m.group(2))}")
    return out


_DATEISH_WORDS = set(_MONTHS) | set(_MONTHS.values())
_YEAR_DAY_RX = re.compile(r"^(?:(?:19|20)\d{2}|\d{1,2})$")


def _is_dateish(t):
    """A single TOKEN (not a phrase) that names a year, a month, or a bare
    1-2 digit day -- forgiven the same way _QWORDS is in match()'s
    synonym-only guard, since these are handled by the SEPARATE date-scoping
    mechanism (extract_dates + answer_question), not by attribute matching."""
    return t in _DATEISH_WORDS or bool(_YEAR_DAY_RX.match(t))


def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", str(s).lower())
            if t not in _STOP and len(t) > 1}


def strength(w):
    """Monotone squash of a positive weight into (0,1) for activation. Not a
    probability -- an activation gain."""
    return 1.0 - math.exp(-max(w, 0.0))


def correct_facts(facts, prov, corrections):
    """OWNER CORRECTIONS at the fact level, applied BEFORE wiring (so edges,
    audit, report and recall all rebuild consistently). The owner is ground
    truth; corrections are data (an owner-edited file), never inference.

    Each correction: {"action": "deny"|"confirm"|"retype",
                      "attribute": <attr>, "value": <substring of the value>,
                      "exact": true?          # value must match exactly
                      "new_attribute": <attr> # retype only}
      deny    -> the fact is wrong: dropped from both tiers.
      confirm -> owner-vouched: a provisional fact is promoted; the
                 confirmation IS the second piece of evidence (mentions += 1).
      retype  -> right fact, wrong attribute (a project extracted as an
                 occupation, hardware as a tool): the attribute is renamed;
                 same-slot facts merge (mentions summed, receipts unioned).
    Returns (facts, provisional, log)."""
    def _match(c, attr, label):
        if str(c.get("attribute", "")).lower().strip() != attr:
            return False
        sub = str(c.get("value", "")).lower().strip()
        return label == sub if c.get("exact") else sub in label

    out = {"asserted": [], "prov": []}
    log = []
    for tier, src in (("asserted", facts), ("prov", prov)):
        for f in src:
            n, attr, label, recs = f[0], f[1], f[2], f[3]
            toks = set(f[4]) if len(f) > 4 and f[4] else _tokens(label)
            dest, drop = tier, False
            for c in corrections:
                if not _match(c, attr, label.lower()):
                    continue
                act = c.get("action")
                if act == "deny":
                    drop = True
                    log.append(("denied", f"{attr}={label}"))
                    break
                if act == "retype":
                    new = str(c.get("new_attribute", "")).lower().strip()
                    if new and new != attr:
                        log.append(("retyped", f"{attr}={label} -> {new}"))
                        attr = new
                elif act == "confirm" and tier == "prov":
                    n += 1                      # the confirmation is evidence
                    dest = "asserted"
                    log.append(("confirmed", f"{attr}={label}"))
            if not drop:
                out[dest].append((n, attr, label, recs, toks))
    # merge facts that now share (attr, label) -- e.g. after a retype
    merged = {}
    for n, attr, label, recs, toks in out["asserted"]:
        k = (attr, label)
        if k in merged:
            m = merged[k]
            merged[k] = (m[0] + n, attr, label, m[3] + recs, m[4] | toks)
        else:
            merged[k] = (n, attr, label, recs, toks)
    facts_out = sorted(merged.values(), key=lambda f: -f[0])
    return facts_out, out["prov"], log


class WireGraph:
    """Receipted co-occurrence graph over corroborated facts.

    nodes: id -> {id, attr, value, n_mentions, convs: {conv_id: date}}
    edges: (a, b) sorted tuple -> {a, b, cooc, weight, convs: [conv_id...]}
    """

    def __init__(self, min_cooc=MIN_COOC):
        self.min_cooc = min_cooc
        self.n_convs = 1
        self.nodes = {}        # ASSERTED tier: corroborated, wired, volunteered
        self.provisional = {}  # PROVISIONAL tier: single-mention, direct-match only
        self.edges = {}
        self.adj = defaultdict(dict)   # id -> {neighbour_id: edge}

    @staticmethod
    def _mk_node(n, attr, label, recs, tier, toks=None):
        """toks: the value-cluster's token UNION (all merged variants -- each a
        receipted real mention), so a query can match any variant, not just the
        winning label. Still non-generative: tokens come from stored mentions."""
        convs = {}
        for date, cid in recs:
            convs.setdefault(cid, date)
        return {"id": f"{attr}={label}", "attr": attr, "value": label,
                "n_mentions": int(n), "convs": convs, "tier": tier,
                "toks": set(toks) if toks else _tokens(label)}

    # ---------------- construction ----------------

    @classmethod
    def from_facts(cls, facts, n_convs, min_cooc=MIN_COOC, provisional=None):
        """facts: [(n_mentions, attr, value_label, receipts)] with receipts a list
        of (date, conv_id) -- exactly the GROW layer's corroborated readout.
        n_convs: total conversations in the stream (the association base rate).
        provisional: same shape, the single-mention tail -- stored for direct
        query match only, never wired, never volunteered."""
        g = cls(min_cooc)
        g.n_convs = max(int(n_convs), 1)
        for f in facts:
            nd = cls._mk_node(*f[:4], "asserted", toks=f[4] if len(f) > 4 else None)
            g.nodes[nd["id"]] = nd
        for f in (provisional or []):
            nd = cls._mk_node(*f[:4], "provisional", toks=f[4] if len(f) > 4 else None)
            if nd["id"] not in g.nodes:
                g.provisional[nd["id"]] = nd
        # W1: decide supersession ONCE, here, at write time -- not on every
        # read. Provisional nodes take part: a superseded job title is usually
        # single-mention, so excluding them would miss most of the changes.
        try:
            import currency as _CU
            _CU.mark_current(list(g.nodes.values()) + list(g.provisional.values()))
        except Exception:
            for nd in list(g.nodes.values()) + list(g.provisional.values()):
                nd.setdefault("current", True)
                nd.setdefault("superseded_by", None)

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

    def _persona_tokens(self):
        """The user's OWN name tokens, derived from the store itself (never
        from a query): the highest-mention subject-less attr=='name' fact's
        value. Subject-less 'name' is, by this schema's own construction
        (ingest_user: key = f"{subj}:{a}" if subj else a), specifically the
        PRIMARY user's name -- someone else's name is always subject-prefixed
        ("mentor:name"). Cached on the graph; empty (no-op) whenever no such
        fact was ever extracted. Used by match() (Fix: persona-token
        subtraction, entry: firewalled dev-set retrieval fix) so a query that
        names its own subject ("What is Michelle Hernandez's job title?")
        doesn't have that name token block a synonym-bridge match on the
        actual attribute asked about, or spuriously win a perfect-overlap
        direct match against the store's own name=<full name> fact."""
        cached = getattr(self, "_persona_toks_cache", None)
        if cached is not None:
            return cached
        cands = [nd for nd in list(self.nodes.values()) + list(self.provisional.values())
                 if nd["attr"] == "name"]
        toks = frozenset(_tokens(max(cands, key=lambda nd: nd["n_mentions"])["value"])
                          if cands else set())
        self._persona_toks_cache = toks
        return toks

    def match(self, query, store=None):
        """Non-generative query resolution: token grounding between the query and
        a node's attr+value tokens, scored over the SMALLER token set so query
        framing words ("what is ... connected to") do not dilute a real match,
        while a query sharing nothing with a node can never match it.

        PERSONA-TOKEN SUBTRACTION (entry: firewalled dev-set retrieval fix):
        the query's own tokens are first reduced by the store's own persona
        name (see _persona_tokens) -- every question about a specific person
        tends to name them, and the raw name tokens were both winning a
        false perfect-overlap match against the store's own name=<full name>
        fact AND (worse) counting as UNEXPLAINED content that blocked the
        synonym bridge from matching the actual attribute asked about. Never
        lets the subtraction empty the query out (falls back to the raw
        tokens) so a query that IS just the name still matches it.

        SYNONYM BRIDGE (Fix 1): a fixed table maps common question words to
        the canonical attribute token a stored fact would carry ("work" ->
        "occupation") -- a static lexical bridge, not semantic search;
        non-generative by construction. GUARD: a synonym-ONLY match (no
        direct token overlap with the node) is accepted ONLY when the query
        carries no UNEXPLAINED content tokens -- "what does he do for work"
        is a pure attribute question (match), while "i work at acme corp"
        names a value (acme corp) the store does not hold, so it must still
        abstain rather than surface an unrelated occupation fact. Date-ish
        tokens (a named year/month/day) and date-framing prepositions
        ("as"/"on"/"by") are forgiven the same way question-framing words
        are -- they are the separate date-scoping mechanism's job
        (answer_question), not an attribute this node could ever hold.

        Returns [(score, node_id)] best-first over `store` (default: the
        asserted tier); [] means no stored fact matches the query."""
        q = _tokens(query)
        if not q:
            return []
        persona = self._persona_tokens()
        qeff = (q - persona) or q
        syn_attrs = {_QUERY_SYNONYMS[t] for t in qeff if t in _QUERY_SYNONYMS}
        hits = []
        for nid, nd in (self.nodes if store is None else store).items():
            nt = _tokens(nd["attr"]) | nd["toks"]
            if not nt:
                continue
            ov = len(qeff & nt) / min(len(qeff), len(nt))
            if ov < MATCH_MIN and syn_attrs & _tokens(nd["attr"]):
                # synonym-only path: every query content token must be
                # accounted for by the node, the trigger words, question
                # framing, or a date the date-scoper's job -- an unexplained
                # token means the query names something this node does not
                # hold.
                unexplained = qeff - nt - set(_QUERY_SYNONYMS) - _QWORDS - _DATE_PREP
                unexplained = {t for t in unexplained if not _is_dateish(t)}
                if not unexplained:
                    ov = MATCH_MIN
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
        this yet', with the seed's own receipts still returned.

        THE HYBRID: single-mention facts matching the query are returned under
        "provisional" -- labeled, receipted quotes, never assertions, never
        spread from. A provisional-only match is NOT abstention (the memory HAS
        seen it, once); abstention means never seen at all."""
        seeds = self.match(query)
        prov = [{"node": self.provisional[nid], "score": sc}
                for sc, nid in self.match(query, store=self.provisional)]
        if not seeds:
            if prov:
                return {"seeds": [], "neighbourhood": [], "provisional": prov,
                        "note": "unconfirmed: seen once, never corroborated"}
            return {"abstain": True, "query": query,
                    "reason": "no stored fact matches the query"}
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
                "neighbourhood": neigh[:top], "provisional": prov}

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
        # tier invariant: the provisional (single-mention) store is never wired
        for a, b in self.edges:
            if a in self.provisional or b in self.provisional:
                v.append((a, b, "provisional node appears in an edge"))
        return {"pass": not v, "violations": v,
                "n_nodes": len(self.nodes), "n_provisional": len(self.provisional),
                "n_edges": len(self.edges), "n_pairs_checked": n_pairs}


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
