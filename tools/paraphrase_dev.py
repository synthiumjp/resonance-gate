"""Paraphrase recall on the readable dev set (2026-10-03).

    python tools/paraphrase_dev.py [--related] [--misses]

bench/false_memory/cases_dev_paraphrase.jsonl: 60 scenarios, 64 questions
worded differently from what the user said. A question counts as found when
a returned line contains one of its expected terms. --related also counts
the labelled "possibly related" candidates returned when nothing was
confirmed (what the agent sees); without it only confirmed answers count.
This set is for TUNING; measure on a blind set before believing a gain.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(_ROOT, "bench", "false_memory", "cases_dev_paraphrase.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--related", action="store_true")
    ap.add_argument("--misses", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(_ROOT, "server"))
    os.environ.setdefault("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm
    cases = [json.loads(l) for l in open(CASES)]
    hit = conf = tot = 0
    misses = []
    for c in cases:
        d = tempfile.mkdtemp(prefix="rg-para-")
        os.environ["RG_MEMORY_DIR"] = d
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": None, "owner": None})
        for i, cv in enumerate(c["conversations"]):
            pm.profile_ingest(cv["turns"], conversation_id=f"{c['id']}-{i}",
                              owner_name=c["owner"], date=cv.get("date"))
        for p in c["probes"]:
            r = pm.profile_recall(p["q"])
            terms = p["expect"]["terms"]
            ranked = r.get("ranked") or []
            rel = r.get("related") or []

            def has(fs):
                return any(t in f"{f.get('text')} {f.get('said') or ''}".lower()
                           for f in fs for t in terms)
            tot += 1
            c_ok = has(ranked)
            ok = c_ok or (a.related and has(rel))
            conf += c_ok
            hit += ok
            if not ok:
                misses.append((c["id"], p["q"], terms, r.get("gate"),
                               [f.get("text") for f in (ranked or rel)][:3]))
        shutil.rmtree(d, ignore_errors=True)
    print(f"confirmed {conf}/{tot}" + (f"   with candidates {hit}/{tot}" if a.related else ""))
    if a.misses:
        for m in misses:
            print(f"  {m[0]} {m[1]}  expect {m[2]}  gate={m[3]}\n      got {m[4]}")


if __name__ == "__main__":
    main()
