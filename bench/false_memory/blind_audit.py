"""Blinded audit of judge verdicts (2026-10-09, adversarial review A2).

    python blind_audit.py packet <results dir> <out dir>
        writes <out dir>/packet.jsonl (one row per answer to a forbid probe,
        system names replaced by random codes, shuffled) and <out dir>/key.json
        (codes -> system; the auditor must not open it)
    python blind_audit.py apply <results dir> <out dir> <overrides.json>
        reads <out dir>/decisions.jsonl ({"aid", "fm": true|false, "reason"},
        only where the auditor disagrees with the judge) and writes the
        overrides file score.py reads (FM_OVERRIDES), keyed by system

The auditor sees the scenario (from the cases file), the question, the
proposition, the answer and the judge's verdict, never which system gave the
answer, and applies one rule to all: override only a clear judge error.
"""
import json
import os
import random
import secrets
import sys


def packet(res, out):
    os.makedirs(out, exist_ok=True)
    rows, key = [], {}
    for l in open(os.path.join(res, "probe_details.jsonl")):
        d = json.loads(l)
        if d["view"] != "answer" or "fm" not in d:
            continue
        aid = secrets.token_hex(4)
        key[aid] = {"system": d["system"], "id": d["id"],
                    "line": (d.get("lines") or [""])[0]}
        rows.append({"aid": aid, "scenario": d["id"], "class": d["class"],
                     "answer": (d.get("lines") or [""])[0],
                     "judge_says_false_memory": bool(d.get("fm"))})
    random.Random(7).shuffle(rows)
    with open(os.path.join(out, "packet.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    json.dump(key, open(os.path.join(out, "key.json"), "w"))
    print(f"{len(rows)} answers in the packet")


def apply(res, out, overrides_path):
    key = json.load(open(os.path.join(out, "key.json")))
    ov = []
    path = os.path.join(out, "decisions.jsonl")
    for l in (open(path) if os.path.exists(path) else []):
        d = json.loads(l)
        k = key.get(d["aid"])
        if not k or not k["line"]:
            continue
        ov.append({"system": k["system"], "id": k["id"], "fm": bool(d["fm"]),
                   "reason": d.get("reason", ""), "line": k["line"]})
    json.dump({"_note": "blinded audit (blind_audit.py): the auditor saw no "
                        "system names; one rule for all", "overrides": ov},
              open(overrides_path, "w"), indent=1)
    by = {}
    for o in ov:
        by.setdefault(o["system"], [0, 0])[0 if o["fm"] else 1] += 1
    print({s: f"+{a} false memories, -{b}" for s, (a, b) in by.items()})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "packet":
        packet(sys.argv[2], sys.argv[3])
    else:
        apply(sys.argv[2], sys.argv[3], sys.argv[4])
