# Consistent engine refresh

Recompute all 2398 distinct matchups (3591 table rows) on the corrected engine. Keep the approved profiles, opponent pools, 27-unit balancing, three-to-ten seed rule and 23 review phases. No old pilot or campaign outcomes are imported.

Use four persistent workers. Save every run to SQLite and fsynced JSONL; record game time and processing time, including the last heartbeat on a processing cutoff. There is no practical game-time cutoff. Keep the 120-second processing watchdog and report every unresolved run.

Each phase checks source fingerprints, coverage, database integrity and an exact-seed replay. Advance automatically after those checks. Publish at each phase boundary, 250 new results, or ten minutes. Resume uses existing journals and records. Scoring and browser integration remain deferred.
