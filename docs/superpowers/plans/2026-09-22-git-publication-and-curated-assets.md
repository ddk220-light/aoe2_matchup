# Clean Git Publication and Curated Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the user approves it. Steps use checkbox (`- [ ]`) syntax for tracking. Do not start implementation from the existence of this document.

**Goal:** Retain useful source, documentation, workflows and deliberately selected reusable assets, while excluding unapproved generated media from the pending push and from ordinary staging immediately after generation.

**Architecture:** Use standard, committed Git ignore rules with exact-path exceptions for approved assets. Preserve existing asset paths and consumers. Rebuild only the unpublished local commits from the verified remote tip, preserving all files on disk and the original history in a local recovery branch. Independent scope review covers the entire outgoing range before any later push.

**Tech Stack:** Existing Git for Windows, PowerShell, `.gitignore`, repository instructions and Markdown; no new services, dependencies, custom hooks or asset-management framework.

**Spec:** The user's requirements in this document are the specification. Initially a planning-only deliverable dated 2026-09-22; the owner subsequently approved local implementation and clarified that the complete existing reusable unit library must be retained. No push is authorized.

## Approved refinement and execution status

The owner's follow-up selected the full per-unit library, including game/transparent icons, native and enhanced idle sprites, blue-team sprites, attack animations and final unit illustrations. The exact current set is **1,548 files across 223 unit folders, 1,102,507,305 bytes (1,051.43 MiB)**. It is recorded in `docs/GIT_ASSET_POLICY.md` and as exact `.gitignore` exceptions. The 17 YouTube covers remain local-only; already-published art, including the explicit Temple Guard golden set, stays unchanged. No standalone idle-animation GIFs/WebPs exist in this unit library, so none are fabricated or regenerated.

An additional untracked `graphics/ASSET_INVENTORY_2026-09-22.md` appeared after planning. It has been identified and left unchanged and outside staging. Its baseline raw Git blob ID is `041ba88dcfb5ac48a550ca4ef9b8728681c44cbd`.

During validation, two concurrent changes appeared in `graphics/units/flemish_militia/icon.png` and `icon_transparent.png`. They are reconciled as other work: preserve their current working files, leave those edits uncommitted, and retain the pinned original versions in the replacement commit using index-only restore. Do not write the old versions over the newer working files. Stop if other unexpected changes appear.

The same concurrent asset-completion work subsequently created `graphics/asset_completion_2026-09-22/` source/scripts/manifests. Reconciliation: preserve that directory unchanged by this task and outside staging; do not ignore valuable source or adopt it merely to obtain a clean working tree. The final commit check uses the exact staged path/content set, while unrelated untracked files remain outside the commit.

| Task | Status |
| --- | --- |
| 1. Selection, baseline and recovery | Complete: user scope mapped to finalized asset families; source/remote verified; local recovery ref created; all 1,565 original images hash-match |
| 2. Automatic exclusions and instructions | Complete: all 1,548 exact asset exceptions, 9 generated-output probes and source eligibility checks passed |
| 3. Reconstruct unpublished history | Complete: mixed reset to verified base; 41 source/policy files and 1,548 pinned unit assets staged; 17 covers ignored and preserved locally |
| 4. Verify, commit and independent review | Content and ignore checks passed; local commit and final independent review pending; no push authorized |

## Global constraints / user requirements

- Keep valuable code, documents, workflows and learnings.
- Generated assets are not automatically redundant: the owner may deliberately retain reusable angle-specific GIFs or other assets in Git.
- Do not infer approval of all GIFs, all images, or a filename family from the user's description of some useful files.
- Unapproved generated media must be excluded by existing Git mechanisms at creation, not sorted only when pushing.
- Preserve local assets, raw recordings, external-drive contents, and already-published application assets.
- No rendering, simulation runs, model downloads, new cloud storage, infrastructure changes, deployments, or broad test suites.
- No force-push, remote history rewrite, `git clean`, `git reset --hard`, recursive deletion, or wholesale `git add .` / `git add -A`.
- Review this plan locally and ask for user approval before implementation.
- Approval to implement this plan permits the described local edits, local recovery ref, mixed reset and replacement local commit only. It does not authorize a push, deployment, or production operation.

## Verified starting point

| Item | Observed value |
| --- | --- |
| Repository | `D:/AI/aoe2_matchup` |
| Local branch | `codex/video-recorder-v3` |
| Local source snapshot | `563825f43b3e7d1d71155b3b90be7d2574f106ec` |
| Live remote branch tip at audit | `251f6befa2986d04fafe8556ace4682ad253ae2a` |
| Outgoing history | Six local commits; 1,603 changed paths |
| Valuable non-image changes | 38 paths; under 0.5 MiB of current file contents |
| Generated image changes | 1,565 paths, about 1.04 GiB of logical file contents |
| Candidate reusable GIF family | 193 `*_attack_dir06_dat4x.gif` files, 634.78 MiB |
| Remaining candidate image exclusions | 1,372 PNG files, 430.83 MiB; inspect exact owner selections before deciding exceptions |

The sizes above are file-content totals, not promises of exact network-transfer size. The GIF generator documents direction 06, red player color, DAT 4x processing and transparent attack animation. `apps/video/build_story_short.py` consumes these paths as a fallback. Selection does not require regenerating or renaming them.

Existing remote images include application assets and production artwork. Their wholesale removal and historical storage reduction are outside this plan.

## Approval gates

1. **Plan approval — received:** The owner approved the local-only procedure below, including preserving a recovery branch and using `git reset --mixed` to rebuild the unpublished history without changing working-tree files.
2. **Asset selection — received:** The owner selected the full existing per-unit reusable library, not just the 193 attack GIFs. The exact 1,548-path snapshot is now recorded in `docs/GIT_ASSET_POLICY.md`; it does not pre-approve future files by wildcard.
3. **Later publication:** After the replacement commit and independent report are ready, ask for separate push authorization. Do not push as part of this plan's implementation.

This approval intentionally retains approximately 1.03 GiB of unit assets. Most of the earlier PNG exclusion proposal is superseded because the owner selected the complete library. Only the 17 cover backups (14.17 MiB) are excluded from the original pending media set. Large size is now expected, not by itself an accidental-upload finding.

## File map

| File / location | Planned action |
| --- | --- |
| `.gitignore` | Replace the obsolete blanket art-backup statements; add scoped media exclusions and exact retained-asset exceptions |
| `AGENTS.md` | Record the mandatory independent full-outgoing-history review and source/output policy |
| `docs/VIDEO_PRODUCTION_RUNBOOK.md` | Replace the blanket generated-art commit instruction in section 13 with selective retention and ignored-output guidance |
| `docs/GIT_ASSET_POLICY.md` | Create the concise policy plus exact retained-asset register with reason, variant, size and Git blob ID |
| This plan | Keep as the approved procedure and decision record |
| The 38 paths in Appendix A | Retain their current useful content; only `.gitignore` and the runbook receive the policy edits described here |
| Owner-selected assets under `graphics/units/` or other named paths | Retain byte-for-byte at existing paths; enumerate individually |
| Unselected local media | Keep on disk, but absent from the replacement commits and ignored where generated |
| Generator scripts and application consumers | No source changes or path migration in this cleanup |

## Task 1: Confirm selection, scope and recovery point

**Files:** Create `docs/GIT_ASSET_POLICY.md` only after approval. Read the original six commits and their tree metadata.

**Interfaces:** Produce an exact list of approved binary paths and the exact source list in Appendix A; both feed staging and review. The `.gitignore` exceptions are the actual Git inclusion mechanism, not a new manifest interpreter.

- [ ] Confirm the two implementation approvals above. If the owner chooses a family, expand it from the pinned source snapshot to exact filenames, display its count/size, and record that family-level approval. Do not silently include later files with similar names.
- [ ] Recheck state using the commands below. Expect the branch/HEAD/remote values above. The known initial working-tree changes are this plan and the separate asset-inventory document explicitly preserved above. Stop and reconcile any other user edits or changed remote tip; never overwrite them or silently merge extra work.

```powershell
git branch --show-current
git rev-parse HEAD
git --no-optional-locks status --porcelain=v1 --untracked-files=all
git ls-remote --heads origin refs/heads/codex/video-recorder-v3
git diff --name-status 251f6befa2986d04fafe8556ace4682ad253ae2a..563825f43b3e7d1d71155b3b90be7d2574f106ec
git ls-tree -r -l 563825f43b3e7d1d71155b3b90be7d2574f106ec -- graphics/units graphics/youtube
```

- [ ] Create a **local-only** recovery branch at the original snapshot. Use ordinary creation, never overwrite a pre-existing ref. If the name exists, inspect it and reuse only if it already points to this exact snapshot.

```powershell
git branch backup/local-video-recorder-v3-20260922 563825f43b3e7d1d71155b3b90be7d2574f106ec
git rev-parse backup/local-video-recorder-v3-20260922
```

- [ ] Record each approved asset's repository path, reuse purpose, known angle/action/model, bytes and existing Git blob ID in `docs/GIT_ASSET_POLICY.md`. Unknown metadata stays explicitly unknown; do not infer quality approval from a filename. Hashes identify existing content without expensive rerenders.
- [ ] Check the selected assets' existing consumers, starting with `apps/video/build_story_short.py` and `graphics/units/sync_web_sprites.py`. Separate self-contained reusable GIFs from any required companion metadata or local production inputs. If a proposed exclusion removes a required tracked dependency, present that exact dependency for selection rather than silently retaining an entire folder. Record external/local-only inputs in the policy; do not promise the production workflow runs from a clone without them.
- [ ] Record that the recovery branch is not a publication target. No `--all`, `--mirror`, or indiscriminate ref/tag push is allowed.

**Acceptance:** Exact asset choices exist; recovery ref matches the original snapshot; no media file has been changed, moved, or deleted.

## Task 2: Make exclusions automatic without changing application paths

**Files:** Modify `.gitignore`, `AGENTS.md`, `docs/VIDEO_PRODUCTION_RUNBOOK.md`; create/update `docs/GIT_ASSET_POLICY.md`.

**Interfaces:** All existing generator/consumer paths remain valid. Standard Git evaluates exclusions; retained exceptions are exact paths, not all matching GIFs or all files in a selected unit folder.

- [ ] Replace the two obsolete `.gitignore` comments saying generated art is tracked as backup. Explain that source and owner-selected reusable assets are tracked, while unapproved outputs are local-only.
- [ ] Add the following narrow media exclusions. They do not ignore parent directories or source scripts, so exact-path negations remain effective. Existing tracked assets remain tracked; this is intentionally not a purge of published images.

```gitignore
# New generated media: local by default. Owner-approved exact paths follow.
/graphics/units/**/*.png
/graphics/units/**/*.gif
/graphics/units/**/*.jpg
/graphics/units/**/*.jpeg
/graphics/units/**/*.webp
/graphics/youtube/**/*.png
/graphics/youtube/**/*.gif
/graphics/youtube/**/*.jpg
/graphics/youtube/**/*.jpeg
/graphics/youtube/**/*.webp
/graphics/art/**/*.png
/graphics/art/**/*.gif
/graphics/art/**/*.jpg
/graphics/art/**/*.jpeg
/graphics/art/**/*.webp
/graphics/extracted/**/*.png
/graphics/extracted/**/*.gif
/graphics/extracted/**/*.jpg
/graphics/extracted/**/*.jpeg
/graphics/extracted/**/*.webp
/apps/video/intro/assets/**/*.png
/apps/video/intro/assets/**/*.gif
/apps/video/intro/assets/**/*.jpg
/apps/video/intro/assets/**/*.jpeg
/apps/video/intro/assets/**/*.webp
/apps/video/intro/thumbnails/**/*.png
/apps/video/intro/thumbnails/**/*.gif
/apps/video/intro/thumbnails/**/*.jpg
/apps/video/intro/thumbnails/**/*.jpeg
/apps/video/intro/thumbnails/**/*.webp
```

- [ ] Append one root-anchored `!` exception for each approved asset path, using the owner's exact list. Do not use `!*_dir06_dat4x.gif` or a whole-folder exception: that would pre-approve future generated files. Use `apply_patch` to edit the rules, not a new generator or custom hook.
- [ ] Keep existing `data/local/`, `.scratch/`, `.worktrees/`, raw-game-file and raw-video exclusions intact. Document that new scratch workflows write directly to `data/local/generated/` or an existing ignored output directory. Reusable source/helpers belong in tracked source directories, not only in scratch.
- [ ] Preserve existing website static assets, databases, lookup manifests, CSS, templates and consumers. Do not invoke `sync_web_sprites.py`: it promotes images into application paths and is not part of this cleanup.
- [ ] State the limitation accurately: ignored **new** files stay out of ordinary staging. Tracked assets can still be modified, and force-add can bypass ignore rules. Variations must be written to ignored output paths, not over a tracked approved asset, unless an update to that asset is requested.
- [ ] Replace section 13's blanket commit instruction with: "Commit code, source-backed data, approved templates/manifests, documentation and explicitly owner-selected reusable assets recorded in the Git asset policy. Keep raw captures, rendered videos, frame streams, unselected generated media, credentials and machine-local state outside Git. Generation alone is not asset-retention approval."
- [ ] Append these requirements to `AGENTS.md` and link the asset policy:

```text
Before every Git push, obtain an independent requirements/scope review of the
exact user request, destination ref, live remote tip, complete outgoing commit
range, changed paths, binary inventory and newly reachable object sizes.
Review earlier unpushed commits, not only the latest commit or staged diff.
Proceed only within the user's publication authorization and with no unresolved
scope mismatches. Routine in-scope review is automatic; ask the user only for
new authority or a material ambiguity. If independent review is unavailable,
stop before pushing and report it. Re-review if the candidate or remote changes.
Generated media is local-only unless explicitly selected for retention. Follow
docs/GIT_ASSET_POLICY.md; use explicit staging paths, never force-add as a shortcut.
Do not publish local recovery refs or bypass the review with --all/--mirror.
Size is evidence to compare with approved scope, not a substitute for scope:
an intentionally approved large GIF library may be valid.
```

**Acceptance:** Known generator output formats are ignored automatically, selected assets have exact exceptions, scripts/docs remain eligible, and no generator or consumer code changed. This is a repository instruction plus standard Git policy, not a claim of tamper-proof global enforcement.

## Task 3: Rebuild the unpublished history in place, preserving files

**Files:** Git index/current local branch only, followed by the exact approved files. No new worktree is necessary.

**Interfaces:** Input is the verified remote base, preserved source snapshot, source-path list and approved asset list. Output is a new local commit based directly on the remote base, without the image-backup commit in its ancestry.

- [ ] Immediately before changing the local branch, recheck that HEAD/branch and live remote still match Task 1; verify the recovery ref again. Confirm every working-tree edit is a policy/plan file or one of the two explicitly preserved concurrent icon edits above.
- [ ] Use only this explicitly planned mixed reset. It moves the current local branch and resets the index to the remote base; it **does not change working-tree files**. Do not substitute `--hard`, a checkout, or a deletion operation.

```powershell
git reset --mixed 251f6befa2986d04fafe8556ace4682ad253ae2a
git --no-optional-locks status --short --untracked-files=all
```

- [ ] Confirm all 1,565 original image paths remain on disk. Compare unchanged files with their pinned Git blob identities and the two concurrent icons with their separately captured pre-reset working-file identities. The original 1,565 files all hash-matched before those concurrent edits occurred. Use existing Git hashing; do not decode/re-encode them. Stop on any unexplained mismatch.
- [ ] Confirm the status contains only the 38 source paths, the three policy/plan additions or modifications (`AGENTS.md`, `docs/GIT_ASSET_POLICY.md`, this plan), the owner-selected asset paths, and the known untracked asset-inventory document that must remain unstaged. Existing ignored scratch and unselected media must not appear as untracked candidates.
- [ ] Stage the exact 38 source paths in Appendix A plus the three policy/plan files using explicit literal path arguments. Restore the approved asset snapshot into the index only with `git --literal-pathspecs restore --source=563825f43b3e7d1d71155b3b90be7d2574f106ec --staged --` followed by the exact selected paths. Use bounded batches of 80 explicit paths to stay within Windows command-length limits. Index-only restore preserves the two concurrent working-file edits without including them. Do not stage parent folders or expand filesystem wildcards. Inspect the full staged file list before committing.

**Acceptance:** Original files/history remain recoverable; excluded assets are ignored and untracked in the replacement index; existing published content is retained; the new commit will have the remote base as parent, not the old backup-bearing local history.

## Task 4: Proportionate verification, local commit, independent review

**Files:** No new test framework. Use Git read-only checks and existing blob metadata.

- [ ] Verify ignore behavior with `git check-ignore --no-index -q -- PATH` for each case below, using actual approved paths from Task 1 where required. Exit 0 means ignored; exit 1 means not ignored. `--no-index` ensures a tracked file does not mask an ineffective rule.

| Probe | Expected |
| --- | --- |
| `graphics/units/unapproved_probe/unapproved_probe_attack_dir06_dat4x.gif` | Ignored even though its name resembles the retained family |
| `graphics/units/unapproved_probe/attack/0000.png` | Ignored |
| `graphics/youtube/unapproved_probe.png` | Ignored |
| `graphics/art/unapproved_probe.webp` | Ignored |
| `graphics/extracted/unapproved_probe.png` | Ignored |
| `apps/video/intro/assets/unapproved_probe.png` | Ignored |
| `apps/video/intro/thumbnails/unapproved_probe.jpg` | Ignored |
| `data/local/generated/unapproved_probe.mp4` | Ignored |
| `.scratch/unapproved_probe.png` | Ignored |
| Each selected asset | Not ignored |
| `graphics/units/build_attack_gifs.py` and `docs/GIT_ASSET_POLICY.md` | Not ignored |

These probes need not create files. Also check actual excluded files after Task 3 with normal `git check-ignore`, confirming they are no longer tracked by the replacement index.

On this Windows installation, PowerShell's ordinary pipeline adds CRLF and `git check-ignore --stdin` interprets the CR as part of the filename. Use literal path arguments (batches of 80 for the full asset list), not that stdin pipeline, for ignore validation. The corrected checks passed without changing the ignore rules.

- [ ] Check the staged path set equals the explicit source/policy/selected-asset set. Check `git diff --cached --check`. Check every source file matches the preserved snapshot except the specified policy edits; retained binaries must match the approved blob IDs exactly. Check no deletion or change to existing website assets or `data/golden/` is staged.
- [ ] Create one local replacement commit with a message describing the real combined scope: `Preserve Shorts workflow and curated assets; exclude generated scratch`. Do not describe it as documentation-only if selected binaries/code are included.
- [ ] Inspect the complete outgoing history and objects, not merely the final diff:

```powershell
git log --oneline 251f6befa2986d04fafe8556ace4682ad253ae2a..HEAD
git diff --stat 251f6befa2986d04fafe8556ace4682ad253ae2a..HEAD
git rev-list --objects 251f6befa2986d04fafe8556ace4682ad253ae2a..HEAD |
    git cat-file '--batch-check=%(objecttype) %(objectsize) %(rest)'
git merge-base --is-ancestor 1e175d6f HEAD
git merge-base --is-ancestor 251f6befa2986d04fafe8556ace4682ad253ae2a HEAD
```

Expected: one replacement commit; binary paths limited to selected assets; first ancestry check exits 1 (old backup commit absent), second exits 0 (remote base retained). Shared identical blobs should not be misclassified merely because an excluded path once referenced the same content. The old large objects remain locally via the recovery branch, but are not reachable from the replacement branch unless deliberately retained.

- [ ] Dispatch an independent reviewer using `superpowers:requesting-code-review`, with the exact user requirements, approved asset list, original and replacement SHAs, live destination ref and full outgoing inventory. Ask for a requirements/scope verdict, not a broad refactor or exhaustive test suite. Address discrepancies only within authorized scope.
- [ ] Recheck working-tree status, selected/excluded asset preservation, recovery ref, and unchanged live remote. Give the user a report with source count, selected asset count/size, excluded count/size, review verdict, and local commit ID. Stop and ask before any push.

**Acceptance:** Useful source and selected reusable assets are preserved; the unwanted backup payload is absent from all outgoing ancestry; newly generated files in the covered locations are excluded automatically; the remote is unchanged.

## Recovery and boundaries

- The local recovery branch retains all six original commits. The working directory retains selected and excluded assets. This cleanup will not shrink the local `.git` object store, and that is intentional for recovery.
- If reconstruction is interrupted, stop and report the exact state. The documented recovery reference is `backup/local-video-recorder-v3-20260922`; a mixed reset to it can restore the previous branch/index without deleting working files, but do not auto-run a rollback that obscures later user edits.
- Existing published images stay as-is. This does not implement the older storage/CDN migration proposals, introduce Git LFS, relocate assets, or prune historical objects.
- Future application-asset promotions or changes to tracked retained assets remain normal scoped changes requiring user intent. An ignore rule is not a general detector of semantic intent, nor a universal ban on arbitrary output paths.

## Self-review of this plan

- **Coverage:** Valuable files are retained (Appendix A / Tasks 3–4); owner-selected GIFs are protected (Tasks 1–4); new generated media is ignored (Task 2); legacy instructions are reconciled (Task 2); full-range independent review is recorded and applied (Tasks 2 and 4); approval and no-push boundaries are explicit.
- **Correction made during review:** Reject a blanket ban on all GIFs or all binaries. Exact owner selection controls retention, and a legitimate 635 MiB library must not be called an accidental upload solely due to size.
- **Correction made during review:** Avoid migrating generator output roots or changing consumers. Scoped ignore rules solve immediate staging behavior while preserving reusable paths.
- **Correction made during review:** Avoid a new worktree, asset deletion, or a revert of the backup commit. A local recovery ref plus mixed reset preserves disk contents and removes the old backup commit from the replacement ancestry.
- **Correction made during review:** Do not use a family wildcard as the permanent exception: enumerate the currently approved assets so newly generated lookalikes remain ignored.
- **Dependency check:** Retention review must identify required companions and external production inputs; preserving paths alone does not prove a fresh clone has every input. No wholesale asset promotion or consumer rewrite is authorized to address an unverified dependency.
- **Consistency:** The remote base and source snapshot are fixed throughout; the approved path set drives `.gitignore`, staging and review; policy edits are the only allowed differences from retained source content.
- **Approval update:** Local implementation and the complete existing per-unit library are approved. The original GIF-only selection question is resolved by that broader library selection. There is still no push authorization.

## Appendix A: Existing valuable source changes to retain

```text
.gitignore
README.md
apps/video/SHORTS_CAMERA.md
apps/video/build_champi_comparison_overlay.py
apps/video/build_story_batch.py
apps/video/build_story_short.py
apps/video/build_vertical_short.py
apps/video/overlay/battle_camera.py
apps/video/overlay/battle_end.py
apps/video/overlay/shorts_battle.py
apps/video/overlay/shorts_story.py
apps/video/overlay/static_stats.py
apps/video/overlay/unit_timeline.py
apps/video/overlay/video_enhance.py
apps/video/prepare_story_attacks.py
apps/video/tests/test_battle_camera.py
apps/video/tests/test_intro_sequence.py
apps/video/tests/test_short_exit.py
apps/video/tests/test_short_revision_timing.py
apps/video/tests/test_shorts_battle.py
apps/video/tests/test_shorts_story.py
apps/video/tests/test_video_enhance.py
docs/VIDEO_PRODUCTION_RUNBOOK.md
docs/superpowers/plans/2026-09-20-shorts-bookends.md
docs/superpowers/plans/2026-09-21-iconic-shorts-v8-batch.md
docs/superpowers/plans/2026-09-21-short-replacement-cards.md
docs/superpowers/plans/2026-09-22-approved-ten-shorts.md
docs/video-production/SHORTS_APPROVED_WORKFLOW.md
docs/video-production/SHORTS_FROM_RAW.md
docs/video-production/reference/shorts-v15/README.md
docs/video-production/reference/shorts-v15/batch.json
docs/video-production/reference/shorts-v15/final-v15/voices/build_catalog.py
docs/video-production/reference/shorts-v15/final-v15/voices/build_editorial_candidates.py
docs/video-production/reference/shorts-v15/final-v15/voices/inspect_xianbei_actions.py
docs/video-production/reference/shorts-v15/finish_final_batch.py
docs/video-production/reference/shorts-v15/render_final_batch.py
docs/video-production/reference/shorts-v15/run_batch.py
docs/video-production/reference/shorts-v15/test_final_batch.py.txt
```

The nine-file reference bundle is approximately 48 KiB of reproducibility source, not a media backup. Preserve the dated plans as historical decisions; do not expand this cleanup into rewriting their old progress notes.

## Official behavior references

- [Git ignore rules](https://git-scm.com/docs/gitignore): apply to untracked files; exact negations work only when parent directories are not excluded.
- [Git mixed reset](https://git-scm.com/docs/git-reset): changes the branch/index while leaving working-tree files unchanged.
- [Git branch creation](https://git-scm.com/docs/git-branch): creates a recovery reference without switching or rewriting files.
- [Git check-ignore](https://git-scm.com/docs/git-check-ignore): checks ignore behavior, including `--no-index` for testing tracked paths.
