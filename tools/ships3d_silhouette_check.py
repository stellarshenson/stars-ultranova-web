"""Silhouette distance check over the full hull roster.

Inputs:  walkthrough/review/renders3d/sil-<hull>.png (256 black-on-white
         silhouettes produced by tools/ships3d_sil.html via ships3d_server.py)
Output:  pairwise IoU of the binary masks, highest first - flags any pair
         above the confusion threshold. Same-role size-ladder neighbours
         (both hulls in one family) are reported but not counted as failures;
         cross-family or cross-class twins are.

Run: python tools/ships3d_silhouette_check.py [threshold=0.85]
Exit 1 if any cross-family pair meets the threshold.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"

FAMILY = {
    "scout": "scout", "probe": "probe",
    "frigate": "warship", "destroyer": "warship", "cruiser": "warship",
    "battle-cruiser": "warship", "battleship": "warship", "dreadnought": "warship",
    "privateer": "raider", "rogue": "raider",
    "small-freighter": "freighter", "medium-freighter": "freighter",
    "large-freighter": "freighter", "super-freighter": "freighter", "galleon": "freighter",
    "fuel-transport": "tanker", "super-fuel-transport": "tanker",
    "midget-miner": "miner", "mini-miner": "miner", "miner": "miner",
    "maxi-miner": "miner", "ultra-miner": "miner",
    "mini-bomber": "bomber", "b17-bomber": "bomber", "b52-bomber": "bomber",
    "stealth-bomber": "stealth",
    "mini-colony-ship": "colony", "colony-ship": "colony",
    "mini-mine-layer": "minelayer", "super-mine-layer": "minelayer",
    "nubian": "modular", "meta-morph": "modular",
    "assault-transport": "assault",
}


def main():
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else 0.85
    hulls = sorted(FAMILY)
    masks = {}
    for h in hulls:
        path = RENDERS / f"sil-{h}.png"
        if not path.exists():
            print(f"missing {path} - run tools/ships3d_sil.html first")
            return 2
        masks[h] = np.asarray(Image.open(path).convert("L")) < 128
    pairs = []
    for i, a in enumerate(hulls):
        for b in hulls[i + 1:]:
            iou = (masks[a] & masks[b]).sum() / (masks[a] | masks[b]).sum()
            pairs.append((float(iou), a, b))
    pairs.sort(reverse=True)
    failures = 0
    for iou, a, b in pairs[:20]:
        same = FAMILY[a] == FAMILY[b]
        tag = "ladder" if same else ("FAIL" if iou >= threshold else "ok")
        if tag == "FAIL":
            failures += 1
        print(f"{iou:.3f}  {tag:6s} {a:22s} {b}")
    print(f"\n{failures} cross-family pair(s) at or above IoU {threshold}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
