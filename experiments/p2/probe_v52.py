"""v5.2 gate probe (entry 95 discipline: cheap probe before GPU-days).

A/B: SYSTEM_V5 vs SYSTEM_V52 on (a) supersession turns -- v5.2 must capture
"Y (previously X)"; (b) regression turns -- narrative extraction must be
unchanged. Runs against the llama-cpp /v1 server (env RG_OLLAMA_URL).
Deterministic pass/fail summary; no judge.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

os.environ.setdefault("RG_OLLAMA_URL", "http://localhost:8090/v1/chat/completions")
import extract_remote as ER
import llm_profile as LP

SUPERSESSION = [
    ("i've switched from green tea to black coffee for my morning routine",
     ["black coffee", "green tea"]),
    ("i quit my job at apple last week and started at google",
     ["google", "apple"]),
    ("we're no longer in the melbourne office, the team moved to sydney",
     ["sydney", "melbourne"]),
    ("i stopped using mem0 and moved everything to my own memory stack",
     ["own memory stack", "mem0"]),
    ("my mentor used to be alex but sophia has taken over that role now",
     ["sophia", "alex"]),
]
REGRESSION = [
    ("she values her moments of solitude because they help her recharge",
     ["solitude", "recharg"]),
    ("i appreciate snakes for how low-maintenance and fascinating they are",
     ["snakes", "low"]),
    ("working on projects together has really brought my wife and me closer",
     ["closer", "projects"]),
    ("my name is martin mark and i was born on 2 aug 1996",
     ["martin", "1996"]),
]


def run(system, model="qwen3:14b"):
    out = []
    for text, _ in SUPERSESSION + REGRESSION:
        facts, _, failed = ER.extract_via_v1(text, model, system)
        out.append(facts if not failed else None)
    return out


def score(name, results):
    n_sup = len(SUPERSESSION)
    sup_ok = reg_ok = 0
    for i, (text, needles) in enumerate(SUPERSESSION + REGRESSION):
        facts = results[i] or []
        blob = json.dumps(facts).lower()
        hit = all(n.lower() in blob for n in needles)
        if i < n_sup:
            sup_ok += hit
        else:
            reg_ok += hit
        if not hit:
            print(f"  [{name}] MISS: {text[:55]}")
            print(f"          got: {json.dumps(facts)[:120]}")
    print(f"{name}: supersession {sup_ok}/{n_sup}  regression {reg_ok}/{len(REGRESSION)}")
    return sup_ok, reg_ok


if __name__ == "__main__":
    print("== v5 baseline")
    s5, r5 = score("v5", run(LP.SYSTEM_V5))
    print("== v5.2 candidate")
    s52, r52 = score("v5.2", run(LP.SYSTEM_V52))
    verdict = "PASS" if (s52 >= 4 and r52 >= r5) else "FAIL"
    print(f"\nVERDICT: {verdict} (need supersession>=4/5 and no regression loss)")
