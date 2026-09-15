"""Read bounded UTF-8 RSS/Atom feeds and watch explicitly configured pages."""

import hashlib
import http.client
import re
import xml.etree.ElementTree as ET  # nosec B405: DTD/entity rejected before parsing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .core import digest, now, read_json
from .net import MAX_BYTES, canonical_url, fetch


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def plain(value):
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def published(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if stamp.tzinfo is None:
        return None  # Do not invent a timezone.
    return stamp.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_feed(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Feed exceeds size limit")
    text = raw.decode("utf-8-sig", errors="strict")
    if "\x00" in text:
        raise ValueError("Null characters and non-UTF-8 XML are forbidden")

    # XML-aware guard: declarations inside CDATA/comments are inert text.
    # Abort on real DTDs before any entity declarations can be processed.
    from xml.parsers import expat

    def reject_declaration(*args):
        raise ValueError("XML DTD and entity declarations are forbidden")

    guard = expat.ParserCreate()
    guard.StartDoctypeDeclHandler = reject_declaration
    guard.EntityDeclHandler = reject_declaration
    guard.ExternalEntityRefHandler = reject_declaration
    guard.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        guard.Parse(text, True)
    except expat.ExpatError as exc:
        raise ValueError(f"Malformed XML feed: {exc}") from exc
    # Same immutable text, validated above without permitting a real DTD.
    root = ET.fromstring(text)  # nosec B314: bounded, DTD-free XML verified by Expat
    local = lambda tag: tag.rsplit("}", 1)[-1]
    if local(root.tag) not in ("rss", "feed", "RDF"):
        raise ValueError("Response is not RSS/Atom")
    rows = []
    for element in root.iter():
        if local(element.tag) not in ("item", "entry"):
            continue
        fields = {}
        for child in element:
            name = local(child.tag)
            if name == "link" and child.attrib.get("rel", "alternate") != "alternate":
                continue
            fields.setdefault(name, child.attrib.get("href") or "".join(child.itertext()))
        try:
            url = canonical_url(fields.get("link", "").strip())
        except ValueError:
            continue
        title = plain(fields.get("title", ""))[:300]
        if not title:
            continue
        rows.append({"url": url, "title": title,
                     "summary": plain(fields.get("summary", fields.get("description", "")))[:1000],
                     "published_at": published(fields.get("published", fields.get("pubDate")))})
        if len(rows) >= 200:
            break
    return rows


def relevant(row, config):
    text = (row["title"] + " " + row["summary"]).lower()
    return all(any(re.search(r"\b" + re.escape(term) + r"\b", text) for term in config[key])
               for key in ("space_terms", "security_terms"))


def config_at(path):
    config = read_json(path)
    sources = config.get("sources", [])
    if not sources or len(sources) > 30:
        raise ValueError("Configure between 1 and 30 sources")
    ids = set()
    for source in sources:
        if source["id"] in ids:
            raise ValueError("Duplicate source ID")
        ids.add(source["id"])
        if source["kind"] not in ("feed", "page"):
            raise ValueError("Source kind must be feed or page")
        canonical_url(source["url"])
        if urlsplit(source["url"]).hostname not in config["allowed_hosts"]:
            raise ValueError("Configured source host must be explicitly allowlisted")
    for key in ("space_terms", "security_terms"):
        if not config.get(key) or any(not isinstance(t, str) or not t for t in config[key]):
            raise ValueError("Keyword lists must contain nonempty strings")
    return config


def store_candidate(conn, row, source, is_relevant):
    stamp = now()
    fingerprint = digest(row)
    old = conn.execute("SELECT hash FROM candidates WHERE url=?", (row["url"],)).fetchone()
    changed = old is None or old["hash"] != fingerprint
    conn.execute("""INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?)
      ON CONFLICT(url) DO UPDATE SET title=excluded.title,summary=excluded.summary,
      published_at=excluded.published_at,
      last_changed=CASE WHEN candidates.hash<>excluded.hash THEN excluded.last_changed ELSE candidates.last_changed END,
      hash=excluded.hash,relevant=excluded.relevant""",
                 (row["url"], row["title"], row["summary"], row["published_at"], stamp,
                  stamp, fingerprint, int(is_relevant)))
    conn.execute("""INSERT INTO candidate_sources VALUES (?,?,?) ON CONFLICT(url,source)
      DO UPDATE SET last_seen=excluded.last_seen""", (row["url"], source, stamp))
    return int(changed)


def collect(conn, config, fetcher=fetch):
    reports = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        cursor = conn.execute("INSERT INTO runs(started_at,source,outcome) VALUES (?,?,'running')",
                              (now(), source["id"]))
        run_id = cursor.lastrowid
        conn.commit()  # A crash leaves an observable unfinished run.
        conn.execute("SAVEPOINT source_collect")
        try:
            raw = fetcher(source["url"], config["allowed_hosts"])
            checksum = hashlib.sha256(raw).hexdigest()
            if source["kind"] == "feed":
                rows = parse_feed(raw)
            else:
                # Watch page changes without copying/re-publishing article bodies.
                text = plain(raw.decode("utf-8", errors="strict"))
                rows = [{"url": canonical_url(source["url"]), "title": source["name"],
                         "summary": "Monitored reference page. Content SHA-256: " + hashlib.sha256(text.encode()).hexdigest(),
                         "published_at": None}]
            changed = sum(store_candidate(conn, row, source["id"],
                          source["kind"] == "page" or relevant(row, config)) for row in rows)
            conn.execute("RELEASE source_collect")
            conn.execute("UPDATE runs SET finished_at=?,outcome='ok',fetched=?,changed=?,content_hash=? WHERE id=?",
                         (now(), len(rows), changed, checksum, run_id))
            reports.append({"source": source["id"], "outcome": "ok", "items": len(rows), "changed": changed})
        except (ValueError, OSError, ET.ParseError, UnicodeError, http.client.HTTPException) as exc:
            conn.execute("ROLLBACK TO source_collect")
            conn.execute("RELEASE source_collect")
            error = str(exc)[:300]
            conn.execute("UPDATE runs SET finished_at=?,outcome='error',error=? WHERE id=?", (now(), error, run_id))
            reports.append({"source": source["id"], "outcome": "error", "error": error})
        conn.commit()
    return reports
