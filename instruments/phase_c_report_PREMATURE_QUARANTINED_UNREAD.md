# Phase C confirmatory report (single registered run)

registration: https://osf.io/95e2q/ filed 2026-07-19T16:16
seeds: corpus=888000011 assign=888000012 boot=888000013 perm=888000014
corpus: k=237 N=500 items=280 forced accuracy=0.6107

| source | AUROC2 | 95% CI |
|---|---|---|
| GATE(1-u) | 0.9808 | (0.9654, 0.9931) |
| FOIL | 0.9858 | (0.9700, 0.9962) |
| VERBALISED | 0.4631 | (0.3989, 0.5250) |
| JUDGE | 0.4699 | (0.4078, 0.5353) |
| PROBE | 0.5331 | (0.4651, 0.6022) |
| GATE(b) | 0.9213 | (0.8873, 0.9500) |
| GATE(b/(b+d)) | 0.8337 | (0.7787, 0.8866) |

H1 : diff GATE(1-u)-VERBALISED CI (+0.4551, +0.5805) -> PASS
H2 : FOIL-GATE gap +0.0050 (margin 0.02) -> PASS
H2b: PROBE CI (0.4651, 0.6022) contains 0.5 -> PASS
H3 : referential AUC 1.0000, stored AUC 1.0000 (floors 0.90) -> PASS
H4 : ungrounded leak 0/57 = 0.0000 (<= 0.02) -> PASS; grounded 0/63; checker precision=0.938 recall=1.000
permutation null: mean=0.4993 sd=0.0369 p=<0.001
meta-d': d'=0.562 meta-d'=4.543 M=8.078
ECE (descriptive, no calibration fit): {'GATE(1-u)': np.float64(0.1846), 'FOIL': np.float64(0.036), 'VERBALISED': np.float64(0.1732), 'JUDGE': np.float64(0.425), 'PROBE': np.float64(0.066), 'GATE(b)': np.float64(0.345), 'GATE(b/(b+d))': np.float64(0.272)}
