## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 14% [5-25] (6/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 14% [5-25] (6/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 88% [69-100] (14/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 66% [52-80] (29/44) | 100% [100-100] (44/44) | 91% [82-98] (40/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 100% [100-100] (44/44) | 86% [75-95] (38/44) | 95% [89-100] (42/44) | 75% [61-86] (33/44) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 14% [5-25] (6/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 14% [5-25] (6/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 88% [69-100] (14/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 66% [52-80] (29/44) | 100% [100-100] (44/44) | 91% [82-98] (40/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 100% [100-100] (44/44) | 86% [75-95] (38/44) | 95% [89-100] (42/44) | 75% [61-86] (33/44) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 11% [2-23] (5/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 11% [2-23] (5/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 88% [69-100] (14/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 66% [52-80] (29/44) | 100% [100-100] (44/44) | 91% [82-98] (40/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 100% [100-100] (44/44) | 86% [75-95] (38/44) | 95% [89-100] (42/44) | 75% [61-86] (33/44) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 11% [2-23] (5/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 84% [73-93] (37/44) | 5% [0-11] (2/44) | 91% [82-98] (40/44) | 11% [2-23] (5/44) | 91% [82-98] (40/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 18% [7-30] (8/44) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 88% [69-100] (14/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) | 94% [81-100] (15/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 66% [52-80] (29/44) | 100% [100-100] (44/44) | 91% [82-98] (40/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 100% [100-100] (44/44) | 86% [75-95] (38/44) | 95% [89-100] (42/44) | 75% [61-86] (33/44) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 132 | 0 | 0.0 | 17.4 | 0.132 |
| rag | 132 | 104 | 0.788 | 0.9 | 0.007 |
| agentmemory | 132 | 0 | 0.0 | 69.5 | 0.527 |
| ai-memory | 132 | 0 | 0.0 | 112.5 | 0.852 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
