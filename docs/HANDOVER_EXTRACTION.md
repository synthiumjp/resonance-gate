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


### Product path (e244–e247, 2026-08-23)

End-to-end on u0 through the official harness, rgx cache vs the LLM cache,
zero extraction calls: **QA 59.8% vs 59.1% correct, hallucination 17.7 vs
18.9, updating 12.6% vs 4.3%** — the LLM leaves the write path at no QA
cost. Found and fixed in the STORE path, not the parser: (1) facts rendered
through the LLM-era template ("Martin Mark's is is open") — the proposition
`text` now rides through ingest/cluster/graph (`21df0cf`); (2) hearsay
ingested as fact — `evidential=report` mentions never corroborate, hearsay-
only slots live in a separate tier (`d23fce8`); (3) the per-session artifact
credited only first mentions while 35% of gold restates earlier facts — now
credits any fact with a receipt in the session (`43c193b`); (4) the attribute
exclusion regex matched "path" inside `career_paths`. Both arms re-judged (e247): hearsay tier costs no QA (p=0.21) and buys +15.2pt store interference accuracy; all arms level on QA. `sourcedrecall.profile_ingest` ships zero-LLM ingestion over MCP (dcd564b). Judging the rgx store takes
~7 h on the WSL GPU; the accuracy phase scores every stored fact alone.

### Published comparison (do NOT quote yet)
HaluMem-Medium extraction F1: Memobase 25.13 · Supermemory 56.90 · Mem0 57.31 ·
Mem0-Graph 57.85 · MemOS 79.70 · MOSAIC 86.77. Our judge is local and e176
measured a frontier judge scoring us ~9.67pt WORSE — that cancels in our own
paired comparisons but **not** against someone else's published table.

---

## 3. START HERE — state at 2026-09-05, and what to do first

**Session closed 2026-09-05 with e249–e277 committed, tree clean, 569 tests
green** (43 more under `RG_HEARSAY=1`). Nothing is running. No judged run has
happened since e247 — 28 entries ago, nine of them unconditional parser
changes.

### 3.0 Read this before touching anything

- `notebook.md` entries **e257–e277** are the current arc. e276/e277 is the
  most important: an adversarial review found SEVEN false-fact classes that
  all six measurement axes scored 100% on.
- `docs/EXPERIMENT_LEDGER.md` **§5m, §5o, §5p, §5q, §5r** are the laws earned
  in that arc. They will save you a day each.

### 3.1 The two instruments — RUN BOTH BEFORE AND AFTER ANY CHANGE

    ~/rg_private/halumem/official/.venv/bin/python tools/dogfood.py --v3
    ~/rg_private/halumem/official/.venv/bin/python tools/refusal_report.py
    ~/rg_private/halumem/official/.venv/bin/python -m pytest rgx/ experiments/p2 tools/ server/tests -q
    ~/rg/.venv/bin/python -m pytest server/tests/test_mcp_layer.py -q   # needs `mcp`; the stanza venv lacks it

`server/tests` was NOT in this command until 2026-09-05, and two of its tests
were failing on HEAD while the handover said "569 green". Never drop it again.

`tools/dogfood.py` is the PRODUCT harness — six axes over a synthetic
conversation: recall, abstention, PURITY (nothing unasserted reaches the
store), tiering, CURRENCY (a superseded fact must not come back first) and
CONFLICT (a real contradiction raises an ask; a multi-valued slot does not).
It self-checks its own probes first (`check_probes()`) and refuses to be read
while they are inconsistent — five stale probes in one session earned that.

`rgx/refusal_cases.py` is the REFUSAL matrix: CommitmentBank's four
entailment-cancelling operators × CheckList's test types. **Add a row BEFORE
fixing a non-assertion leak, not after.** Its DIR column (a matched
declarative that must still assert) is what separates real refusal from a
parse failure; its INV column has twice caught an operator handled in one
phrasing and not another.

Current: recall 20/26 rank-1 · 26/26 in pool, abstention 8/8 (e275 removed a
probe; "9/9" in older entries is stale), purity 21/21, currency 3/3·3/3,
conflict 1/1·0 false. Refusal matrix all cells pass (11 rows added 2026-09-05).
The gate now fails on three properties: purity, abstention, and every stated
fact present in the pool -- before 2026-09-05 a store-nothing system passed.

**Read `docs/REVIEW_2026-09-05.md`** before trusting any number above: it
lists what each axis can and cannot see (purity is a 21-string denylist;
recall matches by substring).

### 3.2 The judged row — STAGED, NOT RUN

JP said hold. Everything is ready:

- **The cache is rebuilt** with the current parser:
  `~/rg_private/halumem/qa_rgx/cache_u0_v5.jsonl.new` (2329 lines, 10 min to
  build via `tools/build_rgx_cache.py --user 0`). Old banked as `.bak_e247`.
  **Move `.new` into place before running.**
- **What the parser changes did**, measured from that diff: 41% of turns
  changed output; raw fact count −17.5%; but by SLOT, 635 gone / 756 added /
  322 rephrased = **net +121**. It is not the pruning the raw count suggests.
- **Judge server `:8090` does not survive a reboot.** Launch line is in §3.6
  below. Verify it responds before starting the chain.
- **The chain**: `~/rg_private/halumem/qa_rerun2/chain.sh`, both arms, ~10.5h
  (llm 3h04, rgx 7h28 — from its own log). Use e247's flags, so the PARSER is
  the single variable. Do NOT add `RG_TEXT_LONGEST` / `RG_HEARSAY` /
  `owner_pronoun` to the same run; one night, one question (§6c).
- **KNOWN LIMIT of that run (e277 audit):** `eval_rgp2.py:146` calls
  `retrieve_facts_v3` DIRECTLY, so the judged row exercises none of
  `recall_v3`'s floor / grounding / subject-rerank / stale-demotion. It
  answers the parser question and nothing about this session's retrieval work.
  Do not report it as "the session, judged".
- Launch a QUALITY sentinel from the start, not a liveness watcher (memory
  `quality-sentinels-not-liveness-watchers`).
- A NULL result is the likely and good outcome: e239 and e243 both came back
  benchmark-neutral for this class of correctness fix. Flat = nine changes
  discharged and the stale-artifact debt cleared.

### 3.3 Run another adversarial review — this is now a standing activity

Four sonnet agents, non-overlapping, all told to VERIFY BY RUNNING CODE and to
report what they could NOT break. Ninety minutes found more than a day of
building measurement axes (§5q). The first round's briefs were: attack the
recent parser changes; audit the measurement claims; red-team the store for
false facts; audit architecture and dead code. **There is no reason to think
one round exhausted it.**

Sonnet or haiku only, never fable/opus (memory `subagents-sonnet-or-haiku-only`).

### 3.4 Open defects, verified and NOT fixed

- **From the 2026-09-05 review, still open** (`docs/REVIEW_2026-09-05.md`
  §A4, §C, §D): superseded facts render as CORROBORATED in `context_block`
  with no staleness marker; the fallback retriever abstains on "Where do I
  work?"; `obl:unmarked` arguments are dropped ("I run five miles every
  day" -> nothing); pre-verbal adverb as sole argument dropped ("I no longer
  smoke" -> nothing); coordinated adjective predicates lose the second
  conjunct; perfect+negation word order ("has been not to Europe"); purity
  is a denylist and recall is a substring match; three divergent
  single-valued-slot allowlists; non-atomic `conversations.json` writes.

- **Attribute-level abstention.** "What is my partner's job?" returns "Sam
  works from home" — related, true, not an answer. Recorded as
  `PARTIAL_KNOWLEDGE` in `tools/dogfood.py`, deliberately outside the
  abstention count so that number keeps one meaning.
- **Cross-turn coreference.** 16.7% of a real store (e262), parked. `coref/`
  (committed in feea1fc, untested) already has centering + binding; Lee et al. 2013's
  precision-ranked sieve is the right architecture — rules that can only
  REJECT, never propose.
- **Temporal reasoning.** Dates are stored and completely unused.
- **Entity resolution at scale.** u0 has three people with distinct names; the
  disambiguation population has never existed in any test we have run.
- **Two paraphrase recall gaps** remain at rank 1 (pool is 26/26).

### 3.5 Where I would go next, and the caveat on that

**The auditable-memory loop: browser + rehydrate + correct, wired end to end.**
`server/sourcedrecall/browser.py`, `profile_rehydrate` and `profile_correct`
(deny/confirm/retype) all exist and are half-wired.

The argument: we will not beat MemOS at 79.7 extraction F1. A store at 0.65
that the user can SEE AND FIX is more useful than one at 0.85 they cannot
inspect — it turns imperfect extraction from a defeat into a survivable
condition, and it is the only thing on the list a person could actually use.
It also plays to the one structural advantage: nothing here can generate, so
the store is a document rather than an opaque model.

**CAVEAT, and take it seriously:** that is architectural reasoning, and §5g
says architectural reasoning is not evidence of a lever. It was wrong four
times in one day. Build the THINNEST version a person can click through and
let that decide, rather than designing the whole thing.

**Do NOT build:** more measurement axes, more thresholds, more benchmark
chasing. There is more instrument than evidence already.

### 3.6 Ops

Judge server (GGUF, does not survive reboot):

    ~/rg/.venv/bin/python -m llama_cpp.server \
      --model /usr/share/ollama/.ollama/models/blobs/sha256-a8cc1361f3145dc01f6d77c6c82c9116b9ffe3c97b34716fe20418455876c40e \
      --n_gpu_layers -1 --n_ctx 16384 --port 8090 --host 127.0.0.1 --chat_format chatml

`rgx` tests need stanza: use `~/rg_private/halumem/official/.venv/bin/python`;
`~/rg/.venv` has no stanza. The 16GB card is shared with the Windows desktop
under WSL — long runs belong overnight. Stanza rebuilds can go to the Mac
Studio (memory `mac-studio-worker`).

**Flags that changed default in e277:** `RG_PROFILE_V3` is now ON (v3 is the
product retriever; `=0` opts out, and it falls back rather than failing where
models are absent). `FLOOR_V3` is now `None` — measured inert AND costly.
`RG_NLI=0` restores the strict no-transformer guarantee at the cost of
conflict detection. `RG_TEXT_LONGEST` defaults ON in the product path and OFF
in the benchmark harness, deliberately (e266).

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
