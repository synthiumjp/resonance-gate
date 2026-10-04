"""A memory the user can read and edit (2026-10-02): MEMORY.md, fact ids,
forget and confirm by id, and the feedback-loop guard on the hooks."""
import json

import pytest

pytest.importorskip("stanza", reason="ingest needs the rgx parser (stanza)")


@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.delenv("SOURCEDRECALL_OWNER", raising=False)
    import sourcedrecall.profile_memory as mod

    def reset():
        mod._state.update({"mem": None, "audit_pass": None,
                           "needs_reload": False, "uncached_turns": None,
                           "transcripts": None})
        mod._ingest_state.update({"extractor": None, "owner": None})
    reset()
    yield mod
    reset()


U = lambda c: {"role": "user", "content": c}


def _seed(pm):
    pm.profile_ingest([U("I live in Fitzroy."), U("I'm allergic to penicillin."),
                       {"role": "assistant",
                        "content": "I remember you mentioning you play the cello."}],
                      conversation_id="a", owner_name="Dana Cole",
                      date="2026-09-01")
    pm.profile_ingest([U("Big news, I moved to Brunswick last weekend."),
                       U("The billing service is written in Go.")],
                      conversation_id="b", owner_name="Dana Cole",
                      date="2026-09-20")


def test_every_write_rewrites_a_readable_memory_file(pm, tmp_path):
    _seed(pm)
    md = (tmp_path / "MEMORY.md").read_text()
    assert md.startswith("# Memory: Dana Cole")
    about = md.split("## About you")[1].split("##")[0]
    assert "allergic to penicillin" in about and '"I\'m allergic to penicillin."' in about
    gone = md.split("## No longer true")[1].split("##")[0]
    assert "Fitzroy" in gone
    heard = md.split("## Said by the assistant, never confirmed by you")[1]
    assert "cello" in heard


def test_a_fact_can_be_forgotten_by_its_id(pm, tmp_path):
    _seed(pm)
    hit = pm.profile_recall("Am I allergic to anything?")["ranked"][0]
    assert hit["id"] and len(hit["id"]) == 6
    out = pm.profile_forget(hit["id"])
    assert out["forgotten"] is True
    after = pm.profile_recall("Am I allergic to anything?")
    assert not any("penicillin" in (f.get("text") or "")
                   for f in after.get("ranked") or [])
    assert "penicillin" not in (tmp_path / "MEMORY.md").read_text()


def test_an_unknown_id_is_an_error_not_a_silent_success(pm):
    _seed(pm)
    assert pm.profile_forget("zzzzzz")["forgotten"] is False


def test_the_hooks_never_store_the_memory_summary_itself(tmp_path):
    """If the injected summary is ever recorded as user text, re-ingesting it
    would store the memory's own output as new facts."""
    from sourcedrecall import claude_hooks as H
    t = tmp_path / "t.jsonl"
    rows = [
        {"type": "user", "message": {"role": "user", "content":
         "[MEMORY: what the user has told you]\n- Dana Cole lives in Fitzroy  "
         "[\"I live in Fitzroy.\" · 2026-09-01]\n[MEMORY RULES] Each line is "
         "something the user told you."}},
        {"type": "user", "message": {"role": "user", "content": "I play the drums."}},
    ]
    t.write_text("\n".join(json.dumps(r) for r in rows))
    turns, _ = H.read_transcript(str(t))
    assert turns == [{"role": "user", "content": "I play the drums."}]


def test_a_life_event_replaces_the_state_it_ends(pm, tmp_path):
    """2026-10-02: "I got divorced" used to produce nothing, so "married"
    stayed current forever."""
    pm.profile_ingest([U("I'm married."), U("I'm 33.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-01-10")
    pm.profile_ingest([U("I got divorced last year."), U("I'm 34.")],
                      conversation_id="b", owner_name="Dana Cole",
                      date="2026-09-20")
    md = (tmp_path / "MEMORY.md").read_text()
    about = md.split("## About you")[1].split("##")[0]
    gone = md.split("## No longer true")[1].split("##")[0]
    assert "divorced last year" in about and "34" in about
    assert "married" in gone and "33" in gone


def test_a_remark_tied_to_its_moment_leaves_the_summary(pm, tmp_path):
    """Research into what users want (2026-10-02): "I'm eating keto today",
    said three weeks ago, is not a permanent constraint."""
    import datetime
    old = (datetime.date.today() - datetime.timedelta(days=20)).isoformat()
    pm.profile_ingest([U("I live in Fitzroy."), U("I'm eating keto today."),
                       U("I'm so tired.")], conversation_id="a",
                      owner_name="Dana Cole", date=old)
    pm.profile_ingest([U("I'm in Sydney this week for work.")],
                      conversation_id="b", owner_name="Dana Cole",
                      date=datetime.date.today().isoformat())
    block = pm.profile_context(None)["block"]
    assert "Fitzroy" in block
    assert "keto" not in block and "tired" not in block
    sydney = next(l for l in block.splitlines() if "Sydney" in l)
    assert "(said in passing)" in sydney and "Dana Cole is in Sydney this week" in sydney
    # still findable, and labelled
    hit = [f for f in pm.profile_recall("What diet am I on?")["ranked"]
           if "keto" in (f.get("text") or "")]
    assert hit and hit[0]["passing"] is True
    # and it never replaced where they live
    md = (tmp_path / "MEMORY.md").read_text()
    assert "Fitzroy" in md.split("## About you")[1].split("##")[0]
    assert "keto" in md.split("## Said in passing")[1]


@pytest.mark.parametrize("first,then,q,want,old", [
    ("Our place is in Northcote, two minutes from the creek trail.",
     "We finally relocated to Coburg last week.", "Where do I live?",
     "Coburg", "Northcote"),
    ("I'm a junior analyst at the bank.",
     "They promoted me to senior analyst on Friday!", "What is my job title?",
     "senior analyst", "junior analyst"),
])
def test_a_change_of_state_answers_with_the_new_value(pm, first, then, q, want, old):
    """False-memory bench, dev cases (2026-10-02): the change was stored and
    linked, then the question was refused -- "relocated" shares no word
    with "live"."""
    pm.profile_ingest([U(first)], conversation_id="a", owner_name="Jordan Pike",
                      date="2026-03-02")
    pm.profile_ingest([U(then)], conversation_id="b", owner_name="Jordan Pike",
                      date="2026-03-09")
    r = pm.profile_recall(q)
    assert r["found"] and want in r["ranked"][0]["text"]
    stale = [f for f in r["ranked"] if old in f["text"]]
    assert all(f["current"] is False for f in stale)


def test_a_question_about_someone_else_is_not_grounded_by_the_users_job(pm):
    pm.profile_ingest([U("I'm a barista at Seven Seeds.")], conversation_id="a",
                      owner_name="Jordan Pike", date="2026-03-02")
    assert not pm.profile_recall("What does my brother do for work?")["found"]


# ---- the user's own words when no fact answers (2026-10-02) ---------------

def test_a_sentence_the_parser_missed_is_quoted_when_it_answers(pm):
    pm.profile_ingest([U("I study marine biology at the University of Queensland.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    r = pm.profile_recall("What do I study?")
    assert r["found"] and "marine biology" in r["ranked"][0]["text"]
    assert r["ranked"][0]["status"] == "verbatim"


def test_a_near_sentence_is_not_an_answer(pm):
    pm.profile_ingest([U("I have a dog and a cat at home."),
                       U("My friend Dev lives in Leiden.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    for q in ("Do I have any children?", "What city was I born in?"):
        assert not pm.profile_recall(q)["found"], q


def test_a_later_unparsed_sentence_follows_the_older_fact(pm):
    pm.profile_ingest([U("I get through roughly four coffees a day, it's a problem.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    pm.profile_ingest([U("Two months without any coffee now. Switched to tea.")],
                      conversation_id="b", owner_name="Jordan Pike", date="2026-03-09")
    texts = [f["text"] for f in pm.profile_recall("How much coffee do I drink?")["ranked"]]
    assert any("Two months without any coffee" in t for t in texts)


def test_a_forgotten_fact_is_not_quoted_back(pm):
    pm.profile_ingest([U("I'm allergic to penicillin.")], conversation_id="a",
                      owner_name="Jordan Pike", date="2026-03-02")
    hit = pm.profile_recall("Am I allergic to anything?")["ranked"][0]
    pm.profile_forget(hit["id"])
    r = pm.profile_recall("Am I allergic to anything?")
    assert "penicillin" not in str(r.get("ranked"))


def test_a_forgotten_fact_stays_forgotten_after_a_reload(pm):
    pm.profile_ingest([U("I take medication for my anxiety every morning.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    hit = pm.profile_recall("What medication do I take?")["ranked"][0]
    pm.profile_forget(hit["id"])
    pm._state["mem"] = None
    assert "medication" not in str(pm.profile_recall("What medication do I take?").get("ranked"))


def test_a_quote_can_be_forgotten_by_its_id(pm):
    pm.profile_ingest([U("I study marine biology at the University of Queensland.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    q = pm.profile_recall("What do I study?")["ranked"][0]
    assert pm.profile_forget(q["id"])["forgotten"]
    assert not pm.profile_recall("What do I study?")["found"]
    pm._state["mem"] = None
    assert not pm.profile_recall("What do I study?")["found"]


@pytest.mark.parametrize("said,q", [
    ("If I were rich I would quit my job and travel the world.", "Am I rich?"),
    ("Imagine if I had a pet tiger, that would be wild.", "Do I have a pet tiger?"),
    ("My sister Anna lives in Boston and she has two kids.", "Do I have kids?"),
    ("Everyone at work eats sushi on Fridays.", "Do I eat sushi?"),
])
def test_hypotheticals_and_other_people_are_not_quoted(pm, said, q):
    pm.profile_ingest([U(said)], conversation_id="a", owner_name="Jordan Pike",
                      date="2026-03-02")
    r = pm.profile_recall(q)
    assert not any(f.get("status") == "verbatim" for f in r.get("ranked") or [])


# ---- candidates when nothing is confirmed (2026-10-03) ---------------------

def test_an_unconfirmed_question_gets_labelled_candidates(pm, monkeypatch):
    monkeypatch.setenv("RG_EVIDENCE", "facts")   # candidates are the fact block's
    pm.profile_ingest([U("I'm in my second year of a law degree at Monash.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    r = pm.profile_recall("Which university do I attend?")
    assert r["found"] is False and r["abstain"] is True
    rel = r.get("related") or []
    assert 1 <= len(rel) <= 3 and all(f.get("related") for f in rel)
    assert any("Monash" in (f.get("text") or "") for f in rel)
    block = pm.profile_context("Which university do I attend?")["block"]
    assert "(possibly related)" in block and "Monash" in block


def test_nothing_is_offered_from_another_project(pm, tmp_path):
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    pm.profile_ingest([U("The billing service is written in Go.")], conversation_id="a",
                      owner_name="Jordan Pike", date="2026-03-02", scope=str(proj))
    other = tmp_path / "other"
    other.mkdir()
    r = pm.profile_recall("What language is the billing service in?", scope=str(other))
    assert "billing" not in str(r.get("related"))


# ---- forgetting removes what the fact left behind (2026-10-03) -------------

def test_forgetting_the_new_value_restores_the_old_one(pm):
    pm.profile_ingest([U("I live in Fitzroy.")], conversation_id="a",
                      owner_name="Jordan Pike", date="2026-03-02")
    pm.profile_ingest([U("I moved to Brunswick last week.")], conversation_id="b",
                      owner_name="Jordan Pike", date="2026-03-09")
    new = next(f for f in pm.profile_recall("Where do I live?")["ranked"]
               if "Brunswick" in f["text"])
    pm.profile_forget(new["id"])
    r = pm.profile_recall("Where do I live?")
    fitz = [f for f in r["ranked"] if "Fitzroy" in f["text"]]
    assert fitz and fitz[0]["current"] is True
    assert "Brunswick" not in str(r)


def test_forgetting_a_fact_drops_the_names_it_introduced(pm, tmp_path):
    pm.profile_ingest([U("My dog Biscuit needs a walk twice a day.")],
                      conversation_id="a", owner_name="Jordan Pike", date="2026-03-02")
    world = json.load(open(tmp_path / "world.json"))
    assert "biscuit" in world
    hit = pm.profile_recall("Do I have a dog?")["ranked"][0]
    pm.profile_forget(hit["id"])
    world = json.load(open(tmp_path / "world.json"))
    assert "biscuit" not in world


def test_the_browser_shows_the_memory_and_a_recall(pm):
    from sourcedrecall.browser import _render_memory
    pm.profile_ingest([U("I live in Fitzroy.")], conversation_id="a",
                      owner_name="Jordan Pike", date="2026-03-02")
    pm.profile_ingest([U("I moved to Brunswick last week.")], conversation_id="b",
                      owner_name="Jordan Pike", date="2026-03-09")
    owner, groups = pm.memory_groups()
    page = _render_memory(owner, groups, "Where do I live?",
                          pm.profile_recall("Where do I live?"))
    assert "Memory: Jordan Pike" in page and "About you" in page
    assert "(no longer true)" in page and "Brunswick" in page
    assert "<script" not in page.lower()
    evil = _render_memory(owner, groups, "<script>alert(1)</script>", None)
    assert "<script>alert" not in evil


# ---- a new user's first questions (2026-10-03, fresh install on the Mac) ----

def test_a_new_users_first_questions(pm):
    pm.profile_ingest([U("I moved to Brunswick last week. My physical health "
                         "remains stable due to my active lifestyle."),
                       U("My dog Biscuit is a beagle.")],
                      conversation_id="a", owner_name="Sam Reed", date="2026-10-03")
    r = pm.profile_recall("Where do I live?")
    assert r["found"]
    texts = [f["text"] for f in r["ranked"]]
    assert "Brunswick" in texts[0], texts
    r = pm.profile_recall("What breed is my dog?")
    assert r["found"], r.get("answer")
    assert "beagle" in r["ranked"][0]["text"]


# ---- whole messages in the block (2026-10-04, LoCoMo dev) ------------------

A = lambda c: {"role": "assistant", "content": c}


def test_the_block_quotes_the_whole_message(pm):
    pm.profile_ingest([U("I work at Acme. The office is in Carlton so I cycle there.")],
                      conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    block = pm.profile_context("Where do I work?")["block"]
    acme = next(l for l in block.splitlines() if "Acme" in l)
    assert "The office is in Carlton" in acme


def test_the_block_shows_the_question_a_message_answered(pm):
    pm.profile_ingest([A("Where do you work these days?"), U("I work at Acme now.")],
                      conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    block = pm.profile_context("Where do I work?")["block"]
    acme = next(l for l in block.splitlines() if "Acme" in l)
    assert 'in reply to "Where do you work these days?"' in acme


def test_a_forgotten_sentence_is_not_quoted_inside_a_message(pm):
    pm.profile_ingest([U("I work at Acme. I'm allergic to penicillin.")],
                      conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    hit = pm.profile_recall("Am I allergic to anything?")["ranked"][0]
    assert "penicillin" in hit["text"]
    pm.profile_forget(hit["id"])
    block = pm.profile_context("Where do I work?")["block"]
    assert "Acme" in block and "penicillin" not in block


# ---- messages-first evidence (2026-10-04, RG_EVIDENCE=messages) -----------

def test_messages_first_quotes_the_user_with_the_parsers_notes(pm, monkeypatch):
    monkeypatch.setenv("RG_EVIDENCE", "messages")
    pm.profile_ingest([U("I live in Fitzroy, above a bakery.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-01-05")
    pm.profile_ingest([U("Big news, I moved to Brunswick last weekend.")],
                      conversation_id="b", owner_name="Dana Cole", date="2026-03-01")
    block = pm.profile_context("Where do I live?")["block"]
    lines = [l for l in block.splitlines() if l.startswith("- ")]
    assert lines and "Fitzroy" in lines[0] and "Brunswick" in lines[-1]   # oldest first
    assert '"I live in Fitzroy, above a bakery."' in lines[0]
    assert "(no longer true:" in lines[0]
    assert "no longer true" not in lines[-1]


def test_messages_first_says_when_nothing_is_stored(pm, monkeypatch):
    """With messages first, the closest messages are shown and the reader
    decides (blind v3: 12/12 never-mentioned questions refused); an empty
    store says so, and RG_MSG_GATE=1 restores the parser's gate."""
    monkeypatch.setenv("RG_EVIDENCE", "messages")
    pm.profile_ingest([A("Hello! How can I help today?")], conversation_id="z",
                      owner_name="Dana Cole", date="2026-01-01")
    assert "Nothing stored matches" in pm.profile_context("What is my blood type?")["block"]
    pm.profile_ingest([U("I live in Fitzroy, above a bakery.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-01-05")
    monkeypatch.setenv("RG_MSG_GATE", "1")
    pm._state["msg_index"] = None
    block = pm.profile_context("What is my blood type?")["block"]
    assert "Nothing stored matches" in block or "Fitzroy" not in block


def test_messages_first_keeps_other_projects_out(pm, monkeypatch, tmp_path):
    monkeypatch.setenv("RG_EVIDENCE", "messages")
    a, b = tmp_path / "proj_a", tmp_path / "proj_b"
    a.mkdir(); b.mkdir()
    pm.profile_ingest([U("The billing service is written in Go and deployed with Helm.")],
                      conversation_id="a", owner_name="Dana Cole", date="2026-01-05",
                      scope=str(a))
    block = pm.profile_context("What language is the billing service in?", scope=str(b))["block"]
    assert "Go and deployed" not in block
    block = pm.profile_context("What language is the billing service in?", scope=str(a))["block"]
    assert "Go and deployed" in block


def test_forgetting_the_sentence_drops_its_link(pm, tmp_path):
    pm.profile_ingest([U("My hometown is Ballarat.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-03-02")
    import json, os
    w = json.load(open(os.path.join(str(tmp_path), "world.json")))
    assert w.get("=hometown") == "Ballarat"
    pm._forget_names("My hometown is Ballarat.")
    w = json.load(open(os.path.join(str(tmp_path), "world.json")))
    assert "=hometown" not in w


# ---- embeddings kept on disk (2026-10-04) -----------------------------------

def test_embeddings_are_saved_and_forgetting_removes_them(pm, tmp_path):
    import os
    pm.profile_ingest([U("I work at Acme. I'm allergic to penicillin.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-03-02")
    pm.profile_context("Where do I work?")
    path = os.path.join(str(tmp_path), "embeddings.bin")
    assert os.path.exists(path) and os.path.getsize(path) > 0
    hit = pm.profile_recall("Am I allergic to anything?")["ranked"][0]
    pm.profile_forget(hit["id"])
    assert not os.path.exists(path)
    block = pm.profile_context("Where do I work?")["block"]
    assert "Acme" in block and "penicillin" not in block


def test_a_rebuilt_index_reuses_saved_embeddings(tmp_path, monkeypatch):
    import sys, os
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    import sourcedrecall.profile_memory  # noqa: F401 -- puts the memory code on the path
    import retrieve_v3 as R
    calls = []

    class Bi:
        def encode(self, texts, **kw):
            import numpy as np
            calls.append(len(texts))
            return np.ones((len(texts), R._EMB_DIM), dtype=np.float32)
    R._EMB_CACHE.clear()
    a = R._encode_cached(Bi(), ["one", "two"])
    b = R._encode_cached(Bi(), ["two", "three", "one"])
    assert calls == [2, 1] and a.shape == (2, R._EMB_DIM) and b.shape == (3, R._EMB_DIM)
    R._EMB_CACHE.clear()                       # a new process reads the file
    R._encode_cached(Bi(), ["one", "two", "three"])
    assert calls == [2, 1]
    with open(os.path.join(str(tmp_path), "embeddings.bin"), "ab") as fh:
        fh.write(b"torn")                      # a torn last record is ignored
    R._EMB_CACHE.clear()
    R._encode_cached(Bi(), ["one"])
    assert calls == [2, 1]


# ---- projects and the person (2026-10-04) ----------------------------------

def test_project_facts_stay_and_the_persons_preferences_travel(pm, tmp_path):
    a, b = tmp_path / "rusty-cli", tmp_path / "sales-analytics"
    a.mkdir(); b.mkdir()
    pm.profile_ingest([U("This repo is a Rust CLI, we build it with cargo workspaces."),
                       U("By the way, I prefer tabs everywhere and please never add comments to my code.")],
                      conversation_id="a", owner_name="Sam Reed", date="2026-03-01", scope=str(a))
    pm.profile_ingest([U("This project is all SQL: dbt models on Snowflake.")],
                      conversation_id="b", owner_name="Sam Reed", date="2026-03-05", scope=str(b))
    lang = pm.profile_context("What language is this project written in?", scope=str(b))["block"]
    assert "SQL" in lang and "Rust" not in lang
    tabs = pm.profile_context("Should I use tabs or spaces?", scope=str(b))["block"]
    assert "tabs everywhere" in tabs and "Rust" not in tabs



def test_standing_instructions_lead_every_sessions_summary(pm, tmp_path):
    a, b = tmp_path / "proj-a", tmp_path / "proj-b"
    a.mkdir(); b.mkdir()
    pm.profile_ingest([U("I live in Fitzroy."), U("Please never add comments to my code."),
                       U("This repo deploys to Fly.io.")],
                      conversation_id="a", owner_name="Sam Reed", date="2026-03-01", scope=str(a))
    block = pm.profile_context(None, scope=str(b))["block"]
    lines = [l for l in block.splitlines() if l.startswith("- ")]
    assert lines and "(standing instruction)" in lines[0] and "never add comments" in lines[0]
    assert "Fly.io" not in block


def test_code_is_not_parsed_and_an_always_preference_travels(pm, tmp_path):
    """2026-10-05: a pasted code block ran into the preceding sentence and
    nothing was stored; "I always use tabs ... in any code you write for me"
    stayed in the project it was said in."""
    a, b = tmp_path / "bramble-engine", tmp_path / "pollen-count"
    a.mkdir(); b.mkdir()
    msg = ("This is a C++ game engine. Please reformat this header, and for the record "
           "I always use tabs for indentation, never spaces, in any code you write for me.\n"
           "```cpp\nstruct Vec2 {\n  float x, y;\n};\n```")
    pm.profile_ingest([U(msg)], conversation_id="a", owner_name="Walter Hughes",
                      date="2026-04-01", scope=str(a))
    block = pm.profile_context("How do I like my code indented?", scope=str(b))["block"]
    assert "tabs" in block and "struct Vec2" not in block


def test_prose_only_drops_code_and_traces():
    from sourcedrecall import profile_memory as P
    t = ("Getting this:\nTraceback (most recent call last):\n  File \"app.py\", line 3\n"
         "KeyError: 'x'\nI moved the config to YAML last week.\n```py\nx = 1\n```")
    assert P._prose_only(t) == "Getting this:\nI moved the config to YAML last week."


def test_memory_file_lists_standing_instructions_first(pm):
    pm.profile_ingest([U("I live in Fitzroy."), U("Please never add comments to my code.")],
                      conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    md = open(pm.export_markdown()).read()
    sections = [l for l in md.splitlines() if l.startswith("## ")]
    assert sections[0] == "## What you have asked the assistant to always do"
    first = md.split(sections[0])[1].split("## ")[0]
    assert "never add comments" in first and "Fitzroy" not in first


# ---- opt-in notes written by the user's own model (2026-10-05) -------------

def test_model_notes_are_labelled_replaced_and_forgotten(pm, monkeypatch):
    from sourcedrecall import notes as N
    monkeypatch.setenv("SOURCEDRECALL_NOTES_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODEL", "fake")
    calls = []

    def fake(prompt, timeout=600):
        calls.append(prompt)
        return ("- Dana Cole plays the clarinet and the violin.\nSomeone else likes jazz.\n"
                "Dana Cole is allergic to penicillin.")
    monkeypatch.setattr(N, "_call", fake)
    turns = [U("I picked up the violin last year, still playing clarinet too. "
               "I'm allergic to penicillin.")]
    out = pm.profile_ingest(turns, conversation_id="a", owner_name="Dana Cole",
                            date="2026-03-02")
    assert out["model_calls"] == 1 and len(calls) == 1
    block = pm.profile_context("What instruments do I play?")["block"]
    assert "(note written by your model) Dana Cole plays the clarinet and the violin." in block
    assert "Someone else likes jazz" not in block
    pm.profile_ingest(turns, conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    assert len([r for r in pm._load_notes() if r["conv"] == "a"]) == 2   # replaced, not doubled
    hit = pm.profile_recall("Am I allergic to anything?")["ranked"][0]
    pm.profile_forget(hit["id"])
    assert pm._load_notes() == []                                         # the conversation's notes go


def test_notes_are_off_by_default(pm):
    pm.profile_ingest([U("I play the violin.")], conversation_id="a",
                      owner_name="Dana Cole", date="2026-03-02")
    assert pm._load_notes() == []
    assert "note written by your model" not in pm.profile_context("What do I play?")["block"]
