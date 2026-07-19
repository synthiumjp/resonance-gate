# E4 dress rehearsal report

(post-freeze regeneration, 2026-07-19, frozen constants C_L2=0.4528/S_L2=0.0342 — Deviation 3; this provenance line added at commit time)

seed=20260719 quick=False backend=GPU wall=116s
corpus: k=235 N=500 items=280 forced-answer accuracy=0.625

## AUROC2 (paired bootstrap B=2000 seed=20260730)

| source | AUROC2 | 95% CI | ECE | meta-d' | M-ratio |
|---|---|---|---|---|---|
| GATE(b) | 0.9044 | (0.8675, 0.9392) | 0.3615 | 2.914 | 4.572 |
| VERBALISED | 0.4881 | (0.4252, 0.5500) | 0.1471 | 0.000 | 0.000 |
| PROBE | 0.4993 | (0.4295, 0.5688) | 0.0918 | 0.032 | 0.051 |
| JUDGE | 0.5129 | (0.4543, 0.5754) | 0.4089 | 0.144 | 0.226 |
| NULL(strata) | 0.9044 | (0.8686, 0.9364) | 0.3615 | 2.914 | 4.572 |
| NULL(full) | 0.5728 | (0.5010, 0.6392) | 0.3961 | 0.488 | 0.766 |

permutation test (GATE vs full shuffle, n_perm=1000 seed=20260733): null mean=0.4995 sd=0.0354 p=<0.001
gate secondaries: {'gate_b_over_bd': np.float64(0.8252244897959183), 'gate_1mu': np.float64(0.9567346938775511)}

diff GATE(b) - VERBALISED: +0.4163 CI (+0.3448, +0.4883)
diff GATE(b) - PROBE: +0.4051 CI (+0.3277, +0.4848)
diff GATE(b) - JUDGE: +0.3916 CI (+0.3207, +0.4585)
diff GATE(b) - NULL(strata): +0.0000 CI (-0.0498, +0.0497)
diff GATE(b) - NULL(full): +0.3316 CI (+0.2525, +0.4150)
diff VERBALISED - PROBE: -0.0112 CI (-0.1046, +0.0923)
diff VERBALISED - JUDGE: -0.0247 CI (-0.0761, +0.0265)
diff VERBALISED - NULL(strata): -0.4163 CI (-0.4879, -0.3416)
diff VERBALISED - NULL(full): -0.0847 CI (-0.1707, +0.0041)
diff PROBE - JUDGE: -0.0136 CI (-0.1065, +0.0740)
diff PROBE - NULL(strata): -0.4051 CI (-0.4836, -0.3262)
diff PROBE - NULL(full): -0.0736 CI (-0.1733, +0.0279)
diff JUDGE - NULL(strata): -0.3916 CI (-0.4576, -0.3214)
diff JUDGE - NULL(full): -0.0600 CI (-0.1477, +0.0286)
diff NULL(strata) - NULL(full): +0.3316 CI (+0.2577, +0.4087)

## leak_v2
grounded: 0/37 = 0.000
ungrounded: 0/55 = 0.000
checker: precision=0.938 recall=1.000 (tp=15 fp=1 fn=0 tn=44, seed=20260732)

### checker sample for review (real outputs, flags)
- flag=1 'Hey, did you hear about the wedding? Nora Hansen is married to Michael Souza.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Laura Olson studied at Nora Lowe.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'James (brother) reports to Alice Tran.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Nora Schmidt is a sibling of Daniel Zheng.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Zenith Labs is a sibling of Zoe Fischer.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Felix (landlord) studied at Felix Sousa.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Michael (colleague) lives in Nina (landlord).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Nora (neighbour) works at Simon (landlord).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Robert (brother) lives in Cambridge (MA).'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Pioneer Energy manages Maya Schmidt.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Ruth (old classmate) works at Victor Zheng.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Vertex Systems was born in Acme Labs.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Victor Zheng was born in Tom Schmitt.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'Emma (colleague) works at Maya Jones.'
- flag=0 "I don't have that. Want me to note it?"
- flag=0 'John (manager) was born in Zoe Meyer.'
- flag=0 "I don't have that. Want me to note it?"

## power / freeze parameters
H1 (GATE vs VERBALISED): dev gap=+0.4163, per-item sd=0.610, n for 80% power at alpha=.05: 17
H2 (GATE vs PROBE): dev gap=+0.4051 (margin question: is |gap| <= 0.02 realistic?)
