"""Paste detection on the development sets with the classifier off and on
(2026-10-13). Counts per set; LoCoMo turns whose marking changes.

    python eval_dev.py P2_DIR CASES_DIR [LOCOMO10.json]

Development sets only (cases_dev_*); held-out sets are never read here.
For a pasted item (class e) it counts the gold conversation's user turns
marked as pasted (any); for an own item (class f), the turns holding an
expected term left unmarked (all).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, sys.argv[1])
import prose  # noqa: E402

FLAG = os.environ.get("EVAL_FLAG", "RG_PASTE_CLF")   # the switch compared off and on


def word(t, s):
    return re.search(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])", s.lower())


def pasted(u, owner, nx):
    return isinstance(prose._paste_span(u, owner, nx), tuple)


def run(path):
    n = {"e": 0, "f": 0}
    got = {"off": {"e": 0, "f": 0}, "on": {"e": 0, "f": 0}}
    for l in open(path, encoding="utf-8"):
        c = json.loads(l)
        p = c["probes"][0]
        cls = p.get("class") or c["class"]
        if cls not in "ef" or (cls == "f" and "expect" not in p):
            continue
        g = c["conversations"][p.get("gold_conversation") or 0]
        us = [t["content"] for t in g["turns"] if t["role"] == "user"]
        nxt = dict(zip(us, us[1:]))
        n[cls] += 1
        for mode in ("off", "on"):
            os.environ[FLAG] = "0" if mode == "off" else "1"
            if cls == "e":
                got[mode]["e"] += any(pasted(u, c["owner"], nxt.get(u)) for u in us)
            else:
                hold = [u for u in us if any(word(t, u) for t in p["expect"]["terms"])] or us
                got[mode]["f"] += all(not pasted(u, c["owner"], nxt.get(u)) for u in hold)
    return n, got


for f in sorted(glob.glob(os.path.join(sys.argv[2], "cases_dev_*.jsonl"))):
    n, got = run(f)
    if not (n["e"] or n["f"]):
        continue
    print(f"{os.path.basename(f)[10:-6]:>12}: pasted found {got['off']['e']} -> {got['on']['e']} of {n['e']}; "
          f"own kept {got['off']['f']} -> {got['on']['f']} of {n['f']}")
if len(sys.argv) > 3:
    ch = tot = 0
    for conv in json.load(open(sys.argv[3]))[2:]:   # the dev turns are training data
        for k, v in conv["conversation"].items():
            if k.startswith("session_") and isinstance(v, list):
                for j, t in enumerate(v):
                    nx = next((x.get("text", "") for x in v[j + 1:j + 3] if x.get("speaker") == t.get("speaker")), None)
                    tot += 1
                    os.environ[FLAG] = "0"
                    a = pasted(t.get("text", ""), t.get("speaker", ""), nx)
                    os.environ[FLAG] = "1"
                    b = pasted(t.get("text", ""), t.get("speaker", ""), nx)
                    ch += (a != b)
    print(f"LoCoMo test conversations, turns changed by the classifier (detection only): {ch} of {tot}")
