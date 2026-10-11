questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 129/239 = 54.0% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 139/258 = 53.9% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 36/83 = 43.4% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 572/727 = 78.7% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 876/1307 = 67.0% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 1045 | 722 | 356 |
| mean retrieval latency s | 0.881 | 0.151 | 0.284 |
| ingest messages | 10188 | 0 | 5094 |
| ingest model calls | 468 | 0 | 5094 |
| ingest seconds | 1564 | 0 | 115 |
| reader+judge s per question | 5.6 | 5.0 | 5.6 |
