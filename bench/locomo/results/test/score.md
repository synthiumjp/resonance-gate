questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 64/239 = 26.8% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 85/258 = 32.9% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 22/83 = 26.5% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 266/727 = 36.6% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 437/1307 = 33.4% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 342 | 722 | 356 |
| mean retrieval latency s | 0.944 | 0.151 | 0.284 |
| ingest messages | 10188 | 10188 | 5094 |
| ingest model calls | 0 | 941 | 5094 |
| ingest seconds | 1780 | 21583 | 115 |
| reader+judge s per question | 4.0 | 5.0 | 5.6 |
