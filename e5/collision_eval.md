# E5.2 collision fix — BEFORE/AFTER (held-out seed 6662001)
corpus: k=218 items=217 families={'clean_single': 39, 'collide_key': 40, 'collide_syn': 80, 'distinct_attr': 58}
TAU_COLLIDE=0.9

## Collision detection AUROC (near-synonym collide_syn vs clean_single+distinct_attr)
  BEFORE (frozen key-identity stored-d, from m_l2): 0.6173
  AFTER  (semantic collision score c_sem):          1.0000

## Answers-both-ways rate (the 54% §5.4 defect)
  collide_syn: BEFORE 32/40 = 0.800  ->  AFTER 0/40 = 0.000
  collide_key: BEFORE 2/20 = 0.100  ->  AFTER 2/20 = 0.100  (DEFERRED: near-dup subject surface)

## Conflict-detection rate per family (AFTER)
  collide_syn: 39/40 pairs flagged = 0.975
  collide_key: 0/20 pairs flagged = 0.000

## False-collision rate (FP guard — must stay ~0)
  distinct_attr pairs flagged: BEFORE 0/29 -> AFTER 0/29 = 0.000
  ALL negative items (clean_single+distinct_attr) flagged AFTER: 0/97 = 0.000

## EXIT CRITERIA
  near-synonym answers-both-ways AFTER = 0.000  (< 0.05 required) -> PASS
  near-synonym detection AUROC AFTER  = 1.0000 (> 0.90 required) -> PASS
  false-collision rate (distinct_attr) = 0.000 (guard: ~0) -> PASS
  ==> E5.2 EXIT GREEN
