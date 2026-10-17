# HaluMem: memory updates and questions

HaluMem-Medium (github.com/MemTensor/HaluMem), its first two users: 304
memory updates and 352 questions. Scored with HaluMem's own evaluation code
for its update and question parts only (`experiments/p2/halumem_official/make_eval_uqa.py`
copies them unchanged); its integrity and accuracy parts judge extracted
memory statements, which sourcedrecall does not write. The judge was the local
Qwen3-14B, not the OpenAI model in the paper, so the numbers are not
comparable with published ones (`experiments/p2/halumem_official/PATCHES.md`
lists every change to the harness). Both systems were scored by the same
judge. sourcedrecall measured on commit 53e0d9c, 2026-10-16/17; plain
retrieval on d6613e0, 2026-10-13/14 (its answers do not depend on our code).

| | sourcedrecall | plain retrieval |
|---|---|---|
| updates: the new value given, of 304 | 154 (51%) | 96 (32%) |
| updates: a wrong value given | 6 (2%) | 10 (3%) |
| questions answered correctly, of 352 | 184 (52%) | 162 (46%) |
| questions answered wrongly, of those the judge could score | 55 of 267 (21%) | 72 of 270 (27%) |

The rest of the updates were omissions: the new value was not given. Overall
scores: `scores_53e0d9c.json` (d6613e0: `scores_d6613e0.json`, sourcedrecall
156, 6, 185 and 51 of 266). The per-item results repeat HaluMem's text
and are not included here; rerun with `experiments/p2/halumem_official/eval_sdr.py`
(`--system sdr` or `--system plain --users 0,1`) and the commands in
`make_eval_uqa.py`.
