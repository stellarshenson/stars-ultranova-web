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
        textHighlight: '#ffff00'
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
     * Mouse down - start drag or select.
     */
    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (e.button === 0) {  // Left click
            // Check for star/fleet click first
            const worldPos = this.screenToWorld(x, y);
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
     * Mouse move - pan or hover.
     */
    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

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
     * Mouse up - end drag.
     */
    onMouseUp(e) {
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
            case 'Escape':
                GameState.clearSelection();
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

        // Clear
        ctx.fillStyle = this.colors.background;
        ctx.fillRect(0, 0, w, h);

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
     * Render a star.
     */
    renderStar(star) {
        const ctx = this.ctx;
        const pos = this.worldToScreen(star.position_x, star.position_y);
        const radius = this.starRadius * this.zoom;

        // Skip if off screen
        if (pos.x < -radius || pos.x > this.canvas.width + radius ||
            pos.y < -radius || pos.y > this.canvas.height + radius) {
            return;
        }

        // Determine color based on ownership
        let color = this.colors.starUncolonized;
        if (star.colonists > 0) {
            if (star.owner === 1) {  // Player
                color = this.colors.starFriendly;
            } else if (star.owner > 1) {  // Enemy
                color = this.colors.starEnemy;
            }
        }

        // Draw star
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

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
        ctx.fillText('WASD/Arrows: Pan | +/-: Zoom | G: Grid | N: Names',
            this.canvas.width - padding, this.canvas.height - padding);
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
    }
};

// Export
window.GalaxyMap = GalaxyMap;
