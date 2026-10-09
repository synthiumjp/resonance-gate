"""Judge stored LoCoMo answers again with the strict prompt (LOCOMO_JUDGE=strict
in common.py): <dir>/ans_<system>.jsonl -> <dir>/ans_<system>_strict.jsonl,
same answers, new verdicts. Resumable.

    LOCOMO_JUDGE=strict python rejudge.py results/<dir> sourcedrecall [...]
    python score.py results/<dir> sourcedrecall_strict ...   (needs ctx_<system>_strict.jsonl: linked)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main():
    d, systems = sys.argv[1], sys.argv[2:]
    assert os.environ.get("LOCOMO_JUDGE") == "strict", "set LOCOMO_JUDGE=strict"
    for s in systems:
        out = os.path.join(d, f"ans_{s}_strict.jsonl")
        done = {r["qid"] for r in C.jsonl_read(out)}
        rows = [r for r in C.jsonl_read(os.path.join(d, f"ans_{s}.jsonl")) if r["qid"] not in done]
        print(s, len(rows), "to judge", flush=True)
        for i, r in enumerate(rows):
            j = C.llm(C.judge_prompt().format(question=r["question"], gold=r["gold"], pred=r["pred"]),
                      max_tokens=120)
            C.jsonl_append(out, dict(r, system=f"{s}_strict", judge_text=j, label=C.judge_label(j)))
            if i % 100 == 0:
                print(f"  {s} {i}/{len(rows)}", flush=True)
        ctx = os.path.join(d, f"ctx_{s}_strict.jsonl")
        if not os.path.exists(ctx):
            os.symlink(f"ctx_{s}.jsonl", ctx)


if __name__ == "__main__":
    main()
