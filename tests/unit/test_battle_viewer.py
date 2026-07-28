"""
Unit tests for the battle viewer's coordinate transform
(frontend/js/views/battle-viewer.js).

Canvas cannot run here, so this covers what does not need pixels: the
file parses (node --check) and the board-position-to-canvas-pixel
transform is exercised directly in node. Stack positions come from
RonBattleEngine on a 0-1000 board with GRID_SCALE (100) units per
square, reported as grid_size; the canvas is 400px over the canonical
10 x 10 board, so every position must land inside it.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BATTLE_VIEWER = REPO_ROOT / "frontend" / "js" / "views" / "battle-viewer.js"

NODE = shutil.which("node")

# Ron engine constants (backend/server/battle/ron_battle_engine.py)
GRID_SCALE = 100
CANVAS = 400

# Board positions in grid units -> expected canvas pixels
POSITIONS = [
    ([0, 0], [0.0, 0.0]),
    ([500, 500], [200.0, 200.0]),
    # Second empire's start box (SpaceAllocator perimeter, 2 empires)
    ([999, 1000], [399.6, 400.0]),
]

TRANSFORM_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const viewer = global.window.BattleViewer;

// show() and cellCenter() run against a stub so no DOM is needed
const stub = {
    canvasWidth: viewer.canvasWidth,
    container: { classList: { remove() {} } },
    render() {},
    renderBattle() {}
};
viewer.show.call(stub, JSON.parse(process.argv[2]));

const out = {
    gridScale: stub.gridScale,
    gridSize: stub.gridSize,
    cellSize: stub.cellSize,
    pixels: JSON.parse(process.argv[3]).map(
        p => viewer.cellCenter.call(stub, { x: p[0], y: p[1] }))
};
console.log(JSON.stringify(out));
"""


DESCRIBE_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const viewer = global.window.BattleViewer;

const report = JSON.parse(process.argv[2]);
const stub = { battleReport: report, getStack: viewer.getStack,
               stackName: viewer.stackName,
               PRIORITY_TIER_LABELS: viewer.PRIORITY_TIER_LABELS };
console.log(JSON.stringify(report.steps.map(
    s => viewer.describeStep.call(stub, s))));
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestBattleViewerLegibility:
    """The replay log names the tier and role behind every shot, and
    a withdrawal reads as a withdrawal (backend BattleStepTarget /
    BattleStepWithdraw)."""

    @pytest.fixture(scope="class")
    def lines(self):
        report = {
            "location": "Sol", "grid_size": GRID_SCALE, "year": 2455,
            "stacks": {
                "1": {"key": 1, "owner": 1, "name": "Raider",
                      "battle_plan": "Commerce Raid",
                      "battle_role": "Escort",
                      "token": {"design_name": "Stalwart Defender",
                                "quantity": 2}},
                "2": {"key": 2, "owner": 2, "name": "Convoy",
                      "battle_plan": "Default",
                      "battle_role": "Logistics",
                      "token": {"design_name": "Teamster",
                                "quantity": 1}},
            },
            "steps": [
                {"type": "Target", "stack_key": 1, "target_key": 2,
                 "percent_to_fire": 100, "priority": 7,
                 "target_role": "Logistics"},
                {"type": "Withdraw", "stack_key": 2},
                # A report written before the change carries neither
                {"type": "Target", "stack_key": 1, "target_key": 2,
                 "percent_to_fire": 50},
            ],
        }
        result = subprocess.run(
            [NODE, "-e", DESCRIBE_SCRIPT, str(BATTLE_VIEWER),
             json.dumps(report)],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_target_step_names_the_tier_and_the_role(self, lines):
        assert lines[0] == ("Raider targets Convoy "
                            "[Primary target, Logistics] (100% fire)")

    def test_withdrawal_has_its_own_line(self, lines):
        assert lines[1] == "Convoy withdraws from the battle"

    def test_legacy_target_step_still_reads(self, lines):
        assert lines[2] == "Raider targets Convoy (50% fire)"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestBattleViewerTransform:
    """Positions on the 0-1000 grid map inside the 400px canvas."""

    @pytest.fixture(scope="class")
    def transform(self):
        report = {"location": "Sol", "grid_size": GRID_SCALE,
                  "year": 2455, "steps": [], "stacks": {}}
        result = subprocess.run(
            [NODE, "-e", TRANSFORM_SCRIPT, str(BATTLE_VIEWER),
             json.dumps(report), json.dumps([p for p, _ in POSITIONS])],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_parses(self):
        result = subprocess.run([NODE, "--check", str(BATTLE_VIEWER)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_board_is_ten_squares_over_the_canvas(self, transform):
        """grid_size is units per square, not a count of squares."""
        assert transform["gridScale"] == GRID_SCALE
        assert transform["gridSize"] == 10
        assert transform["cellSize"] == CANVAS / 10

    def test_positions_map_to_expected_pixels(self, transform):
        for pixel, (_, expected) in zip(transform["pixels"], POSITIONS):
            assert pixel["x"] == pytest.approx(expected[0])
            assert pixel["y"] == pytest.approx(expected[1])

    def test_every_position_stays_on_canvas(self, transform):
        for pixel in transform["pixels"]:
            assert 0 <= pixel["x"] <= CANVAS
            assert 0 <= pixel["y"] <= CANVAS
