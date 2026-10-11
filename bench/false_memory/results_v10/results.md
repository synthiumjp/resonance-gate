## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 30% [18-42] (18/60) | 38% [27-52] (23/60) | 8% [2-17] (5/60) | 57% [45-70] (34/60) | 42% [30-55] (25/60) | 75% [63-85] (45/60) | 30% [18-42] (18/60) | 32% [20-43] (19/60) | 12% [3-20] (7/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 60% [40-80] (12/20) | 80% [60-95] (16/20) | 10% [0-25] (2/20) | 80% [60-95] (16/20) | 20% [5-40] (4/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 85% [70-100] (17/20) | 35% [15-55] (7/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 15% [5-28] (6/40) | 18% [8-30] (7/40) | 8% [0-18] (3/40) | 45% [30-60] (18/40) | 52% [38-68] (21/40) | 65% [50-80] (26/40) | 45% [30-60] (18/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) |
| CONTROL RECALL, class f (higher is better) | 60% [47-72] (36/60) | 93% [87-98] (56/60) | 80% [70-90] (48/60) | 98% [95-100] (59/60) | 95% [88-100] (57/60) | 78% [68-88] (47/60) | 70% [58-82] (42/60) | 32% [20-43] (19/60) | 28% [17-40] (17/60) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 85% [70-100] (17/20) | 80% [60-95] (16/20) | 75% [55-90] (15/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) | 85% [70-100] (17/20) | 35% [15-55] (7/20) |

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
| FALSE-MEMORY RATE, classes a-e (lower is better) | 30% [18-42] (18/60) | 38% [27-52] (23/60) | 7% [2-13] (4/60) | 57% [45-70] (34/60) | 43% [32-57] (26/60) | 75% [63-85] (45/60) | 33% [22-45] (20/60) | 32% [20-43] (19/60) | 12% [3-20] (7/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 60% [40-80] (12/20) | 80% [60-95] (16/20) | 5% [0-15] (1/20) | 80% [60-95] (16/20) | 15% [0-30] (3/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 85% [70-100] (17/20) | 35% [15-55] (7/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 15% [5-28] (6/40) | 18% [8-30] (7/40) | 8% [0-18] (3/40) | 45% [30-60] (18/40) | 57% [42-72] (23/40) | 65% [50-80] (26/40) | 50% [35-65] (20/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) |
| CONTROL RECALL, class f (higher is better) | 60% [47-72] (36/60) | 93% [87-98] (56/60) | 80% [70-90] (48/60) | 98% [95-100] (59/60) | 95% [88-100] (57/60) | 78% [68-88] (47/60) | 70% [58-82] (42/60) | 32% [20-43] (19/60) | 28% [17-40] (17/60) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 85% [70-100] (17/20) | 80% [60-95] (16/20) | 75% [55-90] (15/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) | 85% [70-100] (17/20) | 35% [15-55] (7/20) |

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
| sourcedrecall | 1419 | 0 | 0.0 | 283.9 | 0.2 |
| rag | 1419 | 805 | 0.567 | 4.9 | 0.003 |
| agentmemory | 1419 | 0 | 0.0 | 142.9 | 0.101 |
| ai-memory | 1419 | 0 | 0.0 | 508.1 | 0.358 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
