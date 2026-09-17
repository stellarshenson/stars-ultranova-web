"""Static server plus save endpoints for the ships3d pipeline.

Serves the repo root (so /frontend/..., /assets/..., /tools/... resolve) and
accepts:
- POST /api/save-ship?name=<hull>    binary glb -> assets/ships/<hull>.glb
- POST /api/save-render?name=<slug>  png bytes  -> walkthrough/review/renders3d/<slug>.png

This is the only machinery needed to let the browser-side compiler write the
canonical asset store and the review renders.

Run: python tools/ships3d_server.py [port]   (default 9911)
"""

import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPS = ROOT / "assets" / "ships"
RENDERS = ROOT / "walkthrough" / "review" / "renders3d"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path.startswith("/api/save-ship"):
            out_dir, ext = SHIPS, "glb"
        elif self.path.startswith("/api/save-render"):
            out_dir, ext = RENDERS, "png"
        else:
            self.send_error(404)
            return
        m = re.search(r"[?&]name=([a-z0-9_\-]+)", self.path)
        if not m:
            self.send_error(400, "missing or invalid name")
            return
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > 200_000_000:
            self.send_error(400, "bad content length")
            return
        body = self.rfile.read(length)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{m.group(1)}.{ext}"
        out.write_bytes(body)
        payload = ('{"ok": true, "bytes": %d, "path": "%s"}' % (len(body), out.relative_to(ROOT))).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9911
    print(f"ships3d server on http://127.0.0.1:{port}/ root={ROOT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
