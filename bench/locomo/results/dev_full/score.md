questions answered by all systems: 233

| category | n | rag | sourcedrecall |
|---|---|---|---|
| 1 multi-hop | 43 | 19/43 = 44.2% | 10/43 = 23.3% |
| 2 temporal | 63 | 36/63 = 57.1% | 34/63 = 54.0% |
| 3 open-domain | 13 | 9/13 = 69.2% | 8/13 = 61.5% |
| 4 single-hop | 114 | 81/114 = 71.1% | 45/114 = 39.5% |
| overall (1-4) | 233 | 145/233 = 62.2% | 97/233 = 41.6% |

| | rag | sourcedrecall |
|---|---|---|
| mean context tokens (len/4) | 385 | 415 |
| mean retrieval latency s | 0.012 | 0.353 |
| ingest messages | 788 | 1576 |
| ingest model calls | 788 | 0 |
| ingest seconds | 1 | 300 |
| reader+judge s per question | 4.3 | 4.5 |
