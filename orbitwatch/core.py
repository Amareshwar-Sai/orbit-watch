"""SQLite persistence, evidence validation, and review state transitions."""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .net import canonical_url

ROOT = Path(__file__).resolve().parent.parent


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def packed(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 1_048_576:
        raise ValueError("JSON input exceeds 1 MiB")
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def database(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS incidents (
      id TEXT PRIMARY KEY, payload TEXT NOT NULL, hash TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL,
      updated_at TEXT NOT NULL, reviewer TEXT, reviewed_at TEXT,
      catalog_hash TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS revisions (
      incident_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
      hash TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(incident_id,version));
    CREATE TABLE IF NOT EXISTS reviews (
      id INTEGER PRIMARY KEY, incident_id TEXT NOT NULL, version INTEGER NOT NULL,
      decision TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL,
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS candidates (
      url TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL,
      published_at TEXT, first_seen TEXT NOT NULL, last_changed TEXT NOT NULL,
      hash TEXT NOT NULL, relevant INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS candidate_sources (
      url TEXT NOT NULL REFERENCES candidates(url), source TEXT NOT NULL,
      last_seen TEXT NOT NULL, PRIMARY KEY(url,source));
    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
      source TEXT NOT NULL, outcome TEXT NOT NULL, fetched INTEGER NOT NULL DEFAULT 0,
      changed INTEGER NOT NULL DEFAULT 0, error TEXT, content_hash TEXT);
    """)
    if "catalog_hash" not in {r[1] for r in conn.execute("PRAGMA table_info(incidents)")}:
        conn.execute("ALTER TABLE incidents ADD COLUMN catalog_hash TEXT NOT NULL DEFAULT ''")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def text_field(value, label, limit=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label}: expected nonempty text, at most {limit} characters")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{label}: control characters are forbidden")
    return value


def catalog():
    data = read_json(ROOT / "data/sparta.json")
    return data, {x["id"]: x for x in data["techniques"]}


def validate_incident(data):
    if not isinstance(data, dict):
        raise ValueError("Incident must be a JSON object")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", data.get("id", "")):
        raise ValueError("id must be a lowercase slug")
    for field in ("title", "summary", "segment", "limitations"):
        text_field(data.get(field), field)
    if data.get("kind") not in ("incident", "research", "hypothetical"):
        raise ValueError("kind must be incident, research, or hypothetical")
    incident_date = date.fromisoformat(data.get("event_date", ""))
    if incident_date > datetime.now(timezone.utc).date():
        raise ValueError("event_date cannot be in the future")
    sources = data.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 30:
        raise ValueError("Provide 1–30 sources")
    source_ids = set()
    for source in sources:
        sid = text_field(source.get("id"), "source id", 40)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or sid in source_ids:
            raise ValueError("Source IDs must be unique alphanumeric identifiers")
        source_ids.add(sid)
        text_field(source.get("title"), "source title", 300)
        canonical_url(source.get("url"))
        date.fromisoformat(source.get("published_date", ""))
        date.fromisoformat(source.get("accessed_date", ""))

    def refs(row):
        values = row.get("sources")
        if not isinstance(values, list) or not values or not set(values) <= source_ids:
            raise ValueError("Every claim/step/mapping requires valid source IDs")

    refs({"sources": data.get("summary_sources")})
    for field in ("claims", "steps"):
        rows = data.get(field)
        if not isinstance(rows, list) or not 1 <= len(rows) <= 30:
            raise ValueError(f"{field}: provide 1–30 entries")
        for row in rows:
            text_field(row.get("text"), field)
            if row.get("certainty") not in ("reported", "corroborated", "inference"):
                raise ValueError("certainty must be reported, corroborated, or inference")
            refs(row)
    snapshot, techniques = catalog()
    if data.get("sparta_snapshot") != snapshot["snapshot"]:
        raise ValueError("Incident SPARTA snapshot must match the bundled catalog")
    mappings = data.get("mappings", [])
    if not isinstance(mappings, list) or len(mappings) > 30:
        raise ValueError("mappings must be a list of at most 30 entries")
    for mapping in mappings:
        if mapping.get("technique") not in techniques:
            raise ValueError("Unknown SPARTA technique; verify and extend the catalog first")
        if techniques[mapping["technique"]].get("deprecated"):
            raise ValueError("Deprecated SPARTA technique; reassess the mapping")
        text_field(mapping.get("rationale"), "mapping rationale")
        if mapping.get("confidence") not in ("low", "medium", "high"):
            raise ValueError("Mapping confidence must be low, medium, or high")
        refs(mapping)
    if not mappings:
        text_field(data.get("unmapped_reason"), "unmapped_reason")
    controls = data.get("controls")
    if not isinstance(controls, list) or not 1 <= len(controls) <= 30:
        raise ValueError("Provide 1–30 defensive recommendations")
    for control in controls:
        for field in ("action", "why", "validation"):
            text_field(control.get(field), "control " + field)
        if control.get("phase") not in ("prevent", "detect", "contain", "recover"):
            raise ValueError("Unknown defense phase")
    rank = data.get("impact", {})
    for axis in ("mission", "scope", "recovery"):
        if type(rank.get(axis)) is not int or not 0 <= rank[axis] <= 5:
            raise ValueError("Impact axes must be integers from 0 to 5")
    text_field(rank.get("rationale"), "impact rationale")
    refs(rank)
    return data


def import_incident(conn, data):
    validate_incident(data)
    checksum = digest(data)
    catalog_checksum = digest(catalog()[0])
    old = conn.execute("SELECT * FROM incidents WHERE id=?", (data["id"],)).fetchone()
    if old and old["hash"] == checksum and old["catalog_hash"] == catalog_checksum:
        return "unchanged"
    version = old["version"] + 1 if old else 1
    stamp = now()
    conn.execute("""INSERT INTO incidents VALUES (?,?,?,'draft',?,?,NULL,NULL,?)
      ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,hash=excluded.hash,
      status='draft',version=excluded.version,updated_at=excluded.updated_at,
      reviewer=NULL,reviewed_at=NULL,catalog_hash=excluded.catalog_hash""",
                 (data["id"], packed(data), checksum, version, stamp, catalog_checksum))
    conn.execute("INSERT INTO revisions VALUES (?,?,?,?,?)",
                 (data["id"], version, packed(data), checksum, stamp))
    return "draft"


def review(conn, incident_id, version, decision, reviewer, note):
    if decision not in ("approved", "rejected"):
        raise ValueError("Unknown review decision")
    text_field(reviewer, "reviewer", 100)
    text_field(note, "review note", 2000)
    row = conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
    if not row or row["version"] != version:
        raise ValueError("Missing record or stale version; inspect the current draft first")
    if row["catalog_hash"] != digest(catalog()[0]):
        raise ValueError("SPARTA catalog changed; reassess and re-import this record before review")
    validate_incident(json.loads(row["payload"]))
    stamp = now()
    conn.execute("INSERT INTO reviews VALUES (NULL,?,?,?,?,?,?)",
                 (incident_id, version, decision, reviewer, note, stamp))
    conn.execute("UPDATE incidents SET status=?,reviewer=?,reviewed_at=? WHERE id=?",
                 (decision, reviewer, stamp, incident_id))


def incidents(conn):
    result = []
    catalog_checksum = digest(catalog()[0])
    for row in conn.execute("SELECT * FROM incidents ORDER BY updated_at DESC,id"):
        item = dict(row)
        item["data"] = json.loads(item.pop("payload"))
        if item["status"] == "approved" and item["catalog_hash"] != catalog_checksum:
            item["status"] = "needs-review"
        item["score"] = sum(item["data"]["impact"][k] for k in ("mission", "scope", "recovery"))
        result.append(item)
    return result


def top_incidents(conn):
    rows = [r for r in incidents(conn) if r["status"] == "approved" and r["data"]["kind"] == "incident"]
    return sorted(rows, key=lambda r: (-r["score"], r["id"]))[:5]
