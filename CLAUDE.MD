# Resonance Gate (RG) — project context

## What this is
A research build: a vector-symbolic (VSA/hyperdimensional) memory substrate in
which retrieval and confidence are the same operation. A frozen small
transformer will later phrase gate-cleared content; it is never a source of
facts. Current phase: E1 (exploratory substrate core). Full plan in
docs/rg-project-plan-v1.md — read it before proposing anything.

## Hard rules
- Phase E is exploratory: iterate freely, but EVERY design change gets a
  dated entry in notebook.md (append-only) with one line of rationale.
- All randomness seeded. Every script takes/prints its seed. No exceptions —
  the confirmatory phase depends on exact reproducibility.
- NumPy only for the substrate. No torch, no GPU, no external services.
  The substrate being trivial on CPU is a design claim we are proving.
- Do NOT build ahead of the current stage. No gate logic, no LLM integration,
  no MCP, no resonator networks until their stage. If a task seems to need
  them, stop and say so.
- Tests accompany every module. Exit criteria below are the definition of done.

## Substrate spec (fixed for E1 — do not redesign)
- Algebra: MAP. Bipolar int8 vectors in {-1,+1}, default D=8192 (D=16384
  as a comparison arm).
- bind(a,b) = a*b elementwise (self-inverse).
- permute(v,k) = np.roll(v,k); inverse is roll(v,-k).
- bundle(list) = sign(sum), zero ties broken by a seeded coin (deterministic
  given seed).
- Record: R = subj * permute(rel,1) * permute(obj,2).
- Retrieval of obj from a record or bundle B given (subj, rel):
  permute(B * subj * permute(rel,1), -2), then cleanup.
- Cleanup: cosine against the codebook matrix; return top-2 as
  [(name, cos)]. The sorted cosines are load-bearing: a = s1 (resolution),
  m = s1 - s2 (margin). Always compute and return both.

## Layout
rg/
  substrate/       # map_ops.py, tests, capacity sweep
  gate/            # E2 — empty for now
  mouth/           # E3 — empty for now
  instruments/     # E4 — empty for now
  docs/            # project plan
  notebook.md      # append-only lab log

## Stage E1 exit criteria (from the plan)
1. Round-trip: 50 triples in one bundle at D=8192, object retrieval by
   (subj, rel) with cleanup accuracy >= 0.99.
2. Capacity curves: for k in {10,25,50,100,200,350,500}, distributions of
   a and m for in-memory queries (hits) AND never-written queries (misses),
   >= 20 fresh-substrate trials per k, object codebook >= 500 entries.
   Output CSV: k, accuracy, a_hit mean/sd, a_miss mean/sd, m_hit mean/sd,
   hit-vs-miss Cohen's d. These curves are the mu(k,D,N)/sigma(k,D,N)
   inputs for the E2 load-normalised gate — measure them carefully.
3. Write path is O(1): appending fact k+1 must not touch facts 1..k.
   Demonstrate with a timing test flat in k.
4. Everything reproducible from a clean checkout with one command.

