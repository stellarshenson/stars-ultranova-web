"""
Seeded e2e: terraforming a marginal colony world.

A default JOAT race (terraform ability +-3 per variable at its
starting Bio/Prop/Energy/Weapons 3) first shows the skip semantics on
its homeworld (seeded at the race optimum, so a Terraform order is
"completed" without spending), then colonizes the nearest star (random
off-optimum environment) and runs a Terraform production order until
the first clicks land, improving habitability.
"""

SEED = 20260713
MAX_COLONIZE_TURNS = 15
MAX_TERRAFORM_TURNS = 30


def dist2(a, b):
    return ((a["position_x"] - b["position_x"]) ** 2
            + (a["position_y"] - b["position_y"]) ** 2)


def env(star):
    return (star["gravity"], star["temperature"], star["radiation"])


def hab_value(race_dict, star_dict):
    """Exact (unrounded) habitability from the ported race math."""
    from backend.core.game_objects.star import Star
    from backend.core.race.race import Race

    race = Race.from_dict(race_dict)
    star = Star()
    star.gravity = star_dict["gravity"]
    star.temperature = star_dict["temperature"]
    star.radiation = star_dict["radiation"]
    return race.hab_value(star)


class TestTerraforming:

    def test_colonize_and_terraform(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            accelerated_start=True)
        state = harness.state(1)
        home = harness.my_stars(1)[0]
        home_env = env(home)

        # (a) Homeworld sanity: the homeworld is seeded at the race
        # optimum (galaxy_generator homeworld block), so a Terraform
        # order is skipped - env unchanged, order dropped with a
        # completion message (TerraformProductionUnit.IsSkipped intent)
        harness.submit(1, "production", {
            "mode": "Add", "star_key": home["name"], "index": 0,
            "production_order": {"production_type": "TERRAFORM",
                                 "quantity": 5, "name": "Terraform"},
        })
        harness.generate_turn()
        after = harness.star_by_name(home["name"], 1)
        assert env(after) == home_env
        assert not any(o["production_type"] == "TERRAFORM"
                       for o in after["production_queue"])
        messages = harness.state(1)["messages"]
        assert any("completed terraforming" in m["text"] for m in messages)
        assert not any("unknown item" in m["text"] for m in messages)

        # All production resources to the colony effort, none to labs
        levels = {key: 0 for key in state["research"]["levels"]}
        levels["Energy"] = 1
        harness.submit(1, "research",
                       {"budget": 0, "topics": {"levels": levels}})

        # (b) Colonize the nearest star (random environment,
        # off-optimum for this seed - asserted below)
        fleets = harness.my_fleets(1)
        colony_ship = next(f for f in fleets
                           if f["can_colonize"] and not f["is_starbase"])
        assert colony_ship["cargo"]["colonists"] > 0  # launches loaded
        stars = harness.state(1)["stars"]
        target = min((s for s in stars if s["name"] != home["name"]),
                     key=lambda s: dist2(s, home))
        harness.submit(1, "waypoint", {
            "mode": "Add", "fleet_key": colony_ship["key"], "index": 0,
            "waypoint": {
                "position_x": target["position_x"],
                "position_y": target["position_y"],
                "warp_factor": 6, "destination": target["name"],
                "task": {"type": "Colonise"},
            },
        })
        for _ in range(MAX_COLONIZE_TURNS):
            harness.generate_turn()
            colony = harness.star_by_name(target["name"], 1)
            if colony.get("intel") == "owned":
                break
        assert colony.get("intel") == "owned", \
            f"{target['name']} not colonized in {MAX_COLONIZE_TURNS} turns"

        env0 = env(colony)
        race_dict = harness.state(1)["empire"]["race"]
        hab0 = hab_value(race_dict, colony)
        # Precondition: the random environment is off the race optimum
        # (50/50/50 for the default 15-85 hab ranges)
        assert any(abs(value - 50) >= 1 for value in env0), env0

        # Terraform 2 points; the young colony banks partial progress
        # (2-and-growing resources/year) until each 100-resource point
        # completes
        harness.submit(1, "production", {
            "mode": "Add", "star_key": target["name"], "index": 0,
            "production_order": {"production_type": "TERRAFORM",
                                 "quantity": 2, "name": "Terraform"},
        })
        colony_after = None
        for _ in range(MAX_TERRAFORM_TURNS):
            harness.generate_turn()
            messages = harness.state(1)["messages"]
            assert not any("unknown item" in m["text"] for m in messages)
            colony_after = harness.star_by_name(target["name"], 1)
            if env(colony_after) != env0:
                break
        assert colony_after is not None and env(colony_after) != env0, \
            f"no terraform click within {MAX_TERRAFORM_TURNS} turns"

        # Every changed variable moved toward the race optimum centre
        deltas = 0
        for key, before in zip(("gravity", "temperature", "radiation"), env0):
            now = colony_after[key]
            if now != before:
                assert abs(now - 50) < abs(before - 50), (key, before, now)
                deltas += abs(now - before)
        assert deltas >= 1
        # Habitability - and with it population growth, which scales
        # with hab_value in Star.calculate_growth - improved. The API
        # habitability field is rounded to integer percent, so compare
        # the exact ported hab math (and the rounded value as sanity)
        assert hab_value(race_dict, colony_after) > hab0
        assert colony_after["habitability"] >= round(hab0 * 100)
