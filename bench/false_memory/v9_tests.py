"""Held-out v9, the hypotheses as pre-registered (docs/PREREG_HELDOUT_V9.md),
from probe_details.jsonl (answer view, audited). Counts only.

    FM_CASES=cases_v9.jsonl FM_RESULTS=results_v9 python v9_tests.py
"""
import collections
import json
import os

from fair_summary import fisher

HERE = os.path.dirname(os.path.abspath(__file__))
cases = {json.loads(l)["id"]: json.loads(l) for l in open(os.environ.get("FM_CASES") or
                                                        os.path.join(HERE, "cases_v9.jsonl"))}
res = os.environ.get("FM_RESULTS") or os.path.join(HERE, "results_v9")
# (system, part, class) -> [false memories, forbid probes, hits, expect probes]
t = collections.defaultdict(lambda: [0, 0, 0, 0])
for l in open(os.path.join(res, "probe_details.jsonl")):
    d = json.loads(l)
    if d["view"] != "answer":
        continue
    c = cases[d["id"]]
    part = c["subtype"][:1]
    if part == "U":             # facts in pasted text: does the question name the source?
        part = "N" if c["subtype"].startswith("U_named") else "M"
    x = t[(d["system"], part, d.get("class") or c["class"])]
    if "fm" in d:
        x[0] += bool(d.get("fm_audited"))
        x[1] += 1
    if "hit" in d:
        x[2] += bool(d["hit"])
        x[3] += 1
systems = sorted({s for s, _, _ in t}, key=lambda s: (s != "sourcedrecall", s))


def cell(s, part, cls, which):
    v = t.get((s, part, cls), [0, 0, 0, 0])
    return (v[0], v[1]) if which == "fm" else (v[2], v[3])


def pooled(s, parts):
    k = n = 0
    for (s2, part, cls), v in t.items():
        if s2 == s and part in parts and cls in "abcde":
            k, n = k + v[0], n + v[1]
    return k, n


def row(name, get, lower_better=True):
    ours = get("sourcedrecall")
    out = []
    for s in systems:
        k, n = get(s)
        c = f"{s} {k}/{n}"
        if s != "sourcedrecall" and n and ours[1]:
            c += f" (p={fisher(ours[0], ours[1], k, n):.2f})"
        out.append(c)
    print(f"{name}: " + "; ".join(out))


row("H1/H2 D pasted given as the user's (class e, false memory)", lambda s: cell(s, "D", "e", "fm"))
row("H1 D own material answered (class f, expected term)", lambda s: cell(s, "D", "f", "hit"))


def both(s):
    a, b = cell(s, "N", "f", "hit"), cell(s, "M", "f", "hit")
    return a[0] + b[0], a[1] + b[1]


row("H3 U facts in pasted text answered, all (class f, expected term)", both)
row("H3 U source named in the question", lambda s: cell(s, "N", "f", "hit"))
row("H3 U source not named in the question", lambda s: cell(s, "M", "f", "hit"))
row("H4 B old state given as current (class b, false memory)", lambda s: cell(s, "B", "b", "fm"))
row("H5 X everyday facts answered (class f, expected term)", lambda s: cell(s, "X", "f", "hit"))
row("H6 pooled false memories over D and B (classes a-e)", lambda s: pooled(s, "DB"))
