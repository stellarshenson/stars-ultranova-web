"""
Seeded e2e scenarios for score records and victory conditions.

Scores (backend/server/scores.py, port of ServerState/Scores.cs) are
public to all players and computed live in the player state; per-year
score history is a web extension recorded at the end of every
generated turn. Victory (backend/server/victory_check.py, port of
ServerState/VictoryCheck.cs) is checked before the year increment,
gated by the configurable minimum game time.
"""

SEED = 20260714

SCORE_FIELDS = (
    "empire_id", "rank", "score", "planets", "starbases",
    "unarmed_ships", "escort_ships", "capital_ships",
    "tech_level", "resources",
)


def _planets_owned_victory(minimum_game_time):
    """Victory payload: planets_owned at 1% (met by any homeworld)."""
    return {
        "planets_owned": {"enabled": True, "value": 1},
        "targets_to_meet": 1,
        "minimum_game_time": minimum_game_time,
    }


class TestScoresInPlayerState:

    def test_scores_public_and_history_grows_per_turn(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)

        # At creation: live records for every empire, no history yet
        # (IntelWriter.cs:79-89 writes no scores at StartingYear)
        state = harness.state(1)
        assert len(state["scores"]) == 2
        for record in state["scores"]:
            for field in SCORE_FIELDS:
                assert field in record, f"missing score field {field}"
            assert record["race_name"]
        assert sorted(r["rank"] for r in state["scores"]) == [1, 2]
        assert all(not entries
                   for entries in state["score_history"].values())

        # Scores are public: both empires see identical records
        assert harness.state(2)["scores"] == state["scores"]

        # History grows by exactly one entry per empire per turn,
        # stamped with the post-increment year
        for expected_entries in (1, 2, 3):
            result = harness.generate_turn()
            state = harness.state(1)
            for empire_id in ("1", "2"):
                entries = state["score_history"][empire_id]
                assert len(entries) == expected_entries
                assert entries[-1]["year"] == result["turn"]

        # Score inputs only grow in the opening turns (population and
        # resources on an undisturbed homeworld), so each empire's
        # score history is monotonic non-decreasing
        for empire_id in ("1", "2"):
            entries = state["score_history"][empire_id]
            scores = [e["score"] for e in entries]
            assert scores == sorted(scores)

        # The latest history entry matches the live public record
        for record in state["scores"]:
            latest = state["score_history"][str(record["empire_id"])][-1]
            assert latest["score"] == record["score"]


class TestVictoryDeclaration:

    def test_victory_by_planets_owned_low_threshold(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2,
                            victory=_planets_owned_victory(2))

        # The check runs before the year increment: at generated turn
        # N the game_time seen is N-1, so turns 1 and 2 stay gated
        # (game_time 0 and 1 < 2)
        for _ in range(2):
            harness.generate_turn()
            assert harness.state(1)["victor"] is None

        # Turn 3: game_time 2 >= 2 - the first empire meeting the 1%
        # planets target (empire 1, first in iteration order) wins
        result = harness.generate_turn()
        state = harness.state(1)
        assert state["victor"] == 1

        victory_messages = [
            m for m in state["messages"]
            if m["type"] == "Victory" and "have won the game" in m["text"]
        ]
        assert len(victory_messages) == 1

        # The loser sees the same public announcement
        assert any("have won the game" in m["text"]
                   for m in harness.state(2)["messages"])

        # Victor persists on subsequent turns, announced only once
        result = harness.generate_turn()
        assert harness.state(1)["victor"] == 1
        assert not any(m["type"] == "Victory"
                       for m in result["messages"])

    def test_no_victory_before_minimum_time(self, harness):
        # Edge: target met from turn 0, but minimum_game_time 50
        # blocks the declaration (VictoryCheck.cs:76-81)
        harness.create_game(seed=SEED, size="tiny", players=2,
                            victory=_planets_owned_victory(50))

        for _ in range(3):
            harness.generate_turn()
            assert harness.state(1)["victor"] is None

    def test_victory_settings_default(self, harness):
        # No victory payload -> C# defaults (GameSettings.cs:49-58):
        # planets_owned enabled at 60%, minimum game time 50
        harness.create_game(seed=SEED, size="tiny", players=2)

        status = harness.state(1)["victory_status"]
        assert status["minimum_game_time"] == 50
        assert status["targets_to_meet"] == 1
        planets = status["targets"]["planets_owned"]
        assert planets["enabled"] is True
        assert planets["value"] == 60
        assert status["targets"]["total_score"]["enabled"] is False

        # A balanced start declares no victor in the opening turns
        for _ in range(2):
            harness.generate_turn()
            assert harness.state(1)["victor"] is None


class TestEscortSpamNotDominant:

    def test_escort_spam_does_not_outscore_planet_empire(self, harness):
        # DEF-8 acceptance bar (run100 shape): an empire with a few
        # planets and a horde of cheap armed probes must NOT outscore
        # an empire with 10x the planets. Escort/unarmed ship points
        # are capped at one scoring ship per owned planet (web mod,
        # backend/server/scores.py); the ScoreRecord still reports the
        # raw escort count for the report UI
        from backend.core.game_objects import Fleet
        from backend.core.globals import NOBODY
        from backend.services.game_manager import get_game_manager
        from backend.services.ship_specs import SimpleDesign, make_token
        from backend.core.data_structures import Resources

        harness.create_game(seed=SEED, size="small", players=2)

        manager = get_game_manager()
        server_data = manager._load_game_state(harness.game_id)
        spammer = server_data.all_empires[1]
        expander = server_data.all_empires[2]

        # Hand out planets: empire 1 gets 3 extras (4 with the
        # homeworld), empire 2 gets 10x that
        neutral = [s for s in server_data.all_stars.values()
                   if s.owner == NOBODY]
        assert len(neutral) >= 43, "small galaxy too sparse for test"
        for star in neutral[:3]:
            star.owner = 1
            star.colonists = 100000
            spammer.owned_stars[star.name] = star
        for star in neutral[3:42]:
            star.owner = 2
            star.colonists = 100000
            expander.owned_stars[star.name] = star

        # Empire 1 fields 300 escort-class probes (armed, power
        # rating < 2000) in one fleet
        probe = SimpleDesign(key=spammer.get_next_design_key(),
                             name="Armed Probe", has_weapons=True,
                             armor=100,
                             cost=Resources(ironium=2, energy=6))
        spammer.designs[probe.key] = probe
        fleet = Fleet()
        fleet.key = spammer.get_next_fleet_key()
        fleet.name = "Probe Swarm"
        fleet.turn_year = spammer.turn_year
        home = next(iter(spammer.owned_stars.values()))
        fleet.position = home.position.copy()
        fleet.in_orbit_name = home.name
        token = make_token(probe, 300)
        fleet.tokens[token.design_key] = token
        spammer.owned_fleets[fleet.key] = fleet
        manager._save_game_state(harness.game_id, server_data)

        harness.generate_turn()

        scores = {r["empire_id"]: r
                  for r in harness.state(1)["scores"]}
        # Raw count intact (300 injected + any escort-class ships in
        # the starting fleet)
        assert scores[1]["escort_ships"] >= 300
        assert scores[1]["planets"] == 4
        # 39 granted + homeworld (+ any star the starting fleets
        # colonized during the generated turn)
        assert scores[2]["planets"] >= 40
        # The acceptance bar: expansion strictly outscores the spam
        assert scores[2]["score"] > scores[1]["score"]
        assert scores[2]["rank"] == 1
