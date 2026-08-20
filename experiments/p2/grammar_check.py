"""The CHECK layer over parser candidates. Deterministic first, model last.

JP's architecture: grammar extracts, the model only checks or fixes. That
makes the checker two stages, not one, and the order matters -- every
candidate the free stage kills is a model call not spent.

  STAGE 1  deterministic, no model:
      GROUNDED      every content word must trace to the source turn. This is
                    an EXTRACTIVE system, so a word that is not in the turn
                    was invented -- and that is the evidence-layer claim
                    stated as a filter rather than a slogan.
      WELLFORMED    morphology the parser is known to get wrong ("ises
                    looking", "has reflecting"), first-person residue where
                    the person shift failed, degenerate self-reference.
      SUBSTANTIVE   a proposition has to assert something: a bare subject, a
                    one-word tail or a pure discourse marker is not a memory.
  STAGE 2  model entailment: does the turn SUPPORT this proposition. One
      yes/no per surviving candidate, no generation. MiniCheck-class verifiers
      at 770M match GPT-4-turbo at ~400x lower cost, so this is the cheap half
      of the system, not the expensive one.

Why the order is not arbitrary: the parser emits 2.57 records per gold point
against gold's ~1.0, so most candidates are surplus. Paying a model to read
all of them would put the cost back exactly where this architecture removes
it.
"""
import re

STOP = set("the a an is are was were be been being of to in on at for and or "
           "with his her their its it he she they as by from that this what "
           "which who i my me we our us you your not no do does did have has "
           "had will would can could should may might must".split())

_BAD_MORPH = re.compile(r"\b\w+ises\b|\bhas \w+ing\b|\bises\b|\b(?:is|has) "
                        r"(?:is|has|was)\b", re.I)
_FIRST_RESIDUE = re.compile(r"\b(?:I|my|me|mine|myself|we|us|our)\b")
_DISCOURSE = {"absolutely", "of course", "sure", "okay", "ok", "yes", "no",
              "hello", "hi", "thanks", "thank you", "well", "so", "actually"}


def _content(s):
    """Content words, with possessives normalised.

    The possessive matters: the parser writes "Martin Mark's major", whose
    tokens are {martin, mark's}, while the owner strip-list holds {martin,
    mark}. Leaving "'s" attached made the owner's own surname read as
    ungrounded invented content and killed four of the five best propositions
    in the store -- including "User's name is Martin Mark", which is verbatim
    gold."""
    out = []
    for w in re.findall(r"[a-z0-9']+", str(s).lower()):
        w = w.rstrip("'").removesuffix("'s")
        if w and w not in STOP and len(w) > 2:
            out.append(w)
    return out


def _stems(words):
    """Crude stemming so inflected forms match their source ("lives"/"live")."""
    out = set()
    for w in words:
        out.add(w)
        for suf in ("ing", "ed", "es", "s", "ly"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                out.add(w[:-len(suf)])
        if w.endswith("ies"):
            out.add(w[:-3] + "y")
    return out


def prefilter(prop, turn, owner=None, min_grounded=0.85, min_content=1):
    """-> (keep: bool, reason: str). No model call."""
    text = str(prop).strip()
    if not text:
        return False, "empty"

    # "user" is a subject token too -- gold writes the name point as "User's
    # name is X", and counting "user" as content made it ungrounded.
    own = set(_content(owner or "")) | {"user"}
    pc = [w for w in _content(text) if w not in own]
    if len(pc) < min_content:
        # one content word can be the whole fact -- "Male", "Bachelor" --
        # and requiring two dropped "Martin Mark is a Male" against gold
        # "Martin Mark's gender is Male".
        return False, "not substantive (no content beyond the subject)"
    if text.lower().strip(" .") in _DISCOURSE:
        return False, "discourse marker"

    if _BAD_MORPH.search(text):
        return False, "malformed morphology"
    if _FIRST_RESIDUE.search(text):
        return False, "first-person residue (person shift incomplete)"
    if owner and re.search(rf"{re.escape(owner)}'s .* is {re.escape(owner)}'s",
                           text, re.I):
        return False, "degenerate self-reference"

    # GROUND THE VALUE, NOT THE SLOT NAME.
    #
    # A slot name is a LABEL we supply from our own schema; a value is CONTENT
    # that must come from the source. Gold calls it "birth date" where the
    # speaker said "born on", and "parent status" where they said "Both
    # parents are alive" -- so grounding the whole string rejects exactly the
    # canonical naming the lexicon exists to add, which is what happened: every
    # lexicon proposition was dropped as "ungrounded (birth, date)".
    #
    # The evidence-layer claim is that we never invent CONTENT. It was never
    # that we may only use the speaker's own words for our field names.
    body = text
    m = re.search(r"'s .{0,40}? (?:is|are|include[s]?)\s+(.*)$", text)
    if not m:
        m = re.search(r"'s .{0,40}?:\s*(.*)$", text)
    if m:
        body = m.group(1)
    vc = [w for w in _content(body) if w not in own] or pc

    src = _stems(_content(turn))
    ungrounded = [w for w in vc if w not in src and w[:-1] not in src
                  and (w + "s") not in src]
    pc = vc
    frac = 1.0 - (len(ungrounded) / max(1, len(pc)))
    if frac < min_grounded:
        return False, f"ungrounded ({', '.join(ungrounded[:4])})"
    return True, "kept"


VERIFY_PROMPT = (
    "Does the MESSAGE support the STATEMENT?\n\n"
    "MESSAGE:\n{turn}\n\nSTATEMENT:\n{prop}\n\n"
    "Answer with one word, YES or NO. Answer NO if the statement adds any "
    "detail the message does not state, or misattributes something."
)


def verify(prop, turn, ask):
    """Model entailment. `ask(prompt) -> str`. One yes/no, never generation."""
    out = ask(VERIFY_PROMPT.format(turn=str(turn)[:1500], prop=prop))
    return str(out).strip().upper().startswith("Y")
