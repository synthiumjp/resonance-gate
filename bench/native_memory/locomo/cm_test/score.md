questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag | claude-memory |
|---|---|---|---|---|---|
| 1 multi-hop | 239 | 129/239 = 54.0% | 148/239 = 61.9% | 94/239 = 39.3% | 170/239 = 71.1% |
| 2 temporal | 258 | 148/258 = 57.4% | 96/258 = 37.2% | 128/258 = 49.6% | 187/258 = 72.5% |
| 3 open-domain | 83 | 30/83 = 36.1% | 34/83 = 41.0% | 32/83 = 38.6% | 42/83 = 50.6% |
| 4 single-hop | 727 | 550/727 = 75.7% | 566/727 = 77.9% | 486/727 = 66.9% | 602/727 = 82.8% |
| overall (1-4) | 1307 | 857/1307 = 65.6% | 844/1307 = 64.6% | 740/1307 = 56.6% | 1001/1307 = 76.6% |

| | sourcedrecall | mem0 | rag | claude-memory |
|---|---|---|---|---|
| mean context tokens (len/4) | 683 | 722 | 356 | 10784 |
| mean retrieval latency s | 0.715 | 0.151 | 0.284 | 0.000 |
| reader+judge s per question | 4.1 | 5.0 | 5.6 | 34.2 |
