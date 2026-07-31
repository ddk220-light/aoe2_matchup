# Ingest 2026-07-31 — v3 pal-steppe live rounds + HCA/HC re-record families

Two tape drops ingested via the established `aoe2x.calibration.ingest` pipeline
(content-hash idempotent, reused-tag repeats auto-assigned the next free
`_rN` slot). Drops archived as `aoe2_golden_melee_v3_palsteppe24.zip` and
`aoe2_golden_rerecords_0731b.zip` in `D:/AI/aoe2_golden/drops/`.

**Scope note:** the three siege-onager re-records that arrived alongside
(halberdier__vs__siege_onager, siege_onager__vs__heavy_camel,
siege_onager__vs__hussar) were **deferred by the user mid-ingest** — a better
tape is coming. Their tapes, truth cards, and manifest entries are byte-for-byte
untouched (verified by re-hashing the tape streams against the manifest).
`aoe2_golden_rerecords_0731.zip` in drops/ is the superseded first cut of the
0731 drop; only its heavy_cav_archer__vs__paladin content (byte-identical in
the b cut) is ingested.

## Delta actually ingested

### palsteppe24 (cumulative v3 melee corpus, 79 fights in drop)

- 67 fights = byte-identical redeliveries of the already-ingested v2 corpus
  (no-ops; verified by per-fight content hash, never tag names).
- **12 NEW: paladin__vs__elite_steppe live-position rounds.** Drop tags
  r13–r24 → manifest run_ids **r19–r30** (order-preserving; drop tags r13–r18
  collided with the frozen v2 rounds already holding those run_ids, so the
  ingester's reused-tag rule assigned the next free slots).
- Live-position check: new rounds median 41–53 distinct positions/unit
  (vs 1 for the frozen v2 rounds r7–r18, which keep first-frame spawns per
  v2 policy). Spawns regenerated via `tools/simjs/dump_calib_spawns.py`
  (240 tapes, all new fights non-degenerate).
- Truth outcomes (from the tapes): **paladin 11/12 in the live rounds**
  (steppe's one win is r19); family total incl. frozen rounds: paladin 20/24.

The family now spans: 6 quarantined v1 originals (untouched) + 12 frozen v2
(outcome-valid only) + 12 live v3 = 24 scoreable.

### rerecords0731b (11 fights in drop; 3 onager deferred, 8 ingested)

- **heavy_cav_archer__vs__paladin**: old single re-recorded. Old tape archived
  as `tapes/heavy_cav_archer__vs__paladin.pre0731` (non-manifest name = inert);
  new recording installed under the same base tag, manifest entry refreshed
  in place (owners/counts unchanged: HCA=owner 2 Saracens ×21, Paladin=owner 3
  Spanish ×15), truth card rebuilt. Plus **_r2.._r5 NEW** (4 rounds).
  No outcome flip: paladin wins all 5 (survivors 12/10/11/9/9 of 15); the old
  single (paladin 12 survivors) was consistent — this adds variance samples.
- **hand_cannoneer__vs__heavy_cav_archer** (+_r2, _r3, all NEW tags): supersedes
  the old REVERSED-TAG single `heavy_cav_archer__vs__hand_cannoneer` (side-label
  trap: same matchup, opposite tag order, so the tooling treats them as
  different matchups). Old tape archived as
  `tapes/heavy_cav_archer__vs__hand_cannoneer.pre0731`, its manifest entry
  removed and its truth card deleted (a stale card under the dead tag would be
  a scoreboard trap). Positions live (median ~26 distinct pos/unit).
  No outcome flip — HCA wins all 3 — but the **margin moved a lot**: old single
  had HCA at 9/19 survivors, 489 HP (32.2% of army max); new rounds have HCA at
  12/19 828 HP (54%), 16/19 1005 HP (66%), 13/19 826 HP (54%).

## Corpus counts

Manifest 222 → **240** entries (+12 pal-steppe, +4 HCA_vs_paladin, +3
HC_vs_HCA, −1 reversed-tag single). Quarantined still 6 (v1 pal-steppe,
untouched). **Scoreable denominator 216 → 234.**

Melee gate (`test_melee_only_is_the_round4_gate`) pinned 83 → **95**
(history 31 → 89 → 83 → 95); `tools/simjs/melee_hp_report.py` docstring
updated to match. Fight-set membership is slug-derived (fight_sets.json), so
pal-steppe rounds joined `melee` and HC_vs_HCA joined `ranged` automatically;
HCA_vs_paladin is mixed (in neither set), onager fights are siege — as v2.

## Post-ingest baseline (current shipped defaults, 20 seeds, tapebox)

`data/calibration/runs/20260731T154530Z-post-0731-ingest-baseline.json`
(fresh sim dir, 234 fights × 20 seeds, 0 failures).

| board | winners | rate |
|---|---|---|
| pre-ingest night-final (20260731T112133Z) | 194/216 | 89.8% |
| **post-ingest baseline** | **201/234** | **85.9%** |
| both boards on the 215 shared run_ids | 193/215 both | identical |
| strict-comparable (also dropping the re-recorded HCA_vs_paladin base) | 192/214 both | identical |

Denominators differ; on the shared subset the two boards agree fight-for-fight
— the engine and every pre-existing fight's score are unchanged, so the whole
delta is the 19 added rows (8/19 winner-match) plus the refreshed
HCA_vs_paladin base (match on both boards).

Per family (new board): melee 68/95, mixed 81/86, siege 24/25, ranged 8/8,
fire-lancer 20/20. Canaries all green: champion__vs__arbalester 6/6,
halberdier__vs__heavy_cav_archer 6/6, arbalester__vs__elite_steppe 6/6,
hand_cannoneer__vs__heavy_camel 6/6.

### The new headline residual: paladin__vs__elite_steppe live rounds 1/12

At shipped defaults the engine picks **steppe in all 24 scoreable pal-steppe
rounds** (median 3 steppe survivors in every live round) — this was already
true pre-ingest on the 12 frozen rounds (9/12 flipped on night-final; its only
"matches" were the 3 rounds steppe genuinely won). The 12 live rounds turn
that from an outcome-only suspicion into a positionally-grounded 1/12: the
tape shows paladins winning 11/12 from these exact spawns. (The "engine was
100% paladin under exact spawns" observation from the pre-ingest experiments
does not reproduce at shipped defaults.) This family is now the single
biggest winner-match residual in the corpus.

### heavy_cav_archer__vs__paladin: 5/5

Engine picks paladin in every seed on all five rounds, matching truth.

### hand_cannoneer__vs__heavy_cav_archer: residual largely resolved by re-truth

Against the OLD single (HCA 489 HP, 32.2%) the engine over-predicted the HCA
winner's HP (sim median 700.5, +211.5 HP ≈ +13.9 pts of the 1520 army max;
scored ~23.5 pts against it in the pre-ingest analyses). Under the NEW truth
the same engine behavior is nearly on the tape: sim median 812 HP vs tape
828 / 1005 / 826 → deltas 16 / 193 / 13.5 HP (winner-side hp_remaining
MATCH / MISMATCH / MATCH). The old single now looks like the low-HP outlier
of the family, not the engine.

### Onager re-records: deferred

Not ingested (user call, better tape coming). The three existing onager
fights score exactly as before (winner_match=True, agreement 1.0). The old
engine-vs-old-truth comparison stands unchanged until the new tape lands.

## Tests

- `pytest tests/test_calibration_filters.py -q`: 14 passed (pin now 95).
- Full `pytest -q`: 363 passed, 13 skipped, **33 pre-existing failures** in
  Python-engine tests (test_position_sim_abilities, test_ranged_melee_class_armor,
  test_value_lost, test_resource_per_kill, test_battle_outcome,
  test_ability_registry) — all `AttributeError: 'BattleUnit' object has no
  attribute '_is_ranged_flag'` from commit 19407f3 (`aoe2x/sim/simulation_real.py`
  untouched this session; the campaign treats the Python engines as deprecated).
- `node --test tests/js/engine/`: **360/360 pass** (no JS touched).
