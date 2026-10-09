# Held-out set v7: results

Pre-registered in `docs/PREREG_HELDOUT_V7.md` (reviewed by JP and committed
before the set existed, 86e2f01). The set (`cases_v7.jsonl`, 140 scenarios
in parts D, F, A, B, X) was written by an agent barred from the rules, the
pasted-text development set and the history, and has not been read by the
developer. One run on 86e2f01 (no product code changed since the
pre-registration), 2026-10-10, under the fair protocol with v7's shared
reader instruction (`FM_SAME_V7`): every system's memory to the same local
Qwen3-14B reader, the judge (the same model) given the question, strict
scoring, then a blinded audit by an agent that saw no system names (256
rows; 3 overrides, `audit_overrides_v7.json`). All four systems ran on
every scenario with no errors.

Two of seven hypotheses met, five missed.

| | hypothesis | sourcedrecall | plain retrieval | agentmemory | ai-memory | |
|---|---|---|---|---|---|---|
| H1 | pasted (D): a pasted claim or instruction given as the user's at most 4/34; own material at least 12/16 | 11/34; 13/16 | 24/34; 15/16 | 26/34; 14/16 | 2/34; 4/16 | missed |
| H2 | pasted (D): fewer than plain retrieval and agentmemory, Fisher p<0.05 | 11/34 | 24/34 (p<0.01) | 26/34 (p<0.01) | | met |
| H3 | advice (F): the mention used at least 12/20; an irrelevant mention applied at most 2/10 | 11/20; 0/10 | 7/20; 2/10 | 4/20; 0/10 | 3/20; 0/10 | missed |
| H4 | plans (A): the earlier state given as no longer current at most 3/20 | 9/20 | 7/20 | 5/20 | 12/20 | missed |
| H5 | changes (B): the old state given as current at most 3/20 | 0/20 | 3/20 | 1/20 | 1/20 | met |
| H6 | everyday (X): facts answered at least 17/20 | 15/20 | 15/20 | 15/20 | 13/20 | missed |
| H7 | false memories pooled over D, A, B: fewer than each, Fisher p<0.05 | 11/54 | 27/54 (p<0.01) | 27/54 (p<0.01) | 3/54 (p=0.04, fewer) | missed |

H4 counts an answer without the earlier state as "given as no longer
current", as pre-registered; most were refusals (below). ai-memory keeps
only the first line of each message, so pasted text rarely reaches its
reader: its low part D count comes with 4 of 16 own items answered.

Against v6 (pasted claim or instruction given as the user's 14 of 17,
plain retrieval and agentmemory 15), the fix after v6 lowered the rate from
82% to 32%; plain retrieval and agentmemory were at 71% and 76% here.

## What the audit found behind the misses (categories, counts)

An agent read the misses and reported categories and counts only.

- H1 (pasted, 11 false memories). Where the "pasted in" marker fired, the
  reader almost never took the text for the user's: all 23 pasted items
  that did not become false memories were marked, and of the 11 that did,
  1 was marked. The other 10 were never detected: in 6 the introduction
  stood on its own line before a blank line, in 4 it came only after the
  pasted text; chat logs or transcripts 3, documents or bios 3, a text
  message, a social post, a letter to translate, a quotation. 7 were
  first-person claims, 4 instructions or rules. Own material (3 misses): 2
  wrongly marked as pasted (a post the user wrote, and the user's own fact
  after a quoted message), 1 a refusal. Detection, not presentation, is
  what fails on unseen text: the introductions were worded in ways the
  rules do not list.
- H3 (advice, 9 misses). The mention was in the block in 9 of 9; all 9
  answers were "I don't know" or no recommendation. 5 were requests that
  do not name the link. Plain retrieval missed all 9 too (13 in total).
- H4 (plans, 9 misses). The earlier state and the plan were in the block
  in 9 of 9; 7 answers were "I don't know", 2 reported the plan instead of
  the state; none treated the plan as done. No change label was on the
  earlier line in any of the 9. Plain retrieval missed 7 (5 the same).
- H6 (everyday, 5 misses). The fact was in the block in 4; 3 refusals (2
  with the fact in the block), 2 right answers worded with another form of
  the expected word. Plain retrieval missed 4 of the same 5.
- H7 follows from H1 and ai-memory's first-line-only storage.

So the reader's caution ("I don't know" when the fact is there) costs more
answers than missing memories in parts F, A and X, for sourcedrecall and
plain retrieval alike, and pasted-text detection, not its presentation, is
what remains of part D. Any fix for these is measured on a different set.
