"""Change-of-state handling on the readable dev set (2026-10-03).

    python tools/stale_dev.py [--misses]

bench/false_memory/cases_dev_stale.jsonl: 50 scenarios where a later
conversation changes something said earlier. For each question it reports:
  new   a returned line carries the NEW state (one of the expected terms);
  stale a line from an EARLIER conversation came back still marked current.
"stale" is an approximation (an unrelated old fact also counts); --misses
prints both kinds for reading. This set is for TUNING; measure on a blind
set before believing a gain.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(_ROOT, "bench", "false_memory", "cases_dev_stale.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--misses", action="store_true")
    ap.add_argument("--facts", action="store_true",
                    help="with --misses: also list every stored fact")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(_ROOT, "server"))
    os.environ.setdefault("RG_NLI", "0")
    import sourcedrecall.profile_memory as pm
    cases = [json.loads(l) for l in open(CASES)]
    tot = new_ok = stale_n = 0
    report = []
    for c in cases:
        d = tempfile.mkdtemp(prefix="rg-stale-")
        os.environ["RG_MEMORY_DIR"] = d
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": None, "owner": None})
        dates = []
        for i, cv in enumerate(c["conversations"]):
            pm.profile_ingest(cv["turns"], conversation_id=f"{c['id']}-{i}",
                              owner_name=c["owner"], date=cv.get("date"))
            dates.append(cv.get("date"))
        last = max(x for x in dates if x)
        for p in c["probes"]:
            r = pm.profile_recall(p["q"])
            fs = (r.get("ranked") or []) + (r.get("related") or [])
            terms = (p.get("expect") or {}).get("terms") or []
            got_new = any(t in f"{f.get('text')} {f.get('said') or ''}".lower()
                          for f in fs for t in terms)
            old_current = [f for f in fs if f.get("current") is not False
                           and not f.get("changed_later")
                           and str((f.get("receipts") or [{}])[0].get("date") or "")[:10]
                           < str(last)[:10]]
            tot += 1
            new_ok += got_new
            stale_n += bool(old_current)
            if not got_new or old_current:
                stored = []
                if a.facts:
                    mem = pm._ensure_loaded()
                    stored = [f"{f.get('_tier')}{'' if f.get('current') is not False else ' GONE'}: {f.get('text')}"
                              for f in pm._all_facts(mem)]
                said = [f"[{cv.get('date')}] " + " / ".join(
                    t["content"] for t in cv["turns"] if t["role"] == "user")
                    for cv in c["conversations"]]
                report.append((c["id"], p["q"], terms, got_new,
                               [f.get("text") for f in old_current][:2],
                               [f.get("text") for f in fs][:3], said, stored))
        shutil.rmtree(d, ignore_errors=True)
    print(f"new state returned {new_ok}/{tot}   old line still current {stale_n}/{tot}")
    if a.misses:
        for cid, q, terms, ok, old, got, said, stored in report:
            print(f"\n{cid} Q: {q}  expect {terms}  new={'yes' if ok else 'NO'}")
            if old:
                print(f"   STALE: {old}")
            print(f"   got: {got}")
            for s in said:
                print(f"   said {s[:200]}")
            for s in stored:
                print(f"   stored {s[:200]}")


if __name__ == "__main__":
    main()
