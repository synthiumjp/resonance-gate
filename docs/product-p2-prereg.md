# product-p2 pre-registration: the write-side confidence gate

**Status:** registered before any p2 measurement is run. Committed to git prior
to Phase 0 so the timestamp is checkable.
**Branch:** `product-p2`, cut from `product-p1`. `rg-freeze-1.0` and `rg-1.1`
are untouched.
**Date registered:** 2026-07-20

---

## 0. The problem this addresses

The product's input is chat transcripts, notes and agent working memory — not
explicit "remember this fact" calls. Three independent findings say the
binding constraint is the WRITE side, not retrieval:

| finding | source | number |
|---|---|---|
| production memory store is mostly junk | mem0 issue #4573 (10,134 entries, manually reviewed) | **97.8% junk**; a stronger extraction model did not help |
| importance-based retention is near-floor | Kang et al., arXiv:2606.10616 | Generative-Agents-style scoring **F1 0.020–0.027**; best purpose-built method 0.263–0.401 |
| the field does not measure this at all | MemOps, arXiv:2607.12893 | benchmarks score "only the correctness of a final answer", conflating extraction, retention and retrieval error |

Meanwhile retrieval is close to solved (MemoryAgentBench retrieval-only
ceiling ≈100%) and contradiction resolution is at the floor (BEAM best
≈0.05; MemoryAgentBench multi-hop conflict ≤6% for Mem0/MemGPT/GraphRAG).

**Design response.** Move the substrate's calibrated refusal from the read
path to the write path, and tier the store so that low-confidence material is
retained but cannot make assertions.

---

## 1. What gets built

Three storage tiers:

- **SPAN** — the raw source text. Always retained, never gated, never
  discarded. It is the receipt.
- **PROVISIONAL** — an extracted triple. Retrievable. **May not fire a
  contradiction alert.**
- **PROMOTED** — a triple corroborated by an independent restatement.
  Alert-worthy. What the product asserts.

Four mechanisms, all reusing rg-1.1 parts:

1. **Write-time abstain** — the gate's ABSTAIN action applied at `write()`.
2. **Support check** — verify the triple is supported by its own source span,
   not merely resolvable in the registry.
3. **Cardinality accrual** — live `frac_multi(r)` (entry 26) decides
   update vs. multi-value.
4. **Provenance-gated alerts** — no contradiction surfaces without both
   source spans attached.

### Hard constraint on the runtime

**The shipped write-gate may not add a model call beyond the extraction step
that already exists.** Support checking must be embedding/lexical/self-
consistency based. An LLM judge appears in this plan ONLY as calibration
ground truth, never as a runtime component. If the gate cannot work without a
judge in the loop, we have built another LLM-in-the-loop system and the
LLM-free-retrieval claim dies with it — that is a kill condition, not a
tuning problem.

---

## 2. Claims, each with the result that would falsify it

Two constructs are kept **separate throughout** and must never be reported as
one number:

- **SUPPORT** — is the stored triple entailed by the span it came from?
  (What our gate targets.)
- **UTILITY** — is the retained set the gold evidence a later query needs?
  (What Kang et al. measure. Our gate is *not* query-conditional, so it is not
  designed to optimise this.)

Conflating them would be a construct-validity error and would invalidate any
comparison to the external numbers.

### C5 — CALIBRATION (tested first; everything depends on it)

*The write-gate's confidence ranks supported above unsupported triples.*

- **Metric:** AUROC of gate confidence separating judge-labelled supported
  from unsupported triples; plus Spearman ρ of support-rate across confidence
  bins.
- **Pre-committed threshold:** AUROC ≥ 0.70 **and** ρ ≥ 0.5.
- **Falsifier:** AUROC < 0.70. The 0.70 bar is set deliberately against
  E5.1, where this gate scored 0.738 overall but **0.516 — chance — among
  items it chose to answer**. A write-gate built on the same signal may be
  equally blind, and we would not see it from inside the system.
- **If falsified:** do not ship self-gating. Fall back to "retain spans,
  extract nothing automatically." This kills the p2 design, not just a
  parameter.

### C1 — SUPPORT PRECISION

*Gating raises the support precision of what gets stored.*

- **Metric:** judge-labelled support precision of the retained triple set,
  gated vs. ungated, at matched storage budget.
- **Pre-committed threshold:** ≥ +20 points precision over ungated, with
  relative recall loss ≤ 50%.
- **External anchor:** the ungated arm is our replication of the 97.8%-junk
  condition. If our ungated arm is *not* junk-heavy, the corpus is not in the
  regime and C1 is uninterpretable — **stop and report**, as in entry 24.
- **Falsifier:** precision gain < 20 points, or achieved only by discarding
  proportionally as much good material (i.e. no better than a random
  threshold at the same retention rate). A random-threshold arm at matched
  retention is mandatory.

### C2 — ALERT PRECISION (the product claim)

*Tiering + provenance reduces false contradiction alerts.*

- **Metric:** precision/recall **curve** (not a point) for contradiction
  alerts, on LongMemEval's 78 knowledge-update instances.
- **Arms:** alert-on-everything · alert-on-promoted-only · random threshold at
  matched alert rate.
- **Pre-committed threshold:** alert precision ≥ 0.70 at recall ≥ 0.30.
- **External anchor:** BEAM best contradiction-resolution ≈ 0.05;
  MemoryAgentBench ≤6%. Note these are *resolution* metrics on different
  data — quotable as context, **not** as a like-for-like baseline.
- **Falsifier:** promoted-only fails to beat the random-threshold arm.
- **If falsified:** contradiction alerting on auto-extracted triples is not
  viable; the product becomes span retrieval plus manually asserted facts.

### C3 — CARDINALITY DETERMINISM

*`frac_multi(r)` decides update vs. multi-value as well as an LLM judge, at
zero marginal runtime cost.*

- **Metric:** classification accuracy on real update/multi-value pairs.
- **Comparator:** an LLM judge run on the same pairs (Graphiti's `resolve_edge`
  prompt is the natural choice, since it is the shipped incumbent).
- **Pre-committed threshold:** within 5 points of the judge, or better.
- **Known risk, registered in advance:** entry 26 showed a relation-level
  statistic mislabels the majority case under heterogeneous cardinality
  ("mostly 1, 10% multi" scores fun=0.907, and frac_multi=0.10 is the
  correctly-shaped statistic but still a relation-level prior). C3 may fail
  for this reason. If it does, the fallback is per-subject observation with
  the relation-level value as a prior only for unseen keys.

### C4 — ACCRUAL

*The gate's decisions improve as memory grows.*

- **Metric:** C1 and C2 metrics at 25%, 50%, 100% of ingested memory.
- **Pre-committed threshold:** 100% > 25%, bootstrap CI on the difference
  excluding 0.
- **Falsifier:** flat. The "gets better with use" claim is then dead and must
  not be made in any product copy.

---

## 3. Phase order and stop rules

| phase | work | stop rule |
|---|---|---|
| **0** | Characterise the support judge (qwen3:14b) on a hand-labelled set of ≥100 triple/span pairs, including hedged, negated, hypothetical, future-tense and attributed cases | judge precision or recall < 0.85 → **STOP**. Everything downstream is noise. Precedent: E5.1's leak judge was characterised 60/60 before use |
| **1** | Ungated baseline: extract over LongMemEval's 10,960 turns, measure support precision and retention utility separately | ungated support precision already high → corpus not in regime → **STOP and report** |
| **2** | Build write-gate; test **C5**, then **C1** | C5 fails → **STOP**, design dead |
| **3** | Tiering + corroboration promotion; test **C2** | C2 fails → fall back to span-only product |
| **4** | Cardinality accrual; test **C3** | C3 fails → per-subject fallback |
| **5** | Accrual; test **C4** | — |
| **6** | Held-out confirmation on a second dataset (BEAM primary; MemoryAgentBench FactConsolidation secondary) | — |

**DEV/EVAL discipline** (precedent: entry 19). All thresholds and the gate's
parameters are tuned on a DEV split only. EVAL is scored **once**. Any tuning
after seeing EVAL is a deviation and gets logged as one.

---

## 4. Threats to validity, pre-answered

1. **Judge validity.** The whole plan rests on a model labelling "is this
   triple supported by this span". Mitigation: Phase 0 characterisation with a
   stop rule, on a set that deliberately includes the classes the E5.1 audit
   (A5) showed a weaker judge missed — negation, implication, temporal,
   attribution.
2. **Circularity.** Using the same embedding registry to both extract and
   support-check would let the gate approve its own errors. The support check
   must use a signal not already used in extraction; this is checked by
   measuring gate confidence against judge labels on *held-out* spans.
3. **Construct conflation.** SUPPORT ≠ UTILITY. Reported separately, always.
   Comparison to Kang et al. is on UTILITY only and carries the caveat that
   our gate is not query-conditional.
4. **Corpus realism.** LongMemEval conversations are partly synthetic.
   Findings may not transfer to genuinely messy human transcripts. Stated as a
   limitation; Phase 6 uses a second, independent dataset.
5. **Self-designed foils.** The comparator arms (ungated, random-threshold at
   matched rate) are mandatory precisely because this project has twice
   inflated results against foils of its own design (audit A1; entries 24,
   26). A result without the random-threshold arm is not reportable.
6. **Degenerate-task artefacts.** Entry 26 recorded an F1 of 1.000 at every
   threshold that was worthless because the task was separable by
   construction. Any perfect or near-perfect score in p2 must be interrogated
   for the same defect before it is believed.

---

## 5. What we will not claim

- Not that superposition improves retrieval. The VSA literature never claims
  it (accuracy is what VSA spends, not what it gains), and E5.1 found
  membership + top-1 cosine fully accounts for this gate's advantage.
- Not that contradiction detection is novel. NLI contradiction detection,
  SHACL/OWL cardinality checks and truth discovery are decades deep. The
  narrow claim available is **disclosure over resolution** — surfacing both
  facts rather than silently picking — which Zep and mem0 both decline to do,
  and which a user has explicitly requested (graphiti issue #934).
- Not that the system is LLM-free. Retrieval is. Extraction is not, and the
  product copy must say so.
- Not "gets better with use" unless C4 passes.

---

## 6. Deliverable

A `product-p2` branch in which `write()` returns a tier and a confidence,
provisional facts cannot fire alerts, spans are retained and returned with
every conflict — and a notebook entry per phase carrying the numbers, the
comparator arms, and any stop rule that fired.
