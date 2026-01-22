/**
 * Stars Nova Web - Panel Manager
 * Coordinates visibility, pinning, and collapsing of info panels.
 */

const PanelManager = {
    /**
     * Panel configuration and state
     */
    panels: {
        planet: {
            id: 'star-panel',
            visible: false,
            pinned: false,
            collapsed: false,
            order: 0
        },
        fleet: {
            id: 'fleet-panel',
            visible: false,
            pinned: false,
            collapsed: false,
            order: 1
        }
    },

    /**
     * Layout mode: 'stacked' or 'side-by-side'
     */
    layout: 'stacked',

    /**
     * Initialize the panel manager.
     */
    init() {
        this.restoreState();
        this.setupEventListeners();
        console.log('PanelManager initialized');
    },

    /**
     * Setup game state event listeners.
     */
    setupEventListeners() {
        if (window.GameState) {
            GameState.on('starSelected', (star) => {
                this.onStarSelected(star);
            });

            GameState.on('fleetSelected', (fleet) => {
                this.onFleetSelected(fleet);
            });

            GameState.on('selectionCleared', () => {
                this.onSelectionCleared();
            });
        }
    },

    /**
     * Handle star selection.
     * @param {Object} star - Selected star object
     */
    onStarSelected(star) {
        // Show planet panel unless fleet panel is pinned
        if (!this.panels.fleet.pinned) {
            this.hidePanel('fleet');
        }
        this.showPanel('planet');
    },

    /**
     * Handle fleet selection.
     * @param {Object} fleet - Selected fleet object
     */
    onFleetSelected(fleet) {
        // Show fleet panel unless planet panel is pinned
        if (!this.panels.planet.pinned) {
            this.hidePanel('planet');
        }
        this.showPanel('fleet');
    },

    /**
     * Handle selection cleared.
     */
    onSelectionCleared() {
        // Hide unpinned panels
        if (!this.panels.planet.pinned) {
            this.hidePanel('planet');
        }
        if (!this.panels.fleet.pinned) {
            this.hidePanel('fleet');
        }
    },

    /**
     * Show a panel.
     * @param {string} panelName - Panel name (planet, fleet)
     */
    showPanel(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.visible = true;
        const element = document.getElementById(panel.id);
        if (element) {
            element.classList.remove('hidden');
            if (panel.collapsed) {
                element.classList.add('collapsed');
            } else {
                element.classList.remove('collapsed');
            }
        }
        this.saveState();
    },

    /**
     * Hide a panel.
     * @param {string} panelName - Panel name
     */
    hidePanel(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.visible = false;
        const element = document.getElementById(panel.id);
        if (element) {
            element.classList.add('hidden');
        }
        this.saveState();
    },

    /**
     * Toggle panel visibility.
     * @param {string} panelName - Panel name
     */
    togglePanel(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        if (panel.visible) {
            this.hidePanel(panelName);
        } else {
            this.showPanel(panelName);
        }
    },

    /**
     * Toggle pin state for a panel.
     * @param {string} panelName - Panel name
     */
    togglePin(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.pinned = !panel.pinned;
        this.updatePinButton(panelName);
        this.saveState();
    },

    /**
     * Set pin state for a panel.
     * @param {string} panelName - Panel name
     * @param {boolean} pinned - New pin state
     */
    setPin(panelName, pinned) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.pinned = pinned;
        this.updatePinButton(panelName);
        this.saveState();
    },

    /**
     * Update pin button visual state.
     * @param {string} panelName - Panel name
     */
    updatePinButton(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        const element = document.getElementById(panel.id);
        if (element) {
            const pinBtn = element.querySelector('.pin-btn');
            if (pinBtn) {
                pinBtn.classList.toggle('pinned', panel.pinned);
                pinBtn.title = panel.pinned ? 'Unpin panel' : 'Pin panel';
            }
        }
    },

    /**
     * Toggle collapse state for a panel.
     * @param {string} panelName - Panel name
     */
    toggleCollapse(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.collapsed = !panel.collapsed;
        this.updateCollapseState(panelName);
        this.saveState();
    },

    /**
     * Set collapse state for a panel.
     * @param {string} panelName - Panel name
     * @param {boolean} collapsed - New collapse state
     */
    setCollapse(panelName, collapsed) {
        const panel = this.panels[panelName];
        if (!panel) return;

        panel.collapsed = collapsed;
        this.updateCollapseState(panelName);
        this.saveState();
    },

    /**
     * Update collapse visual state.
     * @param {string} panelName - Panel name
     */
    updateCollapseState(panelName) {
        const panel = this.panels[panelName];
        if (!panel) return;

        const element = document.getElementById(panel.id);
        if (element) {
            element.classList.toggle('collapsed', panel.collapsed);

            const collapseBtn = element.querySelector('.collapse-btn');
            if (collapseBtn) {
                collapseBtn.textContent = panel.collapsed ? '\u25B6' : '\u25BC';
                collapseBtn.title = panel.collapsed ? 'Expand panel' : 'Collapse panel';
            }
        }
    },

    /**
     * Set layout mode.
     * @param {string} layout - 'stacked' or 'side-by-side'
     */
    setLayout(layout) {
        this.layout = layout;
        const container = document.getElementById('left-column') || document.getElementById('info-panel');
        if (container) {
            container.classList.toggle('side-by-side', layout === 'side-by-side');
        }
        this.saveState();
    },

    /**
     * Get panel state.
     * @param {string} panelName - Panel name
     * @returns {Object} Panel state
     */
    getPanelState(panelName) {
        return this.panels[panelName] || null;
    },

    /**
     * Check if panel is pinned.
     * @param {string} panelName - Panel name
     * @returns {boolean} True if pinned
     */
    isPinned(panelName) {
        const panel = this.panels[panelName];
        return panel ? panel.pinned : false;
    },

    /**
     * Check if panel is collapsed.
     * @param {string} panelName - Panel name
     * @returns {boolean} True if collapsed
     */
    isCollapsed(panelName) {
        const panel = this.panels[panelName];
        return panel ? panel.collapsed : false;
    },

    /**
     * Check if panel is visible.
     * @param {string} panelName - Panel name
     * @returns {boolean} True if visible
     */
    isVisible(panelName) {
        const panel = this.panels[panelName];
        return panel ? panel.visible : false;
    },

    /**
     * Add panel header controls to existing panel.
     * @param {string} panelName - Panel name
     * @param {HTMLElement} headerElement - The panel header element
     */
    addHeaderControls(panelName, headerElement) {
        const panel = this.panels[panelName];
        if (!panel || !headerElement) return;

        // Create controls container
        const controls = document.createElement('div');
        controls.className = 'panel-controls';

        // Pin button
        const pinBtn = document.createElement('button');
        pinBtn.className = 'pin-btn' + (panel.pinned ? ' pinned' : '');
        pinBtn.textContent = '\uD83D\uDCCC'; // Pushpin emoji
        pinBtn.title = panel.pinned ? 'Unpin panel' : 'Pin panel';
        pinBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.togglePin(panelName);
        });

        // Collapse button
        const collapseBtn = document.createElement('button');
        collapseBtn.className = 'collapse-btn';
        collapseBtn.textContent = panel.collapsed ? '\u25B6' : '\u25BC';
        collapseBtn.title = panel.collapsed ? 'Expand panel' : 'Collapse panel';
        collapseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleCollapse(panelName);
        });

        controls.appendChild(pinBtn);
        controls.appendChild(collapseBtn);
        headerElement.appendChild(controls);
    },

    /**
     * Save panel state to localStorage.
     */
    saveState() {
        const state = {
            panels: {},
            layout: this.layout
        };

        for (const [name, panel] of Object.entries(this.panels)) {
            state.panels[name] = {
                pinned: panel.pinned,
                collapsed: panel.collapsed,
                order: panel.order
            };
        }

        try {
            localStorage.setItem('stars-nova-panels', JSON.stringify(state));
        } catch (e) {
            console.warn('Failed to save panel state:', e);
        }
    },

    /**
     * Restore panel state from localStorage.
     */
    restoreState() {
        try {
            const saved = localStorage.getItem('stars-nova-panels');
            if (!saved) return;

            const state = JSON.parse(saved);

            if (state.layout) {
                this.layout = state.layout;
            }

            if (state.panels) {
                for (const [name, savedPanel] of Object.entries(state.panels)) {
                    if (this.panels[name]) {
                        this.panels[name].pinned = savedPanel.pinned || false;
                        this.panels[name].collapsed = savedPanel.collapsed || false;
                        this.panels[name].order = savedPanel.order || 0;
                    }
                }
            }
        } catch (e) {
            console.warn('Failed to restore panel state:', e);
        }
    },

    /**
     * Reset all panels to default state.
     */
    reset() {
        for (const panel of Object.values(this.panels)) {
            panel.visible = false;
            panel.pinned = false;
            panel.collapsed = false;
        }
        this.layout = 'stacked';
        this.saveState();
    }
};

window.PanelManager = PanelManager;
