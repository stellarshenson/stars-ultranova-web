/**
 * Stars Nova Web - SVG Nebula Renderer
 *
 * Renders nebulae using Gaussian Mixture Models along filament spines,
 * based on astronomical observations of nebula morphology:
 *
 * - Filamentary structures from shock fronts and magnetic field lines
 * - Rayleigh-Taylor instabilities creating finger-like projections
 * - Turbulent flows producing wispy, stringy appearance
 * - KDE-like density contours for organic boundaries
 *
 * References:
 * - Veil Nebula: Supernova remnant with intricate filaments
 * - Crab Nebula: Filamentary structure from pulsar wind
 * - Orion Nebula: H-II region with pillars and streamers
 */

const NebulaSVG = {
    svg: null,
    defs: null,
    nebulaeGroup: null,

    // Astronomical color palettes
    palettes: {
        emission: {
            primary: { r: 180, g: 60, b: 120 },    // H-alpha pink
            secondary: { r: 100, g: 160, b: 180 }, // O-III teal
            tertiary: { r: 140, g: 80, b: 160 }    // Mixed
        },
        reflection: {
            primary: { r: 80, g: 120, b: 200 },
            secondary: { r: 100, g: 140, b: 220 },
            tertiary: { r: 60, g: 100, b: 180 }
        },
        dark: {
            primary: { r: 15, g: 10, b: 25 },
            secondary: { r: 25, g: 15, b: 35 },
            tertiary: { r: 20, g: 12, b: 30 }
        },
        diffuse: {
            primary: { r: 70, g: 50, b: 110 },
            secondary: { r: 90, g: 60, b: 130 },
            tertiary: { r: 80, g: 55, b: 120 }
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

        this.defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        this.svg.appendChild(this.defs);

        this.createFilters();

        this.nebulaeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        this.nebulaeGroup.setAttribute('id', 'nebulae');
        this.svg.appendChild(this.nebulaeGroup);

        console.log('NebulaSVG initialized with GMM filamentary model');
    },

    /**
     * Create SVG filters for soft, diffuse appearance.
     */
    createFilters() {
        // Multiple blur levels
        [['blur-extreme', 50], ['blur-ultra', 35], ['blur-heavy', 22],
         ['blur-medium', 14], ['blur-soft', 8], ['blur-light', 4], ['blur-wispy', 2]
        ].forEach(([id, std]) => this.createBlurFilter(id, std));

        // Glow filter for bright regions
        this.createGlowFilter();

        // Turbulence for texture
        this.createTurbulenceFilter();
    },

    createBlurFilter(id, stdDev) {
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', id);
        filter.setAttribute('x', '-150%');
        filter.setAttribute('y', '-150%');
        filter.setAttribute('width', '400%');
        filter.setAttribute('height', '400%');

        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('in', 'SourceGraphic');
        blur.setAttribute('stdDeviation', stdDev);

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
        blur.setAttribute('stdDeviation', '5');
        blur.setAttribute('result', 'glow');

        const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
        ['glow', 'glow', 'SourceGraphic'].forEach(input => {
            const node = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
            node.setAttribute('in', input);
            merge.appendChild(node);
        });

        filter.appendChild(blur);
        filter.appendChild(merge);
        this.defs.appendChild(filter);
    },

    createTurbulenceFilter() {
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.setAttribute('id', 'turbulence');
        filter.setAttribute('x', '-50%');
        filter.setAttribute('y', '-50%');
        filter.setAttribute('width', '200%');
        filter.setAttribute('height', '200%');

        const turbulence = document.createElementNS('http://www.w3.org/2000/svg', 'feTurbulence');
        turbulence.setAttribute('type', 'fractalNoise');
        turbulence.setAttribute('baseFrequency', '0.015');
        turbulence.setAttribute('numOctaves', '5');
        turbulence.setAttribute('result', 'noise');

        const displacement = document.createElementNS('http://www.w3.org/2000/svg', 'feDisplacementMap');
        displacement.setAttribute('in', 'SourceGraphic');
        displacement.setAttribute('in2', 'noise');
        displacement.setAttribute('scale', '15');
        displacement.setAttribute('xChannelSelector', 'R');
        displacement.setAttribute('yChannelSelector', 'G');

        filter.appendChild(turbulence);
        filter.appendChild(displacement);
        this.defs.appendChild(filter);
    },

    /**
     * Seeded random number generator (improved quality).
     */
    seededRandom(seed) {
        const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
        return x - Math.floor(x);
    },

    /**
     * Box-Muller transform for Gaussian random numbers.
     */
    gaussianRandom(seed, mean = 0, stdDev = 1) {
        const u1 = this.seededRandom(seed);
        const u2 = this.seededRandom(seed + 0.5);
        const z = Math.sqrt(-2 * Math.log(u1 + 0.0001)) * Math.cos(2 * Math.PI * u2);
        return mean + z * stdDev;
    },

    /**
     * Generate nebulae from backend data or procedurally.
     */
    generate(stars, universeWidth, universeHeight, seed = 0) {
        if (!this.nebulaeGroup) return;
        this.nebulaeGroup.innerHTML = '';

        if (GameState.nebulae && GameState.nebulae.regions && GameState.nebulae.regions.length > 0) {
            this.renderFromBackend(GameState.nebulae, seed);
            return;
        }

        this.generateProcedural(stars, universeWidth, universeHeight, seed);
    },

    /**
     * Render nebulae from backend data using filamentary GMM.
     */
    renderFromBackend(nebulaField, baseSeed = 0) {
        if (!this.nebulaeGroup) return;

        const sortedRegions = [...nebulaField.regions].sort(
            (a, b) => Math.max(b.radius_x, b.radius_y) - Math.max(a.radius_x, a.radius_y)
        );

        for (let i = 0; i < sortedRegions.length; i++) {
            this.renderFilamentaryNebula(sortedRegions[i], baseSeed + i * 10000);
        }
    },

    /**
     * Render a single nebula using GMM-based filamentary structure.
     */
    renderFilamentaryNebula(region, seed) {
        const palette = this.palettes[region.nebula_type] || this.palettes.diffuse;
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Generate filament network using GMM
        const filaments = this.generateFilamentNetwork(region, seed);

        // Render background diffuse glow (very soft)
        this.renderDiffuseHalo(region, palette, seed);

        // Render each filament with multiple layers
        filaments.forEach((filament, i) => {
            this.renderFilament(filament, palette, region.density, seed + i * 100);
        });

        // Add bright knots along dense regions
        if (region.nebula_type === 'emission') {
            this.renderBrightKnots(filaments, palette, region.density, seed + 5000);
        }
    },

    /**
     * Generate a network of filaments using GMM components along curved spines.
     *
     * Based on astronomical observations:
     * - Main shock front creates primary filament
     * - Rayleigh-Taylor instabilities create branching fingers
     * - Magnetic field lines create parallel striations
     */
    generateFilamentNetwork(region, seed) {
        const filaments = [];
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Number of primary filaments based on nebula size
        const numPrimary = 3 + Math.floor(this.seededRandom(seed) * 4);

        for (let i = 0; i < numPrimary; i++) {
            const filamentSeed = seed + i * 1000;

            // Generate curved spine using random walk with momentum
            const spine = this.generateFilamentSpine(region, filamentSeed);
            filaments.push({
                spine: spine,
                width: 3 + this.seededRandom(filamentSeed + 1) * 8,
                type: 'primary'
            });

            // Add secondary branching filaments (Rayleigh-Taylor fingers)
            const numBranches = Math.floor(this.seededRandom(filamentSeed + 2) * 3);
            for (let j = 0; j < numBranches; j++) {
                const branchSeed = filamentSeed + 100 + j * 50;
                const branchPoint = Math.floor(this.seededRandom(branchSeed) * (spine.length - 2)) + 1;
                const branchSpine = this.generateBranchSpine(spine, branchPoint, region, branchSeed);

                if (branchSpine.length > 3) {
                    filaments.push({
                        spine: branchSpine,
                        width: 2 + this.seededRandom(branchSeed + 1) * 4,
                        type: 'secondary'
                    });
                }
            }
        }

        // Add wispy tendrils (thin, long filaments)
        const numTendrils = 4 + Math.floor(this.seededRandom(seed + 500) * 6);
        for (let i = 0; i < numTendrils; i++) {
            const tendrilSeed = seed + 2000 + i * 100;
            const tendrilSpine = this.generateTendrilSpine(region, tendrilSeed);

            filaments.push({
                spine: tendrilSpine,
                width: 1 + this.seededRandom(tendrilSeed + 1) * 3,
                type: 'tendril'
            });
        }

        return filaments;
    },

    /**
     * Generate a curved filament spine using correlated random walk.
     * Models shock front propagation with turbulent perturbations.
     */
    generateFilamentSpine(region, seed) {
        const points = [];
        const numPoints = 12 + Math.floor(this.seededRandom(seed) * 8);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Start from a random point on the nebula boundary
        const startAngle = this.seededRandom(seed + 1) * Math.PI * 2;
        let x = region.x + Math.cos(startAngle) * baseRadius * (0.3 + this.seededRandom(seed + 2) * 0.5);
        let y = region.y + Math.sin(startAngle) * baseRadius * (0.3 + this.seededRandom(seed + 3) * 0.5);

        // Initial direction with some randomness
        let angle = startAngle + Math.PI + (this.seededRandom(seed + 4) - 0.5) * Math.PI * 0.5;
        let momentum = 0.7 + this.seededRandom(seed + 5) * 0.3; // How much previous direction influences next

        points.push({ x, y });

        for (let i = 1; i < numPoints; i++) {
            // Step length varies
            const stepLength = baseRadius * (0.08 + this.seededRandom(seed + i * 10) * 0.12);

            // Add curvature (correlated direction changes)
            const curvature = this.gaussianRandom(seed + i * 10 + 1, 0, 0.3);
            angle += curvature * (1 - momentum);

            // Add small perpendicular perturbations (turbulence)
            const perpturb = this.gaussianRandom(seed + i * 10 + 2, 0, stepLength * 0.2);

            x += Math.cos(angle) * stepLength + Math.cos(angle + Math.PI/2) * perpturb;
            y += Math.sin(angle) * stepLength + Math.sin(angle + Math.PI/2) * perpturb;

            // Keep within nebula bounds (soft constraint)
            const distFromCenter = Math.sqrt((x - region.x) ** 2 + (y - region.y) ** 2);
            if (distFromCenter > baseRadius * 1.2) {
                // Bend back toward center
                const toCenter = Math.atan2(region.y - y, region.x - x);
                angle = angle * 0.7 + toCenter * 0.3;
            }

            points.push({ x, y });
        }

        return points;
    },

    /**
     * Generate a branching filament from a parent spine.
     */
    generateBranchSpine(parentSpine, branchIndex, region, seed) {
        const points = [];
        const branchPoint = parentSpine[branchIndex];
        const prevPoint = parentSpine[Math.max(0, branchIndex - 1)];

        // Branch direction perpendicular to parent with some variation
        const parentAngle = Math.atan2(branchPoint.y - prevPoint.y, branchPoint.x - prevPoint.x);
        const branchSide = this.seededRandom(seed) > 0.5 ? 1 : -1;
        let angle = parentAngle + branchSide * (Math.PI / 2 + (this.seededRandom(seed + 1) - 0.5) * 0.8);

        let x = branchPoint.x;
        let y = branchPoint.y;
        points.push({ x, y });

        const numPoints = 5 + Math.floor(this.seededRandom(seed + 2) * 5);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        for (let i = 1; i < numPoints; i++) {
            const stepLength = baseRadius * (0.04 + this.seededRandom(seed + i * 10) * 0.08);
            angle += this.gaussianRandom(seed + i * 10 + 3, 0, 0.4);

            x += Math.cos(angle) * stepLength;
            y += Math.sin(angle) * stepLength;
            points.push({ x, y });
        }

        return points;
    },

    /**
     * Generate a thin tendril filament.
     */
    generateTendrilSpine(region, seed) {
        const points = [];
        const baseRadius = Math.max(region.radius_x, region.radius_y);
        const numPoints = 8 + Math.floor(this.seededRandom(seed) * 6);

        // Start from random position within nebula
        let x = region.x + this.gaussianRandom(seed + 1, 0, baseRadius * 0.4);
        let y = region.y + this.gaussianRandom(seed + 2, 0, baseRadius * 0.4);
        let angle = this.seededRandom(seed + 3) * Math.PI * 2;

        points.push({ x, y });

        for (let i = 1; i < numPoints; i++) {
            const stepLength = baseRadius * (0.06 + this.seededRandom(seed + i * 10) * 0.1);
            angle += this.gaussianRandom(seed + i * 10 + 4, 0, 0.5);

            x += Math.cos(angle) * stepLength;
            y += Math.sin(angle) * stepLength;
            points.push({ x, y });
        }

        return points;
    },

    /**
     * Render diffuse halo around the nebula.
     */
    renderDiffuseHalo(region, palette, seed) {
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Very large, very faint outer glow
        const haloPath = this.createBlobPath(
            region.x, region.y,
            baseRadius * 1.8, baseRadius * 1.6,
            seed, 10
        );

        const halo = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        halo.setAttribute('d', haloPath);
        halo.setAttribute('fill', this.colorToRgba(palette.primary, region.density * 0.02));
        halo.setAttribute('filter', 'url(#blur-extreme)');
        this.nebulaeGroup.appendChild(halo);

        // Secondary halo
        const halo2Path = this.createBlobPath(
            region.x, region.y,
            baseRadius * 1.3, baseRadius * 1.1,
            seed + 100, 8
        );

        const halo2 = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        halo2.setAttribute('d', halo2Path);
        halo2.setAttribute('fill', this.colorToRgba(palette.secondary, region.density * 0.03));
        halo2.setAttribute('filter', 'url(#blur-ultra)');
        this.nebulaeGroup.appendChild(halo2);
    },

    /**
     * Render a single filament with GMM-based width variation.
     */
    renderFilament(filament, palette, density, seed) {
        const { spine, width, type } = filament;
        if (spine.length < 2) return;

        // Sample GMM components along the spine
        const gmmPoints = this.sampleGMMAlongSpine(spine, width, seed);

        // Create KDE-like contour path
        const contourPath = this.createFilamentContour(spine, gmmPoints, width, seed);

        // Render multiple layers for soft appearance
        const layers = [
            { scale: 2.5, blur: 'blur-heavy', opacity: density * 0.03 },
            { scale: 1.8, blur: 'blur-medium', opacity: density * 0.05 },
            { scale: 1.3, blur: 'blur-soft', opacity: density * 0.06 },
            { scale: 1.0, blur: 'blur-light', opacity: density * 0.08 }
        ];

        if (type === 'tendril') {
            // Tendrils are thinner and more transparent
            layers.forEach(l => { l.opacity *= 0.5; l.scale *= 0.7; });
        }

        layers.forEach((layer, i) => {
            const scaledPath = this.scaleFilamentPath(contourPath, spine, layer.scale);
            const color = i % 2 === 0 ? palette.primary : palette.secondary;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', scaledPath);
            path.setAttribute('fill', this.colorToRgba(color, layer.opacity));
            path.setAttribute('filter', `url(#${layer.blur})`);
            this.nebulaeGroup.appendChild(path);
        });
    },

    /**
     * Sample GMM components along a spine to create width variation.
     * Each component is an elongated Gaussian perpendicular to the spine.
     */
    sampleGMMAlongSpine(spine, baseWidth, seed) {
        const samples = [];
        const numSamples = spine.length * 3;

        for (let i = 0; i < numSamples; i++) {
            const t = i / (numSamples - 1);
            const spineIndex = Math.min(Math.floor(t * (spine.length - 1)), spine.length - 2);
            const localT = (t * (spine.length - 1)) - spineIndex;

            // Interpolate position on spine
            const p1 = spine[spineIndex];
            const p2 = spine[spineIndex + 1];
            const x = p1.x + (p2.x - p1.x) * localT;
            const y = p1.y + (p2.y - p1.y) * localT;

            // Direction perpendicular to spine
            const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x) + Math.PI / 2;

            // Width variation using Gaussian
            const widthVar = baseWidth * (0.5 + Math.abs(this.gaussianRandom(seed + i * 10, 0, 0.5)));

            // Sample perpendicular offset
            const offset = this.gaussianRandom(seed + i * 10 + 1, 0, widthVar);

            samples.push({
                x: x + Math.cos(angle) * offset,
                y: y + Math.sin(angle) * offset,
                weight: Math.exp(-offset * offset / (2 * widthVar * widthVar))
            });
        }

        return samples;
    },

    /**
     * Create a smooth contour path around a filament using sampled GMM points.
     */
    createFilamentContour(spine, gmmPoints, baseWidth, seed) {
        if (spine.length < 2) return '';

        // Generate upper and lower edges
        const upperEdge = [];
        const lowerEdge = [];

        for (let i = 0; i < spine.length; i++) {
            const p = spine[i];
            const prev = spine[Math.max(0, i - 1)];
            const next = spine[Math.min(spine.length - 1, i + 1)];

            // Tangent direction
            const tangent = Math.atan2(next.y - prev.y, next.x - prev.x);
            const normal = tangent + Math.PI / 2;

            // Width varies along filament (thicker in middle, tapered at ends)
            const taper = Math.sin((i / (spine.length - 1)) * Math.PI);
            const widthNoise = 0.7 + this.seededRandom(seed + i * 7) * 0.6;
            const localWidth = baseWidth * taper * widthNoise;

            upperEdge.push({
                x: p.x + Math.cos(normal) * localWidth,
                y: p.y + Math.sin(normal) * localWidth
            });
            lowerEdge.push({
                x: p.x - Math.cos(normal) * localWidth,
                y: p.y - Math.sin(normal) * localWidth
            });
        }

        // Build smooth bezier path
        let path = `M ${upperEdge[0].x} ${upperEdge[0].y}`;

        // Upper edge (forward)
        for (let i = 1; i < upperEdge.length; i++) {
            const prev = upperEdge[i - 1];
            const curr = upperEdge[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed + i * 20) - 0.5) * baseWidth * 0.3;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed + i * 21) - 0.5) * baseWidth * 0.3;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // Cap at end
        const lastUpper = upperEdge[upperEdge.length - 1];
        const lastLower = lowerEdge[lowerEdge.length - 1];
        const lastSpine = spine[spine.length - 1];
        path += ` Q ${lastSpine.x} ${lastSpine.y} ${lastLower.x} ${lastLower.y}`;

        // Lower edge (backward)
        for (let i = lowerEdge.length - 2; i >= 0; i--) {
            const prev = lowerEdge[i + 1];
            const curr = lowerEdge[i];
            const cpx = (prev.x + curr.x) / 2 + (this.seededRandom(seed + i * 30) - 0.5) * baseWidth * 0.3;
            const cpy = (prev.y + curr.y) / 2 + (this.seededRandom(seed + i * 31) - 0.5) * baseWidth * 0.3;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // Cap at start
        const firstUpper = upperEdge[0];
        const firstLower = lowerEdge[0];
        const firstSpine = spine[0];
        path += ` Q ${firstSpine.x} ${firstSpine.y} ${firstUpper.x} ${firstUpper.y}`;

        path += ' Z';
        return path;
    },

    /**
     * Scale a filament path outward from its spine.
     */
    scaleFilamentPath(pathStr, spine, scale) {
        // For simplicity, regenerate with scaled width
        // This is a rough approximation
        return pathStr.replace(/(-?\d+\.?\d*)/g, (match, num, offset, string) => {
            const val = parseFloat(num);
            // Find closest spine point and scale from there
            // Simplified: just return the path as-is for blur layers
            return match;
        });
    },

    /**
     * Render bright knots at dense regions (star-forming regions).
     */
    renderBrightKnots(filaments, palette, density, seed) {
        const numKnots = 2 + Math.floor(this.seededRandom(seed) * 4);

        for (let i = 0; i < numKnots; i++) {
            // Pick a random point on a random filament
            const filament = filaments[Math.floor(this.seededRandom(seed + i * 10) * filaments.length)];
            const spineIndex = Math.floor(this.seededRandom(seed + i * 10 + 1) * filament.spine.length);
            const point = filament.spine[spineIndex];

            const knotRadius = 5 + this.seededRandom(seed + i * 10 + 2) * 10;

            // Render as glowing blob
            const knotPath = this.createBlobPath(point.x, point.y, knotRadius, knotRadius * 0.8, seed + i * 100, 6);

            const knot = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            knot.setAttribute('d', knotPath);
            knot.setAttribute('fill', this.colorToRgba(palette.primary, density * 0.15));
            knot.setAttribute('filter', 'url(#glow)');
            this.nebulaeGroup.appendChild(knot);
        }
    },

    /**
     * Create an organic blob path.
     */
    createBlobPath(cx, cy, rx, ry, seed, numPoints = 8) {
        const points = [];
        const angleStep = (Math.PI * 2) / numPoints;

        for (let i = 0; i < numPoints; i++) {
            const angle = i * angleStep;
            const radiusVar = 0.7 + this.seededRandom(seed + i * 13) * 0.6;
            points.push({
                x: cx + Math.cos(angle) * rx * radiusVar,
                y: cy + Math.sin(angle) * ry * radiusVar,
                angle
            });
        }

        let path = `M ${points[0].x} ${points[0].y}`;
        for (let i = 0; i < numPoints; i++) {
            const curr = points[i];
            const next = points[(i + 1) % numPoints];
            const cpDist = Math.sqrt((next.x - curr.x) ** 2 + (next.y - curr.y) ** 2) * 0.4;

            const cp1x = curr.x + Math.cos(curr.angle + Math.PI/2) * cpDist * (0.3 + this.seededRandom(seed + i * 17) * 0.7);
            const cp1y = curr.y + Math.sin(curr.angle + Math.PI/2) * cpDist * (0.3 + this.seededRandom(seed + i * 19) * 0.7);
            const cp2x = next.x + Math.cos(next.angle - Math.PI/2) * cpDist * (0.3 + this.seededRandom(seed + i * 23) * 0.7);
            const cp2y = next.y + Math.sin(next.angle - Math.PI/2) * cpDist * (0.3 + this.seededRandom(seed + i * 29) * 0.7);

            path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
        }
        path += ' Z';
        return path;
    },

    /**
     * Procedural nebula generation when no backend data.
     */
    generateProcedural(stars, width, height, seed) {
        const clusters = this.findClusters(stars);
        const voids = this.findVoids(stars, width, height);

        // Generate emission nebulae near clusters
        for (let i = 0; i < Math.min(4, clusters.length); i++) {
            const cluster = clusters[i];
            this.renderFilamentaryNebula({
                x: cluster.x + (this.seededRandom(seed + i * 100) - 0.5) * 50,
                y: cluster.y + (this.seededRandom(seed + i * 101) - 0.5) * 50,
                radius_x: 70 + this.seededRandom(seed + i * 102) * 90,
                radius_y: 60 + this.seededRandom(seed + i * 103) * 80,
                rotation: this.seededRandom(seed + i * 104) * Math.PI,
                density: 0.4 + this.seededRandom(seed + i * 105) * 0.3,
                nebula_type: 'emission'
            }, seed + i * 10000);
        }

        // Dark nebulae in voids
        for (let i = 0; i < Math.min(2, voids.length); i++) {
            const void_ = voids[i];
            this.renderFilamentaryNebula({
                x: void_.x,
                y: void_.y,
                radius_x: 50 + this.seededRandom(seed + 500 + i) * 60,
                radius_y: 45 + this.seededRandom(seed + 501 + i) * 55,
                rotation: this.seededRandom(seed + 502 + i) * Math.PI,
                density: 0.5,
                nebula_type: 'dark'
            }, seed + 500000 + i * 10000);
        }

        // Diffuse background
        this.renderFilamentaryNebula({
            x: width * 0.5,
            y: height * 0.5,
            radius_x: width * 0.4,
            radius_y: height * 0.35,
            rotation: this.seededRandom(seed + 900) * Math.PI,
            density: 0.15,
            nebula_type: 'diffuse'
        }, seed + 900000);
    },

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
                clusters.push({ x: (cx + 0.5) * cellSize, y: (cy + 0.5) * cellSize, density: count });
            }
        }

        return clusters.sort((a, b) => b.density - a.density);
    },

    findVoids(stars, width, height) {
        const voids = [];
        const cellSize = 100;

        for (let x = cellSize; x < width - cellSize; x += cellSize) {
            for (let y = cellSize; y < height - cellSize; y += cellSize) {
                let nearby = 0;
                for (const star of stars) {
                    if (Math.sqrt((star.position_x - x) ** 2 + (star.position_y - y) ** 2) < cellSize * 1.5) nearby++;
                }
                if (nearby === 0) voids.push({ x, y });
            }
        }
        return voids;
    },

    colorToRgba(color, opacity) {
        return `rgba(${color.r}, ${color.g}, ${color.b}, ${opacity})`;
    },

    updateViewBox(viewX, viewY, zoom, canvasWidth, canvasHeight) {
        if (!this.svg) return;
        const worldWidth = canvasWidth / zoom;
        const worldHeight = canvasHeight / zoom;
        this.svg.setAttribute('viewBox', `${viewX - worldWidth/2} ${viewY - worldHeight/2} ${worldWidth} ${worldHeight}`);
    }
};

window.NebulaSVG = NebulaSVG;
