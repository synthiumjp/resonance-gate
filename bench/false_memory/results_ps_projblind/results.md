## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 9% [0-19] (3/32) | 16% [3-28] (5/32) | 0% [0-0] (0/32) |
| a negation/hedge/question | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| b stale | 43% [14-86] (3/7) | 71% [43-100] (5/7) | 0% [0-0] (0/7) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| CONTROL RECALL, class f (higher is better) | 46% [23-69] (6/13) | 77% [54-100] (10/13) | 77% [54-100] (10/13) |
| explicit abstention, c+d (returned nothing) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) |
| true-fact side recall, a/b/e (secondary) | 71% [43-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 9% [0-19] (3/32) | 16% [3-28] (5/32) | 0% [0-0] (0/32) |
| a negation/hedge/question | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| b stale | 43% [14-86] (3/7) | 71% [43-100] (5/7) | 0% [0-0] (0/7) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| CONTROL RECALL, class f (higher is better) | 46% [23-69] (6/13) | 77% [54-100] (10/13) | 77% [54-100] (10/13) |
| explicit abstention, c+d (returned nothing) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) |
| true-fact side recall, a/b/e (secondary) | 71% [43-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 9% [0-19] (3/32) | 16% [3-28] (5/32) | 0% [0-0] (0/32) |
| a negation/hedge/question | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| b stale | 43% [14-86] (3/7) | 71% [43-100] (5/7) | 0% [0-0] (0/7) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| CONTROL RECALL, class f (higher is better) | 46% [23-69] (6/13) | 77% [54-100] (10/13) | 77% [54-100] (10/13) |
| explicit abstention, c+d (returned nothing) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) |
| true-fact side recall, a/b/e (secondary) | 71% [43-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 9% [0-19] (3/32) | 16% [3-28] (5/32) | 0% [0-0] (0/32) |
| a negation/hedge/question | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| b stale | 43% [14-86] (3/7) | 71% [43-100] (5/7) | 0% [0-0] (0/7) |
| c invention | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| CONTROL RECALL, class f (higher is better) | 46% [23-69] (6/13) | 77% [54-100] (10/13) | 77% [54-100] (10/13) |
| explicit abstention, c+d (returned nothing) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| no false assertion, c+d | 100% [100-100] (6/6) | 100% [100-100] (6/6) | 100% [100-100] (6/6) |
| true-fact side recall, a/b/e (secondary) | 71% [43-100] (5/7) | 100% [100-100] (7/7) | 100% [100-100] (7/7) |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 34208 | 0 | 0.0 | 3483.1 | 0.102 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
