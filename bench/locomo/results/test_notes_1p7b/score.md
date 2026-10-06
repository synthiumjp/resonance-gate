questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 149/239 = 62.3% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 142/258 = 55.0% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 39/83 = 47.0% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 576/727 = 79.2% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 906/1307 = 69.3% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 1582 | 722 | 356 |
| mean retrieval latency s | 0.976 | 0.151 | 0.284 |
| ingest messages | 10188 | 0 | 5094 |
| ingest model calls | 468 | 0 | 5094 |
| ingest seconds | 4678 | 0 | 115 |
| reader+judge s per question | 14.6 | 5.0 | 5.6 |
