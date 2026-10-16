"""LoCoMo with Claude as reader and judge (2026-10-16): the same stored
retrievals (ctx_<system>.jsonl) and the same reader and judge prompts as
answer.py, read and judged by Claude through the Batch API. Writes
<out>/ans_<system>.jsonl and copies the ctx files, so score.py reads <out>
as it reads a local run.

    python answer_claude.py results/release_test_default results/claude_test_default \\
        sourcedrecall mem0 rag [--reader claude-sonnet-5-5] [--judge claude-sonnet-5-5]
"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common as C  # noqa: E402
from claude_batch import run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("systems", nargs="+")
    ap.add_argument("--reader", default="claude-sonnet-5-5")
    ap.add_argument("--judge", default="claude-sonnet-5-5")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = {}
    for s in a.systems:
        shutil.copy(os.path.join(a.src, f"ctx_{s}.jsonl"), os.path.join(a.out, f"ctx_{s}.jsonl"))
        for i, r in enumerate(C.jsonl_read(os.path.join(a.out, f"ctx_{s}.jsonl"))):
            rows[f"{s}-{i}"] = (s, r)
    preds = run({k: C.READER.format(context=r["context"], question=r["question"])
                 for k, (s, r) in rows.items()}, a.reader, 300, os.path.join(a.out, "reader_batch.json"))
    judged = run({k: C.JUDGE.format(question=r["question"], gold=r["answer"], pred=preds[k])
                  for k, (s, r) in rows.items()}, a.judge, 300, os.path.join(a.out, "judge_batch.json"))
    for s in a.systems:
        path = os.path.join(a.out, f"ans_{s}.jsonl")
        if os.path.exists(path):
            os.unlink(path)
    for k, (s, r) in rows.items():
        C.jsonl_append(os.path.join(a.out, f"ans_{s}.jsonl"), {
            "qid": r["qid"], "system": s, "category": r["category"], "question": r["question"],
            "gold": r["answer"], "pred": preds[k], "judge_text": judged[k],
            "label": C.judge_label(judged[k]), "reader": a.reader, "judge": a.judge})


if __name__ == "__main__":
    main()
