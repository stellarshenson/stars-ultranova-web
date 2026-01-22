/**
 * Stars Nova Web - SVG Nebula Renderer
 * Renders nebulae as SVG paths with blur filters for organic shapes.
 */

const NebulaSVG = {
    svg: null,
    defs: null,
    nebulaeGroup: null,

    // Unified purple color palette
    palette: {
        primary: { r: 90, g: 50, b: 140 },
        secondary: { r: 110, g: 70, b: 160 },
        accent: { r: 80, g: 60, b: 130 },
        dark: { r: 30, g: 20, b: 50 }
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

        // Clear existing content
        this.svg.innerHTML = '';

        // Create defs for filters
        this.defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        this.svg.appendChild(this.defs);

        // Create blur filters with varying intensities
        this.createFilters();

        // Create group for nebulae
        this.nebulaeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        this.nebulaeGroup.setAttribute('id', 'nebulae');
        this.svg.appendChild(this.nebulaeGroup);

        console.log('NebulaSVG initialized');
    },

    /**
     * Create SVG blur filters.
     */
    createFilters() {
        // Multiple blur levels for depth
        const blurLevels = [
            { id: 'blur-soft', stdDev: 8 },
            { id: 'blur-medium', stdDev: 15 },
            { id: 'blur-heavy', stdDev: 25 },
            { id: 'blur-wispy', stdDev: 5 }
        ];

        for (const blur of blurLevels) {
            const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
            filter.setAttribute('id', blur.id);
            filter.setAttribute('x', '-50%');
            filter.setAttribute('y', '-50%');
            filter.setAttribute('width', '200%');
            filter.setAttribute('height', '200%');

            const feGaussianBlur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
            feGaussianBlur.setAttribute('in', 'SourceGraphic');
            feGaussianBlur.setAttribute('stdDeviation', blur.stdDev);

            filter.appendChild(feGaussianBlur);
            this.defs.appendChild(filter);
        }

        // Glow filter for bright cores
        const glow = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        glow.setAttribute('id', 'glow');
        glow.setAttribute('x', '-100%');
        glow.setAttribute('y', '-100%');
        glow.setAttribute('width', '300%');
        glow.setAttribute('height', '300%');

        const feGaussianBlur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        feGaussianBlur.setAttribute('stdDeviation', '4');
        feGaussianBlur.setAttribute('result', 'coloredBlur');

        const feMerge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
        const feMergeNode1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        feMergeNode1.setAttribute('in', 'coloredBlur');
        const feMergeNode2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        feMergeNode2.setAttribute('in', 'SourceGraphic');
        feMerge.appendChild(feMergeNode1);
        feMerge.appendChild(feMergeNode2);

        glow.appendChild(feGaussianBlur);
        glow.appendChild(feMerge);
        this.defs.appendChild(glow);
    },

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
        if (!this.nebulaeGroup) return;

        // Clear existing nebulae
        this.nebulaeGroup.innerHTML = '';

        // Analyze star distribution
        const clusters = this.findClusters(stars);
        const voids = this.findVoids(stars, universeWidth, universeHeight);

        // Generate different nebula types
        this.addWispyNebulae(clusters, seed);
        this.addFilamentNebulae(stars, universeWidth, universeHeight, seed + 1000);
        this.addDarkNebulae(voids, seed + 2000);
        this.addBrightCores(clusters, seed + 3000);
    },

    /**
     * Find star clusters using simple density analysis.
     */
    findClusters(stars) {
        const clusters = [];
        const cellSize = 80;
        const density = {};

        // Count stars per cell
        for (const star of stars) {
            const key = `${Math.floor(star.position_x / cellSize)},${Math.floor(star.position_y / cellSize)}`;
            density[key] = (density[key] || 0) + 1;
        }

        // Find high-density cells
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

        return clusters;
    },

    /**
     * Find void regions.
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
     * Get color from palette with variation.
     */
    getColor(seed, opacity = 0.15) {
        const colors = [this.palette.primary, this.palette.secondary, this.palette.accent];
        const base = colors[Math.floor(this.seededRandom(seed * 7) * colors.length)];
        const vary = 15;
        const r = base.r + Math.floor(this.seededRandom(seed * 11) * vary - vary / 2);
        const g = base.g + Math.floor(this.seededRandom(seed * 13) * vary - vary / 2);
        const b = base.b + Math.floor(this.seededRandom(seed * 17) * vary - vary / 2);
        return `rgba(${r}, ${g}, ${b}, ${opacity})`;
    },

    /**
     * Create organic bezier path for nebula shape.
     */
    createOrganicPath(centerX, centerY, baseRadius, seed, points = 8) {
        const angleStep = (Math.PI * 2) / points;
        let path = '';

        const controlPoints = [];
        for (let i = 0; i < points; i++) {
            const angle = i * angleStep;
            const radiusVar = baseRadius * (0.6 + this.seededRandom(seed * 100 + i) * 0.8);
            const x = centerX + Math.cos(angle) * radiusVar;
            const y = centerY + Math.sin(angle) * radiusVar;
            controlPoints.push({ x, y, angle });
        }

        // Create smooth bezier curve through points
        path = `M ${controlPoints[0].x} ${controlPoints[0].y}`;

        for (let i = 0; i < points; i++) {
            const curr = controlPoints[i];
            const next = controlPoints[(i + 1) % points];

            // Control point distance
            const cpDist = baseRadius * 0.4;

            // Outward control points for smooth curves
            const cp1x = curr.x + Math.cos(curr.angle + Math.PI / 2) * cpDist * (0.5 + this.seededRandom(seed * 200 + i) * 0.5);
            const cp1y = curr.y + Math.sin(curr.angle + Math.PI / 2) * cpDist * (0.5 + this.seededRandom(seed * 201 + i) * 0.5);
            const cp2x = next.x + Math.cos(next.angle - Math.PI / 2) * cpDist * (0.5 + this.seededRandom(seed * 202 + i) * 0.5);
            const cp2y = next.y + Math.sin(next.angle - Math.PI / 2) * cpDist * (0.5 + this.seededRandom(seed * 203 + i) * 0.5);

            path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Create elongated wispy path.
     */
    createWispyPath(startX, startY, endX, endY, width, seed) {
        const dx = endX - startX;
        const dy = endY - startY;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        const perpAngle = angle + Math.PI / 2;

        // Create wavy edges
        const segments = 6;
        const topPoints = [];
        const bottomPoints = [];

        for (let i = 0; i <= segments; i++) {
            const t = i / segments;
            const x = startX + dx * t;
            const y = startY + dy * t;

            // Wavy width variation
            const waveOffset = Math.sin(t * Math.PI * 2 + this.seededRandom(seed * 300 + i) * Math.PI) * width * 0.3;
            const localWidth = width * (0.3 + 0.7 * Math.sin(t * Math.PI)) + waveOffset;

            topPoints.push({
                x: x + Math.cos(perpAngle) * localWidth,
                y: y + Math.sin(perpAngle) * localWidth
            });
            bottomPoints.push({
                x: x - Math.cos(perpAngle) * localWidth,
                y: y - Math.sin(perpAngle) * localWidth
            });
        }

        // Build path
        let path = `M ${topPoints[0].x} ${topPoints[0].y}`;

        // Top edge with curves
        for (let i = 1; i < topPoints.length; i++) {
            const prev = topPoints[i - 1];
            const curr = topPoints[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed * 400 + i) - 0.5) * width * 0.5;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed * 401 + i) - 0.5) * width * 0.5;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // Connect to bottom edge
        const lastTop = topPoints[topPoints.length - 1];
        const lastBottom = bottomPoints[bottomPoints.length - 1];
        path += ` Q ${endX + (this.seededRandom(seed * 500) - 0.5) * width} ${endY + (this.seededRandom(seed * 501) - 0.5) * width} ${lastBottom.x} ${lastBottom.y}`;

        // Bottom edge (reverse order)
        for (let i = bottomPoints.length - 2; i >= 0; i--) {
            const prev = bottomPoints[i + 1];
            const curr = bottomPoints[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed * 600 + i) - 0.5) * width * 0.5;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed * 601 + i) - 0.5) * width * 0.5;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Add wispy nebulae near clusters.
     */
    addWispyNebulae(clusters, seed) {
        const count = Math.min(5, clusters.length + 2);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;
            let x, y;

            if (i < clusters.length) {
                const cluster = clusters[i];
                const angle = this.seededRandom(s * 11) * Math.PI * 2;
                const dist = 30 + this.seededRandom(s * 13) * 50;
                x = cluster.x + Math.cos(angle) * dist;
                y = cluster.y + Math.sin(angle) * dist;
            } else {
                x = 100 + this.seededRandom(s * 15) * 400;
                y = 100 + this.seededRandom(s * 17) * 400;
            }

            const radius = 50 + this.seededRandom(s * 19) * 80;
            const pathData = this.createOrganicPath(x, y, radius, s, 8 + Math.floor(this.seededRandom(s * 21) * 4));

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData);
            path.setAttribute('fill', this.getColor(s, 0.12));
            path.setAttribute('filter', 'url(#blur-medium)');
            this.nebulaeGroup.appendChild(path);

            // Inner brighter layer
            const innerRadius = radius * 0.6;
            const innerPath = this.createOrganicPath(x, y, innerRadius, s + 1000, 6);
            const inner = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            inner.setAttribute('d', innerPath);
            inner.setAttribute('fill', this.getColor(s + 500, 0.08));
            inner.setAttribute('filter', 'url(#blur-soft)');
            this.nebulaeGroup.appendChild(inner);
        }
    },

    /**
     * Add filament/stream nebulae.
     */
    addFilamentNebulae(stars, width, height, seed) {
        const count = 3 + Math.floor(this.seededRandom(seed) * 3);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;

            // Random start and end points
            const startX = 50 + this.seededRandom(s * 11) * (width - 100);
            const startY = 50 + this.seededRandom(s * 13) * (height - 100);
            const angle = this.seededRandom(s * 15) * Math.PI;
            const length = 100 + this.seededRandom(s * 17) * 200;
            const endX = startX + Math.cos(angle) * length;
            const endY = startY + Math.sin(angle) * length;

            const filamentWidth = 15 + this.seededRandom(s * 19) * 25;
            const pathData = this.createWispyPath(startX, startY, endX, endY, filamentWidth, s);

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData);
            path.setAttribute('fill', this.getColor(s, 0.08));
            path.setAttribute('filter', 'url(#blur-wispy)');
            this.nebulaeGroup.appendChild(path);
        }
    },

    /**
     * Add dark nebulae in void regions.
     */
    addDarkNebulae(voids, seed) {
        const count = Math.min(3, voids.length);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;
            const void_ = voids[Math.floor(this.seededRandom(s) * voids.length)];

            const radius = 40 + this.seededRandom(s * 11) * 60;
            const pathData = this.createOrganicPath(void_.x, void_.y, radius, s, 7);

            const { dark } = this.palette;
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData);
            path.setAttribute('fill', `rgba(${dark.r}, ${dark.g}, ${dark.b}, 0.25)`);
            path.setAttribute('filter', 'url(#blur-heavy)');
            this.nebulaeGroup.appendChild(path);
        }
    },

    /**
     * Add bright cores to clusters.
     */
    addBrightCores(clusters, seed) {
        const count = Math.min(4, clusters.length);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;
            const cluster = clusters[i];

            const radius = 20 + this.seededRandom(s * 11) * 30;
            const pathData = this.createOrganicPath(cluster.x, cluster.y, radius, s, 6);

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', pathData);
            path.setAttribute('fill', this.getColor(s, 0.18));
            path.setAttribute('filter', 'url(#glow)');
            this.nebulaeGroup.appendChild(path);
        }
    },

    /**
     * Update SVG viewBox to match canvas view.
     */
    updateViewBox(viewX, viewY, zoom, canvasWidth, canvasHeight) {
        if (!this.svg) return;

        // Calculate visible world area
        const worldWidth = canvasWidth / zoom;
        const worldHeight = canvasHeight / zoom;
        const worldX = viewX - worldWidth / 2;
        const worldY = viewY - worldHeight / 2;

        this.svg.setAttribute('viewBox', `${worldX} ${worldY} ${worldWidth} ${worldHeight}`);
    }
};

window.NebulaSVG = NebulaSVG;
