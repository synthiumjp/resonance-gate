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
                       "uncached_turns": None, "transcripts": None})
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
