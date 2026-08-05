# Project Agent Instructions

## Absolute clean-room tape source of truth

The JavaScript simulation is being rebuilt from scratch. For every new
calibration, tape-forensics, or simulation-vs-tape task, the **only** permitted
tape archive is:

`aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`

Required SHA-256:

`33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`

### Initial intake authorization

The archive may initially be copied only from:

`C:\Users\ddk22\Downloads\aoe2_golden_basics_championvschampion_2026-08-04.zip`

Before copying, verify that the external file has the required SHA-256. Copy it
byte-for-byte into the project-local path above and verify the copied file has
the same SHA-256. After intake, use only the project-local copy.

### Non-negotiable rules

- Never inspect, extract, ingest, score, compare against, cite, or otherwise use
  any other tape archive or tape-derived truth corpus.
- The former standard-units archive and everything derived from it are legacy
  evidence and must not be used for this clean-room JavaScript simulation.
- Existing material under the old `calibration/` workflow must not be treated as
  evidence for the clean-room rebuild.
- All new extracted tapes, fixtures, manifests, reports, and simulation
  comparisons must live under `aoe2x/js_simulation/calibration/`.
- Before tape analysis, verify the project-local archive SHA-256.
- Every active clean-room manifest entry must record the required SHA-256 as
  `zip_sha256`.
- If no clean-room manifest exists yet, it may be bootstrapped only from the
  verified project-local archive.
- If the archive is missing or its hash differs, stop and ask the user. Never
  substitute another tape.
- Derived fixtures must be reproducible from the verified archive and must not
  be manually edited to fit simulation results.

This Champion-versus-Champion basics archive is the starting ground truth for
the clean-room simulator rebuild. Begin with the 1v1 matchup and expand only
after its mechanics and outcome distribution are understood.
