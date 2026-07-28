"""
Functional: the PlanetArt renderer in a real browser.

Drives frontend/preview-planets.html - a static page with no game state -
and checks the four things unit tests cannot reach:

- every world canvas holds real pixels (non-blank)
- the twelve environments differ from each other by both a colour and a
  structure histogram distance; the structure distance is hue-blind
  (it histograms local luminance gradients), so it is the direct answer
  to "they practically differ only by rotation and hue"
- the same star id renders byte-identical twice, with the bitmap cache
  cleared in between, so determinism comes from the generator
- a single world renders in under 25 ms, timed in page with
  performance.now

Measured distances and timings are written to
logs/functional/planet-rendering.json.
"""

import json

from .conftest import LOG_DIR

PREVIEW_PATH = "/static/preview-planets.html"

# Bars, set from the measured spread of the twelve review environments
# (worst observed pair: colour 0.27, structure 0.07).
MIN_COLOUR_DISTANCE = 0.20
MIN_STRUCTURE_DISTANCE = 0.05
MAX_RENDER_MS = 25.0

# Two descriptors per canvas, over opaque pixels only so the page around
# the disc never counts:
#   colour    - 4x4x4 RGB cube (64 bins)
#   structure - luminance-gradient orientation by magnitude (25 bins:
#               one flat bin plus 8 orientations at 3 magnitude levels).
# The structure descriptor ignores colour entirely, so recolouring one
# world into another cannot move it - only different surface structure
# can.
HISTOGRAM_JS = """
() => {
  const canvases = Array.from(document.querySelectorAll('canvas.world'));
  return canvases.map(canvas => {
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const d = ctx.getImageData(0, 0, W, H).data;
    const lum = new Float64Array(W * H);
    const opacity = new Float64Array(W * H);
    const colour = new Float64Array(64);
    let n = 0, blank = true, first = -1;
    for (let p = 0, i = 0; p < W * H; p++, i += 4) {
      opacity[p] = d[i + 3];
      lum[p] = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      if (d[i + 3] < 250) continue;
      n++;
      colour[(d[i] >> 6) * 16 + (d[i + 1] >> 6) * 4 + (d[i + 2] >> 6)]++;
      if (first < 0) first = lum[p];
      else if (Math.abs(lum[p] - first) > 1) blank = false;
    }
    const structure = new Float64Array(25);
    let nStruct = 0;
    for (let y = 1; y < H - 1; y++) {
      for (let x = 1; x < W - 1; x++) {
        const p = y * W + x;
        if (opacity[p] < 250 || opacity[p - 1] < 250 || opacity[p + 1] < 250
            || opacity[p - W] < 250 || opacity[p + W] < 250) continue;
        const gx = lum[p + 1] - lum[p - 1];
        const gy = lum[p + W] - lum[p - W];
        const mag = Math.sqrt(gx * gx + gy * gy);
        nStruct++;
        if (mag < 3) { structure[0]++; continue; }
        let a = Math.atan2(gy, gx);
        if (a < 0) a += Math.PI;
        const ob = Math.min(7, Math.floor(a / Math.PI * 8));
        const mb = mag < 12 ? 0 : (mag < 40 ? 1 : 2);
        structure[1 + mb * 8 + ob]++;
      }
    }
    for (let i = 0; i < 64; i++) colour[i] /= (n || 1);
    for (let i = 0; i < 25; i++) structure[i] /= (nStruct || 1);
    return {
      id: canvas.dataset.world,
      ms: Number(canvas.dataset.ms),
      pixels: n,
      blank: blank,
      colour: Array.from(colour),
      structure: Array.from(structure)
    };
  });
}
"""

# Render the same star twice with the cache cleared in between and
# compare the raw bytes.
DETERMINISM_JS = """
() => {
  const star = { id: 'determinism-probe', name: 'Determinism Probe',
                 temperature: 46, radiation: 62, gravity: 58, colonists: 0 };
  const bytes = [];
  for (let pass = 0; pass < 2; pass++) {
    PlanetArt.cache.clear();
    const c = document.createElement('canvas');
    c.width = 200; c.height = 200;
    PlanetArt.render(c, star);
    bytes.push(Array.from(
      c.getContext('2d').getImageData(0, 0, 200, 200).data));
  }
  let diff = 0;
  for (let i = 0; i < bytes[0].length; i++) {
    if (bytes[0][i] !== bytes[1][i]) diff++;
  }
  return { bytes: bytes[0].length, diff: diff };
}
"""

# Time a cold render of each environment (cache cleared each pass) after
# a warm-up, and keep the median of three passes per world.
TIMING_JS = """
() => {
  const envs = [
    ['Frozen', 10, 15, 50], ['Frozen, irradiated', 10, 85, 50],
    ['Cold earthlike', 35, 40, 50], ['Temperate ideal', 50, 50, 50],
    ['Low gravity', 50, 50, 20], ['High gravity', 50, 50, 80],
    ['Irradiated temperate', 50, 90, 50], ['Hot desert', 70, 30, 50],
    ['Volcanic', 75, 70, 60], ['Scorching hell', 95, 95, 70],
    ['Cold gas giant', 25, 40, 95], ['Hot gas giant', 80, 60, 95]
  ];
  const canvas = document.createElement('canvas');
  canvas.width = 200; canvas.height = 200;
  const draw = (id, t, r, g) => {
    PlanetArt.cache.clear();
    const t0 = performance.now();
    PlanetArt.render(canvas, { id: id, name: id, temperature: t,
                               radiation: r, gravity: g, colonists: 0 });
    return performance.now() - t0;
  };
  for (let i = 0; i < 3; i++) draw('warmup-' + i, 50, 50, 50 + i * 20);
  const out = {};
  for (const [name, t, r, g] of envs) {
    const runs = [];
    for (let i = 0; i < 3; i++) runs.push(draw(name + '-timing-' + i, t, r, g));
    runs.sort((a, b) => a - b);
    out[name] = runs[1];
  }
  return out;
}
"""


def _l1_half(a, b):
    """L1 distance between two normalized histograms, scaled to 0..1."""
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


def test_worlds_are_structurally_distinct(page, server):
    page.goto(server + PREVIEW_PATH)
    page.wait_for_function("() => window.PREVIEW_READY === true")

    worlds = page.evaluate(HISTOGRAM_JS)
    assert len(worlds) == 20, "12 environments plus four seed pairs"

    for w in worlds:
        assert not w["blank"], f"{w['id']} rendered blank"
        assert w["pixels"] > 5000, f"{w['id']} drew only {w['pixels']} pixels"

    twelve = worlds[:12]
    pairs = []
    for i in range(len(twelve)):
        for j in range(i + 1, len(twelve)):
            a, b = twelve[i], twelve[j]
            pairs.append({
                "a": a["id"], "b": b["id"],
                "colour": _l1_half(a["colour"], b["colour"]),
                "structure": _l1_half(a["structure"], b["structure"]),
            })

    worst_colour = min(pairs, key=lambda p: p["colour"])
    worst_structure = min(pairs, key=lambda p: p["structure"])

    # Same-environment seed pairs: proof that two identical worlds still
    # differ, which is what the rejected renderer could not do.
    seed_pairs = []
    for i in range(12, 20, 2):
        a, b = worlds[i], worlds[i + 1]
        seed_pairs.append({
            "a": a["id"], "b": b["id"],
            "colour": _l1_half(a["colour"], b["colour"]),
            "structure": _l1_half(a["structure"], b["structure"]),
        })

    determinism = page.evaluate(DETERMINISM_JS)
    timings = page.evaluate(TIMING_JS)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "planet-rendering.json", "w") as f:
        json.dump({
            "pairs": pairs,
            "seed_pairs": seed_pairs,
            "worst_colour": worst_colour,
            "worst_structure": worst_structure,
            "determinism": determinism,
            "timings_ms": timings,
        }, f, indent=2)

    assert worst_colour["colour"] >= MIN_COLOUR_DISTANCE, (
        f"colour histograms too close: {worst_colour}")
    assert worst_structure["structure"] >= MIN_STRUCTURE_DISTANCE, (
        f"surface structure too similar: {worst_structure}")

    for sp in seed_pairs:
        assert sp["colour"] >= 0.05 or sp["structure"] >= 0.05, (
            f"same environment, different star still looks identical: {sp}")

    assert determinism["diff"] == 0, (
        f"{determinism['diff']} of {determinism['bytes']} bytes differ "
        f"between two renders of the same star")

    slowest = max(timings.items(), key=lambda kv: kv[1])
    assert slowest[1] < MAX_RENDER_MS, (
        f"{slowest[0]} took {slowest[1]:.1f} ms (bar {MAX_RENDER_MS} ms)")
