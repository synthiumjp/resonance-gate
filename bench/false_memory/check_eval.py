"""profile_check against the false-memory sets (2026-10-05).

Each scenario is stored as the benchmark stores it; then every probe's
concrete false claim (`forbid.prop`, e.g. "The user currently lives in
Northcote.") is checked. A false claim must never come back "supported".
Out-of-date claims (class b) should come back "no_longer_true"; negated or
hedged ones (a) "contradicted"; assistant-injected ones (e) "unconfirmed"
or "never_said". With --positives FILE (jsonl: {"id", "q", "claim"}),
true current claims are checked too and should come back "supported".

    FM_CASES=cases_dev_stale2.jsonl python check_eval.py [--positives F] [--counts-only]
"""
import collections
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adapters  # noqa: E402


def main():
    cases = [json.loads(l) for l in open(os.environ.get("FM_CASES") or os.path.join(HERE, "cases.jsonl"))]
    counts_only = "--counts-only" in sys.argv
    pos = {}
    if "--positives" in sys.argv:
        want = os.path.basename(os.environ.get("FM_CASES") or "cases.jsonl")
        for l in open(sys.argv[sys.argv.index("--positives") + 1]):
            r = json.loads(l)
            if r.get("file", want) == want:
                pos.setdefault(r["id"], []).append(r)
    out_path = os.environ.get("CHECK_OUT")
    out = open(out_path, "w") if out_path else None
    tally = collections.Counter()
    for c in cases:
        probes = [p for p in c["probes"] if (p.get("forbid") or {}).get("prop")
                  and not p["forbid"]["prop"].startswith("States ")]
        if not probes and c["id"] not in pos:
            continue
        wd = tempfile.mkdtemp(prefix=f"chk_{c['id']}_", dir=os.environ.get("FM_SCRATCH"))
        ad = adapters.SourcedRecallAdapter(wd)
        ad.ingest(c)
        pm = ad.pm
        for p in probes:
            r = pm.profile_check(p["forbid"]["prop"], scope=ad._scope(p.get("scope")))
            tally[("false", c["class"], r["verdict"] + (f" ({r['since']})" if r.get("since") else ""))] += 1
            if out:
                out.write(json.dumps({"id": c["id"], "kind": "false", "class": c["class"],
                                      "claim": p["forbid"]["prop"], **r}) + "\n")
        for pr in pos.get(c["id"], []):
            r = pm.profile_check(pr["claim"], scope=ad._scope(pr.get("scope")))
            tally[("true", c["class"], r["verdict"] + (f" ({r['since']})" if r.get("since") else ""))] += 1
            if out:
                out.write(json.dumps({"id": c["id"], "kind": "true", "class": c["class"],
                                      "claim": pr["claim"], **r}) + "\n")
    for kind in ("false", "true"):
        rows = {k: v for k, v in tally.items() if k[0] == kind}
        if not rows:
            continue
        print(f"{kind} claims:")
        for cls in sorted({k[1] for k in rows}):
            vs = {k[2]: v for k, v in rows.items() if k[1] == cls}
            print(f"  class {cls}: " + ", ".join(f"{v} {n}" for v, n in sorted(vs.items(), key=lambda x: -x[1])))
        tot = collections.Counter()
        for k, v in rows.items():
            tot[k[2]] += v
        print("  all: " + ", ".join(f"{v} {n}" for v, n in sorted(tot.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
