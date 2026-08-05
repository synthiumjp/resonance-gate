# %%
"""HaluMem QA judge run on Kaggle Benchmarks -- checkpointed against a hard
dollar cap (entry 175).

Upload as a Kaggle notebook with the exported items dataset attached. Re-score
answers RG already composed, using a frontier judge, so the only variable
against the published comparators is the scorer.

Budget discipline is the whole design. Credits are ~$10/day and a full pass is
~2.2M tokens, so a run can plausibly die mid-way:
  * every verdict is appended to /kaggle/working the moment its chunk lands,
    so an interrupted run keeps everything already paid for
  * re-running skips checkpointed ids -- attach the previous run's output as an
    input dataset and it resumes across days
  * cost is read from run.chat.usage after each chunk and the loop stops BEFORE
    the cap, rather than discovering the cap by failing
  * nothing raises: the notebook always reaches the end and saves its output,
    because a crashed notebook can lose /kaggle/working entirely

The judge prompt is NOT built here. It arrives pre-rendered from the official
EVALUATION_PROMPT_FOR_QUESTION by kbench_judge_export.py, so upstream's wording
cannot drift remotely. This side only sends an opaque string and parses the
reply with upstream's own fenced-JSON regex.
"""
import glob
import json
import os
import re

import kaggle_benchmarks as kbench
import pandas as pd

# %%
MODEL = os.environ.get("JUDGE_MODEL", "").strip()
BUDGET_USD = float(os.environ.get("JUDGE_BUDGET_USD", "8.0"))
CHUNK = int(os.environ.get("JUDGE_CHUNK", "25"))
NJOBS = int(os.environ.get("JUDGE_NJOBS", "4"))
MAX_ITEMS = int(os.environ.get("JUDGE_MAX_ITEMS", "0"))

WORK = "/kaggle/working"
CKPT = os.path.join(WORK, "halumem_judge_verdicts.jsonl")
# Upstream's parser: a fenced ```json block is required, and anything else is a
# failure. Kept byte-identical to llms.llm_request_for_json so the frontier
# judge is parsed under exactly the rules the local judge was.
JSON_RX = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _read_jsonl(path):
    out = []
    with open(path) as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


# %%
items = []
for p in sorted(glob.glob("/kaggle/input/**/halumem_judge_items-*.jsonl",
                          recursive=True)):
    items.extend(_read_jsonl(p))
    print(f"items from {p}: {len(items)}")
if not items:
    raise SystemExit("no items dataset attached -- expected "
                     "halumem_judge_items-*.jsonl under /kaggle/input")

# Resume from this session's checkpoint AND from any prior run attached as an
# input dataset, so multi-day runs accumulate instead of restarting.
done = {}
for p in [CKPT] + sorted(glob.glob(
        "/kaggle/input/**/halumem_judge_verdicts*.jsonl", recursive=True)):
    if os.path.exists(p):
        for r in _read_jsonl(p):
            if r.get("item_id") and r.get("verdict"):
                done[r["item_id"]] = r
        print(f"checkpoint {p}: cumulative {len(done)} done")

todo = [it for it in items if it["item_id"] not in done]
if MAX_ITEMS:
    todo = todo[:MAX_ITEMS]
print(f"\ntotal {len(items)} | already judged {len(done)} | to do {len(todo)}")

# Carry prior verdicts into this session's checkpoint so the output file is
# always the complete picture, not just the delta.
if done and not os.path.exists(CKPT):
    with open(CKPT, "w") as f:
        for r in done.values():
            f.write(json.dumps(r) + "\n")

llm = kbench.llms[MODEL] if MODEL else kbench.llm
print(f"judge model: {MODEL or '(default)'}   budget ${BUDGET_USD:.2f}")


# %%
@kbench.task(name="halumem-qa-judge")
def halumem_qa_judge(llm, item_id: str, judge_prompt: str) -> str:
    """One official QA judge call. Returns JSON text so the raw reply survives
    into the checkpoint -- a verdict alone could not be re-audited later."""
    out = llm.prompt(judge_prompt)
    m = JSON_RX.search(out or "")
    if not m:
        return json.dumps({"verdict": "ParseError", "raw": (out or "")[:4000]})
    try:
        parsed = json.loads(m.group(1))
    except Exception as e:
        return json.dumps({"verdict": "ParseError",
                           "raw": (out or "")[:4000], "err": str(e)[:200]})
    return json.dumps({"verdict": parsed.get("evaluation_result") or "None",
                       "reasoning": str(parsed.get("reasoning", ""))[:1500]})


# %%
spent = 0.0
n_new = 0
stopped = None
try:
    for i in range(0, len(todo), CHUNK):
        if spent >= BUDGET_USD:
            stopped = f"budget cap ${BUDGET_USD:.2f} reached"
            break
        chunk = todo[i:i + CHUNK]
        df = pd.DataFrame(chunk)[["item_id", "judge_prompt"]]
        runs = halumem_qa_judge.evaluate(
            evaluation_data=df, llm=[llm], n_jobs=NJOBS,
            on_failure="continue", max_attempts=2,
        )

        with open(CKPT, "a") as f:
            for run in runs:
                params = getattr(run, "params", {}) or {}
                iid = params.get("item_id")
                if not iid:
                    continue
                rec = {"item_id": iid, "model": MODEL or "default"}
                res = getattr(run, "result", None)
                try:
                    payload = json.loads(res) if isinstance(res, str) else {}
                except Exception:
                    payload = {}
                if payload.get("verdict"):
                    rec.update(payload)
                else:
                    # An errored run is recorded WITHOUT a verdict so the resume
                    # logic retries it, instead of freezing a failure as a real
                    # judgement (which would read as judge refusal).
                    rec["error"] = str(getattr(run, "error_message", "") or
                                       "no result")[:300]
                f.write(json.dumps(rec) + "\n")
                if rec.get("verdict"):
                    n_new += 1
            f.flush()
            os.fsync(f.fileno())

        for run in runs:
            u = getattr(getattr(run, "chat", None), "usage", None)
            nd = getattr(u, "total_cost_nanodollars", None) if u else None
            if nd:
                spent += nd / 1e9

        rate = spent / max(n_new, 1)
        remaining = len(items) - len(done) - n_new
        print(f"[{min(i + CHUNK, len(todo))}/{len(todo)}] new={n_new} "
              f"spent=${spent:.3f} (${rate:.4f}/item) "
              f"projected-to-finish=${rate * remaining:.2f}", flush=True)
except Exception as e:
    # Never re-raise: a crashed notebook can lose /kaggle/working, which would
    # throw away verdicts already paid for.
    stopped = f"{type(e).__name__}: {str(e)[:300]}"

# %%
final = {}
for r in _read_jsonl(CKPT):
    if r.get("verdict"):
        final[r["item_id"]] = r
from collections import Counter
tally = Counter(r["verdict"] for r in final.values())
n = len(final)
print(f"\n=== HaluMem QA judge: {n}/{len(items)} judged ===")
print(f"stopped: {stopped or 'completed all todo'}")
print(f"spent this session: ${spent:.3f}")
for k, c in tally.most_common():
    print(f"  {k:14} {c:5}  ({100 * c / max(n, 1):.2f}%)")

pd.DataFrame(list(final.values())).to_csv(
    os.path.join(WORK, "halumem_judge_verdicts.csv"), index=False)
json.dump({"judged": n, "total": len(items), "spent_usd": spent,
           "stopped": stopped, "model": MODEL or "default",
           "tally": dict(tally)},
          open(os.path.join(WORK, "halumem_judge_status.json"), "w"), indent=2)
print(f"\ncheckpoint: {CKPT}")
if n < len(items):
    print(f"INCOMPLETE: {len(items) - n} left. Attach this notebook's output "
          f"as an input dataset and re-run to resume.")
