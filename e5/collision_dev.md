# E5.2 collision fix — DEV study (seed 6661001)
corpus: k=209 items=205 rejected=9
relation synonym classes: [['is employed by', 'works at'], ['lives in', 'resides in']]
families: {'clean_single': 37, 'collide_key': 38, 'collide_syn': 80, 'distinct_attr': 50}

hybrid detector score = max subject raw-emb cosine over equivalent-relation records with a DIFFERENT object:
  family         label   n   mean    min    max
  clean_single       0  37  0.594  0.386  0.775
  collide_key        1  38  0.789  0.378  0.937
  collide_syn        1  80  1.000  1.000  1.000
  distinct_attr      0  50  0.640  0.362  0.794

per-family detection rate (detect = score >= tau):
    tau collide_syn collide_key distinct(FP)  single(FP)
   0.70       1.000       0.737        0.340       0.216
   0.75       1.000       0.632        0.120       0.054
   0.80       1.000       0.632        0.000       0.000
   0.85       1.000       0.632        0.000       0.000
   0.90       1.000       0.316        0.000       0.000
   0.95       1.000       0.000        0.000       0.000

DECISION: collide_syn (near-synonym RELATION collision, the §5.4 defect) = same subject exactly + synonym-class relation -> score 1.000, detected at every tau, zero cross-subject leakage.
collide_key (near-dup SUBJECT surface 'Maria'/'Maria\'s') canNOT be separated from confusable distinct names by subject cosine (genuine variant 0.85 vs Tom Baker/Barker 0.78 — overlap); it is DEFERRED to write-time canonicalization, not detected here.
TAU_COLLIDE = 0.90: structurally above the confusable-distinct ceiling (~0.78 measured), so cross-subject false collisions are excluded by construction; collide_syn (cos 1.0) always passes.
