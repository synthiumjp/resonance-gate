"""Is a block of a user's message someone else's text? (2026-10-13)

Held-out sets v6 to v12 each found pasted text in shapes the rules in
prose.py did not read (v12: a third of the pasted texts unmarked, their
source named in other words, after the text, or only in the next message).
This is a small logistic model beside the rules, for one question only:
given a block, the user's words around it (the frame) and the user's next
message, was the block written by someone else? Features are linguistic and
cheap: word n-grams of the frame and the next message, the block's first
and last lines, how much of the block is in the first or second person,
greetings, sign-offs, a signature that is or is not the owner's, speaker
labels, header lines, and the rules' own cues. No language model, no
embedder; the weights are a generated module (paste_clf_weights.py,
tools/paste_clf/train.py).

    p_other(block, frame="", after="", owner="") -> probability
    best_span(text, owner=None, after=None) -> (start, end, p) or None
"""
import math
import re
import zlib

try:
    from paste_clf_weights import BIAS, DIM, THRESHOLD, W
except ImportError:          # no trained weights: the classifier is off
    BIAS, DIM, THRESHOLD, W = 0.0, 1 << 15, 2.0, {}
try:
    from paste_clf_weights import LEXICAL
except ImportError:
    LEXICAL = False

_TOK = re.compile(r"[a-z]+(?:'[a-z]+)?|[0-9]+|[^\sa-z0-9]")
_FIRST = {"i", "i'm", "i've", "i'd", "i'll", "me", "my", "mine", "myself"}
_SECOND = {"you", "your", "you're", "yours", "you've", "you'll"}
_GREET = re.compile(r"^(?:hi|hey|hello|dear|good (?:morning|afternoon|evening)|greetings|yo)\b", re.I)
_SIGNOFF = re.compile(r"^(?:thanks|thank you|cheers|regards|best|love|xx+|sincerely|kind regards|"
                      r"warm regards|best wishes|take care|ta|many thanks)\b", re.I)
_SPEAKER = re.compile(r"^\s*(?:\[[^\]]{1,20}\]\s*)?[A-Z][\w .'-]{0,24}:\s+\S")
_HEADER = re.compile(r"^\s*(?:from|to|subject|sent|date|cc|posted by|reply-to)\b\s*:?", re.I)
# someone other than the user, as people name them around a paste
_THIRD = re.compile(
    r"\b(?:brother|sister|mum|mom|mother|dad|father|parents?|grandma|grandad|grandpa|gran|nan|nana|"
    r"aunt|auntie|uncle|cousin|niece|nephew|son|daughter|kids?|wife|husband|partner|boyfriend|"
    r"girlfriend|ex|friend|mate|bestie|flatmate|roommate|housemate|neighbou?r|landlord|landlady|"
    r"boss|manager|colleague|coworker|co-worker|team ?lead|ceo|hr|recruiter|client|customer|"
    r"supplier|vendor|teacher|tutor|school|college|uni|university|principal|coach|doctor|dentist|"
    r"gp|vet|nurse|council|bank|admin|mod|moderator|server|group|group ?chat|channel|forum|"
    r"reddit|redditor|poster|op|author|writer|reviewer|someone|somebody|a guy|a woman|a man|"
    r"stranger|panelist|speaker|guest|host|parents' group|class ?rep|pta)\b|"
    r"\b(?!(?:it|that|what|there|here|he|she|who|let|where|how)['’]s\b)[A-Za-z]+['’]s\b", re.I)
# a named person as the source ("from Kai", "Kai put", "by Mira"); a bare
# capitalised word is not one (days, months, "Re: Folding bikes")
_NAMED = re.compile(r"\b(?:from|by|via)\s+[A-Z][a-z]+\b|"
                    r"\b(?!(?:I|The|This|That|It|My|Re|Fwd|Hi|Hey|Dear)\b)[A-Z][a-z]+\s+"
                    r"(?:said|says|put|posted|wrote|asked|texted|messaged|sent|replied|just|keeps|always)\b")
_USER_I = re.compile(r"\b(?:I|I'm|I’m|Im|I've|I’ve|Ive|I'd|I’d|Id|I'll|I’ll)\b")   # the user as subject
# the next message points back at a text: "^", "the note above", "that was the
# school's newsletter", "this is what Kai put"; "it was an awesome day" is not
_TEXTS = (r"(?:e-?mail|message|msg|text|note|post|card|review|newsletter|letter|reply|bio|transcript|"
          r"rules|chat|dm|update|announcement|notice|ad|auto-?reply|comment|tweet|thread|memo|invite|"
          r"rules list|group ?chat)")
_DEICTIC = re.compile(r"^\W*(?:\^|the (?:above|note|message|text|email|post)\b|"
                      r"(?:that|this|it)(?:'s|’s| is| was)\s+(?:from|what)\b|"
                      r"(?:that|this|it)(?:'s|’s| is| was)\s+(?:the|an?|my|his|her|their|our)\s+"
                      r"(?:[\w'’-]+\s+){0,3}?" + _TEXTS + r"\b)|"
                      r"\babove\b|\bthat (?:one|message|email|text|note|post)\b", re.I)
_NAME_LINE = re.compile(r"^[-–—~\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]*\.?)?)\s*[.!,]?\s*$")


def _toks(s, cap=80):
    return _TOK.findall((s or "").lower())[:cap]


def _grams(prefix, s, n=3, cap=80):
    t = _toks(s, cap)
    for k in range(1, n + 1):
        for i in range(len(t) - k + 1):
            yield prefix + " ".join(t[i:i + k])


def features(block, frame="", after="", owner="", lexical=None):
    """-> {hashed index: value}. lexical: word n-grams too (LEXICAL from the
    weights module); off, only the abstract features below (dev set
    cases_dev_shapes: the n-grams learned the training texts' style)."""
    if lexical is None:
        lexical = LEXICAL
    f = {}

    def add(name, v=1.0):
        i = zlib.crc32(name.encode("utf-8")) % DIM
        f[i] = f.get(i, 0.0) + v

    for g in (_grams("F:", frame) if lexical else ()):
        add(g)
    for g in (_grams("N:", after) if lexical else ()):
        add(g)
    lines = [l.strip() for l in (block or "").splitlines() if l.strip()]
    first, last = (lines[0], lines[-1]) if lines else ("", "")
    for g in (_grams("A:", first, 2, 16) if lexical else ()):
        add(g)
    for g in (_grams("Z:", last, 2, 16) if lexical else ()):
        add(g)
    words = [w for w in _toks(block, 400) if w[0].isalpha()]
    n = max(1, len(words))
    add("first_person", 5.0 * sum(w in _FIRST for w in words) / n)
    add("second_person", 5.0 * sum(w in _SECOND for w in words) / n)
    add("len_bin_%d" % min(8, int(math.log2(n + 1))))
    add("lines_bin_%d" % min(6, len(lines)))
    add("frame_none" if not (frame or "").strip() else "frame_some")
    add("after_none" if not (after or "").strip() else "after_some")
    if _GREET.match(first):
        add("greeting_first")
    if any(_SIGNOFF.match(l) for l in lines[-3:]):
        add("signoff_end")
    sig = _NAME_LINE.match(last)
    own_first = (owner or "").split()[0].lower() if owner else ""
    if sig:
        add("sig_owner" if own_first and own_first in sig.group(1).lower() else "sig_other")
    if own_first and re.search(r"\b(?:i'?m|i am|my name is|this is|it'?s)\s+" + re.escape(own_first) + r"\b",
                               (block or "").lower()):
        add("self_named_owner")
    if sum(bool(_SPEAKER.match(l)) for l in lines) >= 2:
        add("speaker_lines")
    if any(_HEADER.match(l) for l in lines[:4]):
        add("header_lines")
    if (block or "").lstrip()[:1] in "\"'“‘>":
        add("quoted")
    # 2026-10-13 (dev set cases_dev_shapes: the first model scored "my
    # brother, last night:" 0.00, having learned the training introductions'
    # verbs): who the user's words around the block are about, abstractly
    fp_block = sum(w in _FIRST for w in words) / n
    for tag, ctx in (("F", frame), ("N", after)):
        c = " ".join((ctx or "").split())
        if not c:
            continue
        third = bool(_THIRD.search(c) or _NAMED.search(c))
        user_i = bool(_USER_I.search(c))
        if third:
            add(tag + "~third_party")
        if third and not user_i:
            add(tag + "~third_party_no_I")
            if fp_block >= 0.03:
                add(tag + "~third_party_no_I_block_first_person")
        if user_i:
            add(tag + "~user_I")
        if len(c.split()) <= 8:
            add(tag + "~short")
        if tag == "F" and c.rstrip().endswith(":"):
            add("F~colon_end")
        if tag == "F" and re.match(r"^\W*(?:\^|--|—|-|\()", c):
            add("F~points_back")
        if _DEICTIC.search(c):
            add(tag + "~deictic")
    # the rules' cues, as features (prose.py)
    try:
        import prose as _P
        for name, rx in (("frame_source", _P._FRAME_SOURCE), ("frame_from_other", _P._FROM_OTHER),
                         ("frame_own", _P._FRAME_OWN), ("later_other", _P._LATER_OTHER)):
            if frame and rx.search(frame):
                add("F~" + name)
            if after and rx.search(after):
                add("N~" + name)
    except (ImportError, AttributeError):
        pass
    return f


def p_other(block, frame="", after="", owner=""):
    z = BIAS + sum(W.get(i, 0.0) * v for i, v in features(block, frame, after, owner).items())
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


_PARA = re.compile(r"\S(?:.*?\S)?(?=\n[ \t]*\n|\s*\Z)", re.S)


def candidates(text):
    """-> [(start, end, frame)]: the whole message; it without a short first
    and/or last paragraph (the user's words around a paste); a short
    "intro:" line before the rest."""
    paras = list(_PARA.finditer(text or ""))
    out = []
    if not paras:
        return out
    short = lambda m: len(m.group(0).split()) <= 45  # noqa: E731
    out.append((paras[0].start(), paras[-1].end(), ""))
    if len(paras) >= 2 and short(paras[0]):
        out.append((paras[1].start(), paras[-1].end(), paras[0].group(0)))
    if len(paras) >= 2 and short(paras[-1]):
        out.append((paras[0].start(), paras[-2].end(), paras[-1].group(0)))
    if len(paras) >= 3 and short(paras[0]) and short(paras[-1]):
        out.append((paras[1].start(), paras[-2].end(), paras[0].group(0) + "\n" + paras[-1].group(0)))
    # an "intro:" line: the colon ends the line ("Rails 7: `error`" is not one)
    m = re.match(r"([^\n:]{3,120}):[ \t]*\n(?=\s*\S)", text)
    if m and len(m.group(1).split()) <= 15:
        out.append((m.end(), paras[-1].end(), m.group(1)))
    return out


def _attributes(ctx):
    """The user's words name someone else as the speaker and the user is not
    the subject ("my brother, last night:", "^ my cousin", "this is what Kai
    put in the group"), and they do not say the text is the user's."""
    c = " ".join((ctx or "").split())
    if not c or len(c.split()) > 30:
        return False
    # the block's own opening ("Hi Saira,", "Cara zia Rosa,") or a quotation
    if _GREET.match(c) or re.match(r"^\W*[\"“]", c) or (c.endswith(",") and len(c.split()) <= 4):
        return False
    try:
        import prose as _P
        if _P._FRAME_OWN.search(c) and not _P._FROM_OTHER.search(c):
            return False
    except (ImportError, AttributeError):
        pass
    return bool((_THIRD.search(c) or _NAMED.search(c)) and not _USER_I.search(c))


def third_party_span(text, owner=None, after=None, min_words=15):
    """2026-10-13 (dev set cases_dev_shapes): a block in the first person
    whose surrounding words, before, after or in the next message, name
    someone else and not the user -> (start, end), else None."""
    if "```" in (text or "") or (text or "").count("`") >= 2:
        return None
    for s, e, frame in candidates(text):
        block = text[s:e]
        words = [w for w in _toks(block, 400) if w[0].isalpha()]
        if len(words) < min_words or not any(w in _FIRST for w in words):
            continue
        if frame and _attributes(frame):
            return s, e
        if (not frame and after and len(words) >= 20 and _attributes(after)
                and _DEICTIC.search(" ".join(after.split()))):
            return s, e
    return None


def best_span(text, owner=None, after=None, min_words=20, threshold=None):
    """Only where the user said something around the block (an introduction
    before or after it, or a next message): a lone message of the user's own
    is never judged by the model (dev sets, first model: own preferences
    marked 28 of 36 without this)."""
    if not W:
        return None
    # code and error messages are the user's question, as in the rules
    if "```" in (text or "") or (text or "").count("`") >= 2:
        return None
    # the next message says it is theirs ("that was my diary entry")
    try:
        import prose as _P
        if after and _P._FRAME_OWN.search(after) and not _P._FROM_OTHER.search(after):
            return None
    except (ImportError, AttributeError):
        pass
    import os
    thr = threshold if threshold is not None else float(os.environ.get("RG_PASTE_CLF_T") or THRESHOLD)
    best = None
    for s, e, frame in candidates(text):
        block = text[s:e]
        if len(block.split()) < min_words or not (frame.strip() or (after or "").strip()):
            continue
        p = p_other(block, frame, after or "", owner or "")
        if best is None or p > best[2]:
            best = (s, e, p)
    return best if best and best[2] >= thr else None
