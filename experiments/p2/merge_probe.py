"""How much single-record coverage would CONSOLIDATION buy? (offline S6 probe)

Entry 206: the judge credits records, not stores. Late misses have 50% union
coverage of their own session's emissions but only 15.1% single-record
coverage, and the single-record column is what separates credited from
missed. So the lever is to emit fewer, larger records that each carry a whole
gold-shaped proposition.

This prices that offline, before spending a judge call.

WHAT IS DELIBERATELY NOT MEASURED HERE: adding the persona's name. Gold
contains the name and our records do not, so "prepend the subject" raises any
token-overlap score mechanically without the judge having changed its mind
about anything. Measuring it would be rigging the instrument, which is what
§4 of the ledger is a list of. Gold is name-stripped throughout; the name is
a rendering question the judge has to answer.

Strategies, each a deterministic post-processing pass over one session's
emissions:

  none        what we ship today, one record per slot fact
  by_slot     merge records sharing a slot ("plan: a" + "plan: b")
  by_overlap  merge records whose values share >=2 content tokens
  all         merge the whole session into one record

`all` is NOT a proposal. It is the degenerate upper bound, included so the
other strategies can be read against something -- any strategy approaching it
is buying coverage by destroying the unit the accuracy metric scores.

THE COST COLUMN IS THE POINT. Coverage here is a recall proxy; every merge
also shrinks the record count, and target_accuracy judges each emitted record
on its own. A strategy that doubles coverage while halving record count has
not obviously won -- it has moved mass from one official metric to the other,
and only the judge can say which way that nets out. Reported side by side so
the trade is visible rather than implied.
"""
import argparse
import collections
import glob
import json
import os
import re

RESULTS = os.path.expanduser(
    "~/rg_private/halumem/official/HaluMem/eval/results")
BUCKET = 9
STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())
TIER = re.compile(r"\s*\((?:asserted|provisional|inferred|retracted)\)\s*$")
SLOT = re.compile(r"^([a-z_]+):\s*")
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


def split_record(m):
    """-> (slot, value_tokens)"""
    s = TIER.sub("", str(m))
    mo = SLOT.match(s)
    slot = mo.group(1) if mo else ""
    return slot, toks(SLOT.sub("", s))


def merge(records, how, rng=None):
    """records: [(slot, tokens)] -> [tokens], one entry per emitted record."""
    if how == "none":
        return [t for _, t in records]
    if how == "all":
        return [set().union(*[t for _, t in records])] if records else []
    if how == "by_slot":
        g = collections.defaultdict(set)
        for slot, t in records:
            g[slot] |= t
        return list(g.values())
    if how == "by_overlap":
        out = []
        for _, t in records:
            for i, o in enumerate(out):
                if len(o & t) >= 2:
                    out[i] = o | t
                    break
            else:
                out.append(set(t))
        return out
    if how.startswith("random:"):
        # THE NULL. A merged record is a bigger token set, so it covers more
        # of ANY gold by construction -- exactly the containment-without-a-
        # null mistake entries 151-153 retracted three findings for. This
        # merges the same records into the same NUMBER of groups, chosen at
        # random. A real strategy has to beat its own record count.
        k = int(how.split(":")[1])
        if not records or k <= 0:
            return []
        idx = list(range(len(records)))
        rng.shuffle(idx)
        groups = collections.defaultdict(set)
        for j, i in enumerate(idx):
            groups[j % k] |= records[i][1]
        return list(groups.values())
    raise ValueError(how)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="round5")
    ap.add_argument("--th", type=float, default=0.5)
    a = ap.parse_args()

    recs = []
    lead = collections.defaultdict(collections.Counter)
    for f in glob.glob(f"{RESULTS}/rgp2-{a.version}/tmp2/*.json"):
        for r in json.load(open(f, encoding="utf-8")).get(
                "memory_integrity_records", []):
            if r.get("memory_source") == "interference":
                continue
            recs.append(r)
            mo = OWNER.match(str(r.get("memory_content", "")))
            if mo:
                lead[dechunk(r["uuid"], 0)[0]][mo.group(1)] += 1
    names = {u: toks(c.most_common(1)[0][0]) for u, c in lead.items()}

    # On a proposition-rendered artifact EVERY record contains the owner's
    # name, so an overlap>=2 test merges almost everything and matches its own
    # random null -- measuring "bigger records", not grouping. Strip the owner
    # tokens from the grouping key, exactly as gold is name-stripped.
    owner_toks = set()
    for c in lead.values():
        owner_toks |= toks(c.most_common(1)[0][0])

    raw = {}
    for line in open(f"{RESULTS}/rgp2-{a.version}/rgp2_eval_results.jsonl",
                     encoding="utf-8"):
        u = json.loads(line)
        for si, s in enumerate(u["sessions"]):
            rows = []
            for m in s.get("extracted_memories", []):
                slot, tk = split_record(m)
                rows.append((slot, tk - owner_toks))
            raw[dechunk(u["uuid"], si)] = rows

    # FORMAT GUARD. by_slot keys on the "slot:" prefix, which only the
    # pre-590529e artifact carries -- proposition rendering (entry 163) emits
    # "<Owner>'s <slot> is <value>" with no prefix. Without this guard every
    # record parses as slot "" and by_slot silently degenerates to `all`,
    # printing a 3x "win" that is one record per session.
    have_slot = sum(1 for v in raw.values() for slot, _ in v if slot)
    total_rec = sum(len(v) for v in raw.values())
    frac = have_slot / max(1, total_rec)
    print(f"rgp2-{a.version}, threshold {a.th}, gold name-stripped")
    print(f"  records carrying a 'slot:' prefix: {frac:.1%}")
    prose = frac < 0.5
    if prose:
        print("  proposition-rendered artifact: by_slot is unavailable (the slot\n"
              "  is not recoverable from the string), so only by_overlap and its\n"
              "  matched null are run. The grouping key still exists upstream as\n"
              "  nd['attr'], so the strategy is implementable -- just not\n"
              "  measurable from a rendered artifact.")
    print()
    print()
    print(f"  {'strategy':<24}{'records':>9}{'EARLY cov':>12}{'LATE cov':>11}"
          f"{'LATE missed':>13}")
    import random
    rng = random.Random(0)
    plans = (["none", "by_overlap", "random-null(by_overlap)", "all"] if prose
             else ["none", "by_slot", "random-null(by_slot)",
                   "by_overlap", "random-null(by_overlap)", "all"])
    sizes = {}
    for how in plans:
        if how.startswith("random-null"):
            ref = how[len("random-null("):-1]
            merged = {k: merge(v, f"random:{sizes[ref][k]}", rng)
                      for k, v in raw.items()}
        else:
            merged = {k: merge(v, how) for k, v in raw.items()}
            sizes[how] = {k: len(v) for k, v in merged.items()}
        nrec = sum(len(v) for v in merged.values())
        cov = collections.defaultdict(lambda: [0, 0])
        for r in recs:
            uu, si = dechunk(r["uuid"], r.get("ssession_id", 0))
            g = toks(r.get("memory_content")) - names.get(uu, set())
            if not g:
                continue
            best = max((len(g & e) / len(g) for e in merged.get((uu, si), [])),
                       default=0.0)
            late = si >= BUCKET
            cov[late][0] += best >= a.th
            cov[late][1] += 1
            if late and r.get("memory_integrity_score") != 2:
                cov["lm"][0] += best >= a.th
                cov["lm"][1] += 1
        e, l, lm = cov[False], cov[True], cov["lm"]
        tag = ("  <- upper bound, not a proposal" if how == "all"
               else "  <- same record count, random grouping"
               if how.startswith("random-null") else "")
        print(f"  {how:<24}{nrec:>9}{e[0]/e[1]:>11.1%}{l[0]/l[1]:>11.1%}"
              f"{lm[0]/lm[1]:>13.1%}{tag}")

    print("\n  'records' is the denominator of target_accuracy. Coverage bought")
    print("  by shrinking it is not free -- it moves mass between the two")
    print("  official metrics, and only the judge prices that.")


if __name__ == "__main__":
    main()
