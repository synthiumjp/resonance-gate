"""Retrieval v3 -- the opt-in accuracy tier (entry 132/134, dev 56.7/22.5).

BM25(+focus-weighted query) top-120 ∪ bge-small dense top-20, cross-encoder
reranked, top-120. Costs two small CPU models (~150MB, ~0.5s/query); the
pure-python retrieve.py stays the default tier.

Focus weighting (entry 133): persona-name and date tokens in the QUERY are
scaffolding, weighted 0.25 (entry 96's lesson applied to the BM25 path).
"""
import math
import re

from wire import _tokens, _QUERY_SYNONYMS
import retrieve as RV

_MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
           "oct", "nov", "dec", "january", "february", "march", "april",
           "june", "july", "august", "september", "october", "november",
           "december"}
_YEAR_RX = re.compile(r"^(19|20)\d\d$")

_bi = _ce = None


def _models():
    global _bi, _ce
    if _bi is None:
        from sentence_transformers import CrossEncoder, SentenceTransformer
        _bi = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
        _ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", device="cpu")
    return _bi, _ce


class IndexV3:
    """Per-memory-state index: BM25 tables + dense embeddings + persona set."""

    def __init__(self, mem):
        bi, _ = _models()
        self.facts = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        self.docs = [RV._stems(d["attr"]) | RV._stems(d["value"]) for d in self.facts]
        n = len(self.facts)
        from collections import Counter
        df = Counter()
        for t in self.docs:
            for x in t:
                df[x] += 1
        self.idf = {x: math.log(1 + (n - c + 0.5) / (c + 0.5)) for x, c in df.items()}
        self.avgdl = sum(len(t) for t in self.docs) / max(n, 1)
        self.texts = [f"{d['attr']}: {d['value']}" for d in self.facts]
        self.emb = bi.encode(self.texts, batch_size=256, show_progress_bar=False,
                             normalize_embeddings=True)
        self.persona = set()
        for d in self.facts:
            if d["attr"] == "name":
                self.persona |= _tokens(d["value"])


def retrieve_facts_v3(index, question, k=120, dense_k=20):
    import numpy as np
    bi, ce = _models()
    raw = _tokens(question)
    allt = raw | {w for t in raw if t in _QUERY_SYNONYMS
                  for w in _tokens(_QUERY_SYNONYMS[t])}
    qw = {}
    for t in allt:
        w = 0.25 if (t in index.persona or t in _MONTHS or _YEAR_RX.match(t)) else 1.0
        s = RV._stem(t)
        qw[s] = max(qw.get(s, 0.0), w)
    scored = []
    for j, t in enumerate(index.docs):
        inter = set(qw) & t
        if not inter:
            continue
        dl = len(t)
        sc = sum(qw[x] * index.idf.get(x, 0.0) * ((RV.K1 + 1) /
                 (1 + RV.K1 * (1 - RV.B + RV.B * dl / index.avgdl)))
                 for x in inter)
        scored.append((sc, j))
    scored.sort(key=lambda z: -z[0])
    qv = bi.encode([question], normalize_embeddings=True)[0]
    dense_top = list(np.argsort(-(index.emb @ qv))[:dense_k])
    cand = list(dict.fromkeys([j for _, j in scored[:k]] + dense_top))
    if not cand:
        return []
    ces = ce.predict([(question, index.texts[j]) for j in cand],
                     show_progress_bar=False)
    return [index.facts[cand[i]] for i in np.argsort(-ces)[:k]]


# As-of rule (entry 134): appended for date-anchored questions only.
ANCHORED_RX = re.compile(
    r"\b(as of|by (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})|"
    r"on (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* \d|"
    r"in (19|20)\d\d|between .{2,20} and )", re.I)

TEMPORAL_RULE = ("\n4. THIS QUESTION IS ANCHORED TO A DATE OR PERIOD. Use the memory whose "
 "date matches, or most closely PRECEDES, the asked date -- a memory dated AFTER the "
 "asked date describes a LATER state of affairs and must NOT be used to answer about "
 "the earlier time. For 'between X and Y' or 'how did it change' questions, use the "
 "dated memories inside that window.")
