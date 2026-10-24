"""Coding recall v1: the systems, the reader and the judge
(docs/PREREG_CODING_V1.md). Runs on the Mac; everything it writes goes to
OUT (outside the repo). Resumable: each step skips what is already done.

    python run.py ours    dev OUT    # store each repo's history in its own memory
    python run.py rag     dev OUT    # plain retrieval index: transcript chunks
    python run.py native  dev OUT    # native memory with a Qwen writer (labelled)
    python run.py context dev OUT QUESTIONS [system ...]   # each system's context per question
                                     # (sourcedrecall-e8r4m2: a dev variant)
    python run.py answer  dev OUT [system ...]
    python run.py score   dev OUT [QUESTIONS]   # QUESTIONS: only these (a vetted subset)

Systems: sourcedrecall, native-qwen, both-qwen (native then ours), rag; native-sonnet
and both-sonnet read OUT/native_sonnet/, a memory folder kept by Sonnet subagents
(the native writer, same instructions), converted to the same JSON.
"""
import hashlib
import json
import os
import re
import sys

from common import HERE, append, chat, claim, condensed, fitted, jsonl, sessions

sys.path.insert(0, os.path.dirname(HERE))      # bench/, for claude_memory
OWNER = "Dev"
K_RECORDS, K_MESSAGES, K_RAG, K_EXCERPTS = 0, 0, 10, 10   # frozen from dev 2026-10-23


def _state(out, repo):
    # CODING_STORES: another set of stores (a dev variant built another way)
    return os.path.join(out, os.environ.get("CODING_STORES", "stores"), repo.replace("/", "__"))


def _use_store(out, repo):
    os.environ["SOURCEDRECALL_STATE"] = _state(out, repo)
    # paths.default_memory_dir keeps an RG_MEMORY_DIR already set, so without
    # this every repository after the first went into the first one's store
    os.environ["RG_MEMORY_DIR"] = os.path.join(_state(out, repo), "conversations")
    os.environ["SOURCEDRECALL_SCOPING"] = "0"     # one store per repo
    os.environ["SOURCEDRECALL_OWNER"] = OWNER
    os.environ.setdefault("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None, "episodes_index": None,
                      "msg_index": None, "notes_index": None})
    pm._ingest_state.update({"extractor": None, "owner": None})
    return pm


# ------------------------------------------------------------ sourcedrecall
def ours(split, out):
    from sourcedrecall import claude_hooks as H
    for repo, ss in sorted(sessions(split).items()):
        done_p = os.path.join(_state(out, repo), "bench_done.json")
        done = set(json.load(open(done_p))) if os.path.exists(done_p) else set()
        if len(done) == len(ss):
            continue
        _use_store(out, repo)
        for sid, ts, path in ss:
            if sid in done:
                continue
            r = H.ingest_session(path, sid, OWNER, cwd=None)
            done.add(sid)
            os.makedirs(os.path.dirname(done_p), exist_ok=True)
            json.dump(sorted(done), open(done_p, "w"))
            print(repo, sid[:8], {k: r.get(k) for k in ("facts", "coding_records", "coding_error")}, flush=True)


def _variant(system):
    """"sourcedrecall-e8r4m2": 8 excerpts, 4 records, 2 of the user's
    messages (dev tuning); plain "sourcedrecall" is the default."""
    m = re.fullmatch(r"sourcedrecall-e(\d+)r(\d+)m(\d+)(?:-\w+)?", system)
    return tuple(int(x) for x in m.groups()) if m else (K_EXCERPTS, K_RECORDS, K_MESSAGES)


def ours_context(out, repo, q, system="sourcedrecall"):
    pm = _use_store(out, repo) if os.environ.get("SOURCEDRECALL_STATE") != _state(out, repo) else \
        __import__("sourcedrecall.profile_memory", fromlist=["x"])
    ke, kr, km = _variant(system)
    recs = pm.profile_history(q, k=ke, all_projects=True, records=kr)["results"] if ke or kr else []
    if not kr:
        recs = [r for r in recs if r["kind"] == "excerpt"]
    msgs = pm._messages_for(q, k=km) if km else []
    lines = [f"[{r['date']}] {r['kind']}: " + " | ".join(r["text"].splitlines()) for r in recs]
    lines += [f"[{m.get('date')}] the user said: {m['text'][:600]}" for m in msgs]
    return lines


# ------------------------------------------------------------ plain retrieval
def _chunks(text, size=1200):
    out, cur = [], ""
    for line in text.splitlines():
        if cur and len(cur) + len(line) > size:
            out.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur)
    return out


def rag(split, out):
    for repo, ss in sorted(sessions(split).items()):
        p = os.path.join(out, "rag", repo.replace("/", "__") + ".jsonl")
        if os.path.exists(p):
            continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        rows = []
        for sid, ts, path in ss:
            for c in _chunks(condensed(path)):
                rows.append({"session": sid, "date": ts[:10], "text": c})
        with open(p + ".tmp", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(p + ".tmp", p)
        print(repo, len(rows), "chunks", flush=True)


_RAG = {}


def rag_context(out, repo, q):
    import retrieve_v3 as RV3
    if repo not in _RAG:
        rows = jsonl(os.path.join(out, "rag", repo.replace("/", "__") + ".jsonl"))
        docs = [{"attr": "", "value": r["text"], "text": r["text"], "date": r["date"]} for r in rows]
        _RAG.clear()
        _RAG[repo] = RV3.IndexV3(None, facts=docs)
    hits = RV3.retrieve_facts_v3(_RAG[repo], q, k=60, dense_k=30, top_n=K_RAG)
    return [f"[{h['date']}] " + " ".join(h["text"].split()) for h in hits]


# ------------------------------------------------- native memory, Qwen writer
NATIVE_CHARS = 26000     # the transcript share of Qwen's 16k-token context


def native(split, out):
    import claude_memory as CM
    for repo, ss in sorted(sessions(split).items()):
        p = os.path.join(out, "native", repo.replace("/", "__") + ".json")
        st = json.load(open(p)) if os.path.exists(p) else {"done": 0, "files": {}}
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if st["done"] >= len(ss) or not claim(p):
            continue
        try:
            _native_repo(CM, repo, ss, p, st)
        finally:
            os.remove(p + ".lock")


def _native_repo(CM, repo, ss, p, st):
    for i in range(st["done"], len(ss)):
        sid, ts, path = ss[i]
        build = lambda tr, st=st, ts=ts: (CM.INSTRUCTIONS  # noqa: E731
                  + '\n\nReply with JSON only: {"changes": [{"action": "write" or "delete", '
                    '"file": "name.md", "content": "..."}]}'
                  + f"\n\nThe conversation's date: {ts[:10]}.\n\nThe memory folder:\n\n"
                  + CM._folder(st["files"])
                  + f"\n\nThe conversation that just ended (a coding session in {repo}, condensed: "
                    "USER, ASSISTANT, and TOOL calls with the start of their results):\n\n<transcript>\n"
                  + tr + "\n</transcript> /no_think")
        changes = None
        for _ in range(2):
            reply, _n = fitted(build, path, sizes=(NATIVE_CHARS, 18000, 10000), max_tokens=2500)
            m = re.search(r"\{.*\}", reply or "", re.S)
            try:
                changes = json.loads(m.group(0))["changes"] if m else None
                break
            except (ValueError, KeyError, TypeError):
                changes = None
        files = dict(st["files"])
        for ch in changes or []:
            if not isinstance(ch, dict) or not ch.get("file"):
                continue
            n = CM._safe(ch["file"])
            if ch.get("action") == "delete":
                files.pop(n, None)
            elif ch.get("content"):
                files[n] = str(ch["content"]).strip()
        st = {"done": i + 1, "files": files, "unreadable": st.get("unreadable", 0) + (changes is None)}
        json.dump(st, open(p + ".tmp", "w"))
        os.replace(p + ".tmp", p)
        print(repo, i + 1, len(ss), len(files), "files", "" if changes is not None else "UNREADABLE", flush=True)


def native_context(out, repo, q, writer="native"):
    import retrieve  # noqa: F401  experiments/p2's, before claude_memory puts bench/locomo first
    import claude_memory as CM
    st = json.load(open(os.path.join(out, writer, repo.replace("/", "__") + ".json")))
    return CM.lines(st["files"])


# ---------------------------------------------------------- context, answers
SYSTEMS = ["sourcedrecall", "native-qwen", "both-qwen", "rag"]


def _qid(q):
    return f"{q['repo']}#{q['session'][:8]}#{q['type']}#" + \
        hashlib.sha1(q["question"].encode()).hexdigest()[:6]


def context(split, out, questions, systems=None):
    qs = jsonl(questions)
    path = os.path.join(out, "context.jsonl")
    have = {(r["system"], r["qid"]) for r in jsonl(path)}
    for i, q in enumerate(sorted(qs, key=lambda r: r["repo"])):
        qid = q["qid"] = _qid(q)
        got = {}
        for s in systems or SYSTEMS:
            if (s, qid) in have:
                continue
            if s.startswith("sourcedrecall"):
                got[s] = ours_context(out, q["repo"], q["question"], s)
            elif s == "rag":
                got[s] = rag_context(out, q["repo"], q["question"])
            elif s == "native-qwen":
                got[s] = native_context(out, q["repo"], q["question"])
            elif s == "both-qwen":
                got[s] = (native_context(out, q["repo"], q["question"])
                          + ours_context(out, q["repo"], q["question"]))
            elif s == "native-sonnet":
                got[s] = native_context(out, q["repo"], q["question"], "native_sonnet")
            elif s == "both-sonnet":
                got[s] = (native_context(out, q["repo"], q["question"], "native_sonnet")
                          + ours_context(out, q["repo"], q["question"]))
        for s, lines in got.items():
            append(path, dict(q, system=s, lines=lines, ctx_tokens=len("\n".join(lines)) // 4))
        print(i, qid, {s: len(v) for s, v in got.items()}, flush=True)


READ = """You are a coding assistant with a memory of earlier sessions on this project ({repo}). Answer the developer's question in one or two sentences, using only the memory below. If the memory does not answer it, say you don't know.

MEMORY:
{memory}

QUESTION: {q} /no_think"""


def answer(split, out, systems=None):
    from make_questions import judge
    path = os.path.join(out, os.environ.get("CODING_ANSWERS", "answers.jsonl"))
    have = {(r["system"], r["qid"]) for r in jsonl(path)}
    from common import READER, READER_MODEL
    for r in jsonl(os.path.join(out, "context.jsonl")):
        if (systems and r["system"] not in systems) or (r["system"], r["qid"]) in have:
            continue
        mem = "\n".join(f"- {l}" for l in r["lines"]) or "(nothing)"
        a = chat(READ.format(repo=r["repo"], memory=mem, q=r["question"]), max_tokens=160,
                 base=READER, model=READER_MODEL)
        ok = judge(r["question"], r["answer"], a)
        append(path, {"qid": r["qid"], "system": r["system"], "type": r["type"], "pred": a,
                      "correct": ok, "ctx_tokens": r["ctx_tokens"]})
        print(r["system"], r["qid"], ok, flush=True)


def score(split, out, questions=None):
    """questions: score only the questions in this file (a vetted subset)."""
    from math import comb
    rows = jsonl(os.path.join(out, os.environ.get("CODING_ANSWERS", "answers.jsonl")))
    if questions:
        keep = {_qid(q) for q in jsonl(questions)}
        rows = [r for r in rows if r["qid"] in keep]
    by = {}
    for r in rows:
        by.setdefault(r["system"], {})[r["qid"]] = r
    common = set.intersection(*(set(v) for v in by.values())) if by else set()
    systems = [s for s in SYSTEMS if s in by] + sorted(s for s in by if s not in SYSTEMS)
    print(f"questions answered by every system: {len(common)}\n")
    print("| | n | " + " | ".join(systems) + " |")
    print("|---|---|" + "---|" * len(systems))
    types = sorted({by[systems[0]][q]["type"] for q in common})
    for t in types + ["all"]:
        ids = [q for q in common if t == "all" or by[systems[0]][q]["type"] == t]
        cells = [f"{sum(by[s][q]['correct'] for q in ids)}/{len(ids)}" for s in systems]
        print(f"| {t} | {len(ids)} | " + " | ".join(cells) + " |")
    print("| context tokens (mean) | | " + " | ".join(
        f"{sum(by[s][q]['ctx_tokens'] for q in common) / max(1, len(common)):.0f}" for s in systems) + " |")

    def p(a, b):
        x = sum(by[a][q]["correct"] and not by[b][q]["correct"] for q in common)
        y = sum(by[b][q]["correct"] and not by[a][q]["correct"] for q in common)
        n = x + y
        return x, y, (min(1.0, 2 * sum(comb(n, i) for i in range(min(x, y) + 1)) / 2 ** n) if n else 1.0)
    for a, b in (("both-qwen", "native-qwen"), ("sourcedrecall", "native-qwen"), ("sourcedrecall", "rag"),
                 ("both-sonnet", "native-sonnet"), ("sourcedrecall", "native-sonnet")):
        if a in by and b in by:
            x, y, pv = p(a, b)
            print(f"\n{a} vs {b}: {x} to {y}, McNemar p={pv:.3g}")


if __name__ == "__main__":
    cmd, split, out = sys.argv[1], sys.argv[2], os.path.expanduser(sys.argv[3])
    os.makedirs(out, exist_ok=True)
    if cmd == "context":
        context(split, out, sys.argv[4], sys.argv[5:] or None)
    elif cmd == "score":
        score(split, out, sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "answer":
        answer(split, out, sys.argv[4:] or None)
    else:
        {"ours": ours, "rag": rag, "native": native}[cmd](split, out)
