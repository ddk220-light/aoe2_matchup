"""Archive verified Cavalier raw/frames pairs using the checked compact workflow."""
import archive_champi_geometric as archive

if __name__=='__main__':
    archive.OUT=archive.ROOT/'data/local/cavalier-comparison'
    archive.JOB_PREFIX='cavalier_'
    archive.ARCHIVE_PREFIX='cavalier'
    archive.CIVS=('bulgarians','poles','burmese','sicilians')
    archive.TITLE_PREFIX='Cavalier'
    archive.PRESERVE_BASELINE=False
    archive.main()
