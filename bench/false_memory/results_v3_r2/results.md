## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 20% [7-33] (6/30) | 27% [10-43] (8/30) | 37% [20-53] (11/30) | 30% [13-47] (9/30) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 62% [25-88] (5/8) | 62% [25-88] (5/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |
| c invention | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 17% [0-50] (1/6) | 17% [0-50] (1/6) |
| d attribute absent | 17% [0-50] (1/6) | 33% [0-67] (2/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 20% [0-60] (1/5) | 0% [0-0] (0/5) |
| CONTROL RECALL, class f (higher is better) | 39% [19-60] (9/23) | 43% [23-65] (10/23) | 100% [100-100] (23/23) | 100% [100-100] (23/23) |
| explicit abstention, c+d (returned nothing) | 75% [50-100] (9/12) | 50% [25-75] (6/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 92% [75-100] (11/12) | 75% [50-100] (9/12) | 83% [58-100] (10/12) | 92% [75-100] (11/12) |
| true-fact side recall, a/b/e (secondary) | 50% [12-88] (4/8) | 50% [12-88] (4/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 20% [7-33] (6/30) | 27% [10-43] (8/30) | 37% [20-53] (11/30) | 30% [13-47] (9/30) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 62% [25-88] (5/8) | 62% [25-88] (5/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |
| c invention | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 17% [0-50] (1/6) | 17% [0-50] (1/6) |
| d attribute absent | 17% [0-50] (1/6) | 33% [0-67] (2/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 20% [0-60] (1/5) | 0% [0-0] (0/5) |
| CONTROL RECALL, class f (higher is better) | 39% [19-60] (9/23) | 43% [23-65] (10/23) | 100% [100-100] (23/23) | 100% [100-100] (23/23) |
| explicit abstention, c+d (returned nothing) | 75% [50-100] (9/12) | 50% [25-75] (6/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 92% [75-100] (11/12) | 75% [50-100] (9/12) | 83% [58-100] (10/12) | 92% [75-100] (11/12) |
| true-fact side recall, a/b/e (secondary) | 50% [12-88] (4/8) | 50% [12-88] (4/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 17% [3-30] (5/30) | 23% [10-40] (7/30) | 30% [13-47] (9/30) | 27% [13-43] (8/30) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 62% [25-88] (5/8) | 62% [25-88] (5/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |
| c invention | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 20% [0-60] (1/5) | 0% [0-0] (0/5) |
| CONTROL RECALL, class f (higher is better) | 39% [19-60] (9/23) | 43% [23-65] (10/23) | 100% [100-100] (23/23) | 100% [100-100] (23/23) |
| explicit abstention, c+d (returned nothing) | 75% [50-100] (9/12) | 50% [25-75] (6/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 100% [100-100] (12/12) | 83% [58-100] (10/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 50% [12-88] (4/8) | 50% [12-88] (4/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 17% [3-30] (5/30) | 23% [10-40] (7/30) | 30% [13-47] (9/30) | 27% [13-43] (8/30) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 62% [25-88] (5/8) | 62% [25-88] (5/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |
| c invention | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 20% [0-60] (1/5) | 0% [0-0] (0/5) |
| CONTROL RECALL, class f (higher is better) | 39% [19-60] (9/23) | 43% [23-65] (10/23) | 100% [100-100] (23/23) | 100% [100-100] (23/23) |
| explicit abstention, c+d (returned nothing) | 75% [50-100] (9/12) | 50% [25-75] (6/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 100% [100-100] (12/12) | 83% [58-100] (10/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 50% [12-88] (4/8) | 50% [12-88] (4/8) | 100% [100-100] (8/8) | 100% [100-100] (8/8) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 72 | 0 | 0.0 | 11.4 | 0.159 |
| mem0 | 72 | 114 | 1.583 | 12913.1 | 179.349 |
| rag | 72 | 65 | 0.903 | 0.9 | 0.012 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3:14b, temperature 0.
