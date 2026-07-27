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

    // Phenomena tooltip (storms, wormholes, minefields, dust)
    tooltip: null,
    tooltipTarget: null,

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

    // Repeat-click cycling through stacked objects (LeftMouse,
    // StarMap.cs:859-895): screen position of the last selecting
    // click and the index into the near-object list
    lastClick: null,
    cycleIndex: 0,

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

        // Phenomena hover tooltip
        this.initTooltip();

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
        this.canvas.addEventListener('contextmenu', (e) => this.onContextMenu(e));

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

        this.hideTooltip();

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

            // Stacked-object cycling (LeftMouse, StarMap.cs:859-895):
            // repeat clicks within 10 device px of the previous click
            // advance through the near-object list, wrapping; a click
            // further away restarts at the first object
            const candidates = this.findObjectsAt(worldPos.x, worldPos.y);

            if (candidates.length > 0) {
                if (this.lastClick &&
                        Math.abs(x - this.lastClick.x) <= 10 &&
                        Math.abs(y - this.lastClick.y) <= 10) {
                    this.cycleIndex = (this.cycleIndex + 1) % candidates.length;
                } else {
                    this.cycleIndex = 0;
                }
                this.lastClick = { x: x, y: y };

                const clicked = candidates[this.cycleIndex];
                if (clicked.type === 'star') {
                    GameState.selectStar(clicked.object);
                } else if (clicked.type === 'fleet') {
                    GameState.selectFleet(clicked.object);
                }
            } else {
                this.lastClick = null;
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
                this.hideTooltip();
            } else {
                this.canvas.style.cursor = 'grab';
                // Phenomena tooltip (storm, wormhole, minefield, dust)
                const phenomenon = this.findPhenomenonAt(worldPos.x, worldPos.y);
                if (phenomenon) {
                    this.showTooltip(phenomenon, e.clientX, e.clientY);
                } else {
                    this.hideTooltip();
                }
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
        // Keep the tooltip while the cursor moves onto it, so its
        // Encyclopedia link stays clickable
        if (!(e && e.relatedTarget && this.tooltip
                && this.tooltip.contains(e.relatedTarget))) {
            this.hideTooltip();
        }
        this.render();
    },

    /**
     * Mouse wheel - zoom.
     */
    onWheel(e) {
        e.preventDefault();

        this.hideTooltip();

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Get world position under mouse before zoom
        const worldBefore = this.screenToWorld(mouseX, mouseY);

        // Adjust zoom
        const zoomDelta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoom = Math.max(this.minAllowedZoom(), Math.min(this.maxZoom, this.zoom * zoomDelta));

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
                this.zoom = Math.max(this.minAllowedZoom(), this.zoom / 1.2);
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
                this.hideTooltip();
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
        for (const fleet of GameState.allVisibleFleets) {
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
     * All objects near a world position, stars first then fleets,
     * alphabetical within each type (FindNearObjects + ItemSorter,
     * StarMap.cs:971-1014). Own starbase fleets are excluded per
     * StarMap.cs:977; foreign contacts are included. Divergence from
     * C#: the C# "near" box is a fixed 40x40 ly area
     * (PointUtilities.cs:125-137); the web threshold is zoom-relative
     * to match findObjectAt.
     */
    findObjectsAt(worldX, worldY) {
        const threshold = this.starRadius * 2 / this.zoom;

        const stars = GameState.stars
            .filter(s => Math.hypot(s.position_x - worldX,
                                    s.position_y - worldY) < threshold)
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
            .map(s => ({ type: 'star', object: s }));

        const fleets = GameState.allVisibleFleets
            .filter(f => !f.is_starbase &&
                         Math.hypot(f.position_x - worldX,
                                    f.position_y - worldY) < threshold)
            .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
            .map(f => ({ type: 'fleet', object: f }));

        return stars.concat(fleets);
    },

    /**
     * Right-click context menu listing all near objects - stars, a
     * separator, then fleets (RightMouse + ContextSelect,
     * StarMap.cs:897-953). Reuses the map tooltip div as the popup.
     */
    onContextMenu(e) {
        e.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const worldPos = this.screenToWorld(e.clientX - rect.left,
                                            e.clientY - rect.top);
        const candidates = this.findObjectsAt(worldPos.x, worldPos.y);
        if (candidates.length === 0 || !this.tooltip) {
            this.hideTooltip();
            return;
        }

        this.tooltipTarget = 'context-menu';
        let html = '<div class="map-context-menu">';
        let lastType = null;
        for (let i = 0; i < candidates.length; i++) {
            const c = candidates[i];
            if (lastType && c.type !== lastType) {
                html += '<hr class="map-context-separator">';
            }
            lastType = c.type;
            const icon = c.type === 'star' ? '*' : '&gt;';
            html += `<a class="map-context-item" href="#" data-index="${i}">` +
                    `${icon} ${c.object.name}</a>`;
        }
        html += '</div>';
        this.tooltip.innerHTML = html;

        this.tooltip.querySelectorAll('.map-context-item').forEach(item => {
            item.addEventListener('click', (ev) => {
                ev.preventDefault();
                const picked = candidates[parseInt(item.dataset.index)];
                this.hideTooltip();
                if (picked.type === 'star') {
                    GameState.selectStar(picked.object);
                } else {
                    GameState.selectFleet(picked.object);
                }
            });
        });

        this.tooltip.style.left = `${e.clientX + 4}px`;
        this.tooltip.style.top = `${e.clientY + 4}px`;
        this.tooltip.classList.remove('hidden');
    },

    /**
     * Center view on homeworld.
     */
    centerOnHomeworld() {
        // Find player's homeworld (first star with colonists owned by player)
        const homeworld = GameState.stars.find(s => s.intel === 'owned');
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

        // Start within the zoom-out clamp for this board
        this.zoom = Math.max(this.zoom, this.minAllowedZoom());

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

        // Spatial phenomena underlays
        this.renderMinefields();
        this.renderStorms();
        this.renderWormholes();
        this.renderTraders();

        // Draw waypoint lines for selected fleet
        if (this.selectedFleet) {
            this.renderWaypoints(this.selectedFleet);
        }

        // Draw stars
        for (const star of GameState.stars) {
            this.renderStar(star);
        }

        // Draw fleets
        for (const fleet of GameState.allVisibleFleets) {
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
     * Render known minefields as hatched circles
     * (own fields green, hostile fields red).
     */
    renderMinefields() {
        const fields = GameState.minefields || [];
        if (!fields.length) return;
        const ctx = this.ctx;

        for (const field of fields) {
            const { x: sx, y: sy } = this.worldToScreen(field.x, field.y);
            const radius = field.radius * this.zoom;
            if (radius < 2) continue;

            const own = field.owner === GameState.empireId;
            const detonating = own && field.detonate;
            const color = detonating ? '255, 150, 40'
                : (own ? '0, 255, 0' : '255, 60, 60');
            // Detonating fields pulse like storms
            const pulse = detonating
                ? 0.75 + 0.25 * Math.sin(Date.now() / 400) : 1;

            ctx.save();
            ctx.beginPath();
            ctx.arc(sx, sy, radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${color}, ${0.07 * pulse})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(${color}, ${0.45 * pulse})`;
            ctx.setLineDash([4, 4]);
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.setLineDash([]);

            if (this.zoom >= 0.5) {
                ctx.fillStyle = `rgba(${color}, 0.7)`;
                ctx.font = '9px monospace';
                ctx.textAlign = 'center';
                const label = `${field.mine_descriptor || ''} mines`
                    + (detonating ? ' DETONATING' : '');
                ctx.fillText(label, sx, sy);
            }
            ctx.restore();
        }
    },

    /**
     * Render galactic storms as pulsing irregular blobs: a dashed red
     * boundary along the server-sampled perimeter polygon, filled
     * with a radial gradient whose alpha follows the intensity ramp
     * (strongest at the core, zero at the boundary).
     */
    renderStorms() {
        const storms = GameState.storms || [];
        if (!storms.length) return;
        const ctx = this.ctx;
        const pulse = 0.75 + 0.25 * Math.sin(Date.now() / 400);

        for (const storm of storms) {
            const { x: sx, y: sy } = this.worldToScreen(storm.x, storm.y);
            const radius = storm.radius * this.zoom;
            if (radius < 2) continue;

            // Blob perimeter polygon from the server-sampled radii
            // (circular fallback for storms without a shape)
            let radii = storm.shape_radii;
            if (!radii || !radii.length) radii = new Array(32).fill(storm.radius);
            const n = radii.length;
            let maxR = 0;
            const blob = new Path2D();
            for (let i = 0; i < n; i++) {
                const theta = (i / n) * Math.PI * 2;
                const r = radii[i] * this.zoom;
                if (r > maxR) maxR = r;
                const px = sx + Math.cos(theta) * r;
                const py = sy + Math.sin(theta) * r;
                if (i === 0) blob.moveTo(px, py);
                else blob.lineTo(px, py);
            }
            blob.closePath();

            ctx.save();
            // Interior gradient alpha approximates the smoothstep
            // intensity ramp: full at the core, zero at the boundary,
            // scaled by the storm's peak intensity
            const peak = storm.intensity;
            const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, maxR);
            grad.addColorStop(0, `rgba(255, 120, 40, ${0.45 * peak * pulse})`);
            grad.addColorStop(0.5, `rgba(220, 70, 120, ${0.23 * peak * pulse})`);
            grad.addColorStop(0.8, `rgba(160, 50, 140, ${0.05 * peak * pulse})`);
            grad.addColorStop(1, 'rgba(120, 40, 160, 0)');
            ctx.fillStyle = grad;
            ctx.fill(blob);

            // Dashed red boundary along the blob perimeter
            ctx.strokeStyle = `rgba(255, 60, 60, ${0.6 * pulse})`;
            ctx.setLineDash([6, 6]);
            ctx.lineWidth = 1.5;
            ctx.stroke(blob);
            ctx.setLineDash([]);

            if (this.zoom >= 0.4) {
                ctx.fillStyle = 'rgba(255, 160, 80, 0.85)';
                ctx.font = 'bold 10px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('STORM', sx, sy + 3);
            }
            ctx.restore();
        }
    },

    /**
     * Render Mystery Traders: a dashed gold projected-course line from
     * the trader along its velocity to the map edge, then a filled
     * gold diamond marker with a pulsing halo (visible to everyone -
     * universal visibility, no fog).
     */
    renderTraders() {
        const traders = GameState.traders || [];
        if (!traders.length) return;
        const ctx = this.ctx;
        const pulse = 0.75 + 0.25 * Math.sin(Date.now() / 400);

        for (const trader of traders) {
            const { x: sx, y: sy } = this.worldToScreen(trader.x, trader.y);

            // Projected course: extend the velocity ray far past the
            // board; the canvas clips it at the viewport
            const speed = Math.hypot(trader.velocity_x, trader.velocity_y);
            if (speed > 0) {
                const reach = 2000;  // ly, beyond any board size
                const ex = trader.x + trader.velocity_x / speed * reach;
                const ey = trader.y + trader.velocity_y / speed * reach;
                const end = this.worldToScreen(ex, ey);
                ctx.save();
                ctx.strokeStyle = `rgba(240, 200, 90, ${0.45 * pulse})`;
                ctx.setLineDash([8, 6]);
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                ctx.moveTo(sx, sy);
                ctx.lineTo(end.x, end.y);
                ctx.stroke();
                ctx.setLineDash([]);
                ctx.restore();
            }

            ctx.save();
            // Pulsing halo
            const halo = ctx.createRadialGradient(sx, sy, 0, sx, sy, 18);
            halo.addColorStop(0, `rgba(255, 214, 120, ${0.5 * pulse})`);
            halo.addColorStop(1, 'rgba(255, 214, 120, 0)');
            ctx.fillStyle = halo;
            ctx.beginPath();
            ctx.arc(sx, sy, 18, 0, Math.PI * 2);
            ctx.fill();

            // Filled gold diamond (rotated square)
            const r = 6;
            ctx.fillStyle = 'rgba(255, 214, 120, 0.95)';
            ctx.strokeStyle = 'rgba(120, 80, 20, 0.9)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(sx, sy - r);
            ctx.lineTo(sx + r, sy);
            ctx.lineTo(sx, sy + r);
            ctx.lineTo(sx - r, sy);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();

            if (this.zoom >= 0.4) {
                ctx.fillStyle = 'rgba(255, 224, 150, 0.9)';
                ctx.font = 'bold 10px monospace';
                ctx.textAlign = 'center';
                ctx.fillText('TRADER', sx, sy - r - 4);
            }
            ctx.restore();
        }
    },

    /**
     * Render discovered wormholes: two swirl endpoints joined by a
     * faint line.
     */
    renderWormholes() {
        const wormholes = GameState.wormholes || [];
        if (!wormholes.length) return;
        const ctx = this.ctx;
        const spin = (Date.now() / 900) % (Math.PI * 2);

        for (const w of wormholes) {
            const { x: ax, y: ay } = this.worldToScreen(w.x1, w.y1);
            const { x: bx, y: by } = this.worldToScreen(w.x2, w.y2);

            ctx.save();
            ctx.strokeStyle = 'rgba(170, 110, 255, 0.18)';
            ctx.setLineDash([2, 8]);
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
            ctx.stroke();
            ctx.setLineDash([]);

            for (const [ex, ey, label] of [[ax, ay, `${w.name} (A)`],
                                           [bx, by, `${w.name} (B)`]]) {
                const r = Math.max(4, 7 * this.zoom);
                for (let arm = 0; arm < 3; arm++) {
                    ctx.beginPath();
                    ctx.strokeStyle = 'rgba(190, 130, 255, 0.8)';
                    ctx.lineWidth = 1.5;
                    const start = spin + arm * (Math.PI * 2 / 3);
                    ctx.arc(ex, ey, r, start, start + Math.PI * 0.9);
                    ctx.stroke();
                }
                ctx.beginPath();
                ctx.arc(ex, ey, Math.max(1.5, r * 0.3), 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(230, 200, 255, 0.9)';
                ctx.fill();

                if (this.showNames && this.zoom >= 0.5) {
                    ctx.fillStyle = 'rgba(190, 140, 255, 0.85)';
                    ctx.font = '9px monospace';
                    ctx.textAlign = 'center';
                    ctx.fillText(label, ex, ey + r + 10);
                }
            }
            ctx.restore();
        }
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
        if (star.intel === 'owned') {
            fillColor = this.colors.starFriendly;
        } else if (star.owner > 0 && star.colonists > 0) {
            fillColor = this.colors.starEnemy;
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

        // Draw ownership ring for colonized stars we know about
        if (star.colonists > 0 && (star.intel === 'owned' || star.owner > 0)) {
            const ringColor = star.intel === 'owned' ? this.colors.starFriendly : this.colors.starEnemy;
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
        let color = fleet.intel === 'scanned' ? this.colors.fleetEnemy : this.colors.fleetFriendly;

        // Mineral packets get a distinct glyph: a small slug with a
        // motion streak (own via is_packet; scanned contacts by name)
        const isPacket = fleet.is_packet ||
            (fleet.intel === 'scanned' && /Mineral Packet/.test(fleet.name || ''));

        if (isPacket) {
            // Streak trails away from the flight direction when known
            let angle = Math.PI * 0.75;
            if (fleet.waypoints && fleet.waypoints.length > 0) {
                const wp = fleet.waypoints[0];
                angle = Math.atan2(wp.position_y - fleet.position_y,
                                   wp.position_x - fleet.position_x);
            }
            ctx.strokeStyle = color;
            ctx.lineWidth = Math.max(1, radius * 0.5);
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(pos.x - Math.cos(angle) * radius * 2.4,
                       pos.y - Math.sin(angle) * radius * 2.4);
            ctx.lineTo(pos.x - Math.cos(angle) * radius * 0.6,
                       pos.y - Math.sin(angle) * radius * 0.6);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius * 0.7, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        } else {
            // Draw fleet as diamond
            ctx.beginPath();
            ctx.moveTo(pos.x, pos.y - radius);
            ctx.lineTo(pos.x + radius, pos.y);
            ctx.lineTo(pos.x, pos.y + radius);
            ctx.lineTo(pos.x - radius, pos.y);
            ctx.closePath();
            ctx.fillStyle = color;
            ctx.fill();
        }

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
            // Own fleets only; scan range comes from ship designs
            const scanRange = fleet.scan_range || fleet.scanner_range || 66;
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
            if (star.intel !== 'owned') continue;

            const scanRange = star.scan_range || 0;
            if (scanRange <= 0) continue;
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
        if (x === undefined || y === undefined || isNaN(x) || isNaN(y)) return;
        this.viewX = x;
        this.viewY = y;
        this.render();
    },

    /**
     * Set zoom level.
     */
    setZoom(level) {
        this.zoom = Math.max(this.minAllowedZoom(), Math.min(this.maxZoom, level));
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
     * Game board bounds (all stars plus padding), or null when no
     * stars are loaded.
     */
    boardBounds() {
        const stars = GameState.stars || [];
        if (stars.length === 0) return null;

        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        for (const star of stars) {
            minX = Math.min(minX, star.position_x);
            maxX = Math.max(maxX, star.position_x);
            minY = Math.min(minY, star.position_y);
            maxY = Math.max(maxY, star.position_y);
        }

        const padding = 50;
        return {
            minX: minX - padding, maxX: maxX + padding,
            minY: minY - padding, maxY: maxY + padding
        };
    },

    /**
     * Best-fit zoom for the whole game board, or null when no stars
     * are loaded.
     */
    computeFitZoom() {
        const bounds = this.boardBounds();
        if (!bounds) return null;

        const zoomX = this.canvas.width / (bounds.maxX - bounds.minX);
        const zoomY = this.canvas.height / (bounds.maxY - bounds.minY);
        return Math.min(zoomX, zoomY, this.maxZoom);
    },

    /**
     * Minimum allowed zoom: ~20% wider than the board best fit
     * (fitZoom / 1.2, user directive 2026-07-13). Falls back to the
     * static minZoom when no game is loaded.
     */
    minAllowedZoom() {
        const fit = this.computeFitZoom();
        return fit ? fit / 1.2 : this.minZoom;
    },

    /**
     * Zoom to fit all stars in view.
     */
    zoomToFit() {
        const bounds = this.boardBounds();
        if (!bounds) return;

        this.zoom = Math.max(this.computeFitZoom(), this.minZoom);

        // Center on midpoint
        this.viewX = (bounds.minX + bounds.maxX) / 2;
        this.viewY = (bounds.minY + bounds.maxY) / 2;

        this.render();
    },

    // =========================================================================
    // Phenomena tooltip
    // =========================================================================

    /**
     * Create the phenomena tooltip element (hidden until a phenomenon
     * is hovered on the map).
     */
    initTooltip() {
        this.tooltip = document.getElementById('map-tooltip');
        if (!this.tooltip) {
            this.tooltip = document.createElement('div');
            this.tooltip.id = 'map-tooltip';
            this.tooltip.className = 'map-tooltip hidden';
            document.body.appendChild(this.tooltip);
        }
        this.tooltip.addEventListener('mouseleave', () => this.hideTooltip());
    },

    /**
     * Show the tooltip for a phenomenon. The position freezes while
     * the same phenomenon stays hovered so the Encyclopedia link can
     * be reached with the cursor.
     */
    showTooltip(phenomenon, clientX, clientY) {
        if (!this.tooltip) return;
        if (this.tooltipTarget === phenomenon.id) return;

        this.tooltipTarget = phenomenon.id;
        this.tooltip.innerHTML = `
            <div class="map-tooltip-title">${phenomenon.title}</div>
            <div class="map-tooltip-summary">${phenomenon.summary}</div>
            <a class="map-tooltip-link" href="#">Encyclopedia</a>
        `;
        this.tooltip.querySelector('.map-tooltip-link')
            .addEventListener('click', (ev) => {
                ev.preventDefault();
                this.hideTooltip();
                if (window.Encyclopedia) {
                    Encyclopedia.open(phenomenon.entryId);
                }
            });
        this.tooltip.style.left = `${clientX + 14}px`;
        this.tooltip.style.top = `${clientY + 14}px`;
        this.tooltip.classList.remove('hidden');
    },

    /**
     * Hide the phenomena tooltip.
     */
    hideTooltip() {
        if (!this.tooltip) return;
        this.tooltip.classList.add('hidden');
        this.tooltipTarget = null;
    },

    /**
     * Local storm intensity at a world position - port of
     * GalacticStorm.boundary_radius/get_intensity_at
     * (backend/server/server_data.py:179-217): distance normalized by
     * the interpolated blob boundary radius along the bearing, eased
     * with a smoothstep ramp.
     */
    stormIntensityAt(storm, x, y) {
        const dx = x - storm.x;
        const dy = y - storm.y;

        let boundary = storm.radius;
        const radii = storm.shape_radii;
        if (radii && radii.length) {
            const n = radii.length;
            const tau = Math.PI * 2;
            const theta = ((Math.atan2(dy, dx) % tau) + tau) % tau;
            const t = theta / tau * n;
            const i = Math.floor(t) % n;
            const frac = t - Math.floor(t);
            boundary = radii[i] * (1 - frac) + radii[(i + 1) % n] * frac;
        }
        if (boundary <= 0) return 0;

        const d = Math.hypot(dx, dy) / boundary;
        if (d >= 1) return 0;
        const ease = 1 - d;
        return storm.intensity * ease * ease * (3 - 2 * ease);  // smoothstep
    },

    /**
     * Dust density at a world position from the client's nebula field
     * data - region analogue of NebulaField._build_grid
     * (backend/server/server_data.py:367-417): gaussian falloff per
     * dark region, additive, clamped to 1.
     */
    dustDensityAt(x, y) {
        const regions = GameState.nebulae?.regions;
        if (!regions) return 0;

        let density = 0;
        for (const region of regions) {
            if (region.nebula_type !== 'dark') continue;
            if (!(region.radius_x > 0 && region.radius_y > 0)) continue;

            const cosR = Math.cos(-(region.rotation || 0));
            const sinR = Math.sin(-(region.rotation || 0));
            const dx = x - region.x;
            const dy = y - region.y;
            const localX = dx * cosR - dy * sinR;
            const localY = dx * sinR + dy * cosR;

            const normDist = Math.sqrt(
                (localX / region.radius_x) ** 2 +
                (localY / region.radius_y) ** 2
            );
            if (normDist < 2.0) {
                density = Math.min(
                    1, density + region.density * Math.exp(-normDist * normDist)
                );
            }
        }
        return density;
    },

    /**
     * Hit-test spatial phenomena at a world position for the hover
     * tooltip. Checked most-specific first: storms, wormhole
     * endpoints, minefields, then the (large) dust nebula regions.
     * Numbers in the summaries mirror backend/core/globals.py and
     * turn_generator.py MINE_STATS.
     */
    findPhenomenonAt(worldX, worldY) {
        // Traders first: the marker is small and must win over the
        // large storm blobs. Numbers mirror backend/core/globals.py
        // MT_* constants.
        for (const trader of GameState.traders || []) {
            const catchRadius = Math.max(8, 10 / this.zoom);
            if (Math.hypot(worldX - trader.x, worldY - trader.y)
                    <= catchRadius) {
                return {
                    id: `trader-${trader.key}`,
                    entryId: 'mystery-trader',
                    title: trader.name,
                    summary: `Crossing at warp ${trader.warp} - gift `
                        + '1000+ kT of minerals or colonists at its '
                        + 'position for a reward'
                };
            }
        }

        for (const storm of GameState.storms || []) {
            const local = this.stormIntensityAt(storm, worldX, worldY);
            if (local > 0) {
                return {
                    id: `storm-${storm.key}`,
                    entryId: 'storms',
                    title: 'Galactic Storm',
                    summary: `Local intensity ${Math.round(local * 100)}% - `
                        + 'hull damage, warp mishaps above warp 6, '
                        + 'scanner loss, colonist attrition'
                };
            }
        }

        for (const w of GameState.wormholes || []) {
            const ends = [[w.x1, w.y1, 'A'], [w.x2, w.y2, 'B']];
            for (const [ex, ey, end] of ends) {
                const catchRadius = Math.max(8, 10 / this.zoom);
                if (Math.hypot(worldX - ex, worldY - ey) <= catchRadius) {
                    return {
                        id: `wormhole-${w.key}-${end}`,
                        entryId: 'wormholes',
                        title: `${w.name} (${end})`,
                        summary: 'Instant fuel-free transit to the far end; '
                            + 'endpoints drift each year'
                    };
                }
            }
        }

        const mineSafeWarp = { 0: 4, 1: 6, 2: 5 };
        for (const field of GameState.minefields || []) {
            if (Math.hypot(worldX - field.x, worldY - field.y)
                    <= field.radius) {
                const safe = mineSafeWarp[field.mine_type] || 4;
                return {
                    id: `minefield-${field.key}`,
                    entryId: 'minefields',
                    title: `${field.mine_descriptor || 'Standard'} Minefield`,
                    summary: `Safe at warp ${safe} or below; faster fleets `
                        + 'risk a strike that stops them dead'
                };
            }
        }

        const dust = this.dustDensityAt(worldX, worldY);
        if (dust >= 0.05) {
            return {
                id: 'dust-nebula',
                entryId: 'dust-nebulae',
                title: 'Dust Nebula',
                summary: `Dust density ${Math.round(dust * 100)}% - ships `
                    + `slowed ${Math.round(40 * dust)}%, scanners dampened `
                    + `${Math.round(50 * dust)}%`
            };
        }

        return null;
    }
};

// Export
window.GalaxyMap = GalaxyMap;
