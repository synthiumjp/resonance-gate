"""Generate a held-out user's extraction artifact with the LoRA, and cache it.

Split from the judging step on purpose: generation needs the GPU for the
adapter, judging needs it for the llama-cpp judge server, and 15.9 GiB will not
hold both. So this writes the artifact to disk and exits, freeing the card.

The LoRA's propositions become `extracted_memories` DIRECTLY rather than being
parsed back into attr/value atoms and pushed through the store. That is the
honest test of extraction quality -- a round trip through the atom store would
measure the round trip too. It also does not cost the evidence layer: each
proposition carries the session and turn it came from, which is a receipt.
Atoms were the implementation of provenance, never the thing itself.

The owner substitution happens here: the model emits "User's ..." by
construction (e221 -- it cannot hallucinate a name it never writes) and the
owner's real name is something the STORE knows, so it is filled in
deterministically at emission time.
"""
import argparse
import collections
import json
import os
import re
import sys

DATA = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
P2 = "/home/jp/rg/experiments/p2"
if P2 not in sys.path:
    sys.path.insert(0, P2)
TRAIN_USERS = set(range(10, 20))


def owner_of(user):
    for s in user["sessions"]:
        for mp in s.get("memory_points", []):
            m = re.match(r"User's name is (.+?)\s*$", str(mp.get("memory_content", "")))
            if m:
                return m.group(1).strip()
    return None


_NAME_POINT = re.compile(r"^User's name is\b", re.I)


def rename(text, owner):
    """"User's gender is Male" -> "<Owner>'s gender is Male".

    EXCEPT the name point itself. Gold writes it literally as "User's name is
    Martin Mark", so substituting there produces "Martin Mark's name is Martin
    Mark" -- which reads as a bug and stops matching the one gold point whose
    whole content is the name."""
    if not owner or _NAME_POINT.match(text):
        return text
    t = re.sub(r"^User's\b", f"{owner}'s", text)
    t = re.sub(r"^User\b", owner, t)
    return re.sub(r"\bUser's\b", f"{owner}'s", t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--adapter", default=os.path.expanduser(
        "~/rg_private/halumem/lora/adapter-v3"))
    ap.add_argument("--base", default=os.path.expanduser(
        "~/rg_private/halumem/lora/base/Qwen3-1.7B"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--scope", default="user", choices=("user", "all"))
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args()

    if a.user in TRAIN_USERS:
        raise SystemExit(f"REFUSING: user {a.user} is in the TRAINING split.")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from lora_dataset import build_messages, owner_gender_of

    user = [json.loads(l) for l in open(DATA, encoding="utf-8")][a.user]
    owner = owner_of(user)
    gender = owner_gender_of(user)
    print(f"user {a.user}, owner {owner!r}, gender {gender!r}, scope {a.scope}")

    tok = AutoTokenizer.from_pretrained(a.adapter)
    tok.pad_token = tok.pad_token or tok.eos_token
    tok.padding_side = "left"
    m = PeftModel.from_pretrained(
        AutoModelForCausalLM.from_pretrained(a.base, dtype=torch.bfloat16,
                                             device_map={"": 0}), a.adapter).eval()

    # Build prompts with the SHARED builder so generation cannot drift from
    # training. Context is taken over the full dialogue, then extraction is
    # scoped -- a user-scope run still SEES assistant turns as context, which
    # is what the training examples look like.
    jobs = []
    for si, s in enumerate(user["sessions"]):
        turns = [t for t in (s.get("dialogue") or [])
                 if str(t.get("content", "")).strip()]
        for ti, t in enumerate(turns):
            if a.scope == "user" and t.get("role") != "user":
                continue
            jobs.append((si, ti, build_messages(turns, ti, gender)))

    per = collections.defaultdict(list)
    bad = 0
    for i in range(0, len(jobs), a.batch):
        ch = jobs[i:i + a.batch]
        ps = [tok.apply_chat_template(msgs, tokenize=False,
                                      add_generation_prompt=True,
                                      enable_thinking=False)
              for _, _, msgs in ch]
        enc = tok(ps, return_tensors="pt", padding=True, truncation=True,
                  max_length=1536).to("cuda")
        with torch.no_grad():
            out = m.generate(**enc, max_new_tokens=192, do_sample=False,
                             pad_token_id=tok.pad_token_id)
        for (si, ti, _), seq in zip(ch, out):
            txt = tok.decode(seq[enc["input_ids"].shape[1]:],
                             skip_special_tokens=True).strip()
            try:
                for x in json.loads(txt):
                    c = str(x.get("content", "")).strip()
                    if c:
                        per[si].append({"content": rename(c, owner),
                                        "type": x.get("type"),
                                        "session": si, "turn": ti})
            except Exception:
                bad += 1
        if (i // a.batch) % 25 == 0:
            print(f"  {min(i+a.batch,len(jobs))}/{len(jobs)}", flush=True)

    n = sum(len(v) for v in per.values())
    print(f"turns {len(jobs)} -> {n} memories, {bad} unparseable batchesitems")
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"user": a.user, "owner": owner, "scope": a.scope,
                   "adapter": a.adapter, "unparseable": bad,
                   "sessions": {str(k): v for k, v in per.items()}}, fh)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
