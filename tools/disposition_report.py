#!/usr/bin/env python3
"""Read halumem_run.ingest_user's RG_DISPOSITION log + a STORED_BUT_LOST
autopsy (tools/update_miss_autopsy.py's per-point output) and answer: for
each gold memory-update point that rgx EMITTED but the store does not
contain, which stage killed it?

Matching: update_miss_autopsy.py's "best_record" field is exactly
`fct.get("text")` off the record that best covers that gold point -- and
the disposition log carries that SAME "text" for every record (added
alongside the existing rid/attr/value/evidential fields). So the primary
match is EXACT string equality on "text". Falls back to token-containment
against the same session's records only if no exact hit (should be rare --
the two logs are built from the same cache).

Usage:
    python3 tools/disposition_report.py \\
        [--disposition ~/rg_private/halumem/qa_rgx/disposition_u0.jsonl] \\
        [--miss /tmp/update_miss_u0.jsonl] [--klass STORED_BUT_LOST]
"""
import argparse
import collections
import json
import os
import re
import sys

_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"the", "a", "an", "is", "are", "was", "were", "his", "her", "their",
         "to", "of", "and", "in", "for", "on", "with", "as", "that", "this",
         "has", "have", "had", "he", "she", "they", "it", "s", "from", "by",
         "at", "be", "been", "or", "but", "not", "its", "also", "which"}


def toks(s):
    return {w for w in _WORD.findall((s or "").lower()) if w not in _STOP}


def contained(gold, cand):
    g = toks(gold)
    return len(g & toks(cand)) / len(g) if g else 0.0


# The three competing hypotheses this instrument was built to referee.
# "text-collision" is a 4th mechanism this script's own matching surfaced
# (see README below) -- not one of the three, kept separate on purpose.
def _bucket(disp):
    if disp == "became-hearsay":
        return "G1 (hearsay tier)"
    if disp == "merged-into-existing-slot":
        return "G2 (cluster-merge collision)"
    if disp in ("excluded-by-attr", "dropped-by-prefilter/quality",
                "dropped-by-subject-hygiene"):
        return "G3 (well-formedness/exclusion gate)"
    if disp in ("became-asserted", "became-provisional"):
        return "(reached store -- see text_lost)"
    return "other/unmatched"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disposition", default=os.environ.get(
        "RG_DISPOSITION", os.path.expanduser(
            "~/rg_private/halumem/qa_rgx/disposition_u0.jsonl")))
    ap.add_argument("--miss", default="/tmp/update_miss_u0.jsonl")
    ap.add_argument("--klass", default="STORED_BUT_LOST")
    ap.add_argument("--cover", type=float, default=0.6,
                     help="fallback token-containment threshold")
    args = ap.parse_args()

    disp_rows = [json.loads(l) for l in open(args.disposition)]
    by_text = collections.defaultdict(list)
    for d in disp_rows:
        if d.get("text"):
            by_text[d["text"]].append(d)

    miss_rows = [json.loads(l) for l in open(args.miss)]
    targets = [r for r in miss_rows if r.get("class") == args.klass]
    if not targets:
        sys.exit(f"no rows with class=={args.klass!r} in {args.miss}")

    print(f"=== disposition report: {len(targets)} {args.klass} gold "
          f"point(s), {len(disp_rows)} disposition records ===\n")

    verdict = collections.Counter()
    unresolved = []
    for i, r in enumerate(targets, 1):
        gold = r.get("gold", "")
        best_record = r.get("best_record", "")
        session = r.get("session")
        exact = by_text.get(best_record, [])
        match_kind = "exact" if exact else None
        matches = exact
        if not matches:
            # Fallback: token-containment against every disposition record
            # from the SAME session (should not usually be needed).
            cands = [d for d in disp_rows if d.get("session") == session]
            scored = sorted(cands, key=lambda d: -contained(best_record,
                                                             d.get("text", "")))
            if scored and contained(best_record, scored[0].get("text", "")) >= args.cover:
                matches = [scored[0]]
                match_kind = "fuzzy"

        print(f"--- #{i}  session {session} ---")
        print(f"  GOLD  : {gold[:150]}")
        print(f"  RECORD: {best_record[:150]}")
        if not matches:
            print("  DISPOSITION: NO MATCH in disposition log "
                  "(premise check failed for this point -- see report)")
            verdict["unmatched"] += 1
            unresolved.append(r)
            print()
            continue
        for m in matches:
            tl = m.get("text_lost")
            print(f"  DISPOSITION [{match_kind}]: {m['disposition']}"
                  f"  ({_bucket(m['disposition'])})"
                  f"  evidential={m.get('evidential')}  text_lost={tl}")
            if m.get("reason"):
                print(f"    reason: {m['reason']}")
            bucket = _bucket(m["disposition"])
            if m["disposition"] in ("became-asserted", "became-provisional") and tl:
                bucket = "TEXT-COLLISION (same value, first-write-wins text)"
            verdict[bucket] += 1
        print()

    print("=== aggregate verdict ===")
    for k, v in verdict.most_common():
        print(f"  {k:<45s} {v:3d}  ({100*v/len(targets):5.1f}%)")
    if unresolved:
        print(f"\n{len(unresolved)} point(s) had NO matching disposition "
              f"record at all -- the premise (rgx emitted a covering record "
              f"for this gold point) does not hold for these; treat as a "
              f"separate finding, not evidence for any of G1/G2/G3.")


if __name__ == "__main__":
    main()
