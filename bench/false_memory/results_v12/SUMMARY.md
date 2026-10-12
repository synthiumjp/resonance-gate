# Held-out set v12: results

Pre-registered in `docs/PREREG_HELDOUT_V12.md` (approved by JP and committed
before the set existed, 27fd77f). The set (`cases_v12.jsonl`, 160
scenarios in parts D, R, U, B, X; committed at 20b1acb, no product code
changed since the pre-registration) was written by an agent barred from the
rules, the development sets, the earlier held-out sets and their audit
categories, and has not been read by the developer. Part R holds 30 public
Enron emails from a pool of 150 drawn with a fixed seed, read by the
developer as counts only. One run, 2026-10-13, 08:18 to 09:29, on the Mac,
under the v7 protocol (every system's memory to the same reader with the
same instruction, the judge Qwen3-14B given the question, strict scoring),
read by Qwen3-14B (a second llama_cpp.server instance with the same model
file, flags and build as before, on port 8092, because the first was busy
with HaluMem's scorer) and by Phi-4 14B. All four systems ran on every
scenario with no errors.

One blinded audit per reader, by an agent that saw no system names:

- Qwen3-14B: 320 rows, 10 overrides, all judge misses of a false memory
  (`audit_overrides_v12.json`: plain retrieval +4, agentmemory +3,
  sourcedrecall +2, ai-memory +1).
- Phi-4: 320 rows, 18 overrides, all judge misses of a false memory
  (`audit_overrides_v12_phi4.json`: agentmemory +7, plain retrieval +6,
  sourcedrecall +5).

The figures below are after the audit (`tests_audited.txt`,
`parts_audited.txt`); the judge's own are in `tests.txt`.

Seven of eleven hypotheses met with the first reader. H1, H4, H10 and H11
missed; with the second reader H1, H4 and H10 are missed, so H9 is missed.

## First reader (Qwen3-14B)

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 6/40 | 12/40 | 28/40 | 35/40 | 8/40 | missed |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 12/40 | p=7e-4 (Holm 0.002) | p=2e-7 (Holm 1e-6) | | met |
| H3 | own material (D): answered at least 25/30 | 25/30 | 29/30 | 30/30 | 11/30 | met |
| H4 | own material: no more than 3 of 30 fewer than plain retrieval | 4 fewer (p=0.19) | | | | missed |
| H5 | facts in pasted text (U): at least 16/20, at least 7/10 in each half | 19/20; named 10/10, not named 9/10 | 20/20 | 10/20 | 3/20 | met |
| H6 | changes (B): the old state given as current at most 3/20 | 1/20 | 0/20 | 0/20 | 1/20 | met |
| H7 | everyday (X): facts answered at least 15/20 | 19/20 | 19/20 | 19/20 | 14/20 | met |
| H8 | false memories pooled over D and B: fewer than plain retrieval and agentmemory, Fisher p<0.05 | 13/60 | 28/60 (p=0.007, Holm 0.013) | 35/60 (p=8e-5, Holm 3e-4) | 9/60 | met |
| H10 | real emails (R): a real writer's claim given as the user's at most 6/20 | 7/20 | 14/20 | 12/20 | 2/20 | missed |
| H11 | real emails: fewer than plain retrieval, Fisher p<0.05 | 7/20 | 14/20 (p=0.056, Holm 0.056) | | | missed |
| H12 | real own emails: answered at least 7/10 | 10/10 | 10/10 | 7/10 | 0/10 | met |

Reported, not tested: the user's own writing brought to be read over
(subtype `D_read_`, 17 of the 30 own items) answered 15/17 (plain
retrieval 17/17, agentmemory 17/17, ai-memory 5/17).

## Second reader (Phi-4), H9

| | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|
| H1 pasted given as the user's (at most 6/40) | 13/40 | 32/40 | 35/40 | 9/40 | missed |
| H2 against plain retrieval and agentmemory (reported) | | p=4e-5 (Holm 1e-4) | p=8e-7 (Holm 4e-6) | | |
| H3 own material answered (at least 25/30) | 26/30 | 30/30 | 30/30 | 18/30 | holds |
| H4 no more than 3 fewer than plain retrieval | 4 fewer (p=0.11) | | | | missed |
| H10 real emails given as the user's (at most 6/20) | 7/20 | 14/20 | 11/20 | 3/20 | missed |
| facts in pasted text (U) | 19/20 | 20/20 | 10/20 | 3/20 | |
| changes (B), old state as current | 1/20 | 0/20 | 0/20 | 0/20 | |
| everyday (X) | 19/20 | 19/20 | 19/20 | 19/20 | |
| pooled false memories, D and B | 14/60 | 32/60 | 35/60 | 9/60 | |
| real own emails answered | 10/10 | 10/10 | 7/10 | 0/10 | |
| own writing brought to be read over | 15/17 | 17/17 | 17/17 | 9/17 | |

## Said it did not know (reported, not tested)

| | sourcedrecall | plain retrieval | agentmemory | ai-memory |
|---|---|---|---|---|
| D pasted claims (40), Qwen3-14B / Phi-4 | 26 / 27 | 11 / 5 | 3 / 3 | 31 / 25 |
| D own material (30), Qwen3-14B / Phi-4 | 4 / 4 | 1 / 0 | 0 / 0 | 17 / 10 |
| R real pasted (20), Qwen3-14B / Phi-4 | 13 / 12 | 6 / 3 | 8 / 6 | 18 / 16 |
| R real own (10), Qwen3-14B / Phi-4 | 0 / 0 | 0 / 0 | 1 / 1 | 10 / 8 |

## Detection alone (counts, no model)

On this set's pasted items, the frozen v11 code and the v12 code mark the
same number as pasted: part D 26 of 40 pasted texts found by both, 26 of 30
own texts kept by both; part R 13 (v11 code) and 15 (v12 code) of 20
pasted found, 10 of 10 own kept by both. So the rise in pasted claims
given as the user's from v11 (5/40) to v12 (12/40) is not a regression
from the changes after v11; v12's pasted texts come in shapes the
detection did not mark, in a third of part D.

## Across the held-out sets

Pasted claims or instructions given as the user's (part D, Qwen3-14B,
audited): v6 82% (14/17), v7 32% (11/34), v8 22% (9/40), v9 10% (4/40),
v10 8% (3/40), v11 13% (5/40), v12 30% (12/40). Plain retrieval: 88%, 71%,
40%, 55%, 58%, 58%, 70%. Own material answered: v10 13/20, v11 24/30, v12
25/30 (plain retrieval 19, 30, 29).

## What the audit found behind the misses (categories, counts)

An agent read the misses (judge verdicts before the audit) and reported
categories and counts.

- Part D, pasted (Qwen 11, Phi-4 10 false memories, 10 the same items).
  12 of the 40 pasted texts were not marked as pasted at all; 10 of those
  became false memories with Qwen, 9 with Phi-4. How they came in: an
  introduction before the text naming the source, in the same message (4:
  a text message, a networking message, a community rules list with an
  instruction, a transcript with speaker labels); an introduction after
  the text in the same message (2); the source said only in a later
  message (3); no introduction, only a header inside the text (1). The
  other 28 were marked (about 19 with the writer's sentences about
  themselves left out, 9 withheld whole); 1 marked item per reader was
  still given as the user's, where the claim stayed visible inside the
  marked snippet.
- Part D, own (Qwen 5, Phi-4 4 not answered, 4 the same). In those 4 the
  user's own writing (a caption, a blog post, a text they had sent, a
  letter they signed) was marked as someone else's and the fact cut, though
  each carried an ownership cue or the user's signature. The fifth (Qwen
  only) was unmarked with the fact shown: a reader error.
- Part R, real emails (Qwen 6, Phi-4 5 before the audit). 5 of the 20
  pasted emails were not marked; all 5 were false memories with Qwen, 4
  with Phi-4: the source said in the next message in words the rule does
  not read ("the note above is from ..."), an introduction that announces
  the paste ahead of time, a first-person bio introduced as someone
  else's, and an email with no source at all. One marked item per reader
  was given as the user's with the claim visible in the snippet.

So the misses are mostly detection: texts whose source the user named, in
the same message or the next one, in words or positions the rules do not
read; and, more rarely, the user's own writing taken for someone else's.
One false memory per reader in D, and one in R, came from a marked text
whose claim stayed visible in the shown snippet.

The analysing agent's report quoted a few specific details of the set
(two short phrases and the kinds of some texts) beyond the categories
asked for; the developer has read them. Nothing in the counts depends on
it, and the set is spent.

## Files

- `results_v12/` (Qwen3-14B) and `results_v12_phi4/`: the systems' returns
  (`raw_*`), the answers, the judge log, `probe_details.jsonl`, the scores
  before (`tests.txt`, `parts.txt`) and after the audit (`*_audited*`).
- `audit_results_v12/`, `audit_results_v12_phi4/`: packets, keys and the
  auditors' decisions. The Mac home directory is written as `~/`.
