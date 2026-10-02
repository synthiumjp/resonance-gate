questions answered by all systems: 30

| category | n | sourcedrecall | mem0 | rag |
|---|---|---|---|---|
| 1 multi-hop | 2 | 0/2 = 0.0% | 1/2 = 50.0% | 0/2 = 0.0% |
| 2 temporal | 11 | 5/11 = 45.5% | 8/11 = 72.7% | 9/11 = 81.8% |
| 3 open-domain | 1 | 0/1 = 0.0% | 1/1 = 100.0% | 1/1 = 100.0% |
| 4 single-hop | 16 | 8/16 = 50.0% | 12/16 = 75.0% | 13/16 = 81.2% |
| overall (1-4) | 30 | 13/30 = 43.3% | 22/30 = 73.3% | 23/30 = 76.7% |

| | sourcedrecall | mem0 | rag |
|---|---|---|---|
| mean context tokens (len/4) | 250 | 753 | 409 |
| mean retrieval latency s | 0.400 | 0.133 | 0.012 |
| ingest messages | 232 | 232 | 116 |
| ingest model calls | 0 | 24 | 116 |
| ingest seconds | 44 | 369 | 2 |
| reader+judge s per question | 15.1 | 80.6 | 4.3 |
