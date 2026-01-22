/**
 * Stars Nova Web - Dialogs
 * Modal dialogs for game operations.
 * New Game, Load Game, Settings dialogs.
 */

const Dialogs = {
    // Overlay element
    overlay: null,

    /**
     * Initialize dialogs system.
     */
    init() {
        // Create overlay container if it doesn't exist
        this.overlay = document.getElementById('dialog-overlay');
        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.id = 'dialog-overlay';
            this.overlay.className = 'dialog-overlay hidden';
            document.body.appendChild(this.overlay);
        }

        // Close on overlay click
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this.close();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.overlay.classList.contains('hidden')) {
                this.close();
            }
        });

        console.log('Dialogs initialized');
    },

    /**
     * Show a dialog.
     */
    show(html) {
        if (!this.overlay) return;
        this.overlay.innerHTML = `<div class="dialog-content">${html}</div>`;
        this.overlay.classList.remove('hidden');
    },

    /**
     * Close current dialog.
     */
    close() {
        if (this.overlay) {
            this.overlay.classList.add('hidden');
            this.overlay.innerHTML = '';
        }
    },

    /**
     * Show New Game dialog.
     */
    showNewGame() {
        const html = `
            <div class="dialog-header">
                <h2>New Game</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <div class="form-group">
                    <label for="game-name">Game Name</label>
                    <input type="text" id="game-name" value="New Game" class="form-input">
                </div>

                <div class="form-group">
                    <label for="player-count">Number of Players</label>
                    <select id="player-count" class="form-select">
                        <option value="2">2 Players</option>
                        <option value="3">3 Players</option>
                        <option value="4">4 Players</option>
                        <option value="5">5 Players</option>
                        <option value="6">6 Players</option>
                        <option value="8">8 Players</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="universe-size">Universe Size</label>
                    <select id="universe-size" class="form-select">
                        <option value="tiny">Tiny (200 ly)</option>
                        <option value="small">Small (400 ly)</option>
                        <option value="medium" selected>Medium (600 ly)</option>
                        <option value="large">Large (800 ly)</option>
                        <option value="huge">Huge (1000 ly)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="star-density">Star Density</label>
                    <select id="star-density" class="form-select">
                        <option value="sparse">Sparse</option>
                        <option value="normal" selected>Normal</option>
                        <option value="dense">Dense</option>
                        <option value="packed">Packed</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="game-seed">Seed (optional)</label>
                    <input type="number" id="game-seed" placeholder="Random" class="form-input">
                </div>

                <div class="form-group">
                    <button class="btn-small" id="btn-design-race">Design Custom Race...</button>
                </div>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" id="btn-create-game">Create Game</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;

        this.show(html);

        // Bind create button
        document.getElementById('btn-create-game')?.addEventListener('click', async () => {
            const name = document.getElementById('game-name').value || 'New Game';
            const playerCount = parseInt(document.getElementById('player-count').value) || 2;
            const universeSize = document.getElementById('universe-size').value || 'medium';
            const density = document.getElementById('star-density').value || 'normal';
            const seed = document.getElementById('game-seed').value || null;

            try {
                await GameState.createGame(name, playerCount, universeSize, density, seed);
                this.close();
            } catch (error) {
                alert('Failed to create game: ' + error.message);
            }
        });

        // Bind race designer button
        document.getElementById('btn-design-race')?.addEventListener('click', () => {
            if (window.RaceWizard) {
                RaceWizard.show();
            }
        });
    },

    /**
     * Show Load Game dialog.
     */
    async showLoadGame() {
        // Fetch available games
        let games = [];
        try {
            games = await ApiClient.listGames();
        } catch (error) {
            alert('Failed to load games: ' + error.message);
            return;
        }

        let gamesHtml = '';
        if (games.length === 0) {
            gamesHtml = '<p class="info-text">No saved games found.</p>';
        } else {
            gamesHtml = '<ul class="game-list">';
            for (const game of games) {
                gamesHtml += `
                    <li class="game-item" data-id="${game.id}">
                        <div class="game-info">
                            <span class="game-name">${game.name}</span>
                            <span class="game-turn">Turn ${game.turn}</span>
                        </div>
                        <div class="game-actions">
                            <button class="btn-small btn-load-game" data-id="${game.id}">Load</button>
                            <button class="btn-small btn-danger btn-delete-game" data-id="${game.id}">Delete</button>
                        </div>
                    </li>
                `;
            }
            gamesHtml += '</ul>';
        }

        const html = `
            <div class="dialog-header">
                <h2>Load Game</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                ${gamesHtml}
            </div>

            <div class="dialog-footer">
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;

        this.show(html);

        // Bind load buttons
        document.querySelectorAll('.btn-load-game').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const gameId = e.target.dataset.id;
                try {
                    await GameState.loadGame(gameId);
                    this.close();
                } catch (error) {
                    alert('Failed to load game: ' + error.message);
                }
            });
        });

        // Bind delete buttons
        document.querySelectorAll('.btn-delete-game').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const gameId = e.target.dataset.id;
                if (!confirm('Delete this game? This cannot be undone.')) return;

                try {
                    await ApiClient.deleteGame(gameId);
                    this.showLoadGame(); // Refresh dialog
                } catch (error) {
                    alert('Failed to delete game: ' + error.message);
                }
            });
        });
    },

    /**
     * Show Settings dialog.
     */
    showSettings() {
        // Load current settings
        const settings = this.loadSettings();

        const html = `
            <div class="dialog-header">
                <h2>Settings</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <h3>Display</h3>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-grid" ${settings.showGrid ? 'checked' : ''}>
                        Show Grid
                    </label>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-names" ${settings.showNames ? 'checked' : ''}>
                        Show Names
                    </label>
                </div>

                <h3>Audio</h3>
                <div class="form-group">
                    <label for="setting-volume">Volume</label>
                    <input type="range" id="setting-volume" min="0" max="100"
                           value="${settings.volume}" class="form-range">
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-music" ${settings.music ? 'checked' : ''}>
                        Enable Music
                    </label>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-sfx" ${settings.sfx ? 'checked' : ''}>
                        Enable Sound Effects
                    </label>
                </div>

                <h3>Gameplay</h3>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-autosave" ${settings.autosave ? 'checked' : ''}>
                        Auto-save each turn
                    </label>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="setting-confirm" ${settings.confirmEndTurn ? 'checked' : ''}>
                        Confirm end turn
                    </label>
                </div>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" id="btn-save-settings">Save</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;

        this.show(html);

        // Bind save button
        document.getElementById('btn-save-settings')?.addEventListener('click', () => {
            const newSettings = {
                showGrid: document.getElementById('setting-grid').checked,
                showNames: document.getElementById('setting-names').checked,
                volume: parseInt(document.getElementById('setting-volume').value),
                music: document.getElementById('setting-music').checked,
                sfx: document.getElementById('setting-sfx').checked,
                autosave: document.getElementById('setting-autosave').checked,
                confirmEndTurn: document.getElementById('setting-confirm').checked
            };

            this.saveSettings(newSettings);
            this.applySettings(newSettings);
            this.close();
        });
    },

    /**
     * Load settings from localStorage.
     */
    loadSettings() {
        const defaults = {
            showGrid: true,
            showNames: true,
            volume: 50,
            music: true,
            sfx: true,
            autosave: true,
            confirmEndTurn: true
        };

        try {
            const saved = localStorage.getItem('stars-nova-settings');
            if (saved) {
                return { ...defaults, ...JSON.parse(saved) };
            }
        } catch (e) {
            console.error('Failed to load settings:', e);
        }

        return defaults;
    },

    /**
     * Save settings to localStorage.
     */
    saveSettings(settings) {
        try {
            localStorage.setItem('stars-nova-settings', JSON.stringify(settings));
        } catch (e) {
            console.error('Failed to save settings:', e);
        }
    },

    /**
     * Apply settings to the application.
     */
    applySettings(settings) {
        // Apply to galaxy map
        if (window.GalaxyMap) {
            GalaxyMap.showGrid = settings.showGrid;
            GalaxyMap.showNames = settings.showNames;
            GalaxyMap.render();
        }
    },

    /**
     * Show Turn Report dialog.
     */
    showTurnReport(report) {
        const messages = report.messages || [];

        let messagesHtml = '';
        if (messages.length === 0) {
            messagesHtml = '<p class="info-text">No messages this turn.</p>';
        } else {
            messagesHtml = '<ul class="message-list">';
            for (const msg of messages) {
                const typeClass = msg.type?.toLowerCase().replace(' ', '-') || '';
                messagesHtml += `
                    <li class="message-item ${typeClass}">
                        <span class="message-type">[${msg.type || 'Info'}]</span>
                        <span class="message-text">${msg.text}</span>
                    </li>
                `;
            }
            messagesHtml += '</ul>';
        }

        const html = `
            <div class="dialog-header">
                <h2>Turn ${report.turn} Report</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body turn-report">
                <div class="report-summary">
                    <div class="summary-item">
                        <span class="summary-label">Stars:</span>
                        <span class="summary-value">${report.stars || 0}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Fleets:</span>
                        <span class="summary-value">${report.fleets || 0}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Population:</span>
                        <span class="summary-value">${this.formatNumber(report.population || 0)}</span>
                    </div>
                </div>

                <h3>Messages</h3>
                ${messagesHtml}
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">Continue</button>
            </div>
        `;

        this.show(html);
    },

    /**
     * Show confirmation dialog.
     */
    confirm(title, message) {
        return new Promise((resolve) => {
            const html = `
                <div class="dialog-header">
                    <h2>${title}</h2>
                </div>

                <div class="dialog-body">
                    <p>${message}</p>
                </div>

                <div class="dialog-footer">
                    <button class="btn-primary" id="btn-confirm-yes">Yes</button>
                    <button class="btn-secondary" id="btn-confirm-no">No</button>
                </div>
            `;

            this.show(html);

            document.getElementById('btn-confirm-yes')?.addEventListener('click', () => {
                this.close();
                resolve(true);
            });

            document.getElementById('btn-confirm-no')?.addEventListener('click', () => {
                this.close();
                resolve(false);
            });
        });
    },

    /**
     * Format large numbers.
     */
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
};

// Export
window.Dialogs = Dialogs;
