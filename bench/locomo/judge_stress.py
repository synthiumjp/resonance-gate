"""How lenient is our LoCoMo judge? The LoCoMo audit (fetch_audit.sh) has
two sets of deliberately wrong answers to every question: v1 specific but
wrong, v2 vague but on topic. A good judge accepts close to none; the audit
found gpt-4o-mini with this prompt accepted 10.6% and 62.8%. Judged here with
our judge (C.JUDGE, LOCOMO_LLM_BASE / LOCOMO_LLM_MODEL) on the test
conversations (2-9), categories 1-4. Resumable.

    python judge_stress.py [--n 0] [--out results/judge_stress.jsonl]"""
import argparse
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def wrong_answers(v):
    r = json.load(open(os.path.join(C.RESULTS, f"locomo_audit_ap_{v}.json")))["detailed_results"]
    out = {}
    for rows in r.values():
        for x in rows:
            c = int(x["question_id"].split("_")[1])
            if c >= 2 and str(x["category"]) in "1234":
                out[(c, x["question"].strip())] = x["generated_answer"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="a random sample of this many questions (0 = all)")
    ap.add_argument("--out", default=os.path.join(C.RESULTS, "judge_stress.jsonl"))
    a = ap.parse_args()
    # gold answers from our own data, the same rows the systems were judged on
    rows = {(int(r["qid"].split(":")[0]), r["question"].strip()): r
            for r in C.jsonl_read(os.path.join(C.RESULTS, "test", "ctx_rag.jsonl"))}
    done = {(r["v"], r["qid"]) for r in C.jsonl_read(a.out)}
    for v in ("v1", "v2"):
        wa = wrong_answers(v)
        keys = sorted(k for k in rows if k in wa)
        if a.n:
            keys = random.Random(20261009).sample(keys, min(a.n, len(keys)))
        print(v, len(keys), "questions", flush=True)
        for i, k in enumerate(keys):
            r = rows[k]
            if (v, r["qid"]) in done:
                continue
            j = C.llm(C.judge_prompt().format(question=r["question"], gold=r["answer"], pred=wa[k]), max_tokens=120)
            C.jsonl_append(a.out, {"v": v, "qid": r["qid"], "category": r["category"],
                                   "label": C.judge_label(j), "judge_text": j})
            if i % 50 == 0:
                print(f"  {v} {i}/{len(keys)}", flush=True)
    res = C.jsonl_read(a.out)
    for v in ("v1", "v2"):
        rs = [r for r in res if r["v"] == v]
        k = sum(r["label"] == "CORRECT" for r in rs)
        cat = Counter(r["category"] for r in rs if r["label"] == "CORRECT")
        print(f"{v}: wrong answers judged CORRECT {k}/{len(rs)} = {100 * k / max(1, len(rs)):.1f}%  by category {dict(sorted(cat.items()))}")


if __name__ == "__main__":
    main()
