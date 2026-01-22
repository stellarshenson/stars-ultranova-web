/**
 * Stars Nova Web - SVG Nebula Renderer
 *
 * Renders nebulae based on astronomical models:
 * - Emission nebulae (H-II regions): Ionized hydrogen around hot O/B stars, pink/magenta
 * - Reflection nebulae: Dust scattering starlight, blue tint
 * - Dark nebulae: Cold molecular clouds absorbing light
 * - Diffuse nebulae: Large faint structures with complex filamentary patterns
 *
 * Uses multiple overlapping layers with heavy blur for soft, realistic boundaries.
 */

const NebulaSVG = {
    svg: null,
    defs: null,
    nebulaeGroup: null,

    // Astronomical color palettes
    palettes: {
        // H-II emission (hydrogen-alpha pink + oxygen-III teal)
        emission: {
            primary: { r: 180, g: 60, b: 120 },    // H-alpha pink
            secondary: { r: 100, g: 160, b: 180 }, // O-III teal
            highlight: { r: 220, g: 100, b: 160 }  // Bright core
        },
        // Reflection nebulae (blue from Rayleigh scattering)
        reflection: {
            primary: { r: 80, g: 120, b: 200 },
            secondary: { r: 100, g: 140, b: 220 },
            highlight: { r: 150, g: 180, b: 255 }
        },
        // Dark/molecular clouds
        dark: {
            primary: { r: 15, g: 10, b: 25 },
            secondary: { r: 25, g: 15, b: 35 },
            highlight: { r: 10, g: 5, b: 15 }
        },
        // Diffuse interstellar medium (purple/violet)
        diffuse: {
            primary: { r: 70, g: 50, b: 110 },
            secondary: { r: 90, g: 60, b: 130 },
            highlight: { r: 110, g: 80, b: 150 }
        }
    },

    /**
     * Initialize SVG nebula layer.
     */
    init(svgId) {
        this.svg = document.getElementById(svgId);
        if (!this.svg) {
            console.error('Nebula SVG element not found:', svgId);
            return;
        }

        this.svg.innerHTML = '';

        // Create defs for filters
        this.defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        this.svg.appendChild(this.defs);

        // Create advanced blur filters
        this.createFilters();

        // Create group for nebulae
        this.nebulaeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        this.nebulaeGroup.setAttribute('id', 'nebulae');
        this.svg.appendChild(this.nebulaeGroup);

        console.log('NebulaSVG initialized with astronomical models');
    },

    /**
     * Create SVG blur filters with multiple intensities for layered rendering.
     */
    createFilters() {
        // Ultra-soft blur for outer halos
        this.createBlurFilter('blur-ultra', 40);
        // Heavy blur for diffuse regions
        this.createBlurFilter('blur-heavy', 25);
        // Medium blur for main body
        this.createBlurFilter('blur-medium', 15);
        // Soft blur for structure
        this.createBlurFilter('blur-soft', 8);
        // Light blur for detail
        this.createBlurFilter('blur-light', 4);
        // Wispy filter for filaments
        this.createBlurFilter('blur-wispy', 3);

        // Turbulence filter for adding texture
        this.createTurbulenceFilter();

        // Glow filter for bright cores
        this.createGlowFilter();
    },

    createBlurFilter(id, stdDev) {
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', id);
        filter.setAttribute('x', '-100%');
        filter.setAttribute('y', '-100%');
        filter.setAttribute('width', '300%');
        filter.setAttribute('height', '300%');

        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('in', 'SourceGraphic');
        blur.setAttribute('stdDeviation', stdDev);

        filter.appendChild(blur);
        this.defs.appendChild(filter);
    },

    createTurbulenceFilter() {
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', 'turbulence');
        filter.setAttribute('x', '-50%');
        filter.setAttribute('y', '-50%');
        filter.setAttribute('width', '200%');
        filter.setAttribute('height', '200%');

        // Fractal noise
        const turbulence = document.createElementNS('http://www.w3.org/2000/svg', 'feTurbulence');
        turbulence.setAttribute('type', 'fractalNoise');
        turbulence.setAttribute('baseFrequency', '0.02');
        turbulence.setAttribute('numOctaves', '4');
        turbulence.setAttribute('result', 'noise');

        // Displacement map
        const displacement = document.createElementNS('http://www.w3.org/2000/svg', 'feDisplacementMap');
        displacement.setAttribute('in', 'SourceGraphic');
        displacement.setAttribute('in2', 'noise');
        displacement.setAttribute('scale', '20');
        displacement.setAttribute('xChannelSelector', 'R');
        displacement.setAttribute('yChannelSelector', 'G');
        displacement.setAttribute('result', 'displaced');

        // Blur the result
        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('in', 'displaced');
        blur.setAttribute('stdDeviation', '10');

        filter.appendChild(turbulence);
        filter.appendChild(displacement);
        filter.appendChild(blur);
        this.defs.appendChild(filter);
    },

    createGlowFilter() {
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', 'glow');
        filter.setAttribute('x', '-100%');
        filter.setAttribute('y', '-100%');
        filter.setAttribute('width', '300%');
        filter.setAttribute('height', '300%');

        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('stdDeviation', '6');
        blur.setAttribute('result', 'glow');

        const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
        const node1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        node1.setAttribute('in', 'glow');
        const node2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        node2.setAttribute('in', 'glow');
        const node3 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        node3.setAttribute('in', 'SourceGraphic');
        merge.appendChild(node1);
        merge.appendChild(node2);
        merge.appendChild(node3);

        filter.appendChild(blur);
        filter.appendChild(merge);
        this.defs.appendChild(filter);
    },

    /**
     * Seeded random number generator.
     */
    seededRandom(seed) {
        const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
        return x - Math.floor(x);
    },

    /**
     * Generate nebulae from backend data or procedurally.
     */
    generate(stars, universeWidth, universeHeight, seed = 0) {
        if (!this.nebulaeGroup) return;

        this.nebulaeGroup.innerHTML = '';

        // Use backend nebula data if available
        if (GameState.nebulae && GameState.nebulae.regions && GameState.nebulae.regions.length > 0) {
            this.renderFromBackend(GameState.nebulae);
            return;
        }

        // Fallback: procedural generation based on star distribution
        this.generateProcedural(stars, universeWidth, universeHeight, seed);
    },

    /**
     * Render nebulae from backend NebulaField data with astronomical accuracy.
     */
    renderFromBackend(nebulaField) {
        if (!this.nebulaeGroup) return;

        // Sort by size (largest first) for proper layering
        const sortedRegions = [...nebulaField.regions].sort(
            (a, b) => Math.max(b.radius_x, b.radius_y) - Math.max(a.radius_x, a.radius_y)
        );

        for (let i = 0; i < sortedRegions.length; i++) {
            const region = sortedRegions[i];
            this.renderNebulaRegion(region, i);
        }
    },

    /**
     * Render a single nebula region with multiple layers for soft boundaries.
     */
    renderNebulaRegion(region, seed) {
        const palette = this.palettes[region.nebula_type] || this.palettes.diffuse;
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Layer 1: Ultra-soft outer halo (very large, very faint)
        this.addNebulaLayer({
            x: region.x,
            y: region.y,
            radiusX: region.radius_x * 2.0,
            radiusY: region.radius_y * 2.0,
            rotation: region.rotation,
            color: palette.primary,
            opacity: region.density * 0.03,
            filter: 'blur-ultra',
            seed: seed * 1000,
            points: 12
        });

        // Layer 2: Heavy blur outer region
        this.addNebulaLayer({
            x: region.x,
            y: region.y,
            radiusX: region.radius_x * 1.5,
            radiusY: region.radius_y * 1.5,
            rotation: region.rotation,
            color: palette.primary,
            opacity: region.density * 0.06,
            filter: 'blur-heavy',
            seed: seed * 1000 + 100,
            points: 10
        });

        // Layer 3: Medium blur main body
        this.addNebulaLayer({
            x: region.x,
            y: region.y,
            radiusX: region.radius_x * 1.1,
            radiusY: region.radius_y * 1.1,
            rotation: region.rotation,
            color: this.mixColors(palette.primary, palette.secondary, 0.3),
            opacity: region.density * 0.08,
            filter: 'blur-medium',
            seed: seed * 1000 + 200,
            points: 10
        });

        // Layer 4: Inner structure with turbulence
        if (region.nebula_type !== 'dark') {
            this.addNebulaLayer({
                x: region.x,
                y: region.y,
                radiusX: region.radius_x * 0.8,
                radiusY: region.radius_y * 0.8,
                rotation: region.rotation,
                color: palette.secondary,
                opacity: region.density * 0.1,
                filter: 'turbulence',
                seed: seed * 1000 + 300,
                points: 8
            });
        }

        // Layer 5: Bright core for emission nebulae
        if (region.nebula_type === 'emission' && region.density > 0.3) {
            this.addNebulaLayer({
                x: region.x,
                y: region.y,
                radiusX: region.radius_x * 0.4,
                radiusY: region.radius_y * 0.4,
                rotation: region.rotation,
                color: palette.highlight,
                opacity: region.density * 0.12,
                filter: 'glow',
                seed: seed * 1000 + 400,
                points: 6
            });
        }

        // Add filamentary structure
        if (region.nebula_type !== 'dark' && baseRadius > 60) {
            this.addFilaments(region, palette, seed);
        }
    },

    /**
     * Add a single nebula layer.
     */
    addNebulaLayer(params) {
        const pathData = this.createOrganicPath(
            params.x, params.y,
            params.radiusX, params.radiusY,
            params.seed,
            params.points || 8
        );

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', pathData);
        path.setAttribute('fill', this.colorToRgba(params.color, params.opacity));
        path.setAttribute('filter', `url(#${params.filter})`);

        if (params.rotation && params.rotation !== 0) {
            const rotDeg = params.rotation * 180 / Math.PI;
            path.setAttribute('transform',
                `rotate(${rotDeg}, ${params.x}, ${params.y})`
            );
        }

        this.nebulaeGroup.appendChild(path);
    },

    /**
     * Add filamentary structures to a nebula.
     */
    addFilaments(region, palette, baseSeed) {
        const numFilaments = 2 + Math.floor(this.seededRandom(baseSeed * 7) * 4);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        for (let i = 0; i < numFilaments; i++) {
            const seed = baseSeed * 100 + i;
            const angle = this.seededRandom(seed) * Math.PI * 2;
            const length = baseRadius * (0.5 + this.seededRandom(seed + 1) * 0.8);
            const width = 8 + this.seededRandom(seed + 2) * 15;

            const startX = region.x + Math.cos(angle) * baseRadius * 0.3;
            const startY = region.y + Math.sin(angle) * baseRadius * 0.3;
            const endX = startX + Math.cos(angle + (this.seededRandom(seed + 3) - 0.5) * 0.8) * length;
            const endY = startY + Math.sin(angle + (this.seededRandom(seed + 3) - 0.5) * 0.8) * length;

            const pathData = this.createFilamentPath(startX, startY, endX, endY, width, seed);

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData);
            path.setAttribute('fill', this.colorToRgba(palette.secondary, region.density * 0.05));
            path.setAttribute('filter', 'url(#blur-soft)');
            this.nebulaeGroup.appendChild(path);
        }
    },

    /**
     * Create organic bezier path for nebula shape with irregular edges.
     */
    createOrganicPath(centerX, centerY, radiusX, radiusY, seed, numPoints = 8) {
        const points = [];
        const angleStep = (Math.PI * 2) / numPoints;

        // Generate points with fractal-like variation
        for (let i = 0; i < numPoints; i++) {
            const baseAngle = i * angleStep;
            // Add multiple scales of variation for more natural shapes
            const var1 = (this.seededRandom(seed * 100 + i) - 0.5) * 0.4;
            const var2 = (this.seededRandom(seed * 200 + i) - 0.5) * 0.2;
            const var3 = (this.seededRandom(seed * 300 + i) - 0.5) * 0.1;
            const radiusVar = 0.6 + var1 + var2 + var3 + 0.5;

            const x = centerX + Math.cos(baseAngle) * radiusX * radiusVar;
            const y = centerY + Math.sin(baseAngle) * radiusY * radiusVar;
            points.push({ x, y, angle: baseAngle });
        }

        // Build smooth bezier curve
        let path = `M ${points[0].x} ${points[0].y}`;

        for (let i = 0; i < numPoints; i++) {
            const curr = points[i];
            const next = points[(i + 1) % numPoints];

            // Control point distance based on segment length
            const dx = next.x - curr.x;
            const dy = next.y - curr.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const cpDist = dist * 0.4;

            // Outward-curving control points for organic look
            const midAngle = (curr.angle + next.angle) / 2;
            const perpVar = (this.seededRandom(seed * 400 + i) - 0.5) * 0.5;

            const cp1x = curr.x + Math.cos(curr.angle + Math.PI / 2) * cpDist * (0.3 + this.seededRandom(seed * 500 + i) * 0.7);
            const cp1y = curr.y + Math.sin(curr.angle + Math.PI / 2) * cpDist * (0.3 + this.seededRandom(seed * 501 + i) * 0.7);
            const cp2x = next.x + Math.cos(next.angle - Math.PI / 2) * cpDist * (0.3 + this.seededRandom(seed * 502 + i) * 0.7);
            const cp2y = next.y + Math.sin(next.angle - Math.PI / 2) * cpDist * (0.3 + this.seededRandom(seed * 503 + i) * 0.7);

            path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Create filament/tendril path.
     */
    createFilamentPath(x1, y1, x2, y2, width, seed) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const perpAngle = angle + Math.PI / 2;

        const segments = 8;
        const topPoints = [];
        const bottomPoints = [];

        for (let i = 0; i <= segments; i++) {
            const t = i / segments;
            const x = x1 + dx * t;
            const y = y1 + dy * t;

            // Tapered width (thicker in middle)
            const taper = Math.sin(t * Math.PI);
            // Wavy variation
            const wave = Math.sin(t * Math.PI * 3 + this.seededRandom(seed * 600 + i) * Math.PI) * width * 0.3;
            const localWidth = (width * taper + wave) * (0.5 + this.seededRandom(seed * 700 + i) * 0.5);

            topPoints.push({
                x: x + Math.cos(perpAngle) * localWidth,
                y: y + Math.sin(perpAngle) * localWidth
            });
            bottomPoints.push({
                x: x - Math.cos(perpAngle) * localWidth,
                y: y - Math.sin(perpAngle) * localWidth
            });
        }

        // Build path with quadratic curves for smoothness
        let path = `M ${topPoints[0].x} ${topPoints[0].y}`;

        for (let i = 1; i < topPoints.length; i++) {
            const prev = topPoints[i - 1];
            const curr = topPoints[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed * 800 + i) - 0.5) * width * 0.3;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed * 801 + i) - 0.5) * width * 0.3;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // Arc to bottom
        const last = topPoints[topPoints.length - 1];
        const lastBottom = bottomPoints[bottomPoints.length - 1];
        path += ` Q ${x2} ${y2} ${lastBottom.x} ${lastBottom.y}`;

        // Bottom edge (reverse)
        for (let i = bottomPoints.length - 2; i >= 0; i--) {
            const prev = bottomPoints[i + 1];
            const curr = bottomPoints[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed * 900 + i) - 0.5) * width * 0.3;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed * 901 + i) - 0.5) * width * 0.3;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Procedural nebula generation fallback.
     */
    generateProcedural(stars, width, height, seed) {
        // Find star clusters
        const clusters = this.findClusters(stars);
        const voids = this.findVoids(stars, width, height);

        // Large diffuse background nebulae
        this.addDiffuseBackground(width, height, seed);

        // Emission nebulae near star clusters (H-II regions)
        for (let i = 0; i < Math.min(4, clusters.length); i++) {
            const cluster = clusters[i];
            this.renderNebulaRegion({
                x: cluster.x + (this.seededRandom(seed + i * 100) - 0.5) * 60,
                y: cluster.y + (this.seededRandom(seed + i * 101) - 0.5) * 60,
                radius_x: 60 + this.seededRandom(seed + i * 102) * 80,
                radius_y: 50 + this.seededRandom(seed + i * 103) * 70,
                rotation: this.seededRandom(seed + i * 104) * Math.PI,
                density: 0.4 + this.seededRandom(seed + i * 105) * 0.3,
                nebula_type: 'emission'
            }, seed + i * 1000);
        }

        // Dark nebulae in void regions
        for (let i = 0; i < Math.min(3, voids.length); i++) {
            const void_ = voids[i];
            this.renderNebulaRegion({
                x: void_.x,
                y: void_.y,
                radius_x: 40 + this.seededRandom(seed + 500 + i) * 50,
                radius_y: 35 + this.seededRandom(seed + 501 + i) * 45,
                rotation: this.seededRandom(seed + 502 + i) * Math.PI,
                density: 0.5 + this.seededRandom(seed + 503 + i) * 0.3,
                nebula_type: 'dark'
            }, seed + 500 + i * 1000);
        }

        // Reflection nebulae (blue, near bright stars)
        const brightStars = stars.filter(s => s.spectral_class === 'O' || s.spectral_class === 'B');
        for (let i = 0; i < Math.min(2, brightStars.length); i++) {
            const star = brightStars[i];
            this.renderNebulaRegion({
                x: star.position_x + (this.seededRandom(seed + 700 + i) - 0.5) * 30,
                y: star.position_y + (this.seededRandom(seed + 701 + i) - 0.5) * 30,
                radius_x: 30 + this.seededRandom(seed + 702 + i) * 40,
                radius_y: 25 + this.seededRandom(seed + 703 + i) * 35,
                rotation: this.seededRandom(seed + 704 + i) * Math.PI,
                density: 0.3 + this.seededRandom(seed + 705 + i) * 0.2,
                nebula_type: 'reflection'
            }, seed + 700 + i * 1000);
        }
    },

    /**
     * Add large diffuse background nebulosity.
     */
    addDiffuseBackground(width, height, seed) {
        const numClouds = 3 + Math.floor(this.seededRandom(seed) * 3);

        for (let i = 0; i < numClouds; i++) {
            const s = seed * 10 + i;
            this.renderNebulaRegion({
                x: width * (0.1 + this.seededRandom(s) * 0.8),
                y: height * (0.1 + this.seededRandom(s + 1) * 0.8),
                radius_x: 100 + this.seededRandom(s + 2) * 150,
                radius_y: 80 + this.seededRandom(s + 3) * 120,
                rotation: this.seededRandom(s + 4) * Math.PI,
                density: 0.15 + this.seededRandom(s + 5) * 0.15,
                nebula_type: 'diffuse'
            }, s * 1000);
        }
    },

    /**
     * Find star clusters using density analysis.
     */
    findClusters(stars) {
        const clusters = [];
        const cellSize = 80;
        const density = {};

        for (const star of stars) {
            const key = `${Math.floor(star.position_x / cellSize)},${Math.floor(star.position_y / cellSize)}`;
            density[key] = (density[key] || 0) + 1;
        }

        for (const [key, count] of Object.entries(density)) {
            if (count >= 3) {
                const [cx, cy] = key.split(',').map(Number);
                clusters.push({
                    x: (cx + 0.5) * cellSize,
                    y: (cy + 0.5) * cellSize,
                    density: count
                });
            }
        }

        return clusters.sort((a, b) => b.density - a.density);
    },

    /**
     * Find void regions with few stars.
     */
    findVoids(stars, width, height) {
        const voids = [];
        const cellSize = 100;

        for (let x = cellSize; x < width - cellSize; x += cellSize) {
            for (let y = cellSize; y < height - cellSize; y += cellSize) {
                let nearbyStars = 0;
                for (const star of stars) {
                    const dist = Math.sqrt((star.position_x - x) ** 2 + (star.position_y - y) ** 2);
                    if (dist < cellSize * 1.5) nearbyStars++;
                }
                if (nearbyStars === 0) {
                    voids.push({ x, y });
                }
            }
        }

        return voids;
    },

    /**
     * Convert color object to rgba string.
     */
    colorToRgba(color, opacity) {
        return `rgba(${color.r}, ${color.g}, ${color.b}, ${opacity})`;
    },

    /**
     * Mix two colors.
     */
    mixColors(c1, c2, ratio) {
        return {
            r: Math.round(c1.r * (1 - ratio) + c2.r * ratio),
            g: Math.round(c1.g * (1 - ratio) + c2.g * ratio),
            b: Math.round(c1.b * (1 - ratio) + c2.b * ratio)
        };
    },

    /**
     * Update SVG viewBox to match canvas view.
     */
    updateViewBox(viewX, viewY, zoom, canvasWidth, canvasHeight) {
        if (!this.svg) return;

        const worldWidth = canvasWidth / zoom;
        const worldHeight = canvasHeight / zoom;
        const worldX = viewX - worldWidth / 2;
        const worldY = viewY - worldHeight / 2;

        this.svg.setAttribute('viewBox', `${worldX} ${worldY} ${worldWidth} ${worldHeight}`);
    }
};

window.NebulaSVG = NebulaSVG;
