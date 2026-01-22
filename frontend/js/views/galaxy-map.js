/**
 * Stars Nova Web - Galaxy Map
 * Canvas-based star map with pan/zoom and selection.
 * Ported from original Stars! visual style.
 */

const GalaxyMap = {
    // Canvas and context
    canvas: null,
    ctx: null,

    // View state
    viewX: 0,          // Camera position (world coordinates)
    viewY: 0,
    zoom: 1.0,         // Zoom level (1.0 = 100%)
    minZoom: 0.25,
    maxZoom: 4.0,

    // Interaction state
    isDragging: false,
    dragStartX: 0,
    dragStartY: 0,
    viewStartX: 0,
    viewStartY: 0,

    // Selection
    selectedStar: null,
    selectedFleet: null,
    hoverStar: null,
    hoverFleet: null,

    // Visual settings
    starRadius: 6,
    fleetRadius: 4,
    selectionRadius: 12,
    gridSize: 100,
    showGrid: true,
    showNames: true,
    showNebulae: true,
    showScannerRange: false,

    // Distance measuring state
    isMeasuring: false,
    measureStart: null,
    measureEnd: null,

    // Nebulae cache (generated once per game)
    nebulae: null,
    nebulaeSeed: 0,

    // Colors (matching Stars! original)
    colors: {
        background: '#050510',
        grid: '#101030',
        gridMajor: '#181840',
        starUncolonized: '#606060',
        starFriendly: '#00ff00',
        starEnemy: '#ff0000',
        starNeutral: '#ffff00',
        fleetFriendly: '#00cc00',
        fleetEnemy: '#cc0000',
        selection: '#ffffff',
        hover: '#aaaaff',
        waypoint: '#00ffff',
        waypointLine: '#006666',
        text: '#c0c0c0',
        textHighlight: '#ffff00',
        scannerRange: 'rgba(0, 255, 0, 0.15)',
        scannerRangeBorder: 'rgba(0, 255, 0, 0.4)',
        measureLine: '#ffff00',
        measureText: '#ffff00'
    },

    /**
     * Initialize the galaxy map.
     */
    init(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('Galaxy map canvas not found:', canvasId);
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.resize();

        // Initialize SVG nebula layer
        if (window.NebulaSVG) {
            NebulaSVG.init('nebula-layer');
        }

        // Bind events
        this.bindEvents();

        // Listen to game state changes
        GameState.on('gameLoaded', () => this.onGameLoaded());
        GameState.on('gameCreated', () => this.onGameLoaded());
        GameState.on('turnGenerated', () => this.render());
        GameState.on('starSelected', (star) => this.onStarSelected(star));
        GameState.on('fleetSelected', (fleet) => this.onFleetSelected(fleet));
        GameState.on('selectionCleared', () => this.onSelectionCleared());

        // Initial render
        this.render();

        console.log('Galaxy map initialized');
    },

    /**
     * Resize canvas to container.
     */
    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.render();
    },

    /**
     * Bind mouse/touch events.
     */
    bindEvents() {
        // Resize
        window.addEventListener('resize', () => this.resize());

        // Mouse events
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('mouseleave', (e) => this.onMouseLeave(e));
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));

        // Touch events
        this.canvas.addEventListener('touchstart', (e) => this.onTouchStart(e));
        this.canvas.addEventListener('touchmove', (e) => this.onTouchMove(e));
        this.canvas.addEventListener('touchend', (e) => this.onTouchEnd(e));

        // Keyboard
        document.addEventListener('keydown', (e) => this.onKeyDown(e));
    },

    /**
     * Convert screen coordinates to world coordinates.
     */
    screenToWorld(screenX, screenY) {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        return {
            x: (screenX - centerX) / this.zoom + this.viewX,
            y: (screenY - centerY) / this.zoom + this.viewY
        };
    },

    /**
     * Convert world coordinates to screen coordinates.
     */
    worldToScreen(worldX, worldY) {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        return {
            x: (worldX - this.viewX) * this.zoom + centerX,
            y: (worldY - this.viewY) * this.zoom + centerY
        };
    },

    /**
     * Mouse down - start drag, select, or measure distance.
     */
    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (e.button === 0) {  // Left click
            const worldPos = this.screenToWorld(x, y);

            // Shift+click for distance measuring
            if (e.shiftKey) {
                this.isMeasuring = true;
                this.measureStart = { x: worldPos.x, y: worldPos.y };
                this.measureEnd = { x: worldPos.x, y: worldPos.y };
                this.canvas.style.cursor = 'crosshair';
                this.render();
                return;
            }

            // Check for star/fleet click first
            const clicked = this.findObjectAt(worldPos.x, worldPos.y);

            if (clicked) {
                if (clicked.type === 'star') {
                    GameState.selectStar(clicked.object);
                } else if (clicked.type === 'fleet') {
                    GameState.selectFleet(clicked.object);
                }
            } else {
                // Start panning
                this.isDragging = true;
                this.dragStartX = x;
                this.dragStartY = y;
                this.viewStartX = this.viewX;
                this.viewStartY = this.viewY;
                this.canvas.style.cursor = 'grabbing';
            }
        }
    },

    /**
     * Mouse move - pan, hover, or measure.
     */
    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (this.isMeasuring) {
            // Update measure end position
            const worldPos = this.screenToWorld(x, y);
            this.measureEnd = { x: worldPos.x, y: worldPos.y };
            this.render();
            return;
        }

        if (this.isDragging) {
            // Pan view
            const dx = (x - this.dragStartX) / this.zoom;
            const dy = (y - this.dragStartY) / this.zoom;
            this.viewX = this.viewStartX - dx;
            this.viewY = this.viewStartY - dy;
            this.render();
        } else {
            // Check hover
            const worldPos = this.screenToWorld(x, y);
            const hovered = this.findObjectAt(worldPos.x, worldPos.y);

            const oldHoverStar = this.hoverStar;
            const oldHoverFleet = this.hoverFleet;

            this.hoverStar = null;
            this.hoverFleet = null;

            if (hovered) {
                if (hovered.type === 'star') {
                    this.hoverStar = hovered.object;
                    this.canvas.style.cursor = 'pointer';
                } else if (hovered.type === 'fleet') {
                    this.hoverFleet = hovered.object;
                    this.canvas.style.cursor = 'pointer';
                }
            } else {
                this.canvas.style.cursor = 'grab';
            }

            // Re-render if hover changed
            if (oldHoverStar !== this.hoverStar || oldHoverFleet !== this.hoverFleet) {
                this.render();
            }
        }
    },

    /**
     * Mouse up - end drag or measuring.
     */
    onMouseUp(e) {
        if (this.isMeasuring) {
            // Keep the measurement visible until next click or Escape
            this.isMeasuring = false;
            this.canvas.style.cursor = 'grab';
            return;
        }
        this.isDragging = false;
        this.canvas.style.cursor = 'grab';
    },

    /**
     * Mouse leave.
     */
    onMouseLeave(e) {
        this.isDragging = false;
        this.hoverStar = null;
        this.hoverFleet = null;
        this.canvas.style.cursor = 'grab';
        this.render();
    },

    /**
     * Mouse wheel - zoom.
     */
    onWheel(e) {
        e.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Get world position under mouse before zoom
        const worldBefore = this.screenToWorld(mouseX, mouseY);

        // Adjust zoom
        const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoom * zoomDelta));

        // Get world position under mouse after zoom
        const worldAfter = this.screenToWorld(mouseX, mouseY);

        // Adjust view to keep mouse position stable
        this.viewX += worldBefore.x - worldAfter.x;
        this.viewY += worldBefore.y - worldAfter.y;

        this.render();
    },

    /**
     * Double click - center on object.
     */
    onDoubleClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const worldPos = this.screenToWorld(x, y);

        // Center view on clicked position
        this.viewX = worldPos.x;
        this.viewY = worldPos.y;
        this.render();
    },

    /**
     * Touch start.
     */
    onTouchStart(e) {
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            this.onMouseDown({ clientX: touch.clientX, clientY: touch.clientY, button: 0 });
        }
    },

    /**
     * Touch move.
     */
    onTouchMove(e) {
        if (e.touches.length === 1) {
            e.preventDefault();
            const touch = e.touches[0];
            this.onMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
        }
    },

    /**
     * Touch end.
     */
    onTouchEnd(e) {
        this.onMouseUp(e);
    },

    /**
     * Keyboard shortcuts.
     */
    onKeyDown(e) {
        const panSpeed = 50 / this.zoom;

        switch (e.key) {
            case 'ArrowUp':
            case 'w':
                this.viewY -= panSpeed;
                this.render();
                break;
            case 'ArrowDown':
            case 's':
                this.viewY += panSpeed;
                this.render();
                break;
            case 'ArrowLeft':
            case 'a':
                this.viewX -= panSpeed;
                this.render();
                break;
            case 'ArrowRight':
            case 'd':
                this.viewX += panSpeed;
                this.render();
                break;
            case '+':
            case '=':
                this.zoom = Math.min(this.maxZoom, this.zoom * 1.2);
                this.render();
                break;
            case '-':
                this.zoom = Math.max(this.minZoom, this.zoom / 1.2);
                this.render();
                break;
            case 'Home':
                this.centerOnHomeworld();
                break;
            case 'g':
                this.showGrid = !this.showGrid;
                this.render();
                break;
            case 'n':
                this.showNames = !this.showNames;
                this.render();
                break;
            case 'S':
                // Shift+S for scanner range toggle
                if (e.shiftKey) {
                    this.showScannerRange = !this.showScannerRange;
                    this.render();
                }
                break;
            case 'Escape':
                GameState.clearSelection();
                // Also cancel measuring
                if (this.isMeasuring) {
                    this.isMeasuring = false;
                    this.measureStart = null;
                    this.measureEnd = null;
                    this.render();
                }
                break;
        }
    },

    /**
     * Find object at world coordinates.
     */
    findObjectAt(worldX, worldY) {
        const threshold = this.starRadius * 2 / this.zoom;

        // Check fleets first (on top)
        for (const fleet of GameState.fleets) {
            const dx = fleet.position_x - worldX;
            const dy = fleet.position_y - worldY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < threshold) {
                return { type: 'fleet', object: fleet };
            }
        }

        // Check stars
        for (const star of GameState.stars) {
            const dx = star.position_x - worldX;
            const dy = star.position_y - worldY;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < threshold) {
                return { type: 'star', object: star };
            }
        }

        return null;
    },

    /**
     * Center view on homeworld.
     */
    centerOnHomeworld() {
        // Find player's homeworld (first star with colonists owned by player)
        const homeworld = GameState.stars.find(s => s.colonists > 0 && s.owner === 1);
        if (homeworld) {
            this.viewX = homeworld.position_x;
            this.viewY = homeworld.position_y;
            this.render();
        }
    },

    /**
     * Game loaded handler.
     */
    onGameLoaded() {
        this.selectedStar = null;
        this.selectedFleet = null;
        // Regenerate nebulae for this game
        this.nebulae = null;

        // Generate SVG nebulae
        if (window.NebulaSVG && GameState.stars && GameState.stars.length > 0) {
            const universeSize = GameState.game?.universe_size || 'medium';
            const sizes = { tiny: 200, small: 400, medium: 600, large: 800, huge: 1000 };
            const size = sizes[universeSize] || 600;
            const seed = GameState.game ? (GameState.game.id.charCodeAt(0) || 1) : Date.now();
            NebulaSVG.generate(GameState.stars, size, size, seed);
        }

        this.centerOnHomeworld();
    },

    /**
     * Star selected handler.
     */
    onStarSelected(star) {
        this.selectedStar = star;
        this.selectedFleet = null;
        this.render();
    },

    /**
     * Fleet selected handler.
     */
    onFleetSelected(fleet) {
        this.selectedFleet = fleet;
        this.selectedStar = null;
        this.render();
    },

    /**
     * Selection cleared handler.
     */
    onSelectionCleared() {
        this.selectedStar = null;
        this.selectedFleet = null;
        this.render();
    },

    /**
     * Main render function.
     */
    render() {
        if (!this.ctx) return;

        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        // Clear with transparent background (SVG shows through)
        ctx.clearRect(0, 0, w, h);

        // Update SVG viewBox to match canvas view
        if (window.NebulaSVG) {
            NebulaSVG.updateViewBox(this.viewX, this.viewY, this.zoom, w, h);
        }

        // Draw grid
        if (this.showGrid) {
            this.renderGrid();
        }

        // Draw waypoint lines for selected fleet
        if (this.selectedFleet) {
            this.renderWaypoints(this.selectedFleet);
        }

        // Draw stars
        for (const star of GameState.stars) {
            this.renderStar(star);
        }

        // Draw fleets
        for (const fleet of GameState.fleets) {
            this.renderFleet(fleet);
        }

        // Draw scanner range overlay
        if (this.showScannerRange) {
            this.renderScannerRanges();
        }

        // Draw distance measuring line
        if (this.measureStart && this.measureEnd) {
            this.renderMeasureLine();
        }

        // Draw selection indicator
        if (this.selectedStar) {
            this.renderSelection(this.selectedStar.position_x, this.selectedStar.position_y);
        }
        if (this.selectedFleet) {
            this.renderSelection(this.selectedFleet.position_x, this.selectedFleet.position_y);
        }

        // Draw hover indicator
        if (this.hoverStar && this.hoverStar !== this.selectedStar) {
            this.renderHover(this.hoverStar.position_x, this.hoverStar.position_y);
        }
        if (this.hoverFleet && this.hoverFleet !== this.selectedFleet) {
            this.renderHover(this.hoverFleet.position_x, this.hoverFleet.position_y);
        }

        // Draw HUD
        this.renderHUD();
    },

    /**
     * Render grid.
     */
    renderGrid() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;

        // Calculate visible area in world coordinates
        const topLeft = this.screenToWorld(0, 0);
        const bottomRight = this.screenToWorld(w, h);

        // Grid lines
        const gridStep = this.gridSize;
        const majorStep = gridStep * 5;

        const startX = Math.floor(topLeft.x / gridStep) * gridStep;
        const startY = Math.floor(topLeft.y / gridStep) * gridStep;

        ctx.lineWidth = 1;

        // Minor grid
        ctx.strokeStyle = this.colors.grid;
        ctx.beginPath();
        for (let x = startX; x <= bottomRight.x; x += gridStep) {
            if (x % majorStep !== 0) {
                const screen = this.worldToScreen(x, 0);
                ctx.moveTo(screen.x, 0);
                ctx.lineTo(screen.x, h);
            }
        }
        for (let y = startY; y <= bottomRight.y; y += gridStep) {
            if (y % majorStep !== 0) {
                const screen = this.worldToScreen(0, y);
                ctx.moveTo(0, screen.y);
                ctx.lineTo(w, screen.y);
            }
        }
        ctx.stroke();

        // Major grid
        ctx.strokeStyle = this.colors.gridMajor;
        ctx.beginPath();
        for (let x = startX; x <= bottomRight.x; x += gridStep) {
            if (x % majorStep === 0) {
                const screen = this.worldToScreen(x, 0);
                ctx.moveTo(screen.x, 0);
                ctx.lineTo(screen.x, h);
            }
        }
        for (let y = startY; y <= bottomRight.y; y += gridStep) {
            if (y % majorStep === 0) {
                const screen = this.worldToScreen(0, y);
                ctx.moveTo(0, screen.y);
                ctx.lineTo(w, screen.y);
            }
        }
        ctx.stroke();
    },

    /**
     * Generate nebulae using NebulaDesigner if available.
     */
    generateNebulae(seed = 0) {
        this.nebulaeSeed = seed;

        // Use NebulaDesigner if available and we have stars
        if (window.NebulaDesigner && GameState.stars && GameState.stars.length > 0) {
            const universeSize = GameState.game?.universe_size || 'medium';
            const sizes = { tiny: 200, small: 400, medium: 600, large: 800, huge: 1000 };
            const size = sizes[universeSize] || 600;
            this.nebulae = NebulaDesigner.generate(GameState.stars, size, size, seed);
        } else {
            // Fallback to simple generation
            this.nebulae = this.generateSimpleNebulae(seed);
        }
    },

    /**
     * Simple nebula generation fallback.
     */
    generateSimpleNebulae(seed) {
        const nebulae = [];
        const seededRandom = (s) => {
            const x = Math.sin(s) * 10000;
            return x - Math.floor(x);
        };

        // Single consistent blue-purple color scheme
        const baseColor = { r: 70, g: 90, b: 140 };

        const count = 8 + Math.floor(seededRandom(seed * 7) * 6);

        for (let i = 0; i < count; i++) {
            const s = seed * 100 + i;
            const centerX = seededRandom(s * 11) * 800 + 100;
            const centerY = seededRandom(s * 13) * 800 + 100;
            const baseRadius = 60 + seededRandom(s * 17) * 100;

            const particleCount = 12 + Math.floor(seededRandom(s * 19) * 12);

            for (let j = 0; j < particleCount; j++) {
                const ps = s * 1000 + j;
                const angle = seededRandom(ps * 23) * Math.PI * 2;
                const dist = seededRandom(ps * 29) * baseRadius;

                nebulae.push({
                    x: centerX + Math.cos(angle) * dist,
                    y: centerY + Math.sin(angle) * dist,
                    radius: 25 + seededRandom(ps * 43) * 40,
                    color: {
                        r: baseColor.r + Math.floor(seededRandom(ps * 47) * 20 - 10),
                        g: baseColor.g + Math.floor(seededRandom(ps * 53) * 20 - 10),
                        b: baseColor.b + Math.floor(seededRandom(ps * 59) * 20 - 10)
                    },
                    opacity: 0.12 + seededRandom(ps * 61) * 0.08,
                    scaleX: 0.8 + seededRandom(ps * 67) * 0.4,
                    scaleY: 0.8 + seededRandom(ps * 71) * 0.4,
                    rotation: seededRandom(ps * 73) * Math.PI * 2
                });
            }
        }
        return nebulae;
    },

    /**
     * Render nebulae with sharper edges and elongated shapes.
     */
    renderNebulae() {
        if (!this.nebulae || this.nebulae.length === 0) {
            const seed = GameState.game ? (GameState.game.id.charCodeAt(0) || 1) : Date.now();
            this.generateNebulae(seed);
        }

        const ctx = this.ctx;

        for (const nebula of this.nebulae) {
            const screenPos = this.worldToScreen(nebula.x, nebula.y);

            // Support both old (radius) and new (width/height) formats
            const hasWidthHeight = nebula.width !== undefined && nebula.height !== undefined;
            const screenWidth = hasWidthHeight ? nebula.width * this.zoom : (nebula.radius || 30) * this.zoom;
            const screenHeight = hasWidthHeight ? nebula.height * this.zoom : screenWidth;
            const maxDim = Math.max(screenWidth, screenHeight);

            // Skip if off screen
            const margin = maxDim * 2;
            if (screenPos.x < -margin || screenPos.x > this.canvas.width + margin ||
                screenPos.y < -margin || screenPos.y > this.canvas.height + margin) {
                continue;
            }

            ctx.save();
            ctx.translate(screenPos.x, screenPos.y);
            ctx.rotate(nebula.rotation || 0);

            // Apply scale for old format, or use width/height ratio for new format
            if (!hasWidthHeight) {
                ctx.scale(nebula.scaleX || 1, nebula.scaleY || 1);
            }

            const { r, g, b } = nebula.color;
            const opacity = nebula.opacity || 0.15;

            // Create elliptical gradient by scaling
            if (hasWidthHeight) {
                const scaleRatio = screenHeight / screenWidth;
                ctx.scale(1, scaleRatio);

                // Sharper gradient for more defined edges
                const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, screenWidth);

                if (nebula.type === 'core') {
                    gradient.addColorStop(0, `rgba(${r + 30}, ${g + 30}, ${b + 30}, ${opacity * 1.5})`);
                    gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, ${opacity})`);
                    gradient.addColorStop(0.8, `rgba(${r}, ${g}, ${b}, ${opacity * 0.3})`);
                    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                } else if (nebula.type === 'dust') {
                    // Darker, more diffuse
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${opacity * 0.8})`);
                    gradient.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, ${opacity * 0.4})`);
                    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                } else {
                    // Wispy/filament - sharper edges
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${opacity})`);
                    gradient.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${opacity * 0.8})`);
                    gradient.addColorStop(0.7, `rgba(${r}, ${g}, ${b}, ${opacity * 0.3})`);
                    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                }

                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(0, 0, screenWidth, 0, Math.PI * 2);
                ctx.fill();
            } else {
                // Old format (radius only)
                const screenRadius = screenWidth;
                const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, screenRadius);

                if (nebula.isBright) {
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${opacity * 1.8})`);
                    gradient.addColorStop(0.4, `rgba(${r}, ${g}, ${b}, ${opacity * 1.2})`);
                    gradient.addColorStop(0.75, `rgba(${r}, ${g}, ${b}, ${opacity * 0.5})`);
                    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                } else {
                    gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${opacity})`);
                    gradient.addColorStop(0.6, `rgba(${r}, ${g}, ${b}, ${opacity * 0.7})`);
                    gradient.addColorStop(0.85, `rgba(${r}, ${g}, ${b}, ${opacity * 0.2})`);
                    gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                }

                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(0, 0, screenRadius, 0, Math.PI * 2);
                ctx.fill();
            }

            ctx.restore();
        }
    },

    // Spectral class colors (RGB values matching astronomical colors)
    spectralColors: {
        'O': { r: 155, g: 176, b: 255 },  // Blue
        'B': { r: 170, g: 191, b: 255 },  // Blue-white
        'A': { r: 202, g: 215, b: 255 },  // White
        'F': { r: 248, g: 247, b: 255 },  // Yellow-white
        'G': { r: 255, g: 244, b: 234 },  // Yellow
        'K': { r: 255, g: 210, b: 161 },  // Orange
        'M': { r: 255, g: 180, b: 100 },  // Red-orange
    },

    /**
     * Get color for a star based on spectral class.
     */
    getSpectralColor(star) {
        const spectralClass = star.spectral_class || 'G';
        const colors = this.spectralColors[spectralClass] || this.spectralColors['G'];
        return `rgb(${colors.r}, ${colors.g}, ${colors.b})`;
    },

    /**
     * Render a star.
     */
    renderStar(star) {
        const ctx = this.ctx;
        const pos = this.worldToScreen(star.position_x, star.position_y);

        // Base radius scaled by star_radius (normalized, 1.0 = Sun)
        const starRadius = star.star_radius || 1.0;
        const sizeMultiplier = Math.min(2.5, Math.max(0.5, 0.8 + Math.log10(starRadius + 0.1) * 0.5));
        const radius = this.starRadius * this.zoom * sizeMultiplier;

        // Skip if off screen
        if (pos.x < -radius * 3 || pos.x > this.canvas.width + radius * 3 ||
            pos.y < -radius * 3 || pos.y > this.canvas.height + radius * 3) {
            return;
        }

        // Get spectral color
        const spectralClass = star.spectral_class || 'G';
        const colors = this.spectralColors[spectralClass] || this.spectralColors['G'];

        // Draw glow for larger/hotter stars
        if (starRadius > 5 || spectralClass === 'O' || spectralClass === 'B') {
            const glowRadius = radius * 2.5;
            const gradient = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, glowRadius);
            gradient.addColorStop(0, `rgba(${colors.r}, ${colors.g}, ${colors.b}, 0.4)`);
            gradient.addColorStop(0.5, `rgba(${colors.r}, ${colors.g}, ${colors.b}, 0.15)`);
            gradient.addColorStop(1, `rgba(${colors.r}, ${colors.g}, ${colors.b}, 0)`);
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, glowRadius, 0, Math.PI * 2);
            ctx.fill();
        }

        // Determine star color - spectral for uncolonized, ownership for colonized
        let fillColor;
        if (star.colonists > 0) {
            if (star.owner === 1) {  // Player
                fillColor = this.colors.starFriendly;
            } else if (star.owner > 1) {  // Enemy
                fillColor = this.colors.starEnemy;
            } else {
                fillColor = `rgb(${colors.r}, ${colors.g}, ${colors.b})`;
            }
        } else {
            fillColor = `rgb(${colors.r}, ${colors.g}, ${colors.b})`;
        }

        // Draw star core
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = fillColor;
        ctx.fill();

        // Add slight highlight for 3D effect
        if (radius > 2) {
            const highlight = ctx.createRadialGradient(
                pos.x - radius * 0.3, pos.y - radius * 0.3, 0,
                pos.x, pos.y, radius
            );
            highlight.addColorStop(0, 'rgba(255, 255, 255, 0.3)');
            highlight.addColorStop(0.5, 'rgba(255, 255, 255, 0.1)');
            highlight.addColorStop(1, 'rgba(255, 255, 255, 0)');
            ctx.fillStyle = highlight;
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fill();
        }

        // Draw ownership ring for colonized stars
        if (star.colonists > 0) {
            const ringColor = star.owner === 1 ? this.colors.starFriendly : this.colors.starEnemy;
            ctx.strokeStyle = ringColor;
            ctx.lineWidth = Math.max(1, 2 * this.zoom);
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius + 2 * this.zoom, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw name if enabled and zoomed in enough
        if (this.showNames && this.zoom >= 0.5) {
            ctx.font = `${Math.round(10 * this.zoom)}px sans-serif`;
            ctx.fillStyle = this.colors.text;
            ctx.textAlign = 'center';
            ctx.fillText(star.name, pos.x, pos.y + radius + 12 * this.zoom);
        }
    },

    /**
     * Render a fleet.
     */
    renderFleet(fleet) {
        const ctx = this.ctx;
        const pos = this.worldToScreen(fleet.position_x, fleet.position_y);
        const radius = this.fleetRadius * this.zoom;

        // Skip if off screen
        if (pos.x < -radius || pos.x > this.canvas.width + radius ||
            pos.y < -radius || pos.y > this.canvas.height + radius) {
            return;
        }

        // Determine color based on ownership
        let color = fleet.owner === 1 ? this.colors.fleetFriendly : this.colors.fleetEnemy;

        // Draw fleet as diamond
        ctx.beginPath();
        ctx.moveTo(pos.x, pos.y - radius);
        ctx.lineTo(pos.x + radius, pos.y);
        ctx.lineTo(pos.x, pos.y + radius);
        ctx.lineTo(pos.x - radius, pos.y);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();

        // Draw name if selected or zoomed in
        if ((fleet === this.selectedFleet || this.zoom >= 1.0) && this.showNames) {
            ctx.font = `${Math.round(9 * this.zoom)}px sans-serif`;
            ctx.fillStyle = this.colors.text;
            ctx.textAlign = 'center';
            ctx.fillText(fleet.name, pos.x, pos.y + radius + 10 * this.zoom);
        }
    },

    /**
     * Render waypoints for a fleet.
     */
    renderWaypoints(fleet) {
        if (!fleet.waypoints || fleet.waypoints.length === 0) return;

        const ctx = this.ctx;
        ctx.strokeStyle = this.colors.waypointLine;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);

        // Start from fleet position
        let prevPos = this.worldToScreen(fleet.position_x, fleet.position_y);

        ctx.beginPath();
        ctx.moveTo(prevPos.x, prevPos.y);

        for (const waypoint of fleet.waypoints) {
            const wpPos = this.worldToScreen(waypoint.position_x, waypoint.position_y);
            ctx.lineTo(wpPos.x, wpPos.y);

            // Draw waypoint marker
            ctx.fillStyle = this.colors.waypoint;
            ctx.fillRect(wpPos.x - 3, wpPos.y - 3, 6, 6);
        }

        ctx.stroke();
        ctx.setLineDash([]);
    },

    /**
     * Render selection indicator.
     */
    renderSelection(worldX, worldY) {
        const ctx = this.ctx;
        const pos = this.worldToScreen(worldX, worldY);
        const radius = this.selectionRadius * this.zoom;

        ctx.strokeStyle = this.colors.selection;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.stroke();
    },

    /**
     * Render hover indicator.
     */
    renderHover(worldX, worldY) {
        const ctx = this.ctx;
        const pos = this.worldToScreen(worldX, worldY);
        const radius = this.selectionRadius * this.zoom;

        ctx.strokeStyle = this.colors.hover;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
    },

    /**
     * Render HUD overlay.
     */
    renderHUD() {
        const ctx = this.ctx;
        const padding = 10;

        // Zoom indicator (bottom left)
        ctx.font = '12px monospace';
        ctx.fillStyle = this.colors.text;
        ctx.textAlign = 'left';
        ctx.fillText(`Zoom: ${Math.round(this.zoom * 100)}%`, padding, this.canvas.height - padding);

        // Turn indicator (top right)
        if (GameState.game) {
            ctx.textAlign = 'right';
            ctx.fillText(`Turn ${GameState.game.turn}`, this.canvas.width - padding, padding + 12);
        }

        // Controls hint (bottom right)
        ctx.textAlign = 'right';
        ctx.fillStyle = '#666666';
        ctx.fillText('WASD: Pan | +/-: Zoom | G: Grid | N: Names | Shift+S: Scanner | Shift+Drag: Measure',
            this.canvas.width - padding, this.canvas.height - padding);
    },

    /**
     * Render scanner range circles for player's fleets.
     */
    renderScannerRanges() {
        const ctx = this.ctx;

        // Draw scanner ranges for player's fleets
        for (const fleet of GameState.fleets) {
            if (fleet.owner !== 1) continue;  // Only player fleets

            // Get scanner range from fleet (default to 50 ly if not set)
            const scanRange = fleet.scan_range || fleet.scanner_range || 50;
            if (scanRange <= 0) continue;

            const pos = this.worldToScreen(fleet.position_x, fleet.position_y);
            const radius = scanRange * this.zoom;

            // Draw filled circle
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = this.colors.scannerRange;
            ctx.fill();

            // Draw border
            ctx.strokeStyle = this.colors.scannerRangeBorder;
            ctx.lineWidth = 1;
            ctx.stroke();
        }

        // Also draw scanner ranges for player's colonized stars
        for (const star of GameState.stars) {
            if (star.owner !== 1 || star.colonists <= 0) continue;

            // Colonized planets have a base scanner range
            const scanRange = 30;  // Base planetary scanner range
            const pos = this.worldToScreen(star.position_x, star.position_y);
            const radius = scanRange * this.zoom;

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = this.colors.scannerRange;
            ctx.fill();

            ctx.strokeStyle = this.colors.scannerRangeBorder;
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    },

    /**
     * Render distance measuring line.
     */
    renderMeasureLine() {
        if (!this.measureStart || !this.measureEnd) return;

        const ctx = this.ctx;
        const start = this.worldToScreen(this.measureStart.x, this.measureStart.y);
        const end = this.worldToScreen(this.measureEnd.x, this.measureEnd.y);

        // Calculate distance in light years
        const dx = this.measureEnd.x - this.measureStart.x;
        const dy = this.measureEnd.y - this.measureStart.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Draw dashed line
        ctx.strokeStyle = this.colors.measureLine;
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.moveTo(start.x, start.y);
        ctx.lineTo(end.x, end.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw start and end markers
        ctx.fillStyle = this.colors.measureLine;
        ctx.beginPath();
        ctx.arc(start.x, start.y, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(end.x, end.y, 5, 0, Math.PI * 2);
        ctx.fill();

        // Draw distance label at midpoint
        const midX = (start.x + end.x) / 2;
        const midY = (start.y + end.y) / 2;
        const label = `${distance.toFixed(1)} ly`;

        ctx.font = 'bold 14px monospace';
        ctx.fillStyle = this.colors.measureText;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';

        // Draw background for text
        const textWidth = ctx.measureText(label).width;
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.fillRect(midX - textWidth / 2 - 4, midY - 20, textWidth + 8, 18);

        // Draw text
        ctx.fillStyle = this.colors.measureText;
        ctx.fillText(label, midX, midY - 5);
    },

    /**
     * Center on specific coordinates.
     */
    centerOn(x, y) {
        this.viewX = x;
        this.viewY = y;
        this.render();
    },

    /**
     * Set zoom level.
     */
    setZoom(level) {
        this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, level));
        this.render();
    },

    /**
     * Toggle star names visibility.
     */
    toggleNames() {
        this.showNames = !this.showNames;
        this.render();
    },

    /**
     * Toggle scanner range overlay.
     */
    toggleScannerRange() {
        this.showScannerRange = !this.showScannerRange;
        this.render();
    },

    /**
     * Toggle grid visibility.
     */
    toggleGrid() {
        this.showGrid = !this.showGrid;
        this.render();
    },

    /**
     * Zoom to fit all stars in view.
     */
    zoomToFit() {
        const stars = GameState.stars || [];
        if (stars.length === 0) return;

        // Find bounds
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        for (const star of stars) {
            minX = Math.min(minX, star.x);
            maxX = Math.max(maxX, star.x);
            minY = Math.min(minY, star.y);
            maxY = Math.max(maxY, star.y);
        }

        // Add padding
        const padding = 50;
        minX -= padding;
        maxX += padding;
        minY -= padding;
        maxY += padding;

        // Calculate zoom to fit
        const worldWidth = maxX - minX;
        const worldHeight = maxY - minY;
        const screenWidth = this.canvas.width;
        const screenHeight = this.canvas.height;

        const zoomX = screenWidth / worldWidth;
        const zoomY = screenHeight / worldHeight;
        this.zoom = Math.min(zoomX, zoomY, this.maxZoom);
        this.zoom = Math.max(this.zoom, this.minZoom);

        // Center on midpoint
        this.viewX = (minX + maxX) / 2;
        this.viewY = (minY + maxY) / 2;

        this.render();
    }
};

// Export
window.GalaxyMap = GalaxyMap;
