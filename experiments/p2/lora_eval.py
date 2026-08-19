"""Score the specialised extractor against the prompted 14B, on HELD-OUT users.

The comparison that matters is not loss. It is: for a session's gold memory
points, how many does each extractor's emitted record set cover, and at what
emission cost.

FAIRNESS, and it is the whole design:

  * BOTH arms are scored on the same gold, the same sessions, the same
    threshold, with the same tokeniser and the same owner-name stripping.
  * The prompted baseline emits `attr: value` atoms, and gold is prose (96%,
    e217). Comparing raw atoms against prose sentences would score the
    FORMAT, not the extraction -- the exact trap of e206/e215. So the
    baseline's atoms are rendered through `propositions.render` first, which
    is what the shipped system actually emits.
  * The LoRA emits gold-shaped sentences directly, so it is scored as-is.
  * EMISSION COUNT is reported for both. Coverage bought by emitting more is
    not free: it lands on precision, where we are currently healthy at 0.665,
    and F1 is a harmonic mean.

HELD-OUT ONLY. Users 0-9 were never trained on (`lora_dataset.py` refuses
them) and this script refuses to evaluate on 10-19, so a contaminated number
cannot be produced by accident in either direction.

The offline coverage figure over-reads judged recall by ~18pt (e220), so it is
a SCREEN, not a result: it decides whether the adapter is worth judge calls.
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
STOP = set("the a an is are was were of to in on at for and or with his her "
           "their its it he she they as by from that this what which who".split())


def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower())
            if w not in STOP and len(w) > 2}


def gold_for(user):
    out = collections.defaultdict(list)
    for si, s in enumerate(user["sessions"]):
        for mp in s.get("memory_points", []):
            if str(mp.get("is_update")) != "True":
                out[si].append(mp["memory_content"])
    return out


def run_lora(user, base, adapter, max_new=192, max_turns=0, batch=8):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    from lora_dataset import SYSTEM

    tok = AutoTokenizer.from_pretrained(adapter)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16,
                                             device_map={"": 0})
    m = PeftModel.from_pretrained(m, adapter)
    m.eval()

    jobs = []
    for si, s in enumerate(user["sessions"]):
        for t in (s.get("dialogue") or []):
            c = str(t.get("content", "")).strip()
            if c:
                jobs.append((si, f"[{t.get('role','user')}] " + c[:1800]))
    if max_turns:
        jobs = jobs[:max_turns]

    per = collections.defaultdict(list)
    for i in range(0, len(jobs), batch):
        chunk = jobs[i:i + batch]
        prompts = [tok.apply_chat_template(
            [{"role": "system", "content": SYSTEM},
             {"role": "user", "content": c}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False)
            for _, c in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True,
                  truncation=True, max_length=1024).to("cuda")
        with torch.no_grad():
            out = m.generate(**enc, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.pad_token_id)
        for (si, _), seq in zip(chunk, out):
            txt = tok.decode(seq[enc["input_ids"].shape[1]:],
                             skip_special_tokens=True).strip()
            try:
                for x in json.loads(txt):
                    c = str(x.get("content", "")).strip()
                    if c:
                        per[si].append(c)
            except Exception:
                per[si].append("__UNPARSEABLE__")
        if (i // batch) % 20 == 0:
            print(f"  lora {min(i+batch,len(jobs))}/{len(jobs)}", flush=True)
    return per, len(jobs)


def run_prompted(user, uidx):
    """The shipped extractor: cached atoms, RENDERED, which is what it emits."""
    import halumem_run as H
    import propositions as PR
    cache = os.path.expanduser(
        f"~/rg_private/halumem/dev/cache_u{uidx}_v5_14b.jsonl")
    if not os.path.exists(cache):
        cache = os.path.expanduser(f"~/rg_private/halumem/cache_u{uidx}.jsonl")
    if not os.path.exists(cache):
        return None, 0
    mem, _ = H.ingest_user(user, cache_path=cache)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    owner = PR.owner_name([{"attr": n["attr"], "value": n["value"]} for n in nodes])
    per = collections.defaultdict(list)
    for nd in nodes:
        p = PR.render({"attr": nd["attr"], "value": nd["value"]}, owner=owner)
        if not p:
            continue
        for cid in (nd.get("convs") or {}):
            if str(cid).startswith("s") and str(cid)[1:].isdigit():
                per[int(str(cid)[1:])].append(p)
                break
    return per, sum(len(v) for v in per.values())


def score(per, gold, owner_toks, th):
    hit = tot = 0
    for si, gs in gold.items():
        recs = [toks(r) for r in per.get(si, [])]
        for g in gs:
            gt = toks(g) - owner_toks
            if not gt:
                continue
            tot += 1
            if any(len(gt & r) / len(gt) >= th for r in recs):
                hit += 1
    return hit, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="0,1")
    ap.add_argument("--base", default=os.path.expanduser(
        "~/rg_private/halumem/lora/base/Qwen3-1.7B"))
    ap.add_argument("--adapter", default=os.path.expanduser(
        "~/rg_private/halumem/lora/adapter-v1"))
    ap.add_argument("--max-turns", type=int, default=0)
    a = ap.parse_args()

    users = [int(x) for x in a.users.split(",")]
    bad = [u for u in users if u in TRAIN_USERS]
    if bad:
        raise SystemExit(f"REFUSING: users {bad} are the TRAINING split. "
                         "Evaluating on them would produce a number that "
                         "cannot be un-seen.")

    rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    agg = collections.defaultdict(lambda: [0, 0, 0])
    for ui in users:
        u = rows[ui]
        gold = gold_for(u)
        own = toks(" ".join(re.findall(r"^User's name is (.+)$", "\n".join(
            mp for v in gold.values() for mp in v), re.M)) or "")
        print(f"\n=== user {ui} (held out) ===")
        pb, nb = run_prompted(u, ui)
        pl, nturns = run_lora(u, a.base, a.adapter, max_turns=a.max_turns)
        for th in (0.4, 0.5, 0.6):
            if pb is not None:
                h, t = score(pb, gold, own, th)
                agg[("prompted", th)][0] += h
                agg[("prompted", th)][1] += t
                agg[("prompted", th)][2] = nb
            h, t = score(pl, gold, own, th)
            agg[("lora", th)][0] += h
            agg[("lora", th)][1] += t
            agg[("lora", th)][2] = sum(len(v) for v in pl.values())
        unp = sum(1 for v in pl.values() for x in v if x == "__UNPARSEABLE__")
        print(f"  turns generated {nturns}, unparseable outputs {unp}")

    print(f"\n{'arm':<12}{'thr':>6}{'covered':>16}{'records':>10}")
    for (arm, th), (h, t, n) in sorted(agg.items()):
        print(f"{arm:<12}{th:>6}{h}/{t} = {h/max(1,t):6.1%}{n:>10}")
    print("\n  Offline coverage over-reads judged recall by ~18pt (e220). This")
    print("  is a SCREEN to decide whether the adapter earns judge calls, not")
    print("  a result. Record counts are the precision cost.")


if __name__ == "__main__":
    main()
