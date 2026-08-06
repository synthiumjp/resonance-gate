"""A/B the rerank cutoff: top_n=120 (round-5 behaviour) vs top_n=N (entry 178).

Entry 178 found retrieve_v3 used one `k` for both the BM25 candidate pool and
the post-rerank cutoff, so the cross-encoder reordered candidates without
removing any: median 77 facts reached the composer, 32.5% of questions got the
full 120. Where a supporting fact is present it ranks p50=1 / p75=3 / p90=9, so
a small cutoff should keep the evidence and drop the distraction.

Design notes that matter for the result being trustworthy:
  * ONE variable. Composer, CAL, extraction, judge and question set are all
    held at the round-5 configuration -- including RG_PREFIX_NO_THINK, which
    entry 177 shows is itself a defect. Fixing two things at once would make
    neither attributable.
  * PAIRED. Both arms answer the same questions off the same index in the same
    pass, so McNemar applies and index-build nondeterminism cannot leak in.
  * Where the two contexts come out IDENTICAL (few enough facts retrieved that
    the cutoff does nothing) the arms cannot differ, so the second compose is
    skipped -- that is a cost saving, not a shortcut, and the count is reported.

  python ab_topn.py --users 10,11,12 --top-n 20
"""
import argparse
import collections
import json
import os
import sys
import time

os.environ.setdefault("RG_RETRIEVE_V3", "1")
os.environ.setdefault("RG_PREFIX_NO_THINK", "1")   # round-5 parity, see above

EVAL = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
sys.path.insert(0, EVAL)
sys.path.insert(0, "/home/jp/rg/experiments/p2")

import eval_rgp2 as E                      # noqa: E402
import retrieve_v3 as RV3                  # noqa: E402
from eval_tools import evaluation_for_question   # noqa: E402
from validity import mcnemar               # noqa: E402


def compose_with(mode, on, top_n, mem, question, index):
    """compose_answer under one arm's configuration.

    Both switches are read from the environment at CALL time -- RG_TOP_N inside
    retrieve_facts_v3, RG_QA_PROPS inside format_fact -- so both arms share one
    process and one index, which is what makes the pairing airtight."""
    os.environ.pop("RG_TOP_N", None)
    os.environ.pop("RG_QA_PROPS", None)
    os.environ.pop("RG_POOL_K", None)
    if mode == "topn" and on:
        os.environ["RG_TOP_N"] = str(top_n)
    elif mode == "props" and on:
        os.environ["RG_QA_PROPS"] = "1"
    elif mode == "pool" and on:
        # Shrinks what the cross-encoder must score -- the 4.5s/query cost --
        # rather than what the composer reads. Different lever from top_n.
        os.environ["RG_POOL_K"] = str(top_n)
    return E.compose_answer(mem, question, index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="10,11,12")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--mode", default="topn", choices=("topn", "props", "pool"),
                    help="topn: B applies the rerank cutoff. "
                         "props: B renders context as propositions. "
                         "pool: B shrinks the BM25 candidate pool (CPU).")
    ap.add_argument("--out", default=os.path.expanduser(
        "~/rg_private/halumem/dev/ab_topn.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    data = list(E.iter_jsonl(E.DEFAULT_DATA_PATH))
    idxs = [int(x) for x in args.users.split(",")]

    done = set()
    if os.path.exists(args.out):
        for line in open(args.out):
            try:
                done.add(json.loads(line)["qid"])
            except Exception:
                pass
    print(f"resuming with {len(done)} already done" if done else "fresh run")

    of = open(args.out, "a")
    n = 0
    t0 = time.time()
    identical = 0
    for ui in idxs:
        user = data[ui]
        cache = os.path.join(E.DEFAULT_CACHE_DIR,
                             "cache_u{}{}.jsonl".format(ui, E._SFX))
        if not os.path.exists(cache):
            print(f"user {ui}: no cache {cache} -- skipped")
            continue
        sessions = user["sessions"]
        for k, session in enumerate(sessions):
            if "questions" not in session or session.get(
                    "is_generated_qa_session", False):
                continue
            mem, _ = E.RG.ingest_user({"sessions": sessions[:k + 1]}, cache,
                                      min_mentions=2)
            index = RV3.IndexV3(mem)
            for qn, qa in enumerate(session["questions"]):
                qid = f"{ui}|{k}|{qn}"
                if qid in done:
                    continue
                q = qa["question"]
                a_ans, a_ctx = compose_with(args.mode, False, args.top_n,
                                            mem, q, index)
                b_ans, b_ctx = compose_with(args.mode, True, args.top_n,
                                            mem, q, index)
                same_ctx = (a_ctx == b_ctx)
                if same_ctx:
                    identical += 1
                    b_ans = a_ans
                rec = {"qid": qid, "question": q, "answer": qa.get("answer"),
                       "evidence": qa.get("evidence"),
                       "qtype": qa.get("question_type"),
                       "same_context": same_ctx,
                       "a_lines": a_ctx.count("\n") + 1,
                       "b_lines": b_ctx.count("\n") + 1,
                       "a_ans": a_ans, "b_ans": b_ans}
                for arm, ans in (("a", a_ans), ("b", b_ans)):
                    try:
                        v = evaluation_for_question(
                            q, qa.get("answer"), qa.get("evidence"), ans
                        ).get("evaluation_result")
                    except Exception:
                        v = None
                    rec[f"{arm}_verdict"] = v
                if same_ctx:
                    rec["b_verdict"] = rec["a_verdict"]
                of.write(json.dumps(rec) + "\n")
                of.flush()
                n += 1
                if n % 20 == 0:
                    el = time.time() - t0
                    print(f"  {n} done ({identical} identical-context) "
                          f"{el/60:.1f} min", flush=True)
                if args.limit and n >= args.limit:
                    of.close()
                    return report(args.out, args.top_n, args.mode)
    of.close()
    report(args.out, args.top_n, args.mode)


def report(path, top_n, mode="topn"):
    recs = []
    for line in open(path):
        try:
            recs.append(json.loads(line))
        except Exception:
            pass
    recs = [r for r in recs if r.get("a_verdict") and r.get("b_verdict")]
    n = len(recs)
    if not n:
        print("no judged records")
        return
    print(f"\n=== {mode} A/B  (n={n}) ===")
    print(f"identical contexts: {sum(1 for r in recs if r['same_context'])} "
          f"({100*sum(1 for r in recs if r['same_context'])/n:.0f}%)")
    print(f"mean context lines: A(120) {sum(r['a_lines'] for r in recs)/n:.1f}"
          f"   B({top_n}) {sum(r['b_lines'] for r in recs)/n:.1f}")
    blabel = {"topn": f"B top_n={top_n}", "props": "B propositions",
              "pool": f"B pool_k={top_n}"}[mode]
    for arm, lbl in (("a", "A round-5 baseline"), ("b", blabel)):
        c = collections.Counter(r[f"{arm}_verdict"] for r in recs)
        print(f"  {lbl:24} Correct {100*c['Correct']/n:5.2f}%  "
              f"Halluc {100*c['Hallucination']/n:5.2f}%  "
              f"Omission {100*c['Omission']/n:5.2f}%")
    for lbl in ("Correct", "Hallucination"):
        m = mcnemar([r["a_verdict"] == lbl for r in recs],
                    [r["b_verdict"] == lbl for r in recs])
        print(f"  McNemar {lbl:14} A-only {m['lost']}, B-only {m['gained']}, "
              f"net {m.get('net',0):+}, p={m['p']:.3g}"
              f"{'  SIGNIFICANT' if m['reliable'] else ''}")


if __name__ == "__main__":
    main()
