# Project Agent Instructions

## Absolute tape source of truth

For every calibration, tape-forensics, or simulation-vs-tape task, the **only**
permitted tape archive is the ignored project-local file named by
`calibration/source/source_of_truth.json`.

Required SHA-256:
`31A31FE39C025DDD88EB1F502FD62E0EC48464F4CBB72C1693D5C4FEED0713C9`

This rule is non-negotiable:

- Never inspect, extract, ingest, score, compare against, cite, or otherwise use
  any other tape archive or tape-derived truth corpus.
- Never search the historical external workspace for replacement tapes.
- Only material regenerated through the verified project-local workflow is
  current evidence.
- Before tape analysis, verify the allowed archive's SHA-256 and confirm every
  active `calibration/fixtures/manifest.json` entry has that same `zip_sha256`.
- If the allowed file is missing or its hash differs, stop and ask the user. Do
  not substitute another tape.

Canonical details: `calibration/docs/TAPE_SOURCE_OF_TRUTH.md`.
