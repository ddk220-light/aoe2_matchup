"""Check the video handoff's local Markdown links and section anchors.

Does not fetch remote URLs, inspect credentials, or start production. Historical
documents are link targets; their dated local artifact paths are not recursively
treated as prerequisites of the current runbook.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def headings(path):
    text = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8-sig'), flags=re.S)
    result = set()
    counts = {}
    for label in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, flags=re.M):
        slug = re.sub(r'[^\w\- ]', '', label.lower()).replace(' ', '-')
        index = counts.get(slug, 0)
        counts[slug] = index + 1
        result.add(slug + (f'-{index}' if index else ''))
    return result


def check():
    documents = [ROOT / 'docs/VIDEO_PRODUCTION_RUNBOOK.md',
                 *sorted((ROOT / 'docs/video-production').glob('*.md'))]
    errors, count = [], 0
    for source in documents:
        text = re.sub(r'```.*?```', '', source.read_text(encoding='utf-8-sig'), flags=re.S)
        for link in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', text):
            parts = urlsplit(link)
            if parts.scheme or parts.netloc:
                continue
            count += 1
            target = (source.parent / unquote(parts.path)).resolve() if parts.path else source
            reason = None
            if not target.exists():
                reason = 'target missing'
            elif parts.fragment and target.suffix == '.md' and unquote(parts.fragment) not in headings(target):
                reason = 'section anchor missing'
            if reason:
                errors.append(dict(source=str(source.relative_to(ROOT)), link=link, reason=reason))
    return dict(passed=not errors, documents=len(documents), localLinks=count, errors=errors)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
