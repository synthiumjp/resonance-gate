"""Re-judge an existing HaluMem answer set with a frontier judge (entry 175).

Every RG number so far was scored by our local qwen3:14b judge, while the
published comparators (MOSAIC 73.1/10.2, MemOS, Zep, mem0) were scored by
GPT-4o. Entry 105 established our judge is stricter and noisier -- 2.5%
nondeterminism -- but never measured how much of the gap it accounts for.
This re-scores answers we have ALREADY composed, so the only thing that
changes is the judge. Composer, evidence and prompts are untouched.

It deliberately does NOT reimplement scoring: it calls the official
`eval_tools.evaluation_for_question` with the official prompt, and swaps the
backend purely through OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL. Only
the real official judge counts, so the judge logic must stay upstream's.

Built for free-tier quotas: requests are paced to --rpm, every verdict is
appended to disk the moment it lands, and --max-calls stops cleanly under a
daily cap. Re-running skips whatever is already scored, so a 1,764-item set
can cross several days without losing work.

  export OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  export OPENAI_API_KEY=...            # aistudio.google.com/apikey
  export OPENAI_MODEL=gemini-2.5-flash
  python3 judge_frontier.py --results ~/rg_private/halumem/official/HaluMem/eval/results/rgp2-round5
"""
import argparse
import glob
import json
import os
import sys
import time

EVAL_DIR = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")


def load_items(results_dir):
    """Flatten a results dir into judge-ready records with stable ids.

    The id is positional (user/session/question) rather than a hash of the
    text, so a re-run after re-composing the SAME question set lines up, and
    the four fields are exactly the ones the official QA prompt consumes."""
    path = os.path.join(results_dir, "rgp2_eval_results.jsonl")
    items = []
    for line in open(path):
        d = json.loads(line)
        uid = d.get("uuid") or d.get("user_name")
        for si, s in enumerate(d.get("sessions", [])):
            for qi, q in enumerate(s.get("questions") or []):
                items.append({
                    "id": f"{uid}|{si}|{qi}",
                    "question": q.get("question", ""),
                    "answer": q.get("answer", ""),
                    "evidence": q.get("evidence", ""),
                    "system_response": q.get("system_response", ""),
                    "question_type": q.get("question_type", ""),
                    "difficulty": q.get("difficulty", ""),
                })
    return items


def load_local_verdicts(results_dir, items):
    """Pair each item with the verdict our local qwen3:14b judge already gave.

    Pairing is greedy on (uuid, question, system_response) rather than
    positional: the harness judges users with a worker pool, so tmp2 record
    order does not match session order (verified: 29/1764 positional
    mismatches, 0 with this key). 14 questions repeat within a user, but a
    repeat with an identical response is interchangeable for judging, so
    consuming matches from a queue is sound. Returns {item_id: verdict}."""
    from collections import defaultdict, deque
    idx = defaultdict(deque)
    for f in glob.glob(os.path.join(results_dir, "tmp2", "*.json")):
        try:
            recs = json.load(open(f)).get("question_answering_records", [])
        except Exception:
            continue
        for r in recs:
            idx[(r.get("uuid"), r.get("question"), r.get("system_response"))
                ].append(r.get("result_type"))
    out = {}
    for it in items:
        k = (it["id"].split("|")[0], it["question"], it["system_response"])
        if idx.get(k):
            out[it["id"]] = idx[k].popleft()
    return out


def compare_paired(rows, local):
    """Frontier vs local judge on the SAME items. Reports the full
    disagreement matrix, not just the marginals -- two judges can agree on the
    headline rate while disagreeing on most individual items."""
    from collections import Counter
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from validity import mcnemar

    pairs = [(local[r["id"]], r.get("verdict")) for r in rows if r["id"] in local]
    if not pairs:
        print("\n(no paired local verdicts found -- skipping comparison)")
        return {}
    n = len(pairs)
    lc = Counter(l for l, _ in pairs)
    fc = Counter(f for _, f in pairs)
    print(f"\n=== PAIRED: frontier vs local judge (n={n}) ===")
    print(f"  {'':14} {'local':>9} {'frontier':>9} {'delta':>8}")
    for k in ("Correct", "Hallucination", "Omission"):
        a, b = 100 * lc[k] / n, 100 * fc[k] / n
        print(f"  {k:14} {a:8.2f}% {b:8.2f}% {b - a:+7.2f}")
    agree = sum(1 for l, f in pairs if l == f)
    print(f"  item-level agreement: {100 * agree / n:.1f}%")
    print("  local -> frontier flow (top shifts):")
    flow = Counter((l, f) for l, f in pairs if l != f)
    for (l, f), c in flow.most_common(6):
        print(f"    {str(l):14} -> {str(f):14} {c:5}")

    stat = {"n": n, "agreement_pct": 100 * agree / n}
    for k in ("Correct", "Hallucination"):
        m = mcnemar([l == k for l, _ in pairs], [f == k for _, f in pairs])
        print(f"  McNemar on {k}: local-only {m['lost']}, frontier-only "
              f"{m['gained']}, net {m.get('net', 0):+}, p={m['p']:.3g}"
              f"{'  SIGNIFICANT' if m['reliable'] else ''}")
        stat[f"mcnemar_{k.lower()}"] = m
    stat["local_pct"] = {k: 100 * lc[k] / n for k in
                         ("Correct", "Hallucination", "Omission")}
    stat["frontier_pct"] = {k: 100 * fc[k] / n for k in
                            ("Correct", "Hallucination", "Omission")}
    return stat


def import_verdicts(results, path, limit=0):
    """Ingest verdicts judged elsewhere (Kaggle Benchmarks) and compare.

    Kept in this module so a Kaggle-routed run and a direct-API run land in
    exactly the same paired report -- the routing is an implementation detail,
    the measurement is not."""
    items = load_items(results)
    if limit:
        items = items[:limit]
    by_id = {it["id"]: it for it in items}

    recs = []
    if path.endswith(".csv"):
        import csv
        with open(path, newline="") as f:
            recs = list(csv.DictReader(f))
    else:
        for line in open(path):
            try:
                recs.append(json.loads(line))
            except Exception:
                pass

    rows, unknown, novote = [], 0, 0
    seen = set()
    for r in recs:
        iid = r.get("item_id") or r.get("id")
        v = r.get("verdict")
        if iid not in by_id:
            unknown += 1
            continue
        if not v or v in ("ParseError", "None", "nan", ""):
            novote += 1
            continue
        if iid in seen:            # later checkpoint lines supersede earlier
            rows = [x for x in rows if x["id"] != iid]
        seen.add(iid)
        row = dict(by_id[iid])
        row["verdict"] = v
        row["judge_model"] = r.get("model", "?")
        rows.append(row)

    print(f"imported     : {len(rows)} verdicts from {path}")
    if unknown:
        print(f"  ! {unknown} rows had ids not in this results set (wrong export?)")
    if novote:
        print(f"  ! {novote} rows had no usable verdict (parse errors/retries pending)")
    if not rows:
        sys.exit("no usable verdicts imported")
    model = rows[0].get("judge_model", "?")
    stat = report(rows, f"FRONTIER JUDGE ({model})")
    stat["judge_model"] = model
    stat["items_total"] = len(items)
    stat["complete"] = len(rows) >= len(items)
    stat["paired"] = compare_paired(rows, load_local_verdicts(results, items))
    sp = os.path.join(results, "frontier_judge_summary.json")
    json.dump(stat, open(sp, "w"), indent=2)
    print(f"\nwrote {sp}")
    if not stat["complete"]:
        print(f"PARTIAL: {len(rows)}/{len(items)} judged -- "
              f"percentages are on the judged subset only.")


def load_done(out_path):
    done = {}
    if os.path.exists(out_path):
        for line in open(out_path):
            try:
                d = json.loads(line)
                done[d["id"]] = d
            except Exception:
                pass
    return done


def tally(rows):
    from collections import Counter, defaultdict
    t, by = Counter(), defaultdict(Counter)
    for r in rows:
        v = r.get("verdict")
        t[v] += 1
        by[r.get("question_type", "?")][v] += 1
    return t, by


def report(rows, label):
    t, by = tally(rows)
    n = len(rows)
    if not n:
        return {}
    print(f"\n=== {label} (n={n}) ===")
    for k in ("Correct", "Hallucination", "Omission", None):
        c = t.get(k, 0)
        print(f"  {str(k):14} {c:5}  ({100 * c / n:.2f}%)")
    print("--- by question type (Correct/Halluc/Omission/None):")
    for qt, c in sorted(by.items()):
        tot = sum(c.values())
        print(f"  {qt[:34]:34} {c['Correct']:4}/{c['Hallucination']:4}/"
              f"{c['Omission']:4}/{c[None]:4}   (n={tot})")
    return {"n": n, "correct_pct": 100 * t["Correct"] / n,
            "halluc_pct": 100 * t["Hallucination"] / n,
            "omission_pct": 100 * t["Omission"] / n,
            "none_pct": 100 * t[None] / n,
            "counts": {str(k): v for k, v in t.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True,
                    help="results dir containing rgp2_eval_results.jsonl")
    ap.add_argument("--out", default=None,
                    help="verdict jsonl (default: <results>/frontier_judge.jsonl)")
    ap.add_argument("--rpm", type=float, default=15.0,
                    help="requests per minute (Gemini free tier flash = 15)")
    ap.add_argument("--max-calls", type=int, default=1450,
                    help="stop after this many NEW calls (free daily cap headroom)")
    ap.add_argument("--limit", type=int, default=0,
                    help="only consider the first N items (smoke runs)")
    ap.add_argument("--only-ids-from", default=None,
                    help="restrict to the item_ids present in this verdict "
                         "file, so two judges are compared on the same items")
    ap.add_argument("--import-verdicts", default=None,
                    help="ingest verdicts produced elsewhere (Kaggle "
                         "Benchmarks .jsonl/.csv) and compare; makes no API calls")
    args = ap.parse_args()

    if args.import_verdicts:
        return import_verdicts(os.path.expanduser(args.results),
                               os.path.expanduser(args.import_verdicts),
                               args.limit)

    # These are qwen3-specific reroutes; leaving either on would silently send
    # a frontier judge down the ollama native path or prefix a nonsense token.
    for v in ("RG_NO_THINK", "RG_PREFIX_NO_THINK"):
        if os.environ.get(v, "0") == "1":
            sys.exit(f"refusing to run: {v}=1 is a qwen3-only path")
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set")
    # llms.py reads these with a bare int() at import and dies if unset.
    os.environ.setdefault("RETRY_TIMES", "4")
    os.environ.setdefault("WAIT_TIME_LOWER", "2")
    os.environ.setdefault("WAIT_TIME_UPPER", "30")
    os.environ.setdefault("OPENAI_TIMEOUT", "180")
    os.environ.setdefault("OPENAI_TEMPERATURE", "0.0")

    sys.path.insert(0, EVAL_DIR)
    from eval_tools import evaluation_for_question

    results = os.path.expanduser(args.results)
    out_path = args.out or os.path.join(results, "frontier_judge.jsonl")
    items = load_items(results)
    if args.only_ids_from:
        keep = set()
        for line in open(os.path.expanduser(args.only_ids_from)):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("verdict"):
                keep.add(r.get("item_id"))
        items = [it for it in items if it["id"] in keep]
        print(f"restricted to {len(items)} items from {args.only_ids_from}")
    if args.limit:
        items = items[:args.limit]
    done = load_done(out_path)
    todo = [it for it in items if it["id"] not in done]

    model = os.environ.get("OPENAI_MODEL", "?")
    print(f"judge model : {model}")
    print(f"base url    : {os.environ.get('OPENAI_BASE_URL')}")
    print(f"items       : {len(items)}  already judged: {len(done)}  todo: {len(todo)}")
    if not todo:
        print("nothing to do -- all items already judged")
    else:
        print(f"pacing      : {args.rpm} rpm, stopping after {args.max_calls} new calls\n")

    interval = 60.0 / args.rpm if args.rpm > 0 else 0.0
    made = 0
    errors = 0
    of = open(out_path, "a")
    for it in todo:
        if made >= args.max_calls:
            print(f"\nhit --max-calls={args.max_calls}; "
                  f"{len(todo) - made} items remain. Re-run tomorrow to resume.")
            break
        t0 = time.time()
        try:
            res = evaluation_for_question(it["question"], it["answer"],
                                          it["evidence"], it["system_response"])
            verdict = (res or {}).get("evaluation_result")
            raw = res
        except Exception as e:
            # A failed call is recorded as an explicit error rather than a
            # verdict, so it is retried on the next run instead of silently
            # counting as a None (which would look like judge refusal).
            errors += 1
            print(f"  ! {it['id']}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            if errors >= 25 and errors > made:
                print("\naborting: errors dominate -- check key/quota/model name")
                break
            time.sleep(min(interval * 2, 30))
            continue
        rec = dict(it)
        rec["verdict"] = verdict
        rec["judge_model"] = model
        rec["raw"] = raw
        of.write(json.dumps(rec) + "\n")
        of.flush()
        done[it["id"]] = rec
        made += 1
        if made % 25 == 0:
            t, _ = tally(list(done.values()))
            n = len(done)
            print(f"  [{made}/{min(len(todo), args.max_calls)}] judged={n}  "
                  f"correct {100 * t['Correct'] / n:.1f}%  "
                  f"halluc {100 * t['Hallucination'] / n:.1f}%", flush=True)
        dt = time.time() - t0
        if interval > dt:
            time.sleep(interval - dt)
    of.close()

    rows = list(done.values())
    stat = report(rows, f"FRONTIER JUDGE ({model})")
    if stat:
        stat["judge_model"] = model
        stat["complete"] = len(rows) >= len(items)
        stat["items_total"] = len(items)
        # Compared on the judged subset only -- the local side is restricted to
        # the same items, so a partial run is still a fair paired test.
        stat["paired"] = compare_paired(rows, load_local_verdicts(results, items))
        sp = os.path.join(results, "frontier_judge_summary.json")
        json.dump(stat, open(sp, "w"), indent=2)
        print(f"\nwrote {out_path}\nwrote {sp}")
        if not stat["complete"]:
            print(f"PARTIAL: {len(rows)}/{len(items)} judged -- "
                  f"percentages above are on the judged subset only.")


if __name__ == "__main__":
    main()
