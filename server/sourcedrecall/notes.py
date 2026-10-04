"""Model-written notes, OFF by default (2026-10-05).

sourcedrecall stores the user's own words and never calls a model. This
optional mode asks a model the user runs themselves (any OpenAI-compatible
server: Ollama, llama.cpp, LM Studio) to write short notes once per stored
conversation -- one sentence per lasting fact the user stated. Short notes
let a question that needs several facts from different conversations
("What instruments does she play?") see more of them in the same space.

Every note keeps the conversation and date it came from and is shown
labelled as written by the model. Forgetting a sentence removes the notes
of the conversations it was in.

    SOURCEDRECALL_NOTES_URL    e.g. http://127.0.0.1:11434/v1 (Ollama)
    SOURCEDRECALL_NOTES_MODEL  the model name that server knows
"""
import json
import os
import re
import urllib.request

PROMPT = """Below is one conversation from {date}. "{owner}" is the person this memory is about; the other side is someone they talked to.

Write the lasting facts {owner} states in it about themselves and their life: what they do, have, like, prefer, plan, did, and facts about the people, places and things in their life. One short sentence per line, in the third person, starting with "{owner}". Combine items that belong together ("{owner} plays the clarinet and the violin"). Use only what {owner} says; do not add anything the other side says unless {owner} confirms it; no guesses. If there is nothing lasting, write NONE.

CONVERSATION:
{conversation}
/no_think"""


def enabled():
    return bool(os.environ.get("SOURCEDRECALL_NOTES_URL")
                and os.environ.get("SOURCEDRECALL_NOTES_MODEL"))


def _call(prompt, timeout=600):
    url = os.environ["SOURCEDRECALL_NOTES_URL"].rstrip("/") + "/chat/completions"
    body = {"model": os.environ["SOURCEDRECALL_NOTES_MODEL"], "temperature": 0,
            "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    text = out["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def write_notes(owner, date, turns):
    """-> the model's notes for one conversation (list of sentences)."""
    lines = []
    for t in turns:
        who = owner if t.get("role", "user") == "user" else "Other"
        txt = " ".join(str(t.get("content", "")).split())
        if txt:
            lines.append(f"{who}: {txt[:1500]}")
    if not any(l.startswith(owner + ":") for l in lines):
        return []
    raw = _call(PROMPT.format(owner=owner, date=date or "unknown date",
                              conversation="\n".join(lines)[:12000]))
    out = []
    for ln in raw.splitlines():
        ln = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
        if not ln or ln.upper().startswith("NONE"):
            continue
        if owner.split()[0].lower() not in ln.lower():
            continue          # a note must be about the owner
        out.append(ln)
    return out[:20]
