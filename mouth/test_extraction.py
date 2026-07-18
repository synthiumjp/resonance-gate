"""E3 Part 3: extraction precision on a 40-utterance hand-labelled dev set.
Reports precision AND what got conservatively dropped (the design accepts
recall loss; it must not accept precision loss)."""

import pytest

from write_path import extract_triples

# (utterance, gold triples)  — gold uses the schema's own conventions
DEV = [
    ("My brother Tom works at Acme Labs.", [("tom (brother)", "works at", "acme labs")]),
    ("Elizabeth Carter lives in Geneva.", [("elizabeth carter", "lives in", "geneva")]),
    ("Maria Garcia lives in Lisbon and manages Sam Diaz.",
     [("maria garcia", "lives in", "lisbon"), ("maria garcia", "manages", "sam diaz")]),
    ("Sarah Kim manages Daniel Diaz.", [("sarah kim", "manages", "daniel diaz")]),
    ("Peter Yang studied at Cambridge (UK).", [("peter yang", "studied at", "cambridge (uk)")]),
    ("My meeting is scheduled at 2pm.", [("my meeting", "is scheduled at", "2pm")]),
    ("Nina Vogel was born in Verona.", [("nina vogel", "was born in", "verona")]),
    ("My colleague Tom works at Vertex Robotics.",
     [("tom (colleague)", "works at", "vertex robotics")]),
    ("Emma Nguyen is married to John Patel.",
     [("emma nguyen", "is married to", "john patel")]),
    ("Mark Lowe reports to Julia Quinn.", [("mark lowe", "reports to", "julia quinn")]),
    ("Alice Wong works at Harbor Energy.", [("alice wong", "works at", "harbor energy")]),
    ("My sister lives in Dublin.", [("my sister", "lives in", "dublin")]),
    ("Robert Schmidt studied at Georgetown.",
     [("robert schmidt", "studied at", "georgetown")]),
    ("Elena Ito manages the Lisbon office.",
     [("elena ito", "manages", "the lisbon office")]),
    ("David Hansen was born in Salem.", [("david hansen", "was born in", "salem")]),
    ("Katherine Novak reports to Alice Wong.",
     [("katherine novak", "reports to", "alice wong")]),
    ("James Fischer is a sibling of Sofia Rios.",
     [("james fischer", "is a sibling of", "sofia rios")]),
    ("Laura Silva resides in Oakville.", [("laura silva", "resides in", "oakville")]),
    ("William Weber lives in Fairview.", [("william weber", "lives in", "fairview")]),
    ("Julia Quinn works at Beacon Media.", [("julia quinn", "works at", "beacon media")]),
    ("My cousin Anna lives in Boston.", [("anna (cousin)", "lives in", "boston")]),
    ("Tom Baker reports to Elena Ito.", [("tom baker", "reports to", "elena ito")]),
    ("Sofia Rios was born in Madrid.", [("sofia rios", "was born in", "madrid")]),
    ("John Park is married to Nina Tran.", [("john park", "is married to", "nina tran")]),
    ("Chris Wong studied at Bristol.", [("chris wong", "studied at", "bristol")]),
    ("Do you know where Anna lives?", []),
    ("Where does my brother work?", []),
    ("I think Bob might work at Zenith.", []),
    ("Maybe Sarah lives in Portland.", []),
    ("Tom doesn't work at Acme Labs anymore.", []),
    ("I wonder if Peter studied at Cambridge.", []),
    ("Could you remind me when my meeting is?", []),
    ("That's interesting.", []),
    ("I'm not sure who manages the team.", []),
    ("If Maria moves to Lisbon, she'll be happy.", []),
    ("Who does Mark report to?", []),
    ("I heard James might be moving.", []),
    ("Thanks, that's all for now.", []),
    ("Elizabeth used to live in Geneva.", []),
    ("It would be great if Alice worked at Harbor Energy.", []),
]


def _norm(t):
    """Case/whitespace-insensitive; leading articles on slots are not scored
    (reported normalization — 'the Lisbon office' == 'Lisbon office')."""
    out = []
    for x in t:
        x = x.strip().lower()
        for art in ("the ", "a ", "an "):
            if x.startswith(art):
                x = x[len(art):]
                break
        out.append(x)
    return tuple(out)


def test_extraction_precision():
    n_extracted = n_correct = n_gold = n_dropped = 0
    false_pos, dropped = [], []
    for utt, gold in DEV:
        got = [_norm(t) for t in extract_triples(utt)]
        gold_n = [_norm(t) for t in gold]
        n_gold += len(gold_n)
        n_extracted += len(got)
        for t in got:
            if t in gold_n:
                n_correct += 1
            else:
                false_pos.append((utt, t))
        for t in gold_n:
            if t not in got:
                n_dropped += 1
                dropped.append((utt, t))
    precision = n_correct / n_extracted if n_extracted else 1.0
    print(f"\n[extraction] {len(DEV)} utterances, {n_gold} gold triples")
    print(f"[extraction] extracted={n_extracted} correct={n_correct} "
          f"PRECISION={precision:.3f}")
    print(f"[extraction] conservatively dropped {n_dropped}/{n_gold} gold triples")
    for utt, t in false_pos:
        print(f"[extraction]   FALSE-POS {t}  <- \"{utt}\"")
    for utt, t in dropped:
        print(f"[extraction]   dropped {t}  <- \"{utt}\"")
    # exploratory bar: precision is the claim, recall is allowed to pay for it
    assert precision >= 0.9
