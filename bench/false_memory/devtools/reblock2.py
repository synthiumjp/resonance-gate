"""Copy a results dir with sourcedrecall's [MEMORY RULES] paragraph moved
from after the lines to just under the header line, wording unchanged.
usage: reblock2.py SRC_RESULTS DST_RESULTS"""
import json, sys, os
src, dst = sys.argv[1:3]
os.makedirs(dst, exist_ok=True)
n = m_ = 0
with open(os.path.join(dst, "raw_sourcedrecall.jsonl"), "w") as f:
    for r in map(json.loads, open(os.path.join(src, "raw_sourcedrecall.jsonl"))):
        for p in r.get("probes") or []:
            b = p.get("block") or ""
            if "\n[MEMORY RULES]" in b:
                body, rules = b.split("\n[MEMORY RULES]", 1)
                head, _, lines = body.partition("\n")
                p["block"] = head + "\n[MEMORY RULES]" + rules.rstrip() + "\n" + lines; n += 1
            elif b:
                m_ += 1
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("first: blocks rewritten:", n, "left:", m_)
