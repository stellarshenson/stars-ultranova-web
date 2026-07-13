"""
Tests for planetary defense types and planetary scanner upgrades.

Coverage math anchored against Common/Defenses.cs and the C# unit test
DefencesTest.cs; type/scanner selection against the components.xml
ladder; the research level-up auto-upgrade against StarUpdateStep.cs
TechLevelUp; the invasion port against InvadeTask.cs.
"""

import pytest

from backend.core.data_structures import EmpireData, TechLevel
from backend.core.data_structures.tech_level import ResearchField
from backend.core.defenses import (
    DEFENSE_BASE_COVERAGE,
    DEFENSE_TYPE_LADDER,
    best_defense_type,
    best_planetary_scanner,
    compute_defense_coverage,
)
from backend.core.game_objects.star import Star
from backend.core.globals import NOBODY
from backend.core.production import ProductionQueue
from backend.core.production.production_queue import (
    ProductionOrder, ProductionType
)
from backend.core.race.race import Race
from backend.server import ServerData
from backend.server.turn_steps import PostBombingStep, StarUpdateStep

from .test_turn_generator import MockCargo, MockFleet, MockFleetToken, MockStar


def _tech(**levels) -> TechLevel:
    return TechLevel.from_values(**levels)


# --------------------------------------------------------------------------
# Coverage formulas (Defenses.cs:58-85)
# --------------------------------------------------------------------------

class TestDefenseCoverage:

    def test_coverage_per_type_at_100_defenses(self):
        """Each defense type's population coverage at MaxDefenses."""
        for name, _req in DEFENSE_TYPE_LADDER:
            star = MockStar(name="D", owner=1, defenses=100,
                            defense_type=name)
            cov = compute_defense_coverage(star)
            base = DEFENSE_BASE_COVERAGE[name]
            expected = 1.0 - (1.0 - base) ** 100
            assert cov["population"] == pytest.approx(expected)
            assert cov["buildings"] == pytest.approx(expected * 0.5)
            assert cov["invasion"] == pytest.approx(expected * 0.75)
            assert cov["smart"] == pytest.approx(
                1.0 - (1.0 - base * 0.5) ** 100)
            assert cov["summary"] == int(
                ((cov["buildings"] + cov["population"] + cov["invasion"])
                 / 3) * 100)

    def test_neutron_anchor_values_from_csharp_test(self):
        """DefencesTest.cs:43-49: Neutron, 100 defenses."""
        star = MockStar(name="D", owner=1, defenses=100,
                        defense_type="Neutron Shield")
        cov = compute_defense_coverage(star)
        assert cov["population"] == pytest.approx(0.9791, abs=0.001)
        assert cov["smart"] == pytest.approx(0.8524, abs=0.001)

    def test_type_none_gives_zero_coverage(self):
        """Defenses.cs:60-68: DefenseType "None" zeroes everything."""
        star = MockStar(name="D", owner=1, defenses=100,
                        defense_type="None")
        cov = compute_defense_coverage(star)
        assert cov == {"population": 0.0, "buildings": 0.0,
                       "invasion": 0.0, "smart": 0.0, "summary": 0}

    def test_defenses_capped_at_100(self):
        """star.Defenses caps at Global.MaxDefenses = 100."""
        star = MockStar(name="D", owner=1, defenses=500,
                        defense_type="SDI")
        capped = MockStar(name="D", owner=1, defenses=100,
                          defense_type="SDI")
        assert compute_defense_coverage(star) == \
            compute_defense_coverage(capped)


# --------------------------------------------------------------------------
# Defense type ladder (components.xml Energy requirements)
# --------------------------------------------------------------------------

class TestBestDefenseType:

    @pytest.mark.parametrize("energy,expected", [
        (0, "SDI"),
        (4, "SDI"),
        (5, "Missile Battery"),
        (10, "Laser Battery"),
        (16, "Planetary Shield"),
        (23, "Neutron Shield"),
        (26, "Neutron Shield"),
    ])
    def test_energy_ladder(self, energy, expected):
        assert best_defense_type(_tech(energy=energy)) == expected

    def test_wm_capped_by_xml_restrictions(self):
        """components.xml: WM races cannot use Laser Battery,
        Planetary Shield or Neutron Shield."""
        assert best_defense_type(_tech(energy=26), ["WM"]) == \
            "Missile Battery"

    def test_ar_gets_no_planetary_defenses(self):
        """components.xml: every defense type is AR not_available."""
        assert best_defense_type(_tech(energy=26), ["AR"]) == "None"


# --------------------------------------------------------------------------
# Planetary scanner selection (components.xml)
# --------------------------------------------------------------------------

class TestBestPlanetaryScanner:

    def _best(self, traits=(), **levels):
        return best_planetary_scanner(list(traits), _tech(**levels))

    def test_no_tech_gives_viewer_50(self):
        best = self._best()
        assert best.name == "Viewer 50"
        assert best.scan_range_normal == 50
        assert best.scan_range_penetrating == 0

    def test_electronics_3_gives_scoper_150(self):
        assert self._best(electronics=3).name == "Scoper 150"

    def test_snooper_needs_all_three_fields(self):
        """Tech gating is ALL fields (TechLevel partial order):
        Electronics 10 alone stays on Scoper 280."""
        assert self._best(electronics=10).name == "Scoper 280"
        best = self._best(electronics=10, energy=3, biotechnology=3)
        assert best.name == "Snooper 320X"
        assert best.scan_range_normal == 320
        assert best.scan_range_penetrating == 160

    def test_nas_race_cannot_use_snoopers(self):
        best = self._best(traits=["NAS"], electronics=10, energy=3,
                          biotechnology=3)
        assert best.name == "Scoper 280"

    def test_ar_gets_no_planetary_scanner(self):
        assert self._best(traits=["AR"], electronics=10) is None


# --------------------------------------------------------------------------
# Research level-up auto-upgrade (StarUpdateStep.cs TechLevelUp)
# --------------------------------------------------------------------------

def _leveled_empire(star, **research_bank):
    """Empire owning `star` with a research bank ready to level up."""
    empire = EmpireData(id=1)
    empire.race = Race(name="Testers")
    empire.research_levels = TechLevel()
    empire.research_resources = TechLevel.from_values(**research_bank)
    empire.owned_stars[star.name] = star
    star.owner = 1
    return empire


def _run_level_up(empire, area):
    step = StarUpdateStep()
    step.server_state = ServerData()
    step.server_state.all_empires = {empire.id: empire}
    step._check_tech_level_up(area, empire)
    return step.server_state.all_messages


class TestTechLevelUpUpgrades:

    def test_scanner_replaced_on_electronics_level_up(self):
        """Electronics 0 -> 1 replaces Viewer 50 with Viewer 90 on
        every owned star and announces it."""
        star = Star(name="Home")
        star.scanner_type = "Viewer 50"
        star.scan_range = 50
        star.defense_type = "SDI"
        # Cost to attain Electronics 1: fib(6)*10 = 80
        empire = _leveled_empire(star, electronics=80)

        messages = _run_level_up(empire, ResearchField.ELECTRONICS)

        assert empire.research_levels.get_level(
            ResearchField.ELECTRONICS) == 1
        assert star.scanner_type == "Viewer 90"
        assert star.scan_range == 90
        assert star.pen_scan_range == 0
        assert any("replaced by Viewer 90" in m.text for m in messages)

    def test_defense_type_upgrades_at_energy_5(self):
        """Energy jump past 5 upgrades every owned star's defenses to
        Missile Battery with a message."""
        star = Star(name="Home")
        star.defense_type = "SDI"
        star.scanner_type = "Viewer 50"
        star.scan_range = 50
        # Bank 600: levels Energy to 5 (threshold 590) but not 6 (940)
        empire = _leveled_empire(star, energy=600)

        messages = _run_level_up(empire, ResearchField.ENERGY)

        assert empire.research_levels.get_level(ResearchField.ENERGY) == 5
        assert star.defense_type == "Missile Battery"
        assert any("upgraded to Missile Battery" in m.text
                   for m in messages)
        # Energy 5 unlocks no better planetary scanner
        assert star.scanner_type == "Viewer 50"

    def test_level_up_without_unlock_changes_nothing(self):
        """Energy 0 -> 1 unlocks no scanner or defense change."""
        star = Star(name="Home")
        star.defense_type = "SDI"
        star.scanner_type = "Viewer 50"
        star.scan_range = 50
        empire = _leveled_empire(star, energy=80)

        messages = _run_level_up(empire, ResearchField.ENERGY)

        assert empire.research_levels.get_level(ResearchField.ENERGY) == 1
        assert star.defense_type == "SDI"
        assert star.scanner_type == "Viewer 50"
        assert star.scan_range == 50
        assert not any("replaced" in m.text or "upgraded" in m.text
                       for m in messages)

    def test_multi_level_jump_lands_on_best_scanner(self):
        """One turn jumping Electronics 0 -> 8 sweeps through four
        scanner unlocks and ends on Scoper 280 (never a downgrade)."""
        star = Star(name="Home")
        star.scanner_type = "Viewer 50"
        star.scan_range = 50
        star.defense_type = "SDI"
        # Bank 2500: Electronics threshold L8 = 2400, L9 = 3850
        empire = _leveled_empire(star, electronics=2500)

        _run_level_up(empire, ResearchField.ELECTRONICS)

        assert empire.research_levels.get_level(
            ResearchField.ELECTRONICS) == 8
        assert star.scanner_type == "Scoper 280"
        assert star.scan_range == 280
        assert star.pen_scan_range == 0


# --------------------------------------------------------------------------
# Invasion (InvadeTask.cs port)
# --------------------------------------------------------------------------

def _invasion_setup(troop_kilotons, colonists, defenses=0,
                    defense_type="None", sender_race=None,
                    receiver_race=None):
    server_state = ServerData()
    star = MockStar(name="Target", owner=2, colonists=colonists,
                    defenses=defenses, defense_type=defense_type,
                    manufacturing_queue=ProductionQueue())
    star.manufacturing_queue.orders.append(
        ProductionOrder(production_type=ProductionType.MINE, quantity=1,
                        name="Mine"))
    server_state.all_stars = {"Target": star}

    sender = EmpireData(id=1)
    sender.race = sender_race
    receiver = EmpireData(id=2)
    receiver.race = receiver_race
    receiver.owned_stars[star.name] = star
    server_state.all_empires = {1: sender, 2: receiver}

    fleet = MockFleet(
        key=1, owner=1, in_orbit=star,
        cargo=MockCargo(colonists_in_kilotons=troop_kilotons),
        tokens={1: MockFleetToken(quantity=1)})
    sender.owned_fleets = {1: fleet}

    return server_state, star, fleet, sender, receiver


class TestInvasion:

    def _invade(self, server_state, star, fleet, sender, receiver):
        return PostBombingStep()._perform_invasion(
            fleet, star, sender, receiver, server_state)

    def test_defenders_win(self):
        """InvadeTask.cs:181-198: survivors = defenders - attackers*1.1."""
        state = _invasion_setup(troop_kilotons=10, colonists=10000)
        server_state, star, fleet, sender, receiver = state
        messages = self._invade(*state)

        # 1000 troops * 1.1 = 1100 strength vs 10000 defenders
        assert star.colonists == 10000 - 1100
        assert star.owner == 2
        assert fleet.cargo.colonists_in_kilotons == 0
        assert any("attackers were slain" in m.text for m in messages)

    def test_defenders_win_100_colonist_floor(self):
        """Surviving defenders never drop below 100 colonists."""
        # 1000 defenders vs 900 troops: survivor = 1000 - 990 = 10
        state = _invasion_setup(troop_kilotons=9, colonists=1000)
        _, star, _, _, _ = state
        self._invade(*state)
        assert star.colonists == 100

    def test_attackers_win_transfers_ownership(self):
        """InvadeTask.cs:199-222: queue cleared, ownership moves,
        remaining = max(int(-survivor / 1.1), 100)."""
        state = _invasion_setup(troop_kilotons=100, colonists=1000)
        server_state, star, fleet, sender, receiver = state
        messages = self._invade(*state)

        # survivor = 1000 - 11000 = -10000; remaining = int(10000/1.1)
        assert star.colonists == int(10000 / 1.1)
        assert star.owner == 1
        assert star.name in sender.owned_stars
        assert star.name not in receiver.owned_stars
        assert len(star.manufacturing_queue.orders) == 0
        # New owner's researched defense type governs (canonical)
        assert star.defense_type == "SDI"
        assert any("defenders were slain" in m.text for m in messages)

    def test_exact_tie_wipes_the_planet(self):
        """InvadeTask.cs:223-240: both sides annihilated."""
        # 10000 troops * 1.1 = 11000 == defenders
        state = _invasion_setup(troop_kilotons=100, colonists=11000)
        _, star, _, _, _ = state
        star.mines = 20
        star.factories = 20
        messages = self._invade(*state)

        assert star.colonists == 0
        assert star.mines == 0
        assert star.factories == 0
        assert star.owner == NOBODY
        assert len(star.manufacturing_queue.orders) == 0
        assert any("fought to the last" in m.text for m in messages)

    def test_wm_attacker_bonus(self):
        """WM attacker bonus 1.1 * 1.5 = 1.65 flips the baseline loss
        into a win (InvadeTask.cs:162-166)."""
        baseline = _invasion_setup(troop_kilotons=10, colonists=1500)
        self._invade(*baseline)
        assert baseline[1].owner == 2  # 1100 < 1500: defenders hold

        wm = _invasion_setup(troop_kilotons=10, colonists=1500,
                             sender_race=Race(name="Wolves",
                                              primary_trait="WM"))
        self._invade(*wm)
        assert wm[1].owner == 1  # 1650 > 1500: attackers take it

    def test_is_defender_bonus(self):
        """IS defender bonus 2.0 flips the baseline loss into a hold
        (InvadeTask.cs:168-172)."""
        baseline = _invasion_setup(troop_kilotons=10, colonists=1000)
        self._invade(*baseline)
        assert baseline[1].owner == 1  # 1100 > 1000: attackers take it

        is_def = _invasion_setup(troop_kilotons=10, colonists=1000,
                                 receiver_race=Race(name="Turtles",
                                                    primary_trait="IS"))
        self._invade(*is_def)
        assert is_def[1].owner == 2  # 1100 < 2000: defenders hold

    def test_invasion_coverage_reduces_troops_on_ground(self):
        """InvadeTask.cs:158-159: troopsOnGround = troops *
        (1 - InvasionCoverage) with Neutron Shield / 100 defenses."""
        state = _invasion_setup(troop_kilotons=100, colonists=100000,
                                defenses=100,
                                defense_type="Neutron Shield")
        _, star, _, _, _ = state
        self._invade(*state)

        invasion_cov = (1.0 - (1.0 - 0.0379) ** 100) * 0.75
        troops_on_ground = int(10000 * (1.0 - invasion_cov))
        attacker_strength = int(troops_on_ground * 1.1)
        assert star.colonists == 100000 - attacker_strength

    def test_starbase_cancels_invasion(self):
        """InvadeTask.cs:134-138: a starbase kills all invaders -
        order cancelled, troops stay aboard."""
        state = _invasion_setup(troop_kilotons=100, colonists=1000)
        server_state, star, fleet, sender, receiver = state
        starbase = MockFleet(key=(2 << 32) | 9, owner=2,
                             is_starbase=True,
                             tokens={1: MockFleetToken(quantity=1)})
        starbase.in_orbit_name = "Target"
        receiver.owned_fleets = {starbase.key: starbase}

        messages = self._invade(*state)

        assert star.owner == 2
        assert star.colonists == 1000
        assert fleet.cargo.colonists_in_kilotons == 100
        assert any("starbase" in m.text for m in messages)

    def test_own_planet_beams_troops_down(self):
        """InvadeTask.cs:93-101: invading an owned planet just lands
        the colonists."""
        state = _invasion_setup(troop_kilotons=10, colonists=5000)
        server_state, star, fleet, sender, receiver = state
        star.owner = 1
        self._invade(*state)
        assert star.colonists == 6000
        assert fleet.cargo.colonists_in_kilotons == 0

    def test_unowned_planet_cancels_invasion(self):
        """InvadeTask.cs:103-108: cannot invade an uncolonised star."""
        state = _invasion_setup(troop_kilotons=10, colonists=0)
        server_state, star, fleet, sender, receiver = state
        star.owner = NOBODY
        messages = self._invade(*state)
        assert fleet.cargo.colonists_in_kilotons == 10
        assert any("not colonised" in m.text for m in messages)


# --------------------------------------------------------------------------
# Colonization installs the empire's best researched types
# --------------------------------------------------------------------------

class TestColonizationInstallations:

    def test_colonize_sets_defense_and_scanner_types(self):
        """New colonies get the best researched defense type and
        planetary scanner (canonical; C# leaves both "None")."""
        server_state = ServerData()
        star = MockStar(name="New World", owner=NOBODY)
        server_state.all_stars = {"New World": star}

        sender = EmpireData(id=1)
        sender.race = Race(name="Settlers")
        sender.research_levels = _tech(energy=5, electronics=1)
        server_state.all_empires = {1: sender}

        fleet = MockFleet(
            key=1, owner=1,
            cargo=MockCargo(colonists_in_kilotons=10),
            can_colonize=True,
            tokens={1: MockFleetToken(quantity=1)})

        PostBombingStep()._perform_colonization(
            fleet, star, sender, server_state)

        assert star.owner == 1
        assert star.defense_type == "Missile Battery"
        assert star.scanner_type == "Viewer 90"
        assert star.scan_range == 90
        assert star.pen_scan_range == 0
