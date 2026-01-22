/**
 * Stars Nova Web - Nebula Designer
 * Creates procedural nebulae with consistent cosmic coloring.
 * Uses unified blue-purple palette with wispy, elongated structures.
 */

const NebulaDesigner = {
    // Single unified cosmic palette - purple/blue tones
    baseColor: { r: 100, g: 60, b: 140 },  // Deep purple base

    // Color variations (all in same family)
    variations: [
        { r: 90, g: 50, b: 130 },   // Deeper purple
        { r: 110, g: 70, b: 150 },  // Lighter purple
        { r: 80, g: 60, b: 160 },   // Blue-purple
        { r: 120, g: 80, b: 140 },  // Pink-purple
    ],

    /**
     * Seeded random number generator.
     */
    seededRandom(seed) {
        const x = Math.sin(seed) * 10000;
        return x - Math.floor(x);
    },

    /**
     * Generate nebulae based on star distribution.
     */
    generate(stars, universeWidth, universeHeight, seed = 0) {
        const nebulae = [];

        // Analyze star distribution
        const starMap = this.analyzeStarDistribution(stars, universeWidth, universeHeight);

        // Generate wispy nebula structures
        this.addWispyNebulae(nebulae, starMap, seed);
        this.addFilaments(nebulae, starMap, seed + 1000);
        this.addDustLanes(nebulae, starMap, seed + 2000);

        return nebulae;
    },

    /**
     * Analyze star distribution to find clusters and voids.
     */
    analyzeStarDistribution(stars, width, height) {
        const cellSize = 80;
        const cols = Math.ceil(width / cellSize);
        const rows = Math.ceil(height / cellSize);
        const grid = [];

        for (let y = 0; y < rows; y++) {
            grid[y] = [];
            for (let x = 0; x < cols; x++) {
                grid[y][x] = { count: 0, stars: [] };
            }
        }

        for (const star of stars) {
            const cx = Math.floor(star.position_x / cellSize);
            const cy = Math.floor(star.position_y / cellSize);
            if (cx >= 0 && cx < cols && cy >= 0 && cy < rows) {
                grid[cy][cx].count++;
                grid[cy][cx].stars.push(star);
            }
        }

        // Find cluster centers
        const clusters = [];
        for (let y = 1; y < rows - 1; y++) {
            for (let x = 1; x < cols - 1; x++) {
                const density = this.getNeighborhoodDensity(grid, x, y, cols, rows);
                if (density > 4) {
                    clusters.push({
                        x: (x + 0.5) * cellSize,
                        y: (y + 0.5) * cellSize,
                        density
                    });
                }
            }
        }

        // Find voids
        const voids = [];
        for (let y = 1; y < rows - 1; y++) {
            for (let x = 1; x < cols - 1; x++) {
                const density = this.getNeighborhoodDensity(grid, x, y, cols, rows);
                if (density === 0) {
                    voids.push({
                        x: (x + 0.5) * cellSize,
                        y: (y + 0.5) * cellSize
                    });
                }
            }
        }

        // Galaxy center of mass
        let centerX = 0, centerY = 0;
        for (const star of stars) {
            centerX += star.position_x;
            centerY += star.position_y;
        }
        centerX /= stars.length || 1;
        centerY /= stars.length || 1;

        return { grid, cellSize, cols, rows, clusters, voids, center: { x: centerX, y: centerY }, width, height };
    },

    getNeighborhoodDensity(grid, x, y, cols, rows) {
        let density = 0;
        for (let dy = -1; dy <= 1; dy++) {
            for (let dx = -1; dx <= 1; dx++) {
                const nx = x + dx;
                const ny = y + dy;
                if (nx >= 0 && nx < cols && ny >= 0 && ny < rows) {
                    density += grid[ny][nx].count;
                }
            }
        }
        return density;
    },

    /**
     * Get a color from the unified palette.
     */
    getColor(seed) {
        const variation = this.variations[Math.floor(this.seededRandom(seed * 7) * this.variations.length)];
        // Small random adjustment
        const adjust = 15;
        return {
            r: variation.r + Math.floor(this.seededRandom(seed * 11) * adjust - adjust / 2),
            g: variation.g + Math.floor(this.seededRandom(seed * 13) * adjust - adjust / 2),
            b: variation.b + Math.floor(this.seededRandom(seed * 17) * adjust - adjust / 2)
        };
    },

    /**
     * Add main wispy nebula clouds near clusters.
     */
    addWispyNebulae(nebulae, starMap, seed) {
        const count = 4 + Math.floor(this.seededRandom(seed) * 4);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;
            let x, y;

            if (i < starMap.clusters.length) {
                const cluster = starMap.clusters[i];
                const angle = this.seededRandom(s * 11) * Math.PI * 2;
                const dist = 20 + this.seededRandom(s * 13) * 60;
                x = cluster.x + Math.cos(angle) * dist;
                y = cluster.y + Math.sin(angle) * dist;
            } else {
                x = starMap.center.x + (this.seededRandom(s * 15) - 0.5) * starMap.width * 0.6;
                y = starMap.center.y + (this.seededRandom(s * 17) - 0.5) * starMap.height * 0.6;
            }

            // Create wispy cloud with elongated particles
            this.addWispyCloud(nebulae, x, y, s);
        }
    },

    /**
     * Add wispy cloud structure - elongated particles radiating outward.
     */
    addWispyCloud(nebulae, centerX, centerY, seed) {
        const baseRadius = 60 + this.seededRandom(seed * 19) * 80;
        const mainAngle = this.seededRandom(seed * 21) * Math.PI;  // Orientation
        const particleCount = 15 + Math.floor(this.seededRandom(seed * 23) * 15);

        for (let j = 0; j < particleCount; j++) {
            const ps = seed * 1000 + j;

            // Elongate along main angle
            const angleOffset = (this.seededRandom(ps * 29) - 0.5) * 1.2;
            const angle = mainAngle + angleOffset;
            const dist = this.seededRandom(ps * 31) * baseRadius;

            // Elongated particle - stretch along radial direction
            const stretchFactor = 1.5 + this.seededRandom(ps * 37) * 2.0;
            const width = 15 + this.seededRandom(ps * 41) * 25;
            const height = width * stretchFactor;

            const distFactor = 1 - Math.min(1, dist / baseRadius);

            nebulae.push({
                x: centerX + Math.cos(angle) * dist,
                y: centerY + Math.sin(angle) * dist,
                width: width,
                height: height,
                rotation: angle,
                color: this.getColor(ps),
                opacity: 0.08 + distFactor * 0.06,
                type: 'wispy'
            });
        }

        // Brighter core
        for (let k = 0; k < 3; k++) {
            const cs = seed * 10000 + k;
            nebulae.push({
                x: centerX + (this.seededRandom(cs * 43) - 0.5) * 20,
                y: centerY + (this.seededRandom(cs * 47) - 0.5) * 20,
                width: 25 + this.seededRandom(cs * 51) * 15,
                height: 25 + this.seededRandom(cs * 53) * 15,
                rotation: this.seededRandom(cs * 57) * Math.PI,
                color: this.getColor(cs),
                opacity: 0.12,
                type: 'core'
            });
        }
    },

    /**
     * Add long filamentary structures connecting regions.
     */
    addFilaments(nebulae, starMap, seed) {
        const count = 3 + Math.floor(this.seededRandom(seed) * 3);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;

            // Start and end points
            const startX = starMap.center.x + (this.seededRandom(s * 11) - 0.5) * starMap.width * 0.7;
            const startY = starMap.center.y + (this.seededRandom(s * 13) - 0.5) * starMap.height * 0.7;
            const endX = starMap.center.x + (this.seededRandom(s * 15) - 0.5) * starMap.width * 0.7;
            const endY = starMap.center.y + (this.seededRandom(s * 17) - 0.5) * starMap.height * 0.7;

            const dx = endX - startX;
            const dy = endY - startY;
            const length = Math.sqrt(dx * dx + dy * dy);
            const angle = Math.atan2(dy, dx);

            // Place elongated particles along filament
            const segments = Math.floor(length / 30);
            for (let j = 0; j < segments; j++) {
                const t = j / segments;
                const ps = s * 1000 + j;

                // Curved path with some noise
                const noise = (this.seededRandom(ps * 19) - 0.5) * 30;
                const perpAngle = angle + Math.PI / 2;

                const x = startX + dx * t + Math.cos(perpAngle) * noise;
                const y = startY + dy * t + Math.sin(perpAngle) * noise;

                nebulae.push({
                    x: x,
                    y: y,
                    width: 8 + this.seededRandom(ps * 23) * 12,
                    height: 25 + this.seededRandom(ps * 29) * 35,
                    rotation: angle + (this.seededRandom(ps * 31) - 0.5) * 0.4,
                    color: this.getColor(ps),
                    opacity: 0.05 + this.seededRandom(ps * 37) * 0.04,
                    type: 'filament'
                });
            }
        }
    },

    /**
     * Add subtle dust lanes in void areas.
     */
    addDustLanes(nebulae, starMap, seed) {
        const count = 2 + Math.floor(this.seededRandom(seed) * 2);

        for (let i = 0; i < count && i < starMap.voids.length; i++) {
            const s = seed * 100 + i;
            const void_ = starMap.voids[Math.floor(this.seededRandom(s) * starMap.voids.length)];

            // Dark dust color
            const dustColor = { r: 30, g: 20, b: 45 };

            const dustCount = 8 + Math.floor(this.seededRandom(s * 11) * 8);
            const mainAngle = this.seededRandom(s * 13) * Math.PI;

            for (let j = 0; j < dustCount; j++) {
                const ps = s * 1000 + j;
                const angle = mainAngle + (this.seededRandom(ps * 17) - 0.5) * 0.6;
                const dist = this.seededRandom(ps * 19) * 60;

                nebulae.push({
                    x: void_.x + Math.cos(angle) * dist,
                    y: void_.y + Math.sin(angle) * dist,
                    width: 20 + this.seededRandom(ps * 23) * 30,
                    height: 40 + this.seededRandom(ps * 29) * 50,
                    rotation: angle,
                    color: dustColor,
                    opacity: 0.1 + this.seededRandom(ps * 31) * 0.08,
                    type: 'dust'
                });
            }
        }
    }
};

window.NebulaDesigner = NebulaDesigner;
