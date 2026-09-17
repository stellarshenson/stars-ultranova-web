"""Assemble the rebuild WIP gallery sheet.

Inputs:  walkthrough/review/renders3d/<hull>.png             (1024 beauty renders, flavour 0)
         walkthrough/review/renders3d/flavour-<hull>-XX.png  (optional 384 flavour incarnations)
Output:  walkthrough/review/ships3d-rebuild-wip.png

Layout: 6-column grid of all 32 hulls at 512 (flavour 0) with name and
triangle labels; if the flavour renders exist, a second section shows every
hull at flavour 0.0 / 0.5 / 1.0 - same record, knob turned.

Run: python tools/ships3d_wip_montage.py
"""

import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"
OUT = ROOT / "walkthrough" / "review" / "ships3d-rebuild-wip.png"
SHIPS = ROOT / "assets" / "ships"

HULLS = [
    "scout", "probe", "frigate", "destroyer", "cruiser", "battle-cruiser", "battleship",
    "dreadnought", "privateer", "rogue", "small-freighter", "medium-freighter",
    "large-freighter", "super-freighter", "galleon", "fuel-transport",
    "super-fuel-transport", "midget-miner", "mini-miner", "miner", "maxi-miner",
    "ultra-miner", "mini-bomber", "b17-bomber", "stealth-bomber", "b52-bomber",
    "mini-colony-ship", "colony-ship", "mini-mine-layer", "super-mine-layer",
    "nubian", "meta-morph", "assault-transport",
]

BG = (5, 7, 12)
FG = (207, 214, 223)
DIM = (110, 123, 143)


def glb_stats(hull):
    buf = (SHIPS / f"{hull}.glb").read_bytes()
    json_len = struct.unpack_from("<I", buf, 12)[0]
    doc = json.loads(buf[20:20 + json_len])
    tris = 0
    for mesh in doc["meshes"]:
        for prim in mesh["primitives"]:
            acc = doc["accessors"][prim["indices"]]
            tris += acc["count"] // 3
    return tris, len(buf)


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    cols, tile, label_h = 6, 512, 36
    rows = (len(HULLS) + cols - 1) // cols
    header_h = 72
    grid_h = rows * (tile + label_h)
    W = cols * tile

    have_flavours = all(
        (RENDERS / f"flavour-{h}-{t}.png").exists()
        for h in HULLS for t in ("00", "05", "10"))
    ftile, fl_label = 256, 30
    fcols = 4  # hull triples per row
    frows = (len(HULLS) + fcols - 1) // fcols
    fheader_h = 72
    flavour_h = (fheader_h + frows * (ftile + fl_label)) if have_flavours else 0

    H = header_h + grid_h + flavour_h
    sheet = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(sheet)
    f_head = font(34)
    f_label = font(20)
    f_sub = font(16)

    draw.text((24, 20), "ships3d rebuild WIP - 32 hulls, compiled glb renders (flavour 0) at 512",
              font=f_head, fill=FG)

    for i, hull in enumerate(HULLS):
        cx, cy = i % cols, i // cols
        x, y = cx * tile, header_h + cy * (tile + label_h)
        img = Image.open(RENDERS / f"{hull}.png").convert("RGB").resize((tile, tile), Image.LANCZOS)
        sheet.paste(img, (x, y))
        tris, size = glb_stats(hull)
        draw.text((x + 10, y + tile + 4), hull, font=f_label, fill=FG)
        draw.text((x + 270, y + tile + 7), f"{tris:,} tris {size / 1e6:.1f} MB", font=f_sub, fill=DIM)

    if have_flavours:
        fy0 = header_h + grid_h
        draw.text((24, fy0 + 20), "flavour knob 0.0 / 0.5 / 1.0 - same record, dial turned",
                  font=f_head, fill=FG)
        for i, hull in enumerate(HULLS):
            bx, by = i % fcols, i // fcols
            x0 = bx * 3 * ftile
            y0 = fy0 + fheader_h + by * (ftile + fl_label)
            for j, t in enumerate(("00", "05", "10")):
                img = Image.open(RENDERS / f"flavour-{hull}-{t}.png").convert("RGB").resize((ftile, ftile), Image.LANCZOS)
                sheet.paste(img, (x0 + j * ftile, y0))
            draw.text((x0 + 8, y0 + ftile + 4), hull, font=f_label, fill=FG)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {W}x{H})")


if __name__ == "__main__":
    main()
