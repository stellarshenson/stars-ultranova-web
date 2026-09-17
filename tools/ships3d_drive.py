"""Drive the ships3d compile/render pages in headless Chrome.

Usage: python tools/ships3d_drive.py compile [ship|all]
       python tools/ships3d_drive.py render [detail]
       python tools/ships3d_drive.py flavour [ship|all]
Waits for window.COMPILE_DONE / window.RENDER_DONE and prints the JSON.
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:9911"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "compile"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if mode == "compile":
        url = f"{BASE}/tools/ships3d_compile.html?ship={arg or 'all'}"
        flag = "COMPILE_DONE"
        timeout_ms = 40 * 60 * 1000
    elif mode == "flavour":
        url = f"{BASE}/tools/ships3d_flavour.html?ship={arg or 'all'}"
        flag = "RENDER_DONE"
        timeout_ms = 40 * 60 * 1000
    else:
        url = f"{BASE}/tools/ships3d_render.html" + ("?detail=1" if arg == "detail" else "")
        flag = "RENDER_DONE"
        timeout_ms = 30 * 60 * 1000

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome", headless=True,
            args=["--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        )
        page = browser.new_page(viewport={"width": 2200, "height": 2200})
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_function(f"window.{flag} !== null", timeout=timeout_ms)
        result = page.evaluate(f"window.{flag}")
        browser.close()
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
