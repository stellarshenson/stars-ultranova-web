/**
 * Stars Nova Web - SVG Nebula Renderer
 *
 * Models two distinct nebula types based on astronomical observations:
 *
 * GAS NEBULAE (Emission/Reflection):
 * - Ionized hydrogen clouds around hot O/B stars
 * - Soft, diffuse boundaries that blend into space
 * - Stars embedded within the gas (star-forming regions)
 * - H-alpha emission (red-pink) and O-III (teal-cyan) colors
 * - Filamentary structure from magnetic field confinement
 *
 * DUST CLOUDS (Dark/Absorption):
 * - Dense molecular clouds with sharper boundaries
 * - Block background starlight creating dark patches
 * - Rifts and lanes with defined edges
 * - Brown/amber warm dust glow at edges (infrared)
 *
 * References:
 * - Orion Nebula (M42): H-II emission with embedded star cluster
 * - Horsehead Nebula: Sharp dust cloud boundary against emission
 * - Carina Nebula: Massive star-forming complex with pillars
 * - Coal Sack: Dark absorption nebula silhouette
 */

const NebulaSVG = {
    svg: null,
    defs: null,
    nebulaeGroup: null,
    dustGroup: null,
    gasGroup: null,

    // Astronomical color palettes
    palettes: {
        // Gas nebulae - ionized hydrogen regions
        emission: {
            primary: { r: 200, g: 70, b: 130 },    // H-alpha deep pink
            secondary: { r: 80, g: 150, b: 170 },   // O-III teal
            tertiary: { r: 160, g: 90, b: 150 },    // Mixed emission
            glow: { r: 255, g: 180, b: 200 }        // Bright core glow
        },
        reflection: {
            primary: { r: 70, g: 110, b: 190 },     // Reflected starlight blue
            secondary: { r: 90, g: 130, b: 210 },
            tertiary: { r: 60, g: 95, b: 170 },
            glow: { r: 150, g: 180, b: 255 }
        },
        // Dust clouds - molecular absorption
        dark: {
            primary: { r: 8, g: 5, b: 15 },         // Cold dense core
            secondary: { r: 15, g: 10, b: 25 },     // Mid density
            tertiary: { r: 25, g: 18, b: 35 },      // Outer transition
            edge: { r: 60, g: 35, b: 25 }           // Warm dust edge (IR glow)
        },
        diffuse: {
            primary: { r: 60, g: 45, b: 95 },
            secondary: { r: 80, g: 55, b: 115 },
            tertiary: { r: 70, g: 50, b: 105 },
            glow: { r: 120, g: 100, b: 160 }
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

        // Dust layer renders first (behind gas)
        this.dustGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        this.dustGroup.setAttribute('id', 'dust-clouds');
        this.svg.appendChild(this.dustGroup);

        // Gas nebulae render on top
        this.gasGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        this.gasGroup.setAttribute('id', 'gas-nebulae');
        this.svg.appendChild(this.gasGroup);

        // Combined reference
        this.nebulaeGroup = this.gasGroup;

        console.log('NebulaSVG initialized with dual dust/gas model');
    },

    /**
     * Create SVG filters for different nebula appearances.
     */
    createFilters() {
        // Gas nebula blur levels (softer)
        [['gas-blur-heavy', 30], ['gas-blur-medium', 18],
         ['gas-blur-soft', 10], ['gas-blur-light', 5]
        ].forEach(([id, std]) => this.createBlurFilter(id, std));

        // Dust cloud blur (sharper)
        [['dust-blur-edge', 6], ['dust-blur-soft', 3], ['dust-blur-sharp', 1]
        ].forEach(([id, std]) => this.createBlurFilter(id, std));

        // Glow for star-forming regions
        this.createGlowFilter();

        // Turbulence for texture variation
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
        filter.setAttribute('id', 'star-glow');
        filter.setAttribute('x', '-100%');
        filter.setAttribute('y', '-100%');
        filter.setAttribute('width', '300%');
        filter.setAttribute('height', '300%');

        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('stdDeviation', '4');
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
        filter.setAttribute('id', 'dust-texture');
        filter.setAttribute('x', '-30%');
        filter.setAttribute('y', '-30%');
        filter.setAttribute('width', '160%');
        filter.setAttribute('height', '160%');

        const turbulence = document.createElementNS('http://www.w3.org/2000/svg', 'feTurbulence');
        turbulence.setAttribute('type', 'fractalNoise');
        turbulence.setAttribute('baseFrequency', '0.025');
        turbulence.setAttribute('numOctaves', '4');
        turbulence.setAttribute('result', 'noise');

        const displacement = document.createElementNS('http://www.w3.org/2000/svg', 'feDisplacementMap');
        displacement.setAttribute('in', 'SourceGraphic');
        displacement.setAttribute('in2', 'noise');
        displacement.setAttribute('scale', '8');
        displacement.setAttribute('xChannelSelector', 'R');
        displacement.setAttribute('yChannelSelector', 'G');

        filter.appendChild(turbulence);
        filter.appendChild(displacement);
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
     * Box-Muller transform for Gaussian random numbers.
     */
    gaussianRandom(seed, mean = 0, stdDev = 1) {
        const u1 = Math.max(0.0001, this.seededRandom(seed));
        const u2 = this.seededRandom(seed + 0.5);
        const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
        return mean + z * stdDev;
    },

    /**
     * Generate nebulae from backend data or procedurally.
     */
    generate(stars, universeWidth, universeHeight, seed = 0) {
        if (!this.gasGroup || !this.dustGroup) return;
        this.gasGroup.innerHTML = '';
        this.dustGroup.innerHTML = '';

        if (GameState.nebulae && GameState.nebulae.regions && GameState.nebulae.regions.length > 0) {
            this.renderFromBackend(GameState.nebulae, stars, seed);
            return;
        }

        this.generateProcedural(stars, universeWidth, universeHeight, seed);
    },

    /**
     * Render nebulae from backend data.
     */
    renderFromBackend(nebulaField, stars, baseSeed = 0) {
        // Separate regions by type
        const gasRegions = [];
        const dustRegions = [];

        for (const region of nebulaField.regions) {
            if (region.nebula_type === 'dark') {
                dustRegions.push(region);
            } else {
                gasRegions.push(region);
            }
        }

        // Render dust clouds first (darker, behind)
        dustRegions.sort((a, b) => Math.max(b.radius_x, b.radius_y) - Math.max(a.radius_x, a.radius_y));
        for (let i = 0; i < dustRegions.length; i++) {
            this.renderDustCloud(dustRegions[i], baseSeed + i * 10000);
        }

        // Render gas nebulae on top
        gasRegions.sort((a, b) => Math.max(b.radius_x, b.radius_y) - Math.max(a.radius_x, a.radius_y));
        for (let i = 0; i < gasRegions.length; i++) {
            this.renderGasNebula(gasRegions[i], stars, baseSeed + 500000 + i * 10000);
        }
    },

    /**
     * Render a gas nebula (emission/reflection) with embedded stars.
     * These have soft boundaries and host star-forming regions.
     */
    renderGasNebula(region, stars, seed) {
        const palette = this.palettes[region.nebula_type] || this.palettes.emission;
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Find stars within this nebula region
        const embeddedStars = stars.filter(star => {
            const dx = star.position_x - region.x;
            const dy = star.position_y - region.y;
            return Math.sqrt(dx*dx + dy*dy) < baseRadius * 1.2;
        });

        // Generate substantial filament network
        const filaments = this.generateGasFilaments(region, embeddedStars, seed);

        // Layer 1: Very diffuse outer halo
        this.renderGasHalo(region, palette, seed);

        // Layer 2: Main filament structures
        filaments.forEach((filament, i) => {
            this.renderGasFilament(filament, palette, region.density, seed + i * 100);
        });

        // Layer 3: Bright cores around embedded stars
        this.renderStarFormingRegions(embeddedStars, region, palette, seed + 8000);
    },

    /**
     * Generate substantial gas filaments that follow magnetic field lines.
     * These are thicker and more persistent than the previous implementation.
     */
    generateGasFilaments(region, stars, seed) {
        const filaments = [];
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Primary filaments - substantial structures
        const numPrimary = 2 + Math.floor(this.seededRandom(seed) * 3);

        for (let i = 0; i < numPrimary; i++) {
            const filamentSeed = seed + i * 1000;

            // Generate curved spine with controlled curvature
            const spine = this.generateSubstantialSpine(region, filamentSeed);

            filaments.push({
                spine: spine,
                width: 12 + this.seededRandom(filamentSeed + 1) * 20, // Much wider
                type: 'primary'
            });

            // Add branches that connect to stars
            const numBranches = 1 + Math.floor(this.seededRandom(filamentSeed + 2) * 2);
            for (let j = 0; j < numBranches; j++) {
                const branchSeed = filamentSeed + 100 + j * 50;
                const branchPoint = 2 + Math.floor(this.seededRandom(branchSeed) * (spine.length - 4));
                const branchSpine = this.generateBranchSpine(spine, branchPoint, region, branchSeed);

                if (branchSpine.length > 4) {
                    filaments.push({
                        spine: branchSpine,
                        width: 8 + this.seededRandom(branchSeed + 1) * 12,
                        type: 'secondary'
                    });
                }
            }
        }

        // Connect filaments to star positions (star-forming pillars)
        for (let i = 0; i < Math.min(stars.length, 3); i++) {
            const star = stars[i];
            const pillarSeed = seed + 3000 + i * 100;
            const pillarSpine = this.generatePillarToStar(region, star, pillarSeed);

            if (pillarSpine.length > 3) {
                filaments.push({
                    spine: pillarSpine,
                    width: 15 + this.seededRandom(pillarSeed) * 10,
                    type: 'pillar'
                });
            }
        }

        return filaments;
    },

    /**
     * Generate a substantial filament spine with controlled curvature.
     * Less nimble, more persistent direction.
     */
    generateSubstantialSpine(region, seed) {
        const points = [];
        const numPoints = 8 + Math.floor(this.seededRandom(seed) * 5);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Start position
        const startAngle = this.seededRandom(seed + 1) * Math.PI * 2;
        const startDist = baseRadius * (0.2 + this.seededRandom(seed + 2) * 0.4);
        let x = region.x + Math.cos(startAngle) * startDist;
        let y = region.y + Math.sin(startAngle) * startDist;

        // Initial direction - inward toward center with variation
        let angle = Math.atan2(region.y - y, region.x - x) + (this.seededRandom(seed + 3) - 0.5) * 1.2;

        points.push({ x, y });

        // High momentum for persistent direction
        const momentum = 0.85;

        for (let i = 1; i < numPoints; i++) {
            // Larger, more consistent steps
            const stepLength = baseRadius * (0.12 + this.seededRandom(seed + i * 10) * 0.08);

            // Gentle curvature
            const curvature = this.gaussianRandom(seed + i * 10 + 1, 0, 0.15);
            angle += curvature * (1 - momentum);

            x += Math.cos(angle) * stepLength;
            y += Math.sin(angle) * stepLength;

            // Soft boundary constraint
            const distFromCenter = Math.sqrt((x - region.x) ** 2 + (y - region.y) ** 2);
            if (distFromCenter > baseRadius * 1.1) {
                const toCenter = Math.atan2(region.y - y, region.x - x);
                angle = angle * 0.6 + toCenter * 0.4;
            }

            points.push({ x, y });
        }

        return points;
    },

    /**
     * Generate a branch spine from parent filament.
     */
    generateBranchSpine(parentSpine, branchIndex, region, seed) {
        const points = [];
        const branchPoint = parentSpine[branchIndex];
        const prevPoint = parentSpine[Math.max(0, branchIndex - 1)];

        const parentAngle = Math.atan2(branchPoint.y - prevPoint.y, branchPoint.x - prevPoint.x);
        const branchSide = this.seededRandom(seed) > 0.5 ? 1 : -1;
        let angle = parentAngle + branchSide * (Math.PI / 3 + (this.seededRandom(seed + 1) - 0.5) * 0.5);

        let x = branchPoint.x;
        let y = branchPoint.y;
        points.push({ x, y });

        const numPoints = 4 + Math.floor(this.seededRandom(seed + 2) * 4);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        for (let i = 1; i < numPoints; i++) {
            const stepLength = baseRadius * (0.08 + this.seededRandom(seed + i * 10) * 0.06);
            angle += this.gaussianRandom(seed + i * 10 + 3, 0, 0.2);

            x += Math.cos(angle) * stepLength;
            y += Math.sin(angle) * stepLength;
            points.push({ x, y });
        }

        return points;
    },

    /**
     * Generate a pillar structure extending toward a star.
     */
    generatePillarToStar(region, star, seed) {
        const points = [];
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Start from nebula edge toward star
        const angleToStar = Math.atan2(star.position_y - region.y, star.position_x - region.x);
        const startDist = baseRadius * 0.6;

        let x = region.x + Math.cos(angleToStar + Math.PI) * startDist * (0.5 + this.seededRandom(seed) * 0.5);
        let y = region.y + Math.sin(angleToStar + Math.PI) * startDist * (0.5 + this.seededRandom(seed + 1) * 0.5);

        points.push({ x, y });

        const numPoints = 5 + Math.floor(this.seededRandom(seed + 2) * 3);
        let angle = angleToStar;

        for (let i = 1; i < numPoints; i++) {
            const t = i / (numPoints - 1);
            // Interpolate toward star with some wobble
            const targetX = x + (star.position_x - x) * 0.3;
            const targetY = y + (star.position_y - y) * 0.3;

            const wobble = this.gaussianRandom(seed + i * 10, 0, baseRadius * 0.03);
            x = targetX + Math.cos(angle + Math.PI/2) * wobble;
            y = targetY + Math.sin(angle + Math.PI/2) * wobble;

            angle = Math.atan2(star.position_y - y, star.position_x - x);
            points.push({ x, y });
        }

        return points;
    },

    /**
     * Render diffuse halo around gas nebula.
     */
    renderGasHalo(region, palette, seed) {
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Outer halo
        const haloPath = this.createOrganicBlob(
            region.x, region.y,
            baseRadius * 1.5, baseRadius * 1.3,
            seed, 12
        );

        const halo = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        halo.setAttribute('d', haloPath);
        halo.setAttribute('fill', this.colorToRgba(palette.primary, region.density * 0.015));
        halo.setAttribute('filter', 'url(#gas-blur-heavy)');
        this.gasGroup.appendChild(halo);

        // Mid halo with secondary color
        const midPath = this.createOrganicBlob(
            region.x, region.y,
            baseRadius * 1.1, baseRadius * 0.95,
            seed + 100, 10
        );

        const mid = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        mid.setAttribute('d', midPath);
        mid.setAttribute('fill', this.colorToRgba(palette.secondary, region.density * 0.025));
        mid.setAttribute('filter', 'url(#gas-blur-medium)');
        this.gasGroup.appendChild(mid);
    },

    /**
     * Render a single gas filament with soft boundaries.
     */
    renderGasFilament(filament, palette, density, seed) {
        const { spine, width, type } = filament;
        if (spine.length < 2) return;

        // Create filled path along spine
        const contourPath = this.createFilamentPath(spine, width, seed);

        // Multiple soft layers
        const layers = type === 'pillar' ? [
            { blur: 'gas-blur-medium', opacity: density * 0.04, color: palette.primary },
            { blur: 'gas-blur-soft', opacity: density * 0.06, color: palette.secondary },
            { blur: 'gas-blur-light', opacity: density * 0.08, color: palette.tertiary }
        ] : [
            { blur: 'gas-blur-heavy', opacity: density * 0.025, color: palette.primary },
            { blur: 'gas-blur-medium', opacity: density * 0.04, color: palette.secondary },
            { blur: 'gas-blur-soft', opacity: density * 0.05, color: palette.tertiary }
        ];

        layers.forEach((layer) => {
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', contourPath);
            path.setAttribute('fill', this.colorToRgba(layer.color, layer.opacity));
            path.setAttribute('filter', `url(#${layer.blur})`);
            this.gasGroup.appendChild(path);
        });
    },

    /**
     * Render bright glowing regions around embedded stars.
     */
    renderStarFormingRegions(stars, region, palette, seed) {
        for (let i = 0; i < stars.length; i++) {
            const star = stars[i];
            const glowSeed = seed + i * 100;

            // Check if star is actually inside nebula
            const dx = star.position_x - region.x;
            const dy = star.position_y - region.y;
            const dist = Math.sqrt(dx*dx + dy*dy);
            const baseRadius = Math.max(region.radius_x, region.radius_y);

            if (dist > baseRadius) continue;

            // Glow intensity based on distance from center
            const intensity = 1 - (dist / baseRadius) * 0.5;
            const glowRadius = 15 + this.seededRandom(glowSeed) * 20;

            // Inner bright core
            const innerPath = this.createOrganicBlob(
                star.position_x, star.position_y,
                glowRadius * 0.4, glowRadius * 0.35,
                glowSeed, 6
            );

            const inner = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            inner.setAttribute('d', innerPath);
            inner.setAttribute('fill', this.colorToRgba(palette.glow, region.density * intensity * 0.15));
            inner.setAttribute('filter', 'url(#star-glow)');
            this.gasGroup.appendChild(inner);

            // Outer diffuse glow
            const outerPath = this.createOrganicBlob(
                star.position_x, star.position_y,
                glowRadius, glowRadius * 0.85,
                glowSeed + 50, 8
            );

            const outer = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            outer.setAttribute('d', outerPath);
            outer.setAttribute('fill', this.colorToRgba(palette.primary, region.density * intensity * 0.06));
            outer.setAttribute('filter', 'url(#gas-blur-soft)');
            this.gasGroup.appendChild(outer);
        }
    },

    /**
     * Render a dust cloud with sharper boundaries.
     * These are denser molecular clouds that block starlight.
     */
    renderDustCloud(region, seed) {
        const palette = this.palettes.dark;
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        // Dust clouds have more defined edges - less blur
        // Layer 1: Main body (sharp)
        const mainPath = this.createDustShape(region, seed);

        const main = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        main.setAttribute('d', mainPath);
        main.setAttribute('fill', this.colorToRgba(palette.primary, region.density * 0.7));
        main.setAttribute('filter', 'url(#dust-blur-sharp)');
        this.dustGroup.appendChild(main);

        // Layer 2: Outer transition (slightly softer)
        const transitionPath = this.createDustShape(region, seed + 100, 1.15);

        const transition = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        transition.setAttribute('d', transitionPath);
        transition.setAttribute('fill', this.colorToRgba(palette.secondary, region.density * 0.4));
        transition.setAttribute('filter', 'url(#dust-blur-soft)');
        this.dustGroup.insertBefore(transition, main);

        // Layer 3: Warm edge glow (infrared emission from heated dust)
        const edgePath = this.createDustShape(region, seed + 200, 1.25);

        const edge = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        edge.setAttribute('d', edgePath);
        edge.setAttribute('fill', this.colorToRgba(palette.edge, region.density * 0.08));
        edge.setAttribute('filter', 'url(#dust-blur-edge)');
        this.dustGroup.insertBefore(edge, transition);

        // Add internal structure - dense knots
        this.renderDustKnots(region, palette, seed + 500);
    },

    /**
     * Create dust cloud shape with rifts and defined boundaries.
     */
    createDustShape(region, seed, scale = 1.0) {
        const baseRadius = Math.max(region.radius_x, region.radius_y) * scale;
        const aspectRatio = region.radius_y / region.radius_x;

        // More angular, defined shape
        const numPoints = 10 + Math.floor(this.seededRandom(seed) * 6);
        const points = [];

        for (let i = 0; i < numPoints; i++) {
            const angle = (i / numPoints) * Math.PI * 2 + region.rotation;

            // Less smooth variation for sharper edges
            const radiusVar = 0.75 + this.seededRandom(seed + i * 17) * 0.5;

            // Add occasional deep indentations (rifts)
            const riftChance = this.seededRandom(seed + i * 23);
            const riftFactor = riftChance > 0.85 ? 0.6 : 1.0;

            const r = baseRadius * radiusVar * riftFactor;

            points.push({
                x: region.x + Math.cos(angle) * r,
                y: region.y + Math.sin(angle) * r * aspectRatio,
                angle
            });
        }

        // Build path with less smoothing
        let path = `M ${points[0].x} ${points[0].y}`;

        for (let i = 0; i < numPoints; i++) {
            const curr = points[i];
            const next = points[(i + 1) % numPoints];

            // Shorter control point distances for sharper curves
            const cpDist = Math.sqrt((next.x - curr.x) ** 2 + (next.y - curr.y) ** 2) * 0.25;

            const cp1x = curr.x + Math.cos(curr.angle + Math.PI/2) * cpDist;
            const cp1y = curr.y + Math.sin(curr.angle + Math.PI/2) * cpDist;
            const cp2x = next.x + Math.cos(next.angle - Math.PI/2) * cpDist;
            const cp2y = next.y + Math.sin(next.angle - Math.PI/2) * cpDist;

            path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Render dense knots within dust cloud.
     */
    renderDustKnots(region, palette, seed) {
        const numKnots = 2 + Math.floor(this.seededRandom(seed) * 3);
        const baseRadius = Math.max(region.radius_x, region.radius_y);

        for (let i = 0; i < numKnots; i++) {
            const knotSeed = seed + i * 100;

            // Position within cloud
            const knotAngle = this.seededRandom(knotSeed) * Math.PI * 2;
            const knotDist = baseRadius * (0.2 + this.seededRandom(knotSeed + 1) * 0.4);
            const knotX = region.x + Math.cos(knotAngle) * knotDist;
            const knotY = region.y + Math.sin(knotAngle) * knotDist;

            const knotRadius = 8 + this.seededRandom(knotSeed + 2) * 15;

            const knotPath = this.createOrganicBlob(knotX, knotY, knotRadius, knotRadius * 0.8, knotSeed, 6);

            const knot = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            knot.setAttribute('d', knotPath);
            knot.setAttribute('fill', this.colorToRgba(palette.primary, region.density * 0.85));
            knot.setAttribute('filter', 'url(#dust-blur-sharp)');
            this.dustGroup.appendChild(knot);
        }
    },

    /**
     * Create smooth filament path.
     */
    createFilamentPath(spine, baseWidth, seed) {
        if (spine.length < 2) return '';

        const upperEdge = [];
        const lowerEdge = [];

        for (let i = 0; i < spine.length; i++) {
            const p = spine[i];
            const prev = spine[Math.max(0, i - 1)];
            const next = spine[Math.min(spine.length - 1, i + 1)];

            const tangent = Math.atan2(next.y - prev.y, next.x - prev.x);
            const normal = tangent + Math.PI / 2;

            // Taper at ends, thick in middle
            const taper = Math.sin((i / (spine.length - 1)) * Math.PI);
            const widthVar = 0.8 + this.seededRandom(seed + i * 7) * 0.4;
            const localWidth = baseWidth * taper * widthVar;

            upperEdge.push({
                x: p.x + Math.cos(normal) * localWidth,
                y: p.y + Math.sin(normal) * localWidth
            });
            lowerEdge.push({
                x: p.x - Math.cos(normal) * localWidth,
                y: p.y - Math.sin(normal) * localWidth
            });
        }

        // Build bezier path
        let path = `M ${upperEdge[0].x} ${upperEdge[0].y}`;

        // Upper edge
        for (let i = 1; i < upperEdge.length; i++) {
            const prev = upperEdge[i - 1];
            const curr = upperEdge[i];
            const cpx = (prev.x + curr.x) / 2;
            const cpy = (prev.y + curr.y) / 2;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // End cap
        const lastU = upperEdge[upperEdge.length - 1];
        const lastL = lowerEdge[lowerEdge.length - 1];
        const lastS = spine[spine.length - 1];
        path += ` Q ${lastS.x} ${lastS.y} ${lastL.x} ${lastL.y}`;

        // Lower edge (reversed)
        for (let i = lowerEdge.length - 2; i >= 0; i--) {
            const prev = lowerEdge[i + 1];
            const curr = lowerEdge[i];
            const cpx = (prev.x + curr.x) / 2;
            const cpy = (prev.y + curr.y) / 2;
            path += ` Q ${cpx} ${cpy} ${curr.x} ${curr.y}`;
        }

        // Start cap
        const firstU = upperEdge[0];
        const firstL = lowerEdge[0];
        const firstS = spine[0];
        path += ` Q ${firstS.x} ${firstS.y} ${firstU.x} ${firstU.y}`;

        path += ' Z';
        return path;
    },

    /**
     * Create organic blob shape.
     */
    createOrganicBlob(cx, cy, rx, ry, seed, numPoints = 8) {
        const points = [];
        const angleStep = (Math.PI * 2) / numPoints;

        for (let i = 0; i < numPoints; i++) {
            const angle = i * angleStep;
            const radiusVar = 0.75 + this.seededRandom(seed + i * 13) * 0.5;
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
            const cpDist = Math.sqrt((next.x - curr.x) ** 2 + (next.y - curr.y) ** 2) * 0.35;

            const cp1x = curr.x + Math.cos(curr.angle + Math.PI/2) * cpDist;
            const cp1y = curr.y + Math.sin(curr.angle + Math.PI/2) * cpDist;
            const cp2x = next.x + Math.cos(next.angle - Math.PI/2) * cpDist;
            const cp2y = next.y + Math.sin(next.angle - Math.PI/2) * cpDist;

            path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
        }

        path += ' Z';
        return path;
    },

    /**
     * Procedural generation when no backend data.
     */
    generateProcedural(stars, width, height, seed) {
        // Find star clusters to host gas nebulae
        const clusters = this.findStarClusters(stars);

        // Generate emission nebulae around star clusters
        for (let i = 0; i < Math.min(3, clusters.length); i++) {
            const cluster = clusters[i];
            this.renderGasNebula({
                x: cluster.x,
                y: cluster.y,
                radius_x: 80 + this.seededRandom(seed + i * 100) * 80,
                radius_y: 70 + this.seededRandom(seed + i * 101) * 70,
                rotation: this.seededRandom(seed + i * 102) * Math.PI,
                density: 0.5 + this.seededRandom(seed + i * 103) * 0.3,
                nebula_type: 'emission'
            }, cluster.stars, seed + i * 10000);
        }

        // Find voids for dust clouds
        const voids = this.findVoids(stars, width, height);

        for (let i = 0; i < Math.min(2, voids.length); i++) {
            const void_ = voids[i];
            this.renderDustCloud({
                x: void_.x,
                y: void_.y,
                radius_x: 40 + this.seededRandom(seed + 500 + i) * 50,
                radius_y: 35 + this.seededRandom(seed + 501 + i) * 45,
                rotation: this.seededRandom(seed + 502 + i) * Math.PI,
                density: 0.6 + this.seededRandom(seed + 503 + i) * 0.3,
                nebula_type: 'dark'
            }, seed + 500000 + i * 10000);
        }

        // Background diffuse nebula
        if (clusters.length > 0) {
            const mainCluster = clusters[0];
            this.renderGasNebula({
                x: mainCluster.x,
                y: mainCluster.y,
                radius_x: width * 0.25,
                radius_y: height * 0.22,
                rotation: this.seededRandom(seed + 900) * Math.PI,
                density: 0.2,
                nebula_type: 'diffuse'
            }, mainCluster.stars, seed + 900000);
        }
    },

    /**
     * Find clusters of stars that would host nebulae.
     */
    findStarClusters(stars) {
        const clusters = [];
        const cellSize = 100;
        const cells = {};

        // Group stars into cells
        for (const star of stars) {
            const key = `${Math.floor(star.position_x / cellSize)},${Math.floor(star.position_y / cellSize)}`;
            if (!cells[key]) {
                cells[key] = [];
            }
            cells[key].push(star);
        }

        // Find dense cells
        for (const [key, cellStars] of Object.entries(cells)) {
            if (cellStars.length >= 2) {
                const [cx, cy] = key.split(',').map(Number);
                const avgX = cellStars.reduce((s, st) => s + st.position_x, 0) / cellStars.length;
                const avgY = cellStars.reduce((s, st) => s + st.position_y, 0) / cellStars.length;

                clusters.push({
                    x: avgX,
                    y: avgY,
                    density: cellStars.length,
                    stars: cellStars
                });
            }
        }

        return clusters.sort((a, b) => b.density - a.density);
    },

    findVoids(stars, width, height) {
        const voids = [];
        const cellSize = 120;

        for (let x = cellSize; x < width - cellSize; x += cellSize) {
            for (let y = cellSize; y < height - cellSize; y += cellSize) {
                let nearby = 0;
                for (const star of stars) {
                    if (Math.sqrt((star.position_x - x) ** 2 + (star.position_y - y) ** 2) < cellSize * 1.2) {
                        nearby++;
                    }
                }
                if (nearby === 0) {
                    voids.push({ x, y });
                }
            }
        }
        return voids;
    },

    colorToRgba(color, opacity) {
        return `rgba(${color.r}, ${color.g}, ${color.b}, ${Math.max(0, Math.min(1, opacity))})`;
    },

    updateViewBox(viewX, viewY, zoom, canvasWidth, canvasHeight) {
        if (!this.svg) return;
        const worldWidth = canvasWidth / zoom;
        const worldHeight = canvasHeight / zoom;
        this.svg.setAttribute('viewBox', `${viewX - worldWidth/2} ${viewY - worldHeight/2} ${worldWidth} ${worldHeight}`);
    }
};

window.NebulaSVG = NebulaSVG;
