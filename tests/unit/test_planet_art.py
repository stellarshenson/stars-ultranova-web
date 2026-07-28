"""
Unit tests for the PlanetArt renderer (frontend/js/views/planet-art.js).

Canvas cannot run here, so this module covers what does not need pixels:
the file parses (node --check), the old star-panel renderer is gone, and
the CLASSIFIER is exercised directly in node - the classifier touches no
DOM, so it runs as shipped rather than being ported to Python. Pixel
behaviour (structure, determinism, timing) lives in
tests/functional/test_planet_rendering.py.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
PLANET_ART = FRONTEND / "js" / "views" / "planet-art.js"
STAR_PANEL = FRONTEND / "js" / "views" / "star-panel.js"
PREVIEW = FRONTEND / "preview-planets.html"

NODE = shutil.which("node")

# The twelve environments of the review sheet: name, temp, rad, gravity
ENVIRONMENTS = [
    ("Frozen", 10, 15, 50, "ice"),
    ("Frozen, irradiated", 10, 85, 50, "radiated"),
    ("Cold earthlike", 35, 40, 50, "tundra"),
    ("Temperate ideal", 50, 50, 50, "terran"),
    ("Low gravity", 50, 50, 20, "barren"),
    ("High gravity", 50, 50, 80, "terran"),
    ("Irradiated temperate", 50, 90, 50, "toxic"),
    ("Hot desert", 70, 30, 50, "desert"),
    ("Volcanic", 75, 70, 60, "volcanic"),
    ("Scorching hell", 95, 95, 70, "toxic"),
    ("Cold gas giant", 25, 40, 95, "gas"),
    ("Hot gas giant", 80, 60, 95, "gas"),
]

CLASSIFY_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const stars = JSON.parse(process.argv[2]);
console.log(JSON.stringify(
    stars.map(s => global.window.PlanetArt.classify(s))));
"""


def _node_check(path):
    result = subprocess.run([NODE, "--check", str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSources:
    def test_planet_art_parses(self):
        _node_check(PLANET_ART)

    def test_star_panel_parses(self):
        _node_check(STAR_PANEL)


class TestStarPanelDelegates:
    def test_old_renderer_removed(self):
        source = STAR_PANEL.read_text()
        assert "getPlanetColors" not in source
        assert "drawPlanetTexture" not in source
        assert "shiftTowardPurple" not in source

    def test_render_delegates_to_planet_art(self):
        assert "PlanetArt.render(this.planetCanvas, star)" \
            in STAR_PANEL.read_text()

    def test_index_loads_planet_art_but_not_the_preview(self):
        index = (FRONTEND / "index.html").read_text()
        assert "js/views/planet-art.js?v=" in index
        assert "preview-planets" not in index

    def test_preview_page_is_static(self):
        html = PREVIEW.read_text()
        assert "js/views/planet-art.js" in html
        assert "js/views/encyclopedia.js" in html
        assert "/api/" not in html


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestClassifier:
    def _classify(self, stars):
        result = subprocess.run(
            [NODE, "-e", CLASSIFY_SCRIPT, str(PLANET_ART), json.dumps(stars)],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    def test_review_sheet_environments(self):
        """Every one of the nine classes is reachable from the sheet."""
        stars = [{"id": name, "name": name, "temperature": t,
                  "radiation": r, "gravity": g}
                 for name, t, r, g, _ in ENVIRONMENTS]
        got = self._classify(stars)
        expected = [cls for *_, cls in ENVIRONMENTS]
        assert got == expected
        assert len(set(got)) == 9

    def test_gas_giant_wins_over_temperature(self):
        stars = [{"id": "a", "temperature": t, "radiation": 50, "gravity": 92}
                 for t in (5, 50, 95)]
        assert self._classify(stars) == ["gas", "gas", "gas"]

    def test_defaults_when_environment_missing(self):
        assert self._classify([{"id": "bare"}]) == ["terran"]
