# Pre-registration: held-out set v8

Approved by JP on 2026-10-10 ("Keep going", in reply to the request to
review it); this is the version shown, committed before the set was
written. The code is frozen at this commit until the run. Written before
set v8 exists. Its purpose is to test, once and on
conversations no one working on the system has read, the change to how
pasted text is detected made after held-out v7
(`bench/false_memory/results_v7/SUMMARY.md`), with checks that it takes
nothing away elsewhere. The result is published whatever it is.

## What changed since v7

- v7: where pasted text was marked, the reader took it for the user's once
  in 24; 10 pasted items were never detected (introductions on their own
  line before a blank line, or after the paste, worded in ways the rules did
  not list).
- f69fc33: detection reads the message's shape: a short paragraph of the
  user's and a block in another voice (greeting, sign-off, chat log,
  heading, review, list of rules, code comments), the introduction before or
  after it; chat logs anywhere in a message; a letter addressed to the user
  by name; "^ that's from ...". The owner's name is passed to the parser.
- Second development set `cases_dev_pasted2.jsonl` (60, written by an agent
  without the rules, introductions varied on purpose): detection without a
  model 6/40 -> 37/40 pasted items removed, own items kept 15/20 -> 19/20;
  end to end under the v7 protocol, false memories 33/60 -> 5/60 questions, own material
  answered 13/20 -> 16/20. First development set unchanged (3/34, 13/16).
- A reworded rule on when the reader should say "I don't know" was tried
  and refuted on development data (22f45bf, reverted); nothing else changed.

## Protocol

As v7 (`FM_SAME_V7=1`, the judge given the question, strict scoring, a
blinded audit), all four systems: sourcedrecall, plain retrieval,
agentmemory, ai-memory. Run by `v8_run.sh`, hypotheses computed by
`v8_tests.py`, both written before the set exists.

## The set

Written by an agent from a brief that names the categories but not the
rules, the development sets or the v6 and v7 audit categories, at
`bench/false_memory/cases_v8.jsonl`; the developer reads only counts. 100
scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 60 | 40 with a claim about "I" or an instruction inside material from someone else, the introduction placed and worded as people do (before, after, in the middle, in another message, none); 20 where the user's own drafts, notes, posts or facts come in the same shapes |
| B. changes | 20 | an earlier state, then a change that happened |
| X. everyday | 20 | ordinary facts and preferences, no pasted text |

## Hypotheses and what would refute them

1. Pasted (D): a pasted claim or instruction given as the user's in at most
   6 of 40; the user's own material answered in at least 15 of 20.
2. Pasted, against the others: D false memories fewer than plain
   retrieval's and agentmemory's, two-sided Fisher p below 0.05.
3. Changes (B): the old state given as current in at most 3 of 20.
4. Everyday (X): facts answered in at least 15 of 20.
5. Pooled false memories over D and B: fewer than plain retrieval's and
   agentmemory's, Fisher p below 0.05 (ai-memory reported beside it, with
   its own-material count).

## How each hypothesis is measured (fixed before the set exists)

Benchmark format; `subtype` starts with the part letter; `split` is `v8`.
- D: pasted items class e (`forbid.prop` "The user <claim>." or "The user
  wants the assistant to always <x>."); own items class f with
  `expect.terms`. H1: class e false memories; class f expected terms. H2:
  Fisher on class e false memories.
- B: class b, `forbid.prop` the old state as current, `expect.terms` the
  new. H3: false memories.
- X: class f. H4: expected terms.
- H5: pooled over D and B, classes a-e.

## Procedure

1. JP reviews this file; the version reviewed is committed before the set
   is written. The code is frozen from that commit until the run.
2. The agent writes the set and validates the format; nothing else changes.
3. One run, one blinded audit.
4. All numbers are published in `bench/false_memory/results_v8/` and the
   rule ledger, met or not.
