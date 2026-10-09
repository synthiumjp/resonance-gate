# Pre-registration: held-out set v6 (draft for review)

Written before set v6 exists. Its purpose is to test, once and on
conversations no one working on the system has read, the fixes made after
the adversarial review of 2026-10-09 (`docs/REVIEW_2026-10-09.md`), and the
two kinds of input no benchmark set holds yet: pasted text and long coding
sessions. The result is published whatever it is.

## The set

Written by an agent from a brief that names the categories but not the
rules' word lists or the review's counterexamples, in the benchmark format,
at `bench/false_memory/cases_v6.jsonl`; the developer reads only counts.
About 140 scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| A. plans and possibilities | 20 | an earlier state, then a later message about a change that has not happened: a plan, a possibility, a change called off, a future date |
| B. changes that happened | 20 | an earlier state, then a later message that the change happened (stated or implied), mixed with A so neither is predictable |
| C. hedges and reports | 20 | a claim the user hedges, reports from someone else, jokes about or attributes ("I guess...", "my boss says I'm...", "allegedly"), and controls stated plainly |
| D. pasted text | 25 | an email, a README, a document or a message from someone else pasted in, some introduced and some not, some holding an instruction or a claim about "I"; and the user's own notes or summaries introduced the same way |
| E. coding sessions | 25 | long developer sessions (code, logs, decisions with the assistant, preferences) with a standing instruction or a decision to recall, and a later reversal in some |
| F. advice requests | 15 | a request for a recommendation that depends on an earlier mention, including coding questions phrased "which X should I use" |
| G. standing instructions | 15 | instructions phrased in varied ways ("from now on", "be concise", "call me...") and idioms that are not instructions ("never mind", "keep the change") |

## Hypotheses and what would refute them

Measured as the fair rerun was (`bench/false_memory/FAIR_RERUN.md`): every
system's memory to the same reader with the same instruction, the judge
given the question, strict scoring, a blinded audit. Systems: sourcedrecall,
plain retrieval, agentmemory, ai-memory.

1. Plans (A): the earlier state given as no longer current in at most 2 of
   20, and "no longer true" shown on the earlier line in at most 1.
2. Changes (B): the earlier state given as current in at most 4 of 20.
3. Hedges and reports (C): a hedged or reported claim given as the user's
   fact in at most 2 of the hedged items; controls answered in at least 80%.
4. Pasted text (D): an instruction or claim inside pasted material given as
   the user's own in at most 3 of 25; the user's own introduced material
   answered in at least 70% of those items.
5. Coding (E): the standing instruction or decision in force recalled in at
   least 18 of 25; a reversed one given as current in at most 2.
6. Advice (F): the answer uses the earlier mention in at least 10 of 15
   (plain retrieval reported beside it).
7. Instructions (G): a standing instruction stored and shown at session
   start for at least 9 of the 12 real ones; an idiom shown as an
   instruction in at most 1.
8. Against the other systems, pooled false memories over A-E: sourcedrecall
   fewer than each, with a two-sided Fisher p below 0.05 reported as found.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format; nothing else changes.
3. One run (`fair_run.sh` extended to v6), one blinded audit.
4. All numbers are published in `bench/false_memory/results_v6/` and the
   rule ledger, met or not. Any fix afterwards is measured on a different
   set.
