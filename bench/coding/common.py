"""Coding recall v1 (docs/PREREG_CODING_V1.md): shared pieces. Runs on the
Mac. The data (SWE-chat v2 transcripts) stays in CODING_DATA, outside the
repo; nothing here writes into the repo.

    CODING_DATA=~/jpwork/coding_data/swechat
    CODING_LLM=http://127.0.0.1:8091/v1   (Qwen3-14B, llama_cpp.server)
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [os.path.join(ROOT, "server"), ROOT, os.path.join(ROOT, "experiments", "p2")]

DATA = os.path.expanduser(os.environ.get("CODING_DATA", "~/jpwork/coding_data/swechat"))
LLM = os.environ.get("CODING_LLM", "http://127.0.0.1:8091/v1")
MODEL = os.environ.get("CODING_LLM_MODEL", "qwen3-14b-a8cc1361.gguf")
# the second reader (Phi-4): reads the memory; the judge stays on CODING_LLM
READER = os.environ.get("CODING_READER", LLM)
READER_MODEL = os.environ.get("CODING_READER_MODEL", MODEL)
HISTORY = 40          # sessions of history per repository, at most


def _jp_sessions():
    """JP's own Claude Code sessions (copied to CODING_JP, private, never
    committed): one project per folder, sessions by their first timestamp."""
    import glob
    root = os.path.expanduser(os.environ.get("CODING_JP", "~/jpwork/coding_data/jp_sessions"))
    out = {}
    for p in glob.glob(os.path.join(root, "*", "*.jsonl")):
        ts = None
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"timestamp"' in line:
                    try:
                        ts = json.loads(line).get("timestamp")
                    except ValueError:
                        continue
                    if ts:
                        break
        if ts:
            proj = os.path.basename(os.path.dirname(p))
            out.setdefault(proj, []).append((os.path.splitext(os.path.basename(p))[0], ts, p))
    return {k: sorted(v, key=lambda x: x[1])[:HISTORY] for k, v in out.items()}


def sessions(split):
    """-> {repo: [(session_id, created_at, transcript path)]} in time order,
    only those whose transcript was fetched, the first HISTORY."""
    if split == "jp":
        return _jp_sessions()
    out = {}
    with open(os.path.join(DATA, f"{split}_sessions.csv")) as fh:
        for r in csv.DictReader(fh):
            p = os.path.join(DATA, r["transcript_path"])
            if os.path.getsize(p) if os.path.exists(p) else 0:
                out.setdefault(r["repo_id"], []).append((r["session_id"], r["created_at"], p))
    return {k: sorted(v, key=lambda x: x[1])[:HISTORY] for k, v in out.items()}


def condensed(path, max_chars=36000):
    """A session as lines: what the user typed, the assistant's text, each
    tool call with its command or file and the start of its result. The
    question writer, the native-memory writer and plain retrieval all read
    this same view."""
    from sourcedrecall import claude_hooks as H
    from sourcedrecall import coding as C
    lines = []
    for e in C.events(path, H._classify):
        if "say" in e:
            t = " ".join(e["text"].split())
            lines.append(f"{'USER' if e['say'] == 'user' else 'ASSISTANT'}: {t[:800]}")
            continue
        inp = e["input"] or {}
        what = (inp.get("command") or inp.get("file_path") or inp.get("notebook_path")
                or inp.get("pattern") or inp.get("url") or inp.get("description") or "")
        what = " ".join(str(what).split())[:300]
        res = " ".join(str(e["output"] or "").split())[:300]
        lines.append(f"TOOL {e['tool']}: {what}" + (f" -> {'[failed] ' if e['error'] else ''}{res}"
                                                   if e["tool"] in ("Bash",) or e["error"] else ""))
    text = "\n".join(lines)
    if len(text) > max_chars:   # the start and the end of a long session
        text = text[:max_chars * 2 // 3] + "\n[...]\n" + text[-max_chars // 3:]
    return text


def claim(p):
    """One process per Qwen server, sharing the repositories: a repository
    is taken by whoever creates its lock first (p + ".lock")."""
    try:
        os.close(os.open(p + ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return True
    except FileExistsError:
        return False


class TooLong(Exception):
    pass


def fitted(build, path, sizes=(30000, 20000, 12000), **kw):
    """chat(build(condensed transcript)), shortening the transcript until the
    prompt fits Qwen's 16k-token context (code is dense in tokens)."""
    for n in sizes:
        try:
            return chat(build(condensed(path, max_chars=n)), **kw), n
        except TooLong:
            continue
    return None, None


def chat(prompt, max_tokens=1200, temperature=0.0, json_mode=False, timeout=900,
         base=None, model=None):
    body = {"model": model or MODEL, "temperature": temperature, "max_tokens": max_tokens, "seed": 0,
            "messages": [{"role": "user", "content": prompt}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request((base or LLM).rstrip("/") + "/chat/completions",
                                 json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 400:            # the prompt does not fit the context
                raise TooLong() from e
            if attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    raw = out["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()


def jsonl(path):
    try:
        with open(path) as fh:
            return [json.loads(l) for l in fh if l.strip()]
    except OSError:
        return []


def append(path, row):
    with open(path, "a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
