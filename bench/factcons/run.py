"""Updated facts v1 (docs/PREREG_FACTCONSOL_V1.md): MemoryAgentBench's
FactConsolidation sets, fed to each memory as dated sessions of 25 facts.
Runs on the Mac; reads FC_DATA (one jsonl per set, made from the parquet by
prep.sh) and writes only to OUT. Resumable: each step skips what is done.

    python run.py ours    OUT SET ...     # SET: factconsolidation_sh_6k, ...
    python run.py native  OUT SET ...     # Qwen writer (labelled unfair to native)
    python run.py context OUT SET ... [-- system ...]
    python run.py answer  OUT [system ...]
    python run.py score   OUT

Systems: sourcedrecall, rag, native-qwen, full (the whole dated list, a ceiling,
only where it fits the reader). sh and mh sets of one size share a fact list,
so stores and native memory are kept per list.
"""
import datetime
import functools
import json
import os
import re
import string
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "coding"))
from common import TooLong, append, chat, claim, jsonl  # noqa: E402

sys.path.insert(0, os.path.dirname(HERE))      # bench/, for claude_memory
DATA = os.path.expanduser(os.environ.get("FC_DATA", "~/jpwork/mab_data"))
PER_SESSION, K = 25, 10
START = datetime.date(2026, 1, 1)
SYSTEMS = ["sourcedrecall", "rag", "native-qwen", "full"]


@functools.lru_cache(None)
def load(name):
    return jsonl(os.path.join(DATA, name + ".jsonl"))[0]


def list_key(name):
    return name.rsplit("_", 1)[1]           # 6k, 32k, 64k: one fact list per size


@functools.lru_cache(None)
def sessions(name):
    """[(date, [fact, ...])]: the facts in order, numbers removed, 25 a day."""
    facts = [re.sub(r"^\d+\. ", "", l).strip() for l in load(name)["context"].splitlines()
             if re.match(r"\d+\. ", l)]
    return [((START + datetime.timedelta(i // PER_SESSION)).isoformat(), facts[i:i + PER_SESSION])
            for i in range(0, len(facts), PER_SESSION)]


# ------------------------------------------------------------ sourcedrecall
_CUR = {}


def _store(out, key):
    d = os.path.join(out, "stores", key)
    import sourcedrecall.profile_memory as pm
    if _CUR.get("d") != d:      # as bench/locomo/retrieve.py's Ours._fresh
        os.environ.update(RG_MEMORY_DIR=d, RG_NLI="0", SOURCEDRECALL_SCOPING="0")
        os.environ.pop("SOURCEDRECALL_OWNER", None)
        keep = pm._ingest_state.get("extractor")
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": keep,
                                 "owner": pm._ingest_state.get("owner") if keep else None})
        _CUR["d"] = d
    return d, pm


def ours(out, name):
    key = list_key(name)
    d, pm = _store(out, key)
    if os.path.exists(os.path.join(d, "done")):
        return
    os.makedirs(d, exist_ok=True)
    # as on LoCoMo: the graph rebuild and MEMORY.md export once, after the last session
    real_reload, real_export = pm._reload_locked, pm._export_quietly
    pm._reload_locked = pm._export_quietly = lambda: None
    for i, (date, facts) in enumerate(sessions(name)):
        pm.profile_ingest([{"role": "user", "content": "\n".join(facts)}], conversation_id=f"s{i}",
                          title=f"facts {i}", owner_name="user", date=date)
    pm._reload_locked, pm._export_quietly = real_reload, real_export
    pm._state["mem"] = None      # the next recall loads the finished store
    open(os.path.join(d, "done"), "w").write("")
    print("ours", key, "stored", flush=True)


def ours_context(out, name, q):
    _d, pm = _store(out, list_key(name))
    blk = pm.profile_context(q, max_facts=K)["block"]
    return [l[2:] for l in blk.splitlines() if l.startswith("- ")]


# ---------------------------------------------------------- plain retrieval
_RAG = {}


def rag_context(name, q):
    import retrieve_v3 as RV3
    key = list_key(name)
    if key not in _RAG:
        docs = [{"attr": "", "value": f, "text": f, "date": d} for d, fs in sessions(name) for f in fs]
        _RAG.clear()
        _RAG[key] = RV3.IndexV3(None, facts=docs)
    hits = RV3.retrieve_facts_v3(_RAG[key], q, k=60, dense_k=30, top_n=K)
    return [f"[{h['date']}] {h['text']}" for h in hits]


# ------------------------------------------------- native memory, Qwen writer
def native(out, name):
    import claude_memory as CM
    key = list_key(name)
    p = os.path.join(out, "native", key + ".json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    st = json.load(open(p)) if os.path.exists(p) else {"done": 0, "files": {}}
    ss = sessions(name)
    if st["done"] >= len(ss) or st.get("stopped") or not claim(p):
        return
    try:
        for i in range(st["done"], len(ss)):
            date, facts = ss[i]
            prompt = (CM.INSTRUCTIONS
                      + '\n\nReply with JSON only: {"changes": [{"action": "write" or "delete", '
                        '"file": "name.md", "content": "..."}]}'
                      + f"\n\nThe conversation's date: {date}.\n\nThe memory folder:\n\n"
                      + CM._folder(st["files"])
                      + "\n\nThe conversation that just ended:\n\n<transcript>\nUSER: "
                      + "\n".join(facts) + "\n</transcript> /no_think")
            changes = None
            try:
                for _ in range(2):
                    m = re.search(r"\{.*\}", chat(prompt, max_tokens=4000) or "", re.S)
                    try:
                        changes = json.loads(m.group(0))["changes"] if m else None
                        break
                    except (ValueError, KeyError, TypeError):
                        changes = None
            except TooLong:     # the folder no longer fits the writer's window
                st["stopped"] = i
                print("native", key, "stopped at session", i, flush=True)
                break
            files = dict(st["files"])
            for ch in changes or []:
                if not isinstance(ch, dict) or not ch.get("file"):
                    continue
                n = CM._safe(ch["file"])
                if ch.get("action") == "delete":
                    files.pop(n, None)
                else:
                    files[n] = str(ch.get("content", "")).strip()
            st.update(files=files, done=i + 1, unreadable=st.get("unreadable", 0) + (changes is None))
            json.dump(st, open(p + ".tmp", "w"))
            os.replace(p + ".tmp", p)
            print("native", key, i + 1, "/", len(ss), len(files), "files", flush=True)
        json.dump(st, open(p + ".tmp", "w"))
        os.replace(p + ".tmp", p)
    finally:
        os.remove(p + ".lock")


def native_context(out, name):
    import retrieve  # noqa: F401  experiments/p2's, before claude_memory puts bench/locomo first
    import claude_memory as CM
    st = json.load(open(os.path.join(out, "native", list_key(name) + ".json")))
    return None if st.get("stopped") is not None else CM.lines(st["files"])


def full_context(name):
    return [f"[{d}] {f}" for d, fs in sessions(name) for f in fs]


# ------------------------------------------------------------------ the run
def context(out, names, systems=None):
    path = os.path.join(out, "context.jsonl")
    have = {(r["system"], r["qid"]) for r in jsonl(path)}
    for name in names:
        r = load(name)
        for i, (q, a) in enumerate(zip(r["questions"], r["answers"])):
            qid = f"{name}#{i}"
            for s in systems or SYSTEMS:
                if (s, qid) in have:
                    continue
                if s == "sourcedrecall":
                    lines = ours_context(out, name, q)
                elif s == "rag":
                    lines = rag_context(name, q)
                elif s == "native-qwen":
                    lines = native_context(out, name)
                else:
                    lines = full_context(name)
                if lines is None:
                    continue
                append(path, {"qid": qid, "set": name, "system": s, "question": q, "answers": a,
                              "lines": lines, "ctx_tokens": len("\n".join(lines)) // 4})
            print(qid, flush=True)


READ = """You have a memory of facts the user told you in earlier conversations, each with its date. When two facts conflict, the one with the later date holds. Using only the memory below, answer the question with just the answer, in a few words. If the memory does not answer it, say you don't know.

MEMORY:
{memory}

QUESTION: {q} /no_think"""


def answer(out, systems=None):
    from common import READER, READER_MODEL
    path = os.path.join(out, os.environ.get("FC_ANSWERS", "answers.jsonl"))
    have = {(r["system"], r["qid"]) for r in jsonl(path)}
    for r in jsonl(os.path.join(out, "context.jsonl")):
        if (systems and r["system"] not in systems) or (r["system"], r["qid"]) in have:
            continue
        mem = "\n".join(f"- {l}" for l in r["lines"]) or "(nothing)"
        try:
            a = chat(READ.format(memory=mem, q=r["question"]), max_tokens=60,
                     base=READER, model=READER_MODEL)
        except TooLong:   # past the reader's window: no row
            print(r["system"], r["qid"], "too long", flush=True)
            continue
        a = re.sub(r"<think>.*?</think>", "", a or "", flags=re.S).strip()
        ok = any(_norm(g) in _norm(a) for g in r["answers"] if _norm(g))
        append(path, {"qid": r["qid"], "set": r["set"], "system": r["system"], "pred": a,
                      "correct": ok, "ctx_tokens": r["ctx_tokens"]})
        print(r["system"], r["qid"], ok, flush=True)


def _norm(s):
    """SQuAD-style, as MemoryAgentBench's substring match: lower case, no
    punctuation, no articles, single spaces."""
    s = "".join(c for c in s.lower() if c not in string.punctuation)
    return " ".join(w for w in s.split() if w not in ("a", "an", "the"))


def score(out):
    rows = jsonl(os.path.join(out, os.environ.get("FC_ANSWERS", "answers.jsonl")))
    systems = [s for s in SYSTEMS if any(r["system"] == s for r in rows)]
    sets = sorted({r["set"] for r in rows}, key=lambda n: (int(list_key(n)[:-1]), n))
    print("| set | " + " | ".join(systems) + " |")
    print("|---|" + "---|" * len(systems))
    for name in sets:
        cells = []
        for s in systems:
            rs = [r for r in rows if r["set"] == name and r["system"] == s]
            cells.append(f"{sum(r['correct'] for r in rs)}/{len(rs)}"
                         + (f" ({sum(r['ctx_tokens'] for r in rs) // len(rs)} tok)" if rs else "")
                         if rs else "-")
        print(f"| {name} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    cmd, out = sys.argv[1], os.path.expanduser(sys.argv[2])
    rest = sys.argv[3:]
    names, systems = (rest[:rest.index("--")], rest[rest.index("--") + 1:]) if "--" in rest else (rest, None)
    if cmd == "ours":
        for n in names:
            ours(out, n)
    elif cmd == "native":
        for n in names:
            native(out, n)
    elif cmd == "context":
        context(out, names, systems)
    elif cmd == "answer":
        answer(out, rest or None)
    elif cmd == "score":
        score(out)
