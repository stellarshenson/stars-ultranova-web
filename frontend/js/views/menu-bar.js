/**
 * Stars Nova Web - Menu Bar Component
 * Classic Stars! 1995 style dropdown menu system
 */

const MenuBar = {
    container: null,
    activeMenu: null,
    menuData: null,

    /**
     * Menu structure definition
     */
    MENUS: {
        file: {
            label: 'File',
            items: [
                { id: 'new-game', label: 'New Game...', shortcut: 'Ctrl+N', action: 'newGame' },
                { id: 'open-game', label: 'Open Game...', shortcut: 'Ctrl+O', action: 'openGame' },
                { id: 'close-game', label: 'Close Game', action: 'closeGame' },
                { type: 'separator' },
                { id: 'save-game', label: 'Save Game', shortcut: 'Ctrl+S', action: 'saveGame' },
                { id: 'save-as', label: 'Save Game As...', action: 'saveGameAs' },
                { type: 'separator' },
                { id: 'export-turn-package', label: 'Export Turn Package...', action: 'exportTurnPackage' },
                { id: 'export-orders-file', label: 'Export Orders File...', action: 'exportOrdersFile' },
                { id: 'export-game-file', label: 'Export Game File...', action: 'exportGameFile' },
                { id: 'import-orders-file', label: 'Import Orders File...', action: 'importOrdersFile' },
                { id: 'import-game-file', label: 'Import Game File...', action: 'importGameFile' },
                { type: 'separator' },
                { id: 'exit', label: 'Exit', action: 'exit' }
            ]
        },
        view: {
            label: 'View',
            items: [
                { id: 'scanner-pane', label: 'Scanner Pane', type: 'toggle', checked: true, action: 'toggleScannerPane' },
                { type: 'separator' },
                { id: 'star-names', label: 'Star Names', type: 'toggle', checked: true, shortcut: 'N', action: 'toggleStarNames' },
                { id: 'fleet-paths', label: 'Fleet Paths', type: 'toggle', checked: true, action: 'toggleFleetPaths' },
                { id: 'scanner-ranges', label: 'Scanner Ranges', type: 'toggle', checked: false, shortcut: 'Shift+S', action: 'toggleScannerRanges' },
                { id: 'idle-fleets', label: 'Idle Fleets', type: 'toggle', checked: true, action: 'toggleIdleFleets' },
                { type: 'separator' },
                { id: 'find-star', label: 'Find Star...', shortcut: 'Ctrl+F', action: 'findStar' },
                { id: 'find-fleet', label: 'Find Fleet...', action: 'findFleet' },
                { type: 'separator' },
                { id: 'zoom-in', label: 'Zoom In', shortcut: '+', action: 'zoomIn' },
                { id: 'zoom-out', label: 'Zoom Out', shortcut: '-', action: 'zoomOut' },
                { id: 'zoom-fit', label: 'Zoom to Fit', shortcut: 'Home', action: 'zoomFit' }
            ]
        },
        turn: {
            label: 'Turn',
            items: [
                { id: 'generate-turn', label: 'Generate Turn', shortcut: 'F9', action: 'generateTurn' },
                { type: 'separator' },
                { id: 'wait-all', label: 'Wait for All', action: 'waitForAll' },
                { id: 'submit-orders', label: 'Submit Orders', action: 'submitOrders' }
            ]
        },
        commands: {
            label: 'Commands',
            items: [
                { id: 'rename-fleet', label: 'Rename Fleet...', action: 'renameFleet' },
                { id: 'split-fleet', label: 'Split Fleet...', action: 'splitFleet' },
                { id: 'merge-fleets', label: 'Merge Fleets', action: 'mergeFleets' },
                { type: 'separator' },
                { id: 'transfer-cargo', label: 'Transfer Cargo...', action: 'transferCargo' },
                { type: 'separator' },
                { id: 'player-relations', label: 'Player Relations...', shortcut: 'F7', action: 'playerRelations' },
                { id: 'battle-plans', label: 'Battle Plans...', action: 'battlePlans' },
                { type: 'separator' },
                { id: 'design-ship', label: 'Design Ship...', shortcut: 'F4', action: 'designShip' },
                { type: 'separator' },
                { id: 'research', label: 'Research...', action: 'research' },
                { id: 'production', label: 'Production...', action: 'production' }
            ]
        },
        report: {
            label: 'Report',
            items: [
                { id: 'planet-summary', label: 'Planet Summary', shortcut: 'F3', action: 'planetSummary' },
                { id: 'fleet-summary', label: 'Fleet Summary', action: 'fleetSummary' },
                { type: 'separator' },
                { id: 'research-status', label: 'Research Status', action: 'researchStatus' },
                { id: 'race-summary', label: 'Race Summary', action: 'raceSummary' },
                { type: 'separator' },
                { id: 'score-history', label: 'Score History', action: 'scoreHistory' },
                { id: 'victory-conditions', label: 'Victory Conditions', action: 'victoryConditions' },
                { id: 'battle-history', label: 'Battle History', action: 'battleHistory' }
            ]
        },
        help: {
            label: 'Help',
            items: [
                { id: 'game-manual', label: 'Game Manual', shortcut: 'F1', action: 'gameManual' },
                { id: 'encyclopedia', label: 'Encyclopedia', action: 'encyclopedia' },
                { id: 'keyboard-shortcuts', label: 'Keyboard Shortcuts', action: 'keyboardShortcuts' },
                { type: 'separator' },
                { id: 'about', label: 'About Stars Nova', action: 'about' }
            ]
        }
    },

    /**
     * Toggle state for view menu items
     */
    toggleStates: {
        'scanner-pane': true,
        'star-names': true,
        'fleet-paths': true,
        'scanner-ranges': false,
        'idle-fleets': true
    },

    /**
     * Initialize the menu bar.
     * @param {string} containerId - The ID of the container element
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('MenuBar container not found:', containerId);
            return;
        }

        this.render();
        this.bindEvents();
        this.bindKeyboardShortcuts();

        console.log('MenuBar initialized');
    },

    /**
     * Render the menu bar HTML.
     */
    render() {
        this.container.innerHTML = `
            <div class="menu-bar">
                ${Object.entries(this.MENUS).map(([id, menu]) => `
                    <div class="menu-item" data-menu="${id}">
                        <span class="menu-label">${menu.label}</span>
                        <div class="menu-dropdown hidden" data-dropdown="${id}">
                            ${this.renderMenuItems(menu.items)}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    },

    /**
     * Render menu items HTML.
     * @param {Array} items - Array of menu item definitions
     * @returns {string} HTML string
     */
    renderMenuItems(items) {
        return items.map(item => {
            if (item.type === 'separator') {
                return '<div class="menu-separator"></div>';
            }

            const checkmark = item.type === 'toggle'
                ? `<span class="menu-check">${this.toggleStates[item.id] ? '\u2713' : ''}</span>`
                : '<span class="menu-check"></span>';

            const shortcut = item.shortcut
                ? `<span class="menu-shortcut">${item.shortcut}</span>`
                : '';

            return `
                <div class="menu-action" data-action="${item.action}" data-id="${item.id}" data-toggle="${item.type === 'toggle'}">
                    ${checkmark}
                    <span class="menu-action-label">${item.label}</span>
                    ${shortcut}
                </div>
            `;
        }).join('');
    },

    /**
     * Bind event handlers.
     */
    bindEvents() {
        // Menu item click - show dropdown
        this.container.querySelectorAll('.menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const menuId = item.dataset.menu;
                this.toggleMenu(menuId);
            });

            // Hover to switch menus when one is already open
            item.addEventListener('mouseenter', () => {
                if (this.activeMenu) {
                    const menuId = item.dataset.menu;
                    if (menuId !== this.activeMenu) {
                        this.showMenu(menuId);
                    }
                }
            });
        });

        // Menu action click
        this.container.querySelectorAll('.menu-action').forEach(action => {
            action.addEventListener('click', (e) => {
                e.stopPropagation();
                const actionName = action.dataset.action;
                const itemId = action.dataset.id;
                const isToggle = action.dataset.toggle === 'true';

                if (isToggle) {
                    this.handleToggle(itemId, action);
                } else {
                    this.closeAllMenus();
                }

                this.executeAction(actionName);
            });
        });

        // Click outside to close
        document.addEventListener('click', () => {
            this.closeAllMenus();
        });

        // Escape to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeMenu) {
                this.closeAllMenus();
            }
        });
    },

    /**
     * Bind keyboard shortcuts.
     */
    bindKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't handle shortcuts when typing in inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Function keys
            if (e.key === 'F1') {
                e.preventDefault();
                this.executeAction('gameManual');
            } else if (e.key === 'F3') {
                e.preventDefault();
                this.executeAction('planetSummary');
            } else if (e.key === 'F4') {
                e.preventDefault();
                this.executeAction('designShip');
            } else if (e.key === 'F7') {
                e.preventDefault();
                this.executeAction('playerRelations');
            } else if (e.key === 'F9') {
                e.preventDefault();
                this.executeAction('generateTurn');
            }

            // Ctrl shortcuts
            if (e.ctrlKey) {
                if (e.key === 'n' || e.key === 'N') {
                    e.preventDefault();
                    this.executeAction('newGame');
                } else if (e.key === 'o' || e.key === 'O') {
                    e.preventDefault();
                    this.executeAction('openGame');
                } else if (e.key === 's' || e.key === 'S') {
                    e.preventDefault();
                    this.executeAction('saveGame');
                } else if (e.key === 'f' || e.key === 'F') {
                    e.preventDefault();
                    this.executeAction('findStar');
                }
            }

            // N for star names (without modifiers)
            if (e.key === 'n' && !e.ctrlKey && !e.altKey && !e.metaKey) {
                const item = this.container.querySelector('[data-id="star-names"]');
                if (item) {
                    this.handleToggle('star-names', item);
                    this.executeAction('toggleStarNames');
                }
            }

            // + and - for zoom
            if (e.key === '+' || e.key === '=') {
                this.executeAction('zoomIn');
            } else if (e.key === '-') {
                this.executeAction('zoomOut');
            }

            // Home for zoom to fit
            if (e.key === 'Home') {
                this.executeAction('zoomFit');
            }
        });
    },

    /**
     * Toggle a menu open/closed.
     * @param {string} menuId - Menu identifier
     */
    toggleMenu(menuId) {
        if (this.activeMenu === menuId) {
            this.closeAllMenus();
        } else {
            this.showMenu(menuId);
        }
    },

    /**
     * Show a specific menu dropdown.
     * @param {string} menuId - Menu identifier
     */
    showMenu(menuId) {
        this.closeAllMenus();

        const dropdown = this.container.querySelector(`[data-dropdown="${menuId}"]`);
        const menuItem = this.container.querySelector(`[data-menu="${menuId}"]`);

        if (dropdown && menuItem) {
            dropdown.classList.remove('hidden');
            menuItem.classList.add('active');
            this.activeMenu = menuId;
        }
    },

    /**
     * Close all menu dropdowns.
     */
    closeAllMenus() {
        this.container.querySelectorAll('.menu-dropdown').forEach(dropdown => {
            dropdown.classList.add('hidden');
        });
        this.container.querySelectorAll('.menu-item').forEach(item => {
            item.classList.remove('active');
        });
        this.activeMenu = null;
    },

    /**
     * Handle toggle menu item.
     * @param {string} itemId - Item identifier
     * @param {Element} element - The menu action element
     */
    handleToggle(itemId, element) {
        this.toggleStates[itemId] = !this.toggleStates[itemId];
        const checkEl = element.querySelector('.menu-check');
        if (checkEl) {
            checkEl.textContent = this.toggleStates[itemId] ? '\u2713' : '';
        }
    },

    /**
     * Get toggle state.
     * @param {string} itemId - Item identifier
     * @returns {boolean} Current toggle state
     */
    getToggleState(itemId) {
        return this.toggleStates[itemId] || false;
    },

    /**
     * Set toggle state.
     * @param {string} itemId - Item identifier
     * @param {boolean} state - New state
     */
    setToggleState(itemId, state) {
        this.toggleStates[itemId] = state;
        const element = this.container.querySelector(`[data-id="${itemId}"]`);
        if (element) {
            const checkEl = element.querySelector('.menu-check');
            if (checkEl) {
                checkEl.textContent = state ? '\u2713' : '';
            }
        }
    },

    /**
     * Execute a menu action.
     * @param {string} actionName - Action identifier
     */
    executeAction(actionName) {
        console.log('Menu action:', actionName);

        switch (actionName) {
            // File menu
            case 'newGame':
                if (window.Dialogs) Dialogs.showNewGame();
                break;
            case 'openGame':
                if (window.Dialogs) Dialogs.showLoadGame();
                break;
            case 'closeGame':
                this.closeGame();
                break;
            case 'saveGame':
                this.saveGame();
                break;
            case 'saveGameAs':
                this.saveGameAs();
                break;
            case 'exit':
                // In web app, just go back to menu
                this.closeGame();
                break;

            // Correspondence play (File menu)
            case 'exportTurnPackage':
                this.exportTurnPackage();
                break;
            case 'exportOrdersFile':
                this.exportOrdersFile();
                break;
            case 'exportGameFile':
                this.exportGameFile();
                break;
            case 'importOrdersFile':
                this.importOrdersFile();
                break;
            case 'importGameFile':
                this.importGameFile();
                break;

            // View menu
            case 'toggleScannerPane':
                // Toggle the scanner pane visibility
                break;
            case 'toggleStarNames':
                if (window.GalaxyMap) {
                    GalaxyMap.toggleNames();
                }
                break;
            case 'toggleFleetPaths':
                if (window.GalaxyMap) {
                    GalaxyMap.showWaypoints = this.toggleStates['fleet-paths'];
                    GalaxyMap.render();
                }
                break;
            case 'toggleScannerRanges':
                if (window.GalaxyMap) {
                    GalaxyMap.toggleScannerRange();
                    this.setToggleState('scanner-ranges', GalaxyMap.showScannerRange);
                }
                break;
            case 'toggleIdleFleets':
                // Toggle idle fleet highlighting
                break;
            case 'findStar':
                this.showFindStarDialog();
                break;
            case 'findFleet':
                this.showFindFleetDialog();
                break;
            case 'zoomIn':
                if (window.GalaxyMap) {
                    GalaxyMap.setZoom(GalaxyMap.zoom * 1.2);
                }
                break;
            case 'zoomOut':
                // setZoom clamps to the best-fit zoom-out limit
                if (window.GalaxyMap) {
                    GalaxyMap.setZoom(GalaxyMap.zoom * 0.8);
                }
                break;
            case 'zoomFit':
                if (window.GalaxyMap) {
                    GalaxyMap.zoomToFit();
                }
                break;

            // Turn menu
            case 'generateTurn':
                if (window.GameState && GameState.game) {
                    GameState.generateTurn();
                }
                break;
            case 'waitForAll':
                this.showSubmissionStatus();
                break;
            case 'submitOrders':
                this.submitOrders();
                break;

            // Commands menu
            case 'renameFleet':
                this.renameSelectedFleet();
                break;
            case 'splitFleet':
                if (window.FleetPanel && GameState.selectedFleet) {
                    FleetPanel.showSplitDialog();
                } else {
                    ApiClient.showStatus('Select a fleet first', 'error');
                }
                break;
            case 'mergeFleets':
                if (window.FleetPanel && GameState.selectedFleet) {
                    FleetPanel.showMergeDialog();
                } else {
                    ApiClient.showStatus('Select a fleet first', 'error');
                }
                break;
            case 'transferCargo':
                if (window.FleetPanel && GameState.selectedFleet) {
                    FleetPanel.showCargoDialog();
                } else {
                    ApiClient.showStatus('Select a fleet first', 'error');
                }
                break;
            case 'designShip':
                if (window.DesignPanel) {
                    DesignPanel.toggle();
                }
                break;
            case 'research':
                this.showResearchDialog();
                break;
            case 'playerRelations':
                this.showPlayerRelationsDialog();
                break;
            case 'battlePlans':
                // C# parity: Commands menu opens the BattlePlans
                // dialog (NovaGUI.cs:228-231)
                if (window.Dialogs) Dialogs.showBattlePlans();
                break;
            case 'production':
                if (window.StarPanel && GameState.selectedStar &&
                        GameState.selectedStar.intel === 'owned') {
                    StarPanel.showProductionDialog();
                } else {
                    ApiClient.showStatus('Select one of your planets first', 'error');
                }
                break;

            // Report menu
            case 'planetSummary':
                if (window.Reports) {
                    Reports.show('planets');
                }
                break;
            case 'fleetSummary':
                if (window.Reports) {
                    Reports.show('fleets');
                }
                break;
            case 'researchStatus':
                if (window.Reports) {
                    Reports.show('research');
                }
                break;
            case 'raceSummary':
                // Show race summary
                break;
            case 'scoreHistory':
                // Score report tab includes the score history graph
                if (window.Reports) {
                    Reports.show('score');
                }
                break;
            case 'victoryConditions':
                if (window.Dialogs) {
                    Dialogs.showVictoryConditions();
                }
                break;
            case 'battleHistory':
                if (window.BattleViewer && BattleViewer.showBattleList) {
                    BattleViewer.showBattleList();
                }
                break;

            // Help menu
            case 'gameManual':
                // Open game manual
                this.showHelp();
                break;
            case 'encyclopedia':
                if (window.Encyclopedia) {
                    Encyclopedia.open();
                }
                break;
            case 'keyboardShortcuts':
                this.showKeyboardShortcuts();
                break;
            case 'about':
                this.showAbout();
                break;

            default:
                console.log('Unhandled action:', actionName);
        }
    },

    /**
     * Close the current game.
     */
    closeGame() {
        if (window.GameState) {
            GameState.game = null;
            GameState.stars = [];
            GameState.fleets = [];
        }
        document.getElementById('game-container')?.classList.add('hidden');
        document.getElementById('menu-container')?.classList.remove('hidden');
    },

    /**
     * Save the current game.
     */
    async saveGame() {
        if (!window.GameState || !GameState.game) {
            console.log('No game to save');
            return;
        }
        // Game auto-saves on turn generation
        if (window.ApiClient) {
            ApiClient.showStatus('Game saved', 'success');
        }
    },

    /**
     * Save game with new name.
     */
    async saveGameAs() {
        // For now, just save
        this.saveGame();
    },

    // =========================================================================
    // Correspondence play (acc-crit Correspondence Play section):
    // the game travels between people as versioned JSON files
    // =========================================================================

    /**
     * Download a JSON payload as a file.
     */
    downloadJson(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)],
            { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },

    /**
     * Pick a local JSON file and pass the parsed object to callback.
     */
    pickJsonFile(callback) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json,application/json';
        input.addEventListener('change', async () => {
            const file = input.files[0];
            if (!file) return;
            try {
                callback(JSON.parse(await file.text()));
            } catch (error) {
                ApiClient.showStatus('Not a valid JSON file', 'error');
            }
        });
        input.click();
    },

    _requireGame() {
        if (!window.GameState || !GameState.game) {
            ApiClient.showStatus('No game loaded', 'error');
            return false;
        }
        return true;
    },

    /**
     * Export this empire's fog-of-war turn package.
     */
    async exportTurnPackage() {
        if (!this._requireGame()) return;
        try {
            const pkg = await ApiClient.getTurnPackage(
                GameState.game.id, GameState.empireId);
            this.downloadJson(pkg,
                `empire-${pkg.empire_id}-${pkg.turn_year}.turn.json`);
            ApiClient.showStatus('Turn package exported', 'success');
        } catch (error) { /* status already shown */ }
    },

    /**
     * Export this empire's orders for the current year.
     */
    async exportOrdersFile() {
        if (!this._requireGame()) return;
        try {
            const orders = await ApiClient.getOrdersFile(
                GameState.game.id, GameState.empireId);
            this.downloadJson(orders,
                `empire-${orders.empire_id}-${orders.turn_year}.orders.json`);
            ApiClient.showStatus(
                `Orders file exported (${orders.orders.length} orders)`,
                'success');
        } catch (error) { /* status already shown */ }
    },

    /**
     * Export the full game file (host/carrier only).
     */
    async exportGameFile() {
        if (!this._requireGame()) return;
        try {
            const file = await ApiClient.exportGame(GameState.game.id);
            this.downloadJson(file,
                `${GameState.game.name}-${file.turn_year}.game.json`);
            ApiClient.showStatus('Game file exported', 'success');
        } catch (error) { /* status already shown */ }
    },

    /**
     * Import a player's orders file into the current game.
     */
    importOrdersFile() {
        if (!this._requireGame()) return;
        this.pickJsonFile(async (data) => {
            try {
                const result = await ApiClient.importOrders(
                    GameState.game.id, data);
                await GameState.refreshState();
                ApiClient.showStatus(
                    `Orders imported for empire ${result.empire_id}: ` +
                    `${result.orders_applied} applied, turn locked`,
                    'success');
            } catch (error) {
                // 409 stale year / 401 password surfaced verbatim by
                // ApiClient.showStatus already
            }
        });
    },

    /**
     * Import a full game file as a new game and load it.
     */
    importGameFile() {
        this.pickJsonFile(async (data) => {
            try {
                const imported = await ApiClient.importGame(data);
                if (window.Dialogs && data.note) {
                    // The game file is host/carrier material and
                    // says so on import (fog integrity criterion)
                    Dialogs.showMessage('Game File Imported',
                        `${data.note}\n\nImported as "${imported.name}" ` +
                        `at year ${imported.turn}.`);
                }
                await GameState.loadGame(imported.id);
                document.getElementById('menu-container')?.classList.add('hidden');
                document.getElementById('game-container')?.classList.remove('hidden');
            } catch (error) { /* status already shown */ }
        });
    },

    /**
     * Submit (lock) this empire's orders for the year.
     */
    async submitOrders() {
        if (!this._requireGame()) return;
        try {
            const result = await GameState.submitOrders();
            ApiClient.showStatus(
                `Orders submitted for ${result.turn_year}`, 'success');
            this.showSubmissionStatus();
        } catch (error) { /* status already shown */ }
    },

    /**
     * Per-empire submission status (the C# console player list:
     * "No Orders" until an empire first submits).
     */
    async showSubmissionStatus() {
        if (!this._requireGame()) return;
        try {
            const subs = await ApiClient.getSubmissions(GameState.game.id);
            const lines = subs.map(s => {
                const status = s.turn_submitted
                    ? `Submitted ${s.last_turn_submitted}`
                    : (s.last_turn_submitted === 0
                        ? 'No Orders'
                        : `Waiting (last ${s.last_turn_submitted})`);
                return `${s.race_name} (${s.ai_program}): ${status}`;
            });
            if (window.Dialogs) {
                Dialogs.showMessage('Turn Submissions', lines.join('\n'));
            }
        } catch (error) { /* status already shown */ }
    },

    /**
     * Show find star dialog.
     */
    showFindStarDialog() {
        if (!window.Dialogs || !window.GameState) return;

        const stars = GameState.stars || [];
        const options = stars.map(s => ({ value: s.name, label: s.name }));

        Dialogs.showSelectDialog('Find Star', 'Select a star:', options, (starName) => {
            const star = stars.find(s => s.name === starName);
            if (star && window.GalaxyMap) {
                GalaxyMap.centerOn(star.position_x, star.position_y);
                GameState.selectStar(star);
            }
        });
    },

    /**
     * Show find fleet dialog.
     */
    showFindFleetDialog() {
        if (!window.Dialogs || !window.GameState) return;

        const fleets = GameState.fleets || [];
        const options = fleets.map(f => ({ value: f.key, label: f.name }));

        Dialogs.showSelectDialog('Find Fleet', 'Select a fleet:', options, (fleetKey) => {
            const fleet = fleets.find(f => f.key === fleetKey);
            if (fleet && window.GalaxyMap) {
                GalaxyMap.centerOn(fleet.position_x, fleet.position_y);
                GameState.selectFleet(fleet);
            }
        });
    },

    /**
     * Rename the selected fleet.
     */
    renameSelectedFleet() {
        if (!window.GameState || !GameState.selectedFleet) {
            ApiClient.showStatus('Select a fleet first', 'error');
            return;
        }
        if (window.FleetPanel) {
            FleetPanel.renameFleet();
        }
    },

    /**
     * Research settings dialog - budget and next research field.
     */
    async showResearchDialog() {
        const research = GameState.research;
        if (!research) {
            ApiClient.showStatus('No research data available', 'error');
            return;
        }

        const fields = ['Energy', 'Weapons', 'Propulsion', 'Construction', 'Electronics', 'Biotechnology'];
        const currentTarget = fields.find(f => (research.topics || {})[f] === 1) || 'Energy';

        const items = fields.map(f => {
            const lvl = (research.levels || {})[f] || 0;
            const progress = (research.progress || {})[f] || 0;
            const cost = (research.next_costs || {})[f] || 0;
            const marker = f === currentTarget ? ' (current)' : '';
            return `${f} - level ${lvl}, ${progress}/${cost} to next${marker}`;
        });

        const fieldIdx = await Dialogs.selectOption(
            'Research', 'Field to research next:', items
        );
        if (fieldIdx === null) return;

        const budgetStr = await Dialogs.promptText(
            'Research Budget', 'Percent of resources to research (0-100):',
            String(research.budget)
        );
        if (budgetStr === null) return;
        const budget = Math.max(0, Math.min(100, parseInt(budgetStr) || 0));

        const topics = {};
        for (const f of fields) topics[f] = 0;
        topics[fields[fieldIdx]] = 1;

        try {
            await GameState.submitCommand('research', {
                budget: budget,
                topics: { levels: topics }
            });
            await GameState.refreshState();
            ApiClient.showStatus(
                `Research: ${fields[fieldIdx]} at ${budget}% budget`, 'info'
            );
        } catch (error) {
            ApiClient.showStatus('Failed to set research: ' + error.message, 'error');
        }
    },

    /**
     * Player Relations dialog - per-opponent Enemy/Neutral/Friend.
     * Web port of the WinForms dialog (PlayerRelations.cs): empire
     * list on the left, "Relation" radio group on the right; a radio
     * change applies immediately, mirroring RelationChanged
     * (PlayerRelations.cs:104-120). The C# display bug at
     * PlayerRelations.cs:89 (Neutral shown as Friend) is not ported.
     */
    showPlayerRelationsDialog() {
        const relations = GameState.relations || [];
        if (relations.length === 0) {
            ApiClient.showStatus('No other empires known', 'error');
            return;
        }

        const listHtml = relations.map((r, i) =>
            `<option value="${i}">${r.race_name || 'Empire ' + r.id}</option>`
        ).join('');

        const html = `
            <div class="dialog-header">
                <h2>Player Relations</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>
            <div class="dialog-body">
                <div style="display: flex; gap: 16px;">
                    <div class="form-group" style="flex: 1;">
                        <label for="relations-empire-list">Empires</label>
                        <select id="relations-empire-list" class="form-select"
                                size="${Math.min(Math.max(relations.length, 4), 12)}">
                            ${listHtml}
                        </select>
                    </div>
                    <fieldset style="flex: 1;">
                        <legend>Relation</legend>
                        <div class="form-group">
                            <label><input type="radio" name="relation-choice" value="Enemy"> Enemy</label>
                        </div>
                        <div class="form-group">
                            <label><input type="radio" name="relation-choice" value="Neutral"> Neutral</label>
                        </div>
                        <div class="form-group">
                            <label><input type="radio" name="relation-choice" value="Friend"> Friend</label>
                        </div>
                    </fieldset>
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" onclick="Dialogs.close()">Done</button>
            </div>
        `;

        Dialogs.show(html);

        const list = document.getElementById('relations-empire-list');
        if (list) list.value = '0';
        const radios = document.querySelectorAll('input[name="relation-choice"]');

        // Show the selected empire's CURRENT relation (fixes the C#
        // display bug where Neutral rendered as Friend)
        const syncRadios = () => {
            const entry = relations[parseInt(list.value)];
            radios.forEach(radio => {
                radio.checked = radio.value === (entry ? entry.relation : 'Enemy');
            });
        };
        syncRadios();

        list?.addEventListener('change', syncRadios);
        radios.forEach(radio => {
            radio.addEventListener('change', async () => {
                const entry = relations[parseInt(list.value)];
                if (!entry || !radio.checked) return;
                try {
                    await GameState.submitCommand('relation', {
                        target_empire_id: entry.id,
                        relation: radio.value
                    });
                    entry.relation = radio.value;
                    await GameState.refreshState();
                    ApiClient.showStatus(
                        `${entry.race_name || 'Empire ' + entry.id}: ${radio.value}`, 'info'
                    );
                } catch (error) {
                    ApiClient.showStatus('Failed to set relation: ' + error.message, 'error');
                    syncRadios();
                }
            });
        });
    },

    /**
     * Show help/manual.
     */
    showHelp() {
        if (window.Dialogs) {
            Dialogs.showMessage('Game Manual',
                'Stars Nova Web is a 4X space strategy game.\n\n' +
                'Build fleets, colonize planets, research technology, ' +
                'and conquer the galaxy!\n\n' +
                'Use the menu bar to access all game features.'
            );
        }
    },

    /**
     * Show keyboard shortcuts.
     */
    showKeyboardShortcuts() {
        if (window.Dialogs) {
            Dialogs.showMessage('Keyboard Shortcuts',
                'Navigation:\n' +
                '  WASD / Arrows - Pan map\n' +
                '  + / - - Zoom in/out\n' +
                '  Home - Zoom to fit\n' +
                '  N - Toggle star names\n' +
                '  G - Toggle grid\n' +
                '  Shift+S - Toggle scanner ranges\n' +
                '  Shift+Drag - Measure distance\n\n' +
                'Game:\n' +
                '  F3 - Planet report\n' +
                '  F4 - Ship designer\n' +
                '  F7 - Player relations\n' +
                '  F9 - Generate turn\n' +
                '  Ctrl+N - New game\n' +
                '  Ctrl+O - Open game\n' +
                '  Ctrl+S - Save game\n' +
                '  Ctrl+F - Find star\n\n' +
                'Escape - Close dialogs/menus'
            );
        }
    },

    /**
     * Show about dialog.
     */
    showAbout() {
        if (window.Dialogs) {
            Dialogs.showMessage('About Stars Nova',
                'Stars Nova Web v0.1.0\n\n' +
                'For my beloved son Henry,\n' +
                'alienated from his father for so long...\n\n' +
                'with thanks to my beloved wife Ewa\n\n' +
                'A web-based port of Stars! Nova,\n' +
                'the open-source clone of Stars!\n\n' +
                'Original Stars! by Jeff Johnson and Jeff McBride (1995)\n' +
                'Stars! Nova by the Nova team\n' +
                'Web port for modern browsers'
            );
        }
    }
};

window.MenuBar = MenuBar;
