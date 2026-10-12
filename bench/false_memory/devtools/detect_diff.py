"""Paste detection before and after a prose.py change, no models: every user
turn of the dev sets (and LoCoMo, if given) through both versions of
_paste_span; prints each turn whose result changes and the totals.
usage: detect_diff.py OLD_PROSE.py NEW_PROSE.py CASES_DIR [LOCOMO_JSON]"""
import glob, importlib.util, json, os, sys


def load(path, name):
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


old, new = load(sys.argv[1], "prose_old"), load(sys.argv[2], "prose_new")
kind = lambda sp: "own" if sp == "own" else ("pasted" if sp else "-")  # noqa: E731
tot, ch = {}, 0


def check(src, cid, sub, owner, text):
    global ch
    a, b = kind(old._paste_span(text, owner)), kind(new._paste_span(text, owner))
    tot[(src, a, b)] = tot.get((src, a, b), 0) + 1
    if a != b:
        ch += 1
        print(f"{src} {cid} {sub}: {a} -> {b} | {' '.join(text.split())[:160]!r}")


for f in sorted(glob.glob(os.path.join(sys.argv[3], "cases*.jsonl"))):
    base = os.path.basename(f)
    if not (base == "cases.jsonl" or base.startswith("cases_dev_")):
        continue                      # dev sets only; held-out sets are never read
    for c in map(json.loads, open(f)):
        for cv in c["conversations"]:
            for t in cv["turns"]:
                if t["role"] == "user":
                    check(base[6:-6] or "cases", c["id"], c.get("subtype", ""), c["owner"], t["content"])
if len(sys.argv) > 4:
    for conv in json.load(open(sys.argv[4])):
        cc = conv["conversation"]
        for k, v in cc.items():
            if k.startswith("session_") and isinstance(v, list):
                for t in v:
                    check("locomo", conv.get("sample_id", ""), k, t.get("speaker", ""), t.get("text", ""))
print("changed:", ch)
for k in sorted(tot):
    if k[1] != k[2] or k[1] != "-":
        print(" ", k, tot[k])
