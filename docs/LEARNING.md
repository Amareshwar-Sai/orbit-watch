# Learn DevSecOps by changing OrbitWatch

Work through these milestones in order. Each should produce something you can
show and explain in an interview. Finishing the project means being able to
diagnose a failed test or risky change, not just running a scanner successfully.

## Milestone 1 — Evidence and software behaviour

Run `START-HERE.md`. Read `core.py`, then follow one case through import, draft,
review and export. Locate the tests proving that a revision revokes approval.

Why it matters: security requirements need enforceable behaviour. A rule in a
README can be ignored; a tested export gate rejects an invalid state.

Deliverable: show a successful draft import, a blocked unapproved export, an
approval, then a corrected draft that needs review again. Explain why an old
approval cannot cover new text.

## Milestone 2 — Git and continuous integration

Create your own repository from this folder and inspect `.gitignore` before adding
files. Do not commit `var/`, local databases or environment secrets. The included
workflow will run when placed at the repository root under `.github/workflows/`.
The GitHub plugin is optional; your repository and Actions work independently.

```bash
git init -b main
git add .
git status
git commit -m "Start OrbitWatch evidence pipeline"
```

Set your Git author identity if prompted. Create/select the intended GitHub repo
and add its actual remote using your own authenticated Git workflow. No remote
has been created or configured by this package.

Use a branch for your first change. Add a legitimate source keyword and a test
explaining a false negative it fixes. Open a pull request, inspect the CI jobs,
and review the diff before merging. Configure branch protection to require checks
once you've run them successfully; the YAML alone does not enforce merge policy.

Deliverable: a reviewed PR with passing tests and scanner results. Explain the
difference between a test failure, a vulnerability finding and a scanner outage.

## Milestone 3 — Threat modelling and security regression

Read `docs/SECURITY.md` and `net.py`. Trace how a source URL becomes a socket.
Explain why checking a hostname before making an unrelated second DNS lookup is
insufficient, and why the TLS certificate must still be checked against the name.

Exercises:

1. Run the mixed public/private DNS test and explain why the whole answer set is
   rejected.
2. Run the malicious XML test and identify the entity-expansion trust boundary.
3. Place harmless `<script>` text in a test case title. Check that the dashboard
   displays text rather than executing it.
4. Attempt a review against an old version and explain the error.

Use local test fixtures. Do not scan or attack third-party satellites or networks.

Deliverable: a short threat model with assets, trust boundaries, attack paths,
controls and remaining risk, backed by the tests you can demonstrate.

## Milestone 4 — Containers and vulnerability management

Build using the README Docker commands. Inspect the image user and Compose
configuration. Explain why dropping capabilities, removing root and limiting
resources help even for a local service.

```bash
docker compose exec dashboard id
docker compose exec dashboard python -m orbitwatch list
docker compose ps
```

Expected user UID/GID: 10001. The root filesystem should be read-only while the
research volume remains writable. A read-only filesystem is not a replacement
for input validation, and a non-root process can still damage data it owns.

Run image scanning through CI, inspect each finding and update the base image
where appropriate. Do not suppress everything to get a green badge. Record any
justified exception with scope, owner and expiry in a later policy mechanism.

Deliverable: image scan report, an explanation of a real finding, and a reviewed
fix/rebuild. Then improve tag pinning to verified digests and add SBOM generation.

## Milestone 5 — Daily operation and recovery

Run one daily collection before enabling the long-running worker:

```bash
python3 -m orbitwatch daily
```

Check the dated briefing and source outcomes. A machine that sleeps or is turned
off will not collect; restarting the worker runs again but does not reconstruct
missed feed history. An always-on host and a proper scheduler come later.

Practice backup and recovery using a new destination:

```bash
python3 -m orbitwatch backup var/backups/exercise-01.db
python3 -m orbitwatch --db var/backups/exercise-01.db list
python3 -m orbitwatch --db var/backups/exercise-01.db serve --port 8001
```

Compare case counts and review status with the original. Stop the restored test
instance with Ctrl+C. Do not overwrite the original database to test recovery.

Deliverable: a recovery note with backup time, restore verification and measured
recovery duration. Add a tested external failure notification only after choosing
and authorising its destination.

## Milestone 6 — Better intelligence and optional AI

Expand to several independently reviewed incidents. Measure citation correctness,
incident deduplication and SPARTA mapping agreement on a small labelled benchmark.
Make sure the benchmark contains non-incidents and ambiguous examples.

Then add an optional extractor with structured outputs, source-span references,
cost limits, retry limits and an offline test mode. Keep its output in draft status.
Compare its claims against your manual evidence set before accepting it as a useful
research assistant. The application must function without the model provider.

Deliverable: measured extraction quality with examples of failures and corrections,
not only a successful demo. This is where the product becomes an assisted article
generator rather than a deterministic evidence publisher.

## Milestone 7 — Continuous delivery

Only after the local pipeline is understood: separate staging and production,
choose a host, add authentication, deploy a signed artifact, exercise rollback,
and make publication approval independent from code deployment approval.

Deliverable: a release with a traceable commit, test/scan results, SBOM, signature,
deployment record and rollback drill. None of these deployment steps is claimed
complete in v0.1.
