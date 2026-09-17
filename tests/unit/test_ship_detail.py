"""
Unit tests for the ShipDetail renderer (frontend/js/views/ship-detail.js)
and the shared SDF engine (frontend/js/views/sdf-engine.js) it marches on.

Canvas cannot run here, but the renderer was deliberately built so that
the expensive half of it does not need one: `renderPixels` returns a raw
RGBA buffer and touches no DOM, and the distance field and its operators
are plain functions. So these tests exercise the real shipped code in
node rather than a Python port of it.

Covered: both files parse, the engine is genuinely shared with the
station renderer (same function objects, not a copy), the new arc
primitive is a true distance, every hull class in the catalogue is a
data record that compiles through the generic part evaluator, bounds
really contain the geometry, cameras are off axis, every class renders
non-empty and lit, renders are byte identical, classes are pairwise
distinct, and a cold render fits the 800 ms budget. The visual result
lives in walkthrough/review/ships-photoreal.png.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
SHIP_DETAIL = FRONTEND / "js" / "views" / "ship-detail.js"
SDF_ENGINE = FRONTEND / "js" / "views" / "sdf-engine.js"
STATION_DETAIL = FRONTEND / "js" / "views" / "station-detail.js"
PREVIEW = FRONTEND / "preview-ships.html"

NODE = shutil.which("node")

# Every ship hull class in backend/data/components.xml. Stations, the
# mineral packet and salvage render elsewhere or not at all.
HULLS = [
    "Scout",
    "Frigate",
    "Destroyer",
    "Cruiser",
    "Battle Cruiser",
    "Battleship",
    "Dreadnought",
    "Nubian",
    "Meta Morph",
    "Privateer",
    "Rogue",
    "Galleon",
    "Small Freighter",
    "Medium Freighter",
    "Large Freighter",
    "Super Freighter",
    "Colony Ship",
    "Mini-Colony Ship",
    "Assault Transport",
    "Mini Bomber",
    "B-17 Bomber",
    "Stealth Bomber",
    "B-52 Bomber",
    "Midget Miner",
    "Mini Miner",
    "Miner",
    "Maxi Miner",
    "Ultra Miner",
    "Mini Mine Layer",
    "Super Mine Layer",
]

# Size the render tests march at. Small enough to keep the suite quick,
# large enough that every class still covers a few thousand pixels.
RENDER_SIZE = 96

LOAD = """
const fs = require('fs');
global.window = {};
eval(fs.readFileSync(process.argv[1], 'utf8'));
const SD = global.window.ShipDetail;
"""

ENGINE_SHARED_SCRIPT = LOAD + """
eval(fs.readFileSync(process.argv[2], 'utf8'));
const ST = global.window.StationDetail;
console.log(JSON.stringify({
    // identity, not equality: one engine module, two consumers
    samePrimitives: SD.sdf.sphere === ST.sdf.sphere
        && SD.sdf.box === ST.sdf.box
        && SD.sdf.union === ST.sdf.union
        && SD.sdf.smoothSubtract === ST.sdf.smoothSubtract,
    sameTune: SD.TUNE.MARCH_STEPS === ST.TUNE.MARCH_STEPS,
    // ship materials extend the shared table rather than forking it
    shipMaterialCount: SD.MATERIALS.length,
    stationMaterialCount: ST.MATERIALS.length,
    baseSliceShared: SD.MATERIALS[0] === ST.MATERIALS[0]
        && SD.MATERIALS[5] === ST.MATERIALS[5]
}));
"""

ARC_SCRIPT = LOAD + """
const A = SD.sdf.arc;
// sdArc(ax, rb, rc, R, r, an): torus about the ax axis, swept an
// radians either side of +rb. On the arc spine the field is -r; at
// R + r along the spine direction it is zero; the cap ends are round.
const R = 0.5, r = 0.1;
const capAngle = 0.5;
const probeAngle = 1.2;
const spine = A(0, R, 0, R, r, 1.0);
const surface = A(0, R + r, 0, R, r, 1.0);
const outside = A(0, R + 2 * r, 0, R, r, 1.0);
// a point on the circle but past the angular cap: nearest surface is
// the spherical cap end, a chord away minus the tube radius
const px = R * Math.cos(probeAngle), py = R * Math.sin(probeAngle);
const beyondCap = A(0, px, py, R, r, capAngle);
const chord = 2 * R * Math.sin((probeAngle - capAngle) / 2);
console.log(JSON.stringify({
    spine, surface, outside, beyondCap, expectedCap: chord - r
}));
"""

TABLE_SCRIPT = LOAD + """
const table = SD.DESIGNS;
const names = Object.keys(table);
const shape = {};
for (const n of names) {
    const d = table[n];
    shape[n] = {
        bound: d.bound,
        yaw: d.yaw,
        pitch: d.pitch,
        fill: d.fill,
        partCount: d.parts.length,
        scene: typeof d.scene === 'function',
        sceneFinite: isFinite(d.scene(2, 2, 2)) && isFinite(d.scene(0, 0, 0))
    };
}
let badPrimitiveThrows = false;
try { SD.compilePart({ p: 'dodecahedron', d: [1] }); }
catch (e) { badPrimitiveThrows = true; }
let badOpThrows = false;
try { SD.compilePart({ p: 'box', op: 'xor', d: [1, 1, 1] }); }
catch (e) { badOpThrows = true; }
console.log(JSON.stringify({
    names: names,
    shape: shape,
    materials: SD.MATERIALS.length,
    tune: SD.TUNE,
    badPrimitiveThrows: badPrimitiveThrows,
    badOpThrows: badOpThrows,
    fallbacks: {
        exact: SD.classify('Dreadnought'),
        freighterish: SD.classify('Bulk Freighter Mk II'),
        colonish: SD.classify('Colonizer'),
        minerish: SD.classify('Deep Core Miner'),
        layerish: SD.classify('Mine Dispenser'),
        unknown: SD.classify('No Such Hull'),
        empty: SD.classify(null)
    }
}));
"""

BOUNDS_SCRIPT = LOAD + """
// Walk each compiled scene from well outside the class bound back
// toward the origin along a spread of directions, and record the
// radius of the outermost surface found. Nothing may sit beyond the
// declared bound, because the renderer rejects rays that miss that
// sphere outright.
const out = {};
for (const name of Object.keys(SD.DESIGNS)) {
    const spec = SD.DESIGNS[name];
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
const buffers = {};
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
    buffers[name] = first;
    out.push({
        name: name, length: first.length, ms: ms,
        ink: ink, lit: lit, bright: bright, identical: identical
    });
}

// pairwise distinctness: two hulls must not paint the same picture.
// Count pixels whose colour differs meaningfully between the pair.
const total = size * size;
let minDiff = 1;
let closest = null;
for (let a = 0; a < names.length; a++) {
    for (let b = a + 1; b < names.length; b++) {
        const A = buffers[names[a]], B = buffers[names[b]];
        let diff = 0;
        for (let i = 0; i < A.length; i += 4) {
            if (Math.abs(A[i] - B[i]) > 12
                || Math.abs(A[i + 1] - B[i + 1]) > 12
                || Math.abs(A[i + 3] - B[i + 3]) > 12) diff++;
        }
        const frac = diff / total;
        if (frac < minDiff) {
            minDiff = frac;
            closest = names[a] + ' vs ' + names[b];
        }
    }
}
console.log(JSON.stringify({ renders: out, minDiff: minDiff,
    closest: closest }));
"""


def _node(script, *args):
    result = subprocess.run(
        [NODE, "-e", script, str(SHIP_DETAIL), *args],
        capture_output=True, text=True, cwd=str(REPO_ROOT))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSources:
    def test_sources_parse(self):
        for path in (SDF_ENGINE, SHIP_DETAIL):
            result = subprocess.run([NODE, "--check", str(path)],
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr

    def test_no_nondeterminism(self):
        """A call to Math.random anywhere would break the per-class cache."""
        assert "Math.random(" not in SHIP_DETAIL.read_text()
        assert "Math.random(" not in SDF_ENGINE.read_text()

    def test_preview_page_is_static(self):
        html = PREVIEW.read_text()
        assert "js/views/sdf-engine.js" in html
        assert "js/views/ship-detail.js" in html
        assert "/api/" not in html
        assert "window.PREVIEW_READY" in html


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestSharedEngine:
    def test_engine_is_shared_not_copied(self):
        """
        Ship and station renderers must resolve to the same engine
        module: identical function objects, not parallel implementations
        that will drift apart.
        """
        data = _node(ENGINE_SHARED_SCRIPT, str(STATION_DETAIL))
        assert data["samePrimitives"] is True
        assert data["sameTune"] is True
        assert data["baseSliceShared"] is True
        # ships extend the shared material table with drive plasma,
        # weapon glow, stealth composite and hazard paint
        assert data["shipMaterialCount"] == data["stationMaterialCount"] + 4

    def test_arc_primitive_is_a_true_distance(self):
        """
        The arc (capped torus) is new with the ship catalogue. Sphere
        tracing steps by the reported distance, so it must be exact on
        the tube and at the angular caps alike.
        """
        d = _node(ARC_SCRIPT)
        assert d["spine"] == pytest.approx(-0.1, abs=1e-9)
        assert d["surface"] == pytest.approx(0.0, abs=1e-9)
        assert d["outside"] == pytest.approx(0.1, abs=1e-9)
        assert d["beyondCap"] == pytest.approx(d["expectedCap"], abs=1e-9)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestCatalogue:
    def test_carries_every_ship_hull(self):
        assert _node(TABLE_SCRIPT)["names"] == HULLS

    def test_every_design_record_compiles(self):
        """
        A design is a data record: a part list the generic evaluator
        walks, plus the camera framing. The compiled scene must return
        finite distances everywhere - the marcher has no other guard.
        """
        shape = _node(TABLE_SCRIPT)["shape"]
        for name, spec in shape.items():
            assert spec["scene"], f"{name} did not compile to a scene"
            assert spec["sceneFinite"], f"{name} returns non-finite distances"
            assert spec["partCount"] >= 5, (
                f"{name} has only {spec['partCount']} parts - "
                "that is a blob, not a hull")
            assert spec["bound"] > 0, f"{name} has no bounding radius"
            assert 0 < spec["fill"] <= 1, f"{name} has a bad fill factor"

    def test_unknown_schema_entries_are_rejected(self):
        """The compiler must fail loudly on a bad record, not render mush."""
        data = _node(TABLE_SCRIPT)
        assert data["badPrimitiveThrows"] is True
        assert data["badOpThrows"] is True

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
        gets both a yaw and a pitch away from zero, and yaw varies
        across the catalogue so the sheet does not read as clones.
        """
        shape = _node(TABLE_SCRIPT)["shape"]
        yaws = []
        for name, spec in shape.items():
            assert abs(spec["yaw"]) > 0.15, f"{name} is nearly axis-on in yaw"
            assert abs(spec["pitch"]) > 0.15, f"{name} is nearly level"
            yaws.append(round(spec["yaw"], 3))
        assert len(set(yaws)) >= len(yaws) * 2 // 3, (
            "yaw barely varies across the catalogue")

    def test_march_tunables_are_exposed(self):
        tune = _node(TABLE_SCRIPT)["tune"]
        assert tune["MARCH_STEPS"] > 0
        assert tune["MAX_DIST"] > 0
        assert tune["AO_TAPS"] > 0
        assert tune["SHADOW_STEPS"] > 0

    def test_unknown_hulls_fall_back_by_family(self):
        fb = _node(TABLE_SCRIPT)["fallbacks"]
        assert fb["exact"] == "Dreadnought"
        assert fb["freighterish"] == "Medium Freighter"
        assert fb["colonish"] == "Colony Ship"
        assert fb["minerish"] == "Miner"
        assert fb["layerish"] == "Mini Mine Layer"
        assert fb["unknown"] == "Scout"
        assert fb["empty"] == "Scout"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
class TestRender:
    @pytest.fixture(scope="class")
    def rendered(self):
        return _node(RENDER_SCRIPT, str(RENDER_SIZE), json.dumps(HULLS))

    @pytest.fixture(scope="class")
    def renders(self, rendered):
        return {r["name"]: r for r in rendered["renders"]}

    def test_every_class_renders_something(self, renders):
        for name in HULLS:
            r = renders[name]
            assert r["length"] == RENDER_SIZE * RENDER_SIZE * 4
            # a ship that covers under two percent of the frame is a
            # speck, not a detail view
            coverage = r["ink"] / (RENDER_SIZE * RENDER_SIZE)
            assert coverage > 0.02, f"{name} covered only {coverage:.3f}"

    def test_every_class_is_lit(self, renders):
        """Silhouette is not enough: the hull has to catch the key light."""
        for name in HULLS:
            r = renders[name]
            assert r["lit"] > r["ink"] * 0.5, f"{name} rendered mostly black"
            assert r["bright"] > 50, f"{name} has no highlight anywhere"

    def test_renders_are_byte_identical(self, renders):
        """
        Determinism is what makes the per-class cache safe, and what
        stops a hull changing appearance between visits.
        """
        for name in HULLS:
            assert renders[name]["identical"], f"{name} rendered differently"

    def test_renders_fit_the_budget(self, renders):
        """Cold render budget: 800 ms per hull."""
        for name in HULLS:
            assert renders[name]["ms"] <= 800, (
                f"{name} took {renders[name]['ms']} ms cold")

    def test_classes_are_pairwise_distinct(self, rendered):
        """
        Thirty hulls must be thirty pictures. The closest pair still has
        to disagree on a meaningful fraction of the frame.
        """
        assert rendered["minDiff"] > 0.03, (
            f"nearly identical renders: {rendered['closest']} "
            f"differ on only {rendered['minDiff']:.3f} of the frame")
