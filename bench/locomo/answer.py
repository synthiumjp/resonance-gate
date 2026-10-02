"""Reader and judge over the stored retrievals. Resumable: one line per
(system, question) in <out>/ans_<system>.jsonl.

    python answer.py rag sourcedrecall mem0 --out results/test
Uses LOCOMO_LLM_BASE / LOCOMO_LLM_MODEL (default: local Ollama qwen3:14b)."""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+")
    ap.add_argument("--out", default=os.path.join(C.RESULTS, "test"))
    a = ap.parse_args()
    for sysname in a.systems:
        ansf = os.path.join(a.out, f"ans_{sysname}.jsonl")
        done = {r["qid"] for r in C.jsonl_read(ansf)}
        rows = [r for r in C.jsonl_read(os.path.join(a.out, f"ctx_{sysname}.jsonl")) if r["qid"] not in done]
        print(sysname, len(rows), "to answer", flush=True)
        for i, r in enumerate(rows):
            t0 = time.time()
            pred = C.llm(C.READER.format(context=r["context"], question=r["question"]), max_tokens=120)
            t1 = time.time()
            j = C.llm(C.JUDGE.format(question=r["question"], gold=r["answer"], pred=pred), max_tokens=120)
            C.jsonl_append(ansf, {"qid": r["qid"], "system": sysname, "category": r["category"],
                                  "question": r["question"], "gold": r["answer"], "pred": pred,
                                  "judge_text": j, "label": C.judge_label(j),
                                  "reader_s": t1 - t0, "judge_s": time.time() - t1})
            if i % 25 == 0:
                print(f"  {sysname} {i}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
