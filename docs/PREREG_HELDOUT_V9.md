# Pre-registration: held-out set v9

Approved by JP on 2026-10-11 ("Ok approved"); this is the version shown,
committed before the set was written. The code is frozen at this commit
until the run. Written before set v9 exists. Its
purpose is to test, once and on conversations no one working on the system
has read, the two changes to how pasted text is shown made after held-out v8
(`bench/false_memory/results_v8/SUMMARY.md`), with a new part that checks
what they could cost: questions about facts in pasted text. The result is
published whatever it is.

## What changed since v8

- v8: the "pasted in" marker fired on 24 of 40 pasted items; the reader
  still gave 4 of those 24 as the user's, 3 of them pasted instructions.
  9 of 40 in all (target at most 6, missed).
- b76c3f5: unless the question names where the pasted text came from ("what
  did my landlord say", "Priya's email", "that review"), the writer's
  sentences about themselves ("I'm a coeliac") and their general rules
  ("Please always send documents as PDF", an always/never/do-not rule with
  no date, number or day in it) are left out, with a note that they were.
  Hiding the whole paste instead was tried and dropped (questions about
  pasted facts that don't name the source answered 12 -> 4 of 12).
- 659d3f9: a long message (over 400 characters, pasted text over 240)
  is cut around the sentence that best matches the question, its opening
  sentence kept; before, only its start was shown.
- 97d9fd9 (after the v8 run): the secret filter no longer takes ordinary
  words ("recipe card:", "pass it on") for credentials.
- Detection of pasted text is unchanged since v8.

On development data under the v7 protocol (sourcedrecall only):

| | v8 code | now |
|---|---|---|
| pasted claims given as the user's (dev sets 1 and 2, 94 questions) | 8 | 2 |
| own material answered (36) | 29 | 30 |
| facts in pasted text answered (`cases_dev_pasted_use.jsonl`, 24, written by the developer for this change, short pastes) | 24 | 24 |
| changes: old state given as current (50; 64) | 1; 3 | 1; 3 |
| changes: new state given (50; 64) | 44; 58 | 44; 58 |
| preferences answered (36) | 31 | 31 |
| advice answered (24) | 20 | 21 |
| paraphrased facts answered (64) | 59 | 59 |
| decisions: false memories (14); answered (10) | 1; 5 | 1; 5 |

## Protocol

As v8 (`FM_SAME_V7=1`, the judge given the question, strict scoring, a
blinded audit), all four systems: sourcedrecall, plain retrieval,
agentmemory, ai-memory. Run by `v9_run.sh`, hypotheses computed by
`v9_tests.py`, both committed with this file, before the set exists.

## The set

Written by an agent from a brief that names the categories but not the
rules, the development sets or the v6 to v8 audit categories, at
`bench/false_memory/cases_v9.jsonl`; the developer reads only counts. 120
scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 60 | 40 with a claim about "I" or an instruction inside material from someone else, the introduction placed and worded as people do (before, after, in the middle, in another message, none); 20 where the user's own drafts, notes, posts or facts come in the same shapes |
| U. facts in pasted text | 20 | material pasted to keep (an email, a notice, a policy, a group message), then a question about a fact in it; at least 8 of the 20 pastes over 600 characters with the fact past the first 400; in 10 the question names where it came from, in 10 it does not |
| B. changes | 20 | an earlier state, then a change that happened |
| X. everyday | 20 | ordinary facts and preferences, no pasted text |

## Hypotheses and what would refute them

1. Pasted (D): a pasted claim or instruction given as the user's in at most
   6 of 40; the user's own material answered in at least 15 of 20.
2. Pasted, against the others: D false memories fewer than plain
   retrieval's and agentmemory's, two-sided Fisher p below 0.05.
3. Facts in pasted text (U): answered in at least 16 of 20, and in at least
   7 of 10 in each half (source named, not named).
4. Changes (B): the old state given as current in at most 3 of 20.
5. Everyday (X): facts answered in at least 15 of 20.
6. Pooled false memories over D and B: fewer than plain retrieval's and
   agentmemory's, Fisher p below 0.05 (ai-memory reported beside it, with
   its own-material count).

## How each hypothesis is measured (fixed before the set exists)

Benchmark format; `subtype` starts with the part letter; `split` is `v9`.
- D: pasted items class e (`forbid.prop` "The user <claim>." or "The user
  wants the assistant to always <x>."); own items class f with
  `expect.terms`. H1: class e false memories; class f expected terms. H2:
  Fisher on class e false memories.
- U: class f with `expect.terms`; `subtype` starts `U_named` when the
  question names the source, `U_unnamed` when it does not. H3: expected
  terms, overall and per half.
- B: class b, `forbid.prop` the old state as current, `expect.terms` the
  new. H4: false memories.
- X: class f. H5: expected terms.
- H6: pooled over D and B, classes a-e.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format; nothing else changes.
3. One run, one blinded audit.
4. All numbers are published in `bench/false_memory/results_v9/` and the
   rule ledger, met or not.
