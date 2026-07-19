# Phase C confirmatory report (single registered run)

registration: https://osf.io/95e2q/ filed 2026-07-19T16:16
seeds: corpus=999000021 assign=999000022 boot=999000023 perm=999000024
corpus: k=233 N=500 items=280 forced accuracy=0.6357

| source | AUROC2 | 95% CI |
|---|---|---|
| GATE(1-u) | 0.9790 | (0.9645, 0.9907) |
| FOIL | 0.9920 | (0.9830, 0.9983) |
| VERBALISED | 0.4933 | (0.4339, 0.5564) |
| JUDGE | 0.4955 | (0.4321, 0.5594) |
| PROBE | 0.5120 | (0.4390, 0.5862) |
| GATE(b) | 0.9359 | (0.9055, 0.9635) |
| GATE(b/(b+d)) | 0.8570 | (0.8039, 0.9098) |

H1 : diff GATE(1-u)-VERBALISED CI (+0.4226, +0.5456) -> PASS
H2 : FOIL-GATE gap +0.0130 (margin 0.02) -> PASS
H2b: PROBE CI (0.4390, 0.5862) contains 0.5 -> PASS
H3 : referential AUC 1.0000, stored AUC 1.0000 (floors 0.90) -> PASS
H4 : ungrounded leak 0/60 = 0.0000 (<= 0.02) -> PASS; grounded 0/60; checker precision=1.000 recall=1.000
permutation null: mean=0.4992 sd=0.0363 p=<0.001
meta-d': d'=0.694 meta-d'=5.466 M=7.876
ECE (descriptive, no calibration fit): {'GATE(1-u)': np.float64(0.1593), 'FOIL': np.float64(0.0526), 'VERBALISED': np.float64(0.1482), 'JUDGE': np.float64(0.4071), 'PROBE': np.float64(0.0363), 'GATE(b)': np.float64(0.3824), 'GATE(b/(b+d))': np.float64(0.3127)}
