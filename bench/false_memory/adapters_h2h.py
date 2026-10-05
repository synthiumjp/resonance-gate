"""Head-to-head adapters (2026-10-05): two memory tools that also store
without a language model, run the way their Claude Code integrations store
a session. Same interface as adapters.py; both need FM_H2H (default
~/jpwork/h2h) holding the downloaded tools, and a scratch dir under it.

"""
import json
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timedelta

H2H = os.path.abspath(os.path.expanduser(os.environ.get("FM_H2H", "~/jpwork/h2h")))
BIN = os.path.join(H2H, "aim", "ai-memory")
MODEL_CACHE = os.path.join(H2H, "models-cache", "all-MiniLM-L6-v2")
TOP_K = 5
PAGE_CHARS = 1500
# AIM_FULL_OBS=1: for session-page hits, read the session's raw observations
# (full message text) instead of the page, whose message lines are cut at ~80 chars.
FULL_OBS = os.environ.get("AIM_FULL_OBS") == "1"


def _free_port(start=49474):
    for p in range(start, start + 200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


class AiMemoryAdapter:
    """ai-memory 2.5.2 (akitaonrails/ai-memory), no LLM provider; its local
    MiniLM embedder is on. Each conversation is written as a Claude Code
    transcript with the conversation's date and replayed with its own
    `ai-memory backfill --session <sid>` (session start, prompts, replies,
    session end through /hook/batch); the server writes a rule-based session
    page. Live hooks stamp the current time, so backfill is the path that
    keeps the dates. A question goes to its MCP tool memory_query (top 5),
    then memory_read_page of each hit, cut at 1,500 characters. Its session
    pages cut each message at about 80 characters; AIM_FULL_OBS=1 returns the
    session's full messages instead. A conversation's scope is its project."""
    name = "ai-memory"

    def __init__(self, workdir):
        self.workdir = os.path.abspath(workdir)
        assert self.workdir.startswith(H2H + os.sep), "workdir must be under ~/jpwork/h2h"
        self.home = os.path.join(self.workdir, "home")
        self.data = os.path.join(self.workdir, "data")
        self.projroot = os.path.join(self.workdir, "proj")
        for d in (self.home, self.data, self.projroot):
            os.makedirs(d, exist_ok=True)
        # Pre-seed the local embedding model (otherwise it is downloaded on
        # first start and hybrid search only turns on after a restart).
        dst = os.path.join(self.data, "models", "all-MiniLM-L6-v2")
        if os.path.isdir(MODEL_CACHE) and not os.path.isdir(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(MODEL_CACHE, dst)
        self.port = _free_port()
        self.url = "http://127.0.0.1:%d" % self.port
        self.env = dict(os.environ, HOME=self.home, AI_MEMORY_SERVER_URL=self.url,
                        AI_MEMORY_BACKFILL_ON_START="false")
        for k in ("AI_MEMORY_LLM_PROVIDER", "AI_MEMORY_LLM_MODEL"):
            self.env.pop(k, None)
        self.log = open(os.path.join(self.workdir, "serve.log"), "ab")
        self._n = 0
        self.projects = []
        self.proc = subprocess.Popen(
            [BIN, "serve", "--data-dir", self.data, "--transport", "http",
             "--bind", "127.0.0.1:%d" % self.port],
            env=self.env, stdout=self.log, stderr=self.log, start_new_session=True)
        for _ in range(100):
            try:
                self._mcp("tools/list", {})
                break
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("ai-memory serve exited")
                time.sleep(0.3)
        else:
            self.close()
            raise RuntimeError("ai-memory serve did not come up")

    # ---- MCP over HTTP (stateless JSON) ----
    def _mcp(self, method, params):
        self._n += 1
        b = {"jsonrpc": "2.0", "id": self._n, "method": method, "params": params}
        r = urllib.request.Request(self.url + "/mcp", data=json.dumps(b).encode(), headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"})
        return json.loads(urllib.request.urlopen(r, timeout=120).read())

    def _tool(self, name, args):
        res = self._mcp("tools/call", {"name": name, "arguments": args})
        if "error" in res:
            raise RuntimeError(res["error"])
        txt = res["result"]["content"][0]["text"]
        if res["result"].get("isError"):
            raise RuntimeError(txt)
        try:
            return json.loads(txt)
        except ValueError:
            return txt

    # ---- ingest ----
    @staticmethod
    def _proj_name(scope):
        return re.sub(r"[^a-z0-9._-]+", "-", (scope or "main").lower()).strip("-") or "main"

    def ingest(self, scenario):
        t0 = time.time()
        n = 0
        for conv in scenario["conversations"]:
            proj = self._proj_name(conv.get("scope"))
            cwd = os.path.join(self.projroot, proj)
            os.makedirs(cwd, exist_ok=True)
            if proj not in self.projects:
                self.projects.append(proj)
            sid = str(uuid.uuid4())
            tdir = os.path.join(self.home, ".claude", "projects", re.sub(r"[/.]", "-", cwd))
            os.makedirs(tdir, exist_ok=True)
            ts = datetime.strptime(conv["date"], "%Y-%m-%d") + timedelta(hours=9)
            lines = []
            for t in conv["turns"]:
                stamp = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                ts += timedelta(seconds=30)
                if t["role"] == "user":
                    msg = {"role": "user", "content": t["content"]}
                else:
                    msg = {"role": "assistant",
                           "content": [{"type": "text", "text": t["content"]}]}
                lines.append(json.dumps({"type": t["role"], "sessionId": sid, "cwd": cwd,
                                         "timestamp": stamp, "message": msg}))
                n += 1
            with open(os.path.join(tdir, sid + ".jsonl"), "w") as f:
                f.write("\n".join(lines) + "\n")
            r = subprocess.run([BIN, "backfill", "--data-dir", self.data, "--session", sid,
                                "--force", "--quiet"], cwd=cwd, env=self.env,
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise RuntimeError("backfill failed: " + (r.stderr or r.stdout)[-600:])
        time.sleep(0.5)   # let the server index the last pages / embeddings
        return {"messages": n, "model_calls": 0, "seconds": time.time() - t0}

    # ---- retrieval ----
    def query(self, q, scope=None):
        args = {"query": q, "limit": TOP_K}
        single = None
        if scope:
            single = self._proj_name(scope)
        elif len(self.projects) <= 1:
            single = (self.projects or ["main"])[0]
        if single:
            args.update(workspace="default", project=single)
        else:
            args["scopes"] = [{"workspace": "default", "project": p} for p in self.projects]
        res = self._tool("memory_query", args)
        hits = res.get("hits", []) if isinstance(res, dict) else []
        lines = []
        for h in hits[:TOP_K]:
            ra = {"path": h["path"]}
            proj = h.get("project") or single
            if proj:
                ra.update(workspace=h.get("workspace") or "default", project=proj)
            body = None
            m = re.match(r"sessions/(.+)\.md$", h["path"])
            if FULL_OBS and m and proj:
                # memory_read_session_observations: untruncated prompts/replies
                try:
                    ob = self._tool("memory_read_session_observations", {
                        "session_id": m.group(1), "workspace": "default", "project": proj})
                    rows = [o for o in ob["observations"] if o["kind"] in ("user-prompt", "other")]
                    body = "\n".join("[%s] %s: %s" % (
                        o["created_at"][:10], "user" if o["kind"] == "user-prompt" else "assistant",
                        o["body"]) for o in rows)
                except Exception:
                    body = None
            if body is None:
                try:
                    pg = self._tool("memory_read_page", ra)
                    body = pg.get("body", "") if isinstance(pg, dict) else str(pg)
                except Exception:
                    body = h.get("snippet", "")
            body = re.sub(r"\n{2,}", "\n", body).strip()
            lines.append("[%s] %s" % (h["path"], body[:PAGE_CHARS]))
        return {"lines": lines, "views": {}, "block": "\n".join(lines)}

    def close(self):
        p = getattr(self, "proc", None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(15)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        try:
            self.log.close()
        except Exception:
            pass


# --------------------------------------------------------------- agentmemory
AM_DIR = os.path.join(H2H, "am")          # npm install @agentmemory/agentmemory@0.9.29
AM_HOME = os.path.join(H2H, "amhome")     # .agentmemory/.env: EMBEDDING_PROVIDER=local
NODE = os.path.join(H2H, "node-v22.20.0-darwin-arm64", "bin", "node")
AM_URL = "http://127.0.0.1:3111"          # its --instance flag does not reach the engine
AM_PORTS = (3111, 3112, 3113, 49134)


def _wait_ports_free(ports, timeout=60):
    """The engine of the previous scenario can hold its ports for a while
    after it is stopped."""
    end = time.time() + timeout
    while time.time() < end:
        busy = False
        for p in ports:
            with socket.socket() as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", p))
                except OSError:
                    busy = True
                    break
        if not busy:
            return
        time.sleep(1)
    raise RuntimeError(f"ports {ports} still busy")


class AgentMemoryAdapter:
    """agentmemory 0.9.29 (rohitg00/agentmemory), no LLM key: BM25 plus its
    local MiniLM embeddings. Each conversation is written as a Claude Code
    transcript with the conversation's date and loaded with its own Claude
    Code importer (POST /agentmemory/replay/import-jsonl), which stores the
    user's prompts and the assistant's replies. A question goes to
    smart-search (what its memory_smart_search tool calls), top 5, and each
    hit is expanded to its full text, as an agent would. Its search has no
    project filter (the project only narrows its "lessons"), so scope is
    not used. A fresh server and data directory per scenario."""
    name = "agentmemory"

    def __init__(self, workdir):
        self.workdir = os.path.abspath(workdir)
        assert self.workdir.startswith(H2H + os.sep), "workdir must be under " + H2H
        self.data = os.path.join(self.workdir, "data")
        self.tx = os.path.join(self.workdir, "tx")
        for d in (self.data, self.tx):
            os.makedirs(d, exist_ok=True)
        self.env = dict(os.environ, HOME=AM_HOME,
                        PATH=os.path.dirname(NODE) + os.pathsep + os.environ.get("PATH", ""))
        for k in [k for k in self.env if k.startswith(("OPENAI", "ANTHROPIC", "GEMINI"))]:
            self.env.pop(k)
        self.log = open(os.path.join(self.workdir, "serve.log"), "ab")
        for attempt in range(2):
            _wait_ports_free(AM_PORTS)
            if self._start():
                return
            self.close()
        raise RuntimeError("agentmemory did not come up")

    def _start(self):
        self.proc = subprocess.Popen(
            [NODE, os.path.join(AM_DIR, "node_modules", "@agentmemory", "agentmemory",
                                "dist", "cli.mjs"),
             "--data-dir", self.data, "--tools", "core"],
            cwd=AM_DIR, env=self.env, stdin=subprocess.DEVNULL,
            stdout=self.log, stderr=self.log, start_new_session=True)
        for _ in range(120):
            try:
                urllib.request.urlopen(AM_URL + "/agentmemory/health", timeout=2)
                return True
            except OSError:
                if self.proc.poll() is not None:
                    return False
                time.sleep(0.5)
        return False

    @staticmethod
    def _post(path, body):
        r = urllib.request.Request(AM_URL + path, json.dumps(body).encode(),
                                   {"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(r, timeout=300).read())

    def ingest(self, scenario):
        t0 = time.time()
        n = 0
        for conv in scenario["conversations"]:
            sid = str(uuid.uuid4())
            cwd = os.path.join(self.workdir, "proj", conv.get("scope") or "main")
            ts = datetime.strptime(conv["date"], "%Y-%m-%d") + timedelta(hours=9)
            rows = []
            for t in conv["turns"]:
                stamp = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                ts += timedelta(seconds=30)
                msg = ({"role": "user", "content": t["content"]} if t["role"] == "user"
                       else {"role": "assistant",
                             "content": [{"type": "text", "text": t["content"]}]})
                rows.append(json.dumps({"type": t["role"], "sessionId": sid, "cwd": cwd,
                                        "timestamp": stamp, "uuid": str(uuid.uuid4()),
                                        "message": msg}))
                n += 1
            path = os.path.join(self.tx, sid + ".jsonl")
            with open(path, "w") as f:
                f.write("\n".join(rows) + "\n")
            r = self._post("/agentmemory/replay/import-jsonl", {"path": path})
            if not r.get("success"):
                raise RuntimeError("import failed: " + json.dumps(r)[:400])
        time.sleep(1.0)   # embeddings are written after the import returns
        return {"messages": n, "model_calls": 0, "seconds": time.time() - t0}

    def query(self, q, scope=None):
        res = self._post("/agentmemory/smart-search", {"query": q, "limit": TOP_K})
        hits = res.get("results", [])[:TOP_K]
        lines = []
        if hits:
            ex = self._post("/agentmemory/smart-search", {
                "query": q, "expandIds": [{"obsId": h["obsId"], "sessionId": h["sessionId"]}
                                          for h in hits]})
            full = {e["obsId"]: e["observation"] for e in ex.get("results", [])}
            for h in hits:
                o = full.get(h["obsId"]) or {}
                who = {"prompt_submit": "user", "stop": "assistant"}.get(
                    o.get("title") or h.get("title"), o.get("title") or "")
                text = o.get("narrative") or o.get("title") or ""
                lines.append("[%s] %s: %s" % ((h.get("timestamp") or "")[:10], who,
                                               " ".join(text.split())[:PAGE_CHARS]))
        for les in res.get("lessons") or []:
            t = les.get("content") or les.get("text") or les.get("title")
            if t:
                lines.append("(lesson) " + " ".join(str(t).split())[:PAGE_CHARS])
        return {"lines": lines, "views": {}, "block": "\n".join(lines)}

    def close(self):
        p = getattr(self, "proc", None)
        if p and p.poll() is None:
            import signal
            try:
                os.killpg(p.pid, signal.SIGTERM)
                p.wait(20)
            except Exception:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    pass
        # the engine it starts can outlive the CLI
        subprocess.run(["pkill", "-f", os.path.join(AM_HOME, ".agentmemory", "bin", "iii")],
                       capture_output=True)
        try:
            self.log.close()
        except Exception:
            pass
