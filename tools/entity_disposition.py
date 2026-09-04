#!/usr/bin/env python3
"""Disposition log for person-mention linking (rgx/entities.py).

The instrument, not the mechanism. For every capitalised person-shaped
mention in a record set it logs which strategy resolved it -- or why it was
declined -- so the population each strategy actually serves is measured
rather than assumed. This arc's two largest findings (e250's hearsay leak,
e255's text collision) both came from a disposition log built to answer a
different question; ledger sec. 4 is the standing reason to build the
instrument before believing the mechanism.

    python tools/entity_disposition.py CACHE.jsonl --owner "Martin Mark"
    python tools/entity_disposition.py CACHE.jsonl --owner "Martin Mark" \
        --peritem out.jsonl --show 20

Reads the cache shape written by rgx.facts.write_cache:
    {"h": ..., "f": [{"attribute","value","text","kind","turn","role"}, ...]}
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])

from rgx.entities import Registry, attach_relations   # noqa: E402

# Capitalised tokens that are NOT person mentions. Without this the
# disposition denominator is dominated by sentence-initial function words
# ("This" 362, "By" 280, "The" 200 on u0) and the "unknown" rate reads as
# unresolved PEOPLE when it is mostly punctuation-adjacent grammar. Read the
# matches before believing the count (ledger sec. 4).
NON_NAMES = frozenset("""
This That These Those The A An As By While Despite With Just Yes No In On At
For From To If When Whether During After Before Since Because However
Their There They It Its He She His Her We Our You Your I My Me Am Are Is Was
Were Be Been Being Do Does Did Have Has Had Will Would Can Could Should May
Might Must Not And Or But So Then Than Also Now Here What Which Who Whom How
Why Where Both Each Every All Some Any More Most Much Many Such Other Another
Overall Additionally Furthermore Moreover Given Though Although Once Upon
""".split())


def is_name_shaped(mention, start, text):
    """A mention worth counting as a PERSON candidate."""
    if mention in NON_NAMES:
        return False
    # sentence-initial single capitalised word: grammar, not a name, unless
    # it is a multi-part CamelCase run ("WilliamsJoshua")
    if start == 0 and not re.match(r"^[A-Z][a-z]+[A-Z]", mention):
        return False
    return True


def load(path):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for si, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            for f in d.get("f", []) or []:
                if f.get("text"):
                    recs.append(f)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--min-confidence", type=float, default=1.0)
    ap.add_argument("--peritem", help="write one JSON line per mention")
    ap.add_argument("--show", type=int, default=10,
                    help="sample N rewritten records to stdout")
    args = ap.parse_args()

    recs = load(args.cache)
    reg = Registry(owner_name=args.owner).add_records(recs).build()

    print(f"records: {len(recs)}")
    print(f"\n=== REGISTRY ({len(reg.people)} people) ===")
    for canon, p in sorted(reg.people.items(),
                           key=lambda kv: -sum(kv[1].relations.values())):
        rels = ", ".join(f"{r}x{n}" for r, n in p.relations.most_common())
        flag = "  <-- CONTESTED" if p.contested else ""
        al = f"  aliases={sorted(p.aliases)}" if p.aliases else ""
        print(f"  {canon:20s} {p.relation or '-':12s} "
              f"conf={p.relation_confidence:.2f}  [{rels}]{al}{flag}")

    strat = Counter()
    per_person = Counter()
    changed = []
    log_all = []
    for r in recs:
        log = []
        new = attach_relations(r["text"], reg, args.owner,
                               min_confidence=args.min_confidence, _log=log)
        for e in log:
            e["name_shaped"] = is_name_shaped(
                e["mention"], e.get("span_start", 1), r["text"])
        for e in log:
            if not e.get("name_shaped", True):
                strat["filtered"] += 1
                continue
            strat[e["strategy"]] += 1
            if e["person"]:
                per_person[e["person"]] += 1
            e["record_kind"] = r.get("kind")
            e["record_turn"] = r.get("turn")
            log_all.append(e)
        if new != r["text"]:
            changed.append((r.get("kind"), r["text"], new))

    total = sum(v for k, v in strat.items() if k != "filtered")
    print(f"\n=== MENTION DISPOSITION (n={total}) ===")
    linked = strat["exact"] + strat["alias"] + strat["unique"]
    print(f"  (filtered as non-name tokens: {strat['filtered']})")
    for k in ("exact", "alias", "unique", "ambiguous", "unknown", "owner"):
        n = strat.get(k, 0)
        if not total:
            continue
        mark = "  LINKED" if k in ("exact", "alias", "unique") else ""
        print(f"  {k:12s} {n:6d}  {100.0*n/total:5.1f}%{mark}")
    if total:
        print(f"  {'-'*30}\n  linked       {linked:6d}  "
              f"{100.0*linked/total:5.1f}%")

    print(f"\n=== RECORDS REWRITTEN: {len(changed)} of {len(recs)} "
          f"({100.0*len(changed)/max(1,len(recs)):.2f}%) ===")
    for kind, old, new in changed[:args.show]:
        print(f"  [{kind}]\n    -  {old[:130]}\n    +  {new[:130]}")

    if args.peritem:
        with open(args.peritem, "w", encoding="utf-8") as fh:
            for e in log_all:
                fh.write(json.dumps(e) + "\n")
        print(f"\nwrote {len(log_all)} mention rows -> {args.peritem}")


if __name__ == "__main__":
    main()
