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
from collections import Counter

from wire import _tokens, _QUERY_SYNONYMS

K1, B = 1.5, 0.75


def _fact_tokens(d):
    return _tokens(d["attr"]) | _tokens(d["value"])


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
    q = _tokens(question)
    return q | {_QUERY_SYNONYMS[t] for t in q if t in _QUERY_SYNONYMS}


def format_fact(d):
    dates = sorted(d["convs"].values())
    dt = dates[-1] if dates else "?"
    tag = (f"confirmed x{d['n_mentions']}" if d["n_mentions"] >= 2
           else "unconfirmed(once)")
    return f"[{tag}, {dt}] {d['attr'].replace(':', ' of ')}: {d['value']}"


def retrieve(mem, question, k=30, index=None):
    """Top-k receipted facts as a context block for the composer."""
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
    lines = [format_fact(facts[j]) for _, _, j in scored[:k]]
    return "\n".join(lines) or "(no relevant memories)"
