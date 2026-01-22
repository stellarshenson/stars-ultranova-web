# Stars Nova Web Documentation

Technical documentation for the Stars Nova Web game engine.

## Articles

### Galaxy Visualization

- [Star Generation and Rendering](STAR_GENERATION.md) - GMM distribution, spectral classification, canvas rendering
- [Nebula Generation and Rendering](NEBULA_RENDERING.md) - Dual dust/gas model, filament structures, SVG rendering

## Overview

Stars Nova Web is a Python/FastAPI port of the Stars! 4X strategy game. The visualization system aims for astronomical realism while maintaining the classic Stars! aesthetic.

### Key Technologies

| Layer | Technology | Purpose |
|-------|------------|---------|
| Backend | Python/FastAPI | Game logic, generation |
| Persistence | SQLite | Game state storage |
| Frontend | Vanilla JS | No framework dependencies |
| Galaxy Map | HTML5 Canvas | Star and fleet rendering |
| Nebulae | SVG | Scalable cloud rendering |

### Architectural Principles

- **Astronomical accuracy**: Star distribution follows IMF, nebulae model real physics
- **Deterministic generation**: Seeded random for reproducible galaxies
- **Separation of concerns**: Backend generates data, frontend renders visuals
- **Performance**: SVG viewBox sync with canvas avoids re-rendering
