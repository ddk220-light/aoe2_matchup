# Replacement Short Card Labels Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this bounded continuation inline. Steps use checkbox syntax for tracking.

**Goal:** Keep the approved special-effect card format for the four user-approved replacement recordings.

**Architecture:** Extend only the existing `special_effects(unit, relics=0)` label function using sourced reference fields. The existing renderer, native attack extraction, crop, model and serial batch runner remain the implementation path.

**Tech Stack:** Python, unittest, existing Pillow/FFmpeg video pipeline.

**Spec:** User-approved V8 format and existing `data/local/iconic-shorts-v8-20260921/README.md`.

## Global Constraints

- Existing clean recordings only; no new game captures or simulations.
- Keep jobs 03–08 and their running process unchanged.
- Local changes only; no publication, push or production mutation.
- SeedVR2 Sharp 2x and the approved V8 layout remain unchanged.
- Proportionate focused smoke checks, not a hardening pass.

### Task 1: Source-backed effect labels and replacement preflight

**Files:** Modify `apps/video/overlay/static_stats.py` and `apps/video/tests/test_shorts_battle.py`.

**Interfaces:** Consume reference fields `splash_on_hit_radius`, `total_projectiles`, and `charge_projectile_count`. Produce the existing list of green card strings; never alter attack statistics.

- [x] Add a failing test using literal fixtures: radius `.65` produces `Splash damage on impact`; total projectiles `6` produces `Fires multiple projectiles`; charge projectiles `5` produces `Charged projectile volley`. With these fields zero/one, none of these labels appears. Assert the fixture is unchanged.
- [x] Run `unittest` discovery restricted to `test_shorts_battle.py`; observe the expected missing-label failure.
- [x] Add the three positive-field branches in `special_effects`, with exactly the label strings above.
- [x] Run the same focused tests and inspect replacement card/frame preflights against actual staged recordings.
- [x] Append the four replacements after PID 4276. Waiting launcher is PID 1740.
- [ ] Generate their HAT assets only after the six existing jobs release the GPU, then invoke the existing batch CLI with `--numbers 1 2 9 10`. The launched script performs these queued steps.
- [x] Verify the waiting process, logs, source hashes and disk budget. Record status honestly; final MP4 review/delivery remains pending.

Execution stays in this already-active task, following the user's approval to make the replacement Shorts. No new checkout or integration action is needed.
