/**
 * Stars Nova Web - Main Application
 * Initializes the application and handles UI interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    const App = {
        init() {
            this.bindEvents();
            this.initComponents();
            this.setupGameState();
            this.loadSettings();

            console.log('Stars Nova Web initialized');
        },

        /**
         * Initialize all UI components.
         */
        initComponents() {
            // Initialize dialogs first (needed by other components)
            if (window.Dialogs) {
                Dialogs.init();
            }

            // Initialize galaxy map
            if (window.GalaxyMap) {
                GalaxyMap.init('galaxy-map');
            }

            // Initialize panels
            if (window.StarPanel) {
                StarPanel.init('star-panel');
            }

            if (window.FleetPanel) {
                FleetPanel.init('fleet-panel');
            }

            if (window.DesignPanel) {
                DesignPanel.init('design-panel');
            }

            if (window.BattleViewer) {
                BattleViewer.init('battle-viewer');
            }
        },

        /**
         * Bind UI event handlers.
         */
        bindEvents() {
            // Header buttons
            document.getElementById('btn-new-game')?.addEventListener('click', () => {
                Dialogs.showNewGame();
            });

            document.getElementById('btn-load-game')?.addEventListener('click', () => {
                Dialogs.showLoadGame();
            });

            document.getElementById('btn-ship-designer')?.addEventListener('click', () => {
                if (window.DesignPanel) {
                    DesignPanel.toggle();
                }
            });

            document.getElementById('btn-generate-turn')?.addEventListener('click', () => {
                this.generateTurn();
            });

            document.getElementById('btn-settings')?.addEventListener('click', () => {
                Dialogs.showSettings();
            });

            // Menu buttons
            document.getElementById('menu-new-game')?.addEventListener('click', () => {
                Dialogs.showNewGame();
            });

            document.getElementById('menu-continue')?.addEventListener('click', () => {
                this.continueGame();
            });

            document.getElementById('menu-load-game')?.addEventListener('click', () => {
                Dialogs.showLoadGame();
            });

            document.getElementById('menu-settings')?.addEventListener('click', () => {
                Dialogs.showSettings();
            });
        },

        /**
         * Setup game state event listeners.
         */
        setupGameState() {
            GameState.on('gameCreated', (game) => {
                this.onGameLoaded(game);
                this.setStatus(`Created game: ${game.name}`);
            });

            GameState.on('gameLoaded', (game) => {
                this.onGameLoaded(game);
                this.setStatus(`Loaded game: ${game.name} (Turn ${game.turn})`);
            });

            GameState.on('starSelected', (star) => {
                this.setStatus(`Selected: ${star.name}`);
            });

            GameState.on('fleetSelected', (fleet) => {
                this.setStatus(`Selected: ${fleet.name}`);
            });

            GameState.on('selectionCleared', () => {
                this.setStatus('Ready');
            });

            GameState.on('turnGenerated', (turn) => {
                this.setStatus(`Turn ${turn} generated`);
                // Show turn report if there are messages
                if (GameState.game) {
                    this.showTurnReport();
                }
            });
        },

        /**
         * Handle game loaded.
         */
        onGameLoaded(game) {
            this.hideMenu();
            this.showGame();

            // Resize and center galaxy map on homeworld
            // Must resize after showing the container so canvas has dimensions
            if (window.GalaxyMap) {
                GalaxyMap.resize();
                GalaxyMap.centerOnHomeworld();
            }

            // Update empire summary
            this.updateEmpireSummary();
        },

        /**
         * Update the empire summary display.
         */
        updateEmpireSummary() {
            if (!GameState.game) return;

            // Count player's planets and calculate totals
            const playerStars = GameState.stars.filter(s => s.owner === 1);
            const playerFleets = GameState.fleets.filter(f => f.owner === 1);

            const totalPop = playerStars.reduce((sum, s) => sum + (s.colonists || 0), 0);
            const totalIronium = playerStars.reduce((sum, s) => sum + (s.ironium || 0), 0);
            const totalBoranium = playerStars.reduce((sum, s) => sum + (s.boranium || 0), 0);
            const totalGermanium = playerStars.reduce((sum, s) => sum + (s.germanium || 0), 0);

            // Update DOM
            const setPlanets = document.getElementById('summary-planets');
            const setFleets = document.getElementById('summary-fleets');
            const setPop = document.getElementById('summary-population');
            const setResearch = document.getElementById('summary-research');

            if (setPlanets) setPlanets.textContent = playerStars.length;
            if (setFleets) setFleets.textContent = playerFleets.length;
            if (setPop) setPop.textContent = this.formatPopulation(totalPop);
            if (setResearch) setResearch.textContent = '15%';  // Default research budget

            // Update resources
            const resContainer = document.getElementById('summary-resources');
            if (resContainer) {
                const irEl = resContainer.querySelector('.res-ir');
                const boEl = resContainer.querySelector('.res-bo');
                const geEl = resContainer.querySelector('.res-ge');
                if (irEl) irEl.textContent = this.formatNumber(totalIronium);
                if (boEl) boEl.textContent = this.formatNumber(totalBoranium);
                if (geEl) geEl.textContent = this.formatNumber(totalGermanium);
            }
        },

        /**
         * Format population for display.
         */
        formatPopulation(pop) {
            if (pop >= 1000000) {
                return (pop / 1000000).toFixed(1) + 'M';
            } else if (pop >= 1000) {
                return (pop / 1000).toFixed(1) + 'K';
            }
            return pop.toString();
        },

        /**
         * Format number with K/M suffix.
         */
        formatNumber(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(0) + 'K';
            }
            return num.toString();
        },

        /**
         * Continue last game.
         */
        async continueGame() {
            try {
                const games = await ApiClient.listGames();
                if (games.length === 0) {
                    Dialogs.showNewGame();
                    return;
                }

                // Load most recent game
                await GameState.loadGame(games[0].id);
            } catch (error) {
                console.error('Failed to continue:', error);
                Dialogs.showNewGame();
            }
        },

        /**
         * Generate next turn.
         */
        async generateTurn() {
            if (!GameState.game) {
                this.setStatus('No active game');
                return;
            }

            // Check settings for confirmation
            const settings = Dialogs.loadSettings();
            if (settings.confirmEndTurn) {
                const confirmed = await Dialogs.confirm(
                    'Generate Turn',
                    'Are you sure you want to generate the next turn?'
                );
                if (!confirmed) return;
            }

            try {
                this.setStatus('Generating turn...');
                await GameState.generateTurn();
            } catch (error) {
                this.setStatus('Turn generation failed');
                alert('Failed to generate turn: ' + error.message);
            }
        },

        /**
         * Show turn report.
         */
        async showTurnReport() {
            if (!GameState.game) return;

            try {
                // Construct a report from current state
                const report = {
                    turn: GameState.game.turn,
                    stars: GameState.stars.filter(s => s.owner === 1).length,
                    fleets: GameState.fleets.filter(f => f.owner === 1).length,
                    population: GameState.stars
                        .filter(s => s.owner === 1)
                        .reduce((sum, s) => sum + (s.colonists || 0), 0),
                    messages: GameState.game.messages || []
                };

                Dialogs.showTurnReport(report);
            } catch (error) {
                console.error('Failed to show turn report:', error);
            }
        },

        /**
         * Hide main menu.
         */
        hideMenu() {
            document.getElementById('menu-container')?.classList.add('hidden');
        },

        /**
         * Show main menu.
         */
        showMenu() {
            document.getElementById('menu-container')?.classList.remove('hidden');
            document.getElementById('game-container')?.classList.add('hidden');
        },

        /**
         * Show game view.
         */
        showGame() {
            document.getElementById('game-container')?.classList.remove('hidden');
        },

        /**
         * Set status bar text.
         */
        setStatus(text) {
            const statusBar = document.getElementById('status-bar');
            if (statusBar) {
                statusBar.textContent = text;
            }
        },

        /**
         * Load and apply settings.
         */
        loadSettings() {
            if (window.Dialogs) {
                const settings = Dialogs.loadSettings();
                Dialogs.applySettings(settings);
            }
        }
    };

    App.init();
});
