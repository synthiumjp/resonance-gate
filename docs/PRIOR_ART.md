# Prior art and timeline

This project's central idea -- a memory for AI agents in which **nothing can
generate a fact**, that **abstains honestly** when it holds no evidence,
and in which every stored fact carries **receipts** -- predates the "System
One" decision-model wave of September 2026 (TypeSafe's Jev, launched
2026-09-15; Jev-Mem, arXiv 2609.23986, 2026-09-21; JevMem and others).

Git commit dates are set by whoever commits, so they are not, on their own,
evidence. This page separates what is **independently timestamped by a third
party** from what is **self-dated**, so anyone can check the first kind
without trusting us.

## Independently timestamped (verifiable by anyone)

| date (UTC) | what | who timestamps it | how to verify |
|---|---|---|---|
| 2026-05-29 | Zenodo: *Making LLMs Say What They Know: Probe-Targeted Fine-Tuning for Verbal Confidence Calibration* (Cacioli) | Zenodo | record 20436841 |
| 2026-07-07 | Zenodo: *Repairing the Know-Say Gap: A No-Finetuning Probe-to-Logit Confidence Controller* (Cacioli) | Zenodo | record 21237443 |
| 2026-07-19 06:16 | OSF registration: *The Resonance Gate: confirmatory study of endogenous confidence in a VSA memory substrate* | OSF | osf.io/95e2q (`date_registered`) |
| 2026-07-19 06:55 | GitHub repository `synthiumjp/resonance-gate` created | GitHub | `GET /repos/synthiumjp/resonance-gate` -> `created_at` |
| 2026-07-20 | Zenodo: *The Resonance Gate: endogenous confidence from retrieval geometry in a vector-symbolic memory* (Cacioli) | Zenodo | record 21446859 |
| 2026-07-21 11:30 | Last push before this page: branch `product-p2` at commit `beb8772` | GitHub (push record) | the commit is on GitHub; its contents are below |

What the July-pushed tree (`beb8772`, on GitHub since 2026-07-21) already
states, in its own words:

- `CLAUDE.MD`: "a vector-symbolic memory substrate in which retrieval and
  confidence are the same operation. A frozen small transformer will later
  phrase gate-cleared content; **it is never a source of facts**."
- `docs/product-p2-prereg.md` (added 2026-07-20): the product
  pre-registration for a **write-side confidence gate** -- what may enter
  the memory, decided before anything reaches a language model, with loss
  asymmetry stated as "false assertion destroys trust".
- `experiments/p2/` and `docs/`: receipts, provenance, corroboration and
  abstention ("honest no-match") are already the design vocabulary --
  `git grep` at `beb8772` finds them in the pre-registration, the handover
  and the belief store.

## Self-dated (commit history, pushed 2026-10-02)

The conversation-memory product was built between 2026-07-21 and
2026-10-02 and pushed in one batch on 2026-10-02, so for this span GitHub
records only that the commits *arrived* on 2026-10-02. The commit dates and
the append-only lab notebook (`notebook.md`, one dated entry per change) give
the sequence. Milestones relevant to the System-One comparison, as dated in
the notebook:

| notebook date | entry | what |
|---|---|---|
| 2026-08-20 to 08-21 | e227-e237 | deterministic grammar parser replaces LLM extraction: zero model calls at write time, replicated on a second user |
| 2026-09-04 | e264-e271 | refusal of non-assertions at write time (questions, hypotheticals, hedges, negation) as a CommitmentBank x CheckList matrix |
| 2026-09-04 | e273-e274 | currency (a superseded fact must not answer first) and contradiction surfaced as a question rather than resolved silently |
| 2026-09-06 | e280 | refusals as named predicates over an empty result set (adopted after reading a post about a zero-LLM PubMed graph; credited there) |

Each commit's hash covers its parent's, so the history cannot be re-dated
piecemeal without changing every later hash -- but a whole history could in
principle be fabricated, which is why the table above is the evidence and
this one is the narrative.

## Keeping it verifiable

Pushing after each working session gives every later change a GitHub-side
timestamp. For a stronger anchor, the current commit hash can be stamped
with OpenTimestamps (`ots stamp`), which records it in the Bitcoin
blockchain.
