"""Read-only local memory browser, served on 127.0.0.1.

  /          what the memory holds about you, grouped as in MEMORY.md, each
             fact with your exact words, the date and its id; a search box
             shows what recall returns for a question (2026-10-03)
  /triples   the explicit triples written with `remember`, with provenance,
             confidence (b,d,u) and any active conflict

Read-only by design: forget a fact with `sourcedrecall-memory forget <id>`
or by asking the assistant. This is a trust
feature: you can SEE exactly what the memory holds. Read-only by design —
writes go through the MCP tools so provenance stays clean.

No framework, no external assets, localhost bind only. Never a leak surface:
it only renders records already stored via the audited tools.
"""

import html
import http.server
import json
import threading

FOOTER = (
    "Explicit triples written with the remember tool. Contradictory writes "
    "under synonymous keys are flagged rather than silently resolved.")

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>sourcedrecall — stored records</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:0;background:#0f1115;color:#e6e6e6}}
 header{{padding:16px 24px;border-bottom:1px solid #2a2e37}}
 h1{{margin:0;font-size:18px}} .sub{{color:#8b93a1;font-size:13px;margin-top:4px}}
 main{{padding:16px 24px}} table{{border-collapse:collapse;width:100%}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #23272f;vertical-align:top}}
 th{{color:#8b93a1;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
 tr.conflict td{{background:#2a1e12}} .flag{{color:#f0a860;font-weight:600}}
 .obj{{color:#7fd1b9}} .rel{{color:#9db4ff}} .src{{color:#8b93a1;font-size:12px}}
 .conf{{font-variant-numeric:tabular-nums;color:#8b93a1;font-size:12px}}
 code{{color:#8b93a1;font-size:12px}}
 footer{{padding:16px 24px;color:#8b93a1;font-size:12px;border-top:1px solid #2a2e37;max-width:70ch}}
 .empty{{color:#8b93a1;padding:24px 0}}
</style></head><body>
<header><h1>sourcedrecall</h1>
<div class="sub">{n} active record(s){conflicts} · read-only ·
<a href="/" style="color:#9db4ff">refresh</a></div></header>
<main>{table}</main>
<footer>{footer}</footer></body></html>"""


def _render(records):
    n = len(records)
    n_conf = sum(1 for r in records if r["conflict"])
    conflicts = f" · <span class='flag'>{n_conf} in conflict</span>" if n_conf else ""
    if not records:
        table = "<div class='empty'>No records stored yet.</div>"
    else:
        rows = []
        for r in records:
            c = r["confidence"]
            cls = " class='conflict'" if r["conflict"] else ""
            flag = "<span class='flag'>⚠ conflict</span>" if r["conflict"] else ""
            rows.append(
                f"<tr{cls}><td>{html.escape(r['subject'])}</td>"
                f"<td class='rel'>{html.escape(r['relation'])}</td>"
                f"<td class='obj'>{html.escape(r['object'])} {flag}</td>"
                f"<td class='src'>{html.escape(r['source'])}</td>"
                f"<td class='conf'>b={c['b']} d={c['d']} u={c['u']}</td>"
                f"<td><code>{html.escape(r['record_id'])}</code></td></tr>")
        table = ("<table><thead><tr><th>subject</th><th>relation</th>"
                 "<th>object</th><th>source</th><th>confidence</th>"
                 "<th>id</th></tr></thead><tbody>"
                 + "".join(rows) + "</tbody></table>")
    return PAGE.format(n=n, conflicts=conflicts, table=table,
                       footer=html.escape(FOOTER))


MEM_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>sourcedrecall memory</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 :root{{--bg:#fff;--fg:#1d1f23;--mute:#6b7280;--line:#e5e7eb;--acc:#2f5fd0;--old:#9a6700}}
 @media (prefers-color-scheme: dark){{:root{{--bg:#0f1115;--fg:#e6e6e6;--mute:#8b93a1;--line:#23272f;--acc:#9db4ff;--old:#e3b341}}}}
 body{{font:15px/1.5 system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}}
 header,main,footer{{max-width:880px;margin:0 auto;padding:16px}}
 h1{{font-size:20px;margin:0}} h2{{font-size:15px;margin:28px 0 8px;color:var(--mute);font-weight:600}}
 .sub,.meta,footer{{color:var(--mute);font-size:13px}}
 form{{margin-top:12px;display:flex;gap:8px}} input{{flex:1;padding:8px 10px;font:inherit;
  border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}}
 button{{padding:8px 14px;font:inherit;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}}
 ul{{list-style:none;padding:0;margin:0}} li{{padding:8px 0;border-bottom:1px solid var(--line)}}
 .said{{color:var(--mute)}} .tag{{color:var(--old);font-size:13px}} code{{color:var(--mute);font-size:12px}}
 .result{{border:1px solid var(--line);border-radius:8px;padding:8px 14px;margin-top:12px}}
 a{{color:var(--acc)}}
</style></head><body>
<header><h1>{title}</h1>
<div class="sub">{n} facts · read-only · <a href="/">refresh</a> · <a href="/triples">explicit triples</a></div>
<form method="get" action="/"><input name="q" value="{q}" placeholder="Ask what it remembers, e.g. Where do I live?">
<button>Recall</button></form>{result}</header>
<main>{body}</main>
<footer>Each line is a short summary, then your exact words and the date. To remove one:
<code>sourcedrecall-memory forget &lt;id&gt;</code>, or ask your assistant to forget it.</footer>
</body></html>"""


def _fact_li(f, tag=""):
    e = html.escape
    text = e(f.get("text") or f"{f.get('attribute')}: {f.get('value')}")
    said = (f.get("said") or "").strip()
    date = ((f.get("receipts") or [{}])[0].get("date") or "")
    bits = []
    if said:
        bits.append(f'<span class="said">"{e(said[:240])}"</span>')
    if date:
        bits.append(e(str(date)[:10]))
    if (f.get("mentions") or 0) > 1:
        bits.append(f"said {f['mentions']}x")
    labels = [t for t, on in (("no longer true", f.get("current") is False),
                              ("said in passing", f.get("passing")),
                              ("may have changed since", f.get("changed_later")),
                              ("possibly related", f.get("related"))) if on]
    lab = "".join(f'<span class="tag">({t})</span> ' for t in labels) or tag
    return (f"<li>{lab}{text}<div class='meta'>{' · '.join(bits)} · "
            f"<code>{e(str(f.get('id') or ''))}</code></div></li>")


def _render_memory(owner, groups, q="", rec=None):
    e = html.escape
    n = sum(len(g) for _, g in groups)
    body = "".join(f"<h2>{e(t)}</h2><ul>{''.join(_fact_li(f) for f in g)}</ul>"
                   for t, g in groups)
    # 2026-10-05: notes written by the user's own model (opt-in notes mode)
    try:
        from sourcedrecall import profile_memory as _pm
        notes = sorted(_pm._load_notes(), key=lambda r: str(r.get("date") or ""),
                       reverse=True)
    except Exception:
        notes = []
    if notes:
        items = "".join(
            f"<li>{e(r['text'])} <span class='sub'>{e(str(r.get('date') or ''))}"
            f" · id <code>{e(_pm._note_id(r))}</code></span></li>" for r in notes)
        body += f"<h2>Notes written by your model</h2><ul>{items}</ul>"
    body = body or "<p class='sub'>Nothing stored yet.</p>"
    result = ""
    if q:
        if rec and rec.get("found"):
            items = "".join(_fact_li(f) for f in rec.get("ranked") or [])
            result = f"<div class='result'><ul>{items}</ul></div>"
        elif rec and rec.get("related"):
            items = "".join(_fact_li(f) for f in rec["related"])
            result = ("<div class='result'><div class='sub'>Nothing stored is known "
                      f"to answer this. Closest things said:</div><ul>{items}</ul></div>")
        else:
            result = "<div class='result sub'>Nothing stored about this.</div>"
    title = f"Memory: {e(owner)}" if owner else "Memory"
    return MEM_PAGE.format(title=title, n=n, q=e(q), result=result, body=body)


# 2026-10-09 (security review): the browser answered any Host header (a web
# page could rebind its name to 127.0.0.1 and read the memory) and anyone on
# the machine. Now: loopback Host names only, a random token per run (in the
# printed address once, then a strict cookie), and headers that keep the
# page from being framed, sniffed, cached or running scripts.
_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                               "form-action 'self'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def new_token():
    import secrets
    return secrets.token_urlsafe(18)


def make_handler(service, token=None):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body, ctype="text/html; charset=utf-8", status=200, cookie=None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in _HEADERS.items():
                self.send_header(k, v)
            if cookie:
                self.send_header("Set-Cookie", f"sdr={cookie}; HttpOnly; SameSite=Strict; Path=/")
            self.end_headers()
            self.wfile.write(data)

        def _allowed(self, query):
            port = self.server.server_address[1]
            host = (self.headers.get("Host") or "").strip().lower()
            if host not in {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}:
                return False, None
            if not token:
                return True, None
            import hmac
            given = (query.get("t") or [""])[0]
            if given and hmac.compare_digest(given, token):
                return True, token                       # set the cookie
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "sdr" and hmac.compare_digest(v, token):
                    return True, None
            return False, None

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            ok, cookie = self._allowed(parse_qs(u.query))
            if not ok:
                self._send("Open the address printed by `sourcedrecall-memory view` "
                           "(it carries this run's key).", "text/plain; charset=utf-8", 403)
                return
            if cookie:
                # drop the key from the address bar
                self.send_response(303)
                self.send_header("Location", u.path or "/")
                for k, v in _HEADERS.items():
                    self.send_header(k, v)
                self.send_header("Set-Cookie", f"sdr={cookie}; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if u.path.startswith("/api/records") and service is not None:
                self._send(json.dumps(service.all_records()),
                           "application/json")
            elif u.path == "/triples" and service is not None:
                self._send(_render(service.all_records()))
            elif u.path == "/":
                from sourcedrecall import profile_memory as pm
                q = (parse_qs(u.query).get("q") or [""])[0].strip()[:300]
                owner, groups = pm.memory_groups()
                rec = pm.profile_recall(q) if q else None
                self._send(_render_memory(owner, groups, q, rec))
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass  # quiet
    return Handler


def url_file():
    from sourcedrecall.paths import private_dir, state_dir
    import os
    return os.path.join(private_dir(state_dir()), "browser-url")


def start_browser(service, port=7071, host="127.0.0.1"):
    """Start the read-only browser on host:port in a daemon thread. host is
    forced to loopback — the browser never binds a public interface. Its
    address, with this run's key, is written to browser-url in the private
    state dir (`sourcedrecall-memory view` prints it)."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("browser binds loopback only")
    token = new_token()
    httpd = http.server.HTTPServer((host, port), make_handler(service, token))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with open(url_file(), "w") as f:
            f.write(f"http://127.0.0.1:{port}/?t={token}\n")
    except OSError:
        pass
    return httpd
