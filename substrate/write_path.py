"""E3 write path: extraction, echo-check, supersede/forget (plan 4.6-4.7),
plus the query path that feeds the two-source gate (E3.2).

Memory layout: L1 = running int64 accumulator over whitened records (sign at
read — O(1) writes, E1 exit criterion 3 unchanged); L2 = exact per-record
store with provenance metadata and tombstones; registries = the interface
layer (raw-cosine resolve). k and N are always known exactly.

Provenance design note (logged, entry 9): provenance is carried on the L2
entry, NOT multiplicatively bound into the bundle record — binding it in
would break (subj, rel) addressability, since queries don't know provenance
in advance. The E1 record algebra stays frozen.
"""

import json
import os
import numpy as np

from map_ops import encode_record
import normalisation as nz
from opinion import opinion_two_source
from controller import route_tagged
from l2_ambiguity import L2Store

D = 8192
# product-p1: the MCP layer exposes a caller-facing provenance vocabulary
# (caller-stated default, plus user-stated / agent-inferred / tool-derived).
# The frozen roles (user-stated / assistant-inferred / tool-derived) stay
# valid; provenance is stored VERBATIM so the record says exactly what the
# caller claimed.
PROVENANCE_ROLES = ("caller-stated", "user-stated", "agent-inferred",
                    "assistant-inferred", "tool-derived")
NEW_ENTRY_COSINE = 0.85  # resolve below this -> the string is a new registry entry
CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "encoder", "calibration_lambda075.json")


def default_calibration(recompute=False, seed=775):
    """(null_moments, hit_moments) for the lambda=0.75 substrate, cached to
    disk; recomputable from a clean checkout (delete the json)."""
    if os.path.exists(CALIB_PATH) and not recompute:
        with open(CALIB_PATH) as f:
            c = json.load(f)
        return (tuple(c["null"]),
                (c["hit"][0], np.array(c["hit"][1]), np.array(c["hit"][2])))
    from e31_common import Pools, calibrations
    from whitening import blend_transform, load_or_fit_zca
    from registry import LAMBDA_SUBSTRATE
    mu, W = load_or_fit_zca()
    p = Pools(D, transform=blend_transform(mu, W, LAMBDA_SUBSTRATE))
    nm, hm = calibrations(p, seed=seed)
    with open(CALIB_PATH, "w") as f:
        json.dump({"null": list(nm),
                   "hit": [hm[0], list(hm[1]), list(hm[2])],
                   "lambda": LAMBDA_SUBSTRATE, "seed": seed}, f, indent=1)
    return nm, hm


class WriteResult:
    def __init__(self, accepted, echo_a=None, reason=""):
        self.accepted = accepted
        self.echo_a = echo_a
        self.reason = reason


class QueryResult:
    def __init__(self, action, tag, op, record=None, provenance=None,
                 candidates=None, m_ref=None, m_l2=None, conflict=False,
                 resolution_hint=None, c_sem=None):
        self.action = action          # controller Action
        self.tag = tag                # None | 'referential' | 'stored'
        self.op = op                  # Opinion2
        self.record = record          # (subj, rel, obj) best resolved record
        self.provenance = provenance
        self.candidates = candidates  # referential entry names / stored records
        self.m_ref = m_ref
        self.m_l2 = m_l2
        # product-p0 / rg-1.1 passive-collision contract: on a detected
        # stored collision the server returns ALL disagreeing facts and does
        # NOT choose. conflict=True flags it; resolution_hint offers
        # {by_recency, by_resolution} the CALLER may apply or ignore. An
        # explicit update()/supersede() is a different event and DOES resolve
        # (frozen path, unchanged).
        self.conflict = conflict
        self.resolution_hint = resolution_hint
        self.c_sem = c_sem            # semantic collision score (diagnostic)


class Memory:
    def __init__(self, ent_registry, rel_registry, calib=None,
                 collision_mode="semantic"):
        self.ent = ent_registry
        self.rel = rel_registry
        nm, hm = calib if calib is not None else default_calibration()
        self.nm, self.hm = nm, hm
        self.acc = np.zeros(D, dtype=np.int64)
        self.store = L2Store(D)
        self.k = 0
        self._triple_index = {}  # (subj, rel, obj) -> store idx (active)
        # 'semantic' (rg-1.1 default): near-synonym-aware stored-collision
        # detection. 'key' reproduces rg-freeze-1.0 exactly (key-identity
        # margin only) — kept for the E5.2 BEFORE arm and A/B comparison.
        assert collision_mode in ("semantic", "key")
        self.collision_mode = collision_mode

    # ---------------------------------------------------------- write side

    def _record(self, subj, rel, obj):
        return encode_record(self.ent.vector(subj), self.rel.vector(rel),
                             self.ent.vector(obj)).astype(np.int64)

    def write(self, subj, rel, obj, provenance="user-stated", echo=True):
        """O(1) append + immediate echo-check read-back through the gate.
        Below-floor resolution -> reject, roll back, report (do not store)."""
        assert provenance in PROVENANCE_ROLES
        for name, reg in [(subj, self.ent), (rel, self.rel), (obj, self.ent)]:
            if name not in reg:
                reg.add([name])
        rec = self._record(subj, rel, obj)
        self.acc += rec
        idx = self.store.append(self.ent.vector(subj), self.rel.vector(rel),
                                obj, meta={"provenance": provenance,
                                           "triple": (subj, rel, obj)})
        self.k += 1
        if echo:
            a, _, top1 = self._unbind(subj, rel)
            z = nz.z_resolution(a, self.k, len(self.ent), D,
                                null_moments=self.nm, hit_moments=self.hm)
            # pass if the record resolves above floor to itself OR to a sibling
            # record under the same (subj, rel) key — that is a legitimate
            # stored collision (DELIBERATE handles it), not a failed write
            sibling = (subj, rel, top1) in self._triple_index
            if z <= 0 or (top1 != obj and not sibling):
                self.acc -= rec
                self.store.tombstone(idx)
                self.k -= 1
                return WriteResult(False, a, f"echo-check failed (z={float(z):.2f}, "
                                             f"read back '{top1}')")
            self._triple_index[(subj, rel, obj)] = idx
            return WriteResult(True, a)
        self._triple_index[(subj, rel, obj)] = idx
        return WriteResult(True)

    def forget(self, subj, rel, obj):
        """Subtract the exact record from the bundle + tombstone its L2 entry.
        Deleted stays deleted; k decrements (crosstalk shrinks with it)."""
        idx = self._triple_index.pop((subj, rel, obj), None)
        if idx is None:
            return False
        self.acc -= self._record(subj, rel, obj)
        self.store.tombstone(idx)
        self.k -= 1
        return True

    def supersede(self, subj, rel, old_obj, new_obj, provenance="user-stated"):
        """Correction: subtract/tombstone the old record, write the successor."""
        if not self.forget(subj, rel, old_obj):
            return WriteResult(False, reason="no such record to supersede")
        return self.write(subj, rel, new_obj, provenance=provenance)

    # ---------------------------------------------------------- read side

    def bundle(self):
        B = np.sign(self.acc).astype(np.int8)
        B[B == 0] = 1  # deterministic tie rule at read (acc holds exact sums)
        return B

    def _unbind(self, subj, rel):
        B = self.bundle()
        noisy = np.roll(B.astype(np.int32) * self.ent.vector(subj).astype(np.int32)
                        * np.roll(self.rel.vector(rel).astype(np.int32), 1), -2)
        cos = (self.ent.matrix().astype(np.float32) @ noisy.astype(np.float32)) / D
        order = np.argsort(-cos)[:2]
        a = float(cos[order[0]])
        m = a - float(cos[order[1]])
        return a, m, self.ent.names[order[0]]

    def query(self, subj_term, rel_term):
        """Full E3.2 read path: registry resolve (referential margin) ->
        whitened substrate unbind -> two-source gate -> tagged routing."""
        subj_res = self.ent.resolve(subj_term, top=2)
        rel_res = self.rel.resolve(rel_term, top=2)
        m_ref = (subj_res[0][1] - subj_res[1][1]) if len(subj_res) > 1 else 1.0
        subj, rel = subj_res[0][0], rel_res[0][0]

        if self.k == 0:
            op = opinion_two_source(0.0, 1, max(len(self.ent), 2), m_ref=m_ref,
                                    D=D, null_moments=self.nm, hit_moments=self.hm)
            return QueryResult("abstain", None, op, m_ref=m_ref)

        a, m_l1, top1 = self._unbind(subj, rel)
        c1, c2, o1, o2 = self.store.top2_batch(self.ent.vector(subj)[None, :],
                                               self.rel.vector(rel)[None, :])
        m_l2 = float(c1[0] - c2[0])

        # SEMANTIC stored-collision score (rg-1.1): near-synonym-aware. In
        # 'key' mode c_sem stays None -> opinion falls back to the frozen m_l2
        # margin (exact BEFORE reproduction).
        c_sem = sem_conflicts = sem_primary = None
        if self.collision_mode == "semantic":
            from l2_ambiguity import semantic_collision
            c_sem, sem_conflicts, sem_primary = semantic_collision(
                self.store, self.ent, self.rel, subj, rel)

        op = opinion_two_source(a, self.k, len(self.ent), m_ref=m_ref, m_l2=m_l2,
                                m_l1=m_l1, c_sem=c_sem, D=D, null_moments=self.nm,
                                hit_moments=self.hm)
        saturated = nz.is_saturated(self.k, len(self.ent), D,
                                    null_moments=self.nm, hit_moments=self.hm)
        action, tag = route_tagged(op, saturated=saturated, l2_available=True)

        record = provenance = candidates = None
        conflict, resolution_hint = False, None
        if tag == "referential":
            candidates = [n for n, _ in subj_res]
        elif tag == "stored":
            if self.collision_mode == "semantic" and sem_conflicts:
                # PASSIVE COLLISION: surface every disagreeing fact (primary +
                # all conflicts), one per distinct object; the server does NOT
                # pick one. resolution_hint is advisory only.
                recs, seen = [], set()
                pool = [(sem_primary[0], sem_primary[1])] + \
                       [(tr, pv) for tr, pv, _, _ in sem_conflicts]
                for tr, pv in pool:
                    if tr[2] in seen:
                        continue
                    seen.add(tr[2])
                    recs.append((tr, pv))
                candidates = recs
                conflict = len(recs) > 1
                resolution_hint = self._resolution_hint(recs) if conflict else None
            else:
                recs = []
                for obj_id in (o1[0], o2[0]):
                    for i, mrec in enumerate(self.store.meta):
                        if (self.store.active[i] and mrec and mrec["triple"][0] == subj
                                and mrec["triple"][1] == rel and mrec["triple"][2] == obj_id):
                            recs.append((mrec["triple"], mrec["provenance"]))
                            break
                candidates = recs
        if action.value == "answer":
            best_idx = self._triple_index.get((subj, rel, top1))
            if best_idx is not None:
                meta = self.store.meta[best_idx]
                record, provenance = meta["triple"], meta["provenance"]
            else:
                record, provenance = (subj, rel, top1), "user-stated"
        return QueryResult(action.value, tag, op, record=record,
                           provenance=provenance, candidates=candidates,
                           m_ref=m_ref, m_l2=m_l2, conflict=conflict,
                           resolution_hint=resolution_hint, c_sem=c_sem)

    def _resolution_hint(self, recs):
        """Advisory tie-breakers for a passive collision (caller may ignore):
        by_recency = latest-written record; by_resolution = record whose own
        (subject, relation) key resolves to its object most strongly."""
        scored = []
        for tr, pv in recs:
            idx = self._triple_index.get(tr, -1)
            a_i = self._unbind(tr[0], tr[1])[0]
            scored.append((tr, idx, a_i))
        return {"by_recency": max(scored, key=lambda x: x[1])[0],
                "by_resolution": max(scored, key=lambda x: x[2])[0]}


# ------------------------------------------------------------- extraction

EXTRACT_SYSTEM = """You extract explicit factual assertions from one utterance as triples.
Output ONLY lines of this exact form, nothing else:
(subject | relation | object)
Rules:
- Only facts the speaker directly and explicitly asserts. Questions,
  negations ("doesn't", "no longer"), past states ("used to"), hearsay
  ("I heard"), and uncertainty ("might", "maybe", "I think") give NONE.
- relation is a short lowercase verb phrase like: works at, lives in,
  was born in, manages, reports to, is married to, is a sibling of,
  studied at, is scheduled at.
- Use names exactly as spoken, with no additions. ONLY when the speaker
  identifies a person by role ("my brother Tom") write: Tom (brother).
- If there is no explicit factual assertion, output exactly: NONE
Examples:
"Sarah Kim manages Daniel Diaz." -> (Sarah Kim | manages | Daniel Diaz)
"My brother Tom works at Acme Labs." -> (Tom (brother) | works at | Acme Labs)
"Do you know where Anna lives?" -> NONE
"Maria Garcia lives in Lisbon and manages Sam Diaz." ->
(Maria Garcia | lives in | Lisbon)
(Maria Garcia | manages | Sam Diaz)
"Tom doesn't work at Acme Labs anymore." -> NONE
"Nina Vogel was born in Verona." -> (Nina Vogel | was born in | Verona)
"My cousin Anna lives in Boston." -> (Anna (cousin) | lives in | Boston)
"My colleague Dana works at Orion Foods." -> (Dana (colleague) | works at | Orion Foods)
"My landlord lives in Ashford." -> (my landlord | lives in | Ashford)
"Dana lives in Madrid now." -> (Dana | lives in | Madrid)
"I think Bob might work at Zenith." -> NONE
"My meeting is scheduled at 2pm." -> (my meeting | is scheduled at | 2pm)"""

_TRIPLE_RE = None


def extract_triples(utterance):
    """Mouth-parsed explicit-assertion extraction under the strict schema.
    Anything malformed or non-explicit is dropped (conservative by design).
    Returns [(subj, rel, obj), ...] — provenance is attached at write time."""
    global _TRIPLE_RE
    import re
    if _TRIPLE_RE is None:
        # fields may contain parentheses ("Tom (brother)", "Cambridge (UK)")
        _TRIPLE_RE = re.compile(r"^\(\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\)$")
    hedge = re.compile(r"\b(i think|i heard|might|maybe|used to|would|doesn't|"
                       r"don't|no longer|anymore|probably|wonder)\b", re.IGNORECASE)
    from llm import generate  # the mouth; lazy so the substrate core stays LLM-free
    # "Utterance:" prefix, not quote-wrapping: quoted sentence-initial names
    # trigger a copy glitch in SmolLM3 ("Eizabeth") — measured, entry 9
    raw = generate(EXTRACT_SYSTEM, f"Utterance: {utterance}", max_tokens=96, temperature=0.0)
    triples = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.upper() == "NONE":
            continue
        mt = _TRIPLE_RE.match(line)
        if not mt:  # malformed: dropped, conservative
            continue
        t = (mt.group(1), mt.group(2).lower(), mt.group(3))
        # post-guard: hedge/negation markers inside any field mean the model
        # tried to triple-ise a non-assertion — drop, conservative
        if any(hedge.search(x) for x in t):
            continue
        if t not in triples:
            triples.append(t)
    return [_bind_qualifier(t, utterance) for t in triples]


def _bind_qualifier(triple, utterance):
    """Deterministic qualifier binding: 'my <role> <Name>' in the utterance
    forces subject 'Name (role)'; bare 'my <role>' forces 'my <role>'. The
    model's own qualifier use is fickle at 3B — this must not depend on it."""
    import re
    s, r, o = triple
    for m in re.finditer(r"\b[Mm]y (\w+) ([A-Z]\w+)\b", utterance):
        role, name = m.group(1), m.group(2)
        if s in (name, f"{role} {name}", f"{name} ({role})".lower()):
            return (f"{name} ({role})", r, o)
    m = re.search(r"\b[Mm]y (\w+)\b", utterance)
    if m and s.lower() in (m.group(1).lower(),):
        return (f"my {m.group(1)}", r, o)
    return (s, r, o)
