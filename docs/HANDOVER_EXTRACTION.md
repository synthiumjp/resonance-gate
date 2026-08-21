# Handover — deterministic extraction (rgx), 2026-08-21

Read this, then `docs/EXPERIMENT_LEDGER.md` §1 (established), §5a–5l (laws and
corrections), §6 (open items). Notebook entries 217–232 are this arc.

---

## 1. What was built

**A deterministic memory extractor that beats a prompted 14B on the official
HaluMem judge, with zero model calls at extraction time.**

Shipped as a package: `rgx/` — `Extractor(owner_name=...).extract(dialogue)` →
`Record(text, kind, session, turn, role, quality)`. Core is `rgx/parse.py`
(UD/Stanza clause walker) and `rgx/check.py` (deterministic filters + quality
score). `experiments/p2/grammar_ud.py` and `grammar_check.py` are SHIMS onto
the package — the benchmark harness and the shipped package are the same code
on purpose, so the ledger's numbers describe what users get.

The transformation is a **person shift**: first person → third, verb agreement,
pronoun shift inside the span, plus a small lexicon mapping surface expressions
to gold's slot names. Morphology and dependency structure, not semantics.

---

## 2. Numbers — what is measured, and what is NOT

Judged by HaluMem's own `evaluation.py` harness, held-out user 0, 575–576 gold
points, prompted arm reused across runs.

| arm | precision | recall | F1 |
|---|---|---|---|
| prompted 14B (shipped extractor) | 0.6684 (n=98) | 0.2122 | 0.3231 |
| spaCy parser (pre-port) | 0.9301 **(biased)** | 0.4311 | 0.5891 **(withdrawn)** |
| **UD/Stanza parser (current)** | **UNMEASURED** | **0.4609** | **OPEN** |

- **Recall is solid and is the headline**: +24.87pt over the prompted 14B,
  discordant 40/183, **McNemar exact p = 4.8e-23**. Recall judges all gold
  points, so it is untouched by the sampling defect below.
- **No F1 should be quoted.** `--limit-accuracy` used to take the FIRST N
  records; those are early sessions (the templated persona intro, where
  everything is easier). That inflated BOTH arms — prompted read 0.7759 biased
  vs 0.6684 corrected. Fixed to a seeded random sample in
  `lora_judge_ab.py`. The UD arm's corrected precision **never finished**.
- **Everything rests on ONE user.**

### Published comparison (do NOT quote yet)
HaluMem-Medium extraction F1: Memobase 25.13 · Supermemory 56.90 · Mem0 57.31 ·
Mem0-Graph 57.85 · MemOS 79.70 · MOSAIC 86.77. Our judge is local and e176
measured a frontier judge scoring us ~9.67pt WORSE — that cancels in our own
paired comparisons but **not** against someone else's published table.

---

## 3. Immediate next steps, in order

1. **Finish user 0 precision.** Server may still be up on :8090.
   ```
   cd ~/rg_private/halumem/official/HaluMem/eval
   RG_EXTRACT_V5=1 RG_PREFIX_NO_THINK=1 PYTHONUNBUFFERED=1 \
     ~/rg_private/halumem/official/.venv/bin/python \
     /home/jp/rg/experiments/p2/lora_judge_ab.py \
     --user 0 --label grammar --limit-integrity 4 --limit-accuracy 300 \
     --lora-artifact ~/rg_private/halumem/lora/artifact_u0_ud.json
   ```
   Then F1 = harmonic(P, 0.4609). ~50 min; progress prints every 100 calls and
   a 15-minute silence is normal, not a stall (check `server_*.log` mtime).

2. **Judge user 1.** Artifact already built:
   `~/rg_private/halumem/lora/artifact_u1_ud.json` (3242 turns → 5497 props).
   Same command with `--user 1`, no `--reuse` (no saved prompted verdicts for
   u1). This is the weakest claim in the whole result — one user.

3. **Re-baseline the ledger** once both land. §1 and entries 227/228/231 all
   carry head-sampled precision; correct them in place, do not just supersede.

---

## 4. Standing rules earned this session — do not relearn these

- **Diagnose, never theorise.** Every gain came from reading judged misses and
  raw output. Every loss came from reasoning forward from a theory about the
  judge: preference templates (−1.2pt) and pruning (−12.2pt) were both wrong
  within the hour.
- **The token-overlap proxy is BARRED** for extraction comparisons. It
  over-read the LoRA by 5.4pt, under-read the parser by 3.5pt, scored garbage
  relation strings ABOVE correct ones, and said +2.9pt where the judge said
  −0.17pt. Judge, or do not believe it. `--reuse` makes that affordable — a
  fixed baseline is never re-scored.
- **Read what is on each side of a comparison.** e211 subtracted a judge
  penalty from one arm only; e218 compared a component against the whole
  store. Both times the metric was fine and the ARMS were wrong.
- **Over-emission does not cost precision** (`target_accuracy` scores each
  record alone) **and pruning does not buy recall** (capping cost 12.15pt).
  Both directions tested; see §5k.
- **A metric built on token overlap cannot see a fact's negation.** Six
  instrument defects this session; five flattered the results and one silently
  stored facts as their opposite.

## 5. Dead ends — do not spend time here again

- **LoRA extractor.** Trained Qwen3-1.7B on users 10–19; judged R 0.1701 vs the
  parser's 0.4609. `lora_*.py` and `~/rg_private/halumem/lora/adapter-v*`
  remain if wanted, but the branch is closed.
- **MG/CCG parsers.** Only wide-coverage MG parser is 2019, PTB-trained, no
  successor. Research-grade and brittle on dialogue.
- **AMR/UCCA, conversational OpenIE.** No evidence of better stability on
  dialogue; best published dialogue triple extraction is 51.14% F1 on single
  utterances.
- **Composition/entity-resolution for F1.** Worth +0.6pt pooled (e220).
  `person_subject.py` and `entity_resolve.py` are kept as PRODUCT fixes
  (0 wrong merges, 10/10 leak detection) but do not move the benchmark.
- **The inference gate (`RG_QGATE`).** Net-negative on the current stack:
  0.70 hallucinations removed per correct answer lost (e210).

## 6. Where the remaining recall is

On user 0, of the judged misses: **97% are present in the session dialogue**,
so almost nothing is unreachable. Roughly 40% are already emitted in some form
(a FORM problem) and 60% are not emitted at all (coverage). Both are parsing
work, and parsing work has returned 3–11pt per round.

Worth trying next, from the parser research (`notebook.md` e223 onward):
CoreNLP Enhanced++ dependencies for coordination stability; CAIT's
CHILDES-trained parser (arXiv:2605.19718) as a second opinion; Maverick
coreference for cross-turn linking.
