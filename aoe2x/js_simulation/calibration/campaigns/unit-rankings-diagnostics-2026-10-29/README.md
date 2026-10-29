# Ranking timeout diagnostics

Status: **running**. Completed 60/110 diagnostic tasks.

The bulk campaign and its saved outcomes remain the source records. These are supplemental diagnostic reruns.

Three controls must reproduce exact final-state and event hashes before any flagged run is investigated. 
Runs execute one at a time after the bulk campaign stops. The nominal processing allowance is 120 seconds; 
an external 130-second cutoff covers an unresponsive tick and profile flushing. 
Game-time-cutoff cases have no practical game-time cap. Original processing-time-cutoff cases 
first retain the original 150-game-second cap to make their timings interpretable. 
Tracing and CPU profiling add overhead, and the original campaign used four workers. 
A faster rerun alone does not prove a contention bug. Inactivity observations require inspection.

| Task | Matchup / seed | Stop reason | Processing seconds | Last game seconds |
|---|---|---|---:|---:|
| diagnose_engine_error | Burgundians Scorpion vs. Saracens Hand Cannoneer / seed 0 | engine_error | 24.34 | 13.916666666666666 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Spanish Elite Skirmisher / seed 0 | decided | 104.29 | 97.56666666666666 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Spanish Elite Skirmisher / seed 1 | processing_limit | 120.18 | 31.45 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Spanish Elite Skirmisher / seed 2 | decided | 111.07 | 95.91666666666667 |
| diagnose_processing_timeout | Portuguese Scorpion vs. Saracens Heavy Cavalry Archer / seed 0 | processing_limit | 120.27 | 9.15 |
| diagnose_processing_timeout | Portuguese Scorpion vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.31 | 27.9 |
| diagnose_processing_timeout | Goths Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 0 | processing_limit | 121.25 | 20.15 |
| diagnose_processing_timeout | Goths Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 1 | processing_limit | 120.49 | 22.133333333333333 |
| diagnose_processing_timeout | Saracens Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 0 | processing_limit | 120.33 | 20.633333333333333 |
| diagnose_processing_timeout | Saracens Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 2 | processing_limit | 120.28 | 20.15 |
| diagnose_processing_timeout | Vikings Mounted Crossbowman vs. Saracens Heavy Cavalry Archer / seed 0 | processing_limit | 120.43 | 11.516666666666667 |
| diagnose_processing_timeout | Vikings Mounted Crossbowman vs. Saracens Heavy Cavalry Archer / seed 1 | processing_limit | 120.14 | 12.316666666666666 |
| diagnose_processing_timeout | Vikings Mounted Crossbowman vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.10 | 11.316666666666666 |
| diagnose_processing_timeout | Berbers Hand Cannoneer vs. Saracens Heavy Cavalry Archer / seed 0 | processing_limit | 120.22 | 18.116666666666667 |
| diagnose_processing_timeout | Berbers Hand Cannoneer vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.27 | 19.233333333333334 |
| diagnose_processing_timeout | Burgundians Scorpion vs. Spanish Elite Skirmisher / seed 0 | processing_limit | 120.20 | 28.333333333333332 |
| diagnose_processing_timeout | Burgundians Scorpion vs. Spanish Elite Skirmisher / seed 1 | processing_limit | 120.25 | 23.4 |
| diagnose_processing_timeout | Mayans Elite Plumed Archer vs. Saracens Heavy Cavalry Archer / seed 0 | processing_limit | 120.15 | 41.4 |
| diagnose_processing_timeout | Mayans Elite Plumed Archer vs. Saracens Heavy Cavalry Archer / seed 1 | processing_limit | 120.43 | 8.683333333333334 |
| diagnose_processing_timeout | Mayans Elite Plumed Archer vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.42 | 8.7 |
| diagnose_processing_timeout | Franks Crossbowman vs. Spanish Hussar / seed 0 | processing_limit | 120.32 | 12.35 |
| diagnose_processing_timeout | Franks Crossbowman vs. Spanish Hussar / seed 1 | processing_limit | 120.95 | 8.05 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Saracens Heavy Cavalry Archer / seed 0 | processing_limit | 120.48 | 73.46666666666667 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Saracens Heavy Cavalry Archer / seed 1 | processing_limit | 120.52 | 76.5 |
| diagnose_processing_timeout | Bohemians Elite Hussite Wagon vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.48 | 69.65 |
| diagnose_processing_timeout | Portuguese Cavalier vs. Spanish Paladin / seed 0 | decided | 108.41 | 60.03333333333333 |
| diagnose_processing_timeout | Portuguese Cavalier vs. Spanish Paladin / seed 1 | decided | 109.12 | 60.03333333333333 |
| diagnose_processing_timeout | Portuguese Cavalier vs. Spanish Paladin / seed 2 | decided | 108.01 | 60.03333333333333 |
| diagnose_processing_timeout | Muisca Elite Guecha Warrior vs. Spanish Hussar / seed 0 | processing_limit | 120.46 | 42.516666666666666 |
| diagnose_processing_timeout | Muisca Elite Guecha Warrior vs. Spanish Hussar / seed 1 | processing_limit | 120.80 | 48.7 |
| diagnose_processing_timeout | Muisca Elite Guecha Warrior vs. Spanish Hussar / seed 2 | processing_limit | 120.34 | 31.316666666666666 |
| diagnose_processing_timeout | Dravidians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 0 | processing_limit | 120.27 | 23.2 |
| diagnose_processing_timeout | Dravidians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 1 | processing_limit | 120.32 | 22.216666666666665 |
| diagnose_processing_timeout | Dravidians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 2 | processing_limit | 120.47 | 31.916666666666668 |
| diagnose_processing_timeout | Cumans Crossbowman vs. Spanish Hussar / seed 0 | processing_limit | 120.16 | 15.033333333333333 |
| diagnose_processing_timeout | Cumans Crossbowman vs. Spanish Hussar / seed 1 | processing_limit | 120.63 | 7.916666666666667 |
| diagnose_processing_timeout | Georgians Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 0 | processing_limit | 120.51 | 20.133333333333333 |
| diagnose_processing_timeout | Georgians Heavy Cavalry Archer vs. Saracens Hand Cannoneer / seed 1 | processing_limit | 120.75 | 22.15 |
| diagnose_processing_timeout | Celts Crossbowman vs. Spanish Hussar / seed 0 | processing_limit | 120.19 | 12.15 |
| diagnose_processing_timeout | Celts Crossbowman vs. Spanish Hussar / seed 1 | processing_limit | 120.52 | 7.883333333333334 |
| diagnose_processing_timeout | Armenians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 0 | processing_limit | 120.19 | 23.833333333333332 |
| diagnose_processing_timeout | Armenians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 1 | processing_limit | 120.28 | 24.666666666666668 |
| diagnose_processing_timeout | Armenians Heavy Scorpion vs. Spanish Elite Skirmisher / seed 2 | processing_limit | 120.26 | 37.71666666666667 |
| diagnose_processing_timeout | Spanish Archer vs. Spanish Hussar / seed 0 | processing_limit | 120.15 | 12.333333333333334 |
| diagnose_processing_timeout | Spanish Archer vs. Spanish Hussar / seed 1 | processing_limit | 120.93 | 7.966666666666667 |
| diagnose_processing_timeout | Dravidians Heavy Scorpion vs. Saracens Heavy Cavalry Archer / seed 1 | processing_limit | 120.80 | 29.266666666666666 |
| diagnose_processing_timeout | Dravidians Heavy Scorpion vs. Saracens Heavy Cavalry Archer / seed 2 | processing_limit | 120.27 | 15.15 |
| diagnose_processing_timeout | Chinese Heavy Scorpion vs. Spanish Elite Skirmisher / seed 0 | processing_limit | 120.20 | 24.25 |
| diagnose_processing_timeout | Chinese Heavy Scorpion vs. Spanish Elite Skirmisher / seed 1 | processing_limit | 120.23 | 24.466666666666665 |
| diagnose_processing_timeout | Chinese Heavy Scorpion vs. Spanish Elite Skirmisher / seed 2 | decided | 111.05 | 51.53333333333333 |
| diagnose_processing_timeout | Bulgarians Archer vs. Spanish Hussar / seed 0 | processing_limit | 120.33 | 12.45 |
| extend_game_time | Aztecs Elite Skirmisher vs. Turks Cavalier / seed 2 | processing_limit | 121.15 | 168.86666666666667 |
| extend_game_time | Bohemians Mounted Crossbowman vs. Spanish Hussar / seed 0 | decided | 32.87 | 288.8 |
| extend_game_time | Khmer Elite Battle Elephant vs. Saracens Heavy Cavalry Archer / seed 0 | decided | 30.12 | 207.33333333333334 |
| extend_game_time | Shu War Chariot vs. Spanish Elite Skirmisher / seed 1 | decided | 47.62 | 202.03333333333333 |
| extend_game_time | Shu War Chariot vs. Spanish Elite Skirmisher / seed 2 | decided | 71.07 | 199.65 |
| extend_game_time | Britons Elite Skirmisher vs. Turks Cavalier / seed 2 | processing_limit | 121.15 | 148.21666666666667 |
| parity_control | Gurjaras Spearman vs. Chinese Arbalester / seed 2 | decided | 3.32 | 16.816666666666666 |
| parity_control | Wei Elite Tiger Cavalry vs. Chinese Arbalester / seed 2 | decided | 5.16 | 23.033333333333335 |
| parity_control | Jurchens Grenadier vs. Spanish Champion / seed 2 | decided | 2.46 | 11.65 |

Per-run `result.json` includes CPU hotspots, tick timings, last unit states, and original provenance. 
`timeline.jsonl` records progress, positions, targets, HP, and event counts. 
Raw CPU profiles and the copied runtime remain local to keep Git checkpoints manageable.
