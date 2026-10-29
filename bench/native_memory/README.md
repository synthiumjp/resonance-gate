# Claude Code's memory, simulated

Claude Code keeps a memory folder per project: `MEMORY.md` and topic files
that Claude writes for itself. To compare it with sourcedrecall without
running Claude Code over thousands of conversations, `bench/claude_memory.py`
simulates it: after each session a writer model updates the folder,
following Claude Code's published memory guidance (save what will help
later, keep it short, update or delete what changed). The reader is then
given every file in the folder. Claude Code itself loads `MEMORY.md` and
opens other files only when it chooses, so this is generous to it.

Writers:
- LoCoMo and the false-memory sets: Claude Sonnet 5.5 through Anthropic's
  Batch API (2026-10-21; 1,269 calls for the false-memory sets).
- Coding sets: Claude Sonnet 5.5 as Claude Code subagents, a fresh agent
  every 9 sessions, on 10 of the 20 held-out repositories (2026-10-25); a
  Qwen3-14B writer on all 20, which kept far poorer folders (it wiped one
  repository's folder at session 25), labelled unfair to Claude Code's
  memory. Coding results: `bench/coding/results_v1/`,
  `docs/PREREG_CODING_V1.md`.
- Updated facts (FactConsolidation): Qwen3-14B only, labelled unfair:
  `bench/factcons/results_v1/heldout_run1_6ad96bb/`.

## LoCoMo

`locomo/memory_folders/` holds the folder the writer kept for each
conversation and speaker. Qwen3-14B read and judged every system:

| | sourcedrecall | Mem0 | plain retrieval | Claude Code's memory | both |
|---|---|---|---|---|---|
| multi-hop | 54.0% | 61.9% | 39.3% | 71.1% | 71.5% |
| temporal | 57.4% | 37.2% | 49.6% | 72.5% | 78.3% |
| open-domain | 36.1% | 41.0% | 38.6% | 50.6% | 53.0% |
| single-hop | 75.7% | 77.9% | 66.9% | 82.8% | 90.0% |
| overall | 65.6% | 64.6% | 56.6% | 76.6% | 81.9% |
| context tokens | 683 | 722 | 356 | 10,784 | about 11,470 |

sourcedrecall's column is from commit 012fcca (65.4% on 3671a09). "both" is
Claude Code's folder followed by sourcedrecall's block. Paired tests:
Claude Code's memory against sourcedrecall 284 to 140 (p<0.001); both
against Claude Code's memory 121 to 51 (p<0.001). `locomo/cm_test`,
`locomo/cm_both`.

With Claude Sonnet 5.5 reading (Qwen3-14B judging every system,
`locomo/cm_claude_reader`): sourcedrecall 77.2%, Mem0 70.9%, plain retrieval
69.6%, Claude Code's memory 86.5%. Claude Code's memory is ahead on every
kind of question with both readers.

## Pasted text (held-out sets v11, v12 and the real emails)

Qwen3-14B reading (`false_memory/results_cm_*_qwen`), with the 012fcca
returns of the other systems:

| | sourcedrecall | Claude Code's memory | plain retrieval |
|---|---|---|---|
| v11: pasted claims given as the user's, of 40 | 3 | 5 | 23 |
| v11: facts inside pasted text answered, of 20 | 20 | 15 | 20 |
| v11: the user's own pasted material answered, of 30 | 25 | 27 | 30 |
| v12: pasted claims given as the user's, of 40 | 8 | 11 | 28 |
| v12: real emails given as the user's, of 20 | 5 | 4 | 14 |
| v12: facts inside pasted text answered, of 20 | 19 | 11 | 20 |
| v12: the user's own pasted material answered, of 30 | 25 | 29 | 29 |
| v12: the user's own real emails answered, of 10 | 10 | 6 | 10 |
| real emails set: given as the user's, of 20 | 1 | 1 | 16 |
| real emails set: the user's own answered, of 10 | 9 | 3 | 10 |

With Claude Sonnet 5.5 reading (`false_memory/results_cmc_*`, the 53e0d9c
returns of the others): pasted claims given as the user's 0 and 1 of 40
for Claude Code's memory, 0 and 0 for sourcedrecall; facts inside pasted
text 15 and 11 of 20 against 20 and 19.

The writer's notes rarely take a pasted claim for the user's; what they
lose is the detail inside the pasted text and, on the real emails, the
user's own.
