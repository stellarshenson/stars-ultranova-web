/**
 * Stars Nova Web - Design Panel
 * Ship designer interface for creating and editing ship designs.
 * Ported from original Stars! visual style.
 */

const DesignPanel = {
    // DOM elements
    container: null,

    // Design state
    currentDesign: null,
    availableHulls: [],
    availableComponents: [],

    // View state
    isVisible: false,

    /**
     * Initialize the design panel.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Design panel container not found:', containerId);
            return;
        }

        // Listen to events
        GameState.on('gameLoaded', () => this.loadComponents());
        GameState.on('gameCreated', () => this.loadComponents());
    },

    // Item types that can be mounted in hull slots (see ItemType enum
    // in backend/core/game_objects/item.py)
    mountableItemTypes: [
        'ENGINE', 'MECHANICAL', 'ELECTRICAL', 'SCANNER', 'ORBITAL', 'GATE',
        'MINING_ROBOT', 'MINE_LAYER', 'SHIELD', 'ARMOR', 'BOMB',
        'WEAPON', 'BEAM_WEAPONS', 'TORPEDOES'
    ],

    /**
     * Load available components.
     * The components endpoint returns everything (including hulls and
     * engines) with an item_type field; keep only mountable components.
     */
    async loadComponents() {
        try {
            const hulls = await ApiClient.request('GET', '/designs/hulls');
            const components = await ApiClient.request('GET', '/designs/components');

            this.availableHulls = hulls;
            this._mountableComponents = components.filter(
                c => this.mountableItemTypes.includes(c.item_type)
            );
            this.applyMtFilter();
        } catch (error) {
            console.error('Failed to load components:', error);
        }
    },

    /**
     * Hide Mystery Trader hidden-tech items until the trader grants
     * them (GameState.mtComponents; the server enforces the same gate
     * in design_builder on save). Re-applied on show() so a mid-game
     * grant surfaces without reloading the catalog.
     */
    applyMtFilter() {
        this.availableComponents = (this._mountableComponents || []).filter(
            c => !(c.properties || {})['Mystery Trader Item']
                || (GameState.mtComponents || []).includes(c.name)
        );
    },

    /**
     * Show the design panel.
     */
    show() {
        if (!this.container) return;

        this.isVisible = true;
        this.container.classList.remove('hidden');
        this.applyMtFilter();
        this.render();
    },

    /**
     * Hide the design panel.
     */
    hide() {
        if (!this.container) return;

        this.isVisible = false;
        this.container.classList.add('hidden');
    },

    /**
     * Toggle visibility.
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    },

    /**
     * Render the design panel.
     */
    render() {
        if (!this.container) return;

        let html = `
            <div class="design-panel-header">
                <h2>Ship Designer</h2>
                <button class="btn-close" id="btn-close-design">X</button>
            </div>

            <div class="design-panel-content">
                <div class="design-left">
                    ${this.renderHullSelector()}
                    ${this.renderComponentList()}
                </div>

                <div class="design-right">
                    ${this.renderDesignPreview()}
                    ${this.renderDesignStats()}
                </div>
            </div>

            <div class="design-panel-footer">
                <button class="btn-primary" id="btn-save-design">Save Design</button>
                <button class="btn-secondary" id="btn-cancel-design">Cancel</button>
            </div>
        `;

        this.container.innerHTML = html;
        this.bindEvents();
    },

    /**
     * Render hull selector.
     */
    renderHullSelector() {
        let options = '<option value="">Select a hull...</option>';

        for (const hull of this.availableHulls) {
            const selected = this.currentDesign?.hull === hull.name ? 'selected' : '';
            options += `<option value="${hull.name}" ${selected}>${hull.name}</option>`;
        }

        return `
            <div class="design-section">
                <h3>Hull</h3>
                <select id="hull-selector" class="design-select">
                    ${options}
                </select>
            </div>
        `;
    },

    /**
     * Render component list.
     */
    renderComponentList() {
        const categories = this.groupComponentsByCategory();

        let html = '<div class="design-section"><h3>Components</h3>';

        for (const [category, components] of Object.entries(categories)) {
            html += `
                <div class="component-category">
                    <h4>${category}</h4>
                    <ul class="component-list">
            `;

            for (const comp of components) {
                html += `
                    <li class="component-item" data-name="${comp.name}">
                        <span class="component-name">${comp.name}</span>
                        <button class="btn-tiny btn-add-component" data-name="${comp.name}">+</button>
                    </li>
                `;
            }

            html += '</ul></div>';
        }

        html += '</div>';
        return html;
    },

    /**
     * Group components by category (derived from item_type).
     */
    groupComponentsByCategory() {
        const categoryByType = {
            'ENGINE': 'Engines',
            'WEAPON': 'Weapons',
            'BEAM_WEAPONS': 'Weapons',
            'TORPEDOES': 'Weapons',
            'SHIELD': 'Shields',
            'ARMOR': 'Armor',
            'SCANNER': 'Scanners',
            'ELECTRICAL': 'Electrical',
            'MECHANICAL': 'Mechanical',
            'BOMB': 'Bombs',
            'MINE_LAYER': 'Mine Layers',
            'MINING_ROBOT': 'Mining Robots',
            'ORBITAL': 'Orbital',
            'GATE': 'Orbital'
        };

        const categories = {};
        for (const comp of this.availableComponents) {
            const cat = categoryByType[comp.item_type] || 'Other';
            if (!categories[cat]) {
                categories[cat] = [];
            }
            categories[cat].push(comp);
        }

        return categories;
    },

    /**
     * Render design preview.
     */
    renderDesignPreview() {
        if (!this.currentDesign) {
            return `
                <div class="design-section">
                    <h3>Design Preview</h3>
                    <div class="design-preview-empty">
                        <p>Select a hull to begin designing.</p>
                    </div>
                </div>
            `;
        }

        const slots = this.currentDesign.slots || [];
        let slotsHtml = '';

        for (let i = 0; i < slots.length; i++) {
            const slot = slots[i];
            const filled = slot.component ? 'filled' : 'empty';
            const label = slot.component
                ? (slot.count > 1 ? `${slot.count}x ${slot.component}` : slot.component)
                : 'Empty';
            slotsHtml += `
                <div class="slot ${filled}" data-index="${i}">
                    <span class="slot-type">${slot.type} (${slot.max})</span>
                    <span class="slot-component">${label}</span>
                </div>
            `;
        }

        return `
            <div class="design-section">
                <h3>Design Preview</h3>
                <div class="design-name-row">
                    <input type="text" id="design-name" value="${this.currentDesign.name || 'New Design'}"
                           placeholder="Design name" class="design-name-input">
                </div>
                <div class="design-preview">
                    <div class="hull-shape">${this.currentDesign.hull}</div>
                    <div class="slots-grid">
                        ${slotsHtml}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Render design stats.
     */
    renderDesignStats() {
        const stats = this.currentDesign?.stats || {
            mass: 0,
            cost_ironium: 0,
            cost_boranium: 0,
            cost_germanium: 0,
            cost_resources: 0,
            fuel_capacity: 0,
            armor: 0,
            shields: 0,
            initiative: 0
        };

        return `
            <div class="design-section">
                <h3>Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-row">
                        <span>Mass:</span>
                        <span class="stat-value">${stats.mass} kT</span>
                    </div>
                    <div class="stat-row">
                        <span>Fuel Capacity:</span>
                        <span class="stat-value">${stats.fuel_capacity} mg</span>
                    </div>
                    <div class="stat-row">
                        <span>Armor:</span>
                        <span class="stat-value">${stats.armor}</span>
                    </div>
                    <div class="stat-row">
                        <span>Shields:</span>
                        <span class="stat-value">${stats.shields}</span>
                    </div>
                    <div class="stat-row">
                        <span>Initiative:</span>
                        <span class="stat-value">${stats.initiative}</span>
                    </div>
                </div>

                <h4>Cost</h4>
                <div class="cost-grid">
                    <div class="cost-item ironium">Ir: ${stats.cost_ironium}</div>
                    <div class="cost-item boranium">Bo: ${stats.cost_boranium}</div>
                    <div class="cost-item germanium">Ge: ${stats.cost_germanium}</div>
                    <div class="cost-item resources">Res: ${stats.cost_resources}</div>
                </div>
            </div>
        `;
    },

    /**
     * Bind event handlers.
     */
    bindEvents() {
        // Close button
        const closeBtn = document.getElementById('btn-close-design');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }

        // Hull selector
        const hullSelect = document.getElementById('hull-selector');
        if (hullSelect) {
            hullSelect.addEventListener('change', (e) => this.selectHull(e.target.value));
        }

        // Add component buttons
        const addButtons = this.container.querySelectorAll('.btn-add-component');
        addButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const name = e.target.dataset.name;
                this.addComponent(name);
            });
        });

        // Save button
        const saveBtn = document.getElementById('btn-save-design');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveDesign());
        }

        // Cancel button
        const cancelBtn = document.getElementById('btn-cancel-design');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hide());
        }
    },

    /**
     * Select a hull.
     */
    selectHull(hullName) {
        const hull = this.availableHulls.find(h => h.name === hullName);
        if (!hull) {
            this.currentDesign = null;
            this.render();
            return;
        }

        // Create new design with this hull. Slots keep the hull module
        // cell_number - it is the slot identity in the design command.
        this.currentDesign = {
            name: `New ${hullName}`,
            hull: hullName,
            slots: hull.modules?.map(m => ({
                cell_number: m.cell_number,
                type: m.component_type,
                max: m.component_maximum || 1,
                component: null,
                count: 0
            })) || [],
            stats: this.baseHullStats(hull)
        };

        this.render();
    },

    /**
     * Base stats from a hull response.
     */
    baseHullStats(hull) {
        return {
            mass: hull.mass || 0,
            fuel_capacity: hull.fuel_capacity || 0,
            armor: hull.armor_strength || 0,
            shields: 0,
            initiative: hull.battle_initiative || 0,
            cost_ironium: hull.cost?.ironium || 0,
            cost_boranium: hull.cost?.boranium || 0,
            cost_germanium: hull.cost?.germanium || 0,
            cost_resources: hull.cost?.energy || 0
        };
    },

    /**
     * Keep the typed design name across re-renders.
     */
    syncName() {
        const nameInput = document.getElementById('design-name');
        if (nameInput && this.currentDesign) {
            this.currentDesign.name = nameInput.value;
        }
    },

    /**
     * Add a component to the design.
     */
    addComponent(componentName) {
        if (!this.currentDesign) {
            ApiClient.showStatus('Select a hull first', 'error');
            return;
        }

        const component = this.availableComponents.find(c => c.name === componentName);
        if (!component) return;

        // Prefer a slot already holding this component with spare capacity
        let slot = this.currentDesign.slots.find(s =>
            s.component === componentName && s.count < s.max
        );

        if (!slot) {
            slot = this.currentDesign.slots.find(s =>
                !s.component && this.slotAcceptsComponent(s.type, component.item_type)
            );
            if (!slot) {
                ApiClient.showStatus('No available slot for this component', 'error');
                return;
            }
            slot.component = componentName;
            slot.count = 0;
        }

        slot.count++;

        this.syncName();
        this.updateStats();
        this.render();
    },

    /**
     * Check if a slot accepts a component item type.
     * Mirrors slot_accepts in backend/services/design_builder.py:
     * the slot type is a phrase ("Shield or Armor", "General Purpose",
     * "Scanner Electrical Mechanical") and each recognized token widens
     * the accepted set.
     */
    slotAcceptsComponent(slotType, itemType) {
        const tokenTypes = {
            'weapon': ['WEAPON', 'BEAM_WEAPONS', 'TORPEDOES'],
            'engine': ['ENGINE'],
            'shield': ['SHIELD'],
            'armor': ['ARMOR'],
            'electrical': ['ELECTRICAL'],
            'elect': ['ELECTRICAL'],
            'mechanical': ['MECHANICAL'],
            'mech': ['MECHANICAL'],
            'scanner': ['SCANNER'],
            'bomb': ['BOMB'],
            'orbital': ['ORBITAL', 'GATE'],
            'miner': ['MINING_ROBOT']
        };

        // General purpose: everything except engines and orbitals
        const generalPurpose = [
            'WEAPON', 'BEAM_WEAPONS', 'TORPEDOES', 'SHIELD', 'ARMOR',
            'ELECTRICAL', 'MECHANICAL', 'SCANNER', 'BOMB',
            'MINING_ROBOT', 'MINE_LAYER'
        ];

        const lowered = (slotType || '').toLowerCase();
        if (lowered.includes('general purpose')) {
            return generalPurpose.includes(itemType);
        }
        if (lowered.includes('mine layer') && itemType === 'MINE_LAYER') {
            return true;
        }
        for (const token of lowered.replace(/ or /g, ' ').split(/\s+/)) {
            const accepted = tokenTypes[token];
            if (accepted && accepted.includes(itemType)) {
                return true;
            }
        }
        return false;
    },

    /**
     * Update design stats based on hull + components.
     * Client-side estimate only - the server is authoritative.
     */
    updateStats() {
        if (!this.currentDesign) return;

        const hull = this.availableHulls.find(h => h.name === this.currentDesign.hull);
        const stats = hull ? this.baseHullStats(hull) : { ...this.currentDesign.stats };

        for (const slot of this.currentDesign.slots) {
            if (!slot.component || slot.count <= 0) continue;

            const comp = this.availableComponents.find(c => c.name === slot.component);
            if (!comp) continue;

            const n = slot.count;
            stats.mass = (stats.mass || 0) + (comp.mass || 0) * n;
            stats.armor = (stats.armor || 0) + (comp.properties?.Armor?.Value || 0) * n;
            stats.shields = (stats.shields || 0) + (comp.properties?.Shield?.Value || 0) * n;
            stats.cost_ironium = (stats.cost_ironium || 0) + (comp.cost?.ironium || 0) * n;
            stats.cost_boranium = (stats.cost_boranium || 0) + (comp.cost?.boranium || 0) * n;
            stats.cost_germanium = (stats.cost_germanium || 0) + (comp.cost?.germanium || 0) * n;
            stats.cost_resources = (stats.cost_resources || 0) + (comp.cost?.energy || 0) * n;
        }

        this.currentDesign.stats = stats;
    },

    /**
     * Save the current design through the canonical design command.
     * The server aggregates and validates (slot type/capacity, tech
     * requirements, engine required for non-starbase designs).
     */
    async saveDesign() {
        if (!this.currentDesign || !GameState.game) {
            ApiClient.showStatus('No design to save', 'error');
            return;
        }

        this.syncName();
        const name = (this.currentDesign.name || '').trim();
        if (!name) {
            ApiClient.showStatus('Design name is required', 'error');
            return;
        }

        const slots = this.currentDesign.slots
            .filter(s => s.component && s.count > 0)
            .map(s => ({
                cell_number: s.cell_number,
                component: s.component,
                count: s.count
            }));

        try {
            await GameState.submitCommand('design', {
                mode: 'Add',
                design: {
                    name: name,
                    hull: this.currentDesign.hull,
                    slots: slots
                }
            });

            ApiClient.showStatus('Design saved', 'success');
            await GameState.refreshState();
            this.currentDesign = null;
            this.hide();
        } catch (error) {
            ApiClient.showStatus(error.message, 'error');
        }
    },

    /**
     * Create new design.
     */
    newDesign() {
        this.currentDesign = null;
        this.show();
    },

    /**
     * Edit existing design.
     */
    editDesign(design) {
        this.currentDesign = { ...design };
        this.show();
    }
};

// Export
window.DesignPanel = DesignPanel;
