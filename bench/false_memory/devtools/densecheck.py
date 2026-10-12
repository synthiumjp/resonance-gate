"""Does the dense (bge-small) similarity separate the lines a question needs
from filler better than the cross-encoder? Over dev20's blocks and score
logs (sdr-dev13): per shown line, the cross-encoder score (log), the cosine
of question and message (the product's bi-encoder), the route, and whether
the line holds an expected term. Writes JSON lines for analysis.
usage: densecheck.py SET OUT.jsonl   (from ~/jpwork on the Mac)"""
import json, os, re, sys
T = os.path.expanduser("~/jpwork/sdr-dev13")
sys.path.insert(0, os.path.join(T, "experiments/p2"))
import retrieve_v3 as RV3
S, out = sys.argv[1], sys.argv[2]
D = os.path.join(T, "bench/false_memory")
bi, _ = RV3._models()
cases = {c["id"]: c for c in map(json.loads, open(os.path.join(D, f"cases_dev_{S}.jsonl")))}
R = os.path.join(D, f"results_dev20_{S}")
log = [json.loads(l) for l in open(os.path.join(R, "msglog.jsonl"))]
W = lambda x: r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])"  # noqa: E731
i = 0
with open(out, "w") as fo:
    for r in map(json.loads, open(os.path.join(R, "raw_sourcedrecall.jsonl"))):
        c = cases[r["id"]]
        for p, cp in zip(r["probes"], c["probes"]):
            b = p.get("block") or ""
            if not b or b.startswith("[MEMORY] Nothing stored"):
                continue
            e = log[i]; i += 1
            ls = b.partition("\n[MEMORY RULES]")[0].split("\n")[1:]
            texts = [re.sub(r'^- \[[^\]]*\] (?:\(in reply to "[^"]*"\) )?', "", l) for l in ls]
            qv = bi.encode([p["q"]], normalize_embeddings=True)[0]
            ev = bi.encode(texts, normalize_embeddings=True)
            terms = (cp.get("expect") or {}).get("terms") or []
            for l, m, v in zip(ls, e["msgs"], ev):
                fo.write(json.dumps({"id": r["id"], "q": p["q"], "cls": cp.get("class", c["class"]),
                                     "advice": e.get("advice"), "ce": m["score"], "rank": m["rank"],
                                     "via": m["via"] is not None, "cos": float(v @ qv),
                                     "has_term": any(re.search(W(t), l.lower()) for t in terms),
                                     "line": l[:160]}) + "\n")
print(S, "probes", i)
