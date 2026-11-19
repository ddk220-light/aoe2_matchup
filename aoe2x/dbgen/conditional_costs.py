"""Conditional prices for audited regional/unique capture subjects.

These bonuses are not ordinary DAT cost-attribute commands. Keep their scope
explicit: the Saxon list covers the audited Hearth Troop and Varangian Guard
lines, not every possible foot unit. Audit additional lines before adding them.
"""

SAXON_FOOT_SOLDIER_IDS = frozenset((2703, 2704, 2705, 2706))


def has_max_saxon_foot_discount(civ, master):
    """Four controlled TCs/Castles give the requested maximum 20% discount.

    Installed English help 120209 supplies the percentage and building cap.
    The official Saxon deep dive explicitly includes Barracks Varangian Guards:
    https://www.ageofempires.com/news/saxons-civilization-deep-dive/
    Mounted Crossbowmen are not foot soldiers and must not receive this bonus.
    """
    return civ == 'Saxons' and master in SAXON_FOOT_SOLDIER_IDS
