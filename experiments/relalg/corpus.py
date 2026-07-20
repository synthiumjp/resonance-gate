"""E8 relation-algebra study: 3-hop chains stratified by the ALGEBRAIC TYPE
of the relation at each hop, with store load held constant across conditions.

THE INDEPENDENT VARIABLE is relation structure. k is padded to an identical
constant in EVERY condition and sits inside the capacity law, so no contrast
in this experiment can be explained by load. That padding has a consequence
worth stating plainly: with k constant by construction, the ALL-FUNCTIONAL
condition IS the load-matched control -- it is the same store size as the
fan-out conditions with none of the shared-key structure. A separate
"inflate the functional store to match" arm would be the identical object.
An UNPADDED fan-out arm is included anyway, to show what the naive
comparison would have looked like and hence what the control removes.

RELATION TYPES, by algebraic signature:
  FUNCTIONAL (1:1)   each (subj, rel) key carries exactly one object.
  ONE-TO-MANY (F)    each (subj, rel) key carries F objects. This is a
                     STORED COLLISION in rg-1.1's terms -- the same key
                     answered F ways -- so the unbind returns a superposition
                     of F object vectors and cleanup must choose among them.
  SYMMETRIC          r(a,b) implies r(b,a); both directions stored.

CONDITIONS (each its own store, k padded to cfg.k_total):
  functional              F-F-F. Also the load-matched control.
  fanout_h{1,2,3} x F     fan-out at that hop, F in {2,4,8}.
  scrambled_h{1,2,3} x F  the ALGEBRA-SCRAMBLED control. Identical fact
                          count and identical k to its fan-out twin, but the
                          F-1 sibling objects are re-homed to FRESH DISTINCT
                          SUBJECTS under the SAME relation. Load, relation
                          degree and fact count are all preserved; the only
                          thing destroyed is that F objects shared one key.
  fanout_h2_unpadded x F  fan-out with k NOT padded (the confounded compare).
  symmetric               person-person chain, reverse edges stored.
  symmetric_baseline      same template and relations, forward edges only.

BRANCHING (decided with the registrant): at a fan-out hop ALL F siblings get
full onward chains, so a valid-but-unintended sibling still resolves at the
next hop. Without this a hop-2 mispick would surface as a hop-3 failure and
the localisation measurement could not tell "fan-out breaks hop 2" from
"fan-out breaks everything downstream".

SCORING is deliberately two-valued and both are reported: ANY-VALID (did the
traversal end on any object reachable by a legal path) and SPECIFIC (did it
end on the one designated target). They answer different questions -- can it
traverse fan-out at all, versus can it pick the intended branch.

Writes use echo=False so every condition holds exactly the fact set the design
specifies; the frozen echo-check would otherwise reject writes load-dependently
and desynchronise k across conditions.

Seeds: cfg.seed + 1000*world_index, logged per world.
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

# Per hop position: a FUNCTIONAL and a ONE-TO-MANY relation with the SAME type
# signature, so the algebraic type can be swapped at a hop without changing
# the entity types the chain runs through. None of these strings are members
# of gate/l2_ambiguity.RELATION_SYNONYMS, so relation_equiv never conflates
# two distinct relations here.
FUNC_RELS = {1: "works at", 2: "was founded by", 3: "was born in"}
MANY_RELS = {1: "is a member of", 2: "is advised by", 3: "has lived in"}
HOP_TYPES = {1: ("person", "org"), 2: ("org", "person"), 3: ("person", "city")}

# Symmetric template runs person->person->person->person so r(b,a) typechecks.
SYM_RELS = ["is a sibling of", "is married to", "is a cousin of"]
SYMBASE_RELS = ["reports to", "manages", "mentors"]

FILLER_RELS = [
    ("advises", "person", "person"), ("coaches", "person", "person"),
    ("recruited", "person", "person"), ("replaced", "person", "person"),
    ("commutes to", "person", "city"), ("holidays in", "person", "city"),
    ("owns property in", "person", "city"), ("votes in", "person", "city"),
    ("supplies", "org", "org"), ("licenses to", "org", "org"),
    ("partners with", "org", "org"), ("subcontracts to", "org", "org"),
    ("is headquartered in", "org", "city"), ("banks in", "org", "city"),
    ("consults for", "person", "org"), ("interned at", "person", "org"),
]
SCRAMBLE_SUFFIX = ""   # scrambled siblings keep the SAME relation, by design

ALL_RELS = (list(FUNC_RELS.values()) + list(MANY_RELS.values()) + SYM_RELS
            + SYMBASE_RELS + [r for r, _, _ in FILLER_RELS])

F_VALUES = (2, 4, 8)


@dataclass
class RelAlgConfig:
    seed: int = 20260722
    n_worlds: int = 20
    chains_per_world: int = 5      # -> 100 chains per condition
    n_person: int = 700
    n_org: int = 150
    n_city: int = 40
    k_total: int = 150             # constant across conditions, and genuinely
                                   # INSIDE capacity: at k=400 this corpus runs
                                   # N~500 so k_max ~= 420 and even the
                                   # functional baseline was load-degraded to
                                   # ~0.3, compressing every contrast. At k=150
                                   # (N~160-230, k_max ~480-516) the store is at
                                   # ~30% of capacity, so a fan-out effect
                                   # cannot be load in disguise. The k=400 run
                                   # is retained as an at-capacity stress point
                                   # in report_k400.json.


@dataclass
class Fact:
    subj: str
    rel: str
    obj: str
    kind: str


@dataclass
class Chain:
    condition: str
    world: int
    fanout_hop: object       # 0-based hop index carrying the fan-out, or None
    F: int                   # 1 when no fan-out
    start: str
    rels: list               # length-3 relation surfaces
    intended_path: list      # [start, o1, o2, o3]
    intended_final: str
    valid_finals: set
    valid_at: dict           # (hop_index, subject) -> set(valid objects)
    key_card: list           # objects stored at the intended-path key, per hop
    symmetric: bool = False


@dataclass
class World:
    condition: str
    index: int
    seed: int
    F: int = 1
    facts: list = field(default_factory=list)
    chains: list = field(default_factory=list)
    n_filler: int = 0
    n_reverse_skipped: int = 0


def _fresh(pool, cursor, t):
    """An entity that will later be used as a SUBJECT: must be unused, or
    two chains would silently share a (subj, rel) key and manufacture
    unintended fan-out."""
    i = cursor[t]
    if i >= len(pool[t]):
        raise RuntimeError(f"entity pool '{t}' exhausted ({len(pool[t])})")
    cursor[t] += 1
    return pool[t][i]


def _draw(pool, cursor, t, rng, terminal, seen=None):
    """Terminal (last-hop) objects are pure sinks -- nothing is ever keyed on
    them -- so they may repeat ACROSS chains, which is what keeps the 40-entry
    city pool from being exhausted by wide fan-out. Within a chain they must
    still be DISTINCT: two siblings landing on the same object would collapse
    a fan-out key below cardinality F and shrink valid_finals, quietly making
    the condition weaker than its label. Non-terminal objects become the next
    hop's subject and must be globally fresh."""
    if not terminal:
        return _fresh(pool, cursor, t)
    if seen is None:
        return pool[t][int(rng.integers(len(pool[t])))]
    if len(seen) >= len(pool[t]):
        raise RuntimeError(f"terminal pool '{t}' too small for this fan-out")
    while True:
        o = pool[t][int(rng.integers(len(pool[t])))]
        if o not in seen:
            seen.add(o)
            return o


def _build_branching_chain(rels, fanout_hop, F, pool, cursor, add, kind, htypes, rng, sink_ok=True):
    """Build one 3-hop chain. At fanout_hop the key carries F objects and
    EVERY sibling gets its own full onward chain."""
    start = _fresh(pool, cursor, htypes[1][0])
    valid_at, key_card = {}, [1, 1, 1]
    seen_term = set()          # terminal objects already used BY THIS CHAIN
    # frontier: list of subjects alive at the current hop
    frontier = [start]
    intended = [start]
    for h in range(3):
        rel = rels[h]
        _, obj_t = htypes[h + 1]
        width = F if (fanout_hop is not None and h == fanout_hop) else 1
        terminal = (h == 2) and sink_ok
        new_frontier = []
        for si, subj in enumerate(frontier):
            objs = [_draw(pool, cursor, obj_t, rng, terminal, seen_term)
                    for _ in range(width)]
            valid_at[(h, subj)] = set(objs)
            for o in objs:
                add(subj, rel, o, kind)
            new_frontier.extend(objs)
        if fanout_hop is not None and h == fanout_hop:
            key_card[h] = F
        # the intended branch is always sibling 0 of the intended subject
        intended.append(sorted(valid_at[(h, intended[-1])])[0]
                        if len(valid_at[(h, intended[-1])]) > 1
                        else next(iter(valid_at[(h, intended[-1])])))
        frontier = new_frontier
    valid_finals = set(frontier)
    return start, intended, valid_finals, valid_at, key_card


def _build_scrambled_chain(rels, fanout_hop, F, pool, cursor, add, kind, htypes, rng, sink_ok=True):
    """Algebra-scrambled twin: identical fact count and identical relations,
    but the F-1 siblings live under FRESH DISTINCT SUBJECTS, so no key is
    shared. The chain itself stays fully resolvable and functional."""
    start = _fresh(pool, cursor, htypes[1][0])
    valid_at, key_card = {}, [1, 1, 1]
    seen_term = set()
    frontier = [start]
    intended = [start]
    for h in range(3):
        rel = rels[h]
        subj_t, obj_t = htypes[h + 1]
        new_frontier = []
        terminal = (h == 2) and sink_ok
        for subj in frontier:
            o = _draw(pool, cursor, obj_t, rng, terminal, seen_term)
            valid_at[(h, subj)] = {o}
            add(subj, rel, o, kind)
            new_frontier.append(o)
            if fanout_hop is not None and h == fanout_hop:
                # the displaced siblings: same relation, fresh subjects, and
                # each still gets its onward chain so the fact count matches
                # the fan-out twin exactly
                for _ in range(F - 1):
                    alt_subj = _fresh(pool, cursor, subj_t)
                    alt_obj = _draw(pool, cursor, obj_t, rng, terminal, seen_term)
                    add(alt_subj, rel, alt_obj, kind)
                    valid_at[(h, alt_subj)] = {alt_obj}
                    new_frontier.append(alt_obj)
        intended.append(next(iter(valid_at[(h, intended[-1])])))
        frontier = new_frontier
    return start, intended, {intended[-1]}, valid_at, key_card


def build_world(cfg, condition, index, F=1, fanout_hop=None, pad=True):
    seed = cfg.seed + 1000 * index + 97 * (fanout_hop or 0) + 7 * F
    rng = np.random.default_rng(seed)
    persons, _q, orgs, cities = _pools()
    pool = {
        "person": [persons[i] for i in rng.permutation(len(persons))[: cfg.n_person]],
        "org": [orgs[i] for i in rng.permutation(len(orgs))[: cfg.n_org]],
        "city": [cities[i] for i in rng.permutation(len(cities))[: cfg.n_city]],
    }
    cursor = {t: 0 for t in pool}
    w = World(condition=condition, index=index, seed=seed, F=F)
    used = set()

    def add(s, r, o, kind):
        if s == o:
            return False
        used.add((s, r))
        w.facts.append(Fact(s, r, o, kind))
        return True

    symmetric = condition == "symmetric"
    if symmetric:
        rels = list(SYM_RELS)
    elif condition == "symmetric_baseline":
        rels = list(SYMBASE_RELS)
    else:
        rels = [MANY_RELS[h + 1] if (fanout_hop is not None and h == fanout_hop)
                else FUNC_RELS[h + 1] for h in range(3)]

    htypes = (HOP_TYPES if condition not in ("symmetric", "symmetric_baseline")
              else {1: ("person", "person"), 2: ("person", "person"),
                    3: ("person", "person")})
    if True:
        for _ in range(cfg.chains_per_world):
            n_before = len(w.facts)
            if condition.startswith("scrambled"):
                s, path, finals, va, kc = _build_scrambled_chain(
                    rels, fanout_hop, F, pool, cursor, add, "chain", htypes, rng,
                    sink_ok=not symmetric)
            else:
                s, path, finals, va, kc = _build_branching_chain(
                    rels, fanout_hop, F, pool, cursor, add, "chain", htypes, rng,
                    sink_ok=not symmetric)
            new_facts = w.facts[n_before:]
            if symmetric:
                # store the reverse of every forward edge. Note these land on
                # DIFFERENT keys (each hop uses a different relation), so
                # symmetry here adds facts WITHOUT creating fan-out -- which is
                # exactly what isolates "does the reverse copy corrupt" from
                # the fan-out effect.
                for f in new_facts:
                    if f.kind != "chain":
                        continue
                    if (f.obj, f.rel) in used:
                        w.n_reverse_skipped += 1   # would have made fan-out
                        continue
                    add(f.obj, f.rel, f.subj, "reverse")
            w.chains.append(Chain(
                condition=condition, world=index, fanout_hop=fanout_hop,
                F=F if fanout_hop is not None else 1, start=s, rels=rels,
                intended_path=path, intended_final=path[-1],
                valid_finals=finals, valid_at=va, key_card=kc,
                symmetric=symmetric))

    # ---- pad to the constant k with filler on fresh subjects
    if pad:
        guard = 0
        while len(w.facts) < cfg.k_total and guard < 60 * cfg.k_total:
            guard += 1
            r, st, ot = FILLER_RELS[int(rng.integers(len(FILLER_RELS)))]
            if cursor[st] >= len(pool[st]):
                continue          # this type is spent; try another relation
            s = _fresh(pool, cursor, st)
            o = pool[ot][int(rng.integers(len(pool[ot])))]
            if (s, r) in used:
                continue
            if add(s, r, o, "filler"):
                w.n_filler += 1
    validate(w)
    return w


def validate(w):
    """Assert the store realises the intended algebra: every intended-path key
    carries exactly the cardinality the condition specifies. Catches silent
    fan-out from entity reuse, which would contaminate the control arms."""
    key_objs = {}
    for f in w.facts:
        key_objs.setdefault((f.subj, f.rel), set()).add(f.obj)
    for c in w.chains:
        for h in range(3):
            subj = c.intended_path[h]
            got = len(key_objs.get((subj, c.rels[h]), ()))
            want = c.key_card[h]
            if got != want:
                raise AssertionError(
                    f"{w.condition} world {w.index} hop {h}: key "
                    f"({subj!r}, {c.rels[h]!r}) holds {got} objects, want {want}")


CONDITIONS = (
    [("functional", 1, None, True)]
    + [(f"fanout_h{h+1}", F, h, True) for h in (0, 1, 2) for F in F_VALUES]
    + [(f"scrambled_h{h+1}", F, h, True) for h in (0, 1, 2) for F in F_VALUES]
    + [("fanout_h2_unpadded", F, 1, False) for F in F_VALUES]
    + [("symmetric", 1, None, True), ("symmetric_baseline", 1, None, True)]
)


def condition_name(base, F, fanout_hop):
    return base if fanout_hop is None else f"{base}_F{F}"


def build_all(cfg):
    for base, F, fanout_hop, pad in CONDITIONS:
        name = condition_name(base, F, fanout_hop)
        for i in range(cfg.n_worlds):
            yield name, build_world(cfg, base, i, F=F, fanout_hop=fanout_hop, pad=pad)


def registry_names(world):
    names = []
    for f in world.facts:
        names.extend((f.subj, f.obj))
    for c in world.chains:
        names.append(c.start)
        for _, objs in c.valid_at.items():
            names.extend(objs)
    return list(dict.fromkeys(names))


def chance_baseline(world):
    """Random codebook entry of the final answer's type."""
    names = set(registry_names(world))
    persons, _q, orgs, cities = _pools()
    sym = world.condition in ("symmetric", "symmetric_baseline")
    target = set(persons) if sym else set(cities)
    n = len(names & target)
    return {"n_type": n, "chance_typed": 1.0 / max(1, n),
            "chance_untyped": 1.0 / max(1, len(names))}
