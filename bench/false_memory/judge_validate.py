"""Validate the judge on the 30 hand-labelled items in judge_items.jsonl
(written before any system output was seen). Reports raw agreement, and
agreement of judge + the lexical pre-filter that score.py uses for classes
a, b, e. Every call goes to results/judge_validation_log.jsonl.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge  # noqa: E402

items = [json.loads(l) for l in open(os.path.join(HERE, "judge_items.jsonl"))]
log = os.path.join(HERE, "results", "judge_validation_log.jsonl")
if os.path.exists(log):
    os.remove(log)
rows = []
for it in items:
    v = judge.ask(it["prop"], it["line"], context="validation", log_path=log)
    # the pre-filter has no question here; use the proposition alone
    pf = judge.lexical_overlap(it["prop"], "", it["line"])
    rows.append({"prop": it["prop"], "line": it["line"], "label": it["label"],
                 "judge": "YES" if v else "NO", "prefilter_passes": pf,
                 "judge_with_prefilter": "YES" if (v and pf) else "NO"})
n = len(rows)
agree = sum(r["judge"] == r["label"] for r in rows)
agree_pf = sum(r["judge_with_prefilter"] == r["label"] for r in rows)
yes = [r for r in rows if r["label"] == "YES"]
no = [r for r in rows if r["label"] == "NO"]
out = {"n": n, "model": judge.MODEL, "agreement": agree / n, "agree": agree,
       "agreement_with_prefilter": agree_pf / n,
       "recall_on_YES": sum(r["judge"] == "YES" for r in yes) / len(yes),
       "specificity_on_NO": sum(r["judge"] == "NO" for r in no) / len(no),
       "n_yes": len(yes), "n_no": len(no),
       "disagreements": [r for r in rows if r["judge"] != r["label"]
                         or r["judge_with_prefilter"] != r["label"]]}
json.dump(out, open(os.path.join(HERE, "results", "judge_validation.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "disagreements"}, indent=1))
for r in out["disagreements"]:
    print("DISAGREE", r)
