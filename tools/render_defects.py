#!/usr/bin/env python3
"""Scan emitted records for RENDER defects -- ungrammatical output.

e234's lesson: 5.5-9% of every record on both users was ungrammatical in a way
token overlap cannot see, and it was found by READING raw output, not by any
metric. This makes that scan repeatable and gives every fix a before/after
number that needs no judge.

Each signature is a specific, named defect in the person-shift/render path.
These are correctness bugs in shipped output regardless of any benchmark: a
memory that says "Martin Mark've been feeling" is wrong for a user, not just
for a scorer.

    python3 tools/render_defects.py --cache ~/rg_private/halumem/qa_rgx/cache_u0_v5.jsonl
    python3 tools/render_defects.py --cache ... --show clitic_residue
"""
import argparse
import collections
import json
import pathlib
import re

# Each: name -> (compiled pattern, one-line description)
SIGNATURES = {
    "clitic_residue": (
        # NOT |s: "Martin Mark's" is a legitimate possessive, and including it
        # made this signature fire on 66% of records, all false positives.
        re.compile(r"\b\w+'(ve|ll|re|m)\b|\bn't\b", re.I),
        "contraction survived the person shift ('Martin Mark've')"),
    "copular_aux_stripped": (
        re.compile(r"\b(is|are|was|were)\s+(been|being)\b", re.I),
        "aux dropped from a copular render ('is been vital')"),
    "bare_been": (
        re.compile(r"^(?!.*\b(has|have|had|having)\b).*\bbeen\b", re.I),
        "'been' with no perfect auxiliary anywhere"),
    "stray_complementizer": (
        re.compile(r"\b(is|are|was|were|seems|seem)\s+that\s+a?\b", re.I),
        "matrix complementizer leaked into the child span ('is that a')"),
    "seems_it_like": (
        re.compile(r"\bseems?\s+it\s+like\b", re.I),
        "raising/expletive residue ('seems it like')"),
    "advmod_between_verb_and_obj": (
        re.compile(r"\b(visited|maintained|includes|evolved|improved|reached)"
                   r"\s+(recently|successfully|now|also|already|still)\s+\w",
                   re.I),
        "post-verbal adverb ordered between verb and object"),
    "plural_head_singular_agr": (
        re.compile(r"\b(\w+s)\s+has\s+\w+ed\b", re.I),
        "agreement taken off an embedded head ('insights has improved')"),
    "repeated_owner_possessive": (
        re.compile(r"\b(\w+ \w+)'s .*\b\1's\b"),
        "owner's full name repeated where a pronoun belongs ('his')"),
    "repeated_owner_name": (
        re.compile(r"\b(\w+ \w+)\b.*\b\1\b.*\b\1\b"),
        "owner's full name appears 3+ times in one proposition"),
    "first_person_residue": (
        re.compile(r"\b(I|my|me|mine|myself)\b"),
        "first person survived the shift"),
    "doubled_aux": (
        re.compile(r"\b(is|are|was|were|has|have)\s+\1\b", re.I),
        "auxiliary emitted twice ('is is')"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--show", help="print examples for this signature")
    ap.add_argument("--n", type=int, default=8)
    args = ap.parse_args()

    texts = []
    for line in pathlib.Path(args.cache).expanduser().open():
        try:
            d = json.loads(line)
        except Exception:
            continue
        for f in d.get("f", []):
            t = f.get("text")
            if t:
                texts.append(t)

    counts = collections.Counter()
    examples = collections.defaultdict(list)
    hit_any = 0
    for t in texts:
        hit = False
        for name, (rx, _) in SIGNATURES.items():
            if rx.search(t):
                counts[name] += 1
                hit = True
                if len(examples[name]) < 40:
                    examples[name].append(t)
        hit_any += hit

    print(f"\n=== render defects: {len(texts)} emitted records ===\n")
    for name, (_, desc) in SIGNATURES.items():
        n = counts[name]
        flag = "  <-- " if n else "      "
        print(f"  {name:<30s}{n:5d}  ({100*n/max(len(texts),1):5.2f}%)"
              f"{flag}{desc if n else ''}")
    print(f"\n  records with >=1 defect: {hit_any} "
          f"({100*hit_any/max(len(texts),1):.2f}%)")

    if args.show:
        print(f"\n--- examples: {args.show} ---")
        for t in examples[args.show][:args.n]:
            print(f"  {t[:170]}")


if __name__ == "__main__":
    main()
