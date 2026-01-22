/**
 * Stars Nova Web - API Client
 * Handles all communication with the backend API.
 */

const API_BASE = '/api';

const ApiClient = {
    /**
     * Make a request to the API.
     */
    async request(method, path, body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${API_BASE}${path}`, options);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }

        return response.json();
    },

    // Games
    async createGame(name, playerCount = 2, universeSize = 'medium') {
        return this.request('POST', '/games/', {
            name,
            player_count: playerCount,
            universe_size: universeSize
        });
    },

    async listGames() {
        return this.request('GET', '/games/');
    },

    async getGame(gameId) {
        return this.request('GET', `/games/${gameId}`);
    },

    async deleteGame(gameId) {
        return this.request('DELETE', `/games/${gameId}`);
    },

    async generateTurn(gameId) {
        return this.request('POST', `/games/${gameId}/turn/generate`);
    },

    // Stars
    async listStars(gameId) {
        return this.request('GET', `/games/${gameId}/stars/`);
    },

    async getStar(gameId, starName) {
        return this.request('GET', `/games/${gameId}/stars/${encodeURIComponent(starName)}`);
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

    async updateFleetWaypoints(gameId, fleetKey, waypoints) {
        return this.request('PUT', `/games/${gameId}/fleets/${fleetKey}/waypoints`, waypoints);
    }
};

// Export for use in other modules
window.ApiClient = ApiClient;
