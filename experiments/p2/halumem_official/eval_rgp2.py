"""HaluMem adapter for the RG p2 memory system (github.com/MemTensor/HaluMem
eval harness). Mirrors the contract of eval_memzero.py / eval_memos.py --
same run-artifact shape consumed by evaluation.py -- but nothing here calls
a vendor API: memory extraction is cache-replay (RG_EXTRACT_V4=1, per-turn
extraction cache under ~/rg_private/halumem/cache_u{i}_v4.jsonl) and QA
answering is pure python (non-generative recall). The only LLM calls in the
whole rgp2 evaluation happen downstream, in evaluation.py's judge stage,
against the local ollama endpoint configured in .env.

Interface this file fills in, per the official contract:
  - "memory extraction" artifact per session: session["extracted_memories"],
    a list[str] -- here the FULL final stored-fact set for the user (both
    tiers), the same list repeated for every session (our system is not
    session-incremental; see HANDOVER/report note on this).
  - "memory update" artifact: for each gold memory_point with
    is_update=="True" and non-empty original_memories, attach
    memory_point["memories_from_system"] = list[str] (our mem.recall() over
    the memory_content as query).
  - "QA" artifact: for each question, attach question["system_response"] =
    our answer_question() output verbatim (no separate LLM composition step
    -- our answers are already a stored-fact readout, so this IS the
    system's final response).

Usage (matches eval_memzero.py's __main__ shape):
    python eval_rgp2.py [--data_path PATH] [--version default]
                         [--users 0,1,2] [--cache_dir DIR]
"""

import argparse
import copy
import json
import os
import sys
import time

# our system lives outside this repo -- import it directly, no packaging
_P2 = "/home/jp/rg/experiments/p2"
if _P2 not in sys.path:
    sys.path.insert(0, _P2)

# v4 (events/plans) extraction schema -- matches the caches we were given
# (cache_u{i}_v4.jsonl, one per HaluMem-Medium user, covering every turn).
# Must be set BEFORE importing halumem_run (it reads the env var at import
# time to pick the extraction system prompt / cache-file suffix).
os.environ.setdefault("RG_EXTRACT_V4", "1")

import halumem_run as RG  # noqa: E402  (path/env setup must run first)

DEFAULT_DATA_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
DEFAULT_CACHE_DIR = os.path.expanduser("~/rg_private/halumem")


def _fact_str(nd):
    """Render one WireGraph node (asserted or provisional) as "attr: value
    (tier)" -- the flat text form the official pipeline expects a memory
    system's stored items to be in (a list[str])."""
    return f"{nd['attr']}: {nd['value']} ({nd.get('tier', 'asserted')})"


def extracted_memories_for(mem):
    """All stored facts for this user, both tiers -- the "memory extraction"
    artifact per the task mapping (asserted + provisional, receipted)."""
    return [_fact_str(nd) for nd in list(mem.g.nodes.values())] + \
           [_fact_str(nd) for nd in list(mem.g.provisional.values())]


def search_memories(mem, query, top=10):
    """"Get Dialogue Memory" / retrieval-for-update equivalent: our
    mem.recall(query), flattened to list[str] the way the official adapters
    return client.search() results. Never generates -- verbatim stored
    facts or an empty list."""
    r = mem.recall(query)
    if not r["found"]:
        return []
    out = [f"{f['attribute']}: {f['value']}" for f in r["asserted"]]
    out += [f"(linked) {w['fact']['attribute']}: {w['fact']['value']}"
            for w in r["wired"]]
    out += [f"UNCONFIRMED: {f['attribute']}: {f['value']}"
            for f in r["unconfirmed"]]
    return out[:top]


def process_user(idx, user_data, cache_dir=DEFAULT_CACHE_DIR):
    """idx: 0-based position of this user in the source jsonl -- selects the
    matching per-user extraction cache (cache_u{idx}_v4.jsonl); ingestion is
    pure cache replay, no model call. Returns a dict in the same shape
    eval_memzero.py's process_user produces (minus the tmp-file bookkeeping),
    ready to be JSON-lines'd into results/rgp2-<version>/rgp2_eval_results.jsonl
    and consumed unmodified by evaluation.py.

    SESSION-INCREMENTAL, not a single whole-user ingest: we re-run
    ingest_user on the growing prefix sessions[:k+1] for each session k (still
    cache-only, ~ms each -- 65 sessions/user costs well under a second). This
    matters for two reasons, both about matching the OTHER frames' semantics
    (which all add() session-by-session against a persistent store, so a
    session's "extracted_memories" are only what's new as of that session,
    and QA search only ever sees memories from sessions <= the question's
    own):
      1. extracted_memories per session = facts that are NEW (first
         appearance, or a tier flip provisional->asserted, i.e. newly
         corroborated) as of that session -- NOT the full final user profile
         repeated on every session. Repeating the full list (~150-250 facts
         for a HaluMem-Medium user) on every one of ~65 sessions would blow
         memory_accuracy_inputs up ~65x per user (evaluation.py issues one
         judge call per item in session["extracted_memories"]) for no
         semantic benefit, and would over-credit early sessions with facts
         only established much later.
      2. QA answer_question(mem, ...) and the update-search use the
         AS-OF-THIS-SESSION memory, not the final one -- no peeking at
         future sessions' facts when answering a question asked earlier.
    """
    uuid = user_data["uuid"]
    sessions = user_data["sessions"]
    cache_path = os.path.join(cache_dir, f"cache_u{idx}_v4.jsonl")

    new_user_data = {"uuid": uuid, "user_name": uuid, "sessions": []}
    prev_state = {}  # node id -> tier, as of the previous session

    for k, session in enumerate(sessions):
        t0 = time.time()
        prefix = {"sessions": sessions[:k + 1]}
        mem, n_turns = RG.ingest_user(prefix, cache_path, min_mentions=2)
        dur_ms = (time.time() - t0) * 1000

        cur_items = list(mem.g.nodes.items()) + list(mem.g.provisional.items())
        cur_state = {nid: nd["tier"] for nid, nd in cur_items}
        new_facts = [_fact_str(nd) for nid, nd in cur_items
                     if prev_state.get(nid) != nd["tier"]]
        prev_state = cur_state

        new_session = {
            "memory_points": session["memory_points"],
            "dialogue": session["dialogue"],
        }

        if session.get("is_generated_qa_session", False):
            new_session["add_dialogue_duration_ms"] = dur_ms
            new_session["is_generated_qa_session"] = True
            del new_session["dialogue"]
            del new_session["memory_points"]
            new_user_data["sessions"].append(new_session)
            continue

        new_session["extracted_memories"] = new_facts
        new_session["add_dialogue_duration_ms"] = dur_ms

        for mpt in new_session["memory_points"]:
            if mpt.get("is_update") != "True" or not mpt.get("original_memories"):
                continue
            mpt["memories_from_system"] = search_memories(mem, mpt["memory_content"])

        if "questions" not in session:
            new_user_data["sessions"].append(new_session)
            continue

        new_session["questions"] = []
        for qa in session["questions"]:
            t1 = time.time()
            answer = RG.answer_question(mem, qa["question"])
            qa_dur = (time.time() - t1) * 1000

            new_qa = copy.deepcopy(qa)
            new_qa["context"] = "\n".join(extracted_memories_for(mem)[:20])
            new_qa["search_duration_ms"] = qa_dur
            new_qa["system_response"] = answer  # non-generative: IS the answer
            new_qa["response_duration_ms"] = 0.0
            new_session["questions"].append(new_qa)

        new_user_data["sessions"].append(new_session)

    return new_user_data


def iter_jsonl(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main(data_path, version="default", user_indices=None, cache_dir=DEFAULT_CACHE_DIR):
    frame = "rgp2"
    save_path = f"results/{frame}-{version}/"
    os.makedirs(save_path, exist_ok=True)
    output_file = os.path.join(save_path, f"{frame}_eval_results.jsonl")

    users = list(enumerate(iter_jsonl(data_path)))
    if user_indices is not None:
        users = [(i, u) for i, u in users if i in user_indices]

    start_time = time.time()
    with open(output_file, "w", encoding="utf-8") as f_out:
        for idx, user_data in users:
            print(f"[rgp2] user {idx} ({user_data['uuid']}) "
                  f"-- {len(user_data['sessions'])} sessions ...")
            result = process_user(idx, user_data, cache_dir)
            f_out.write(json.dumps(result, ensure_ascii=False) + "\n")
            f_out.flush()
            n_q = sum(len(s.get("questions", [])) for s in result["sessions"])
            print(f"[rgp2]   -> {len(result['sessions'])} sessions, "
                  f"{n_q} questions answered")

    elapsed = time.time() - start_time
    print(f"Done in {elapsed:.2f}s. Results at {output_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_path", default=DEFAULT_DATA_PATH)
    ap.add_argument("--version", default="default")
    ap.add_argument("--cache_dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--users", default=None,
                     help="comma-separated 0-based user indices "
                          "(default: all 20)")
    args = ap.parse_args()
    idxs = None
    if args.users:
        idxs = {int(x) for x in args.users.split(",")}
    main(args.data_path, args.version, idxs, args.cache_dir)
