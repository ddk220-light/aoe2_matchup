from pathlib import Path
import json, shutil, subprocess
root=Path(__file__).resolve().parents[2]
work=root/'.scratch/asset-completion'
slugs=['heavy_mounted_crossbowman','savar']
descriptions=json.loads((work/'art-descriptions.json').read_text())
descriptions['heavy_mounted_crossbowman']="One heavy mounted crossbowman on a gray horse with chainmail barding and red saddle cloth. Copy the icon's compact red helmet, SMALL upturned silver visor and visible face exactly. Silver shoulder plates and brown leather clothing. Copy the single wooden crossbow's exact shape and proportions from the icon, held raised as in the sprite. Complete horse and rider."
descriptions['savar']="A Persian Savar on a dark horse in silver chainmail barding and red-edged trappings. Match the icon exactly: fitted silver helmet with five broad diagonal spiral flutes and a gold brow band, normal human head proportions, mail face veil with visible eye opening, gold armor, broad curved saber, red round shield with gold curling relief. Full horse and rider."
for p in (work/'art-descriptions.json',root/'graphics/asset_completion_2026-09-22/art-descriptions.json'):
    p.write_text(json.dumps(descriptions,indent=2))
backup=work/'superseded-second-render'; backup.mkdir(exist_ok=True)
for slug in slugs:
    for kind in ('bg','nobg','icon'):
        path=root/f'graphics/art/flux2_hybrid/{slug}_idle_dir05_{kind}.png'
        assert path.resolve().is_relative_to((root/'graphics/art/flux2_hybrid').resolve())
        assert not (backup/path.name).exists()
        shutil.move(str(path),str(backup/path.name))
    shutil.copy2(work/f'{slug}-generation.json',backup/f'{slug}-generation.json')
source=(root/'.scratch/generate_missing_unit_art.py').read_text().replace('seed=7','seed=21').replace('manual_seed(7)','manual_seed(21)')
script=root/'.scratch/generate_heavy_revision3.py'; script.write_text(source)
subprocess.run(['D:/miniconda3/envs/visomaster/python.exe',str(script),*slugs],check=True)
subprocess.run(['D:/miniconda3/python.exe',str(root/'.scratch/finish_unit_art.py'),*slugs],check=True)
subprocess.run(['D:/miniconda3/python.exe',str(root/'.scratch/art_detail_review.py'),*slugs],check=True)
