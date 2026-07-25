"""HaluMem dev-set extraction + scoring (users 10-19, FIREWALLED from the
official test users 0-9): builds per-turn extraction caches with the CPU
extractor (qwen3:1.7b via the LOCAL ollama daemon, SYSTEM_V4) and scores the
resulting memory against gold, so extraction coverage can be iterated on
WITHOUT ever touching the official test users or the GPU/llama_cpp path that
the official benchmark run owns.

Hard constraints (see experiments/p2/halumem_run.py for the pilot/official
adapter this reuses code from):
  - NEVER call http://localhost:8090 or import llama_cpp for inference. All
    model calls in this file go to the local ollama daemon's native
    /api/chat (http://localhost:11434), CPU-only.
  - halumem_run.judge_answer() and llm_profile.extract_profile_facts() both
    call consistency.get_llm(), which loads a GGUF into the GPU via
    llama_cpp -- this file NEVER calls either. Extraction here is a
    parallel ollama-based implementation (extract_via_ollama, below) with
    the SAME output contract; the dev-loop judge (judge_answer_ollama) is a
    parallel ollama-based implementation that reuses halumem_run.JUDGE's
    prompt TEXT only.
  - `score` only runs halumem_run.ingest_user() against a COMPLETE cache
    (every turn hash already present), so ingest_user's internal cache-miss
    fallback to extract_profile_facts()/get_llm() is never exercised.

Usage:
  dev_set.py extract [--users 10-19] [--limit N]   # low priority, resumable
  dev_set.py score   [--users 10-19]                # writes dev_baseline_17b.json
  dev_set.py dryrun                                  # 30-turn smoke test, user 10
"""

import argparse
import copy
import hashlib
import json
import os
import re
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from llm_profile import SYSTEM_V4, SYSTEM_V5, canon_subject
import halumem_run as HR   # ingest_user, extraction_proxy, answer_question, JUDGE text
                            # -- NOT halumem_run.judge_answer or llm_profile.extract_profile_facts,
                            # both of which call the GPU consistency.get_llm(); see module docstring.

OLLAMA_URL = "http://localhost:11434/api/chat"
EXTRACT_MODEL = "qwen3:1.7b"
JUDGE_MODEL = "qwen3:1.7b"

DEV_DIR = os.path.expanduser("~/rg_private/halumem/dev")
HALUMEM_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
DEV_USER_IDX = list(range(10, 20))   # firewalled dev set; users 0-9 are official test

# v5 (entry 94 narrative ontology, see llm_profile.SYSTEM_V5): own cache/own
# suffix, same pattern as v4's -- opt in via RG_EXTRACT_V5 so the v4 dev
# caches (the ceiling baseline) stay untouched. Checked before v4.
EXTRACT_SYSTEM = SYSTEM_V5 if os.environ.get("RG_EXTRACT_V5") else SYSTEM_V4
_CSFX = "_v5" if os.environ.get("RG_EXTRACT_V5") else ""


def _cache_path(uidx, template=None):
    # template: full path pattern with {i} (decoupling A/B: score the SAME
    # users from a different extractor's caches, judge held constant)
    if template:
        return os.path.expanduser(template.format(i=uidx))
    return os.path.join(DEV_DIR, f"cache_u{uidx}{_CSFX}_17b.jsonl")


def _load_users(path=HALUMEM_PATH):
    with open(path) as f:
        return [json.loads(l) for l in f]


def _user_turns(user):
    """Yield (sha1_hash, truncated_text) for every user-role turn, in the
    EXACT order/truncation halumem_run.ingest_user uses (content.strip()
    [:1800], then sha1 hex of that). Must stay byte-identical to
    ingest_user's loop or cache lookups will not line up."""
    for sess in user["sessions"]:
        for t in sess.get("dialogue", []):
            if t.get("role") != "user":
                continue
            text = str(t.get("content", "")).strip()[:1800]
            if not text:
                continue
            h = hashlib.sha1(text.encode()).hexdigest()
            yield h, text


def _trim_user_to_turns(user, n):
    """A deep-copied user object truncated to (at most) the first n user-role
    turns, counted with the SAME predicate as _user_turns. Used only for the
    dry-run replay so ingest_user sees a user whose turns are a strict
    subset of what got cached."""
    trimmed = copy.deepcopy(user)
    kept_sessions = []
    count = 0
    for sess in trimmed["sessions"]:
        new_dialogue = []
        for t in sess.get("dialogue", []):
            new_dialogue.append(t)
            if t.get("role") == "user" and str(t.get("content", "")).strip():
                count += 1
            if count >= n:
                break
        sess["dialogue"] = new_dialogue
        kept_sessions.append(sess)
        if count >= n:
            break
    trimmed["sessions"] = kept_sessions
    return trimmed


def _call_ollama(model, system, user_text, num_predict=200, timeout=120):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user_text}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": num_predict, "seed": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = json.load(resp)["message"]["content"]
    return txt, time.monotonic() - t0


def _parse_facts(txt):
    """Identical parse contract to llm_profile.extract_profile_facts /
    probe_small._parse_facts: strip stray <think> residue, find the JSON
    array, normalise attribute/value, resolve subject via canon_subject.
    Returns None on parse failure (caller retries)."""
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        return None
    try:
        arr = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(arr, list):
        return None
    facts = []
    for f in arr:
        if isinstance(f, dict) and f.get("attribute") and f.get("value"):
            a = re.sub(r"\s+", "_", str(f["attribute"]).strip().lower())[:30]
            # 160 (was 80): matches llm_profile.extract_profile_facts -- v5
            # narrative values keep a stated reason clause verbatim-ish, up
            # to ~15 words.
            v = str(f["value"]).strip()[:160]
            if a and v:
                fact = {"attribute": a, "value": v}
                subj = canon_subject(f.get("subject", "self"))
                if subj != "self":
                    fact["subject"] = subj[:40]
                facts.append(fact)
    return facts


def extract_via_ollama(text, model=EXTRACT_MODEL, system=SYSTEM_V4, timeout=120):
    """Same output contract as llm_profile.extract_profile_facts, over the
    local ollama daemon instead of llama_cpp/GPU. `text` is the ALREADY
    1800-truncated turn text (as produced by _user_turns); this further
    truncates to [:1600] for the model call, matching
    extract_profile_facts's internal truncation exactly. One retry on
    timeout/parse failure. Returns (facts, latency_secs_or_None, failed)."""
    last_latency = None
    for attempt in (1, 2):
        try:
            txt, elapsed = _call_ollama(model, system, text[:1600],
                                        num_predict=200, timeout=timeout)
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
            if attempt == 2:
                return [], last_latency, True
            continue
        last_latency = elapsed
        facts = _parse_facts(txt)
        if facts is None:
            if attempt == 2:
                return [], last_latency, True
            continue
        return facts, last_latency, False
    return [], last_latency, True


def judge_answer_ollama(question, gold, answer_text, model=JUDGE_MODEL):
    """DEV-LOOP judge ONLY: qwen3:1.7b via the local ollama daemon, reusing
    halumem_run.JUDGE's prompt TEXT (not halumem_run.judge_answer itself,
    which calls the GPU consistency.get_llm()). This exists purely for fast,
    self-consistent, RELATIVE comparisons between our own extractor/prompt
    versions on the firewalled dev set -- it is a different, smaller judge
    model than the pilot's qwen3:14b, so dev-loop numbers are NOT comparable
    to halumem_run's pilot QA numbers or to the official benchmark."""
    txt, _lat = _call_ollama(model, HR.JUDGE,
                             f"QUESTION: {question}\nGOLD: {gold}\nSYSTEM: {answer_text}",
                             num_predict=10)
    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip().lower()
    for v in ("correct", "hallucination", "omission"):
        if v in txt:
            return v
    return "omission"


def _cache_complete(user, cache_path):
    cached = set()
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                cached.add(json.loads(line)["h"])
            except Exception:
                pass
    turns = list(_user_turns(user))
    total = len(turns)
    have = sum(1 for h, _ in turns if h in cached)
    return have == total, have, total


def _parse_users_arg(spec):
    """'10-19' or '10,12,15' -> [10,19] / [10,12,15]. None -> DEV_USER_IDX."""
    if not spec:
        return DEV_USER_IDX
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

def cmd_extract(args):
    os.nice(10)   # low priority -- the official benchmark eval shares this host's CPU
    os.makedirs(DEV_DIR, exist_ok=True)
    users = _load_users()
    user_indices = _parse_users_arg(args.users)
    deadline = (time.monotonic() + args.time_budget) if args.time_budget else None
    print(f"extractor: {'v5' if EXTRACT_SYSTEM is SYSTEM_V5 else 'v4'} "
          f"(RG_EXTRACT_V5={'1' if os.environ.get('RG_EXTRACT_V5') else '0'})")

    for uidx in user_indices:
        user = users[uidx]
        cache_path = _cache_path(uidx)
        cached = set()
        if os.path.exists(cache_path):
            for line in open(cache_path):
                try:
                    cached.add(json.loads(line)["h"])
                except Exception:
                    pass
        turns = list(_user_turns(user))
        todo = [(h, t) for h, t in turns if h not in cached]
        if args.limit is not None:
            todo = todo[:max(0, args.limit - len(cached))] if args.limit > len(cached) else []
        print(f"user {uidx}: {len(turns)} turns total, {len(cached)} already cached, "
              f"{len(todo)} to extract -> {cache_path}")
        if not todo:
            continue
        cf = open(cache_path, "a")
        t0 = time.monotonic()
        n_done = 0
        stopped_early = False
        for h, text in todo:
            facts, latency, failed = extract_via_ollama(text, system=EXTRACT_SYSTEM)
            cf.write(json.dumps({"h": h, "f": facts}) + "\n")
            cf.flush()
            n_done += 1
            if n_done % 100 == 0:
                elapsed = time.monotonic() - t0
                rate = n_done / elapsed
                remaining = len(todo) - n_done
                eta_s = remaining / rate if rate > 0 else float("inf")
                print(f"  user {uidx}: {n_done}/{len(todo)} done  "
                      f"rate={rate:.3f} turns/s  ETA={eta_s / 60:.1f} min"
                      f"{'  [parse_failed]' if failed else ''}")
            if deadline is not None and time.monotonic() >= deadline:
                print(f"  user {uidx}: time budget reached at {n_done}/{len(todo)} "
                      f"-- stopping (resumable, re-run to continue)")
                stopped_early = True
                break
        cf.close()
        if stopped_early:
            return
        print(f"user {uidx}: extraction complete ({len(turns)} turns cached)")


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

def score_user(uidx, user, cache_path):
    mem, n_turns = HR.ingest_user(user, cache_path, min_mentions=2)
    gold_mps = [mp for s in user["sessions"] for mp in s.get("memory_points", [])
                if mp.get("memory_source") != "interference"]
    cov, tot = HR.extraction_proxy(mem, gold_mps)

    qs = [(q, s) for s in user["sessions"] for q in s.get("questions", [])]
    tally = defaultdict(int)
    for q, s in qs:
        ans = HR.answer_question(mem, q["question"], surface="plain")
        verdict = judge_answer_ollama(q["question"], q["answer"], ans)
        tally[verdict] += 1
    n = sum(tally.values())

    return {
        "user": uidx, "n_turns": n_turns,
        "n_asserted": len(mem.g.nodes), "n_provisional": len(mem.g.provisional),
        "proxy_covered": cov, "proxy_total": tot,
        "proxy_pct": 100 * cov / max(tot, 1),
        "n_questions": n,
        "correct": tally["correct"],
        "hallucination": tally["hallucination"],
        "omission": tally["omission"],
        "correct_pct": 100 * tally["correct"] / max(n, 1),
        "hallucination_pct": 100 * tally["hallucination"] / max(n, 1),
        "omission_pct": 100 * tally["omission"] / max(n, 1),
    }


def cmd_score(args):
    os.makedirs(DEV_DIR, exist_ok=True)
    users = _load_users()
    user_indices = _parse_users_arg(args.users)

    results = []
    for uidx in user_indices:
        user = users[uidx]
        cache_path = _cache_path(uidx, getattr(args, "cache_template", None))
        complete, have, total = _cache_complete(user, cache_path)
        if not complete:
            print(f"user {uidx}: cache incomplete ({have}/{total} turns) -- skipping "
                  f"(run `extract --users {uidx}` first)")
            continue
        print(f"user {uidx}: scoring ({total} cached turns)...")
        t0 = time.monotonic()
        res = score_user(uidx, user, cache_path)
        print(f"  done in {time.monotonic() - t0:.1f}s  "
              f"proxy={res['proxy_pct']:.1f}%  correct={res['correct_pct']:.1f}%  "
              f"halluc={res['hallucination_pct']:.1f}%  omit={res['omission_pct']:.1f}%")
        results.append(res)

    if not results:
        print("\nno dev users had a complete cache -- nothing scored.")
        return

    agg_cov = sum(r["proxy_covered"] for r in results)
    agg_tot = sum(r["proxy_total"] for r in results)
    agg_n = sum(r["n_questions"] for r in results)
    agg_correct = sum(r["correct"] for r in results)
    agg_halluc = sum(r["hallucination"] for r in results)
    agg_omit = sum(r["omission"] for r in results)
    aggregate = {
        "n_users": len(results),
        "proxy_covered": agg_cov, "proxy_total": agg_tot,
        "proxy_pct": 100 * agg_cov / max(agg_tot, 1),
        "n_questions": agg_n,
        "correct": agg_correct, "hallucination": agg_halluc, "omission": agg_omit,
        "correct_pct": 100 * agg_correct / max(agg_n, 1),
        "hallucination_pct": 100 * agg_halluc / max(agg_n, 1),
        "omission_pct": 100 * agg_omit / max(agg_n, 1),
    }

    out = {
        "note": ("DEV-LOOP numbers: extractor qwen3:1.7b + judge qwen3:1.7b, both via "
                 "the local ollama daemon. For RELATIVE comparison between our own "
                 "versions on the firewalled dev set (users 10-19) only -- NOT "
                 "comparable to halumem_run's pilot numbers (qwen3:14b judge via "
                 "llama_cpp/GPU) or to the official benchmark."),
        "dev_users_scored": [r["user"] for r in results],
        "per_user": results,
        "aggregate": aggregate,
    }
    out_path = os.path.join(DEV_DIR, getattr(args, "out", None)
                            or "dev_baseline_17b.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print("\n=== per-user ===")
    header = f"{'user':5s} {'turns':6s} {'proxy%':8s} {'correct%':9s} {'halluc%':8s} {'omit%':7s}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['user']:<5d} {r['n_turns']:<6d} {r['proxy_pct']:<8.1f} "
              f"{r['correct_pct']:<9.1f} {r['hallucination_pct']:<8.1f} {r['omission_pct']:<7.1f}")
    print("-" * len(header))
    a = aggregate
    print(f"{'ALL':5s} {'':6s} {a['proxy_pct']:<8.1f} {a['correct_pct']:<9.1f} "
          f"{a['hallucination_pct']:<8.1f} {a['omission_pct']:<7.1f}")
    print(f"\nsaved {out_path}")


# ---------------------------------------------------------------------------
# dryrun -- pipeline-shape check only, per task step 3. Extracts 30 turns of
# user 10 in the foreground, confirms cache lines appear and ingest_user can
# replay them on a trimmed user object (so ingest_user never sees a turn
# whose hash is NOT in the cache -- no fallback to the GPU extractor).
# ---------------------------------------------------------------------------

def cmd_dryrun(args):
    os.nice(10)
    os.makedirs(DEV_DIR, exist_ok=True)
    users = _load_users()
    user10 = users[10]
    turns = list(_user_turns(user10))[:30]
    cache_path = os.path.join(DEV_DIR, "dryrun_cache_u10_17b.jsonl")
    if os.path.exists(cache_path):
        os.remove(cache_path)

    print(f"dry run: extracting {len(turns)} turns of user 10 (foreground)...")
    cf = open(cache_path, "w")
    latencies = []
    for i, (h, text) in enumerate(turns):
        facts, latency, failed = extract_via_ollama(text)
        cf.write(json.dumps({"h": h, "f": facts}) + "\n")
        cf.flush()
        latencies.append(latency)
        print(f"  {i+1:2d}/{len(turns)}  {latency:5.2f}s  n_facts={len(facts)}"
              f"{'  PARSE_FAILED' if failed else ''}")
    cf.close()

    with open(cache_path) as f:
        n_lines = sum(1 for _ in f)
    print(f"\ncache lines written: {n_lines} -> {cache_path}")

    trimmed = _trim_user_to_turns(user10, 30)
    mem, n_turns = HR.ingest_user(trimmed, cache_path, min_mentions=1)
    print(f"ingest_user replay: {n_turns} turns -> {len(mem.g.nodes)} asserted + "
          f"{len(mem.g.provisional)} provisional, {len(mem.g.edges)} edges")

    median = statistics.median(latencies)
    mean = statistics.mean(latencies)
    print(f"\nlatency over {len(latencies)} turns: median={median:.2f}s mean={mean:.2f}s "
          f"min={min(latencies):.2f}s max={max(latencies):.2f}s")

    all_dev_users = [users[i] for i in DEV_USER_IDX]
    total_turns = sum(len(list(_user_turns(u))) for u in all_dev_users)
    projected_s = total_turns * mean
    print(f"\nturns across all dev users (10-19): {total_turns}")
    print(f"projected total extraction time (mean latency x total turns): "
          f"{projected_s / 60:.1f} min ({projected_s / 3600:.2f} h)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="extract facts for dev users (resumable)")
    p_extract.add_argument("--users", default=None, help="e.g. '10-19' or '10,12,15' (default: all)")
    p_extract.add_argument("--limit", type=int, default=None,
                           help="cap total cached lines per user (testing only)")
    p_extract.add_argument("--time-budget", dest="time_budget", type=float, default=None,
                           help="stop (resumable) after this many seconds, for chunking "
                                "a long extraction across foreground calls")

    p_score = sub.add_parser("score", help="score dev users with a complete cache")
    p_score.add_argument("--users", default=None, help="e.g. '10-19' or '10,12,15' (default: all)")
    p_score.add_argument("--cache-template", dest="cache_template", default=None,
                         help="path pattern with {i}, e.g. '~/rg_private/halumem/cache_u{i}_v4.jsonl'")
    p_score.add_argument("--out", default=None, help="output json filename (in dev dir)")

    sub.add_parser("dryrun", help="30-turn foreground smoke test on user 10, then stop")

    args = ap.parse_args()
    if args.cmd == "extract":
        cmd_extract(args)
    elif args.cmd == "score":
        cmd_score(args)
    elif args.cmd == "dryrun":
        cmd_dryrun(args)


if __name__ == "__main__":
    main()
