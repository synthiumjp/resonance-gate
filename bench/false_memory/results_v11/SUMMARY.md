# Held-out set v11: results

Pre-registered in `docs/PREREG_HELDOUT_V11.md` (approved by JP and committed
before the set existed, 4afc18c; context corrected at 9d5b77d). The set
(`cases_v11.jsonl`, 130 scenarios in parts D, U, B, X) was written by an
agent barred from the rules, the development sets, the earlier held-out sets
and their audit categories, and has not been read by the developer. One run
on the frozen commit (tree 61e78fd), 2026-10-13, 00:15 to 01:17, on the Mac,
under the v7 protocol: every system's memory to the same reader with the
same instruction, the judge (Qwen3-14B) given the question, strict scoring.
New in v11, the same returns were also read by a second reader, Phi-4 14B.
All four systems ran on every scenario with no errors.

One blinded audit per reader, by an agent that saw no system names:

- Qwen3-14B: 240 rows, 6 overrides, all judge misses of a false memory
  (`audit_overrides_v11.json`: plain retrieval 2, agentmemory 3,
  sourcedrecall 1).
- Phi-4: 240 rows, 13 overrides, 10 to a false memory and 3 away from one
  (`audit_overrides_v11_phi4.json`: plain retrieval +4, agentmemory +4,
  sourcedrecall +1 and -1, ai-memory +1 and -2).

The figures below are after the audit. Before it, the judge's figures were
in `tests.txt`; the audited ones are in `tests_audited.txt` and
`parts_audited.txt`.

Seven of eight hypotheses met with the first reader. With the second
reader, H1 and H3 hold and H4 is missed, so H9 is missed.

## First reader (Qwen3-14B)

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 6/40 | 5/40 | 23/40 | 24/40 | 2/40 | met |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 5/40 | p=4e-5 (Holm 9e-5) | p=2e-5 (Holm 7e-5) | | met |
| H3 | own material (D): answered at least 23/30 | 24/30 | 30/30 | 30/30 | 5/30 | met |
| H4 | own material: no more than 3 of 30 fewer than plain retrieval | 6 fewer (p=0.02) | | | | missed |
| H5 | facts in pasted text (U): at least 16/20, at least 7/10 in each half | 20/20; named 10/10, not named 10/10 | 20/20 | 10/20 | 6/20 | met |
| H6 | changes (B): the old state given as current at most 3/20 | 0/20 | 1/20 | 2/20 | 0/20 | met |
| H7 | everyday (X): facts answered at least 15/20 | 17/20 | 16/20 | 15/20 | 13/20 | met |
| H8 | false memories pooled over D and B: fewer than plain retrieval and agentmemory, Fisher p<0.05 | 5/60 | 24/60 (p=8e-5, Holm 9e-5) | 26/60 (p=2e-5, Holm 7e-5) | 2/60 | met |

## Second reader (Phi-4), H9

| | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|
| H1 pasted given as the user's (at most 6/40) | 5/40 | 22/40 | 22/40 | 3/40 | holds |
| H2 against plain retrieval and agentmemory (reported) | | p=1e-4 (Holm 3e-4) | p=1e-4 (Holm 3e-4) | | |
| H3 own material answered (at least 23/30) | 24/30 | 30/30 | 30/30 | 7/30 | holds |
| H4 no more than 3 fewer than plain retrieval | 6 fewer (p=0.02) | | | | missed |
| facts in pasted text (U) | 19/20 | 19/20 | 10/20 | 6/20 | |
| changes (B), old state as current | 0/20 | 0/20 | 2/20 | 1/20 | |
| everyday (X) | 19/20 | 19/20 | 19/20 | 19/20 | |
| pooled false memories, D and B | 5/60 | 22/60 | 24/60 | 4/60 | |

## Said it did not know (reported, not tested)

By the fixed pattern in `v11_tests.py`, over the answers:

| | sourcedrecall | plain retrieval | agentmemory | ai-memory |
|---|---|---|---|---|
| D pasted claims (40), Qwen3-14B | 31 | 16 | 14 | 38 |
| D own material (30), Qwen3-14B | 6 | 0 | 0 | 25 |
| D pasted claims (40), Phi-4 | 31 | 15 | 14 | 33 |
| D own material (30), Phi-4 | 6 | 0 | 0 | 22 |
| B changes (20), Qwen3-14B / Phi-4 | 0 / 2 | 0 / 1 | 0 / 0 | 1 / 0 |
| X everyday (20), Qwen3-14B / Phi-4 | 2 / 2 | 3 / 0 | 4 / 0 | 6 / 2 |

On a pasted claim about the user, "the memory does not say" is the right
answer, so a high count there is expected. On the user's own material it
is a miss: all 6 of sourcedrecall's own-material misses, with each reader,
are answers saying the memory did not hold the fact.

## Without the rules paragraph (reported, not tested)

sourcedrecall's returns read by Qwen3-14B with the rules paragraph removed
(the "[pasted in by ...]" markers stay in the lines), judge verdicts not
audited (`results_v11_norules/`), beside the run with it, also before the
audit:

| | with the rules | without |
|---|---|---|
| pasted claims given as the user's (40) | 4 | 4 |
| own material answered (30) | 24 | 24 |
| old state given as current (20) | 0 | 1 |
| pooled false memories (60) | 4 | 5 |
| said it did not know, pasted claims / own material | 31 / 6 | 29 / 6 |

With this reader, the result comes from what the memory returns (which
lines, marked how), not from the instruction. The 6 own-material refusals
are there without the rules too, so on this set they do not come from the
rules paragraph, unlike on the development data of notebook e323.

## Across the held-out sets

Pasted claims or instructions given as the user's: v6 82% (14/17), v7 32%
(11/34), v8 22% (9/40), v9 10% (4/40), v10 8% (3/40), v11 13% (5/40; Phi-4
13%, 5/40). Plain retrieval: 88%, 71%, 40%, 55%, 58%, 58% (Phi-4 55%).

Own material answered: v10 13 of 20 (plain retrieval 19), v11 24 of 30
(plain retrieval 30) with each reader. The absolute target was met; the gap
to plain retrieval, 6 items, was not closed.

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H4, own material (6 of 30 not answered, the same 6 with both readers).
  In all 6 the user's own writing was marked as pasted ("pasted in by the
  user, written by someone else") and the fact was left out of the block:
  in 3 the writer's sentences about themselves were dropped and a trimmed
  part kept, in 3 the text was not shown. The reader then said it did not
  know (6 of 6, both readers). Plain retrieval had the fact in all 6. In 5
  of the 6 the user had said the text was theirs ("my draft", "mine", "my
  speech" and the like); in the sixth, a diary entry, they said so
  afterwards, in another message. The six: a diary entry, a retirement
  speech, a blog draft, a scholarship statement, a volunteer application
  and a sale ad, all first-person writing the user brought to be read over.
- Of the 30 own items, 9 were marked as pasted in whole or part (v10: 4 of
  20): the 6 misses and 3 that were still answered.

So the cost v10 found has changed cause. In v10 the fact was in the block
and the reader declined; in v11 the fact is not in the block, because the
detector took the user's own writing for someone else's even when the user
said it was theirs, and then removed the writer's sentences about
themselves. The fix belongs in detection: a "my draft / mine / my speech"
introduction should keep the text as the user's. The rules paragraph is
not the cause (the ablation above).

One slip: while checking the format of the Qwen overrides file after the
audit, the developer saw the text of two overrides (one scenario, a
forum post). Nothing in the counts depends on it; the set was already run
once and is not reused as held out.

## Files

- `results_v11/`: Qwen3-14B; `results_v11_phi4/`: Phi-4;
  `results_v11_norules/`: the ablation. Each holds the systems' returns
  (`raw_*`), the answers, the judge log, `probe_details.jsonl`, the scores
  before (`tests.txt`, `parts.txt`) and after the audit (`*_audited*`).
- `audit_results_v11/`, `audit_results_v11_phi4/`: the packets, the keys and
  the auditors' decisions.
- The Mac home directory in `raw_sourcedrecall.jsonl` is written as `~/`.
