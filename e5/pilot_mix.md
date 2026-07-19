# E5.1 pilot log — family-mix tuning (DEV seed 5551001 only)

Tuning trajectory (answered-errors, strict, frozen artifact):
  1. initial mix (id=100, ood=50, syn=30, nearkey=16, conf=30, para=12, ref=12): 16 — most hazards routed RECOLLECT/DELIBERATE; f_confusable 30/30 recollect (kept as a finding).
  2. + isolation filter (subjects for f_syn/f_id/f_distract need registry m_ref >= 0.25) + f_distract family; id=40, syn=55, conf=15, distract=15: 52.
  3. syn=65, conf=12, distract=8: 60 (k=244).
  4. syn=72: 61 (k=259 — recollect eats the gain near paging).
  5. FINAL: syn=74, id=36, conf=8, para=6, distract=8: 63 at k=251. Frozen as CorpusV2Config defaults.

pilot seed=5551001: k=251 N=543 items=285 rejected_writes=12
  f_confusable   n=  8 answered=  0 ans_err=  0 ans_ok=  0 routes={'recollect': 8}
  f_distract     n=  8 answered=  7 ans_err=  1 ans_ok=  6 routes={'answer': 7, 'recollect': 1}
  f_id           n= 36 answered= 26 ans_err=  0 ans_ok= 26 routes={'answer': 26, 'recollect': 10}
  f_nearkey      n= 34 answered=  6 ans_err=  4 ans_ok=  2 routes={'deliberate': 23, 'answer': 6, 'recollect': 5}
  f_ood          n= 40 answered=  0 ans_err=  0 ans_ok=  0 routes={'recollect': 40}
  f_para         n=  6 answered=  0 ans_err=  0 ans_ok=  0 routes={'recollect': 6}
  f_ref          n=  5 answered=  0 ans_err=  0 ans_ok=  0 routes={'deliberate': 5}
  f_syn          n=148 answered=115 ans_err= 58 ans_ok= 57 routes={'recollect': 33, 'answer': 115}
  TOTAL answered-errors (strict): 63  (target >= 60)

final default config: CorpusV2Config(seed=5551001, n_entities=500, n_id=36, n_ood=40, n_syn_pairs=74, n_nearkey=18, n_confusable=8, n_para=6, n_ref=8, n_distract=8, min_m_ref=0.25)
