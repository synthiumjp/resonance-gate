## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 25% [5-45] (5/20) | 20% [5-40] (4/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 25% [5-45] (5/20) | 20% [5-40] (4/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) |
| CONTROL RECALL, class f (higher is better) | 50% [20-80] (5/10) | 90% [70-100] (9/10) | 90% [70-100] (9/10) | 100% [100-100] (10/10) | 100% [100-100] (10/10) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a |

## B. After manual audit of judge errors (audit_overrides.json)

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 25% [5-45] (5/20) | 20% [5-40] (4/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 25% [5-45] (5/20) | 20% [5-40] (4/20) | 5% [0-15] (1/20) | 95% [85-100] (19/20) | 85% [70-100] (17/20) |
| CONTROL RECALL, class f (higher is better) | 50% [20-80] (5/10) | 90% [70-100] (9/10) | 90% [70-100] (9/10) | 100% [100-100] (10/10) | 100% [100-100] (10/10) |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a |

### Held-out split

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | n/a | n/a | n/a | n/a | n/a |
| a negation/hedge/question | n/a | n/a | n/a | n/a | n/a |
| b stale | n/a | n/a | n/a | n/a | n/a |
| c invention | n/a | n/a | n/a | n/a | n/a |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | n/a | n/a | n/a | n/a | n/a |
| CONTROL RECALL, class f (higher is better) | n/a | n/a | n/a | n/a | n/a |
| explicit abstention, c+d (returned nothing) | n/a | n/a | n/a | n/a | n/a |
| no false assertion, c+d | n/a | n/a | n/a | n/a | n/a |
| true-fact side recall, a/b/e (secondary) | n/a | n/a | n/a | n/a | n/a |

## Ingest cost

| system | messages | model calls | calls/message | seconds | seconds/message |
|---|---|---|---|---|---|
| sourcedrecall | 262 | 0 | 0.0 | 9.7 | 0.037 |
| rag | 262 | 135 | 0.515 | 1.6 | 0.006 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
