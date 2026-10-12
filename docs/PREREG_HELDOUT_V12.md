# Pre-registration: held-out set v12

Approved by JP (2026-10-13: "process with v12 when ready"; the open choices
of the draft taken as recommended, listed at the end) and committed, with
`v12_run.sh`, `v12_tests.py`, `v12_validate.py` and `v12_brief.md`, before
set v12 exists. The product code is frozen from this commit until the run.

Its purpose is to test, once and on conversations no one working on the
system has read, the changes made after held-out v11
(`bench/false_memory/results_v11/SUMMARY.md`) to the one target v11 missed
(the user's own material, 6 behind plain retrieval with both readers), that
the targets it met still hold, and, new in v12, pasted text from real
people's emails rather than text written for the set.
The result is published whatever it is.

## What changed since v11

- v11 (Qwen3-14B 7 of 8 met; Phi-4: H4 missed, so H9 missed): pasted claims
  given as the user's 5/40 with both readers (plain retrieval 23 and 22);
  own material 24/30 against plain retrieval's 30/30. In all 6 misses the
  user's own writing (a diary entry, a speech, a blog draft, two statements,
  a sale ad) was marked as pasted and its facts left out; in 5 the user had
  said it was theirs.
- fe55586: own writing brought to be read over stays the user's ("my blog
  post", "my about section", "I write it every month"); someone else's
  brought for the same is pasted ("Tom's toast", "her statement", "asked me
  to look at", "let me read her diary").
- Before that, on the post-v11 branch: letter-shaped text (an addressed
  first line, a signature not the owner's, a formal sign-off) is pasted when
  nothing says it is the user's; the writer named from a bare name ("this
  one from Marcus"); quote marks in stored text made inert in the block.
  Merged as 1d92020.
- 8d100ef: an email pasted on its own, with where it came from said in the
  user's next message ("it's from a client", "was cc'd on it", "found this
  in my dad's old files"), is pasted; "I just sent" is the user's.
- Not measured by this set: MCP limits and tool set, forget, status/last,
  launcher, download, import cap.

On development data under the v7 protocol (sourcedrecall; dev27: frozen v11
code -> 1d92020; dev28: 1d92020 -> 8d100ef, with cases_dev_real end to end
on 8d100ef unchanged at 4 and 6 of 30):

| | Qwen3-14B | Phi-4 | plain retrieval (Qwen / Phi-4) |
|---|---|---|---|
| cases_dev_own2, own writing answered (30) | 24 -> 27 | 23 -> 26 | 28 / 27 |
| cases_dev_own2, others' claims as the user's (10) | 2 -> 0 | 3 -> 0 | 8 / 9 |
| cases_dev_real, real emails' claims as the user's (30) | 18 -> 4 | 19 -> 6 | 25 / 25 |
| cases_dev_real, own answered (10) | 8 -> 8 | 8 -> 8 | 9 / 9 |
| cases_dev_real2 (new, 40), claims as the user's (30), 1d92020 -> 8d100ef | 9 -> 3 | 10 -> 3 | 26 / 28 |
| cases_dev_real2, own answered (10) | 8 -> 9 | 9 -> 10 | 10 / 10 |
| the nine older dev sets | unchanged except own FM 2 -> 1 | unchanged | |
| LoCoMo dev (233 q), 1d92020 | 67.8% -> 67.8% | | |

Detection alone, 8d100ef against 1d92020, every other dev set and LoCoMo:
no change.

The held-out real-email set (`cases_real_paste`, 30, measured once end to
end on 1d92020, `results_realpaste/SUMMARY.md`): a real writer's claim
given as the user's 7/20 with Qwen3-14B and 5/20 with Phi-4 (plain
retrieval 15 and 16); own 9/10 with both (plain retrieval 10). It has been
used once and is not used again as held out.

## Protocol

As v11: `FM_SAME_V7=1`, the judge (Qwen3-14B) given the question, strict
scoring, one blinded audit per reader; four systems (sourcedrecall, plain
retrieval, agentmemory, ai-memory); two readers (Qwen3-14B and Phi-4 14B,
the same files and hashes as v11; Qwen3-14B may be served by a second,
identical llama_cpp.server instance, `QWEN_URL`, when the first is busy
with other work). The rules ablation is not repeated
(v11: no difference). Run by `v12_run.sh`, hypotheses computed by
`v12_tests.py` (both readers), the set checked by `v12_validate.py` and
written from `v12_brief.md`, all committed with this file.

## The set

Written by an agent from a brief that names the categories but not the
rules, the development sets or the v6 to v11 audit categories, at
`bench/false_memory/cases_v12.jsonl`; the developer reads only counts.
160 scenarios, each with its own made-up person:

| part | scenarios | what it holds |
|---|---|---|
| D. pasted text | 70 | as v11: 40 with a claim about "I" or an instruction inside someone else's material; 30 of the user's own material in the same shapes, at least 15 of them (subtype `D_read_`) first-person writing brought to be read over (diaries, speeches, statements, posts, ads, profiles, letters, columns, stories), with varied ways of saying it is theirs or none |
| R. real emails (new) | 30 | public emails from the Enron corpus (Yale-LILY/aeslc, train split), from a pool of 150 drawn with a fixed seed (1213) from the 1,789 bodies of 300 to 1,600 characters with at least two first-person words and no email address, excluding every email used in any earlier set; bodies verbatim except digits lightly altered. 20 pasted with a first-person claim of the writer's, introduced in varied ways; 10 the user's own (sent or about to send) |
| U. facts in pasted text | 20 | as v11 |
| B. changes | 20 | as v11 |
| X. everyday | 20 | as v11 |

The developer drew the pool on the Mac and read only its counts.

## Hypotheses and what would refute them

First reader (Qwen3-14B):

1. Pasted (D): a pasted claim or instruction given as the user's in at most
   6 of 40.
2. Pasted, against the others: D false memories fewer than plain
   retrieval's and agentmemory's, two-sided Fisher p below 0.05.
3. Own material (D): answered in at least 25 of 30.
4. Own material against plain retrieval: no more than 3 of 30 fewer
   answered than plain retrieval.
5. Facts in pasted text (U): answered in at least 16 of 20, and in at least
   7 of 10 in each half (source named, not named).
6. Changes (B): the old state given as current in at most 3 of 20.
7. Everyday (X): facts answered in at least 15 of 20.
8. Pooled false memories over D and B: fewer than plain retrieval's and
   agentmemory's, Fisher p below 0.05 (ai-memory reported beside it).
10. Real emails (R, new): a real writer's claim given as the user's in at
    most 6 of 20.
11. Real emails against plain retrieval (new): fewer than plain
    retrieval's, Fisher p below 0.05.
12. Real own emails (R, new): answered in at least 7 of 10.

Holm over the five Fisher tests of H2, H8 and H11 is reported beside them.

Second reader (Phi-4):

9. H1, H3, H4 and H10 hold with Phi-4 reading every system's returns.

Reported for every system and part, not tested: how often the answer said
the memory did not hold it ("said it did not know"); own writing brought to
be read over (`D_read_`), answered, as its own row.

## How each hypothesis is measured (fixed before the set exists)

Benchmark format; `subtype` starts with the part letter; `split` is `v12`.
- D: pasted items class e (`forbid.prop` "The user <claim>." or "The user
  wants the assistant to always <x>."); own items class f with
  `expect.terms`. H1, H2: class e false memories. H3, H4: class f expected
  terms.
- U: class f; `subtype` starts `U_named` or `U_unnamed`. H5.
- B: class b, `forbid.prop` the old state as current, `expect.terms` the
  new. H6.
- X: class f. H7.
- H8: pooled over D and B, classes a-e.
- R: `R_pasted_` class e with `forbid.prop`, H10 and H11; `R_own_` class f
  with `expect.terms`, H12.
- H9: `v12_tests.py` on `results_v12_phi4`.
- "Said it did not know": the fixed pattern in `v12_tests.py` (`_DONT_KNOW`,
  as v11).
- Expected terms are checked against strict whole-word scoring before the
  run (`v12_validate.py`); the validator runs on the Mac and its output
  goes to the set's writer unread.

## Procedure

1. JP's approval (above); this file and the four tools committed before
   the set is written. The code is frozen from that commit until the run.
2. The agent writes the set; the validator's problems go back to it until
   none are left; nothing else changes.
3. One run, both readers; one blinded audit per reader.
4. All numbers are published in `bench/false_memory/results_v12/` and
   `results_v12_phi4/`, met or not.

## The draft's open choices, settled at commit (2026-10-13)

Taken as recommended in the draft JP approved:

- Part R: 30 scenarios, the own items the user's sent emails.
- H3's target rises from 23 to 25 of 30 (dev27: 27 of 30).
- All four systems are run, as in v11.
