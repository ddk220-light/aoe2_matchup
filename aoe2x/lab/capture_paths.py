"""Bound internal capture filenames without changing frozen matchup identity."""
from pathlib import Path


def capture_prefix(run_directory: Path, matchup_id: str) -> Path:
    directory = run_directory / 'raw recordings'
    descriptive = directory / matchup_id
    # The video can fit while .frames.bin crosses Windows MAX_PATH. Use the
    # longest required suffix to select one consistent stem for every sidecar.
    # Each run has its own directory; the manifest retains the descriptive ID.
    if len(str(descriptive.absolute()) + '.frames.bin') >= 260:
        return directory / 'capture'
    return descriptive
