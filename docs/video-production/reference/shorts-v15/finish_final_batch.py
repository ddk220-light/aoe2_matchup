"""Build the local review index after actual inspection of the ten review sheets."""
from datetime import datetime, timezone
from pathlib import Path
import run_batch
from build_story_batch import read, save

ROOT = Path(__file__).resolve().parent
DEST = ROOT/'final-v15'


def main():
    batch = read(ROOT/'batch.json')
    stamp = datetime.now(timezone.utc).isoformat()
    exports = []
    lines = ['# The ten approved-format Shorts','',
             'New v15-format exports from the existing planned recordings. '
             'All have dynamic sequential command-voice intros, two seconds of real aftermath, '
             'smooth victory transitions and the quieter victory cue.','',
             'Mounted units without spoken command responses use a spoken attack line from the same civilization, as selected by the user. '
             'A longer line finishes over the held final pose before the next unit starts.','',
             'The original P2/P3 order is preserved even when the planned matchup title lists the units in the opposite order.','']
    for item in batch['items']:
        out = DEST/f"{item['number']:02d}-{item['key']}"
        story, verification, audit = (read(out/name) for name in ('story.json','verification.json','timing-audit.json'))
        assert verification['media']=='passed'
        assert (out/'review-sheet.jpg').is_file()
        video = Path(story['video'])
        assert video.is_file()
        verification.update(visualReview='Actual-MP4 review sheet inspected by agent; user review pending',
                            agentReviewedAt=stamp)
        if item['number']==10:
            verification['visualReview']='Byte-identical copy of the user-approved Grenadier/Huskarl v15'
        audit.update(visualReview=verification['visualReview'],agentReviewedAt=stamp)
        save(out/'verification.json',verification)
        save(out/'timing-audit.json',audit)
        exports.append({'number':item['number'],'title':item['title'],'video':str(video),
            'durationSeconds':story['durationSeconds'],'battleStartSeconds':story['introSeconds'],
            'sha256':verification['sha256'],'reviewSheet':str(out/'review-sheet.jpg'),
            'media':'passed','agentVisualReview':verification['visualReview']})
        lines += [f"## {item['number']:02d}. {item['title']}",'',
            f"[Play video]({video.as_posix()}) · {story['durationSeconds']:.2f}s · Battle starts at {story['introSeconds']:.2f}s",'',
            f"![Review frames]({(out/'review-sheet.jpg').as_posix()})",'']
    assert len(exports)==10
    # Generated review artifact, not source-code editing.
    (DEST/'REVIEW.md').write_text('\n'.join(lines),encoding='utf-8')
    save(DEST/'completion.json',{'completedAt':stamp,'workflow':'docs/video-production/SHORTS_APPROVED_WORKFLOW.md',
        'exports':exports,'count':10,'published':False,'originalRecordingsModified':False})
    save(DEST/'status.json',{'phase':'ready_for_user_review','active':None,'completed':list(range(1,11)),
        'updatedAt':stamp,'index':str(DEST/'REVIEW.md')})
    print('Ten finished exports indexed:',DEST/'REVIEW.md')
    for entry in exports:
        print(f"{entry['number']:02d} | {entry['title']} | {entry['durationSeconds']:.2f}s | {entry['video']}")


if __name__=='__main__':
    main()
