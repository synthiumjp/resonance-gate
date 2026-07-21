# HANDOVER — RG Product (p2): a memory an LLM connects to that does not hallucinate

*Deep handover, 2026-07-21. Read this first, then notebook.md entries 53–69, then
the code. Branch: `product-p2`. Remote: github.com/synthiumjp/resonance-gate.git.*

---

## 0. THE VISION (crystallised this session — this is the north star)

A **memory system an LLM connects to** (an MCP server; `rg-product` already exists in
the repo, commit 90fd99c) that is **non-hallucinating BY CONSTRUCTION**. The LLM is
the fallible **client** (it generates, and it extracts candidate facts — both
error-prone). The memory is the stable **substrate** (it stores, corroborates, and
returns facts *with receipts*, or abstains). The division of labour IS the design:
the LLM stays creative; the memory can't make things up.

Two mechanisms, biologically framed by the registrant:

- **GROW** — *Bayesian nodes* (BUILT, `belief.py`). Each memory is a **posterior, not a
  record**. Evidence CONCENTRATES the belief (log-odds add); stale evidence decays.
  A fact crosses "asserted" only when corroboration pushes it over threshold. One-off
  mentions sit at the junk prior and are never asserted.
- **WIRE** — *Hebbian edges* (NOT YET BUILT — this is the immediate next step). Facts
  that co-occur should **link**, and the edge weight should **grow** with each
  co-occurrence ("fire together → wire together"). Retrieval becomes **spreading
  activation** over the graph, not a table lookup: query one node → wired neighbours
  light up → return a *connected, evidenced* neighbourhood.

**Why it does not hallucinate** (structural, not a tuning trick):
1. Retrieval is **non-generative** — it returns *stored* facts, never generates text,
   so it cannot confabulate what was never put in.
2. **Corroboration gates assertion** — a fact must recur ≥N times to be returned;
   noise/typos/one-offs stay below the line.
3. **Receipts** — every returned fact carries its source turns; ungrounded → not
   returned.
4. **Abstention** — no corroborated evidence → it says *nothing*, not a guess.
   Silence over hallucination.

The **WIRE layer must preserve this**: an edge is *also evidence* ("these two facts
were actually seen together N times", receipted). Links are never invented — they are
co-occurrence counts with Bayesian weights. Spreading activation only traverses edges
real co-occurrence built.

This composes into ONE memory across three layers that already exist as separate work:
**LLM extraction (feed) → Bayesian belief (grow) → VSA/resonance substrate (wire) →
non-generative receipted retrieval.** `rg` = "resonance gate" = the binding/associative
substrate; the belief layer is the node dynamics; they are not three projects, they
are the three layers of one.

---

## 1. THE KEY INSIGHT THAT MADE IT WORK

**CORROBORATION IS THE NOISE FILTER.** A *noisy* per-turn LLM extractor (~50% junk on
real data) + corroboration (assert only facts seen ≥N times) = a ~75%-precise profile,
because **real facts repeat and junk doesn't**. You do NOT need a perfect extractor;
you need a noisy one plus corroboration + receipts. This is the load-bearing result of
the whole session (entry 67). It is *robust, realtime, and receipted* — and it is what
turns a fallible LLM into a trustworthy memory.

---

## 2. WHAT IS BUILT & VALIDATED (the pipeline)

Ingest a messy stream (chat transcripts, notes, agent working memory) →

1. **Per-turn LLM extraction** (`llm_profile.py`, `extract_profile_facts`): ONE
   small-context LLM call per turn → `[{attribute, value}]` stable self-facts. Realtime
   (no history in prompt), **median 200 ms/turn** on qwen3:14b (p90 533 ms). Strict
   prompt rejects metaphors/instructions/code/section-refs/non-first-person.
   `canon_attr` folds synonym attributes into one slot (residence/location/city →
   location; all role phrasings → a MULTI-VALUED occupation — see §5).
2. **Belief accumulation** (`belief.py`): Bayesian posterior per (subject, attribute)
   slot. Corroboration concentrates; change-point decay.
3. **Corroboration + clustering readout** (`run_profile_full.py`): value clustering by
   token overlap (melbourne / melbourne australia → one summed fact), assert only
   clusters with ≥ N mentions. **Readout hygiene** (`_TECH_VALUE`, `_DEVICE_WORDS`,
   `_EXCLUDE_ATTR`) drops paths/drives/filenames/machine-names-as-location and
   transient/technical attributes.
4. **Receipts**: every corroborated fact carries the dates + conversation titles it
   came from → written to an UNREDACTED local `profile_report.txt` for the owner to
   verify; stdout stays REDACTED.

**Also built & sound (the "change" machinery, still useful for the substrate):**
- `run_belief.py` — belief pipeline + `changes()` with commensurability gates
  (`_real_change`: same-scale, referent, additive, dwelling checks).
- `numeric_gate.py` — rejects incidental numbers (years, IDs, enumeration, filler).
- `consistency.py` + `scope_audit.py` — LLM-as-energy categorical audit, neighbourhood-
  scoped/windowed so it runs at conversation scale (was crashing on 8192 ctx).
- `rci.py` — Reliable Change Index / commensurability (Jacobson-Truax; from the
  registrant's own arXiv:2604.27405).
- `twopath.py`, `value_extract.py`, `cos_extract.py`, `functional_extract.py`,
  `resolve.py`, `gate.py`, `schema.py` — the model-free extraction/gating layer
  (works on clean benchmarks; too noisy for raw research chat — see §3).

**Runners:** `run_real.py` (one transcript), `corpus_run.py` (a corpus, blind-judge
packet), `run_crosssession.py` (whole history, model-free, + current-state view),
`run_profile_sample.py` (LLM extraction, sampled), `run_profile_full.py` (**the main
one** — full-stream LLM extraction + corroboration + checkable report).

---

## 3. THE HONEST FINDINGS (the through-line — do not re-learn these the hard way)

- **Independent/out-of-sample validation caught over-optimism EVERY time it ran**
  (COND-E, the trip false alarm, B-semantic 16→8, the real-corpus 12.8%). Every
  trustworthy number came AFTER independent adjudication; every in-house-only number
  was inflated. *This is the single most reliable finding of the project. Keep the
  discipline: measure before building, validate out-of-sample, use blind judges.*
- **Real fact-CHANGES within/across sessions are RARE** (entries 58, 60): ~0 genuine
  in-conversation life-fact changes in ~8k ShareGPT convos; ~1 in the registrant's 13
  months. So "change detection" is low-yield; the value is the **accurate growing
  profile/graph**, not change alerts.
- **Distribution shift is real and brutal** (entries 60, 64): model-free extraction
  works on clean benchmarks (LongMemEval 11/39 @ 0/51) and curated personal chat
  (ShareGPT ~2% false alarm) and **manufactures junk on raw research/engineering
  chat** (keep_location firing on "keep digging"; §7.4.1 as an employer). This is why
  extraction went LLM-based.
- **Corroboration + receipts = trust via legibility, not perfection** (entries 67–69):
  the profile doesn't ask to be trusted; it shows evidence and is CORRECTABLE. The
  owner corrected two real errors in seconds via receipts.
- **Identity is MULTI-VALUED — do not collapse it** (entry 69): a person legitimately
  holds several concurrent roles. My "one job per person" prior was wrong and nearly
  deleted real facts. Requisite variety: the memory must HOLD the multiplicity.

---

## 4. VALIDATED NUMBERS (trustworthy — measured, mostly out-of-sample)

- LongMemEval knowledge-update recall **11/39**, fresh false alarms **0/51** — held
  IDENTICAL across every gate added this session (the regression guard; run
  `run_belief.py`).
- Per-turn LLM extraction latency **median 200 ms, p90 533 ms** (qwen3:14b) — realtime.
- Full-stream corroboration on real 13-month history: **1,010 single-mention facts
  dropped, ~160–197 corroborated kept**, ~**75% precision** on the corroborated set
  (vs ~10–15% model-free). Real facts rose to x10–x57; junk stayed x1.
- Categorical audit false-alarm on real no-change corpus: **1/47 (2.1%)**; numeric
  path after commensurability fixes: **0/47** (was 5/47).

---

## 5. IMMEDIATE NEXT STEP — BUILD THE WIRE LAYER

Over the corroborated facts (already cached on real data — see §6), build:
- **Co-occurrence edges**: two facts asserted from the same conversation (or a small
  window) get an edge; weight = co-occurrence count, receipted to those conversations.
  Bayesian weight (log-odds of association), not raw count.
- **Spreading-activation retrieval**: query a node → activate wired neighbours by edge
  weight → return the connected, evidenced neighbourhood (or abstain).
- **Non-hallucination test** (the acceptance criterion): does traversal ever surface an
  *unsupported* link? A link must trace to real co-occurrence + receipts, never be
  invented. Test on the registrant's data (cached) and on a held-out stream.

Natural home: the `rg-1.1` VSA/HDC substrate (binding + associative resonance). The
belief layer supplies node posteriors; the substrate supplies the wiring. New file
suggestion: `experiments/p2/wire.py` + `run_wire.py`.

---

## 6. DATA & PRIVACY (critical — read before touching any data)

- **Everything private is QUARANTINED and must NEVER enter git.** The repo pushes to a
  PUBLIC GitHub remote. PII in the notebook/commits is blocked by a classifier (this is
  correct — do not work around it).
- **Preserved artifacts (this session's scratchpad is ephemeral; these were copied to
  a persistent, out-of-repo dir):** `~/rg_private/`
  - `data-...batch-0000.zip` — the registrant's Claude export (878 conversations,
    18,160 human msgs, 2025-06 .. 2026-07). Unzip → `conversations.json` (546 MB) +
    `projects/`, `memories.json`, `users.json` (has name/email/phone).
  - `profile_cache.jsonl` — **13,911 turns of LLM extraction (the ~45-min run).** Keyed
    by sha1(turn text); reusing it makes `run_profile_full.py` near-instant. NOTE:
    changing the extraction PROMPT invalidates it (delete to rebuild).
  - `profile_report.txt` — the checkable corroborated profile with receipts.
- **`.gitignore` already excludes** `experiments/p2/real/`, `data-*batch*.zip`,
  `*:Zone.Identifier`, `private_chat/`. Keep private data OUT of the repo tree entirely
  (use `~/rg_private/` or a session scratchpad).
- **Execution of pipelines over personal data is GATED**: the classifier blocks the
  main loop from running them. The USER runs them via the `!` prefix (in-session, with
  their authorisation) and pastes/points at output. Redact identifiers in any stdout
  that returns to the shared session; unredacted reports stay in local files only.
- Two ShareGPT corpora were also built this session (48-conv anonymised validation
  corpus; earlier single transcript) — those lived in the *old* scratchpad and are
  likely gone; re-scrape if needed (but note: scraping strangers' PII repeatedly
  tripped the classifier — prefer the registrant's own data or a de-identified set).

---

## 7. OWED / DEFERRED WORK

- **WIRE layer** (§5) — the immediate next build.
- **Extraction refinements** (narrow, after the multi-role correction): (a) third-party
  attribution — a family member's fact must attach to the RELATIONSHIP, not the owner
  (e.g. spouse's job); (b) an SSH hostname must not be extracted as the owner's
  username. Both need a stricter first-person + entity-typing prompt, then a cache
  rebuild (~45 min).
- **The injection/correction loop** (proves usefulness): profile → injected as context
  to a fresh LLM turn → assistant visibly knows the user → owner corrects a fact via
  receipts → memory updates. Judge by feel: "does it know me and can I trust/fix it?"
- **The memory's query contract**: when asked something with no corroborated evidence,
  does it correctly ABSTAIN? This is the hallucination test for the substrate as a
  store, on ANY stream, not just the registrant's.
- Larger fresh precision sample; calibration fitting (belief junk-prior/retention
  thresholds are stated-but-unfit); the categorical LLM audit run entity-scoped on the
  full history (was cost-deferred).

---

## 8. CONVENTIONS & CONSTRAINTS

- **Commit at every stage boundary WITHOUT asking** (RG repo rule; freeze needs clean
  history). End commit messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- `notebook.md` (repo root) is the lab notebook — entries 1–69. This session added
  53–69. Keep appending; NO PII in it.
- **Frozen/immutable:** tags `rg-freeze-1.0`, `rg-1.1` — do not touch. The frozen
  research artifact is untouched.
- Relaxed purity: originally "LLM-free retrieval". Now honestly: **LLM at extraction +
  audit; model-free at the belief/commensurability/retrieval layer.** State this
  relaxation openly; it is Ashby-forced, not hidden. RETRIEVAL stays non-generative
  (that is the non-hallucination guarantee).
- Environment: WSL2 + ROCm (AMD GPU via /dev/dxg). qwen3:14b GGUF blob
  `sha256-a8cc1361...` via llama-cpp on GPU (`consistency.get_llm`). venv at
  `/home/jp/rg/.venv`. The 3B extractor (`extract_v2`) also exists.
- Registrant is the ground truth for their own profile; the product philosophy is
  legibility + correctability, not perfection.

---

## 9. ONE-PARAGRAPH RESTART

We are building a memory an LLM connects to that does not hallucinate: Bayesian nodes
that GROW (posteriors concentrate with corroboration — built, `belief.py`) and Hebbian
edges that WIRE (co-occurrence links — NOT built, the next step). The load-bearing
result is that a noisy per-turn LLM extractor + corroboration + receipts yields a
trustworthy, realtime, correctable profile on real messy data (validated on the
registrant's own 13-month history: 200 ms/turn, ~75% precision, junk filtered by
corroboration, every fact receipted). Next: build `wire.py` — co-occurrence edges
(weighted, receipted) + spreading-activation retrieval that returns a connected
evidenced neighbourhood or abstains, tested for whether traversal ever surfaces an
unsupported link. Data is quarantined in `~/rg_private/` (cache = 45 min of extraction,
reuse it); never commit PII; the user runs personal-data pipelines via `!`.
