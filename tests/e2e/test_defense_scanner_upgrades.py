"""
Seeded e2e: defense type and planetary scanner research upgrades.

An IS race (no starting tech) begins on Viewer 50 / SDI, builds a
fixed stack of defenses, then researches Energy past 5: every owned
star's defense type auto-upgrades to Missile Battery and the
player-visible coverage percent - the same SummaryCoverage the bombing
and invasion consumers derive their reductions from - rises by the
exact Defenses.cs numbers with the defense count held constant.
Refocusing to Electronics then climbs the planetary scanner ladder
(Viewer 90 -> Scoper 150) with the scan range following the type.
"""

SEED = 20260715
MAX_TURNS = 30
DEFENSES = 10

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")

# IS has no PRT starting tech, so the homeworld starts on the
# Viewer 50 / SDI baseline; cheap energy speeds the ladder climb and
# growthRate 6 buys the advantage-point headroom (same pattern as
# tests/e2e/test_research.py)
RACE = {
    "name": "Wardens",
    "pluralName": "Wardens",
    "prt": "IS",
    "growthRate": 6,
    "researchCosts": {
        "energy": "cheap", "electronics": "cheap", "weapons": "normal",
        "propulsion": "normal", "construction": "normal",
        "biotechnology": "normal",
    },
}


def _summary_coverage(base, defenses):
    """SummaryCoverage percent (Defenses.cs:81-84)."""
    pop = 1.0 - (1.0 - base) ** defenses
    return int(((pop * 0.5 + pop + pop * 0.75) / 3) * 100)


def _focus(harness, field, budget):
    topics = {key: 0 for key in RESEARCH_FIELDS}
    topics[field] = 1
    result = harness.submit(1, "research",
                            {"budget": budget,
                             "topics": {"levels": topics}})
    assert result["status"] in ("applied", "unchanged")


def _play_until(harness, predicate, seen_messages):
    """Generate turns until predicate(state) or MAX_TURNS; collects
    player-1 message texts into seen_messages."""
    for _ in range(MAX_TURNS):
        result = harness.generate_turn()
        seen_messages.extend(
            m.get("text", "") for m in result["messages"]
            if m.get("audience") in (1, 0, -1))
        state = harness.state(1)
        if predicate(state):
            return state
    raise AssertionError("condition not reached within MAX_TURNS")


class TestDefenseScannerUpgrades:

    def test_research_upgrades_defenses_and_scanners(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE, accelerated_start=True)
        home = harness.my_stars(1)[0]
        home_name = home["name"]

        # (a) Starting installations: Viewer 50 / SDI baseline
        assert home["scanner_type"] == "Viewer 50"
        assert home["scan_range"] == 50
        assert home["pen_scan_range"] == 0
        assert home["defense_type"] == "SDI"
        assert home["defenses"] == 0
        assert home["defense_coverage"] == 0

        # (b) Build a fixed defense stack with research parked
        _focus(harness, "Energy", budget=0)
        harness.submit(1, "production", {
            "mode": "Add", "star_key": home_name, "index": 0,
            "production_order": {"production_type": "DEFENSE",
                                 "quantity": DEFENSES, "name": "Defense"},
        })
        messages = []
        _play_until(
            harness,
            lambda s: next(st for st in s["stars"]
                           if st["name"] == home_name)
            .get("defenses", 0) >= DEFENSES,
            messages)

        star = harness.star_by_name(home_name, 1)
        assert star["defenses"] == DEFENSES
        sdi_coverage = _summary_coverage(0.0099, DEFENSES)
        assert star["defense_coverage"] == sdi_coverage
        assert sdi_coverage > 0

        # (c) Research Energy to 5: defenses upgrade to Missile
        # Battery and the coverage the bombing/invasion consumers use
        # measurably improves with the defense count unchanged
        _focus(harness, "Energy", budget=100)
        state = _play_until(
            harness,
            lambda s: s["research"]["levels"]["Energy"] >= 5,
            messages)

        star = harness.star_by_name(home_name, 1)
        assert star["defense_type"] == "Missile Battery"
        assert star["defenses"] == DEFENSES
        assert star["defense_coverage"] == \
            _summary_coverage(0.0199, DEFENSES)
        assert star["defense_coverage"] > sdi_coverage
        assert any("upgraded to Missile Battery" in text
                   for text in messages)

        # (d) Refocus Electronics: the planetary scanner ladder climbs
        # and the scan range follows the type
        _focus(harness, "Electronics", budget=100)
        _play_until(
            harness,
            lambda s: s["research"]["levels"]["Electronics"] >= 1,
            messages)
        star = harness.star_by_name(home_name, 1)
        assert star["scanner_type"] == "Viewer 90"
        assert star["scan_range"] == 90
        assert star["pen_scan_range"] == 0
        assert any("replaced by Viewer 90" in text for text in messages)

        _play_until(
            harness,
            lambda s: s["research"]["levels"]["Electronics"] >= 3,
            messages)
        star = harness.star_by_name(home_name, 1)
        assert star["scanner_type"] == "Scoper 150"
        assert star["scan_range"] == 150
        assert star["pen_scan_range"] == 0
        assert any("replaced by Scoper 150" in text for text in messages)
