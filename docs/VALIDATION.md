# Validation record — 2026-09-15

## Executed in the build workspace

Environment: Linux, Python 3.12.14. The project uses no third-party runtime Python
packages. The tests run with `python3 -m unittest discover -s tests -v`.

- **37 tests passed**, including actual loopback HTTP requests and a subprocess
  CLI workflow that imports, reviews, exports and restores from a backup.
- Python compilation checks passed for application, tests and Python scripts.
- Every dashboard route returned HTTP 200; unknown/traversal paths returned 404.
- The health endpoint returned success and responses carried CSP and nosniff headers.
- SSRF/DNS pinning, hostile XML, output escaping, review versioning, catalog change
  invalidation, historical ranking, deduplication and partial collection failure
  behaviour were tested with controlled fixtures.
- Existing output files and backups survived overwrite attempts unchanged.

## Live collection attempted, not verified successful

All three configured sources failed DNS resolution in this restricted workspace.
Each failure appeared in the run log and the collector returned a nonzero status.
The feed URLs were identified from official publisher pages, but end-to-end
retrieval and parsing of their live responses must be tested on your network.

This is not evidence that the feeds themselves are down. Controlled RSS/Atom
fixtures validate the parser and failure handling, not ongoing source availability.

## Not executed here

- Docker build, Compose startup, non-root container smoke test and image scan:
  Docker is unavailable in this workspace.
- Bandit, Gitleaks and Grype: scanner executables/images are unavailable and require
  external downloads. CI configuration is supplied, but no passing CI run is claimed.
- Browser screenshots and visual inspection: Playwright is present, but its
  Chromium browser binary is absent. The optional `scripts/visual-check.cjs` was
  attempted and could not launch a browser. HTTP route/content checks passed;
  visual correctness across devices is not yet verified.
- Long-duration daily worker operation, real source retention and recovery under
  machine sleep/reboot.
- macOS/ARM64 and Kali execution: supported by the portable standard-library
  design, but not executed on those platforms in this build workspace.

## Your first acceptance checks

1. Run the 37 tests on your machine.
2. Seed and open the dashboard; check the overview, queue and case pages visually.
3. Run one `collect`; inspect source health, including all errors.
4. Read the seed case's sources, approve the current version, and export it.
5. Enable CI in your repository, then inspect the actual scanner/build results.

For optional browser QA, install Playwright/Chromium in your own development
environment, start the dashboard, then run `node scripts/visual-check.cjs`.
The screenshot command writes under ignored `var/screenshots` and checks for
horizontal overflow at desktop/mobile widths.
