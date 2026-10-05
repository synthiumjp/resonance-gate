"""Retrieval v3 -- the opt-in accuracy tier (entry 132/134, dev 56.7/22.5).

BM25(+focus-weighted query) top-120 ∪ bge-small dense top-20, cross-encoder
reranked, top-120. Costs two small CPU models (~150MB, ~0.5s/query); the
pure-python retrieve.py stays the default tier.

Focus weighting (entry 133): persona-name and date tokens in the QUERY are
scaffolding, weighted 0.25 (entry 96's lesson applied to the BM25 path).
"""
import math
import os
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
        # 2026-10-02: ONNX Runtime with fp16-stored weights when setup has
        # installed them (ort_models.py; identical rankings), else PyTorch
        import ort_models as _O
        if _O.use_onnx(_O.EMBEDDER) and _O.use_onnx(_O.RERANKER):
            _bi, _ce = _O.Encoder(_O.EMBEDDER), _O.CrossEncoder(_O.RERANKER)
        else:
            from sentence_transformers import CrossEncoder, SentenceTransformer
            _bi = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
            _ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2", device="cpu")
    return _bi, _ce


# 2026-10-04: embeddings are kept on disk, keyed by the text, so an index
# rebuilt after every stored conversation embeds only what is new. Without it
# 20,000 messages took 46 s to index on the Mac, on the first question after
# each session. RG_MEMORY_DIR/embeddings.bin: fixed-size records (20-byte
# key, then the float32 vector), appended; a torn last record is ignored.
# Forgetting deletes the file (profile_memory.profile_forget).
_EMB_MODEL = "bge-small-en-v1.5"
_EMB_DIM = 384
_EMB_CACHE = {}


def emb_cache_path():
    d = os.environ.get("RG_MEMORY_DIR")
    if not d or os.environ.get("RG_EMB_CACHE") == "0":
        return None
    return os.path.join(d, "embeddings.bin")


def _emb_key(text):
    import hashlib
    return hashlib.sha1(f"{_EMB_MODEL}\x00{text}".encode("utf-8")).digest()


def _load_emb(path):
    import numpy as np
    rec = 20 + 4 * _EMB_DIM
    out = {}
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return out
    for i in range(len(data) // rec):
        r = data[i * rec:(i + 1) * rec]
        out[r[:20]] = np.frombuffer(r[20:], dtype=np.float32)
    return out


def _encode_cached(bi, texts):
    import numpy as np
    path = emb_cache_path()
    if path is None:
        return bi.encode(texts, batch_size=256, show_progress_bar=False,
                         normalize_embeddings=True)
    cache = _EMB_CACHE.get(path)
    if cache is None or not os.path.exists(path):
        cache = _EMB_CACHE[path] = _load_emb(path)
    keys = [_emb_key(t) for t in texts]
    miss = list(dict.fromkeys(k for k in keys if k not in cache))
    if miss:
        first = {}
        for k, t in zip(keys, texts):
            first.setdefault(k, t)
        vecs = np.asarray(bi.encode([first[k] for k in miss], batch_size=256,
                                    show_progress_bar=False,
                                    normalize_embeddings=True), dtype=np.float32)
        try:
            with open(path, "ab") as fh:
                for k, v in zip(miss, vecs):
                    fh.write(k + v.tobytes())
        except OSError:
            pass
        for k, v in zip(miss, vecs):
            cache[k] = v
    if not keys:
        return np.zeros((0, _EMB_DIM), dtype=np.float32)
    return np.stack([cache[k] for k in keys])


class IndexV3:
    """Per-memory-state index: BM25 tables + dense embeddings + persona set."""

    def __init__(self, mem, facts=None):
        bi, _ = _models()
        self.facts = (list(facts) if facts is not None
                      else list(mem.g.nodes.values())
                      + list(mem.g.provisional.values()))
        # 2026-10-02 (tools/scale_test.py): the record's own words are
        # indexed too. A world fact's key is the subject's head lemma
        # ("service_write_in"), so "billing" was never indexed and "What
        # language is the billing service in?" lost the fact to filler once
        # the store had a few hundred "service" facts.
        self.docs = [RV._stems(d["attr"]) | RV._stems(d["value"])
                     | RV._stems(d.get("text") or "") for d in self.facts]
        n = len(self.facts)
        from collections import Counter
        df = Counter()
        for t in self.docs:
            for x in t:
                df[x] += 1
        self.idf = {x: math.log(1 + (n - c + 0.5) / (c + 0.5)) for x, c in df.items()}
        self.avgdl = sum(len(t) for t in self.docs) / max(n, 1)
        self.texts = [f"{d['attr']}: {d['value']}" for d in self.facts]
        self.emb = _encode_cached(bi, self.texts)
        # Owner name for proposition rendering (entry 178 defect 5): unprefixed
        # facts belong to the profile owner, so the renderer needs it to say
        # "Martin Mark's ..." rather than "The user's ...".
        try:
            import propositions as _PR
            self.owner = _PR.owner_name(self.facts)
        except Exception:
            self.owner = None
        self.persona = set()
        for d in self.facts:
            if d["attr"] == "name":
                self.persona |= _tokens(d["value"])
        # entry 249: the hearsay tier (entry 246 -- slots whose only mentions
        # are assistant claims about the user) gets its OWN index, never this
        # one. Mixing hearsay into `self.facts` would let an assistant claim
        # displace a corroborated fact from the cross-encoder's top_n, and the
        # measurement would then be of retrieval displacement rather than of
        # the hearsay label. Built only under RG_HEARSAY, so with the flag
        # unset this attribute is None and the index is byte-identical to the
        # one that produced every banked number.
        self.hearsay = None
        if facts is None and os.environ.get("RG_HEARSAY") == "1":
            hs = list(getattr(mem.g, "hearsay", {}).values())
            if hs:
                self.hearsay = IndexV3(mem, facts=hs)


_CB = {"model": None, "docs": {}}


def _colbert_scores(question, texts):
    """MaxSim scores of `texts` for `question`; document vectors cached by
    text. The model folder is RG_COLBERT_DIR (model.onnx, tokenizer.json,
    colbert_config.json)."""
    import colbert_onnx
    if _CB["model"] is None:
        _CB["model"] = colbert_onnx.ColBERT(os.environ["RG_COLBERT_DIR"])
    m, cache = _CB["model"], _CB["docs"]
    need = [t for t in dict.fromkeys(texts) if t not in cache]
    if need:
        if len(cache) > 50000:
            cache.clear()
        for t, v in zip(need, m.encode_docs(need)):
            cache[t] = v
    q = m.encode_queries([question])[0]
    return [colbert_onnx.maxsim(q, cache[t]) if hasattr(colbert_onnx, "maxsim")
            else float((q @ cache[t].T).max(axis=1).sum()) for t in texts]


def retrieve_facts_v3(index, question, k=120, dense_k=20, top_n=None,
                      min_score=None, with_scores=False, fuse=None, colbert=None):
    """Retrieve evidence for one question.

    `k` is the BM25 CANDIDATE POOL, `top_n` is how many survive the
    cross-encoder. They were the same variable until entry 178, which meant the
    reranker reordered the pool and never removed anything -- median 77 facts
    reached the composer and 32.5% of questions hit the full 120. Measured on
    round 5, a supporting fact that is present ranks p50=1 / p75=3 / p90=9, so
    a small top_n keeps ~95% of it and drops 55-100 distractor lines.

    top_n=None preserves the round-5 behaviour exactly, so that run stays
    reproducible; RG_TOP_N switches the fix on for A/B.
    """
    import numpy as np
    # RG_POOL_K shrinks what the CROSS-ENCODER must score, which is where the
    # measured 4.5s/query goes (entry 180). Distinct from RG_TOP_N, which only
    # trims what the composer reads and saves no CPU at all.
    pool = os.environ.get("RG_POOL_K", "").strip()
    if pool.isdigit() and int(pool) > 0:
        k = int(pool)
    if top_n is None:
        env = os.environ.get("RG_TOP_N", "").strip()
        top_n = int(env) if env.isdigit() and int(env) > 0 else k
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
    order = np.argsort(-ces)[:top_n]
    if fuse:
        # 2026-10-05 (LoCoMo dev, message search; literature scan: the
        # ms-marco cross-encoder alone ranks chatty answering messages low):
        # z-scored BM25, dense and cross-encoder, weights (bm25, ce) = fuse;
        # dense weight 1 - bm25
        wb, wc = fuse
        bm = dict((j, sc) for sc, j in scored)
        def zs(v):
            v = np.asarray(v, float)
            sd = v.std()
            return (v - v.mean()) / sd if sd > 0 else v * 0
        dn = index.emb[cand] @ qv
        mix = (wb * zs([bm.get(j, 0.0) for j in cand]) + (1 - wb) * zs(dn)
               + wc * zs(ces))
        order = np.argsort(-mix)[:top_n]
    if colbert:
        # 2026-10-05: late interaction (answerai-colbert-small-v1 on ONNX
        # Runtime, colbert_onnx.py) over the same candidates, fused with
        # BM25 and the cross-encoder: weights (bm25, colbert, ce) = colbert
        wb, wk, wc = colbert
        bm = dict((j, sc) for sc, j in scored)
        ks = _colbert_scores(question, [index.texts[j] for j in cand])
        def zs(v):
            v = np.asarray(v, float)
            sd = v.std()
            return (v - v.mean()) / sd if sd > 0 else v * 0
        mix = (wb * zs([bm.get(j, 0.0) for j in cand]) + wk * zs(ks) + wc * zs(ces))
        order = np.argsort(-mix)[:top_n]
    # entry 249: `min_score` is an ABSOLUTE relevance floor on the
    # cross-encoder logit, not a rank cut. The ranked path above always
    # returns top_n whatever the scores are -- correct for the main fact
    # pool (those ARE the answer candidates, and a weak best candidate is
    # still the best we have), but wrong for an optional side-channel like
    # hearsay, where "nothing here is on topic" must be expressible.
    # Default None keeps the banked behaviour byte-identical.
    if min_score is not None:
        order = [i for i in order if float(ces[i]) >= min_score]
    if with_scores:
        return [(index.facts[cand[i]], float(ces[i])) for i in order]
    return [index.facts[cand[i]] for i in order]


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
