"""E4 dev stimulus generator (seeded). Builds a synthetic personal-knowledge
corpus in the registry's entity families (confusables included), writes it
into a fresh substrate, and emits query sets with ground truth attached:

  ID   — written facts, answerable (gold = the stored object)
  OOD  — never-written (subj, rel), unanswerable (gold = ABSTAIN)
  COLL — planted stored-collisions (two objects under one key)
  REF  — referential-ambiguity probes (underspecified terms, >= 2 candidates)

Sized from CorpusConfig so the confirmatory set can later be generated at
any n with disjoint seeds. Nothing here touches substrate/gate/encoder/mouth
behaviour — it only USES the public write/query path.
"""

import os
import sys
from dataclasses import dataclass, field

_R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np

from entities import FIRST, QUALIFIER, make_entities
from registry import Registry
from write_path import Memory

RELATIONS = ["works at", "lives in", "was born in", "manages", "reports to",
             "is married to", "is a sibling of", "studied at", "is scheduled at"]
PERSON_RELS = {"manages", "reports to", "is married to", "is a sibling of"}
PLACE_RELS = {"lives in", "was born in", "studied at"}


@dataclass
class CorpusConfig:
    seed: int = 20260719
    n_entities: int = 500        # registry size (people + orgs + places)
    n_facts: int = 200           # singleton facts written (k stays < paging 280)
    n_id: int = 150              # ID queries (sampled from written facts)
    n_ood: int = 150             # never-written queries
    n_coll: int = 25             # planted stored-collisions (2 records each)
    n_ref: int = 25              # underspecified referential probes


@dataclass
class Item:
    kind: str                    # 'id' | 'ood' | 'coll' | 'ref'
    subj_term: str               # what the "user" asks with
    rel: str
    gold: object                 # ID: object str; OOD: None; COLL/REF: set of valid


@dataclass
class Corpus:
    config: CorpusConfig
    memory: Memory
    items: list = field(default_factory=list)
    facts: list = field(default_factory=list)


def build(cfg: CorpusConfig) -> Corpus:
    rng = np.random.default_rng(cfg.seed)
    pool = make_entities(cfg.n_entities, cfg.seed)
    # guarantee confusable first-name families for REF probes
    ref_families = {}
    for f in FIRST[:12]:
        fam = [f"{f} ({q})" for q in QUALIFIER[:2]]
        ref_families[f] = fam
        pool = fam + pool
    pool = list(dict.fromkeys(pool))[: cfg.n_entities]

    ent = Registry(pool)
    rel = Registry(RELATIONS)
    mem = Memory(ent, rel)

    def rand_obj(r, subj):
        while True:
            o = pool[int(rng.integers(len(pool)))]
            if o != subj:
                return o

    # ---- singleton facts (unique (subj, rel) keys)
    facts, used = [], set()
    while len(facts) < cfg.n_facts:
        s = pool[int(rng.integers(len(pool)))]
        r = RELATIONS[int(rng.integers(len(RELATIONS)))]
        if (s, r) in used:
            continue
        used.add((s, r))
        o = rand_obj(r, s)
        if mem.write(s, r, o).accepted:
            facts.append((s, r, o))

    # ---- planted collisions
    coll_items = []
    n_planted = 0
    while n_planted < cfg.n_coll:
        s = pool[int(rng.integers(len(pool)))]
        r = RELATIONS[int(rng.integers(len(RELATIONS)))]
        if (s, r) in used:
            continue
        used.add((s, r))
        o1, o2 = rand_obj(r, s), rand_obj(r, s)
        if o1 == o2:
            continue
        if mem.write(s, r, o1).accepted and mem.write(s, r, o2).accepted:
            coll_items.append(Item("coll", s, r, {o1, o2}))
            n_planted += 1

    # ---- ID queries: sample written singletons
    id_idx = rng.permutation(len(facts))[: cfg.n_id]
    id_items = [Item("id", facts[i][0], facts[i][1], facts[i][2]) for i in id_idx]

    # ---- OOD queries: keys never written (subjects can be known entities)
    ood_items = []
    while len(ood_items) < cfg.n_ood:
        s = pool[int(rng.integers(len(pool)))]
        r = RELATIONS[int(rng.integers(len(RELATIONS)))]
        if (s, r) in used:
            continue
        used.add((s, r))
        ood_items.append(Item("ood", s, r, None))

    # ---- referential probes: bare first names whose family members BOTH
    # have a written fact under the probed relation family
    ref_items = []
    fam_names = list(ref_families)
    fi = 0
    while len(ref_items) < cfg.n_ref and fi < 4 * len(fam_names):
        f = fam_names[fi % len(fam_names)]
        fi += 1
        members = ref_families[f]
        r = RELATIONS[int(rng.integers(len(RELATIONS)))]
        wrote, objs = [], []
        for m2 in members:
            if (m2, r) not in used:
                used.add((m2, r))
                o = rand_obj(r, m2)
                if mem.write(m2, r, o).accepted:
                    wrote.append(m2)
                    objs.append(o)
        if len(wrote) >= 1:
            # gold: candidate members (for routing) + their stored objects
            # (for forced-answer correctness scoring)
            ref_items.append(Item("ref", f, r,
                                  {"members": set(members), "objects": set(objs)}))

    items = id_items + ood_items + coll_items + ref_items
    rng.shuffle(items)
    return Corpus(config=cfg, memory=mem, items=items, facts=facts)
