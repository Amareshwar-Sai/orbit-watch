import copy
import http.client
import json
import socket
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

from orbitwatch.articles import article, briefing
from orbitwatch.core import ROOT, database, import_incident, incidents, read_json, review, top_incidents, validate_incident
from orbitwatch.ingest import collect, config_at, parse_feed, published, relevant, store_candidate
from orbitwatch.net import PinnedHTTPS, canonical_url, fetch, public_addresses, read_bounded
from orbitwatch.web import handler_for, render

RSS = b'''<rss version="2.0"><channel><item><title>Satellite cyber attack report</title>
<link>https://example.org/report?utm_source=rss</link><description><![CDATA[<p>Ground station intrusion.</p><script>evil()</script>]]></description>
<pubDate>Tue, 15 Sep 2026 08:00:00 GMT</pubDate></item></channel></rss>'''


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        self.data = read_json(ROOT / "data/incidents/ka-sat-2022.json")
        self.ctx = database(self.path)
        self.conn = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.tmp.cleanup()

    def seed(self):
        import_incident(self.conn, self.data)

    def approve(self):
        review(self.conn, self.data["id"], 1, "approved", "Test reviewer", "Fixture review")

    def test_seed_idempotent(self):
        self.seed()
        self.assertEqual(import_incident(self.conn, self.data), "unchanged")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM revisions").fetchone()[0], 1)

    def test_draft_excluded_then_reviewed_included(self):
        self.seed()
        self.assertEqual(top_incidents(self.conn), [])
        self.approve()
        self.assertEqual(len(top_incidents(self.conn)), 1)

    def test_edit_revokes_approval_preserves_history(self):
        self.seed()
        self.approve()
        self.data["title"] += " revised"
        self.seed()
        row = incidents(self.conn)[0]
        self.assertEqual((row["status"], row["version"], row["reviewer"]), ("draft", 2, None))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM reviews").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM revisions").fetchone()[0], 2)

    def test_stale_review_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            review(self.conn, self.data["id"], 0, "approved", "Test", "Wrong version")

    def test_research_and_hypothetical_excluded(self):
        for kind in ("research", "hypothetical"):
            d = copy.deepcopy(self.data)
            d.update(id=kind, kind=kind)
            import_incident(self.conn, d)
            review(self.conn, kind, 1, "approved", "Test", "Reviewed demo")
        self.assertEqual(top_incidents(self.conn), [])

    def test_top_five_and_deterministic_ties(self):
        for i in range(7):
            d = copy.deepcopy(self.data)
            d["id"] = f"record-{i}"
            import_incident(self.conn, d)
            review(self.conn, d["id"], 1, "approved", "Test", "Test records")
        self.assertEqual([r["id"] for r in top_incidents(self.conn)], [f"record-{i}" for i in range(5)])

    def test_unknown_citation_rejected(self):
        self.data["steps"][0]["sources"] = ["missing"]
        with self.assertRaises(ValueError):
            self.seed()
        self.assertEqual(incidents(self.conn), [])

    def test_unknown_technique_rejected(self):
        self.data["mappings"][0]["technique"] = "FAKE-001"
        with self.assertRaises(ValueError):
            validate_incident(self.data)

    def test_no_mapping_needs_explanation(self):
        self.data["mappings"] = []
        with self.assertRaises(ValueError):
            validate_incident(self.data)
        self.data["unmapped_reason"] = "Evidence insufficient"
        validate_incident(self.data)

    def test_catalog_change_requires_reassessment(self):
        self.data["sparta_snapshot"] = "future-snapshot"
        with self.assertRaises(ValueError):
            validate_incident(self.data)

    def test_deprecated_mapping_rejected(self):
        from orbitwatch.core import catalog
        snapshot, entries = catalog()
        entries["IA-0007"]["deprecated"] = True
        with patch("orbitwatch.core.catalog", return_value=(snapshot, entries)):
            with self.assertRaises(ValueError):
                validate_incident(self.data)

    def test_definition_change_invalidates_old_approval(self):
        self.seed()
        self.approve()
        from orbitwatch.core import catalog
        snapshot, entries = catalog()
        snapshot["scope"] += " Updated definition context."
        with patch("orbitwatch.core.catalog", return_value=(snapshot, entries)):
            self.assertEqual(top_incidents(self.conn), [])
            self.assertEqual(incidents(self.conn)[0]["status"], "needs-review")
            with self.assertRaises(ValueError):
                self.approve()
            self.seed()
            self.assertEqual(incidents(self.conn)[0]["version"], 2)

    def test_article_labels_and_citations(self):
        self.seed()
        text = article(incidents(self.conn)[0])
        for value in ("DRAFT", "2022-02-24", "[V1]", "Confidence: medium", "proposed engineering controls", "## Limits"):
            self.assertIn(value, text)
        self.assertNotIn("CONFIRMED", text)

    def test_xss_input_inert(self):
        self.data["title"] = '<script>alert("bad")</script>'
        self.seed()
        html = render(self.conn, "/cases", {})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", article(incidents(self.conn)[0]))

    def test_duplicate_source_reports_dont_duplicate_candidate(self):
        row = parse_feed(RSS)[0]
        self.assertEqual(store_candidate(self.conn, row, "one", True), 1)
        self.assertEqual(store_candidate(self.conn, row, "two", True), 0)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM candidates").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM candidate_sources").fetchone()[0], 2)

    def test_mixed_source_failure_persists_and_continues(self):
        config = config_at(ROOT / "config/sources.json")
        config["sources"] = [dict(config["sources"][0], id="failed"), dict(config["sources"][1], id="good")]
        fetcher = Mock(side_effect=[OSError("offline"), RSS])
        results = collect(self.conn, config, fetcher)
        self.assertEqual([r["outcome"] for r in results], ["error", "ok"])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM candidates").fetchone()[0], 1)
        self.assertIn("offline", briefing(self.conn))

    def test_bad_feed_creates_error_not_empty_success(self):
        config = config_at(ROOT / "config/sources.json")
        config["sources"] = config["sources"][:1]
        result = collect(self.conn, config, lambda *_: b"<html>Access denied</html>")
        self.assertEqual(result[0]["outcome"], "error")

    def test_sql_input_does_not_change_tables(self):
        render(self.conn, "/queue", {"q": ["'; DROP TABLE incidents; --"]})
        self.assertEqual(incidents(self.conn), [])


class ParsingTests(unittest.TestCase):
    def test_rss_cleans_scripts_and_canonicalizes(self):
        row = parse_feed(RSS)[0]
        self.assertEqual(row["url"], "https://example.org/report")
        self.assertEqual(row["summary"], "Ground station intrusion.")
        self.assertEqual(row["published_at"], "2026-09-15T08:00:00+00:00")

    def test_atom_alternate_link(self):
        raw = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Satellite security</title>
        <link rel="self" href="https://example.org/api"/><link rel="alternate" href="https://example.org/article"/>
        <published>2026-01-01T10:00:00Z</published></entry></feed>'''
        self.assertEqual(parse_feed(raw)[0]["url"], "https://example.org/article")

    def test_xxe_and_utf16_blocked(self):
        for raw in [b'<!DOCTYPE rss [<!ENTITY a SYSTEM "file:///etc/passwd">]><rss>&a;</rss>',
                    '<rss/>'.encode("utf-16")]:
            with self.assertRaises((ValueError, UnicodeError)):
                parse_feed(raw)

    def test_oversized_feed_blocked(self):
        with self.assertRaises(ValueError):
            parse_feed(b"x" * 1_048_577)

    def test_unsafe_link_skipped(self):
        self.assertEqual(parse_feed(RSS.replace(b"https://example.org/report?utm_source=rss", b"javascript:alert(1)")), [])

    def test_undated_is_unknown(self):
        self.assertIsNone(published("yesterday"))
        self.assertIsNone(published("2026-01-01"))
        self.assertIsNone(parse_feed(RSS.replace(b"Tue, 15 Sep 2026 08:00:00 GMT", b""))[0]["published_at"])

    def test_both_keyword_groups_needed(self):
        config = config_at(ROOT / "config/sources.json")
        self.assertTrue(relevant({"title": "Satellite cyber attack", "summary": ""}, config))
        self.assertFalse(relevant({"title": "Satellite launch", "summary": ""}, config))
        self.assertFalse(relevant({"title": "Database attack", "summary": ""}, config))


class NetworkTests(unittest.TestCase):
    def test_unsafe_urls_rejected(self):
        for url in ["http://example.org", "https://127.0.0.1/", "https://[::1]/", "https://localhost/",
                    "https://x.local/", "https://example.org:8080/", "https://u:p@example.org/",
                    "https://example.org/\r\nX-Test:foo", "file:///etc/passwd"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_url(url)

    def test_private_or_mixed_dns_blocked(self):
        for values in [["127.0.0.1"], ["169.254.169.254"], ["::1"], ["8.8.8.8", "10.0.0.1"]]:
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (v, 443)) for v in values]
            with patch("socket.getaddrinfo", return_value=answers), self.assertRaises(ValueError):
                public_addresses("example.org")

    def test_host_allowlist_before_dns(self):
        with patch("orbitwatch.net.public_addresses") as resolver:
            with self.assertRaises(ValueError):
                fetch("https://evil.example/", ["example.org"])
            resolver.assert_not_called()

    def test_dns_pin_and_tls_hostname(self):
        conn = PinnedHTTPS("example.org", "93.184.216.34")
        context, raw = Mock(), Mock()
        conn._context = context
        with patch("socket.create_connection", return_value=raw) as connect:
            conn.connect()
        connect.assert_called_once_with(("93.184.216.34", 443), timeout=10)
        context.wrap_socket.assert_called_once_with(raw, server_hostname="example.org")

    def test_redirect_rejected(self):
        connection = Mock()
        connection.getresponse.return_value.status = 302
        with patch("orbitwatch.net.public_addresses", return_value=["93.184.216.34"]), patch("orbitwatch.net.PinnedHTTPS", return_value=connection):
            with self.assertRaises(ValueError):
                fetch("https://example.org/", ["example.org"])
        connection.close.assert_called_once()

    def test_content_length_and_stream_limits(self):
        response = Mock()
        response.getheader.side_effect = lambda key, default=None: "99" if key == "Content-Length" else default
        with self.assertRaises(ValueError):
            read_bounded(response, 10)
        response.getheader.side_effect = lambda key, default=None: default
        response.read1.side_effect = [b"x" * 11]
        with self.assertRaises(ValueError):
            read_bounded(response, 10)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "http.db"
        with database(cls.path) as conn:
            import_incident(conn, read_json(ROOT / "data/incidents/ka-sat-2022.json"))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(cls.path, 0))
        cls.port = cls.server.server_port
        cls.server.RequestHandlerClass = handler_for(cls.path, cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, path, method="GET", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path, headers=headers or {})
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_pages_and_health(self):
        for route in ["/", "/cases", "/queue", "/sources", "/sparta", "/case?id=ka-sat-2022", "/health", "/style.css"]:
            with self.subTest(route=route):
                status, headers, body = self.request(route)
                self.assertEqual(status, 200)
                self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
                self.assertTrue(body)

    def test_host_header_blocks_rebinding(self):
        self.assertEqual(self.request("/", headers={"Host": "attacker.example"})[0], 403)

    def test_no_remote_edits(self):
        self.assertEqual(self.request("/review", method="POST")[0], 501)

    def test_path_traversal_blocked(self):
        self.assertEqual(self.request("/../../etc/passwd")[0], 404)

    def test_markdown_download_inert(self):
        status, headers, body = self.request("/article?id=ka-sat-2022")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn(b"DRAFT", body)


if __name__ == "__main__":
    unittest.main()
