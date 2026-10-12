"""Inputs for train.py from public data (2026-10-13).

    python prep.py AESLC_TRAIN.parquet LOCOMO10.json EXCLUDE.jsonl[,...] OUT_DIR

emails.jsonl: 1,500 Enron email bodies (aeslc train, 150 to 1,500
characters, seed 7) that are not among the emails of any test or
development set (EXCLUDE: jsonl files with a "body" field, or case files),
addresses replaced by example.com ones. chat.jsonl: the turns of LoCoMo's
development conversations (0 and 1 only; 2 to 9 are the test set) of 12
words or more, with the same speaker's next turn.
"""
import json
import random
import re
import sys

import pyarrow.parquet as pq

parquet, locomo, excl, out = sys.argv[1:5]
key = lambda s: " ".join(re.sub(r"\W+", " ", s or "").lower().split()[:12])  # noqa: E731
seen = set()
for f in excl.split(","):
    for l in open(f, encoding="utf-8"):
        d = json.loads(l)
        if "body" in d:
            seen.add(key(d["body"]))
        for cv in d.get("conversations", []):
            for t in cv.get("turns", []):
                for para in re.split(r"\n\s*\n", t.get("content", "")):
                    seen.add(key(para))
rows = pq.read_table(parquet).to_pylist()
col = next(k for k in rows[0] if "body" in k.lower())
pool = [r[col] for r in rows if 150 <= len(r[col] or "") <= 1500 and key(r[col]) not in seen]
random.Random(7).shuffle(pool)
mail = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
with open(f"{out}/emails.jsonl", "w", encoding="utf-8") as f:
    for b in pool[:1500]:
        f.write(json.dumps({"body": mail.sub("someone@example.com", b)}) + "\n")
n = 0
with open(f"{out}/chat.jsonl", "w", encoding="utf-8") as f:
    for conv in json.load(open(locomo))[:2]:
        cc = conv["conversation"]
        for k, v in cc.items():
            if not (k.startswith("session_") and isinstance(v, list)):
                continue
            for j, t in enumerate(v):
                if len((t.get("text") or "").split()) < 12:
                    continue
                nx = next((x.get("text", "") for x in v[j + 1:j + 3] if x.get("speaker") == t.get("speaker")), "")
                f.write(json.dumps({"text": t["text"], "next": nx}) + "\n")
                n += 1
print(f"emails {min(len(pool), 1500)} of {len(pool)} eligible; chat turns {n}")
