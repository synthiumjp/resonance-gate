"""Score the raw returns. Rules per class (all in this file):

  a negation / non-assertion   FAIL if any returned line asserts the forbidden proposition
  b stale                      FAIL if any returned line asserts the OLD value as current
  c invention / absence        FAIL if any returned line asserts the forbidden claim
  d attribute absent           FAIL if any returned line asserts the forbidden claim
  e assistant-injected         FAIL if any returned line asserts the forbidden claim
  f controls                   PASS if any expected term appears in the returned lines
                               (deterministic substring match, no judge)

"Asserts" is decided by the local judge (judge.py), one line at a time. For
classes a, b, e a line that shares no content stem with the proposition or the
question is not sent to the judge (verdict: does not assert); classes c and d
send every line.

Metrics (per system, per class, on all scenarios and on the held-out split):
  false-memory rate   share of forbid-probes (classes a-e) where the memory returned
                      something that fails the rule above
  control recall      share of class-f probes whose expected term was returned
  explicit abstention share of class c/d probes where the system returned nothing
  abstention, lenient share of class c/d probes where nothing returned asserted the claim
  true-fact side recall (secondary) share of a/b/e probes that carry an expected term
                      (e.g. the NEW address in a stale scenario) in which it was returned

Bootstrap: percentile 95% CI, cluster resampling over scenarios, seeded.
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge  # noqa: E402

RESULTS = os.environ.get("FM_RESULTS") or os.path.join(HERE, "results")
CASES = os.environ.get("FM_CASES") or os.path.join(HERE, "cases.jsonl")
OVERRIDES = os.environ.get("FM_OVERRIDES") or os.path.join(HERE, "audit_overrides.json")
SEED = 20261002
REPS = 10000
SYSTEMS = ["sourcedrecall", "mem0", "rag"]
PREFILTER_CLASSES = {"a", "b", "e"}
CLASSES = "abcdef"
NAMES = {"a": "a negation/hedge/question", "b": "b stale", "c": "c invention",
         "d": "d attribute absent", "e": "e assistant-injected", "f": "f control"}


def load(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def asserts(cls, prop, question, line, owner, ctx):
    if cls in PREFILTER_CLASSES and not judge.lexical_overlap(prop, question, line):
        return False
    return judge.ask(prop, line, owner, context=ctx)


def score_view(cases, raw, view):
    rows = []
    for c in cases:
        r = raw.get(c["id"])
        for i, p in enumerate(c["probes"]):
            if r is None or "error" in r:
                lines, err = [], True
            else:
                pr = r["probes"][i]
                lines = pr["lines"] if view == "lines" else pr["views"].get(view, [])
                err = False
            row = {"id": c["id"], "class": c["class"], "split": c["split"], "error": err,
                   "empty": not lines, "lines": lines}
            if "forbid" in p:
                prop = p["forbid"]["prop"]
                bad = [l for l in lines if asserts(c["class"], prop, p["q"], l, c["owner"],
                                                   f'{c["id"]}/{p["q"]}')]
                row["fm"] = bool(bad)
                row["bad"] = bad
            if "expect" in p:
                blob = " ".join(lines).lower()
                row["hit"] = any(t.lower() in blob for t in p["expect"]["terms"])
            rows.append(row)
    return rows


def boot(rows, key, seed=SEED):
    """mean of key over rows (those where key is present) with cluster bootstrap CI."""
    rows = [r for r in rows if key(r) is not None]
    if not rows:
        return None
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(1.0 if key(r) else 0.0)
    ids = list(by)
    n = sum(len(v) for v in by.values())
    m = sum(sum(v) for v in by.values()) / n
    rng = random.Random(seed)
    sums = [(sum(v), len(v)) for v in by.values()]
    vals = []
    for _ in range(REPS):
        s = k = 0
        for _ in ids:
            a, b = sums[rng.randrange(len(sums))]
            s += a
            k += b
        vals.append(s / k)
    vals.sort()
    return {"rate": m, "lo": vals[int(0.025 * REPS)], "hi": vals[int(0.975 * REPS) - 1],
            "n": n, "k": int(sum(sum(v) for v in by.values()))}


def metrics(rows):
    out = {}
    for split in ("all", "heldout"):
        sub = [r for r in rows if split == "all" or r["split"] == "heldout"]
        m = {}
        m["false_memory_all"] = boot([r for r in sub if r["class"] in "abcde"],
                                     lambda r: r.get("fm"))
        for c in "abcde":
            m[f"false_memory_{c}"] = boot([r for r in sub if r["class"] == c],
                                          lambda r: r.get("fm"))
        m["control_recall"] = boot([r for r in sub if r["class"] == "f"], lambda r: r.get("hit"))
        cd = [r for r in sub if r["class"] in "cd"]
        m["abstain_explicit_cd"] = boot(cd, lambda r: r["empty"])
        m["abstain_lenient_cd"] = boot(cd, lambda r: (not r["fm"]) if "fm" in r else None)
        m["side_recall_abe"] = boot([r for r in sub if r["class"] in "abe"], lambda r: r.get("hit"))
        out[split] = m
    return out


def _k(line):
    """Match key: the fact text without the quote/date suffix (the context
    view formats the suffix differently from the recall view)."""
    return line.split(" [")[0].strip()


def apply_overrides(rows, system):
    """Manual audit of judge errors, see audit_overrides.json."""
    ov = [o for o in json.load(open(OVERRIDES))["overrides"]
          if o["system"] == system]
    out = []
    for r in rows:
        r = dict(r)
        for o in ov:
            if o["id"] != r["id"] or "fm" not in r:
                continue
            if o["fm"] is False and any(_k(b) == _k(o["line"]) for b in r["bad"]):  # judge false positive
                r["bad"] = [b for b in r["bad"] if _k(b) != _k(o["line"])]
                r["fm"] = bool(r["bad"])
            elif o["fm"] is True and any(_k(b) == _k(o["line"]) for b in r["lines"]):  # judge false negative
                r["fm"] = True
        out.append(r)
    return out


def ingest_cost(raw):
    msgs = sum(r["ingest"]["messages"] for r in raw.values() if "ingest" in r)
    calls = sum(r["ingest"]["model_calls"] for r in raw.values() if "ingest" in r)
    secs = sum(r["ingest"]["seconds"] for r in raw.values() if "ingest" in r)
    return {"messages": msgs, "model_calls": calls, "seconds": round(secs, 1),
            "calls_per_message": round(calls / msgs, 3) if msgs else None,
            "seconds_per_message": round(secs / msgs, 3) if msgs else None,
            "scenarios_with_error": sum(1 for r in raw.values() if "error" in r)}


def pct(x):
    if x is None:
        return "n/a"
    return f'{100 * x["rate"]:.0f}% [{100 * x["lo"]:.0f}-{100 * x["hi"]:.0f}] ({x["k"]}/{x["n"]})'


def main():
    cases = load(CASES)
    result = {"seed": SEED, "bootstrap_reps": REPS, "judge_model": judge.MODEL,
              "systems": {}}
    print("bootstrap seed", SEED, "reps", REPS)
    details = []
    for s in SYSTEMS:
        raw = {r["id"]: r for r in load(os.path.join(RESULTS, f"raw_{s}.jsonl"))}
        if not raw:
            continue
        views = ["lines"] + (["context"] if s == "sourcedrecall" else [])
        # the answer view (answer.py): the reader's answer, judged as one line
        ans = {r["id"]: r["answers"] for r in
               load(os.path.join(RESULTS, f"answers_{s}.jsonl"))}
        for cid, al in ans.items():
            for pr, a in zip((raw.get(cid) or {}).get("probes") or [], al):
                pr.setdefault("views", {})["answer"] = [a] if a else []
        if ans:
            views.append("answer")
        result["systems"][s] = {"ingest_cost": ingest_cost(raw), "views": {},
                                "views_audited": {}}
        for v in views:
            rows = score_view(cases, raw, v)
            arows = apply_overrides(rows, s)
            result["systems"][s]["views"][v] = metrics(rows)
            result["systems"][s]["views_audited"][v] = metrics(arows)
            details += [dict(r, system=s, view=v, fm_audited=a.get("fm"))
                        for r, a in zip(rows, arows)]
            print(s, v, "scored", flush=True)
    result["n_scenarios"] = len(cases)
    result["n_heldout"] = sum(c["split"] == "heldout" for c in cases)
    json.dump(result, open(os.path.join(RESULTS, "results.json"), "w"), indent=1)
    with open(os.path.join(RESULTS, "probe_details.jsonl"), "w") as f:
        for d in details:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    write_md(result)


COLS = [("false_memory_all", "FALSE-MEMORY RATE, classes a-e (lower is better)"),
        ("false_memory_a", "a negation/hedge/question"), ("false_memory_b", "b stale"),
        ("false_memory_c", "c invention"), ("false_memory_d", "d attribute absent"),
        ("false_memory_e", "e assistant-injected"),
        ("control_recall", "CONTROL RECALL, class f (higher is better)"),
        ("abstain_explicit_cd", "explicit abstention, c+d (returned nothing)"),
        ("abstain_lenient_cd", "no false assertion, c+d"),
        ("side_recall_abe", "true-fact side recall, a/b/e (secondary)")]


def _tables(res, vk):
    L = []
    for split, title in (("all", "All scenarios"), ("heldout", "Held-out split")):
        L += [f"### {title}", "", "| metric | " + " | ".join(
            f"{s}{'' if v == 'lines' else ' (' + v + ' block)'}"
            for s in res["systems"] for v in res["systems"][s][vk]) + " |",
              "|---|" + "---|" * sum(len(res["systems"][s][vk]) for s in res["systems"])]
        for key, label in COLS:
            cells = [pct(res["systems"][s][vk][v][split][key])
                     for s in res["systems"] for v in res["systems"][s][vk]]
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        L.append("")
    return L


def write_md(res):
    L = []
    for vk, heading in (("views", "A. Judge verdicts as produced"),
                        ("views_audited", "B. After manual audit of judge errors (audit_overrides.json)")):
        L += [f"## {heading}", ""] + _tables(res, vk)
    L += ["## Ingest cost", "",
          "| system | messages | model calls | calls/message | seconds | seconds/message |",
          "|---|---|---|---|---|---|"]
    for s, d in res["systems"].items():
        c = d["ingest_cost"]
        L.append(f'| {s} | {c["messages"]} | {c["model_calls"]} | {c["calls_per_message"]} | '
                 f'{c["seconds"]} | {c["seconds_per_message"]} |')
    L += ["", f'Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed {res["seed"]}, '
              f'{res["bootstrap_reps"]} resamples. Judge: {res["judge_model"]}, temperature 0.']
    open(os.path.join(RESULTS, "results.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
