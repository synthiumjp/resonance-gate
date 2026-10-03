"""Which value of a changing attribute is the CURRENT one.

The defect this fixes, seen by reading user 10's store rather than scoring it:
twenty-five job records sit flat with equal standing, so "what do you do?" has
eighteen answers. The striking part is that the store is RIGHT -- in
conversation order it holds a coherent career:

    s1   senior data scientist (apple)
    s3   lead data analyst (google)
    s11  part-time role
    s29  freelance career
    s39  founder and ceo
    s56  chief visionary officer (innovative ai corp)

Nothing is missing and nothing is wrong. The information needed to answer is
present and unreachable, because a memory that never supersedes anything is a
log, not a memory. For a product whose claim is LIVING memory of the user's
world, that is the defect, not the extraction.

WHAT IS AND IS NOT SINGLE-VALUED. Superseding the wrong attribute destroys
real knowledge: a person has one current employer but many hobbies, and
"latest wins" applied to `hobby` would throw away everything but the most
recent. So the set is explicit, small, and only contains attributes where a
person can hold exactly one value at a time. Everything else accumulates,
which is the safe default -- an over-eager supersession loses data, a missed
one only leaves clutter.

HISTORY IS KEPT, NEVER DELETED. Superseded values stay, marked, with the
position that replaced them. "Where did I work before Google?" is a question
a memory product must answer, and it is the same data.
"""
import re

# A person holds exactly one of these at a time. Deliberately conservative:
# adding an attribute here silently discards competing values, so the bar is
# "could a reasonable person hold two of these at once?" -- if yes, it stays out.
SINGLE_VALUED = {
    "occupation", "job_title", "employer", "workplace", "company",
    "location", "residence", "city", "country",
    "income", "monthly_income", "salary", "savings",
    "age", "birth_date", "gender", "name",
    "marital_status", "relationship_status",
    "lifestyle", "employment_status",
    "health_condition", "mental_health",
}

# Subjects that are not people and must not carry personal attributes.
# "Ai works as empathetic interaction", "Friends works as provide diverse
# perspectives", "Team works as instrumental in overcoming challenges" are all
# in the shipped store; they are extraction noise wearing a person's schema.
NON_PERSON = {"ai", "team", "friends", "colleagues", "family", "people",
              "everyone", "others", "society", "work", "company", "group",
              "community", "world", "technology"}


# --- alias groups for STATE slots (W2a, e215) ------------------------------
#
# The extractor spells one concept many ways. For user 10, the person's
# physical health state is spread over six slot names holding mutually
# contradictory values, all marked current:
#
#   physical_condition: normal, no chronic diseases   (early)
#   health_condition:   chronic disease
#   health_status:      hypertension managed
#   physical_health:    stable
#
# Supersession cannot fire because the keys never collide (e214).
#
# SCOPE, and it is the whole design. This aliases ONLY state-like slots -- the
# ones that are single-valued anyway, where two names for one concept produce
# a contradiction. It deliberately does NOT touch the narrative slots
# (motivation, value, belief, plan), which hold 233 and 86 values for this one
# user: those are genuinely multi-valued, merging them buys nothing, and
# supersession would be actively wrong.
#
# Mechanical normalisation was tried first and rejected on measurement:
# stripping current_/former_/_preference/_area style affixes collapsed 161
# names to 137 (15%) and the new collisions were almost all in `motivation`.
# The 161 names are different WORDS, not morphological variants, so the map is
# explicit and hand-checked rather than derived.
#
# NOTHING IS RENAMED. The store keeps whatever the extractor called it; these
# groups are used only to decide which value is current, so a wrong alias
# costs a wrong supersession, never a lost fact.
_ALIAS = {}


def _alias_group(*names, canon=None):
    tgt = canon or names[0]
    for n in names:
        _ALIAS[n] = tgt


_alias_group("occupation", "job_title", "job", "role", "position",
             "current_role", "current_position", "current_job")
_alias_group("employer", "current_employer", "company", "workplace",
             "organisation", "organization", "firm")
_alias_group("location", "residence", "city", "current_location", "hometown",
             "based_in")
_alias_group("income", "monthly_income", "salary", "current_income", "wage",
             "monthly_salary")
_alias_group("health_condition", "condition", "health", "health_status",
             "physical_condition", "physical_health", "physical_health_status")
_alias_group("mental_health", "mental_health_status", "mental_state",
             "mental_condition")
_alias_group("marital_status", "relationship_status")
_alias_group("employment_status", "work_status", "employment")

# A slot name that says the value is OLD. The extractor is already performing
# supersession here -- in the attribute name, three different ways (e214) --
# so read it rather than fight it: these alias to the base slot but may never
# WIN it, whatever their session order. Without this, "I used to work at
# Google" mentioned late would supersede the current employer.
_PAST_PREFIX = re.compile(r"^(?:former|past|previous|prior|ex)_(.+)$")


def canon_state_attr(attr):
    """-> (grouping key, is_past). Never renames the stored attribute."""
    a = str(attr or "").strip().lower()
    past = False
    m = _PAST_PREFIX.match(a)
    if m:
        a, past = m.group(1), True
    return _ALIAS.get(a, a), past


def _same_value(a, b):
    """Are these two strings the SAME fact, differently phrased?

    Exact comparison was enough while supersession only ever compared values
    inside ONE slot, where clustering had already merged variants. Across an
    alias group it is not: `monthly_income = "8700 usd"` and
    `income = "8700 usd monthly"` are one fact, and calling them a revision
    made the store report "updated from: 8700 usd monthly" -- a fabricated
    change, which on an update metric is worse than reporting nothing.

    Subset rather than similarity: one phrasing carrying strictly more detail
    than the other is the same fact elaborated. Two values that merely overlap
    ("8700 usd" vs "8210 usd") are not, and must stay a revision.
    """
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return True
    ta = {t for t in re.findall(r"[a-z0-9]+", na) if len(t) > 1}
    tb = {t for t in re.findall(r"[a-z0-9]+", nb) if len(t) > 1}
    if not ta or not tb:
        return False
    return ta <= tb or tb <= ta


def _norm(v):
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def is_non_person_subject(subject):
    return _norm(subject) in NON_PERSON


def resolve(facts):
    """Order-aware supersession over a list of stored facts.

    facts: dicts with at least `attr` and `value`, in the order they were
    learned; an optional `session` is used for reporting when present.

    Returns the same dicts, each with three keys added:
        current        True unless a later fact spoke to the same
                       subject+attribute
        superseded_by  index of the fact that CHANGED this value, else None
        restated_by    index of the fact that REPEATED this value, else None

    The two are distinguished deliberately. Restating a value is corroboration
    and changing it is supersession -- they mean opposite things about
    confidence, and collapsing them would make a fact look revised every time
    the user simply mentioned it again. Either way only the newest record
    surfaces as current, or "what do you do?" answers three times.

    Nothing is dropped. Multi-valued attributes are all current.
    """
    from propositions import split_subject

    out = []
    latest = {}
    for i, f in enumerate(facts):
        subj, attr = split_subject(f.get("attr", ""))
        key = (_norm(subj), attr)
        g = dict(f)
        g["current"] = True
        g["superseded_by"] = None
        g["restated_by"] = None
        out.append(g)
        if attr not in SINGLE_VALUED:
            continue
        prev = latest.get(key)
        if prev is not None:
            out[prev]["current"] = False
            if _norm(out[prev]["value"]) == _norm(f.get("value")):
                out[prev]["restated_by"] = i
            else:
                out[prev]["superseded_by"] = i
        latest[key] = i
    return out


def current(facts):
    """Just the facts that still hold."""
    return [f for f in resolve(facts) if f["current"]]


def history(facts, attr, subject=None):
    """Every value an attribute has held for ONE subject, oldest first -- the
    answer to "where did I work before?", which is the same data read the
    other way.

    subject=None means the profile owner, i.e. facts stored without a subject
    prefix. Scoping is not optional: without it a mentor's job and a
    colleague's job land in the owner's career history, which is how the first
    version of this read -- Sophia's "mentor" appearing in Michelle's job
    timeline."""
    from propositions import split_subject
    want = _norm(subject) if subject else None
    out = []
    for f in resolve(facts):
        subj, a = split_subject(f.get("attr", ""))
        if a != attr or _norm(subj) != (want or ""):
            continue
        out.append((f.get("value"), f.get("session"), f["current"]))
    return out


def subjects(facts):
    """Every subject the store holds facts about, with a flag for the ones
    that are not people. Reporting only -- resolve() never drops anything."""
    from propositions import split_subject
    seen = {}
    for f in facts:
        subj, _ = split_subject(f.get("attr", ""))
        name = subj or ""
        seen.setdefault(name, [0, is_non_person_subject(name)])
        seen[name][0] += 1
    return seen


# --- write-time supersession (W1) -----------------------------------------
#
# resolve() above answers the question at READ time, over a list of facts. That
# is the wrong place. Every system that scores well on HaluMem's UPDATING axis
# -- MOSAIC's write-time conflict detection, Zep's bitemporal valid_at/
# invalid_at edges, Eywa's "at most one active state fact per key" -- decides
# at INGESTION whether a new fact replaces an old one. The systems that leave
# it to the retriever score 5-25% on updating; ours scores 2.9%, worst on the
# board (e211).
#
# So the same rule runs once, when the store is built, and the answer is
# recorded on the node. Read-time then costs nothing and every consumer --
# retrieval, the artifact, the QA context -- sees the same verdict instead of
# each re-deriving it (or, today, not deriving it at all).

def _session_ord(conv_id):
    """Sort key for a receipt's conversation id. HaluMem ingestion writes
    's12'; other paths write real conversation uuids, which carry no order --
    those fall back to date, handled by the caller."""
    cid = str(conv_id)
    if cid.startswith("s") and cid[1:].isdigit():
        return int(cid[1:])
    return None


_TIER_RANK = {"asserted": 1, "provisional": 0}


def _evidence(nd):
    """Tiebreak within one session: corroboration first, then tier. Recency
    alone cannot separate two values asserted in the SAME session, and picking
    by list order silently chose a job DUTY over "chief visionary officer"
    when both landed in session 56."""
    return (int(nd.get("n_mentions", 1) or 1),
            _TIER_RANK.get(nd.get("tier"), 0))


def _node_position(nd):
    """(session_index, date) for the LATEST mention of a node -- the point at
    which the store last saw this value asserted."""
    best_s, best_d = None, ""
    for cid, date in (nd.get("convs") or {}).items():
        si = _session_ord(cid)
        if si is not None and (best_s is None or si > best_s):
            best_s = si
        if str(date) > best_d:
            best_d = str(date)
    return (best_s if best_s is not None else -1, best_d)


def mark_current(nodes):
    """Mark write-time supersession on wire node dicts, in place.

    nodes: an iterable of node dicts as built by WireGraph._mk_node -- each has
    `attr` (which may carry a 'subject:' prefix), `value`, and `convs`.

    Adds to every node:
        current        False if a LATER node gave the same subject+attribute a
                       different value
        superseded_by  the id of the node that replaced it, else None

    Non-destructive by design: nothing is dropped and history stays queryable.
    Only attributes in SINGLE_VALUED participate -- see the note there on why
    that set is deliberately small.

    Returns the number of nodes marked superseded.
    """
    from propositions import split_subject

    groups = {}
    for nd in nodes:
        nd.setdefault("current", True)
        nd.setdefault("superseded_by", None)
        subj, attr = split_subject(nd.get("attr", ""))
        canon, past = canon_state_attr(attr)
        nd["past"] = past
        if canon not in SINGLE_VALUED:
            continue
        groups.setdefault((_norm(subj), canon), []).append(nd)

    n = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda m: (_node_position(m), _evidence(m)))
        # a slot that names itself as past may never be the current value
        live = [m for m in members if not m.get("past")] or members

        # A GENUINE TIE IS NOT A DECISION. If two values share the latest
        # session AND the same evidence, we do not know which is current --
        # so both stay current rather than one being picked by list order.
        # Asserting the wrong one is worse than admitting the ambiguity, and
        # this is a store whose whole claim is not doing that.
        top = (_node_position(live[-1]), _evidence(live[-1]))
        winners = [m for m in live
                   if (_node_position(m), _evidence(m)) == top]
        winner = winners[-1]
        tied = {id(m) for m in winners}
        for w in winners:
            w.setdefault("supersedes", [])
        for nd in members:
            if id(nd) in tied:
                continue
            # Same value, different slot name ("employer" and
            # "current_employer" both holding "innovative ai corp") is a
            # DUPLICATE, not a revision. Within one slot the cluster already
            # merged these, so this only arises across an alias group -- and
            # leaving both current shows the user the same fact twice. Retire
            # it as a restatement, which is what it is: corroboration, not a
            # change of mind.
            nd["current"] = False
            if _same_value(nd.get("value"), winner.get("value")):
                nd["restated_by"] = winner.get("id")
            else:
                nd["superseded_by"] = winner.get("id")
                # THE REVERSE LINK, and it is the one that matters. Retrieval
                # returns the CURRENT node; the old value is ranked lower and
                # usually never surfaces. Recording only old->new therefore
                # hides the pair from anything that reads the store. The
                # update judge asks for "all information points" of "updated
                # X from A to B", so the current node has to carry A.
                # entry 244 follow-up: prefer the retired node's own
                # proposition text over its bare value -- "supersedes" is
                # read verbatim by callers (eval_rgp2.py's "updated from:"
                # annotation), and the raw value alone can be an ungrammatical
                # fragment ("since becoming the senior director") where the
                # full text reads as prose. Falls back to value when the node
                # has no text (LLM-cache facts), unchanged from before.
                winner["supersedes"].append(nd.get("text") or nd.get("value"))
                n += 1
    return n


# ---------------------------------------------------------------------------
# e273: CESSATION. The user says when something ENDS, and nobody was listening.
#
# `mark_current` gates on SINGLE_VALUED, a 24-name allowlist that covers 0.2%
# of the rgx store (e251), so on the product path essentially nothing is ever
# marked stale. The product harness makes the consequence visible: "I sold the
# Volvo. I drive a Skoda now." and "What car do I drive?" still answers Volvo.
#
# But the user TOLD us. "I left Lumen Health", "I sold the Volvo", "I am no
# longer a vegetarian" are cessation statements, and the deterministic parser
# already extracts them cleanly (pred=leave val="Lumen Health"). This reads
# that signal instead of inferring one -- evidence, not a heuristic about
# recency.
#
# What it does NOT do is delete anything. A receipt is permanent; a stale fact
# stays in the store, marked, so it can still be quoted with its date. Hiding
# it would be the same class of dishonesty as inventing one.

CESSATION_PREDS = frozenset((
    "leave", "quit", "sell", "stop", "end", "cancel", "resign", "drop",
    "abandon", "discontinue", "unsubscribe", "delete", "retire"))

_CESSATION_PHRASES = ("no longer", "not any more", "not anymore",
                      "used to", "no more")
# 2026-10-02 (false-memory bench): an ending that is an event about a
# PERSON or animal. Review 2026-10-02: it ends only facts that name the same
# one -- "My friend died in Leeds" ended "I live in Leeds" when the place was
# what got matched.
_EVENT_END = (" died", "passed away", "split up", "broke up", "broken up")
# the cessation's own words, never what it ends ("Biscuit died" ends what
# mentions Biscuit, not what mentions "died")
_CESSATION_WORDS = frozenset("""died dies passed away split broke broken
sold sell sells quit quits left leave leaves stopped stop stops ended end
cancelled canceled cancel dropped drop resigned retired""".split())

_NOISE = frozenset("""
a an the my your his her their its this that these those of at in on for to
and or but not no longer any more anymore now last month year week job
monday tuesday wednesday thursday friday saturday sunday weekend yesterday
today tonight morning afternoon evening ago recently finally just again over
january february march april may june july august september october november
december
""".split())


def _stem(t):
    """Plural to singular, enough to match "the Italian class" against
    "evening classes in Italian"."""
    if len(t) > 4 and t.endswith("es") and t[-3] in "sxz" or t.endswith(("ches", "shes")):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def _infer_owner(g):
    """The name most records start with ("Dana Cole ..."), when the caller
    did not pass one."""
    import re
    from collections import Counter
    c = Counter()
    n = 0
    for st in (g.nodes, g.provisional):
        for nd in st.values():
            m = re.match(r"([A-Z][a-z]+ [A-Z][a-z]+)(?:'s)?\b", nd.get("text") or "")
            n += 1
            if m:
                c[m.group(1)] += 1
    if c:
        name, k = c.most_common(1)[0]
        if k >= max(1, 0.3 * n):
            return name
    return None


def _named_others(text, owner=None):
    """Names introduced with "named"/"called" or as "my <relation> <Name>"."""
    import re
    own = {w.lower() for w in re.findall(r"[A-Za-z]+", owner or "")}
    out = set()
    for m in re.finditer(r"\b(?:named|called|(?:dog|cat|friend|sister|brother|"
                         r"girlfriend|boyfriend|wife|husband|partner|son|"
                         r"daughter|colleague|boss|manager|neighbour|neighbor)"
                         r")\s+([A-Z][a-z]+)", text or ""):
        if m.group(1).lower() not in own:
            out.add(m.group(1).lower())
    return out


def _names(text, owner=None):
    """Capitalised words that are not the first word or the owner's name,
    lower-cased."""
    import re
    own = {w.lower() for w in re.findall(r"[A-Za-z]+", owner or "")}
    words = re.findall(r"[A-Za-z][a-z']+", text or "")
    out = set()
    for i, w in enumerate(words):
        b = w.rstrip("'s").rstrip("'")
        if i and b[:1].isupper() and b.lower() not in own \
                and b.lower() not in _NOISE:
            out.add(b.lower())
    first = words[0].rstrip("'s").rstrip("'") if words else ""
    if first[:1].isupper() and first.lower() not in own and first.lower() not in (
            "the", "my", "a", "an", "i", "we", "our"):
        out.add(first.lower())
    return out


def _content(text):
    import re
    return {_stem(t) for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in _NOISE and len(t) > 2}


def _latest(nd, order=None):
    """Latest mention, as an ORDINAL when conversation order is known.

    Dates alone are not enough: a user can state a fact and supersede it in
    the same day, which is exactly what happens in one sitting with an
    assistant, and `convs` then gives both nodes the same string. `order`
    maps conversation id -> ingestion ordinal, which is a real sequence.
    """
    convs = nd.get("convs", {}) or {}
    if order:
        ords = [order[c] for c in convs if c in order]
        if ords:
            return max(ords)
    ds = sorted(convs.values())
    return ds[-1] if ds else ""


def mark_ceased(g, owner=None, order=None):
    """Mark nodes a later cessation statement has ended. Returns the list of
    (ceased_node_id, cessation_node_id) pairs it set, for the caller to log.

    Deliberately conservative:
      * the cessation record must be strictly LATER than the node it ends;
      * EVERY content token of the cessation's object must appear in the
        node's text, so "sold the Volvo" ends "car is a Volvo" and not
        "bike is red";
      * a node is never ended by itself, and never by another cessation.
    """
    if owner is None:
        owner = _infer_owner(g)
    stores = [g.nodes, g.provisional]
    ceased = []
    cess = []
    for st in stores:
        for nid, nd in st.items():
            attr = (nd.get("attr") or "").lower()
            val = (nd.get("value") or "").lower()
            text = (nd.get("text") or "").lower()
            if any(p in f" {text}" for p in _EVENT_END):
                # who died is named BEFORE the verb; "at St Mary's" is where
                raw = nd.get("text") or ""
                cut = min(raw.lower().find(p.strip()) for p in _EVENT_END
                          if p.strip() in raw.lower())
                names = _names(raw[:cut], owner)
                if names:
                    cess.append((nid, nd, names, _latest(nd, order), True))
                continue
            is_cess = (attr.split("_")[0] in CESSATION_PREDS
                       or any(p in val for p in _CESSATION_PHRASES)
                       or any(p in text for p in _CESSATION_PHRASES))
            if is_cess:
                toks = _content(nd.get("value")) - _CESSATION_WORDS
                if toks:
                    cess.append((nid, nd, toks, _latest(nd, order), False))
    if not cess:
        return ceased
    for st in stores:
        for nid, nd in st.items():
            ndate = _latest(nd, order)
            hay = f"{nd.get('text') or ''} {nd.get('value') or ''}".lower()
            for cid, cnd, toks, cdate, by_name in cess:
                if cid == nid:
                    continue
                # "a dog named Rex and a cat named Tom": Tom's death does
                # not end Rex. Only names INTRODUCED as names count -- a
                # place in the same fact ("...a trip to Japan") is not a
                # second person (false-memory bench b05)
                if by_name and _named_others(nd.get("text"), owner) - toks:
                    continue
                if cdate == "" or ndate == "" or ndate >= cdate:
                    continue
                if by_name:
                    import re as _re
                    if not toks.issubset(set(_re.findall(r"[a-z]+", hay))):
                        continue
                elif not toks.issubset(_content(hay)):
                    continue
                nd["current"] = False
                nd["superseded_by"] = cid
                # e274: distinguishes "the USER said this ended" from "a
                # heuristic decided this is stale". Only the former resolves a
                # conflict -- a heuristic's guess is exactly what the conflict
                # surface exists to ASK about instead of silently picking.
                nd["ceased"] = True
                ceased.append((nid, cid))
                break
    return ceased


# ---------------------------------------------------------------------------
# 2026-10-02: STATE CHANGES. "I moved to Brunswick" did not supersede "I live
# in Fitzroy" -- found by a stranger installing the product, not by the
# harness. `mark_current` keys on SINGLE_VALUED slot names from the LLM
# extractor ("residence", "employer"); the deterministic parser files the same
# facts under its own predicate keys ("live_in", "move_to", "work_at",
# "join"), so on the product path nothing was ever superseded by a later
# value -- only by an explicit ending ("I quit", "no longer").
#
# A STATE FAMILY is one thing a person has exactly one of at a time, read off
# the parser's own keys. Some members HOLD the state ("I live in X"), some
# ENTER it ("I moved to X", "I joined X"); a later member with a different
# value replaces an earlier one. Deliberately small: two families, both ones
# where "could a reasonable person hold two at once?" is mostly no. Hedged
# plans never enter a family -- "I'm thinking about moving to Brunswick" is
# filed under `think`, not `move_to`, by the parser itself.

_PLACE_NOISE = frozenset("""
in at to on from the a an now again currently anymore any more last this next
week weekend month year years ago recently just finally back there here
""".split())

# Role nouns. Matched on the HEAD of the predicate noun phrase only, so "a
# huge fan of jazz" is not a job and "a senior nurse at the Alfred" is a
# nurse. Deliberately a closed list: a role that is missing here is simply
# not tracked, while a non-role that slipped in ("runner") would make a
# hobby supersede a job.
_ROLES = frozenset("""
nurse doctor physician surgeon gp dentist pharmacist paramedic midwife therapist
physiotherapist psychologist psychiatrist counsellor counselor vet veterinarian
teacher tutor lecturer professor principal librarian researcher scientist
engineer developer programmer architect designer analyst consultant manager
director lead supervisor coordinator administrator assistant secretary
receptionist clerk accountant auditor bookkeeper lawyer solicitor barrister
paralegal judge journalist editor writer author translator photographer artist
musician chef cook baker barista waiter waitress bartender cashier retailer
salesperson recruiter marketer founder ceo cto cfo coo owner freelancer
contractor intern apprentice student pilot driver mechanic electrician plumber
carpenter builder labourer laborer gardener cleaner carer caregiver officer
firefighter soldier detective farmer technician operator nanny
""".split())
_DIETS = frozenset("vegetarian vegan pescatarian carnivore omnivore keto paleo".split())
_STATUS = {"single": "single", "married": "married", "engaged": "engaged",
           "divorced": "divorced", "separated": "separated",
           "widowed": "widowed", "dating": "dating"}
_EVENT_STATUS = {"divorce": "divorced", "engage": "engaged",
                 "separate": "separated", "remarry": "married",
                 "widow": "widowed"}
_CAR_BRANDS = frozenset("""
volvo skoda tesla toyota honda mazda subaru nissan ford holden hyundai kia
volkswagen vw audi bmw mercedes porsche jeep lexus mitsubishi suzuki renault
peugeot citroen fiat mini jaguar landrover rivian polestar byd mg
corolla camry yaris prius rav4 tiguan impreza i30 cerato
""".split())
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_HEAD_STOP = re.compile(r"\b(of|at|in|for|with|who|that|which|from|on|to|"
                        r"because|since|and|but)\b")
_LEAD = re.compile(r"^(?:now|currently|still|finally|officially|also|"
                   r"actually|really)\s+")
_TRAIL = re.compile(r"\s+(?:now|again|anymore|any more|these days|"
                    r"currently|too|as well|nowadays)$")


def _head_phrase(value):
    """The predicate noun phrase up to its first preposition or clause,
    without leading/trailing time adverbs: 'now a senior nurse at the
    Alfred' -> 'a senior nurse'."""
    v = (value or "").lower().strip(" .!,")
    v = _LEAD.sub("", v)
    m = _HEAD_STOP.search(v)
    if m:
        v = v[:m.start()]
    v = _TRAIL.sub("", v.strip())
    return v.strip()


def _place_tokens(value):
    return {t for t in re.findall(r"[a-z0-9']+", (value or "").lower())
            if t not in _PLACE_NOISE and len(t) > 1}


_RES_PREDS = {"live_in", "reside_in", "move_to", "relocate_to", "settle_in"}
_HOME_SLOTS = {"place", "house", "flat", "apartment", "home", "unit"}
_NOT_A_PLACE = frozenset("""a an the need good bad great nice terrible decent
fine poor perfect excellent awful total complete such process state shape
order disrepair desperate dire much some""".split())
_EMP_PREDS = {"work_at", "work_for", "join", "start_at", "employ_by"}
_JOB_PREDS = {"get", "start", "land", "take", "accept", "work_as"}


def _families(attr, value, weak=False):
    """-> [(family, value key)] for the single-valued states this fact
    states. A fact can state two ("I work as a nurse at St Vincent's" is a
    role AND an employer). The key is what two facts must share to be the
    same value; a later fact in the family with a different key replaces an
    earlier one."""
    a = (attr or "").lower().split(":")[-1]
    v = (value or "").lower()
    out = []
    neg = bool(re.match(r"^(not|no longer)\b", v.strip()))
    # 2026-10-02 (false-memory bench): "Our place is in Northcote" -- the
    # home is the subject and the place its complement
    home = None
    if a in _HOME_SLOTS:
        # Review 2026-10-02: "My flat is in a terrible state", "in need of a
        # new roof", "in good shape" are not addresses. The word after "in"
        # must start a place name, and only that phrase is the place.
        m = re.match(r"^in\s+([a-z]+(?:\s+[a-z]+)?)", v)
        if m and m.group(1).split()[0] not in _NOT_A_PLACE:
            home = m.group(1)
    if a in _RES_PREDS or home:
        t = _place_tokens(home or v)
        if t:
            out.append(("residence", frozenset(t)))
    if a in _EMP_PREDS:
        t = _place_tokens(v)
        if t:
            out.append(("employer", frozenset(t)))
    # "I do freight scheduling for a shipping firm": a job described by what
    # the person does for an organisation
    m = re.search(r"\bfor (?:a|an|the) ((?:\w+ ){0,3}(?:firm|company|agency|"
                  r"business|startup|bank|hospital|school|council|charity|"
                  r"studio|consultancy|corporation|organi[sz]ation|clinic|"
                  r"university|newspaper|nonprofit|ngo))\b", v)
    # Review 2026-10-02: "I do the garden for the council", "I run a book
    # club for a school" are not jobs, so this only GROUNDS a question about
    # work (weak=True); it never replaces an employer.
    if weak and a in ("do", "handle", "run", "manage", "work") and m and not neg:
        t = _place_tokens(m.group(1))
        if t:
            out.append(("employer", frozenset(t)))
    if a in _JOB_PREDS:
        m = re.search(r"\bat\s+(.+)$", v)
        if m and (a == "work_as" or "job" in v or "role" in v or "position" in v):
            t = _place_tokens(m.group(1))
            if t:
                out.append(("employer", frozenset(t)))
    # "started eating fish again" states a diet the way "eats fish" does
    m = re.match(r"^(?:eating|to eat)\s+(.*)$", v)
    if a in ("start", "begin", "go_back") and m:
        a, v = "eat", m.group(1)
    weak_meat = bool(re.search(r"\b(free|fingers?|pies?|substitutes?|"
                               r"alternatives?|once|occasionally|rarely|for "
                               r"charity|on holiday|and chips)\b|-free", v))
    head = _head_phrase(re.sub(r"^(?:as|to)\s+", "", v)
                        if a in ("work_as", "start_as", "promote_to", "hire_as")
                        else v)
    hw = re.findall(r"[a-z]+", head)
    # "started as an intern in a lab for a week", "hired me as a tutor for
    # my kid": a role with a "for" phrase is a stint, not a change of job --
    # it grounds a question but does not replace the role
    stint = (a in ("start_as", "hire_as") and re.search(r"\bfor\b", v)
             and not weak)
    if a in ("is", "become", "work_as", "train_as", "qualify_as", "start_as",
             "promote_to", "hire_as") and hw and hw[-1] in _ROLES and not neg \
            and not stint:
        # the role noun plus the modifier just before it: 'ward manager',
        # 'team lead', but 'senior nurse' == 'nurse' -- except after a
        # promotion, where the level is the change
        role = hw[-1]
        level = ("senior", "junior", "head", "lead", "principal", "chief")
        if len(hw) >= 2 and (hw[-2] not in ("a", "an", "the", "senior",
                                            "junior", "head", "new", "full",
                                            "time", "part")
                             or (a == "promote_to" and hw[-2] in level)):
            role = f"{hw[-2]} {role}"
        out.append(("role", frozenset([role])))
    if a in ("is", "become", "go", "turn", "eat") and hw and hw[-1] in _DIETS:
        out.append(("diet", frozenset([("not " if neg else "") + hw[-1]])))
    if a == "eat" and re.search(r"\b(meat|chicken|beef|fish|pork|seafood)\b", v) \
            and not neg and not weak_meat:
        out.append(("diet", frozenset(["eats meat"])))
    if a in ("is", "become", "get") and hw and hw[-1] in _STATUS:
        out.append(("relationship status",
                    frozenset([("not " if neg else "") + _STATUS[hw[-1]]])))
    # 2026-10-03 (stale dev set): "my girlfriend Mara" after "I'm single" is
    # a change of status; the possessed partner word names it
    if not neg:
        if re.match(r"^(?:wife|husband)(?:_|$)", a):
            out.append(("relationship status", frozenset(["married"])))
        elif re.match(r"^(?:girlfriend|boyfriend|partner|fiance|fiancee)(?:_|$)", a):
            out.append(("relationship status",
                        frozenset(["engaged" if a.startswith("fianc") else "partnered"])))
    if a.startswith("marry") and not neg:
        out.append(("relationship status", frozenset(["married"])))
    # 2026-10-02: the parser now keeps life events with nothing after the
    # verb ("I got divorced last year", "I'm engaged!"). The predicate is the
    # verb itself, so a possessed subject ("dad_retire") never matches.
    verb = a.split("_")[0]
    if verb in _EVENT_STATUS and not neg:
        out.append(("relationship status", frozenset([_EVENT_STATUS[verb]])))
    if verb == "retire" and not neg:
        out.append(("role", frozenset(["retired"])))
    if a in ("is", "turn"):
        m = re.fullmatch(r"(\d{1,3})(?:\s+years?\s+old)?", head)
        if m and 0 < int(m.group(1)) < 120:
            out.append(("age", frozenset([m.group(1)])))
    if a in ("drive", "buy", "own", "get"):
        brands = set(re.findall(r"[a-z]+", v)) & _CAR_BRANDS
        if brands or (a == "drive" and hw):
            out.append(("car", frozenset(brands or hw[-1:])))
    if a == "have":
        m = re.search(r"\b(\d+|" + "|".join(_NUM_WORDS) +
                      r")\s+(kids|children|sons|daughters)\b", v)
        if m:
            n = m.group(1)
            out.append(("number of children",
                        frozenset([str(_NUM_WORDS.get(n, n))])))
    return out


def _family_value(attr, value):
    """Back-compat: the first family, as (family, token set)."""
    fams = _families(attr, value)
    return (fams[0][0], set(fams[0][1])) if fams else (None, None)


# "I ALSO joined the Alfred" is a second job, not a change of job -- found by
# the first test of this pass, which marked St Vincent's "no longer true".
_ADDITIVE = re.compile(r"\b(also|as well|too|second job|another job|"
                       r"side job|part[- ]time|on the side|in addition)\b")


def _different(fam, a, b):
    """Place and employer values are token sets ('in Brunswick now' ~ 'to
    Brunswick'): different only if neither contains the other. The other
    families hold one normalised key, compared exactly."""
    if fam in ("residence", "employer"):
        return not (a <= b or b <= a)
    return a != b


# 2026-10-02: things said in passing. Research into what users want: "the
# LLM treating a casual comment made three weeks ago ("I'm eating keto
# today") as an unshakeable, permanent constraint". A statement tied to the
# moment, or a mood, is kept and searchable, but it never replaces a lasting
# fact and it drops out of the session summary after a few days.
_PASSING_TIME = re.compile(
    r"\b(today|tonight|this (?:morning|afternoon|evening|week|weekend)|"
    r"right now|at the moment|for now|atm|for the day)\b", re.I)
_MOODS = frozenset("""tired exhausted stressed hungry thirsty sick ill bored
busy anxious sad angry frustrated sleepy hungover annoyed grumpy overwhelmed
cranky knackered cold hot excited nervous upset""".split())
_INTENSIFIERS = re.compile(r"^(?:so|really|very|a bit|a little|pretty|kind of|"
                           r"kinda|super|quite|feeling|absolutely|totally)\s+")


def passing(text=None, said=None, attr=None, value=None):
    """Is this fact tied to the moment it was said?"""
    if _PASSING_TIME.search(said or text or ""):
        return True
    a = (attr or "").lower().split(":")[-1]
    if a in ("is", "feel", "get") and value:
        v = value.lower().strip()
        while True:
            v2 = _INTENSIFIERS.sub("", v)
            if v2 == v:
                break
            v = v2
        words = re.findall(r"[a-z]+", v)
        if words and words[0] in _MOODS and len(words) <= 3:
            return True
    return False


def mark_state_changes(g, order=None):
    """Mark facts a LATER statement in the same state family replaced.
    Returns [(old_node_id, new_node_id)].

    Conservative, like mark_ceased:
      * the replacing fact must be strictly LATER (by conversation order);
        two statements in one conversation are not ordered here;
      * values must actually differ -- neither token set contains the other,
        so "lives in Brunswick now" is a restatement of "moved to Brunswick",
        not a change;
      * nothing is deleted: the old fact stays, marked current=False with
        superseded_by, and renders "(no longer true)".
    The user SAID the state changed, so the old fact is also marked `ceased`
    -- which, by e274's rule, resolves a would-be conflict instead of asking.
    """
    members = {}
    for st in (g.nodes, g.provisional):
        for nid, nd in st.items():
            said = f"{nd.get('text') or ''} {nd.get('source') or ''}"
            additive = bool(_ADDITIVE.search(said.lower()))
            # "I'm in Sydney this week" does not move anyone to Sydney
            if passing(nd.get("text"), nd.get("source"), nd.get("attr"),
                       nd.get("value")):
                continue
            for fam, key in _families(nd.get("attr"), nd.get("value")):
                members.setdefault(fam, []).append(
                    (nid, nd, set(key), _latest(nd, order), additive))
    changed = []
    for fam, items in members.items():
        for nid, nd, toks, when, _add in items:
            if nd.get("current") is False and nd.get("superseded_by"):
                continue
            later = [(cid, ctoks, cwhen) for cid, _c, ctoks, cwhen, cadd in items
                     if cid != nid and cwhen != "" and when != ""
                     and cwhen > when and not cadd
                     and _different(fam, toks, ctoks)]
            if not later:
                continue
            cid = max(later, key=lambda x: x[2])[0]
            nd["current"] = False
            nd["superseded_by"] = cid
            nd["ceased"] = True
            changed.append((nid, cid))
    return changed
