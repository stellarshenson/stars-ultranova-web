"""Assemble the class-identity review sheet: one row per family, each row
showing every member hull beside the family's defining feature.

Inputs:  walkthrough/review/renders3d/<hull>.png (1024 beauty renders)
Output:  walkthrough/review/ships3d-class-identity.png

Run: python tools/ships3d_class_identity_montage.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"
OUT = ROOT / "walkthrough" / "review" / "ships3d-class-identity.png"

ROWS = [
    ("warship - one prow language Frigate to Dreadnought: the W40k underbite "
     "blade scaled to class, broadside gun decks on the capitals",
     ["frigate", "destroyer", "cruiser", "battle-cruiser", "battleship", "dreadnought"]),
    ("raider - Privateer: fat stubby rust trader. Rogue: dark lean smuggler, "
     "twin outboard drive nacelles",
     ["privateer", "rogue"]),
    ("freighter - container-spine ladder; Galleon is the armed merchantman: "
     "wide flat single deck under a dorsal turret line",
     ["small-freighter", "medium-freighter", "large-freighter", "super-freighter", "galleon"]),
    ("tanker - sphere tank row on an open keel truss",
     ["fuel-transport", "super-fuel-transport"]),
    ("miner - purpose-built tools: bucket-wheel boom, ore intake maw, conveyor "
     "spine, hoppers and floodmasts, one language up the ladder",
     ["midget-miner", "mini-miner", "miner", "maxi-miner", "ultra-miner"]),
    ("bomber - ordnance frame: fat bombs and torpedoes hung in visible rows; "
     "the stealth hull carries its load in ventral bays",
     ["mini-bomber", "b17-bomber", "b52-bomber", "stealth-bomber"]),
    ("colony - the fattest hulls in the fleet: swollen pressurised drums, "
     "habitat dome crown, greenhouse glazing",
     ["mini-colony-ship", "colony-ship"]),
    ("minelayer - dispenser drums aft of an open mine-rack deck",
     ["mini-mine-layer", "super-mine-layer"]),
    ("scout and probe - crewed recon dart with canopy vs windowless unmanned "
     "instrument bus with dishes and whisker booms",
     ["scout", "probe"]),
    ("modular - Nubian socketed module frame; Meta Morph radial arms",
     ["nubian", "meta-morph"]),
    ("assault - armoured landing wedge with drop pods",
     ["assault-transport"]),
]

BG = (5, 7, 12)
FG = (207, 214, 223)
DIM = (130, 143, 163)


def font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", size)
    except OSError:
        return ImageFont.load_default()


def main():
    tile, header_h, row_head, label_h = 512, 110, 56, 40
    cols = max(len(hulls) for _, hulls in ROWS)
    W = cols * tile
    row_h = row_head + tile + label_h
    H = header_h + len(ROWS) * row_h

    sheet = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(sheet)
    f_head = font(52)
    f_row = font(30)
    f_label = font(26)

    draw.text((32, 28), "stars-ultranova ships3d - class identity: one row per family, "
              "the defining feature named", font=f_head, fill=FG)

    for r, (caption, hulls) in enumerate(ROWS):
        y = header_h + r * row_h
        draw.text((32, y + 14), caption, font=f_row, fill=FG)
        for c, hull in enumerate(hulls):
            img = Image.open(RENDERS / f"{hull}.png").convert("RGB").resize((tile, tile), Image.LANCZOS)
            x = c * tile
            sheet.paste(img, (x, y + row_head))
            draw.text((x + 14, y + row_head + tile + 6), hull, font=f_label, fill=DIM)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB, {W}x{H})")


if __name__ == "__main__":
    main()
