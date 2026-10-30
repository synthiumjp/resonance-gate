questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 140/239 = 58.6% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 157/258 = 60.9% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 37/83 = 44.6% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 592/727 = 81.4% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 926/1307 = 70.8% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 992 | 722 | 356 |
| mean retrieval latency s | 0.882 | 0.151 | 0.284 |
| ingest messages | 10188 | 0 | 5094 |
| ingest model calls | 468 | 0 | 5094 |
| ingest seconds | 2271 | 0 | 115 |
| reader+judge s per question | 7.4 | 5.0 | 5.6 |
