# own-writing note on lines detection calls "own"; reader called directly on fixed retrieval
import json, sys, os, re, urllib.request, collections
os.chdir(os.path.expanduser("~/jpwork/sdr-dev11/bench/false_memory"))
sys.path.insert(0, "."); os.environ["FM_SAME_V7"] = "1"; os.environ["FM_READER_SAME"] = "1"
import answer as A
sys.path.insert(0, os.path.expanduser("~/jpwork/sdr-dev12/experiments/p2"))
from prose import _paste_span
S, R = sys.argv[1], sys.argv[2]
NOTES = {"m1": "(their own writing: I, me and my in it are the user) ",
         "m2": "(the user's own words about themselves) "}
def call(prompt):
    body = {"model": "qwen3-14b-a8cc1361.gguf", "temperature": 0, "max_tokens": 120, "seed": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
LINE = re.compile(r'^(- \[[^\]]+\] (?:\(in reply to "[^"]*"\) )?)"(.*)"(.*)$')
norm = lambda t: re.sub(r"\s+", " ", t).strip()[:60]
OWNS = {}
def mark(block, owner, note, cid=None):
    out, n = [], 0
    for l in block.split("\n"):
        m = LINE.match(l)
        if m and norm(m.group(2)) in OWNS.get(cid, ()):
            l = m.group(1) + note + '"' + m.group(2) + '"' + m.group(3); n += 1
        out.append(l)
    return "\n".join(out), n
cases = {c["id"]: c for c in map(json.loads, open(f"cases_dev_{S}.jsonl"))}
tot = collections.Counter(); nm = 0
for c in cases.values():
    OWNS[c["id"]] = {norm(t["content"]) for cv in c["conversations"] for t in cv["turns"]
                     if t["role"] == "user" and _paste_span(t["content"], c["owner"]) == "own"}
for r in map(json.loads, open(f"{R}/raw_sourcedrecall.jsonl")):
    c = cases[r["id"]]
    for p, cp in zip(r["probes"], c["probes"]):
        today = max(cv["date"] for cv in c["conversations"])
        res = []
        for name in ("asis", "m1", "m2"):
            blk = p["block"] if name == "asis" else mark(p["block"], c["owner"], NOTES[name], c["id"])[0]
            if name == "m1": nm += mark(p["block"], c["owner"], "", c["id"])[1] > 0
            if name != "asis" and blk == p["block"]:
                a = res[0][1]
            else:
                a = call(A.PROMPT.format(today=today, q=p["q"], memory=blk, rules=A.SAME_RULES))
            res.append((name, a))
        for name, a in res:
            if "expect" in cp:
                h = any(re.search(r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])", a.lower()) for x in cp["expect"]["terms"])
                tot[(name, "hit")] += h
            if "forbid" in cp:
                tot[(name, "forbid_q")] += 1
        print(r["id"], cp["class"], " | ".join(f"{n}: {a[:90]!r}" for n, a in res), flush=True)
print("probes with a marked line:", nm)
print(sorted(tot.items()))
