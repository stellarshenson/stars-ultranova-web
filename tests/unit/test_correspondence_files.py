"""
Unit tests for correspondence play building blocks: the race password
hash (PasswordUtility.cs parity), password persistence on the race,
the per-empire orders log serialization, and the file envelope
constants.
"""

from backend.core.data_structures.empire_data import EmpireData
from backend.core.globals import (
    TURN_PACKAGE_FORMAT, ORDERS_FILE_FORMAT, GAME_FILE_FORMAT,
    CORRESPONDENCE_FILE_VERSION
)
from backend.core.race.race import Race
from backend.services.game_manager import (
    calculate_password_hash, _race_from_wizard
)


class TestPasswordHash:
    """CalculateHash parity (Common/PasswordUtility.cs:30-36)."""

    def test_known_vector(self):
        # MD5("test") = 098f6bcd4621d373cade4e832627b4f6, formatted as
        # C# BitConverter.ToString: uppercase hex pairs joined by '-'
        assert calculate_password_hash("test") == (
            "09-8F-6B-CD-46-21-D3-73-CA-DE-4E-83-26-27-B4-F6")

    def test_empty_string_vector(self):
        # MD5("") = d41d8cd98f00b204e9800998ecf8427e
        assert calculate_password_hash("") == (
            "D4-1D-8C-D9-8F-00-B2-04-E9-80-09-98-EC-F8-42-7E")

    def test_format_shape(self):
        digest = calculate_password_hash("hunter2")
        parts = digest.split("-")
        assert len(parts) == 16
        assert all(len(p) == 2 and p == p.upper() for p in parts)

    def test_deterministic(self):
        assert (calculate_password_hash("secret")
                == calculate_password_hash("secret"))
        assert (calculate_password_hash("secret")
                != calculate_password_hash("Secret"))


class TestRacePassword:
    """Password hash stored on the race (Race.cs:50)."""

    def test_round_trip(self):
        race = Race()
        race.name = "Guarded"
        race.password = calculate_password_hash("hunter2")
        restored = Race.from_dict(race.to_dict())
        assert restored.password == race.password

    def test_default_empty(self):
        assert Race().password == ""
        assert Race.from_dict(Race().to_dict()).password == ""

    def test_wizard_hashes_plaintext(self):
        race = _race_from_wizard({"name": "Guarded",
                                  "password": "hunter2"})
        assert race.password == calculate_password_hash("hunter2")

    def test_wizard_without_password_stays_open(self):
        assert _race_from_wizard({"name": "Open"}).password == ""


class TestOrdersLog:
    """Per-empire orders log serialization (EmpireData)."""

    def test_round_trip(self):
        empire = EmpireData(id=1)
        empire.orders_log = [
            {"command_type": "research",
             "command_data": {"budget": 30}},
            {"op": "rename_fleet",
             "args": {"fleet_key": 4294967297, "name": "Flagship"}},
        ]
        restored = EmpireData.from_dict(empire.to_dict())
        assert restored.orders_log == empire.orders_log

    def test_default_empty(self):
        assert EmpireData().orders_log == []
        assert EmpireData.from_dict(EmpireData().to_dict()).orders_log \
            == []


class TestEnvelopeConstants:
    """Correspondence file envelope identifiers (core/globals.py)."""

    def test_formats_distinct(self):
        formats = {TURN_PACKAGE_FORMAT, ORDERS_FILE_FORMAT,
                   GAME_FILE_FORMAT}
        assert len(formats) == 3
        assert all(f.startswith("stars-ultranova-") for f in formats)

    def test_version(self):
        assert CORRESPONDENCE_FILE_VERSION == 1
