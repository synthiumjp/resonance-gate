"""Small-model extractor probe (entry TBD): can a 1-3B model on CPU replace
qwen3:14b as the per-turn memory extractor for a no-GPU tier?

The architecture tolerates a noisy extractor (corroboration filters junk); what
matters is (a) rule-following on the probe_extractor suite under SYSTEM_V4,
and (b) CPU latency per extraction call through the LOCAL ollama daemon
(http://localhost:11434, CPU-only in this session by instruction).

Reuses probe_extractor's CASES/WORLD_CASES/EVENT_CASES and judge(), and
llm_profile's canon_subject for parsing, so the output contract and scoring
are IDENTICAL to the GPU (llama-cpp) qwen3:14b runs this compares against.

Usage: python experiments/p2/probe_small.py
"""

import json
import re
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from llm_profile import SYSTEM_V4, canon_subject
from probe_extractor import CASES, WORLD_CASES, EVENT_CASES, judge

OLLAMA_URL = "http://localhost:11434/api/chat"
RESULTS_PATH = __file__.rsplit("/", 1)[0] + "/probe_small_results.json"

# candidates: (model, budget) -- budget caps full-suite runs; qwen3:14b gets a
# tiny 3-case latency-only sample per the task (its GPU quality score, 27/27,
# is already known and is NOT re-measured here).
CANDIDATES = ["qwen3:1.7b", "qwen3:0.6b", "gemma3:1b", "llama3.2:3b"]
LATENCY_ONLY_MODEL = "qwen3:14b"

ABORT_AFTER = 5          # cases
ABORT_AVG_SECS = 60.0    # abort a model if its running avg latency exceeds this

# All cases tagged with which list they came from, so EVENT_CASES (kind
# pos/neg, same as CASES) get scored under their OWN "event" split rather
# than folding into the case pos/neg splits.
ALL_CASES = ([(t, k, s, "case") for t, k, s in CASES] +
             [(t, k, s, "world") for t, k, s in WORLD_CASES] +
             [(t, k, s, "event") for t, k, s in EVENT_CASES])


def _split_for(kind, source):
    if source == "event":
        return "event"
    if kind == "wpos":
        return "wpos"
    return kind  # "neg" / "pos"


def _call_ollama(model, system, text, timeout=120):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": text[:1600]}],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 200, "seed": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        txt = json.load(resp)["message"]["content"]
    return txt, time.monotonic() - t0


def _parse_facts(txt):
    """Same parse contract as llm_profile.extract_profile_facts: strip any
    <think> residue, find the JSON array, normalise attribute/value, resolve
    subject via canon_subject. Returns None on parse failure (caller retries)."""
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
            v = str(f["value"]).strip()[:80]
            if a and v:
                fact = {"attribute": a, "value": v}
                subj = canon_subject(f.get("subject", "self"))
                if subj != "self":
                    fact["subject"] = subj[:40]
                facts.append(fact)
    return facts


def extract_via_ollama(text, model, system):
    """Same output contract as llm_profile.extract_profile_facts: a list of
    {attribute, value, subject?} dicts. 120s timeout, ONE retry on
    timeout/parse failure. Returns (facts, latency_secs_or_None, failed_bool).
    latency is the wall time of the LAST completed HTTP call (even a
    parse-failed one still measures real call latency); None only if every
    attempt raised (timeout/connection error)."""
    last_latency = None
    for attempt in (1, 2):
        try:
            txt, elapsed = _call_ollama(model, system, text)
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


def run_model(model, cases, abort_after=None, abort_avg_secs=None):
    """Runs `cases` through extract_via_ollama + judge(). Returns a dict with
    per-case results, split tallies, latencies, parse-failure count, and
    whether it was aborted as impractical."""
    per_case = []
    latencies = []
    parse_failures = 0
    aborted = False
    for i, (text, kind, spec, source) in enumerate(cases):
        facts, latency, failed = extract_via_ollama(text, model, SYSTEM_V4)
        if failed:
            parse_failures += 1
        if latency is not None:
            latencies.append(latency)
        ok, detail = judge(kind, spec, facts)
        split = _split_for(kind, source)
        per_case.append({
            "text": text, "kind": kind, "source": source, "split": split,
            "ok": bool(ok), "detail": [list(d) if isinstance(d, tuple) else d
                                        for d in detail],
            "facts": facts, "latency": latency, "parse_failed": failed,
        })
        print(f"  [{model}] {i+1}/{len(cases)} {'ok ' if ok else 'XX '}"
              f"({split:5s}) {latency if latency is not None else -1:6.2f}s  "
              f"{text[:50]}")
        if (abort_after is not None and len(per_case) >= abort_after and
                latencies and statistics.mean(latencies) > abort_avg_secs):
            print(f"  [{model}] ABORTED after {len(per_case)} cases: "
                  f"avg latency {statistics.mean(latencies):.1f}s > "
                  f"{abort_avg_secs:.0f}s budget -- impractical on CPU")
            aborted = True
            break
    return {
        "model": model, "per_case": per_case, "latencies": latencies,
        "parse_failures": parse_failures, "aborted": aborted,
        "n_run": len(per_case), "n_total": len(cases),
    }


def _pct(latencies, p):
    if not latencies:
        return None
    s = sorted(latencies)
    k = (len(s) - 1) * p
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])


def summarize(result):
    splits = {}
    for c in result["per_case"]:
        s = splits.setdefault(c["split"], [0, 0])
        s[0] += c["ok"]
        s[1] += 1
    total_ok = sum(c["ok"] for c in result["per_case"])
    lat = result["latencies"]
    return {
        "model": result["model"],
        "score": f"{total_ok}/{result['n_run']}"
                 + ("" if result["n_run"] == result["n_total"] else
                    f" (of {result['n_total']}, aborted)"),
        "splits": {k: f"{v[0]}/{v[1]}" for k, v in sorted(splits.items())},
        "median_latency": statistics.median(lat) if lat else None,
        "p90_latency": _pct(lat, 0.9),
        "parse_failures": result["parse_failures"],
        "aborted": result["aborted"],
    }


def _load_existing():
    try:
        with open(RESULTS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    # incremental, per-model: an explicit argv of model names runs (and
    # merges into RESULTS_PATH) just those models, so a long sweep can be
    # chunked into separate foreground calls without losing prior results.
    # No argv -> full default sweep (CANDIDATES + LATENCY_ONLY_MODEL).
    requested = sys.argv[1:] or (CANDIDATES + [LATENCY_ONLY_MODEL])

    all_results = _load_existing()

    for model in requested:
        if model == LATENCY_ONLY_MODEL:
            # latency-only sample, 3 cases (one neg, one pos, one event),
            # quality NOT scored here -- GPU runs already established 27/27.
            sample = [ALL_CASES[0], ALL_CASES[12], ALL_CASES[-2]]
            print(f"\n=== {LATENCY_ONLY_MODEL}: latency-only sample "
                  f"({len(sample)} cases, quality known 27/27 from GPU) ===")
            res = run_model(LATENCY_ONLY_MODEL, sample)
        else:
            print(f"\n=== {model}: full suite ({len(ALL_CASES)} cases) ===")
            res = run_model(model, ALL_CASES, abort_after=ABORT_AFTER,
                             abort_avg_secs=ABORT_AVG_SECS)
        all_results[model] = res
        with open(RESULTS_PATH, "w") as f:
            json.dump(all_results, f, indent=2)

    # reprint the full cumulative table from whatever is now on disk, in a
    # stable order (CANDIDATES first, then the latency-only model, then
    # anything else that got run under a different name).
    order = CANDIDATES + [LATENCY_ONLY_MODEL]
    ordered_models = [m for m in order if m in all_results] + \
                     [m for m in all_results if m not in order]
    summaries = []
    for model in ordered_models:
        s = summarize(all_results[model])
        if model == LATENCY_ONLY_MODEL:
            s["score"] = "27/27 (GPU, not re-run)"
        summaries.append(s)

    print("\n\n=== SUMMARY TABLE ===")
    header = (f"{'model':14s} {'score':22s} {'neg':7s} {'pos':7s} "
              f"{'wpos':7s} {'event':7s} {'median':8s} {'p90':8s} {'fail':5s}")
    print(header)
    print("-" * len(header))
    for s in summaries:
        sp = s["splits"]
        med = f"{s['median_latency']:.2f}s" if s["median_latency"] is not None else "n/a"
        p90 = f"{s['p90_latency']:.2f}s" if s["p90_latency"] is not None else "n/a"
        flag = " ABORTED" if s["aborted"] else ""
        print(f"{s['model']:14s} {s['score']:22s} "
              f"{sp.get('neg', '-'):7s} {sp.get('pos', '-'):7s} "
              f"{sp.get('wpos', '-'):7s} {sp.get('event', '-'):7s} "
              f"{med:8s} {p90:8s} {s['parse_failures']:<5d}{flag}")

    print(f"\nRaw per-case results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
