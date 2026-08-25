"""Two-judge validation for the HaluMem pilot (entry 53 discipline): a single
local judge's numbers are not trustworthy on their own -- LLM-judging is
documented-unreliable (see consistency.py's design note: Graphiti 1/9 on a
cheap model). This script separates the pilot into three cache-friendly
stages so the two judge passes can run independently and be cross-checked:

  answers  -- pure-python replay of ingest + non-generative QA over all 20
              HaluMem users, using the extraction caches already baked with
              RG_EXTRACT_V4 semantics. Zero LLM calls (asserted, not just
              hoped): every fact used here was extracted in a prior run and
              is being read back out of the cache file, never regenerated.
  judge    -- ONE local model (qwen3:14b, already pinned in consistency.py,
              or gemma3:12b, a second, independently-trained local model)
              grades every (question, gold, answer) triple with the SAME
              JUDGE rubric text. Two structurally different models grading
              the same rubric is the two-judge protocol; agreement between
              them is the trust signal single-judge numbers cannot give.
  report   -- joins answers + both verdict files and reports both judges'
              raw tallies, their agreement rate, and the BOTH-CONFIRMED
              tallies (a verdict only counts if the two independently-
              trained judges agree on it) -- the number this pilot can
              actually stand behind.

Usage:
  two_judge.py answers <HaluMem-Medium.jsonl>
  two_judge.py judge <answers.jsonl> --model qwen|gemma
  two_judge.py report
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# RG_EXTRACT_V4 selects the v4 (events/plans) extraction system inside
# halumem_run -- set before import so its module-level _SYSTEM/_CSFX match
# the semantics the cache files were built under. Irrelevant to correctness
# here (answers-stage ingest is pure cache replay, never calls extraction)
# but kept so a future cache MISS would fail loud in the right system, not
# silently extract under v3 rules.
os.environ.setdefault("RG_EXTRACT_V4", "1")

import halumem_run as HR
from halumem_run import JUDGE, answer_question, ingest_user

HALUMEM_DIR = os.path.expanduser("~/rg_private/halumem")
ANSWERS_PATH = os.path.join(HALUMEM_DIR, "answers_v4.jsonl")
N_USERS = 20
MIN_MENTIONS = 2

def _gemma_judge(question, gold, answer_text):
    """gemma3:12b via the LOCAL ollama HTTP API (localhost only -- no paid
    API, no network egress). The direct llama-cpp load of the gemma3 blob
    failed: the venv's llama-cpp-python predates the gemma3 architecture.
    ollama's own runtime handles it, so judge 2 goes through the daemon --
    still a second, structurally different local model, which is the whole
    point of the two-judge protocol."""
    import urllib.request
    body = json.dumps({
        "model": "gemma3:12b",
        "messages": [{"role": "system", "content": JUDGE},
                     {"role": "user", "content":
                      f"QUESTION: {question}\nGOLD: {gold}\nSYSTEM: {answer_text}"}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 10, "seed": 0},
    }).encode()
    req = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        txt = json.load(resp)["message"]["content"]
    return _parse_verdict(txt)


def _parse_verdict(txt):
    """Delegates to halumem_run.parse_verdict -- the single fixed parser
    (word-boundary matching, negation-safe, returns HR.UNPARSEABLE instead
    of silently coercing garbage to "omission"). Kept as a thin wrapper here
    rather than re-inlined so both judges in this two-judge protocol are
    scored by literally the same parsing code, not two copies that could
    drift."""
    return HR.parse_verdict(txt)


def _judge_text(llm, question, gold, answer_text, no_think):
    """One judge call against the SAME rubric (halumem_run.JUDGE) and the
    SAME parsing (strip <think>, first matching word wins). /no_think is a
    qwen3-specific control token -- prepending it for gemma would just be
    inert-or-worse noise in the prompt, so it is qwen-only, per spec."""
    if llm == "ollama-gemma":
        return _gemma_judge(question, gold, answer_text)
    sys_content = ("/no_think " + JUDGE) if no_think else JUDGE
    out = llm.create_chat_completion(
        messages=[{"role": "system", "content": sys_content},
                  {"role": "user", "content":
                   f"QUESTION: {question}\nGOLD: {gold}\nSYSTEM: {answer_text}"}],
        max_tokens=10, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    return _parse_verdict(txt)


def cmd_answers(args):
    """Stage 1: ingest all 20 users from cache (pure replay, no LLM), answer
    every question non-generatively, write one line per question. A user is
    SKIPPED (with a warning) if its cache file is missing, rather than
    letting ingest_user fall through to extraction on cache misses -- this
    subcommand must be runnable with zero LLM calls, and a missing cache
    would silently violate that."""
    users = [json.loads(l) for l in open(args.halumem_path)]
    os.makedirs(HALUMEM_DIR, exist_ok=True)
    n_written = 0
    with open(ANSWERS_PATH, "w") as out:
        for i in range(N_USERS):
            if i >= len(users):
                print(f"warning: user {i} not in {args.halumem_path}, skipping")
                continue
            cache_path = os.path.join(HALUMEM_DIR, f"cache_u{i}_v4.jsonl")
            if not os.path.exists(cache_path):
                print(f"warning: no cache at {cache_path}, skipping user {i}")
                continue
            n_before = sum(1 for _ in open(cache_path))
            mem, n_turns = ingest_user(users[i], cache_path, MIN_MENTIONS)
            n_after = sum(1 for _ in open(cache_path))
            assert n_after == n_before, (
                f"user {i}: cache grew ({n_before} -> {n_after} lines) -- "
                f"a cache MISS triggered extraction; this subcommand must "
                f"be zero-LLM-call")
            qs = [(q, s) for s in users[i]["sessions"]
                  for q in s.get("questions", [])]
            for q, _s in qs:
                ans = answer_question(mem, q["question"])
                out.write(json.dumps({
                    "u": i, "qtype": q.get("question_type", "?"),
                    "q": q["question"], "gold": q["answer"], "ans": ans,
                }) + "\n")
                n_written += 1
            print(f"user {i}: {n_turns} turns, {len(qs)} questions answered")
    print(f"\nwrote {n_written} answers -> {ANSWERS_PATH}")


def cmd_judge(args):
    """Stage 2: grade every (u, q) in the answers file with ONE local model.
    Resumable by (u, q) pair -- reruns after an interrupted pass pick up
    where they left off instead of re-spending GPU time on rows already
    graded."""
    out_path = os.path.join(HALUMEM_DIR, f"verdicts_{args.model}.jsonl")
    done = set()
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                d = json.loads(line)
                done.add((d["u"], d["q"]))
            except Exception:
                pass
    rows = [json.loads(l) for l in open(args.answers_path)]
    todo = [r for r in rows if (r["u"], r["q"]) not in done]
    print(f"{len(rows)} rows, {len(done)} already judged, "
          f"{len(todo)} to go (model={args.model})")

    if args.model == "qwen":
        judge_one = lambda r: HR.judge_answer(r["q"], r["gold"], r["ans"])
    else:
        judge_one = lambda r: _judge_text("ollama-gemma", r["q"], r["gold"],
                                           r["ans"], no_think=False)

    out = open(out_path, "a")
    for i, r in enumerate(todo):
        verdict = judge_one(r)
        out.write(json.dumps({"u": r["u"], "qtype": r["qtype"], "q": r["q"],
                               "verdict": verdict}) + "\n")
        out.flush()
        if (i + 1) % 100 == 0:
            print(f"  ...{i + 1}/{len(todo)} judged")
    out.close()
    print(f"done -> {out_path}")


def _load_verdicts(model):
    path = os.path.join(HALUMEM_DIR, f"verdicts_{model}.jsonl")
    d = {}
    if not os.path.exists(path):
        print(f"warning: no verdicts file at {path}")
        return d
    for line in open(path):
        try:
            r = json.loads(line)
            d[(r["u"], r["q"])] = r["verdict"]
        except Exception:
            pass
    return d


def _tally_report(verdicts, answers_by_key):
    """Overall + per-qtype tally for one judge's verdicts dict."""
    overall = {}
    by_type = {}
    for key, v in verdicts.items():
        overall[v] = overall.get(v, 0) + 1
        qtype = answers_by_key.get(key, {}).get("qtype", "?")
        by_type.setdefault(qtype, {})
        by_type[qtype][v] = by_type[qtype].get(v, 0) + 1
    return overall, by_type


def _print_tally(name, overall, by_type):
    n = sum(overall.values())
    print(f"\n-- {name} judge (n={n}) --")
    for v in ("correct", "hallucination", "omission", HR.UNPARSEABLE):
        c = overall.get(v, 0)
        if v == HR.UNPARSEABLE and c == 0:
            continue  # keep the common case's output unchanged
        print(f"  {v:13s}: {c:4d}  ({100 * c / max(n, 1):.1f}%)")
    print(f"  by question type:")
    for t, d in sorted(by_type.items()):
        tn = sum(d.values())
        print(f"    {t[:34]:34s} n={tn:3d}  correct {d.get('correct',0):3d}  "
              f"halluc {d.get('hallucination',0):3d}  "
              f"omit {d.get('omission',0):3d}")


def cmd_report(args):
    """Stage 3: join answers + both verdict files, report each judge's own
    numbers, their agreement, and the BOTH-CONFIRMED tallies -- the only
    numbers this pilot is licensed to quote per entry-53 discipline."""
    if not os.path.exists(ANSWERS_PATH):
        print(f"no answers file at {ANSWERS_PATH}; run `answers` first")
        return
    answers = [json.loads(l) for l in open(ANSWERS_PATH)]
    answers_by_key = {(r["u"], r["q"]): r for r in answers}

    qwen_v = _load_verdicts("qwen")
    gemma_v = _load_verdicts("gemma")

    # (a) per-judge tallies, overall and by qtype
    qo, qbt = _tally_report(qwen_v, answers_by_key)
    go, gbt = _tally_report(gemma_v, answers_by_key)
    _print_tally("qwen", qo, qbt)
    _print_tally("gemma", go, gbt)

    # (b) inter-judge agreement -- only over (u, q) pairs BOTH judges graded
    common = sorted(set(qwen_v) & set(gemma_v))
    print(f"\n-- inter-judge agreement (n={len(common)} pairs graded by both) --")
    if common:
        agree = sum(1 for k in common if qwen_v[k] == gemma_v[k])
        print(f"  overall: {agree}/{len(common)} ({100 * agree / len(common):.1f}%)")
        # per verdict class: of the pairs where EITHER judge said class c,
        # what fraction did BOTH say c -- a per-class overlap rate, not just
        # a marginal count, so a class one judge over-calls shows up as a
        # low agreement rate for that class even if its raw tally is high.
        for c in ("correct", "hallucination", "omission"):
            either = [k for k in common if qwen_v[k] == c or gemma_v[k] == c]
            both = [k for k in either if qwen_v[k] == c and gemma_v[k] == c]
            if either:
                print(f"  {c:13s}: {len(both):4d}/{len(either):4d} "
                      f"({100 * len(both) / len(either):.1f}%) agree "
                      f"when either judge said {c}")
    else:
        print("  (no overlapping pairs -- run `judge` for both models)")

    # (c) BOTH-JUDGE-CONFIRMED tallies + split bucket
    confirmed = {"correct": 0, "hallucination": 0, "omission": 0}
    split = {"n": 0, "by_qtype": {}}
    confirmed_halluc_keys = []
    for k in common:
        qv, gv = qwen_v[k], gemma_v[k]
        if qv == gv:
            confirmed[qv] += 1
            if qv == "hallucination":
                confirmed_halluc_keys.append(k)
        else:
            split["n"] += 1
            qtype = answers_by_key.get(k, {}).get("qtype", "?")
            split["by_qtype"][qtype] = split["by_qtype"].get(qtype, 0) + 1

    print(f"\n-- both-judge-confirmed (n={len(common)}) --")
    for v in ("correct", "hallucination", "omission"):
        c = confirmed[v]
        print(f"  {v:13s}: {c:4d}  ({100 * c / max(len(common), 1):.1f}%)")
    print(f"  split (judges disagree): {split['n']:4d}  "
          f"({100 * split['n'] / max(len(common), 1):.1f}%)")
    if split["by_qtype"]:
        print("  split by question type:")
        for t, c in sorted(split["by_qtype"].items()):
            print(f"    {t[:34]:34s} n={c}")

    # (d) both-confirmed hallucinations, printed in full for inspection --
    # synthetic HaluMem personas, no real user data, safe to print verbatim.
    print(f"\n-- both-judge-confirmed HALLUCINATIONS "
          f"(n={len(confirmed_halluc_keys)}) --")
    for k in confirmed_halluc_keys:
        r = answers_by_key.get(k, {})
        print(f"  u={r.get('u')} qtype={r.get('qtype')}")
        print(f"    Q:    {r.get('q')}")
        print(f"    GOLD: {r.get('gold')}")
        print(f"    ANS:  {r.get('ans')}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ans = sub.add_parser("answers", help="ingest + answer all users, zero LLM calls")
    p_ans.add_argument("halumem_path", help="path to HaluMem-Medium.jsonl")
    p_ans.set_defaults(func=cmd_answers)

    p_judge = sub.add_parser("judge", help="grade answers with ONE local judge")
    p_judge.add_argument("answers_path", help="path to answers_v4.jsonl")
    p_judge.add_argument("--model", choices=["qwen", "gemma"], required=True)
    p_judge.set_defaults(func=cmd_judge)

    p_rep = sub.add_parser("report", help="join both judges + report")
    p_rep.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
