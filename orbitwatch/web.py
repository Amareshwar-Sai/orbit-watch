"""Read-only local dashboard. Editorial actions are available only through CLI."""

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .articles import article
from .core import ROOT, catalog, database, incidents, top_incidents


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)} ↗</a>'


def page(title, body, active="Overview"):
    nav = "".join(f'<a class="{"active" if label == active else ""}" href="{url}">{label}</a>'
                  for label, url in [("Overview", "/"), ("Evidence queue", "/queue"),
                                     ("Case library", "/cases"), ("Source health", "/sources"),
                                     ("SPARTA", "/sparta")])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{esc(title)} · OrbitWatch</title><link rel="stylesheet" href="/style.css"></head>
    <body><aside><a class="brand" href="/">◉ ORBITWATCH</a><p class="tagline">SPACE SECURITY INTELLIGENCE</p>
    <nav>{nav}</nav><div class="aside-note"><span class="dot"></span> LOCAL WORKSPACE<br>
    <small>Evidence first. Every claim accountable.</small></div></aside><main>
    <header><span>RESEARCH OPERATIONS / 01</span><span class="pill">LOCAL · READ ONLY</span></header>
    <h1>{esc(title)}</h1>{body}<footer>OrbitWatch v0.1 · Analyst-reviewed research · SPARTA by The Aerospace Corporation</footer>
    </main></body></html>'''


def case_cards(rows):
    if not rows:
        return '<div class="empty">No records yet. Run <code>python -m orbitwatch seed</code> to load the historical example.</div>'
    return '<div class="cards">' + "".join(f'''<a class="case" href="/case?id={esc(r['id'])}">
    <div><span class="pill">{esc(r['status'])}</span><span class="muted">{esc(r['data']['kind'])} · {esc(r['data']['event_date'])}</span></div>
    <h3>{esc(r['data']['title'])}</h3><p>{esc(r['data']['summary'])}</p>
    <div class="case-bottom"><span>{esc(r['data']['segment'])}</span><b>{r['score']}<small>/15</small></b></div></a>''' for r in rows) + '</div>'


def render(conn, path, query):
    if path == "/":
        rows = incidents(conn)
        count = conn.execute("SELECT count(*) FROM candidates WHERE relevant=1").fetchone()[0]
        failures = conn.execute("SELECT count(*) FROM runs WHERE id IN (SELECT max(id) FROM runs GROUP BY source) AND outcome<>'ok'").fetchone()[0]
        body = '<p class="lead">Follow the evidence.<br>Understand the mission impact.</p>'
        body += '<div class="stats">' + ''.join(f'<section><span>{label}</span><strong>{number}</strong></section>'
                  for label, number in [("SOURCE CANDIDATES", count), ("CASES TO REVIEW", sum(r["status"] == "draft" for r in rows)),
                                        ("APPROVED CASES", sum(r["status"] == "approved" for r in rows)), ("SOURCE ISSUES", failures)]) + '</div>'
        body += '<div class="section-title"><h2>Reviewed incident priorities</h2><span>UP TO FIVE</span></div><p class="muted">Historical incidents ranked within your reviewed corpus. This is not a daily attack count.</p>'
        ranked = top_incidents(conn)
        body += case_cards(ranked) if ranked else '<div class="empty">No approved incidents yet. Open the case library, inspect the evidence, then approve a version through the CLI.</div>'
        body += '<div class="section-title"><h2>Your case library</h2><a href="/cases">View all →</a></div>' + case_cards(rows[:4])
        return page("Mission intelligence", body)
    if path == "/cases":
        return page("Case library", '<p class="lead">Trace each claim from source to assessment.</p>' + case_cards(incidents(conn)), "Case library")
    if path == "/case":
        row = next((r for r in incidents(conn) if r["id"] == query.get("id", [""])[0]), None)
        if not row:
            return None
        body = f'<p><span class="pill">{esc(row["status"])} · v{row["version"]}</span> <a href="/article?id={esc(row["id"])}">Download article draft ↓</a></p>'
        body += '<div class="notice">Read the linked sources before approval. The application validates citation references, not whether a source proves a claim.</div>'
        body += '<pre class="article">' + esc(article(row)) + '</pre>'
        history = conn.execute("SELECT version,decision,reviewer,note,created_at FROM reviews WHERE incident_id=? ORDER BY id DESC", (row["id"],)).fetchall()
        body += '<h2>Review history</h2>' + ''.join('<p>' + esc(dict(h)) + '</p>' for h in history)
        return page(row["data"]["title"], body, "Case library")
    if path == "/queue":
        q = query.get("q", [""])[0][:200]
        show_all = query.get("all", [""])[0] == "1"
        rows = conn.execute("SELECT * FROM candidates WHERE (?=1 OR relevant=1) AND (instr(lower(title),lower(?))>0 OR instr(lower(summary),lower(?))>0) ORDER BY last_changed DESC LIMIT 200", (int(show_all), q, q)).fetchall()
        body = '<p class="lead">Source reports are leads, not verified incidents.</p>'
        body += f'<form method="get"><label>Search reports <input name="q" value="{esc(q)}" placeholder="Satellite, VPN, ground station…"></label><label class="check"><input type="checkbox" name="all" value="1" {"checked" if show_all else ""}> Include keyword-filtered reports</label><button>Search</button></form>'
        body += '<p class="muted">Latest 200 matching reports. Dates distinguish publication from discovery; unknown publication dates stay unknown.</p>'
        for row in rows:
            body += f'<section class="report"><h3>{link(row["url"],row["title"])}</h3><p>{esc(row["summary"])}</p><small>Published: {esc(row["published_at"] or "Unknown")} · First seen: {esc(row["first_seen"])} · Changed: {esc(row["last_changed"])}</small></section>'
        if not rows:
            body += '<div class="empty">No reports match. Run collection and check Source health for failures.</div>'
        return page("Evidence queue", body, "Evidence queue")
    if path == "/sources":
        rows = conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 100").fetchall()
        body = '<p class="lead">A quiet feed and a failed feed are different things.</p><div class="table-wrap"><table><thead><tr><th>Source / started</th><th>Outcome</th><th>Inspected</th><th>Changed</th><th>Detail</th></tr></thead><tbody>'
        for r in rows:
            body += f'<tr><td>{esc(r["source"])}<br><small>{esc(r["started_at"])}</small></td><td>{esc(r["outcome"])}</td><td>{r["fetched"]}</td><td>{r["changed"]}</td><td>{esc(r["error"] or "—")}</td></tr>'
        body += '</tbody></table></div><p class="muted">Showing the last 100 source runs. A running record without a finish time may indicate an interrupted collection.</p>'
        return page("Source health", body, "Source health")
    if path == "/sparta":
        metadata, techniques = catalog()
        body = '<p class="lead">Explicit mappings. Visible uncertainty.</p><div class="notice">This is a curated starter subset, not the complete SPARTA matrix. Snapshot: ' + esc(metadata["snapshot"]) + '</div>'
        for t in techniques.values():
            body += f'<section class="report"><h3>{link(t["url"], t["id"] + " · " + t["name"])}</h3><p>{esc(t["scope_note"])}</p></section>'
        return page("SPARTA reference", body, "SPARTA")
    return None


def handler_for(db_path, port):
    class Handler(BaseHTTPRequestHandler):
        server_version = "OrbitWatch"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def do_GET(self):
            # Host validation blocks ordinary DNS-rebinding access to this loopback app.
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self.send_error(403, "Use the local dashboard address")
                return
            if len(self.path) > 4096:
                self.send_error(414)
                return
            p = urlsplit(self.path)
            try:
                query = parse_qs(p.query, max_num_fields=10)
            except ValueError:
                self.send_error(400)
                return
            content_type = "text/html; charset=utf-8"
            attachment = False
            with database(db_path) as conn:
                if p.path == "/health":
                    conn.execute("SELECT 1").fetchone()
                    body, content_type = '{"status":"ok"}', "application/json"
                elif p.path == "/style.css":
                    body, content_type = (ROOT / "static/style.css").read_text(), "text/css"
                elif p.path == "/article":
                    row = next((r for r in incidents(conn) if r["id"] == query.get("id", [""])[0]), None)
                    body = article(row) if row else None
                    content_type, attachment = "text/plain; charset=utf-8", True
                else:
                    body = render(conn, p.path, query)
            if body is None:
                self.send_error(404)
                return
            raw = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="orbitwatch-article.md"')
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt, *args):
            pass  # Request URLs may contain research terms; do not persist them.

    return Handler


def serve(db_path, port=8000, container=False):
    address = "0.0.0.0" if container else "127.0.0.1"  # nosec B104: Docker loopback port mapping
    server = ThreadingHTTPServer((address, port), handler_for(db_path, port))
    print(f"OrbitWatch: http://127.0.0.1:{port} — Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
