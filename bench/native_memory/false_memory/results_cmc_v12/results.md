## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) | claude-memory | claude-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 31% [21-41] (25/80) | 28% [18-38] (22/80) | 1% [0-4] (1/80) | 80% [71-89] (64/80) | 5% [1-10] (4/80) | 84% [75-91] (67/80) | 9% [2-15] (7/80) | 41% [30-52] (33/80) | 5% [1-10] (4/80) | 11% [5-19] (9/80) | 6% [1-11] (5/80) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 70% [50-90] (14/20) | 80% [60-95] (16/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 5% [0-15] (1/20) | 20% [5-40] (4/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 18% [8-28] (11/60) | 10% [3-18] (6/60) | 0% [0-0] (0/60) | 73% [62-83] (44/60) | 5% [0-12] (3/60) | 78% [67-88] (47/60) | 10% [3-18] (6/60) | 23% [13-35] (14/60) | 7% [2-13] (4/60) | 13% [5-22] (8/60) | 2% [0-5] (1/60) |
| CONTROL RECALL, class f (higher is better) | 68% [57-78] (54/80) | 95% [90-99] (76/80) | 94% [89-99] (75/80) | 100% [100-100] (80/80) | 100% [100-100] (80/80) | 85% [78-92] (68/80) | 85% [78-92] (68/80) | 52% [41-64] (42/80) | 52% [41-64] (42/80) | 84% [75-91] (67/80) | 84% [75-91] (67/80) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 65% [45-85] (13/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) | claude-memory | claude-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) | claude-memory | claude-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 31% [21-41] (25/80) | 28% [18-38] (22/80) | 1% [0-4] (1/80) | 80% [71-89] (64/80) | 5% [1-10] (4/80) | 84% [75-91] (67/80) | 9% [2-15] (7/80) | 41% [30-52] (33/80) | 5% [1-10] (4/80) | 11% [5-19] (9/80) | 6% [1-11] (5/80) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 70% [50-90] (14/20) | 80% [60-95] (16/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 5% [0-15] (1/20) | 20% [5-40] (4/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 18% [8-28] (11/60) | 10% [3-18] (6/60) | 0% [0-0] (0/60) | 73% [62-83] (44/60) | 5% [0-12] (3/60) | 78% [67-88] (47/60) | 10% [3-18] (6/60) | 23% [13-35] (14/60) | 7% [2-13] (4/60) | 13% [5-22] (8/60) | 2% [0-5] (1/60) |
| CONTROL RECALL, class f (higher is better) | 68% [57-78] (54/80) | 95% [90-99] (76/80) | 94% [89-99] (75/80) | 100% [100-100] (80/80) | 100% [100-100] (80/80) | 85% [78-92] (68/80) | 85% [78-92] (68/80) | 52% [41-64] (42/80) | 52% [41-64] (42/80) | 84% [75-91] (67/80) | 84% [75-91] (67/80) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 65% [45-85] (13/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) | claude-memory | claude-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 1053 | 0 | 0.0 | 31.3 | 0.03 |
| rag | 1053 | 534 | 0.507 | 4.7 | 0.004 |
| agentmemory | 1053 | 0 | 0.0 | 187.7 | 0.178 |
| ai-memory | 1053 | 0 | 0.0 | 484.4 | 0.46 |
| claude-memory | 1053 | 517 | 0.491 | 1577.7 | 1.498 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
