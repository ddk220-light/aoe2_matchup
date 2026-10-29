# Pursuit and contact corrections: validation

37 pilot checks: 19 exact, 18 changed, 0 winner changes.

12 anomaly retries: {'win': 11, 'processing_timeout': 1}.

The exact-preserving collision optimization has its own validation report. These 
additional corrections intentionally repair blocked-pursuit and contact-handoff behavior.

| Matchup / seed | Processing seconds | Game seconds reached | Status |
|---|---:|---:|---|
| Aztecs|imp_elite_skirm vs. Turks|paladin / 2 | 24.04 | 35.40 | win |
| Britons|imp_elite_skirm vs. Turks|paladin / 2 | 23.78 | 35.40 | win |
| Cumans|imp_elite_skirm vs. Spanish|hussar / 0 | 10.34 | 32.22 | win |
| Celts|imp_elite_skirm vs. Spanish|hussar / 0 | 9.30 | 34.12 | win |
| Burgundians|heavy_scorpion vs. Saracens|hand_cannoneer / 0 | 14.13 | 34.73 | win |
| Gurjaras|imp_elite_skirm vs. Turks|paladin / 0 | 8.50 | 33.70 | win |
| Incas|imp_elite_skirm vs. Turks|paladin / 0 | 7.42 | 33.70 | win |
| Incas|imp_elite_skirm vs. Spanish|champion / 1 | 120.00 | 152.92 | processing timeout |
| Mapuche|imp_elite_skirm vs. Spanish|hussar / 2 | 80.43 | 40.20 | win |
| Muisca|elite_guecha_warrior_muisca vs. Spanish|hussar / 0 | 16.90 | 50.48 | win |
| Muisca|imp_elite_skirm vs. Turks|paladin / 1 | 7.32 | 34.18 | win |
| Tupi|imp_slinger vs. Turks|paladin / 1 | 6.71 | 27.62 | win |

Separate engine version. Keep original results immutable; do not combine changed behavior with original ranking samples. Recompute affected campaign results before scoring.

Expanded checks: 191 of 192 tests passed. The existing large mobile-ranged 
crowding expectation fails identically on the unchanged baseline. No expectations 
were rewritten. See [test-status.json](test-status.json) for the test list and evidence.

See [summary.json](summary.json) for winner, survivor, and duration comparisons; 
[runs.jsonl](runs.jsonl) includes every result and its engine source hashes.
