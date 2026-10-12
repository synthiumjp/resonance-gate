"""Reader-only check on fixed retrieval: sourcedrecall's block with each
quoted message's line breaks put back (the parser and window flatten them;
plain retrieval keeps them). Restores a break wherever the last words of one
line of the user's message and the first words of the next appear joined by
a space in a block line. Strict whole-word scoring of expected terms only.
usage: breaks.py SET RESULTS_DIR   (run from ~/jpwork on the Mac)"""
import json, sys, os, re, urllib.request, collections
os.chdir(os.path.expanduser("~/jpwork/sdr-dev12/bench/false_memory"))
sys.path.insert(0, "."); os.environ["FM_SAME_V7"] = "1"; os.environ["FM_READER_SAME"] = "1"
import answer as A
S, R = sys.argv[1], sys.argv[2]


def call(prompt):
    body = {"model": "qwen3-14b-a8cc1361.gguf", "temperature": 0, "max_tokens": 120, "seed": 0,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()


def joins(text):
    """(flat join, broken join) pairs for each line boundary of a message"""
    out = []
    ls = text.split("\n")
    i = 0
    while i < len(ls) - 1:
        a = ls[i].split()
        j, blank = i + 1, False
        while j < len(ls) and not ls[j].strip():
            j, blank = j + 1, True
        if a and j < len(ls):
            b = ls[j].split()
            ta, tb = " ".join(a[-3:]), " ".join(b[:3])
            out.append((ta + " " + tb, ta, tb, blank))
        i = j
    return out


def rebreak(block, case, indent):
    msgs = [t["content"] for cv in case["conversations"] for t in cv["turns"]
            if t["role"] == "user" and "\n" in t["content"]]
    head, sep, rules = block.partition("\n[MEMORY RULES]")
    out, n = [], 0
    for l in head.split("\n"):
        for m in msgs:
            for flat, ta, tb, blank in joins(m):
                if flat in l:
                    nl = "\n" + ("\n" if blank else "") + ("  " if indent else "")
                    l = l.replace(flat, ta + nl + tb, 1); n += 1
        out.append(l)
    return "\n".join(out) + sep + rules, n


hit = lambda a, terms, q: any(
    re.search(r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])", a.lower())
    and not re.search(r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])", q.lower())
    for x in terms)
cases = {c["id"]: c for c in map(json.loads, open(f"cases_dev_{S}.jsonl"))}
tot = collections.Counter(); changed = 0
for r in map(json.loads, open(f"{R}/raw_sourcedrecall.jsonl")):
    c = cases[r["id"]]
    for p, cp in zip(r["probes"], c["probes"]):
        if "expect" not in cp or not p.get("block"):
            continue
        today = max(cv["date"] for cv in c["conversations"])
        res = []
        for name, ind in (("asis", None), ("raw", False), ("indent", True)):
            blk, n = (p["block"], 0) if ind is None else rebreak(p["block"], c, ind)
            if name == "raw":
                changed += n > 0
            a = res[0][1] if (ind is not None and n == 0) else call(
                A.PROMPT.format(today=today, q=p["q"], memory=blk, rules=A.SAME_RULES))
            h = hit(a, cp["expect"]["terms"], p["q"]); tot[name] += h
            res.append((name, a, h))
        print(r["id"], " ".join(f"{n}={'HIT' if h else 'miss'}" for n, _, h in res),
              "|", " | ".join(a[:70].replace("\n", " ") for _, a, _ in res[1:]), flush=True)
print("probes with breaks restored:", changed)
print(dict(tot))
