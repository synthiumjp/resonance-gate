# RG freeze checklist — complete tunables inventory

Everything that freezes at the week-12 tag. "Last changed" cites the
notebook entry where the value was set or last moved. Values current as of
2026-07-19 (E4). The freeze commit records this file plus the artifact hash.

## Substrate geometry
| tunable | value | last changed |
|---|---|---|
| D (dimension) | 8192 | entry 7 (D=16384 arm dropped, entry 6 finding) |
| Algebra | MAP: bind=elementwise product, permute=np.roll, bundle=sign(sum), seeded tie-break | entry 1 (E1 spec, never moved) |
| Record shape | subj * p1(rel) * p2(obj) | entry 1 |
| Provenance carriage | L2 entry metadata, NOT bound into the record | entry 9 (design note) |

## Encoder / interface layer
| tunable | value | last changed |
|---|---|---|
| Embedding model | sentence-transformers/all-MiniLM-L6-v2 @ 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 | entry 5 |
| Projection seed / shape | 314 / 8192x384 Gaussian, sign() | entry 5 |
| Whitening | shrinkage ZCA, lambda = 0.75 (substrate-side only), eps=1e-5, fit pool = entities seeds 660/661 | entry 8 (chosen), entry 7 (design) |
| Interface geometry | RAW embedding cosine (registry resolve) | entry 7 |
| WRITE_MERGE_COSINE (entity canon) | 0.95 | entry 9 |
| REL_MERGE_COSINE (relation canon) | 0.80 | entry 9 |
| Registry resolve top-k | 2 | entry 8 |

## Gate
| tunable | value | last changed |
|---|---|---|
| THETA / ALPHA / BETA | 0.0 / 1.0 / 1.0 | entry 4 |
| z zero-point | variance-weighted hit/null crossing | entry 4 |
| Moments mode | EMBEDDED full-measured (calibrate_null k=100 t=4; calibrate_hit k_refs 25/50/100 t=3) | entries 5, 6 |
| Paging safety fraction | 0.5 (paging = 280 at lambda=0.75, N=500) | entry 4 (set), entry 8 (value) |
| Saturation gamma | 1.0 null-sd | entry 4 |
| C_REF / S_REF (referential d) | 0.19 / 0.08 | entry 9 (from Part-0c) |
| C_L2 / S_L2 / BETA_L2 (stored d) | 0.15 / 0.08 / 1.0 | entry 6 (placeholders — CALIBRATE BEFORE FREEZE) |
| Controller U_IGNORANT / U_WEAK | 0.85 / 0.35 | entry 4 |
| Two-source d combination | max of z-normalised sources; L1 margin fast-path only | entry 7 |

## Mouth
| tunable | value | last changed |
|---|---|---|
| Model file | SmolLM3-Q4_K_M.gguf sha256 8334b850b7bd46238c16b0c550df2138f0889bf433809008cc17a8b05761863e | entry 5 |
| Runtime | llama-cpp-python 0.3.34 (hipBLAS gfx1100 build; RG_CPU=1 fallback pinned) | entry 9 |
| Template table | 10 relations + fallback; sha256[:16] 26135bf6e928f53b | entry 9 |
| verify_leadin constraints | no digits, no relation vocab, no proper nouns past token 1, <= 8 words | entry 9 |
| Extraction prompt | EXTRACT_SYSTEM v3 ("Utterance:" wrapper, 12 examples, hedge post-guard, deterministic qualifier binding) | entry 9 |
| Query-parse prompt | QUERY_SYSTEM v1 (6 examples) | entry 9 |
| Elicitation prompts | VERBALISE_PROMPT v1, JUDGE_PROMPT v1 (instruments/baselines.py) | entry 10 |

## Instruments
| tunable | value | last changed |
|---|---|---|
| GATE scalar (primary) | b (secondaries b/(b+d), 1-u logged) | entry 10 |
| Pseudo-2AFC / bootstrap | B=2000, seeds in report; AUROC2 rank-based | entry 10 |
| meta-d' | response-conditional, single-interval, 4 quantile bins, window 0.55-0.95, Guggenmos d'<0.2 exclusion | entry 10 |
| ECE bins | 10 equal-width | entry 10 |
| Probe method | ADAPTATION: logistic head over answer-token logit features (docs/ method absent — reconcile before freeze if doc lands) | entry 10 |
| Leak checker | claim-extraction + surface union, RESOLVE_SUPPORT=0.90; characterisation seed in report | entry 10 |
| Corpus config | CorpusConfig defaults (500/160/120/120/20/20), seed 20260719 (dev) | entry 10 |

## Known gaps to close before the freeze
1. C_L2/S_L2/BETA_L2 are uncalibrated placeholders (AUC-insensitive, but the
   freeze should record measured values).
2. Probe method + type-2 apparatus implemented from literature, not the
   Synthium docs (absent from docs/) — reconcile or record as v1-adapted.
3. Confirmatory corpus generator must be run with a DISJOINT seed family
   (registered at freeze; dev family is 20260719).
