"""E7 partition study: seeded relational corpus in a HIGH-DEGREE regime.

This module builds FACTS and CHAINS only. It does not write anything into a
substrate — stores.py takes the identical fact list and materialises it under
four partitioning conditions, so every condition holds a byte-identical set
of facts and the ONLY thing that varies is how they are split.

THE REGIME. The corpus is built so that chain-relevant facts are the
high-contention ones:

  HUB entities  (n_hub_org orgs, n_hub_person persons) carry high out-degree
                (many facts as SUBJECT, under distinct relations) and high
                in-degree (many facts as OBJECT). Chains route THROUGH hubs:
                the 2nd-hop fact is (hub_org, r2, hub_person) and the 3rd-hop
                fact is (hub_person, r3, city).
  CHAIN relations are reused heavily by background facts, so their degree is
                far above the cold relations.
  COLD entities appear as subject in exactly ONE fact, under a cold relation.
                These are the "typical" facts of the Kumar probe.

Chain starts are deliberately COLD, so hop 1 is a typical-contention fact and
hops 2-3 are high-contention: the contrast the Kumar probe measures lives
inside the same chain, in the same store, at the same k and N.

KEYS ARE UNIQUE. No (subject, relation) key is ever written twice. This is
deliberate and load-bearing: two facts under one key is UNDERDETERMINATION
(the unbind returns a genuine superposition of two objects and no cleanup can
choose), not interference. Mixing the two would make any COND-0 failure
uninterpretable, and it would stop COND-RE from ever reaching K=1. Degree
here therefore means "shares a component with many facts", never "answers the
same question twice".

Reserved-but-unwritten keys (the absent links of the BROKEN and DISTRACTOR
arms) are held in a reserve set so no background fact can accidentally supply
a link that is meant to be missing.

Seeds: cfg.seed + 1000*world_index. DEV/EVAL discipline follows entry 19 —
background load is calibrated on the DEV seed until COND-0 sits in the
target regime, then frozen and scored on the held-out EVAL seed.
"""

import os
import sys
from dataclasses import dataclass, field

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from entities import _pools

# Chain relations, one bank per hop position, typed. None are members of
# gate/l2_ambiguity.RELATION_SYNONYMS ({works at, is employed by},
# {lives in, resides in}), so the semantic-collision detector never treats two
# distinct chain relations as the same attribute.
#
# Only TWO surfaces per hop position (six chain relations total). This is a
# calibration decision, not cosmetics: relation degree is facts-per-relation,
# so at a fixed store size a wide chain vocabulary cannot be high-degree. The
# DEV run with four surfaces per hop gave chain-relation degree 63 against
# cold 52 -- no contrast at all, and the Kumar axis was untestable.
HOP_RELS = {
    1: ["works at", "consults for"],        # person -> org
    2: ["was founded by", "is led by"],     # org -> person
    3: ["lives in", "was born in"],         # person -> city
}
HOP_TYPES = {1: ("person", "org"), 2: ("org", "person"), 3: ("person", "city")}
CHAIN_RELS = [r for rs in HOP_RELS.values() for r in rs]

# THREE relation bands, kept disjoint so the two degree axes can be moved
# independently:
#   CHAIN_RELS  high degree -- chain links plus a dedicated background block.
#   FILLER_RELS carry hub OUT-degree. Separate from COLD_RELS because if hubs
#               spent their out-degree on the cold relations, cold-relation
#               degree would rise with hub degree and the relation axis would
#               collapse (exactly what happened on DEV).
#   COLD_RELS   used ONLY by typical facts, so they stay near degree 1.
FILLER_RELS = [
    ("mentors", "person", "person"), ("advises", "person", "person"),
    ("reports to", "person", "person"), ("manages", "person", "person"),
    ("is married to", "person", "person"), ("coaches", "person", "person"),
    ("recruited", "person", "person"), ("replaced", "person", "person"),
    ("commutes to", "person", "city"), ("holidays in", "person", "city"),
    ("owns property in", "person", "city"), ("votes in", "person", "city"),
    ("supplies", "org", "org"), ("licenses to", "org", "org"),
    ("partners with", "org", "org"), ("subcontracts to", "org", "org"),
    ("competes with", "org", "org"), ("acquired", "org", "org"),
    ("is headquartered in", "org", "city"), ("has an office in", "org", "city"),
    ("was incorporated in", "org", "city"), ("banks in", "org", "city"),
]
COLD_RELS = [
    ("is a sibling of", "person", "person"), ("carpools with", "person", "person"),
    ("tutors", "person", "person"), ("sublets from", "person", "person"),
    ("volunteers with", "person", "person"), ("sails with", "person", "person"),
    ("retired to", "person", "city"), ("summers in", "person", "city"),
    ("trained in", "person", "city"), ("was married in", "person", "city"),
    ("warehouses in", "org", "city"), ("ships from", "org", "city"),
    ("leases to", "org", "org"), ("insures", "org", "org"),
    ("arbitrates for", "org", "org"), ("certifies", "org", "org"),
]
FILLER_REL_NAMES = [r for r, _, _ in FILLER_RELS]
COLD_REL_NAMES = [r for r, _, _ in COLD_RELS]
ALL_RELS = CHAIN_RELS + FILLER_REL_NAMES + COLD_REL_NAMES

HOPS = (1, 2, 3)
ARMS = ("intact", "broken", "distractor")


@dataclass
class PartitionConfig:
    """Sized from the DEV calibration (notebook entry 24).

    k_total is the load knob and it is the one that matters. The first DEV
    attempt used k_total=2000 at N~970, i.e. 5.3x the capacity law
    k_max ~= D/(pi*ln N) ~= 379: COND-0 sat on the noise floor (high-degree
    0.075, typical 0.090, 90% of facts failing echo read-back), so BOTH fact
    classes were destroyed equally and no degree-specific effect could be
    detected either way. The probe is only informative at a load where
    typical-fact retrieval is well off the floor, which is what k_total=400
    buys. Kumar's mechanism, if it operates here, must show up as high-degree
    facts degrading FASTER than typical ones at the same k -- not as
    everything dying together.
    """
    seed: int = 20260721          # EVAL seed; DEV calibration used seed+7
    n_worlds: int = 17            # -> ~102 chains per (arm, hop-length)
    chains_per_cell: int = 6
    n_hub_org: int = 18           # >= chains-with-L>=2 / len(HOP_RELS[2]) so
    n_hub_person: int = 10        # every 2nd/3rd-hop key can stay unique
    n_person: int = 600           # entity registry composition
    n_org: int = 150
    n_city: int = 40
    k_total: int = 400            # nominal load; actual is the sum of the
                                  # blocks below and is reported per world
    n_hub_subject_facts: int = 6  # filler-relation facts per hub (out-degree)
    n_hub_object_facts: int = 2   # facts pointing AT each hub (in-degree)
    n_typical: int = 60           # degree-1 facts: the probe's control class
    n_chain_rel_background: int = 60  # degree-1 subjects on CHAIN relations:
                                  # raises relation degree without touching
                                  # entity degree, so the two axes stay separable
    n_load_filler: int = 0        # PURE LOAD: extra facts on FILLER relations
                                  # only. Subjects may repeat, so the degree
                                  # structure of BOTH probe classes is left
                                  # untouched -- this varies k alone, which is
                                  # what separates "load hurts" from "degree
                                  # hurts" in the sweep.
    n_probe: int = 200            # atomic probes per class, per world-set


@dataclass
class Fact:
    subj: str
    rel: str
    obj: str
    kind: str    # 'chain' | 'hub_subject' | 'hub_object' | 'typical'


@dataclass
class Chain:
    arm: str
    hops: int
    world: int
    start: str
    rels: list
    links: list          # length-L intended (subj, rel, obj)
    stored: list         # length-L bools
    missing_hop: object
    gold: object


@dataclass
class World:
    index: int
    seed: int
    facts: list = field(default_factory=list)
    chains: list = field(default_factory=list)
    kumar_probe: list = field(default_factory=list)   # (subj, rel, gold)
    typical_probe: list = field(default_factory=list)
    degree: dict = field(default_factory=dict)


def _degree_stats(facts):
    out_d, in_d, rel_d = {}, {}, {}
    for f in facts:
        out_d[f.subj] = out_d.get(f.subj, 0) + 1
        in_d[f.obj] = in_d.get(f.obj, 0) + 1
        rel_d[f.rel] = rel_d.get(f.rel, 0) + 1
    return {"out_degree": out_d, "in_degree": in_d, "rel_degree": rel_d}


def build_world(cfg: PartitionConfig, index: int) -> World:
    seed = cfg.seed + 1000 * index
    rng = np.random.default_rng(seed)
    persons, _qualified, orgs, cities = _pools()

    person = [persons[i] for i in rng.permutation(len(persons))[: cfg.n_person]]
    org = [orgs[i] for i in rng.permutation(len(orgs))[: cfg.n_org]]
    city = [cities[i] for i in rng.permutation(len(cities))[: cfg.n_city]]

    hub_org = org[: cfg.n_hub_org]
    hub_person = person[: cfg.n_hub_person]
    cold_person = person[cfg.n_hub_person:]
    cold_org = org[cfg.n_hub_org:]
    pool = {"person": person, "org": org, "city": city}

    w = World(index=index, seed=seed)
    used = set()      # (subj, rel) keys written
    reserved = set()  # (subj, rel) keys that must stay ABSENT

    # unique key slots for the high-contention hops
    hop2_slots = [(o, r) for o in hub_org for r in HOP_RELS[2]]
    hop3_slots = [(p, r) for p in hub_person for r in HOP_RELS[3]]
    rng.shuffle(hop2_slots)
    rng.shuffle(hop3_slots)
    s2, s3 = iter(hop2_slots), iter(hop3_slots)

    cold_cursor = 0

    def next_cold_person():
        nonlocal cold_cursor
        p = cold_person[cold_cursor]
        cold_cursor += 1
        return p

    chain_facts = []
    for arm in ARMS:
        for L in HOPS:
            for _ in range(cfg.chains_per_cell):
                start = next_cold_person()
                r1 = HOP_RELS[1][int(rng.integers(len(HOP_RELS[1])))]
                if L == 1:
                    mid1 = hub_org[int(rng.integers(len(hub_org)))]
                    links = [(start, r1, mid1)]
                else:
                    try:
                        mid1, r2 = next(s2)
                    except StopIteration:
                        continue  # slots exhausted; logged via cell counts
                    if L == 2:
                        mid2 = hub_person[int(rng.integers(len(hub_person)))]
                        links = [(start, r1, mid1), (mid1, r2, mid2)]
                    else:
                        try:
                            mid2, r3 = next(s3)
                        except StopIteration:
                            continue
                        dest = city[int(rng.integers(len(city)))]
                        links = [(start, r1, mid1), (mid1, r2, mid2),
                                 (mid2, r3, dest)]

                if arm == "intact":
                    missing = None
                elif arm == "broken":
                    # a MIDDLE link (hops 0..L-2). At L=1 none exists, so the
                    # single link is dropped -- identical to DISTRACTOR at L=1,
                    # recorded honestly rather than hidden.
                    missing = 0 if L == 1 else int(rng.integers(L - 1))
                else:
                    missing = L - 1

                stored = [i != missing for i in range(L)]
                for (s, r, o), keep in zip(links, stored):
                    (used if keep else reserved).add((s, r))
                    if keep:
                        chain_facts.append(Fact(s, r, o, "chain"))

                w.chains.append(Chain(
                    arm=arm, hops=L, world=index, start=start,
                    rels=[r for _, r, _ in links], links=links, stored=stored,
                    missing_hop=missing,
                    gold=links[L - 1][2] if arm == "intact" else None))

    facts = list(chain_facts)

    def try_add(s, r, o, kind):
        if s == o or (s, r) in used or (s, r) in reserved:
            return False
        used.add((s, r))
        facts.append(Fact(s, r, o, kind))
        return True

    # ---- hub OUT-degree: FILLER-relation facts anchored on each hub. Filler
    # relations are disjoint from the cold band, so raising hub degree does
    # not drag cold-relation degree up with it.
    hubs = [(h, "org") for h in hub_org] + [(h, "person") for h in hub_person]
    for hub, htype in hubs:
        cands = [(r, ot) for r, st, ot in FILLER_RELS if st == htype]
        rng.shuffle(cands)
        for r, ot in cands[: cfg.n_hub_subject_facts]:
            try_add(hub, r, pool[ot][int(rng.integers(len(pool[ot])))],
                    "hub_subject")

    # ---- hub IN-degree: facts pointing AT each hub, on CHAIN relations
    for hub, htype in hubs:
        hop = 1 if htype == "org" else 2
        src_pool = cold_person if htype == "org" else cold_org
        for _ in range(cfg.n_hub_object_facts):
            s = src_pool[int(rng.integers(len(src_pool)))]
            r = HOP_RELS[hop][int(rng.integers(len(HOP_RELS[hop])))]
            try_add(s, r, hub, "hub_object")

    # ---- CHAIN-RELATION background: degree-1 subjects on chain relations.
    # This is the lever that separates the two degree axes -- it raises
    # relation degree while leaving entity degree at 1.
    added = 0
    while added < cfg.n_chain_rel_background and cold_cursor < len(cold_person) - 60:
        hop = 1 + int(rng.integers(3))
        st, ot = HOP_TYPES[hop]
        r = HOP_RELS[hop][int(rng.integers(len(HOP_RELS[hop])))]
        s = next_cold_person() if st == "person" else cold_org[int(rng.integers(len(cold_org)))]
        if try_add(s, r, pool[ot][int(rng.integers(len(pool[ot])))], "chain_rel_bg"):
            added += 1

    # ---- typical facts: a cold subject used exactly once, COLD relation
    guard, n_typ = 0, 0
    while n_typ < cfg.n_typical and guard < 40 * cfg.k_total:
        guard += 1
        r, st, ot = COLD_RELS[int(rng.integers(len(COLD_RELS)))]
        if st == "person":
            if cold_cursor >= len(cold_person):
                break
            s = next_cold_person()
        else:
            s = cold_org[int(rng.integers(len(cold_org)))]
        if try_add(s, r, pool[ot][int(rng.integers(len(pool[ot])))], "typical"):
            n_typ += 1

    # ---- pure load filler (sweep only; n_load_filler = 0 in the main config)
    guard, added_f = 0, 0
    while added_f < cfg.n_load_filler and guard < 60 * (cfg.n_load_filler + 1):
        guard += 1
        # PERSON-subject filler relations only, with subjects drawn ONLY from
        # cold persons not yet consumed by chain starts / chain-rel background
        # / typical facts. Org subjects are excluded because typical facts may
        # also use cold orgs, and any overlap raises a probe-class subject's
        # out-degree -- which decays the degree contrast exactly as load rises,
        # i.e. weakens the null precisely where it must be strongest.
        pf = [(r, ot) for r, st, ot in FILLER_RELS if st == "person"]
        r, ot = pf[int(rng.integers(len(pf)))]
        src = cold_person[cold_cursor:]
        if not len(src):
            break
        s_ = src[int(rng.integers(len(src)))]
        if try_add(s_, r, pool[ot][int(rng.integers(len(pool[ot])))], "load_filler"):
            added_f += 1

    w.facts = facts
    w.degree = _degree_stats(facts)

    # ---- probe sets: identical question form, different contention.
    # KUMAR = high-degree chain facts at hop >= 2 (hub subject, chain relation)
    # TYPICAL = degree-1 cold subject, cold relation
    intact = [c for c in w.chains if c.arm == "intact" and c.hops >= 2]
    kp = [(c.links[i][0], c.links[i][1], c.links[i][2])
          for c in intact for i in range(1, c.hops)]
    tp = [(f.subj, f.rel, f.obj) for f in facts if f.kind == "typical"]
    rng.shuffle(kp)
    rng.shuffle(tp)
    w.kumar_probe = kp[: cfg.n_probe]
    w.typical_probe = tp[: cfg.n_probe]
    return w


def build(cfg: PartitionConfig):
    for i in range(cfg.n_worlds):
        yield build_world(cfg, i)


def registry_names(cfg: PartitionConfig, world: World):
    """Every entity string the world touches (the shared codebook)."""
    names = []
    for f in world.facts:
        names.extend((f.subj, f.obj))
    for c in world.chains:
        names.append(c.start)
        for s, _, o in c.links:
            names.extend((s, o))
    return list(dict.fromkeys(names))


def chance_baseline(world: World, cfg: PartitionConfig):
    """P(a random codebook entry of the correct type is the gold answer),
    per hop-length. Answer types follow HOP_TYPES."""
    names = set(registry_names(cfg, world))
    persons, _q, orgs, cities = _pools()
    n = {"person": len(names & set(persons)), "org": len(names & set(orgs)),
         "city": len(names & set(cities))}
    N = len(names)
    return {L: {"answer_type": HOP_TYPES[L][1], "n_type": n[HOP_TYPES[L][1]],
                "chance_typed": 1.0 / max(1, n[HOP_TYPES[L][1]]),
                "chance_untyped": 1.0 / max(1, N)} for L in HOPS}


def degree_summary(world: World):
    """Logged per world: the degree distribution that defines the regime."""
    d = world.degree
    hubs = [s for s, c in d["out_degree"].items() if c >= 5]

    def q(vals):
        v = np.asarray(sorted(vals)) if vals else np.array([0])
        return {"mean": float(v.mean()), "p50": float(np.percentile(v, 50)),
                "p90": float(np.percentile(v, 90)), "max": int(v.max())}
    chain_rel = [d["rel_degree"].get(r, 0) for r in CHAIN_RELS]
    cold_rel = [d["rel_degree"].get(r, 0) for r in COLD_REL_NAMES]
    # the two probe classes, by the degree of their SUBJECT
    hub_subjects = {f.subj for f in world.facts if f.kind in ("hub_subject",)}
    typ_subjects = {f.subj for f in world.facts if f.kind == "typical"}
    hub_out = [d["out_degree"][s] for s in hub_subjects]
    typ_out = [d["out_degree"][s] for s in typ_subjects]
    return {
        "n_facts": len(world.facts),
        "n_entities": len(set(list(d["out_degree"]) + list(d["in_degree"]))),
        "out_degree": q(list(d["out_degree"].values())),
        "in_degree": q(list(d["in_degree"].values())),
        "n_high_out_degree_entities": len(hubs),
        "chain_relation_degree": q(chain_rel),
        "cold_relation_degree": q(cold_rel),
        "filler_relation_degree": q([d["rel_degree"].get(r, 0) for r in FILLER_REL_NAMES]),
        "hub_out_degree": q(hub_out), "typical_out_degree": q(typ_out),
        "degree_ratio_hub_vs_typical": (float(np.mean(hub_out)) / float(np.mean(typ_out))
                                        if typ_out and np.mean(typ_out) else float("nan")),
        "kind_counts": {k: sum(1 for f in world.facts if f.kind == k)
                        for k in ("chain", "hub_subject", "hub_object",
                                  "chain_rel_bg", "typical", "load_filler")},
    }
