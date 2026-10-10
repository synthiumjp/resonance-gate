# Held-out set v8: results

Pre-registered in `docs/PREREG_HELDOUT_V8.md` (approved by JP and committed
before the set existed, dd189d3). The set (`cases_v8.jsonl`, 100 scenarios
in parts D, B, X) was written by an agent barred from the rules, the
development sets and the history, and has not been read by the developer.
One run on dd189d3 (no product code changed since the pre-registration),
2026-10-10, under the v7 protocol: every system's memory to the same local
Qwen3-14B reader with the same instruction, the judge (the same model) given
the question, strict scoring, then a blinded audit by an agent that saw no
system names (240 rows, 1 override, `audit_overrides_v8.json`). All four
systems ran on every scenario with no errors.

Two of five hypotheses met, three missed.

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 6/40; own material at least 15/20 | 9/40; 16/20 | 16/40; 19/20 | 20/40; 19/20 | 2/40; 5/20 | missed |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 9/40 | 16/40 (p=0.15) | 20/40 (p=0.02) | | missed |
| H3 | changes (B): the old state given as current at most 3/20 | 2/20 | 2/20 | 2/20 | 2/20 | met |
| H4 | everyday (X): facts answered at least 15/20 | 18/20 | 19/20 | 18/20 | 14/20 | met |
| H5 | false memories pooled over D and B: fewer than plain retrieval and agentmemory, Fisher p<0.05 | 11/60 | 18/60 (p=0.20) | 22/60 (p=0.04) | 4/60 | missed |

Pasted claims or instructions given as the user's, across the three
held-out sets: v6 82% (14/17), v7 32% (11/34), v8 22% (9/40). Plain
retrieval: 88%, 71%, 40%; this set's pasted text misled every system less.
ai-memory keeps only the first line of each message: 2/40 with 5 of 20 own
items answered.

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H1 (9 false memories). The "pasted in" marker fired on 24 of the 40
  pasted items; 4 of those 24 were still given as the user's, 3 of them
  instructions the reader followed as the user's rules despite "(the writer
  asks)". 5 were never marked, all first-person claims in a paste of one
  paragraph: the introduction on the same line (2), after one line break
  (1, where the introduction itself had been removed by the secret filter
  as "[secret removed]"), after the paste (1), none (1). Of the 31 pasted
  items that were not false memories, 20 were marked and 11 unmarked but
  answered "I don't know". 7 of the 9 were also wrong for plain retrieval.
  Own material (4 misses): 2 wrongly marked as pasted, 2 refusals.
- H3 (2): both the old and the new line in the block; the reader answered
  from the old.
- H4 (2): the fact in the block, the reader said it did not know.

So on unseen text the marker now fires on most pasted material; what is
left is one-paragraph pastes with the introduction on the same line or
none, pasted instructions the reader follows even when marked, and a secret
filter that removes an introduction. Any fix is measured on a different set.
