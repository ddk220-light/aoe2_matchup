# Combat calibration against per-tick game recordings — design

**Date:** 2026-07-30 · **Branch:** `improved-simulation` · **Status:** approved, pre-implementation

Replaces outcome-level validation (38 win/loss rows) with **event-level calibration** against
real AoE2 fights recorded at ~60 Hz. Each recording carries every damage event, every
projectile, and 10 Hz unit positions — so the simulator can be fitted to *how* the real game
fights, not merely who won.

Supersedes `docs/superpowers/specs/2026-07-29-target-thrash-design.md` as the validation
authority. That spec's engine fix (pursuit exemption) survives and is re-justified here
against this rig; its tape-corpus scoring is retired.

---

## 1. The data

A drop is a zip (`aoe2_golden_spike_2026-07-29.zip` is the first). Decoded per fight:

| stream | shape | rate |
|---|---|---|
| `<tag>.units.jsonl.gz` | `{t, id, owner, master, x, y, hp, state, facet, stance, volley, charge}` | 10 Hz |
| `<tag>.damage.jsonl.gz` | `{t, attacker, victim, damage, victim_hp_after, kill, attacker_owner, attacker_master, victim_owner, victim_master}` | per event |
| `<tag>.missiles.jsonl.gz` | `{t, id, owner, master, fired_from, x, y}` | ~60 Hz |
| `<tag>.commands.jsonl` | `{t, kind}` | per command |
| `<tag>.meta.json` | composition, `stream_hz`, `position_sample_hz`, `fight_t_start/end`, counts | — |
| `<tag>.summary.json` | per-side and per-unit rollups | — |
| `GROUND_TRUTH.md` | human-readable derived card | — |
| `matchups_91.json` | the planned corpus: 91 rows of `{civ1, slug1, label1, civ2, slug2, label2}` | — |

**The spike (2 fights, in hand):**

| fight | civs | counts | outcome | duration |
|---|---|---|---|---|
| `hand_cannoneer__vs__elite_elephant` | Japanese vs Burmese | 21 v 12 | elephants (5 survive, 928 hp) | 152.31 s |
| `elite_steppe__vs__arbalester` | Cumans vs Chinese | 14 v 21 | arbalesters (4 survive, 160 hp) | 71.23 s |

Civs are resolved from `matchups_91.json` and **cross-validated** against observed spawn HP
(Burmese Elite Battle Elephant = 320 hp matches the tape's first victim at 312 + 8 damage).

**Arena:** the documented 16×16 golden arena with ~39% solid tiles (positions span
[2.5, 13.5]). The JS engine simulates a 30×20 open box. **Geometry mismatch is accepted and
out of scope** (user decision): only combat dynamics are calibrated. Movement-dependent
metrics are reported, never gated.

**Cadence:** the 91-fight corpus arrives as a later drop; unique units after that. One
recording per matchup, with the scorer nominating specific matchups for re-recording.

## 2. Why event-level, and what the spike already proves

Single-fight event counts are large (380 shots, 436 hits), so **per-metric confidence comes
from within one tape** — one recording per matchup is statistically sufficient for
high-count metrics, and the scorer marks low-count metrics INCONCLUSIVE rather than
pretending. That is the reroll list.

The spike already exposes four calibration gaps:

| signal | tape | engine today |
|---|---|---|
| melee crowd churn | elephant swing median **5.672 s** vs fastest **2.018 s** (+3.654 s); steppe +0.278 s; HC +0.494 s | **mechanism absent in JS** (`grep churn` on `engine/*.js` → nothing) |
| effective accuracy | HC **96.8%** (368/380) vs 65% paper; arbalester **91.9%** (350/381) vs 90% paper | rolls paper accuracy per shot; graze exists at 0.5× |
| trample | 7 of 53 elephant swings hit >1 victim (13%), mean 3.14 victims, splash fraction 0.25, damage support `18×32, 17.5×6, 13×3, 8.5×1, 4.5×15, 4×11` | `tramplePercent`/`trampleRadius`/`trampleFlatDamage` exist ([battle_unit.js:78-81](apps/website/static/js/engine/battle_unit.js:78)) — values and multi-hit rate unaudited |
| reload floor | arbalester fastest observed **1.582 s** < 2.0 s paper reload | investigate before changing anything |

The HC damage histogram (`8×360, 4×8`) independently confirms the engine's graze model is
real: 8 full hits and 8-damage half-hits at 4. That is a mechanism to *fit*, not invent.

## 3. Architecture

Five components, each independently testable.

```
drop.zip ──ingest──> D:/AI/aoe2_golden/tapes/<tag>/       (external, large)
                     data/calibration/truth/<tag>.json    (in-repo, small)
                     data/calibration/manifest.json

engine ──eventLog──> sim event files (tape format) ──┐
                                                      ├──extract──> truth cards ──score──> scoreboard
tape streams ────────────────────────────────────────┘                                     + reroll list
```

**The load-bearing property: ONE extractor.** `aoe2x/calibration/extract.py` computes every
metric, and consumes tape-format event streams regardless of origin. The simulator emits
*the tape's own shapes*, so tape and sim pass through identical code. A metric cannot mean
two different things in the two worlds — the classic calibration failure is structurally
excluded rather than guarded by discipline.

### 3.1 Storage

| path | contents | in repo? |
|---|---|---|
| `D:/AI/aoe2_golden/drops/` | raw zips, archived by name | no (external, like the matchup DBs) |
| `D:/AI/aoe2_golden/tapes/<tag>/` | decoded streams | no |
| `D:/AI/aoe2_golden/simruns/<tag>/` | per-seed sim event files | no |
| `data/calibration/truth/<tag>.json` | truth card (few KB) | **yes** — the fixture under test |
| `data/calibration/manifest.json` | tag → zip sha256, composition, resolved civs, counts, ingest date | **yes** |
| `data/calibration/runs/<stamp>.json` | scoreboard output | **yes** |

Rationale: the 91-fight corpus will be tens of MB decoded; the repo keeps only what a test
needs. Matches the existing convention that matchup DBs live outside the repo.

### 3.2 Ingest — `aoe2x/calibration/ingest.py`

`python -m aoe2x.calibration.ingest <zip>`. Idempotent: re-ingesting a known sha256 is a
no-op; new tags append. Per fight it: extracts streams to the external tape dir; resolves
each side's `(civ, slug)` by matching `meta.json`'s composition unit names against
`matchups_91.json` labels; **cross-validates** the resolved unit's `ref_units.final_hp`
against the tape's observed spawn HP and its `final_attack` against the modal full-hit
damage; then writes the truth card and manifest entry. Any mismatch is a hard failure with
the conflicting values printed — never a silent best guess.

### 3.3 Truth-card extractor — `aoe2x/calibration/extract.py`

Input: damage events + missile events + composition. Output per side:

| metric | definition | gated? |
|---|---|---|
| `swing_interval_median` | per-unit consecutive-attack gaps → median over units. Melee: damage events by attacker. Ranged: missile launches by `fired_from`. | **yes** |
| `swing_interval_fastest` | minimum per-unit median across units | **yes** |
| `churn` | median − fastest | **yes** |
| `effective_accuracy` | hits landed / projectiles fired (ranged only) | **yes** |
| `damage_histogram` | `{damage_value: count}` over all landed hits | **yes** |
| `hits_landed`, `damage_dealt`, `kills` | totals | **yes** |
| `survivors`, `hp_remaining` | end state | **yes** |
| `trample_multi_rate` | swings hitting >1 victim / total swings (same attacker, same tick) | **yes** (when the unit has trample) |
| `trample_victims_mean/max`, `splash_fraction` | derived from multi-victim swings | **yes** (same condition) |
| `first_blood` | t of first landed hit | reported |
| `duration_s`, `mean_distance_tiles` | fight length, travel | reported (geometry-dependent) |

Every metric carries `n` (its event count) so the scorer can weigh it.

### 3.4 Sim event recorder — `apps/website/static/js/engine/`

Opt-in `sim.eventLog`: `null` by default (zero cost, zero behavioural change). When set to
an object with `damage: []` and `missiles: []`, the engine appends:

- in `takeDamage` ([battle_unit.js:1171](apps/website/static/js/engine/battle_unit.js:1171)), beside the existing `combatStats` hook: `{t, attacker, victim, damage, victim_hp_after, kill, attacker_owner, victim_owner}`
- at projectile spawn: `{t, fired_from, owner}`

`takeDamage` is the single funnel for all damage in the engine (direct, splash, trample,
charge, bleed), so one hook captures everything.

**Parity discipline.** `stateHash()` ([sim.js:232](apps/website/static/js/engine/sim.js:232)) hashes only `x, y, currentHp, state` per
unit plus four sim values — the log is invisible to it, exactly as `combatStats` already is.
Two gates: `parity_check.mjs` green with the recorder off, and a test asserting bit-identical
`stateHash` streams with the recorder on vs off. If recording changes a fight, it is a bug.

### 3.5 Calibration runner — `tools/simjs/calib_runner.mjs`

Per manifest fight: build both teams from the resolved `(civ, slug)` and the tape's own
counts (**never a count rule** — three incompatible ones exist in this repo), run **20
seeds** with `eventLog` enabled, write per-seed event files in tape format.

### 3.6 Scorer — `aoe2x/calibration/score.py`

Tape card vs the 20-seed sim card distribution. Per metric: tape value, sim median, sim
[p10, p90], delta, verdict.

- **MATCH** — tape value inside the sim's 20-seed spread, or within the metric's tolerance.
- **MISMATCH** — outside both.
- **INCONCLUSIVE** — the tape's own event count is too small to distinguish (binomial CI on
  a rate metric wider than the tolerance; fewer than 5 events for an interval metric).

Tolerances, from the metric's own statistics rather than taste: rate metrics use a binomial
95% CI from the tape's `n`; interval metrics use the tape's per-unit IQR; count metrics use
the 20-seed p10–p90 band. INCONCLUSIVE rows collect into a **reroll request list** printed at
the end and written to the run file — the "which matchups need more recordings" answer.

Overall verdict per fight: all gated metrics MATCH or INCONCLUSIVE → PASS.

## 4. The fit — ordered backlog

One mechanism per change; both spike tapes re-scored after each. A change is kept only if
its target metrics move toward tape and no other gated metric regresses on either tape.

1. **Crowd churn.** Port the neighbour-scaled swing-delay mechanism (present in
   `simulation_real.py`, absent from the JS). Fit its constant so the elephant's +3.654 s and
   the steppe lancer's +0.278 s both land — a single constant answering two very different
   crowd densities is the honest test of the mechanism's shape.
2. **Effective accuracy against large targets.** HC's 96.8% vs 65% paper is the biggest gap.
   The graze mechanism exists; what is missing is misses *landing on* large hitboxes. Fit
   hit-capture as a function of target radius, checked against arbalester-vs-lancer (91.9%
   vs 90% paper — nearly clean), so the fix cannot be a blanket accuracy inflation.
3. **Trample audit.** Check Burmese Elite Battle Elephant's `trample_*` values in the
   reference DB, then fit radius/percent to the observed 13% multi-hit rate, 3.14 mean
   victims and 0.25 splash fraction.
4. **Reload-model investigation.** Arbalester's fastest observed interval (1.582 s) is below
   its 2.0 s paper reload. Investigate — Thumb Ring bookkeeping, frame quantisation, or a
   real model gap — and report before changing anything.
5. **Pursuit fix (revived).** The HC-vs-elephant tape is the thrash pair: the sim runs ~340 s
   where the tape takes 152 s. The design and prototype from the retired spec land here,
   justified by this scorer.

## 5. Auto-pickup

A background monitor watches `C:/Users/ddk22/Downloads` for new `aoe2_golden*.zip` (~15 min
cadence). On arrival: ingest → 20-seed sim runs → scoreboard + reroll list, then the fit
continues against the enlarged corpus. Nothing about the pipeline is spike-specific; a drop
with 91 fights flows through the same path.

## 6. Reuse and retirement

**Reused:** the combat-dict dump pattern (`tools/simjs/dump_tape_dicts.py`, generalised to
take a matchup list), the `buildFight` drive seam in `headless.mjs`, the parity-gate
discipline, and `capture_golden.mjs` (specified in the retired plan, built here when the
first parity break lands).

**Retired as gates** (code remains, no longer authoritative): `tape_corpus.json` scoring,
`tape_rig_js.py`, `margin_score.py`. The 38-row outcome corpus is superseded by 2 (soon 93)
event-level recordings.

## 7. Risks

1. **Geometry confound.** The engine fights on a 30×20 open box; the tape on a 16×16 arena
   that is 39% trees. Swing intervals and accuracy are only weakly geometry-dependent;
   distance, duration and first-blood are strongly so — hence gated vs reported. If a gated
   metric proves geometry-driven, it moves to reported and is recorded as such.
2. **Fitting to two fights.** Constants fitted on the spike may not generalise. Mitigation:
   every constant must satisfy *both* tapes (different unit classes, different crowd
   densities), and the 91-fight drop re-scores everything automatically.
3. **Civ resolution.** Tapes carry unit names, not civs. Mitigated by matching against
   `matchups_91.json` and hard-failing on any HP/attack cross-validation mismatch.
4. **Recorder perturbation.** Guarded by the on/off `stateHash` equality test.
5. **Trample event attribution.** "Same attacker, same tick" identifies multi-victim swings;
   at 60 Hz two genuinely separate swings cannot collide, but a tolerance of one stream
   frame is applied and the assumption is recorded.

## 8. Success criteria

For the spike (both tapes): every gated metric MATCH or INCONCLUSIVE, with churn,
hit-capture and trample each earning its constant from measurement. Parity re-captured once,
with the behavioural change recorded. `node --test tests/js/engine/` and `python -m pytest`
green. The scorer emits a reroll list naming any matchup whose tape lacked the events to
decide.
