"""E3 Part 4: the 20-turn scripted conversation, end to end through the real
loop (LLM extraction/parsing, whitened substrate, two-source gate, tagged
controller, template speak). Asserts the routing at every turn, including
BOTH ambiguity kinds and a correction + post-correction query."""

import pytest

from rg_chat import ChatSession

# (utterance, expected action, expected tag, content check)
SCRIPT = [
    ("My brother Tom works at Acme Labs.", "write", None,
     lambda i: ("Tom (brother)", "works at", "Acme Labs") in i["written"]),
    ("My colleague Tom works at Vertex Robotics.", "write", None,
     lambda i: ("Tom (colleague)", "works at", "Vertex Robotics") in i["written"]),
    ("Elizabeth Carter lives in Geneva.", "write", None,
     lambda i: ("Elizabeth Carter", "lives in", "Geneva") in i["written"]),
    ("Where does Elizabeth Carter live?", "answer", None,
     lambda i: i["record"][2] == "Geneva"),
    ("Where does Tom work?", "deliberate", "referential",
     lambda i: set(i["candidates"]) == {"Tom (brother)", "Tom (colleague)"}),
    ("Where does my brother Tom work?", "answer", None,
     lambda i: i["record"][2] == "Acme Labs"),
    ("Does Sarah Kim manage anyone?", "abstain", None, None),
    ("Sarah Kim manages Daniel Diaz.", "write", None,
     lambda i: ("Sarah Kim", "manages", "Daniel Diaz") in i["written"]),
    ("Who does Sarah Kim manage?", "answer", None,
     lambda i: i["record"][2] == "Daniel Diaz"),
    ("My meeting is scheduled at 2pm.", "write", None,
     lambda i: ("my meeting", "is scheduled at", "2pm") in i["written"]),
    ("My meeting is scheduled at 3pm.", "write", None,
     lambda i: ("my meeting", "is scheduled at", "3pm") in i["written"]),
    ("When is my meeting?", "deliberate", "stored", None),
    ("Actually, Elizabeth Carter lives in Vienna now.", "write", None,
     lambda i: ("Elizabeth Carter", "lives in", "Vienna") in i["superseded"]),
    ("Where does Elizabeth Carter live?", "answer", None,
     lambda i: i["record"][2] == "Vienna"),
    ("Peter Yang studied at Bristol.", "write", None,
     lambda i: ("Peter Yang", "studied at", "Bristol") in i["written"]),
    ("Where did Peter Yang study?", "answer", None,
     lambda i: i["record"][2] == "Bristol"),
    ("Forget where Peter Yang studied.", "forget", None,
     lambda i: len(i["removed"]) == 1),
    ("Where did Peter Yang study?", "abstain", None, None),
    ("Does Maria Garcia live in Lisbon?", "abstain", None, None),
    ("Nina Vogel was born in Verona.", "write", None,
     lambda i: ("Nina Vogel", "was born in", "Verona") in i["written"]),
]


def test_twenty_turn_conversation():
    session = ChatSession(use_llm_wrapper=False)
    transcript, failures = [], []
    for n, (utt, want_action, want_tag, check) in enumerate(SCRIPT, 1):
        reply, info = session.turn(utt)
        action, tag = info.get("action"), info.get("tag")
        ok = action == want_action and (want_tag is None or tag == want_tag)
        if ok and check is not None:
            try:
                ok = bool(check(info))
            except Exception as e:  # content check crash = failure, not error
                ok = False
        status = "ok" if ok else f"FAIL (want {want_action}/{want_tag})"
        transcript.append((n, utt, action, tag, reply, status))
        if not ok:
            failures.append(n)

    print("\n" + "=" * 78)
    for n, utt, action, tag, reply, status in transcript:
        tagtxt = f"/{tag}" if tag else ""
        print(f"T{n:02d} you> {utt}")
        print(f"    rg [{action}{tagtxt}]> {reply}   <{status}>")
    print("=" * 78)
    print(f"[conversation] k={session.mem.k} entities={len(session.ent)} "
          f"failures={failures}")
    assert not failures, f"turns failed routing: {failures}"
