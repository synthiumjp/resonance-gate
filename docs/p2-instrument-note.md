# product-p2 instrument note: characterising the SUPPORT judge

**Status:** written and committed BEFORE any triple/span pair is generated or
inspected. This is instrument validation, not hypothesis testing — it precedes
the claims pre-registration deliberately, because (a) if the judge fails there
is no study to register, and (b) the judge's measured reliability caps what any
downstream threshold can credibly assert.
**Date:** 2026-07-20
**Branch:** `product-p2`

---

## 1. What the instrument is for

Every product-p2 claim rests on being able to answer one question at scale:

> Given an extracted triple T = (subject, relation, object) and the source span
> S it was derived from — **is T supported by S?**

The judge is the ground-truth labeller for that question during calibration.
It is **not** a runtime component and must never become one; the shipped
write-gate may add no model call beyond the extraction step that already
exists (see the claims prereg). If the gate cannot work without a judge in the
loop, the design has failed, not been extended.

## 2. The judge, pinned

- model: `qwen3:14b`, ollama digest `bdbd181c33f2ed1b31c972991882db3c`
- blob: `sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e`
- 14.8B, Q4_K_M
- Precedent: E5.1 pinned its leak judge by tag + blob sha and characterised it
  on a labelled set before use (60/60). Same discipline here.

### NO JUDGE SHOPPING — pre-committed

`qwen3:14b` is the judge. If it fails the stop rule below, we report the
failure and either fix the **protocol** (rubric ambiguity, prompt) or abandon
the approach. **We do not try further models until one passes.** Trying
candidate judges until one clears the bar is the one serious forking path in
this step, and it is closed here in advance. Any change of judge after seeing
characterisation results is a deviation and gets logged as one, with the
original result reported alongside.

## 3. The rubric — written before seeing any pair

**Label `SUPPORTED`** iff the span **directly and explicitly asserts** the
triple as a *currently held fact*, in the voice of the speaker whose fact it
is.

**Label `NOT_SUPPORTED`** if any of the following applies. These classes are
listed explicitly because the E5.1 audit (A5) showed a weaker judge silently
missing several of them:

| class | example span | wrongly extracted triple |
|---|---|---|
| hedged | "I think Bob might work at Zenith" | (Bob \| works at \| Zenith) |
| hypothetical / conditional | "if I moved to Boston I'd need a car" | (user \| lives in \| Boston) |
| future / intentional | "I'm thinking of moving to Boston" | (user \| lives in \| Boston) |
| negated | "I don't work at Acme any more" | (user \| works at \| Acme) |
| superseded within the span | "I used to live in Lisbon, now Madrid" | (user \| lives in \| Lisbon) |
| attributed to another | "my friend says I should join Acme" | (user \| works at \| Acme) |
| interrogative | "do you know where Anna lives?" | (Anna \| lives in \| …) |
| assistant-sourced | assistant offers a general fact | any triple about the user |
| inferred, not stated | "I commute to the Dublin office daily" | (user \| lives in \| Dublin) |
| altered argument | span says "Tom Fischer" | (Tom Fisher \| … \| …) |
| over-specific object | span says "moved north" | (user \| lives in \| Boston) |

**Judgement calls, fixed now:**

- A **paraphrased relation** is SUPPORTED if meaning is preserved
  ("works at" for "I'm employed at"). Relation wording is not required to match.
- **Subject identity must hold.** A swapped or merged entity is NOT_SUPPORTED
  even if the rest is right.
- **Tense:** a fact asserted as true at the time of the span counts as
  SUPPORTED even if later superseded elsewhere in the conversation. Supersession
  across spans is a different measurement (C3), not a support failure.
- Third label **`UNCLEAR`** is permitted. UNCLEAR items are excluded from
  precision/recall. **If UNCLEAR exceeds 15% of the set, the rubric is
  defective** — fix the rubric and relabel, and log that this happened.

## 4. The labelled set

- **n ≥ 120** triple/span pairs.
- **Source A (realistic distribution):** pairs produced by running the actual
  pinned extractor (SmolLM3-3B Q4_K_M, `mouth/llm.py`) over real user turns
  sampled from LongMemEval oracle. These carry the extractor's true error
  profile.
- **Source B (guaranteed hard-class coverage):** targeted pairs constructed to
  cover every row of the table in §3, because those classes may be too rare in
  Source A to measure. Source B items are marked and reported separately —
  precision/recall are reported for A, B, and A∪B.
- **Class balance:** the set must contain at least 30 SUPPORTED and 30
  NOT_SUPPORTED after labelling, or neither precision nor recall is estimable.
  If Source A alone does not reach that, Source B fills the gap.

### Labelling procedure

Labelling is done by JP (registrant-accepted, logged as such — this is a
single-rater instrument and that is a stated limitation, not a hidden one).

- **Blind:** the labeller does not see whether a pair came from Source A or B,
  nor which extraction condition produced it.
- **Order randomised** under a logged seed.
- Labels are committed **before** the judge is run on the set.

## 5. Stop rule

Judge is scored against the human labels on the SUPPORTED class:

> **precision ≥ 0.85 AND recall ≥ 0.85** — both, on A∪B.

- **If met:** proceed to write the claims pre-registration, with downstream
  thresholds set relative to this measured ceiling rather than to statistical
  convention.
- **If not met: STOP.** No p2 claims are registered and no gate is built on
  this instrument. Report the failure, then either repair the protocol or
  abandon the approach. Do not shop for a judge.

Additionally reported, not gated on: per-class recall over the §3 table (which
hard classes the judge misses), and the UNCLEAR rate.

## 6. Why this bounds the claims that follow

The judge is the measuring device for support precision. A claim of "support
precision ≥ 0.90" is not credible if the instrument itself is only 0.90
precise — the assertion would sit inside the device's own noise. Therefore:

- Absolute operating points in the claims prereg will be set **with margin
  below the judge's measured reliability**, and reported **with the
  instrument's error attached**, never as bare point estimates.
- **Primary claims will be stated as contrasts** (gated vs. random-threshold at
  matched retention), because every comparator arm is scored by the same
  instrument and systematic judge bias partly cancels in a contrast while it
  does not cancel in an absolute number.

## 7. Known limitations, stated now

1. **Single rater.** No inter-rater reliability is available. Accepted by the
   registrant; recorded here rather than omitted. The labelled set is published
   with the results so a second rater can be added later.
2. **Rater is not independent of the pipeline.** The same person wrote the
   extraction prompt and the rubric. Mitigated by blind, randomised labelling
   and by fixing the rubric in advance, not eliminated.
3. **Corpus.** LongMemEval conversations are partly synthetic; the extractor's
   error profile on genuinely messy human transcripts may differ.
