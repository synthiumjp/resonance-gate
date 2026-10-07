# Pre-registration: held-out set v5

Reviewed and approved by JP on 2026-10-08; this is the version reviewed,
committed before the set was written. Written before set v5 exists. Its purpose is to test the rules in
`docs/HOW_IT_READS.md` on conversations no one working on the system has
read, once, and to publish the result whatever it is.

## Why a new set

The held-out sets v2-v4, `cases_code_blind` and `cases_projects_blind` have
been run many times. On 2026-10-05 an agent described the categories of the
claim check's errors on them (counts only), and some rules were written
from those categories, so those sets no longer test the newest rules
cleanly.

## The set

Written by an agent, in the benchmark format (`bench/false_memory`), stored
at `bench/false_memory/cases_v5.jsonl`; the developer reads only counts.
About 120 scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| A. changes stated | 25 | a later message states a change ("I moved to...", "I left Acme") |
| B. changes implied | 25 | a later message implies it: presupposition triggers, change-of-state verbs, "now" |
| C. no change, with traps | 20 | later messages about other people's changes, rentals, holidays, moods |
| D. decisions | 20 | the assistant proposes; the user accepts, declines, defers, or later reverses |
| E. claims to check | 20 | true, out-of-date, denied, hedged, assistant-only and never-said claims |
| F. advice requests | 10 | "Can you recommend...", answered by something the user mentioned |

The agent writes them from a brief that names the categories but not the
rules' word lists, so the set is not built around the patterns.

## Hypotheses and what would refute them

Measured with the 14B local reader and judge used for every published run,
answer view, audited by an agent with the same rule for every system.

1. Changes stated (A): old state given as current in at most 2/25.
2. Changes implied (B): old state given as current in at most 6/25, and
   "may have changed since" or "no longer true" shown on at least 12 of the
   25 out-of-date lines.
3. No change (C): a change label on a current fact in at most 1/20.
4. Decisions (D): accepted decisions recalled in at least 7/10 of the
   accepted ones; a declined proposal given as decided in at most 1.
5. Claim check (E): "said" for a denied, hedged, assistant-only or
   never-said claim in at most 2 of the claims of those kinds.
6. Advice (F): the session with the answer among the top 5 in at least 8/10.
7. Every rule family keeps a label precision above its unlabelled base rate
   (`screen_labels.py`).

Plain retrieval (top 3 user messages by bge-small) runs on the same set as
the reference.

## How each hypothesis is measured (fixed 2026-10-08, before the set exists)

The set uses the benchmark's format (`class` a-f, probes with `forbid.prop`
and `expect.terms`); `subtype` starts with the part letter (`A_`, `B_`, ...)
and `split` is `v5`.

- A, B: class b; `forbid.prop` is the old state as current, `expect.terms`
  the new one. H1, H2 (first half): `score.py`, false memories per part.
  H2 (second half): `screen_labels.py` on part B, lines about the
  out-of-date state carrying "may have changed since" or "no longer true".
- C: class f; `expect.terms` the unchanged current value. H3:
  `screen_labels.py` on part C, change labels on lines about the current
  state or in the scenario.
- D: accepted and reversed decisions as class f (`expect.terms` the choice
  in force), declined or deferred as class e (`forbid.prop` "The user
  decided to ..."). H4: class f recall over the accepted ones; class e false
  memories.
- E: false claims as probes (class a denied or hedged, c never said, e said
  only by the assistant, b out of date) and true current claims in
  `positives_v5.jsonl`; `check_eval.py --counts-only`. H5: "supported"
  returned for a, c or e claims.
- F: class f with `gold_conversation` (the index of the conversation that
  holds the answer). H6: `v5_advice.py`, that conversation among the first
  five reached by `profile_memory._messages_for(question, k=50)`, the
  LongMemEval protocol.
- H7: `screen_labels.py` on the whole set.

## Procedure

1. JP reviews this file; the version reviewed is committed (and may be
   posted to OSF) before the set is written.
2. The agent writes the set and validates the format; nothing in the code
   changes after that until the run.
3. One run: retrieval, reader, judge, audit, `screen_labels.py`,
   `check_eval.py`.
4. All numbers are published in `bench/false_memory/results_v5/` and the
   rule ledger, met or not. A missed hypothesis is reported as missed; any
   fix afterwards is measured on a different set.
