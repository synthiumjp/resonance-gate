#!/usr/bin/env python3
"""Census: how many assistant-turn report frames does rule (a) actually reach?

ox-alpha's review (2026-08-25) speculated that `rgx/parse.py::_report_frame`
requires a FIRST-PERSON matrix subject ("I remember you mentioned...") and so
misses the second-person frame ("You mentioned you took a cooking class"),
which may be the dominant interference phrasing. That would mean the hearsay
tier we are about to surface in QA is starved.

This settles it deterministically off the dataset -- no parse, no model, no
judge spend. It counts assistant-turn sentences carrying a report verb, split
by whether the reporting clause's SUBJECT is first person (reachable by rule
(a)) or second person (NOT reachable).

usage: python3 tools/hearsay_census.py [--users 0 1] [--examples 8]
"""
import argparse, collections, json, pathlib, re, sys

DATA = pathlib.Path.home() / "rg_private" / "halumem" / "HaluMem-Medium.jsonl"

# the report verbs rgx keys on; kept in sync with rgx/parse.py REPORT_VERBS
REPORT = (r"remember|recall|mention|say|said|tell|told|note|noted|notice|"
          r"noticed|hear|heard|see|seen|gather|understand|understood|"
          r"bring up|brought up|share|shared|describe|described")

# A report frame ASSERTS something about what the user previously said. Only
# past/perfect reporting counts -- "you see", "you tell me" in the present are
# discourse filler, not reports, and inflated the first cut of this census.
PAST = (r"remembered|recalled|mentioned|said|told|noted|noticed|heard|"
        r"gathered|understood|brought up|shared|described|expressed|"
        r"indicated|explained")

FIRST_RX = re.compile(rf"\b(i|we)\s+(\w+\s+){{0,2}}({REPORT})\b", re.I)
SECOND_RX = re.compile(rf"\b(you|you've|you have|you had)\s+(\w+\s+){{0,2}}"
                       rf"({PAST})\b", re.I)
# "as you mentioned", "since you said" -- still second-person matrix subject
SECOND_SUB_RX = re.compile(rf"\b(as|since|when|after)\s+you\s+(\w+\s+){{0,2}}"
                           rf"({PAST})\b", re.I)

# rule (b) expletive / GENERIC_SUBJ, and rule (c) HEDGE_ADV sentence opener,
# lexicons copied from rgx/parse.py. A second-person report frame that also
# trips one of these is still tagged evidential, so it is NOT a miss.
HEDGE_ADV = r"interestingly|curiously|apparently|supposedly|reportedly|perhaps"
GENERIC = r"people|some|others|many|one|everyone|someone"
RULE_BC_RX = re.compile(
    rf"(^\s*({HEDGE_ADV})\b)"                      # rule (c) opener
    rf"|(\b(it|there)('s|\s+is|\s+was|\s+seems|\s+appears)\b)"  # rule (b) expl
    rf"|(\b({GENERIC})\s+\w*\s*(say|says|said|think|thinks)\b)",  # rule (b) gen
    re.I)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()

    if not DATA.exists():
        sys.exit(f"dataset not found: {DATA}")

    counts = collections.Counter()
    examples = collections.defaultdict(list)

    with DATA.open() as fh:
        for idx, line in enumerate(fh):
            if idx not in args.users:
                continue
            rec = json.loads(line)
            for conv in rec.get("sessions", []):
                for t in conv.get("dialogue", []):
                    if t.get("role") != "assistant":
                        continue
                    for sent in sentences(t.get("content", "")):
                        # interrogatives are dropped upstream by rgx and are
                        # not report frames at all ("How do you see...?"),
                        # so they must not enter the census.
                        if sent.rstrip().endswith("?"):
                            counts["skipped: interrogative"] += 0
                            continue
                        first = bool(FIRST_RX.search(sent))
                        second = bool(SECOND_RX.search(sent)
                                      or SECOND_SUB_RX.search(sent))
                        if not (first or second):
                            continue
                        if first:
                            bucket = "first-person (rule (a) REACHES)"
                        elif RULE_BC_RX.search(sent):
                            # rule (b) expletive/generic subject, or rule (c)
                            # hedge-adverb opener, still tags it evidential
                            bucket = "second-person, but rule (b)/(c) catches"
                        else:
                            bucket = "second-person, NO rule catches (MISSED)"
                        counts[bucket] += 1
                        if len(examples[bucket]) < args.examples:
                            examples[bucket].append(sent[:160])

    total = sum(counts.values())
    if not total:
        sys.exit("no report-frame sentences found -- check the dataset schema; "
                 "run with a debug dump of one record's keys")

    print(f"assistant-turn report-frame sentences, users {args.users}: {total}\n")
    for bucket, n in counts.most_common():
        print(f"  {n:5d}  {100*n/total:5.1f}%  {bucket}")
    missed = counts["second-person, NO rule catches (MISSED)"]
    print(f"\nUNREACHABLE by any evidential rule: {missed} "
          f"({100*missed/total:.1f}% of report frames)")
    print("NOTE: rules (b)/(c) are approximated by regex here and the match is\n"
          "LENIENT (any expletive in the sentence, not just on the governing\n"
          "clause), so this is a LOWER bound on the miss rate.")
    for bucket in examples:
        print(f"\n--- {bucket} ---")
        for e in examples[bucket]:
            print(f"  {e}")


if __name__ == "__main__":
    main()
