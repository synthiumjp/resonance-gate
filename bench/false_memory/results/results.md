## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 10% [3-18] (6/60) | 12% [5-20] (7/60) | 32% [20-43] (19/60) | 23% [13-35] (14/60) |
| a negation/hedge/question | 0% [0-0] (0/16) | 0% [0-0] (0/16) | 0% [0-0] (0/16) | 0% [0-0] (0/16) |
| b stale | 33% [8-58] (4/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| c invention | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) |
| d attribute absent | 10% [0-30] (1/10) | 20% [0-50] (2/10) | 40% [10-70] (4/10) | 20% [0-50] (2/10) |
| e assistant-injected | 8% [0-25] (1/12) | 8% [0-25] (1/12) | 25% [0-50] (3/12) | 0% [0-0] (0/12) |
| CONTROL RECALL, class f (higher is better) | 88% [72-100] (14/16) | 88% [72-100] (14/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | 95% [85-100] (19/20) | 85% [70-100] (17/20) | 0% [0-0] (0/20) | 0% [0-0] (0/20) |
| no false assertion, c+d | 95% [85-100] (19/20) | 90% [75-100] (18/20) | 80% [60-95] (16/20) | 90% [75-100] (18/20) |
| true-fact side recall, a/b/e (secondary) | 55% [27-82] (6/11) | 55% [27-82] (6/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 16% [0-32] (3/19) | 21% [5-42] (4/19) | 32% [11-53] (6/19) | 26% [11-47] (5/19) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 75% [25-100] (3/4) | 75% [25-100] (3/4) | 100% [100-100] (4/4) | 100% [100-100] (4/4) |
| c invention | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| d attribute absent | 0% [0-0] (0/3) | 33% [0-100] (1/3) | 67% [0-100] (2/3) | 33% [0-100] (1/3) |
| e assistant-injected | 0% [0-0] (0/4) | 0% [0-0] (0/4) | 0% [0-0] (0/4) | 0% [0-0] (0/4) |
| CONTROL RECALL, class f (higher is better) | 71% [33-100] (5/7) | 71% [33-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |
| explicit abstention, c+d (returned nothing) | 100% [100-100] (6/6) | 83% [50-100] (5/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 83% [50-100] (5/6) | 67% [33-100] (4/6) | 83% [50-100] (5/6) |
| true-fact side recall, a/b/e (secondary) | 0% [0-0] (0/4) | 0% [0-0] (0/4) | 100% [100-100] (4/4) | 100% [100-100] (4/4) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 7% [2-13] (4/60) | 7% [2-13] (4/60) | 27% [17-38] (16/60) | 20% [10-30] (12/60) |
| a negation/hedge/question | 0% [0-0] (0/16) | 0% [0-0] (0/16) | 0% [0-0] (0/16) | 0% [0-0] (0/16) |
| b stale | 33% [8-58] (4/12) | 33% [8-58] (4/12) | 100% [100-100] (12/12) | 100% [100-100] (12/12) |
| c invention | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) |
| d attribute absent | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) | 0% [0-0] (0/10) |
| e assistant-injected | 0% [0-0] (0/12) | 0% [0-0] (0/12) | 33% [8-58] (4/12) | 0% [0-0] (0/12) |
| CONTROL RECALL, class f (higher is better) | 88% [72-100] (14/16) | 88% [72-100] (14/16) | 100% [100-100] (16/16) | 100% [100-100] (16/16) |
| explicit abstention, c+d (returned nothing) | 95% [85-100] (19/20) | 85% [70-100] (17/20) | 0% [0-0] (0/20) | 0% [0-0] (0/20) |
| no false assertion, c+d | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) | 100% [100-100] (20/20) |
| true-fact side recall, a/b/e (secondary) | 55% [27-82] (6/11) | 55% [27-82] (6/11) | 100% [100-100] (11/11) | 100% [100-100] (11/11) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | mem0 | rag |
|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 16% [0-32] (3/19) | 16% [0-32] (3/19) | 26% [11-47] (5/19) | 21% [5-42] (4/19) |
| a negation/hedge/question | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) | 0% [0-0] (0/5) |
| b stale | 75% [25-100] (3/4) | 75% [25-100] (3/4) | 100% [100-100] (4/4) | 100% [100-100] (4/4) |
| c invention | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| d attribute absent | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| e assistant-injected | 0% [0-0] (0/4) | 0% [0-0] (0/4) | 25% [0-75] (1/4) | 0% [0-0] (0/4) |
| CONTROL RECALL, class f (higher is better) | 71% [33-100] (5/7) | 71% [33-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |
| explicit abstention, c+d (returned nothing) | 100% [100-100] (6/6) | 83% [50-100] (5/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) |
| true-fact side recall, a/b/e (secondary) | 0% [0-0] (0/4) | 0% [0-0] (0/4) | 100% [100-100] (4/4) | 100% [100-100] (4/4) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 108 | 0 | 0.0 | 13.3 | 0.123 |
| mem0 | 108 | 168 | 1.556 | 2588.8 | 23.97 |
| rag | 108 | 94 | 0.87 | 0.9 | 0.008 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3:14b, temperature 0.
