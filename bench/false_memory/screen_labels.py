"""Screen the trust labels against the benchmark (2026-10-05).

A label is shown to the agent only if it means what it says, item by item
(the validity-screening rule: a signal that looks right on average can be
useless or inverted for the individual line). For every line of the memory
block sourcedrecall returned for a probe, this records which labels the line
carries and whether the line is about the out-of-date state (the probe's
forbidden proposition) or the current one (the probe's expected terms).

    python screen_labels.py <results dir> [<cases file>] [--counts-only]

Per label it reports:
  on_stale   share of lines about the out-of-date state that carry it
  on_current lines about the current state that carry it (a label saying
             "no longer true" or "may have changed" on the current fact
             misleads)
  on_control lines in scenarios where nothing changed (class f) that carry it
  precision  of the lines carrying it, how many are about the out-of-date
             state, against the same share among unlabelled lines

"About the out-of-date state" is lexical: the line contains the distinctive
words of the forbidden proposition (those not in the question). "About the
current state": it contains an expected term. Both are approximations; the
counts say how many lines were matched each way. --counts-only prints no
text (for the blind sets).
"""
import collections
import json
import os
import re
import sys

LABELS = {
    "no longer true": re.compile(r"\(no longer true\b", re.I),
    "may have changed since": re.compile(r"\(may have changed since\b", re.I),
    "said in passing": re.compile(r"\(said in passing\b", re.I),
    "model note": re.compile(r"note written by your model", re.I),
}
STOP = set("""the a an and or of to in on at for with from by as is are was were be been
has have had does did do not no their they them his her him she he its it this that
these those who which what when where why how user currently still now any some
about your you my me i we our there here into over after before than then just
also very really""".split())


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOP}


def stale_words(prop, question, owner):
    return words(prop) - words(question) - words(owner)


def main(results, cases_path, counts_only):
    cases = {c["id"]: c for c in map(json.loads, open(cases_path))}
    raw = [json.loads(l) for l in open(os.path.join(results, "raw_sourcedrecall.jsonl"))]
    n = collections.Counter()
    examples = collections.defaultdict(list)
    for r in raw:
        c = cases.get(r["id"])
        if not c or "probes" not in r:
            continue
        for p, gold in zip(r["probes"], c["probes"]):
            block = p.get("block") or ""
            lines = [l for l in block.splitlines() if l.startswith("- ")]
            forbid = (gold.get("forbid") or {}).get("prop") or ""
            sw = stale_words(forbid, gold["q"], c["owner"])
            terms = [t.lower() for t in (gold.get("expect") or {}).get("terms", [])]
            for line in lines:
                low = line.lower()
                lw = words(line)
                # the label text itself repeats the fact; judge the quote part
                quote = re.split(r"\s\((?:no longer true|may have changed since|said in passing)", line)[0].lower()
                is_stale = bool(sw) and len(sw & words(quote)) >= min(2, len(sw))
                is_cur = any(t in quote for t in terms)
                if is_stale and is_cur:
                    is_stale = is_cur = False      # ambiguous: both in one line
                control = c.get("class") == "f"
                labs = [name for name, rx in LABELS.items() if rx.search(line)]
                n["lines"] += 1
                n["stale_lines"] += is_stale
                n["cur_lines"] += is_cur
                n["control_lines"] += control
                if not labs:
                    n["unlab"] += 1
                    n["unlab_stale"] += is_stale
                for lab in labs:
                    n[(lab, "fired")] += 1
                    n[(lab, "stale")] += is_stale
                    n[(lab, "cur")] += is_cur
                    n[(lab, "control")] += control
                    if is_cur and not counts_only:
                        examples[lab].append((c["id"], gold["q"], line[:200]))
    print(f"lines {n['lines']}: about the out-of-date state {n['stale_lines']}, "
          f"about the current state {n['cur_lines']}, in no-change scenarios {n['control_lines']}")
    base = n["unlab_stale"] / n["unlab"] if n["unlab"] else 0
    print(f"unlabelled lines: {n['unlab']}, of which out-of-date {n['unlab_stale']} ({base:.1%})")
    for lab in LABELS:
        f = n[(lab, "fired")]
        if not f:
            print(f"{lab}: never fired")
            continue
        print(f"{lab}: fired {f} | on out-of-date lines {n[(lab,'stale')]}/{n['stale_lines']} "
              f"| on CURRENT lines {n[(lab,'cur')]}/{n['cur_lines']} "
              f"| in no-change scenarios {n[(lab,'control')]}/{n['control_lines']} "
              f"| precision {n[(lab,'stale')]}/{f} = {n[(lab,'stale')]/f:.1%} vs unlabelled {base:.1%}")
    for lab, ex in examples.items():
        print(f"\n{lab} on a current-state line:")
        for e in ex[:8]:
            print("  ", e)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    res = args[0]
    cases = args[1] if len(args) > 1 else os.environ.get("FM_CASES", "cases.jsonl")
    main(res, cases, "--counts-only" in sys.argv)
