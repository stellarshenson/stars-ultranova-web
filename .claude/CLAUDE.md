<!-- @import /home/lab/workspace/.claude/CLAUDE.md -->

# Project-Specific Configuration

This file imports workspace-level configuration from `/home/lab/workspace/.claude/CLAUDE.md`.
All workspace rules apply. Project-specific rules below strengthen or extend them.

The workspace `/home/lab/workspace/.claude/` directory contains additional instruction files
(MERMAID.md, NOTEBOOK.md, DATASCIENCE.md, GIT.md, and others) referenced by CLAUDE.md.
Consult workspace CLAUDE.md and the .claude directory to discover all applicable standards.

## Mandatory Bans (Reinforced)

The following workspace rules are STRICTLY ENFORCED for this project:

- **No automatic git tags** - only create tags when user explicitly requests
- **No automatic version changes** - only modify version in package.json/pyproject.toml/etc. when user explicitly requests
- **No automatic publishing** - never run `make publish`, `npm publish`, `twine upload`, or similar without explicit user request
- **No manual package installs if Makefile exists** - use `make install` or equivalent Makefile targets, not direct `pip install`/`uv install`/`npm install`
- **No automatic git commits or pushes** - only when user explicitly requests

## Project Context

Stars Nova Web - a direct port of the Stars! 4X strategy game from C# to a Python web application.

**Technology Stack**:
- Python 3.11+
- FastAPI framework
- uvicorn ASGI server
- HTML/CSS/JavaScript frontend (preserving original Stars! aesthetic)
- Original Stars! Nova C# codebase as reference (`stars-nova-orig-c#/`)

**Reference Implementation**:
- All game logic, rules, and calculations must match the C# source in `stars-nova-orig-c#/`
- Visual style, themes, and imagery preserved from original
- Feature parity is mandatory - no omissions or simplifications

**Key Directories**:
- `stars-nova-orig-c#/` - Original C# source (reference only, gitignored)
- `src/` - Python backend source
- `static/` - Frontend assets (HTML, CSS, JS, images)
- `tests/` - Test suite

## Strengthened Rules

**Code Porting**:
- When porting C# code, preserve original logic exactly - do not "improve" or "modernize" algorithms
- Document the original C# file and line numbers in comments when porting complex logic
- Maintain original variable/function naming conventions where practical for traceability
