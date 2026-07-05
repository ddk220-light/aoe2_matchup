"""Emit ships/civ_region.json: each served civ -> sail region (+ region/ship lists).

Region is read from the dat (per-civ building graphic b_<region>_house). Building
sets without their own sail set reuse another (matches the wiki): South Asian/
Indian (indi) -> Middle Eastern (orie); Andean/South American (ande) -> Meso (meso).
"""
import sys, os, re, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sail_lib as S
from genieutils.datfile import DatFile

DAT = 'D:/SteamLibrary/steamapps/common/AoE2DE/resources/_common/dat/empires2_x2_p1.dat'

# served civs (must match apps/website/static/js/constants.js ENABLED_CIVS)
ENABLED = ["Armenians","Aztecs","Bengalis","Berbers","Bohemians","Britons","Bulgarians",
    "Burgundians","Burmese","Byzantines","Celts","Chinese","Cumans","Dravidians","Ethiopians",
    "Franks","Georgians","Goths","Gurjaras","Hindustanis","Huns","Incas","Italians","Japanese",
    "Jurchens","Khitans","Khmer","Koreans","Lithuanians","Magyars","Malay","Malians","Mapuche",
    "Mayans","Mongols","Muisca","Persians","Poles","Portuguese","Romans","Saracens","Shu",
    "Sicilians","Slavs","Spanish","Tatars","Teutons","Tupi","Turks","Vietnamese","Vikings","Wei","Wu"]

# site civ name -> dat civ name (only where they differ)
DAT_ALIAS = {"Britons":"British", "Franks":"French", "Byzantines":"Byzantine", "Mayans":"Mayan"}

# building region token -> sail region (sail-reuse for sets without their own sails)
REGION_REMAP = {'indi':'orie', 'ande':'meso', 'persian':'orie', 'greek':'medi',
                'thracian':'medi', 'puru':'orie'}

def cname(c):
    n = getattr(c, 'name', None)
    return n.split(b'\x00',1)[0].decode('latin1','replace') if isinstance(n, bytes) else (n or '')

def main():
    df = DatFile.parse(DAT)
    gby = {gr.id: gr for gr in df.graphics if gr}
    # building unit id whose graphic encodes the region (house, found earlier = 191)
    HOUSE = 191
    def region_for_civ(dat_name):
        for c in df.civs:
            if cname(c) == dat_name:
                u = c.units[HOUSE]
                sg = u.standing_graphic
                gid = sg[0] if isinstance(sg,(list,tuple)) else sg
                fn = (gby.get(gid).file_name if gby.get(gid) else '') or ''
                m = re.match(r'b_([a-z]+)_', fn.lower())
                tok = m.group(1) if m else None
                return REGION_REMAP.get(tok, tok)
        return None

    civ_region = {}
    missing = []
    for civ in ENABLED:
        dat_name = DAT_ALIAS.get(civ, civ)
        reg = region_for_civ(dat_name)
        if reg not in S.SAIL_REGIONS:
            missing.append((civ, dat_name, reg))
        civ_region[civ] = reg

    if missing:
        print("WARNING unmapped:", missing)

    out = {
        "civ_region": civ_region,
        "regions": list(S.SAIL_REGIONS),
        "ships": list(S.SHIP_HULLS.keys()),
        "sail_assignment": {k: f"{v[0]}_{v[1]}" for k, v in S.SAIL_ASSIGN.items()},
        "note": ("Per civ, region = civ_region[civ]; ship sprite at "
                 "ships/<region>/<ship>.png (player2 red), <ship>_blue.png (player1 blue), "
                 "<ship>.gif (animated). indi(S.Asian)->orie, ande(Andean)->meso sail reuse."),
    }
    dst = os.path.join(S._ROOT, '.scratch', 'ship_out', 'civ_region.json')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, 'w'), indent=2)
    from collections import Counter
    print("wrote", dst)
    print("region counts:", dict(Counter(civ_region.values())))
    print("civs mapped:", len(civ_region), "/ expected 53")

if __name__ == '__main__':
    main()
