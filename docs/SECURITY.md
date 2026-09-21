# Security model and limits

## Trust boundaries

Untrusted: remote feeds, titles, excerpts and referenced pages.
Trusted for this local prototype: the machine owner, project configuration,
incident JSON files and the CLI reviewer. No external LLM receives content or has
tools in v0.1. The app does not execute article text or use it as instructions.

## Controls implemented

| Threat | Control | Evidence |
| --- | --- | --- |
| SSRF into private networks | Exact allowlist, HTTPS only, no credentials/ports/IP literals, all DNS answers must be public | URL/DNS regression tests |
| DNS rebinding during fetch | Connect to a checked numeric address while verifying TLS against the original hostname | Pinned connection test |
| Redirect to internal host | No automatic redirect following | Redirect rejection test |
| Oversized/decompression response | 1 MiB cap, streamed limit, reject compression, socket/read deadlines | Length/stream tests |
| XML external entities | Strict bounded UTF-8, reject DTD/entity declarations before parsing | Malicious XML and UTF-16 tests |
| Stored script content | Feed plain-text extraction; HTML escaping; no JavaScript; restrictive CSP | XSS and HTTP header tests |
| Remote editorial mutation | Dashboard provides GET routes only; review is a CLI operation | POST rejection test |
| DNS-rebinding into dashboard | Loopback binding and exact Host validation | Host-header test |
| SQL injection | Bound SQLite parameters | Search payload regression test |
| Unsupported citations/techniques | Reference IDs and subset membership validated; deprecated entries refused | Validation tests |
| Stale approval | Case updates reset approval; version required for review; catalog hash changes invalidate approval | State-transition tests |
| Overstated top-five list | Only approved real incidents, capped at five; historical corpus explicitly labelled | Ranking tests |
| Lost research | SQLite backup API with overwrite refusal | Recovery exercise in learning guide |

## Local operation

The Python standard-library HTTP server is intended for local use only. It is not
a production server and is not authenticated. Anyone with access to this user's
machine/browser session can read the local dashboard. Filesystem permissions
protect the data from other users; they do not protect it from a compromised
account. The Docker `--container` mode binds all interfaces inside the container,
so retain Compose's host mapping `127.0.0.1:8000:8000`.

The application is not a hardened multi-user service. Add authentication, TLS,
request-rate/concurrency limits and a supported server before internet exposure.
OS-level egress restrictions can further isolate a deployed collector. DNS lookup
timeouts follow the operating system resolver; the 10-second socket timeout does
not enforce a resolver deadline. Resource limits help bound parser/server load.

## CI gates supplied

- Regression tests must pass.
- Bandit medium/high findings block the test job. Narrow `nosec` annotations
  document the guarded XML parser and Docker binding; review those exceptions.
- Gitleaks scans checked-out source files with redacted findings. This initial
  workflow does **not** scan every historical commit.
- Grype scans the built image's packages and blocks high/critical findings,
  including findings without an available fix. Registry/DB failures also fail the
  job; they are not silently interpreted as a clean scan.
- Checkout uses a full commit SHA and does not persist credentials. Workflow
  permissions are read-only. No deployment token or publication operation is used.

The scanners have not been executed in the restricted build workspace. Their
workflow must be exercised on GitHub before it is described as a passing CI gate.

## Supply-chain work still to do

The Python image and scanner container versions use tags, not immutable digests.
Bandit's direct version is pinned, but its transitive dependencies are not yet
hash-locked. This package therefore does **not** claim reproducible or signed
builds. In the next hardening milestone, resolve trusted image digests, inspect
provenance, generate a hash-locked development requirements file, generate an SBOM
and sign release artifacts. Do not invent digests or pretend unverified hashes
establish provenance.

Dependabot configuration is supplied for Python requirements, Dockerfile and
GitHub Actions. It does not automatically maintain every container tag embedded
in shell commands; review the scanner tags explicitly.

No runtime Python dependencies does not mean no vulnerabilities: the interpreter,
OpenSSL, SQLite and base OS need updates. Container scanning covers that risk more
directly than an empty application `pip` dependency audit.

## Operational work still to do

There is no external failure notification, retention policy, rate-limited public
API, cloud deployment, full-text evidence archive or tamper-proof audit log.
Review source health regularly. Protect backups according to the sensitivity of
your research. Raw incident export is a local capability, not a network permission.

For later LLM integration, retrieved text must remain untrusted data. An extractor
should have no shell, credential or publishing access, should return schema-bound
drafts with evidence spans, and must never approve its own output. These are design
requirements for the future integration, not a claim that AI injection has already
been tested here.

## Official tool references

- Bandit: https://bandit.readthedocs.io/
- Gitleaks: https://github.com/gitleaks/gitleaks
- Grype: https://github.com/anchore/grype
- Secure software development framework: https://csrc.nist.gov/projects/ssdf


## Temporary container vulnerability exceptions

Grype scans the application image for known vulnerabilities.
Unaccepted High and Critical findings fail CI.

Specific exceptions are recorded in config/grype.yaml.
Each rule identifies a CVE, package, version and review reason.
Accepted findings remain visible in scan output as suppressed.

These exceptions are temporary risk acceptances for local learning
and CI. They do not mean the vulnerabilities have been fixed or
that the image is approved for public deployment.

The reviewed runtime uses:

- A non-root user (UID 10001).
- A read-only root filesystem.
- All Linux capabilities dropped.
- No-new-privileges enabled.

Some affected components were absent in our local checks.
Others remain installed, with restricted attack conditions or
uncertainty about whether the application can reach the affected code.

Reassess exceptions when application code, installed packages or
runtime settings change. The CI review deadline is 2026-10-20;
the workflow stops at that date until the exceptions are reviewed.
