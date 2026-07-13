"""
Stars Nova Web - Race Advantage Point Calculator

Exact port of: Common/RaceDefinition/RaceAdvantagePointCalculator.cs
plus the habitability helpers it requires verbatim from
Common/RaceDefinition/Race.cs (HabValue, NormalizeHabitalityDistance,
GetMaxMalus, GetMalusForEnvironment) and
Common/DataStructures/EnvironmentTolerance.cs (OptimumLevel/Median).

The web Race.hab_value is an acknowledged simplification and will NOT
reproduce the C# numbers, so this module carries its own faithful port
of C# Race.HabValue for the point integration.

Every '/' on ints in the C# source is truncating division (toward
zero); the final points/3 can act on a negative value, where Python's
'//' floors instead - _trunc_div is used everywhere ints are divided.
"""
import math


def _trunc_div(a: int, b: int) -> int:
    """C# integer division: truncate toward zero (Python // floors)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


# PRT costs, applied as points -= PRT_COST[prt]
# (RaceAdvantagePointCalculator.cs:26-36)
PRT_COST = {
    "HE": 40,
    "SS": 95,
    "WM": 45,
    "CA": 10,
    "IS": -100,
    "SD": -150,
    "PP": 120,
    "IT": 180,
    "AR": 90,
    "JOAT": -66,
}

# LRT costs, applied as points += LRT_COST[code]; negative = costs
# points (RaceAdvantagePointCalculator.cs:38-52). The C# code for
# No Ram Scoop Engines is "NRS"; the web uses "NRSE".
LRT_COST = {
    "IFE": -235,
    "TT": -25,
    "ARM": -159,
    "ISB": -201,
    "GR": 40,
    "UR": -240,
    "MA": -155,
    "NRS": 160,
    "CE": 240,
    "OBRM": 255,
    "NAS": 325,
    "LSP": 180,
    "BET": 70,
    "RS": 30,
}

# The 14 real LRT codes iterated by the C# cost loop
# (SecondaryTraits.cs:79-94); "CF" and "ExtraTech" are secondary
# traits but explicitly NOT LRTs (RaceAdvantagePointCalculator.cs:340-343)
LRT_CODES = ("IFE", "TT", "ARM", "ISB", "GR", "UR", "MA", "NRS",
             "CE", "OBRM", "NAS", "LSP", "BET", "RS")

# Science cost rebate table for net-expensive research
# (RaceAdvantagePointCalculator.cs:22)
SCIENCE_COST = [150, 330, 540, 780, 1050, 1380]


def _has_lrt(race, code: str) -> bool:
    """Race has the LRT, accepting the web's "NRSE" alias for "NRS"."""
    if code == "NRS":
        return race.has_trait("NRS") or race.has_trait("NRSE")
    return race.has_trait(code)


# Hab dimension order used throughout the calculator loops:
# 0 = gravity, 1 = temperature, 2 = radiation
# (Race.cs LowerHab/UpperHab/CenterHab/IsImmune, lines 556-610)

def _lower_hab(race, i: int) -> int:
    return (race.gravity_min, race.temperature_min, race.radiation_min)[i]


def _upper_hab(race, i: int) -> int:
    return (race.gravity_max, race.temperature_max, race.radiation_max)[i]


def _is_immune(race, i: int) -> bool:
    return (race.immune_gravity, race.immune_temperature,
            race.immune_radiation)[i]


def _center_hab(race, i: int) -> int:
    # OptimumLevel = Median() = (Max - Min) / 2 + Min with C# integer
    # division (EnvironmentTolerance.cs:59-61, 85-88)
    return _trunc_div(_upper_hab(race, i) - _lower_hab(race, i), 2) \
        + _lower_hab(race, i)


def _normalize_hab_distance(race, i: int, star_value: int) -> float:
    """
    Clicks_from_center / total_clicks_from_center_to_edge.

    Port of: Race.cs NormalizeHabitalityDistance (lines 255-269).
    """
    if _is_immune(race, i):
        return 0.0
    minv = _lower_hab(race, i)
    maxv = _upper_hab(race, i)
    span = abs(maxv - minv)
    # C# `double totalClicksFromCenterToEdge = span / 2;` - INTEGER
    # division of two ints, then widened to double (span 71 -> 35.0)
    total_clicks = float(_trunc_div(span, 2))
    centre = minv + total_clicks
    clicks_from_center = abs(centre - star_value)
    if total_clicks == 0.0:
        # C# double division by zero: Infinity (or NaN for 0/0);
        # only reachable for a degenerate span < 2 tolerance
        return float("inf") if clicks_from_center > 0 else float("nan")
    return clicks_from_center / total_clicks


def _hab_value(race, gravity: int, radiation: int, temperature: int) -> float:
    """
    Habitability of a test planet, -0.45..1.0.

    Port of: Race.cs HabValue (lines 145-192) with the malus branch
    (GetMaxMalus lines 223-231, GetMalusForEnvironment lines 233-247).
    """
    r = _normalize_hab_distance(race, 2, radiation)
    g = _normalize_hab_distance(race, 0, gravity)
    t = _normalize_hab_distance(race, 1, temperature)

    if r > 1 or g > 1 or t > 1:
        # Currently not habitable: sum of per-dimension maluses
        result = 0
        max_malus = 30 if race.has_trait("TT") else 15  # Race.cs:223-231
        if r > 1:
            result -= _malus_for_environment(race, 2, radiation, max_malus)
        if g > 1:
            result -= _malus_for_environment(race, 0, gravity, max_malus)
        if t > 1:
            result -= _malus_for_environment(race, 1, temperature, max_malus)
        return result / 100.0

    x = g - 0.5 if g > 0.5 else 0.0
    y = t - 0.5 if t > 0.5 else 0.0
    z = r - 0.5 if r > 0.5 else 0.0

    return math.sqrt((1 - g) * (1 - g) + (1 - t) * (1 - t)
                     + (1 - r) * (1 - r)) \
        * (1 - x) * (1 - y) * (1 - z) / math.sqrt(3.0)


def _malus_for_environment(race, i: int, star_value: int,
                           max_malus: int) -> int:
    """Port of: Race.cs GetMalusForEnvironment (lines 233-247)."""
    if star_value > _upper_hab(race, i):
        return min(max_malus, star_value - _upper_hab(race, i))
    if star_value < _lower_hab(race, i):
        return min(max_malus, _lower_hab(race, i) - star_value)
    return 0


def _planet_value_calc(race, test_planet_hab) -> float:
    """
    Port of: RaceAdvantagePointCalculator.cs planetValueCalc (lines
    60-68). NOTE THE INDEX SWAP, preserved deliberately: the loop
    dimensions use hab index order 0=gravity, 1=temperature,
    2=radiation, but the C# feeds slot [1] to star.Radiation and slot
    [2] to star.Temperature. It only matters when the temperature and
    radiation ranges differ, but it is the original behavior.
    """
    return _hab_value(race,
                      gravity=test_planet_hab[0],
                      radiation=test_planet_hab[1],
                      temperature=test_planet_hab[2]) * 100.0


def _hab_points(race) -> int:
    """
    Habitability point integral over the terraformable planet grid.

    Port of: RaceAdvantagePointCalculator.cs habPoints (lines 70-202).
    """
    advantage_points = 0.0
    is_total_terraforming = _has_lrt(race, "TT")  # line 83

    # v108 is initialized ONCE per call (line 85) and only overwritten
    # inside the h != 0 non-immune branches - it is NOT reset between
    # h iterations. Port exactly.
    v108 = [0, 0, 0]
    test_hab_start = [0, 0, 0]
    test_hab_width = [0, 0, 0]
    iter_num = [0, 0, 0]
    test_planet_hab = [0, 0, 0]

    for h in range(3):
        if h == 0:
            tt_corr_factor = 0
        elif h == 1:
            tt_corr_factor = 8 if is_total_terraforming else 5
        else:
            tt_corr_factor = 17 if is_total_terraforming else 15

        for i in range(3):
            if _is_immune(race, i):
                test_hab_start[i] = 50
                test_hab_width[i] = 11
                iter_num[i] = 1
            else:
                test_hab_start[i] = _lower_hab(race, i) - tt_corr_factor
                if test_hab_start[i] < 0:
                    test_hab_start[i] = 0
                tmp_hab = _upper_hab(race, i) + tt_corr_factor
                if tmp_hab > 100:
                    tmp_hab = 100
                test_hab_width[i] = tmp_hab - test_hab_start[i]
                iter_num[i] = 11

        v13e = 0.0
        for i in range(iter_num[0]):
            if i == 0 or iter_num[0] <= 1:
                tmp_hab = test_hab_start[0]
            else:
                # C# integer division (line 118)
                tmp_hab = _trunc_div(test_hab_width[0] * i,
                                     iter_num[0] - 1) + test_hab_start[0]

            if h != 0 and not _is_immune(race, 0):
                # Terraforming correction (lines 120-128)
                v100 = _center_hab(race, 0) - tmp_hab
                if abs(v100) <= tt_corr_factor:
                    v100 = 0
                elif v100 < 0:
                    v100 += tt_corr_factor
                else:
                    v100 -= tt_corr_factor
                v108[0] = v100
                tmp_hab = _center_hab(race, 0) - v100
            test_planet_hab[0] = tmp_hab

            v136 = 0.0
            for j in range(iter_num[1]):
                if j == 0 or iter_num[1] <= 1:
                    tmp_hab = test_hab_start[1]
                else:
                    tmp_hab = _trunc_div(test_hab_width[1] * j,
                                         iter_num[1] - 1) + test_hab_start[1]

                if h != 0 and not _is_immune(race, 1):
                    v100 = _center_hab(race, 1) - tmp_hab
                    if abs(v100) <= tt_corr_factor:
                        v100 = 0
                    elif v100 < 0:
                        v100 += tt_corr_factor
                    else:
                        v100 -= tt_corr_factor
                    v108[1] = v100
                    tmp_hab = _center_hab(race, 1) - v100
                test_planet_hab[1] = tmp_hab

                v12e = 0.0
                for k in range(iter_num[2]):
                    if k == 0 or iter_num[2] <= 1:
                        tmp_hab = test_hab_start[2]
                    else:
                        tmp_hab = _trunc_div(
                            test_hab_width[2] * k,
                            iter_num[2] - 1) + test_hab_start[2]

                    if h != 0 and not _is_immune(race, 2):
                        v100 = _center_hab(race, 2) - tmp_hab
                        if abs(v100) <= tt_corr_factor:
                            v100 = 0
                        elif v100 < 0:
                            v100 += tt_corr_factor
                        else:
                            v100 -= tt_corr_factor
                        v108[2] = v100
                        tmp_hab = _center_hab(race, 2) - v100
                    test_planet_hab[2] = tmp_hab

                    planet_desir = _planet_value_calc(race, test_planet_hab)

                    v100 = v108[0] + v108[1] + v108[2]
                    if v100 > tt_corr_factor:
                        planet_desir -= v100 - tt_corr_factor
                        if planet_desir < 0:
                            planet_desir = 0
                    planet_desir *= planet_desir
                    if h == 0:
                        planet_desir *= 7
                    elif h == 1:
                        planet_desir *= 5
                    else:
                        planet_desir *= 6
                    v12e += planet_desir

                # lines 185-186: double math, real division
                if not _is_immune(race, 2):
                    v12e = (v12e * test_hab_width[2]) / 100
                else:
                    v12e *= 11
                v136 += v12e

            if not _is_immune(race, 1):
                v136 = (v136 * test_hab_width[1]) / 100
            else:
                v136 *= 11
            v13e += v136

        if not _is_immune(race, 0):
            v13e = (v13e * test_hab_width[0]) / 100
        else:
            v13e *= 11
        advantage_points += v13e

    # Round half up via +0.5 then truncate (line 201)
    return int(advantage_points / 10.0 + 0.5)


def calculate_advantage_points(race, breakdown: dict = None) -> int:
    """
    Advantage points remaining for a race design; negative = over
    budget.

    Port of: RaceAdvantagePointCalculator.cs calculateAdvantagePoints
    (lines 204-394). If a dict is passed as breakdown it is filled
    with the running raw point total after each step, mirroring the
    commented-out step couts in the C# source.

    Returns:
        The final point total (raw points / 3, truncated toward zero).
    """
    points = 1650  # line 206

    prt = race.primary_trait
    hab = _trunc_div(_hab_points(race), 2000)  # line 214, int division

    # Growth curve (lines 218-235)
    gr_rate_factor = int(race.growth_rate)  # (int) cast truncates
    gr_rate = gr_rate_factor
    if gr_rate_factor <= 5:
        points += (6 - gr_rate_factor) * 4200
    elif gr_rate_factor <= 13:
        if gr_rate_factor == 6:
            points += 3600
        elif gr_rate_factor == 7:
            points += 2250
        elif gr_rate_factor == 8:
            points += 600
        elif gr_rate_factor == 9:
            points += 225
        gr_rate_factor = gr_rate_factor * 2 - 5
    elif gr_rate_factor < 20:
        gr_rate_factor = (gr_rate_factor - 6) * 3
    else:
        gr_rate_factor = 45

    points -= _trunc_div(hab * gr_rate_factor, 24)  # line 235

    if breakdown is not None:
        breakdown["habitability_growth"] = points

    # Hab centers / immunities (lines 239-252)
    immune_count = 0
    for j in range(3):
        if _is_immune(race, j):
            immune_count += 1
        else:
            points += abs(_center_hab(race, j) - 50) * 4
    if immune_count > 1:
        points -= 150

    # Factory overrun penalty - applies to ALL PRTs including AR
    # (lines 256-271)
    fac_operate = race.operable_factories
    ten_fac_res = race.factory_production
    if fac_operate > 10 or ten_fac_res > 10:
        fac_operate -= 9
        if fac_operate < 1:
            fac_operate = 1
        ten_fac_res -= 9
        if ten_fac_res < 1:
            ten_fac_res = 1
        ten_fac_res *= 2 + (1 if prt == "HE" else 0)
        # additional penalty for two- and three-immune
        if immune_count >= 2:
            points -= _trunc_div(ten_fac_res * fac_operate * gr_rate, 2)
        else:
            points -= _trunc_div(ten_fac_res * fac_operate * gr_rate, 9)

    # Pop efficiency (lines 273-278)
    j = _trunc_div(race.colonists_per_resource, 100)
    if j > 25:
        j = 25
    if j <= 7:
        points -= 2400
    elif j == 8:
        points -= 1260
    elif j == 9:
        points -= 600
    elif j > 10:
        points += (j - 10) * 120

    if breakdown is not None:
        breakdown["population"] = points

    # Factories and mines - skipped entirely for AR (lines 282-329)
    if prt != "AR":
        # Factories (lines 285-312)
        prod_points = 10 - race.factory_production
        cost_points = 10 - race.factory_cost
        oper_points = 10 - race.operable_factories
        tmp_points = 0
        if prod_points > 0:
            tmp_points = prod_points * 100  # ASSIGN, not +=
        else:
            tmp_points += prod_points * 121
        if cost_points > 0:
            tmp_points += cost_points * cost_points * (-60)
        else:
            tmp_points += cost_points * (-55)
        if oper_points > 0:
            tmp_points += oper_points * 40
        else:
            tmp_points += oper_points * 35
        if tmp_points > 700:
            tmp_points = _trunc_div(tmp_points - 700, 3) + 700

        if oper_points <= -7:
            if oper_points < -11:
                if oper_points < -14:
                    tmp_points -= 360
                else:
                    tmp_points += (oper_points + 7) * 45
            else:
                tmp_points += (oper_points + 6) * 30

        if prod_points <= -3:
            tmp_points += (prod_points + 2) * 60

        points += tmp_points

        if race.has_trait("CF"):
            points -= 175  # line 312

        # Mines (lines 315-327)
        prod_points = 10 - race.mine_production_rate
        cost_points = 3 - race.mine_cost
        oper_points = 10 - race.operable_mines
        tmp_points = 0
        if prod_points > 0:
            tmp_points = prod_points * 100  # ASSIGN, not +=
        else:
            tmp_points += prod_points * 169
        if cost_points > 0:
            tmp_points -= 360
        else:
            tmp_points += cost_points * (-65) + 80
        if oper_points > 0:
            tmp_points += oper_points * 40
        else:
            tmp_points += oper_points * 35

        points += tmp_points
    else:
        points += 210  # AR (line 329)

    if breakdown is not None:
        breakdown["factories_mines"] = points

    # PRT and LRT costs (lines 333-360)
    points -= PRT_COST[prt]
    i = 0
    k = 0
    for code in LRT_CODES:
        if _has_lrt(race, code):
            if LRT_COST[code] >= 0:
                i += 1
            else:
                k += 1
            points += LRT_COST[code]
    # LRT count balancing (lines 351-353)
    if (k + i) > 4:
        points -= (k + i) * (k + i - 4) * 10
    if (i - k) > 3:
        points -= (i - k - 3) * 60
    if (k - i) > 3:
        points -= (k - i - 3) * 40

    # NAS/PRT interaction (lines 355-360)
    if _has_lrt(race, "NAS"):
        if prt == "PP":
            points -= 280
        elif prt == "SS":
            points -= 200
        elif prt == "JOAT":
            points -= 40

    if breakdown is not None:
        breakdown["traits"] = points

    # Research (lines 365-387)
    tmp_points = 0
    for tech in race.research_costs.values():
        if tech == 175 or tech == 150:
            # expensive / +75% (150 deprecated, old race files only)
            research_stat = -1
        elif tech == 100:
            research_stat = 0  # normal
        else:  # tech == 50
            research_stat = 1  # cheap / -50%
        tmp_points += research_stat
    if tmp_points > 0:
        points -= tmp_points * tmp_points * 130
        if tmp_points == 6:
            points += 1430
        elif tmp_points == 5:
            points += 520
    elif tmp_points < 0:
        points += SCIENCE_COST[-tmp_points - 1]
        if tmp_points < -4 and \
                _trunc_div(race.colonists_per_resource, 100) < 10:
            points -= 190
    if race.has_trait("ExtraTech"):
        points -= 180  # line 386
    if prt == "AR" and race.research_costs.get("Energy") == 50:
        points -= 100  # line 387

    if breakdown is not None:
        breakdown["research"] = points
        breakdown["raw_total"] = points

    # C# integer division truncates toward zero; points may be
    # negative here (e.g. a 3-immune JOAT returns -3900, not -3901)
    return _trunc_div(points, 3)


def get_leftover_advantage_points(race) -> int:
    """
    Leftover points spent on the homeworld at game start:
    clamp(advantage points, 0, 50).

    Port of: Race.cs GetLeftoverAdvantagePoints (lines 215-221).
    """
    advantage_points = calculate_advantage_points(race)
    advantage_points = max(0, advantage_points)
    advantage_points = min(50, advantage_points)
    return advantage_points
