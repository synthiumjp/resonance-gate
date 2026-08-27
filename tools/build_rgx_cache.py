#!/usr/bin/env python3
"""Build the deterministic (rgx) extraction cache for a HaluMem user.

WHY THIS EXISTS. `~/rg_private/halumem/qa_rgx/cache_u0_v5.jsonl` -- the input
to every rgx-arm number we have -- was produced by an ad-hoc script that is
not in the tree. So until now the rgx arm's INPUT was not reproducible from
the repo, and no new user could be run at all. This closes that: it is the
generator, in the tree, validated by reproducing u0's existing cache exactly.

FORMAT. One JSON object per line, matching what halumem_run.ingest_user reads:
    {"h": sha1(turn_text), "f": [ {attribute, value, text, kind, turn, role,
                                   evidential}, ... ]}
`h` is the BARE sha1 of the turn text -- deliberately role-blind, because it
is a cache key shared with the LLM arm's caches (see wire.role_hash_guard for
why that tradeoff is deliberate and how it is detected).

Turn text is truncated to 1800 chars before hashing AND before extraction,
exactly as ingest_user does, or the hashes will not match at read time.

    python3 tools/build_rgx_cache.py --user 1 --out ~/rg_private/halumem/qa_rgx/cache_u1_v5.jsonl
    python3 tools/build_rgx_cache.py --user 0 --verify ~/rg_private/halumem/qa_rgx/cache_u0_v5.jsonl
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, "/home/jp/rg")
DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"
TRUNC = 1800          # must match halumem_run.ingest_user


def owner_of(rec):
    """The profile owner's name.

    persona_info is a STRING, not a dict -- "[Recorded on ...] Name: Martin
    Mark; Gender: Male; ...". Reading it as a dict silently yields None, the
    extractor falls back to "The user", and every emitted proposition names
    the wrong subject: that produced a cache 90% of whose records differed
    from the banked one on exactly that token.
    """
    pi = rec.get("persona_info")
    if isinstance(pi, dict):
        for k in ("name", "user_name", "full_name"):
            if pi.get(k):
                return str(pi[k])
        return None
    if isinstance(pi, str):
        m = re.search(r"\bName:\s*([^;\n]+)", pi)
        if m:
            return m.group(1).strip()
    return None


def records_for(ex, text, role, session, turn):
    out = []
    for r in ex.extract_turn(text, role, session, turn):
        out.append({"attribute": r.predicate, "value": r.value,
                    "text": r.text, "kind": r.kind, "turn": r.turn,
                    "role": r.role, "evidential": r.evidential})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--out")
    ap.add_argument("--verify", help="compare against an existing cache "
                                     "instead of writing")
    ap.add_argument("--owner", help="override the owner name")
    args = ap.parse_args()

    from rgx import Extractor

    with DATA.open() as fh:
        for i, line in enumerate(fh):
            if i == args.user:
                rec = json.loads(line)
                break
        else:
            sys.exit(f"user {args.user} not in {DATA}")

    owner = args.owner or owner_of(rec)
    print(f"user {args.user}: owner={owner!r}", file=sys.stderr)
    ex = Extractor(owner_name=owner)

    seen, lines, n_turns = set(), [], 0
    t0 = time.time()
    for si, sess in enumerate(rec["sessions"]):
        for ti, t in enumerate(sess.get("dialogue", [])):
            text = str(t.get("content", "")).strip()[:TRUNC]
            if not text:
                continue
            n_turns += 1
            h = hashlib.sha1(text.encode()).hexdigest()
            if h in seen:            # same key would be written twice
                continue
            seen.add(h)
            lines.append({"h": h,
                          "f": records_for(ex, text, t.get("role", "user"),
                                           si, ti)})
            if n_turns % 250 == 0:
                el = time.time() - t0
                print(f"  {n_turns} turns, {el:.0f}s "
                      f"({el/n_turns:.3f}s/turn)", file=sys.stderr)

    print(f"{n_turns} turns -> {len(lines)} cache entries, "
          f"{time.time()-t0:.0f}s", file=sys.stderr)

    if args.verify:
        old = {}
        for line in open(args.verify):
            d = json.loads(line)
            old[d["h"]] = d["f"]
        new = {d["h"]: d["f"] for d in lines}
        only_old, only_new = set(old) - set(new), set(new) - set(old)
        common = set(old) & set(new)
        same = sum(1 for h in common if old[h] == new[h])
        # Which FIELDS actually differ? `turn` is provenance metadata that
        # nothing downstream reads (grep: no consumer of fct["turn"] in
        # halumem_run / run_wire / wire), so a difference there is cosmetic.
        # A difference in attribute/value/text/evidential is NOT.
        import collections as _c
        fielddiff = _c.Counter()
        semantic_diff = 0
        for h in common:
            a, b = old[h], new[h]
            if a == b:
                continue
            if len(a) != len(b):
                fielddiff["RECORD COUNT"] += 1
                semantic_diff += 1
                continue
            bad = False
            for ra, rb in zip(a, b):
                for k in set(ra) | set(rb):
                    if ra.get(k) != rb.get(k):
                        fielddiff[k] += 1
                        if k != "turn":
                            bad = True
            semantic_diff += bad
        print("\n  differing keys by FIELD:")
        for k, v in fielddiff.most_common():
            note = "  (cosmetic: nothing reads it)" if k == "turn" else ""
            print(f"    {k:<14s}{v:5d}{note}")
        print(f"\n  keys differing ONLY in cosmetic fields : "
              f"{len(common)-same-semantic_diff}")
        print(f"  keys with a SEMANTIC difference        : {semantic_diff}")
        print(f"\n=== verify vs {args.verify} ===")
        print(f"  entries: existing {len(old)}, regenerated {len(new)}")
        print(f"  keys only in existing : {len(only_old)}")
        print(f"  keys only in new      : {len(only_new)}")
        print(f"  common keys           : {len(common)}")
        print(f"  IDENTICAL records     : {same}/{len(common)} "
              f"({100*same/max(len(common),1):.1f}%)")
        if same != len(common):
            for h in list(common):
                if old[h] != new[h]:
                    print("\n  first differing key:", h)
                    print("   existing:", json.dumps(old[h])[:300])
                    print("   new     :", json.dumps(new[h])[:300])
                    break
        return

    if not args.out:
        sys.exit("--out required unless --verify")
    outp = pathlib.Path(args.out).expanduser()
    outp.parent.mkdir(parents=True, exist_ok=True)
    with outp.open("w") as fh:
        for d in lines:
            fh.write(json.dumps(d) + "\n")
    print(f"wrote {outp} ({len(lines)} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()
