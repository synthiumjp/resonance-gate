"""Ingest each conversation into one memory system and store, per question,
what the system retrieves (no reader here). Resumable.

    python retrieve.py sourcedrecall|mem0|rag --convs 2-9 --out results/test
        [--max-sessions N] [--limit N] [--sample N]

sourcedrecall and rag run in the sourcedrecall venv; mem0 in the mem0 venv
(see README). Writes <out>/ctx_<system>.jsonl, one line per question, and
<out>/ingest_<system>.jsonl, one line per store (or per session for mem0)."""
import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

# the pinned RG checkout (a detached worktree of the commit named in the README)
RG = os.environ.get("RG_REPO", os.path.dirname(os.path.dirname(HERE)))
SCRATCH = os.environ.get("LOCOMO_SCRATCH", "/tmp/locomo_stores")


def msg_texts(sess, owner):
    """(role, speaker, text) for one store: the owner's turns are 'user'."""
    return [("user" if t["speaker"] == owner else "assistant", t["speaker"], t["text"])
            for t in sess]


def evidence_sessions(conv, qid_j):
    s = set()
    for e in conv["qa"][qid_j].get("evidence", []):
        for part in str(e).replace(";", " ").split():
            if part.startswith("D") and ":" in part:
                try:
                    s.add(int(part[1:].split(":")[0]))
                except ValueError:
                    pass
    return s


# ---------------------------------------------------------------- RAG
class Rag:
    name = "rag"

    def __init__(self):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")

    def enc(self, texts, query=False):
        if query:
            texts = ["Represent this sentence for searching relevant passages: " + t for t in texts]
        return self.m.encode(texts, normalize_embeddings=True, batch_size=64)

    def stores(self, idx, conv, max_sessions):
        A, B = conv["conversation"]["speaker_a"], conv["conversation"]["speaker_b"]
        t0 = time.time()
        self.docs = []
        for n, iso, raw, turns in C.sessions(conv)[:max_sessions]:
            for t in turns:
                self.docs.append(f"[{iso or raw}] {t['speaker']}: {t['text']}")
        self.vecs = self.enc(self.docs)
        yield {"speaker": "all", "messages": len(self.docs), "model_calls": len(self.docs),
               "seconds": time.time() - t0}, (A, B)

    def query(self, q, names):
        sims = self.vecs @ self.enc([q], query=True)[0]
        order = sims.argsort()[::-1][:C.TOP_K]
        return {"Retrieved turns": [self.docs[i] for i in order]}


# ------------------------------------------------------- sourcedrecall
class Ours:
    name = "sourcedrecall"

    def __init__(self):
        os.environ["RG_NLI"] = "0"
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.pop("SOURCEDRECALL_OWNER", None)
        for p in ("server", ""):   # sourcedrecall, rgx, experiments/p2 all from the pinned checkout
            sys.path.insert(0, os.path.join(RG, p) if p else RG)
        self.pm = None

    def _fresh(self, d):
        os.environ["RG_MEMORY_DIR"] = d
        import sourcedrecall.profile_memory as pm
        self.pm = pm
        keep = pm._ingest_state.get("extractor")
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": keep,
                                 "owner": pm._ingest_state.get("owner") if keep else None})

    def stores(self, idx, conv, max_sessions):
        c = conv["conversation"]
        for owner in (c["speaker_a"], c["speaker_b"]):
            d = os.path.join(SCRATCH, f"ours_{idx}_{owner}")
            shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d)
            self._fresh(d)
            t0 = time.time()
            n = calls = 0
            # profile_ingest rebuilds the whole graph and rewrites MEMORY.md after every
            # call, which is quadratic over 30 sessions. Extraction and the cache do not
            # depend on that rebuild, so it is deferred to once, after the last session.
            real_reload, real_export = self.pm._reload_locked, self.pm._export_quietly
            self.pm._reload_locked = lambda: None
            self.pm._export_quietly = lambda: None
            for sn, iso, raw, turns in C.sessions(conv)[:max_sessions]:
                tt = [{"role": r, "content": x} for r, _s, x in msg_texts(turns, owner)]
                res = self.pm.profile_ingest(tt, conversation_id=f"s{sn}", title=f"session {sn}",
                                             owner_name=owner, date=iso)
                n += res["turns"]
                calls += res["model_calls"]
            self.pm._reload_locked, self.pm._export_quietly = real_reload, real_export
            self.pm._state["mem"] = None     # next recall loads the finished store
            self.owner = owner
            yield {"speaker": owner, "messages": n, "model_calls": calls,
                   "seconds": time.time() - t0}, (owner,)

    def query(self, q, names):
        r = self.pm.profile_recall(q)
        lines = []
        if r.get("found") and not r.get("abstain"):
            for f in r.get("ranked", [])[:C.TOP_K]:
                s = f["text"]
                if f.get("said"):
                    s += f' [they said: "{f["said"]}"]'
                dt = (f.get("receipts") or [{}])[0].get("date")
                if dt:
                    s += f" (date: {dt})"
                if not f.get("current", True):
                    s = "(no longer true) " + s
                lines.append(s)
        return {f"Memories of {self.owner}": lines}


# ---------------------------------------------------------------- Mem0
class Mem0:
    name = "mem0"

    def __init__(self):
        os.environ.setdefault("MEM0_TELEMETRY", "False")
        self.calls = 0

    def _mk(self, d):
        from mem0 import Memory
        base = os.environ.get("LOCOMO_MEM0_LLM_BASE")
        if base:   # llama_cpp.server (OpenAI-compatible) through the tunnel
            llm = {"provider": "openai", "config": {
                "model": C.LLM_MODEL, "temperature": 0.0, "max_tokens": 2000,
                "openai_base_url": base, "api_key": "none"}}
        else:      # dev: Ollama, qwen3-14b-fm = qwen3:14b + num_ctx 12288
            llm = {"provider": "ollama", "config": {
                "model": os.environ.get("FM_MEM0_LLM", "qwen3-14b-fm"), "temperature": 0.0,
                "max_tokens": 2000, "ollama_base_url": "http://127.0.0.1:11434"}}
        cfg = {"llm": llm,
               "embedder": {"provider": "ollama", "config": {
                   "model": "nomic-embed-text", "ollama_base_url": "http://127.0.0.1:11434",
                   "embedding_dims": 768}},
               "vector_store": {"provider": "qdrant", "config": {
                   "collection_name": "lc", "path": os.path.join(d, "qdrant"),
                   "embedding_model_dims": 768, "on_disk": True}},
               "history_db_path": os.path.join(d, "history.db")}
        m = Memory.from_config(cfg)
        g, e = m.llm.generate_response, m.embedding_model.embed

        def gen(*a, **k):
            self.calls += 1
            return g(*a, **k)

        def emb(*a, **k):
            self.calls += 1
            return e(*a, **k)
        m.llm.generate_response, m.embedding_model.embed = gen, emb
        client = m.llm.client
        if base:
            create = client.chat.completions.create

            def nothink(*a, **k):
                # qwen3 thinking off, no Mem0 prompt text changed. "/no_think" goes at the
                # START of the system message (at the end of the user message the model
                # ignores it). response_format=json_object is dropped: llama_cpp turns it
                # into a JSON grammar that forbids the empty <think></think> block the model
                # writes first, and the model then answers "{}" for every session. The empty
                # think block is stripped from the reply before Mem0 parses it.
                ms = [dict(x) for x in k.get("messages", [])]
                if ms and ms[0].get("role") == "system":
                    ms[0]["content"] = "/no_think\n" + str(ms[0]["content"])
                elif ms:
                    ms[0]["content"] = "/no_think\n" + str(ms[0]["content"])
                k["messages"] = ms
                k.pop("response_format", None)
                resp = create(*a, **k)
                try:
                    import re as _re
                    msg = resp.choices[0].message
                    msg.content = _re.sub(r"<think>.*?</think>", "", msg.content or "", flags=_re.S).strip()
                except Exception:   # noqa: BLE001
                    pass
                return resp
            client.chat.completions.create = nothink
        else:
            chat = client.chat

            def chat_nothink(*a, **k):
                k.setdefault("think", False)
                return chat(*a, **k)
            client.chat = chat_nothink
        return m

    def stores(self, idx, conv, max_sessions):
        c = conv["conversation"]
        self.mem = {}
        prog = os.path.join(self.out, "mem0_progress.jsonl")
        done = {(r["conv"], r["speaker"], r["session"]) for r in C.jsonl_read(prog)}
        for owner in (c["speaker_a"], c["speaker_b"]):
            d = os.path.join(SCRATCH, f"mem0_{idx}_{owner}")
            ses = C.sessions(conv)[:max_sessions]
            if not any((idx, owner, s[0]) in done for s in ses):
                shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)
            m = self._mk(d)
            self.mem[owner] = m
            t0 = time.time()
            n = 0
            self.calls = 0
            for sn, iso, raw, turns in ses:
                if (idx, owner, sn) in done:
                    continue
                # Mem0 2.2.1 OSS rejects a timestamp argument, so the date and the
                # speaker's name go in the message text.
                msgs = [{"role": r, "content": f"[{iso or raw}] {s}: {x}"}
                        for r, s, x in msg_texts(turns, owner)]
                t1 = time.time()
                c0 = self.calls
                m.add(msgs, user_id=owner)
                n += len(msgs)
                C.jsonl_append(prog, {"conv": idx, "speaker": owner, "session": sn,
                                      "messages": len(msgs), "model_calls": self.calls - c0,
                                      "seconds": time.time() - t1})
            # one ingest line per store is assembled from the progress log
            rows = [r for r in C.jsonl_read(prog) if r["conv"] == idx and r["speaker"] == owner]
            yield {"speaker": owner, "messages": sum(r["messages"] for r in rows),
                   "model_calls": sum(r["model_calls"] for r in rows),
                   "seconds": sum(r["seconds"] for r in rows)}, (owner,)

    def query(self, q, names):
        out = {}
        for owner, m in self.mem.items():
            r = m.search(q, filters={"user_id": owner}, top_k=C.TOP_K)
            items = r["results"] if isinstance(r, dict) else r
            out[f"Memories of {owner}"] = [it["memory"] for it in items]
        return out


def fmt(sections):
    parts = []
    for k, lines in sections.items():
        parts.append(k + ":\n" + ("\n".join("- " + l for l in lines) if lines else "- (nothing retrieved)"))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=["sourcedrecall", "mem0", "rag"])
    ap.add_argument("--convs", default="2-9")
    ap.add_argument("--out", default=os.path.join(C.RESULTS, "test"))
    ap.add_argument("--max-sessions", type=int, default=999)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sample", type=int, default=0, help="per-conversation sample size")
    a = ap.parse_args()
    sysobj = {"sourcedrecall": Ours, "mem0": Mem0, "rag": Rag}[a.system]()
    sysobj.out = a.out
    ctxf = os.path.join(a.out, f"ctx_{a.system}.jsonl")
    ingf = os.path.join(a.out, f"ingest_{a.system}.jsonl")
    done = {r["qid"] for r in C.jsonl_read(ctxf)}
    for idx, conv in C.load(C.parse_convs(a.convs)):
        qs = C.questions(idx, conv)
        if a.max_sessions < 999:   # dev: only questions whose evidence is inside the ingested sessions
            qs = [q for q in qs
                  if (lambda ev: ev and max(ev) <= a.max_sessions)(
                      evidence_sessions(conv, int(q["qid"].split(":")[1])))]
        if a.sample:
            qs = C.sample(qs, a.sample)
        if a.limit:
            qs = qs[:a.limit]
        todo = [q for q in qs if q["qid"] not in done]
        if not todo:
            continue
        print(f"conv {idx}: {len(todo)} questions to retrieve", flush=True)
        for stats, names in sysobj.stores(idx, conv, a.max_sessions):
            C.jsonl_append(ingf, dict(stats, conv=idx, system=a.system))
            print("  ingested", stats, flush=True)
            # sourcedrecall answers one store at a time (module state), so retrieval is
            # stored per store and merged below; rag/mem0 hold all stores at once.
            if a.system == "sourcedrecall" or (a.system == "mem0" and stats["speaker"] != conv["conversation"]["speaker_b"]):
                if a.system == "sourcedrecall":
                    part = os.path.join(a.out, f"part_{a.system}_{idx}_{stats['speaker']}.jsonl")
                    have = {r["qid"] for r in C.jsonl_read(part)}
                    for q in todo:
                        if q["qid"] in have:
                            continue
                        t0 = time.time()
                        s = sysobj.query(q["question"], names)
                        C.jsonl_append(part, {"qid": q["qid"], "speaker": stats["speaker"],
                                              "sections": s, "latency": time.time() - t0})
                continue
            for q in todo:
                t0 = time.time()
                s = sysobj.query(q["question"], names)
                dt = time.time() - t0
                ctx = fmt(s)
                C.jsonl_append(ctxf, dict(q, system=a.system, context=ctx, latency=dt,
                                          ctx_tokens=len(ctx) // 4))
        if a.system == "sourcedrecall":
            parts = {}
            for sp in (conv["conversation"]["speaker_a"], conv["conversation"]["speaker_b"]):
                for r in C.jsonl_read(os.path.join(a.out, f"part_{a.system}_{idx}_{sp}.jsonl")):
                    parts.setdefault(r["qid"], []).append(r)
            for q in todo:
                rs = parts[q["qid"]]
                sec = {}
                for r in rs:
                    sec.update(r["sections"])
                ctx = fmt(sec)
                C.jsonl_append(ctxf, dict(q, system=a.system, context=ctx,
                                          latency=sum(r["latency"] for r in rs),
                                          ctx_tokens=len(ctx) // 4))


if __name__ == "__main__":
    main()
