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
                </div>
            </div>
        `;
    },

    /**
     * Render waypoints.
     */
    renderWaypoints(fleet) {
        const waypoints = fleet.waypoints || [];

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
                const task = (wp.task_type || 'NoTask').replace('TaskObj', '').replace('NoTask', 'None');
                const dest = wp.destination || `(${wp.position_x}, ${wp.position_y})`;

                html += `
                    <li class="waypoint-item" data-index="${i}">
                        <div class="waypoint-dest">${dest}</div>
                        <div class="waypoint-task">Task: ${task}</div>
                        <div class="waypoint-warp">Warp ${wp.warp_factor || 5}</div>
                        <button class="btn-tiny btn-delete-wp" data-index="${i}">X</button>
                    </li>
                `;
            }
            html += '</ol>';
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
     * Render fleet actions.
     */
    renderFleetActions(fleet) {
        return `
            <div class="fleet-section">
                <h3>Actions</h3>
                <div class="action-buttons">
                    <button class="btn-small" id="btn-transfer-cargo">Cargo</button>
                    <button class="btn-small" id="btn-transfer-fleet">Xfer Fleet</button>
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

        // Delete individual waypoints
        const deleteButtons = this.container.querySelectorAll('.btn-delete-wp');
        deleteButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                this.deleteWaypoint(index);
            });
        });

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
     * Show add waypoint dialog - pick a destination star, warp, and task.
     */
    async showAddWaypointDialog() {
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

        const targets = stars.concat(wormholeTargets);
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
            const modeIdx = await Dialogs.selectOption(
                'Cargo Task', 'Cargo operation:',
                ['Load', 'Unload', 'Set Amount To']);
            if (modeIdx === null) return;

            const amount = {};
            for (const [label, key] of [
                    ['Ironium', 'ironium'],
                    ['Boranium', 'boranium'],
                    ['Germanium', 'germanium'],
                    ['Colonists', 'colonists_in_kilotons']]) {
                const value = await Dialogs.promptText(
                    'Cargo Amount', `${label} (kT):`, '0');
                if (value === null) return;
                amount[key] = Math.max(0, parseInt(value) || 0);
            }

            taskPayload = {
                type: 'Cargo',
                mode: ['LOAD', 'UNLOAD', 'SET'][modeIdx],
                amount: amount,
                target_name: target.name
            };
        }

        this.addWaypoint(target, warp, tasks[taskIdx], taskPayload);
    },

    /**
     * Add a waypoint (canonical waypoint command).
     */
    async addWaypoint(targetStar, warpFactor, task, taskPayload = null) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await GameState.submitCommand('waypoint', {
                mode: 'Add',
                fleet_key: this.currentFleet.key,
                index: (this.currentFleet.waypoints || []).length,
                waypoint: {
                    position_x: targetStar.position_x,
                    position_y: targetStar.position_y,
                    warp_factor: warpFactor,
                    destination: targetStar.name,
                    task: taskPayload ||
                          { type: task === 'None' ? 'NoTask'
                                 : task === 'Lay Mines' ? 'LayMines'
                                 : task === 'Remote Mining' ? 'RemoteMine'
                                 : task }
                }
            });

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
