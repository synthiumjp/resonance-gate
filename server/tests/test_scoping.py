"""Scoping (2026-10-02): the most common complaint about AI memory is one
context leaking into another. Facts about the user show everywhere; facts
about the world show only in the project they were said in."""
import os

import pytest

pytest.importorskip("stanza", reason="ingest needs the rgx parser (stanza)")

U = lambda c: {"role": "user", "content": c}


@pytest.fixture
def projects(tmp_path, monkeypatch):
    a = tmp_path / "billing"
    (a / ".git").mkdir(parents=True)
    (a / "src" / "deep").mkdir(parents=True)
    b = tmp_path / "shop"
    b.mkdir()
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path / "mem"))
    monkeypatch.setenv("RG_NLI", "0")
    for k in ("CLAUDE_PROJECT_DIR", "SOURCEDRECALL_SCOPE", "SOURCEDRECALL_SCOPING",
              "SOURCEDRECALL_OWNER"):
        monkeypatch.delenv(k, raising=False)
    import sourcedrecall.profile_memory as pm

    def reset():
        pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                          "uncached_turns": None, "transcripts": None})
        pm._ingest_state.update({"extractor": None, "owner": None})
    reset()
    pm.profile_ingest([U("I'm allergic to penicillin."),
                       U("I work on the billing service. The billing service is written in Go.")],
                      conversation_id="a", owner_name="Dana Cole",
                      scope=str(a / "src" / "deep"))
    pm.profile_ingest([U("I maintain the checkout service. The checkout service is written in Rust.")],
                      conversation_id="b", owner_name="Dana Cole", scope=str(b))
    pm.profile_ingest([U("I use the office coffee machine every day. The office coffee machine is broken.")],
                      conversation_id="c", owner_name="Dana Cole")
    yield pm, str(a), str(b)
    reset()


def _texts(out):
    return " | ".join(f.get("text") or "" for f in (out.get("ranked") or []))


def test_a_subdirectory_of_a_repository_is_the_same_project(projects):
    from sourcedrecall.paths import project_scope
    pm, a, b = projects
    assert project_scope(os.path.join(a, "src", "deep")) == os.path.realpath(a)
    assert project_scope(b) == os.path.realpath(b)


def test_a_projects_facts_stay_in_that_project(projects):
    pm, a, b = projects
    q = "What is the billing service written in?"
    assert "Go" in _texts(pm.profile_recall(q, scope=a))
    other = pm.profile_recall(q, scope=b)
    assert "billing" not in _texts(other)


def test_facts_about_the_user_are_visible_everywhere(projects):
    pm, a, b = projects
    for sc in (a, b):
        assert "penicillin" in _texts(pm.profile_recall("Am I allergic to anything?", scope=sc))


def test_facts_from_no_project_are_visible_everywhere(projects):
    pm, a, b = projects
    assert "coffee machine" in pm.profile_context(None, scope=b)["block"]


def test_the_summary_in_one_project_leaves_out_the_others(projects):
    pm, a, b = projects
    block = pm.profile_context(None, scope=b)["block"]
    assert "checkout service" in block
    # neither the billing service's facts nor the user's WORK on it follow
    # them into another project; their allergy does
    assert "billing service" not in block
    assert "penicillin" in block


def test_with_no_scope_everything_is_visible(projects):
    pm, a, b = projects
    block = pm.profile_context(None)["block"]
    assert "billing service" in block and "checkout service" in block


def test_scoping_can_be_switched_off(projects, monkeypatch):
    pm, a, b = projects
    monkeypatch.setenv("SOURCEDRECALL_SCOPING", "0")
    assert "billing service" in pm.profile_context(None, scope=b)["block"]


def test_claude_code_s_project_dir_is_the_default_scope(projects, monkeypatch):
    pm, a, b = projects
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", b)
    assert "billing service" not in pm.profile_context(None)["block"]


def test_the_memory_file_groups_world_facts_by_project(projects):
    pm, a, b = projects
    md = open(pm.export_markdown(), encoding="utf-8").read()
    assert f"## Project: billing ({os.path.realpath(a)})" in md
    assert f"## Project: shop ({os.path.realpath(b)})" in md
    section = md.split("## Project: billing")[1].split("##")[0]
    assert "billing service" in section and "checkout" not in section
