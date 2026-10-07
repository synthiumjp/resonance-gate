---
license: apache-2.0
base_model: Qwen/Qwen3-0.6B
language: en
tags: [onnx, onnxruntime-genai, memory, notes, sourcedrecall]
---

# sourcedrecall notes model (English, 0.6B, int4 ONNX)

A small model for one job: given one conversation, write the lasting facts
the named person states about themselves, one short sentence per line, or
NONE. sourcedrecall runs it inside its own process on onnxruntime-genai, on
the CPU, with no server: about 2 to 3 seconds per conversation on 4 threads,
peak memory about 1.9 GB, 0.54 GB on disk.

It is optional. sourcedrecall stores and finds the user's own words without
it; with it, short notes are added, each kept only if its words are in what
the user wrote, and shown labelled as written by a model.

## How it was made

- Base: Qwen/Qwen3-0.6B (Apache-2.0), full fine-tune with mlx-lm, then
  int4 ONNX with the onnxruntime-genai builder (k_quant_mixed).
- Teacher: Qwen3-14B wrote notes for 3,000 LongMemEval-S conversations (MIT)
  and 1,500 SODA dialogues (CC BY 4.0), each SODA dialogue from both
  speakers' sides; a note was kept only if most of its words are in the
  person's own lines.
- Every training conversation got a random owner name and date format, and
  its pronouns were made explicit (I/my -> the speaker, you/your -> the
  listener), as sourcedrecall does before the model reads a conversation.
- Training and evaluation scripts: tools/distil in the sourcedrecall repository.

## Measured (local Qwen3-14B reader and judge)

| LoCoMo test (conversations 2-9, held out) | overall | multi-hop | temporal | single-hop |
|---|---|---|---|---|
| sourcedrecall, no notes | 64.7% | 53.6% | | |
| with this model's notes | 68.2% | 55.2% | 58.9% | 79.0% |
| with Qwen3-14B's notes (a server) | 73.1% | 62.3% | 57.4% | 85.4% |
| Mem0 | 64.6% | 61.9% | 37.2% | 77.9% |

Notes on the LoCoMo development conversations, judged against the
conversation by Qwen3-14B: 80% said by the person, 13% gave the person the
other speaker's facts (Qwen3-14B's own notes: 93% and 3%). Held-out false
memory sets: 0 of 30 (v3); an old state given as current 3 of 44 (v4, the
same as with Qwen3-14B's notes).

## Limits

English only. It sometimes gives the user something the other person said
("has kids" from the other person's children): 13% of notes in the test
above. It writes one fact per line and does not close sourcedrecall's
multi-hop gap to Mem0.

## Attribution

SODA (Kim et al., 2023), CC BY 4.0. LongMemEval (Wu et al., 2024), MIT.
Qwen3 (Qwen team), Apache-2.0.
