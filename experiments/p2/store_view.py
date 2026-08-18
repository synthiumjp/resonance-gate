"""Read a user's memory the way the person it is about would read it.

WHY THIS EXISTS. Seven percent of user 10's store shipped as broken English
("Michelle Hernandez plans to joining a club", "is motivated by to contribute")
and nothing in the stack noticed for months. Not because anyone was careless
-- because no instrument we had could see it:

  the offline proxies compare TOKEN SETS, so they are near-invariant to
  whether the words form a sentence;
  the official judge's per-record score is dominated by gold membership --
  in-gold records mean 1.330, out-of-gold 0.022, and no in-gold record scores
  0 -- so ranking by it ranks by "did HaluMem enumerate this", not by quality;
  every aggregate we report is a mean over one of those two.

There was no signal to miss. The only way to see it was to look at the text,
and we never printed the text. So this prints the text.

Two modes:

  view   the store as prose, grouped, with the noise made visible: how much
         is one-off intentions, how many values compete for the same
         attribute, how much is still provisional.
  lint   the checks a human would make on sight, as assertions. Exits non-zero
         when any fire, so a run can fail on them instead of shipping them.

LINT IS THE POINT. `view` needs a person; `lint` runs every time. The rule
this file encodes: if a defect would be obvious to someone reading the output,
it belongs in lint, not in a metric.
"""
import argparse
import collections
import json
import os
import re
import sys

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")

# Each check is (name, regex, why it is wrong to a reader).
MALFORMED = [
    ("verb_gerund_join", re.compile(r"\b(?:plans|aims) to \w+ing\b", re.I),
     "'plans to' takes a bare infinitive, not a gerund"),
    ("prep_infinitive_join", re.compile(r"\b(?:motivated by|values|prefers) to \w+", re.I),
     "a preposition-verb takes a noun phrase, not an infinitive"),
    ("double_infinitive", re.compile(r"\bto to \b", re.I), "doubled 'to'"),
    ("empty_value", re.compile(r"\b(?:is|are)\s*\((?:asserted|provisional)\)", re.I),
     "attribute rendered with no value"),
    ("dangling_conjunction", re.compile(r"\b(?:and|but|or|because)\s*\((?:asserted|provisional)\)", re.I),
     "sentence truncated mid-clause"),
]
TIER = re.compile(r"\s*\((asserted|provisional|inferred|retracted)\)\s*$")


def load(version, user=0):
    p = f"{RESULTS}/rgp2-{version}/rgp2_eval_results.jsonl"
    with open(p, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i == user:
                return json.loads(line)
    raise SystemExit(f"no user {user} in {p}")


def records(u):
    return [(si, str(m)) for si, s in enumerate(u["sessions"])
            for m in s.get("extracted_memories", [])]


def view(u):
    recs = records(u)
    print(f"{len(recs)} memories over {len(u['sessions'])} conversations\n")

    print("HOW CONFIDENT IT CLAIMS TO BE")
    t = collections.Counter(m.group(1) for _, r in recs
                            for m in [TIER.search(r)] if m)
    n = sum(t.values()) or 1
    for k, v in t.most_common():
        print(f"  {k:<14}{v:>6}  {v/n:5.0%}")
    if t.most_common(1) and t.most_common(1)[0][1] / n > 0.8:
        print(f"  -> {t.most_common(1)[0][0]} on {t.most_common(1)[0][1]/n:.0%} of "
              "everything: the confidence signal is not discriminating")

    print("\nCOMPETING VALUES FOR ONE ATTRIBUTE (what happens if you ask?)")
    lead = collections.defaultdict(set)
    for _, r in recs:
        body = TIER.sub("", r)
        mo = re.match(r"(.+?\b(?:works as|works at|lives in|is motivated by|"
                      r"'s [a-z ]+ is))\s+(.+)$", body, re.I)
        if mo:
            lead[mo.group(1).strip().lower()].add(mo.group(2).strip().lower()[:44])
    for k, v in sorted(lead.items(), key=lambda x: -len(x[1]))[:6]:
        if len(v) > 1:
            print(f"  {len(v):3d} values | {k[:52]}")
            for x in sorted(v)[:3]:
                print(f"        - {x}")

    print("\nWHAT IT LEARNED FIRST vs LAST")
    for label, si in (("first conversation", 0),
                      ("last conversation", len(u["sessions"]) - 1)):
        got = [r for s, r in recs if s == si][:5]
        print(f"  {label}:")
        for r in got:
            print(f"      {TIER.sub('', r)[:88]}")


def lint(u, quiet=False):
    recs = records(u)
    fired = []
    for name, rx, why in MALFORMED:
        hits = [r for _, r in recs if rx.search(r)]
        if hits:
            fired.append((name, len(hits), why, hits[0]))
    if not quiet:
        print(f"lint: {len(recs)} memories")
        if not fired:
            print("  clean")
        for name, n, why, eg in fired:
            print(f"  FAIL {name}: {n} records ({n/len(recs):.1%}) -- {why}")
            print(f"       e.g. {eg[:92]}")
    return 1 if fired else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("view", "lint"))
    ap.add_argument("--version", default="s5-base")
    ap.add_argument("--user", type=int, default=0)
    a = ap.parse_args()
    u = load(a.version, a.user)
    if a.mode == "view":
        view(u)
        return 0
    return lint(u)


if __name__ == "__main__":
    sys.exit(main())
