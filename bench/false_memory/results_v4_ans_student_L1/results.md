## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 16% [7-27] (7/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 16% [7-27] (7/44) |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 68% [55-82] (30/44) | 100% [100-100] (44/44) | 89% [77-98] (39/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 82% [70-93] (36/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 16% [7-27] (7/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | 82% [70-93] (36/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 91% [82-98] (40/44) | 16% [7-27] (7/44) |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 68% [55-82] (30/44) | 100% [100-100] (44/44) | 89% [77-98] (39/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 75% [61-86] (33/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 89% [80-98] (39/44) | 16% [7-27] (7/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | 75% [61-86] (33/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 89% [80-98] (39/44) | 16% [7-27] (7/44) |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 68% [55-82] (30/44) | 100% [100-100] (44/44) | 89% [77-98] (39/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 75% [61-86] (33/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 89% [80-98] (39/44) | 16% [7-27] (7/44) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | 75% [61-86] (33/44) | 86% [75-95] (38/44) | 9% [2-18] (4/44) | 89% [80-98] (39/44) | 16% [7-27] (7/44) |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 68% [55-82] (30/44) | 100% [100-100] (44/44) | 89% [77-98] (39/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 132 | 104 | 0.788 | 85.0 | 0.644 |
| rag | 132 | 104 | 0.788 | 0.9 | 0.007 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
