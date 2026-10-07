"""Held-out v5, hypothesis 6 (docs/PREREG_HELDOUT_V5.md): for each advice
request (part F), is the conversation that holds the answer among the first
five reached by the product's message search? The LongMemEval protocol:
conversations ranked by first appearance among
profile_memory._messages_for(question, k=50). Prints counts and ids only.

    FM_CASES=cases_v5.jsonl python v5_advice.py
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "server"))
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("SOURCEDRECALL_NOTES", "off")


def main():
    from sourcedrecall import profile_memory as pm
    cases = [json.loads(l) for l in open(os.environ.get("FM_CASES") or
                                         os.path.join(HERE, "cases_v5.jsonl"))]
    hit = n = 0
    miss = []
    for c in cases:
        if not str(c.get("subtype", "")).startswith("F_"):
            continue
        wd = tempfile.mkdtemp(prefix="v5f-")
        os.environ["RG_MEMORY_DIR"] = wd
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None, "msg_index": None})
        for i, conv in enumerate(c["conversations"]):
            pm.profile_ingest([{"role": t["role"], "content": t["content"]} for t in conv["turns"]],
                              conversation_id=f"c{i}", owner_name=c["owner"],
                              date=conv.get("date"))
        for p in c["probes"]:
            if "gold_conversation" not in p:
                continue
            sess = []
            for h in pm._messages_for(p["q"], k=50):
                if h.get("conv") not in sess:
                    sess.append(h.get("conv"))
            n += 1
            if f"c{p['gold_conversation']}" in sess[:5]:
                hit += 1
            else:
                miss.append(c["id"])
        shutil.rmtree(wd, ignore_errors=True)
    print(f"H6 advice: answer's conversation in the top 5 for {hit}/{n}"
          + (f"; missed: {', '.join(miss)}" if miss else ""))


if __name__ == "__main__":
    main()
