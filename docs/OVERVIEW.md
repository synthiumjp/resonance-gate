# RG: a receipted, local-first memory layer

**RG** (working name; the MCP server ships as `sourcedrecall`) is a memory
layer for LLM agents. It stores only facts that carry a source receipt,
estimates whether the retrieved evidence is sufficient to answer, and leaves
composition to the client's own language model. It is evaluated on the
HaluMem benchmark, runs on consumer hardware, and makes no paid API calls.

## Why it exists

Most memory systems optimise for remembering and retrieving more. RG
optimises for a different question:

> **What does the system have enough evidence to say?**

Every stored fact keeps its provenance. Repeated evidence raises a fact's
status, conflicting evidence triggers a clarifying question, and insufficient
evidence produces abstention rather than an unsupported answer.

---

## Pipeline

### 1. Offline fact extraction

A small local model converts each user turn into typed facts —
`subject / attribute / value` — under the v5.1 narrative prompt, which keeps
explanatory context inside the value ("solitude for recharging" rather than
"solitude").

The no-GPU configuration is qwen3:1.7b on CPU: ~1.4 GB, ~3.3 s/turn, cached
by a hash of the source turn. Extraction is entirely off the answer path, so
a turn is processed once and adds no latency at query time.

### 2. Gated write policy

Three controls run before a candidate fact enters memory.

**Restatement clustering.** Token-overlap clustering merges re-wordings of
the same fact into one node carrying multiple receipts. This is why the store
grows with what is *new* rather than with what was *said*: on a real 686-
conversation profile it holds 1,103 facts, and a semantic dedup pass on top
removes only a further 1%.

**Correction-derived rules.** When the owner corrects an extraction error,
RG converts the correction into a reusable rule — blocking that error class
at ingest and repairing facts filed under the wrong attribute. On the real
profile, 17 corrections induced 17 rules; replaying the extraction cache
produced 18 interventions, all 18 verified correct by manual audit. The
sample is small: treat this as an initial precision estimate, not a
guarantee.

**Quarantine.** Blocked writes are retained with the rule that blocked them
and are reviewable over MCP. A rule can age badly — an owner who denies a job
title today may hold it next year — so no write is silently destroyed.

### 3. Receipted store

Pure Python over append-friendly JSONL; no database. Every fact records its
source conversation, source date, number of independent mentions, confidence
tier, and spacing metadata. Facts occupy one of three tiers:

- **Provisional** — one observation
- **Asserted** — corroborated
- **Gist** — an abstraction citing at least two dated episodes. *Measured
  and archived: adding gist lines to retrieval context lowered correct
  answers on the class it targeted (33.9% → 29.5%), so the tier is not wired
  into the answer path. The code remains for product use.*

Spacing metadata distinguishes evidence repeated inside one sitting from
evidence consolidated across months. It is reported as evidence metadata, not
as a truth claim: on the owner's own corrections, denied facts skewed
*spaced*, because systematic extraction errors recur whenever their topic
does.

### 4. Two-tier retrieval

**Default tier.** Pure-Python BM25 with light stemming and focus weighting
(persona names and date scaffolding are down-weighted). No model inference;
single-digit milliseconds.

**Accuracy tier (opt-in).** Adds bge-small dense retrieval and a MiniLM
cross-encoder rerank: ~150 MB of weights, ~0.5 s per query.

Measured on dev, with a shuffled-gold null reported alongside because
containment metrics over a large store inflate easily:

| Metric | Default tier | Accuracy tier | Null (chance) |
|---|---|---|---|
| Union recall over the retrieved block | 83.2% | 86.8% | ~35% |
| Single-line recall (one line holds the gold) | 46.8% | 49.9% | — |
| Gold in top-5 lines | 20.7% | 28.7% | — |

Union recall is well above its null, so the signal is real, but single-line
recall is the stricter and more honest companion figure.

Retrieved evidence is emitted in auditable form:

```
[confirmed xN, DATE] attribute: value
```

### 5. Grounded composition

The client's own LLM composes, under a grounding contract: prefer
corroborated evidence, account for recency, abstain when the answer is
absent, and apply an explicit as-of rule to date-anchored questions. RG ships
no composer.

### 6. Evidence sufficiency and the trust dial

A local 4B sidecar plus a ~10 KB logistic probe scores whether the retrieved
evidence supports an answer. A calibrated percentile threshold decides which
answer attempts proceed. **The dial filters attempted answers on that score;
it does not ask the composer to sound more cautious.**

---

## Results

Percentages are of questions judged: n=476 (development, held-out users
10–12), n=1,764 (official, users 0–9).

### The operating frontier (the distinguishing result)

RG's gate makes hallucination a **tunable parameter** rather than a fixed
property. Measured on the development set (n=476), sweeping one threshold:

| Gate | Questions answered | Correct | Hallucination | Precision of answered |
|---|---|---|---|---|
| off | 63.7% | 50.8% | 17.6% | 43.2% |
| p10 | 54.6% | 50.0% | 13.0% | 48.8% |
| p20 | 46.2% | 47.7% | 11.1% | 52.7% |
| p30 | 38.2% | 46.2% | 8.6% | 59.9% |
| p60 | 15.8% | 34.7% | 3.6% | 70.7% |

Abstaining on an answerable question is scored as an omission, not a
success. Callers choose the point: a casual assistant runs the gate off; a
clinical or legal deployment runs it tight and accepts lower coverage for
8.6% or 3.6% hallucination.

### Official submission (frozen configuration, round 5)

| Metric | Value |
|---|---|
| Correct | 55.0% |
| Hallucination | 18.7% |
| Omission | 26.4% |
| Invalid verdicts | 0 |
| Memory Boundary abstention | 97.4% |

n=1,764. Reproducible from committed code. Round 4 (BM25-only retrieval) was
52.6 / 19.1 / 28.3.

**Extraction.** The memory-extraction column is 0.340 (round 4/5 reported
0.282). The gain came entirely from reporting stored facts as
natural-language propositions rather than `attribute: value` slot notation —
the form the benchmark's gold memory points use. Verified by a paired
stage-2 rerun on identical memory points: integrity 0.625 → 0.817. Nothing
was extracted differently, and the QA artifacts were byte-identical across
the two runs (97.5% verdict agreement; the residual 2.5% is judge
nondeterminism, which also sets the noise floor for every judged comparison
here).

**Reliability.** The improvement was tested paired rather than in aggregate,
on the 1,628 questions both rounds judged: correctness gained 136 items and
lost 93 (net +43, McNemar p=0.005, reliable); hallucination changed by 8 net
items (p=0.65, not reliable). Retrieval v3 therefore improves correctness
without a measurable change in hallucination. Largest per-class gain:
Dynamic Update 18.4% → 25.2%.

### Comparator context — not a controlled ranking

Published HaluMem figures use **GPT-4o as both composer and judge**. RG's
numbers use a local qwen3:14b for both. The composer is roughly 7× smaller
and the judge is stricter and noisier, so these rows are not directly
comparable; they are context.

| System | Correct | Hallucination | Tunable risk? |
|---|---|---|---|
| MOSAIC | 73.1% | 10.2% | no |
| MemOS | 67.2% | 15.2% | no |
| Zep | 55.5% | 21.9% | no |
| mem0 | 53.0% | 19.2% | no |
| RG (gate off) | 55.0% | 18.7% | — |
| RG (gate p30) | 46.2%* | 8.6%* | yes |

\* development set. Each published system reports a single operating point
because none exposes a calibrated confidence signal; there is no threshold to
move. RG trades coverage for risk along a measured curve, and at p30 its
hallucination rate is below every published figure.

## Distinctive mechanisms

Receipts on every fact · provisional/asserted/gist tiers · correction-derived
write rules · quarantine instead of deletion · abstention as a first-class
outcome · evidence-sufficiency gating (the trust dial) · clarification on
conflict · receipted consolidation · crosstalk auditing.

Two of these produce numbers no comparator reports:

**Clarification on conflict.** On the owner's real profile RG holds 23
unresolved slot conflicts and surfaces them as questions ("I have three
values for your employer — which is current?") rather than silently picking.

**Crosstalk audit.** Measured at the retrieval-candidate boundary: RG's
hyperdimensional substrate proposed 615 node-to-node associations (top-8 per
node); 317 (51.5%) lacked a receipted edge and were blocked; zero
unreceipted associations entered the verified set. Nothing is claimed about
composer output. Caveat: this substrate uses random codebooks, so its
crosstalk is noise-floor. A semantic vector store's crosstalk would be
*plausible* — harder to catch, not easier.

---

## What the experiments suggest

**Instruction-side changes moved along the trade-off, not past it.** Six
interventions — completeness rules, strict-absence rules, currency marking,
premise correction, answer-format rules, and a validator-retry loop — each
converted omissions into hallucinations at roughly 1:1. In this pipeline,
instructing the composer to be more forthcoming did not improve the frontier.

**Two interventions moved it.** Changing what the composer reads (retrieval
v3) and filtering which attempts survive (the sufficiency probe). The
retrieval change is confirmed on the official split by a paired test
(p=0.005) and, notably, improves correctness *without* a reliable change in
hallucination — unlike every instruction-side lever, each of which traded one
for the other.

A methodological note worth recording: the same retrieval effect was **not**
statistically reliable on the 476-question development set (p=0.19, inside
substantial item-level churn). The development screen was underpowered rather
than wrong. Aggregate deltas below roughly 5 points are not distinguishable
from churn at that sample size, so single-shot development screens should be
read as directional only.

The confidence signal behind the trust dial has been screened with a portable
validity protocol (arXiv:2604.17714) and classifies as **Valid** at both the
median split and the operating threshold (RBS −0.51 and −0.31, both CIs
excluding zero), which is the precondition for interpreting any
selective-prediction system built on it.

**Model scale did not predict performance here.** A 235B composer scored
worse than the 14B (47.9 vs 51.1 correct) and a 32B extractor stored less
gold than the 14B (50.7% vs 55.6% gold-in-store). This does not show scale is
generally ineffective; it shows that in this pipeline, calibration was
model-specific and did not transfer.

---

## Status

- **Official round 5** — the frozen configuration (retrieval v3 + focus
  weighting + as-of rule) running against the official harness. Round 4
  remains the headline until round 5 completes under official conditions.
- **Gist tier** — evaluated and archived. It cost ~10% context growth and
  did not earn it: correct answers on the Generalization class fell from
  33.9% to 29.5%, with hallucination flat and omission up. Abstraction
  competed with evidence for the composer's attention rather than orienting
  it.

---

## Related work referenced

mem0's own issue #4573 reports 224 of 10,134 memories surviving audit after a
32-day production run — an independent, first-party account of what an
ungated write path accumulates. RG's write gate is the direct response.
Consolidation design follows Spens & Burgess (*Nature Human Behaviour*, 2024),
Helfer & Shultz on reconsolidation, and Maguire (2014); the prediction-error
framing and the distortion risks it warns about are why every abstraction in
RG cites its episodes.
