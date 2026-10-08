---
license: apache-2.0
base_model:
- Qwen/Qwen3-0.6B
- Qwen/Qwen3-1.7B
language: en
tags: [onnx, onnxruntime-genai, memory, notes, sourcedrecall]
---

# sourcedrecall notes models (English, int4 ONNX)

Two small models for one job: given one conversation, write the lasting
facts the named person states about themselves, one short sentence per line,
or NONE. sourcedrecall runs them inside its own process on onnxruntime-genai,
on the CPU, with no server.

| file | base | download | a chat session (4 CPU threads) | peak memory |
|---|---|---|---|---|
| `sourcedrecall-notes-en-0.6b.tar.gz` (small) | Qwen3-0.6B | 0.51 GB | 2-3 s | 1.9 GB |
| `sourcedrecall-notes-en-1.7b.tar.gz` (standard) | Qwen3-1.7B | 1.3 GB | about 4.5 s | 3.3 GB |

A long coding session (eight parts of 12,000 characters) takes about 100 s
and up to 3.6 GB with the small model; sourcedrecall writes notes in the
background after the session ends.

They are optional. sourcedrecall stores and finds the user's own words
without them; with one, short notes are added, each kept only if its words
are in what the user wrote, and shown labelled as written by a model.

    pip install 'sourcedrecall[notes]'
    sourcedrecall-setup --notes            # small
    sourcedrecall-setup --notes standard   # standard

## How they were made

- Full fine-tune of the base model with mlx-lm, then int4 ONNX with the
  onnxruntime-genai builder (k_quant_mixed).
- Teacher: Qwen3-14B wrote notes for 3,000 LongMemEval-S conversations (MIT)
  and 1,500 SODA dialogues (CC BY 4.0), each SODA dialogue from both
  speakers' sides; a note was kept only if most of its words are in the
  person's own lines.
- Every training conversation got a random owner name and date format, and
  its pronouns were made explicit (I/my -> the speaker, you/your -> the
  listener), as sourcedrecall does before the model reads a conversation.
- Scripts: `tools/distil` in the sourcedrecall repository.

## Measured (local Qwen3-14B reader and judge for every system)

LoCoMo, conversations 2-9 (1,307 questions; used to choose between models, so not held out):

| | overall | multi-hop | temporal | single-hop |
|---|---|---|---|---|
| sourcedrecall, no notes | 64.7% | 52.3% | 53.5% | 75.5% |
| with the small model's notes | 68.2% | 55.2% | 58.9% | 79.0% |
| with the standard model's notes | 70.3% | 59.0% | 57.4% | 81.6% |
| with Qwen3-14B's notes (a server) | 73.1% | 62.3% | 57.4% | 85.4% |
| Mem0 2.2.1 | 64.6% | 61.9% | 37.2% | 77.9% |

Notes on the LoCoMo development conversations, judged against their
conversation by Qwen3-14B: said by the person 80% (small), 87% (standard),
93% (Qwen3-14B); gave the person the other speaker's facts 13%, 9%, 3%.
Held-out false-memory sets: v3 0 of 30 for both; v4, an old state given as
current, 3 of 44 (small) and 4 of 44 (standard), against 3 with Qwen3-14B's
notes and 2 without notes.

These answer scores come from local models and are not comparable with
published LoCoMo results, which use GPT-4-class models.

## Limits

English only. They sometimes give the user something the other person said
("has kids" from the other person's children), or keep a note whose words
the user wrote but whose meaning differs (a negation, a number). The small
model often writes nothing for short sessions; standard does better there.
Neither closes sourcedrecall's multi-hop gap to Mem0. The held-out false
memory sets were run many times during development; v4 is no longer clean.
Known issues and fixes in progress: docs/REVIEW_2026-10-09.md in the
sourcedrecall repository.

## Attribution

SODA (Kim et al., 2023), CC BY 4.0. LongMemEval (Wu et al., 2024), MIT.
Qwen3 (Qwen team), Apache-2.0.
