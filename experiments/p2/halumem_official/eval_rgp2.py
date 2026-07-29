"""HaluMem adapter for the RG p2 memory system (github.com/MemTensor/HaluMem
eval harness) -- EVIDENCE-LAYER architecture (entry 100 pivot, dev-validated
at 51.7/22.5 in entry 110): RG retrieves BM25-ranked, corroboration-tiered,
receipted evidence lines (experiments/p2/retrieve.py, committed 7e80a05+)
and a local composer LLM (the same class of call every other frame's adapter
makes at QA time) phrases the answer under the calibrated grounding rules.
Memory extraction stays cache-replay; retrieval stays pure python.

Interface this file fills in, per the official contract:
  - "memory extraction" artifact per session: session["extracted_memories"],
    facts NEW as of that session (session-incremental prefix re-ingest).
  - "memory update" artifact: for each gold memory_point with
    is_update=="True" and non-empty original_memories, attach
    memory_point["memories_from_system"] = list[str] (our mem.recall() over
    the memory_content as query).
  - "QA" artifact: question["system_response"] = composer output over the
    retrieved evidence context (PROMPT_MEMZERO + CAL, the exact config
    judged in entry 110); question["context"] = that evidence context.

Env:
  OPENAI_BASE_URL / RG_PREFIX_NO_THINK -- composer endpoint (llms.py); use
    the qwen3:14b llama-cpp server with RG_PREFIX_NO_THINK=1.
  RG_TIMELINE=1 -- ALSO append timeline.change_history (store-receipt-backed
    CHANGE HISTORY) + its read rule. OFF by default: screened but not yet
    judged end-to-end; do not enable for an official run until it is.

Usage (matches eval_memzero.py's __main__ shape):
    python eval_rgp2.py [--data_path PATH] [--version default]
                         [--users 0,1,2] [--cache_dir DIR]
"""

import argparse
import copy
import json
import os
_SFX = "_v5" if os.environ.get("RG_EXTRACT_V5") else "_v4"
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
import retrieve as RV     # noqa: E402
import timeline as TL     # noqa: E402
from llms import llm_request        # noqa: E402  (harness-local)
from prompts import PROMPT_MEMZERO  # noqa: E402

DEFAULT_DATA_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
DEFAULT_CACHE_DIR = os.path.expanduser("~/rg_private/halumem")

_TIMELINE = os.environ.get("RG_TIMELINE", "0") == "1"

# The calibrated grounding rules judged at 51.7/22.5 (entry 110). Keep
# byte-identical to compose_judge_v2ctx.py's CAL.
CAL = ("\n\nGROUNDING RULES (follow exactly):\n"
 "1. Use ONLY the memories above. Each memory is tagged 'confirmed xN' (corroborated N times) "
 "or 'unconfirmed(once)'. When memories conflict, prefer confirmed and the most recent date.\n"
 "2. If the memories DO contain the information asked, answer it concisely and directly.\n"
 "3. Only if the specific information asked is genuinely NOT present in ANY memory, respond "
 "with exactly: Unknown. Do not guess or use outside knowledge -- but do NOT answer 'Unknown' "
 "when the answer is present in the memories.")


def compose_answer(mem, question, index):
    """Evidence-layer QA: retrieve tiered+receipted context, compose under
    the calibrated rules. Returns (answer, context)."""
    facts = RV.retrieve_facts(mem, question, index=index)
    context = "\n".join(RV.format_fact(d) for d in facts) or "(no relevant memories)"
    extra = ""
    if _TIMELINE:
        section = TL.change_history(mem, facts)
        if section:
            context = context + "\n" + section
            extra = TL.TIMELINE_RULE
    try:
        answer = llm_request(PROMPT_MEMZERO.format(context=context,
                                                   question=question) + CAL + extra)
    except Exception:
        answer = "Unknown."
    return answer, context


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
    cache_path = os.path.join(cache_dir, "cache_u{}{}.jsonl".format(idx, _SFX))
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
    cache_path = os.path.join(cache_dir, "cache_u{}{}.jsonl".format(idx, _SFX))

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
        index = RV.build_index(mem)   # one index per session-state
        for qa in session["questions"]:
            t1 = time.time()
            answer, context = compose_answer(mem, qa["question"], index)
            qa_dur = (time.time() - t1) * 1000

            new_qa = copy.deepcopy(qa)
            new_qa["context"] = context
            new_qa["search_duration_ms"] = qa_dur
            new_qa["system_response"] = answer
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
