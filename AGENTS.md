# Project Agent Instructions

## Clean-room tape sources of truth

The JavaScript simulation is being rebuilt from scratch. Every tape archive
used for calibration, tape forensics, or simulation-vs-tape work must be an
explicitly authorized golden archive, stored project-locally under:

`aoe2x/js_simulation/calibration/source/`

The original Champion-versus-Champion archive remains authorized for its
clean-room matchup corpus:

`aoe2x/js_simulation/calibration/source/aoe2_golden_basics_championvschampion_2026-08-04.zip`

Required SHA-256:

`33F4051CB1BE014CDF1D3813E7AB74EF619B468CB6196B5E92E7482508AA1BDE`

The expanded **standard-units golden archive is also authorized** for multi-unit
calibration and simulation comparisons. Its exact project-local filename and
SHA-256 must be recorded in the active clean-room manifest before use.

### Archive intake authorization

The Champion archive may initially be copied only from:

`C:\Users\ddk22\Downloads\aoe2_golden_basics_championvschampion_2026-08-04.zip`

The standard-units golden archive may be copied from the user-designated local
source after its exact filename and SHA-256 have been established.

Before copying an archive, verify the external file's SHA-256. Copy it
byte-for-byte into the project-local source directory, verify the copied file
has the same SHA-256, and record that hash in the active clean-room manifest.
After intake, use only the project-local copy.

### Non-negotiable rules

- Use only explicitly authorized golden archives whose project-local file and
  SHA-256 are recorded in the active clean-room manifest.
- The standard-units golden archive is permitted. Do not substitute an older,
  unmanifested standard-units archive or tape-derived corpus for it.
- Existing material under the old `calibration/` workflow must not be treated as
  evidence for the clean-room rebuild.
- All new extracted tapes, fixtures, manifests, reports, and simulation
  comparisons must live under `aoe2x/js_simulation/calibration/`.
- Before tape analysis, verify the selected project-local archive SHA-256.
- Every active clean-room manifest entry must record the selected archive's
  SHA-256 as `zip_sha256`.
- If no clean-room manifest exists yet, it may be bootstrapped only from a
  verified, explicitly authorized project-local golden archive.
- If the archive is missing or its hash differs, stop and ask the user. Never
  substitute another tape.
- Derived fixtures must be reproducible from the verified archive and must not
  be manually edited to fit simulation results.

The Champion-versus-Champion basics archive is the original focused ground
truth. The standard-units golden archive is the expanded ground truth for
multi-unit movement, target acquisition, and fight-outcome comparisons.
