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

Or, with no server, a small model trained for this one job runs in the
same process on onnxruntime-genai (2026-10-06):

    SOURCEDRECALL_NOTES_DIR    a folder holding its genai_config.json

`sourcedrecall-setup --notes` installs it (paths.notes_models_dir()), and
an installed model is used; SOURCEDRECALL_NOTES=off turns it off again.
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

# The in-process model was trained on this prompt (notes from Qwen3-14B with
# PROMPT, kept only where grounded() passes), so it needs no instructions.
LOCAL_PROMPT = ("Write the lasting facts {owner} states about themselves in this conversation "
                "from {date}, one short sentence per line starting with \"{owner}\", or NONE."
                "\n\n{conversation}")


def _local_dir():
    if os.environ.get("SOURCEDRECALL_NOTES", "").lower() in ("off", "0", "no"):
        return None
    d = os.environ.get("SOURCEDRECALL_NOTES_DIR")
    if not d:
        if os.environ.get("SOURCEDRECALL_NOTES_URL"):
            return None       # a server the user named wins over the installed model
        from sourcedrecall.paths import notes_models_dir
        d = notes_models_dir()
    if not os.path.isfile(os.path.join(d, "genai_config.json")):
        return None
    try:
        import onnxruntime_genai  # noqa: F401
    except ImportError:
        return None
    return d


def enabled():
    return bool(_local_dir() or (os.environ.get("SOURCEDRECALL_NOTES_URL")
                                 and os.environ.get("SOURCEDRECALL_NOTES_MODEL")))


MAX_PARTS = int(os.environ.get("SOURCEDRECALL_NOTES_MAX_PARTS", "8"))
_LOCAL = {}


def _local(prompt, max_new=300):
    import onnxruntime_genai as og
    d = _local_dir()
    if d not in _LOCAL:
        cfg = og.Config(d)
        cfg.clear_providers()
        n = int(os.environ.get("SOURCEDRECALL_NOTES_THREADS", "4"))
        cfg.overlay(json.dumps({"model": {"decoder": {"session_options": {
            "intra_op_num_threads": n}}}}))
        m = og.Model(cfg)
        _LOCAL[d] = (m, og.Tokenizer(m))
    m, tok = _LOCAL[d]
    ids = tok.encode("<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n")
    p = og.GeneratorParams(m)
    p.set_search_options(do_sample=False, max_length=len(ids) + max_new)
    g = og.Generator(m, p)
    g.append_tokens(ids)
    out = []
    while not g.is_done():
        g.generate_next_token()
        out.append(g.get_next_tokens()[0])
    return re.sub(r"<think>.*?</think>", "", tok.decode(out), flags=re.S).strip()


def _call(prompt, timeout=600):
    url = os.environ["SOURCEDRECALL_NOTES_URL"].rstrip("/") + "/chat/completions"
    body = {"model": os.environ["SOURCEDRECALL_NOTES_MODEL"], "temperature": 0,
            "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    text = out["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


CALLS = {"last": 0}


def write_notes(owner, date, turns):
    """-> the model's notes for one conversation (list of sentences);
    CALLS["last"] is how many times the model was run for it."""
    CALLS["last"] = 0
    lines = []
    for t in turns:
        who = owner if t.get("role", "user") == "user" else "Other"
        txt = " ".join(str(t.get("content", "")).split())
        if txt:
            lines.append(f"{who}: {txt[:1500]}")
    if not any(l.startswith(owner + ":") for l in lines):
        return []
    # 2026-10-06: a long session (a day of coding) is read in parts of at
    # most 12,000 characters, not cut at the first 12,000.
    parts, cur = [], []
    for l in lines:
        if cur and len("\n".join(cur + [l])) > 12000:
            parts.append(cur)
            cur = []
        cur.append(l[:12000])
    parts.append(cur)
    parts = [p for p in parts if any(l.startswith(owner + ":") for l in p)][:MAX_PARTS]
    raw = []
    for p in parts:
        args = dict(owner=owner, date=date or "unknown date", conversation="\n".join(p))
        raw.append(_local(LOCAL_PROMPT.format(**args)) if _local_dir()
                   else _call(PROMPT.format(**args)))
    CALLS["last"] = len(parts)
    raw = "\n".join(raw)
    said = " ".join(str(t.get("content", "")) for t in turns
                    if t.get("role", "user") == "user")
    out = []
    for ln in raw.splitlines():
        ln = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip()
        if not ln or ln.upper().startswith("NONE"):
            continue
        if owner.split()[0].lower() not in ln.lower():
            continue          # a note must be about the owner
        if not grounded(ln, said, owner):
            continue          # what the other side said is not a note
        if ln not in out:
            out.append(ln)
    return out[:20 * len(parts)]


_STOP = frozenset("""the a an and or of to in on at for with from by as is are was
were be been has have had does did do not no their they them his her him she he
its it this that these those who which what when where why how also very really
just some any all more most other into about over after before than then there
here our your my me we you""".split())


def _stem(w):
    for suf in ("ing", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            break
    return w[:5]


def _stems(text):
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP}


def grounded(note, said, owner, share=0.6):
    """2026-10-05 (blind v3, notes mode): the model wrote notes from claims
    the ASSISTANT made about the user ("you're vegan, right?"). A note is
    kept only if most of its content words are in what the user wrote."""
    words = _stems(note) - _stems(owner)
    if not words:
        return False
    return len(words & _stems(said)) / len(words) >= share
