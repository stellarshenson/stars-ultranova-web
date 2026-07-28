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

    // Victory targets: [settings key, wizard caption, default checked,
    // default value, max]. Captions and defaults follow the C# New
    // Game wizard (NewGameWizard.Designer.cs) and GameSettings.cs:49-58.
    // SecondPlaceScore has no C# wizard control (defect); the web
    // exposes it with the canonical "exceeds second place by N%" label.
    VICTORY_TARGETS: [
        ['planets_owned', 'Owns the following number of planets (%)', true, 60, 100],
        ['tech_levels', 'Attains the following tech-level', false, 22, 26],
        ['number_of_fields', 'In the following number of fields', false, 4, 6],
        ['total_score', 'Exceeds a score of', false, 1000, 100000],
        ['second_place_score', 'Exceeds second-place score by (%)', false, 0, 1000],
        ['production_capacity', 'Has production capacity of (in K resources)', false, 1000, 100000],
        ['capital_ships', 'Number of capital ships', false, 100, 100000],
        ['highest_score', 'Has the highest score after (years)', false, 100, 10000]
    ],

    /**
     * Show New Game dialog.
     */
    showNewGame() {
        const victoryRows = this.VICTORY_TARGETS.map(([key, caption, checked, value, max]) => `
                        <div class="form-group">
                            <label>
                                <input type="checkbox" id="victory-${key}-enabled" ${checked ? 'checked' : ''}>
                                ${caption}
                                <input type="number" id="victory-${key}-value" class="form-input"
                                       value="${value}" min="0" max="${max}"
                                       style="width: 6em; margin-left: 4px;">
                            </label>
                        </div>`).join('');

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
                        <!-- Options are filled from GET
                             /api/games/universe-sizes so the light-year
                             figures come from the generator's table and
                             are never restated here -->
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
                    <label>
                        <input type="checkbox" id="accelerated-start">
                        Accelerated BBS play (start with 100,000 colonists)
                    </label>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="mystery-trader" checked>
                        Mystery Trader (enigmatic ship crossing the galaxy mid-game)
                    </label>
                </div>

                <fieldset>
                    <legend>Victory Conditions</legend>
                    <p class="info-text">Victory is declared when a player:</p>
                    ${victoryRows}
                    <div class="form-group">
                        <label>
                            Number of targets to meet
                            <input type="number" id="victory-targets-to-meet" class="form-input"
                                   value="1" min="1" max="8"
                                   style="width: 6em; margin-left: 4px;">
                        </label>
                    </div>
                    <div class="form-group">
                        <label>
                            Minimum game time (years)
                            <input type="number" id="victory-minimum-game-time" class="form-input"
                                   value="50" min="10" max="10000"
                                   style="width: 6em; margin-left: 4px;">
                        </label>
                    </div>
                </fieldset>

                <div class="form-group">
                    <label for="player-race">Your Race</label>
                    <div class="race-select-row">
                        <span id="player-race-icon">${RaceIcons.svg(0, 28)}</span>
                        <select id="player-race" class="form-select">
                            <option value="">Default (Humanoids)</option>
                            ${this.getCustomRaces().map((r, i) =>
                                `<option value="${i}">${r.name} (${r.prt || 'JOAT'})</option>`
                            ).join('')}
                        </select>
                    </div>
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

        // Fill the universe size options from the canonical table
        this.populateUniverseSizes();

        // Bind create button
        document.getElementById('btn-create-game')?.addEventListener('click', async () => {
            const name = document.getElementById('game-name').value || 'New Game';
            const playerCount = parseInt(document.getElementById('player-count').value) || 2;
            const universeSize = document.getElementById('universe-size').value || 'medium';
            const density = document.getElementById('star-density').value || 'normal';
            const seed = document.getElementById('game-seed').value || null;
            const acceleratedStart = document.getElementById('accelerated-start').checked;
            const mysteryTrader = document.getElementById('mystery-trader').checked;

            const raceIdx = document.getElementById('player-race').value;
            const race = raceIdx === '' ? null
                : (this.getCustomRaces()[parseInt(raceIdx)] || null);

            const victory = {
                targets_to_meet: parseInt(document.getElementById('victory-targets-to-meet').value) || 1,
                minimum_game_time: parseInt(document.getElementById('victory-minimum-game-time').value) || 50
            };
            for (const [key] of this.VICTORY_TARGETS) {
                victory[key] = {
                    enabled: document.getElementById(`victory-${key}-enabled`).checked,
                    value: parseInt(document.getElementById(`victory-${key}-value`).value) || 0
                };
            }

            try {
                await GameState.createGame(name, playerCount, universeSize, density, seed, race, acceleratedStart, victory, mysteryTrader);
                this.close();
            } catch (error) {
                alert('Failed to create game: ' + error.message);
            }
        });

        // Race emblem preview follows the selected race
        document.getElementById('player-race')?.addEventListener('change', (e) => {
            const iconEl = document.getElementById('player-race-icon');
            if (!iconEl) return;
            const selected = e.target.value === '' ? null
                : (this.getCustomRaces()[parseInt(e.target.value)] || null);
            iconEl.innerHTML = selected
                ? RaceIcons.render(selected.icon || 0, selected.customIcon, 28)
                : RaceIcons.svg(0, 28);
        });

        // Bind race designer button: reopen New Game afterwards so the
        // freshly saved race appears in the selector
        document.getElementById('btn-design-race')?.addEventListener('click', () => {
            if (window.RaceWizard) {
                this.close();
                RaceWizard.show();
            }
        });
    },

    /**
     * Fill the universe size selector from the canonical table.
     *
     * The generator's UNIVERSE_SIZES is the single source of truth for
     * board dimensions; the labels quote whatever it says, so a size
     * change never leaves a stale "(600 ly)" behind on the client.
     */
    async populateUniverseSizes() {
        const select = document.getElementById('universe-size');
        if (!select) return;
        let sizes;
        try {
            sizes = await ApiClient.getUniverseSizes();
        } catch (error) {
            console.error('Failed to load universe sizes:', error);
            return;
        }
        select.innerHTML = sizes.map(size => {
            const label = size.name.charAt(0).toUpperCase() + size.name.slice(1);
            const selected = size.name === 'medium' ? ' selected' : '';
            return `<option value="${size.name}"${selected}>`
                + `${label} (${size.width} ly)</option>`;
        }).join('');
    },

    /**
     * Custom races saved by the race wizard (localStorage).
     */
    getCustomRaces() {
        try {
            return JSON.parse(localStorage.getItem('customRaces') || '[]');
        } catch (e) {
            return [];
        }
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
     * Show the victory announcement for a newly declared winner.
     * @param {number} victorId - Winning empire id
     */
    showVictory(victorId) {
        const record = (GameState.scores || []).find(s => s.empire_id === victorId);
        const raceName = record?.race_name || `Empire ${victorId}`;
        const suffix = victorId === GameState.empireId
            ? 'You are victorious!'
            : 'The game continues, but a victor has been declared.';

        const html = `
            <div class="dialog-header">
                <h2>Victory</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <p>The ${raceName} have won the game</p>
                <p class="info-text">Year ${GameState.game?.turn || ''}. ${suffix}</p>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">Continue</button>
            </div>
        `;

        this.show(html);
    },

    /**
     * Show progress toward each enabled victory target
     * (GameState.victoryStatus from the player state payload).
     */
    showVictoryConditions() {
        const status = GameState.victoryStatus;
        if (!status) {
            this.showMessage('Victory Conditions', 'No game loaded.');
            return;
        }

        const captions = {};
        for (const [key, caption] of this.VICTORY_TARGETS) {
            captions[key] = caption;
        }

        const rows = Object.entries(status.targets)
            .map(([key, t]) => {
                const state = !t.enabled ? 'off'
                    : (t.met ? 'MET' : 'in progress');
                return `
                    <tr class="${t.enabled ? '' : 'disabled'}">
                        <td>${captions[key] || key}</td>
                        <td class="number">${t.value}</td>
                        <td class="number">${t.progress}</td>
                        <td>${state}</td>
                    </tr>`;
            }).join('');

        const minTimeMet = status.game_time >= status.minimum_game_time;
        const html = `
            <div class="dialog-header">
                <h2>Victory Conditions</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <p class="info-text">
                    Targets to meet: ${status.targets_to_meet}.
                    Minimum game time: ${status.minimum_game_time} years
                    (${status.game_time} elapsed${minTimeMet ? '' : ' - victory not yet possible'}).
                </p>
                <div class="report-table-container">
                    <table class="report-table">
                        <thead>
                            <tr>
                                <th>Target</th>
                                <th>Goal</th>
                                <th>Progress</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">OK</button>
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
    },

    /**
     * Show a simple message dialog.
     * @param {string} title - Dialog title
     * @param {string} message - Message to display (supports newlines)
     */
    showMessage(title, message) {
        const formattedMessage = message.replace(/\n/g, '<br>');

        const html = `
            <div class="dialog-header">
                <h2>${title}</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <p style="white-space: pre-wrap; font-family: monospace; font-size: 0.85rem;">${formattedMessage}</p>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">OK</button>
            </div>
        `;

        this.show(html);
    },

    /**
     * Show a select/dropdown dialog.
     * @param {string} title - Dialog title
     * @param {string} label - Label for the select field
     * @param {Array} options - Array of {value, label} objects
     * @param {Function} callback - Called with selected value
     */
    showSelectDialog(title, label, options, callback) {
        const optionsHtml = options.map(opt =>
            `<option value="${opt.value}">${opt.label}</option>`
        ).join('');

        const html = `
            <div class="dialog-header">
                <h2>${title}</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <div class="form-group">
                    <label for="select-dialog-value">${label}</label>
                    <select id="select-dialog-value" class="form-select">
                        ${optionsHtml}
                    </select>
                </div>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" id="btn-select-confirm">OK</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;

        this.show(html);

        document.getElementById('btn-select-confirm')?.addEventListener('click', () => {
            const selected = document.getElementById('select-dialog-value')?.value;
            this.close();
            if (callback && selected) {
                callback(selected);
            }
        });

        // Also allow double-click on select to confirm
        document.getElementById('select-dialog-value')?.addEventListener('dblclick', () => {
            const selected = document.getElementById('select-dialog-value')?.value;
            this.close();
            if (callback && selected) {
                callback(selected);
            }
        });
    },

    /**
     * Show an input prompt dialog.
     * @param {string} title - Dialog title
     * @param {string} label - Label for the input field
     * @param {string} defaultValue - Default value for input
     * @param {Function} callback - Called with entered value
     */
    showPrompt(title, label, defaultValue, callback) {
        const html = `
            <div class="dialog-header">
                <h2>${title}</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>

            <div class="dialog-body">
                <div class="form-group">
                    <label for="prompt-dialog-value">${label}</label>
                    <input type="text" id="prompt-dialog-value" class="form-input" value="${defaultValue || ''}">
                </div>
            </div>

            <div class="dialog-footer">
                <button class="btn-primary" id="btn-prompt-confirm">OK</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;

        this.show(html);

        // Focus the input
        const input = document.getElementById('prompt-dialog-value');
        input?.focus();
        input?.select();

        document.getElementById('btn-prompt-confirm')?.addEventListener('click', () => {
            const value = document.getElementById('prompt-dialog-value')?.value;
            this.close();
            if (callback) {
                callback(value);
            }
        });

        // Enter to confirm
        input?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const value = input.value;
                this.close();
                if (callback) {
                    callback(value);
                }
            }
        });
    },

    /**
     * Promise-based option picker. items may be strings or {value,label}.
     * Resolves with the selected INDEX, or null when cancelled.
     */
    selectOption(title, label, items) {
        return new Promise((resolve) => {
            const optionsHtml = items.map((item, i) => {
                const text = typeof item === 'string' ? item : item.label;
                return `<option value="${i}">${text}</option>`;
            }).join('');

            const html = `
                <div class="dialog-header">
                    <h2>${title}</h2>
                    <button class="btn-close" id="btn-select-cancel-x">X</button>
                </div>
                <div class="dialog-body">
                    <div class="form-group">
                        <label for="select-dialog-value">${label}</label>
                        <select id="select-dialog-value" class="form-select" size="${Math.min(items.length, 12)}">
                            ${optionsHtml}
                        </select>
                    </div>
                </div>
                <div class="dialog-footer">
                    <button class="btn-primary" id="btn-select-confirm">OK</button>
                    <button class="btn-secondary" id="btn-select-cancel">Cancel</button>
                </div>
            `;

            this.show(html);
            const select = document.getElementById('select-dialog-value');
            if (select && items.length > 0) select.value = '0';

            const finish = (value) => { this.close(); resolve(value); };
            const confirm = () => {
                const v = select ? select.value : null;
                finish(v === null || v === '' ? null : parseInt(v));
            };

            document.getElementById('btn-select-confirm')?.addEventListener('click', confirm);
            select?.addEventListener('dblclick', confirm);
            select?.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirm(); });
            document.getElementById('btn-select-cancel')?.addEventListener('click', () => finish(null));
            document.getElementById('btn-select-cancel-x')?.addEventListener('click', () => finish(null));
        });
    },

    /**
     * Promise-based text prompt. Resolves with the string, or null on cancel.
     */
    promptText(title, label, defaultValue = '') {
        return new Promise((resolve) => {
            const html = `
                <div class="dialog-header">
                    <h2>${title}</h2>
                    <button class="btn-close" id="btn-prompt-cancel-x">X</button>
                </div>
                <div class="dialog-body">
                    <div class="form-group">
                        <label for="prompt-dialog-value">${label}</label>
                        <input type="text" id="prompt-dialog-value" class="form-input" value="${defaultValue}">
                    </div>
                </div>
                <div class="dialog-footer">
                    <button class="btn-primary" id="btn-prompt-confirm">OK</button>
                    <button class="btn-secondary" id="btn-prompt-cancel">Cancel</button>
                </div>
            `;

            this.show(html);
            const input = document.getElementById('prompt-dialog-value');
            input?.focus();
            input?.select();

            const finish = (value) => { this.close(); resolve(value); };
            document.getElementById('btn-prompt-confirm')?.addEventListener('click', () => finish(input ? input.value : null));
            input?.addEventListener('keydown', (e) => { if (e.key === 'Enter') finish(input.value); });
            document.getElementById('btn-prompt-cancel')?.addEventListener('click', () => finish(null));
            document.getElementById('btn-prompt-cancel-x')?.addEventListener('click', () => finish(null));
        });
    },

    // Battle plan option lists. Tactic and attack strings match the
    // C# dialog exactly (BattlePlans.Designer.cs:168-174, 147-150);
    // the five target tiers use the stars-nova trunk Victims model
    // consumed by the Ron engine (backend battle_plan.Victims), not
    // the C# 2-tier string list.
    BATTLE_PLAN_TACTICS: [
        'Disengage', 'Disengage if Challenged', 'Maximise Damage',
        'Maximise Damage Ratio', 'Maximise Net Damage',
        'Minimise Damage to Self'
    ],
    BATTLE_PLAN_ATTACK: ['Enemies', 'Enemies and Neutrals', 'Everyone'],
    BATTLE_PLAN_TARGETS: [
        { value: 0, label: 'Starbase' },
        { value: 1, label: 'Bomber' },
        { value: 2, label: 'Capital Ship' },
        { value: 3, label: 'Escort' },
        { value: 4, label: 'Armed Ship' },
        { value: 5, label: 'Any Ship' },
        { value: 6, label: 'Support Ship' },
        { value: 7, label: 'Logistics' }
    ],
    // Doctrine axes (backend battle_plan.STANCES / POSTURES /
    // WITHDRAW_OPTIONS). They sit behind a disclosure: picking a named
    // plan is the default path, the parameters are the opt-in
    BATTLE_PLAN_STANCES: ['Aggressive', 'Balanced', 'Defensive'],
    BATTLE_PLAN_POSTURES: ['Standard', 'Brace', 'Scatter'],
    BATTLE_PLAN_WITHDRAW: ['Never', 'On Damage', 'Half Armour',
                           'Outnumbered'],

    /**
     * Battle Plans dialog - two-pane layout after the C# BattlePlans
     * dialog (BattlePlans.Designer.cs): plan list on the left, plan
     * details on the right. Unlike C# Nova, New/Save/Delete work (the
     * C# buttons exist but are disabled, Designer.cs:94,104 - plan
     * editing was never implemented there).
     */
    showBattlePlans(selectedName = null) {
        const plans = GameState.battlePlans || {};
        const names = Object.keys(plans);
        if (!names.length) {
            ApiClient.showStatus('No battle plans available', 'error');
            return;
        }
        if (!selectedName || !plans[selectedName]) {
            selectedName = names.includes('Default') ? 'Default' : names[0];
        }

        const empireDefault = GameState.defaultBattlePlan || 'Default';
        const listHtml = names.map(n =>
            `<option value="${n}" ${n === selectedName ? 'selected' : ''}>` +
            `${n}${n === empireDefault ? ' (default)' : ''}</option>`
        ).join('');
        const targetOptions = (selected) => this.BATTLE_PLAN_TARGETS.map(t =>
            `<option value="${t.value}" ${t.value === selected ? 'selected' : ''}>${t.label}</option>`
        ).join('');
        const axisOptions = (values, selected) => values.map(v =>
            `<option ${v === selected ? 'selected' : ''}>${v}</option>`
        ).join('');
        const tiers = [
            ['primary_target', 'Primary Target'],
            ['secondary_target', 'Secondary Target'],
            ['tertiary_target', 'Tertiary Target'],
            ['quaternary_target', 'Quaternary Target'],
            ['quinary_target', 'Quinary Target']
        ];
        const plan = plans[selectedName];

        const html = `
            <div class="dialog-header">
                <h2>Battle Plans</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>
            <div class="dialog-body">
                <div style="display: flex; gap: 16px;">
                    <div class="form-group" style="flex: 1;">
                        <label for="battle-plan-list">Available Plans</label>
                        <select id="battle-plan-list" class="form-select"
                                size="${Math.min(Math.max(names.length, 6), 14)}">
                            ${listHtml}
                        </select>
                    </div>
                    <fieldset style="flex: 2;">
                        <legend>Plan Details</legend>
                        <div class="form-group">
                            <label for="battle-plan-name">Plan Name</label>
                            <input type="text" id="battle-plan-name" class="form-input"
                                   value="${plan.name}">
                        </div>
                        <div class="form-group">
                            <label for="battle-plan-stance">Stance</label>
                            <select id="battle-plan-stance" class="form-select">
                                ${axisOptions(this.BATTLE_PLAN_STANCES, plan.stance || 'Balanced')}
                            </select>
                        </div>
                        <details class="plan-details">
                            <summary>Detailed parameters</summary>
                            ${tiers.map(([key, label]) => `
                            <div class="form-group">
                                <label for="battle-plan-${key}">${label}</label>
                                <select id="battle-plan-${key}" class="form-select">
                                    ${targetOptions(plan[key])}
                                </select>
                            </div>`).join('')}
                            <div class="form-group">
                                <label for="battle-plan-posture">Posture</label>
                                <select id="battle-plan-posture" class="form-select">
                                    ${axisOptions(this.BATTLE_PLAN_POSTURES, plan.posture || 'Standard')}
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="battle-plan-withdraw">Withdraw When</label>
                                <select id="battle-plan-withdraw" class="form-select">
                                    ${axisOptions(this.BATTLE_PLAN_WITHDRAW, plan.withdraw || 'Never')}
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="battle-plan-tactic">Tactic</label>
                                <select id="battle-plan-tactic" class="form-select">
                                    ${axisOptions(this.BATTLE_PLAN_TACTICS, plan.tactic)}
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="battle-plan-attack">Attack</label>
                                <select id="battle-plan-attack" class="form-select">
                                    ${axisOptions(this.BATTLE_PLAN_ATTACK, plan.attack)}
                                </select>
                            </div>
                        </details>
                    </fieldset>
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn-small" id="btn-battle-plan-new">New</button>
                <button class="btn-primary" id="btn-battle-plan-save">Save</button>
                <button class="btn-small" id="btn-battle-plan-default"
                        ${selectedName === empireDefault ? 'disabled' : ''}>Make Default</button>
                <button class="btn-small btn-danger" id="btn-battle-plan-delete"
                        ${selectedName === 'Default' ? 'disabled' : ''}>Delete</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Done</button>
            </div>
        `;

        this.show(html);

        const list = document.getElementById('battle-plan-list');
        list?.addEventListener('change', () => {
            this.showBattlePlans(list.value);
        });

        document.getElementById('btn-battle-plan-new')?.addEventListener('click', () => {
            const nameInput = document.getElementById('battle-plan-name');
            if (nameInput) {
                nameInput.value = '';
                nameInput.focus();
            }
        });

        document.getElementById('btn-battle-plan-save')?.addEventListener('click', async () => {
            const name = (document.getElementById('battle-plan-name')?.value || '').trim();
            if (!name) {
                ApiClient.showStatus('Plan name cannot be empty', 'error');
                return;
            }
            const payload = {
                name: name,
                tactic: document.getElementById('battle-plan-tactic')?.value,
                attack: document.getElementById('battle-plan-attack')?.value,
                stance: document.getElementById('battle-plan-stance')?.value,
                posture: document.getElementById('battle-plan-posture')?.value,
                withdraw: document.getElementById('battle-plan-withdraw')?.value
            };
            for (const [key] of tiers) {
                payload[key] = parseInt(document.getElementById(`battle-plan-${key}`)?.value) || 0;
            }
            try {
                await GameState.submitCommand('battle_plan', { mode: 'set', plan: payload });
                await GameState.refreshState();
                ApiClient.showStatus(`Battle plan '${name}' saved`, 'success');
                this.showBattlePlans(name);
            } catch (error) {
                ApiClient.showStatus('Failed to save plan: ' + error.message, 'error');
            }
        });

        // The one-dial path: every fleet production builds inherits
        // this plan, so a commander who never opens the fleet panel
        // still fights coherently
        document.getElementById('btn-battle-plan-default')?.addEventListener('click', async () => {
            try {
                await GameState.submitCommand('battle_plan',
                                              { mode: 'default', name: selectedName });
                await GameState.refreshState();
                ApiClient.showStatus(
                    `New fleets will use '${selectedName}'`, 'success');
                this.showBattlePlans(selectedName);
            } catch (error) {
                ApiClient.showStatus('Failed to set default: ' + error.message, 'error');
            }
        });

        document.getElementById('btn-battle-plan-delete')?.addEventListener('click', async () => {
            if (selectedName === 'Default') return;
            try {
                await GameState.submitCommand('battle_plan', { mode: 'delete', name: selectedName });
                await GameState.refreshState();
                ApiClient.showStatus(`Battle plan '${selectedName}' deleted`, 'info');
                this.showBattlePlans();
            } catch (error) {
                ApiClient.showStatus('Failed to delete plan: ' + error.message, 'error');
            }
        });
    },

    /**
     * Imminent Battles dialog - every fleet about to fight, with the
     * engagement override for each.
     *
     * Combat resolves inside turn generation with no player input
     * during the fight, so the window before the turn is generated is
     * the last moment a commander has. An override applies to that
     * battle only: turn generation clears it and the fleet reverts to
     * its standing plan, whether or not the battle happened.
     */
    showImminentBattles() {
        const warnings = GameState.imminentBattles || [];
        const planNames = Object.keys(GameState.battlePlans || {});

        const rows = warnings.map(w => {
            const options = [
                `<option value="">Standing plan (${w.battle_plan})</option>`
            ].concat(planNames.map(name =>
                `<option value="${name}" ${name === w.engagement_plan ? 'selected' : ''}>${name}</option>`
            )).join('');
            const races = [...new Set(w.hostiles.map(h => h.race_name))].join(', ');
            return `
                <tr>
                    <td>${w.fleet_name}</td>
                    <td>${w.arriving ? 'Arriving at' : 'Engaged at'} ${w.location}</td>
                    <td>${w.hostile_ships} ship${w.hostile_ships === 1 ? '' : 's'} (${races})</td>
                    <td>
                        <select class="form-select imminent-override"
                                data-fleet-key="${w.fleet_key}">${options}</select>
                    </td>
                </tr>`;
        }).join('');

        const body = warnings.length ? `
                <p>These fleets meet hostile forces when the turn is
                generated. A plan chosen here applies to that battle
                only - the fleet reverts to its standing plan
                afterwards.</p>
                <table class="data-table">
                    <thead>
                        <tr><th>Fleet</th><th>Where</th><th>Against</th>
                            <th>This battle only</th></tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>`
            : '<p>No battle is imminent. Nothing of yours is in contact with hostile forces.</p>';

        this.show(`
            <div class="dialog-header">
                <h2>Imminent Battles</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>
            <div class="dialog-body">${body}</div>
            <div class="dialog-footer">
                <button class="btn-secondary" onclick="Dialogs.close()">Done</button>
            </div>
        `);

        document.querySelectorAll('.imminent-override').forEach(select => {
            select.addEventListener('change', async () => {
                try {
                    await ApiClient.setFleetBattlePlan(
                        GameState.game.id,
                        parseInt(select.dataset.fleetKey),
                        GameState.empireId, select.value, true);
                    await GameState.refreshState();
                    ApiClient.showStatus(select.value
                        ? `This battle only: ${select.value}`
                        : 'Reverted to the standing plan', 'info');
                } catch (error) {
                    ApiClient.showStatus(
                        'Failed to set engagement plan: ' + error.message, 'error');
                }
            });
        });
    }
};

// Export
window.Dialogs = Dialogs;
