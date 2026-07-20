"""product-p0 / rg-1.1 — the §5.4 near-synonym collision test corpus (seeded,
config-sized). Focused rebuild from e5/corpus_v2.py conventions: four
families, each query carrying ground truth + a collision label, so the fix
can be measured BEFORE (frozen key-identity) vs AFTER (semantic margin).

Families (label = is this query part of a genuine stored CONTRADICTION?):
  collide_syn  (POSITIVE): same subject, a SYNONYM relation pair
     (works-at/is-employed-by, lives-in/resides-in), two DIFFERENT objects
     -> one residence/employer contradicted under a paraphrased key. The
     first-written arm is the ground-truth-designated referent (TRUE); the
     second is STALE. Two query items per pair (one per relation surface):
     under strict scoring the correct forced answer is the TRUE object for
     BOTH, but the RIGHT behaviour is to DELIBERATE (return both) — that is
     what drops "answers both ways".
  collide_key  (POSITIVE): same person under near-DUPLICATE subject keys
     ("Maria Garcia" / "Maria Garcia's"), same relation, two different
     objects. Two query items (canonical + variant).
  clean_single (NEGATIVE): a singleton fact, canonically queried. Not a
     collision; must still ANSWER.
  distinct_attr(NEGATIVE, the false-positive guard): same subject, two
     DISTINCT relations that are semantically NEARBY but denote different
     attributes (studied-at/works-at, lives-in/was-born-in) with different
     objects -- BOTH valid, NOT a conflict. The fix must NOT flag these.
     Two query items per pair.

STRICT scoring primary (gold_strict = designated referent; None if no forced
answer is correct). Objects type-matched to relations.
"""

import os
import sys

from dataclasses import dataclass, field

import _env  # noqa: F401
import numpy as np

from entities import FIRST, QUALIFIER, make_entities
from registry import Registry
from write_path import Memory

_env.patch_cache()

SYN_PAIRS = [("works at", "is employed by"), ("lives in", "resides in")]
# distinct-but-nearby relation pairs (measured raw cos 0.52-0.56 — HIGHER
# than the works-at/is-employed-by synonym at 0.43; the hard false-positive
# cases). Both relations denote different, individually-valid attributes.
DISTINCT_HARD = [("studied at", "works at"), ("lives in", "was born in"),
                 ("is employed by", "studied at"), ("resides in", "was born in")]
PLAIN_RELS = ["was born in", "manages", "reports to", "is married to",
              "is a sibling of", "studied at"]
PERSON_RELS = {"manages", "reports to", "is married to", "is a sibling of"}
PLACE_RELS = {"lives in", "resides in", "was born in", "studied at"}
ORG_RELS = {"works at", "is employed by"}
ALL_RELS = sorted({r for p in SYN_PAIRS for r in p}
                  | {r for p in DISTINCT_HARD for r in p}
                  | set(PLAIN_RELS))


@dataclass
class CollisionConfig:
    seed: int = 6661001
    n_entities: int = 700
    n_syn: int = 40          # near-synonym collision pairs -> 80 queries
    n_key: int = 20          # near-dup-key collision pairs  -> 40 queries
    n_single: int = 40       # clean singletons
    n_distinct: int = 30     # distinct-attribute pairs (FP guard) -> 60 queries
    min_m_ref: float = 0.20


@dataclass
class CItem:
    kind: str            # syn_a|syn_b|key_canon|key_var|single|distinct_a|distinct_b
    family: str          # collide_syn|collide_key|clean_single|distinct_attr
    label: int           # 1 = genuine collision query, 0 = not
    subj_term: str
    rel: str
    gold_strict: object
    gold_either: object
    meta: dict = field(default_factory=dict)


@dataclass
class CCorpus:
    config: CollisionConfig
    memory: Memory
    items: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    pairs: dict = field(default_factory=dict)   # family -> list of (item_a, item_b)


def _variant(name, i):
    return [name + "'s", name[:len(name) // 2] + name[len(name) // 2 + 1:],
            name + " Jr"][i % 3]


def build_collision(cfg):
    rng = np.random.default_rng(cfg.seed)
    base = make_entities(cfg.n_entities, cfg.seed)
    orgendings = ("Labs", "Analytics", "Logistics", "Systems", "Consulting",
                  "Dynamics", "Robotics", "Foods", "Energy", "Media")
    persons = [e for e in base if " " in e and "(" not in e
               and not any(e.endswith(b) for b in orgendings)]
    orgs = [e for e in base if any(e.endswith(b) for b in orgendings)]
    cities = [e for e in base if (" " not in e or "(" in e)
              and e not in persons and e not in orgs]

    near = [(p, _variant(p, i)) for i, p in enumerate(persons[:cfg.n_key])]
    near_canon = {p for p, _ in near}
    near_var = {v for _, v in near}
    pool = list(dict.fromkeys(base + [v for _, v in near]))
    ent = Registry(pool)
    rel = Registry(ALL_RELS)
    mem = Memory(ent, rel)

    # each subject is used by AT MOST ONE family (disjoint blocks): a subject
    # reused across families could receive genuinely-synonymous facts from two
    # families and become a REAL uncontrolled collision, muddying the labels.
    isolated = [p for p in persons if p not in near_canon and p not in near_var
                and ent.m_ref(p) >= cfg.min_m_ref]
    rng.shuffle(isolated)
    need = cfg.n_syn + cfg.n_distinct + cfg.n_single
    if len(isolated) < need:
        raise ValueError(f"need {need} isolated subjects, have {len(isolated)} "
                         f"(raise n_entities)")
    syn_subjs = isolated[:cfg.n_syn]
    distinct_subjs = isolated[cfg.n_syn:cfg.n_syn + cfg.n_distinct]
    single_subjs = isolated[cfg.n_syn + cfg.n_distinct:need]

    def obj_for(r, exclude=()):
        src = persons if r in PERSON_RELS else orgs if r in ORG_RELS else cities
        for _ in range(200):
            o = src[int(rng.integers(len(src)))]
            if o not in exclude:
                return o
        return None

    used, items, rejected = set(), [], []
    pairs = {"collide_syn": [], "collide_key": [], "distinct_attr": []}

    def w(s, r, o):
        res = mem.write(s, r, o)
        if not res.accepted:
            rejected.append((s, r, o, res.reason))
        return res.accepted

    # collide_syn: one synonym pair per (disjoint) subject
    for s in syn_subjs:
        ra, rb = SYN_PAIRS[int(rng.integers(len(SYN_PAIRS)))]
        oa = obj_for(ra)
        ob = obj_for(rb, exclude={oa})
        if oa is None or ob is None or not (w(s, ra, oa) and w(s, rb, ob)):
            continue
        used |= {(s, ra), (s, rb)}
        ia = CItem("syn_a", "collide_syn", 1, s, ra, oa, {oa, ob},
                   {"true": oa, "stale": ob, "pair": (ra, rb)})
        ib = CItem("syn_b", "collide_syn", 1, s, rb, oa, {oa, ob},
                   {"true": oa, "stale": ob, "pair": (ra, rb)})
        items += [ia, ib]
        pairs["collide_syn"].append((ia, ib))

    # collide_key
    for s, v in near:
        if len(pairs["collide_key"]) >= cfg.n_key:
            break
        r = PLAIN_RELS[int(rng.integers(len(PLAIN_RELS)))]
        if (s, r) in used or (v, r) in used:
            continue
        oa = obj_for(r)
        ob = obj_for(r, exclude={oa})
        if oa is None or ob is None or not (w(s, r, oa) and w(v, r, ob)):
            continue
        used |= {(s, r), (v, r)}
        ia = CItem("key_canon", "collide_key", 1, s, r, oa, {oa, ob},
                   {"true": oa, "stale": ob, "variant": v})
        ib = CItem("key_var", "collide_key", 1, v, r, oa, {oa, ob},
                   {"true": oa, "stale": ob, "canonical": s})
        items += [ia, ib]
        pairs["collide_key"].append((ia, ib))

    # distinct_attr (false-positive guard): same subject, two DISTINCT nearby
    # relations, two different objects, both valid — one pair per subject
    for s in distinct_subjs:
        rx, ry = DISTINCT_HARD[int(rng.integers(len(DISTINCT_HARD)))]
        ox = obj_for(rx)
        oy = obj_for(ry, exclude={ox})
        if ox is None or oy is None or not (w(s, rx, ox) and w(s, ry, oy)):
            continue
        used |= {(s, rx), (s, ry)}
        ia = CItem("distinct_a", "distinct_attr", 0, s, rx, ox, {ox},
                   {"pair": (rx, ry)})
        ib = CItem("distinct_b", "distinct_attr", 0, s, ry, oy, {oy},
                   {"pair": (rx, ry)})
        items += [ia, ib]
        pairs["distinct_attr"].append((ia, ib))

    # clean_single: one fact per (disjoint) subject
    for s in single_subjs:
        r = ALL_RELS[int(rng.integers(len(ALL_RELS)))]
        o = obj_for(r)
        if o is None or not w(s, r, o):
            continue
        used.add((s, r))
        items.append(CItem("single", "clean_single", 0, s, r, o, {o}, {}))

    rng.shuffle(items)
    return CCorpus(cfg, mem, items, rejected, pairs)
