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
