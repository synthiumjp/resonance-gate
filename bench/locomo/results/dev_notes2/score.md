questions answered by all systems: 233

| category | n | rag | sourcedrecall |
|---|---|---|---|
| 1 multi-hop | 43 | 19/43 = 44.2% | 23/43 = 53.5% |
| 2 temporal | 63 | 36/63 = 57.1% | 42/63 = 66.7% |
| 3 open-domain | 13 | 9/13 = 69.2% | 10/13 = 76.9% |
| 4 single-hop | 114 | 81/114 = 71.1% | 87/114 = 76.3% |
| overall (1-4) | 233 | 145/233 = 62.2% | 162/233 = 69.5% |

| | rag | sourcedrecall |
|---|---|---|
| mean context tokens (len/4) | 385 | 1150 |
| mean retrieval latency s | 0.012 | 2.882 |
| ingest messages | 788 | 1576 |
| ingest model calls | 788 | 76 |
| ingest seconds | 1 | 1825 |
| reader+judge s per question | 4.3 | 5.7 |
