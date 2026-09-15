# Your first OrbitWatch session

Goal: run the project, understand one case, and see how evidence review becomes a
testable software workflow. You can do this directly on your Mac; Kali is optional.

## 1. Extract and enter the project

Download `OrbitWatch-v0.1.zip`, extract it, and open a terminal inside the
`OrbitWatch` folder. For example, if you extracted it under Downloads:

```bash
cd ~/Downloads/OrbitWatch
python3 --version
```

Use Python 3.12 or newer for the supported learning setup. No `sudo pip`, global
package installs or Python dependencies are required for this first run.

## 2. Run the checks

```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests finish with `OK`. They use temporary databases and controlled
network fixtures; they do not need external websites. The HTTP tests briefly start
a server on a random loopback port and stop it automatically.

## 3. Load your first case and open the dashboard

```bash
python3 -m orbitwatch seed
python3 -m orbitwatch serve
```

Open **http://127.0.0.1:8000** in your browser. Choose **Case library**, then KA-SAT.
This is a historical draft, not an alert about a new attack. Leave the terminal
running while you use the dashboard.

The first useful distinction to learn: a source reports facts; you make an
assessment; review approves a specific assessment version. Those are three
different things.

## 4. Try a real collection

Open a second terminal in the same project directory:

```bash
python3 -m orbitwatch collect
```

Then inspect **Source health** and **Evidence queue**. General NASA/NCSC feeds may
contain no relevant security reports. A SPARTA page watcher entry is a reference
change, not an attack. Uncheck your expectations of a fixed daily attack count:
the system should show what it actually found.

If you see a DNS, HTTP, certificate or size error, the source failed. Do not remove
the network safeguards to make a run look successful. See the troubleshooting
section below and share the actual error when asking for help.

## 5. Follow the evidence before approving

Open the linked operator report. Check the reported network entry path, effects
on terminals and limits on the spacecraft claim. Read the IA-0007 definition.
Decide whether the qualified mapping is appropriate. Edit the JSON if it needs
correction, then import it before approving the new version.

```bash
python3 -m orbitwatch list
python3 -m orbitwatch review ka-sat-2022 --version 1 --decision approved --reviewer "Amareshwar" --note "Checked source claims and the limits of the SPARTA mapping."
python3 -m orbitwatch article ka-sat-2022 --approved-only --output var/articles/ka-sat-v1.md
```

The command above assumes the case is still version 1; use the actual number
shown by `list`. Approval is your editorial judgement, not independent verification
by the software.

## 6. Prove that a correction needs another review

Make a small, truthful clarification in `data/incidents/ka-sat-2022.json`. Then:

```bash
python3 -m orbitwatch import data/incidents/ka-sat-2022.json
python3 -m orbitwatch list
python3 -m orbitwatch article ka-sat-2022 --approved-only
```

Expected: a new draft version and a blocked approved-only export. The old version
and review decision remain in the database history. This is your first practical
security gate: a code-enforced rule, with regression tests proving it works.

## Troubleshooting

- `No module named orbitwatch`: the terminal is outside the extracted project
  root. Enter the folder containing `README.md` and the `orbitwatch/` directory.
- `Address already in use`: stop the previous instance, or run
  `python3 -m orbitwatch serve --port 8001` and open the matching local address.
- `Temporary failure in name resolution`: check the host/VM internet connection
  and DNS. The supplied tests remain usable offline.
- `HTTP 301/302`: redirects are blocked intentionally. Verify the new feed address
  at the publisher's site, then update both URL and explicit host allowlist.
- `HTTP 403` during collection: the source may reject automated clients. Choose a
  permitted feed or add the source manually; do not bypass access restrictions.
- `Use the local dashboard address`: browse using `127.0.0.1` or `localhost` with
  the exact port. The Host check is a DNS-rebinding protection.
- `Source exceeds the 1 MiB limit`: choose a smaller official feed or add a bounded
  pagination adapter in a reviewed change. Do not make the downloader unlimited.

After this session, continue with `docs/LEARNING.md`. The next milestone is making
the same checks run automatically on a pull request.
