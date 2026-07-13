/**
 * Stars Nova Web - Game State Manager
 * Manages the current game state on the client side.
 *
 * State is loaded through the player-scoped endpoint so the client
 * only sees what its empire knows (fog of war applied server-side).
 */

const GameState = {
    // Current game data
    game: null,
    empireId: 1,           // Single-player: human is always empire 1
    stars: [],             // Player-visible view of every star
    fleets: [],            // Own fleets, full detail
    foreignFleets: [],     // Scanned foreign fleet contacts
    relations: [],         // Per-opponent relation (Enemy/Neutral/Friend)
    battlePlans: {},       // Own battle plans keyed by name
    nebulae: null,         // Nebula field data from backend
    messages: [],          // Last turn's messages for this empire
    research: null,        // Research budget/levels/progress
    designs: [],           // Own ship designs
    race: null,            // Own race definition
    storms: [],            // Galactic storms (visible to all)
    minefields: [],        // Minefields known to this empire
    wormholes: [],         // Wormholes discovered by this empire
    scores: [],            // Public score records for all empires
    scoreHistory: {},      // Per-empire score history (empire id -> entries)
    victor: null,          // Winning empire id once victory declared

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
            await this.refreshState();
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
    async createGame(name, playerCount, universeSize, density, seed, race = null, acceleratedStart = false, victory = null) {
        try {
            this.game = await ApiClient.createGame(name, playerCount, universeSize, density, seed, race, acceleratedStart, victory);
            await this.refreshState();
            this.nebulae = await ApiClient.getNebulae(this.game.id);
            this.emit('gameCreated', this.game);
            return this.game;
        } catch (error) {
            console.error('Failed to create game:', error);
            throw error;
        }
    },

    /**
     * Reload the player-scoped state snapshot.
     */
    async refreshState() {
        const state = await ApiClient.getPlayerState(this.game.id, this.empireId);
        this.game.turn = state.turn_year;
        this.stars = state.stars;
        this.fleets = state.fleets;
        this.foreignFleets = state.foreign_fleets || [];
        this.relations = state.relations || [];
        this.battlePlans = state.battle_plans || {};
        this.messages = state.messages || [];
        this.research = state.research;
        this.designs = state.designs || [];
        this.race = state.empire ? state.empire.race : null;
        this.storms = state.storms || [];
        this.minefields = state.minefields || [];
        this.wormholes = state.wormholes || [];
        this.scores = state.scores || [];
        this.scoreHistory = state.score_history || {};

        // Announce a newly declared victor once per session
        const previousVictor = this.victor;
        this.victor = state.victor ?? null;
        if (previousVictor === null && this.victor !== null) {
            this.emit('victory', this.victor);
        }

        // Keep selection pointing at fresh objects
        if (this.selectedStar) {
            this.selectedStar = this.stars.find(s => s.name === this.selectedStar.name) || null;
        }
        if (this.selectedFleet) {
            this.selectedFleet = this.fleets.find(f => f.key === this.selectedFleet.key) || null;
        }

        this.emit('stateRefreshed', state);
        return state;
    },

    /**
     * All fleets to draw on the map (own + scanned contacts).
     */
    get allVisibleFleets() {
        return [...this.fleets, ...this.foreignFleets];
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
     * Submit a command for the player's empire.
     */
    async submitCommand(commandType, commandData) {
        const result = await ApiClient.submitCommand(
            this.game.id, this.empireId, commandType, commandData
        );
        if (result.status === 'error') {
            throw new Error(result.error || 'Command rejected');
        }
        return result;
    },

    /**
     * Generate next turn.
     */
    async generateTurn() {
        if (!this.game) return;

        try {
            const result = await ApiClient.generateTurn(this.game.id);
            this.game.turn = result.turn;
            await this.refreshState();
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
