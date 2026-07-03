"""Surgical patch: Rocket Cart all-primary volley + armor-ignoring rockets.

ROOT CAUSE
----------
The Rocket Cart line (Chinese/Koreans/Jurchens/Khitans replacement for the
mangonel line, slug stays ``siege_onager``) fires total_projectiles=10 rockets
per volley with dat ``secondary_projectile_unit = -1``: ALL projectiles are the
primary and each one deals its full 5 (6 Chinese) attack. The dat combat-ability
bitfield is 11 = ignore armor (1) + resist armor-ignoring (2) + attack ground
(8), i.e. each rocket ignores target armor (confirmed intentional on the
official forums: "Using many tiny damage projectiles, they would suck against
most units if they didn't ignore armor").

The extraction heuristic in ``combat_properties.get_extracted_combat_properties``
suppressed extra_projectiles for every siege-splash unit — correct for the
Mangonel line (its 5-9 secondaries point at damage-less visual projectile 369),
wrong for Rocket Carts. And ability bitfields are never extracted, so the
ignore-armor flags were missing. Net effect: the sims treated a Heavy Rocket
Cart as a 1-projectile pseudo-mangonel hitting a Paladin for ~4 damage per
volley instead of 10 rockets x 6 armor-ignoring damage = 60.

FIX
---
Recompute, for the four ``unit_name LIKE '%Rocket Cart%'`` rows, in all three
tables the values the (fixed) pipeline now produces from the dat +
``config_combat.CIV_COMBAT_PROPERTIES``:

  extra = total_projectiles - 1   (+1 for Jurchens Thunderclap Bombs, Imp UT)

  ref_units:           extra_projectiles = extra,
                       ignores_pierce_armor = ignores_melee_armor = 1
  ref_projectiles:     upsert the type='extra' row (projectile_count = extra,
                       speed/blast/is_siege copied from the primary row) —
                       generate_main_db reads extra_projectiles from HERE
  ref_special_effects: upsert the two ignore-armor rows (audit/UI) —
                       generate_main_db reads the ignore flags from HERE

This is a surgical patch on the committed DB because a full pipeline regen
needs the extracted dat JSONs (not in the repo) and rewrites combat-property
columns on every row. After running it, re-run
``python -m aoe2x.dbgen.generate_main_db`` so aoe2_units.db matches.

Blanket ignore flags carry no armor-ignore-resist exception (armor class 31):
the only resisting targets are siege units whose melee armor is ~0, so the
in-sim error is nil.

Idempotent: always recomputes from ``total_projectiles``, so re-running is a
no-op.

Run:  python -m aoe2x.dbgen.patches.patch_rocket_cart_volley          (apply)
      python -m aoe2x.dbgen.patches.patch_rocket_cart_volley --dry    (preview)
"""
import os
import sqlite3
import sys

from aoe2x.paths import GOLDEN_DIR as _GOLDEN_DIR

DB = os.path.join(str(_GOLDEN_DIR), "aoe2_reference.db")

# Jurchens Thunderclap Bombs (Imp UT): +1 projectile on top of the volley.
CIV_EXTRA_BONUS = {"Jurchens": 1}


def main():
    dry = "--dry" in sys.argv
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, civ_name, unit_slug, unit_name, total_projectiles, "
        "extra_projectiles, ignores_pierce_armor, ignores_melee_armor "
        "FROM ref_units WHERE unit_name LIKE '%Rocket Cart%' "
        "ORDER BY civ_name, unit_slug"
    )
    rows = cur.fetchall()
    if not rows:
        print("  WARN: no Rocket Cart rows found — nothing to patch")
    changed = 0
    for r in rows:
        uid = r["id"]
        total = int(r["total_projectiles"] or 1)
        extra = max(0, total - 1) + CIV_EXTRA_BONUS.get(r["civ_name"], 0)

        # -- ref_units columns ------------------------------------------------
        old = (r["extra_projectiles"], r["ignores_pierce_armor"],
               r["ignores_melee_armor"])
        new = (extra, 1, 1)

        # -- ref_projectiles type='extra' row (generate_main_db reads this) ---
        cur.execute(
            "SELECT id, projectile_count FROM ref_projectiles "
            "WHERE ref_unit_id=? AND projectile_type='extra'", (uid,))
        extra_row = cur.fetchone()
        old_extra_count = extra_row["projectile_count"] if extra_row else None

        # -- ref_special_effects ignore-armor rows (audit/UI + main-db) -------
        cur.execute(
            "SELECT property_name FROM ref_special_effects "
            "WHERE ref_unit_id=? AND property_name IN "
            "('ignores_pierce_armor', 'ignores_melee_armor')", (uid,))
        have_fx = {x["property_name"] for x in cur.fetchall()}
        missing_fx = [p for p in ("ignores_pierce_armor", "ignores_melee_armor")
                      if p not in have_fx]

        dirty = old != new or old_extra_count != extra or missing_fx
        mark = "  <-- CHANGED" if dirty else ""
        print(
            f"  {r['civ_name']:10s} {r['unit_slug']:14s} "
            f"({r['unit_name']}) total_proj={total:2d}  "
            f"units(extra, ign_p, ign_m) {tuple(old)} -> {new}  "
            f"proj_extra {old_extra_count} -> {extra}  "
            f"fx missing {missing_fx}{mark}"
        )
        if not dirty or dry:
            continue

        cur.execute(
            "UPDATE ref_units SET extra_projectiles=?, "
            "ignores_pierce_armor=?, ignores_melee_armor=? WHERE id=?",
            (extra, 1, 1, uid),
        )
        if extra_row:
            cur.execute(
                "UPDATE ref_projectiles SET projectile_count=? WHERE id=?",
                (extra, extra_row["id"]),
            )
        else:
            # Copy speed/blast/is_siege from the primary projectile row.
            cur.execute(
                "INSERT INTO ref_projectiles (ref_unit_id, projectile_type, "
                "projectile_count, projectile_speed, attacks_json, "
                "blast_radius, is_siege_projectile) "
                "SELECT ref_unit_id, 'extra', ?, projectile_speed, NULL, "
                "blast_radius, is_siege_projectile FROM ref_projectiles "
                "WHERE ref_unit_id=? AND projectile_type='primary'",
                (extra, uid),
            )
        for prop in missing_fx:
            kind = "pierce" if "pierce" in prop else "melee"
            cur.execute(
                "INSERT INTO ref_special_effects (ref_unit_id, property_name, "
                "property_value, source, description) VALUES (?,?,?,?,?)",
                (uid, prop, "1", "CIV_COMBAT_PROPERTIES",
                 f"Unit ignores {kind} armor"),
            )
        changed += 1
    if dry:
        print("DRY RUN -- no changes written")
    else:
        conn.commit()
        print(f"Committed. Rows changed: {changed}")
    conn.close()


if __name__ == "__main__":
    main()
