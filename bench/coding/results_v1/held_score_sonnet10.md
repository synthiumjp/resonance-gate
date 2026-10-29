questions answered by every system: 136

| | n | sourcedrecall | native-qwen | both-qwen | rag | both-sonnet | native-sonnet |
|---|---|---|---|---|---|---|---|
| fix | 43 | 30/43 | 11/43 | 32/43 | 30/43 | 30/43 | 21/43 |
| how | 36 | 19/36 | 12/36 | 19/36 | 22/36 | 26/36 | 20/36 |
| where | 53 | 46/53 | 13/53 | 45/53 | 46/53 | 50/53 | 34/53 |
| why | 4 | 3/4 | 2/4 | 3/4 | 3/4 | 4/4 | 2/4 |
| all | 136 | 98/136 | 38/136 | 99/136 | 101/136 | 110/136 | 77/136 |
| context tokens (mean) | | 2697 | 5363 | 8060 | 2578 | 12298 | 9600 |

both-qwen vs native-qwen: 64 to 3, McNemar p=6.8e-16

sourcedrecall vs native-qwen: 65 to 5, McNemar p=2.22e-14

sourcedrecall vs rag: 9 to 12, McNemar p=0.664

both-sonnet vs native-sonnet: 40 to 7, McNemar p=1.07e-06

sourcedrecall vs native-sonnet: 41 to 20, McNemar p=0.00985
