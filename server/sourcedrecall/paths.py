"""Where sourcedrecall keeps its data. Shared by the MCP server and the
Claude Code hooks, so a hook never has to import the server (and its `mcp`
dependency) just to find the memory. Read from the environment at CALL time,
not import time."""
import os

# 2026-10-09 (security review): only the MCP server set offline mode; the
# hook worker and the command line did not, so a missing model could be
# fetched from the network. Every entry point imports this module.
# sourcedrecall-setup, the one step allowed to download, sets
# SOURCEDRECALL_SETUP=1 first.
if os.environ.get("SOURCEDRECALL_SETUP") != "1":
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def private_dir(d):
    """Create `d` readable by this user only, and make an existing one so
    (2026-10-09, security review: the memory was 0755 with 0644 files, so
    anyone on the machine could read every message). New files are created
    private too (umask)."""
    os.makedirs(d, mode=0o700, exist_ok=True)
    try:
        if os.stat(d).st_mode & 0o077:
            os.chmod(d, 0o700)
    except OSError:
        pass
    try:
        os.umask(os.umask(0o077) | 0o077)
    except Exception:
        pass
    return d


def state_dir():
    return os.environ.get("SOURCEDRECALL_STATE",
                          os.path.expanduser("~/.sourcedrecall"))


def default_memory_dir():
    """2026-10-02, from the new-user install test: RG_MEMORY_DIR was required
    and documented only in a docstring, so the first profile_* call failed.
    The LIBRARY still refuses to guess (profile_memory._data_dir raises, so a
    forgetful test can never touch a real user's data); the server and the
    hooks -- what a person actually runs -- default it beside
    SOURCEDRECALL_STATE."""
    if not os.environ.get("RG_MEMORY_DIR"):
        d = os.path.join(state_dir(), "conversations")
        private_dir(state_dir())
        private_dir(d)
        os.environ["RG_MEMORY_DIR"] = d
    else:
        private_dir(os.environ["RG_MEMORY_DIR"])
    return os.environ["RG_MEMORY_DIR"]


def project_scope(path):
    """The project a directory belongs to: its git root if it is inside a
    repository, else the directory itself (2026-10-02, scoping). None for
    no path. Subdirectories of one repository are one project."""
    if not path:
        return None
    p = os.path.realpath(os.path.expanduser(str(path)))
    cur = p
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return p
        cur = parent


def current_scope(explicit=None):
    """The scope to read in: an explicit one, else SOURCEDRECALL_SCOPE, else
    the project Claude Code is running in (CLAUDE_PROJECT_DIR, which it sets
    for MCP servers and hooks). None means no scoping: everything is
    visible. SOURCEDRECALL_SCOPING=0 turns scoping off."""
    if os.environ.get("SOURCEDRECALL_SCOPING") == "0":
        return None
    raw = (explicit or os.environ.get("SOURCEDRECALL_SCOPE")
           or os.environ.get("CLAUDE_PROJECT_DIR"))
    return project_scope(raw) if raw else None


def parser_models_dir():
    """Where setup installs the PyTorch-free parser's models (2026-10-05)."""
    return os.environ.get("SOURCEDRECALL_PARSER_MODELS",
                          os.path.join(state_dir(), "parser-models"))


def notes_models_dir():
    """Where `sourcedrecall-setup --notes` installs the in-process notes
    model (2026-10-06). Installing it is the opt-in."""
    return os.environ.get("SOURCEDRECALL_NOTES_MODELS",
                          os.path.join(state_dir(), "notes-model"))


def use_installed_parser():
    """Point rgx at the installed stanza_ort models, if there are any (rgx
    falls back to Stanza on PyTorch otherwise)."""
    d = parser_models_dir()
    if (not os.environ.get("RGX_PARSER_MODELS")
            and os.path.exists(os.path.join(d, "config.json"))):
        os.environ["RGX_PARSER_MODELS"] = d
