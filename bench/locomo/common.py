"""Shared pieces for the LoCoMo harness: data, splits, dates, the local LLM
client, and the reader and judge prompts. Standard library only, so it runs in
every venv."""
import datetime
import json
import os
import re
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("LOCOMO_DATA", os.path.expanduser("~/rg_private/locomo/locomo10.json"))
RESULTS = os.environ.get("LOCOMO_RESULTS", os.path.join(HERE, "results"))
# OpenAI-compatible chat endpoint used for the reader and the judge. Dev: Ollama.
# Test run: llama_cpp.server on the Mac Studio, through an ssh tunnel.
LLM_BASE = os.environ.get("LOCOMO_LLM_BASE", "http://127.0.0.1:11434")
LLM_MODEL = os.environ.get("LOCOMO_LLM_MODEL", "qwen3:14b")
TOP_K = 10
CATS = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop"}


def load(convs):
    d = json.load(open(DATA))
    return [(i, d[i]) for i in convs]


def parse_convs(spec):
    out = []
    for p in spec.split(","):
        if "-" in p:
            a, b = p.split("-")
            out += list(range(int(a), int(b) + 1))
        elif p:
            out.append(int(p))
    return out


def sessions(conv):
    """[(n, iso_date, human_date, turns)] in session order. Turns keep the
    speaker name, text only (image captions are not used)."""
    c = conv["conversation"]
    n = 1
    out = []
    while f"session_{n}" in c:
        raw = c.get(f"session_{n}_date_time", "")
        try:
            iso = datetime.datetime.strptime(raw, "%I:%M %p on %d %B, %Y").strftime("%Y-%m-%d")
        except ValueError:
            iso = None
        out.append((n, iso, raw, c[f"session_{n}"]))
        n += 1
    return out


def questions(idx, conv, cats=(1, 2, 3, 4), limit=None):
    qs = []
    for j, q in enumerate(conv["qa"]):
        if q["category"] in cats:
            qs.append({"qid": f"{idx}:{j}", "conv": idx, "question": q["question"],
                       "answer": str(q.get("answer")), "category": q["category"]})
    return qs[:limit] if limit else qs


def sample(qs, n):
    """Deterministic, category-stratified-ish sample: every k-th question."""
    if n >= len(qs):
        return qs
    step = len(qs) / n
    return [qs[int(i * step)] for i in range(n)]


def jsonl_read(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def jsonl_append(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def llm(prompt, max_tokens=200, retries=8):
    """One chat call, temperature 0, qwen3 thinking off, retried on network
    errors (the Mac is reached through an ssh tunnel). Ollama: native
    /api/chat with think=false (its /v1 route ignores /no_think). llama_cpp:
    OpenAI route with the qwen3 /no_think switch appended to the prompt."""
    native = LLM_BASE.rstrip("/").endswith("11434")
    if native:
        url = LLM_BASE.rstrip("/") + "/api/chat"
        body = {"model": LLM_MODEL, "stream": False, "think": False,
                "options": {"temperature": 0, "seed": 0, "num_ctx": 12288, "num_predict": max_tokens},
                "messages": [{"role": "user", "content": prompt}]}
    else:
        url = LLM_BASE.rstrip("/") + "/chat/completions"
        body = {"model": LLM_MODEL, "temperature": 0, "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt + " /no_think"}]}
    data = json.dumps(body).encode()
    for k in range(retries):
        try:
            req = urllib.request.Request(url, data, {"Content-Type": "application/json",
                                                     "Authorization": "Bearer none"})
            r = json.load(urllib.request.urlopen(req, timeout=900))
            t = (r["message"]["content"] if native else r["choices"][0]["message"]["content"]) or ""
            return re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
        except Exception:   # noqa: BLE001
            if k == retries - 1:
                raise
            time.sleep(min(60, 5 * (k + 1)))


READER = """You are an intelligent memory assistant. You answer a question about one of two people, using only the memories retrieved from their conversations.

Instructions:
1. Read the memories of both speakers carefully. Each memory may carry the speaker's own words and the date of the conversation it came from.
2. Answer the question using only the information in the memories. If the question asks for a list, give every item you can find.
3. If the question is about time, use the memory dates to work out the answer. A phrase such as "yesterday" or "last week" is relative to the date of the conversation it came from, so convert it to a concrete date, month or year.
4. If the memories do not contain the answer, make your best guess from what is there.
5. Answer in one short sentence or phrase, with no explanation.

Memories:
{context}

Question: {question}
Answer:"""

JUDGE = """Your task is to label an answer to a question as 'CORRECT' or 'WRONG'. You will be given the following data:
    (1) a question (posed by one user to another user),
    (2) a 'gold' (ground truth) answer,
    (3) a generated answer
which you will score as CORRECT/WRONG.

The point of the question is to ask about something one user should know about the other user based on their prior conversations.
The gold answer will usually be a concise and short answer that includes the referenced topic, for example:
Question: Do you remember what I got the last time I went to Hawaii?
Gold answer: A shell necklace
The generated answer might be much longer, but you should be generous with your grading - as long as it touches on the same topic as the gold answer, it should be counted as CORRECT.

For time related questions, the gold answer will be a specific date, month, year, etc. The generated answer might be much longer or use relative time references (like "last Tuesday" or "next month"), but you should be generous with your grading - as long as it refers to the same date or time period as the gold answer, it should be counted as CORRECT. Even if the format differs (e.g., "May 7th" vs "7 May"), consider it CORRECT if it's the same date.

Now it's time for the real question:
Question: {question}
Gold answer: {gold}
Generated answer: {pred}

First, provide a short (one sentence) explanation of your reasoning, then finish with CORRECT or WRONG.
Do NOT include both CORRECT and WRONG in your response, or it will break the evaluation script."""


def judge_label(text):
    m = re.findall(r"\b(CORRECT|WRONG)\b", text.upper())
    return m[-1] if m else "WRONG"
