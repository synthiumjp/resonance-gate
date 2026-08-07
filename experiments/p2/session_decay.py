"""Where the official integrity metric's mass actually sits: session position.

Every decomposition we have run so far cut the benchmark by QUESTION category
(entry 179) or by memory type. Neither shows what this does: the official
memory-integrity score is dominated by the first nine sessions of each user,
and our recall outside them is about a quarter of what it is inside.

Runs entirely on a judged run that already exists -- no model calls, no new
spend. Default is round 5 (users 0-9, the last full official pass).

Three cuts, in the order that makes the result interpretable:

  by_position    recall per 9-session bucket. The headline.
  by_type        recall for Persona / Event / Relationship, early vs late.
                 This is the cut that decides WHY: if the drop were just the
                 gold mix changing (early sessions are 78% persona, later ones
                 ~58%), per-type recall would hold steady and only the average
                 would move. It does not hold steady.
  known_missed   of the later-session misses, how many are nonetheless present
                 somewhere in the user's full store -- i.e. extracted, but not
                 in the session the judge credited. Reported as a THRESHOLD
                 SWEEP, never a single number: entry 202 established that the
                 token-overlap proxy cannot carry an absolute figure, and this
                 particular band is wide enough that it settles nothing.
"""
import argparse
import collections
import glob
import json
import os
import re

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")
DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
BUCKET = 9

STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def load_records(version):
    for f in glob.glob(f"{RESULTS}/rgp2-{version}/tmp2/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        for r in d.get("memory_integrity_records", []):
            if r.get("memory_source") != "interference":
                yield r


def by_position(version):
    b = collections.defaultdict(lambda: [0, 0])
    for r in load_records(version):
        k = int(r.get("ssession_id", 0)) // BUCKET
        b[k][1] += 1
        b[k][0] += (r.get("memory_integrity_score") == 2)
    print(f"integrity recall by {BUCKET}-session bucket ({version})")
    tot = [0, 0]
    for k in sorted(b):
        h, n = b[k]
        tot[0] += h
        tot[1] += n
        bar = "#" * round(h / n * 40)
        print(f"  s{k*BUCKET:>2}-{k*BUCKET+BUCKET-1:<3} {h:5d}/{n:<5d} {h/n:6.1%} {bar}")
    print(f"  POOLED     {tot[0]:5d}/{tot[1]:<5d} {tot[0]/tot[1]:6.1%}")
    first = b[0]
    print(f"\n  the first bucket holds {first[1]/tot[1]:.1%} of all gold points "
          f"and scores {first[0]/first[1]:.1%};\n  everything after scores "
          f"{(tot[0]-first[0])/(tot[1]-first[1]):.1%}.")


def by_type(version):
    b = collections.defaultdict(lambda: [0, 0])
    for r in load_records(version):
        late = int(r.get("ssession_id", 0)) >= BUCKET
        k = (late, r.get("memory_type"))
        b[k][1] += 1
        b[k][0] += (r.get("memory_integrity_score") == 2)
    print(f"\nrecall by memory type, early (s0-{BUCKET-1}) vs late (s{BUCKET}+)")
    print(f"  {'type':<22}{'early':>16}{'late':>16}    change")
    for mt in ("Persona Memory", "Event Memory", "Relationship Memory"):
        e, l = b[(False, mt)], b[(True, mt)]
        if not e[1] or not l[1]:
            continue
        er, lr = e[0] / e[1], l[0] / l[1]
        print(f"  {mt:<22}{e[0]:5d}/{e[1]:<5d}{er:5.1%}{l[0]:6d}/{l[1]:<5d}{lr:5.1%}"
              f"  {(lr-er)*100:+7.1f}pt")
    print("\n  If the drop were the gold MIX changing (early sessions are 78%"
          "\n  persona, later ~58%), each row would hold flat. Persona does not.")


def known_missed(version):
    store = {}
    path = f"{RESULTS}/rgp2-{version}/rgp2_eval_results.jsonl"
    for line in open(path, encoding="utf-8"):
        u = json.loads(line)
        store[u["uuid"]] = [toks(m) for s in u["sessions"]
                            for m in s.get("extracted_memories", [])]
    misses = collections.defaultdict(list)
    for r in load_records(version):
        if r.get("memory_integrity_score") == 2:
            continue
        if int(r.get("ssession_id", 0)) < BUCKET:
            continue
        misses[r["uuid"]].append(toks(r["memory_content"]))
    tot = sum(len(v) for v in misses.values())
    print(f"\nof the {tot} LATE misses, how many are in the user's full store?")
    print("  (swept, not a single cut -- entry 202: this proxy cannot carry an"
          "\n   absolute, and the band below is too wide to settle anything)")
    for th in (0.4, 0.5, 0.6, 0.7):
        hit = sum(1 for uu, golds in misses.items()
                  for g in golds
                  if g and any(len(g & e) / len(g) >= th
                               for e in store.get(uu, [])))
        print(f"    thresh {th}: {hit:5d}/{tot} = {hit/tot:5.1%}")
    print("  Read as: SOMEWHERE BETWEEN ~1% and ~25% are extracted-but-"
          "miscredited.\n  The rest we never extracted. Only the judge can "
          "narrow this.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="round5")
    a = ap.parse_args()
    by_position(a.version)
    by_type(a.version)
    known_missed(a.version)
