"""The three systems behind one tiny interface.

    adapter = Adapter(workdir)           # fresh, empty store
    cost = adapter.ingest(scenario)      # {"messages", "model_calls", "seconds"}
    out  = adapter.query(question)       # {"lines": [str], "views": {name: [str]}}

`lines` is the memory the system RETURNS for the question and is what the
scorer judges. A system may expose extra views (ours also exposes the
profile_context block); views are scored separately and never mixed into the
headline.

Run each adapter in its own Python environment (see README): sourcedrecall
needs stanza, Mem0 needs mem0ai, the RAG baseline needs only
sentence-transformers. Imports are therefore lazy.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("RG_REPO") or os.path.dirname(os.path.dirname(HERE))   # RG code under test (sourcedrecall only)
TOP_K = 5          # cap on returned items for Mem0 and sourcedrecall
RAG_K = 3          # fixed by the benchmark spec for the verbatim baseline

OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
MEM0_LLM = os.environ.get("FM_MEM0_LLM", "qwen3-14b-fm")   # = qwen3:14b + num_ctx 12288, see Modelfile.mem0
MEM0_EMBED = os.environ.get("FM_MEM0_EMBED", "nomic-embed-text")


def _messages(scenario):
    for conv in scenario["conversations"]:
        for t in conv["turns"]:
            yield conv, t


# --------------------------------------------------------------- RAG
class RagAdapter:
    """Every USER message stored verbatim, top-3 by bge-small cosine."""
    name = "rag"
    _model = None

    def __init__(self, workdir):
        if RagAdapter._model is None:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
            RagAdapter._model = SentenceTransformer("BAAI/bge-small-en-v1.5",
                                                     device="cpu")
        self.msgs = []
        self.vecs = None

    def _enc(self, texts, query=False):
        if query:   # bge's documented retrieval instruction for queries
            texts = ["Represent this sentence for searching relevant passages: " + t
                     for t in texts]
        return RagAdapter._model.encode(texts, normalize_embeddings=True)

    def ingest(self, scenario):
        t0 = time.time()
        n = 0
        for conv, t in _messages(scenario):
            n += 1
            if t["role"] == "user":
                self.msgs.append((conv["date"], t["content"]))
        import numpy as np
        self.vecs = (self._enc([m[1] for m in self.msgs])
                     if self.msgs else np.zeros((0, 384)))
        return {"messages": n, "model_calls": len(self.msgs),  # one embed per stored message
                "seconds": time.time() - t0}

    def query(self, q):
        if not self.msgs:
            return {"lines": [], "views": {}}
        sims = self.vecs @ self._enc([q], query=True)[0]
        order = sims.argsort()[::-1][:RAG_K]
        lines = [f"[{self.msgs[i][0]}] {self.msgs[i][1]}" for i in order]
        return {"lines": lines, "views": {}}


# --------------------------------------------------------------- Mem0
class Mem0Adapter:
    """Mem0 OSS, fully local: ollama LLM + ollama embedder + on-disk qdrant.
    Standard add(messages, user_id=...) / search(query, filters={user_id}).
    Nothing in Mem0's prompts is changed unless FM_MEM0_NOTHINK=1 handling in
    _install_nothink() is needed (see README)."""
    name = "mem0"

    def __init__(self, workdir):
        os.environ.setdefault("MEM0_TELEMETRY", "False")
        from mem0 import Memory
        self.user = "owner"
        cfg = {
            "llm": {"provider": "ollama", "config": {
                "model": MEM0_LLM, "temperature": 0.0, "max_tokens": 2000,
                "ollama_base_url": OLLAMA}},
            "embedder": {"provider": "ollama", "config": {
                "model": MEM0_EMBED, "ollama_base_url": OLLAMA,
                "embedding_dims": 768}},
            "vector_store": {"provider": "qdrant", "config": {
                "collection_name": "fm", "path": os.path.join(workdir, "qdrant"),
                "embedding_model_dims": 768, "on_disk": True}},
            "history_db_path": os.path.join(workdir, "history.db"),
        }
        self.m = Memory.from_config(cfg)
        self.calls = 0
        self._wrap()

    def _wrap(self):
        llm, emb = self.m.llm, self.m.embedding_model
        g = llm.generate_response
        e = emb.embed

        def gen(*a, **k):
            self.calls += 1
            return g(*a, **k)

        def embed(*a, **k):
            self.calls += 1
            return e(*a, **k)
        llm.generate_response = gen
        emb.embed = embed
        # qwen3 is a thinking model; Mem0 does not pass `think`, so ollama
        # would spend minutes of CPU on reasoning before the JSON. Switch it
        # off at the client call. This is the ONLY behavioural change.
        client = llm.client
        chat = client.chat

        def chat_nothink(*a, **k):
            k.setdefault("think", False)
            return chat(*a, **k)
        client.chat = chat_nothink

    def ingest(self, scenario):
        t0 = time.time()
        n = 0
        self.calls = 0
        # one add() per conversation, in date order; the whole dialogue (both
        # roles) is passed, as Mem0's own examples do.
        for conv in scenario["conversations"]:
            msgs = [{"role": t["role"], "content": t["content"]} for t in conv["turns"]]
            n += len(msgs)
            self.m.add(msgs, user_id=self.user)
        return {"messages": n, "model_calls": self.calls,
                "seconds": time.time() - t0}

    def query(self, q):
        r = self.m.search(q, filters={"user_id": self.user}, top_k=TOP_K)
        items = r["results"] if isinstance(r, dict) else r
        lines = [it["memory"] for it in items]
        return {"lines": lines, "views": {}}

    def dump(self):
        r = self.m.get_all(filters={"user_id": self.user})
        items = r["results"] if isinstance(r, dict) else r
        return [it["memory"] for it in items]


# --------------------------------------------------------------- ours
class SourcedRecallAdapter:
    """sourcedrecall.profile_memory, deterministic parser, no model calls.
    A store is a fresh RG_MEMORY_DIR; module state is reset between stores
    the way server/tests/test_profile_ingest.py does (the stanza extractor is
    kept across stores: it is stateless apart from owner_name)."""
    name = "sourcedrecall"

    def __init__(self, workdir):
        os.environ["RG_MEMORY_DIR"] = workdir
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.pop("SOURCEDRECALL_OWNER", None)
        sys.path.insert(0, os.path.join(REPO, "server"))
        import sourcedrecall.profile_memory as pm
        self.pm = pm
        keep = pm._ingest_state.get("extractor")
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": keep,
                                 "owner": pm._ingest_state.get("owner") if keep else None})
        self.n = 0

    def ingest(self, scenario):
        t0 = time.time()
        n = 0
        calls = 0
        for conv in scenario["conversations"]:
            self.n += 1
            res = self.pm.profile_ingest(
                conv["turns"], conversation_id=f"c{self.n}",
                title=f"conversation {self.n}", owner_name=scenario["owner"],
                date=conv["date"])
            n += res["turns"]
            calls += res["model_calls"]
        return {"messages": n, "model_calls": calls, "seconds": time.time() - t0}

    def dump(self):
        """Every stored fact (2026-10-03), so an audit can tell a fact that
        was never stored from one stored but not returned."""
        mem = self.pm._ensure_loaded()
        return [{"text": f.get("text"), "said": f.get("said"),
                 "tier": f.get("_tier"), "current": f.get("current"),
                 "date": (f.get("receipts") or [{}])[0].get("date")}
                for f in self.pm._all_facts(mem)]

    @staticmethod
    def _fact_line(f):
        tag = "" if f.get("current", True) else "(no longer true) "
        said = f.get("said")
        return f'{tag}{f["text"]}' + (f' [they said: "{said}"]' if said else "")

    def query(self, q):
        r = self.pm.profile_recall(q)
        lines = []
        if r.get("found") and not r.get("abstain"):
            lines = [self._fact_line(f) for f in r.get("ranked", [])[:TOP_K]]
        elif r.get("related"):
            # sourcedrecall >= 0.4.1 returns labelled candidates when nothing
            # is confirmed; they reach the agent, so they are scored
            lines = ["(possibly related, not confirmed) " + self._fact_line(f)
                     for f in r["related"][:TOP_K]]
        blk = self.pm.profile_context(q)["block"]
        ctx = [ln[2:] for ln in blk.splitlines() if ln.startswith("- ")]
        # the whole block, as an agent receives it (answer.py reads it)
        return {"lines": lines, "views": {"context": ctx}, "block": blk}
