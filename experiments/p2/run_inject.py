"""p2 INJECTION LOOP: does an assistant with this memory visibly KNOW the user?

The decisive product test (HANDOVER §7): profile -> injected as context into a
fresh LLM turn -> the assistant should use the corroborated facts naturally,
flag unconfirmed ones, and say "I don't know" where memory abstains -- instead
of confabulating. Judged by feel by the profile owner (they are ground truth).

A/B per message: the SAME model answers WITH and WITHOUT the memory block, so
the difference is attributable to the memory alone.

PRIVACY: the model is local (qwen3:14b via llama-cpp, on-device); facts never
leave the machine. Stdout is aggregate-only; the full transcript (both arms)
is appended UNREDACTED to <quarantine>/inject_report.txt for the owner.

Usage: run_inject.py <conversations.json> "<user message>" [more messages...]
"""

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from consistency import get_llm
from memory_api import Memory

BASE_SYSTEM = ("You are a helpful personal assistant. Be concise and natural. "
               "If you don't know something about the user, say so plainly.")


def answer(system, message, max_tokens=350):
    out = get_llm().create_chat_completion(
        messages=[{"role": "system", "content": "/no_think " + system},
                  {"role": "user", "content": message}],
        max_tokens=max_tokens, temperature=0.0)
    txt = out["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()


def main():
    path = sys.argv[1]
    messages = sys.argv[2:]
    if not messages:
        print("usage: run_inject.py <conversations.json> \"<message>\" ...")
        return

    mem = Memory.load(path)
    print(f"memory loaded: {len(mem.g.nodes)} corroborated facts, "
          f"{len(mem.g.edges)} edges, {len(mem.g.provisional)} provisional")

    report = os.path.join(os.path.dirname(path), "inject_report.txt")
    with open(report, "a") as f:
        for msg in messages:
            block = mem.context_block(query=msg)
            profile = mem.context_block()   # top-of-profile always present
            with_mem = answer(BASE_SYSTEM + "\n\n" + profile + "\n\n" + block, msg)
            without = answer(BASE_SYSTEM, msg)
            n_lines = block.count("\n- ") + profile.count("\n- ")
            abstained = "Nothing stored matches" in block
            print(f"\nmsg: {len(msg)} chars | memory lines injected: {n_lines}"
                  f"{' | topic-recall ABSTAINED' if abstained else ''}"
                  f" | reply with-mem {len(with_mem)} chars, without {len(without)}")
            f.write("=" * 72 + f"\nUSER: {msg}\n\n--- injected memory ---\n"
                    f"{profile}\n\n{block}\n\n--- WITH memory ---\n{with_mem}\n\n"
                    f"--- WITHOUT memory ---\n{without}\n\n")
    print(f"\n>>> UNREDACTED A/B transcript appended to:\n    {report}\n"
          f"    Judge by feel: does it know you, does it flag unconfirmed, "
          f"does it say 'I don't know' honestly?")


if __name__ == "__main__":
    main()
