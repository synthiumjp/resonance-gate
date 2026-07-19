# E5.1 report — fair-corpus type-2 analysis (strict scoring primary)

artifact: rg-freeze-1.0 (frozen, read-only). judge model for leak: see e5/leak_v3.py (not run here).
seeds: dev_corpus=5551001 eval_corpus=5552001 assign=5552002 boot=5552003 perm=5552004
eval corpus: k=254 N=544 items=288 rejected_writes=6
strict accuracy=0.4410  either-object accuracy=0.7222
answered (routed ANSWER): 158  answered-errors (strict): 59  answered-errors (either): 7

[running VERBALISED-INFORMED on the mouth...]
## AUROC2 (STRICT scoring) — overall and restricted to answered items

| source | overall AUROC2 | 95% CI | answered-only AUROC2 |
|---|---|---|---|
| GATE(1-u) | 0.7380 | (0.6802, 0.7951) | 0.5160 |
| GATE(b) | 0.7375 | (0.6809, 0.7935) | 0.4763 |
| GATE(b/(b+d)) | 0.6797 | (0.6203, 0.7393) | 0.4458 |
| ORACLE | 0.6607 | (0.6229, 0.7007) | 0.5000 |
| ORACLE+cos | 0.7429 | (0.6854, 0.7997) | 0.5160 |
| FOIL-v2 | 0.7721 | (0.7204, 0.8236) | 0.6023 |
| VERBALISED-INF | 0.6663 | (0.6046, 0.7270) | 0.4408 |

answered-only n=158 (correct=99, errors=59) — the error-ranking test

## GATE vs ORACLE (the stage's number)
  GATE(1-u) - ORACLE (overall, strict): +0.0773 CI (+0.0244, +0.1278) — excludes 0
  GATE(b/(b+d)) - ORACLE (overall, strict): +0.0190 CI (-0.0308, +0.0704) — CONTAINS 0
  GATE(b) - ORACLE (overall, strict): +0.0769 CI (+0.0292, +0.1266) — excludes 0
  GATE(1-u) - ORACLE (ANSWERED-ONLY, strict): +0.0160 CI (-0.0759, +0.1042) — CONTAINS 0
  GATE(b/(b+d)) - ORACLE (ANSWERED-ONLY, strict): -0.0542 CI (-0.1442, +0.0428) — CONTAINS 0
  GATE(b) - ORACLE (ANSWERED-ONLY, strict): -0.0237 CI (-0.1144, +0.0704) — CONTAINS 0

  GATE(1-u) - ORACLE+cos (overall, strict): -0.0049 CI (-0.0134, +0.0032) — CONTAINS 0
  GATE(b/(b+d)) - ORACLE+cos (overall, strict): -0.0632 CI (-0.1307, +0.0060) — CONTAINS 0
  GATE(b) - ORACLE+cos (overall, strict): -0.0054 CI (-0.0421, +0.0336) — CONTAINS 0
  GATE(1-u) - ORACLE+cos (ANSWERED-ONLY, strict): +0.0000 CI (+0.0000, +0.0000) — CONTAINS 0
  GATE(b/(b+d)) - ORACLE+cos (ANSWERED-ONLY, strict): -0.0702 CI (-0.2033, +0.0697) — CONTAINS 0
  GATE(b) - ORACLE+cos (ANSWERED-ONLY, strict): -0.0397 CI (-0.0998, +0.0253) — CONTAINS 0

## H2 parity on a hard corpus (FOIL-v2 retrained on E5 dev)
  FOIL-v2 dev cross-fit AUROC2=0.7194; eval AUROC2=0.7721; GATE(1-u) eval=0.7380
  FOIL-v2 - GATE(1-u) gap (strict, overall): +0.0342 (Phase C margin was 0.02)

## Near-synonym collision behaviour (f_syn) — the audit A4 defect
  synonym pairs where BOTH member queries route ANSWER with DIFFERENT objects (confidently answers both ways): 40/74 = 0.541
  GATE 1-u on f_syn items: mean=0.7641 (clean-ID correct mean=0.8337) — u carries no ambiguity term, so collisions look confident
  stored-d AUC (f_syn collisions vs clean-ID): 0.7888 (Phase C on byte-identical keys: 1.0000)
  f_syn m_l2: min=0.5520 max=0.8477 mean=0.6510 (byte-identical collisions would be exactly 0)

## Per-family strict outcomes
| family | n | answered | ans_err | strict_acc | mean 1-u | mean ORACLE |
|---|---|---|---|---|---|---|
| f_confusable | 8 | 0 | 0 | 0.000 | 0.399 | 0.000 |
| f_distract | 8 | 8 | 0 | 1.000 | 0.867 | 1.000 |
| f_id | 36 | 33 | 1 | 0.944 | 0.824 | 1.000 |
| f_nearkey | 36 | 7 | 5 | 0.472 | 0.769 | 1.000 |
| f_ood | 40 | 0 | 0 | 0.000 | 0.336 | 0.000 |
| f_para | 6 | 0 | 0 | 0.167 | 0.527 | 0.000 |
| f_ref | 6 | 0 | 0 | 0.000 | 0.666 | 1.000 |
| f_syn | 148 | 110 | 53 | 0.453 | 0.764 | 1.000 |

## Phase C continuity (either-object scoring)
  GATE(1-u) either-object AUROC2=0.9363 (Phase C headline was 0.979)
  strict-scoring GATE(1-u)=0.7380 — the delta to the Phase C framing

## Descriptive
  meta-d' (strict): excluded (accuracy 0.441 outside window)
  ECE GATE(1-u) strict=0.2576

## Leak (leak_v3, LLM judge = qwen3:14b via llama-cpp GPU, pulled 2026-07-19)

Judge characterisation on the 60-item labelled set (INCLUDING the
negation/implication/temporal/attribution classes audit A5 proved leak_v2
misses): precision=1.000 recall=1.000 (tp=38 fp=0 fn=0 tn=22, parse_errors=0),
perfect on every class (direct 10/10, negation 8/8, implication 8/8,
temporal 8/8, attribution 4/4, tricky-negative 4/4). This is the checker
with teeth the audit called for.

Leak over 288 candidate outputs, facts relevance-filtered per output:
  judge-flagged: 2/288 = 0.0069
    answer                    0/154
    abstain                   0/88
    deliberate-referential    0/21   (+ 0/1 with lead-in)
    answer + lead-in          1/4
    abstain + lead-in         1/20
  On inspection the 2 flags are:
    - id 28 (answer+leadin): GENUINE leak. Mouth lead-in fabricated "Leo is
      getting ready for a meeting." over body "Leo Tran reports to Sofia
      Klein." — an event in no record. verify_leadin passed it because
      "meeting" is not in its ban regex (leak_v2's KEYWORD_RE *does* list
      "meeting", so leak_v2 would have caught THIS one — but misses the
      negation/implication class instead; the two checkers are blind to
      different things, audit A5).
    - id 24 (abstain+leadin): judge FALSE POSITIVE. "Got that?" flagged as
      an attribution; it is a benign social phrase. (charset precision was
      1.000; real free-text lead-ins have edge cases.)
  => genuine leak 1/288 = 0.35%, entirely in the free-text lead-in surface;
     all 263 templated bodies (answer/abstain/deliberate) are clean 0/263.

Coverage note: the deliberate-STORED surface ("I have two facts on file")
was never emitted in this run — the fair near-synonym collisions route to
ANSWER (different keys) and the near-duplicate keys route to
DELIBERATE-referential, so the stored-ambiguity path fires on nothing here.
That the stored path only triggers on Phase C's byte-identical keys is
itself the A4 finding, restated from the routing side.
