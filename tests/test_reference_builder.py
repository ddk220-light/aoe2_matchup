"""Tests for the reference corpus generator — pure functions only."""
import sys
sys.path.insert(0, "scripts")
import importlib.util

# Load the script as a module without running main()
spec = importlib.util.spec_from_file_location("builder", "scripts/build_reference_docs.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


# --- Wiki parser tests ---

SAMPLE_CIV_WIKITEXT = """
{{Civilization infobox
|name=Aztecs
|focus=Infantry & Monk
|team_bonus=Relics generate +33% gold
|unique_unit=[[Jaguar Warrior]]<br>[[Elite Jaguar Warrior]]
|unique_tech_castle=[[Atlatl]] (400 food, 350 wood)
|unique_tech_imperial=[[Garland Wars]] (450 food, 750 gold)
|bonuses=
* Villagers carry +5
* Military units created 11% faster
* Monks +5 HP per Monastery technology researched
}}
"""

def test_parse_wiki_civ_bonuses():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert "Villagers carry +5" in result["bonuses"]
    assert len(result["bonuses"]) == 3

def test_parse_wiki_civ_team_bonus():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert result["team_bonus"] == "Relics generate +33% gold"

def test_parse_wiki_civ_unique_techs():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert any("Atlatl" in t["name"] for t in result["unique_techs"])
    castle_tech = next(t for t in result["unique_techs"] if t["age"] == "Castle")
    assert "400" in castle_tech["cost"]

def test_parse_wiki_civ_unique_units():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert "Jaguar Warrior" in result["unique_units"]

def test_parse_wiki_civ_focus():
    result = builder.parse_wiki_civ(SAMPLE_CIV_WIKITEXT)
    assert result["focus"] == "Infantry & Monk"


# --- Unit wikitext parser tests ---

SAMPLE_UNIT_WIKITEXT = """
{{Unit infobox
|name=Jaguar Warrior
|hp=50
|attack=10
|melee_armor=1
|pierce_armor=0
|speed=1.0
|range=0
|reload_time=2
|cost=60 food, 30 gold
|train_time=21 seconds
|pop_space=1
|attack_bonus=+10 vs Infantry<br>+5 vs Eagle Warriors
}}
"""

def test_parse_wiki_unit_hp():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert result["hp"] == 50.0

def test_parse_wiki_unit_attack_bonuses():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert len(result["attack_bonuses"]) >= 1

def test_parse_wiki_unit_cost():
    result = builder.parse_wiki_unit(SAMPLE_UNIT_WIKITEXT)
    assert result["cost_food"] == 60
    assert result["cost_gold"] == 30
    assert result["cost_wood"] == 0


# --- DB query tests (in-memory sqlite) ---
import sqlite3

def make_test_db():
    """Create a minimal in-memory DB that mirrors ref_units schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE ref_units (
            id INTEGER PRIMARY KEY,
            civ_name TEXT, unit_name TEXT, unit_slug TEXT, unit_type TEXT, age TEXT,
            base_hp REAL, base_attack REAL, base_melee_armor REAL, base_pierce_armor REAL,
            base_speed REAL, base_range REAL, base_reload_time REAL,
            base_cost_food REAL, base_cost_wood REAL, base_cost_gold REAL,
            base_attacks_json TEXT, base_armors_json TEXT, pop_space REAL DEFAULT 1,
            has_unit INTEGER DEFAULT 1
        );
        CREATE TABLE ref_special_effects (
            id INTEGER PRIMARY KEY,
            ref_unit_id INTEGER,
            property_name TEXT,
            property_value REAL
        );
        CREATE TABLE armor_classes (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        INSERT INTO ref_units VALUES
            (1,'Aztecs','Jaguar Warrior','jaguar_warrior_aztecs','unique','Castle',
             50,10,1,0,1.0,0,2.0,60,0,30,'{"1":10}','{}',1,1),
            (2,'Aztecs','Elite Jaguar Warrior','elite_jaguar_warrior_aztecs','unique','Imperial',
             75,12,1,0,1.0,0,2.0,60,0,30,'{"1":12}','{}',1,1);
        INSERT INTO ref_special_effects VALUES (1,1,'attack_bonus_per_kill',4);
        INSERT INTO armor_classes VALUES (0,'Unused'),(1,'Infantry'),(8,'Cavalry');
    """)
    return conn

def test_query_db_unit_base_stats():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert result["Castle"]["base_hp"] == 50
    assert result["Castle"]["base_attack"] == 10

def test_query_db_unit_special_effects():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert result["Castle"]["attack_bonus_per_kill"] == 4

def test_query_db_unit_both_ages():
    conn = make_test_db()
    result = builder.query_db_unit(conn, "jaguar_warrior_aztecs")
    assert "Castle" in result
    assert "Imperial" in result

def test_query_armor_classes():
    conn = make_test_db()
    result = builder.query_armor_classes(conn)
    assert result[0]["name"] == "Unused"
    assert result[1]["name"] == "Infantry"

def test_query_db_civ():
    conn = make_test_db()
    result = builder.query_db_civ(conn, "Aztecs")
    slugs = [u["unit_slug"] for u in result["unique"]]
    assert "jaguar_warrior_aztecs" in slugs


# --- Comparison engine tests ---

def test_compare_val_match_exact():
    assert builder.compare_val(50, 50) == builder.MATCH

def test_compare_val_match_float_tolerance():
    assert builder.compare_val(0.96, 0.9600) == builder.MATCH

def test_compare_val_mismatch():
    assert builder.compare_val(50, 55) == builder.MISMATCH

def test_compare_val_mismatch_outside_tolerance():
    assert builder.compare_val(0.96, 0.98) == builder.MISMATCH

def test_compare_val_missing_external():
    assert builder.compare_val(None, 50) == builder.MISSING_EXT

def test_compare_val_missing_db():
    assert builder.compare_val(50, None) == builder.NOT_IN_DB

def test_compare_val_both_none():
    assert builder.compare_val(None, None) == builder.MISSING_EXT

def test_compare_val_string_match():
    assert builder.compare_val("Infantry", "Infantry") == builder.MATCH

def test_compare_val_string_case_insensitive():
    assert builder.compare_val("Infantry", "infantry") == builder.MATCH

def test_compare_val_string_mismatch():
    assert builder.compare_val("Infantry", "Cavalry") == builder.MISMATCH


# --- Techtree helper tests ---

SAMPLE_TECHTREE = {
    "units": {
        "359": {
            "id": 359, "name": "Arbalester", "age": 4,
            "hp": 40, "attack": 6, "armor": "0/0",
            "speed": 0.96, "range": 5, "reloadTime": 2.0,
            "cost": {"Food": 25, "Wood": 45},
            "trainTime": 27, "populationUse": 1,
        }
    },
    "civs": [{"name": "Aztecs", "uniqueTechs": []}]
}

def test_find_techtree_unit_found():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "Arbalester")
    assert result is not None
    assert result["id"] == 359

def test_find_techtree_unit_case_insensitive():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "arbalester")
    assert result is not None

def test_find_techtree_unit_not_found():
    result = builder.find_techtree_unit(SAMPLE_TECHTREE, "Nonexistent Unit")
    assert result is None

def test_techtree_unit_stats_armor_parsing():
    unit = {"armor": "1/3", "hp": 50, "attack": 8, "speed": 1.0, "cost": {}}
    result = builder.techtree_unit_stats(unit)
    assert result["melee_armor"] == 1
    assert result["pierce_armor"] == 3

def test_techtree_unit_stats_cost():
    unit = {"armor": "0/0", "cost": {"Food": 60, "Gold": 30}}
    result = builder.techtree_unit_stats(unit)
    assert result["cost_food"] == 60
    assert result["cost_gold"] == 30
    assert result["cost_wood"] == 0
