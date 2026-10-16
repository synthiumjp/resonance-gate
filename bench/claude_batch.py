"""Claude as an extra reader or judge for the benchmarks (2026-10-16).

The local models (Qwen3-14B, Phi-4) stay the main record; this adds a
labelled Claude column so the numbers can be set beside results published
with hosted models. It uses the Message Batches API (half price, results
within a day, usually an hour).

The API key is read from a file (CLAUDE_KEY_FILE, default ~/.anthropic_key),
never from the environment, so it cannot leak into other tools.

    from claude_batch import run
    texts = run({"id1": "prompt one", ...}, "claude-sonnet-5-5", 300, "state.json")

`run` is resumable: the batch id is kept in the state file, so a second call
after an interruption polls the same batch instead of paying again.
"""
import json
import os
import time

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

# answers here are a few words; thinking off keeps them comparable with the
# local readers (Qwen3 thinking off) and cheap
THINKING_OFF = {
    "claude-sonnet-5-5": {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}},
    "claude-haiku-5-5": {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}},
}


def client():
    path = os.path.expanduser(os.environ.get("CLAUDE_KEY_FILE", "~/.anthropic_key"))
    return anthropic.Anthropic(api_key=open(path).read().strip())


def run(prompts, model, max_tokens, state_path, poll=60):
    """prompts: {custom_id: user prompt} -> {custom_id: reply text} ("" for
    a refusal or an error, which are counted and printed)."""
    c = client()
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    if "batch" not in state:
        extra = THINKING_OFF.get(model, {})
        reqs = [Request(custom_id=k, params=MessageCreateParamsNonStreaming(
                    model=model, max_tokens=max_tokens,
                    messages=[{"role": "user", "content": p}], **extra))
                for k, p in prompts.items()]
        b = c.messages.batches.create(requests=reqs)
        state = {"batch": b.id, "model": model, "n": len(reqs)}
        json.dump(state, open(state_path, "w"))
        print(f"batch {b.id}: {len(reqs)} requests to {model}", flush=True)
    while True:
        b = c.messages.batches.retrieve(state["batch"])
        if b.processing_status == "ended":
            break
        print(f"  {b.processing_status}: {b.request_counts.processing} left", flush=True)
        time.sleep(poll)
    out, bad, tin, tout = {}, 0, 0, 0
    for r in c.messages.batches.results(state["batch"]):
        if r.result.type == "succeeded":
            m = r.result.message
            tin += m.usage.input_tokens
            tout += m.usage.output_tokens
            if m.stop_reason == "refusal":
                bad += 1
                out[r.custom_id] = ""
            else:
                out[r.custom_id] = next((x.text for x in m.content if x.type == "text"), "")
        else:
            bad += 1
            out[r.custom_id] = ""
    print(f"batch {state['batch']}: {len(out) - bad} answered, {bad} refused or failed; "
          f"{tin} input and {tout} output tokens", flush=True)
    return out
