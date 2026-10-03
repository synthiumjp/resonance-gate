"""The ANSWER view (2026-10-03): what a user actually sees is the agent's
answer, not a list of memory lines. A local reader model answers each probe
from what the system returned -- the same instruction for every system --
and score.py judges that answer like a memory line ("does it state the old
state as currently true?"). sourcedrecall's lines go in with the product's
own rules header, as an agent receives them; RAG's lines carry their dates.

    FM_RESULTS=... FM_CASES=... FM_READER_OPENAI=http://127.0.0.1:8090/v1 \\
    FM_READER_MODEL=<model> python answer.py sourcedrecall rag

Writes results/answers_<system>.jsonl (one line per scenario, a list of
answers in probe order); a rerun skips scenarios already answered with the
same prompt. Pure standard library.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.environ.get("FM_RESULTS") or os.path.join(HERE, "results")
CASES = os.environ.get("FM_CASES") or os.path.join(HERE, "cases.jsonl")
READER = os.environ.get("FM_READER_OPENAI") or os.environ.get("FM_JUDGE_OPENAI")
MODEL = os.environ.get("FM_READER_MODEL") or os.environ.get("FM_JUDGE_MODEL")

PROMPT = """You are an assistant with a memory of earlier conversations with the user. Today is {today}. Answer the user's question in one or two sentences, using only the memory below. If the memory does not answer it, say you don't know.

{rules}MEMORY:
{memory}

QUESTION: {q} /no_think"""


def _rules():
    try:
        src = open(os.path.join(HERE, "..", "..", "experiments", "p2",
                                "memory_api.py")).read()
        m = re.search(r"^_RULES = \((.*?)\)\n", src, re.S | re.M)
        return eval("(" + m.group(1) + ")") + "\n\n" if m else ""
    except Exception:
        return ""


def _call(prompt):
    body = {"model": MODEL, "temperature": 0, "max_tokens": 120, "seed": 0,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(READER.rstrip("/") + "/chat/completions",
                                 json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=600).read())
    raw = out["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()


def main(systems):
    if not READER or not MODEL:
        sys.exit("set FM_READER_OPENAI and FM_READER_MODEL (or the FM_JUDGE_ ones)")
    cases = {c["id"]: c for c in map(json.loads, open(CASES))}
    rules = _rules()
    for s in systems:
        out_path = os.path.join(RESULTS, f"answers_{s}.jsonl")
        done = {}
        if os.path.exists(out_path):
            for l in open(out_path):
                r = json.loads(l)
                done[r["id"]] = r
        raw = [json.loads(l) for l in open(os.path.join(RESULTS, f"raw_{s}.jsonl"))]
        fresh = {}
        for r in raw:
            c = cases[r["id"]]
            today = max(cv["date"] for cv in c["conversations"])
            prompts = []
            for p in r.get("probes") or []:
                lines = (p.get("views") or {}).get("context") if s == "sourcedrecall" \
                    else p.get("lines")
                mem = "\n".join(f"- {l}" for l in (lines or [])) or "(nothing)"
                prompts.append(PROMPT.format(today=today, q=p["q"], memory=mem,
                                             rules=rules if s == "sourcedrecall" else ""))
            key = hashlib.sha1(json.dumps([MODEL, prompts]).encode()).hexdigest()
            if r["id"] in done and done[r["id"]].get("key") == key:
                fresh[r["id"]] = done[r["id"]]
                continue
            fresh[r["id"]] = {"id": r["id"], "key": key, "model": MODEL,
                              "answers": [_call(pr) for pr in prompts]}
            print(s, r["id"], "answered", flush=True)
            with open(out_path, "w") as f:
                for v in fresh.values():
                    f.write(json.dumps(v, ensure_ascii=False) + "\n")
        with open(out_path, "w") as f:
            for v in fresh.values():
                f.write(json.dumps(v, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(sys.argv[1:] or ["sourcedrecall", "rag"])
