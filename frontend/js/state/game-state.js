/**
 * Stars Nova Web - Game State Manager
 * Manages the current game state on the client side.
 */

const GameState = {
    // Current game data
    game: null,
    stars: [],
    fleets: [],
    nebulae: null,  // Nebula field data from backend

    // Selection state
    selectedStar: null,
    selectedFleet: null,

    // Event handlers
    listeners: {},

    /**
     * Initialize with a game.
     */
    async loadGame(gameId) {
        try {
            this.game = await ApiClient.getGame(gameId);
            this.stars = await ApiClient.listStars(gameId);
            this.fleets = await ApiClient.listFleets(gameId);
            this.nebulae = await ApiClient.getNebulae(gameId);
            this.emit('gameLoaded', this.game);
        } catch (error) {
            console.error('Failed to load game:', error);
            throw error;
        }
    },

    /**
     * Create a new game.
     */
    async createGame(name, playerCount, universeSize, density, seed) {
        try {
            this.game = await ApiClient.createGame(name, playerCount, universeSize, density, seed);
            // Load stars, fleets, and nebulae for the new game
            this.stars = await ApiClient.listStars(this.game.id);
            this.fleets = await ApiClient.listFleets(this.game.id);
            this.nebulae = await ApiClient.getNebulae(this.game.id);
            this.emit('gameCreated', this.game);
            return this.game;
        } catch (error) {
            console.error('Failed to create game:', error);
            throw error;
        }
    },

    /**
     * Select a star.
     */
    selectStar(star) {
        this.selectedStar = star;
        this.selectedFleet = null;
        this.emit('starSelected', star);
    },

    /**
     * Select a fleet.
     */
    selectFleet(fleet) {
        this.selectedFleet = fleet;
        this.selectedStar = null;
        this.emit('fleetSelected', fleet);
    },

    /**
     * Clear selection.
     */
    clearSelection() {
        this.selectedStar = null;
        this.selectedFleet = null;
        this.emit('selectionCleared');
    },

    /**
     * Generate next turn.
     */
    async generateTurn() {
        if (!this.game) return;

        try {
            const result = await ApiClient.generateTurn(this.game.id);
            this.game.turn = result.turn;

            // Reload game data
            this.stars = await ApiClient.listStars(this.game.id);
            this.fleets = await ApiClient.listFleets(this.game.id);

            this.emit('turnGenerated', this.game.turn);
        } catch (error) {
            console.error('Failed to generate turn:', error);
            throw error;
        }
    },

    /**
     * Event handling.
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    },

    off(event, callback) {
        if (!this.listeners[event]) return;
        this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    },

    emit(event, data) {
        if (!this.listeners[event]) return;
        this.listeners[event].forEach(callback => callback(data));
    }
};

// Export
window.GameState = GameState;
