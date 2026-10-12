"""Review 2026-10-12 (3.5): on Windows the store lock gave up after about
10 s and the store was then written unlocked. It now waits, as flock does.
Run here with a stand-in msvcrt that reports the lock busy twice."""
import errno
import sys
import types


def test_the_windows_lock_waits_while_another_process_holds_it(tmp_path, monkeypatch):
    calls = []

    def locking(fd, mode, n):
        calls.append(mode)
        if mode == "NB" and calls.count("NB") <= 2:
            raise OSError(errno.EACCES, "busy")

    fake = types.SimpleNamespace(LK_NBLCK="NB", LK_LOCK="L", LK_UNLCK="U", locking=locking)
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    monkeypatch.setattr("time.sleep", lambda s: None)
    from sourcedrecall.profile_memory import _win_lock
    with open(tmp_path / ".lock", "a+") as fh:
        _win_lock(fh)
    assert calls == ["NB", "NB", "NB"]


def test_another_error_is_not_taken_for_a_busy_lock(tmp_path, monkeypatch):
    import pytest

    def locking(fd, mode, n):
        raise OSError(errno.EBADF, "bad file")

    monkeypatch.setitem(sys.modules, "msvcrt", types.SimpleNamespace(LK_NBLCK=2, locking=locking))
    from sourcedrecall.profile_memory import _win_lock
    with open(tmp_path / ".lock", "a+") as fh, pytest.raises(OSError):
        _win_lock(fh)
