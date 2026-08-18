"""Is the entry-204 collapse OUR extractor failing, or gold moving out of reach?

Entry 204 established that integrity recall is a first-nine-sessions metric:
45.4% persona recall in sessions 0-8, 10.1% after. It could not say WHY. Two
stories fit that curve and they call for opposite work:

  (A) the extractor degrades -- late sessions are longer / more cluttered /
      more update-shaped, and we stop reading them properly. Fixable by us.
  (B) late gold is not stated in its own session -- it is carried over,
      inferred across sessions, or summarised. Then late recall is capped by
      the benchmark's construction, and the whole late regime is a ceiling
      problem no extractor change touches.

Entry 189's ceiling (best single turn covering >=th of a gold point's content
tokens) separates them, but it was only ever computed POOLED. Computed per
session bucket it gives the missing axis:

    ceiling        share of gold reachable from a single turn of its session
    recall         share the judge actually credited us with
    recall|reach   recall AMONG the reachable ones -- our efficiency inside
                   whatever room the benchmark left us

Story (A) predicts a flat ceiling and a collapsing recall|reach.
Story (B) predicts the ceiling itself collapsing, with recall|reach flat.

METHOD NOTE, and it is the reason this is worth running at all: the ceiling
is computed ON THE JUDGED RECORDS THEMSELVES, joined back to the source
dialogue by (uuid, ssession_id, memory_content). Ceiling and recall are
therefore measured over an identical population, and every gold point is a
matched pair (reachable?, credited?). Computing the ceiling over the raw
dataset instead would have compared two different denominators -- the exact
shape of instrument failure #6.

PROXY CAVEAT (entry 202): reachability is token overlap at a threshold, and
that threshold cannot carry an absolute figure. So the reported claim is the
EARLY-vs-LATE CONTRAST at a fixed threshold, which a threshold shift moves in
both buckets together, and every table is swept over th to show the contrast
is not an artifact of the cut. No absolute ceiling number should be quoted
from this file.

No model calls.
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


def load_users():
    """uuid -> [(session_index, [(role, token_set)])]"""
    out = {}
    for line in open(DATA, encoding="utf-8"):
        u = json.loads(line)
        out[u["uuid"]] = [
            [(t.get("role"), toks(t.get("content", "")))
             for t in (s.get("dialogue") or [])]
            for s in u["sessions"]]
    return out


def load_records(version):
    for f in glob.glob(f"{RESULTS}/rgp2-{version}/tmp2/*.json"):
        d = json.load(open(f, encoding="utf-8"))
        for r in d.get("memory_integrity_records", []):
            if r.get("memory_source") != "interference":
                yield r


def best_cover(gold, turns, role=None):
    """Highest single-turn coverage of `gold`, optionally restricted to a role."""
    if not gold:
        return 0.0
    best = 0.0
    for r, tk in turns:
        if role and r != role:
            continue
        c = len(gold & tk) / len(gold)
        if c > best:
            best = c
    return best


def build(version):
    """One row per judged gold point: bucket, type, hit, best-cover scores."""
    users = load_users()
    rows = []
    missing = 0
    for r in load_records(version):
        sess = users.get(r["uuid"])
        si = int(r.get("ssession_id", 0))
        if sess is None or si >= len(sess):
            missing += 1
            continue
        g = toks(r.get("memory_content"))
        turns = sess[si]
        rows.append({
            "bucket": si // BUCKET,
            "late": si >= BUCKET,
            "type": r.get("memory_type"),
            "hit": r.get("memory_integrity_score") == 2,
            "any": best_cover(g, turns),
            "user": best_cover(g, turns, "user"),
        })
    if missing:
        print(f"  (note: {missing} records had no matching source session)")
    return rows


def table(rows, th, key="any"):
    b = collections.defaultdict(lambda: [0, 0, 0])   # n, reachable, hit&reach
    hits = collections.Counter()
    for r in rows:
        k = r["bucket"]
        b[k][0] += 1
        hits[k] += r["hit"]
        if r[key] >= th:
            b[k][1] += 1
            b[k][2] += r["hit"]
    print(f"\n  threshold {th}   ({key} turns)")
    print(f"    {'bucket':<10}{'n':>6}{'ceiling':>10}{'recall':>9}"
          f"{'recall|reach':>14}")
    for k in sorted(b):
        n, reach, hr = b[k]
        print(f"    s{k*BUCKET:>2}-{k*BUCKET+BUCKET-1:<6}{n:>6}"
              f"{reach/n:>9.1%}{hits[k]/n:>9.1%}"
              f"{(hr/reach if reach else 0):>13.1%}")
    early = [r for r in rows if not r["late"]]
    late = [r for r in rows if r["late"]]
    return contrast(early, late, th, key)


def contrast(early, late, th, key):
    def cut(rs):
        n = len(rs)
        reach = [r for r in rs if r[key] >= th]
        hit_r = sum(r["hit"] for r in reach)
        return (n, len(reach) / n if n else 0,
                sum(r["hit"] for r in rs) / n if n else 0,
                hit_r / len(reach) if reach else 0)
    e, l = cut(early), cut(late)
    print(f"    {'EARLY s0-8':<10}{e[0]:>6}{e[1]:>9.1%}{e[2]:>9.1%}{e[3]:>13.1%}")
    print(f"    {'LATE  s9+':<10}{l[0]:>6}{l[1]:>9.1%}{l[2]:>9.1%}{l[3]:>13.1%}")
    print(f"    {'change':<10}{'':>6}{(l[1]-e[1])*100:>+8.1f}pt"
          f"{(l[2]-e[2])*100:>+8.1f}pt{(l[3]-e[3])*100:>+12.1f}pt")
    return {"th": th, "key": key, "ceiling_delta": (l[1] - e[1]) * 100,
            "recall_delta": (l[2] - e[2]) * 100,
            "eff_delta": (l[3] - e[3]) * 100}


def by_type(rows, th, key="any"):
    print(f"\n  by memory type at threshold {th} ({key} turns)")
    print(f"    {'type':<22}{'ceiling e/l':>18}{'recall|reach e/l':>22}")
    for mt in ("Persona Memory", "Event Memory", "Relationship Memory"):
        sub = [r for r in rows if r["type"] == mt]
        if not sub:
            continue
        out = []
        for late in (False, True):
            rs = [r for r in sub if r["late"] == late]
            if not rs:
                out.append((0, 0))
                continue
            reach = [r for r in rs if r[key] >= th]
            out.append((len(reach) / len(rs),
                        sum(r["hit"] for r in reach) / len(reach) if reach else 0))
        print(f"    {mt:<22}{out[0][0]:>8.1%}{out[1][0]:>9.1%}"
              f"{out[0][1]:>12.1%}{out[1][1]:>9.1%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="round5")
    ap.add_argument("--key", default="any", choices=("any", "user"))
    a = ap.parse_args()

    rows = build(a.version)
    print(f"{len(rows)} judged gold points from rgp2-{a.version}, "
          f"joined to their source session")
    print("\nceiling = share reachable from ONE turn of the gold point's own "
          "session\nrecall  = share the judge credited\n"
          "recall|reach = recall among the reachable -- our efficiency inside "
          "the room we had")

    deltas = [table(rows, th, a.key) for th in (0.4, 0.5, 0.6)]
    by_type(rows, 0.5, a.key)

    print("\n  VERDICT (read the sign, not the magnitude -- entry 202)")
    for d in deltas:
        print(f"    th {d['th']}: ceiling {d['ceiling_delta']:+.1f}pt, "
              f"recall {d['recall_delta']:+.1f}pt, "
              f"efficiency {d['eff_delta']:+.1f}pt")
    print("\n    ceiling falls much more than efficiency -> the benchmark moved "
          "gold\n    out of reach (story B). efficiency falls too -> our "
          "extractor also\n    degrades (story A). Both can be true; the "
          "question is the split.")


if __name__ == "__main__":
    main()
