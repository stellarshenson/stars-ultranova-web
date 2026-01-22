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

        console.log('Design panel initialized');
    },

    /**
     * Load available components.
     */
    async loadComponents() {
        try {
            const hulls = await ApiClient.request('GET', '/designs/hulls');
            const engines = await ApiClient.request('GET', '/designs/engines');
            const components = await ApiClient.request('GET', '/designs/components');

            this.availableHulls = hulls;
            this.availableComponents = [...engines, ...components];
        } catch (error) {
            console.error('Failed to load components:', error);
        }
    },

    /**
     * Show the design panel.
     */
    show() {
        if (!this.container) return;

        this.isVisible = true;
        this.container.classList.remove('hidden');
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
     * Group components by category.
     */
    groupComponentsByCategory() {
        const categories = {
            'Engines': [],
            'Weapons': [],
            'Shields': [],
            'Armor': [],
            'Scanners': [],
            'Other': []
        };

        for (const comp of this.availableComponents) {
            const cat = comp.category || 'Other';
            if (categories[cat]) {
                categories[cat].push(comp);
            } else {
                categories['Other'].push(comp);
            }
        }

        // Remove empty categories
        for (const key of Object.keys(categories)) {
            if (categories[key].length === 0) {
                delete categories[key];
            }
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
            slotsHtml += `
                <div class="slot ${filled}" data-index="${i}">
                    <span class="slot-type">${slot.type}</span>
                    <span class="slot-component">${slot.component || 'Empty'}</span>
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

        // Create new design with this hull
        this.currentDesign = {
            name: `New ${hullName}`,
            hull: hullName,
            slots: hull.modules?.map(m => ({
                type: m.type,
                component: null,
                quantity: 0
            })) || [],
            stats: hull.base_stats || {}
        };

        this.render();
    },

    /**
     * Add a component to the design.
     */
    addComponent(componentName) {
        if (!this.currentDesign) {
            alert('Please select a hull first.');
            return;
        }

        const component = this.availableComponents.find(c => c.name === componentName);
        if (!component) return;

        // Find an empty slot that accepts this component type
        const slot = this.currentDesign.slots.find(s =>
            !s.component && this.slotAcceptsComponent(s.type, component.category)
        );

        if (!slot) {
            alert('No available slot for this component.');
            return;
        }

        slot.component = componentName;
        slot.quantity = 1;

        this.updateStats();
        this.render();
    },

    /**
     * Check if a slot accepts a component category.
     */
    slotAcceptsComponent(slotType, componentCategory) {
        const mapping = {
            'Engine': ['Engines'],
            'Weapon': ['Weapons'],
            'Shield': ['Shields'],
            'Armor': ['Armor'],
            'Scanner': ['Scanners'],
            'Mechanical': ['Other', 'Mechanical'],
            'Electrical': ['Other', 'Electrical', 'Scanners'],
            'General': ['Engines', 'Weapons', 'Shields', 'Armor', 'Scanners', 'Other']
        };

        const accepted = mapping[slotType] || mapping['General'];
        return accepted.includes(componentCategory);
    },

    /**
     * Update design stats based on components.
     */
    updateStats() {
        if (!this.currentDesign) return;

        // This would calculate stats from hull + components
        // For now, just accumulate basic values
        let stats = { ...this.currentDesign.stats };

        for (const slot of this.currentDesign.slots) {
            if (slot.component) {
                const comp = this.availableComponents.find(c => c.name === slot.component);
                if (comp) {
                    stats.mass = (stats.mass || 0) + (comp.mass || 0);
                    stats.armor = (stats.armor || 0) + (comp.armor || 0);
                    stats.shields = (stats.shields || 0) + (comp.shields || 0);
                    stats.cost_ironium = (stats.cost_ironium || 0) + (comp.cost?.ironium || 0);
                    stats.cost_boranium = (stats.cost_boranium || 0) + (comp.cost?.boranium || 0);
                    stats.cost_germanium = (stats.cost_germanium || 0) + (comp.cost?.germanium || 0);
                    stats.cost_resources = (stats.cost_resources || 0) + (comp.cost?.resources || 0);
                }
            }
        }

        this.currentDesign.stats = stats;
    },

    /**
     * Save the current design.
     */
    async saveDesign() {
        if (!this.currentDesign || !GameState.game) {
            alert('No design to save.');
            return;
        }

        const nameInput = document.getElementById('design-name');
        if (nameInput) {
            this.currentDesign.name = nameInput.value;
        }

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'design',
                    action: 'add',
                    design: this.currentDesign
                }
            );

            alert('Design saved successfully!');
            this.hide();
        } catch (error) {
            alert('Failed to save design: ' + error.message);
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
