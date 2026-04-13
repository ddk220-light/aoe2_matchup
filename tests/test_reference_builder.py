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
