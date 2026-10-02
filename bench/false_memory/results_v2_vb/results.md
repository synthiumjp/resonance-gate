## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 14% [3-25] (5/37) | 11% [3-22] (4/37) | 46% [30-63] (17/37) | 30% [16-45] (11/37) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 33% [8-58] (4/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 57% [22-100] (4/7) | 0% [0-0] (0/7) |
| CONTROL RECALL, class f (higher is better) | 87% [69-100] (13/15) | 87% [69-100] (13/15) | 100% [100-100] (15/15) | 100% [100-100] (15/15) |
| explicit abstention, c+d (returned nothing) | 83% [58-100] (10/12) | 83% [58-100] (10/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 92% [75-100] (11/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 45% [18-73] (5/11) | 45% [18-73] (5/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 14% [3-25] (5/37) | 11% [3-22] (4/37) | 46% [30-63] (17/37) | 30% [16-45] (11/37) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 33% [8-58] (4/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 17% [0-50] (1/6) | 0% [0-0] (0/6) | 17% [0-50] (1/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 57% [22-100] (4/7) | 0% [0-0] (0/7) |
| CONTROL RECALL, class f (higher is better) | 87% [69-100] (13/15) | 87% [69-100] (13/15) | 100% [100-100] (15/15) | 100% [100-100] (15/15) |
| explicit abstention, c+d (returned nothing) | 83% [58-100] (10/12) | 83% [58-100] (10/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 92% [75-100] (11/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 45% [18-73] (5/11) | 45% [18-73] (5/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 8% [0-18] (3/37) | 11% [3-22] (4/37) | 43% [27-59] (16/37) | 30% [16-45] (11/37) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 25% [0-50] (3/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 57% [22-100] (4/7) | 0% [0-0] (0/7) |
| CONTROL RECALL, class f (higher is better) | 87% [69-100] (13/15) | 87% [69-100] (13/15) | 100% [100-100] (15/15) | 100% [100-100] (15/15) |
| explicit abstention, c+d (returned nothing) | 83% [58-100] (10/12) | 83% [58-100] (10/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 100% [100-100] (12/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 45% [18-73] (5/11) | 45% [18-73] (5/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 8% [0-18] (3/37) | 11% [3-22] (4/37) | 43% [27-59] (16/37) | 30% [16-45] (11/37) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 25% [0-50] (3/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 92% [75-100] (11/12) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| e assistant-injected | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 57% [22-100] (4/7) | 0% [0-0] (0/7) |
| CONTROL RECALL, class f (higher is better) | 87% [69-100] (13/15) | 87% [69-100] (13/15) | 100% [100-100] (15/15) | 100% [100-100] (15/15) |
| explicit abstention, c+d (returned nothing) | 83% [58-100] (10/12) | 83% [58-100] (10/12) | 0% [0-0] (0/12) | 0% [0-0] (0/12) |
| no false assertion, c+d | 100% [100-100] (12/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| true-fact side recall, a/b/e (secondary) | 45% [18-73] (5/11) | 45% [18-73] (5/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 83 | 0 | 0.0 | 11.8 | 0.143 |
| mem0 | 83 | 126 | 1.518 | 3242.8 | 39.07 |
| rag | 83 | 72 | 0.867 | 0.7 | 0.009 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3:14b, temperature 0.
