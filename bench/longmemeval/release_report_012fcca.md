questions run: 500 (non-abstention 470)

SESSION-LEVEL, non-abstention, all types (n=470)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.9 | 33.0 | 97.2 | 85.7 | 98.7 | 93.4 | 99.1 | 97.4 |
| bm25 | 80.0 | 27.9 | 90.6 | 72.8 | 93.6 | 78.5 | 96.4 | 87.0 |
| bge | 88.9 | 30.4 | 95.5 | 81.3 | 97.0 | 90.4 | 98.5 | 96.2 |

SESSION-LEVEL, non-abstention, excluding single-session-assistant (n=414)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.9 | 24.6 | 97.6 | 84.5 | 99.0 | 93.0 | 99.5 | 97.6 |
| bm25 | 79.7 | 20.5 | 90.8 | 70.5 | 93.7 | 76.6 | 96.6 | 86.0 |
| bge | 88.9 | 22.5 | 96.1 | 80.0 | 97.6 | 90.1 | 98.8 | 96.1 |

SESSION-LEVEL, all incl. abstention, all types (n=500)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 95.0 | 32.2 | 97.4 | 85.2 | 98.8 | 92.6 | 99.2 | 97.6 |
| bm25 | 79.6 | 27.0 | 90.6 | 71.4 | 93.4 | 77.6 | 96.2 | 86.2 |
| bge | 88.6 | 29.4 | 95.4 | 80.8 | 96.8 | 89.8 | 98.4 | 96.0 |

SESSION-LEVEL, all incl. abstention, excluding single-session-assistant (n=444)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 95.0 | 24.3 | 97.7 | 84.0 | 99.1 | 92.1 | 99.5 | 97.7 |
| bm25 | 79.3 | 20.0 | 90.8 | 69.1 | 93.5 | 75.7 | 96.4 | 85.1 |
| bge | 88.5 | 21.8 | 95.9 | 79.5 | 97.3 | 89.4 | 98.6 | 95.9 |

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
| bm25 | 75.2 | 0.0 | 90.9 | 47.1 | 95.0 | 58.7 | 96.7 | 75.2 |
| bge | 93.4 | 0.0 | 98.3 | 67.8 | 98.3 | 88.4 | 100.0 | 95.0 |

SESSION-LEVEL, non-abstention, single-session-assistant (n=56)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 |
|---|---|---|---|---|---|---|---|---|
| ours | 94.6 | 94.6 | 94.6 | 94.6 | 96.4 | 96.4 | 96.4 | 96.4 |
| bm25 | 82.1 | 82.1 | 89.3 | 89.3 | 92.9 | 92.9 | 94.6 | 94.6 |
| bge | 89.3 | 89.3 | 91.1 | 91.1 | 92.9 | 92.9 | 96.4 | 96.4 |

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
| ours | 93.7 | 14.2 | 96.1 | 77.2 | 97.6 | 85.0 | 98.4 | 94.5 |
| bm25 | 78.7 | 10.2 | 87.4 | 69.3 | 90.6 | 73.2 | 95.3 | 81.9 |
| bge | 83.5 | 10.2 | 91.3 | 69.3 | 96.1 | 81.1 | 96.1 | 92.1 |

ours: distinct sessions returned from top-50 messages (capped at 10): {10: 500}
ours: unmatched hits (text not mapped to a turn): 129 of 24961

TURN-LEVEL (user turns with has_answer), non-abstention, questions with >=1 gold user turn (n=419)
| system | any@1 | all@1 | any@3 | all@3 | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|---|---|---|---|
| ours | 71.1 | 20.0 | 92.1 | 66.6 | 95.2 | 79.5 | 96.9 | 86.4 | 98.8 | 95.9 |
| bm25 | 56.1 | 15.5 | 78.0 | 49.4 | 82.8 | 58.9 | 88.3 | 70.2 | 95.2 | 84.0 |
| bge | 55.1 | 14.6 | 80.0 | 47.0 | 86.6 | 62.8 | 93.6 | 78.8 | 98.3 | 95.0 |

TURN-LEVEL knowledge-update (n=72)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 98.6 | 93.1 | 98.6 | 97.2 | 98.6 | 97.2 |
| bm25 | 95.8 | 76.4 | 97.2 | 86.1 | 98.6 | 94.4 |
| bge | 94.4 | 79.2 | 98.6 | 93.1 | 98.6 | 97.2 |

TURN-LEVEL multi-session (n=121)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 97.5 | 68.6 | 99.2 | 80.2 | 99.2 | 90.9 |
| bm25 | 82.6 | 36.4 | 88.4 | 52.9 | 96.7 | 69.4 |
| bge | 90.9 | 48.8 | 96.7 | 68.6 | 99.2 | 90.9 |

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
| bge | 80.0 | 70.0 | 90.0 | 76.7 | 100.0 | 100.0 |

TURN-LEVEL single-session-user (n=64)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| bm25 | 92.2 | 92.2 | 95.3 | 95.3 | 98.4 | 98.4 |
| bge | 90.6 | 90.6 | 93.8 | 93.8 | 98.4 | 98.4 |

TURN-LEVEL temporal-reasoning (n=127)
| system | any@5 | all@5 | any@10 | all@10 | any@50 | all@50 |
|---|---|---|---|---|---|---|
| ours | 92.1 | 74.0 | 94.5 | 82.7 | 97.6 | 96.9 |
| bm25 | 80.3 | 61.4 | 87.4 | 71.7 | 94.5 | 86.6 |
| bge | 77.2 | 49.6 | 88.2 | 72.4 | 96.9 | 94.5 |

non-abstention questions with no gold user turn: Counter({'single-session-assistant': 51})
ingest s/q mean: 1.0082  total_s: 3800.2
