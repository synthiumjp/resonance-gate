# Head-to-head: memory tools that store without a language model

2026-10-05. Two other open-source memory tools that, like sourcedrecall, make
no model calls when they store a conversation, run on the
false-memory sets with the same reader and judge as the published runs.

| | version | how a conversation was stored | what a question returns |
|---|---|---|---|
| [agentmemory](https://github.com/rohitg00/agentmemory) | 0.9.29 (npm), local embeddings (`EMBEDDING_PROVIDER=local`), no LLM key | as a Claude Code transcript with the conversation's date, through its own importer (`POST /agentmemory/replay/import-jsonl`) | its smart-search, top 5, each hit expanded to its full text |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | 2.5.2 (release binary), its local embedder, no LLM provider | as a Claude Code transcript with the conversation's date, through `ai-memory backfill --session` (its live hooks stamp the current time) | its MCP tool `memory_query`, top 5, then `memory_read_page` of each hit (cut at 1,500 characters) |
| sourcedrecall | the published runs (`results_v4_ans_mfg0`, `results_codebg_blind`, `results_proj2_blind`) | `profile_ingest` | the memory block |
| plain retrieval | the published runs | user messages | top 3 by bge-small |

A fresh store per scenario for every system. The reader (Qwen3-14B, or
Qwen3-4B where marked) answers each question from what the system returned;
the judge (Qwen3-14B) decides whether the answer states the out-of-date or
never-said proposition as currently true. Adapters:
`adapters_h2h.py`; runner: `run_system.py agentmemory|ai-memory`.

## Results

Superseded by the fair rerun of 2026-10-09 (`FAIR_RERUN.md`): same reader
instruction for every system, the judge given the question, a blinded audit.
The table below is kept as the record of the earlier run.

Caveats found by the adversarial review of 2026-10-09
(`docs/REVIEW_2026-10-09.md`), to be read before these numbers: the reader
got sourcedrecall's lines with the product's rules paragraph and the other
systems' lines without it (`answer.py`), so part of a difference may be the
instruction; only the projects false-memory row is a statistically clear
difference (Fisher p=0.002; v4 2 vs 5 p=0.43, coding 0 vs 2 p=0.50); these
sets were written for this project and have been run many times during
development; the judge does not see the question. A rerun with one
instruction for every system and a blinded audit replaces this table.

| | sourcedrecall | agentmemory | ai-memory | plain retrieval |
|---|---|---|---|---|
| changes of state: old state given as current (14B reader, of 44) | 2 | 5 | 7 | 7 |
| changes of state: new state given (14B, of 44) | 42 | 38 | 33 | 36 |
| changes of state: old state given as current (4B reader, of 44) | 2 | 6 | 11 | |
| things that did not change, answered (4B, of 16) | 16 | 12 | 14 | |
| coding sessions behind 120 others: false memories (of 51) | 0 | 2 | 6 | 3 |
| projects: false memories (of 32) | 0 | 9 | 4 | 3 |
| projects: unchanged facts answered (of 13) | 8 | 12 | 5 | 7 |

With the 14B reader every system answered all 16 unchanged things. Most of
agentmemory's project false memories are another project's fact offered as
true of this one: its search has no project filter. sourcedrecall's
project rows are the published run at an earlier commit, where it answered
8 of 13 unchanged facts; a later, unaudited run of a newer commit answered
10 of 13 (`results_ps_projblind`), which this table does not use.

The systems return different amounts: sourcedrecall its memory block,
agentmemory and ai-memory their top 5 results (ai-memory's pages cut at
1,500 characters), plain retrieval its top 3 messages. The table does not
equalise them.

## Audit

An agent read every answer of classes a-e for all four systems, both
directions (a judged false memory that is not one; a false memory the judge
passed), with one rule for all, and wrote the overrides to
`audit_overrides_{v4,code,projects}_h2h.json`. Changes: agentmemory 0 judge
errors and 2 missed; ai-memory 2 judge errors and 5 missed; sourcedrecall 1
judge error (4B reader) and 0 missed; plain retrieval none. The judge most
often missed bare one- or two-word answers naming the old value, and answers
listing the old item as part of a current set. Answers that open with
a present-tense "Yes" and then say the state ended were left as the judge
ruled for every system; under a stricter rule they would count for
agentmemory (3), ai-memory (1 or 2), sourcedrecall (1, 4B) and plain
retrieval (2).

## Caveats

The sets are synthetic and small (44 to 100 scenarios). Every number comes
from local models, the same for every system, so comparisons within a row
are fair but the scores are not comparable with results from other
set-ups. Each tool was run in the configuration it documents for local use
without an LLM; with an LLM provider both offer more (summaries,
consolidation), which these runs do not measure.
