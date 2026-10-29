questions answered by all systems: 1307

| category | n | sourcedrecall_qj | mem0_qj | rag_qj | claude-memory_qj |
|---|---|---|---|---|---|
| 1 multi-hop | 239 | 161/239 = 67.4% | 162/239 = 67.8% | 130/239 = 54.4% | 205/239 = 85.8% |
| 2 temporal | 258 | 196/258 = 76.0% | 91/258 = 35.3% | 172/258 = 66.7% | 214/258 = 82.9% |
| 3 open-domain | 83 | 54/83 = 65.1% | 55/83 = 66.3% | 51/83 = 61.4% | 62/83 = 74.7% |
| 4 single-hop | 727 | 598/727 = 82.3% | 619/727 = 85.1% | 557/727 = 76.6% | 649/727 = 89.3% |
| overall (1-4) | 1307 | 1009/1307 = 77.2% | 927/1307 = 70.9% | 910/1307 = 69.6% | 1130/1307 = 86.5% |

| | sourcedrecall_qj | mem0_qj | rag_qj | claude-memory_qj |
|---|---|---|---|---|
| mean context tokens (len/4) | 683 | 722 | 356 | 10784 |
| mean retrieval latency s | 0.715 | 0.151 | 0.284 | 0.000 |
