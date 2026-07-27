/**
 * Stars Nova Web - Fleet Panel
 * Displays fleet composition, cargo, and waypoints.
 * Ported from original Stars! visual style.
 */

const FleetPanel = {
    // DOM elements
    container: null,

    // Current fleet being displayed
    currentFleet: null,

    // Fleets at same location (for dropdown)
    fleetsAtLocation: [],

    // Waypoint editing state
    editingWaypoints: false,

    // Selected waypoint leg index (-1 = auto-select last,
    // FleetDetail.cs:482-486)
    selectedWaypointIndex: -1,

    // UI task names mapped to the task types the backend accepts.
    // The C# LoadTask defect (Waypoint.cs:132 - Replace() result
    // discarded, so "Unload Cargo"/"Lay Mines" silently degraded to
    // NoTask) is NOT ported: names map to the real task types here.
    waypointTaskTypes: {
        'None': 'NoTask',
        'Colonise': 'Colonise',
        'Invade': 'Invade',
        'Scrap': 'Scrap',
        'Transfer Cargo': 'Cargo',
        'Lay Mines': 'LayMines',
        'Remote Mining': 'RemoteMine'
    },

    /**
     * Initialize the fleet panel.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Fleet panel container not found:', containerId);
            return;
        }

        // Listen to game state changes
        GameState.on('fleetSelected', (fleet) => this.show(fleet));
        GameState.on('starSelected', () => this.hide());
        GameState.on('selectionCleared', () => this.hide());
        GameState.on('turnGenerated', () => this.refresh());
        GameState.on('stateRefreshed', () => this.refresh());

        console.log('Fleet panel initialized');
    },

    /**
     * Show panel with fleet data.
     */
    async show(fleet) {
        if (!fleet || !this.container) return;

        // Switching fleets resets the leg selection to the last leg
        if (!this.currentFleet || this.currentFleet.key !== fleet.key) {
            this.selectedWaypointIndex = -1;
        }
        this.currentFleet = fleet;
        this.container.classList.remove('hidden');

        // Find all fleets at this location
        this.fleetsAtLocation = this.getFleetsAtLocation(fleet.position_x, fleet.position_y);

        this.render();
    },

    /**
     * Get all fleets at a given location.
     */
    getFleetsAtLocation(x, y, threshold = 5) {
        return GameState.fleets.filter(fleet => {
            const dx = fleet.position_x - x;
            const dy = fleet.position_y - y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            return dist <= threshold;
        });
    },

    /**
     * Hide panel.
     */
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
        this.currentFleet = null;
        this.editingWaypoints = false;
        this.selectedWaypointIndex = -1;
    },

    /**
     * Refresh current display.
     */
    refresh() {
        if (this.currentFleet) {
            const updated = GameState.fleets.find(f => f.key === this.currentFleet.key);
            if (updated) {
                this.currentFleet = updated;
                this.render();
            }
        }
    },

    /**
     * Render the panel contents.
     */
    render() {
        const fleet = this.currentFleet;
        if (!fleet || !this.container) return;

        const isOwned = fleet.intel !== 'scanned';

        let html = `
            <div class="fleet-panel-header">
                ${this.renderFleetHeader(fleet)}
                <span class="fleet-position">(${fleet.position_x}, ${fleet.position_y})</span>
            </div>

            ${this.renderComposition(fleet)}
            ${this.renderFuelAndCargo(fleet)}
            ${this.renderMovement(fleet)}
        `;

        if (isOwned) {
            html += this.renderWaypoints(fleet);
            html += this.renderFleetActions(fleet);
        }

        this.container.innerHTML = html;

        // Bind events
        this.bindFleetSelector();
        if (isOwned) {
            this.bindEvents();
        }
    },

    /**
     * Render fleet header - dropdown if multiple fleets, plain text otherwise.
     */
    renderFleetHeader(fleet) {
        if (this.fleetsAtLocation.length <= 1) {
            return `<h2>${fleet.name}</h2>`;
        }

        // Multiple fleets at location - show dropdown
        let options = '';
        for (const f of this.fleetsAtLocation) {
            const selected = f.key === fleet.key ? 'selected' : '';
            const ownerLabel = f.intel === 'scanned' ? ' (Enemy)' : '';
            const ships = (f.tokens || []).reduce((sum, t) => sum + t.quantity, 0);
            const shipInfo = ships > 0 ? ` - ${ships} ship${ships > 1 ? 's' : ''}` : '';
            options += `<option value="${f.key}" ${selected}>${f.name}${ownerLabel}${shipInfo}</option>`;
        }

        return `
            <select class="fleet-selector" id="fleet-selector">
                ${options}
            </select>
            <span class="fleet-count">${this.fleetsAtLocation.length} fleets here</span>
        `;
    },

    /**
     * Bind fleet selector change event.
     */
    bindFleetSelector() {
        const selector = document.getElementById('fleet-selector');
        if (selector) {
            selector.addEventListener('change', (e) => this.onFleetSelectorChange(e));
        }
    },

    /**
     * Handle fleet selector change.
     */
    onFleetSelectorChange(e) {
        const selectedKey = parseInt(e.target.value);
        const fleet = GameState.fleets.find(f => f.key === selectedKey);
        if (fleet) {
            GameState.selectFleet(fleet);
        }
    },

    /**
     * Render fleet composition.
     */
    renderComposition(fleet) {
        const tokenList = Array.isArray(fleet.tokens) ? fleet.tokens : Object.values(fleet.tokens || {});

        if (tokenList.length === 0) {
            return `
                <div class="fleet-section">
                    <h3>Composition</h3>
                    <p class="info-text">No ships in fleet.</p>
                </div>
            `;
        }

        let html = '<div class="fleet-section"><h3>Ships</h3><ul class="ship-list">';

        for (const token of tokenList) {
            const designName = token.design_name || token.design?.name || 'Unknown';
            html += `
                <li class="ship-item">
                    <span class="ship-name">${designName}</span>
                    <span class="ship-quantity">x${token.quantity}</span>
                </li>
            `;
        }

        html += '</ul></div>';
        return html;
    },

    /**
     * Render fuel and cargo.
     */
    renderFuelAndCargo(fleet) {
        const fuelPercent = fleet.fuel_capacity > 0
            ? Math.min(100, (fleet.fuel_available / fleet.fuel_capacity) * 100)
            : 0;

        const cargoPercent = fleet.cargo_capacity > 0
            ? Math.min(100, (fleet.cargo_mass / fleet.cargo_capacity) * 100)
            : 0;

        return `
            <div class="fleet-section">
                <h3>Fuel</h3>
                <div class="stat-row">
                    <span>Available:</span>
                    <span class="stat-value">${Math.round(fleet.fuel_available || 0)} mg</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill fuel" style="width: ${fuelPercent}%"></div>
                </div>
                <div class="stat-row">
                    <span>Capacity:</span>
                    <span class="stat-value">${Math.round(fleet.fuel_capacity || 0)} mg</span>
                </div>
            </div>

            <div class="fleet-section">
                <h3>Cargo</h3>
                <div class="stat-row">
                    <span>Mass:</span>
                    <span class="stat-value">${Math.round(fleet.cargo_mass || 0)} kT</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill cargo" style="width: ${cargoPercent}%"></div>
                </div>
                <div class="stat-row">
                    <span>Capacity:</span>
                    <span class="stat-value">${Math.round(fleet.cargo_capacity || 0)} kT</span>
                </div>

                ${this.renderCargoBreakdown(fleet)}
            </div>
        `;
    },

    /**
     * Render cargo breakdown.
     */
    renderCargoBreakdown(fleet) {
        const cargo = fleet.cargo || {};
        const hasAnyCargo = cargo.ironium || cargo.boranium || cargo.germanium || cargo.colonists;

        if (!hasAnyCargo) {
            return '<p class="info-text">Cargo hold empty.</p>';
        }

        return `
            <div class="cargo-breakdown">
                ${cargo.ironium ? `<div class="cargo-item ironium">Ir: ${cargo.ironium}</div>` : ''}
                ${cargo.boranium ? `<div class="cargo-item boranium">Bo: ${cargo.boranium}</div>` : ''}
                ${cargo.germanium ? `<div class="cargo-item germanium">Ge: ${cargo.germanium}</div>` : ''}
                ${cargo.colonists ? `<div class="cargo-item colonists">Col: ${cargo.colonists}</div>` : ''}
            </div>
        `;
    },

    /**
     * Render movement information.
     */
    renderMovement(fleet) {
        const nextWp = (fleet.waypoints || [])[0];
        const heading = nextWp
            ? (nextWp.destination || `(${Math.round(nextWp.position_x)}, ${Math.round(nextWp.position_y)})`)
            : (fleet.in_orbit ? `Orbiting ${fleet.in_orbit}` : 'Holding position');
        // Fleet-min storm protection (web extension, wave 4); shown
        // only when some source (storm shields, shields, armor,
        // radiation-hardened race) grants protection
        const stormRow = fleet.storm_protection > 0 ? `
                <div class="stat-row">
                    <span>Storm protection:</span>
                    <span class="stat-value">${Math.round(fleet.storm_protection * 100)}%</span>
                </div>` : '';
        return `
            <div class="fleet-section">
                <h3>Movement</h3>
                <div class="stat-row">
                    <span>Heading:</span>
                    <span class="stat-value">${heading}</span>
                </div>
                <div class="stat-row">
                    <span>Warp Speed:</span>
                    <span class="stat-value">Warp ${fleet.warp_factor || 0}</span>
                </div>${stormRow}
            </div>
        `;
    },

    /**
     * Render waypoints - clickable leg list plus a details editor for
     * the selected leg (FleetDetail.cs WaypointListBox + leg controls).
     */
    renderWaypoints(fleet) {
        const waypoints = fleet.waypoints || [];

        // Default-select the LAST leg (FleetDetail.cs:482-486); clamp
        // after deletes
        if (this.selectedWaypointIndex < 0 ||
                this.selectedWaypointIndex >= waypoints.length) {
            this.selectedWaypointIndex = waypoints.length - 1;
        }

        let html = `
            <div class="fleet-section">
                <h3>Waypoints</h3>
        `;

        if (waypoints.length === 0) {
            html += '<p class="info-text">No waypoints set.</p>';
        } else {
            html += '<ol class="waypoint-list">';
            for (let i = 0; i < waypoints.length; i++) {
                const wp = waypoints[i];
                const task = this.taskDisplayName(wp);
                const dest = wp.destination || `(${wp.position_x}, ${wp.position_y})`;
                const selected = i === this.selectedWaypointIndex ? ' selected' : '';

                html += `
                    <li class="waypoint-item${selected}" data-index="${i}">
                        <div class="waypoint-dest">${dest}</div>
                        <div class="waypoint-task">Task: ${task}</div>
                        <div class="waypoint-warp">Warp ${wp.warp_factor || 0}</div>
                        <button class="btn-tiny btn-delete-wp" data-index="${i}">X</button>
                    </li>
                `;
            }
            html += '</ol>';
            html += this.renderLegDetails(fleet);
        }

        html += `
                <div class="waypoint-buttons">
                    <button class="btn-small" id="btn-add-waypoint">Add Waypoint</button>
                    <button class="btn-small" id="btn-clear-waypoints">Clear All</button>
                </div>
            </div>
        `;

        return html;
    },

    /**
     * Display name of a waypoint's task.
     */
    taskDisplayName(wp) {
        const raw = (wp.task && wp.task.type) || wp.task_type || 'NoTask';
        const norm = raw.replace('TaskObj', '').replace('Task', '');
        switch (norm) {
            case 'No': case '': return 'None';
            case 'Cargo': return 'Transfer Cargo';
            case 'LayMines': return 'Lay Mines';
            case 'RemoteMine': return 'Remote Mining';
            case 'SplitMerge': return 'Split Merge';
            default: return norm;  // Colonise, Invade, Scrap
        }
    },

    /**
     * Leg distance/time/fuel for one leg (FleetDetail.cs:391-412):
     * time = dist / warp^2, fuel = FuelConsumption(warp) * time. The
     * leg origin is the previous waypoint - or the fleet position for
     * leg 0 (web semantics: the list holds destinations, unlike the
     * C# list whose waypoint 0 is the fleet's current position).
     */
    legStats(fleet, index) {
        const waypoints = fleet.waypoints || [];
        const wp = waypoints[index];
        const warp = wp ? (wp.warp_factor || 0) : 0;
        if (!wp || warp <= 0) return { dist: 0, time: 0, fuel: 0 };

        const ox = index > 0 ? waypoints[index - 1].position_x : fleet.position_x;
        const oy = index > 0 ? waypoints[index - 1].position_y : fleet.position_y;
        const dist = Math.hypot(wp.position_x - ox, wp.position_y - oy);
        const time = dist / (warp * warp);
        const perYear = (fleet.fuel_consumption_by_warp || [])[warp] || 0;
        return { dist: dist, time: time, fuel: perYear * time };
    },

    /**
     * Route fuel total over every leg with warp > 0
     * (FleetDetail.cs:414-432).
     */
    routeFuel(fleet) {
        const waypoints = fleet.waypoints || [];
        let total = 0;
        for (let i = 0; i < waypoints.length; i++) {
            total += this.legStats(fleet, i).fuel;
        }
        return total;
    },

    /**
     * Render the selected leg's editor: warp slider (TrackBar default
     * bounds 0-10, FleetDetail.Designer.cs:141-149), task selector,
     * and the leg/route readouts (FleetDetail.cs:376-439).
     */
    renderLegDetails(fleet) {
        const waypoints = fleet.waypoints || [];
        const idx = this.selectedWaypointIndex;
        if (idx < 0 || idx >= waypoints.length) return '';

        const wp = waypoints[idx];
        const warp = wp.warp_factor || 0;
        const stats = this.legStats(fleet, idx);
        const route = this.routeFuel(fleet);
        // Route fuel turns red when it exceeds the fuel aboard
        // (FleetDetail.cs:434-439)
        const routeStyle = route > (fleet.fuel_available || 0)
            ? ' style="color: #ff4444"' : '';

        const current = this.taskDisplayName(wp);
        const tasks = ['None', 'Colonise', 'Invade', 'Scrap',
                       'Transfer Cargo', 'Lay Mines'];
        // Remote mining only for fleets carrying mining robots
        if ((fleet.mining_rate || 0) > 0) tasks.push('Remote Mining');
        // Keep a non-editable task (e.g. Split Merge) visible
        if (!tasks.includes(current)) tasks.push(current);
        const taskOptions = tasks.map(t =>
            `<option value="${t}" ${t === current ? 'selected' : ''}>${t}</option>`
        ).join('');

        return `
            <div class="waypoint-leg-details">
                <div class="stat-row">
                    <span>Warp <span id="wp-warp-value">${warp}</span></span>
                    <input type="range" id="wp-warp-slider" min="0" max="10"
                           value="${warp}">
                </div>
                <div class="stat-row">
                    <span>Task:</span>
                    <select class="form-select" id="wp-task-select">
                        ${taskOptions}
                    </select>
                </div>
                <div class="stat-row">
                    <span>Leg distance:</span>
                    <span class="stat-value">${stats.dist.toFixed(1)} ly</span>
                </div>
                <div class="stat-row">
                    <span>Leg time:</span>
                    <span class="stat-value">${stats.time.toFixed(1)} years</span>
                </div>
                <div class="stat-row">
                    <span>Leg fuel:</span>
                    <span class="stat-value">${stats.fuel.toFixed(1)} mg</span>
                </div>
                <div class="stat-row">
                    <span>Route fuel:</span>
                    <span class="stat-value"${routeStyle}>${route.toFixed(1)} mg</span>
                </div>
                <button class="btn-small" id="btn-insert-waypoint">Insert Before</button>
            </div>
        `;
    },

    /**
     * Render fleet actions.
     */
    renderFleetActions(fleet) {
        // Per-fleet battle plan selector (Fleet.cs:60; the C# fleet
        // summary shows the plan, FleetReport.cs:130)
        const planNames = Object.keys(GameState.battlePlans || {});
        const planOptions = planNames.map(name =>
            `<option value="${name}" ${name === (fleet.battle_plan || 'Default') ? 'selected' : ''}>${name}</option>`
        ).join('');
        const battlePlanRow = planNames.length ? `
                <div class="stat-row">
                    <span>Battle Plan:</span>
                    <select class="form-select" id="fleet-battle-plan">
                        ${planOptions}
                    </select>
                </div>` : '';

        // Gift is enabled only with a Mystery Trader at the fleet's
        // position (co-location, merge tolerance)
        const traderHere = (GameState.traders || []).some(t =>
            Math.hypot(t.x - fleet.position_x,
                       t.y - fleet.position_y) < 1.0);

        return `
            <div class="fleet-section">
                <h3>Actions</h3>
                ${battlePlanRow}
                <div class="action-buttons">
                    <button class="btn-small" id="btn-transfer-cargo">Cargo</button>
                    <button class="btn-small" id="btn-transfer-fleet">Xfer Fleet</button>
                    <button class="btn-small" id="btn-gift-trader" ${traderHere ? '' : 'disabled'}>Gift</button>
                    <button class="btn-small" id="btn-rename-fleet">Rename</button>
                    <button class="btn-small" id="btn-split-fleet">Split</button>
                    <button class="btn-small" id="btn-merge-fleet">Merge</button>
                    <button class="btn-small btn-danger" id="btn-scrap-fleet">Scrap</button>
                </div>
            </div>
        `;
    },

    /**
     * Bind event handlers.
     */
    bindEvents() {
        // Add waypoint
        const addBtn = document.getElementById('btn-add-waypoint');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.showAddWaypointDialog());
        }

        // Clear waypoints
        const clearBtn = document.getElementById('btn-clear-waypoints');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearWaypoints());
        }

        // Delete individual waypoints. Any index is deletable: the web
        // waypoint list holds destinations, so deleting index 0 cancels
        // the current leg - the C# "waypoint 0 undeletable" rule
        // (FleetDetail.cs:204/237) guards its current-position entry
        // and does not apply here.
        const deleteButtons = this.container.querySelectorAll('.btn-delete-wp');
        deleteButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                this.deleteWaypoint(index);
            });
        });

        // Select a waypoint leg (WaypointSelection, FleetDetail.cs:154-163)
        this.container.querySelectorAll('.waypoint-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.classList.contains('btn-delete-wp')) return;
                this.selectedWaypointIndex = parseInt(item.dataset.index);
                this.render();
            });
        });

        // Warp slider: live label on input, submit on release
        // (C# submits per TrackBar Scroll tick and coalesces commands,
        // FleetDetail.cs:98-146; the web submits once on 'change'
        // because commands apply server-side immediately)
        const warpSlider = document.getElementById('wp-warp-slider');
        if (warpSlider) {
            warpSlider.addEventListener('input', () => {
                const label = document.getElementById('wp-warp-value');
                if (label) label.textContent = warpSlider.value;
            });
            warpSlider.addEventListener('change', () => {
                this.editWaypoint(this.selectedWaypointIndex,
                                  { warp_factor: parseInt(warpSlider.value) });
            });
        }

        // Task selector (WaypointTaskChanged, FleetDetail.cs:266-312)
        const taskSelect = document.getElementById('wp-task-select');
        if (taskSelect) {
            taskSelect.addEventListener('change', () =>
                this.onWaypointTaskChanged(taskSelect.value));
        }

        // Insert a leg before the selected one (web extension: the C#
        // client only appends via StarMap Shift+click, StarMap.cs:787-852)
        const insertBtn = document.getElementById('btn-insert-waypoint');
        if (insertBtn) {
            insertBtn.addEventListener('click', () =>
                this.showAddWaypointDialog(this.selectedWaypointIndex));
        }

        // Fleet actions
        const renameBtn = document.getElementById('btn-rename-fleet');
        if (renameBtn) {
            renameBtn.addEventListener('click', () => this.renameFleet());
        }

        const cargoBtn = document.getElementById('btn-transfer-cargo');
        if (cargoBtn) {
            cargoBtn.addEventListener('click', () => this.showCargoDialog());
        }

        const fleetXferBtn = document.getElementById('btn-transfer-fleet');
        if (fleetXferBtn) {
            fleetXferBtn.addEventListener('click', () => this.showFleetTransferDialog());
        }

        const giftBtn = document.getElementById('btn-gift-trader');
        if (giftBtn) {
            giftBtn.addEventListener('click', () => this.showGiftDialog());
        }

        const scrapBtn = document.getElementById('btn-scrap-fleet');
        if (scrapBtn) {
            scrapBtn.addEventListener('click', () => this.scrapFleet());
        }

        const splitBtn = document.getElementById('btn-split-fleet');
        if (splitBtn) {
            splitBtn.addEventListener('click', () => this.showSplitDialog());
        }

        const mergeBtn = document.getElementById('btn-merge-fleet');
        if (mergeBtn) {
            mergeBtn.addEventListener('click', () => this.showMergeDialog());
        }

        const planSelect = document.getElementById('fleet-battle-plan');
        if (planSelect) {
            planSelect.addEventListener('change', () => this.setBattlePlan(planSelect.value));
        }
    },

    /**
     * Assign a battle plan to the current fleet.
     */
    async setBattlePlan(planName) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await ApiClient.setFleetBattlePlan(
                GameState.game.id, this.currentFleet.key,
                GameState.empireId, planName);
            await GameState.refreshState();
            this.refresh();
            ApiClient.showStatus(`Battle plan: ${planName}`, 'info');
        } catch (error) {
            ApiClient.showStatus('Failed to set battle plan: ' + error.message, 'error');
            this.refresh();
        }
    },

    /**
     * Split ships out of the fleet into a new fleet.
     */
    async showSplitDialog() {
        const fleet = this.currentFleet;
        if (!fleet || !fleet.tokens || !fleet.tokens.length) return;

        const totalShips = fleet.tokens.reduce((n, t) => n + t.quantity, 0);
        if (totalShips < 2) {
            ApiClient.showStatus('Need at least two ships to split', 'info');
            return;
        }

        // Ask, per design, how many ships to KEEP in this fleet
        const keep = {};
        for (const token of fleet.tokens) {
            const answer = await Dialogs.promptText(
                'Split Fleet',
                `${token.design_name}: ships to KEEP here ` +
                `(0-${token.quantity}, rest form the new fleet):`,
                String(token.quantity)
            );
            if (answer === null) return;  // cancelled
            const qty = Math.max(0, Math.min(token.quantity,
                                             parseInt(answer) || 0));
            keep[token.design_key] = qty;
        }

        try {
            const result = await ApiClient.splitFleet(
                GameState.game.id, fleet.key, GameState.empireId, keep);
            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
            ApiClient.showStatus(
                `Fleet split: ${result.new_fleet_name} formed`, 'success');
        } catch (error) {
            ApiClient.showStatus('Split failed: ' + error.message, 'error');
        }
    },

    /**
     * Merge another fleet at this location into this fleet.
     */
    async showMergeDialog() {
        const fleet = this.currentFleet;
        if (!fleet) return;

        const candidates = GameState.fleets.filter(f =>
            f.key !== fleet.key &&
            !f.is_starbase &&
            Math.hypot(f.position_x - fleet.position_x,
                       f.position_y - fleet.position_y) < 1.0);

        if (!candidates.length) {
            ApiClient.showStatus('No other fleet here to merge with', 'info');
            return;
        }

        const idx = await Dialogs.selectOption(
            'Merge Fleets',
            `Merge into ${fleet.name}:`,
            candidates.map(f => {
                const ships = (f.tokens || []).reduce(
                    (n, t) => n + t.quantity, 0);
                return `${f.name} (${ships} ships)`;
            })
        );
        if (idx === null) return;

        try {
            await ApiClient.mergeFleets(
                GameState.game.id, fleet.key, GameState.empireId,
                candidates[idx].key);
            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
            ApiClient.showStatus('Fleets merged', 'success');
        } catch (error) {
            ApiClient.showStatus('Merge failed: ' + error.message, 'error');
        }
    },

    /**
     * Submit an Edit command for one leg, copying the untouched
     * fields from the current leg (WaypointSpeedChanged builds a new
     * Waypoint copying Destination/Position/Task, FleetDetail.cs:106-114;
     * the task round-trips intact per FleetDetail.cs:110).
     */
    async editWaypoint(index, changes) {
        const fleet = this.currentFleet;
        if (!fleet || !GameState.game) return;
        const wp = (fleet.waypoints || [])[index];
        if (!wp) return;

        try {
            await GameState.submitCommand('waypoint', {
                mode: 'Edit',
                fleet_key: fleet.key,
                index: index,
                waypoint: {
                    position_x: wp.position_x,
                    position_y: wp.position_y,
                    warp_factor: wp.warp_factor,
                    destination: wp.destination,
                    task: wp.task || { type: 'NoTask' },
                    ...changes
                }
            });

            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
        } catch (error) {
            ApiClient.showStatus('Failed to edit waypoint: ' + error.message, 'error');
            this.refresh();
        }
    },

    /**
     * Replace the selected leg's task with a fresh default task of the
     * chosen type (WaypointTaskChanged semantics, FleetDetail.cs:266-312).
     */
    async onWaypointTaskChanged(taskName) {
        const fleet = this.currentFleet;
        if (!fleet) return;
        const wp = (fleet.waypoints || [])[this.selectedWaypointIndex];
        if (!wp) return;

        let taskPayload;
        if (taskName === 'Transfer Cargo') {
            taskPayload = await this.promptCargoTask(wp.destination);
            if (taskPayload === null) {
                this.refresh();  // cancelled - restore the selector
                return;
            }
        } else {
            taskPayload = { type: this.waypointTaskTypes[taskName] || 'NoTask' };
        }

        this.editWaypoint(this.selectedWaypointIndex, { task: taskPayload });
    },

    /**
     * Prompt for a cargo task's mode and per-commodity amounts
     * (CargoTaskObj.from_dict schema). Returns null when cancelled.
     */
    async promptCargoTask(targetName) {
        const modeIdx = await Dialogs.selectOption(
            'Cargo Task', 'Cargo operation:',
            ['Load', 'Unload', 'Set Amount To']);
        if (modeIdx === null) return null;

        const amount = {};
        for (const [label, key] of [
                ['Ironium', 'ironium'],
                ['Boranium', 'boranium'],
                ['Germanium', 'germanium'],
                ['Colonists', 'colonists_in_kilotons']]) {
            const value = await Dialogs.promptText(
                'Cargo Amount', `${label} (kT):`, '0');
            if (value === null) return null;
            amount[key] = Math.max(0, parseInt(value) || 0);
        }

        return {
            type: 'Cargo',
            mode: ['LOAD', 'UNLOAD', 'SET'][modeIdx],
            amount: amount,
            target_name: targetName
        };
    },

    /**
     * Show add waypoint dialog - pick a destination star, warp, and
     * task. With insertIndex the new leg is inserted BEFORE that
     * index instead of appended.
     */
    async showAddWaypointDialog(insertIndex = null) {
        const fleet = this.currentFleet;
        if (!fleet) return;

        // Destinations: stars sorted by distance from the fleet
        // (excluding the star it currently orbits), then any
        // discovered wormhole endpoints
        const stars = GameState.stars
            .filter(s => s.name !== fleet.in_orbit)
            .map(s => ({
                star: s,
                dist: Math.hypot(s.position_x - fleet.position_x, s.position_y - fleet.position_y)
            })).sort((a, b) => a.dist - b.dist);

        const wormholeTargets = [];
        for (const w of (GameState.wormholes || [])) {
            for (const [label, x, y] of [[`${w.name} (A)`, w.x1, w.y1],
                                          [`${w.name} (B)`, w.x2, w.y2]]) {
                wormholeTargets.push({
                    star: { name: label, position_x: x, position_y: y },
                    dist: Math.hypot(x - fleet.position_x, y - fleet.position_y)
                });
            }
        }

        // Mystery traders: the submitted waypoint carries the trader
        // name as destination, which the turn generator's retarget
        // pass re-resolves every turn - a moving intercept course
        const traderTargets = (GameState.traders || []).map(t => ({
            star: { name: t.name, position_x: t.x, position_y: t.y },
            dist: Math.hypot(t.x - fleet.position_x,
                             t.y - fleet.position_y)
        }));

        const targets = stars.concat(wormholeTargets, traderTargets);
        const choiceIdx = await Dialogs.selectOption(
            'Add Waypoint',
            'Destination:',
            targets.map(e => `${e.star.name} (${Math.round(e.dist)} ly)` +
                             (e.star.intel === 'owned' ? ' *' : ''))
        );
        if (choiceIdx === null) return;
        const target = targets[choiceIdx].star;

        const warpStr = await Dialogs.promptText(
            'Warp Speed',
            'Warp factor (1-9, 10 = stargate jump between your gated starbases):',
            '6');
        if (warpStr === null) return;
        const warp = Math.max(1, Math.min(10, parseInt(warpStr) || 6));

        const tasks = ['None', 'Colonise', 'Lay Mines', 'Transfer Cargo', 'Scrap'];
        // Remote mining is only offered to fleets carrying mining robots
        if ((fleet.mining_rate || 0) > 0) {
            tasks.splice(3, 0, 'Remote Mining');
        }
        const taskIdx = await Dialogs.selectOption('Waypoint Task', 'Task on arrival:', tasks);
        if (taskIdx === null) return;

        // A cargo task needs a mode and per-commodity amounts
        // (CargoTaskObj.from_dict schema)
        let taskPayload = null;
        if (tasks[taskIdx] === 'Transfer Cargo') {
            taskPayload = await this.promptCargoTask(target.name);
            if (taskPayload === null) return;
        }

        this.addWaypoint(target, warp, tasks[taskIdx], taskPayload, insertIndex);
    },

    /**
     * Add a waypoint (canonical waypoint command). With insertIndex
     * the waypoint is inserted at that index (backend INSERT mode, a
     * web extension - C# only appends, StarMap.cs:787-852).
     */
    async addWaypoint(targetStar, warpFactor, task, taskPayload = null,
                      insertIndex = null) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await GameState.submitCommand('waypoint', {
                mode: insertIndex === null ? 'Add' : 'Insert',
                fleet_key: this.currentFleet.key,
                index: insertIndex === null
                    ? (this.currentFleet.waypoints || []).length
                    : insertIndex,
                waypoint: {
                    position_x: targetStar.position_x,
                    position_y: targetStar.position_y,
                    warp_factor: warpFactor,
                    destination: targetStar.name,
                    task: taskPayload ||
                          { type: this.waypointTaskTypes[task] || 'NoTask' }
                }
            });

            // Re-select the list end after an append (UpdateWaypointList,
            // FleetDetail.cs:823-828); keep the inserted leg selected
            // on an insert
            this.selectedWaypointIndex = insertIndex === null
                ? -1 : insertIndex;

            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
            ApiClient.showStatus(`Waypoint set: ${targetStar.name} at warp ${warpFactor}`, 'info');
        } catch (error) {
            ApiClient.showStatus('Failed to add waypoint: ' + error.message, 'error');
        }
    },

    /**
     * Delete a waypoint.
     */
    async deleteWaypoint(index) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await GameState.submitCommand('waypoint', {
                mode: 'Delete',
                fleet_key: this.currentFleet.key,
                index: index
            });

            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
        } catch (error) {
            ApiClient.showStatus('Failed to delete waypoint: ' + error.message, 'error');
        }
    },

    /**
     * Clear all waypoints.
     */
    async clearWaypoints() {
        if (!this.currentFleet || !GameState.game) return;

        const confirmed = await Dialogs.confirm('Clear Waypoints', 'Clear all waypoints?');
        if (!confirmed) return;

        try {
            const count = (this.currentFleet.waypoints || []).length;
            for (let i = count - 1; i >= 0; i--) {
                await GameState.submitCommand('waypoint', {
                    mode: 'Delete',
                    fleet_key: this.currentFleet.key,
                    index: i
                });
            }

            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
        } catch (error) {
            ApiClient.showStatus('Failed to clear waypoints: ' + error.message, 'error');
        }
    },

    /**
     * Cargo transfer between fleet and orbited star.
     */
    async showCargoDialog() {
        const fleet = this.currentFleet;
        if (!fleet || !GameState.game) return;

        if (!fleet.in_orbit) {
            ApiClient.showStatus('Fleet must orbit one of your planets to transfer cargo', 'error');
            return;
        }
        const star = GameState.stars.find(s => s.name === fleet.in_orbit);
        if (!star || star.intel !== 'owned') {
            ApiClient.showStatus('Cargo transfer requires orbiting your own planet', 'error');
            return;
        }

        const cargo = fleet.cargo || {};
        const free = (fleet.cargo_capacity || 0) - (fleet.cargo_mass || 0);
        const html = `
            <div class="dialog-header">
                <h2>Transfer Cargo - ${fleet.name}</h2>
                <button class="btn-close" id="btn-cargo-cancel-x">X</button>
            </div>
            <div class="dialog-body">
                <p class="info-text">Positive loads from ${star.name}, negative unloads.
                   Free capacity: ${free} kT</p>
                <div class="form-group">
                    <label>Ironium (planet: ${star.ironium || 0}, aboard: ${cargo.ironium || 0})</label>
                    <input type="number" id="cargo-ironium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Boranium (planet: ${star.boranium || 0}, aboard: ${cargo.boranium || 0})</label>
                    <input type="number" id="cargo-boranium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Germanium (planet: ${star.germanium || 0}, aboard: ${cargo.germanium || 0})</label>
                    <input type="number" id="cargo-germanium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Colonists (planet: ${star.colonists || 0}, aboard: ${cargo.colonists || 0},
                           in units of 100)</label>
                    <input type="number" id="cargo-colonists" class="form-input" value="0" step="100">
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" id="btn-cargo-confirm">Transfer</button>
                <button class="btn-secondary" id="btn-cargo-cancel">Cancel</button>
            </div>
        `;

        Dialogs.show(html);

        const close = () => Dialogs.close();
        document.getElementById('btn-cargo-cancel')?.addEventListener('click', close);
        document.getElementById('btn-cargo-cancel-x')?.addEventListener('click', close);
        document.getElementById('btn-cargo-confirm')?.addEventListener('click', async () => {
            const delta = {
                ironium: parseInt(document.getElementById('cargo-ironium')?.value) || 0,
                boranium: parseInt(document.getElementById('cargo-boranium')?.value) || 0,
                germanium: parseInt(document.getElementById('cargo-germanium')?.value) || 0,
                colonists: parseInt(document.getElementById('cargo-colonists')?.value) || 0
            };
            Dialogs.close();
            try {
                await ApiClient.transferCargo(GameState.game.id, fleet.key, GameState.empireId, delta);
                await GameState.refreshState();
                this.refresh();
                if (window.StarPanel) StarPanel.refresh();
                ApiClient.showStatus('Cargo transferred', 'info');
            } catch (error) {
                ApiClient.showStatus('Transfer failed: ' + error.message, 'error');
            }
        });
    },

    /**
     * Cargo/fuel transfer with another owned fleet at this location
     * (counterparty rules as in FleetDetail.cs fleetsAtLocation).
     */
    async showFleetTransferDialog() {
        const fleet = this.currentFleet;
        if (!fleet || !GameState.game) return;

        const candidates = GameState.fleets.filter(f =>
            f.key !== fleet.key &&
            !f.is_starbase &&
            Math.hypot(f.position_x - fleet.position_x,
                       f.position_y - fleet.position_y) < 1.0);

        if (!candidates.length) {
            ApiClient.showStatus('No other fleet here to transfer with', 'info');
            return;
        }

        const idx = await Dialogs.selectOption(
            'Transfer With Fleet',
            `Transfer cargo/fuel between ${fleet.name} and:`,
            candidates.map(f => `${f.name} (cargo ${f.cargo_mass || 0}/${f.cargo_capacity || 0} kT)`)
        );
        if (idx === null) return;
        const other = candidates[idx];

        const cargo = fleet.cargo || {};
        const otherCargo = other.cargo || {};
        const free = (fleet.cargo_capacity || 0) - (fleet.cargo_mass || 0);
        const html = `
            <div class="dialog-header">
                <h2>Transfer Cargo - ${fleet.name}</h2>
                <button class="btn-close" id="btn-fxfer-cancel-x">X</button>
            </div>
            <div class="dialog-body">
                <p class="info-text">Positive loads into this fleet from ${other.name},
                   negative unloads. Free capacity: ${free} kT</p>
                <div class="form-group">
                    <label>Ironium (${other.name}: ${otherCargo.ironium || 0}, aboard: ${cargo.ironium || 0})</label>
                    <input type="number" id="fxfer-ironium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Boranium (${other.name}: ${otherCargo.boranium || 0}, aboard: ${cargo.boranium || 0})</label>
                    <input type="number" id="fxfer-boranium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Germanium (${other.name}: ${otherCargo.germanium || 0}, aboard: ${cargo.germanium || 0})</label>
                    <input type="number" id="fxfer-germanium" class="form-input" value="0">
                </div>
                <div class="form-group">
                    <label>Colonists (${other.name}: ${otherCargo.colonists || 0}, aboard: ${cargo.colonists || 0},
                           in units of 100)</label>
                    <input type="number" id="fxfer-colonists" class="form-input" value="0" step="100">
                </div>
                <div class="form-group">
                    <label>Fuel (${other.name}: ${Math.floor(other.fuel_available || 0)},
                           aboard: ${Math.floor(fleet.fuel_available || 0)})</label>
                    <input type="number" id="fxfer-fuel" class="form-input" value="0">
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" id="btn-fxfer-confirm">Transfer</button>
                <button class="btn-secondary" id="btn-fxfer-cancel">Cancel</button>
            </div>
        `;

        Dialogs.show(html);

        const close = () => Dialogs.close();
        document.getElementById('btn-fxfer-cancel')?.addEventListener('click', close);
        document.getElementById('btn-fxfer-cancel-x')?.addEventListener('click', close);
        document.getElementById('btn-fxfer-confirm')?.addEventListener('click', async () => {
            const delta = {
                ironium: parseInt(document.getElementById('fxfer-ironium')?.value) || 0,
                boranium: parseInt(document.getElementById('fxfer-boranium')?.value) || 0,
                germanium: parseInt(document.getElementById('fxfer-germanium')?.value) || 0,
                colonists: parseInt(document.getElementById('fxfer-colonists')?.value) || 0,
                fuel: parseInt(document.getElementById('fxfer-fuel')?.value) || 0
            };
            Dialogs.close();
            try {
                await ApiClient.transferCargoFleet(
                    GameState.game.id, fleet.key, GameState.empireId, other.key, delta);
                await GameState.refreshState();
                this.refresh();
                ApiClient.showStatus('Cargo transferred', 'info');
            } catch (error) {
                ApiClient.showStatus('Transfer failed: ' + error.message, 'error');
            }
        });
    },

    /**
     * One-way gift of minerals/colonists to a co-located Mystery
     * Trader. The trader always keeps the cargo; a 1000+ kT running
     * total earns a reward on the next turn.
     */
    async showGiftDialog() {
        const fleet = this.currentFleet;
        if (!fleet || !GameState.game) return;

        const trader = (GameState.traders || []).find(t =>
            Math.hypot(t.x - fleet.position_x,
                       t.y - fleet.position_y) < 1.0);
        if (!trader) {
            ApiClient.showStatus('No Mystery Trader at this position', 'info');
            return;
        }

        const cargo = fleet.cargo || {};
        const html = `
            <div class="dialog-header">
                <h2>Gift to ${trader.name}</h2>
                <button class="btn-close" id="btn-gift-cancel-x">X</button>
            </div>
            <div class="dialog-body">
                <p class="info-text">The trader keeps whatever you give.
                   A running total of ${trader.gift_threshold} kT or more
                   earns a reward next year
                   (gifted so far: ${trader.gift_total} kT).</p>
                <div class="form-group">
                    <label>Ironium (aboard: ${cargo.ironium || 0})</label>
                    <input type="number" id="gift-ironium" class="form-input" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>Boranium (aboard: ${cargo.boranium || 0})</label>
                    <input type="number" id="gift-boranium" class="form-input" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>Germanium (aboard: ${cargo.germanium || 0})</label>
                    <input type="number" id="gift-germanium" class="form-input" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>Colonists (aboard: ${cargo.colonists || 0},
                           in units of 100)</label>
                    <input type="number" id="gift-colonists" class="form-input" value="0" min="0" step="100">
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" id="btn-gift-confirm">Gift</button>
                <button class="btn-secondary" id="btn-gift-cancel">Cancel</button>
            </div>
        `;

        Dialogs.show(html);

        const close = () => Dialogs.close();
        document.getElementById('btn-gift-cancel')?.addEventListener('click', close);
        document.getElementById('btn-gift-cancel-x')?.addEventListener('click', close);
        document.getElementById('btn-gift-confirm')?.addEventListener('click', async () => {
            const delta = {
                ironium: parseInt(document.getElementById('gift-ironium')?.value) || 0,
                boranium: parseInt(document.getElementById('gift-boranium')?.value) || 0,
                germanium: parseInt(document.getElementById('gift-germanium')?.value) || 0,
                colonists: parseInt(document.getElementById('gift-colonists')?.value) || 0
            };
            Dialogs.close();
            try {
                const result = await ApiClient.giftToTrader(
                    GameState.game.id, fleet.key, GameState.empireId,
                    trader.key, delta);
                await GameState.refreshState();
                this.refresh();
                ApiClient.showStatus(
                    `Gifted - ${result.gift_total} of ` +
                    `${result.threshold} kT toward a reward`, 'info');
            } catch (error) {
                ApiClient.showStatus('Gift failed: ' + error.message, 'error');
            }
        });
    },

    /**
     * Rename fleet.
     */
    async renameFleet() {
        if (!this.currentFleet || !GameState.game) return;

        const newName = await Dialogs.promptText('Rename Fleet', 'New fleet name:', this.currentFleet.name);
        if (!newName || newName === this.currentFleet.name) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/fleets/${this.currentFleet.key}/rename`,
                { empire_id: GameState.empireId, name: newName }
            );
            await GameState.refreshState();
            this.refresh();
            if (window.GalaxyMap) GalaxyMap.render();
        } catch (error) {
            ApiClient.showStatus('Failed to rename fleet: ' + error.message, 'error');
        }
    },

    /**
     * Scrap fleet - sets a Scrap task waypoint at the current position.
     */
    async scrapFleet() {
        if (!this.currentFleet || !GameState.game) return;

        const confirmed = await Dialogs.confirm(
            'Scrap Fleet',
            `Scrap ${this.currentFleet.name}? Minerals will be recovered at its location.`
        );
        if (!confirmed) return;

        try {
            const fleet = this.currentFleet;
            await GameState.submitCommand('waypoint', {
                mode: 'Insert',
                fleet_key: fleet.key,
                index: 0,
                waypoint: {
                    position_x: fleet.position_x,
                    position_y: fleet.position_y,
                    warp_factor: 0,
                    destination: fleet.in_orbit || `${Math.round(fleet.position_x)},${Math.round(fleet.position_y)}`,
                    task: { type: 'Scrap' }
                }
            });

            await GameState.refreshState();
            this.refresh();
            ApiClient.showStatus('Fleet will be scrapped at end of turn', 'info');
        } catch (error) {
            ApiClient.showStatus('Failed to scrap fleet: ' + error.message, 'error');
        }
    }
};

// Export
window.FleetPanel = FleetPanel;
