# Held-out set v10: results

Pre-registered in `docs/PREREG_HELDOUT_V10.md` (approved by JP and committed
before the set existed, 34cbcf7). The set (`cases_v10.jsonl`, 120 scenarios
in parts D, U, B, X) was written by an agent barred from the rules, the
development sets, the earlier held-out sets and the history, and has not
been read by the developer. One run on 34cbcf7 (no product code changed
since the pre-registration; the product files are those of 8473783),
2026-10-11, under the v7 protocol: every system's memory to the same local
Qwen3-14B reader with the same instruction, the judge (the same model) given
the question, strict scoring, then a blinded audit by an agent that saw no
system names (240 rows, 6 overrides, `audit_overrides_v10.json`: plain
retrieval 3, agentmemory 2, sourcedrecall 1). All four systems ran on every
scenario with no errors.

Five of six hypotheses met, one missed.

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 6/40; own material at least 15/20 | 3/40; 13/20 | 23/40; 19/20 | 20/40; 16/20 | 0/40; 2/20 | missed (own material) |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 3/40 | 23/40 (p=2e-6) | 20/40 (p=4e-5) | | met |
| H3 | facts in pasted text (U): at least 16/20, at least 7/10 in each half | 17/20; named 9/10, not named 8/10 | 20/20 | 8/20 | 1/20 | met |
| H4 | changes (B): the old state given as current at most 3/20 | 1/20 | 3/20 | 0/20 | 7/20 | met |
| H5 | everyday (X): facts answered at least 15/20 | 18/20 | 18/20 | 18/20 | 14/20 | met |
| H6 | false memories pooled over D and B: fewer than plain retrieval and agentmemory, Fisher p<0.05 | 4/60 | 26/60 (p=4e-6) | 20/60 (p=4e-4) | 7/60 | met |

Pasted claims or instructions given as the user's, across the five
held-out sets: v6 82% (14/17), v7 32% (11/34), v8 22% (9/40), v9 10%
(4/40), v10 8% (3/40). Plain retrieval: 88%, 71%, 40%, 55%, 58%. ai-memory
keeps only the first line of each message: 0/40, with 2 of 20 own items and
1 of 20 pasted facts answered.

Own material answered: 13 of 20 against plain retrieval's 19 (p=0.04) and
agentmemory's 16 (p=0.48).

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H1, own material (7 of 20 not answered). In 6 the fact was in the block
  and the reader said it did not know: in 5 the text was shown as the
  user's own words (not marked as pasted), in 1 it was marked as pasted and
  the fact was shown. In 1 the user's own text was taken for pasted and the
  fact was left out as the writer's details. In 6 of the 7 the user had
  said the text was theirs. Plain retrieval had the fact in all 7. Of the 20
  own items, 4 were marked as pasted (v9: 6 of 20), 2 of them with
  something left out.
- H3, facts in pasted text (3 of 20 not answered). 1: a message of 1,666
  characters not marked as pasted, cut to the 800-character window with the
  fact near character 1,500, outside it. 1: the fact was a credential and
  the secret filter replaced it. 1: answered correctly, with the time
  written differently from the expected term. Of the 12 pastes over 800
  characters with the fact past character 600 (by the auditor's count; the
  set's writer counted 13), 11 were answered (v9: the 7 long pastes were
  all missed).

So the two costs v9 found are mostly gone on a new set: facts deep in long
pastes are answered (17 of 20, long ones 11 of 12), and own text taken for
pasted lost its fact once (v9: 4). Own material is still below target, now
for a different reason: with the fact in front of it, the reader said it did
not know in 6 of 7 misses, while the same reader given plain retrieval's
lines answered 19 of 20. Why it refuses on sourcedrecall's block is not yet
known; any fix is measured on a different set.
