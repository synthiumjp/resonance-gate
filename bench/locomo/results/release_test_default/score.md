questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 125/239 = 52.3% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 143/258 = 55.4% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 33/83 = 39.8% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 553/727 = 76.1% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 854/1307 = 65.3% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 687 | 722 | 356 |
| mean retrieval latency s | 0.737 | 0.151 | 0.284 |
| ingest messages | 10188 | 0 | 5094 |
| ingest model calls | 0 | 0 | 5094 |
| ingest seconds | 435 | 0 | 115 |
| reader+judge s per question | 3.9 | 5.0 | 5.6 |
