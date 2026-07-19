"""E5.1 fair corpus (seeded, config-sized). Built on instruments/corpus.py
conventions (Item-like records, one seeded rng, public write/query path
only) but a separate module: instruments/ is read-only.

Design goals (E5.1 brief, post-audit):
  - NEAR-SYNONYM COLLISIONS (f_syn): contradictory facts written under the
    synonym relation pairs entities.py ships as confusables
    (works at / is employed by, lives in / resides in). One object is
    ground-truth-designated TRUE, the other STALE; querying either member
    of the pair semantically asks the same question, so strict gold is the
    TRUE object for both queries. The frozen artifact unbinds each key
    separately — the Lisbon/Boston defect class from audit A4.
  - NEAR-DUPLICATE KEYS (f_nearkey): contradictory facts under
    near-duplicate subject strings ("Maria Garcia" / "Maria Garcia's",
    typo variants) — same person, two keys. Strict gold: the TRUE object.
  - ERROR MANUFACTURING (f_confusable): facts written for one member of a
    confusable full-name pair ("Tom Fischer" / "Tom Fisher" — distinct
    people, both registered); the OTHER member is queried. Nothing is on
    file about the queried person: strict gold None. A confident answer is
    a wrong-person error.
  - PARAPHRASE-WRITTEN (f_para): fact written under one member of a
    synonym relation pair, queried under the other. The fact is true of
    the person, so strict gold = the written object; the exact key is
    unwritten (membership oracle says "absent").
  - Kept from Phase C: f_id (singleton facts, canonical query), f_ood
    (never-written keys, known entities, no confusable-family adjacency),
    f_ref (bare-first-name referential probes).

STRICT SCORING is primary everywhere: a forced answer is correct only if
it equals the ground-truth-designated referent (gold_strict; None means no
answer is correct). Either-object scoring (gold_either) is carried for the
Phase C continuity row only.

Objects are TYPE-MATCHED to relations (persons/orgs/cities) — the audit
flagged Phase C's type-incoherent facts as a realism defect.

Family mix tuning (logged per the brief): the answered-error target
(>= 60 strict-incorrect items routed ANSWER by the frozen controller) was
reached on the DEV pilot (seed 5551001) at the default config below; the
pilot log lives in e5/pilot_mix.md.
"""

import os
import sys
from dataclasses import dataclass, field

import _env  # noqa: F401  (sys.path + cache redirect happen at import)

import numpy as np

from entities import FIRST, LAST, QUALIFIER, make_entities
from registry import Registry
from write_path import Memory

_env.patch_cache()

SYN_PAIRS = [("works at", "is employed by"), ("lives in", "resides in")]
PLAIN_RELS = ["was born in", "manages", "reports to", "is married to",
              "is a sibling of", "studied at"]
ALL_RELS = [r for p in SYN_PAIRS for r in p] + PLAIN_RELS

PERSON_RELS = {"manages", "reports to", "is married to", "is a sibling of"}
PLACE_RELS = {"lives in", "resides in", "was born in", "studied at"}
ORG_RELS = {"works at", "is employed by"}

# confusable surname pairs (from entities.LAST near-collisions)
SURNAME_PAIRS = [("Baker", "Barker"), ("Fischer", "Fisher"), ("Chen", "Cheng"),
                 ("Meyer", "Meier"), ("Olsen", "Olson"), ("Hansen", "Hanson"),
                 ("Weber", "Webber"), ("Schmidt", "Schmitt"),
                 ("Sousa", "Souza"), ("Klein", "Kline"), ("Zhang", "Zheng"),
                 ("Wang", "Wong")]


@dataclass
class CorpusV2Config:
    seed: int = 5552001
    n_entities: int = 500
    n_id: int = 36           # singleton facts, canonically queried
    n_ood: int = 40          # never-written keys, known entities
    n_syn_pairs: int = 74    # -> 2 queries each (true-rel + stale-rel)
    n_nearkey: int = 18      # -> 2 queries each (canonical + variant)
    n_confusable: int = 8    # write A, query confusable sibling B
    n_para: int = 6          # write rel-A, query synonym rel-B
    n_ref: int = 8           # bare-first-name referential probes
    n_distract: int = 8      # object has a registered near-sibling org
    min_m_ref: float = 0.25  # isolation filter for f_syn/f_id/f_distract
                             # subjects (keeps the referential channel out
                             # of the way of the families that must reach
                             # the ANSWER route)


@dataclass
class ItemV2:
    kind: str            # id | ood | syn_true | syn_stale | nearkey_true |
                         # nearkey_var | confusable | para | ref
    family: str          # f_id | f_ood | f_syn | f_nearkey | f_confusable |
                         # f_para | f_ref
    subj_term: str
    rel: str
    gold_strict: object  # object str, or None (no forced answer is correct)
    gold_either: object  # set of acceptable objects under Phase C-style
                         # scoring, or None
    meta: dict = field(default_factory=dict)


@dataclass
class CorpusV2:
    config: CorpusV2Config
    memory: Memory
    items: list = field(default_factory=list)
    rejected_writes: list = field(default_factory=list)


def _variant(name, style):
    if style == 0:
        return name + "'s"                       # possessive
    if style == 1:
        i = len(name) // 2                       # single-char deletion typo
        return name[:i] + name[i + 1:]
    return name + " Jr"                          # suffix


def build_v2(cfg: CorpusV2Config) -> CorpusV2:
    rng = np.random.default_rng(cfg.seed)

    # ---- entity pools (all query subjects registered: known-entity rule)
    base = make_entities(cfg.n_entities, cfg.seed)
    persons = [e for e in base if " " in e and "(" not in e
               and not any(e.endswith(b) for b in ("Labs", "Analytics",
                   "Logistics", "Systems", "Consulting", "Dynamics",
                   "Robotics", "Foods", "Energy", "Media"))]
    orgs = [e for e in base if any(e.endswith(b) for b in ("Labs", "Analytics",
            "Logistics", "Systems", "Consulting", "Dynamics", "Robotics",
            "Foods", "Energy", "Media"))]
    cities = [e for e in base if " " not in e or "(" in e]
    cities = [c for c in cities if c not in persons and c not in orgs]

    # confusable full-name pairs (both members registered, distinct people)
    conf_pairs = []
    fi = 0
    for f in FIRST:
        s1, s2 = SURNAME_PAIRS[fi % len(SURNAME_PAIRS)]
        conf_pairs.append((f"{f} {s1}", f"{f} {s2}"))
        fi += 1
        if len(conf_pairs) >= cfg.n_confusable:
            break

    # near-duplicate variants of real persons
    near_subjects = []
    for i, p in enumerate([x for x in persons if x not in
                           {m for pr in conf_pairs for m in pr}][: cfg.n_nearkey]):
        near_subjects.append((p, _variant(p, i % 3)))

    # referential families (bare first names, qualified members)
    ref_families = {}
    for f in FIRST[:cfg.n_ref]:
        ref_families[f] = [f"{f} ({q})" for q in QUALIFIER[:2]]

    pool = list(dict.fromkeys(
        base + [m for pr in conf_pairs for m in pr]
        + [v for _, v in near_subjects]
        + [m for fam in ref_families.values() for m in fam]))
    ent = Registry(pool)
    rel = Registry(ALL_RELS)
    mem = Memory(ent, rel)

    def obj_for(r, exclude=()):
        p = (list(PERSON_RELS) and persons) if r in PERSON_RELS else None
        src = persons if r in PERSON_RELS else orgs if r in ORG_RELS else cities
        while True:
            o = src[int(rng.integers(len(src)))]
            if o not in exclude:
                return o

    used = set()
    items, rejected = [], []

    def write(s, r, o):
        wr = mem.write(s, r, o)
        if not wr.accepted:
            rejected.append((s, r, o, wr.reason))
        return wr.accepted

    conf_members = {m for pr in conf_pairs for m in pr}
    near_members = {m for pr in near_subjects for m in pr}
    ref_members = {m for fam in ref_families.values() for m in fam}
    special = conf_members | near_members | ref_members
    plain_persons = [p for p in persons if p not in special]
    # isolation filter: subjects for the must-reach-ANSWER families need a
    # clean referential margin (the registry is fixed before any write, so
    # m_ref is static and this is corpus design, not gate tuning)
    isolated = [p for p in plain_persons if ent.m_ref(p) >= cfg.min_m_ref]
    rng.shuffle(isolated)

    # org sibling pairs sharing the ORG_A prefix (both registered) for the
    # distractor-object family
    org_sibs = []
    by_prefix = {}
    for o in orgs:
        by_prefix.setdefault(o.split()[0], []).append(o)
    for pref, group in by_prefix.items():
        if len(group) >= 2:
            org_sibs.append((group[0], group[1]))

    # ---- f_syn: contradictory facts under synonym relation pairs.
    # Work-list = (isolated subject) x (both synonym pairs), shuffled: each
    # subject can supply up to len(SYN_PAIRS) collision pairs. Attempt-capped
    # (the pair index is chosen from the work-list, NOT coupled to a single
    # counter — an earlier version keyed subject and pair to the same index,
    # which parity-locked on even-sized isolated pools).
    syn_work = [(s, pair) for s in isolated for pair in SYN_PAIRS]
    rng.shuffle(syn_work)
    for s, (ra, rb) in syn_work:
        if sum(1 for i in items if i.family == "f_syn") >= 2 * cfg.n_syn_pairs:
            break
        r_true, r_stale = (ra, rb) if int(rng.integers(2)) else (rb, ra)
        if (s, r_true) in used or (s, r_stale) in used:
            continue
        o_true = obj_for(r_true)
        o_stale = obj_for(r_true, exclude={o_true})
        if not (write(s, r_true, o_true) and write(s, r_stale, o_stale)):
            continue
        used.add((s, r_true))
        used.add((s, r_stale))
        both = {o_true, o_stale}
        items.append(ItemV2("syn_true", "f_syn", s, r_true, o_true, both,
                            {"pair": (r_true, r_stale), "o_stale": o_stale}))
        items.append(ItemV2("syn_stale", "f_syn", s, r_stale, o_true, both,
                            {"pair": (r_true, r_stale), "o_stale": o_stale}))

    # ---- f_nearkey: contradictory facts under near-duplicate subject keys
    for s, v in near_subjects:
        r = PLAIN_RELS[int(rng.integers(len(PLAIN_RELS)))]
        if (s, r) in used or (v, r) in used:
            r = "studied at" if (s, "studied at") not in used else "was born in"
        o_true = obj_for(r)
        o_stale = obj_for(r, exclude={o_true})
        if not (write(s, r, o_true) and write(v, r, o_stale)):
            continue
        used.add((s, r))
        used.add((v, r))
        both = {o_true, o_stale}
        items.append(ItemV2("nearkey_true", "f_nearkey", s, r, o_true, both,
                            {"variant": v, "o_stale": o_stale}))
        items.append(ItemV2("nearkey_var", "f_nearkey", v, r, o_true, both,
                            {"canonical": s, "o_stale": o_stale}))

    # ---- f_confusable: fact for A, query sibling B (nothing about B on file)
    for a, b in conf_pairs:
        r = ALL_RELS[int(rng.integers(len(ALL_RELS)))]
        if (a, r) in used:
            continue
        o = obj_for(r)
        if not write(a, r, o):
            continue
        used.add((a, r))
        used.add((b, r))  # reserve: B's key stays unwritten
        items.append(ItemV2("confusable", "f_confusable", b, r, None, None,
                            {"written_sibling": a, "sibling_obj": o}))

    # ---- f_para: written under rel-A, queried under synonym rel-B
    para_work = [(s, pair) for s in isolated for pair in SYN_PAIRS]
    rng.shuffle(para_work)
    for s, (ra, rb) in para_work:
        if sum(1 for i in items if i.family == "f_para") >= cfg.n_para:
            break
        r_w, r_q = (ra, rb) if int(rng.integers(2)) else (rb, ra)
        if (s, r_w) in used or (s, r_q) in used:
            continue
        o = obj_for(r_w)
        if not write(s, r_w, o):
            continue
        used.add((s, r_w))
        used.add((s, r_q))  # the queried key stays unwritten
        items.append(ItemV2("para", "f_para", s, r_q, o, {o},
                            {"written_rel": r_w}))

    # ---- f_distract: object has a registered near-sibling org (crosstalk
    # error class: cleanup may land on "Acme Analytics" when "Acme Labs"
    # was stored — the L1 margin these errors shrink is NOT a d-source in
    # the two-source gate, so they present as clean answers)
    distract_work = [(s, r) for s in isolated for r in ORG_RELS]
    rng.shuffle(distract_work)
    dk = 0
    for s, r in distract_work:
        if sum(1 for i in items if i.family == "f_distract") >= cfg.n_distract \
                or not org_sibs:
            break
        if (s, r) in used:
            continue
        o1, o2 = org_sibs[dk % len(org_sibs)]
        dk += 1
        if not write(s, r, o1):
            continue
        used.add((s, r))
        items.append(ItemV2("distract", "f_distract", s, r, o1, {o1},
                            {"sibling_obj": o2}))

    # ---- f_id: singleton facts, canonically queried
    ii = 0
    while sum(1 for i in items if i.family == "f_id") < cfg.n_id:
        ii += 1
        if ii > 200 * cfg.n_id:
            break
        s = isolated[int(rng.integers(len(isolated)))]
        r = ALL_RELS[int(rng.integers(len(ALL_RELS)))]
        if (s, r) in used:
            continue
        o = obj_for(r)
        if not write(s, r, o):
            continue
        used.add((s, r))
        items.append(ItemV2("id", "f_id", s, r, o, {o}))

    # ---- f_ood: never-written keys; known entities; not confusable-adjacent
    oi = 0
    while sum(1 for i in items if i.family == "f_ood") < cfg.n_ood:
        oi += 1
        if oi > 400 * cfg.n_ood:
            break
        s = plain_persons[int(rng.integers(len(plain_persons)))]
        r = ALL_RELS[int(rng.integers(len(ALL_RELS)))]
        if (s, r) in used:
            continue
        # exclude synonym-sibling adjacency: the paired relation also unwritten
        sib = None
        for ra, rb in SYN_PAIRS:
            if r == ra:
                sib = rb
            elif r == rb:
                sib = ra
        if sib and (s, sib) in used:
            continue
        used.add((s, r))
        items.append(ItemV2("ood", "f_ood", s, r, None, None))

    # ---- f_ref: bare first names, both qualified members hold a fact
    for f, fam in ref_families.items():
        r = PLAIN_RELS[int(rng.integers(len(PLAIN_RELS)))]
        objs = []
        ok = True
        for m in fam:
            if (m, r) in used:
                ok = False
                break
            o = obj_for(r)
            if not write(m, r, o):
                ok = False
                break
            used.add((m, r))
            objs.append(o)
        if ok and objs:
            items.append(ItemV2("ref", "f_ref", f, r, None, set(objs),
                                {"members": set(fam)}))

    rng.shuffle(items)
    return CorpusV2(config=cfg, memory=mem, items=items,
                    rejected_writes=rejected)


def score_item(it, top1):
    """(strict, either) correctness of a forced answer for one item."""
    strict = (it.gold_strict is not None) and (top1 == it.gold_strict)
    if it.gold_either is None:
        either = False
    else:
        either = top1 in it.gold_either
    return strict, either
