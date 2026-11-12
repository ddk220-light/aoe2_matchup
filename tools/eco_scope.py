"""Scenario scopes for source-identified economic effects.

This controls relevance, never the numeric magnitude of a bonus. Effect IDs
refer to the supplied DAT; original evidence is retained in review tables.
"""

EARLY_FOOD = {381, 523, 388, 414, 741, 510, 1381, 993}
EARLY_GRANTS = {213, 866, 868, 613, 614, 615, 215, 302, 937, 872,
                227, 230, 216, 586, 212, 217, 1394}
TECHNOLOGY = {304, 349, 350, 351, 32, 181, 237, 804}
CONDITIONAL_LAND = {790, 939, 827, 1071, 669, 881, 882, 883, 1061, 621}
TRADE_RELIC = {488, 841, 783, 490, 1490, 554}


def mechanic_scope(m):
    eid, category = m.get('effect_id'), m.get('category')
    if eid in EARLY_FOOD:
        return 'excluded_finite_early_food'
    if eid in EARLY_GRANTS or category == 'one_time':
        return 'excluded_start_or_age_grant'
    if eid in TECHNOLOGY or category == 'research_reward':
        return 'technology_investment'
    if eid in CONDITIONAL_LAND:
        return 'conditional_land_income'
    if eid in TRADE_RELIC or category in ('passive_income', 'trade', 'conditional_relic'):
        return 'conditional_trade_or_relic'
    if eid == 1475 or category in ('fishing', 'trade_and_fishing') or eid in {863, 434, 435, 436, 675, 677, 10, 411}:
        return 'conditional_water_economy'
    if category in ('replacement_refund', 'combat_income', 'workforce_event') or eid in {792, 1488}:
        return 'conditional_military_event'
    if category in ('population',) or eid in {418, 448}:
        return 'population_capacity'
    if category in ('building_event', 'setup_cost', 'setup_speed', 'setup_and_area', 'repair', 'special_infrastructure') or eid in {953, 575, 171, 165, 795, 168, 759, 760, 551, 552, 553, 585}:
        return 'infrastructure_or_worker_replacement'
    if category == 'pasture':
        return 'pasture_model_required'
    if category == 'garrison_income':
        return 'conditional_garrison_income'
    if category == 'market':
        return 'conditional_market'
    if category == 'worker_protection' or eid == 1404:
        return 'protection_or_information'
    if eid == 33:
        return 'unit_resource_demand'
    if category in ('work_rate', 'carry', 'movement', 'resource_yield', 'recurring_cost', 'farm_event', 'drop_off', 'construction', 'gold_and_trade') or eid in {956, 958, 959}:
        return 'sustained_land_parameters'
    return 'review_scope_required'


def blocks_land_labor(m):
    return mechanic_scope(m) == 'conditional_land_income' or m.get('category') == 'replacement_refund'
