"""Print the returned lines of forbid-probes the judge did NOT flag, for manual
false-negative audit. Usage: python3 audit_unflagged.py <system> [classes]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
system = sys.argv[1]
cls = sys.argv[2] if len(sys.argv) > 2 else "acde"
cases = {}
for ln in open(os.environ.get("FM_CASES") or os.path.join(HERE, "cases.jsonl")):
    c = json.loads(ln)
    cases[c["id"]] = c
raw = {}
for ln in open(os.path.join(os.environ.get("FM_RESULTS") or os.path.join(HERE, "results"), f"raw_{system}.jsonl")):
    r = json.loads(ln)
    raw[r["id"]] = r
for ln in open(os.path.join(os.environ.get("FM_RESULTS") or os.path.join(HERE, "results"), "probe_details.jsonl")):
    d = json.loads(ln)
    if d["system"] == system and d["view"] == "lines" and d["class"] in cls and not d.get("fm"):
        c = cases[d["id"]]
        print(d["id"], "|", c["probes"][0]["forbid"]["prop"], "|",
              [x[:140] for x in raw[d["id"]]["probes"][0]["lines"]])
