"""Army economics: offline data pipeline for the "60-second army investment".

Published as static per-civilization files + /api/economy (no UI yet). See docs/army-economics/README.md.

Modules:
  accounting      purchase bills, 60-second production, labor LP and its compiled dual, research totals
  matchup         evaluate a head-to-head pair from the compiled runtime (Python reference)
  compiler        reviewed source snapshot -> data/army_economics/army_context.jsonl.gz (+ local .db)
  artefact        committed JSON Lines artefact: format, reader and published documents (stdlib only)
  curated         hand-curated, cited corrections and owner decisions applied by the compiler
  policy          owner-approved scope exclusions and validation policy
  special_economy civ gathering mechanics added to the reviewed gathering vectors
  observations    validator for future in-game gathering measurements
  restore         checksum-verified restore of the compressed sources
  paths           repository locations
"""
