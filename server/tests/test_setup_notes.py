"""sourcedrecall-setup --notes [small|standard] (2026-10-07)."""
import io
import os
import tarfile

import pytest

from sourcedrecall import setup_models as S


def test_both_notes_models_are_listed_with_a_checksum():
    assert set(S.NOTES_MODELS) == {"small", "standard"}
    for url, sha, _size in S.NOTES_MODELS.values():
        assert url.startswith("https://huggingface.co/synthiumjp/sourcedrecall-notes-en/")
        assert len(sha) == 64


def test_an_unknown_notes_model_is_refused(capsys):
    assert S.install_notes("huge") == 1
    assert "small or standard" in capsys.readouterr().out


def test_a_notes_archive_is_checked_and_installed(tmp_path, monkeypatch):
    import importlib.util
    if not importlib.util.find_spec("onnxruntime_genai"):
        pytest.skip("onnxruntime-genai not installed")
    src = tmp_path / "m"
    src.mkdir()
    (src / "genai_config.json").write_text("{}")
    arc = tmp_path / "m.tar.gz"
    with tarfile.open(arc, "w:gz") as t:
        t.add(src, arcname="sourcedrecall-notes-en-test")
    dest = tmp_path / "installed"
    monkeypatch.setenv("SOURCEDRECALL_NOTES_MODELS", str(dest))
    monkeypatch.setenv("SOURCEDRECALL_NOTES_ARCHIVE", str(arc))
    monkeypatch.setenv("SOURCEDRECALL_NOTES_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="sha256"):
        S.install_notes("small")
    monkeypatch.delenv("SOURCEDRECALL_NOTES_SHA256")
    assert S.install_notes("standard") == 0
    assert (dest / "genai_config.json").exists()
