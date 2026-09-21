"""Read-only checks for an explicitly selected recording archive volume."""
from pathlib import Path
import shutil


def archive_storage_error(guard):
    """Return a pause reason, never mount, modify, or repair the user's disk."""
    if not guard:
        return None
    import pywintypes
    root = Path(guard['root'])
    try:
        import win32api
        label, serial, *_ = win32api.GetVolumeInformation(root.anchor)
        if label != guard['label'] or serial != guard['volumeSerial']:
            return 'Archive volume identity changed; preserve local sources'
        if not root.is_dir():
            return 'Archive directory is unavailable; preserve local sources'
        if shutil.disk_usage(root).free < guard.get('reserveGiB', 4) * 2**30:
            return 'Archive reserve reached; preserve local sources'
    except (OSError, RuntimeError, pywintypes.error) as error:
        return f'Archive unavailable; preserve local sources: {error}'
    return None
