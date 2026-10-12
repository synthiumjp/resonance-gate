import json, sys, os, re, urllib.request, collections
os.chdir(os.path.expanduser("~/jpwork/sdr-dev11/bench/false_memory"))
sys.path.insert(0, "."); os.environ["FM_SAME_V7"] = "1"; os.environ["FM_READER_SAME"] = "1"
import answer as A
S, R = sys.argv[1], sys.argv[2]
def call(prompt):
    body = {"model": "qwen3-14b-a8cc1361.gguf", "temperature": 0, "max_tokens": 120, "seed": 0, "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
cases = {c["id"]: c for c in map(json.loads, open(f"cases_dev_{S}.jsonl"))}
tot = collections.Counter(); per = collections.defaultdict(list)
for r in map(json.loads, open(f"{R}/raw_sourcedrecall.jsonl")):
    c = cases[r["id"]]; p = r["probes"][0]; cp = c["probes"][0]
    if cp["class"] != "f": continue
    t = [x.lower() for x in cp["expect"]["terms"]]
    if not any(x in p["block"].lower() for x in t): continue
    today = max(cv["date"] for cv in c["conversations"])
    head, rules = p["block"].split("[MEMORY RULES] ")
    sents = re.split(r"(?<=[.])\s+(?=[A-Z(])", rules.strip())
    for k in range(-1, len(sents)):
        rr = " ".join(s for j, s in enumerate(sents) if j != k)
        a = call(A.PROMPT.format(today=today, q=p["q"], memory=head + "[MEMORY RULES] " + rr, rules=A.SAME_RULES))
        h = any(x in a.lower() for x in t)
        name = "all" if k < 0 else f"-{k}:{sents[k][:50]}"
        tot[name] += h
        if h: per[name].append(r["id"])
    print(r["id"], "done", flush=True)
base = set(per["all"])
for name, n in tot.items():
    print(f"{n:3d}  +{len(set(per[name]) - base)} -{len(base - set(per[name]))}  {name}")
