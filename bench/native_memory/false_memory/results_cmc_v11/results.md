## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) | claude-memory | claude-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 27% [17-38] (16/60) | 35% [23-47] (21/60) | 0% [0-0] (0/60) | 68% [57-80] (41/60) | 5% [0-12] (3/60) | 78% [67-88] (47/60) | 3% [0-8] (2/60) | 42% [30-55] (25/60) | 2% [0-5] (1/60) | 3% [0-8] (2/60) | 2% [0-5] (1/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 70% [50-90] (14/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 95% [85-100] (19/20) | 15% [0-30] (3/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 0% [0-0] (0/20) | 0% [0-0] (0/20) | 5% [0-15] (1/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 5% [0-12] (2/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) | 55% [40-70] (22/40) | 0% [0-0] (0/40) | 68% [52-82] (27/40) | 2% [0-8] (1/40) | 12% [2-22] (5/40) | 2% [0-8] (1/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) |
| CONTROL RECALL, class f (higher is better) | 57% [46-69] (40/70) | 93% [86-99] (65/70) | 93% [86-99] (65/70) | 100% [100-100] (70/70) | 99% [96-100] (69/70) | 86% [77-93] (60/70) | 84% [76-91] (59/70) | 49% [37-60] (34/70) | 49% [37-60] (34/70) | 86% [77-93] (60/70) | 87% [79-94] (61/70) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 95% [85-100] (19/20) |

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
| FALSE-MEMORY RATE, classes a-e (lower is better) | 27% [17-38] (16/60) | 35% [23-47] (21/60) | 0% [0-0] (0/60) | 68% [57-80] (41/60) | 5% [0-12] (3/60) | 78% [67-88] (47/60) | 3% [0-8] (2/60) | 42% [30-55] (25/60) | 2% [0-5] (1/60) | 3% [0-8] (2/60) | 2% [0-5] (1/60) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| b stale | 70% [50-90] (14/20) | 95% [85-100] (19/20) | 0% [0-0] (0/20) | 95% [85-100] (19/20) | 15% [0-30] (3/20) | 100% [100-100] (20/20) | 5% [0-15] (1/20) | 100% [100-100] (20/20) | 0% [0-0] (0/20) | 0% [0-0] (0/20) | 5% [0-15] (1/20) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 5% [0-12] (2/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) | 55% [40-70] (22/40) | 0% [0-0] (0/40) | 68% [52-82] (27/40) | 2% [0-8] (1/40) | 12% [2-22] (5/40) | 2% [0-8] (1/40) | 5% [0-12] (2/40) | 0% [0-0] (0/40) |
| CONTROL RECALL, class f (higher is better) | 57% [46-69] (40/70) | 93% [86-99] (65/70) | 93% [86-99] (65/70) | 100% [100-100] (70/70) | 99% [96-100] (69/70) | 86% [77-93] (60/70) | 84% [76-91] (59/70) | 49% [37-60] (34/70) | 49% [37-60] (34/70) | 86% [77-93] (60/70) | 87% [79-94] (61/70) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 80% [60-95] (16/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 100% [100-100] (20/20) | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 95% [85-100] (19/20) |

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
| sourcedrecall | 1700 | 0 | 0.0 | 33.2 | 0.02 |
| rag | 1700 | 857 | 0.504 | 4.6 | 0.003 |
| agentmemory | 1700 | 0 | 0.0 | 152.9 | 0.09 |
| ai-memory | 1700 | 0 | 0.0 | 554.6 | 0.326 |
| claude-memory | 1700 | 648 | 0.381 | 1536.7 | 0.904 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
