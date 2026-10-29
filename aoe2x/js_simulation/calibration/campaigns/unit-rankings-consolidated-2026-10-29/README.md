# Consolidated unit-ranking results

Complete: **3591 opponent rows for 555 civilization/unit variants**, covering 2398 distinct matchups and 7600 required decided runs. No pending seeds, unresolved errors or timeouts. Scoring remains deferred.

The owner stopped the full recomputation and explicitly requested reuse of old results with completed corrected-engine results. **This dataset combines two engine versions.** It is complete under that requested consolidation policy; it is not a uniformly rerun corrected-engine benchmark. Each run identifies its source file, line, record/file hashes, input campaign and engine version; each table row identifies the versions contributing to its averages. Original campaigns are preserved.

- [Final table (CSV)](summary.csv) and [JSON](summary.json)
- [Every included run](runs.jsonl)
- [Validation and coverage](validation.json) and [independent audit](independent-validation.json)
- [Manifest and source fingerprints](manifest.json)
- [Superseded result references](replacements.json)
- [Additional already-recorded seeds](additional-recorded-runs.jsonl)

Included sources: {"original_campaign":6768,"stopped_refresh":684,"corrected_validation":127,"supplemental":21}. All 107 originally unresolved cases have decided replacements. 77 existing extra-seed results are retained separately because their selected initial outcomes no longer trigger expansion; averages use exactly the required 3 or 10 seeds. New supplemental simulations fill only gaps created by the expansion rule.

The 27-unit weighted-cost balance, zero buffers, opponent pools and exact mechanics-profile sharing are unchanged. The full refresh and scheduled check are stopped. Any future work estimated above one hour requires prior user approval.

Rebuild from saved inputs without simulations:

```bash
node aoe2x/js_simulation/node/consolidate-ranking-results.mjs
```
