#!/usr/bin/env python3
"""Run the refusal suite and print a capability x test-type scorecard.

The suite (rgx/refusal_cases.py) is CheckList's structure over
CommitmentBank's inventory. This runs it as a REPORT rather than as a test,
so an unfixed row is visible rather than red -- the point is to see the whole
matrix at once and pick, not to gate a commit on every cell.

    python tools/refusal_report.py            # scorecard
    python tools/refusal_report.py --verbose  # every case, with output
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rgx import Extractor                       # noqa: E402
from rgx.refusal_cases import CASES, INVARIANCE  # noqa: E402

OWNER = "Alex Reyes"


def texts(ex, s, role):
    ex.reset_world()
    return [r.text for r in ex.extract_turn(s, role=role)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    ex = Extractor(owner_name=OWNER)

    rows = defaultdict(lambda: {"mft": [0, 0], "dir": [0, 0], "extra": [0, 0]})
    fails = []
    for c in CASES:
        cap = c["capability"]
        out = texts(ex, c["irrealis"], c["role"])
        blob = " || ".join(out).lower()

        # MFT -- the irrealis frame must not produce the proposition
        if c.get("must_not"):
            bad = [o for o in out if c["must_not"].lower() in o.lower()]
            if c.get("unless_contains"):
                bad = [o for o in bad
                       if c["unless_contains"].lower() not in o.lower()]
            ok = not bad
            rows[cap]["mft"][1] += 1
            rows[cap]["mft"][0] += ok
            if not ok:
                fails.append(("MFT", cap, c["operator"], c["irrealis"],
                              f"asserted {c['must_not']!r}", bad))

        # the irrealis frame may still OWE a fact (negation, factive)
        if c.get("assert_instead"):
            ok = c["assert_instead"].lower() in blob
            rows[cap]["extra"][1] += 1
            rows[cap]["extra"][0] += ok
            if not ok:
                fails.append(("OWED", cap, c["operator"], c["irrealis"],
                              f"missing {c['assert_instead']!r}", out))

        # DIR -- the matched declarative MUST produce it, else the MFT above
        # proves nothing (the parser may simply be failing on the sentence)
        if c.get("control_asserts"):
            cout = texts(ex, c["control"], c.get("control_role", "user"))
            ok = c["control_asserts"].lower() in " || ".join(cout).lower()
            rows[cap]["dir"][1] += 1
            rows[cap]["dir"][0] += ok
            if not ok:
                fails.append(("DIR", cap, c["operator"], c["control"],
                              f"control did not assert {c['control_asserts']!r}",
                              cout))
        if args.verbose:
            print(f"\n[{cap}/{c['operator']}] {c['irrealis']}")
            for o in out:
                print(f"    -> {o}")
            if not out:
                print("    (nothing)")

    # INVARIANCE -- refusal survives rewording the marker
    inv = defaultdict(lambda: [0, 0])
    for cap, needle, role, variants in INVARIANCE:
        for v in variants:
            out = texts(ex, v, role)
            ok = needle.lower() not in " || ".join(out).lower()
            inv[cap][1] += 1
            inv[cap][0] += ok
            if not ok:
                fails.append(("INV", cap, "paraphrase", v,
                              f"asserted {needle!r}", out))

    print(f"{'capability':14s} {'MFT (refuses)':>14s} {'DIR (control)':>14s} "
          f"{'OWED (still asserts)':>21s} {'INV (paraphrase)':>17s}")
    for cap in sorted(rows):
        r = rows[cap]
        def cell(p):
            return f"{p[0]}/{p[1]}" if p[1] else "-"
        i = inv.get(cap)
        print(f"{cap:14s} {cell(r['mft']):>14s} {cell(r['dir']):>14s} "
              f"{cell(r['extra']):>21s} "
              f"{(f'{i[0]}/{i[1]}' if i else '-'):>17s}")

    if fails:
        print(f"\n{len(fails)} FAILING CELLS:")
        for kind, cap, op, sent, why, out in fails:
            print(f"\n  [{kind}] {cap} / {op}")
            print(f"      in : {sent}")
            print(f"      {why}")
            for o in out[:3]:
                print(f"      out: {o[:88]}")
    else:
        print("\nall cells pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
