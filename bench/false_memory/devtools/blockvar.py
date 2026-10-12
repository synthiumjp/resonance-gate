import json, sys, os, re, urllib.request, collections
os.chdir(os.path.expanduser("~/jpwork/sdr-dev11/bench/false_memory"))
sys.path.insert(0, "."); os.environ["FM_SAME_V7"] = "1"; os.environ["FM_READER_SAME"] = "1"
import answer as A
S = sys.argv[1]; R = sys.argv[2]
def call(prompt):
    body = {"model": "qwen3-14b-a8cc1361.gguf", "temperature": 0, "max_tokens": 120, "seed": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
def variants(block):
    head, rules = block.split("[MEMORY RULES]")
    rules = "[MEMORY RULES]" + rules
    yield "asis", block
    yield "no_rules", head.rstrip()
    yield "no_header", "\n".join(head.split("\n")[1:]).rstrip() + "\n" + rules
    unq = re.sub(r'^(- \[[^\]]+\] )(?:\(in reply to "[^"]*"\) )?"(.*)"', r"\1\2", head, flags=re.M)
    yield "no_quotes", unq.rstrip() + "\n" + rules
    yield "bare", "\n".join(unq.split("\n")[1:]).rstrip()
cases = {c["id"]: c for c in map(json.loads, open(f"cases_dev_{S}.jsonl"))}
tot = collections.Counter()
for r in map(json.loads, open(f"{R}/raw_sourcedrecall.jsonl")):
    c = cases[r["id"]]; p = r["probes"][0]; cp = c["probes"][0]
    if cp["class"] != "f": continue
    t = [x.lower() for x in cp["expect"]["terms"]]
    if not any(x in p["block"].lower() for x in t): continue
    today = max(cv["date"] for cv in c["conversations"])
    out = []
    for name, blk in variants(p["block"]):
        a = call(A.PROMPT.format(today=today, q=p["q"], memory=blk, rules=A.SAME_RULES))
        h = any(x in a.lower() for x in t); tot[name] += h
        out.append(f"{name}={'HIT' if h else 'miss'}")
    print(r["id"], " ".join(out), flush=True)
print(dict(tot))
