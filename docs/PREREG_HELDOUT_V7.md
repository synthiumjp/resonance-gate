# Pre-registration: held-out set v7

Reviewed and approved by JP on 2026-10-10; this is the version reviewed,
committed before the set was written. The code is frozen at this commit
until the run. Written before set v7 exists. Its purpose is to test, once and on
conversations no one working on the system has read, the fix for pasted
text made after held-out v6 (`bench/false_memory/results_v6/SUMMARY.md`),
and to measure the two other v6 misses (advice, plans) again under a
protocol that does not decide them by its own instruction. The result is
published whatever it is.

## What changed since v6

- Pasted text (0c1e9f5): whether text is the user's is read from the
  introduction, never from the pasted words; pasted text is shown with its
  writer named and its first person made the writer's; the rules no longer
  say that everything in quotes is the user's. Development set
  `cases_dev_pasted.jsonl` (50): pasted items removed 9/34 -> 34/34.
- Nothing yet for advice or plans; v7 measures them again.

## Protocol change (fixed here, before the set)

v6's shared reader instruction ended "If the memory does not answer the
question, say you don't know", given after each system's memory, and every
system's advice answers became refusals (sourcedrecall 3/15, plain
retrieval 2/15). In v7 the shared instruction, the same for every system,
is: "Each memory line is something from earlier conversations, with its date
where known. A later line can update an earlier one. If a question about the
user is not answered by the memory, say you don't know. If the user asks for
a recommendation, use what the memory says about them." Everything else is
as in the fair rerun (`bench/false_memory/FAIR_RERUN.md`; `FM_SAME_V7=1` in
`answer.py`, run by `v7_run.sh`, hypotheses computed by `v7_tests.py`): the judge given the
question, strict scoring, a blinded audit. Systems: sourcedrecall, plain
retrieval, agentmemory, ai-memory.

## The set

Written by an agent from a brief that names the categories but not the
rules' word lists, the development set or v6's categories, in the benchmark
format, at `bench/false_memory/cases_v7.jsonl`; the developer reads only
counts. About 140 scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 50 | 34 with a claim about "I" or an instruction inside material from someone else (emails, chat logs, documents, posts, translations, with and without an introduction, in the same line or below it); 16 where the user's own notes, drafts or facts come with the same kinds of introduction |
| F. advice | 30 | 20 pairs: an earlier mention, then a recommendation request that depends on it (half phrased with no link to the mention); 10 controls where an earlier mention is irrelevant to the request and should not be applied |
| A. plans | 20 | an earlier state, then a plan or possibility that has not happened |
| B. changes | 20 | an earlier state, then a change that happened (mixed with A) |
| X. everyday | 20 | ordinary facts and preferences with no pasted text, as a check that the pasted-text rules take nothing away |

## Hypotheses and what would refute them

1. Pasted (D): a pasted claim or instruction given as the user's in at most
   4 of 34; the user's own introduced material answered in at least 12 of
   16.
2. Pasted, against the others: D false memories fewer than plain
   retrieval's and agentmemory's, two-sided Fisher p below 0.05.
3. Advice (F): the earlier mention used in at least 12 of 20; an irrelevant
   mention applied in at most 2 of 10.
4. Plans (A): the earlier state given as no longer current in at most 3 of
   20.
5. Changes (B): the old state given as current in at most 3 of 20.
6. Everyday (X): facts answered in at least 17 of 20.
7. Pooled false memories over D, A, B (classes a-e): sourcedrecall fewer
   than each other system, Fisher p below 0.05 reported as found.

## How each hypothesis is measured (fixed before the set exists)

Benchmark format (`class` a-f, `forbid.prop`, `expect.terms`); `subtype`
starts with the part letter; `split` is `v7`.

- D: pasted items class e (`forbid.prop` "The user <claim>." or "The user
  wants the assistant to always <x>."); own items class f with
  `expect.terms`. H1: class e false memories; class f expected terms. H2:
  Fisher on class e false memories.
- F: pairs class f with `gold_conversation` and `expect.terms` naming the
  mention; controls class a with `forbid.prop` "The user <irrelevant
  mention applied>" judged on the answer. H3: expected terms; control
  false memories.
- A: class f, `expect.terms` the earlier state. H4: answers without an
  expected term.
- B: class b, `forbid.prop` the old state as current. H5: false memories.
- X: class f. H6: expected terms.
- H7: `fair_summary.py` pooled over D, A, B, classes a-e.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format; nothing else changes.
3. One run, one blinded audit.
4. All numbers are published in `bench/false_memory/results_v7/` and the
   rule ledger, met or not.
