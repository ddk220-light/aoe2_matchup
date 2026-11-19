"""Verify the authorized r06 delivery without rehashing unrelated old footage."""
import shutil
from pathlib import Path

from compact_recording_archive import digest, read
from copy_capture_campaign import now
from prepare_donut_color_sixth_iteration import WORK, SUBJECTS
from run_champi_comparison_capture import save


def main():
    queue = read(WORK / 'queue.json')
    delivery = read(WORK / 'delivery/status.json')
    assert read(WORK / 'status.json')['state'] == 'COMPLETE'
    assert delivery['state'] == 'COMPLETE' and delivery['verified'] == 24
    verified = []
    for campaign in queue['campaigns']:
        directory = Path(campaign['workDirectory'])
        status = read(directory / 'capture/status.json')
        assert status['state'] == 'COMPLETE' and status['completed'] == campaign['total']
        assert not status['failed'] and not status['pendingExports']
        destination = Path(campaign['destination'])
        receipt = delivery['packages'][campaign['slug']]
        assert receipt['state'] == 'COMPLETE'
        assert digest(destination / 'run.json') == receipt['indexSha256']
        index = read(destination / 'run.json')
        old = read(directory / 'previous-run.json')
        assert index['matchups'][:len(old['matchups'])] == old['matchups']
        added = index['matchups'][len(old['matchups']):]
        manifest = read(directory / 'manifest.json')['matchups']
        assert {r['jobId'] for r in added} == {r['id'] for r in manifest}
        assert len(added) == SUBJECTS[campaign['slug']]
        for row in added:
            assert row['iteration'] == 6 and row['colorCorrected']
            assert row['name'].endswith('_r06 - Donut - Color Corrected')
            scenario = row['capture']['scenario']
            owner = row['subjectOwner']
            assert scenario['subjectOwner'] == owner
            assert scenario['playerColors'] == {str(owner): 0, str(5-owner): 1}
            assert scenario['playerColorsMatchPlan'] and scenario['playerRuntimeConfigurationMatchesPlan']
            assert scenario['player4Count'] == 0
            # The copier already verified both hashes; check the published references
            # and current presence/size, without rereading all old recordings.
            assert set(row['files']) == {'battle.mp4', 'frames.bin'}
            for info in row['files'].values():
                assert (destination / info['path']).stat().st_size == info['bytes']
        for info in index['extensions'][-1]['metadata']:
            assert (destination / info['path']).stat().st_size == info['bytes']
        verified.append(dict(subject=campaign['slug'], addedPairs=len(added),
            preservedPriorRows=len(old['matchups']), destination=str(destination),
            indexSha256=receipt['indexSha256']))
    result = dict(state='COMPLETE', completedAt=now(), videoFramePairs=24,
        iteration=6, colorPolicy='subject_blue_opponent_red_v1', subjects=verified,
        localFreeBytes=shutil.disk_usage(WORK).free,
        shareFreeBytes=shutil.disk_usage(queue['campaigns'][0]['destination']).free,
        checksumEvidence='delivery/status.json; copier verified source and destination SHA-256',
        localSourcesRetained=True)
    save(WORK / 'final-verification.json', result)
    print(result)


if __name__ == '__main__':
    main()
