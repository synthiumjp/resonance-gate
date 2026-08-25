#!/usr/bin/env python3
"""Entry 249: the free four-config QA-context diff.

WHY THIS EXISTS. The next judge cycle was queued to measure two changes at
once -- labeled hearsay (e249) and the e248 renderer fix -- with no way to
attribute a move to either. It does not have to be that way. The judged
answer is produced by a composer reading a CONTEXT STRING, and that context
is a deterministic function of (store, renderer, question): no model call,
no sampling. So the four configurations can be rendered offline, for free,
and diffed.

What that buys:
  * Any question whose context is BYTE-IDENTICAL across two configs must get
    an identical composer input, hence an identical answer at temperature 0,
    hence an identical verdict. Its verdict can be COPIED between arms rather
    than re-judged -- exact reuse, not an approximation.
  * The size of each change is known before spending anything: if hearsay
    touches 6 of 164 questions, its measurable effect is bounded at 6
    questions and the confound is moot.
  * If the LLM arm's contexts are unchanged by both edits, that arm is still
    a fixed baseline and `--reuse` skips it entirely -- roughly halving the
    cycle.

RETRIEVE ONCE, RENDER FOUR WAYS. e248 changed rendering (`format_fact`, and
under flags `currency`/`timeline`); hearsay lives in its own index and is
appended after the corroborated lines. Neither alters which facts the main
retrieval selects or their order, so retrieval runs once per question and the
four contexts are four renderings of the same fact list. (That assumption is
load-bearing; it is verified separately -- see tools/pre_e248.py.)

Costs ~15-30 min of CPU for user 0. No judge, no GPU, no model calls.

    python3 tools/context_diff.py --user 0 --arm rgx
    python3 tools/context_diff.py --user 0 --arm llm
"""
import argparse
import json
import os
import pathlib
import sys
import time

_P2 = "/home/jp/rg/experiments/p2"
_OFFICIAL = os.path.join(_P2, "halumem_official")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"

ARMS = {
    # arm -> (cache_dir, extra env matching chain.sh)
    "rgx": (pathlib.Path.home() / "rg_private/halumem/qa_rgx",
            {"RG_INGEST_ALL_TURNS": "1"}),
    "llm": (pathlib.Path.home() / "rg_private/halumem/qa_llm", {}),
}


def _setup_env(arm):
    """Reproduce chain.sh's environment exactly, minus the composer endpoint
    (no model is called here). Must run before importing the p2 modules --
    several read their flags at import time."""
    cache_dir, extra = ARMS[arm]
    os.environ["RG_EXTRACT_V5"] = "1"
    os.environ["RG_RETRIEVE_V3"] = "1"
    os.environ.update(extra)
    # the harness's own modules live in the HaluMem eval tree
    for p in (_P2, _OFFICIAL):
        if p not in sys.path:
            sys.path.insert(0, p)
    return cache_dir


def _hearsay_lines(hs_index, question, RV3, RV, owner, label, n, min_score):
    if hs_index is None:
        return []
    hs = RV3.retrieve_facts_v3(hs_index, question, top_n=n,
                               min_score=min_score)
    return [label + RV.format_fact(d, owner=owner) for d in hs[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, default=0)
    ap.add_argument("--arm", choices=sorted(ARMS), default="rgx")
    ap.add_argument("--hearsay-n", type=int, default=3)
    ap.add_argument("--hearsay-min", type=float, default=0.0,
                    help="cross-encoder relevance floor for hearsay; "
                         "pass a large negative number to disable")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit-sessions", type=int, default=None,
                    help="smoke-test on the first N sessions only")
    args = ap.parse_args()

    cache_dir = _setup_env(args.arm)
    # RG_HEARSAY must be set before IndexV3 is constructed so the sub-index
    # exists; the rendering of each config is chosen explicitly below, so this
    # does not by itself decide what the diff reports.
    os.environ["RG_HEARSAY"] = "1"

    import halumem_run as RG          # noqa: E402
    import retrieve as RV             # noqa: E402
    import retrieve_v3 as RV3         # noqa: E402
    import propositions as PR         # noqa: E402

    try:
        sys.path.insert(0, "/home/jp/rg/tools")
        import pre_e248                # noqa: E402
        old_format_fact = pre_e248.old_format_fact
        have_old = True
    except Exception as exc:           # harness still useful without it
        print(f"NOTE: pre-e248 renderer unavailable ({exc}); "
              f"reporting the hearsay axis only", file=sys.stderr)
        old_format_fact = None
        have_old = False

    label = "HEARSAY (assistant said this; the user has not): "
    cache_path = os.path.join(str(cache_dir),
                              f"cache_u{args.user}_v5.jsonl")
    if not os.path.exists(cache_path):
        sys.exit(f"cache not found: {cache_path}")

    with DATA.open() as fh:
        for i, line in enumerate(fh):
            if i == args.user:
                user_data = json.loads(line)
                break
        else:
            sys.exit(f"user {args.user} not in {DATA}")

    sessions = user_data["sessions"]
    if args.limit_sessions:
        sessions = sessions[:args.limit_sessions]

    rows = []
    t_start = time.time()
    for k, session in enumerate(sessions):
        questions = session.get("questions") or []
        if not questions or session.get("is_generated_qa_session", False):
            continue
        prefix = {"sessions": user_data["sessions"][:k + 1]}
        mem, _ = RG.ingest_user(prefix, cache_path, min_mentions=2)
        index = RV3.IndexV3(mem)
        owner = getattr(index, "owner", None)
        hs_index = getattr(index, "hearsay", None)
        n_hearsay_nodes = len(getattr(mem.g, "hearsay", {}) or {})

        for q in questions:
            question = q["question"]
            facts = RV3.retrieve_facts_v3(index, question)
            new_lines = [RV.format_fact(d, owner=owner) for d in facts]
            ctx_e248 = "\n".join(new_lines) or "(no relevant memories)"
            if have_old:
                old_lines = [old_format_fact(d, owner=owner) for d in facts]
                ctx_base = "\n".join(old_lines) or "(no relevant memories)"
            else:
                ctx_base = None

            hs = _hearsay_lines(hs_index, question, RV3, RV, owner, label,
                                args.hearsay_n, args.hearsay_min)
            ctx_e248_hs = ctx_e248 + ("\n" + "\n".join(hs) if hs else "")
            ctx_base_hs = (ctx_base + ("\n" + "\n".join(hs) if hs else "")
                           if ctx_base is not None else None)

            rows.append({
                "session": k,
                "question": question,
                "n_facts": len(facts),
                "n_hearsay_nodes": n_hearsay_nodes,
                "n_hearsay_lines": len(hs),
                "hearsay_changes_ctx": bool(hs),
                "e248_changes_ctx": (None if not have_old
                                     else ctx_base != ctx_e248),
                "all_four_identical": (None if not have_old else
                                       ctx_base == ctx_e248 == ctx_base_hs
                                       == ctx_e248_hs),
            })
        print(f"  session {k}: {len(questions)} q, "
              f"{len(rows)} total, {time.time()-t_start:.0f}s",
              file=sys.stderr)

    n = len(rows)
    if not n:
        sys.exit("no questions processed")
    hs_touch = sum(r["hearsay_changes_ctx"] for r in rows)
    print(f"\n=== context diff: user {args.user}, arm {args.arm}, "
          f"{n} questions ===")
    print(f"hearsay changes the context : {hs_touch:4d}  "
          f"({100*hs_touch/n:.1f}%)")
    print(f"hearsay leaves it identical : {n-hs_touch:4d}  "
          f"({100*(n-hs_touch)/n:.1f}%)  <- verdicts copyable on this axis")
    if have_old:
        e_touch = sum(bool(r["e248_changes_ctx"]) for r in rows)
        allsame = sum(bool(r["all_four_identical"]) for r in rows)
        print(f"e248 changes the context    : {e_touch:4d}  "
              f"({100*e_touch/n:.1f}%)")
        print(f"identical across ALL FOUR   : {allsame:4d}  "
              f"({100*allsame/n:.1f}%)  <- verdicts copyable outright")
        print(f"residue needing a judge     : {n-allsame:4d}  "
              f"({100*(n-allsame)/n:.1f}%)")
    else:
        print("(e248 axis not computed -- pre-e248 renderer unavailable)")

    out = args.out or f"/tmp/context_diff_u{args.user}_{args.arm}.jsonl"
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"\nper-question rows -> {out}")


if __name__ == "__main__":
    main()
