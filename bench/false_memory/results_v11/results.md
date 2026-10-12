## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 27% [15-38] (16/60) | 35% [23-47] (21/60) | 7% [2-13] (4/60) | 68% [57-80] (41/60) | 37% [25-48] (22/60) | 78% [67-88] (47/60) | 38% [27-50] (23/60) | 42% [30-55] (25/60) | 3% [0-8] (2/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 65% [45-85] (13/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 95% [85-100] (19/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 10% [0-25] (2/20) | 100% [100-100] (20/20) | 0% [0-0] (0/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 8% [0-18] (3/40) | 5% [0-12] (2/40) | 10% [2-20] (4/40) | 55% [40-70] (22/40) | 52% [38-68] (21/40) | 68% [52-82] (27/40) | 52% [38-68] (21/40) | 12% [2-22] (5/40) | 5% [0-12] (2/40) |
| CONTROL RECALL, class f (higher is better) | 56% [44-67] (39/70) | 91% [84-97] (64/70) | 87% [79-94] (61/70) | 100% [100-100] (70/70) | 94% [89-99] (66/70) | 86% [77-93] (60/70) | 79% [69-87] (55/70) | 49% [37-60] (34/70) | 34% [24-46] (24/70) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 100% [100-100] (20/20) | 90% [75-100] (18/20) |

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
| FALSE-MEMORY RATE, classes a-e (lower is better) | 27% [15-38] (16/60) | 35% [23-47] (21/60) | 8% [2-17] (5/60) | 68% [57-80] (41/60) | 40% [28-53] (24/60) | 78% [67-88] (47/60) | 43% [32-57] (26/60) | 42% [30-55] (25/60) | 3% [0-8] (2/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 65% [45-85] (13/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 95% [85-100] (19/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 10% [0-25] (2/20) | 100% [100-100] (20/20) | 0% [0-0] (0/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 8% [0-18] (3/40) | 5% [0-12] (2/40) | 12% [2-22] (5/40) | 55% [40-70] (22/40) | 57% [42-72] (23/40) | 68% [52-82] (27/40) | 60% [45-75] (24/40) | 12% [2-22] (5/40) | 5% [0-12] (2/40) |
| CONTROL RECALL, class f (higher is better) | 56% [44-67] (39/70) | 91% [84-97] (64/70) | 87% [79-94] (61/70) | 100% [100-100] (70/70) | 94% [89-99] (66/70) | 86% [77-93] (60/70) | 79% [69-87] (55/70) | 49% [37-60] (34/70) | 34% [24-46] (24/70) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 100% [100-100] (20/20) | 90% [75-100] (18/20) |

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
| sourcedrecall | 1700 | 0 | 0.0 | 322.3 | 0.19 |
| rag | 1700 | 857 | 0.504 | 4.6 | 0.003 |
| agentmemory | 1700 | 0 | 0.0 | 152.9 | 0.09 |
| ai-memory | 1700 | 0 | 0.0 | 554.6 | 0.326 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
