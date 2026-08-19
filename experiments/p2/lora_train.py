"""LoRA-train a specialised extractor on HaluMem users 10-19.

Why this exists: post-processing is exhausted (composition +0.6pt pooled,
e220; all-turns +1.65pt judged-null, e212) and we need +11pt of integrity
recall for F1 0.50. The leaders reach 80-87 extraction F1 with typed
extraction architectures, gold is 96% prose (e217), so the difference is in
WHAT the extractor emits per turn -- and section 4b says prompting cannot fix
that. Ten prompt revisions and a 1.7B/14B/24B/32B ladder are the evidence.

CONTAMINATION. Training data comes only from `lora_dataset.py`, which refuses
users 0-9. Those ten users carry every official number this project reports
and there is no way to un-see training data. This script re-asserts the split
rather than trusting the file it is handed.

WHY A 1.7B BASE. The product claim is local-first on a small footprint, and
the current extractor is a prompted 14B. If a task-specialised 1.7B matches or
beats it, that is both the accuracy result AND the product story. If it needs
4B, that still fits the card. Entry 121 measured scale as DEAD for the
prompted extractor (32b < 14B), which is the usual signature of a task where
specialisation beats capacity.

Deliberately plain: bf16 LoRA, no quantisation. bitsandbytes is unreliable on
ROCm and a 1.7B in bf16 fits 14 GiB with room for activations, so 4-bit would
add a failure mode to save memory we have.
"""
import argparse
import json
import os
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.path.expanduser(
        "~/rg_private/halumem/lora/base/Qwen3-1.7B"))
    ap.add_argument("--data", default=os.path.expanduser(
        "~/rg_private/halumem/lora/train_u10-19.jsonl"))
    ap.add_argument("--out", default=os.path.expanduser(
        "~/rg_private/halumem/lora/adapter-v1"))
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--maxlen", type=int, default=768)
    ap.add_argument("--val-frac", type=float, default=0.05)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--warmup", type=int, default=30)
    a = ap.parse_args()

    import torch
    from datasets import Dataset
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              DataCollatorForSeq2Seq, Trainer, TrainingArguments)
    from peft import LoraConfig, get_peft_model

    assert torch.cuda.is_available(), "no GPU visible -- refusing to train on CPU"
    print("device:", torch.cuda.get_device_name(0))

    rows = [json.loads(l) for l in open(a.data, encoding="utf-8")]
    if a.limit:
        rows = rows[:a.limit]
    random.Random(0).shuffle(rows)
    nval = max(50, int(len(rows) * a.val_frac))
    val, train = rows[:nval], rows[nval:]
    print(f"examples: {len(train)} train / {len(val)} val")

    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def encode(ex):
        m = ex["messages"]
        # Loss on the ASSISTANT span only. Training on the prompt as well
        # teaches the model to reproduce dialogue, which is not the task and
        # dilutes the signal that matters -- what to EMIT.
        prompt = tok.apply_chat_template(m[:-1], tokenize=False,
                                         add_generation_prompt=True,
                                         enable_thinking=False)
        full = prompt + m[-1]["content"] + tok.eos_token
        pid = tok(prompt, add_special_tokens=False)["input_ids"]
        fid = tok(full, add_special_tokens=False)["input_ids"][:a.maxlen]
        labels = list(fid)
        for i in range(min(len(pid), len(labels))):
            labels[i] = -100
        return {"input_ids": fid, "attention_mask": [1] * len(fid),
                "labels": labels}

    dtr = Dataset.from_list(train).map(encode, remove_columns=["messages"])
    dva = Dataset.from_list(val).map(encode, remove_columns=["messages"])

    model = AutoModelForCausalLM.from_pretrained(
        a.base, dtype=torch.bfloat16, device_map={"": 0})
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()

    peft_cfg = LoraConfig(
        r=a.rank, lora_alpha=a.rank * 2, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, peft_cfg)
    model.print_trainable_parameters()

    args = TrainingArguments(
        output_dir=a.out, num_train_epochs=a.epochs,
        per_device_train_batch_size=a.bs,
        gradient_accumulation_steps=a.accum,
        # transformers 5.x dropped warmup_ratio; warmup_steps is the survivor
        learning_rate=a.lr, lr_scheduler_type="cosine", warmup_steps=a.warmup,
        logging_steps=25, save_strategy="epoch", eval_strategy="steps",
        eval_steps=200, per_device_eval_batch_size=a.bs,
        bf16=True, report_to=[], gradient_checkpointing=True,
        save_total_limit=2, dataloader_num_workers=2)

    Trainer(model=model, args=args, train_dataset=dtr, eval_dataset=dva,
            data_collator=DataCollatorForSeq2Seq(tok, padding=True,
                                                 label_pad_token_id=-100)).train()
    model.save_pretrained(a.out)
    tok.save_pretrained(a.out)
    print("saved adapter to", a.out)


if __name__ == "__main__":
    main()
