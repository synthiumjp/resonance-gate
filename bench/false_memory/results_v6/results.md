## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) | agentmemory | agentmemory (answer block) | ai-memory | ai-memory (answer block) |
|---|---|---|---|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 41% [29-53] (24/59) | 51% [39-63] (30/59) | 27% [17-39] (16/59) | 46% [34-58] (27/59) | 31% [19-42] (18/59) | 66% [54-78] (39/59) | 27% [17-39] (16/59) | 39% [27-51] (23/59) | 22% [12-34] (13/59) |
| a negation/hedge/question | 21% [0-43] (3/14) | 7% [0-21] (1/14) | 14% [0-36] (2/14) | 7% [0-21] (1/14) | 21% [0-43] (3/14) | 0% [0-0] (0/14) | 14% [0-36] (2/14) | 0% [0-0] (0/14) | 21% [0-43] (3/14) |
| b stale | 39% [21-57] (11/28) | 79% [64-93] (22/28) | 0% [0-0] (0/28) | 64% [46-82] (18/28) | 4% [0-11] (1/28) | 93% [82-100] (26/28) | 0% [0-0] (0/28) | 71% [54-86] (20/28) | 25% [11-43] (7/28) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 59% [35-82] (10/17) | 41% [18-65] (7/17) | 82% [65-100] (14/17) | 47% [24-71] (8/17) | 82% [65-100] (14/17) | 76% [53-94] (13/17) | 82% [65-100] (14/17) | 18% [0-35] (3/17) | 18% [0-35] (3/17) |
| CONTROL RECALL, class f (higher is better) | 58% [47-69] (47/81) | 89% [81-95] (72/81) | 70% [60-80] (57/81) | 80% [72-89] (65/81) | 65% [54-75] (53/81) | 88% [80-94] (71/81) | 64% [53-74] (52/81) | 83% [74-90] (67/81) | 52% [41-63] (42/81) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 43% [25-61] (12/28) | 96% [89-100] (27/28) | 89% [75-100] (25/28) | 86% [71-96] (24/28) | 82% [68-96] (23/28) | 96% [89-100] (27/28) | 89% [75-100] (25/28) | 96% [89-100] (27/28) | 57% [39-75] (16/28) |

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
| FALSE-MEMORY RATE, classes a-e (lower is better) | 41% [29-53] (24/59) | 51% [39-63] (30/59) | 25% [15-37] (15/59) | 46% [34-58] (27/59) | 29% [19-41] (17/59) | 66% [54-78] (39/59) | 29% [17-41] (17/59) | 39% [27-51] (23/59) | 17% [8-27] (10/59) |
| a negation/hedge/question | 21% [0-43] (3/14) | 7% [0-21] (1/14) | 7% [0-21] (1/14) | 7% [0-21] (1/14) | 7% [0-21] (1/14) | 0% [0-0] (0/14) | 14% [0-36] (2/14) | 0% [0-0] (0/14) | 0% [0-0] (0/14) |
| b stale | 39% [21-57] (11/28) | 79% [64-93] (22/28) | 0% [0-0] (0/28) | 64% [46-82] (18/28) | 4% [0-11] (1/28) | 93% [82-100] (26/28) | 0% [0-0] (0/28) | 71% [54-86] (20/28) | 25% [11-43] (7/28) |
| c invention | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 59% [35-82] (10/17) | 41% [18-65] (7/17) | 82% [65-100] (14/17) | 47% [24-71] (8/17) | 88% [71-100] (15/17) | 76% [53-94] (13/17) | 88% [71-100] (15/17) | 18% [0-35] (3/17) | 18% [0-35] (3/17) |
| CONTROL RECALL, class f (higher is better) | 58% [47-69] (47/81) | 89% [81-95] (72/81) | 70% [60-80] (57/81) | 80% [72-89] (65/81) | 65% [54-75] (53/81) | 88% [80-94] (71/81) | 64% [53-74] (52/81) | 83% [74-90] (67/81) | 52% [41-63] (42/81) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 43% [25-61] (12/28) | 96% [89-100] (27/28) | 89% [75-100] (25/28) | 86% [71-96] (24/28) | 82% [68-96] (23/28) | 96% [89-100] (27/28) | 89% [75-100] (25/28) | 96% [89-100] (27/28) | 57% [39-75] (16/28) |

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
| sourcedrecall | 1064 | 0 | 0.0 | 263.0 | 0.247 |
| rag | 1064 | 704 | 0.662 | 4.0 | 0.004 |
| agentmemory | 1064 | 0 | 0.0 | 165.4 | 0.155 |
| ai-memory | 1064 | 0 | 0.0 | 350.3 | 0.329 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
