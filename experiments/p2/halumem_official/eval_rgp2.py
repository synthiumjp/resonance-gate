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
_V3 = os.environ.get("RG_RETRIEVE_V3", "0") == "1"
if _V3:
    import retrieve_v3 as RV3   # noqa: E402  (opt-in accuracy tier)
import timeline as TL     # noqa: E402
import qtype_gate as QG   # noqa: E402  (entry 179)
from llms import llm_request        # noqa: E402  (harness-local)
from prompts import PROMPT_MEMZERO  # noqa: E402

DEFAULT_DATA_PATH = os.path.expanduser("~/rg_private/halumem/HaluMem-Medium.jsonl")
DEFAULT_CACHE_DIR = os.path.expanduser("~/rg_private/halumem")

_TIMELINE = os.environ.get("RG_TIMELINE", "0") == "1"

# Inference-question gate (entry 179). HaluMem is two tasks: on retrieval
# categories we score 64.1% correct / 15.0% halluc under the strict judge, on
# inference categories 11.2% / 46.2%. RG is an evidence layer -- it retrieves
# receipted facts and hands composition to the client -- so when a question
# asks the MEMORY to generalise, declining is the honest answer rather than a
# dodge. RG_QGATE=<threshold> turns it on; unset keeps round-5 behaviour.
# Reads the question TEXT only: a product is never told the question's category.
# W1 (entry 213): surface WRITE-TIME supersession in the update readout.
# HaluMem's update gold is literally shaped "X updated job_title from 'A' to
# 'B'", and until now search_memories returned every value flat -- the judge
# could not tell which was current, and our updating accuracy is 2.9%, worst
# of the eight systems with published HaluMem numbers (e211). currency.
# mark_current already decides this at ingestion; this only reports it.
# Opt-in: it changes the artifact, so it has to be A/B-able.
_SUPERSEDE = os.environ.get("RG_SUPERSEDE") == "1"

_QGATE = None
if os.environ.get("RG_QGATE"):
    try:
        _QGATE = float(os.environ["RG_QGATE"])
    except ValueError:
        _QGATE = None

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
    if _V3:
        facts = RV3.retrieve_facts_v3(index, question)
    else:
        facts = RV.retrieve_facts(mem, question, index=index)
    context = "\n".join(RV.format_fact(d, owner=getattr(index, "owner", None))
                        for d in facts) or "(no relevant memories)"
    if _QGATE is not None and QG.inference_score(question) >= _QGATE:
        # Abstain BEFORE composing: the composer cannot fabricate an inference
        # it was never asked to make, and the call is saved outright. Context is
        # still returned so the decision stays auditable.
        return QG.ABSTAIN, context
    extra = ""
    if _V3 and RV3.ANCHORED_RX.search(question):
        extra += RV3.TEMPORAL_RULE
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


def _fact_str(nd, owner=None):
    """Render one stored fact for the EXTRACTION artifact.

    The harness compares these strings against gold "memory points", which are
    written as natural-language propositions ("Michelle Hernandez's birth date
    is 1980-04-20"). We store `attr: value` atoms; every comparable system
    stores prose. Measured on dev users 10-12 (entry 162), rendering the SAME
    facts as propositions moves gold-point coverage 14.8% -> 45.7% against a
    shuffled-gold null of 4.6% -> 16.9% -- the signal nearly triples with
    nothing extracted differently.

    Scope: this affects the extraction artifact ONLY. The QA context format is
    deliberately unchanged, because its current shape is what produced the
    official round-5 row (55.0/18.7); altering both at once would make that
    number unreproducible.
    """
    import propositions as PR
    prop = PR.render(nd, owner=owner)
    # RG_ARTIFACT_NO_TIER (entry 187): 76.8% of emitted strings ended in
    # "(provisional)" while gold memory points are clean prose. The tier is
    # RG's differentiator and belongs in the QA CONTEXT, where CAL rule 1
    # actually reads it; appending a hedge word to three-quarters of the
    # artifact the judge scores for CAPTURE is noise. Off by default so round 5
    # stays reproducible.
    if os.environ.get("RG_ARTIFACT_NO_TIER") == "1":
        return prop if prop else f"{nd['attr']}: {nd['value']}"
    if not prop:
        return f"{nd['attr']}: {nd['value']} ({nd.get('tier', 'asserted')})"
    return f"{prop} ({nd.get('tier', 'asserted')})"


def extracted_memories_for(mem):
    """All stored facts for this user, both tiers -- the "memory extraction"
    artifact per the task mapping (asserted + provisional, receipted)."""
    import propositions as PR
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())
    owner = PR.owner_name(nodes)
    return [_fact_str(nd, owner=owner) for nd in nodes]


def search_memories(mem, query, top=10):
    """"Get Dialogue Memory" / retrieval-for-update equivalent: our
    mem.recall(query), flattened to list[str] the way the official adapters
    return client.search() results. Never generates -- verbatim stored
    facts or an empty list."""
    r = mem.recall(query)
    if not r["found"]:
        return []

    def _v(f, prefix=""):
        base = f"{prefix}{f['attribute']}: {f['value']}"
        if not _SUPERSEDE or f.get("current", True):
            return base
        # Name the replacement, not just the fact of replacement -- "from A to
        # B" is the whole content of an update gold point, and the id carries
        # the new value already.
        sb = str(f.get("superseded_by") or "")
        newv = sb.split("=", 1)[1] if "=" in sb else ""
        return base + (f" (SUPERSEDED by: {newv})" if newv else " (SUPERSEDED)")

    def _key(f):
        return 0 if f.get("current", True) else 1

    ast = sorted(r["asserted"], key=_key) if _SUPERSEDE else r["asserted"]
    unc = sorted(r["unconfirmed"], key=_key) if _SUPERSEDE else r["unconfirmed"]
    out = [_v(f) for f in ast]
    out += [_v(w["fact"], "(linked) ") for w in r["wired"]]
    out += [_v(f, "UNCONFIRMED: ") for f in unc]
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
        import propositions as PR
        _owner = PR.owner_name([nd for _, nd in cur_items])
        # RG_EMIT_ONCE (entry 187): the default emits on TIER CHANGE, so a
        # fact promoted provisional->confirmed is emitted in TWO sessions.
        # HaluMem gold has no promotion event, so that re-emission is pure
        # inflation of our count against theirs -- measured at 10.1% of
        # emissions, ratio 1.66x -> 1.49x.
        if os.environ.get("RG_EMIT_ONCE") == "1":
            new_facts = [_fact_str(nd, owner=_owner) for nid, nd in cur_items
                         if nid not in prev_state]
        else:
            new_facts = [_fact_str(nd, owner=_owner) for nid, nd in cur_items
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
        index = RV3.IndexV3(mem) if _V3 else RV.build_index(mem)
        for qn, qa in enumerate(session["questions"]):
            t1 = time.time()
            answer, context = compose_answer(mem, qa["question"], index)
            qa_dur = (time.time() - t1) * 1000

            new_qa = copy.deepcopy(qa)
            new_qa["context"] = context
            new_qa["search_duration_ms"] = qa_dur
            new_qa["system_response"] = answer
            new_qa["response_duration_ms"] = 0.0
            new_session["questions"].append(new_qa)
            if (qn + 1) % 25 == 0:   # throughput-sentinel progress marker
                print(f"  ...{qn+1}/{len(session['questions'])}", flush=True)

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
