"""Archive correction captures separately so every zero-relic baseline survives."""
import argparse
import archive_champi_geometric as archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign',choices=['paladin','cavalier'])
    args = parser.parse_args()
    archive.OUT = archive.ROOT / f'data/local/{args.campaign}-leitis-four-relics'
    archive.JOB_PREFIX = 'paladin_line_' if args.campaign == 'paladin' else 'cavalier_'
    archive.ARCHIVE_PREFIX = f'{args.campaign}-leitis-four-relics'
    archive.CIVS = ('franks','teutons','lithuanians','persians') if args.campaign == 'paladin' else ('bulgarians','poles','burmese','sicilians')
    archive.TITLE_PREFIX = f'{args.campaign.title()} Leitis Four Relics'
    archive.PRESERVE_BASELINE = False  # Originals already occupy separate archive directories.
    archive.main()
