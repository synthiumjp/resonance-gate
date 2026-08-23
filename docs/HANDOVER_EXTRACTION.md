# Handover — deterministic extraction (rgx), 2026-08-21

Read this, then `docs/EXPERIMENT_LEDGER.md` §1 (established), §5a–5l (laws and
corrections), §6 (open items). Notebook entries 217–240 are this arc.

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
- **Replicated on user 1 (e237): F1 0.4895 vs prompted 0.2861, p=1.1e-21.**

**CORRECTION (e240): every recall above is UNDER-read.** HaluMem's official `evaluation.py` computes recall over non-interference gold only; our harness counted interference points. On the official definition the parser in the tree scores **u0 R 0.5233 / u1 R 0.4418** (prompted 0.2705 / 0.2369), implied u0 F1 ≈ 0.59. The harness now prints both. Interference (the assistant's false memories about the user) is stored 19–20% of the time by the parser and 0% by the prompted arm — diagnosed as the assistant's 'I' being mapped to the owner, fixed in the e240 parser round.


### Current numbers — tree at `8b30efa`+ (e240–e243, 2026-08-23)

Official definition (non-interference recall), local judge, prompted arm reused:

| user | P | R | F1 | interference acc. | vs prompted F1 |
|---|---|---|---|---|---|
| u0 | 0.7092 | 0.6075 | **0.6544** | 61.3% | 0.3860 |
| u1 | 0.6700 | 0.4880 | **0.5647** | 53.7% | 0.3477 |

Arc: e240 parser round (+13.5 / +4.4pt recall, p=1e-8 / 0.04) → e242
evidential frame rule (−3.3 / −1.4pt recall, +13.7 / +22.4pt interference
accuracy, ships on product grounds) → e243 atom+full / object control /
third-party subjects (null on both, kept). Notebook e240–e243. Judge
server on WSL :8090; Stanza rebuilds go to the Mac Studio (see memory
`mac-studio-worker`). Next: the end-to-end QA number (rgx cache vs LLM
cache, u0) — in flight at time of writing; then update-signal grammar
(used to / no longer / from X to Y) against the updating metric.

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

rgx tests need stanza — run them with `~/rg_private/halumem/official/.venv/bin/python -m pytest rgx/`; `~/rg/.venv` fails all of them with ModuleNotFoundError.

| | u0 | u1 |
|---|---|---|
| baseline judged (pre-fix parser) | done, e233 | done, e237 |
| artifact rebuilt with fixed parser | `artifact_u0_ud_v2.json` | `artifact_u1_ud_v2.json` |
| fix judged — RECALL | **done, e239**: 0.4609→0.4522, p=0.60 | **done, e239**: 0.3820→0.3866, p=0.78 |
| fix judged — precision | done: 0.7099→0.6782, inside 1 SE | **not run** (least informative number; optional) |

**The recall question is SETTLED on both users: two nulls with opposite
signs.** Step 1 below is now optional — it only recovers u1's precision, and
u0's precision came back inside its own standard error. Prefer step 2.

### 1. (Optional) u1 precision only

The GGUF judge server must be up on :8090 first — it does NOT survive a
reboot:

```
~/rg/.venv/bin/python -m llama_cpp.server   --model /usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e   --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 --chat_format chatml
```

Then, from `~/rg_private/halumem/official/HaluMem/eval`:

```
RG_EXTRACT_V5=1 RG_PREFIX_NO_THINK=1 PYTHONUNBUFFERED=1   ~/rg_private/halumem/official/.venv/bin/python   /home/jp/rg/experiments/p2/lora_judge_ab.py   --user 1 --label grammar --limit-accuracy 300   --reuse ~/rg_private/halumem/lora/e239_fixrun/verdicts_u1_ud.json   --save ~/rg_private/halumem/lora/e239_fixrun/verdicts_u1_fix.json   --lora-artifact ~/rg_private/halumem/lora/artifact_u1_ud_v2.json
```

`--reuse` skips the prompted arm (0 calls). ~75 min, and it will re-judge
integrity you already have — pass `--reuse .../verdicts_u1_fix.json` instead
to skip straight to accuracy. `chain_fix.sh` and `watch_chain.py` in
`e239_fixrun/` run the whole thing end to end.

### 2. Then fix the queued parser defects (e238 + e237), as ONE measured change

Superseded by e240: defects A–G are being fixed as one round; see notebook e240.

Both are diagnosed with examples; neither is written yet. The saved artifacts are frozen files, so step 1 can run at any time regardless of tree changes.

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
