## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 33% [22-45] (20/60) | 40% [28-52] (24/60) | 8% [2-15] (5/60) | 65% [53-77] (39/60) | 38% [27-50] (23/60) | 92% [85-98] (55/60) | 43% [30-57] (26/60) | 38% [27-50] (23/60) | 8% [2-17] (5/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 75% [55-90] (15/20) | 90% [75-100] (18/20) | 10% [0-25] (2/20) | 75% [55-90] (15/20) | 15% [0-30] (3/20) | 95% [85-100] (19/20) | 10% [0-25] (2/20) | 90% [75-100] (18/20) | 20% [5-40] (4/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 12% [2-22] (5/40) | 15% [5-28] (6/40) | 8% [0-18] (3/40) | 60% [45-75] (24/40) | 50% [35-65] (20/40) | 90% [80-98] (36/40) | 60% [45-75] (24/40) | 12% [2-22] (5/40) | 2% [0-8] (1/40) |
| CONTROL RECALL, class f (higher is better) | 52% [38-65] (31/60) | 82% [72-92] (49/60) | 68% [57-80] (41/60) | 95% [88-100] (57/60) | 88% [80-97] (53/60) | 80% [70-90] (48/60) | 73% [62-83] (44/60) | 52% [38-65] (31/60) | 25% [15-37] (15/60) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 55% [35-75] (11/20) | 95% [85-100] (19/20) | 70% [50-90] (14/20) | 80% [60-95] (16/20) | 50% [30-70] (10/20) | 95% [85-100] (19/20) | 60% [40-80] (12/20) | 95% [85-100] (19/20) | 35% [15-55] (7/20) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 33% [22-45] (20/60) | 40% [28-52] (24/60) | 10% [3-18] (6/60) | 65% [53-77] (39/60) | 40% [28-52] (24/60) | 92% [85-98] (55/60) | 48% [35-62] (29/60) | 38% [27-50] (23/60) | 10% [3-18] (6/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 75% [55-90] (15/20) | 90% [75-100] (18/20) | 10% [0-25] (2/20) | 75% [55-90] (15/20) | 10% [0-25] (2/20) | 95% [85-100] (19/20) | 10% [0-25] (2/20) | 90% [75-100] (18/20) | 15% [0-30] (3/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 12% [2-22] (5/40) | 15% [5-28] (6/40) | 10% [2-20] (4/40) | 60% [45-75] (24/40) | 55% [40-70] (22/40) | 90% [80-98] (36/40) | 68% [52-82] (27/40) | 12% [2-22] (5/40) | 8% [0-18] (3/40) |
| CONTROL RECALL, class f (higher is better) | 52% [38-65] (31/60) | 82% [72-92] (49/60) | 68% [57-80] (41/60) | 95% [88-100] (57/60) | 88% [80-97] (53/60) | 80% [70-90] (48/60) | 73% [62-83] (44/60) | 52% [38-65] (31/60) | 25% [15-37] (15/60) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 55% [35-75] (11/20) | 95% [85-100] (19/20) | 70% [50-90] (14/20) | 80% [60-95] (16/20) | 50% [30-70] (10/20) | 95% [85-100] (19/20) | 60% [40-80] (12/20) | 95% [85-100] (19/20) | 35% [15-55] (7/20) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 1911 | 0 | 0.0 | 261.9 | 0.137 |
| rag | 1911 | 1274 | 0.667 | 4.6 | 0.002 |
| agentmemory | 1911 | 0 | 0.0 | 142.7 | 0.075 |
| ai-memory | 1911 | 0 | 0.0 | 546.6 | 0.286 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
