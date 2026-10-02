"""p2 FULL-STREAM corroboration test + CHECKABLE report.

Entry 65's sample under-measured CORROBORATION. This runs EVERY prose turn
(realtime replay) so a stable fact climbs to x10+ while a transient stays x1.
Corroboration IS the noise filter (assert only >= N mentions); mentions merge via
full stream + canon_attr + value clustering.

CHECKABILITY (how the user verifies it is really them): writes an UNREDACTED report
with RECEIPTS -- for every corroborated fact, the dates + conversation titles it was
pulled from -- to <quarantine>/profile_report.txt, which the user opens locally. So
each fact is traceable back to the conversations that support it. STDOUT stays
REDACTED (safe for the shared session); the local report file is the ground-truth
check.

Cached/resumable (cache in the quarantine, never git). PRIVACY: quarantined input,
redacted stdout, unredacted report stays local. Generic code only.
Usage: run_profile_full.py <conversations.json> [min_mentions=2]
"""

import json
import os
import re
import sys
import time
import hashlib
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import redact as RC
from redact import redact
from prose import _is_prose
from llm_profile import extract_profile_facts, canon_attr

_STOP = {"the", "a", "an", "my", "of", "and", "in", "at", "to", "for", "with",
         "is", "was", "i", "am", "me", "current", "currently", "new", "some"}

# --- readout hygiene (entry 68), from the registrant's own error taxonomy.
# 1. technical VALUES: file paths, drive letters, host paths, filenames -- never a
#    personal-profile fact value.
_TECH_VALUE = re.compile(
    r"[\\/]"                                     # any slash -> a path
    r"|^[a-z]:$"                                 # bare drive letter  c:  d:
    r"|~/|\.localhost|wsl\."                     # home path / localhost / wsl host
    r"|\.ts\.net"                                # tailscale machine address
    r"|\.(py|csv|jsonl?|txt|md|ipynb|sh|ya?ml|ini|cfg|gguf|safetensors|log|pth?)$",
    re.I)                                        # a filename
# model artifacts (gemma-3-12b-it, mistral-7b-instruct-v0.3, qwen3:14b) are
# tech residue, not stable personal facts (entry 81: recurring transients
# corroborate because the owner talks shop daily; value-typing must catch them)
_MODEL_NAME = re.compile(r"(^|[^a-z0-9])\d+(\.\d+)?b(\b|[-_:])"
                         r"|[-_](it|instruct|chat|base)\b|:\d+b\b", re.I)
# a bare artifact word is not a fact value, whatever the attribute
_VACUOUS_VALUE = {"venv", "file", "files", "folder", "directory", "repo",
                  "script", "dataset", "checkpoint", "notebook", "terminal",
                  "shell", "model", "code"}
# an OS is not a place
_OS_WORDS = {"ubuntu", "linux", "windows", "macos", "debian", "arch", "wsl",
             "wsl2"}
# transient/technical ATTRIBUTE patterns (current_venv, *_directory, ...).
# Every alternative is bounded by (?<![a-z])...(?![a-z]) rather than \b:
# predicate keys are underscore_joined ("optimism_about_exploring_new_
# career_paths"), and \b does NOT fire at "_" (it is a \w character, same
# class as a letter) -- so the old bare "path" alternative matched inside
# "career_paths" too, silently dropping 45 real rgx facts on user 0. The
# letter-class lookaround treats "_" (and string start/end) as a boundary
# but a following/preceding LETTER (e.g. the "s" in "paths") as not, so
# "model_path" still matches while "career_paths" no longer does.
_EXCLUDE_ATTR_RX = re.compile(
    r"(?<![a-z])(?:venv|directory|folder|path|filename)(?![a-z])"
    r"|_file\b|\bfile_", re.I)
# 2. machine/device tokens are not a LOCATION (studio = the ssh box, pc, nas).
_DEVICE_WORDS = {"pc", "nas", "studio", "server", "host", "localhost", "laptop",
                 "desktop", "machine", "vm", "arc", "node", "box"}
# 3. transient / technical ATTRIBUTES -- not stable profile facts (they recur, so
#    corroboration alone does not drop them).
# ONLY genuinely transient/technical attributes. NOT roles: current_role/
# current_position hold REAL jobs (entry 69) and are canon'd to occupation, not
# excluded. Collapsing a multi-role person to one job destroys the profile.
_EXCLUDE_ATTR = {"current_task", "current_activity", "current_directory",
                 "file_modified", "work_directory", "virtual_environment",
                 "model_path", "model_used", "project_phase", "concern",
                 "current_value", "researcher_name", "research_field",
                 "current_issue"}
# a bare dwelling-type word is not a place (entry 77 taxonomy: "house")
_GENERIC_PLACE = {"house", "home", "apartment", "flat", "unit", "room"}
# an occupation value must NAME the occupation, not restate having one
_VACUOUS_OCC = {"day job", "job", "work", "full-time job", "full time job"}


# --- subject/slot hygiene (found by reading a store, not by scoring one) ---
#
# Two defects visible in user 10's shipped store, both of which a person would
# spot on sight and no metric we had could:
#
#   "Ai works as empathetic interaction to foster teamwork"
#   "Friends works as provide diverse perspectives and encouragement"
#   "Michelle Hernandez works as apple"          <- the EMPLOYER, as a job title
#
# Groups and abstractions are not people and must not carry personal
# attributes. This rejects only the crossing of the two -- a non-person
# subject holding a PERSON attribute -- rather than everything about them,
# because "team is instrumental in overcoming challenges" is merely useless
# whereas "Ai's age is 45" is corrupt.
_NON_PERSON_SUBJECT = {"ai", "team", "friends", "colleagues", "family",
                       "people", "everyone", "others", "society", "work",
                       "company", "group", "community", "world", "technology",
                       "them", "us", "we", "they"}
_PERSON_ATTR = {"occupation", "job_title", "employer", "workplace", "age",
                "gender", "birth_date", "income", "monthly_income", "salary",
                "savings", "marital_status", "name", "location", "residence"}

# An organisation is not a job title. Conservative on purpose: the test fires
# only on an unambiguous corporate suffix or a handful of names no one uses as
# a role, and the outcome is a RE-SLOT (occupation -> employer), never a
# rejection. A wrong re-slot moves a true fact to a neighbouring field; a
# wrong rejection destroys it.
_ORG_SUFFIX = re.compile(
    r"\b(?:inc|llc|ltd|corp|corporation|co|plc|gmbh|labs?|technologies|"
    r"systems|solutions|group|holdings|ventures|partners|associates)\.?$", re.I)
_ORG_NAMES = {"apple", "google", "microsoft", "amazon", "meta", "facebook",
              "netflix", "tesla", "nvidia", "ibm", "oracle", "intel", "adobe",
              "salesforce", "uber", "airbnb", "spotify", "twitter", "openai",
              "anthropic", "deepmind"}


def reject_subject_attr(subject, attr):
    """True if a non-person subject is being given a personal attribute."""
    return (str(subject or "").strip().lower() in _NON_PERSON_SUBJECT
            and attr in _PERSON_ATTR)


# A qualifier does not stop a company being a company: "google (part-time)"
# reached the store as an OCCUPATION because the test matched bare names only.
_QUALIFIER = re.compile(r"\s*[\(\[].*?[\)\]]\s*$|\s*[-,;]\s.*$")


def is_organization(v):
    v = str(v or "").strip().lower()
    if not v:
        return False
    core = _QUALIFIER.sub("", v).strip()
    for cand in (v, core):
        if cand and (cand in _ORG_NAMES or _ORG_SUFFIX.search(cand)):
            return True
    return False


def reslot_attr(attr, v):
    """Deterministic slot correction. Returns the attribute this (attr, value)
    actually belongs in -- unchanged unless we are confident."""
    if attr in ("occupation", "job_title") and is_organization(v):
        return "employer"
    return attr


def _reject_value(attr, v):
    """True if this (attr, value) is a technical/path/device artefact, not a fact."""
    v = v.strip().lower()
    if not v or _TECH_VALUE.search(v) or v in _VACUOUS_VALUE:
        return True
    if _MODEL_NAME.search(v):
        return True
    if attr == "location":
        if v in _GENERIC_PLACE or v in _OS_WORDS:
            return True
        # any device-word token poisons a location ("studio jpwork")
        if any(t in _DEVICE_WORDS for t in v.split()):
            return True
    if attr == "occupation" and v in _VACUOUS_OCC:
        return True
    return False


def load_stream_and_titles(path):
    """(stream, uuid->title). One load of conversations.json; stream is human
    turns time-ordered as (step, uuid, date, text)."""
    conv = json.load(open(path))
    conv.sort(key=lambda c: c.get("created_at", ""))
    titles, stream = {}, []
    for i, c in enumerate(conv):
        titles[c.get("uuid", "")] = c.get("name", "") or "(untitled)"
        for m in (c.get("chat_messages") or []):
            if (m.get("sender") or "").lower() != "human":
                continue
            txt = m.get("text") or m.get("content") or ""
            if isinstance(txt, list):
                txt = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x)
                               for x in txt)
            if txt.strip():
                stream.append((i, c.get("uuid", ""), c.get("created_at", "")[:10],
                               txt.strip()[:1800]))
    return stream, titles


# e273: markers that flip or cancel a value. Read off the RAW string, not the
# token set, because the stopword list removes exactly the words that carry
# polarity ("no", "not").
_NEG_MARKERS = (" not ", "n't", " no ", " never ", "no longer", "not any more",
                "not anymore", " former", " ex-", "used to", " stopped ",
                " quit ", " nor ")


def _polarity(val):
    """-> 1 for a plain value, 0 for one carrying a negation/cessation marker.
    Two values of different polarity are DIFFERENT facts and never merge."""
    v = f" {(val or '').lower().strip()} "
    return 0 if any(m in v for m in _NEG_MARKERS) else 1


def _cluster(entries, trace=False):
    """Merge one slot's values by content-token overlap; sum mentions and receipts.
    entries: {value: {"n": int, "recs": [(date, uuid)]}}. Returns list of dicts.

    trace=False (default, byte-identical to before this arg existed): returns
    just the cluster list, exactly as always.
    trace=True (opt-in, RG_DISPOSITION instrumentation only -- see
    halumem_run.ingest_user): ALSO returns {value: cluster_index}, i.e. which
    returned cluster each input value ended up placed in -- so a caller can
    tell a value that WON its cluster (value == clusters[i]["label"]) from
    one that was ABSORBED into an existing cluster started by a different
    value (the merge this docstring describes below). No default-path caller
    passes trace=True, so this is purely additive.

    Merge criterion (fixed, see notebook entry 95): overlap must be a MAJORITY
    of the SMALLER token set -- len(toks & cl["core"]) / min(len(toks),
    len(cl["core"])) >= 0.5 -- not "any shared token". ANY-shared-token was
    fine for short values ("melbourne" / "melbourne australia") but
    destructive for v5's long narrative values (up to ~15 words): two
    distinct facts sharing one generic tail token ("understanding", "focus")
    collided and the absorbed fact's specific wording was discarded (measured
    gold-answer loss). cl["core"] is the FIRST (highest-n) variant's token
    set, used ONLY for the ratio test -- NOT cl["toks"], which keeps
    accumulating the UNION of every merged variant for downstream query
    matching (wire nodes read cl["toks"]; unchanged). Using the union as the
    denominator-shrinking/overlap-inflating side would let clusters snowball:
    each merge grows cl["toks"], making the NEXT candidate's overlap ratio
    against it easier to clear, absorbing further unrelated values over
    several iterations even though none individually shares half its tokens
    with the cluster's ORIGINAL value. cl["core"] stays fixed at the first
    variant, so every candidate is judged against the same original meaning."""
    items = sorted(entries.items(), key=lambda kv: -kv[1]["n"])
    clusters = []
    vmap = {} if trace else None
    for val, d in items:
        toks = {t for t in re.findall(r"[a-z0-9]+", val.lower())
                if t not in _STOP and len(t) > 1}
        pol = _polarity(val)
        placed = False
        for ci, cl in enumerate(clusters):
            # e273: NEVER merge across polarity. "a vegetarian" and "no longer
            # a vegetarian" share every content token, so the overlap test
            # scores them 1.0 and merges them -- and the positive wins the
            # label because it has more mentions. The user said they had
            # STOPPED and the store kept the opposite.
            #
            # Ledger 5l ("token overlap cannot see a negation") recorded this
            # about INSTRUMENTS. Nobody checked the clusterer, which is the
            # same algorithm deciding what the store believes.
            if cl["pol"] != pol:
                continue
            smaller = min(len(toks), len(cl["core"])) or 1
            if len(toks & cl["core"]) / smaller >= 0.5:
                cl["n"] += d["n"]
                # hearsay tier (e246): mentions with evidential=="report" are
                # counted separately (n_hearsay) and never in "n" -- summed
                # across merges the same way "n" is, so a cluster's hearsay
                # count reflects every merged variant's hearsay mentions.
                cl["n_hearsay"] = cl.get("n_hearsay", 0) + d.get("n_hearsay", 0)
                cl["toks"] |= toks
                cl["recs"].extend(d["recs"])
                placed = True
                if trace:
                    vmap[val] = ci
                break
        if not placed:
            # "core" must be a SEPARATE set object from "toks" -- `cl["toks"]
            # |= x` mutates a set IN PLACE, so if core and toks aliased the
            # same object, the "fixed first-variant core" would silently
            # grow with every merge (the exact snowball this fix exists to
            # prevent). set(toks) copies.
            clusters.append({"label": val, "n": d["n"], "toks": set(toks),
                             "core": set(toks), "pol": pol,
                             "recs": list(d["recs"]),
                             # entry 244: keep the FIRST mention's "text"
                             # (the highest-n variant, since items are
                             # processed in that order) -- not overwritten
                             # by later merges, so it stays the winning
                             # label's own proposition text.
                             "text": d.get("text"),
                             "source": d.get("source"),
                             # entry 246: hearsay-mention count for this
                             # (first) variant; see the merge branch above.
                             "n_hearsay": d.get("n_hearsay", 0)})
            if trace:
                vmap[val] = len(clusters) - 1
    if trace:
        return clusters, vmap
    return clusters


def main():
    path = sys.argv[1]
    min_mentions = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    try:
        u = json.load(open(os.path.join(os.path.dirname(path), "users.json")))[0]
        for tok in re.findall(r"[A-Za-z]{3,}", u.get("full_name", "")):
            RC._EXTRA_REDACT.append(tok)
    except Exception:
        pass

    # v2/v3/v4/v5 extraction (RG_EXTRACT_V2/V3/V4/V5) use their OWN cache +
    # report: a prompt change invalidates a cache, and older artifacts stay
    # intact for rollback.
    _sfx = ("_v5" if os.environ.get("RG_EXTRACT_V5")
            else "_v4" if os.environ.get("RG_EXTRACT_V4")
            else "_v3" if os.environ.get("RG_EXTRACT_V3")
            else "_v2" if os.environ.get("RG_EXTRACT_V2") else "")
    cache_path = os.path.join(os.path.dirname(path), f"profile_cache{_sfx}.jsonl")
    print(f"extractor prompt: {_sfx.strip('_') or 'v1'}  (cache: {cache_path})")
    cache = {}
    if os.path.exists(cache_path):
        for line in open(cache_path):
            try:
                d = json.loads(line)
                cache[d["h"]] = d["f"]
            except Exception:
                pass
    cf = open(cache_path, "a")

    stream, titles = load_stream_and_titles(path)
    prose = [s for s in stream if _is_prose(s[3])]
    print(f"full stream: {len(prose)} prose turns (every turn -- realtime replay)\n")

    slots = defaultdict(lambda: defaultdict(lambda: {"n": 0, "recs": []}))
    lat = []
    for i, (step, uuid, date, text) in enumerate(prose):
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if h in cache:
            facts = cache[h]
        else:
            t0 = time.time()
            facts = extract_profile_facts(text)
            lat.append(time.time() - t0)
            cf.write(json.dumps({"h": h, "f": facts}) + "\n")
            cf.flush()
        for fct in facts:
            a = canon_attr(fct["attribute"])
            v = re.sub(r"\s+", " ", str(fct["value"]).strip().lower())
            if (not v or a in _EXCLUDE_ATTR or _EXCLUDE_ATTR_RX.search(a)
                    or _reject_value(a, v)):
                continue
            # v3 world facts: the subject namespaces the slot ("wife:occupation");
            # self-facts keep their plain key. Entity nodes emerge as namespaces.
            subj = fct.get("subject")
            key = f"{subj}:{a}" if subj else a
            slots[key][v]["n"] += 1
            slots[key][v]["recs"].append((date, uuid))
        if (i + 1) % 500 == 0:
            print(f"  ...{i+1}/{len(prose)} turns")

    if lat:
        lat.sort()
        print(f"\nlatency (fresh extractions): median {lat[len(lat)//2]*1000:.0f} ms, "
              f"p90 {lat[int(len(lat)*0.9)]*1000:.0f} ms, {len(lat)} calls")
    else:
        print("\n(all extractions were cache hits -- instant)")

    # corroborated facts, with receipts
    corr = []
    tail = 0
    for attr, entries in slots.items():
        for cl in _cluster(entries):
            if cl["n"] >= min_mentions:
                corr.append((cl["n"], attr, cl["label"], cl["recs"]))
            else:
                tail += 1
    corr.sort(reverse=True)

    # owner corrections apply HERE too (entry 81: the checkable report must
    # reflect them, not just the wire/recall path)
    corr_path = os.path.join(os.path.dirname(path), "corrections.jsonl")
    if os.path.exists(corr_path):
        from wire import correct_facts
        corrections = [json.loads(l) for l in open(corr_path) if l.strip()]
        corrected, _, clog = correct_facts(corr, [], corrections)
        if clog:
            from collections import Counter
            print("owner corrections applied:",
                  dict(Counter(a for a, _ in clog)))
        corr = [(n, a, l, r) for n, a, l, r, *_ in corrected]
        corr.sort(reverse=True)

    # redacted summary to stdout (safe for the shared session)
    print(f"\n=== CORROBORATED PROFILE (>= {min_mentions} mentions) ===")
    print(f"{len(corr)} corroborated facts; {tail} single-mention (x1) filtered\n")
    for n, attr, label, recs in corr[:60]:
        print(f"  [x{n:3d}] {redact(str(attr))[:20]:20s} : {redact(str(label))[:52]}")

    # UNREDACTED checkable report with receipts -> LOCAL file only
    report = os.path.join(os.path.dirname(path), f"profile_report{_sfx}.txt")
    with open(report, "w") as f:
        f.write(f"CHECKABLE PROFILE REPORT  ({len(corr)} corroborated facts, "
                f">= {min_mentions} mentions)\n")
        f.write("Section 1 is the DIGEST (one line per fact) -- skim this and "
                "note anything wrong.\nSection 2 has the receipts (dates + "
                "conversation titles) to verify against.\n")
        f.write("Corrections: add deny/confirm/retype lines to "
                "corrections.jsonl next to this file.\n\n")
        f.write("== 1. DIGEST ==\n")
        for n, attr, label, recs in corr:
            f.write(f"[x{n:3d}] {attr} : {label}\n")
        f.write("\n== 2. RECEIPTS ==\n\n")
        for n, attr, label, recs in corr:
            f.write(f"[x{n}] {attr} : {label}\n")
            seen = set()
            for date, uuid in sorted(recs, reverse=True):
                if uuid in seen:
                    continue
                seen.add(uuid)
                f.write(f"     {date}  {titles.get(uuid, '')[:70]}\n")
                if len(seen) >= 3:
                    extra = len(set(u for _, u in recs)) - len(seen)
                    if extra > 0:
                        f.write(f"     (+{extra} more conversations)\n")
                    break
            f.write("\n")
    print(f"\n>>> UNREDACTED checkable report (with receipts) written to:\n    {report}")
    print("    Open it locally to verify each fact against your own conversations.")


if __name__ == "__main__":
    main()
