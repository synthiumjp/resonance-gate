"""Held-out v5: the answer-view results per part (A-F) and system, audited,
counts only. Reads probe_details.jsonl written by score.py.

    FM_CASES=cases_v5.jsonl FM_RESULTS=results_v5 python v5_parts.py
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
cases = {json.loads(l)["id"]: json.loads(l) for l in open(os.environ.get("FM_CASES") or
                                                        os.path.join(HERE, "cases_v5.jsonl"))}
res = os.environ.get("FM_RESULTS") or os.path.join(HERE, "results_v5")
t = collections.defaultdict(collections.Counter)
for l in open(os.path.join(res, "probe_details.jsonl")):
    d = json.loads(l)
    if d["view"] != "answer":
        continue
    c = cases[d["id"]]
    key = (d["system"], c["subtype"][:1], c["class"])
    t[key]["probes"] += 1
    if "fm" in d:
        t[key]["false_memory"] += bool(d.get("fm_audited"))
        t[key]["forbid"] += 1
    if "hit" in d:
        t[key]["expect"] += 1
        t[key]["hit"] += bool(d["hit"])
for (s, part, cls), c in sorted(t.items()):
    out = [f"{s:14s} part {part} class {cls}: {c['probes']} probes"]
    if c["forbid"]:
        out.append(f"false memory {c['false_memory']}/{c['forbid']}")
    if c["expect"]:
        out.append(f"expected term in the answer {c['hit']}/{c['expect']}")
    print("; ".join(out))
