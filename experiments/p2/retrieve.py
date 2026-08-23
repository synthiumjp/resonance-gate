"""RG evidence-layer retrieval: BM25-ranked, corroboration-tiered, receipted
context for a client LLM composer.

Pure python -- no embeddings, no model, no GPU. BM25 (IDF + length norm) is
used rather than raw token overlap because the 2026 hybrid-retrieval
literature finds lexical BM25 competitive with (and on exact-match/rare-term
workloads, better than) dense embeddings -- and our facts ARE short
entity/attribute/value strings, BM25's home ground. Measured on HaluMem dev
users 10-12: recall@30 58.7% (raw overlap) -> 61.7% (BM25).

Each line carries RG's differentiators, which the composer is instructed to
use: corroboration tier ("confirmed xN" vs "unconfirmed(once)") and the
receipt date -- so the composer can prefer corroborated, recent evidence and
abstain honestly when the answer is absent.
"""
import math
import os
from collections import Counter

from wire import _tokens, _QUERY_SYNONYMS

K1, B = 1.5, 0.75
DEFAULT_K = 120          # measured knee: recall 87.6% @ ~3.1k tokens of context

# Light suffix stripping so query and fact forms unify ("prefer" in a question
# must match "preference" in a stored fact -- the measured cause of real
# retrieval misses). Crude by design: no dictionary, no model, deterministic.
# Measured on HaluMem dev users 10-12: recall@30 60.1% -> 66.1% with stemming;
# with k=120 as well, 87.6%.
_SUFFIXES = ("ences", "ence", "ances", "ance", "ings", "ing", "ions", "ion",
             "ies", "ied", "ers", "er", "ed", "es", "s", "ly", "al")


def _stem(w):
    for suf in _SUFFIXES:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[:-len(suf)]
    return w


def _stems(s):
    return {_stem(t) for t in _tokens(s)}


def _fact_tokens(d):
    return _stems(d["attr"]) | _stems(d["value"])


def build_index(mem):
    """(facts, docs, idf, avgdl) over both tiers of a Memory's graph."""
    facts = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    docs = [_fact_tokens(d) for d in facts]
    n = len(facts)
    df = Counter()
    for t in docs:
        for x in t:
            df[x] += 1
    idf = {x: math.log(1 + (n - c + 0.5) / (c + 0.5)) for x, c in df.items()}
    avgdl = sum(len(t) for t in docs) / max(n, 1)
    return facts, docs, idf, avgdl


def query_tokens(question):
    raw = _tokens(question)
    return _stems(question) | {_stem(_QUERY_SYNONYMS[t]) for t in raw
                                if t in _QUERY_SYNONYMS}


def format_fact(d, owner=None):
    """One retrieved fact as a context line.

    RG_QA_PROPS=1 renders the fact as a natural-language proposition instead of
    an `attr: value` atom (entry 178, defect 5). Gold memory points, MOSAIC's
    nodes, mem0's statements and Zep's facts are all propositions; rendering our
    EXTRACTION artifact that way was worth +25% integrity and +21% F1 (entries
    173/174), but the QA path was deliberately left on atoms so round 5 stayed
    reproducible. Off by default for exactly that reason.

    The tier/date prefix is kept in both modes: CAL rule 1 refers to it, so
    dropping it would change two things at once."""
    dates = sorted(d["convs"].values())
    dt = dates[-1] if dates else "?"
    tag = (f"confirmed x{d['n_mentions']}" if d["n_mentions"] >= 2
           else "unconfirmed(once)")
    # entry 244 follow-up: this renderer never got the entry-244 fix --
    # every other renderer (memory_api.context_block, eval_rgp2._fact_str,
    # eval_rgp2.search_memories._v) prefers the deterministic (rgx)
    # extractor's full proposition ("text") over the attr/value atom, but
    # this one -- used for the judged QA CONTEXT itself -- stayed on the
    # old atom unconditionally, so the judged context leaked predicate-key
    # attrs ("change_highlight: ...", "openness_to_exploring_..."). Use
    # text whenever the node has one, regardless of RG_QA_PROPS.
    if d.get("text"):
        return f"[{tag}, {dt}] {d['text']}"
    if os.environ.get("RG_QA_PROPS") == "1":
        import propositions as _PR
        prop = _PR.render(d, owner=owner)
        if prop:                      # empty only for malformed facts
            return f"[{tag}, {dt}] {prop}"
    return f"[{tag}, {dt}] {d['attr'].replace(':', ' of ')}: {d['value']}"


def retrieve_facts(mem, question, k=DEFAULT_K, index=None):
    """Top-k ranked fact nodes (behavior identical to retrieve(); split out so
    the harness adapter can reach the nodes themselves, e.g. for
    timeline.change_history)."""
    facts, docs, idf, avgdl = index or build_index(mem)
    qt = query_tokens(question)
    scored = []
    for j, t in enumerate(docs):
        inter = qt & t
        if not inter:
            continue
        dl = len(t)
        s = sum(idf.get(x, 0.0) * ((K1 + 1) / (1 + K1 * (1 - B + B * dl / avgdl)))
                for x in inter)
        scored.append((s, facts[j]["n_mentions"], j))
    scored.sort(key=lambda z: (-z[0], -z[1]))
    return [facts[j] for _, _, j in scored[:k]]


def retrieve(mem, question, k=DEFAULT_K, index=None):
    """Top-k receipted facts as a context block for the composer."""
    lines = [format_fact(d) for d in retrieve_facts(mem, question, k, index)]
    return "\n".join(lines) or "(no relevant memories)"
