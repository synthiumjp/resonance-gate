# E4 dress rehearsal report

seed=20260719 quick=True backend=CPU (RG_CPU=1) wall=1271s
corpus: k=52 N=150 items=22 forced-answer accuracy=0.636

## AUROC2 (paired bootstrap B=2000 seed=20260730)

| source | AUROC2 | 95% CI | ECE | meta-d' | M-ratio |
|---|---|---|---|---|---|
| GATE(b) | 1.0000 | (1.0000, 1.0000) | 0.3297 | 6.000 | 8.602 |
| VERBALISED | 0.5000 | (0.2529, 0.7286) | 0.1705 | 0.222 | 0.319 |
| PROBE | 0.4821 | (0.2066, 0.7619) | 0.3560 | 0.001 | 0.001 |
| JUDGE | 0.3661 | (0.1538, 0.6111) | 0.4318 | 0.003 | 0.004 |
| NULL(strata) | 1.0000 | (1.0000, 1.0000) | 0.3297 | 6.000 | 8.602 |
| NULL(full) | 0.4018 | (0.1429, 0.6771) | 0.5461 | 0.000 | 0.000 |

permutation test (GATE vs full shuffle, n_perm=1000 seed=20260733): null mean=0.5016 sd=0.1252 p=<0.001
gate secondaries: {'gate_b_over_bd': np.float64(0.7857142857142857), 'gate_1mu': np.float64(1.0)}

diff GATE(b) - VERBALISED: +0.5000 CI (+0.2714, +0.7471)
diff GATE(b) - PROBE: +0.5179 CI (+0.2381, +0.7934)
diff GATE(b) - JUDGE: +0.6339 CI (+0.3889, +0.8462)
diff GATE(b) - NULL(strata): +0.0000 CI (+0.0000, +0.0000)
diff GATE(b) - NULL(full): +0.5982 CI (+0.3229, +0.8571)
diff VERBALISED - PROBE: +0.0179 CI (-0.2946, +0.3292)
diff VERBALISED - JUDGE: +0.1339 CI (-0.0292, +0.3292)
diff VERBALISED - NULL(strata): -0.5000 CI (-0.7471, -0.2714)
diff VERBALISED - NULL(full): +0.0982 CI (-0.2810, +0.4380)
diff PROBE - JUDGE: +0.1161 CI (-0.2143, +0.4420)
diff PROBE - NULL(strata): -0.5179 CI (-0.7934, -0.2381)
diff PROBE - NULL(full): +0.0804 CI (-0.3036, +0.4476)
diff JUDGE - NULL(strata): -0.6339 CI (-0.8462, -0.3889)
diff JUDGE - NULL(full): -0.0357 CI (-0.3612, +0.2589)
diff NULL(strata) - NULL(full): +0.5982 CI (+0.3229, +0.8571)

## leak_v2
grounded: 1/7 = 0.143
ungrounded: 0/8 = 0.000
checker: precision=1.000 recall=1.000 (tp=15 fp=0 fn=0 tn=45, seed=20260732)

### checker sample for review (real outputs, flags)
- flag=0 'Hugo Fisher is married to Orion Energy.'
- flag=0 "Can't help with that one. I don't have that. Want me to note it?"
- flag=0 'Michael (manager) studied at Ella Wong.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Hello there, how can I assist you today? Cascade Systems reports to Apex Consulting.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Ashford is a sibling of Max Sousa.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Sarah Webber is a sibling of Beacon Media.'
- flag=0 "Hi, what do you need help with today? I don't have that. Want me to note it?"
- flag=0 'Emma (old classmate) is a sibling of Sofia (brother).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Tom (colleague) is a sibling of Tom Wang.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Michael Weber lives in Robert (brother).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Anna (brother) lives in Clara Johnson.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Lena (manager) reports to Nina Olsen.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Emma (old classmate) is a sibling of Sofia (brother).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Sofia (brother) is a sibling of Ashford.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Portland (OR) lives in Dayton.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'James (colleague) is married to Laura (brother).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Hugo Fisher is married to Orion Energy.'
- flag=0 "I don't have that. Want me to note it?"

## power / freeze parameters
H1 (GATE vs VERBALISED): dev gap=+0.5000, per-item sd=0.566, n for 80% power at alpha=.05: 11
H2 (GATE vs PROBE): dev gap=+0.5179 (margin question: is |gap| <= 0.02 realistic?)
