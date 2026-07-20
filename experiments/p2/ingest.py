"""p2 ingest path: raw text in, tiered facts out.

This is the gate wired to the substrate. It is the write path the product
actually needs, as opposed to the explicit-fact `Memory.write()` the research
artifact was built around.

    text span ──> extract ──> gate ──> SPAN store        (always, verbatim)
                                  └──> triple store      (well-formed+grounded)
                                            │
                                            ├─ PROVISIONAL  retrievable, may NOT assert
                                            └─ PROMOTED     corroborated, assertable

DESIGN COMMITMENTS, each traceable to a measured finding:

- THE SPAN IS ALWAYS KEPT. Gate precision on held-out data is 0.636 (entry 29),
  so the gate is wrong often enough that discarding on its say-so would lose
  real facts. Keeping the span makes every gate error recoverable and makes low
  recall cheap.
- MODALITY IS RECORDED, NOT FILTERED. An intention is stored as an intention.
  It stays retrievable ("you mentioned considering Boston") and can never
  collide with a residence fact, which is how "thinking of moving to Boston"
  manufactures a false contradiction in systems that store it as a fact.
- PROMOTION IS BY CORROBORATION, NOT BY AN IMPORTANCE SCORE. Kang et al.
  (arXiv:2606.10616) measure Generative-Agents-style importance scoring at
  F1 0.020-0.027 against gold evidence. Independent restatement is a cheaper
  and better-founded signal, and it is O(1) to maintain.
- CORROBORATION MUST BE INDEPENDENT. A restatement only counts if it comes
  from a different session (or, failing that, a different span). Re-extracting
  the same sentence twice is not evidence. This is the specific mechanism
  behind mem0's 808-copy amplification of a single hallucination (issue #4573):
  recalled memories were re-extracted and re-stored with no notion of
  independence.
- NO EXTRA MODEL CALL. Extraction already costs one; the gate, the tiering and
  the corroboration index add none.

Status: exploratory (entry 29 mode change). Nothing here is pre-registered.
"""

import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field

_HERE = os.path.dirname(os.path.abspath(__file__))
_R = os.path.dirname(os.path.dirname(_HERE))
for _p in (_HERE, _R, f"{_R}/substrate", f"{_R}/gate", f"{_R}/encoder", f"{_R}/mouth"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from gate import assess, SPAN, PROVISIONAL, PROMOTED


def normalise_arg(x):
    """Canonical form for corroboration matching. Deliberately conservative --
    case, articles and first-person surface variants only. Entity resolution
    proper ("Tom" vs "Tom Fischer") is a known open problem (E5.1 f_confusable)
    and is NOT attempted here; conflating those would create false
    corroboration, which is worse than missing it."""
    s = str(x).strip().lower()
    s = re.sub(r"^(the|a|an|my|our)\s+", "", s)
    if re.match(r"^i(\s|'|$)", s) or s in ("me", "myself"):
        return "@speaker"
    return re.sub(r"\s+", " ", s).strip(" .,!?")


def fact_key(triple):
    return (normalise_arg(triple[0]), normalise_arg(triple[1]),
            normalise_arg(triple[2]))


@dataclass
class Record:
    triple: tuple
    span_id: str
    session_id: object
    modality: str
    tier: str
    provenance: str
    corroborations: int = 0
    why: str = ""


@dataclass
class Ingestor:
    """Holds the span store, the triple store and the corroboration index.

    `extractor` is injected so this can be exercised without loading a 1.8GB
    model — pass the real `write_path.extract_triples` in production.
    """
    extractor: object = None
    spans: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    _by_key: dict = field(default_factory=lambda: defaultdict(list))
    _n_span: int = 0

    def _extract(self, text):
        if self.extractor is not None:
            return self.extractor(text)
        from write_path import extract_triples
        return extract_triples(text)

    def ingest(self, text, session_id=None, provenance="user-stated",
               span_id=None):
        """One span in. Returns the records created from it."""
        if span_id is None:
            span_id = f"s{self._n_span:06d}"
            self._n_span += 1
        self.spans[span_id] = {"text": text, "session_id": session_id,
                               "provenance": provenance}

        out = []
        for tr in self._extract(text):
            tr = tuple(tr)
            a = assess(text, tr)
            if a["tier"] == SPAN:
                continue                       # kept as span only, not as a triple
            key = fact_key(tr)
            prior = self._by_key[key]
            # independence: a restatement counts only from a different session,
            # or a different span when sessions are not distinguished
            n_indep = len({(r.session_id if r.session_id is not None else r.span_id)
                           for r in prior
                           if (r.session_id != session_id
                               if (r.session_id is not None and session_id is not None)
                               else r.span_id != span_id)})
            a2 = assess(text, tr, corroborations=n_indep)
            rec = Record(triple=tr, span_id=span_id, session_id=session_id,
                         modality=a2["modality"], tier=a2["tier"],
                         provenance=provenance, corroborations=n_indep,
                         why=a2.get("why", ""))
            self.records.append(rec)
            self._by_key[key].append(rec)
            # a new independent restatement can promote the earlier copies too
            if rec.modality == "ACTUAL" and n_indep >= 1:
                for r in prior:
                    if r.modality == "ACTUAL":
                        r.tier = PROMOTED
                        r.corroborations = max(r.corroborations, n_indep)
            out.append(rec)
        return out

    # ------------------------------------------------------------- read side

    def facts(self, tier=PROMOTED, modality="ACTUAL"):
        """What the system is willing to assert. PROMOTED+ACTUAL by default."""
        seen, out = set(), []
        for r in self.records:
            if r.tier != tier or (modality and r.modality != modality):
                continue
            k = fact_key(r.triple)
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        return out

    def receipt(self, rec):
        """The span a fact came from — what gets shown with any assertion or
        contradiction alert. Never assert without one."""
        s = self.spans[rec.span_id]
        return {"span_id": rec.span_id, "session_id": s["session_id"],
                "text": s["text"], "provenance": s["provenance"]}

    def stats(self):
        c = defaultdict(int)
        for r in self.records:
            c[f"{r.tier}/{r.modality}"] += 1
        return {"spans": len(self.spans), "records": len(self.records),
                "distinct_facts": len(self._by_key),
                "promoted": sum(1 for r in self.records if r.tier == PROMOTED),
                "by_tier_modality": dict(c)}
