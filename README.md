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
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn src.main:app --reload
```

## Source

This project uses [Stars! Nova](https://github.com/stars-nova/stars-nova) as the reference implementation. All game rules, calculations, and behaviours are derived from that codebase.
