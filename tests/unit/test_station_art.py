"""
Unit tests for the orbital station renderer inside PlanetArt
(frontend/js/views/planet-art.js).

Canvas cannot run here, so this module covers what does not need pixels.
_stationParts is pure geometry - it returns integer rectangles in a local
frame - so it runs in node exactly as shipped and the size budget, the
2 px feature floor and the per-class topology are all checked against the
real layout code. The rendered pixel evidence (ink against the planet
disc, contrast on sky and on a lit surface) lives on the review sheet
frontend/preview-planets.html, which reports it per cell.

The design is specified in docs/research-station-rendering.md. The
failure it replaces was topological - N radial spars from a hub, which
reads as an emblem - so the source-level assertions here pin the things
that made it soft: round line caps, alpha-modulated fills and the dashed
orbit ellipse.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
PLANET_ART = FRONTEND / "js" / "views" / "planet-art.js"
PREVIEW = FRONTEND / "preview-planets.html"

NODE = shutil.which("node")

CLASSES = [
    "Orbital Fort", "Space Dock", "Space Station",
    "Ultra Station", "Death Star", "Shipyard",
]

# star-panel canvas is 80 px (R = 25); the review sheet is 200 px (R = 62.5)
RADII = [25, 32, 62.5, 65, 80, 100]

PARTS_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const A = global.window.PlanetArt;
const radii = JSON.parse(process.argv[2]);
const out = {};
for (const [name, spec] of Object.entries(A.STATIONS)) {
    out[name] = { len: spec.len, min: spec.min, kind: spec.kind, sizes: {} };
    for (const R of radii) {
        const L = Math.max(spec.min, Math.round(R * spec.len));
        if (spec.kind === 'sphere') {
            out[name].sizes[R] = { L, w: L, h: L, rects: [] };
            continue;
        }
        const p = A._stationParts(spec.kind, L);
        const rects = [].concat(p.body, p.panels, p.hull, p.struts,
                                p.cuts, p.lights, p.work);
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const q of rects) {
            x0 = Math.min(x0, q.x); y0 = Math.min(y0, q.y);
            x1 = Math.max(x1, q.x + q.w); y1 = Math.max(y1, q.y + q.h);
        }
        out[name].sizes[R] = {
            L, w: x1 - x0, h: y1 - y0, rects,
            counts: {
                body: p.body.length, panels: p.panels.length,
                hull: p.hull.length, struts: p.struts.length,
                cuts: p.cuts.length, lights: p.lights.length,
                work: p.work.length
            }
        };
    }
}
console.log(JSON.stringify(out));
"""

SPEC_SCRIPT = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const A = global.window.PlanetArt;
const stars = JSON.parse(process.argv[2]);
console.log(JSON.stringify(stars.map(s => {
    const spec = A.stationSpec(s);
    return spec ? spec.kind : null;
})));
"""


def _node(script, *args):
    result = subprocess.run([NODE, "-e", script, str(PLANET_ART), *args],
                            capture_output=True, text=True,
                            cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def parts():
    return _node(PARTS_SCRIPT, json.dumps(RADII))


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSource:
    def test_parses(self):
        result = subprocess.run([NODE, "--check", str(PLANET_ART)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_the_rejected_construction_is_gone(self):
        src = PLANET_ART.read_text()
        # radial spars from a hub, a concentric ring and one light per arm
        assert "arms" not in src
        assert "habitation torus" not in src
        assert "setLineDash" not in src

    def test_no_round_caps_and_no_alpha_modulated_station_fills(self):
        src = PLANET_ART.read_text()
        assert "lineCap" not in src
        station = src[src.index("STATION_COLORS"):
                      src.index("A reusable offscreen canvas")]
        assert "rgba(" not in station.replace(
            "rgba(160,185,225,0.12)", "")   # the opt-in orbit arc only
        assert "rgb(4,6,10)" in station     # the keyline

    def test_orbit_ellipse_is_off_by_default(self):
        src = PLANET_ART.read_text()
        assert "STATION_ORBIT_ARC: false" in src

    def test_preview_sheet_covers_every_class(self):
        html = PREVIEW.read_text()
        for name in CLASSES:
            assert f"'{name}'" in html
        assert "window.PREVIEW_READY = true" in html


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestClassTable:
    def test_every_class_present(self, parts):
        assert sorted(parts) == sorted(CLASSES)

    def test_sizes_are_a_small_fraction_of_the_planet(self, parts):
        # the research ceiling is 0.20 R; the rejected table ran to 0.31
        for name, spec in parts.items():
            assert 0.05 <= spec["len"] <= 0.20, name

    def test_hull_names_map_to_their_own_class(self):
        stars = [{"starbase_hull": n} for n in CLASSES]
        kinds = _node(SPEC_SCRIPT, json.dumps(stars))
        assert kinds == ["fort", "dock", "station", "ultra", "sphere", "yard"]
        assert len(set(kinds)) == 6

    def test_unknown_and_absent_hulls(self):
        stars = [{}, {"starbase_hull": "Orbital Drydock"},
                 {"starbase_name": "Nowhere"}]
        assert _node(SPEC_SCRIPT, json.dumps(stars)) \
            == [None, "yard", "fort"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestFootprint:
    def test_never_outgrows_its_own_budget(self, parts):
        """The whole layout fits inside the class's L x L box."""
        for name, spec in parts.items():
            for R, s in spec["sizes"].items():
                assert s["w"] <= s["L"], (name, R, s)
                assert s["h"] <= s["L"], (name, R, s)

    def test_stays_small_at_the_star_panel_size(self, parts):
        """R is 25 on the 80 px panel. The ring classes need more pixels
        than a bar did - a rim with a core inside it cannot resolve below
        about ten - so the drums are a touch larger than the bars were, but
        the ceiling of 9 stays far under the 15.5 px the rejected version
        drew there."""
        for name, spec in parts.items():
            assert spec["sizes"]["25"]["L"] <= 9, name

    def test_grows_with_the_planet(self, parts):
        for name, spec in parts.items():
            sizes = [spec["sizes"][str(R)]["L"] for R in RADII]
            assert sizes == sorted(sizes), name
            assert sizes[-1] > sizes[0], name

    def test_ultra_station_is_never_the_smallest(self, parts):
        for R in RADII:
            ultra = parts["Ultra Station"]["sizes"][str(R)]["L"]
            for name in ("Orbital Fort", "Space Dock", "Death Star"):
                assert ultra > parts[name]["sizes"][str(R)]["L"], (name, R)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestFeatureBudget:
    def test_no_sub_pixel_rectangles(self, parts):
        for name, spec in parts.items():
            for R, s in spec["sizes"].items():
                for q in s["rects"]:
                    assert q["w"] >= 1 and q["h"] >= 1, (name, R, q)

    def test_structure_clears_two_pixels(self, parts):
        """Hull bars are at least 2 px thick; only lights and the 1 px
        gantry strut are allowed thinner - anti-aliasing eats the rest."""
        for name, spec in parts.items():
            for R, s in spec["sizes"].items():
                if not s["rects"]:
                    continue
                for q in s["rects"][:s["counts"]["body"]]:
                    assert min(q["w"], q["h"]) >= 2, (name, R, q)

    def test_rectangles_sit_on_integer_coordinates(self, parts):
        for name, spec in parts.items():
            for R, s in spec["sizes"].items():
                for q in s["rects"]:
                    assert all(float(v).is_integer() for v in q.values()), \
                        (name, R, q)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestTopology:
    """Classes differ by construction, not by scale. Checked at R = 62.5,
    the review-sheet radius."""

    def counts(self, parts, name):
        return parts[name]["sizes"]["62.5"]["counts"]

    def test_no_class_hangs_guns_outside_its_hull(self, parts):
        """User directive: "no guns outside, stations are large enough that
        they'd have their gun emplacements anyway". A barrel showed up as a
        small body rect protruding past the drum or rim; the drum classes
        are now a single dominant volume plus an axle."""
        for name in ("Orbital Fort", "Space Dock"):
            s = parts[name]["sizes"]["62.5"]
            body = s["rects"][:s["counts"]["body"]]
            biggest = max(q["w"] * q["h"] for q in body)
            ink = sum(q["w"] * q["h"] for q in body)
            assert biggest / ink > 0.5, (name, "no dominant hull volume")

    def test_drum_classes_are_a_pressurised_volume_on_an_axle(self, parts):
        for name in ("Orbital Fort", "Space Dock"):
            c = self.counts(parts, name)
            assert c["panels"] == 0, name
            assert c["work"] == 0, name
            s = parts[name]["sizes"]["62.5"]
            body = s["rects"][:s["counts"]["body"]]
            assert len(body) == 2, (name, "drum plus axle")
            axle = [q for q in body if q["w"] == s["L"]]
            assert len(axle) == 1, (name, "the axle spans the full length")

    def test_station_is_a_truss_with_a_panel_pair_and_an_aperture(self, parts):
        """The DS9 ring was tried here and failed at ten pixels - the rim
        leaves a six pixel interior and a core plus pylons fill it, so it
        reads as a block with two slots. The ring lives in the detail view;
        the sprite stays a truss."""
        c = self.counts(parts, "Space Station")
        assert c["panels"] == 2
        assert c["cuts"] == 1
        assert c["lights"] == 1

    def test_ultra_is_a_twin_spine_truss(self, parts):
        s = parts["Ultra Station"]["sizes"]["62.5"]
        body = s["rects"][:s["counts"]["body"]]
        full = [q for q in body if q["w"] == s["L"]]
        assert len(full) == 2, "two parallel spines run the whole length"
        assert full[0]["y"] + full[0]["h"] < full[1]["y"], "with a gap"
        assert s["counts"]["body"] == 7   # two spines, two ties, three modules

    def test_ultra_carries_more_than_the_station(self, parts):
        """Ultra reads as more station, not as a longer one."""
        st = parts["Space Station"]["sizes"]["62.5"]
        ul = parts["Ultra Station"]["sizes"]["62.5"]
        assert ul["counts"]["body"] > st["counts"]["body"]

    def test_shipyard_is_an_open_frame_with_a_ship_in_it(self, parts):
        c = self.counts(parts, "Shipyard")
        assert c["hull"] == 1          # the part-built hull in the slip
        assert c["struts"] == 2        # gantries
        assert c["work"] == 2          # warm lights inside the slip
        assert c["panels"] == 0
        assert c["lights"] == 0        # no navigation lights: that is a fort

    def test_shipyard_gantries_are_unevenly_spaced(self, parts):
        s = parts["Shipyard"]["sizes"]["62.5"]
        start = s["counts"]["body"] + s["counts"]["panels"] \
            + s["counts"]["hull"]
        a, b = s["rects"][start:start + 2]
        left = a["x"] + s["L"] / 2
        right = b["x"] + s["L"] / 2
        assert abs((right - left) - (s["L"] - right)) >= 1

    def test_death_star_is_the_one_that_is_not_a_truss(self, parts):
        """Every other class is built from rectangles; the sphere is not,
        which is how the reference art distinguishes it too."""
        assert parts["Death Star"]["kind"] == "sphere"
        assert parts["Death Star"]["sizes"]["62.5"]["rects"] == []
        for name, spec in parts.items():
            if name == "Death Star":
                continue
            assert len(spec["sizes"]["62.5"]["rects"]) >= 4, name

    def test_only_the_sphere_and_the_truss_fill_a_square(self, parts):
        """Elongation is what buys size back: a bar reads smaller than a
        blob of the same ink."""
        for name in ("Orbital Fort", "Space Dock", "Shipyard"):
            s = parts[name]["sizes"]["62.5"]
            assert s["w"] > s["h"], name

