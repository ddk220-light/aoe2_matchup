# Standing working instructions

## Avoid unnecessary work and use judgment

- Before expensive or repetitive work, verify what actually needs to change. Compare existing artifacts and actual inputs, counts, stats, rules, and captured results. A different policy label or an unavailable disk is not evidence that recordings must be redone.
- Reuse valid work. Identify the smallest necessary set of corrections and explain the exact scope and reason before starting. Never launch a full rerun based on an unverified assumption or merely to be safe.
- Push back clearly when the user's proposed method would waste time or duplicate valid work. Explain the evidence and propose the smaller action that achieves their goal. Do not blindly execute an unnecessary request. Respect an explicit decision to proceed after that explanation.
- Keep verification proportional: perform the checks needed to settle the decision, then act. Do not substitute redundant testing, broad audits, or documentation for progress.
- If unnecessary work is already running, stop it at a safe boundary, preserve completed results, and report the mistake and remaining necessary work plainly.
- For capture reuse and the prior rerun mistake, read [the minimal retake audit](docs/video-production/KNIGHT_MINIMAL_RETAKE_AUDIT.md). Compare actual counts and capture conditions; do not infer incompatibility from version names.

## Disk safety

- Never format, reformat, initialize, erase, or repartition disks, or suggest formatting. The user handles that personally.
- Do not delete or overwrite existing external-drive contents without explicit authorization for those contents.
- If a drive is inaccessible, preserve sources and report the limitation; do not alter its filesystem or partition layout.

## Git publication scope and reusable assets

- Follow [the Git asset policy](docs/GIT_ASSET_POLICY.md). Source, documentation, workflows, learnings and the owner's explicitly selected reusable unit library belong in Git. Generation alone does not authorize retaining a new asset.
- Before **every Git push**, obtain an independent requirements/scope review of the exact current user request, destination ref, live remote tip, complete outgoing commit range, changed paths, binary inventory and newly reachable object sizes. Inspect earlier unpushed commits, not just the latest commit or staged diff.
- Proceed only within the user's publication authorization and with no unresolved scope mismatches. Routine in-scope review is automatic; ask the user only for new authority or a material ambiguity. If independent review is unavailable, stop before pushing and report it. Re-review if the candidate or remote changes.
- Use explicit staging paths and an explicit publication target. Never force-add ignored media as a shortcut or publish local recovery refs with `--all`, `--mirror`, or an indiscriminate ref/tag push.
- Generated/scratch media is local-only unless selected for retention. New workflows write outputs directly into `data/local/generated/` or existing ignored output directories; keep reusable source/helpers in tracked source directories. Preserve the exact approved asset paths and save experiments elsewhere instead of overwriting them.
- Size is evidence to compare with approved scope, not a substitute for scope. A deliberately approved large asset library may be valid; a small documentation request does not authorize uploading it or unrelated earlier commits.
- These are required agent review instructions plus standard Git ignore rules, not an installed native hook or a claim of tamper-proof enforcement. They do not grant push, deployment, production or deletion authority.
