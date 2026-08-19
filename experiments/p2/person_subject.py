"""PERSON vs NON-PERSON subject classification, generalised.

`reject_subject_attr` in run_profile_full.py catches a non-person subject
holding a personal attribute, but only against a small BARE-WORD set
(_NON_PERSON_SUBJECT = "team", "company", "ai", ...). Measured on user 10's
real store, these subjects leak straight through it and generate fake
relationship propositions ("Michelle Hernandez's Colleague network, who has
support..."):

    "Visionary Ai Solutions"   (a company, by NAME, not a bare word)
    "network"
    "organization"
    "startup"
    "Team Members"             (a PLURAL head noun, not an exact-set member)
    "Key Stakeholders"
    "Academic Advisors"

An exact-word set cannot catch a company name or a modified plural
("Key Stakeholders" is two words, neither of which is "team"). This module
replaces exact matching with a small number of GENERALISING rules.

SIGNALS USED, and why:

  1. Organisation, by name or suffix -- reuses run_profile_full.is_organization
     rather than duplicating it. "Visionary Ai Solutions" is caught by the
     "solutions" suffix, not by being a known bare word.
  2. Abstract/collective SINGULAR nouns ("network", "organization", "startup",
     "community", ...) -- a small explicit set, same house style as
     _NON_PERSON_SUBJECT and currency.NON_PERSON: no entity node is ever
     legitimately named "startup".
  3. Plural GROUP/ROLE head nouns ("members", "advisors", "stakeholders",
     "colleagues", ...), matched against the LAST WORD of the subject. This is
     what generalises past the exact-set failure: "Team Members", "Key
     Stakeholders" and "Academic Advisors" all have a different first word but
     the same tell -- the subject names a ROLE CLASS, not one identifiable
     individual. Matched by curated vocabulary, not by "ends in s": a real
     surname ending in s (Evans, Jones, Williams) must not be caught by
     spelling alone, so the set is a list of GROUP-NOUN words, checked as a
     whole token, not a suffix pattern.
  4. Positive person-shape evidence, used only to SHIELD signal 5 (below) from
     firing on an actual person, never to override signals 1-3: an honorific
     ("Dr. ...", "Mrs. ..."), a CamelCase Surname+Firstname merge (HaluMem's
     own writing of names, e.g. "AndersonElizabeth", "BrownKaren"), a spaced
     Title-Case full name ("Michelle Hernandez", "Nguyen Linh"), a relation
     qualifier attached at extraction time ("chris (friend)" -- see
     llm_profile.canon_subject), or membership in a small, deliberately
     non-exhaustive given-name list.
  5. The subject's OWN stored attributes: holding age/birth_date/gender/
     marital_status is person evidence; holding industry/headcount/revenue/
     founded_year/... is organisation evidence. This is the weakest signal
     (a store's own extraction noise can populate either bucket) so it is
     given the narrowest role: it is consulted ONLY when the name itself gave
     no confident verdict (signals 1-3 didn't reject, signal 4 didn't already
     shield it) -- catching an organisation whose NAME doesn't reveal it (no
     suffix, not a known brand, not an abstract noun) but whose FACTS do.

WHAT WAS REJECTED and why:
  - A large given-name gazetteer. Names are an open, culture-spanning set;
    an incomplete list would silently reject every name outside it. The
    asymmetry below makes this unnecessary: default-accept already covers
    "Karen", "Sophia", "Linh" without needing to recognise them as names.
  - Spelling-based plural detection ("ends in s" => group). Surnames end in s
    too (Evans, Jones, Rodgers). Signal 3 is vocabulary, not morphology.
  - Letting the attribute signal (5) override signals 1-3. "team" holding
    "age" reads as corrupted extraction, not evidence that the entity node
    named "team" is secretly a person -- and if it firmly were, the fact is
    stored under a subject that still resolves to a real person elsewhere by
    name, so nothing is lost by not chasing the override.
  - Any LLM/prompt-based judgment. Zero-for-three in this project; must be
    deterministic and fast enough to run on every stored subject.

THE ASYMMETRY, and it decides every close call: wrongly REJECTING a real
person's subject permanently loses their facts (the store never revisits a
dropped subject). Wrongly ACCEPTING a non-person subject produces one junk
record a later stage (dedup, corroboration, the QA layer) can still catch and
drop. So every rule here is a REJECT rule -- deny-list, not allow-list -- and
the default, whenever nothing confidently says "non-person", is ACCEPT. A
name that is merely unfamiliar, ambiguous, or unseen is a person by default.
"""
import re

from run_profile_full import is_organization, _NON_PERSON_SUBJECT, _QUALIFIER

# --- signal 2: abstract/collective nouns that are never one identifiable
# person, matched against the WHOLE (qualifier-stripped) subject. Kept small
# and explicit, same house style as _NON_PERSON_SUBJECT: a word only belongs
# here if no reasonable entity node is named that on its own.
_ABSTRACT_COLLECTIVE = {
    "network", "organization", "organisation", "startup", "community",
    "committee", "board", "department", "division", "industry", "market",
    "sector", "audience", "crowd", "public", "government", "media", "press",
    "platform", "staff", "personnel", "agency", "institution", "initiative",
    "foundation", "nonprofit", "non-profit", "charity", "association",
    "union", "council", "panel", "forum", "ecosystem", "workforce",
    "leadership", "management",
}

# --- signal 3: plural GROUP/ROLE head nouns. Matched against the LAST WORD
# only, because English puts the head noun last: "Team Members", "Key
# Stakeholders", "Academic Advisors" all end in one of these regardless of
# what qualifies them. Deliberately vocabulary (a fixed word list), not a
# spelling rule, so a real surname ending in "s" is never caught by accident.
_ROLE_GROUP_PLURAL = {
    "members", "stakeholders", "advisors", "advisers", "colleagues",
    "associates", "partners", "employees", "staff", "teammates", "clients",
    "coworkers", "co-workers", "peers", "teams", "groups", "networks",
    "communities", "committees", "boards", "departments", "friends",
    "people", "folks", "contacts", "connections", "followers",
    "subscribers", "attendees", "participants", "volunteers", "donors",
    "sponsors", "investors", "shareholders", "directors", "executives",
    "managers", "officers", "representatives", "delegates", "panelists",
    "mentors", "mentees", "alumni", "graduates", "colleagues", "advisors",
    "leads", "founders", "cofounders", "co-founders",
}

# --- signal 4: positive person-shape evidence -------------------------------
_HONORIFIC = re.compile(r"^(?:mr|mrs|ms|miss|mx|dr|prof|sir|dame|rev)\.?\s+\S",
                        re.I)
# HaluMem's own writing of a name as one merged token: "AndersonElizabeth",
# "BrownKaren" -- Surname+Firstname, no space, each half capitalised.
_CAMEL_MERGED = re.compile(r"^[A-Z][a-z]+(?:[A-Z][a-z]+)+$")
# a spaced Title-Case full name: "Michelle Hernandez", "Nguyen Linh"
_TITLE_CASE_MULTIWORD = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$")
# a relation word attached at extraction time (llm_profile.canon_subject:
# "my friend chris" -> "chris (friend)")
_RELATION_QUALIFIER = re.compile(
    r"\((?:friend|wife|husband|spouse|mentor|colleague|neighbou?r|brother|"
    r"sister|mother|father|cousin|boss|manager|client|partner|roommate|"
    r"girlfriend|boyfriend|coworker|co-worker|aunt|uncle|daughter|son|"
    r"grandmother|grandfather|grandma|grandpa|niece|nephew)\)", re.I)
# Small and deliberately NOT exhaustive (see module docstring): this only
# needs to shield signal 5 from a plain first name, not recognise every name.
_GIVEN_NAMES = {
    "karen", "sophia", "elizabeth", "michelle", "linh", "chris", "james",
    "john", "mary", "anna", "maria", "david", "daniel", "alex", "sarah",
    "emma", "olivia", "robert", "michael", "susan", "laura", "peter", "paul",
    "emily", "henry", "grace", "lucas", "mia", "noah", "ava", "liam",
    "ethan", "ella", "ryan", "natalie", "kevin", "rachel", "brian",
    "nicole", "jason", "amanda", "justin", "stephanie", "brandon",
    "melissa", "jonathan", "samantha", "andrew", "jessica", "hernandez",
}

# --- signal 5: attribute evidence -------------------------------------------
_PERSON_ONLY_ATTR = {"age", "birth_date", "gender", "marital_status"}
_ORG_ONLY_ATTR = {"industry", "headcount", "employee_count", "founded",
                  "founded_year", "revenue", "annual_revenue", "market_cap",
                  "tagline", "mission", "hq", "headquarters"}

_LEADING_QUALIFIER = re.compile(r"^(?:the|a|an|our|my)\s+")


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _core(s):
    """Whole-subject normal form for exact-set matching: lowercase, collapsed
    whitespace, trailing qualifier stripped (reuses run_profile_full's
    "google (part-time)" -> "google" rule so "network (internal)" also
    strips down to "network"), leading article stripped."""
    s = _QUALIFIER.sub("", _norm(s)).strip()
    return _LEADING_QUALIFIER.sub("", s)


def _has_positive_person_shape(raw, words):
    if _HONORIFIC.match(raw):
        return True
    if _CAMEL_MERGED.match(raw):
        return True
    if _TITLE_CASE_MULTIWORD.match(raw):
        return True
    if _RELATION_QUALIFIER.search(raw):
        return True
    return any(w.lower() in _GIVEN_NAMES for w in words)


def _attr_names(facts):
    """Accepts a list of attribute-name strings, a list of fact dicts
    (attribute/attr key, may carry a 'subject:' prefix), or a dict keyed by
    attribute name -- whatever shape the caller already has on hand."""
    if not facts:
        return set()
    if isinstance(facts, dict):
        facts = list(facts.keys())
    out = set()
    for f in facts:
        if isinstance(f, str):
            a = f
        elif isinstance(f, dict):
            a = f.get("attribute") or f.get("attr") or f.get("a") or ""
        else:
            continue
        a = str(a).rsplit(":", 1)[-1]
        out.add(a.strip().lower())
    return out


def is_person_subject(subject, facts=None):
    """True unless `subject` is confidently NOT a person.

    facts: optional -- the attribute names this subject already holds in the
    store (strings, fact dicts, or a dict keyed by attribute). Purely
    additional evidence; omit it and the name-only rules still run.

    Deterministic, no model calls. See module docstring for the signal list,
    what was rejected, and the accept-by-default asymmetry this is built
    around: an uncertain subject is a person.
    """
    raw = str(subject or "").strip()
    if not raw:
        # No subject means a self-fact (the store's owner) -- there is
        # nothing here to reject.
        return True

    core = _core(raw)
    words = core.split()
    last = words[-1] if words else ""

    # signals 1-3: confident, name-based, non-person -- these are curated to
    # be near-certain and always win, including over positive shape evidence.
    if is_organization(raw):
        return False
    if core in _NON_PERSON_SUBJECT or core in _ABSTRACT_COLLECTIVE:
        return False
    if last in _ROLE_GROUP_PLURAL:
        return False

    # signal 4: does the name itself already look like a person? If so,
    # signal 5 never gets a chance to reject it (see docstring: attribute
    # evidence is the weakest signal and only fires when the name gave no
    # verdict either way).
    if _has_positive_person_shape(raw, words):
        return True

    # signal 5: the subject's own attributes, consulted only because the name
    # was inconclusive. Person-only evidence wins over org-only evidence if,
    # somehow, both are present -- keeping the accept-by-default bias.
    attrs = _attr_names(facts)
    if attrs:
        if attrs & _PERSON_ONLY_ATTR:
            return True
        if attrs & _ORG_ONLY_ATTR:
            return False

    # Nothing confidently said non-person. Accept: an uncertain subject is a
    # person, because rejecting a real one is the expensive mistake.
    return True


if __name__ == "__main__":
    import json
    import os
    import re as _re
    import sys
    from collections import Counter, defaultdict

    HALUMEM = os.path.expanduser("~/rg_private/halumem")
    EVAL_DIR = os.path.expanduser(
        "~/rg_private/halumem/official/HaluMem/eval")
    CACHE = os.path.join(HALUMEM, "dev", "cache_u10_v5_14b.jsonl")
    GOLD_PATH = os.path.join(HALUMEM, "HaluMem-Medium.jsonl")

    if not os.path.isdir(EVAL_DIR):
        print(f"eval harness not found at {EVAL_DIR} -- nothing to measure "
              f"(this module has no dependency on it; only __main__ does).")
        sys.exit(0)

    sys.path.insert(0, EVAL_DIR)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("RG_EXTRACT_V5", "1")
    os.environ.setdefault("RG_INGEST_ALL_TURNS", "1")

    import halumem_run as H  # noqa: E402
    from run_profile_full import _NON_PERSON_SUBJECT as BASELINE  # noqa: E402
    from propositions import split_subject  # noqa: E402

    users = [json.loads(l) for l in open(GOLD_PATH)]
    u = users[10]
    if not os.path.exists(CACHE):
        print(f"cache not found at {CACHE} -- refusing to make model calls; "
              f"nothing measured.")
        sys.exit(0)

    mem, _ = H.ingest_user(u, cache_path=CACHE)
    nodes = list(mem.g.nodes.values()) + list(mem.g.provisional.values())

    # (a) distinct subjects, and this rule's verdict on each
    subj_attrs = defaultdict(set)
    for nd in nodes:
        subj, attr = split_subject(nd.get("attr", ""))
        subj_attrs[subj or ""].add(attr)

    verdict = {s: is_person_subject(s, facts=attrs)
               for s, attrs in subj_attrs.items()}
    non_owner = {s: v for s, v in verdict.items() if s}
    n_person = sum(1 for v in non_owner.values() if v)
    n_non_person = sum(1 for v in non_owner.values() if not v)

    print(f"(a) distinct non-owner subjects: {len(non_owner)}  "
          f"-> person: {n_person}, non-person: {n_non_person}")

    # gold-mined person names, from HaluMem's Relationship Memory points
    # ("Michelle Hernandez's Friend AndersonElizabeth, Elizabeth is a close
    # friend..."): every name that follows a possessive relation phrase is a
    # real person by construction.
    gold_people = set()
    # Case-insensitive on the RELATION WORD only ((?i:...) is scoped) -- a
    # blanket re.I flag would let [A-Z] in the capture group match lowercase
    # too, and did: it mined "at Google" and "and the" as "names" out of
    # "colleagues at Google" before this was scoped. The captured NAME must
    # stay strictly capitalised.
    rel_rx = _re.compile(
        r"(?:'s\s+|her\s+|his\s+|my\s+)(?i:Friend|Colleague|Family Member|"
        r"Relative|Partner|Spouse|Mentor|Neighbou?r|Classmate|Roommate|"
        r"Manager|Boss|Coworker|Co-worker)s?,?\s+"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][a-z]+)?)")

    def _mine(obj):
        if isinstance(obj, str):
            for m in rel_rx.finditer(obj):
                gold_people.add(m.group(1).strip())
        elif isinstance(obj, dict):
            for v in obj.values():
                _mine(v)
        elif isinstance(obj, list):
            for v in obj:
                _mine(v)

    for key in ("memory_points", "relationship_memory", "gold",
                "memories", "annotations"):
        if key in u:
            _mine(u[key])
    _mine(u)  # cheap net: scan the whole user record, regex is specific

    print(f"    gold-mined person names (Relationship Memory): "
          f"{len(gold_people)} -> {sorted(gold_people)[:20]}"
          f"{' ...' if len(gold_people) > 20 else ''}")

    # (b) false rejections: a gold-mined person whose subject string (loosely
    # matched -- store subjects are canon_subject()'d: lowercased, "andersonElizabeth"
    # style may appear as-is or split) our rule rejects.
    false_rejections = []
    for s, v in non_owner.items():
        if v:
            continue
        s_norm = _norm(s)
        s_tokens = set(_re.findall(r"[a-z]+", s_norm))
        for g in gold_people:
            g_norm = _norm(g)
            if g_norm == s_norm or g_norm in s_norm or s_norm in g_norm:
                false_rejections.append((s, g))
                break
            g_tokens = set(_re.findall(r"[a-z]+", g_norm)) | set(
                _re.findall(r"[A-Z][a-z]+", g))
            g_tokens = {t.lower() for t in g_tokens}
            if g_tokens and g_tokens & s_tokens:
                false_rejections.append((s, g))
                break

    print(f"\n(b) FALSE REJECTIONS against gold-mined person list: "
          f"{len(false_rejections)}")
    for s, g in false_rejections:
        print(f"    REJECTED subject {s!r} matches gold person {g!r}")
    if not false_rejections:
        print("    none.")

    # (c) full reject list, for a human to eyeball
    rejected = sorted(s for s, v in non_owner.items() if not v)
    print(f"\n(c) all {len(rejected)} rejected subjects:")
    for s in rejected:
        print(f"    {s!r}")

    # (d) leak examples from the task
    leaks = ["Visionary Ai Solutions", "network", "organization", "startup",
             "Team Members", "Key Stakeholders", "Academic Advisors"]
    caught = [(ex, not is_person_subject(ex)) for ex in leaks]
    n_caught = sum(1 for _, c in caught if c)
    print(f"\n(d) leak examples caught: {n_caught}/{len(leaks)}")
    for ex, c in caught:
        print(f"    {'CAUGHT' if c else 'MISSED'}  {ex!r}")

    # (e) baseline comparison against _NON_PERSON_SUBJECT
    baseline_reject = {s for s in non_owner if _norm(s) in BASELINE}
    ours_reject = set(rejected)
    print(f"\n(e) baseline (_NON_PERSON_SUBJECT exact-word set) rejects: "
          f"{len(baseline_reject)}")
    print(f"    this rule rejects: {len(ours_reject)}")
    only_ours = sorted(ours_reject - baseline_reject)
    print(f"    caught by this rule but NOT the baseline: {len(only_ours)}")
    for s in only_ours:
        print(f"      {s!r}")
    missed_by_ours = sorted(baseline_reject - ours_reject)
    print(f"    caught by the baseline but NOT this rule: "
          f"{len(missed_by_ours)}")
    for s in missed_by_ours:
        print(f"      {s!r}")
