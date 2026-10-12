# Plan to launch (2026-10-12)

Everything still open from the review of 2026-10-12
(`docs/REVIEW_2026-10-12.md`, numbered items), the market and research
note (`docs/MARKET_2026-10-12.md`, M1-M7) and the launch list. Each item
says what done means. All tests, runs and checks are on the Mac; WSL edits,
commits and pushes only.

Already done on 2026-10-12: review 1.1, 1.2 (script), 1.8, 1.10, 2.5 (Holm
in v11_tests.py), 3.1 (5c4e691), 3.3, 3.7/3.17, 3.12, 3.13, 3.16, 3.18, 4.2,
4.6, MCP annotations (part of 3.2), the Windows lock wait (part of 3.5), CI
written (4.4, not yet green).

## Phase 0. Running now (no product code may change until the v11 run ends)

| | item | done when |
|---|---|---|
| 0.1 | release re-measure on d89d830 (release5.log) | log ends "release measure done" |
| 0.2 | v11 run, both readers, the rules ablation | v11.log ends "v11 done"; audit packets written |
| 0.3 | strict LoCoMo re-judge of the release answers | strict rows for default, small, standard |
| 0.4 | held-out regression step under the fair protocol (release_measure.sh step 4 alone) | counts for v3, v4, coding, projects |
| 0.5 | CI green on ubuntu, macOS, Windows (workflow only, not product code) | three green jobs |

## Phase 1. Write up (day 1)

| | item | done when |
|---|---|---|
| 1.1 | v11 blinded audit (sonnet agent per reader) and results_v11/SUMMARY.md, met or not | committed, with refusal counts, Holm, the ablation row, Phi-4 beside Qwen |
| 1.2 | bench/RELEASE_d89d830.log and README numbers from that one run | README says which commit, that Mem0 and plain retrieval were copied (1.5), top-k 5 vs product 8 (1.5) |
| 1.3 | README number fixes: LongMemEval n=500 vs 470 and the competitors' denominators (1.3); 67.6% (1.4); strict LoCoMo first (1.6); ai-memory and its refusals beside every pooled count (1.7); the pasted-claims trend beside plain retrieval (1.9); "the memory tells the agent" (1.12) | each sentence checked against a file |
| 1.4 | CHANGELOG Unreleased rewritten: current numbers, the 10-09 security fixes, pasted text by shape, own text, the cut, no duplicates (1.11) | one entry per change |
| 1.5 | dev-set outputs behind e322-e324 copied from the Mac into the repo (1.14) | the notebook's numbers recomputable from committed files |

## Phase 2. Product fixes (days 2-3; full suite on the Mac after each)

| | item | done when |
|---|---|---|
| 2.1 | Forget (3.4): HMAC with a per-install key instead of the plain hash; titles and the Cursor spool erased; a sentence that contains the forgotten words, or an assistant reply quoting them, erased whole; the count returned; README says exactly what is erased | tests for each; README sentence matches |
| 2.2 | MCP ingest (3.2): dates more than a day ahead rejected; rehydrate capped and scoped to the project | tests |
| 2.3 | The lock not held while parsing (3.5): parse outside, write inside | concurrency test: 4 writers, no lost conversation |
| 2.4 | Title scrubbed before it is cut (3.6) | test with a secret across character 60 |
| 2.5 | Cursor: store on session end or debounce, not every turn (3.8) | one worker per session |
| 2.6 | Large imports: append instead of rewriting conversations.json; zip cap 1 GB, streamed (3.9) | import of a 50,000-message export in linear time, memory flat |
| 2.7 | Windows details (3.10): DETACHED_PROCESS, utf-8 stdin and open(), README says chmod privacy is POSIX only; a typed "[MEMORY" no longer deletes the rest of a message (3.10, 3.21) | tests; Windows CI job runs them |
| 2.8 | MCP tool descriptions cut to two or three plain sentences; export, quarantine, dynamics, rehydrate hidden by default (3.11) | tool list under a set size |
| 2.9 | Block safety (3.15, 3.20): inner quotes made typographic; `[ MEMORY` with spaces caught; notes and owner names passed through `_inert` | tests with forged lines |
| 2.10 | Non-English questions (3.21): `_focus` and the window use Unicode words; undated messages sort last; a bad RG_MSG_WINDOW falls back | tests |
| 2.11 | Advice pattern narrowed for coding questions (3.14), measured on the dev coding and advice sets | no loss on advice; coding questions no longer in advice mode |
| 2.12 | "What the agent was given": `sourcedrecall-memory last` shows the last block and its size (M3, the bloat and black-box complaints) | command and test |
| 2.13 | Install and packaging: install failure shown to the user at session start, one install time everywhere (4.3); Python capped at 3.13 and `__version__` from the package (4.5); NOTICE with every model's and WordNet's licence, SECURITY.md, CONTRIBUTING (4.8); an uninstall section (4.9) | a clean-machine install shows a failure plainly |

## Phase 3. Evidence (days 3-6)

| | item | done when |
|---|---|---|
| 3.1 | MemPalace in the comparisons (M2): adapter, the dev sets, then the held-out regression sets, same reader and judge | numbers in the README table |
| 3.2 | Claude Code's own memory in the comparisons (M2). Decision needed: its notes are written by Claude | see decisions |
| 3.3 | A coding-task test with and without memory (M3): multi-session coding scenarios where a later task depends on an earlier decision, convention or preference; pass rate checked by tests, plus tokens; dev set first, then a pre-registered held-out set | pre-registration reviewed by JP; one run |
| 3.4 | Real-shaped pasted text (2.4): a small set built from public emails, reviews and forum posts (not written by a language model), made-up owners | detection and false memories reported |
| 3.5 | Stage-wise numbers (M4): what was stored, what was marked out of date, on the dev sets, beside the answers | a table in HOW_IT_READS |
| 3.6 | Measurement hygiene: answer.py retries and a LoCoMo seed (2.8); judge-audit agreement reported (2.6); number and plural forms in strict scoring, applied to every system (2.7) | in the next run's write-up |
| 3.7 | Demo on a store big enough that selection shows (1.13) | bench/demo/OUTPUT.txt regenerated |
| 3.8 | A third reader family (Gemma or Mistral) on the dev sets | dev table with three readers |

## Phase 4. Positioning and docs (day 6-7)

| | item | done when |
|---|---|---|
| 4.1 | README leads with what no one else measures: false memories, pasted text kept apart, out-of-date facts, no model call to store, any LLM; says which mem0 was measured (M1); pasted-text marking as a defence against memory poisoning (M5) | JP approves |
| 4.2 | BENCH/REPRODUCE.md covers v5-v11, the fair protocol and the release script (4.7) | one command reproduces a held-out result |
| 4.3 | docs/launch write-up rebuilt (4.10): one release run, v10 and v11 with refusals, strict LoCoMo first, limits stated plainly, what forget erases | JP approves |
| 4.4 | A clean product repo for sourcedrecall, the research kept in resonance-gate (4.11). Decision needed | see decisions |

## Phase 5. Launch (JP, about a week)

| | item | done when |
|---|---|---|
| 5.1 | A week of real use, with notes of anything wrong | JP's list worked through |
| 5.2 | Make the repo public; confirm both Hugging Face repos are public; tag a new version (4.1) | plugin installs from the tag |
| 5.3 | Plugin install from the tag on a clean Mac, Linux and Windows machine | all three work |
| 5.4 | PyPI trusted publisher set up; release workflow publishes | `pip install sourcedrecall` works |
| 5.5 | Write-up and demo published | |

## After launch

- Implied changes (M6): the open problem in the research and ours (v5:
  labels on 2 of 25). The next parser work.
- A paper on the linguistic approach (M7): no published counterpart found.

## Decisions for JP

1. Claude Code's own memory as a comparison: its notes are written by
   Claude. Options: run it on a few dev scenarios with your Claude
   subscription (no paid API); run Claude Code against our local Qwen
   through an Anthropic-compatible endpoint (not what users get); or
   compare on design only.
2. A clean product repo (4.11): publish sourcedrecall from a fresh history
   with only the product, docs and benchmarks, or as it is now.
3. The coding-task test before launch (adds about 2 days) or after.
4. Launch date: about 22-23 October if v11 holds; later if 3.3 goes first.

## Timeline

| | days | depends on |
|---|---|---|
| Phase 0 | tonight | |
| Phase 1 | 1 | Phase 0 |
| Phase 2 | 2 | v11 run ended |
| Phase 3 | 3-4, partly alongside Phase 2 | decisions 1 and 3 |
| Phase 4 | 1 | Phases 1-3 |
| Phase 5 | about 7 (JP) | Phase 4 |

About two weeks to launch with the coding-task test, ten days without.
