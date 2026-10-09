# Held-out set v6: results

Pre-registered in `docs/PREREG_HELDOUT_V6.md` (reviewed by JP and committed
before the set existed, 3513012). The set (`cases_v6.jsonl`, 140
scenarios in parts A-G) was written by an agent from a brief without the
rules' word lists or the review's counterexamples, and has not been read by
the developer. One run on commit 181aff3 (no product code changed since the
pre-registration; the commits between add the set and the run scripts), 2026-10-09,
under the fair protocol (`FAIR_RERUN.md`): every system's memory to the same
local Qwen3-14B reader with the same instruction, the judge (the same model)
given the question, strict scoring, then a blinded audit by an agent that saw
no system names (236 rows; 6 judge false alarms on hedged claims and 2
missed false memories on pasted text overturned, `audit_overrides_v6.json`).

The competitors' first run failed on every scenario (their adapters need
their scratch folder inside the tool folder; e279e4d, 181aff3). They were
run again alone with the same code and set; sourcedrecall's and plain
retrieval's results from the first run were kept. The failed files are in
`first_run_failed/`.

Four of eight hypotheses met, four missed.

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | plans (A): earlier state given as no longer current at most 2/20; "no longer true" on the earlier line at most 1 | 4/20; never fired | 6/20 | 4/20 | 6/20 | missed |
| H2 | changes (B): old state given as current at most 4/20 | 0/20 | 1/20 | 0/20 | 7/20 | met |
| H3 | hedges and reports (C): given as the user's fact at most 2/14; controls at least 80% | 1/14; 6/6 | 1/14; 6/6 | 2/14; 5/6 | 0/14; 5/6 | met |
| H4 | pasted text (D): a pasted claim or instruction given as the user's at most 3; own material at least 70% | 14/17; 7/8 | 15/17; 7/8 | 15/17; 7/8 | 3/17; 1/8 | missed |
| H5 | coding (E): instruction or decision in force at least 18/25; a reversed one given as current at most 2 | 23/25; 0/8 | 24/25; 0/8 | 23/25; 0/8 | 24/25; 0/8 | met |
| H6 | advice (F): the earlier mention used in at least 10/15 | 3/15 | 2/15 | 2/15 | 0/15 | missed |
| H7 | instructions (G): shown at session start for at least 9/12 real ones; an idiom shown as one at most 1 | 11/12; 0/3 | | | | met |
| H8 | false memories pooled over A-E: fewer than each other system, Fisher p<0.05 | 15/59 | 17/59 (p=0.84) | 17/59 (p=0.84) | 10/59 (p=0.37) | missed |

H5's first count is the in-force instruction or decision (17 class f) plus
the new one after a reversal (8 class b). Two pre-registered parts are
denominators of 17 rather than 25: part D holds 17 pasted items and 8 own
ones, and the hypothesis's "of 25" is read as of those 17.

Other counts, pooled over the set (`summary_audited.txt`): the new or true
state given 25/28 (plain retrieval 23, agentmemory 25, ai-memory 16,
p=0.01); control questions answered 57/81 (53, 52, 42; against ai-memory
p=0.02). The advice retrieval check: the answer's conversation in the top 5
for 15/15. Labels on part A: "may have changed since" once, on a current
line; no other label fired.

Not pre-registered: without part D the false memories are 1 of 42 for
sourcedrecall, 2 for plain retrieval and agentmemory, 7 for ai-memory. Part
D decides H8, and ai-memory's lower count there comes with 1 of 8 own items
answered.

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H4 (pasted text, 14 false memories). The pasted material was introduced
  in 12 of the 14 (in 2 only by a question after it) and not introduced in
  2; the planted item was an instruction in 7 and a claim about "I" in 7.
  In no case did sourcedrecall store it as a fact or a standing instruction:
  all 14 were in the block only as the quoted message. But the "pasted in,
  not the user's words" marker fired on 3 of the 14; in the other 11 the
  introduction and the pasted text were one quoted user line. The reader
  gave the item as the user's in all 14, including the 3 that were marked,
  in 7 of them while naming where it came from. ai-memory's 3 of 17 come
  from keeping only the first line of each message: the pasted text was in
  its returns 0 of 17 times, and its reader mostly said it did not know.
  Two things fail: detecting pasted text after an introduction in the same
  message, and a reader that ignores the marker.
- H6 (advice, 12 misses). The earlier mention was in the block in 12 of 12.
  Every miss was a refusal ("I don't know", "not enough information"),
  none a generic recommendation. sourcedrecall's advice instruction was in
  the block for 10 of the 15 (the advice pattern missed 5), but the fair
  protocol's shared reader instruction, given after it to every system,
  ends "If the memory does not answer the question, say you don't know",
  and the reader followed that. Plain retrieval fell the same way (2/15,
  against 8/10 on v5 without the shared instruction). As run, this measures
  the protocol's instruction as much as the memory; it stays a miss.
- H1 (plans, 4 misses). Both the earlier state and the plan were in the
  block in 4 of 4. The answer said it did not know in 2, treated the plan
  as done in 1, and in 1 described both correctly without the expected
  word. All 4 are among plain retrieval's 6 misses. "No longer true" never
  fired on part A, which is the half of H1 the rules control.
- H8 follows from H4: 14 of sourcedrecall's 15 false memories are part D.
- Part G answers (not a hypothesis; H7 is the session-start check): 6
  misses of 15, of which 5 are strict-match misses with a right answer
  (a plural, answering in the language instead of naming it, and 3 "I
  don't know" where the expected answer was "none") and 1 a vague answer.

Any fix for these is measured on a different set.
