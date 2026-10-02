# Prior art and timeline

This project is a memory for AI agents that does not generate facts, returns
"unknown" when it has no evidence, and records where each fact came from.
The work started before the "System One" decision models released in
September 2026 (TypeSafe's Jev, launched 2026-09-15; Jev-Mem, arXiv
2609.23986, 2026-09-21).

Git commit dates are set by the committer and can't be used as evidence on
their own. The first table lists dates recorded by third parties, which
anyone can check. The second lists dates from our own commit history.

## Third-party timestamps

| date (UTC) | item | recorded by | check |
|---|---|---|---|
| 2026-05-29 | Zenodo: *Making LLMs Say What They Know: Probe-Targeted Fine-Tuning for Verbal Confidence Calibration* (Cacioli) | Zenodo | record 20436841 |
| 2026-07-07 | Zenodo: *Repairing the Know-Say Gap: A No-Finetuning Probe-to-Logit Confidence Controller* (Cacioli) | Zenodo | record 21237443 |
| 2026-07-19 06:16 | OSF registration: *The Resonance Gate: confirmatory study of endogenous confidence in a VSA memory substrate* | OSF | osf.io/95e2q, `date_registered` |
| 2026-07-19 06:55 | GitHub repository `synthiumjp/resonance-gate` created | GitHub | `GET /repos/synthiumjp/resonance-gate`, `created_at` |
| 2026-07-20 | Zenodo: *The Resonance Gate: endogenous confidence from retrieval geometry in a vector-symbolic memory* (Cacioli) | Zenodo | record 21446859 |
| 2026-07-21 11:30 | Push of branch `product-p2` at commit `beb8772` | GitHub | the commit and its tree are on GitHub |

Contents of the tree pushed on 2026-07-21 (`beb8772`):

- `CLAUDE.MD`: "a vector-symbolic memory substrate in which retrieval and
  confidence are the same operation. A frozen small transformer will later
  phrase gate-cleared content; it is never a source of facts."
- `docs/product-p2-prereg.md` (added 2026-07-20): pre-registration of a
  write-side confidence gate that decides what may enter the memory before
  any language model sees it, with the stated loss asymmetry "false
  assertion destroys trust".
- `experiments/p2/` and `docs/`: receipts, provenance, corroboration and
  abstention ("honest no-match") appear throughout the pre-registration, the
  handover notes and the belief store (`git grep` at `beb8772`).

## Commit history (self-dated)

The conversation-memory product was built between 2026-07-21 and 2026-10-02
and pushed on 2026-10-02, so GitHub only records that those commits arrived
on that date. The commit dates and the lab notebook (`notebook.md`, one dated
entry per change, append-only) give the order:

| notebook date | entries | change |
|---|---|---|
| 2026-08-20 to 08-21 | e227-e237 | grammar parser replaces LLM extraction (no model calls at write time); replicated on a second user |
| 2026-09-04 | e264-e271 | questions, hypotheticals, hedges and negations are not stored as facts; tested as a CommitmentBank x CheckList matrix |
| 2026-09-04 | e273-e274 | a replaced fact is not returned first; contradictions are raised as a question |
| 2026-09-06 | e280 | refusals implemented as named checks over an empty result (adapted from a post about a zero-LLM PubMed graph, credited in the notebook) |

Each commit hash depends on its parent, so individual commits can't be
re-dated without changing every later hash. A whole history could still be
fabricated, which is why the third-party table is the evidence and this one
is the record.

## Going forward

Pushing after each working session gives each change a GitHub timestamp. For
a stronger record, the current commit hash can be anchored with
OpenTimestamps (`ots stamp`).
