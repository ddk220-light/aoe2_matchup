# Movement, pursuit and contact corrections: validation

Coverage: 60/144 recorded tasks; complete=False.

37 pilot checks: 3 exact, 34 changed, 3 winner changes.

23 anomaly retries: {'win': 22, 'engine_error': 1}.

The exact-preserving collision optimization has its own validation report. These 
additional corrections intentionally repair pursuit, contact handoffs, obstacle routing and collision recovery.

| Matchup / seed | Processing seconds | Game seconds reached | Status |
|---|---:|---:|---|
| Mapuche|elite_bolas_rider_mapuche vs. Spanish|hussar / 1 | 9.52 | 47.02 | win |
| Berbers|hand_cannoneer vs. Saracens|heavy_cav_archer / 0 | 15.43 | 28.87 | win |
| Armenians|heavy_scorpion vs. Saracens|heavy_cav_archer / 0 | 32.39 | 68.75 | win |
| Bengalis|heavy_scorpion vs. Spanish|imp_elite_skirm / 2 | 20.57 | 67.98 | win |
| Berbers|hand_cannoneer vs. Saracens|heavy_cav_archer / 2 | 30.91 | 29.12 | win |
| Aztecs|imp_elite_skirm vs. Turks|paladin / 2 | 6.06 | 26.93 | engine error |
| Bohemians|elite_hussite_wagon_bohemians vs. Chinese|arbalester / 2 | 18.51 | 73.28 | win |
| Armenians|heavy_scorpion vs. Spanish|imp_elite_skirm / 0 | 17.80 | 71.53 | win |
| Armenians|heavy_scorpion vs. Spanish|imp_elite_skirm / 1 | 17.88 | 73.37 | win |
| Berbers|heavy_cav_archer vs. Saracens|hand_cannoneer / 0 | 12.50 | 30.13 | win |
| Armenians|heavy_scorpion vs. Spanish|imp_elite_skirm / 2 | 18.09 | 66.67 | win |
| Aztecs|heavy_scorpion vs. Saracens|heavy_cav_archer / 0 | 15.72 | 41.90 | win |
| Aztecs|heavy_scorpion vs. Saracens|heavy_cav_archer / 2 | 18.96 | 43.25 | win |
| Bohemians|elite_hussite_wagon_bohemians vs. Spanish|imp_elite_skirm / 0 | 24.77 | 97.57 | win |
| Bohemians|elite_hussite_wagon_bohemians vs. Spanish|imp_elite_skirm / 2 | 21.07 | 100.72 | win |
| Bohemians|elite_hussite_wagon_bohemians vs. Spanish|imp_elite_skirm / 1 | 22.05 | 98.92 | win |
| Bulgarians|heavy_cav_archer vs. Saracens|heavy_cav_archer / 1 | 11.20 | 47.63 | win |
| Burgundians|heavy_scorpion vs. Spanish|imp_elite_skirm / 0 | 19.99 | 123.63 | win |
| Burgundians|heavy_scorpion vs. Spanish|imp_elite_skirm / 1 | 25.95 | 126.00 | win |
| Bohemians|elite_hussite_wagon_bohemians vs. Saracens|heavy_cav_archer / 0 | 34.30 | 93.40 | win |
| Bulgarians|heavy_cav_archer vs. Saracens|hand_cannoneer / 0 | 14.12 | 30.13 | win |
| Bohemians|elite_hussite_wagon_bohemians vs. Saracens|heavy_cav_archer / 1 | 36.50 | 90.65 | win |
| Burgundians|heavy_scorpion vs. Saracens|hand_cannoneer / 0 | 11.08 | 31.42 | win |

Separate engine version. Keep original results immutable; do not combine changed behavior with original ranking samples. Recompute affected campaign results before scoring.

Regression checks are still pending.

See [summary.json](summary.json) for winner, survivor, and duration comparisons; 
[runs.jsonl](runs.jsonl) includes every result and its engine source hashes.
