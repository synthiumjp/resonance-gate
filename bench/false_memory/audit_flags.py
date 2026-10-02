"""List every judged false-memory flag with its proposition, for manual audit.
Usage: python3 audit_flags.py [classes]   (default: all of abcde)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
cls = sys.argv[1] if len(sys.argv) > 1 else "abcde"
cases = {}
for ln in open(os.environ.get("FM_CASES") or os.path.join(HERE, "cases.jsonl")):
    c = json.loads(ln)
    cases[c["id"]] = c
for ln in open(os.path.join(os.environ.get("FM_RESULTS") or os.path.join(HERE, "results"), "probe_details.jsonl")):
    d = json.loads(ln)
    if d["view"] == "lines" and d.get("fm") and d["class"] in cls:
        p = cases[d["id"]]["probes"][0]
        print(d["system"], d["id"], "|", p["forbid"]["prop"], "|", d["bad"])
