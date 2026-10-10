# Held-out set v9: results

Pre-registered in `docs/PREREG_HELDOUT_V9.md` (approved by JP and committed
before the set existed, f3a166b). The set (`cases_v9.jsonl`, 120 scenarios
in parts D, U, B, X) was written by an agent barred from the rules, the
development sets and the history, and has not been read by the developer.
One run on f3a166b (no product code changed since the pre-registration),
2026-10-11, under the v7 protocol: every system's memory to the same local
Qwen3-14B reader with the same instruction, the judge (the same model) given
the question, strict scoring, then a blinded audit by an agent that saw no
system names (240 rows, 12 overrides, `audit_overrides_v9.json`). All four
systems ran on every scenario with no errors.

Four of six hypotheses met, two missed.

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 6/40; own material at least 15/20 | 4/40; 12/20 | 22/40; 17/20 | 27/40; 17/20 | 3/40; 1/20 | missed (own material) |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 4/40 | 22/40 (p=3e-5) | 27/40 (p=2e-7) | | met |
| H3 | facts in pasted text (U): at least 16/20, at least 7/10 in each half | 13/20; named 5/10, not named 8/10 | 20/20 | 9/20 | 1/20 | missed |
| H4 | changes (B): the old state given as current at most 3/20 | 2/20 | 2/20 | 2/20 | 3/20 | met |
| H5 | everyday (X): facts answered at least 15/20 | 16/20 | 16/20 | 18/20 | 13/20 | met |
| H6 | false memories pooled over D and B: fewer than plain retrieval and agentmemory, Fisher p<0.05 | 6/60 | 24/60 (p=3e-4) | 29/60 (p=6e-6) | 6/60 | met |

Pasted claims or instructions given as the user's, across the four
held-out sets: v6 82% (14/17), v7 32% (11/34), v8 22% (9/40), v9 10%
(4/40). Plain retrieval: 88%, 71%, 40%, 55%. ai-memory keeps only the first
line of each message: 3/40, with 1 of 20 own items and 1 of 20 pasted facts
answered.

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H3 (7 of 20 pasted facts not answered; 5 named, 2 not named). All 7 the
  same: the paste was marked as pasted, 838 to 1,167 characters long, the
  fact from character 651 to 992, and the part shown was the paste's start,
  so the fact was not in the block and the reader said it did not know.
  Plain retrieval had the fact in all 7. The window change made after v8
  (659d3f9: cut a long message around the sentence that best matches the
  question) did not pick the fact's sentence in these 7; 2 other long
  pastes with the fact near character 1,000 were answered.
- H1, own material (8 of 20 not answered). 4: the user's own text (notes, a
  resignation letter, a reply in a chat, a diary entry) was taken for
  pasted text, and the fact was in a part left out as the writer's own
  details (2) or not shown at all (2); this is the change made after v8
  (b76c3f5) acting on a wrong detection. 3: the fact in the block, the
  reader said it did not know. 1: answered, but in the plural where the
  expected term was singular.
  Of the 20 own items, 6 were marked as pasted.

So pasted claims given as the user's fell to 4 of 40, well below plain
retrieval and agentmemory, but two costs showed that the development sets
did not: long pastes lose the asked fact to the window, and own text taken
for pasted now loses its facts. Any fix is measured on a different set.
