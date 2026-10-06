## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 14% [0-36] (2/14) | 14% [0-36] (2/14) | 7% [0-21] (1/14) |
| a negation/hedge/question | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 0% [0-0] (0/7) |
| b stale | 29% [0-57] (2/7) | 29% [0-57] (2/7) | 14% [0-43] (1/7) |
| c invention | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 40% [10-70] (4/10) | 60% [30-90] (6/10) | 70% [40-100] (7/10) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 78% [44-100] (7/9) | 100% [100-100] (9/9) | 89% [67-100] (8/9) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 14% [0-36] (2/14) | 14% [0-36] (2/14) | 7% [0-21] (1/14) |
| a negation/hedge/question | 0% [0-0] (0/7) | 0% [0-0] (0/7) | 0% [0-0] (0/7) |
| b stale | 29% [0-57] (2/7) | 29% [0-57] (2/7) | 14% [0-43] (1/7) |
| c invention | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | 40% [10-70] (4/10) | 60% [30-90] (6/10) | 70% [40-100] (7/10) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | 78% [44-100] (7/9) | 100% [100-100] (9/9) | 89% [67-100] (8/9) |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) |
|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 100 | 0 | 0.0 | 44.4 | 0.444 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
