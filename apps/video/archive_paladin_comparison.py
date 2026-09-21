"""Use the verified compact archiver for only the four Paladin-line campaigns."""
import archive_champi_geometric as archive


if __name__ == '__main__':
    archive.OUT = archive.ROOT / 'data/local/paladin-line-comparison'
    archive.JOB_PREFIX = 'paladin_line_'
    archive.ARCHIVE_PREFIX = 'paladin-line'
    archive.CIVS = ('franks', 'teutons', 'lithuanians', 'persians')
    archive.TITLE_PREFIX = 'Paladin Line'
    archive.PRESERVE_BASELINE = False
    archive.main()
