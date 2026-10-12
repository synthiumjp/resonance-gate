"""HaluMem with the current product (2026-10-12; docs/PLAN_TO_LAUNCH.md 3.0).

Writes results/rgp2-<version>/rgp2_eval_results.jsonl in the shape the
official harness's evaluation.py reads (`--frame rgp2 --version <version>`),
so its metric definitions, judge prompts and aggregation are used unchanged;
the judge is the local Qwen3-14B (see PATCHES.md; not comparable with the
paper's GPT-4o rows, comparable with every system run here).

Two systems over the same sessions, stored session by session, each
question asked with only the sessions up to its own:
  sdr    sourcedrecall as shipped: profile_ingest per session (the parser,
         no model call), questions answered from profile_context's block
         (the user's dated messages with the parser's labels), the
         extraction artifact = the parser's facts said in that session, the
         update artifact = the block's lines for the update's text.
  plain  plain retrieval: the user's messages ranked by bge-small cosine,
         the top 8 shown dated, oldest first; no extraction artifact (the
         system stores nothing but messages).
Answers: the harness's own PROMPT_MEMZERO through its llm_request, the same
for both systems.

Run from the harness's eval/ folder (it imports llms and prompts from there):
    PYTHONPATH=<repo>/server python <repo>/experiments/p2/halumem_official/eval_sdr.py \
        --system sdr --version sdr-<commit> --users 0,1
Then: python evaluation.py --frame rgp2 --version sdr-<commit> --user_num 2
"""
import argparse
import copy
import datetime
import json
import os
import re
import shutil
import sys
import tempfile
import time

_P2 = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if _P2 not in sys.path:
    sys.path.insert(0, _P2)
_CWD = os.getcwd()
if os.path.exists(os.path.join(_CWD, "llms.py")) and _CWD not in sys.path:
    sys.path.insert(0, _CWD)

_PRIVATE = os.path.expanduser(os.environ.get("RG_PRIVATE", "~/jpwork/rg_private"))
DATA = os.path.join(_PRIVATE, "halumem", "HaluMem-Medium.jsonl")
SCRATCH = os.environ.get("HALUMEM_SCRATCH") or os.path.join(tempfile.gettempdir(), "halumem-sdr")
TOP = 8


def _date(s):
    return datetime.datetime.strptime(s, "%b %d, %Y, %H:%M:%S").isoformat()


def _owner(user):
    m = re.search(r"Name:\s*([^;]+)", user.get("persona_info") or "")
    return m.group(1).strip() if m else None


def _turns(session):
    return [{"role": "user" if t["role"] == "user" else "assistant", "content": t["content"]}
            for t in session["dialogue"]]


class Sdr:
    """sourcedrecall in a fresh memory folder per user."""

    def __init__(self, idx, owner):
        self.dir = os.path.join(SCRATCH, f"u{idx}")
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir)
        os.environ["RG_MEMORY_DIR"] = self.dir
        os.environ["SOURCEDRECALL_STATE"] = os.path.join(self.dir, "state")
        os.environ.setdefault("RG_NLI", "0")          # as in the LoCoMo runs
        from sourcedrecall import profile_memory as pm
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None, "msg_index": None})
        pm._SECRETS.clear()
        self.pm, self.owner = pm, owner

    def add(self, k, session):
        self.pm.profile_ingest(_turns(session), conversation_id=f"s{k}",
                               owner_name=self.owner, date=_date(session["start_time"]))

    def extracted(self, k):
        mem = self.pm._ensure_loaded()
        nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
        return [nd.get("text") or f"{nd['attr']}: {nd['value']}"
                for nd in nodes if f"s{k}" in (nd.get("convs") or {})]

    def context(self, query):
        return self.pm.profile_context(query)["block"]

    def search(self, query):
        block = self.context(query).split("[MEMORY RULES]")[0]
        return [l[2:].strip() for l in block.splitlines() if l.startswith("- ")][:10]


class Plain:
    """The user's own messages, ranked by bge-small cosine."""

    def __init__(self, idx, owner):
        import ort_models
        self.enc = ort_models.Encoder(ort_models.EMBEDDER)
        self.msgs, self.vecs = [], None

    def add(self, k, session):
        import numpy as np
        d = _date(session["start_time"])[:10]
        new = [(d, t["content"]) for t in session["dialogue"] if t["role"] == "user"
               and t["content"].strip()]
        if not new:
            return
        v = self.enc.encode([t for _, t in new], normalize_embeddings=True)
        self.vecs = v if self.vecs is None else np.vstack([self.vecs, v])
        self.msgs += new

    def extracted(self, k):
        return []

    def _top(self, query):
        if not self.msgs:
            return []
        q = self.enc.encode([query], normalize_embeddings=True)[0]
        order = (self.vecs @ q).argsort()[::-1][:TOP]
        return sorted((self.msgs[i] for i in order), key=lambda m: m[0])

    def context(self, query):
        return "\n".join(f'- [{d}] "{" ".join(t.split())}"' for d, t in self._top(query))

    def search(self, query):
        return [f"[{d}] {t}" for d, t in self._top(query)]


def process_user(idx, user, system):
    from llms import llm_request
    from prompts import PROMPT_MEMZERO
    sysm = (Sdr if system == "sdr" else Plain)(idx, _owner(user))
    out = {"uuid": user["uuid"], "user_name": user["uuid"], "sessions": []}
    for k, session in enumerate(user["sessions"]):
        t0 = time.time()
        sysm.add(k, session)
        new = {"memory_points": session["memory_points"], "dialogue": session["dialogue"],
               "add_dialogue_duration_ms": (time.time() - t0) * 1000}
        if session.get("is_generated_qa_session", False):
            new["is_generated_qa_session"] = True
            del new["dialogue"], new["memory_points"]
            out["sessions"].append(new)
            continue
        new["extracted_memories"] = sysm.extracted(k)
        for mpt in new["memory_points"]:
            if mpt.get("is_update") == "True" and mpt.get("original_memories"):
                mpt["memories_from_system"] = sysm.search(mpt["memory_content"])
        if "questions" not in session or os.environ.get("RG_SKIP_QA") == "1":
            out["sessions"].append(new)
            continue
        new["questions"] = []
        for qa in session["questions"]:
            t1 = time.time()
            ctx = sysm.context(qa["question"])
            ans = llm_request(PROMPT_MEMZERO.format(context=ctx, question=qa["question"]))
            q = copy.deepcopy(qa)
            q.update(context=ctx, system_response=ans, search_duration_ms=(time.time() - t1) * 1000,
                     response_duration_ms=0.0)
            new["questions"].append(q)
        out["sessions"].append(new)
        print(f"  user {idx} session {k + 1}/{len(user['sessions'])}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", choices=["sdr", "plain"], required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--users", default="0,1")
    ap.add_argument("--data_path", default=DATA)
    a = ap.parse_args()
    want = {int(x) for x in a.users.split(",")}
    path = f"results/rgp2-{a.version}/rgp2_eval_results.jsonl"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t0 = time.time()
    with open(path, "w", encoding="utf-8") as fo:
        for idx, line in enumerate(open(a.data_path, encoding="utf-8")):
            if idx not in want:
                continue
            user = json.loads(line)
            print(f"[{a.system}] user {idx}: {len(user['sessions'])} sessions", flush=True)
            fo.write(json.dumps(process_user(idx, user, a.system), ensure_ascii=False) + "\n")
            fo.flush()
    print(f"done in {time.time() - t0:.0f} s: {path}")


if __name__ == "__main__":
    main()
