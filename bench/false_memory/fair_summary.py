"""Summary of the fair rerun (2026-10-09, adversarial review A1-A5): for each
results dir, each system's counts (answer view, audited when overrides were
applied) and a two-sided Fisher exact test of each system against
sourcedrecall. Counts only.

    python fair_summary.py <results dir> [<results dir> ...]
"""
import json
import math
import os
import sys


def fisher(a, n1, b, n2):
    """Two-sided Fisher exact p for a/n1 vs b/n2."""
    total, k = n1 + n2, a + b

    def p(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(total, k)
    lo, hi = max(0, k - n2), min(k, n1)
    obs = p(a)
    return min(1.0, sum(p(x) for x in range(lo, hi + 1) if p(x) <= obs * (1 + 1e-9)))


METRICS = [("false_memory_all", "false memories", True),
           ("side_recall_abe", "new / true state given", False),
           ("control_recall", "control questions answered", False)]


def main(dirs):
    for d in dirs:
        r = json.load(open(os.path.join(d, "results.json")))["systems"]
        print(f"== {os.path.basename(os.path.normpath(d))}")
        for key, name, lower_better in METRICS:
            cells = {}
            for s, v in r.items():
                m = (v.get("views_audited") or v.get("views") or {}).get("answer")
                x = (m or {}).get("all", {}).get(key) if m else None
                if x:
                    cells[s] = (x["k"], x["n"])
            if not cells:
                continue
            ours = cells.get("sourcedrecall")
            parts = []
            for s, (k, n) in cells.items():
                cell = f"{s} {k}/{n}"
                if ours and s != "sourcedrecall":
                    cell += f" (p={fisher(ours[0], ours[1], k, n):.2f})"
                parts.append(cell)
            print(f"  {name}: " + "; ".join(parts))


if __name__ == "__main__":
    main(sys.argv[1:])
