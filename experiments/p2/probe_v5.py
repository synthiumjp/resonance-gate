"""v4 vs v5 regression probe (entry 94 SYSTEM_V5 build): does the narrative
extraction addition (motivation/belief/value/feeling/reflection/preference/
relationship_dynamic, longer reason-bearing values) cost any of the 27
synthetic cases v4 holds at 26/27 on qwen3:1.7b via the local ollama daemon?

Reuses probe_extractor's CASES/WORLD_CASES/EVENT_CASES and judge() (the
SAME synthetic suite and pass/fail criteria SYSTEM_V4 was scored against),
and probe_small's ollama-calling/parsing machinery (NOT llm_profile.
extract_profile_facts / probe_extractor.extract_profile_facts, which call
the GPU consistency.get_llm() -- this stays on the local ollama daemon only,
per the hard constraint on this dev loop).

Usage: python experiments/p2/probe_v5.py
Writes experiments/p2/probe_v5_results.json.
"""

import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from llm_profile import SYSTEM_V4, SYSTEM_V5, canon_subject
from probe_extractor import CASES, WORLD_CASES, EVENT_CASES, judge

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3:1.7b"
RESULTS_PATH = __file__.rsplit("/", 1)[0] + "/probe_v5_results.json"

ARMS = (("v4", SYSTEM_V4), ("v5", SYSTEM_V5))

ALL_CASES = ([(t, k, s, "case") for t, k, s in CASES] +
             [(t, k, s, "world") for t, k, s in WORLD_CASES] +
             [(t, k, s, "event") for t, k, s in EVENT_CASES])


def _split_for(kind, source):
    if source == "event":
        return "event"
    if kind == "wpos":
        return "wpos"
    return kind


def _call_ollama(system, text, timeout=120):
    body = json.dumps({
        "model": MODEL,
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
            v = str(f["value"]).strip()[:160]
            if a and v:
                fact = {"attribute": a, "value": v}
                subj = canon_subject(f.get("subject", "self"))
                if subj != "self":
                    fact["subject"] = subj[:40]
                facts.append(fact)
    return facts


def extract_via_ollama(text, system):
    last_latency = None
    for attempt in (1, 2):
        try:
            txt, elapsed = _call_ollama(system, text)
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


def main():
    tally = {(n, k): 0 for n, _ in ARMS for k in ("neg", "pos", "wpos", "event")}
    per_case = []
    for text, kind, spec, source in ALL_CASES:
        split = _split_for(kind, source)
        res = {}
        for name, system in ARMS:
            facts, latency, failed = extract_via_ollama(text, system)
            ok, detail = judge(kind, spec, facts)
            tally[(name, split)] += ok
            res[name] = {"ok": bool(ok), "detail": [list(d) if isinstance(d, tuple) else d
                                                     for d in detail],
                         "facts": facts, "latency": latency, "parse_failed": failed}
        aok, bok = res[ARMS[0][0]]["ok"], res[ARMS[1][0]]["ok"]
        mark = "==" if aok == bok else (f"{ARMS[1][0]}+" if bok else f"{ARMS[1][0]}-")
        print(f"[{'ok' if aok else 'XX'}->{'ok' if bok else 'XX'} {mark:3s}] "
              f"({split:5s}) {text[:58]}")
        if not bok:
            print(f"         {ARMS[1][0]} detail: {res[ARMS[1][0]]['detail']} "
                  f"facts={res[ARMS[1][0]]['facts']}")
        per_case.append({"text": text, "kind": kind, "split": split, ARMS[0][0]: res[ARMS[0][0]],
                         ARMS[1][0]: res[ARMS[1][0]]})

    counts = {k: sum(1 for _, kk, _, src in ALL_CASES if _split_for(kk, src) == k)
              for k in ("neg", "pos", "wpos", "event")}
    summary = {}
    for name, _ in ARMS:
        tot = sum(tally[(name, k)] for k in counts)
        summary[name] = {"score": f"{tot}/{len(ALL_CASES)}",
                         "splits": {k: f"{tally[(name, k)]}/{n}" for k, n in counts.items()}}
        print(f"{name}: {tot}/{len(ALL_CASES)}  ("
              + ", ".join(f"{k} {tally[(name, k)]}/{n}" for k, n in counts.items()) + ")")

    with open(RESULTS_PATH, "w") as f:
        json.dump({"model": MODEL, "summary": summary, "per_case": per_case}, f, indent=2)
    print(f"\nsaved {RESULTS_PATH}")


if __name__ == "__main__":
    main()
