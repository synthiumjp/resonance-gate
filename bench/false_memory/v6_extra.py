"""Held-out v6, the hypotheses the answer view does not cover
(docs/PREREG_HELDOUT_V6.md). Counts and scenario ids only.

  H7 (part G): after storing a scenario, does the session-start block (no
     question) show a standing-instruction line naming the instruction (real
     ones), or none (idioms)?
  H6 (part F) retrieval: see v5_advice.py (ADVICE_SUBTYPE=F_).

    FM_CASES=cases_v6.jsonl python v6_extra.py
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
os.environ.setdefault("RG_NLI", "0")


def main():
    from sourcedrecall import profile_memory as pm
    cases = [json.loads(l) for l in open(os.environ.get("FM_CASES") or
                                         os.path.join(HERE, "cases_v6.jsonl"))]
    real_ok = real_n = idiom_bad = idiom_n = 0
    miss, wrong = [], []
    for c in cases:
        if not str(c.get("subtype", "")).startswith("G_"):
            continue
        wd = tempfile.mkdtemp(prefix="v6g-")
        os.environ["RG_MEMORY_DIR"] = wd
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None, "msg_index": None})
        for i, conv in enumerate(c["conversations"]):
            pm.profile_ingest([{"role": t["role"], "content": t["content"]} for t in conv["turns"]],
                              conversation_id=f"c{i}", owner_name=c["owner"],
                              date=conv.get("date"))
        block = pm.profile_context()["block"]
        lines = [l.lower() for l in block.splitlines()
                 if "asked the assistant" in l or "asked to be called" in l]
        for p in c["probes"]:
            if p.get("instruction"):
                real_n += 1
                terms = [t.lower() for t in (p.get("expect") or {}).get("terms", [])]
                if any(t in l for t in terms for l in lines):
                    real_ok += 1
                else:
                    miss.append(c["id"])
            else:
                idiom_n += 1
                if lines:
                    idiom_bad += 1
                    wrong.append(c["id"])
        shutil.rmtree(wd, ignore_errors=True)
    print(f"H7 instructions: real ones shown at session start {real_ok}/{real_n}"
          + (f" (missed: {', '.join(miss)})" if miss else ""))
    print(f"H7 idioms: shown as an instruction {idiom_bad}/{idiom_n}"
          + (f" ({', '.join(wrong)})" if wrong else ""))


if __name__ == "__main__":
    main()
