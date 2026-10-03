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
    assert "(said in passing) Dana Cole is in Sydney this week" in block
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

def test_an_unconfirmed_question_gets_labelled_candidates(pm):
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
