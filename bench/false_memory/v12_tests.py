"""Held-out v12, the hypotheses as pre-registered (docs/PREREG_HELDOUT_V12.md),
from probe_details.jsonl (answer view, audited). Counts only.

    FM_CASES=cases_v12.jsonl FM_RESULTS=results_v12 python v12_tests.py
    FM_CASES=cases_v12.jsonl FM_RESULTS=results_v12_phi4 python v12_tests.py

The second line is the same set read by the second reader (Phi-4): H1, H3,
H4 and H10 are tested on both (H9), the rest on the first reader (Qwen3-14B).
Part R holds real emails (H10-H12); own items with subtype D_read_ (the
user's writing brought to be read over) are reported as their own row.
"""
import collections
import json
import os
import re

from fair_summary import fisher

HERE = os.path.dirname(os.path.abspath(__file__))
cases = {json.loads(l)["id"]: json.loads(l) for l in open(os.environ.get("FM_CASES") or
                                                        os.path.join(HERE, "cases_v12.jsonl"))}
res = os.environ.get("FM_RESULTS") or os.path.join(HERE, "results_v12")
# an answer that says the memory does not hold it (reported, not tested)
_DONT_KNOW = re.compile(
    r"\b(?:don't|do not|doesn't|does not|didn't|did not) (?:know|say|mention|have|provide|specify|state)\b|"
    r"\bnot (?:mentioned|provided|specified|stated|known|clear)\b|\bno (?:information|mention|record)\b|"
    r"\bI'm not sure\b|\bunknown\b|\bnot in (?:the|your) memory\b", re.I)
# (system, part, class) -> [false memories, forbid probes, hits, expect probes, said it did not know, answers]
t = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0])
for l in open(os.path.join(res, "probe_details.jsonl")):
    d = json.loads(l)
    if d["view"] != "answer":
        continue
    c = cases[d["id"]]
    part = c["subtype"][:1]
    if c["subtype"].startswith("D_read_") and (d.get("class") or c["class"]) == "f":
        y = t[(d["system"], "W", "f")]   # own writing brought to be read over (reported)
        if "hit" in d:
            y[2] += bool(d["hit"])
            y[3] += 1
        y[4] += bool(_DONT_KNOW.search((d.get("lines") or [""])[0]))
        y[5] += 1
    if part == "U":             # facts in pasted text: does the question name the source?
        part = "N" if c["subtype"].startswith("U_named") else "M"
    x = t[(d["system"], part, d.get("class") or c["class"])]
    if "fm" in d:
        x[0] += bool(d.get("fm_audited"))
        x[1] += 1
    if "hit" in d:
        x[2] += bool(d["hit"])
        x[3] += 1
    x[4] += bool(_DONT_KNOW.search((d.get("lines") or [""])[0]))
    x[5] += 1
systems = sorted({s for s, _, _ in t}, key=lambda s: (s != "sourcedrecall", s))
pvals = []


def cell(s, part, cls, which):
    v = t.get((s, part, cls), [0] * 6)
    return {"fm": (v[0], v[1]), "hit": (v[2], v[3]), "dk": (v[4], v[5])}[which]


def pooled(s, parts):
    k = n = 0
    for (s2, part, cls), v in t.items():
        if s2 == s and part in parts and cls in "abcde":
            k, n = k + v[0], n + v[1]
    return k, n


def row(name, get, test=()):
    ours = get("sourcedrecall")
    out = []
    for s in systems:
        k, n = get(s)
        c = f"{s} {k}/{n}"
        if s != "sourcedrecall" and n and ours[1]:
            p = fisher(ours[0], ours[1], k, n)
            c += f" (p={p:.2g})"
            if s in test:
                pvals.append((f"{name.split()[0]} vs {s}", p))
        out.append(c)
    print(f"{name}: " + "; ".join(out))


row("H1/H2 D pasted given as the user's (class e, false memory)", lambda s: cell(s, "D", "e", "fm"),
    test=("rag", "agentmemory"))
row("H3/H4 D own material answered (class f, expected term)", lambda s: cell(s, "D", "f", "hit"))


def both(s):
    a, b = cell(s, "N", "f", "hit"), cell(s, "M", "f", "hit")
    return a[0] + b[0], a[1] + b[1]


row("H5 U facts in pasted text answered, all (class f, expected term)", both)
row("H5 U source named in the question", lambda s: cell(s, "N", "f", "hit"))
row("H5 U source not named in the question", lambda s: cell(s, "M", "f", "hit"))
row("H6 B old state given as current (class b, false memory)", lambda s: cell(s, "B", "b", "fm"))
row("H7 X everyday facts answered (class f, expected term)", lambda s: cell(s, "X", "f", "hit"))
row("H8 pooled false memories over D and B (classes a-e)", lambda s: pooled(s, "DB"),
    test=("rag", "agentmemory"))
row("H10/H11 R real pasted given as the user's (class e, false memory)", lambda s: cell(s, "R", "e", "fm"),
    test=("rag",))
row("H12 R real own email answered (class f, expected term)", lambda s: cell(s, "R", "f", "hit"))
row("reported: D own writing brought to be read over, answered", lambda s: cell(s, "W", "f", "hit"))
print("Holm over the five Fisher tests of H2, H8 and H11 (adjusted p):")
m = len(pvals)
adj, run = {}, 0.0
for i, (name, p) in enumerate(sorted(pvals, key=lambda z: z[1])):
    run = max(run, min(1.0, (m - i) * p))
    adj[name] = run
for name, p in pvals:
    print(f"  {name}: p={p:.2g}, Holm {adj[name]:.2g}")
print("said it did not know (reported, not tested), per part, all classes:")
for part in "DNMBXR":
    cells = []
    for s in systems:
        k = n = 0
        for (s2, p2, _), v in t.items():
            if s2 == s and p2 == part:
                k, n = k + v[4], n + v[5]
        cells.append(f"{s} {k}/{n}")
    print(f"  {part}: " + "; ".join(cells))
