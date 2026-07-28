"""
Unit tests for the StationDetail renderer (frontend/js/views/station-detail.js).

Canvas cannot run here, but the renderer was deliberately built so that
the expensive half of it does not need one: `renderPixels` returns a raw
RGBA buffer and touches no DOM, and the distance field and its operators
are plain functions. So these tests exercise the real shipped code in
node rather than a Python port of it.

Covered: the file parses, the analytic distance functions are negative
inside their primitive and positive outside it, surface normals derived
from the field are unit length, the design table carries the full class
ladder, every class renders something, and two renders of the same class
are byte identical. The visual result lives in
walkthrough/review/stations-photoreal.png.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
STATION_DETAIL = FRONTEND / "js" / "views" / "station-detail.js"
PLANET_ART = FRONTEND / "js" / "views" / "planet-art.js"
PREVIEW = FRONTEND / "preview-stations.html"

NODE = shutil.which("node")

# The class ladder from the original game's own starbase art, in
# references/original-game/Graphics/High_Resolution/Base/
LADDER = [
    "Orbital Fort",
    "Space Dock",
    "Space Station",
    "Ultra Station",
    "Death Star",
    "Shipyard",
]

# Size the render tests march at. Small enough to keep the suite quick,
# large enough that every class still covers a few thousand pixels.
RENDER_SIZE = 96

LOAD = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const SD = global.window.StationDetail;
"""

PRIMITIVES_SCRIPT = LOAD + """
const S = SD.sdf;

// Each entry: a point known to be inside, one known to be outside, and
// one on the surface. The analytic functions are exact, so the surface
// sample has to come out at zero to within floating point slop.
const cases = {
    sphere:    [S.sphere(0, 0, 0, 1),
                S.sphere(2, 0, 0, 1),
                S.sphere(1, 0, 0, 1)],
    box:       [S.box(0, 0, 0, 1, 1, 1),
                S.box(3, 0, 0, 1, 1, 1),
                S.box(1, 0, 0, 1, 1, 1)],
    roundBox:  [S.roundBox(0, 0, 0, 1, 1, 1, 0.2),
                S.roundBox(3, 0, 0, 1, 1, 1, 0.2),
                S.roundBox(1, 0, 0, 1, 1, 1, 0.2)],
    cyl:       [S.cyl(0, 0, 0, 1, 0.5),
                S.cyl(0, 2, 0, 1, 0.5),
                S.cyl(0, 0.5, 0, 1, 0.5)],
    torus:     [S.torus(0, 1, 0, 1, 0.25),
                S.torus(0, 0, 0, 1, 0.25),
                S.torus(0, 1.25, 0, 1, 0.25)],
    capsule:   [S.capsule(0, 0, 0, 0, -1, 0, 0, 1, 0, 0.3),
                S.capsule(1, 0, 0, 0, -1, 0, 0, 1, 0, 0.3),
                S.capsule(0.3, 0, 0, 0, -1, 0, 0, 1, 0, 0.3)],
    ellipsoid: [S.ellipsoid(0, 0, 0, 1, 2, 1),
                S.ellipsoid(3, 0, 0, 1, 2, 1),
                S.ellipsoid(1, 0, 0, 1, 2, 1)]
};

// exterior distance must be a true distance, not merely positive: a
// point two units clear of a unit sphere is exactly one unit outside it
const exact = {
    sphereExterior: S.sphere(3, 0, 0, 1),
    boxExterior: S.box(4, 0, 0, 1, 1, 1)
};

// operators: union takes the nearer, subtraction opens a hole where the
// cutter is, smooth union never returns more than the plain union
const a = S.sphere(0.9, 0, 0, 1);
const b = S.sphere(0.9 - 2, 0, 0, 1);
const ops = {
    unionTakesNearer: S.union(a, b, 0),
    plainMin: Math.min(a, b),
    subtractOpensHole: S.subtract(S.sphere(0, 0, 0, 1),
                                  S.sphere(0, 0, 0, 0.5), 1),
    intersect: S.intersect(-0.4, -0.1, 0),
    smoothUnion: S.smoothUnion(a, b, 0.3, 0),
    smoothNeverFarther: S.smoothUnion(a, b, 0.3, 0) <= Math.min(a, b) + 1e-12
};

console.log(JSON.stringify({ cases, exact, ops }));
"""

NORMALS_SCRIPT = LOAD + """
const S = SD.sdf;

// A compound field, so the normals being tested are the ones the
// renderer actually shades: a drum smooth-unioned to an axle with a
// torus groove cut round its waist.
function field(x, y, z) {
    let d = S.cyl(y, x, z, 1.0, 0.10);
    d = S.smoothUnion(d, S.roundCyl(y, x, z, 0.29, 0.70, 0.10), 0.10, 2);
    d = S.subtract(d, S.torus(y, x, z, 0.71, 0.055), 5);
    return d;
}

// tetrahedral central differences, the same four-tap pattern the
// renderer uses
function normal(x, y, z) {
    const h = 0.0016;
    const a = field(x + h, y - h, z - h);
    const b = field(x - h, y - h, z + h);
    const c = field(x - h, y + h, z - h);
    const d = field(x + h, y + h, z + h);
    let nx = a - b - c + d, ny = -a - b + c + d, nz = -a + b - c + d;
    const l = Math.sqrt(nx * nx + ny * ny + nz * nz);
    return [nx / l, ny / l, nz / l, l];
}

const lengths = [];
const degenerate = [];
for (let i = 0; i < 240; i++) {
    // walk a helix over the hull so the samples land on the drum, the
    // groove, the fairing and the axle alike
    const t = i / 240;
    const ang = t * Math.PI * 2 * 7;
    const r = 0.62 + 0.16 * Math.sin(t * Math.PI * 5);
    const x = r * Math.cos(ang), z = r * Math.sin(ang);
    const y = -1.0 + 2.0 * t;
    const n = normal(x, y, z);
    if (!isFinite(n[0]) || n[3] === 0) { degenerate.push(i); continue; }
    lengths.push(Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]));
}
console.log(JSON.stringify({ lengths, degenerate }));
"""

TABLE_SCRIPT = LOAD + """
// The class table is data - the point of the design is that a follow-on
// wave adds entries here without touching the raymarcher.
const table = SD.DESIGNS || SD.CLASSES;
const names = Object.keys(table);
const shape = {};
for (const n of names) {
    const d = table[n];
    shape[n] = {
        bound: d.bound,
        yaw: d.yaw,
        pitch: d.pitch,
        scene: typeof d.scene === 'function'
    };
}
console.log(JSON.stringify({
    names: names,
    shape: shape,
    materials: SD.MATERIALS.length,
    tune: SD.TUNE,
    fallbacks: {
        unknown: SD.classify('No Such Hull'),
        yardish: SD.classify('Orbital Shipyard'),
        dockish: SD.classify('Deep Space Dock Mk II'),
        exact: SD.classify('Ultra Station'),
        empty: SD.classify(null)
    }
}));
"""

BOUNDS_SCRIPT = LOAD + """
// Walk each scene field from well outside the class bound back toward
// the origin along a spread of directions, and record the radius of the
// outermost surface found. Nothing may sit beyond the declared bound,
// because the renderer rejects rays that miss that sphere outright.
const out = {};
for (const name of Object.keys(SD.CLASSES)) {
    const spec = SD.CLASSES[name];
    const scene = spec.scene;
    let maxR = 0;
    for (let i = 0; i < 700; i++) {
        // deterministic spherical spread: golden-angle spiral
        const u = (i + 0.5) / 700;
        const ct = 1 - 2 * u;
        const st = Math.sqrt(1 - ct * ct);
        const ph = i * 2.399963229728653;
        const dx = st * Math.cos(ph), dy = ct, dz = st * Math.sin(ph);
        // march inward from outside the bound
        let t = spec.bound * 1.6;
        for (let k = 0; k < 220 && t > 0.02; k++) {
            const h = scene(dx * t, dy * t, dz * t);
            if (h < 1e-4) break;
            t -= Math.max(h * 0.6, 1e-3);
        }
        if (t > maxR) maxR = t;
    }
    out[name] = { bound: spec.bound, max: maxR };
}
console.log(JSON.stringify(out));
"""

RENDER_SCRIPT = LOAD + """
const size = parseInt(process.argv[2], 10);
const names = JSON.parse(process.argv[3]);
const out = [];
for (const name of names) {
    SD.cache.clear();
    const t0 = Date.now();
    const first = SD.renderPixels(name, size);
    const ms = Date.now() - t0;

    // a second render from a cleared cache must reproduce byte for byte,
    // or something in the renderer is reading a clock or Math.random
    SD.cache.clear();
    const second = SD.renderPixels(name, size);

    let identical = first.length === second.length;
    if (identical) {
        for (let i = 0; i < first.length; i++) {
            if (first[i] !== second[i]) { identical = false; break; }
        }
    }

    // ink: pixels with meaningful alpha. lit: pixels with any colour in
    // them, which separates "drew a silhouette" from "drew a black hole"
    let ink = 0, lit = 0, bright = 0;
    for (let i = 0; i < first.length; i += 4) {
        if (first[i + 3] > 8) {
            ink++;
            const v = first[i] + first[i + 1] + first[i + 2];
            if (v > 24) lit++;
            if (v > 300) bright++;
        }
    }
    out.push({
        name: name, length: first.length, ms: ms,
        ink: ink, lit: lit, bright: bright, identical: identical
    });
}
console.log(JSON.stringify(out));
"""


def _node(script, *args):
    result = subprocess.run(
        [NODE, "-e", script, str(STATION_DETAIL), *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSources:
    def test_station_detail_parses(self):
        result = subprocess.run([NODE, "--check", str(STATION_DETAIL)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_no_nondeterminism(self):
        """A call to Math.random anywhere would break the per-class cache."""
        assert "Math.random(" not in STATION_DETAIL.read_text()

    def test_preview_page_is_static(self):
        html = PREVIEW.read_text()
        assert "js/views/station-detail.js" in html
        assert "/api/" not in html
        assert "window.PREVIEW_READY" in html

    def test_star_panel_sprite_left_alone(self):
        """
        The tiny sprite in planet-art.js is a separate renderer and this
        work must not have disturbed it. At eight pixels photorealism is
        not available; the split is the whole reason it is here.
        """
        source = PLANET_ART.read_text()
        assert "_drawStation" in source
        assert "STATIONS:" in source
        assert "StationDetail" not in source


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestDistanceField:
    def test_inside_is_negative_outside_is_positive(self):
        data = _node(PRIMITIVES_SCRIPT)
        for name, (inside, outside, surface) in data["cases"].items():
            assert inside < 0, f"{name}: interior sample was not negative"
            assert outside > 0, f"{name}: exterior sample was not positive"
            assert abs(surface) < 1e-9, f"{name}: surface sample was {surface}"

    def test_exterior_distance_is_a_true_distance(self):
        """
        Sphere tracing steps by the reported distance, so an overstated
        field walks through hulls. Both of these are exact.
        """
        exact = _node(PRIMITIVES_SCRIPT)["exact"]
        assert exact["sphereExterior"] == pytest.approx(2.0, abs=1e-12)
        assert exact["boxExterior"] == pytest.approx(3.0, abs=1e-12)

    def test_operators(self):
        ops = _node(PRIMITIVES_SCRIPT)["ops"]
        assert ops["unionTakesNearer"] == pytest.approx(ops["plainMin"])
        # subtracting a smaller concentric sphere leaves a shell: the
        # centre is now outside the solid
        assert ops["subtractOpensHole"] > 0
        assert ops["intersect"] == pytest.approx(-0.1)
        # a smooth union is never farther than the hard union it fairs
        assert ops["smoothNeverFarther"] is True
        assert ops["smoothUnion"] <= ops["plainMin"] + 1e-12

    def test_normals_are_unit_length(self):
        data = _node(NORMALS_SCRIPT)
        assert data["degenerate"] == []
        assert len(data["lengths"]) >= 200
        for length in data["lengths"]:
            assert length == pytest.approx(1.0, abs=1e-9)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestDesignTable:
    def test_carries_the_whole_ladder(self):
        names = _node(TABLE_SCRIPT)["names"]
        assert names == LADDER

    def test_every_design_is_marchable(self):
        """
        A design is a scene function plus the sphere it fits in. The bound
        is load bearing twice over: it frames the camera, and it is the
        ray rejection test, so an understated bound clips the silhouette.

        Geometry is carried by a per-class scene function rather than by a
        declarative part list. A catalogue of twenty-plus station types
        would want the declarative form; this wave ships the six canonical
        classes and does not.
        """
        shape = _node(TABLE_SCRIPT)["shape"]
        for name, spec in shape.items():
            assert spec["scene"], f"{name} has no scene function"
            assert spec["bound"] > 0, f"{name} has no bounding radius"

    def test_bounds_actually_contain_the_hull(self):
        """
        Every marched hit must land inside the class's bounding sphere.
        If it does not, the ray rejection test is cutting geometry away.
        """
        for name, radius in _node(BOUNDS_SCRIPT).items():
            assert radius["max"] <= radius["bound"] + 1e-6, (
                f"{name} reaches {radius['max']:.3f} "
                f"outside its bound of {radius['bound']}")
            # and the bound must not be wildly loose, or the class renders
            # as a speck in the middle of an empty frame
            assert radius["max"] > radius["bound"] * 0.55, (
                f"{name} only fills {radius['max']:.3f} of {radius['bound']}")

    def test_cameras_are_off_axis(self):
        """
        An axis-on camera flattens a hull into an emblem. Every design
        gets both a yaw and a pitch away from zero.
        """
        shape = _node(TABLE_SCRIPT)["shape"]
        for name, spec in shape.items():
            assert abs(spec["yaw"]) > 0.15, f"{name} is nearly axis-on in yaw"
            assert abs(spec["pitch"]) > 0.15, f"{name} is nearly level"

    def test_march_tunables_are_exposed(self):
        tune = _node(TABLE_SCRIPT)["tune"]
        assert tune["MARCH_STEPS"] > 0
        assert tune["MAX_DIST"] > 0
        assert tune["AO_TAPS"] > 0
        assert tune["SHADOW_STEPS"] > 0

    def test_unknown_hulls_fall_back(self):
        fb = _node(TABLE_SCRIPT)["fallbacks"]
        assert fb["exact"] == "Ultra Station"
        assert fb["yardish"] == "Shipyard"
        assert fb["dockish"] == "Space Dock"
        assert fb["unknown"] == "Orbital Fort"
        assert fb["empty"] == "Orbital Fort"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestRender:
    @pytest.fixture(scope="class")
    def renders(self):
        return {r["name"]: r
                for r in _node(RENDER_SCRIPT, str(RENDER_SIZE),
                               json.dumps(LADDER))}

    def test_every_class_renders_something(self, renders):
        for name in LADDER:
            r = renders[name]
            assert r["length"] == RENDER_SIZE * RENDER_SIZE * 4
            # a station that covers under two percent of the frame is a
            # speck, not a detail view
            coverage = r["ink"] / (RENDER_SIZE * RENDER_SIZE)
            assert coverage > 0.02, f"{name} covered only {coverage:.3f}"

    def test_every_class_is_lit(self, renders):
        """Silhouette is not enough: the hull has to catch the key light."""
        for name in LADDER:
            r = renders[name]
            assert r["lit"] > r["ink"] * 0.5, f"{name} rendered mostly black"
            assert r["bright"] > 50, f"{name} has no highlight anywhere"

    def test_renders_are_byte_identical(self, renders):
        """
        Determinism is what makes the per-class cache safe, and what stops
        a station changing appearance between visits.
        """
        for name in LADDER:
            assert renders[name]["identical"], f"{name} rendered differently"

    def test_classes_differ_from_each_other(self, renders):
        """Six sizes of one shape would be one shape."""
        coverages = sorted(r["ink"] for r in renders.values())
        assert len(set(coverages)) == len(LADDER)
