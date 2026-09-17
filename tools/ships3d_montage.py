"""Assemble the ships3d review sheet from the batch renders.

Inputs:  walkthrough/review/renders3d/<hull>.png          (1024 beauty renders)
         walkthrough/review/renders3d/detail-<hull>.png   (2048 detail shots)
         walkthrough/review/renders3d/detail1k-<hull>.png (1024 bow-quarter row)
Output:  walkthrough/review/ships3d-photoreal.png

Layout: 6-column grid of all hulls at 1024 with name/triangle labels, then
the 2048 detail shots of the five directive hulls in 3-wide rows, then the
frigate/destroyer/cruiser bow-quarter row at 1024 (family blade check).

Run: python tools/ships3d_montage.py
"""

import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"
OUT = ROOT / "walkthrough" / "review" / "ships3d-photoreal.png"
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
DETAIL = ["dreadnought", "battleship", "battle-cruiser", "nubian", "ultra-miner"]
LIGHT_DETAIL = ["frigate", "destroyer", "cruiser"]

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
    cols, tile, label_h = 6, 1024, 64
    rows = (len(HULLS) + cols - 1) // cols
    header_h = 120
    grid_h = rows * (tile + label_h)
    dcols, dtile, dlabel_h = 3, 2048, 80
    drows = (len(DETAIL) + dcols - 1) // dcols
    detail_header_h = 110
    detail_h = detail_header_h + drows * (dtile + dlabel_h)
    ltile, llabel_h = 1024, 64
    light_header_h = 110
    light_h = light_header_h + ltile + llabel_h
    W = cols * tile
    H = header_h + grid_h + detail_h + light_h

    sheet = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(sheet)
    f_head = font(56)
    f_label = font(34)
    f_sub = font(26)

    draw.text((32, 30), "stars-ultranova ships3d - full 33-hull roster, compiled glb renders at 1024",
              font=f_head, fill=FG)

    for i, hull in enumerate(HULLS):
        cx, cy = i % cols, i // cols
        x, y = cx * tile, header_h + cy * (tile + label_h)
        img = Image.open(RENDERS / f"{hull}.png").convert("RGB")
        sheet.paste(img, (x, y))
        tris, size = glb_stats(hull)
        draw.text((x + 20, y + tile + 8), hull, font=f_label, fill=FG)
        draw.text((x + 440, y + tile + 14), f"{tris:,} tris  {size / 1e6:.2f} MB", font=f_sub, fill=DIM)

    dy0 = header_h + grid_h
    draw.text((32, dy0 + 28), "detail shots at 2048 - dreadnought, battleship, battle cruiser, nubian, ultra miner",
              font=f_head, fill=FG)
    for i, hull in enumerate(DETAIL):
        cx, cy = i % dcols, i // dcols
        x = cx * dtile
        y = dy0 + detail_header_h + cy * (dtile + dlabel_h)
        img = Image.open(RENDERS / f"detail-{hull}.png").convert("RGB")
        sheet.paste(img, (x, y))
        tris, size = glb_stats(hull)
        draw.text((x + 24, y + dtile + 12), f"{hull}  -  {tris:,} tris  {size / 1e6:.2f} MB",
                  font=f_label, fill=FG)

    ly0 = dy0 + detail_h
    draw.text((32, ly0 + 28), "light warship blades at 1024, bow quarter - frigate, destroyer, cruiser",
              font=f_head, fill=FG)
    for i, hull in enumerate(LIGHT_DETAIL):
        x = i * ltile
        y = ly0 + light_header_h
        img = Image.open(RENDERS / f"detail1k-{hull}.png").convert("RGB")
        sheet.paste(img, (x, y))
        tris, size = glb_stats(hull)
        draw.text((x + 24, y + ltile + 10), f"{hull}  -  {tris:,} tris  {size / 1e6:.2f} MB",
                  font=f_label, fill=FG)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {W}x{H})")


if __name__ == "__main__":
    main()
