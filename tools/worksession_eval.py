"""Facts the parser writes from work-session messages, filters off and on
(2026-10-14; bench/false_memory/cases_dev_worksession.jsonl, a development
set). For every kind except real_fact, any fact is a wrong one; for
real_fact, a message should still give one.

    python tools/worksession_eval.py [--show]
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import rgx  # noqa: E402

cases = [json.loads(l) for l in open(os.path.join(ROOT, "bench", "false_memory",
                                                  "cases_dev_worksession.jsonl")) if l.strip()]
os.environ["RGX_ASSISTANT_CHAT"] = "1"   # chats with an assistant, as in the product
ex = rgx.Extractor(owner_name="Dana Cole")
got = {}
for mode in ("off", "on"):
    os.environ["RGX_WORK_FILTERS"] = "0" if mode == "off" else "1"
    ex.reset_world()
    got[mode] = {c["id"]: [r.text for r in ex.extract_turn(c["message"], "user")] for c in cases}
by = collections.defaultdict(lambda: [0, 0, 0])
for c in cases:
    k = by[c["kind"]]
    k[0] += 1
    k[1] += bool(got["off"][c["id"]])
    k[2] += bool(got["on"][c["id"]])
print("kind: messages; with any fact, filters off -> on (real_fact: higher is right; others: lower)")
for kind in sorted(by):
    n, a, b = by[kind]
    print(f"  {kind:>15}: {n}; {a} -> {b}")
if "--show" in sys.argv:
    for c in cases:
        if got["on"][c["id"]] and c["kind"] != "real_fact":
            print(f"STILL {c['id']} {c['kind']}: {c['message'][:90]!r} -> {got['on'][c['id']]}")
        if c["kind"] == "real_fact" and got["off"][c["id"]] and not got["on"][c["id"]]:
            print(f"LOST  {c['id']}: {c['message'][:90]!r} -> was {got['off'][c['id']]}")
