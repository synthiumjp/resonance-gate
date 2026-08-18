"""Late-session gold is not missing from our store -- it is FRAGMENTED across it.

Follows ceiling_decay.py, which killed the comfortable explanation for entry
204's collapse: the single-turn ceiling is FLAT across session position (it
even rises slightly late), so late gold is stated in its own session just as
plainly as early gold. The benchmark did not move the target out of reach; we
stopped hitting it.

This file asks what we emit instead. The answer is that we emit the right
CONTENT at the wrong GRANULARITY:

    gold  "Johnson Joseph's cognitive curiosity drives him to explore new
           opportunities and partnerships."
    ours  "motivation: cognitive curiosity for testing boundaries and seeking
           new opportunities (asserted)"

    gold  "Johnson Joseph is committed to fostering innovative solutions and
           shared goals in his consultancy practice."
    ours  "focus: innovative solutions and shared goals (provisional)"

Our emissions are short `slot: value (tier)` records of roughly constant
granularity. Early gold is atomic ("User's name is Martin Mark") and one
record covers it. Late gold is discursive and bundles two or three
propositions into a sentence, so it takes SEVERAL of our records -- and the
judge is asked about one memory point at a time.

Two measurements, both on the judged records so the population is identical:

  one-emission coverage   best single emission covering >=th of the gold
                          point's content tokens. This is roughly what the
                          judge can credit.
  union coverage          the same against the UNION of that session's
                          emissions. This is what we HOLD.

The gap between them is the fragmentation signal.

THE NULL, and it is not optional here (entries 151-153). A union over ~17
emissions is a wide net and would catch gold by vocabulary alone. The control
is the SAME USER's emissions from a DIFFERENT session: same persona, same
slot inventory, same volume, same writing style -- only the session pairing
is destroyed. It runs at 2-4%.

WHAT THIS DOES AND DOES NOT LICENSE. Union coverage is an UPPER BOUND on what
better rendering could recover, not a prediction. "The tokens are present
across three records" is not "the judge would credit one assembled
proposition." Only the judge settles that. Swept over thresholds per entry
202: the absolute levels move a lot, the single-vs-union gap does not.

No model calls.
"""
import argparse
import collections
import glob
import json
import os
import random
import re

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")
BUCKET = 9
STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())
TIER = re.compile(r"\s*\((?:asserted|provisional|inferred|retracted)\)\s*$")
SLOT = re.compile(r"^[a-z_]+:\s*")
OWNER = re.compile(r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)'s\b")


def dechunk(uuid, ssession_id):
    """Chunked runs (s5_chunk.py) split one user into pseudo-users
    "<uuid>#c3" whose sessions restart at 0. Absolute position is what every
    position-based cut here depends on, so restore it: session 4 of chunk 3 is
    session 31. Unchunked runs pass through untouched."""
    if "#c" in uuid:
        base, c = uuid.rsplit("#c", 1)
        return base, int(c) * BUCKET + int(ssession_id)
    return uuid, int(ssession_id)


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def unrender(m):
    """Strip our artifact's machine syntax so the comparison is about CONTENT.

    Without this the slot name and the tier suffix are scored as content
    tokens and the whole measurement is about our formatting -- instrument
    failure #3, which cost us a 0.6% duplicate rate that was really 10.1%."""
    return SLOT.sub("", TIER.sub("", str(m)))


def load(version):
    recs = []
    for f in glob.glob(f"{RESULTS}/rgp2-{version}/tmp2/*.json"):
        for r in json.load(open(f, encoding="utf-8")).get(
                "memory_integrity_records", []):
            if r.get("memory_source") != "interference":
                recs.append(r)

    # The persona's own name is in every gold string and in none of ours, so
    # leaving it in costs ~20pt of coverage on a 10-token gold and measures
    # our lack of a subject rather than our lack of the fact. Recovered from
    # gold's own "<Name>'s ..." phrasing rather than persona_info, whose key
    # name varies.
    lead = collections.defaultdict(collections.Counter)
    for r in recs:
        m = OWNER.match(str(r.get("memory_content", "")))
        if m:
            lead[dechunk(r["uuid"], 0)[0]][m.group(1)] += 1
    names = {u: toks(c.most_common(1)[0][0]) for u, c in lead.items()}

    emit = {}
    for line in open(f"{RESULTS}/rgp2-{version}/rgp2_eval_results.jsonl",
                     encoding="utf-8"):
        u = json.loads(line)
        for si, s in enumerate(u["sessions"]):
            emit[dechunk(u["uuid"], si)] = [
                toks(unrender(m)) for m in s.get("extracted_memories", [])]
    return recs, names, emit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="round5")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed)

    recs, names, emit = load(a.version)
    union = {k: (set().union(*v) if v else set()) for k, v in emit.items()}
    byuser = collections.defaultdict(list)
    for uu, si in union:
        byuser[uu].append(si)

    def cells(th):
        out = collections.defaultdict(lambda: [0, 0, 0, 0])
        for r in recs:
            uu, si = dechunk(r["uuid"], r.get("ssession_id", 0))
            g = toks(r.get("memory_content")) - names.get(uu, set())
            if not g:
                continue
            others = [s for s in byuser[uu] if s != si]
            nl = union.get((uu, random.choice(others)), set()) if others else set()
            key = ("LATE" if si >= BUCKET else "EARLY",
                   "credited" if r.get("memory_integrity_score") == 2 else "missed")
            c = out[key]
            c[0] += max((len(g & e) / len(g) for e in emit.get((uu, si), [])),
                        default=0.0) >= th
            c[1] += len(g & union.get((uu, si), set())) / len(g) >= th
            c[2] += len(g & nl) / len(g) >= th
            c[3] += 1
        return out

    print(f"rgp2-{a.version}: gold content found in its OWN session's emissions")
    print("(persona name removed from gold; 'slot:' and '(tier)' stripped "
          "from ours)\n")
    for th in (0.4, 0.5, 0.6, 0.7):
        out = cells(th)
        print(f"  threshold {th}")
        print(f"    {'':<18}{'one emission':>14}{'union':>9}{'null':>8}"
              f"{'lift':>9}{'n':>7}")
        for key in (("EARLY", "credited"), ("EARLY", "missed"),
                    ("LATE", "credited"), ("LATE", "missed")):
            s, u, nl, n = out[key]
            print(f"    {key[0]+' '+key[1]:<18}{s/n:>13.1%}{u/n:>9.1%}"
                  f"{nl/n:>8.1%}{(u-nl)/n*100:>+8.1f}pt{n:>7}")
        print()

    print("  READ THIS AS: the 'missed' rows are gold the judge did not credit.")
    print("  Their union coverage is the UPPER BOUND on what re-rendering could")
    print("  recover -- not a prediction. The single-vs-union gap is the claim,")
    print("  and it survives every threshold; the absolute levels do not (e202).")


if __name__ == "__main__":
    main()
