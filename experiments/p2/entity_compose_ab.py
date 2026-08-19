"""Does ENTITY RESOLUTION unblock relationship composition? (e218's open question)

e218 measured relationship composition as NEGATIVE: 33.3% coverage of the 51
Relationship gold points against a 37.3% atomic baseline. The diagnosis was
that one person arrives as several subject keys ("karen" and "brownkaren"), so
the composer built 42 weak records instead of ~20 strong ones.

That diagnosis makes a falsifiable prediction: resolve the entities and the
number should move WITHOUT TOUCHING THE COMPOSER. This tests exactly that, and
nothing else -- same composer, same gold, same thresholds, same null design.

Four arms, so the two fixes can be told apart:
    atoms                 the baseline composition has to beat
    compose               e218's result, reproduced
    compose+person        non-person subjects dropped (person_subject)
    compose+person+entity ... and subjects resolved to one identity per person

If the last arm does not beat `atoms`, entity resolution is not the blocker
either, and the composition line of work is closed rather than merely deferred.

No model calls; cache replay only.
"""
import collections
import json
import os
import random
import re
import sys

EV = os.path.expanduser("~/rg_private/halumem/official/HaluMem/eval")
DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
CACHE = os.path.expanduser("~/rg_private/halumem/dev/cache_u10_v5_14b.jsonl")
for p in (EV, "/home/jp/rg/experiments/p2"):
    if p not in sys.path:
        sys.path.insert(0, p)

STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def main():
    import halumem_run as H
    import propositions as PR
    import compose_relationship as CR
    import person_subject as PS
    import entity_resolve as ER

    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][10]
    mem, _ = H.ingest_user(user, cache_path=CACHE)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    owner = PR.owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes])

    facts = [{"attr": n["attr"], "value": n["value"]} for n in nodes]
    subs = sorted({PR.split_subject(f["attr"])[0] for f in facts
                   if PR.split_subject(f["attr"])[0]})

    def drop_non_person(fs):
        keep = {s for s in subs if PS.is_person_subject(s)}
        return [f for f in fs
                if not PR.split_subject(f["attr"])[0]
                or PR.split_subject(f["attr"])[0] in keep]

    def resolve(fs):
        present = sorted({PR.split_subject(f["attr"])[0] for f in fs
                          if PR.split_subject(f["attr"])[0]})
        m = ER.resolve_subjects(present, owner=owner)
        out = []
        for f in fs:
            s, a = PR.split_subject(f["attr"])
            g = dict(f)
            if s and m.get(s):
                g["attr"] = f"{str(m[s]).lower()}:{a}"
            out.append(g)
        return out

    text = "\n".join(str(t.get("content", ""))
                     for ss in user["sessions"] for t in (ss.get("dialogue") or []))

    arms = {
        "compose": facts,
        "compose+person": drop_non_person(facts),
        "compose+person+entity": resolve(drop_non_person(facts)),
    }
    props = {k: (CR.compose(v, owner=owner, session_text=text) or [])
             for k, v in arms.items()}
    atoms = [p for p in (PR.render(f, owner=owner) for f in facts) if p]

    gold = [mp["memory_content"] for s in user["sessions"]
            for mp in s.get("memory_points", [])
            if mp.get("memory_type") == "Relationship Memory"]
    own = toks(owner or "")

    def cov(records, th):
        recs = [toks(r) for r in records]
        hit = 0
        for g in gold:
            gt = toks(g) - own
            if gt and any(len(gt & r) / len(gt) >= th for r in recs):
                hit += 1
        return hit

    rng = random.Random(0)

    def null_props(k):
        """A REAL null: rebuild the same NUMBER of propositions from the same
        facts, grouped by a random subject assignment. Shuffling the output
        LIST was the first attempt and is a no-op -- "does any record cover
        this gold point" is order-invariant, so the null scored identically to
        the real arm in every cell and looked like a perfect control.
        The null has to change WHICH FACTS SHARE A RECORD, not their order."""
        fs = arms[k]
        subj = [PR.split_subject(f["attr"])[0] for f in fs]
        real = [s for s in subj if s]
        if not real:
            return []
        shuffled = real[:]
        rng.shuffle(shuffled)
        it = iter(shuffled)
        out = []
        for f in fs:
            s, a = PR.split_subject(f["attr"])
            g = dict(f)
            if s:
                g["attr"] = f"{next(it)}:{a}"
            out.append(g)
        return CR.compose(g_ := out, owner=owner, session_text=text) or []

    print(f"{len(gold)} Relationship gold points | atoms {len(atoms)}")
    for k in arms:
        print(f"  {k:<24} {len(props[k])} composed propositions")
    print()
    hdr = f"  {'arm':<24}" + "".join(f"{'thr '+str(t):>12}" for t in (0.4, 0.5, 0.6))
    print(hdr)
    print(f"  {'atoms only (baseline)':<26}" +
          "".join(f"{cov(atoms,t)/len(gold):>11.1%}" for t in (0.4, 0.5, 0.6)))
    for k in arms:
        nl = null_props(k)
        print(f"  atoms + {k:<18}" +
              "".join(f"{cov(atoms+props[k],t)/len(gold):>11.1%}"
                      for t in (0.4, 0.5, 0.6)))
        print(f"  {'    (null: same count,':<26}" +
              "".join(f"{cov(atoms+nl,t)/len(gold):>11.1%}"
                      for t in (0.4, 0.5, 0.6)) + "   random subjects)")
    print("\n  Compounds are emitted ALONGSIDE atoms, so `atoms + X` is the only")
    print("  meaningful arm -- comparing 14 composed records against 1522 atoms")
    print("  was the wrong question and made composition look far worse than it is.")


if __name__ == "__main__":
    main()
