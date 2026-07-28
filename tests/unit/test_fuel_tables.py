"""
Unit tests for canonical per-engine per-warp fuel tables (DEF-7).

Verifies parity with the C# reference:
- Common/Components/Engine.cs (FuelConsumption[10], FreeWarpSpeed)
- Common/Components/ShipDesign.cs lines 721-744 (burn formula:
  (mass + cargo) * table[warp - 1] / 100 * warp^2 / 200, IFE x0.85)
- Common/GameObjects/Fleet.cs lines 586-608 (cargo distributed over
  tokens by cargo capacity share)

Deliberate web mods under test:
- ramscoop tables carry NEGATIVE entries at their free warps
  (backend/data/components.xml; C# uses 0) - entries <= 0 burn 0
- Fuel property "Generation" is subtracted from a design's burn
"""

import os
import xml.etree.ElementTree as ET

import pytest

from backend.core.components.engine import (
    Engine, WEB_MOD_RAMSCOOP_ENGINES,
)
from backend.core.data_structures.cargo import Cargo
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.race.race import Race
from backend.services.ship_specs import (
    STARTING_DESIGN_SPECS, _design_from_spec, _free_warp_from_table,
    engine_fuel_table, make_token, SimpleDesign,
)

# Tables come from the single source, backend/data/components.xml -
# no literals here. The docstrings below keep the numeric burn
# expectations, which anchor the arithmetic
QUICK_JUMP_5 = engine_fuel_table("Quick Jump 5")
FUEL_MIZER_WEB = engine_fuel_table("Fuel Mizer")
GALAXY_SCOOP_WEB = engine_fuel_table("Galaxy Scoop")
SETTLERS_DELIGHT_WEB = engine_fuel_table("Settler's Delight")

# The source file itself, parsed independently of the component loader
WEB_XML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))),
    "backend", "data", "components.xml")
CANON_XML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))),
    "references", "original-game", "components.xml")


def _tables_from_xml(path):
    """Engine name -> fuel table, read straight out of the XML."""
    tables = {}
    for component in ET.parse(path).getroot().findall("Component"):
        name = component.find("Item/Name").text
        for prop in component.findall("Property"):
            consumption = prop.find("FuelConsumption")
            if consumption is not None:
                tables[name] = [
                    int(consumption.find("Warp%d" % i).text)
                    for i in range(10)
                ]
    return tables


def _spec(name):
    return next(s for s in STARTING_DESIGN_SPECS if s["name"] == name)


def _fleet_with(token, cargo_mass=0):
    fleet = Fleet()
    fleet.tokens = {token.design_key: token}
    if cargo_mass:
        fleet.cargo = Cargo(ironium=cargo_mass)
    return fleet


class TestTokenTableWiring:
    """make_token caches the design's engine fuel table."""

    def test_every_ship_spec_mounts_an_engine(self):
        """Every starting ship carries an engine; the starbase none
        (StarMapInitialiser.cs:140-151)."""
        for spec in STARTING_DESIGN_SPECS:
            if spec["name"] == "Starbase":
                assert "engine" not in spec
            else:
                assert spec.get("engine"), spec["name"]

    def test_quick_jump_5_table_on_scout_token(self):
        token = make_token(_design_from_spec(_spec("Long Range Scout")))
        assert token.fuel_table == QUICK_JUMP_5

    def test_settlers_delight_table_on_spore_cloud(self):
        token = make_token(_design_from_spec(_spec("Spore Cloud")))
        assert token.fuel_table == SETTLERS_DELIGHT_WEB

    def test_spore_cloud_free_warp_derived_from_table(self):
        """Settler's Delight is free through warp 6 (table entry at
        warp 6 is <= 0); the old hand-set spec value 5 is corrected."""
        design = _design_from_spec(_spec("Spore Cloud"))
        assert design.free_warp_speed == 6
        assert make_token(design).free_warp_speed == 6

    def test_starbase_token_all_zero_table(self):
        token = make_token(_design_from_spec(_spec("Starbase")))
        assert token.fuel_table == [0] * 10

    def test_full_ship_design_engine_table_cached(self):
        """A design exposing a fitted Engine (full ShipDesign path)
        has its table copied onto the token (Engine.cs:34)."""
        class _Design:
            key = 7
            name = "Custom"
            engine = Engine(fuel_consumption=list(FUEL_MIZER_WEB))
            fuel_generation = 0
        token = make_token(_Design())
        assert token.fuel_table == FUEL_MIZER_WEB


class TestBurnFormula:
    """Fleet.fuel_consumption - ShipDesign.cs:721-744 per token."""

    def _scout_fleet(self):
        return _fleet_with(
            make_token(_design_from_spec(_spec("Long Range Scout"))))

    def test_scout_warp5(self):
        """warp 5 reads table[4] = 100 (ShipDesign.cs:732 indexes
        [warp - 1]): 25 x 100/100 x 25 / 200 = 3.125 mg/yr."""
        fleet = self._scout_fleet()
        assert fleet.fuel_consumption(5, Race()) == pytest.approx(3.125)

    def test_scout_warp6(self):
        """warp 6 reads table[5] = 180: 25 x 180/100 x 36 / 200 =
        8.1 mg/yr."""
        fleet = self._scout_fleet()
        assert fleet.fuel_consumption(6, Race()) == pytest.approx(8.1)

    def test_scout_warp8_uses_index_seven(self):
        """warp 8 reads table[7] = 800: 25 x 800/100 x 64 / 200 =
        64 mg/yr."""
        fleet = self._scout_fleet()
        assert fleet.fuel_consumption(8, Race()) == pytest.approx(64.0)

    def test_scout_warp1_free(self):
        """Quick Jump 5 table entry at warp 1 is 0."""
        fleet = self._scout_fleet()
        assert fleet.fuel_consumption(1, Race()) == 0.0

    def test_warp0_and_out_of_range(self):
        fleet = self._scout_fleet()
        assert fleet.fuel_consumption(0, Race()) == 0.0
        assert fleet.fuel_consumption(11, Race()) == 0.0

    def test_ife_reduces_15_percent(self):
        """ShipDesign.cs:739-742."""
        fleet = self._scout_fleet()
        race = Race()
        race.traits.add("IFE")
        assert fleet.fuel_consumption(5, race) == pytest.approx(3.125 * 0.85)

    def test_quadratic_by_warp_character(self):
        """Burn per light year is table[warp - 1]/20000 per kT - the
        w6/w5 ratio is 180/100 and w8/w5 is 800/100, not the linear
        model's 6/5 and 8/5."""
        fleet = self._scout_fleet()
        per_ly = {w: fleet.fuel_consumption(w, Race()) / (w * w)
                  for w in (5, 6, 8)}
        assert per_ly[6] / per_ly[5] == pytest.approx(180 / 100)
        assert per_ly[8] / per_ly[5] == pytest.approx(800 / 100)

    def test_cargo_mass_adds_to_burn(self):
        """(mass + cargo) scaling on a freighter token: Teamster
        mass 60 cargo capacity 70, fully loaded at warp 6 burns
        (60 + 70) x 180/100 x 36 / 200 mg/yr (Fleet.cs:590-600)."""
        token = make_token(_design_from_spec(_spec("Teamster")))
        fleet = _fleet_with(token, cargo_mass=70)
        expected = (60 + 70) * 1.8 * 36 / 200.0
        assert fleet.fuel_consumption(6, Race()) == pytest.approx(expected)

    def test_quantity_scales_burn(self):
        token = make_token(_design_from_spec(_spec("Long Range Scout")),
                           quantity=3)
        fleet = _fleet_with(token)
        assert fleet.fuel_consumption(5, Race()) == pytest.approx(3 * 3.125)

    def test_negative_table_entry_burns_zero(self):
        """Web ramscoop mod: negative entries are free, never a
        negative burn (Spore Cloud at warp 5, table entry -1300)."""
        fleet = _fleet_with(
            make_token(_design_from_spec(_spec("Spore Cloud"))))
        for warp in range(1, 7):
            assert fleet.fuel_consumption(warp, Race()) == 0.0
        assert fleet.fuel_consumption(7, Race()) > 0.0

    def test_fuel_generation_subtracted_and_clamped(self):
        """Web mod mirroring ShipDesign.fuel_consumption's Generation
        subtraction (ship_design.py) - reduces burn, floors at 0."""
        token = make_token(_design_from_spec(_spec("Long Range Scout")))
        token.fuel_generation = 3
        fleet = _fleet_with(token)
        assert fleet.fuel_consumption(5, Race()) == pytest.approx(3.125 - 3)
        token.fuel_generation = 1000
        assert fleet.fuel_consumption(5, Race()) == 0.0

    def test_legacy_all_zero_table_burns_zero(self):
        """Tokens deserialized from saves that predate fuel_table
        default to all zeros and burn nothing."""
        token = ShipToken(design_key=1, mass=25, quantity=1)
        assert _fleet_with(token).fuel_consumption(8, Race()) == 0.0


class TestFreeWarpDetection:
    """Engine.free_warp_speed with the web negative-table mod."""

    def test_fuel_mizer_web_table(self):
        engine = Engine(fuel_consumption=list(FUEL_MIZER_WEB))
        assert engine.free_warp_speed == 4

    def test_galaxy_scoop_web_table(self):
        engine = Engine(fuel_consumption=list(GALAXY_SCOOP_WEB))
        assert engine.free_warp_speed == 9

    def test_canonical_zero_tables_unchanged(self):
        """C# Engine.cs:43-56 semantics preserved for zero entries."""
        canonical_mizer = [0, 0, 0, 0, 35, 120, 175, 235, 360, 420]
        assert Engine(
            fuel_consumption=canonical_mizer).free_warp_speed == 4
        assert Engine(
            fuel_consumption=list(QUICK_JUMP_5)).free_warp_speed == 1

    def test_all_burning_table_has_no_free_warp(self):
        assert Engine(fuel_consumption=[10] * 10).free_warp_speed == 0


class TestSerialization:
    """fuel_table survives round-trips; legacy dicts default safely."""

    def test_ship_token_roundtrip(self):
        token = make_token(_design_from_spec(_spec("Long Range Scout")))
        token.fuel_generation = 2
        restored = ShipToken.from_dict(token.to_dict())
        assert restored.fuel_table == QUICK_JUMP_5
        assert restored.fuel_generation == 2

    def test_ship_token_legacy_dict_defaults(self):
        restored = ShipToken.from_dict({"design_name": "Old", "mass": 25})
        assert restored.fuel_table == [0] * 10
        assert restored.fuel_generation == 0

    def test_simple_design_roundtrip(self):
        design = _design_from_spec(_spec("Spore Cloud"))
        restored = SimpleDesign.from_dict(design.to_dict())
        assert restored.engine_name == "Settler's Delight"
        assert restored.fuel_table == SETTLERS_DELIGHT_WEB
        assert restored.free_warp_speed == 6

    def test_simple_design_legacy_dict_defaults(self):
        restored = SimpleDesign.from_dict(
            {"design_class": "SimpleDesign", "name": "Old"})
        assert restored.engine_name == ""
        assert restored.fuel_table == [0] * 10


class TestCanonicalSource:
    """backend/data/components.xml is the single source of every table.

    Every assertion here compares runtime values against the XML parsed
    directly with ElementTree, so a literal reintroduced anywhere in the
    backend fails the moment it drifts from the source file.
    """

    def test_xml_holds_fifteen_engines(self):
        assert len(_tables_from_xml(WEB_XML)) == 15

    def test_lookup_matches_xml_for_every_engine(self):
        for name, table in _tables_from_xml(WEB_XML).items():
            assert engine_fuel_table(name) == table, name

    def test_loader_matches_xml_for_every_engine(self):
        from backend.services.design_builder import ensure_components_loaded
        loader = ensure_components_loaded()
        for name, table in _tables_from_xml(WEB_XML).items():
            prop = loader.get_component(name).get_property("Engine")
            assert prop.values["fuel_consumption"] == table, name

    def test_every_starting_design_and_token_matches_xml(self):
        tables = _tables_from_xml(WEB_XML)
        for spec in STARTING_DESIGN_SPECS:
            design = _design_from_spec(spec)
            expected = tables.get(spec.get("engine", ""), [0] * 10)
            assert design.fuel_table == expected, spec["name"]
            assert make_token(design).fuel_table == expected, spec["name"]

    def test_starbase_has_no_engine_table(self):
        design = _design_from_spec(_spec("Starbase"))
        assert design.engine_name == ""
        assert design.fuel_table == [0] * 10

    def test_free_warp_convention_has_one_implementation(self):
        for name, table in _tables_from_xml(WEB_XML).items():
            assert _free_warp_from_table(table) == Engine(
                fuel_consumption=list(table)).free_warp_speed, name

    def test_negatives_only_on_the_marked_engines(self):
        tables = _tables_from_xml(WEB_XML)
        negative = {name for name, table in tables.items()
                    if any(entry < 0 for entry in table)}
        assert negative == set(WEB_MOD_RAMSCOOP_ENGINES)

    def test_every_marked_engine_is_a_known_engine(self):
        tables = _tables_from_xml(WEB_XML)
        assert set(WEB_MOD_RAMSCOOP_ENGINES) <= set(tables)

    def test_negatives_form_a_prefix_of_the_table(self):
        """A negative run is the free-warp band: it starts at warp 1
        and ends at the first fuel-burning entry."""
        for name, table in _tables_from_xml(WEB_XML).items():
            positives = [i for i, entry in enumerate(table) if entry > 0]
            first_positive = positives[0] if positives else len(table)
            for i, entry in enumerate(table):
                if i < first_positive:
                    assert entry <= 0, (name, i)
                else:
                    assert entry > 0, (name, i)

    @pytest.mark.skipif(not os.path.exists(CANON_XML),
                        reason="gitignored C# reference tree not present")
    def test_only_delta_from_canon_is_the_marked_web_mod(self):
        """Against references/original-game/components.xml: identical
        everywhere except the marked ram scoops, and there only canon 0
        entries became negative."""
        web = _tables_from_xml(WEB_XML)
        canon = _tables_from_xml(CANON_XML)
        assert set(web) == set(canon)
        modified = set()
        for name, table in web.items():
            reference = canon[name]
            if table == reference:
                continue
            modified.add(name)
            for entry, canon_entry in zip(table, reference):
                if entry != canon_entry:
                    assert canon_entry == 0 and entry < 0, name
        assert modified == set(WEB_MOD_RAMSCOOP_ENGINES)
