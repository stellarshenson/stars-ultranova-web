"""
Stars Nova Web - Scan Step
Ported from ServerState/TurnSteps/ScanStep.cs (230 lines)

Updates intel with scanning information.
"""

from typing import List, TYPE_CHECKING
import math

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.components.ship_design import cloak_percent_from_units
from ...core.globals import (
    NOBODY, NEBULA_SCAN_PENALTY,
    SS_BUILT_IN_CLOAK_UNITS, TACHYON_DETECTOR_FACTOR,
)

if TYPE_CHECKING:
    from ..server_data import ServerData


class ScanStep(ITurnStep):
    """
    Scanning turn step.

    Updates each empire's intel reports based on scanner ranges.
    Handles star scanning (penetrating scan) and fleet detection.

    Ported from ScanStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process scanning for all empires.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for empire in server_state.all_empires.values():
            self._add_stars(empire, server_state)
            self._remove_foreign_fleets(empire)
            self._scan(empire, server_state)

        return messages

    def _add_stars(self, empire, server_state: 'ServerData'):
        """
        Update empire's star ownership and reports.

        Args:
            empire: The empire to update.
            server_state: Game state.
        """
        for star in server_state.all_stars.values():
            if star.owner == empire.id:
                # Add/update owned star
                empire.owned_stars[star.name] = star

                # Update star report with full info
                if star.name not in empire.star_reports:
                    empire.star_reports[star.name] = self._generate_star_report(
                        star, "owned", server_state.turn_year
                    )
                else:
                    empire.star_reports[star.name] = self._generate_star_report(
                        star, "owned", server_state.turn_year
                    )
            else:
                # Remove from owned if we lost it
                if star.name in empire.owned_stars:
                    del empire.owned_stars[star.name]

                # Add basic report if we don't have one
                if star.name not in empire.star_reports:
                    empire.star_reports[star.name] = self._generate_star_report(
                        star, "none", -1
                    )

    def _remove_foreign_fleets(self, empire):
        """
        Remove non-owned fleet reports that are stale.

        Args:
            empire: The empire to update.
        """
        # Remove fleet reports for fleets we don't own
        # These will be re-added if we scan them this turn
        keys_to_remove = [
            key for key in empire.fleet_reports.keys()
            if (key >> 32) != empire.id  # Fleet owner is in high bits
        ]
        for key in keys_to_remove:
            del empire.fleet_reports[key]

    def _scan(self, empire, server_state: 'ServerData'):
        """
        Perform scanning from all empire's scanners.

        Args:
            empire: The empire doing scanning.
            server_state: Game state.
        """
        # Scan from owned fleets
        for fleet in empire.owned_fleets.values():
            scan_range = self._get_fleet_scan_range(fleet, empire)
            pen_scan_range = self._get_fleet_pen_scan_range(fleet, empire)

            if scan_range <= 0 and pen_scan_range <= 0:
                continue

            # Tachyon Detectors on the SCANNING fleet counter target
            # cloak (canonical Stars! rule, C# absent - the property
            # only exists in the ComponentEditor GUI)
            detectors = sum(
                getattr(token, 'tachyon_detectors', 0) * token.quantity
                for token in fleet.tokens.values()
            )

            self._scan_from_position(
                fleet.position.x, fleet.position.y,
                scan_range, pen_scan_range,
                empire, server_state,
                tachyon_detectors=detectors
            )

        # Scan from owned stars
        for star in empire.owned_stars.values():
            scan_range = getattr(star, 'scan_range', 0)
            # Planetary pen scan uses the scanner type's PenetratingScan
            # range. Canonical fix of the C# stub (ScanStep.cs:106
            # "Planetary Pen-Scan not implemented yet" reuses ScanRange
            # for both): non-Snooper planetary scanners (pen 0) no
            # longer reveal foreign star details at a distance
            pen_scan_range = getattr(star, 'pen_scan_range', 0)

            if scan_range <= 0 and pen_scan_range <= 0:
                continue

            self._scan_from_position(
                star.position.x, star.position.y,
                scan_range, pen_scan_range,
                empire, server_state
            )

    def _scan_from_position(self, x: float, y: float,
                            scan_range: int, pen_scan_range: int,
                            empire, server_state: 'ServerData',
                            tachyon_detectors: int = 0):
        """
        Scan all objects from a position.

        Args:
            x, y: Scanner position.
            scan_range: Non-penetrating scan range.
            pen_scan_range: Penetrating scan range.
            empire: Scanning empire.
            server_state: Game state.
            tachyon_detectors: Tachyon Detector count on the scanning
                fleet (planetary scanners carry none).
        """
        # Dust nebulae dampen sensors: reduce ranges by dust density
        # at the scanner's position
        nebula = getattr(server_state, 'nebula_field', None)
        if nebula is not None:
            dust = nebula.get_dust_density_at(x, y)
            if dust > 0.01:
                factor = 1.0 - NEBULA_SCAN_PENALTY * dust
                scan_range = int(scan_range * factor)
                pen_scan_range = int(pen_scan_range * factor)

        # Scan stars (requires penetrating scan)
        for star in server_state.all_stars.values():
            if star.owner == empire.id:
                continue

            distance = self._distance(x, y, star.position.x, star.position.y)

            if distance <= pen_scan_range:
                # Deep scan
                empire.star_reports[star.name] = self._generate_star_report(
                    star, "deep_scan", server_state.turn_year
                )
            # Regular scan doesn't reveal star details

        # Scan fleets (non-penetrating)
        for other_empire in server_state.all_empires.values():
            if other_empire.id == empire.id:
                continue

            for fleet in other_empire.owned_fleets.values():
                distance = self._distance(x, y, fleet.position.x, fleet.position.y)

                # Cloak reduces the range at which the fleet is
                # detected (canonical Stars! rule - C# is a stub:
                # ScanStep.cs:165 has no cloak term and Fleet.Cloaked
                # is never read). Cloak affects fleet detection only,
                # never star pen-scan; at distance 0 the 98% cap
                # guarantees detection
                cloak_pct = self._fleet_cloak_percent(fleet, other_empire)
                if cloak_pct > 0 and tachyon_detectors > 0:
                    # Each detector cuts cloak effectiveness by 5%,
                    # stacking with 4th-root damping (canonical rule,
                    # C# absent)
                    cloak_pct *= (
                        TACHYON_DETECTOR_FACTOR ** (tachyon_detectors ** 0.25)
                    )
                effective_range = scan_range * (1.0 - cloak_pct / 100.0)

                if distance <= effective_range:
                    # Fleet detected
                    empire.fleet_reports[fleet.key] = self._generate_fleet_report(
                        fleet, server_state.turn_year
                    )
                    self._learn_designs(
                        empire, other_empire, fleet, server_state.turn_year
                    )

    def _fleet_cloak_percent(self, fleet, owner_empire) -> float:
        """
        Effective cloak percent of a fleet (canonical Stars! rules -
        the C# reference never applies cloak: ScanStep.cs:165 stub).

        Fleet cloak dilutes over total mass: units_per_kT =
        sum(design units/kT * per-ship mass * quantity) / (ship mass +
        cargo mass). SS PRT ships get 300 built-in units/kT and
        exclude cargo from the divisor (PrimaryTraits.cs:54: "all your
        ships have 75% cloaking built in", "Cargo does not decrease
        your cloaking abilities"). Fleet.cloaked acts as a floor - ISB
        starbases are set to 20 (Manufacture.cs:133).
        """
        ship_mass = sum(
            token.mass * token.quantity for token in fleet.tokens.values()
        )
        is_ss = owner_empire.has_trait("SS") if hasattr(
            owner_empire, 'has_trait') else False

        total_units = 0.0
        for token in fleet.tokens.values():
            rating = getattr(token, 'cloak_units', 0)
            if is_ss:
                rating += SS_BUILT_IN_CLOAK_UNITS
            total_units += rating * token.mass * token.quantity

        divisor = ship_mass
        if not is_ss:
            divisor += getattr(fleet.cargo, 'mass', 0)

        if divisor <= 0:
            pct = 0.0
        else:
            pct = cloak_percent_from_units(total_units / divisor)

        return max(pct, getattr(fleet, 'cloaked', 0.0))

    def _learn_designs(self, empire, other_empire, fleet, year: int):
        """
        Record hull-only design intel for each detected token.

        Port of ScanStep.cs:170-183: a normal scan teaches a HULL-ONLY
        design copy (new ShipDesign(token.Design) + ClearAllocated(),
        ShipDesign.cs:751-758) - hull, name and key, no fitted
        components. Battles later upgrade records to scope "full"
        (BattleEngine.cs:347-368); an existing record is never
        overwritten here.
        """
        reports = empire.empire_reports.setdefault(other_empire.id, {})
        designs = reports.setdefault("designs", {})
        for token in fleet.tokens.values():
            key = hex(token.design_key)
            if key in designs:
                continue
            design = other_empire.designs.get(token.design_key)
            name = getattr(design, 'name', '') or getattr(
                token, 'design_name', '')
            hull_name = getattr(design, 'hull_name', '') or (
                design.blueprint.name
                if getattr(design, 'blueprint', None) else '')
            designs[key] = {
                "key": key,
                "name": name,
                "hull_name": hull_name,
                "owner": other_empire.id,
                "scope": "hull",
                "year": year,
            }

    def _get_fleet_scan_range(self, fleet, empire) -> int:
        """Get fleet's non-penetrating scan range."""
        # Base scan range from scanner components (cached on ShipToken)
        scan_range = 0
        for token in fleet.tokens.values():
            # Use cached scan_range_normal from ShipToken
            token_scan = getattr(token, 'scan_range_normal', 0)
            scan_range = max(scan_range, token_scan)
        return scan_range

    def _get_fleet_pen_scan_range(self, fleet, empire) -> int:
        """Get fleet's penetrating scan range."""
        # Use cached scan_range_penetrating from ShipToken
        pen_range = 0
        for token in fleet.tokens.values():
            token_pen = getattr(token, 'scan_range_penetrating', 0)
            pen_range = max(pen_range, token_pen)
        return pen_range

    def _distance(self, x1: float, y1: float, x2: float, y2: float) -> float:
        """Calculate distance between two points."""
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def _generate_star_report(self, star, scan_level: str, year: int) -> dict:
        """
        Generate a star intel report.

        Args:
            star: The star to report on.
            scan_level: Level of scan ("none", "in_scan", "deep_scan", "owned").
            year: Turn year of the scan.

        Returns:
            Dictionary with star intel.
        """
        report = {
            "name": star.name,
            "position_x": star.position.x,
            "position_y": star.position.y,
            "year": year,
            "scan_level": scan_level
        }

        if scan_level == "none":
            return report

        if scan_level in ("deep_scan", "owned"):
            report.update({
                "owner": star.owner,
                "colonists": star.colonists,
                "gravity": getattr(star, 'gravity', 50),
                "temperature": getattr(star, 'temperature', 50),
                "radiation": getattr(star, 'radiation', 50),
                "ironium_concentration": getattr(star, 'ironium_concentration', 0),
                "boranium_concentration": getattr(star, 'boranium_concentration', 0),
                "germanium_concentration": getattr(star, 'germanium_concentration', 0),
            })

        if scan_level == "owned":
            report.update({
                "factories": getattr(star, 'factories', 0),
                "mines": getattr(star, 'mines', 0),
                "defenses": getattr(star, 'defenses', 0),
                "ironium_stockpile": star.resources_on_hand.ironium if hasattr(star, 'resources_on_hand') else 0,
                "boranium_stockpile": star.resources_on_hand.boranium if hasattr(star, 'resources_on_hand') else 0,
                "germanium_stockpile": star.resources_on_hand.germanium if hasattr(star, 'resources_on_hand') else 0,
            })

        return report

    def _generate_fleet_report(self, fleet, year: int) -> dict:
        """
        Generate a fleet intel report.

        Args:
            fleet: The fleet to report on.
            year: Turn year of the scan.

        Returns:
            Dictionary with fleet intel.
        """
        return {
            "key": fleet.key,
            "name": fleet.name,
            "owner": fleet.owner,
            "position_x": fleet.position.x,
            "position_y": fleet.position.y,
            "year": year,
            "ship_count": sum(t.quantity for t in fleet.tokens.values()),
            "bearing": getattr(fleet, 'bearing', 0),
            "warp": getattr(fleet, 'warp_factor', 0),
            # FleetIntel.cs:206-217 reveals full Composition at InScan
            # (token design keys + quantities)
            "composition": [
                {
                    "design_key": hex(t.design_key),
                    "design_name": getattr(t, 'design_name', ''),
                    "quantity": t.quantity,
                }
                for t in fleet.tokens.values()
            ],
        }
