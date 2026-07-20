"""Persistence / restart recovery: write, drop the instance (simulated kill),
rebuild from the same state dir (restart), recall must recover everything."""


def test_restart_recovers_full_state(tmp_path):
    from rg_memory.service import MemoryService
    d = str(tmp_path / "state")

    s1 = MemoryService(d)
    s1.remember("Maria Garcia", "lives in", "Lisbon")
    s1.remember("Maria Garcia", "resides in", "Boston")   # a live conflict
    s1.remember("Tom Baker", "works at", "Acme Labs", "tool-derived")
    before = s1.recall("Maria Garcia")
    del s1                                                  # "kill" the server

    s2 = MemoryService(d)                                   # "restart"
    after = s2.recall("Maria Garcia")
    assert after["resolved"] is True
    assert after["conflict"] is True                        # conflict survives restart
    assert {f["object"] for f in after["facts"]} >= {"Lisbon", "Boston"}
    assert {f["object"] for f in before["facts"]} == {f["object"] for f in after["facts"]}

    tom = s2.recall("Tom Baker")
    assert tom["facts"][0]["object"] == "Acme Labs"
    assert tom["facts"][0]["source"] == "tool-derived"     # provenance survives


def test_supersede_survives_restart(tmp_path):
    from rg_memory.service import MemoryService
    d = str(tmp_path / "state")
    s1 = MemoryService(d)
    s1.remember("Maria Garcia", "lives in", "Lisbon")
    s1.update("Maria Garcia", "lives in", "Madrid")
    del s1
    s2 = MemoryService(d)
    out = s2.recall("Maria Garcia")
    assert {f["object"] for f in out["facts"]} == {"Madrid"}   # tombstone persisted
