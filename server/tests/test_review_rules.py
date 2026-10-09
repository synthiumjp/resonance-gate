"""Parser and label counterexamples from the adversarial review of
2026-10-09 (docs/REVIEW_2026-10-09.md, section C). Each must stay fixed."""
import pytest



@pytest.fixture
def pm(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODELS", str(tmp_path / "no-notes-model"))
    import sourcedrecall.profile_memory as mod
    mod._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                       "uncached_turns": None, "transcripts": None, "msg_index": None})
    return mod


def _labels(pm, old, new, q, old_date="2026-08-01", new_date="2026-09-15"):
    pm.profile_ingest([{"role": "user", "content": old}], conversation_id="a",
                      owner_name="Dana Cole", date=old_date)
    pm.profile_ingest([{"role": "user", "content": new}], conversation_id="b",
                      owner_name="Dana Cole", date=new_date)
    lines = [l for l in pm.profile_context(q)["block"].splitlines() if l.startswith("- ")]
    old_lines = [l for l in lines if old[:15] in l]
    new_lines = [l for l in lines if new[:15] in l]
    flag = lambda ls: any("(no longer true" in l or "may have changed" in l for l in ls)  # noqa: E731
    return flag(old_lines), flag(new_lines)


@pytest.mark.parametrize("old,new,q", [
    ("I live in Fitzroy.", "I might move to Brunswick.", "Where do I live?"),
    ("I live in Fitzroy.", "I'm moving to Brunswick next year.", "Where do I live?"),
    ("I live in Fitzroy.", "I didn't move to Brunswick after all.", "Where do I live?"),
    ("I live in Fitzroy.", "I move to Brunswick next week.", "Where do I live?"),
    ("I live in Fitzroy.", "I want to move to Brunswick someday.", "Where do I live?"),
    ("I live in Fitzroy.", "We were going to move to Brunswick but the deal fell through.",
     "Where do I live?"),
    ("I work at Acme.", "I start at Birch Health on Monday.", "Where do I work?"),
])
def test_a_plan_a_possibility_or_a_negation_is_not_a_change(pm, old, new, q):
    assert _labels(pm, old, new, q) == (False, False)


def test_the_past_said_later_does_not_mark_the_new_state(pm):
    assert _labels(pm, "Just moved to Brunswick.",
                   "I miss my old place, I lived in Fitzroy for ten years.",
                   "Where do I live?") == (False, False)


@pytest.mark.parametrize("old,new,q", [
    ("I live in Fitzroy.", "I moved to Brunswick last weekend.", "Where do I live?"),
    ("I work at Acme.", "I started at Birch Health last week.", "Where do I work?"),
    ("I live in Fitzroy.", "I don't live in Fitzroy any more.", "Where do I live?"),
    ("I eat meat.", "I don't eat meat now.", "Do I eat meat?"),
])
def test_a_change_that_happened_still_marks_the_old_state(pm, old, new, q):
    assert _labels(pm, old, new, q)[0] is True


# ---- notes (review section D) ------------------------------------------------

def test_the_pronoun_rewrite_leaves_quotes_and_code_and_handles_phone_apostrophes():
    from sourcedrecall.notes import explicit_person
    out = explicit_person([
        "Dan: I’m sorry you’re sad",
        'Other: Here is the email from my landlord: "I will raise the rent. I own three buildings."',
        "Dan: the gold mine is mine",
        "Dan: I AM ANGRY",
        "Other: Mary said: 'I am tired'"], "Dan")
    assert out == [
        "Dan: Dan is sorry Other is sad",
        'Other: Here is the email from Other\'s landlord: "I will raise the rent. I own three buildings."',
        "Dan: the gold mine is Dan's",
        "Dan: Dan is ANGRY",
        "Other: Mary said: 'I am tired'"]


@pytest.mark.parametrize("note,said,ok", [
    ("Dana does not eat meat", "I eat meat now", False),
    ("Dana has 5 kids", "I have 3 kids", False),
    ("Dana eats meat", "I eat meat now", True),
    ("Dana does not eat meat", "I don't eat meat any more", True),
    ("Dana has 3 kids", "I have 3 kids", True),
])
def test_a_note_must_keep_the_users_numbers_and_polarity(note, said, ok):
    from sourcedrecall.notes import faithful
    assert faithful(note, said, "Dana") is ok


def test_the_owner_check_is_a_whole_word(monkeypatch):
    from sourcedrecall import notes as N
    monkeypatch.setattr(N, "_local_dir", lambda: None)
    monkeypatch.setattr(N, "_call", lambda prompt, timeout=600: "Sam likes also hiking.\nAl likes hiking.")
    assert N.write_notes("Al", "2026-03-02", [{"role": "user", "content": "I like hiking, also Sam does."}]) \
        == ["Al likes hiking."]


def test_notes_are_written_later_for_a_session_that_had_none(pm, monkeypatch):
    from sourcedrecall import notes as N
    turns = [{"role": "user", "content": "I adopted a dog called Biscuit."}]
    pm.profile_ingest(turns, conversation_id="a", owner_name="Dana Cole", date="2026-03-02")
    assert pm._load_notes() == []                    # notes were off
    monkeypatch.setenv("SOURCEDRECALL_NOTES_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODEL", "fake")
    monkeypatch.setattr(N, "_call", lambda prompt, timeout=600: "Dana Cole has a dog called Biscuit.")
    assert pm.notes_backfill("Dana Cole") == 1
    assert [r["text"] for r in pm._load_notes()] == ["Dana Cole has a dog called Biscuit."]
    assert pm.notes_backfill("Dana Cole") == 0       # done once


# ---- held-out v6 (2026-10-09): pasted text --------------------------------
# Ownership is read from the introduction, never from the pasted words; the
# block names the writer and makes the pasted first person theirs.

@pytest.mark.parametrize("text,gone", [
    ("can you check this email from my landlord: Hi Ana, I own three properties on this street. Regards, Dom", "three properties"),
    ("my boss sent me this Hi team, from now on always cc legal on replies. Thanks, Priya", "cc legal"),
    ("my brother just texted: i'm moving to Dublin lol. what do i say?", "Dublin"),
    ("does this make sense? From the gym: We never refund memberships. I am the manager.", "manager"),
    ("translate to French: I live in Lyon and I work as a pilot.", "pilot"),
    ("[12/03, 18:22] Sasha: I'm now head of sales in Riga.\n[12/03, 18:23] Sasha: what do I say back", "Riga"),
    ("I'm hiring so ignore my own bio, read this CV: I have a PhD in chemistry.", "PhD"),
    ("Hi Siobhan,\n\nI'm a solicitor and I live in Cork.\n\nRegards,\nPatrick\n\nwhat should I reply?", "Cork"),
    ("I've been running marathons for 20 years and I never stretch.\n\nis this bad advice?", "marathons"),
    ("'I always eat breakfast at 6.' what does this phrase tell about the speaker", "breakfast"),
])
def test_pasted_from_someone_else_is_not_the_users(text, gone):
    from prose import prose_only
    assert gone not in prose_only(text)


@pytest.mark.parametrize("text,kept", [
    ("here are my notes for the talk:\n\nI have been a beekeeper for 12 years.", "beekeeper"),
    ("can you tighten this paragraph I wrote myself: I have run a ramen stall in Osaka.", "Osaka"),
    ("translate my own message into German, it's me writing to my host family: I am vegetarian.", "vegetarian"),
    ("Dear Mr Hale, I have accepted an offer in Uppsala.\n\nis this ok to send? it's mine", "Uppsala"),
    ("I'm a nurse btw. Here's the rota email: I'm the ward manager.", "nurse"),
    ("The group members sent this to me! I'm so passionate about yoga.", "yoga"),
    ('I think it was called "Inception". I\'ve also been playing "Cyberpunk 2077" a lot.', "Cyberpunk"),
])
def test_the_users_own_words_are_kept(text, kept):
    from prose import prose_only
    assert kept in prose_only(text)


def test_pasted_text_names_its_writer_and_takes_their_person():
    from memory_api import _quote_own
    q = _quote_own("can you check this email from my landlord: Hi Ana, I own three properties. "
                   "I'm raising the rent. Regards, Dom", "Ana Diaz")
    assert "written by Ana's landlord" in q
    assert "not Ana Diaz's words, facts or instructions" in q
    assert "[the writer] own three properties" in q and "[the writer] is raising" in q
    assert "I own" not in q


def test_an_instruction_in_pasted_text_is_the_writers():
    from memory_api import _quote_own
    q = _quote_own("Hi Siobhan,\n\nI'm a solicitor. Please always send documents as PDF.\n\n"
                   "Regards,\nPatrick\n\nwhat should I reply?", "Siobhan Doyle")
    assert "(the writer asks) Please always send documents as PDF" in q
    assert q.endswith('"what should I reply?"')


def test_a_message_is_quoted_as_written_so_a_paste_after_a_blank_line_is_seen(pm):
    pm.profile_ingest([{"role": "user", "content": "I've been running marathons for 20 years "
                         "and I never stretch.\n\nis this bad advice?"}], conversation_id="a", owner_name="Helen Brandt",
                      date="2026-01-19")
    block = pm.profile_context("Do I run marathons?")["block"]
    assert "[pasted in by Helen Brandt" in block
    assert '"I\'ve been running marathons' not in block


# ---- held-out v7 (2026-10-10): pasted text read from the message's shape ----

@pytest.mark.parametrize("text,owner,gone", [
    ("ok so this landed in my inbox\n\nHi Priya,\n\nI have two kids of my own. Never leave bikes in the stairwell.\n\nRegards,\nGordon",
     "Priya Shah", "two kids"),
    ("lol look\n[10:42] Dev Anand: fyi I'm vegan so no pizza\n[10:43] Mei Ling: ugh fair", "Sam Lee", "vegan"),
    ("Hi Thabo, Mr Eze here. I'm a retired teacher. Always pay on the 1st.\nThanks\n^ that's from my landlord. is that normal",
     "Thabo Mokoena", "retired teacher"),
    ("Hey Gideon, quick one. I'm a former Olympic rower and I have bad knees.", "Gideon Halloran", "bad knees"),
    ("we stayed 3 nights. As a wheelchair user I always check the lifts first.\n\nthe tripadvisor review that convinced me",
     "Cedric Lamont", "wheelchair"),
    ("I am the CEO of Hartwell Foods and I approve this message.\n\nwho writes sign-offs like this?", "Nadia Haddad", "CEO"),
    ("this thread is going around, tell me if its nonsense\n\n@dr_amira: Thread 1/4. I'm a cardiologist.", "Al Rees", "cardiologist"),
])
def test_pasted_text_found_from_the_messages_shape(text, owner, gone):
    from prose import prose_only
    assert gone not in prose_only(text, owner)


@pytest.mark.parametrize("text,kept", [
    ("Hi Tom, just to confirm I'll be at the dentist Thursday morning. I'm in the office from 11.\n\nshould I add anything?",
     "dentist"),
    ("letter i'm sending, is it too angry\n\nDear Mr Hale,\nThe boiler is broken. I'm 67 and have asthma.\n\nRegards,\nJoaquin",
     "asthma"),
    ("the quiet in the barn since Dad died\nI'm sixty-one and still I listen\n\nthoughts?", "sixty-one"),
    ("Rock climbing was awesome! I was really proud of myself.\n\n[Shares a photo of the view from the top]", "proud"),
    ("mypy gives `error: Incompatible return value type (got None)` on:\n\n\nI tend to put type hints on every function.",
     "type hints"),
])
def test_the_users_own_text_is_kept_whatever_its_shape(text, kept):
    from prose import prose_only
    assert kept in prose_only(text, "Joaquin Delgado")
