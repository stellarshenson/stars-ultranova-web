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

        console.log('Fleet panel initialized');
    },

    /**
     * Show panel with fleet data.
     */
    async show(fleet) {
        if (!fleet || !this.container) return;

        this.currentFleet = fleet;
        this.container.classList.remove('hidden');

        // Fetch waypoints if owned by player
        if (fleet.owner === 1 && GameState.game) {
            try {
                const waypoints = await ApiClient.getFleetWaypoints(GameState.game.id, fleet.key);
                fleet.waypoints = waypoints;
            } catch (error) {
                console.error('Failed to fetch waypoints:', error);
                fleet.waypoints = [];
            }
        }

        this.render();
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

        const isOwned = fleet.owner === 1;

        let html = `
            <div class="fleet-panel-header">
                <h2>${fleet.name}</h2>
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
        if (isOwned) {
            this.bindEvents();
        }
    },

    /**
     * Render fleet composition.
     */
    renderComposition(fleet) {
        const tokens = fleet.tokens || {};
        const tokenList = Object.values(tokens);

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
        return `
            <div class="fleet-section">
                <h3>Movement</h3>
                <div class="stat-row">
                    <span>Warp Speed:</span>
                    <span class="stat-value">Warp ${fleet.warp_factor || 0}</span>
                </div>
                <div class="stat-row">
                    <span>Max Speed:</span>
                    <span class="stat-value">Warp ${fleet.max_warp || 0}</span>
                </div>
                <div class="stat-row">
                    <span>Range (full):</span>
                    <span class="stat-value">${Math.round(fleet.range_full || 0)} ly</span>
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
                const task = wp.task || 'None';
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
                    <button class="btn-small" id="btn-rename-fleet">Rename</button>
                    <button class="btn-small" id="btn-split-fleet">Split</button>
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

        const splitBtn = document.getElementById('btn-split-fleet');
        if (splitBtn) {
            splitBtn.addEventListener('click', () => this.showSplitDialog());
        }

        const scrapBtn = document.getElementById('btn-scrap-fleet');
        if (scrapBtn) {
            scrapBtn.addEventListener('click', () => this.scrapFleet());
        }
    },

    /**
     * Show add waypoint dialog.
     */
    showAddWaypointDialog() {
        // For now, prompt-based - will be replaced with proper dialog
        const destInput = prompt('Destination (star name or "x,y" coordinates):');
        if (!destInput) return;

        const warpInput = prompt('Warp speed (1-10):', '5');
        const warp = parseInt(warpInput) || 5;

        const taskInput = prompt('Task (None, Colonize, Load, Unload, Scrap):', 'None');

        this.addWaypoint(destInput, warp, taskInput || 'None');
    },

    /**
     * Add a waypoint.
     */
    async addWaypoint(destination, warpFactor, task) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'waypoint',
                    fleet_key: this.currentFleet.key,
                    action: 'add',
                    destination: destination,
                    warp_factor: warpFactor,
                    task: task
                }
            );

            // Re-fetch waypoints
            const waypoints = await ApiClient.getFleetWaypoints(
                GameState.game.id, this.currentFleet.key
            );
            this.currentFleet.waypoints = waypoints;
            this.render();

            // Update galaxy map
            if (window.GalaxyMap) {
                GalaxyMap.render();
            }
        } catch (error) {
            alert('Failed to add waypoint: ' + error.message);
        }
    },

    /**
     * Delete a waypoint.
     */
    async deleteWaypoint(index) {
        if (!this.currentFleet || !GameState.game) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'waypoint',
                    fleet_key: this.currentFleet.key,
                    action: 'delete',
                    index: index
                }
            );

            const waypoints = await ApiClient.getFleetWaypoints(
                GameState.game.id, this.currentFleet.key
            );
            this.currentFleet.waypoints = waypoints;
            this.render();

            if (window.GalaxyMap) {
                GalaxyMap.render();
            }
        } catch (error) {
            alert('Failed to delete waypoint: ' + error.message);
        }
    },

    /**
     * Clear all waypoints.
     */
    async clearWaypoints() {
        if (!this.currentFleet || !GameState.game) return;
        if (!confirm('Clear all waypoints?')) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'waypoint',
                    fleet_key: this.currentFleet.key,
                    action: 'clear'
                }
            );

            this.currentFleet.waypoints = [];
            this.render();

            if (window.GalaxyMap) {
                GalaxyMap.render();
            }
        } catch (error) {
            alert('Failed to clear waypoints: ' + error.message);
        }
    },

    /**
     * Rename fleet.
     */
    async renameFleet() {
        if (!this.currentFleet || !GameState.game) return;

        const newName = prompt('New fleet name:', this.currentFleet.name);
        if (!newName || newName === this.currentFleet.name) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'fleet',
                    fleet_key: this.currentFleet.key,
                    action: 'rename',
                    name: newName
                }
            );

            this.currentFleet.name = newName;
            this.render();

            if (window.GalaxyMap) {
                GalaxyMap.render();
            }
        } catch (error) {
            alert('Failed to rename fleet: ' + error.message);
        }
    },

    /**
     * Show split fleet dialog.
     */
    showSplitDialog() {
        alert('Split fleet dialog not yet implemented.');
    },

    /**
     * Scrap fleet.
     */
    async scrapFleet() {
        if (!this.currentFleet || !GameState.game) return;
        if (!confirm(`Scrap ${this.currentFleet.name}? This cannot be undone.`)) return;

        try {
            // Add scrap waypoint task at current position
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'waypoint',
                    fleet_key: this.currentFleet.key,
                    action: 'set_task',
                    index: 0,
                    task: 'Scrap'
                }
            );

            alert('Fleet will be scrapped at end of turn.');
            this.render();
        } catch (error) {
            alert('Failed to scrap fleet: ' + error.message);
        }
    }
};

// Export
window.FleetPanel = FleetPanel;
