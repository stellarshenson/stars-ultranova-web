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
- Configuration via `project.env` file

## Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Copy example configuration (if needed)
cp project.env.example project.env

# Run development server (default port: 9800)
make run

# Or use convenience scripts for background server
./start.sh    # Start server in background, logs to server.log
./stop.sh     # Stop background server

# Run tests
make test
```

The server will start on `http://localhost:9800` by default. You can customize settings in `project.env`.

**Server management:**
- `./start.sh` - Start server in background with logging to `server.log`
- `./stop.sh` - Stop the background server gracefully
- `make run` - Run server in foreground (for development)

### Configuration

Edit `project.env` to customize:
- Server port (default: 9800)
- CORS origins
- Database URL
- Game settings (max players, universe sizes)
- Debug mode

### Development dependencies

```bash
# Install with dev dependencies
make dev-install

# This installs pytest, httpx, playwright and browser drivers
```

## Source

This project uses [Stars! Nova](https://github.com/stars-nova/stars-nova) as the reference implementation. All game rules, calculations, and behaviours are derived from that codebase.
