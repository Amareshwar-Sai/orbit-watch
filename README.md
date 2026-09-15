# OrbitWatch v0.1

A local space-security research pipeline with an evidence queue, versioned case
records, SPARTA assessments and review-controlled article export. Built as a
hands-on DevSecOps learning project.

**Start here:** [START-HERE.md](START-HERE.md). Python 3.12 or newer is the tested
target. The runtime has no third-party Python dependencies or paid API requirement.
Run it directly on macOS or Linux, including Kali ARM64 on an M1 Mac.

## First run

From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m orbitwatch seed
python3 -m orbitwatch serve
```

Open http://127.0.0.1:8000. The KA-SAT historical case starts as a **draft**.
Read its sources and mapping limitations before approving it. Stop with Ctrl+C.

## Implemented

- Read-only local dashboard: overview, evidence queue, case library, collection
  health, SPARTA references and downloadable article drafts.
- Bounded RSS/Atom ingestion, explicit-host HTTPS retrieval and reference-page
  change watching. NASA and NCSC starter feeds plus one SPARTA reference watcher.
- Publication time, discovery time and change time kept separate. Missing source
  dates stay unknown. Keyword filtering is a heuristic, not an incident classifier.
- URL deduplication with multiple source associations. Changed incident records
  receive a new version and lose their prior approval. Review decisions are logged.
- Deterministic Markdown articles from analyst-supplied evidence: reported facts,
  attack sequence, qualified mappings, defensive actions and validation exercises.
- Up to five approved real incidents ranked within the local corpus. Historical
  ranking is separate from newly collected source updates; no quota fabrication.
- One-shot daily collection/briefing and an optional daily worker.
- Non-root Docker packaging, loopback port mapping, capability removal and
  resource limits; GitHub CI with tests, Bandit, Gitleaks and Grype image scanning.
- Safe SQLite backup command and a recovery exercise.

## Deliberate first-version boundaries

This is an **evidence-first prototype**, not a fully autonomous intelligence service.
It does not scrape the entire internet, automatically determine what happened,
generate evidence with an LLM, or publish to a public website. Analysts manually
turn source leads into structured case records. Source-ID validation checks
structure; it does not prove that a citation supports a claim.

The included SPARTA catalog contains **one verified starter technique** (IA-0007).
It is explicitly a subset, not a complete framework import. The KA-SAT mapping is
qualified and partial, and does not establish spacecraft compromise. Only one
historical example is bundled; the application can store and rank additional cases.

The runtime does not need a ChatGPT plugin. GitHub integration would help us work
on the repository and diagnose CI together. SciSpace is optional for finding
research. Neither is connected by this package.

## Everyday commands

```bash
# Retrieve configured sources once. Nonzero exit means at least one source failed.
python3 -m orbitwatch collect

# Collect and write a dated Markdown briefing, including any source failures.
python3 -m orbitwatch daily

# Run once now, then every 24 hours while this foreground process stays alive.
python3 -m orbitwatch worker

# List cases and their current versions.
python3 -m orbitwatch list

# Inspect one draft.
python3 -m orbitwatch article ka-sat-2022

# Approve only after independently checking evidence and interpretation.
python3 -m orbitwatch review ka-sat-2022 --version 1 --decision approved --reviewer "Amareshwar" --note "Checked cited evidence and qualified ground-segment mapping."

# Publication-ready export is gated on that exact version's approval.
python3 -m orbitwatch article ka-sat-2022 --approved-only --output var/articles/ka-sat-v1.md

# Import an edited or new structured case.
python3 -m orbitwatch import path/to/case.json

# Back up an active database using SQLite's backup API.
python3 -m orbitwatch backup var/backups/orbitwatch-01.db
```

Exports and backups refuse to overwrite an existing output path. Use a new name.
Database selection is a global option and must precede the command:

```bash
python3 -m orbitwatch --db var/learning.db seed
```

## Docker (optional second step)

Docker Engine/Compose or Docker Desktop must already be available. The following
configuration is supplied but was **not executed in the build workspace**.

```bash
docker compose build
docker compose run --rm dashboard python -m orbitwatch seed
docker compose up -d dashboard
```

Open http://127.0.0.1:8000. To opt into daily collection:

```bash
docker compose --profile daily up -d
docker compose logs collector
```

Editorial commands use the shared named volume:

```bash
docker compose exec dashboard python -m orbitwatch list
docker compose exec dashboard python -m orbitwatch daily
```

Stop services with `docker compose --profile daily down`. This leaves the named
data volume intact. Avoid `down -v` unless you intend to delete stored research.
Local Python and Docker use separate databases by default. Do not run both
dashboards on port 8000 at once. Use `--port 8001` for a second native instance.

## Learn and extend

- [Learning sequence](docs/LEARNING.md): what to build, break and prove at each stage.
- [Architecture and data model](docs/ARCHITECTURE.md).
- [Security controls and remaining work](docs/SECURITY.md).
- [Research and editorial rules](docs/EDITORIAL.md).
- [Validation results and limitations](docs/VALIDATION.md).

SPARTA is created by The Aerospace Corporation. This project is independent and
does not imply endorsement by Aerospace, Viasat, NASA or NCSC. Third-party reports
are linked and briefly paraphrased, not redistributed in full.
