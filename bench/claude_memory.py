"""Claude Code's own memory, simulated (2026-10-21): the comparison every
Claude Code user will ask for.

Claude Code keeps a memory folder per project: one fact per file (user,
feedback, project and reference notes) and an index, MEMORY.md, that is
loaded at the start of each session. Claude writes it, during the session,
when it judges something worth keeping. This stands in for it: after each
session of a benchmark conversation, Claude (Sonnet 5.5) gets the memory
folder as it stands, the session's transcript and instructions written after
Claude Code's own memory guidance, and returns the files to write or delete.

It is generous to Claude Code's memory in two ways: the writer sees the
whole session with nothing else to do (in Claude Code, memory is a side task
of the work), and the reader gets every file, not only the index (in Claude
Code the index is loaded and files are read when the model asks for them).

Runs on the machine with the API key (~/.anthropic_key, via
claude_batch.client), as bench/claude_runs.sh does. Writes the same files
the other systems' runs write, so answer.py, answer_claude.py and score.py
read them unchanged:

    python bench/claude_memory.py locomo OUT_DIR            # ctx_claude-memory.jsonl
    python bench/claude_memory.py fm CASES.jsonl OUT_DIR    # raw_claude-memory.jsonl

Resumable: each conversation's memory, after each session, is kept in
OUT_DIR/state/. CLAUDE_MEMORY_CAP (dollars, default 40) stops the run
before it spends more.
"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "locomo"))

SYSTEM_ID = "claude-memory"
MODEL = os.environ.get("CLAUDE_MEMORY_MODEL", "claude-sonnet-5-5")
EFFORT = os.environ.get("CLAUDE_MEMORY_EFFORT", "medium")
PRICE = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0),
         "claude-haiku-5-5": (0.1, 0.5)}[MODEL]
CAP = float(os.environ.get("CLAUDE_MEMORY_CAP", "40"))

INSTRUCTIONS = """You keep a persistent, file-based memory for an AI assistant, so that future conversations can build on what the user has told it. A conversation has just ended. You are given the memory folder as it stands and the transcript of that conversation. Update the memory.

Each memory is one file holding one fact, with frontmatter:

---
name: <short-kebab-case-slug>
description: <one-line summary, used to decide relevance later>
type: user | feedback | project | reference
---
<the fact>

user: who the user is (life, work, family, preferences, plans). feedback: guidance the user gave on how the assistant should work. project: ongoing work, goals or constraints. reference: pointers to external resources.

MEMORY.md is the index loaded at the start of every conversation: one line per memory file, `- [Title](file.md) - hook`, no frontmatter, never the memory's content itself. Keep it in step with the files.

Rules:
- Before saving, check for an existing file that already covers it; update that file rather than creating a duplicate.
- When something the user says replaces an earlier fact, update or delete the old memory.
- Delete memories that turn out to be wrong.
- Convert relative dates ("last week", "tomorrow") to absolute dates, using the conversation's date.
- Do not save what only matters to this conversation.
- Save what would help in a future conversation with this user.

Return only the changes: files to write (the full new content) and files to delete. Return no changes if nothing is worth keeping."""

SCHEMA = {
    "type": "object",
    "properties": {"changes": {"type": "array", "items": {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": ["write", "delete"]},
                       "file": {"type": "string"},
                       "content": {"type": "string"}},
        "required": ["action", "file", "content"],
        "additionalProperties": False}}},
    "required": ["changes"],
    "additionalProperties": False,
}

_lock = threading.Lock()
_spent = {"in": 0, "out": 0, "cached": 0, "calls": 0}


def spent():
    return (_spent["in"] * PRICE[0] + _spent["cached"] * PRICE[0] * 0.1
            + _spent["out"] * PRICE[1]) / 1e6


def _safe(name):
    name = os.path.basename(name.strip()) or "note.md"
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", name)
    return name if name.endswith(".md") else name + ".md"


def _folder(files):
    if not files:
        return "(the memory folder is empty)"
    return "\n\n".join(f'<file name="{n}">\n{files[n]}\n</file>'
                       for n in sorted(files, key=lambda n: (n != "MEMORY.md", n)))


def update(c, files, transcript, date):
    """One end-of-session update -> new files dict."""
    prompt = (f"The conversation's date: {date or 'unknown'}.\n\n"
              f"The memory folder:\n\n{_folder(files)}\n\n"
              f"The conversation that just ended:\n\n<transcript>\n{transcript}\n</transcript>")
    for attempt in range(4):
        r = c.messages.create(
            model=MODEL, max_tokens=16000,
            system=[{"type": "text", "text": INSTRUCTIONS, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}})
        with _lock:
            u = r.usage
            _spent["in"] += u.input_tokens + (u.cache_creation_input_tokens or 0) * 1.25
            _spent["cached"] += u.cache_read_input_tokens or 0
            _spent["out"] += u.output_tokens
            _spent["calls"] += 1
        if r.stop_reason in ("refusal", "max_tokens"):
            print(f"  {r.stop_reason} (try {attempt + 1})", flush=True)
            continue
        try:
            changes = json.loads(next(b.text for b in r.content if b.type == "text"))["changes"]
            break
        except (StopIteration, ValueError, KeyError):
            print(f"  unreadable reply (try {attempt + 1})", flush=True)
    else:
        raise RuntimeError("no usable reply after four tries")
    files = dict(files)
    for ch in changes:
        n = _safe(ch["file"])
        if ch["action"] == "delete":
            files.pop(n, None)
        else:
            files[n] = ch["content"].strip()
    return files


def lines(files):
    """What the reader gets: the index first, then every memory file, one
    line each (the reader sees all of it; see the module note)."""
    out = []
    idx = files.get("MEMORY.md")
    if idx:
        out.append("MEMORY.md: " + " | ".join(l.strip() for l in idx.splitlines() if l.strip()))
    for n in sorted(files):
        if n != "MEMORY.md":
            out.append(f"{n}: " + " ".join(files[n].split()))
    return out


def run_stream(c, state_path, sessions):
    """sessions: [(date, transcript)] in order; memory after each one kept
    in state_path, so a rerun continues where it stopped."""
    st = json.load(open(state_path)) if os.path.exists(state_path) else {"done": 0, "files": {}}
    t0 = time.time()
    for i in range(st["done"], len(sessions)):
        if spent() > CAP:
            raise RuntimeError(f"spending cap ${CAP} reached")
        date, tr = sessions[i]
        st["files"] = update(c, st["files"], tr, date)
        st["done"] = i + 1
        st["seconds"] = st.get("seconds", 0) + time.time() - t0
        t0 = time.time()
        tmp = state_path + ".tmp"
        json.dump(st, open(tmp, "w"))
        os.replace(tmp, state_path)
    return st


def _pool(jobs, workers=8):
    errors = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(f): k for k, f in jobs}
        for fu in futs:
            try:
                fu.result()
            except Exception as e:   # one conversation failing does not stop the rest
                errors.append(f"{futs[fu]}: {type(e).__name__}: {e}")
    print(f"{_spent['calls']} calls, ${spent():.2f} so far", flush=True)
    for e in errors:
        print("FAILED", e, flush=True)
    return errors


# ------------------------------------------------------------- LoCoMo
def locomo(out, convs="2-9"):
    import common as C
    from claude_batch import client
    os.makedirs(os.path.join(out, "state"), exist_ok=True)
    c = client()
    data = C.load(C.parse_convs(convs))
    streams = {}
    for idx, conv in data:
        A, B = conv["conversation"]["speaker_a"], conv["conversation"]["speaker_b"]
        for owner, other in ((A, B), (B, A)):
            ss = []
            for sn, iso, raw, turns in C.sessions(conv):
                tr = "\n".join(f"{t['speaker']}{' (the user)' if t['speaker'] == owner else ''}: {t['text']}"
                               for t in turns)
                ss.append((raw or iso, f"[{raw}] {owner} (the user) is chatting with {other}.\n\n{tr}"))
            streams[(idx, owner)] = ss
    jobs = [(k, (lambda k=k: run_stream(c, os.path.join(out, "state", f"locomo_{k[0]}_{k[1]}.json"),
                                        streams[k]))) for k in streams]
    errors = _pool(jobs)
    if errors:
        sys.exit(1)
    ctxf = os.path.join(out, f"ctx_{SYSTEM_ID}.jsonl")
    ingf = os.path.join(out, f"ingest_{SYSTEM_ID}.jsonl")
    for p in (ctxf, ingf):
        if os.path.exists(p):
            os.unlink(p)
    for idx, conv in data:
        A, B = conv["conversation"]["speaker_a"], conv["conversation"]["speaker_b"]
        sec = {}
        for owner in (A, B):
            st = json.load(open(os.path.join(out, "state", f"locomo_{idx}_{owner}.json")))
            sec[f"Memories of {owner}"] = lines(st["files"])
            C.jsonl_append(ingf, {"speaker": owner, "messages": sum(len(t) for *_x, t in C.sessions(conv)),
                                  "model_calls": st["done"], "seconds": st.get("seconds", 0),
                                  "conv": idx, "system": SYSTEM_ID})
        ctx = "\n\n".join(k + ":\n" + ("\n".join("- " + l for l in v) if v else "- (nothing retrieved)")
                          for k, v in sec.items())
        for q in C.questions(idx, conv):
            C.jsonl_append(ctxf, dict(q, system=SYSTEM_ID, context=ctx, latency=0.0,
                                      ctx_tokens=len(ctx) // 4))
    print(f"wrote {ctxf}; ${spent():.2f} in all", flush=True)


# ------------------------------------------------- pasted-text sets
def fm(cases_path, out):
    from claude_batch import client
    os.makedirs(os.path.join(out, "state"), exist_ok=True)
    c = client()
    cases = [json.loads(l) for l in open(cases_path) if l.strip()]
    streams = {}
    for case in cases:
        ss = []
        for cv in case["conversations"]:
            tr = "\n\n".join(f"{'User' if t['role'] == 'user' else 'Assistant'}: {t['content']}"
                             for t in cv["turns"])
            ss.append((cv["date"], f"[{cv['date']}] The user is {case['owner']}.\n\n{tr}"))
        streams[case["id"]] = ss
    jobs = [(k, (lambda k=k: run_stream(c, os.path.join(out, "state", f"{k}.json"), streams[k])))
            for k in streams]
    errors = _pool(jobs)
    rawf = os.path.join(out, f"raw_{SYSTEM_ID}.jsonl")
    with open(rawf, "w") as f:
        for case in cases:
            p = os.path.join(out, "state", f"{case['id']}.json")
            if not os.path.exists(p):
                continue
            st = json.load(open(p))
            if st["done"] < len(case["conversations"]):
                continue
            ls = lines(st["files"])
            f.write(json.dumps({
                "id": case["id"], "system": SYSTEM_ID, "model": MODEL,
                "ingest": {"messages": sum(len(cv["turns"]) for cv in case["conversations"]),
                           "model_calls": st["done"], "seconds": st.get("seconds", 0)},
                "probes": [{"q": pr["q"], "lines": ls, "views": {}} for pr in case["probes"]],
            }, ensure_ascii=False) + "\n")
    print(f"wrote {rawf}; ${spent():.2f} in all", flush=True)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1] == "locomo":
        locomo(sys.argv[2], *(sys.argv[3:4]))
    elif sys.argv[1] == "fm":
        fm(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
