"""Deterministic articles: no model can invent facts or promote a source claim."""

import re

from .core import catalog, now, top_incidents


def md(value):
    # Keep user/source input inert when opened in third-party Markdown renderers.
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def article(record):
    d = record["data"]
    _, techniques = catalog()
    refs = lambda ids: " ".join("[" + sid + "]" for sid in ids)
    lines = ["# " + md(d["title"]), "",
             f"Status: {record['status'].upper()} · Version: {record['version']} · Kind: {d['kind']}",
             f"Event date: {d['event_date']} · Record updated: {record['updated_at']}",
             "", "## Overview", "", md(d["summary"]) + " " + refs(d["summary_sources"]),
             "", "Affected segment: " + md(d["segment"]),
             "", "## Evidence ledger", ""]
    for claim in d["claims"]:
        lines.append(f"- **{claim['certainty']}**: {md(claim['text'])} {refs(claim['sources'])}")
    lines += ["", "## Reported attack sequence", "",
              "Ordering reflects the public account. Missing intrusion details remain unknown.", ""]
    for i, step in enumerate(d["steps"], 1):
        lines.append(f"{i}. {md(step['text'])} ({step['certainty']}) {refs(step['sources'])}")
    lines += ["", "## SPARTA assessment", "", "Catalog snapshot: " + md(d["sparta_snapshot"]), "",
              "Mappings are analyst interpretations, not official incident attributions by Aerospace.", ""]
    for mapping in d["mappings"]:
        technique = techniques.get(mapping["technique"])
        if technique is None:
            lines += ["Former mapping " + md(mapping["technique"]) + " is absent from the current catalog; reassess before publication.", ""]
            continue
        lines += [f"### {technique['id']} — {md(technique['name'])}", "",
                  f"Confidence: {mapping['confidence']}. {md(mapping['rationale'])} {refs(mapping['sources'])}",
                  "", "Official definition: " + technique["url"], ""]
    if not d["mappings"]:
        lines += ["Unmapped: " + md(d["unmapped_reason"]), ""]
    lines += ["## Defensive recommendations", "",
              "These are proposed engineering controls, not claims about controls deployed by the victim.", ""]
    for control in d["controls"]:
        lines += [f"### {control['phase'].title()}: {md(control['action'])}", "",
                  md(control["why"]), "", "Validation: " + md(control["validation"]), ""]
    lines += ["## Impact assessment", "",
              f"Analyst priority: {record['score']}/15. Mission, scope and recovery each range from 0–5; this is not CVSS.",
              md(d["impact"]["rationale"]) + " " + refs(d["impact"]["sources"]),
              "", "## Limits and unknowns", "", md(d["limitations"]), "", "## Sources", ""]
    for source in d["sources"]:
        lines += [f"[{source['id']}] {md(source['title'])} — {source['url']}",
                  f"Published: {source['published_date']}; accessed: {source['accessed_date']}.", ""]
    if record["reviewer"]:
        lines += ["Reviewed by: " + md(record["reviewer"]) + " · " + record["reviewed_at"]]
    return "\n".join(lines) + "\n"


def briefing(conn):
    lines = ["# OrbitWatch briefing", "", "Generated: " + now(), "",
             "## Reviewed historical incident priorities", "",
             "These are the highest-scored approved incidents in this local corpus, not today's attacks or a global top five.", ""]
    ranked = top_incidents(conn)
    if not ranked:
        lines.append("No reviewed incidents qualify yet. Review evidence before approving records.")
    for row in ranked:
        lines.append(f"- {md(row['data']['title'])} — event {row['data']['event_date']}; {row['score']}/15; record {row['id']} v{row['version']}")
    lines += ["", "## Unverified source changes in the past 24 hours", ""]
    rows = conn.execute("SELECT * FROM candidates WHERE relevant=1 AND julianday(last_changed)>=julianday('now','-1 day') ORDER BY last_changed DESC LIMIT 50").fetchall()
    if not rows:
        lines.append("No matching changes were collected. This does not establish that no attacks occurred.")
    for row in rows:
        lines.append(f"- {md(row['title'])} — {row['url']} (publication: {row['published_at'] or 'unknown'}; first seen: {row['first_seen']})")
    lines += ["", "## Latest source collection status", ""]
    for row in conn.execute("SELECT * FROM runs WHERE id IN (SELECT MAX(id) FROM runs GROUP BY source) ORDER BY source"):
        lines.append(f"- {md(row['source'])}: {row['outcome']}; checked {row['started_at']}; " + md(row["error"] or f"{row['fetched']} items inspected"))
    return "\n".join(lines) + "\n"
