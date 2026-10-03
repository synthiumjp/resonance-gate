"""Tables from results/<dir>: accuracy by category and overall, context tokens,
latency, ingest. Only questions answered by ALL listed systems are scored.

    python score.py results/test [system ...]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

d = sys.argv[1]
systems = sys.argv[2:] or ["sourcedrecall", "mem0", "rag"]
ans = {s: {r["qid"]: r for r in C.jsonl_read(os.path.join(d, f"ans_{s}.jsonl"))} for s in systems}
ctx = {s: {r["qid"]: r for r in C.jsonl_read(os.path.join(d, f"ctx_{s}.jsonl"))} for s in systems}
common = set.intersection(*[set(a) for a in ans.values()]) if ans else set()
out = []
w = lambda s="": out.append(s)  # noqa: E731
w(f"questions answered by all systems: {len(common)}\n")
w("| category | n | " + " | ".join(systems) + " |")
w("|---|---|" + "---|" * len(systems))
for cat in [1, 2, 3, 4, "overall"]:
    ids = [q for q in common if cat == "overall" or ans[systems[0]][q]["category"] == cat]
    cells = []
    for s in systems:
        k = sum(ans[s][q]["label"] == "CORRECT" for q in ids)
        cells.append(f"{k}/{len(ids)} = {100 * k / max(1, len(ids)):.1f}%")
    name = "overall (1-4)" if cat == "overall" else f"{cat} {C.CATS[cat]}"
    w(f"| {name} | {len(ids)} | " + " | ".join(cells) + " |")
w()
w("| | " + " | ".join(systems) + " |")
w("|---|" + "---|" * len(systems))
m = lambda f: [f(s) for s in systems]  # noqa: E731
w("| mean context tokens (len/4) | " + " | ".join(f"{sum(ctx[s][q]['ctx_tokens'] for q in common) / max(1, len(common)):.0f}" for s in systems) + " |")
w("| mean retrieval latency s | " + " | ".join(f"{sum(ctx[s][q]['latency'] for q in common) / max(1, len(common)):.3f}" for s in systems) + " |")
ing = {}
for s in systems:
    rows = C.jsonl_read(os.path.join(d, f"ingest_{s}.jsonl"))
    if s == "mem0":   # per-session log: exact even though the run was resumed (a restart repeated some store lines)
        rows = C.jsonl_read(os.path.join(d, "mem0_progress.jsonl"))
    ing[s] = (sum(r["messages"] for r in rows), sum(r["model_calls"] for r in rows), sum(r["seconds"] for r in rows))
w("| ingest messages | " + " | ".join(str(ing[s][0]) for s in systems) + " |")
w("| ingest model calls | " + " | ".join(str(ing[s][1]) for s in systems) + " |")
w("| ingest seconds | " + " | ".join(f"{ing[s][2]:.0f}" for s in systems) + " |")
w("| reader+judge s per question | " + " | ".join(f"{sum(ans[s][q]['reader_s'] + ans[s][q]['judge_s'] for q in common) / max(1, len(common)):.1f}" for s in systems) + " |")
print("\n".join(out))
