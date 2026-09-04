"""Person registry and mention linking over rgx records.

WHY THIS EXISTS (e243). The parser stores the user's third parties as bare
names -- "Susan's support inspires Martin Mark" -- because the relation was
stated turns earlier ("Susan is my friend") and a per-turn parser cannot
carry it. HaluMem's Relationship gold names the relation, so those records
match on content and miss on the judge. e220 measured relation attachment
at +0.6pt pooled F1 and e243 sized the ceiling at ~2pt (27 of 575 gold
points), so this is NOT a benchmark lever and must not be sold as one. It
is a PRODUCT mechanism: a person node that carries its relation to the
owner, with the receipts that assert it.

SHAPE BORROWED, EVIDENCE NOT (arXiv:2603.27277 sec. 3.4). Codebase-Memory
resolves a call site to a definition through a prioritised cascade of
strategies, each carrying its own confidence, falling back to fuzzy string
similarity. The cascade shape is the right one for mention -> entity. Their
paper gives no ablation and no precision number for it, so only the shape
is taken.

WHERE WE DELIBERATELY STOP. Their strategies 5 (suffix, 0.55) and 6 (fuzzy
string similarity, 0.30-0.40) guess when nothing structured matches. RG
does not guess about who a person is: a wrong link attaches one person's
relation to another and renders a fact the user never stated. This cascade
declines instead, and the disposition log records the decline so the
population that WOULD need guessing is measurable rather than assumed.

Nothing here calls a model. Nothing here needs stanza -- it runs over
already-extracted Records (or plain dicts with a "text" key).
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

# Relation nouns that, when POSSESSED BY THE OWNER, assert a relationship.
# Kept deliberately small and concrete: every one of these is a relation a
# person can stand in to the profile owner. Roles that are jobs rather than
# relations ("director", "president") are NOT here -- they belong to the
# person's own attributes, not to the owner's social graph.
RELATION_NOUNS = frozenset("""
colleague colleagues coworker coworkers co-worker co-workers teammate
teammates friend friends mentor mentors mentee mentees manager managers
supervisor supervisors boss bosses client clients partner partners
neighbour neighbours neighbor neighbors classmate classmates roommate
roommates wife husband spouse brother sister sibling siblings mother
father parent parents son daughter child children cousin cousins aunt
uncle nephew niece grandmother grandfather advisor advisors therapist
doctor trainer coach landlord tenant
""".split())

# A capitalised token, or a CamelCase run of them ("WilliamsJoshua"), which
# is how HaluMem writes persona names.
_NAME = r"[A-Z][a-z]+(?:[A-Z][a-z]+)*"
_CAMEL = re.compile(r"[A-Z][a-z]+")

# Confidence per strategy. Ordering is the cascade order; the numbers are
# NOT measured -- they are a declared prior, and the disposition log is what
# turns them into something measurable.
CONF = {"exact": 0.95, "alias": 0.85, "unique": 0.75}


def camel_parts(name):
    """"WilliamsJoshua" -> ["Williams", "Joshua"]; "Susan" -> ["Susan"]."""
    parts = _CAMEL.findall(name)
    return parts if len(parts) > 1 else [name]


@dataclass
class Person:
    """One third party in the owner's world."""
    canonical: str
    aliases: set = field(default_factory=set)
    relations: Counter = field(default_factory=Counter)
    mentions: int = 0
    receipts: list = field(default_factory=list)   # (session, turn) of relation stmts

    @property
    def relation(self):
        """The best-supported relation, or None when there is no support."""
        if not self.relations:
            return None
        return self.relations.most_common(1)[0][0]

    @property
    def relation_confidence(self):
        """Share of relation-statement support behind `relation`. 0.0 when
        none. A value below 1.0 means the store CONTRADICTS itself about
        this person, which is a finding, not a rounding error."""
        total = sum(self.relations.values())
        if not total:
            return 0.0
        return self.relations.most_common(1)[0][1] / total

    @property
    def contested(self):
        return len(self.relations) > 1


def _norm_owner(owner_name):
    """Owner tokens that must never be mistaken for a third party."""
    if not owner_name:
        return set()
    toks = set(camel_parts(owner_name)) | set(owner_name.split())
    return {t for t in toks if t}


class Registry:
    """Harvests person -> relation from records, then resolves mentions.

    Two phases on purpose. Relations are harvested from the WHOLE record
    set before any mention is resolved, so a relation stated in session 9
    is available to a bare mention in session 2. That is the retroactive
    resolution the paper applies to C++ template calls (sec. 3.4), and it
    is the reason this cannot live in the per-turn parser.
    """

    def __init__(self, owner_name=None):
        self.owner_name = owner_name
        self._owner_toks = _norm_owner(owner_name)
        self.people = {}          # canonical -> Person
        self._alias_index = {}    # alias -> set(canonical)
        self._built = False

    # ---- phase 1: harvest -------------------------------------------------

    def _rel_pattern(self):
        if not self.owner_name:
            return None
        own = re.escape(self.owner_name)
        rel = r"([A-Za-z][a-z\-]+)"
        # "<Owner>'s colleague Joshua" / "<Owner>'s colleagues Daniel and Joshua"
        return re.compile(
            rf"{own}'s\s+{rel}\s+((?:{_NAME})(?:\s+and\s+{_NAME})*)")

    def add_records(self, records):
        """Read relation statements out of records. A record may be an rgx
        Record or any object/dict carrying `text` (+ optional session/turn)."""
        pat = self._rel_pattern()
        if pat is None:
            return self
        for r in records:
            text = r.get("text") if isinstance(r, dict) else getattr(r, "text", None)
            if not text:
                continue
            sess = r.get("session") if isinstance(r, dict) else getattr(r, "session", None)
            turn = r.get("turn") if isinstance(r, dict) else getattr(r, "turn", None)
            for m in pat.finditer(text):
                rel = m.group(1).lower()
                if rel not in RELATION_NOUNS:
                    continue
                rel = _singular(rel)
                for name in re.findall(_NAME, m.group(2)):
                    if name in self._owner_toks:
                        continue
                    p = self.people.setdefault(name, Person(canonical=name))
                    p.relations[rel] += 1
                    p.receipts.append((sess, turn))
        self._built = False
        return self

    def build(self):
        """Merge CamelCase canonicals with their bare components, then index
        aliases. "WilliamsJoshua" + "Joshua" become one person iff "Joshua"
        is a component of exactly ONE canonical -- the unique-name gate,
        applied to the registry itself."""
        # component -> canonicals containing it
        comp = {}
        for canon in self.people:
            for part in camel_parts(canon):
                comp.setdefault(part, set()).add(canon)

        # fold a bare name into a multi-part canonical when unambiguous
        for bare in [c for c in list(self.people) if len(camel_parts(c)) == 1]:
            owners = {c for c in comp.get(bare, ()) if c != bare
                      and len(camel_parts(c)) > 1}
            if len(owners) == 1:
                canon = owners.pop()
                merged = self.people.pop(bare)
                target = self.people[canon]
                target.relations.update(merged.relations)
                target.receipts.extend(merged.receipts)
                target.aliases.add(bare)

        self._alias_index = {}
        for canon, p in self.people.items():
            keys = {canon} | set(camel_parts(canon)) | p.aliases
            p.aliases = keys - {canon}
            for k in keys:
                if k in self._owner_toks:
                    continue
                self._alias_index.setdefault(k, set()).add(canon)
        self._built = True
        return self

    # ---- phase 2: resolve -------------------------------------------------

    def resolve(self, mention):
        """mention -> (Person|None, strategy, confidence).

        Strategies, in cascade order:
          exact  0.95  the mention IS a canonical name
          alias  0.85  a registered alias of exactly one person
          unique 0.75  matches exactly one person by component containment
        Declines: 'owner' (it is the profile owner), 'unknown' (no
        candidate), 'ambiguous' (more than one). No fuzzy fallback.
        """
        if not self._built:
            self.build()
        if not mention:
            return None, "unknown", 0.0
        if mention in self._owner_toks or mention == self.owner_name:
            return None, "owner", 0.0
        if mention in self.people:
            return self.people[mention], "exact", CONF["exact"]
        cands = self._alias_index.get(mention)
        if cands and len(cands) == 1:
            return self.people[next(iter(cands))], "alias", CONF["alias"]
        if cands and len(cands) > 1:
            return None, "ambiguous", 0.0
        loose = {c for c in self.people if mention in camel_parts(c)}
        if len(loose) == 1:
            return self.people[loose.pop()], "unique", CONF["unique"]
        if len(loose) > 1:
            return None, "ambiguous", 0.0
        return None, "unknown", 0.0

    def mentions_in(self, text):
        """Every capitalised name-shaped token in `text`, in order, with its
        span. Sentence-initial tokens are included -- the caller decides."""
        return [(m.group(0), m.start(), m.end())
                for m in re.finditer(_NAME, text or "")]


def _singular(rel):
    if rel.endswith("ies"):
        return rel[:-3] + "y"
    if rel.endswith("es") and rel[:-2] in RELATION_NOUNS:
        return rel[:-2]
    if rel.endswith("s") and rel[:-1] in RELATION_NOUNS:
        return rel[:-1]
    return rel


def attach_relations(text, registry, owner_name=None, min_confidence=1.0,
                     _log=None):
    """Rewrite bare person mentions to carry their relation to the owner.

        "Susan's support inspires Martin Mark"
     -> "Martin Mark's friend Susan's support inspires Martin Mark"

    `min_confidence` is the RELATION confidence floor (share of support
    behind the winning relation), NOT the link confidence. Default 1.0 =
    attach only where the store is unanimous about the relation; a
    contested person is left bare rather than rendered under a relation
    the receipts disagree about.

    Only the FIRST mention of each person is rewritten, and only when the
    relation is not already present in the text. Returns the text
    unchanged when nothing qualifies.
    """
    owner = owner_name or registry.owner_name
    if not text or not owner:
        return text
    seen = set()
    out = []
    last = 0
    for mention, start, end in registry.mentions_in(text):
        person, strategy, conf = registry.resolve(mention)
        if _log is not None:
            _log.append({"mention": mention, "strategy": strategy,
                         "span_start": start, "span_end": end,
                         "link_confidence": conf,
                         "person": person.canonical if person else None,
                         "relation": person.relation if person else None,
                         "relation_confidence": (person.relation_confidence
                                                 if person else 0.0),
                         "contested": person.contested if person else False})
        if person is None or person.canonical in seen:
            continue
        rel = person.relation
        if not rel or person.relation_confidence < min_confidence:
            continue
        # already carries a relation right before the name -> leave alone
        prefix = text[max(0, start - 40):start].lower()
        if rel in prefix or f"{owner.lower()}'s" in prefix[-len(owner) - 3:]:
            seen.add(person.canonical)
            continue
        seen.add(person.canonical)
        out.append(text[last:start])
        out.append(f"{owner}'s {rel} {mention}")
        last = end
    out.append(text[last:])
    return "".join(out)


def build_registry(records, owner_name):
    """Convenience: harvest + build in one call."""
    return Registry(owner_name=owner_name).add_records(records).build()
