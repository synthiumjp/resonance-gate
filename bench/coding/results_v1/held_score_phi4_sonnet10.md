questions answered by every system: 102

| | n | sourcedrecall | native-qwen | both-qwen | rag | both-sonnet | native-sonnet |
|---|---|---|---|---|---|---|---|
| fix | 29 | 18/29 | 5/29 | 13/29 | 17/29 | 13/29 | 15/29 |
| how | 29 | 19/29 | 7/29 | 18/29 | 17/29 | 17/29 | 14/29 |
| where | 42 | 37/42 | 12/42 | 38/42 | 36/42 | 36/42 | 21/42 |
| why | 2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| all | 102 | 76/102 | 26/102 | 71/102 | 72/102 | 68/102 | 52/102 |
| context tokens (mean) | | 2674 | 4830 | 7505 | 2566 | 10257 | 7583 |

both-qwen vs native-qwen: 48 to 3, McNemar p=1.97e-11

sourcedrecall vs native-qwen: 51 to 1, McNemar p=2.35e-14

sourcedrecall vs rag: 12 to 8, McNemar p=0.503

both-sonnet vs native-sonnet: 27 to 11, McNemar p=0.0139

sourcedrecall vs native-sonnet: 33 to 9, McNemar p=0.000272
