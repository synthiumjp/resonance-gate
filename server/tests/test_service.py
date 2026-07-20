"""Per-tool unit tests + collision behaviour + an end-to-end scripted session
over MemoryService (the four MCP tools are thin wrappers over these)."""


def test_remember_stores_and_echoes(service):
    r = service.remember("Maria Garcia", "lives in", "Lisbon")
    assert r["stored"] is True and r["echo_ok"] is True
    assert r["record_id"].startswith("r")


def test_remember_rejects_bad_source(service):
    r = service.remember("Tom Baker", "works at", "Acme Labs", source="whoever")
    assert r["stored"] is False and "source" in r["error"]


def test_recall_hit(service):
    service.remember("Tom Baker", "works at", "Acme Labs", "tool-derived")
    out = service.recall("Tom Baker")
    assert out["resolved"] is True and out["conflict"] is False
    assert len(out["facts"]) == 1
    f = out["facts"][0]
    assert (f["subject"], f["relation"], f["object"]) == ("Tom Baker", "works at", "Acme Labs")
    assert f["source"] == "tool-derived"
    assert set(f["confidence"]) == {"b", "d", "u"}


def test_recall_miss_is_honest_empty(service):
    service.remember("Tom Baker", "works at", "Acme Labs")
    out = service.recall("Zebulon Qwerty Nobody")
    assert out["resolved"] is False and out["facts"] == [] and out["conflict"] is False


def test_near_synonym_collision_surfaced_not_resolved(service):
    service.remember("Maria Garcia", "lives in", "Lisbon")
    service.remember("Maria Garcia", "resides in", "Boston")
    out = service.recall("Maria Garcia")
    assert out["conflict"] is True
    objs = {f["object"] for f in out["facts"]}
    assert {"Lisbon", "Boston"} <= objs           # BOTH surfaced
    assert "resolution_hint" in out               # advisory only
    hint = out["resolution_hint"]
    assert set(hint) == {"by_recency", "by_resolution"}
    # the server did NOT pick — both records still present
    ids = {f["record_id"] for f in out["facts"]}
    assert hint["by_recency"] in ids and hint["by_resolution"] in ids


def test_distinct_attribute_is_not_a_conflict(service):
    service.remember("Maria Garcia", "lives in", "Lisbon")
    service.remember("Maria Garcia", "was born in", "Berlin")  # different attribute
    out = service.recall("Maria Garcia")
    assert out["conflict"] is False


def test_update_supersedes_and_resolves_conflict(service):
    service.remember("Maria Garcia", "lives in", "Lisbon")
    service.remember("Maria Garcia", "resides in", "Boston")
    up = service.update("Maria Garcia", "lives in", "Madrid")
    assert up["updated"] is True
    assert len(up["superseded"]) == 2            # both prior residence records
    out = service.recall("Maria Garcia")
    assert out["conflict"] is False
    assert {f["object"] for f in out["facts"]} == {"Madrid"}


def test_forget_variants(service):
    service.remember("Tom Baker", "works at", "Acme Labs")
    service.remember("Tom Baker", "lives in", "Berlin")
    # forget one relation-class
    f1 = service.forget("Tom Baker", "works at")
    assert len(f1["forgotten"]) == 1
    out = service.recall("Tom Baker")
    assert {f["object"] for f in out["facts"]} == {"Berlin"}
    # forget the rest (subject only)
    f2 = service.forget("Tom Baker")
    assert len(f2["forgotten"]) == 1
    assert service.recall("Tom Baker")["resolved"] is False


def test_end_to_end_scripted_session(service):
    assert service.remember("Maria Garcia", "lives in", "Lisbon")["stored"]
    assert service.remember("Maria Garcia", "resides in", "Boston")["stored"]
    assert service.remember("Tom Baker", "works at", "Acme Labs")["stored"]
    assert service.recall("Tom Baker")["facts"][0]["object"] == "Acme Labs"
    assert service.recall("Nobody At All")["resolved"] is False
    coll = service.recall("Maria Garcia")
    assert coll["conflict"] and {f["object"] for f in coll["facts"]} >= {"Lisbon", "Boston"}
    up = service.update("Maria Garcia", "lives in", "Madrid")
    assert up["superseded"] and not service.recall("Maria Garcia")["conflict"]
    service.forget("Maria Garcia")
    assert service.recall("Maria Garcia")["resolved"] is False
