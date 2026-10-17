questions run: 500 (non-abstention 470)

SESSION-LEVEL, non-abstention, all types (n=470)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.9 | 33.0 | 97.2 | 86.0 | 98.7 | 93.6 | 99.1 | 97.4 |
| bm25 | 80.4 | 27.9 | 90.9 | 72.8 | 93.8 | 78.7 | 96.4 | 87.2 |
| bge | 88.7 | 30.4 | 95.7 | 81.7 | 97.0 | 90.4 | 98.5 | 96.2 |

SESSION-LEVEL, non-abstention, excluding single-session-assistant (n=414)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.9 | 24.6 | 97.6 | 84.8 | 99.0 | 93.2 | 99.5 | 97.6 |
| bm25 | 80.2 | 20.5 | 91.1 | 70.5 | 94.0 | 76.8 | 96.6 | 86.2 |
| bge | 88.6 | 22.5 | 96.1 | 80.2 | 97.6 | 90.1 | 98.8 | 96.1 |

SESSION-LEVEL, all incl. abstention, all types (n=500)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 95.0 | 32.2 | 97.4 | 85.4 | 98.8 | 92.8 | 99.2 | 97.6 |
| bm25 | 80.0 | 27.0 | 90.8 | 71.4 | 93.6 | 77.8 | 96.2 | 86.4 |
| bge | 88.2 | 29.4 | 95.6 | 81.2 | 96.8 | 89.8 | 98.4 | 96.2 |

SESSION-LEVEL, all incl. abstention, excluding single-session-assistant (n=444)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 95.0 | 24.3 | 97.7 | 84.2 | 99.1 | 92.3 | 99.5 | 97.7 |
| bm25 | 79.7 | 20.0 | 91.0 | 69.1 | 93.7 | 75.9 | 96.4 | 85.4 |
| bge | 88.1 | 21.8 | 95.9 | 79.7 | 97.3 | 89.4 | 98.6 | 96.2 |

SESSION-LEVEL, non-abstention, knowledge-update (n=72)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 98.6 | 0.0 | 100.0 | 98.6 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | 93.1 | 0.0 | 100.0 | 88.9 | 100.0 | 93.1 | 100.0 | 98.6 |
| bge | 95.8 | 0.0 | 100.0 | 97.2 | 100.0 | 100.0 | 100.0 | 100.0 |

SESSION-LEVEL, non-abstention, multi-session (n=121)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 98.3 | 0.0 | 99.2 | 75.2 | 100.0 | 92.6 | 100.0 | 97.5 |
| bm25 | 76.0 | 0.0 | 90.9 | 47.1 | 95.0 | 58.7 | 96.7 | 75.2 |
| bge | 93.4 | 0.0 | 98.3 | 67.8 | 98.3 | 88.4 | 100.0 | 95.0 |

SESSION-LEVEL, non-abstention, single-session-assistant (n=56)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.6 | 94.6 | 94.6 | 94.6 | 96.4 | 96.4 | 96.4 | 96.4 |
| bm25 | 82.1 | 82.1 | 89.3 | 89.3 | 92.9 | 92.9 | 94.6 | 94.6 |
| bge | 89.3 | 89.3 | 92.9 | 92.9 | 92.9 | 92.9 | 96.4 | 96.4 |

SESSION-LEVEL, non-abstention, single-session-preference (n=30)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 70.0 | 70.0 | 86.7 | 86.7 | 96.7 | 96.7 | 100.0 | 100.0 |
| bm25 | 43.3 | 43.3 | 63.3 | 63.3 | 73.3 | 73.3 | 86.7 | 86.7 |
| bge | 73.3 | 73.3 | 96.7 | 96.7 | 96.7 | 96.7 | 100.0 | 100.0 |

SESSION-LEVEL, non-abstention, single-session-user (n=64)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 98.4 | 98.4 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | 92.2 | 92.2 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bge | 90.6 | 90.6 | 96.9 | 96.9 | 96.9 | 96.9 | 100.0 | 100.0 |

SESSION-LEVEL, non-abstention, temporal-reasoning (n=127)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 93.7 | 14.2 | 96.1 | 78.0 | 97.6 | 85.8 | 98.4 | 94.5 |
| bm25 | 79.5 | 10.2 | 88.2 | 69.3 | 91.3 | 74.0 | 95.3 | 82.7 |
| bge | 82.7 | 10.2 | 91.3 | 70.1 | 96.1 | 81.1 | 96.1 | 92.1 |

ours: distinct sessions returned from top-50 messages (capped at 10): {10: 500}
ours: unmatched hits (text not mapped to a turn): 4 of 24961

TURN-LEVEL (user turns with has_answer), non-abstention, questions with >=1 gold user turn (n=419)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|---|---|---|---|
| ours | 72.1 | 20.0 | 92.8 | 67.5 | 95.9 | 80.7 | 97.4 | 87.8 | 99.3 | 97.4 |
| bm25 | 56.1 | 15.5 | 78.0 | 50.1 | 83.1 | 59.9 | 88.8 | 71.6 | 95.7 | 85.9 |
| bge | 55.4 | 14.3 | 81.1 | 47.5 | 87.8 | 64.0 | 94.3 | 80.2 | 99.0 | 96.7 |

TURN-LEVEL knowledge-update (n=72)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 100.0 | 95.8 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | 95.8 | 77.8 | 98.6 | 88.9 | 100.0 | 97.2 |
| bge | 95.8 | 81.9 | 100.0 | 95.8 | 100.0 | 100.0 |

TURN-LEVEL multi-session (n=121)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 98.3 | 70.2 | 100.0 | 82.6 | 100.0 | 93.4 |
| bm25 | 83.5 | 36.4 | 89.3 | 54.5 | 97.5 | 71.9 |
| bge | 92.6 | 50.4 | 97.5 | 71.1 | 100.0 | 93.4 |

TURN-LEVEL single-session-assistant (n=5)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 80.0 | 80.0 | 80.0 | 80.0 | 100.0 | 100.0 |
| bm25 | 60.0 | 60.0 | 80.0 | 80.0 | 100.0 | 100.0 |
| bge | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

TURN-LEVEL single-session-preference (n=30)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 83.3 | 70.0 | 90.0 | 73.3 | 100.0 | 100.0 |
| bm25 | 46.7 | 26.7 | 56.7 | 40.0 | 76.7 | 73.3 |
| bge | 83.3 | 70.0 | 93.3 | 76.7 | 100.0 | 100.0 |

TURN-LEVEL single-session-user (n=64)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | 92.2 | 92.2 | 95.3 | 95.3 | 98.4 | 98.4 |
| bge | 90.6 | 90.6 | 93.8 | 93.8 | 98.4 | 98.4 |

TURN-LEVEL temporal-reasoning (n=127)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 92.9 | 74.8 | 94.5 | 83.5 | 97.6 | 97.6 |
| bm25 | 80.3 | 63.8 | 87.4 | 73.2 | 94.5 | 89.0 |
| bge | 78.0 | 50.4 | 88.2 | 73.2 | 97.6 | 96.1 |

non-abstention questions with no gold user turn: Counter({'single-session-assistant': 51})
ingest s/q mean: 2.3828  total_s: 4777.7
