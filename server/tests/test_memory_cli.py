"""sourcedrecall-memory ingest / recall / context: the memory without MCP."""
import io
import json
import sys

import pytest

pytest.importorskip("stanza")


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("RG_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("RG_NLI", "0")
    monkeypatch.setenv("SOURCEDRECALL_OWNER", "Dana Cole")
    import sourcedrecall.profile_memory as pm
    pm._state.update({"mem": None, "audit_pass": None, "needs_reload": False,
                      "uncached_turns": None, "transcripts": None})
    pm._ingest_state.update({"extractor": None, "owner": None})
    from sourcedrecall import memory_cli
    yield memory_cli


def test_ingest_from_stdin_then_recall_and_context(cli, monkeypatch, capsys):
    lines = "\n".join(json.dumps(m) for m in [
        {"role": "user", "content": "I moved to Brunswick last week."},
        {"role": "assistant", "content": "Congratulations!"}])
    monkeypatch.setattr(sys, "stdin", io.StringIO(lines))
    assert cli.main(["ingest", "--id", "c1", "--date", "2026-03-02"]) == 0
    assert "stored" in capsys.readouterr().out
    cli.main(["recall", "Where", "do", "I", "live?"])
    assert "Brunswick" in capsys.readouterr().out
    cli.main(["context"])
    out = capsys.readouterr().out
    assert out.startswith("[MEMORY") and "Brunswick" in out


def test_a_json_array_and_content_parts_are_read(cli, tmp_path, capsys):
    f = tmp_path / "chat.json"
    f.write_text(json.dumps([{"role": "user", "content": [
        {"type": "text", "text": "I'm allergic to penicillin."}]}]))
    assert cli.main(["ingest", str(f)]) == 0
    cli.main(["recall", "Am I allergic to anything?", "--json"])
    assert "penicillin" in capsys.readouterr().out
