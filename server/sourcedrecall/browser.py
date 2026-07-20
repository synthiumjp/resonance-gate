"""Read-only local memory browser. A single static page served on
127.0.0.1 that lists every stored record as a human-readable triple with its
provenance, confidence (b,d,u) and any active conflict. This is a trust
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
    "sourcedrecall stores explicit structured facts you write. It does NOT "
    "extract facts from conversation (no language model inside — nothing to "
    "hallucinate). It detects contradictory writes under synonymous keys "
    "(validated on synthetic pairs; real-world validation pending), returns "
    "an honest ‘no match’ when nothing is stored, and surfaces "
    "conflicts rather than silently picking.")

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


def make_handler(service):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, body, ctype="text/html; charset=utf-8"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.startswith("/api/records"):
                self._send(json.dumps(service.all_records()),
                           "application/json")
            elif self.path == "/" or self.path.startswith("/?"):
                self._send(_render(service.all_records()))
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass  # quiet
    return Handler


def start_browser(service, port=7071, host="127.0.0.1"):
    """Start the read-only browser on host:port in a daemon thread. host is
    forced to loopback — the browser never binds a public interface."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("browser binds loopback only")
    httpd = http.server.HTTPServer((host, port), make_handler(service))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
