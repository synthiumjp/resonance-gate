"""Which difference between sourcedrecall's block and plain retrieval's lines
makes the reader refuse on own material? Fixed retrieval, reader called
directly, strict whole-word scoring of expected terms. Each variant changes
one thing.
usage: ablate.py OURS_RESULTS RAG_RESULTS ID [ID ...]   (from ~/jpwork on the Mac)"""
import json, sys, os, re, urllib.request
os.chdir(os.path.expanduser("~/jpwork/sdr-dev12/bench/false_memory"))
sys.path.insert(0, "."); os.environ["FM_SAME_V7"] = "1"; os.environ["FM_READER_SAME"] = "1"
import answer as A
O, G, ids = sys.argv[1], sys.argv[2], sys.argv[3:]


def call(prompt):
    body = {"model": "qwen3-14b-a8cc1361.gguf", "temperature": 0, "max_tokens": 120, "seed": 0,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("http://127.0.0.1:8090/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    raw = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    return re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()


W = lambda x: r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])"
hit = lambda a, terms, q: any(re.search(W(x), a.lower()) and not re.search(W(x), q.lower()) for x in terms)
cases = {c["id"]: c for c in map(json.loads, open("cases_dev_own.jsonl"))}
ours = {r["id"]: r for r in map(json.loads, open(f"{O}/raw_sourcedrecall.jsonl"))}
rag = {r["id"]: r for r in map(json.loads, open(f"{G}/raw_rag.jsonl"))}
for cid in ids:
    c, cp = cases[cid], cases[cid]["probes"][0]
    terms = cp["expect"]["terms"]
    blk = ours[cid]["probes"][0]["block"]
    body, _, rules = blk.partition("\n[MEMORY RULES]")
    rules = "[MEMORY RULES]" + rules
    head, _, lines = body.partition("\n")
    ls = lines.split("\n")
    fact = [l for l in ls if any(re.search(W(t), l.lower()) for t in terms)] or ls
    rl = "\n".join(f"- {l}" for l in rag[cid]["probes"][0]["lines"])
    unq = lambda s: re.sub(r'^(- \[[^\]]+\] )(?:\(in reply to "[^"]*"\) )?"(.*)"$', r"\1\2", s, flags=re.M)
    V = {
        "asis": blk,
        "no_rules": body,
        "no_header": lines + "\n" + rules,
        "plain_header": "[MEMORY: what the user has told you about this]\n" + lines + "\n" + rules,
        "fact_only": head + "\n" + "\n".join(fact) + "\n" + rules,
        "fact_only_no_rules": head + "\n" + "\n".join(fact),
        "no_quotes": head + "\n" + unq(lines) + "\n" + rules,
        "rag_lines+rules": rl + "\n" + rules,
        "rag_lines+head": head + "\n" + rl,
        "rag_lines": rl,
    }
    today = max(cv["date"] for cv in c["conversations"])
    print(f"== {cid} {cp['q']}", flush=True)
    for name, b in V.items():
        a = call(A.PROMPT.format(today=today, q=cp["q"], memory=b, rules=A.SAME_RULES))
        print(f"  {name:20s} {'HIT ' if hit(a, terms, cp['q']) else 'miss'} {a[:90]!r}", flush=True)
print("ablate done")
