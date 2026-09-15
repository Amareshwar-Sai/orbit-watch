# Research rules

## From lead to case

1. Inspect a lead's original source. Find an operator statement, government
   advisory or original research where possible. Record exact URLs and dates.
2. Reuse the structure in `data/incidents/ka-sat-2022.json` to create a new file.
   Give each distinct incident one stable ID; attach multiple reports as sources.
3. Set `kind` to `incident`, `research` or `hypothetical`. A lab exploit or CTF is
   not an operational incident. A general vulnerability report is not evidence
   that someone exploited it against a spacecraft.
4. Write each factual claim and attack stage with source IDs. Label it `reported`
   for a source account, `corroborated` for independently checked evidence, or
   `inference` for your interpretation. The application cannot determine source
   independence; you must justify corroboration during review.
5. Do not fill gaps with plausible exploit steps. State what remains unknown.
6. Check each SPARTA definition against the affected segment and observed
   behaviour. Add its exact identifier to the verified catalog before use. Set
   `mappings` to an empty list and supply `unmapped_reason` if evidence is inadequate.
7. Explain proposed controls and how they could be tested in an isolated lab.
   Separate these proposals from claims about measures actually deployed by the victim.
8. Explain your impact scores and source them. Imported records start as drafts;
   review the current version before any approved-only export.

## Dates and scope

Event date, source publication date and access date are different. Newly finding
a 2022 report does not turn it into a 2026 incident. A changed SPARTA reference
page is a framework update, not a new attack. Do not treat publication order as
an intrusion timeline.

## Source coverage

The initial NASA/NCSC feeds are general feeds and can miss important incidents.
Keyword filtering can produce false positives and false negatives. Inspect filtered
reports using the queue checkbox. Add sources intentionally in `config/sources.json`:
both the URL and host must be configured. This is a bounded feed reader, not an
automatic crawler, full-text archive or paywall bypass.

Retrieved feeds may contain brief publisher-provided excerpts. Do not bulk publish
those excerpts or entire reports; write your own evidence-backed analysis and link
to originals. The page watcher stores a hash, not the complete article body.

## SPARTA attribution and versioning

SPARTA is by The Aerospace Corporation: https://sparta.aerospace.org/.
The starter subset was checked on 2026-09-15; it is not a claim to include every
technique or the full released framework version. When you change the subset,
change its snapshot identifier and reassess affected case records before approval.
The official framework contains deprecated techniques, so do not copy an old ID
from a paper without checking its current page.

The KA-SAT record intentionally uses a qualified, medium-confidence IA-0007
mapping. That mapping is an analyst interpretation and not an official Aerospace
mapping of the Viasat incident. It does not assert on-orbit execution.

## Review note

A useful note states what you checked, what remains uncertain, and why the mapping
is defensible. A source link existing is insufficient. Review the assertion itself.
The local reviewer name is an audit label, not an authenticated or cryptographically
verified identity.
