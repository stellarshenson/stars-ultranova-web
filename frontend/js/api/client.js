/**
 * Stars Nova Web - API Client
 * Handles all communication with the backend API.
 */

// Use relative path for proxy support (base tag handles prefixing)
const API_BASE = 'api';

const ApiClient = {
    // Loading state management
    _loadingCount: 0,

    /**
     * Show loading overlay.
     */
    showLoading(message = 'Loading...') {
        this._loadingCount++;
        if (this._loadingCount === 1) {
            let overlay = document.getElementById('loading-overlay');
            if (!overlay) {
                overlay = document.createElement('div');
                overlay.id = 'loading-overlay';
                overlay.className = 'loading-overlay';
                overlay.innerHTML = `
                    <div class="loading-spinner"></div>
                    <div class="loading-text">${message}</div>
                `;
                document.body.appendChild(overlay);
            } else {
                overlay.querySelector('.loading-text').textContent = message;
                overlay.classList.remove('hidden');
            }
        }
    },

    /**
     * Hide loading overlay.
     */
    hideLoading() {
        this._loadingCount = Math.max(0, this._loadingCount - 1);
        if (this._loadingCount === 0) {
            const overlay = document.getElementById('loading-overlay');
            if (overlay) {
                overlay.classList.add('hidden');
            }
        }
    },

    /**
     * Show status message.
     */
    showStatus(message, type = 'info', duration = 3000) {
        let statusEl = document.getElementById('status-message');
        if (!statusEl) {
            statusEl = document.createElement('div');
            statusEl.id = 'status-message';
            statusEl.className = 'status-message';
            document.body.appendChild(statusEl);
        }

        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;

        if (duration > 0) {
            setTimeout(() => {
                statusEl.classList.add('hidden');
            }, duration);
        }
    },

    /**
     * Make a request to the API.
     */
    async request(method, path, body = null, options = {}) {
        const { showLoading = false, loadingMessage = 'Loading...' } = options;

        if (showLoading) {
            this.showLoading(loadingMessage);
        }

        try {
            const fetchOptions = {
                method,
                headers: {
                    'Content-Type': 'application/json'
                }
            };

            if (body) {
                fetchOptions.body = JSON.stringify(body);
            }

            const response = await fetch(`${API_BASE}${path}`, fetchOptions);

            if (!response.ok) {
                let error;
                try {
                    error = await response.json();
                } catch {
                    error = { detail: `HTTP ${response.status}: ${response.statusText}` };
                }
                throw new Error(error.detail || 'API request failed');
            }

            return response.json();
        } catch (error) {
            console.error(`API Error [${method} ${path}]:`, error);
            this.showStatus(error.message, 'error');
            throw error;
        } finally {
            if (showLoading) {
                this.hideLoading();
            }
        }
    },

    // Games
    async createGame(name, playerCount = 2, universeSize = 'medium', density = 'normal', seed = null, race = null, acceleratedStart = false, victory = null, mysteryTrader = true) {
        return this.request('POST', '/games/', {
            name,
            player_count: playerCount,
            universe_size: universeSize,
            density,
            seed,
            race,
            accelerated_start: acceleratedStart,
            victory,
            mystery_trader: mysteryTrader
        }, { showLoading: true, loadingMessage: 'Creating game...' });
    },

    async listGames() {
        return this.request('GET', '/games/');
    },

    // Races
    async validateRace(race) {
        // Exact server-side advantage-point score for a race wizard
        // payload: {points, legal, leftover_points, breakdown}
        return this.request('POST', '/races/validate', race);
    },

    async getGame(gameId) {
        return this.request('GET', `/games/${gameId}`);
    },

    async deleteGame(gameId) {
        return this.request('DELETE', `/games/${gameId}`, null, {
            showLoading: true, loadingMessage: 'Deleting game...'
        });
    },

    async generateTurn(gameId) {
        return this.request('POST', `/games/${gameId}/turn/generate`, null, {
            showLoading: true, loadingMessage: 'Generating turn...'
        });
    },

    // Stars
    async listStars(gameId) {
        return this.request('GET', `/games/${gameId}/stars/`);
    },

    async getStar(gameId, starName) {
        return this.request('GET', `/games/${gameId}/stars/${encodeURIComponent(starName)}`);
    },

    // Nebulae
    async getNebulae(gameId) {
        return this.request('GET', `/games/${gameId}/nebulae`);
    },

    // Fleets
    async listFleets(gameId) {
        return this.request('GET', `/games/${gameId}/fleets/`);
    },

    async getFleet(gameId, fleetKey) {
        return this.request('GET', `/games/${gameId}/fleets/${fleetKey}`);
    },

    async getFleetWaypoints(gameId, fleetKey) {
        return this.request('GET', `/games/${gameId}/fleets/${fleetKey}/waypoints`);
    },

    async splitFleet(gameId, fleetKey, empireId, keep) {
        // keep: {design_key: quantity to KEEP in this fleet}
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/split`, {
            empire_id: empireId,
            keep
        });
    },

    async mergeFleets(gameId, fleetKey, empireId, otherFleetKey) {
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/merge`, {
            empire_id: empireId,
            other_fleet_key: otherFleetKey
        });
    },

    async getBattles(gameId, empireId) {
        return this.request('GET', `/games/${gameId}/empires/${empireId}/battles`);
    },

    async setFleetBattlePlan(gameId, fleetKey, empireId, plan) {
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/battle-plan`, {
            empire_id: empireId,
            plan
        });
    },

    async transferCargo(gameId, fleetKey, empireId, delta) {
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/cargo`, {
            empire_id: empireId,
            ironium: delta.ironium || 0,
            boranium: delta.boranium || 0,
            germanium: delta.germanium || 0,
            colonists: delta.colonists || 0
        });
    },

    async transferCargoFleet(gameId, fleetKey, empireId, targetFleetKey, delta) {
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/transfer`, {
            empire_id: empireId,
            target_fleet_key: targetFleetKey,
            ironium: delta.ironium || 0,
            boranium: delta.boranium || 0,
            germanium: delta.germanium || 0,
            colonists: delta.colonists || 0,
            fuel: delta.fuel || 0
        });
    },

    async giftToTrader(gameId, fleetKey, empireId, traderKey, delta) {
        // One-way gift to a co-located Mystery Trader (minerals kT,
        // colonists in headcount); the trader always keeps the cargo
        return this.request('POST', `/games/${gameId}/fleets/${fleetKey}/gift`, {
            empire_id: empireId,
            trader_key: traderKey,
            ironium: delta.ironium || 0,
            boranium: delta.boranium || 0,
            germanium: delta.germanium || 0,
            colonists: delta.colonists || 0
        });
    },

    // Empires
    async listEmpires(gameId) {
        return this.request('GET', `/games/${gameId}/empires/`);
    },

    async getEmpire(gameId, empireId) {
        return this.request('GET', `/games/${gameId}/empires/${empireId}`);
    },

    async getPlayerState(gameId, empireId) {
        return this.request('GET', `/games/${gameId}/empires/${empireId}/state`);
    },

    /**
     * Submit a command. commandType is one of waypoint/production/
     * design/research; commandData must match the backend command
     * schema (mode, star_key/fleet_key, production_order/waypoint/...).
     */
    async submitCommand(gameId, empireId, commandType, commandData) {
        return this.request('POST', `/games/${gameId}/empires/${empireId}/commands`, {
            command_type: commandType,
            command_data: commandData
        });
    },

    /**
     * Fling a mineral packet from a starbase mass driver.
     * data: {star, target, warp, ironium, boranium, germanium}.
     */
    async flingPacket(gameId, empireId, data) {
        return this.submitCommand(gameId, empireId, 'fling_packet', data);
    },

    // Designs
    async listHulls() {
        return this.request('GET', '/designs/hulls');
    },

    async getHull(name) {
        return this.request('GET', `/designs/hulls/${encodeURIComponent(name)}`);
    },

    async listEngines() {
        return this.request('GET', '/designs/engines');
    },

    async listComponents(type = null) {
        const path = type ? `/designs/components?type=${type}` : '/designs/components';
        return this.request('GET', path);
    },

    async getComponentStats() {
        return this.request('GET', '/designs/stats');
    }
};

// Export for use in other modules
window.ApiClient = ApiClient;
