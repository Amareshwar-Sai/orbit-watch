import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .articles import article, briefing
from .core import ROOT, database, import_incident, incidents, read_json, review
from .ingest import collect, config_at
from .web import serve


def write_new(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)
    print(path.resolve())


def main(argv=None):
    parser = argparse.ArgumentParser(description="OrbitWatch local research pipeline")
    parser.add_argument("--db", default=os.environ.get("ORBITWATCH_DB", "var/orbitwatch.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    sub.add_parser("seed")
    imp = sub.add_parser("import")
    imp.add_argument("file")
    sub.add_parser("list")
    rev = sub.add_parser("review")
    rev.add_argument("id")
    rev.add_argument("--version", type=int, required=True)
    rev.add_argument("--decision", choices=["approved", "rejected"], required=True)
    rev.add_argument("--reviewer", required=True)
    rev.add_argument("--note", required=True)
    export = sub.add_parser("article")
    export.add_argument("id")
    export.add_argument("--output")
    export.add_argument("--approved-only", action="store_true")
    for name in ("collect", "daily", "worker"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", default=str(ROOT / "config/sources.json"))
        if name != "collect":
            cmd.add_argument("--output-dir", default="var/briefings")
    sub.add_parser("briefing").add_argument("--output")
    backup = sub.add_parser("backup")
    backup.add_argument("output")
    web = sub.add_parser("serve")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--container", action="store_true", help="Bind all container interfaces; use loopback Docker port mapping")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == "serve":
            if not 1024 <= args.port <= 65535:
                raise ValueError("Use a port from 1024 to 65535")
            serve(args.db, args.port, args.container)
            return 0
        if args.command == "worker":
            # Daily project automation; starting this process opts into network retrieval.
            while True:
                result = run_daily(args)
                print(json.dumps({"daily_exit": result}), flush=True)
                time.sleep(86400)
        with database(args.db) as conn:
            if args.command == "init":
                print("Database ready:", args.db)
            elif args.command == "seed":
                for path in sorted((ROOT / "data/incidents").glob("*.json")):
                    print(path.name, import_incident(conn, read_json(path)))
            elif args.command == "import":
                print(import_incident(conn, read_json(args.file)))
            elif args.command == "list":
                for row in incidents(conn):
                    print(f"{row['id']}  v{row['version']}  {row['status']}  {row['score']}/15  {row['data']['kind']}")
            elif args.command == "review":
                review(conn, args.id, args.version, args.decision, args.reviewer, args.note)
                print(args.id, args.decision, "version", args.version)
            elif args.command in ("article", "briefing"):
                if args.command == "article":
                    row = next((r for r in incidents(conn) if r["id"] == args.id), None)
                    if row is None:
                        raise ValueError("Unknown incident ID")
                    if args.approved_only and row["status"] != "approved":
                        raise ValueError("Export blocked: this version is not approved")
                    content = article(row)
                else:
                    content = briefing(conn)
                write_new(args.output, content) if args.output else print(content)
            elif args.command == "backup":
                path = Path(args.output)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb"):
                    pass
                destination = sqlite3.connect(path)
                try:
                    conn.backup(destination)
                finally:
                    destination.close()
                print("Backup created:", path)
            elif args.command == "collect":
                results = collect(conn, config_at(args.config))
                print(json.dumps(results, indent=2))
                return int(any(r["outcome"] != "ok" for r in results))
        if args.command == "daily":
            return run_daily(args)
        return 0
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
        print("OrbitWatch:", exc, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def run_daily(args):
    with database(args.db) as conn:
        results = collect(conn, config_at(args.config))
        print(json.dumps(results, indent=2), flush=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        write_new(Path(args.output_dir) / f"briefing-{stamp}.md", briefing(conn))
        return int(any(r["outcome"] != "ok" for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
