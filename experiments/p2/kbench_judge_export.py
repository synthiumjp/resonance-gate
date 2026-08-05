"""Render the official HaluMem QA judge prompts for a Kaggle Benchmarks run.

Companion to judge_frontier.py (entry 175). Same purpose -- re-score answers
we have ALREADY composed with a frontier judge, so the only variable is the
judge -- but routed through Kaggle Benchmarks, where the model access is
already paid for, instead of a direct API key.

The split of labour matters for faithfulness: prompts are rendered HERE, from
the official EVALUATION_PROMPT_FOR_QUESTION read out of the harness at build
time. The Kaggle side never sees the template and never formats anything; it
just sends an opaque string and returns the reply. So the judge cannot drift
from upstream's wording no matter what happens remotely.

Two things are deliberately withheld from the uploaded rows: the local judge's
verdict, and the retrieved context. The verdict would leak the answer we are
trying to independently re-measure; the context is not part of the official QA
judge prompt and including it would change what is being scored.

  python3 kbench_judge_export.py --results <results_dir> --out-dir <dir>
"""
import argparse
import hashlib
import json
import os
import re
import sys

EVAL_DIR = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from judge_frontier import load_items


def official_qa_template():
    """Read the QA judge prompt out of the harness source.

    Deliberately parsed from the file rather than imported: importing
    eval_tools pulls in llms.py, which requires an API key and a .env at
    import time. We only need the string, and reading it keeps this script
    runnable with no credentials at all."""
    src = open(os.path.join(EVAL_DIR, "eval_tools.py")).read()
    m = re.search(r'EVALUATION_PROMPT_FOR_QUESTION = """(.*?)"""', src, re.S)
    if not m:
        sys.exit("could not find EVALUATION_PROMPT_FOR_QUESTION in eval_tools.py")
    return m.group(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out-dir", default=os.path.expanduser(
        "~/rg_private/halumem/kbench"))
    ap.add_argument("--limit", type=int, default=0,
                    help="export only the first N items (smoke runs)")
    args = ap.parse_args()

    tmpl = official_qa_template()
    results = os.path.expanduser(args.results)
    items = load_items(results)
    if args.limit:
        items = items[:args.limit]

    os.makedirs(args.out_dir, exist_ok=True)
    name = os.path.basename(results.rstrip("/"))
    suffix = f"-n{args.limit}" if args.limit else ""
    path = os.path.join(args.out_dir, f"halumem_judge_items-{name}{suffix}.jsonl")

    total_chars = 0
    with open(path, "w") as f:
        for it in items:
            prompt = tmpl.format(question=it["question"],
                                 reference_answer=it["answer"],
                                 key_memory_points=it["evidence"],
                                 response=it["system_response"])
            total_chars += len(prompt)
            f.write(json.dumps({
                "item_id": it["id"],
                "judge_prompt": prompt,
                "question_type": it["question_type"],
                "difficulty": it["difficulty"],
            }) + "\n")

    # A digest over the exported ids+prompts, so a returned verdict file can be
    # proved to belong to this export rather than a stale one.
    h = hashlib.sha256()
    for line in open(path, "rb"):
        h.update(line)
    digest = h.hexdigest()[:16]
    meta = {"source_results": results, "n_items": len(items),
            "export_digest": digest, "template_chars": len(tmpl)}
    mp = os.path.join(args.out_dir, f"halumem_judge_meta-{name}{suffix}.json")
    json.dump(meta, open(mp, "w"), indent=2)

    est_in = int(total_chars / 3.7)
    print(f"items          : {len(items)}")
    print(f"prompt chars   : {total_chars:,}")
    print(f"est input tok  : {est_in:,}  (+ ~{len(items) * 120:,} output)")
    print(f"export digest  : {digest}")
    print(f"\nwrote {path}\nwrote {mp}")
    print("\nUpload that .jsonl as a PRIVATE Kaggle dataset, then run "
          "kbench_judge_task.py against it.")


if __name__ == "__main__":
    main()
