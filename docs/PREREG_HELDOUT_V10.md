# Pre-registration: held-out set v10

Approved by JP on 2026-10-11 after review; this is the version
reviewed, committed before the set was written. The code is frozen at this
commit until the run. Written before set v10 exists. Its
purpose is to test, once and on conversations no one working on the system
has read, the changes made after held-out v9
(`bench/false_memory/results_v9/SUMMARY.md`) to the two targets v9 missed,
and that the targets it met still hold. The result is published whatever it
is.

## What changed since v9

- v9 (4 of 6 met): pasted claims given as the user's 4/40; missed own
  material 12/20 (4 = own text taken for pasted, its fact left out) and
  facts in pasted text 13/20 (all 7 misses long pastes, the fact past what
  was shown).
- 8473783: pasted text shown to about 1,500 characters and a message to
  about 800 (were 240 and 400), the user's words before and after a paste
  alike, cut around the sentence that best matches the question beyond
  that, with the question's words for the source not counted; the writer's
  sentences about themselves left out only for a question about the user;
  own text recognised by its introduction ("draft email to my landlord,
  sending tonight", "reply I posted on the forum") or by the owner's
  signature or self-introduction in it.

On development data under the v7 protocol (sourcedrecall only), new set
`cases_dev_pasted_long.jsonl` (40, written by an agent without the rules):

| | v9 code | now |
|---|---|---|
| facts in long pastes, source named (12) | 5 | 10 |
| facts in long pastes, source not named (12) | 6 | 12 |
| own texts in pasted shapes (16) | 13 | 16 |
| pasted claims given as the user's (94) | 2 | 2 |
| own material, earlier dev pasted sets (36) | 30 | 31 |

Changes, preferences, advice, paraphrase and decisions unchanged.

## Protocol

As v9 (`FM_SAME_V7=1`, the judge given the question, strict scoring, a
blinded audit), all four systems: sourcedrecall, plain retrieval,
agentmemory, ai-memory. Run by `v10_run.sh`, hypotheses computed by
`v10_tests.py`, both committed with this file, before the set exists.

## The set

Written by an agent from a brief that names the categories but not the
rules, the development sets or the v6 to v9 audit categories, at
`bench/false_memory/cases_v10.jsonl`; the developer reads only counts. 120
scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 60 | 40 with a claim about "I" or an instruction inside material from someone else, the introduction placed and worded as people do (before, after, in the middle, in another message, none); 20 where the user's own drafts, notes, letters, diary entries, replies, posts or facts come in the same shapes, with or without a line saying they are the user's |
| U. facts in pasted text | 20 | material pasted to keep (an email, a notice, a policy, a group message), then a question about a fact in it; at least 10 of the 20 pastes (at least 5 in each half) over 800 characters with the fact past the first 600; in 10 the question names where it came from, in 10 it does not |
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

Benchmark format; `subtype` starts with the part letter; `split` is `v10`.
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

The run follows the re-measurement of LoCoMo and LongMemEval on 8473783,
which uses the same machine and reader.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format; nothing else changes.
3. One run, one blinded audit.
4. All numbers are published in `bench/false_memory/results_v10/` and the
   rule ledger, met or not.
