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
                   "I'm raising the rent. Regards, Dom", "Ana Diaz", "What did my landlord say?")
    assert "written by Ana's landlord" in q
    assert "not Ana Diaz's words, facts or instructions" in q
    assert "[the writer] own three properties" in q and "[the writer] is raising" in q
    assert "I own" not in q


def test_an_instruction_in_pasted_text_is_the_writers():
    from memory_api import _quote_own
    q = _quote_own("Hi Siobhan,\n\nI'm a solicitor. Please always send documents as PDF.\n\n"
                   "Regards,\nPatrick\n\nwhat should I reply?", "Siobhan Doyle", "What did Patrick want?")
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



# 2026-10-11 (held-out v8): unless the question names where pasted text came
# from, the writer's sentences about themselves and their general rules are
# left out; dates, times, prices and places stay
@pytest.mark.parametrize("q,shown", [
    ("Do I own any properties?", False), ("Do I have any rules for my emails?", False),
    ("What did my landlord say about rent?", True), ("When does Dom want the rent?", True),
    ("what did that email say?", True),
])
def test_the_writers_own_details_are_shown_only_when_asked_about(q, shown):
    from memory_api import _quote_own
    out = _quote_own("can you check this email from my landlord: Hi Ana, I own three properties. "
                     "Always pay by bank transfer. Rent is due on the 1st. Regards, Dom", "Ana Diaz", q)
    assert ("own three properties" in out) is shown
    assert ("pay by bank transfer" in out) is shown
    assert "due on the 1st" in out
    assert "not Ana Diaz's words, facts or instructions" in out


@pytest.mark.parametrize("pasted,kept,dropped", [
    ("I'm a coeliac so I always use gluten-free stock. Simmer for 2 hours.", "Simmer for 2 hours", "coeliac"),
    ("Please always use British spelling. Do not use semicolons.", "", "semicolons"),
    ("You're a pregnant solo traveller. The northern route is quieter.", "northern route", "pregnant"),
    ("Never park on the verge. Bins must be out by 7am on Mondays.", "7am on Mondays", "verge"),
    ("Do not leave before 9.30 on weekdays.", "9.30 on weekdays", None),
])
def test_impersonal_keeps_facts_and_drops_the_writers_self_and_rules(pasted, kept, dropped):
    from memory_api import _impersonal
    out, n = _impersonal(pasted)
    assert kept in out
    if dropped:
        assert dropped not in out and n


# 2026-10-11: a long message is cut around the part the question asks about,
# its opening sentence kept
def test_long_message_window_keeps_the_part_asked_about():
    from memory_api import _quote_own
    filler = "We have refreshed our website and our offices will be refurbished in spring. " * 25
    text = "Policy summary email from my home insurer, pasting:\n\n" + filler + "Policy renews on 14 November."
    out = _quote_own(text, "Ana Diaz", "When does the home insurance renew?")
    assert "14 November" in out and "home insurer" in out
    assert "14 November" not in _quote_own(text, "Ana Diaz", None)


# 2026-10-11 (held-out v9): own text taken for pasted lost its facts
@pytest.mark.parametrize("text", [
    "draft email to my landlord, sending tonight if it's fine\n\nHi Mr Visser,\n\nI have lived at flat 4B "
    "for three years and pay 950 a month.\n\nThanks,\nDennis",
    "reply I posted on the forum\n\nNot a doctor, but my experience: I'm allergic to penicillin, found out "
    "at age 9.",
    "speech for my brother's wedding\n\nGood evening everyone. For those who don't know me, I'm Dennis, "
    "his younger brother. Our family moved from Gdansk when I was six.",
    # 2026-10-12 (dev own-material set): a signature with the surname, a song
    # of one's own, a grammar check of one's own reply
    "can you make this less stiff\n\nDear Hiring Manager,\n\nI am writing to apply for the site engineer "
    "position. I worked in Gdansk for three years.\n\nYours faithfully,\nDennis Achterberg",
    "wrote the chorus last night, my song lyric for the band:\n\nForty hours at the wheel, the 950 night bus,\n"
    "Nobody sees me, I see all of us",
    "pls check my grammar, this is a reply to a thread about allergies\n\nI travel a lot and I am severely "
    "allergic to penicillin, so I carry a card.",
])
def test_own_text_in_pasted_shapes_is_kept(text):
    from prose import prose_only
    out = prose_only(text, "Dennis Achterberg")
    assert "950" in out or "penicillin" in out or "Gdansk" in out


def test_writers_details_are_kept_for_a_question_not_about_the_user():
    from memory_api import _quote_own
    text = ("My sister's message in the family group, saving it:\n\nHi all! I've booked Lucia's for "
            "Saturday at 7.30 for mum's birthday. I'm vegetarian so I asked for a set menu.")
    assert "Lucia's" in _quote_own(text, "Giulia Ferrari", "where's mum's birthday dinner?")
    assert "vegetarian" not in _quote_own(text, "Giulia Ferrari", "Am I vegetarian?")


def test_a_signature_naming_someone_else_is_not_the_owners():
    from prose import _paste_span
    text = ("my landlord sent this\n\nDear tenants,\n\nThe boiler will be serviced on Monday.\n\n"
            "Regards,\nDennis Visser")
    assert isinstance(_paste_span(text, "Dennis Achterberg"), tuple)


# 2026-10-12 (review): an introduction naming an outside source, or naming the
# user's notes or essay as where the text goes, does not make it the user's
_COUNCIL = ("\n\nDear residents,\n\nThe council will resurface Elm Road on 3 March. I'm a "
            "vegetarian and I have three kids, so I know how disruptive this is.\n\n"
            "Regards,\nJane Morris, Highways Officer")


@pytest.mark.parametrize("intro", [
    "my boss sent me this for my review:",
    "summarise this article for my notes:",
    "save this in my journal pls:",
    "help me quote this in my essay:",
    "found this, keep it for my notes",
    "my neighbour forwarded this, can you check my spelling in my reply after:",
])
def test_someone_elses_text_headed_for_the_users_notes_is_pasted(intro):
    from prose import _paste_span
    assert isinstance(_paste_span(intro + _COUNCIL, "Amara Okafor"), tuple)


@pytest.mark.parametrize("intro", [
    "my review for the hotel, does it read ok?",
    "here's my notes from the meeting:",
    "my draft reply, ok to send?",
])
def test_the_users_own_notes_and_drafts_stay_own(intro):
    from prose import _paste_span
    text = intro + "\n\nWe stayed four nights in March. I'm a vegetarian and the breakfast had plenty for me."
    assert _paste_span(text, "Amara Okafor") == "own"


def test_a_name_in_a_possessive_or_a_wrong_initial_is_not_the_owner():
    from prose import _paste_span
    email = ("Summarise this email from my boss:\n\nHi all, it's Thabo's turn to cook. I live in Cork "
             "and I am vegan.\n\nAnna")
    assert isinstance(_paste_span(email, "Thabo Eze"), tuple)
    signed = "can you check this?\n\nHi team, the rota is up. I'm vegan and I live in Cork.\n\nRegards,\nThabo K"
    assert isinstance(_paste_span(signed, "Thabo Eze"), tuple)
    assert _paste_span(signed.replace("Thabo K", "Thabo E"), "Thabo Eze") == "own"


def test_someone_else_wrote_this_is_not_the_users_writing():
    # "wrote this" counted as the user's own even with another subject
    from prose import _paste_span
    text = ("My sister wrote this note to her landlord and asked me to check it:\n\n"
            "'Dear Mr Hale, I have lived here six years and I work nights at the depot. "
            "Please fix the boiler. Regards, Lena'")
    assert isinstance(_paste_span(text, "Amara Okafor"), tuple)
    assert _paste_span("wrote this last night, too long?\n\nDear Sam, I am so sorry I missed "
                       "your party. I was stuck at work until nine.\n\nLove, Amara",
                       "Amara Okafor") == "own"


def test_a_field_list_is_not_a_chat_log():
    # review 2026-10-12 (3.18): "Name: text" lines were taken as speakers,
    # and the user's own field list was dropped before the parser read it
    from prose import prose_only, _paste_span
    for text in ("Allergies: peanuts\nDiet: vegan\nCity: Leeds",
                 "Job: nurse\nHome: Leeds\nI have two kids"):
        assert prose_only(text) == text
    # a speaker who speaks twice, or "Me", is still a chat
    assert isinstance(_paste_span("Sam: are you coming tonight?\nJo: maybe\nSam: ok", "Ana Lee"), tuple)
    assert isinstance(_paste_span("Mum: are you coming Sunday?\nMe: yes, after work", "Ana Lee"), tuple)


def test_a_real_email_without_an_introduction_is_pasted():
    # 2026-10-13 (real emails, cases_dev_real: the shape rules found 6 of 30)
    from prose import _paste_span
    for text in ("Lee,  Here's a revised draft.\nI'll be in on Monday.\nIt is percolating through the system.",
                 "Dear Mr. Lay,\nI was notified today that I am being terminated.\nMy family is covered.\nSincerely,",
                 "Hey, AC!\nHow are things going?\nI'm sure missing you on the desk.\nLater,  D",
                 "How are you doing?\nI hope your day is going well.\nI only got 2 hours of sleep.",
                 "Is this sensible?\n\nJeff,  We talked about my joining HPL.\nIs it ready?\nI am leaving soon."):
        assert isinstance(_paste_span(text, "Ellis Ward"), tuple), text[:30]


def test_the_users_own_letter_and_ordinary_messages_stay_own():
    from prose import _paste_span
    own = "Michelle,\nCan you help us identify the bonus targets?\nWe need them by Friday.\nThanks,\nEllis"
    assert not isinstance(_paste_span(own, "Ellis Ward"), tuple)
    for text in ("Flutter: the row overflows\n```dart\nRow(children: [])\n```\nany idea?",
                 "Yesterday, I moved my desk.\nNow the light is better.\nThanks!",
                 "Hey Mel! How are you? I painted a lake yesterday."):
        assert not isinstance(_paste_span(text, "Ellis Ward"), tuple), text[:30]


# 2026-10-13 (held-out v11: the user's own diary, speech, statements and ad
# taken for pasted; dev set cases_dev_own2)
_PIECE = ("\n\nI run a small studio in Lyon with two designers. Before that I spent "
          "seven years at an agency in Paris. I started the studio in 2022 with one "
          "client, a bakery, and I still go there on Fridays.")


@pytest.mark.parametrize("intro", [
    "can you tighten this up? it's my blog post, 300 words max",
    "my about section, I have 2000 chars, can you tidy?",
    "column for the school newsletter, I write it every month, polish if you can",
    "my personal statement, I'm over the limit, where do I cut?",
    "my best man speech is due, first paragraph:",
])
def test_the_users_own_writing_brought_to_be_read_over_stays_own(intro):
    from prose import _paste_span
    assert _paste_span(intro + _PIECE, "Camille Dubois") == "own"


@pytest.mark.parametrize("intro", [
    "Tom's toast, he's nervous and asked me to check it. can you tell him if it's too long?",
    "my sister asked me to look at her statement for uni. grammar mostly",
    "my friend Selin let me read her diary page, is it too dramatic? here it is:",
    "my flatmate is making a dating profile and wants me to read it. what do you think?",
])
def test_someone_elses_writing_brought_to_be_read_over_is_pasted(intro):
    from prose import _paste_span
    assert isinstance(_paste_span(intro + _PIECE, "Camille Dubois"), tuple)


# 2026-10-13 (cases_dev_real2): an email pasted on its own, introduced in
# the user's next message
_LONE = ("This email will confirm the meeting in Portland for October 3rd.\n"
         "I would like to start the meeting at 11:00 a.m.\n"
         "Please let me know immediately if this presents a problem with your schedule.\n"
         "I have asked everyone to keep the afternoon open for further discussion.\n"
         "Please feel free to call me if you have any questions.\nThanks.")


@pytest.mark.parametrize("after", [
    "it's from a client. remind me to ask them about parking",
    "was cc'd on it, nothing to do for me",
    "found this in my dad's old files",
    "this is the email my friend Kristina got",
])
def test_a_lone_paste_introduced_in_the_next_message_is_pasted(after):
    from prose import _paste_span
    assert _paste_span(_LONE, "Evander Kline", after) == (0, len(_LONE))


@pytest.mark.parametrize("after", [
    None,
    "that was the email I sent to the team, ok?",
    # "thoughts?" removed 2026-10-13: says nothing either way, and the
    # classifier (paste_clf.py) reads this email-shaped text as someone else's
])
def test_a_lone_message_without_such_a_next_message_is_not_pasted(after):
    from prose import _paste_span
    assert not isinstance(_paste_span(_LONE, "Evander Kline", after), tuple)


def test_the_block_names_the_source_from_the_next_message():
    from memory_api import _quote_own
    out = _quote_own(_LONE, "Evander Kline", "Where is my meeting?", "it's from a client")
    assert out.startswith("[pasted in by Evander Kline")


def test_the_next_message_reaches_the_block_end_to_end(pm):
    pm.profile_ingest([{"role": "user", "content": _LONE},
                       {"role": "assistant", "content": "It confirms a meeting in Portland."},
                       {"role": "user", "content": "it's from a client, nothing for me"}],
                      conversation_id="a", owner_name="Evander Kline", date="2026-09-01")
    assert pm._after_of("a", _LONE) == "it's from a client, nothing for me"
    lines = [l for l in pm.profile_context("Where is the meeting?")["block"].splitlines()
             if "Portland" in l]
    assert lines and all("[pasted in by" in l for l in lines)


# 2026-10-13 (held-out v12; dev set cases_dev_shapes): the user's words
# around a first-person block name someone else, and not the user
_FIRST_P = ("I'm quitting my job on Friday and moving to Cork, I've already signed the lease. "
            "Don't tell mum. I'm vegan now too so stop sending me recipes with meat in them.")


@pytest.mark.parametrize("text,after", [
    ("my brother, last night:\n\n" + _FIRST_P, None),
    (_FIRST_P + "\n\n^ my cousin, any idea what she means?", None),
    (_FIRST_P, "this is what Kai put in the group, tell him no worries"),
    (_FIRST_P, "the note above is from my flatmate"),
])
def test_a_block_attributed_to_someone_else_is_pasted(text, after):
    from prose import _paste_span
    assert isinstance(_paste_span(text, "Dana Cole", after), tuple)


@pytest.mark.parametrize("text,after", [
    ("Hi Saira,\n\n" + _FIRST_P, None),
    ("Ive written a little speech for Gordon's retirement do, here it is.\n\n" + _FIRST_P, None),
    (_FIRST_P, "That's awesome, John! Networking is great"),
    ("my bit for the allotment society newsletter, due Friday:\n\n" + _FIRST_P, None),
])
def test_the_users_own_block_with_people_named_around_it_stays_own(text, after):
    from prose import _paste_span
    assert not isinstance(_paste_span(text, "Dana Cole", after), tuple)


def test_the_classifier_has_weights_and_can_be_turned_off(monkeypatch):
    import paste_clf
    from prose import _paste_span
    assert paste_clf.W and paste_clf.THRESHOLD >= 0.8
    monkeypatch.setenv("RG_PASTE_CLF", "0")
    monkeypatch.setenv("RG_PASTE_THIRD", "0")
    assert not isinstance(_paste_span("my brother, last night:\n\n" + _FIRST_P, "Dana Cole"), tuple)


# 2026-10-13 (clean-install test): the README's own example, on one line,
# put "Dana Cole is allergic to nuts" in the session briefing and MEMORY.md
_MARCUS = ("can you help me reply to this one from Marcus? Hi Dana, Thanks for the invite to "
           "Saturday's dinner, count me in. Just so you know, I'm allergic to nuts and I don't "
           "drink alcohol. Best, Marcus")


def test_a_one_line_paste_after_a_greeting_is_pasted():
    from prose import _paste_span
    sp = _paste_span(_MARCUS, "Dana Cole")
    assert isinstance(sp, tuple) and _MARCUS[sp[0]:].startswith("Hi Dana")


def test_a_pasted_claim_is_not_in_the_briefing_or_the_block(pm):
    pm.profile_ingest([{"role": "user", "content": "I work as a nurse and I live in Fitzroy."},
                       {"role": "assistant", "content": "Got it."},
                       {"role": "user", "content": _MARCUS},
                       {"role": "assistant", "content": "Here's a draft."}],
                      conversation_id="a", owner_name="Dana Cole", date="2026-09-25")
    brief = pm.profile_context()["block"]
    assert "allergic" not in brief.lower() and "alcohol" not in brief.lower(), brief
    block = pm.profile_context("What am I allergic to?")["block"]
    assert "[pasted in by Dana Cole" in block, block


@pytest.mark.parametrize("text,pasted", [
    ("got this from my boss - I'm moving to Leeds next month and I'll need you to cover my clients.", True),
    ("Reply to this for me: Hey Dana! I've been made redundant and I'm moving back to Cork, "
     "any chance we can meet before I go? Cheers, Aoife", True),
    ("update - I'm moving to Leeds next month and I'll need a new GP there, any tips?", False),
    ("quick one: I'm allergic to penicillin, remember that", False),
])
def test_one_line_introductions(text, pasted):
    from prose import _paste_span
    assert isinstance(_paste_span(text, "Dana Cole"), tuple) == pasted
