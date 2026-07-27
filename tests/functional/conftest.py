"""
Functional browser-test harness (Playwright, headless Chrome).

Distinct from the in-process unit/e2e suite: these tests drive the REAL
served frontend in a real browser against a dedicated uvicorn instance.

- Opt-in: the whole directory is skipped unless RUN_FUNCTIONAL=1, so
  the default "uv run pytest tests/" stays fast and green.
- Isolated server: a session-scoped fixture boots uvicorn on port 9820
  with its working directory set to a pytest temp dir (backend/ and
  frontend/ symlinked in), so the SQLite database (stars_nova.db,
  created relative to the CWD by GameManager) lands in the temp dir
  and the repo's data is never touched. The live dev server on 9800
  is left alone.
- Console forensics: every page collects browser console messages and
  pageerror events; severe entries (console.error / pageerror) FAIL
  the test, and every collected message is written to
  logs/functional/<test-name>-console.log.

Run via scripts/run_functional.sh.
"""

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FUNCTIONAL_DIR = Path(__file__).resolve().parent
PORT = 9820
BASE_URL = f"http://127.0.0.1:{PORT}"
LOG_DIR = REPO_ROOT / "logs" / "functional"

RUN_FUNCTIONAL = os.environ.get("RUN_FUNCTIONAL") == "1"


def pytest_collection_modifyitems(config, items):
    """Skip every test in this directory unless RUN_FUNCTIONAL=1."""
    if RUN_FUNCTIONAL:
        return
    skip = pytest.mark.skip(
        reason="functional browser harness is opt-in (set RUN_FUNCTIONAL=1)")
    for item in items:
        if str(item.fspath).startswith(str(FUNCTIONAL_DIR)):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    """Boot a dedicated uvicorn instance with an isolated database.

    The server's CWD is a temp dir with backend/ and frontend/
    symlinked from the repo, so relative paths inside the app
    (backend/data/components.xml, the SQLite db) resolve there.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    workdir = tmp_path_factory.mktemp("functional_server")
    (workdir / "backend").symlink_to(REPO_ROOT / "backend")
    (workdir / "frontend").symlink_to(REPO_ROOT / "frontend")

    log_file = open(LOG_DIR / "server.log", "w")
    proc = subprocess.Popen(
        [str(REPO_ROOT / ".venv" / "bin" / "python"), "-m", "uvicorn",
         "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=str(workdir),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_health(proc)
    except Exception:
        proc.terminate()
        proc.wait(timeout=10)
        log_file.close()
        raise

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log_file.close()


def _wait_for_health(proc, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"functional server exited early (code {proc.returncode}), "
                f"see logs/functional/server.log")
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError("functional server did not become healthy in time")


@pytest.fixture(scope="session")
def browser():
    """Headless Chrome (system install at /opt/google/chrome/chrome)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox"],
        )
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server, request):
    """Per-test page collecting console forensics.

    Severe console output (console.error / pageerror) fails the test
    in teardown; all collected messages go to
    logs/functional/<test-name>-console.log.
    """
    context = browser.new_context(
        viewport={"width": 2560, "height": 1440})
    pg = context.new_page()
    pg.set_default_timeout(15000)

    messages = []
    pg.on("console", lambda msg: messages.append(
        (f"console.{msg.type}", msg.text)))
    pg.on("pageerror", lambda err: messages.append(
        ("pageerror", str(err))))

    yield pg

    context.close()

    log_path = LOG_DIR / f"{request.node.name}-console.log"
    with open(log_path, "w") as f:
        for kind, text in messages:
            f.write(f"[{kind}] {text}\n")

    severe = [(kind, text) for kind, text in messages
              if kind in ("console.error", "pageerror")]
    if severe:
        detail = "\n".join(f"[{kind}] {text}" for kind, text in severe)
        pytest.fail(
            f"Severe browser console errors (see {log_path}):\n{detail}",
            pytrace=False)
