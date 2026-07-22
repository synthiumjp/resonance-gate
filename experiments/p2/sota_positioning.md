# SOTA positioning — non-hallucinating memory (2026-07-22)

Research sweep: 5 search angles → 23 sources → 115 extracted claims → top 25
distilled. The 3 decision-critical claims below were directly verified against
primary sources; the rest are single-sourced (marked). Verification-panel run
was rate-limited; claims here are labeled by evidence status.

## 1. Landscape verdict (the gap is real)

**No shipped system or published framework offers structural non-hallucination,
corroboration-gated assertion, or memory-layer abstention.** Closest neighbours:

- **Zep/Graphiti** (arXiv:2501.13956 + vendor docs): temporal knowledge graph,
  bi-temporal fact validity, contradiction handling by invalidation. Claims
  per-fact links back to source episodes — the nearest thing to receipts —
  but the paper leaves that capability unevaluated, extraction is generative
  LLM, and its anti-hallucination story is temporal consistency, not
  corroboration or abstention. [vendor-claimed / single-sourced]
- **MemGuard** (arXiv:2605.28009, May 2026): type-aware memory (semantic/
  episodic/procedural roles at write time; type-restricted retrieval) to stop
  "heterogeneous memory contamination". VERIFIED: statistical mitigation
  ("up to 28.27%" reliability gain, 5.8x fewer memory tokens); no structural
  guarantee, no provenance, no abstention. Its LoCoMo error analysis
  [single-sourced] attributes 97.7% of unverifiability errors to WRITE-TIME
  contamination — independent support for our thesis that the memory layer,
  not generation, is where hallucination enters.
- **HippoRAG et al.** (neuro-inspired retrieval): hippocampal-index framing and
  PPR-style graph retrieval exist, so "spreading activation" alone is not
  novel — but all use generative extraction, none receipted/gated. The
  Hebbian-counted-edges + VSA-proposer-gated-by-receipts combination is
  unclaimed. [search-phase, not deep-verified]
- **Abstention literature** (TACL "Know Your Limits" survey): verbalized LLM
  confidence is systematically overconfident and uncalibrated; abstention is
  framed as MODEL behavior. Memory-layer, structural (non-calibration-
  dependent) abstention is essentially absent from the surveyed literature.
  [single-sourced; independently replicated by our own entry-53/54 result]
- **Agent-hallucination taxonomy** (arXiv:2509.18970) names "Memorization
  Hallucinations" — agents trusting stored memory without validation — as a
  first-class failure type. The gap is named in the literature; nothing fills
  it. [single-sourced]

## 2. The benchmark to win: HaluMem (VERIFIED)

HaluMem (arXiv:2511.03506, MemTensor) is the first OPERATION-LEVEL memory-
hallucination benchmark: scores memory extraction, memory updating, and memory
QA separately; ~15k memory points, ~3.5k questions, 1M+ token dialogues.
Its core finding = our architecture's premise: **hallucinations originate in
extraction/updating and propagate to QA.**

Verified current numbers (HaluMem-Medium), shipped systems:

| System      | QA acc | Hallucination | FMR (higher=better) |
|-------------|--------|---------------|---------------------|
| MemOS       | 67.23% | 15.17%        | 44.94%              |
| Zep         | 55.47% | 21.92%        | n/a                 |
| Mem0-Graph  | 54.66% | 19.28%        | 55.70%              |
| Supermemory | 54.07% | 22.24%        | 51.77%              |
| Mem0        | 53.02% | 19.17%        | 56.80%              |
| Memobase    | 35.33% | 29.97%        | 80.78%              |

MemGuard reports 89.53% anti-hallucination accuracy on HaluMem
[single-sourced] — the number to beat on the mitigation axis.

## 2b. MEASURED (2026-07-23, entries 82–87): our row

Full HaluMem-Medium run (all 20 users, n=3,189 unique questions), two
independent LOCAL judges (qwen3:14b strict, gemma3:12b lenient), both-judge
protocol:

| System        | QA correct     | Hallucination        | Memory Boundary |
|---------------|----------------|----------------------|-----------------|
| **rg-p2**     | 57.7–83.3%*    | **0.0% (0/3,189)**   | 548–550/550     |
| MemOS (best)  | 67.23%         | 15.17%               | —               |
| Zep           | 55.47%         | 21.92%               | —               |
| Mem0          | 53.02%         | 19.17%               | —               |

*correct spread = judge strictness (both-confirmed floor 57.7%; strict qwen
63.5%; lenient gemma 83.3%); hallucination is both-judge-confirmed, single-
judge worst case 1/3,189 (0.03%). CAVEAT: in-house judges, not the official
HaluMem harness — treat cross-row comparison as approximate until the
official eval runs. Weakest true axis: Dynamic Update (68/180 strict).

## 3. What a SOTA claim looks like for us

The winnable frontier is the **trust Pareto**: hallucination ≈ 0 and FMR ≈ max
at competitive (not leading) QA accuracy, with metrics nobody else can report:

1. **Fabrication rate ~0 by construction** at the memory layer: QA answers are
   non-generative and receipted; extraction noise is absorbed by corroboration
   (our measured mechanism) instead of stored as fact. Beat: 15.17%
   (best shipped) / 89.53% anti-hallucination (MemGuard).
2. **False Memory Resistance near-ceiling**: distractor facts don't corroborate,
   so they never assert. Beat: 80.78% (Memobase best; leaders sit ~45–57%).
3. **Novel reportable metrics**: receipted-fact coverage (100%), fabricated-link
   rate under exhaustive audit (0), crosstalk-block rate (measured), abstention
   correctness on no-evidence queries (measured 0 fabricated assertions).
4. **The honest weak axis: omission.** Corroboration gating raises omission rate
   (single mentions are provisional, not asserted). The claim is the Pareto
   point, not dominance: near-zero fabrication at X% omission — and HaluMem
   scores hallucination and omission SEPARATELY, which is exactly the framing
   our trade-off needs. The provisional tier (labeled single-mention recall)
   should recover part of the omission axis.

Also run for comparability: LongMemEval (already in our harness: 11/39 @ 0
false alarms held through every gate) and LoCoMo.

## 4. Concrete next steps

1. Build a HaluMem adapter (their harness expects a memory system with
   extract/update/answer operations — our Memory + belief pipeline maps 1:1,
   including the update path via change-point decay).
2. Report the standard triple (accuracy/hallucination/omission) + our audit
   metrics; publish the fabrication-rate-by-construction argument with the
   measured crosstalk/abstention numbers.
3. Positioning sentence: existing systems reduce memory hallucination
   statistically (best: 15.17% shipped, 89.53% mitigated); this system removes
   the mechanism that produces it, and proves it per-operation with receipts.
