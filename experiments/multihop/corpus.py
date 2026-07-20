"""E6 multi-hop corpora: seeded relational chains in three arms.

A CHAIN is a typed path of up to three links through the entity pools:

    person --works at--> org --was founded by--> person --lives in--> city

An L-hop item is the length-L PREFIX of that template, so hop-length is the
only thing that varies between the L=1/2/3 measurements: same schema, same
pools, same store size. Answer type differs by depth (org / person / city),
so the chance baseline is computed per depth against the correct type pool.

Three arms (the negative arms are the point — see notebook entry 23):

  INTACT      every link 1..L is written. gold = the L-th object.
  BROKEN      one MIDDLE link (hop j, 1 <= j < L) was never written, so the
              chain cannot resolve. gold = None (correct behaviour is to
              not answer). At L=1 there IS no middle link, so the arm
              degenerates to "the single link is absent" — identical to
              DISTRACTOR at L=1. Logged, not hidden.
  DISTRACTOR  links 1..L-1 are all written and resolvable, but the FINAL
              link L was never written: a valid partial chain that dead-ends.
              gold = None. Tests graceful failure vs confident wrong answer.

LOAD CONTROL. Every world is padded with filler facts to exactly cfg.k_facts
records, so store load is constant across arms and hop-lengths and accuracy
differences cannot be a capacity artefact. k=200 at N=440 sits well inside
the E1 capacity law k_max ~= D/(pi*ln N) ~= 428 (notebook entry 3).

Chains are entity-disjoint within a world and every (subject, relation) key
is written at most once, so nothing here plants a stored collision — a
missing link stays missing and cannot be supplied by filler.

Nothing in this module touches substrate/gate/encoder behaviour; it only
USES the public write/query path, exactly like instruments/corpus.py.
"""

import os
import sys
from dataclasses import dataclass, field

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from entities import _pools, CITY
from registry import Registry
from write_path import Memory

# The chain template: (relation, subject type, object type). Types are the
# pool names below; they drive both object sampling and the chance baseline.
CHAIN_TEMPLATE = [
    ("works at", "person", "org"),
    ("was founded by", "org", "person"),
    ("lives in", "person", "city"),
]
CHAIN_RELS = [r for r, _, _ in CHAIN_TEMPLATE]

# Filler relations, type-signed the same way. Drawn from the frozen
# RELATIONS10 vocabulary so filler crosstalk is realistic for this registry.
FILLER_TEMPLATE = [
    ("reports to", "person", "person"),
    ("manages", "person", "person"),
    ("is married to", "person", "person"),
    ("is a sibling of", "person", "person"),
    ("was born in", "person", "city"),
    ("studied at", "person", "org"),
]

ALL_RELS = CHAIN_RELS + [r for r, _, _ in FILLER_TEMPLATE]
HOPS = (1, 2, 3)
ARMS = ("intact", "broken", "distractor")


@dataclass
class MultihopConfig:
    seed: int = 20260720
    n_worlds: int = 10           # independent stores; 10 chains/arm/hop each
    chains_per_cell: int = 10    # -> 100 chains per (arm, hop-length)
    n_person: int = 300          # registry composition (N = 440)
    n_org: int = 100
    n_city: int = len(CITY)      # 40 (the whole city pool)
    k_facts: int = 200           # store load, held CONSTANT across all cells


@dataclass
class Chain:
    arm: str                     # 'intact' | 'broken' | 'distractor'
    hops: int                    # L
    world: int
    start: str                   # subject term the query starts from
    rels: list                   # length-L relation surfaces
    links: list                  # length-L intended (subj, rel, obj) triples
    stored: list                 # length-L bools: was this link written?
    missing_hop: object          # 0-based index of the absent link, or None
    gold: object                 # final object str (intact) or None


@dataclass
class World:
    index: int
    seed: int
    memory: Memory
    pools: dict                  # type -> list of registered names
    chains: list = field(default_factory=list)
    n_filler: int = 0
    n_rejected: int = 0          # echo-check rejections (should be ~0)


def _build_pools(cfg, rng):
    persons, qualified, orgs, cities = _pools()
    del qualified  # qualified first names are the confusable family: excluded
    p = [persons[i] for i in rng.permutation(len(persons))[: cfg.n_person]]
    o = [orgs[i] for i in rng.permutation(len(orgs))[: cfg.n_org]]
    c = [cities[i] for i in rng.permutation(len(cities))[: cfg.n_city]]
    return {"person": p, "org": o, "city": c}


def build_world(cfg: MultihopConfig, index: int) -> World:
    """One store: chains from every (arm, hop-length) cell + filler to k."""
    seed = cfg.seed + 1000 * index
    rng = np.random.default_rng(seed)
    pools = _build_pools(cfg, rng)

    ent = Registry(pools["person"] + pools["org"] + pools["city"])
    rel = Registry(ALL_RELS)
    mem = Memory(ent, rel)
    world = World(index=index, seed=seed, memory=mem, pools=pools)

    # entity budget: chains are entity-disjoint, so hand out from shuffled
    # cursors rather than resampling (keeps every chain independent)
    cursor = {t: 0 for t in pools}
    order = {t: list(rng.permutation(len(pools[t]))) for t in pools}

    def take(t):
        i = order[t][cursor[t]]
        cursor[t] += 1
        return pools[t][i]

    used_keys = set()     # (subj, rel) written OR deliberately reserved-absent
    planned = []          # (chain, [(triple, store_it_bool), ...])

    for arm in ARMS:
        for L in HOPS:
            for _ in range(cfg.chains_per_cell):
                tmpl = CHAIN_TEMPLATE[:L]
                # materialise the entity path
                path = [take(tmpl[0][1])]
                for _, _, obj_t in tmpl:
                    path.append(take(obj_t))
                links = [(path[i], tmpl[i][0], path[i + 1]) for i in range(L)]

                if arm == "intact":
                    missing = None
                elif arm == "broken":
                    # a MIDDLE link: hops 0..L-2. At L=1 there is none, so the
                    # single link is the one dropped (degenerate with
                    # distractor — recorded honestly in `missing_hop`).
                    missing = 0 if L == 1 else int(rng.integers(L - 1))
                else:  # distractor: the FINAL link is absent
                    missing = L - 1

                stored = [i != missing for i in range(L)]
                # reserve EVERY key on the path, stored or not, so no filler
                # fact can later supply a link that is meant to be absent
                if any((s, r) in used_keys for s, r, _ in links):
                    continue  # entity collision on a key; skip this chain
                for s, r, _ in links:
                    used_keys.add((s, r))

                gold = links[L - 1][2] if arm == "intact" else None
                ch = Chain(arm=arm, hops=L, world=index, start=links[0][0],
                           rels=[r for _, r, _ in links], links=links,
                           stored=stored, missing_hop=missing, gold=gold)
                planned.append((ch, links, stored))

    # ---- write the chain facts
    for ch, links, stored in planned:
        ok = True
        for (s, r, o), do_store in zip(links, stored):
            if not do_store:
                continue
            if not mem.write(s, r, o).accepted:
                world.n_rejected += 1
                ok = False
        if ok:
            world.chains.append(ch)

    # ---- filler to the constant load k_facts
    guard = 0
    while mem.k < cfg.k_facts and guard < 50 * cfg.k_facts:
        guard += 1
        r, subj_t, obj_t = FILLER_TEMPLATE[int(rng.integers(len(FILLER_TEMPLATE)))]
        s = pools[subj_t][int(rng.integers(len(pools[subj_t])))]
        o = pools[obj_t][int(rng.integers(len(pools[obj_t])))]
        if s == o or (s, r) in used_keys:
            continue
        used_keys.add((s, r))
        if mem.write(s, r, o).accepted:
            world.n_filler += 1
        else:
            world.n_rejected += 1

    return world


def build(cfg: MultihopConfig):
    """All worlds. Yields lazily so a run never holds 10 stores at once."""
    for i in range(cfg.n_worlds):
        yield build_world(cfg, i)


def chance_baseline(cfg: MultihopConfig):
    """P(a random codebook entry OF THE RIGHT TYPE is the gold answer), per
    hop-length. Also returns the untyped 1/N baseline, since cleanup actually
    searches the whole entity registry and may return an off-type answer."""
    n_type = {"person": cfg.n_person, "org": cfg.n_org, "city": cfg.n_city}
    N = sum(n_type.values())
    out = {}
    for L in HOPS:
        t = CHAIN_TEMPLATE[L - 1][2]
        out[L] = {"answer_type": t, "n_type": n_type[t],
                  "chance_typed": 1.0 / n_type[t], "chance_untyped": 1.0 / N}
    return out
