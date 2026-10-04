questions answered by all systems: 1307

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 239 | 116/239 = 48.5% | 148/239 = 61.9% | 94/239 = 39.3% |
| 2 temporal | 258 | 145/258 = 56.2% | 96/258 = 37.2% | 128/258 = 49.6% |
| 3 open-domain | 83 | 27/83 = 32.5% | 34/83 = 41.0% | 32/83 = 38.6% |
| 4 single-hop | 727 | 544/727 = 74.8% | 566/727 = 77.9% | 486/727 = 66.9% |
| overall (1-4) | 1307 | 832/1307 = 63.7% | 844/1307 = 64.6% | 740/1307 = 56.6% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 735 | 722 | 356 |
| mean retrieval latency s | 0.836 | 0.151 | 0.284 |
| ingest messages | 10188 | 0 | 5094 |
| ingest model calls | 0 | 0 | 5094 |
| ingest seconds | 1983 | 0 | 115 |
| reader+judge s per question | 5.1 | 5.0 | 5.6 |
