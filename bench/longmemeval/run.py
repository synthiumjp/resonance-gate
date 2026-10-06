"""LongMemEval-S retrieval recall for sourcedrecall (no language model).
Usage: run.py OUT.jsonl [--limit N] [--start I]
Per question: fresh store, ingest every haystack session, rank sessions by
profile_memory._messages_for(question, k=50) with and without RG_FUSE, plus
BM25 and bge-small baselines over the same user-turn index. One JSONL line
per question (ranked distinct sessions and ranked user turns); metrics are
computed by report.py. Resumable: questions already in OUT are skipped."""
import json, os, re, sys, time, shutil, math
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("RG_REPO") or os.path.dirname(os.path.dirname(HERE))
DATA = os.environ.get("LME_DATA") or os.path.join(HERE, "longmemeval_s_cleaned.json")
SCRATCH = os.environ.get("LME_SCRATCH") or os.path.join(HERE, "scratch")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.dont_write_bytecode = True
sys.path.insert(0, REPO + "/server")

import numpy as np

class _StubExtractor:
    # message search reads only conversations.json; the fact parser (stanza)
    # is ~95% of ingest time and cannot change the message ranking. FULL=1
    # keeps the real parser.
    _world = {}
    def extract_turn(self, *a, **k): return []

def reset(pm, workdir):
    os.environ["RG_MEMORY_DIR"] = workdir
    os.environ.pop("SOURCEDRECALL_OWNER", None)
    keep = pm._ingest_state.get("extractor")
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None,
                      "msg_index": None})
    pm._ingest_state.update({"extractor": keep,
                             "owner": pm._ingest_state.get("owner") if keep else None})

TOK = re.compile(r"[a-z0-9]+")
def toks(s): return TOK.findall(s.lower())

def bm25_scores(docs_tok, qtok, k1=1.5, b=0.75):
    n = len(docs_tok)
    df = Counter()
    for d in docs_tok:
        df.update(set(d))
    avg = sum(len(d) for d in docs_tok) / max(n, 1)
    sc = np.zeros(n)
    for i, d in enumerate(docs_tok):
        tf = Counter(d)
        s = 0.0
        for q in set(qtok):
            f = tf.get(q)
            if not f:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / avg))
        sc[i] = s
    return sc

def norm(s): return " ".join(s.split())

def run_question(pm, rv3, e, qi):
    wd = f"{SCRATCH}/q{qi}"
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)
    try:
        reset(pm, wd)
        t0 = time.time()
        for sid, sess, date in zip(e["haystack_session_ids"], e["haystack_sessions"], e["haystack_dates"]):
            d = date.split(" ")[0].replace("/", "-")
            pm.profile_ingest([{"role": t["role"], "content": t["content"]} for t in sess],
                              conversation_id=sid, owner_name="User", date=d)
        t_ing = time.time() - t0
        # user turns by session, for turn matching
        uturns = {}
        for sid, sess in zip(e["haystack_session_ids"], e["haystack_sessions"]):
            uturns[sid] = [(i, norm(t["content"])) for i, t in enumerate(sess) if t["role"] == "user"]
        used = set()
        def to_turn(sid, text):
            nt = norm(text)
            cands = uturns.get(sid, [])
            for i, c in cands:
                if (sid, i) not in used and c == nt:
                    used.add((sid, i)); return i
            for i, c in cands:
                if (sid, i) not in used and nt and nt in c:
                    used.add((sid, i)); return i
            for i, c in cands:   # denied sentences removed: match on prefix
                if (sid, i) not in used and nt[:40] and c.startswith(nt[:40]):
                    used.add((sid, i)); return i
            return None
        def rank(hits):
            sess, turns = [], []
            nonm = 0
            used.clear()
            for h in hits:
                if h["conv"] not in sess:
                    sess.append(h["conv"])
                ti = to_turn(h["conv"], h["text"])
                if ti is None: nonm += 1
                else: turns.append([h["conv"], ti])
            return sess, turns, nonm
        out = {"question_id": e["question_id"], "question_type": e["question_type"],
               "abs": "_abs" in e["question_id"], "answer_session_ids": e["answer_session_ids"],
               "gold_turns": [[sid, i] for sid, sess in zip(e["haystack_session_ids"], e["haystack_sessions"])
                              for i, t in enumerate(sess) if t["role"] == "user" and t.get("has_answer")],
               "gold_turns_any_role": [[sid, i] for sid, sess in zip(e["haystack_session_ids"], e["haystack_sessions"])
                              for i, t in enumerate(sess) if t.get("has_answer")],
               "n_sessions": len(e["haystack_sessions"]), "ingest_s": round(t_ing, 1), "sys": {}}
        q = e["question"]
        t0 = time.time()
        # LME_VARIANTS="ours:;dense:RG_FUSE3=1,RG_FUSE3_W=0.2/0.0" -- each
        # variant sets environment variables for the message search
        variants = os.environ.get("LME_VARIANTS", "ours:")
        for spec in variants.split(";"):
            name, _, assigns = spec.partition(":")
            saved = {}
            for a in filter(None, assigns.split(",")):
                k, v = a.split("=", 1)
                saved[k] = os.environ.get(k)
                os.environ[k] = v
            pm._state["msg_index"] = pm._state.get("msg_index")
            hits = pm._messages_for(q, k=50)
            s, t, nonm = rank(hits)
            out["sys"][name] = {"sessions": s, "turns": t, "n_hits": len(hits), "unmatched": nonm}
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        out["retrieve_s"] = round(time.time() - t0, 1)
        # baselines over the same index
        idx = pm._state["msg_index"][1]
        facts = idx.facts
        out["n_docs"] = len(facts)
        bi = rv3._models()[0]
        qv = bi.encode([q], normalize_embeddings=True)[0]
        dsc = np.asarray(idx.emb) @ qv
        bsc = bm25_scores([toks(d["text"]) for d in facts], toks(q))
        for name, sc in (("bm25", bsc), ("bge", dsc)):
            order = np.argsort(-sc, kind="stable")
            sess, turns = [], []
            used.clear()
            for j in order:
                d = facts[j]
                if d["conv"] not in sess:
                    sess.append(d["conv"])
                if len(turns) < 50:
                    ti = to_turn(d["conv"], d["text"])
                    if ti is not None: turns.append([d["conv"], ti])
            out["sys"][name] = {"sessions": sess[:50], "turns": turns}
        return out
    finally:
        shutil.rmtree(wd, ignore_errors=True)
        try:
            import retrieve_v3 as r
            r._EMB_CACHE.clear()
        except Exception:
            pass

def main():
    outp = sys.argv[1]
    limit = None; start = 0
    if "--limit" in sys.argv: limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--start" in sys.argv: start = int(sys.argv[sys.argv.index("--start") + 1])
    done = set()
    if os.path.exists(outp):
        for ln in open(outp):
            try: done.add(json.loads(ln)["question_id"])
            except Exception: pass
    data = json.load(open(DATA))
    if "--spread" in sys.argv:   # smoke: spread over types/positions
        data = data[::max(1, len(data) // (limit or 10))]
    data = data[start:]
    if os.environ.get("LME_TYPES"):
        keep = set(os.environ["LME_TYPES"].split(","))
        data = [e for e in data if e["question_type"] in keep]
    import sourcedrecall.profile_memory as pm
    import retrieve_v3 as rv3
    if os.environ.get("FULL") != "1":
        pm._get_extractor = lambda owner: _StubExtractor()
    n = 0
    t00 = time.time()
    for qi, e in enumerate(data, start):
        if limit and n >= limit: break
        if e["question_id"] in done: continue
        t0 = time.time()
        r = run_question(pm, rv3, e, qi)
        r["total_s"] = round(time.time() - t0, 1)
        with open(outp, "a") as fh:
            fh.write(json.dumps(r) + "\n")
        n += 1
        print(f"{n} {e['question_id']} {r['total_s']}s docs={r['n_docs']} elapsed={time.time()-t00:.0f}", flush=True)

main()
