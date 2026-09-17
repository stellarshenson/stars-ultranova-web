"""Assemble the incarnations sheet: every hull at flavour 0.0 / 0.5 / 1.0.

Inputs:  walkthrough/review/renders3d/flavour-<hull>-XX.png  (384 renders,
         XX in 00/05/10, produced by tools/ships3d_flavour.html)
Output:  walkthrough/review/ships3d-incarnations.png

Layout: two hulls per row, each as a triple of flavour tiles, name label
under the left tile and a 0.0 / 0.5 / 1.0 legend under the right edge.

Run: python tools/ships3d_incarnations_montage.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"
OUT = ROOT / "walkthrough" / "review" / "ships3d-incarnations.png"

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


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    tile, label_h, header_h, per_row = 384, 44, 110, 2
    cols = per_row * 3
    rows = (len(HULLS) + per_row - 1) // per_row
    W = cols * tile + 72
    H = header_h + rows * (tile + label_h)
    sheet = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(sheet)
    f_head = font(44)
    f_label = font(26)

    draw.text((24, 30), "ships3d incarnations - every hull at flavour 0.0 / 0.5 / 1.0 (same record, alien knob turned)",
              font=f_head, fill=FG)

    for i, hull in enumerate(HULLS):
        bx, by = i % per_row, i // per_row
        x0 = bx * (3 * tile + 36)
        y0 = header_h + by * (tile + label_h)
        for j, t in enumerate(("00", "05", "10")):
            img = Image.open(RENDERS / f"flavour-{hull}-{t}.png").convert("RGB")
            if img.size != (tile, tile):
                img = img.resize((tile, tile), Image.LANCZOS)
            sheet.paste(img, (x0 + j * tile, y0))
        draw.text((x0 + 8, y0 + tile + 8), hull, font=f_label, fill=FG)
        draw.text((x0 + 3 * tile - 220, y0 + tile + 8), "0.0 / 0.5 / 1.0", font=f_label, fill=DIM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {W}x{H})")


if __name__ == "__main__":
    main()
