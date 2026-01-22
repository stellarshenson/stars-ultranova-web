# Stars Nova Web

A web-based implementation of the Stars! strategy game, ported directly from the C# codebase in `stars-nova-orig-c#`.

## Project Goals

- Direct port of Stars! game mechanics and logic from the original C# implementation
- Python-based backend with uvicorn web server
- Web UI preserving the original visual style, themes, and imagery
- Full feature parity with the source

## Technology Stack

- Python 3.11+
- FastAPI + uvicorn
- HTML/CSS/JavaScript frontend (original Stars! aesthetic)

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Run development server
uv run uvicorn backend.main:app --reload

# Run tests
uv run pytest
```

### Development dependencies

```bash
# Install with dev dependencies
uv sync --all-extras

# Install playwright browsers for screenshot tests
uv run playwright install chromium
```

## Source

This project uses [Stars! Nova](https://github.com/stars-nova/stars-nova) as the reference implementation. All game rules, calculations, and behaviours are derived from that codebase.
