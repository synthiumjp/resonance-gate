# Pre-registration: the wider list detector on LoCoMo test (2026-10-17)

Approved by JP on 2026-10-17 ("ok go"), before any test-conversation run.
Frozen at this commit; the run uses the release tree with 057e9c1's memory_api.py.

## The change

`RG_LIST_WIDE=1` (commit 057e9c1, off by default) widens the questions read
as asking for a set of things. A set question reads more messages (twice
the usual number, at least 16; in the benchmark, 16 per person instead of
5). Newly caught: plural "types/kinds of", nouns with
hyphens or slashes ("transgender-specific events", "artists/bands"), "what
are some", "what does X do to <purpose>", "like/enjoy/love", and "both" or
"in common". It does not catch "What kind of coffee do I drink these days?"
or "What do I do for a living?", where more old messages would bring back
old values.

## What development showed (conversations 0-1, 233 questions)

| | base | wide | trim | wide + trim |
|---|---|---|---|---|
| multi-hop, of 43 | 22 | 27 | 18 | 21 |
| temporal, of 63 | 48 | 48 | 48 | 48 |
| open-domain, of 13 | 7 | 7 | 7 | 7 |
| single-hop, of 114 | 78 | 78 | 78 | 78 |
| overall, of 233 | 155 | 160 | 151 | 154 |

Wide: 12 contexts changed, 5 answers gained, none lost. Two of the five were
accepted loosely by LoCoMo's generous judge ("Pots and plates" for "bowls,
cup"). Trimming each message to its matching sentences (`RG_LIST_TRIM`)
lost answers and is dropped.

False-memory development sets: the detector newly catches 1 of 1,778
questions ("What do I like doing on weekends on the water?"). Returns with
and without the switch, compared on seven development sets (own2, own,
pasted, pasted2, prefs, stale2, shapes; 376 scenarios): one return of all
their questions differs, that one, where one short unrelated message is
added ("do apps matter more than meeting in person") and the message that
answers it is still shown.

## On the test conversations (2-9, 1,307 questions)

The detector newly catches 14 multi-hop, 16 single-hop, 1 open-domain and
no temporal questions. Every other question gets the same context, so its
answer should not change (the reader runs at temperature 0); that is
checked, not assumed.

Run once: the release tree (53e0d9c) with commit 057e9c1's memory_api.py,
`RG_LIST_WIDE=1`, the EWT parser, Qwen3-14B as reader and judge with the
benchmark's usual judge, compared question by question with
`release_test_default` (the same commit without the switch).

## Hypotheses

- H1: multi-hop answers gained minus lost is at least +3.
- H2: no other category loses more than 2 answers net.
- H3: overall gained minus lost is at least +2.
- H4: of the questions whose context did not change, at least 99% get the
  same answer and verdict as before (otherwise the comparison is noise).

## Decision

H1, H2 and H4 met: the detector goes on by default, the README's LoCoMo
figures come from this run (with the strict judge as well), and the
changed questions are read again by Claude Sonnet 5.5 for that column
(about 60 requests). Otherwise it stays off and the result is written up
in `docs/HOW_IT_READS.md` with the other refuted ideas.

## Result (run once, 2026-10-17 22:34 to 2026-10-18 02:56)

`~/jpwork/sdr-mhtest/bench/locomo/results/mhwide_test_default`
(in the repo: `bench/locomo/results/mhwide_test_default`, `compare.txt`).

| | gained | lost | net |
|---|---|---|---|
| multi-hop | 1 | 1 | 0 |
| temporal | 0 | 0 | 0 |
| open-domain | 0 | 0 | 0 |
| single-hop | 2 | 1 | +1 |
| overall | 3 | 2 | +1 |

Contexts changed: 31 of 1,307. Of the 1,276 unchanged, all 1,276 got the
same answer and verdict.

- H1 (multi-hop net at least +3): missed.
- H2 (no other category below -2): met.
- H3 (overall net at least +2): missed.
- H4 (unchanged contexts, at least 99% the same): met.

Decision, as registered: the detector stays off and is listed with the
refuted ideas in `docs/HOW_IT_READS.md`. The development gain (5 of 10
newly caught questions) did not carry over to the 14 the test caught.
