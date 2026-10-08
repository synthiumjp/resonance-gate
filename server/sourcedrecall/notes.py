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
    # find_spec, not import: loading onnxruntime-genai only to ask whether
    # notes are on left it to crash at interpreter exit next to the other
    # ONNX Runtime sessions (2026-10-07, macOS: recursive_mutex lock failed)
    import importlib.util
    return d if importlib.util.find_spec("onnxruntime_genai") else None


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
    # 2026-10-06: the prompt goes in 256 tokens at a time. Whole, its
    # next-token scores for every position (3,000 x 152k) took peak memory
    # from 1.2 to 3.9 GB; in parts it is 2.0 GB, with the same notes.
    for i in range(0, len(ids), 256):
        g.append_tokens(ids[i:i + 256])
    stream, text, seen, n = tok.create_stream(), "", [], 0
    while not g.is_done():
        g.generate_next_token()
        n += 1
        text += stream.decode(g.get_next_tokens()[0])
        if text.endswith("\n"):
            line = text.rstrip("\n").rsplit("\n", 1)[-1].strip()
            if line and seen.count(line) >= 2:
                break                 # a small model can repeat a line forever
            seen.append(line)
    if n >= max_new:
        # stopped at the length limit: the last line is cut off (2026-10-09)
        text = text.rsplit("\n", 1)[0] if "\n" in text.strip() else ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


def _call(prompt, timeout=600):
    url = os.environ["SOURCEDRECALL_NOTES_URL"].rstrip("/") + "/chat/completions"
    body = {"model": os.environ["SOURCEDRECALL_NOTES_MODEL"], "temperature": 0,
            "max_tokens": 600, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    text = out["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# 2026-10-06: person deixis made explicit for the small model. "I" and "my"
# point at whoever is speaking, "you" and "your" at the listener; a 0.6B model
# loses track and gives the user the other side's news ("Caroline has kids"
# from Melanie's "I took the kids", 17% of its notes on LoCoMo dev). Before it
# reads the conversation, each pronoun is replaced by who it refers to.
_AGREE = {"am": "is", "'m": " is", "'ve": " has", "have": "has", "'ll": " will",
          "'d": " would", "was": "was", "were": "was", "are": "is", "'re": " is"}


# 2026-10-09 (adversarial review): quotes and code inside a message belong
# to someone else ("Mary said: 'I am tired'", a landlord's email "I own three
# buildings", print("I am here")); curly apostrophes from phones broke the
# rewrite ("I’m" -> "Dan’m"); "a gold mine" became "a gold Dana's".
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`|(?<![\w])\'[^\'\n]{2,}\'(?![\w])')


def _deixis(text, me, you):
    """Rewrite the pronouns of one speaker's line: first person -> `me`,
    second person -> `you` (names or "Other"). Quotes and code are left as
    they are."""
    text = (text or "").replace("’", "'").replace("‘", "'")
    out, last = [], 0
    for m in _QUOTED.finditer(text):
        out.append(_deixis_plain(text[last:m.start()], me, you))
        out.append(m.group(0))
        last = m.end()
    out.append(_deixis_plain(text[last:], me, you))
    return "".join(out)


def _deixis_plain(text, me, you):
    def subj(name):
        def f(m):
            aux = m.group(2) or ""
            a = _AGREE.get(aux.strip().lower(), aux)
            return name + ((" " + a.strip()) if aux and not aux.startswith("'") else a)
        return f
    t = re.sub(r"\byours\b", you + "'s", text, flags=re.I)
    t = re.sub(r"\byour\b", you + "'s", t, flags=re.I)
    t = re.sub(r"\byourself\b", you, t, flags=re.I)
    t = re.sub(r"\b(I)(?!\w)((?i:'m|'ve|'ll|'d|\s+am\b|\s+have\b|\s+was\b))?", subj(me), t)
    t = re.sub(r"\b(you)(?!\w)('re|'ve|'ll|'d|\s+are\b|\s+have\b|\s+were\b)?", subj(you), t, flags=re.I)
    t = re.sub(r"\bmy\b", me + "'s", t, flags=re.I)
    t = re.sub(r"(?<!\bthe )(?<!\ba )(?<!gold )(?<!coal )(?<!salt )\bmine\b", me + "'s", t,
               flags=re.I)
    t = re.sub(r"\b(me|myself)\b", me, t, flags=re.I)
    return t


def explicit_person(lines, owner, other="Other"):
    """`Name: text` lines -> the same with each pronoun replaced by who it
    refers to."""
    out = []
    for l in lines:
        who, _, txt = l.partition(": ")
        me, you = (owner, other) if who == owner else (other, owner)
        out.append(f"{who}: {_deixis(txt, me, you)}")
    return out


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
    if _local_dir():
        lines = explicit_person(lines, owner)
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
        if not re.search(r"\b" + re.escape(owner.split()[0]) + r"\b", ln, re.I):
            continue          # a note must be about the owner
        if not grounded(ln, said, owner) or not faithful(ln, said, owner):
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


_NUM = re.compile(r"\b\d[\d.,]*\b|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|"
                  r"eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million)\b", re.I)
_NEG = re.compile(r"\b(?:not|no|never|n't|none|nothing|nobody)\b|n't\b", re.I)


def faithful(note, said, owner):
    """2026-10-09 (adversarial review): grounded() takes words, not meaning.
    "Dana does not eat meat" passed against "I eat meat now", "has 5 kids"
    against "I have 3 kids". A number in the note must be in what the user
    wrote, and the note's polarity must match a sentence of theirs about the
    same thing."""
    low_said = said.lower()
    for n in _NUM.findall(note):
        if n.lower() not in low_said:
            return False
    words = _stems(note) - _stems(owner)
    sents = [x for x in re.split(r"(?<=[.!?])\s+|\n+", said) if x.strip()]
    near = [x for x in sents if words and len(words & _stems(x)) * 2 >= len(words)]
    if not near:
        return True
    neg = bool(_NEG.search(note))
    return any(bool(_NEG.search(x)) == neg for x in near)
