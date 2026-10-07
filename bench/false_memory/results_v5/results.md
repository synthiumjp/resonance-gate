## A. Judge verdicts as produced

### All scenarios

| metric | sourcedrecall | sourcedrecall (context block) | sourcedrecall (answer block) | rag | rag (answer block) |
|---|---|---|---|---|---|
| FALSE-MEMORY RATE, classes a-e (lower is better) | 36% [25-46] (27/76) | 57% [45-67] (43/76) | 5% [1-11] (4/76) | 55% [45-66] (42/76) | 16% [8-24] (12/76) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 50% [37-63] (27/54) | 80% [69-89] (43/54) | 7% [2-15] (4/54) | 78% [67-89] (42/54) | 22% [11-33] (12/54) |
| c invention | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| CONTROL RECALL, class f (higher is better) | 50% [34-64] (22/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 91% [82-98] (40/44) | 86% [75-95] (38/44) |
| explicit abstention, c+d (returned nothing) | 100% [100-100] (3/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| no false assertion, c+d | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) |
| true-fact side recall, a/b/e (secondary) | 67% [55-78] (40/60) | 100% [100-100] (60/60) | 87% [78-95] (52/60) | 88% [80-95] (53/60) | 75% [63-85] (45/60) |

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
| FALSE-MEMORY RATE, classes a-e (lower is better) | 36% [25-46] (27/76) | 57% [45-67] (43/76) | 4% [0-9] (3/76) | 55% [45-66] (42/76) | 14% [7-22] (11/76) |
| a negation/hedge/question | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) | 0% [0-0] (0/6) |
| b stale | 50% [37-63] (27/54) | 80% [69-89] (43/54) | 6% [0-13] (3/54) | 78% [67-89] (42/54) | 20% [11-31] (11/54) |
| c invention | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| d attribute absent | n/a | n/a | n/a | n/a | n/a |
| e assistant-injected | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) | 0% [0-0] (0/13) |
| CONTROL RECALL, class f (higher is better) | 50% [34-64] (22/44) | 100% [100-100] (44/44) | 82% [70-93] (36/44) | 91% [82-98] (40/44) | 86% [75-95] (38/44) |
| explicit abstention, c+d (returned nothing) | 100% [100-100] (3/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) | 0% [0-0] (0/3) |
| no false assertion, c+d | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) | 100% [100-100] (3/3) |
| true-fact side recall, a/b/e (secondary) | 67% [55-78] (40/60) | 100% [100-100] (60/60) | 87% [78-95] (52/60) | 88% [80-95] (53/60) | 75% [63-85] (45/60) |

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
| sourcedrecall | 909 | 0 | 0.0 | 227.0 | 0.25 |
| rag | 909 | 560 | 0.616 | 3.0 | 0.003 |

Cells: rate [95% CI] (k/n). Cluster bootstrap over scenarios, seed 20261002, 10000 resamples. Judge: qwen3-14b-a8cc1361.gguf, temperature 0.
