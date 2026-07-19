# Phase C confirmatory report (single registered run)

registration: https://osf.io/95e2q/ filed 2026-07-19T16:16
seeds: corpus=777000001 assign=777000002 boot=777000003 perm=777000004
corpus: k=236 N=500 items=280 forced accuracy=0.6143

| source | AUROC2 | 95% CI |
|---|---|---|
| GATE(1-u) | 0.9619 | (0.9357, 0.9823) |
| FOIL | 0.5000 | (0.5000, 0.5000) |
| VERBALISED | 0.5097 | (0.4402, 0.5746) |
| JUDGE | 0.4619 | (0.4000, 0.5262) |
| PROBE | 0.4601 | (0.3910, 0.5256) |
| GATE(b) | 0.9260 | (0.8923, 0.9552) |
| GATE(b/(b+d)) | 0.8545 | (0.8022, 0.9052) |

H1 : diff GATE(1-u)-VERBALISED CI (+0.3811, +0.5240) -> PASS
H2 : FOIL-GATE gap -0.4619 (margin 0.02) -> PASS
H2b: PROBE CI (0.3910, 0.5256) contains 0.5 -> PASS
H3 : referential AUC 1.0000, stored AUC 1.0000 (floors 0.90) -> PASS
H4 : ungrounded leak 0/61 = 0.0000 (<= 0.02) -> PASS; grounded 1/59; checker precision=1.000 recall=1.000
permutation null: mean=0.4986 sd=0.0364 p=<0.001
meta-d': d'=0.581 meta-d'=3.837 M=6.604
ECE (descriptive, no calibration fit): {'GATE(1-u)': np.float64(0.15), 'FOIL': np.float64(0.6143), 'VERBALISED': np.float64(0.1355), 'JUDGE': np.float64(0.4089), 'PROBE': np.float64(0.0648), 'GATE(b)': np.float64(0.3506), 'GATE(b/(b+d))': np.float64(0.2918)}
