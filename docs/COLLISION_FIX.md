# Collision fix (rg-1.1) — near-synonym stored contradictions

Branch `product-p0` off `rg-freeze-1.0`. The frozen research artifact is
untouched; this is the first product-line change. Full rationale: notebook
entry 20. Measurements: `e5/collision_dev.md`, `e5/collision_eval.md`.

## The defect (blocks a memory product)

The frozen artifact detects a stored collision by **key identity**: two
records collide only when their whitened `(subject, relation)` vectors are
identical, i.e. the *same surface strings*. So a contradiction written under
**near-synonym relations** is invisible:

> "Maria lives in Lisbon."  +  "Maria resides in Boston."

Two different residences on file, but "lives in" and "resides in" are
different keys, so the gate answers **Lisbon** to one phrasing and **Boston**
to the other — confidently, both ways, with no conflict flag. Measured
answers-both-ways rate: **54%** on the E5.1 corpus (audit A4), **80%** on the
purpose-built E5.2 corpus. A product that silently contradicts itself
depending on how you phrase the question is not shippable.

## The fix — semantic stored-collision detection

`gate/l2_ambiguity.semantic_collision` redefines a collision as *the same
question asked twice, answered differently*:

> a stored record collides with the query key iff it has the **same canonical
> subject entity**, an **equivalent relation**, and a **different object**.

The continuous collision score `c_sem ∈ [0,1]` (max qualifying subject
cosine) drives a new stored `d`-source in `opinion_two_source`
(`sigmoid((c_sem − TAU_COLLIDE)/S_COLLIDE)`). With `collision_mode="key"` the
detector is bypassed and the frozen `m_l2` key-identity margin is used
unchanged — that is the exact `rg-freeze-1.0` behaviour, retained for the
BEFORE arm.

### Why not pure embedding cosine (the honest deviation)

The original spec was "near-duplicate keys by **raw embedding cosine** above
`τ_collide`". Measured on the frozen MiniLM registry, raw cosine cannot do
this on **either** axis:

| axis | genuine collision | confusable NON-collision | separable? |
|---|---|---|---|
| relation | works at / is employed by = **0.427** | studied at / works at = **0.557**; lives in / was born in = 0.521 | **no** |
| subject | Maria Garcia / Maria Garcia's = **0.850** | Tom Baker / Tom Barker = **0.784**; Anna Chen / Cheng = 0.769 | **no** |

The true synonym embeds *less* similarly than a distinct-but-related pair;
the genuine name variant embeds *barely* above confusable different people.
So the fix uses:

- **Subject axis — raw embedding cosine** (the spec's mechanism, where it is
  the right tool) with `TAU_COLLIDE = 0.90`, set structurally **above** the
  confusable-distinct-name ceiling (~0.78) so cross-subject false collisions
  are excluded by construction.
- **Relation axis — an explicit synonym-class table** (`RELATION_SYNONYMS`),
  because cosine provably cannot separate synonyms from related relations
  here. In production the table is populated from a paraphrase resource; a
  relation-paraphrase embedding would let this axis be a cosine test too.

`τ_collide` was set on the E5.2 **dev** seed (6661001) only; the numbers below
are the **held-out** seed (6662001).

### Deferred: near-duplicate SUBJECT surfaces

"Maria Garcia" vs "Maria Garcia's" (cos 0.85) falls below `TAU_COLLIDE` and is
**not** detected — no threshold separates it from confusable distinct
surnames (table above). This is a **write-time entity-canonicalization**
concern (resolve near-dup surfaces to one canonical entry, which makes it the
exact-key collision the existing mechanism already handles), not a
collision-detection concern. It is out of scope for rg-1.1 and reported
honestly as unchanged (`collide_key`: 0/20 flagged).

## Passive collision vs explicit update (two distinct events)

- **Passive collision** — two co-equal writes disagree. Recall returns
  **both** facts (`QueryResult.candidates`, each with provenance),
  `conflict=True`, and an advisory `resolution_hint = {by_recency,
  by_resolution}` the caller **may apply or ignore**. The server does **not**
  choose. Route: `DELIBERATE` / tag `stored`.
- **Explicit update** — a later `supersede()` / correction. This **does**
  resolve: the old record is tombstoned via the existing supersedes-chain
  (so it is no longer active and cannot re-collide), the successor is
  written, the audit trail is retained. Unchanged from the frozen artifact.

A collision is never silently resolved; a correction always is.

## Measured before/after (held-out seed 6662001)

| metric | BEFORE (frozen) | AFTER (rg-1.1) |
|---|---|---|
| near-synonym answers-both-ways | 32/40 = **0.800** | 0/40 = **0.000** |
| near-synonym detection AUROC | 0.6173 | **1.0000** |
| false-collision rate (distinct attributes) | 0/29 | **0/29 = 0.000** |
| all-negative items false-flagged | — | 0/97 = 0.000 |
| collide_key (near-dup subject, deferred) | 0.10 both-ways | 0.10 (unchanged) |

**Exit criteria** (answers-both-ways < 5% AND near-synonym detection
AUROC > 0.90): **GREEN**. Frozen regression suite: 33 passed, 1 xfailed with
the semantic default on.

## Tunables (gate/l2_ambiguity.py)

- `RELATION_SYNONYMS` — `{works at, is employed by}`, `{lives in, resides in}`
- `TAU_COLLIDE = 0.90` — subject raw-embedding cosine threshold
- `S_COLLIDE = 0.03` — semantic stored `d`-source sigmoid slope
