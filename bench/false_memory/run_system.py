"""Run ONE system over the cases and write raw returns to
results/raw_<system>.jsonl (one line per scenario; resumable).

    python run_system.py sourcedrecall|mem0|rag [--split dev|heldout|all] [--ids a01,b02]

Each system must be run in its own Python environment (see README).
No judging happens here; this file only stores what the system returned.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adapters  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("system", choices=["sourcedrecall", "mem0", "rag"])
    ap.add_argument("--split", default="all")
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--scratch", default=os.environ.get("FM_SCRATCH", tempfile.gettempdir()))
    a = ap.parse_args()
    cls = {"sourcedrecall": adapters.SourcedRecallAdapter, "mem0": adapters.Mem0Adapter,
           "rag": adapters.RagAdapter}[a.system]
    out = a.out or os.path.join(HERE, "results", f"raw_{a.system}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    done = set()
    if os.path.exists(out):
        done = {json.loads(l)["id"] for l in open(out)}
    cases = [json.loads(l) for l in open(os.path.join(HERE, "cases.jsonl"))]
    want = set(a.ids.split(",")) if a.ids else None
    for c in cases:
        if want and c["id"] not in want:
            continue
        if a.split != "all" and c["split"] != a.split:
            continue
        if c["id"] in done:
            continue
        wd = tempfile.mkdtemp(prefix=f"fm_{a.system}_{c['id']}_", dir=a.scratch)
        t0 = time.time()
        rec = {"id": c["id"], "system": a.system}
        if a.system == "sourcedrecall":
            import subprocess
            rec["rg_repo"] = adapters.REPO
            rec["rg_commit"] = subprocess.run(
                ["git", "-C", adapters.REPO, "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True).stdout.strip()
        try:
            ad = cls(wd)
            rec["ingest"] = ad.ingest(c)
            rec["probes"] = []
            for p in c["probes"]:
                t1 = time.time()
                r = ad.query(p["q"])
                r["q"] = p["q"]
                r["query_seconds"] = round(time.time() - t1, 3)
                rec["probes"].append(r)
            if hasattr(ad, "dump"):
                rec["stored"] = ad.dump()
        except Exception:
            rec["error"] = traceback.format_exc()
        rec["wall"] = round(time.time() - t0, 2)
        with open(out, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(c["id"], a.system, "error" if "error" in rec else "ok", rec["wall"], "s", flush=True)
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()
