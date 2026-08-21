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
| prompted (shipped extractor) | 0.6684 (n=98) | 0.2122 | **0.3221** |
| spaCy parser (pre-port) | 0.9301 **(biased)** | 0.4311 | 0.5891 **(withdrawn)** |
| **UD/Stanza parser (current)** | **0.7099** (n=81) | **0.4609** | **0.5589** |

- **Recall is solid and is the headline**: +24.87pt over the prompted 14B,
  discordant 40/183, **McNemar exact p = 4.8e-23**. Recall judges all gold
  points, so it is untouched by the sampling defect below.
- **The corrected F1 is 0.5589, +23.68pt over the prompted arm (e233).**
  `--limit-accuracy` used to take the FIRST N records; those are early sessions
  (the templated persona intro, where everything is easier). That inflated BOTH
  arms — prompted read 0.7759 biased vs 0.6684 corrected, a +10.75pt head bias.
  Fixed to a seeded random sample in `lora_judge_ab.py`. Every precision in
  entries 225–231 is head-sampled; **0.5891 was never a floor**, it was built on
  the same bias.
- **Everything rests on ONE user.**

### Published comparison (do NOT quote yet)
HaluMem-Medium extraction F1: Memobase 25.13 · Supermemory 56.90 · Mem0 57.31 ·
Mem0-Graph 57.85 · MemOS 79.70 · MOSAIC 86.77. Our judge is local and e176
measured a frontier judge scoring us ~9.67pt WORSE — that cancels in our own
paired comparisons but **not** against someone else's published table.

---

## 3. Immediate next steps, in order

**Machine was restarted 2026-08-21 ~21:40 with the u1 fix-judge mid-run.**
Everything below is resumable; nothing is lost except that one run's progress.
Saved logs and verdicts: `~/rg_private/halumem/lora/e239_fixrun/`.

### State as of the restart

| | u0 | u1 |
|---|---|---|
| baseline judged (pre-fix parser) | done, e233 | done, e237 |
| artifact rebuilt with fixed parser | `artifact_u0_ud_v2.json` | `artifact_u1_ud_v2.json` |
| fix judged | **done, e239** | **INCOMPLETE — died at integrity 500/645** |

### 1. Re-run the u1 fix judge (the only outstanding measurement)

The GGUF judge server must be up on :8090 first — it does NOT survive a
reboot:

```
~/rg/.venv/bin/python -m llama_cpp.server   --model /usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e   --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 --chat_format chatml
```

Then, from `~/rg_private/halumem/official/HaluMem/eval`:

```
RG_EXTRACT_V5=1 RG_PREFIX_NO_THINK=1 PYTHONUNBUFFERED=1   ~/rg_private/halumem/official/.venv/bin/python   /home/jp/rg/experiments/p2/lora_judge_ab.py   --user 1 --label grammar --limit-accuracy 300   --reuse ~/rg_private/halumem/lora/e239_fixrun/verdicts_u1_ud.json   --save ~/rg_private/halumem/lora/e239_fixrun/verdicts_u1_fix.json   --lora-artifact ~/rg_private/halumem/lora/artifact_u1_ud_v2.json
```

`--reuse` skips the prompted arm (0 calls). ~75 min. Compare recall against
the **0.3820** baseline with a PAIRED McNemar over the two grammar verdict
maps — that is the test that matters, and u0's answer was a null (p=0.60).
`chain_fix.sh` and `watch_chain.py` in `e239_fixrun/` do this end to end.

### 2. Then fix the queued parser defects (e238 + e237), as ONE measured change

Both are diagnosed with examples; neither is written yet. Do not start these
until step 1 is done, or the artifacts and the tree diverge again.

* **`_third`'s spelling guards (e238).** `w.endswith("ed") or w.endswith("s")`
  catches need/feed/succeed/proceed and focus/pass/discuss/address/process.
  ~0.7% of records on both users. Replace the test with the UD features
  `_third` already receives. **And the `-es` branch needs `"s"` added** or
  "focus" becomes "focuss" — that branch was never reached before.
* **Two interrogative escapes (e237),** 0.08% of records. One is an embedded
  declarative inside a question ("What steps do you think you'll take?"). One
  is a genuine PRESUPPOSITION ("When you joined the conservation group, did
  you find...?") — the user did join, so that one wants the stray "When"
  stripped, not the clause dropped.

### 3. Then cut an rgx release

The package currently on disk has all four e234/e236 fixes and is measured
benchmark-neutral on u0. That is the first version whose shipped output
matches what the ledger claims.

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
