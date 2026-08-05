"""Drive the HaluMem QA judge over Kaggle Benchmarks from this machine.

Same measurement as kbench_judge_task.py, but run locally instead of as a
Kaggle notebook. Local turned out to be viable once `kaggle b auth` writes a
model-proxy key: a full 1,764-item pass is ~20 min at n_jobs=8, well inside the
credential's 1-hour life. The notebook variant stays for multi-day runs.

Budget is the binding constraint (~$10/day), so this is built to spend it in
stages rather than all at once:
  * --n with --stratify draws a proportional sample across question types, so a
    cheap subset still answers the question for every type
  * every verdict is appended and fsync'd immediately -- an interrupted run
    keeps everything already paid for
  * --budget stops the loop BEFORE the cap, checked between chunks
  * re-running skips checkpointed items, so stage 2 only pays for the remainder

Measured rate on gemini-3.6-flash: $0.00399/item, so ~$1.20 for 300 items and
~$7.04 for all 1,764.

  set -a; . ~/rg_private/kaggle.env; LLM_DEFAULT=gemini-3.6-flash; set +a
  python kbench_judge_run.py --items <exported.jsonl> --n 300 --budget 1.50
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

JSON_RX = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def stratified(items, n):
    """Proportional sample across question types.

    A uniform head-slice would over-weight whichever users happen to sort
    first; the judge effect could plausibly differ by question type (Memory
    Boundary is nearly all abstentions, Multi-hop nearly none), so every type
    has to be represented in proportion or a cheap subset cannot stand in for
    the full set."""
    if not n or n >= len(items):
        return items
    by = defaultdict(list)
    for it in items:
        by[it.get("question_type", "?")].append(it)
    out = []
    for qt, group in sorted(by.items()):
        take = max(1, round(n * len(group) / len(items)))
        out.extend(group[:take])
    return out[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--model", default=os.environ.get("LLM_DEFAULT", ""))
    ap.add_argument("--n", type=int, default=0, help="sample size (0 = all)")
    ap.add_argument("--stratify", action="store_true", default=True)
    ap.add_argument("--budget", type=float, default=1.50, help="hard USD cap")
    ap.add_argument("--chunk", type=int, default=25)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()

    import kaggle_benchmarks as kbench
    import pandas as pd

    items = read_jsonl(os.path.expanduser(args.items))
    if not items:
        sys.exit(f"no items in {args.items}")
    pool = stratified(items, args.n) if args.stratify else items[:args.n or None]

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.expanduser(args.items)),
        f"verdicts-{(args.model or 'default').replace('/', '_')}.jsonl")
    done = {r["item_id"]: r for r in read_jsonl(out_path) if r.get("verdict")}
    todo = [it for it in pool if it["item_id"] not in done]

    print(f"model   : {args.model or '(default)'}")
    print(f"pool    : {len(pool)} of {len(items)}  "
          f"({'stratified' if args.stratify and args.n else 'all'})")
    print(f"done    : {len(done)}   todo: {len(todo)}   budget: ${args.budget:.2f}")
    if not todo:
        print("nothing to do")
    print(f"out     : {out_path}\n")

    llm = kbench.kaggle.load_model(args.model) if args.model else kbench.llm

    @kbench.task(name="halumem-qa-judge", store_task=False, store_run=False)
    def judge(llm, item_id: str, judge_prompt: str) -> dict:
        out = llm.prompt(judge_prompt)
        m = JSON_RX.search(out or "")
        if not m:
            return {"verdict": "ParseError", "raw": (out or "")[:2000]}
        try:
            p = json.loads(m.group(1))
        except Exception as e:
            return {"verdict": "ParseError", "raw": (out or "")[:2000],
                    "err": str(e)[:200]}
        return {"verdict": p.get("evaluation_result") or "None",
                "reasoning": str(p.get("reasoning", ""))[:1500]}

    spent, n_new, stopped = 0.0, 0, None
    try:
        for i in range(0, len(todo), args.chunk):
            if spent >= args.budget:
                stopped = f"budget cap ${args.budget:.2f}"
                break
            chunk = todo[i:i + args.chunk]
            df = pd.DataFrame(chunk)[["item_id", "judge_prompt"]]
            runs = judge.evaluate(evaluation_data=df, llm=[llm],
                                  n_jobs=args.jobs, on_failure="continue",
                                  max_attempts=2)
            with open(out_path, "a") as f:
                for run in runs:
                    iid = (getattr(run, "params", {}) or {}).get("item_id")
                    if not iid:
                        continue
                    res = getattr(run, "result", None)
                    payload = res if isinstance(res, dict) else {}
                    rec = {"item_id": iid, "model": args.model or "default"}
                    if payload.get("verdict") and payload["verdict"] != "ParseError":
                        rec.update(payload)
                        n_new += 1
                    else:
                        rec["error"] = str(getattr(run, "error_message", "") or
                                           payload.get("verdict") or "no result")[:300]
                        if payload.get("raw"):
                            rec["raw"] = payload["raw"][:1000]
                    f.write(json.dumps(rec) + "\n")
                f.flush()
                os.fsync(f.fileno())
            for run in runs:
                u = getattr(getattr(run, "chat", None), "usage", None)
                nd = getattr(u, "total_cost_nanodollars", None) if u else None
                if nd:
                    spent += nd / 1e9
            rate = spent / max(n_new, 1)
            left = len(todo) - min(i + args.chunk, len(todo))
            print(f"[{min(i + args.chunk, len(todo))}/{len(todo)}] "
                  f"ok={n_new} spent=${spent:.3f} (${rate:.5f}/item) "
                  f"rest-of-pool=${rate * left:.2f}", flush=True)
    except KeyboardInterrupt:
        stopped = "interrupted"
    except Exception as e:
        stopped = f"{type(e).__name__}: {str(e)[:200]}"

    final = {r["item_id"]: r for r in read_jsonl(out_path) if r.get("verdict")}
    tally = Counter(r["verdict"] for r in final.values())
    n = len(final)
    print(f"\n=== {n}/{len(pool)} of pool judged ===")
    print(f"stopped : {stopped or 'completed'}")
    print(f"spent   : ${spent:.3f}")
    for k, c in tally.most_common():
        print(f"  {k:14} {c:5}  ({100 * c / max(n, 1):.2f}%)")
    print(f"\nverdicts: {out_path}")
    print("compare with:\n  judge_frontier.py --results <dir> "
          f"--import-verdicts {out_path}")


if __name__ == "__main__":
    main()
