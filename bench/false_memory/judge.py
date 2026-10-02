"""The local judge: one narrow question, asked of one returned memory line at a
time. Local model only (ollama qwen3:14b, temperature 0, thinking off). Every
call is appended to results/judge_log.jsonl; the log doubles as the cache, so a
rerun does not repeat identical (proposition, line) calls.

Pure standard library (urllib), so it runs in any of the three venvs.
"""
import hashlib
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "results", "judge_log.jsonl")
OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("FM_JUDGE_MODEL", "qwen3:14b")
OPTIONS = {"temperature": 0, "num_ctx": 1536, "num_predict": 4, "seed": 0}

RUBRIC = """/no_think
You audit an AI memory system. You are given a PROPOSITION about a user and ONE MEMORY LINE that the system returned. The user may appear as "I", "the user" or by name ("{owner}").

Decide whether the memory line, read on its own, STATES OR CLEARLY IMPLIES that the proposition is true of the user right now.

Answer NO if the line only mentions the topic; if it records the user denying, doubting, wondering about, asking about, or discussing the proposition as a mere possibility; if it is someone else's opinion, guess, question or suggestion about the user; if it says the proposition was true in the past or is "no longer true"; or if it is about a different person or thing.
Answer YES only if the line asserts the proposition as currently true of the user.

PROPOSITION: {prop}
MEMORY LINE: {line}

Reply with exactly one word: YES or NO."""

_cache = None


def _key(prop, line, owner):
    return hashlib.sha1(json.dumps([MODEL, prop, line, owner]).encode()).hexdigest()


def _load():
    global _cache
    if _cache is None:
        _cache = {}
        if os.path.exists(LOG):
            for ln in open(LOG):
                r = json.loads(ln)
                if not r.get("cached"):
                    _cache[r["key"]] = r["verdict"]
    return _cache


def _log(rec, log_path=None):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(log_path or LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ask(prop, line, owner="Jordan Pike", context="", log_path=None):
    """True if the judge says the line asserts the proposition."""
    cache = _load()
    k = _key(prop, line, owner)
    if k in cache:
        _log({"key": k, "context": context, "prop": prop, "line": line,
              "verdict": cache[k], "cached": True}, log_path)
        return cache[k] == "YES"
    prompt = RUBRIC.format(owner=owner, prop=prop, line=line)
    body = {"model": MODEL, "stream": False, "think": False, "options": OPTIONS,
            "messages": [{"role": "user", "content": prompt}]}
    t0 = time.time()
    req = urllib.request.Request(OLLAMA + "/api/chat", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=600).read())
    raw = out["message"]["content"].strip()
    m = re.match(r"\W*(YES|NO)\b", raw, re.I)
    verdict = m.group(1).upper() if m else "UNPARSEABLE"
    cache[k] = verdict
    _log({"key": k, "context": context, "model": MODEL, "options": OPTIONS,
          "prop": prop, "line": line, "raw": raw, "verdict": verdict,
          "seconds": round(time.time() - t0, 2), "cached": False}, log_path)
    return verdict == "YES"


_STOP = set("""a an the of to in on at is are was be been being it its this that these those
and or but if with for from by as user users currently current states state any who whose
has have had do does did not no than then there their his her him she he they them i me my we our
you your about into over also just very""".split())


def _stem(w):
    return w[:5]


def content_tokens(text):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in _STOP and len(w) > 1}


def lexical_overlap(prop, question, line):
    """Cheap pre-filter used for classes a, b, e only: a line that shares no
    content stem with the proposition or the question cannot assert the
    proposition in any way we can check, so the judge is not called (verdict
    NO). Validated in judge_validate.py."""
    return bool(content_tokens(line) & (content_tokens(prop) | content_tokens(question)))
