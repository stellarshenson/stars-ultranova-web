/**
 * Stars Nova Web - Race Designer Wizard
 * Multi-tab wizard for creating custom races.
 * Ported from original Stars! race designer.
 */

const RaceWizard = {
    // DOM elements
    container: null,

    // Current tab
    currentTab: 0,
    tabs: ['race', 'traits', 'production', 'environment', 'research'],
    tabNames: ['Race', 'Traits', 'Production', 'Environment', 'Research'],

    // Race data with defaults
    raceData: {
        name: 'Humanoids',
        pluralName: 'Humanoids',
        icon: 0,
        prt: 'JOAT',  // Primary Racial Trait
        lrts: [],     // Lesser Racial Traits

        // Production settings
        factoryCost: 10,
        factoryEfficiency: 10,
        factoryNumberPer10k: 10,
        mineCost: 5,
        mineEfficiency: 10,
        mineNumberPer10k: 10,
        colonistsPerResource: 1000,
        canOperateOtherRaces: false,

        // Environment settings
        gravityMin: 15,
        gravityMax: 85,
        temperatureMin: 15,
        temperatureMax: 85,
        radiationMin: 15,
        radiationMax: 85,
        immuneGravity: false,
        immuneTemperature: false,
        immuneRadiation: false,
        growthRate: 15,

        // Research settings
        researchCosts: {
            energy: 'normal',
            weapons: 'normal',
            propulsion: 'normal',
            construction: 'normal',
            electronics: 'normal',
            biotechnology: 'normal'
        },
        startAtLevel3: true
    },

    // Advantage points (must be >= 0 to save)
    advantagePoints: 25,

    // Trait data with point costs
    primaryTraits: {
        HE: { name: 'Hyper Expansion', points: 0, description: 'Faster population growth, cheaper colonizers' },
        SS: { name: 'Super Stealth', points: -66, description: 'Better cloaking and stealth abilities' },
        WM: { name: 'War Monger', points: -12, description: 'Better weapons and combat bonuses' },
        CA: { name: 'Claim Adjuster', points: 16, description: 'Terraform planets for other races' },
        IS: { name: 'Inner Strength', points: 36, description: 'Natural defenses and regeneration' },
        SD: { name: 'Space Demolition', points: -8, description: 'Expert at minelaying and bombs' },
        PP: { name: 'Packet Physics', points: -5, description: 'Efficient mass drivers and packets' },
        IT: { name: 'Interstellar Traveler', points: 0, description: 'Stargates and wormhole specialists' },
        AR: { name: 'Alternate Reality', points: -12, description: 'Orbital habitats instead of planets' },
        JOAT: { name: 'Jack of All Trades', points: 66, description: 'Balanced abilities in all areas' }
    },

    lesserTraits: {
        IFE: { name: 'Improved Fuel Efficiency', points: -44, description: 'Ships use less fuel' },
        TT: { name: 'Total Terraforming', points: -53, description: '30% terraforming ability' },
        ARM: { name: 'Advanced Remote Mining', points: -49, description: 'Better remote mining robots' },
        ISB: { name: 'Improved Starbases', points: -26, description: 'Cheaper, better starbases' },
        GR: { name: 'Generalized Research', points: -15, description: 'Research applies to all fields' },
        UR: { name: 'Ultimate Recycling', points: -10, description: 'Recover more from scrapped ships' },
        MA: { name: 'Mineral Alchemy', points: -17, description: 'Convert minerals between types' },
        NRSE: { name: 'No Ram Scoop Engines', points: 53, description: 'Cannot use ram scoop engines' },
        OBRM: { name: 'Only Basic Remote Mining', points: 35, description: 'Limited remote mining tech' },
        CE: { name: 'Cheap Engines', points: -30, description: 'Engines cost less to build' },
        NAS: { name: 'No Advanced Scanners', points: 35, description: 'Cannot use advanced scanners' },
        LSP: { name: 'Low Starting Population', points: 63, description: 'Start with fewer colonists' },
        BET: { name: 'Bleeding Edge Technology', points: -26, description: 'New tech is more powerful but expensive' },
        RS: { name: 'Regenerating Shields', points: -18, description: 'Shields regenerate in combat' }
    },

    /**
     * Initialize the race wizard.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Race wizard container not found:', containerId);
            return;
        }

        console.log('Race wizard initialized');
    },

    /**
     * Show the wizard.
     */
    show() {
        if (!this.container) return;

        this.currentTab = 0;
        this.resetRaceData();
        this.calculatePoints();
        this.container.classList.remove('hidden');
        this.render();
    },

    /**
     * Hide the wizard.
     */
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
    },

    /**
     * Toggle visibility.
     */
    toggle() {
        if (this.container.classList.contains('hidden')) {
            this.show();
        } else {
            this.hide();
        }
    },

    /**
     * Reset race data to defaults.
     */
    resetRaceData() {
        this.raceData = {
            name: 'Humanoids',
            pluralName: 'Humanoids',
            icon: 0,
            prt: 'JOAT',
            lrts: [],
            factoryCost: 10,
            factoryEfficiency: 10,
            factoryNumberPer10k: 10,
            mineCost: 5,
            mineEfficiency: 10,
            mineNumberPer10k: 10,
            colonistsPerResource: 1000,
            canOperateOtherRaces: false,
            gravityMin: 15,
            gravityMax: 85,
            temperatureMin: 15,
            temperatureMax: 85,
            radiationMin: 15,
            radiationMax: 85,
            immuneGravity: false,
            immuneTemperature: false,
            immuneRadiation: false,
            growthRate: 15,
            researchCosts: {
                energy: 'normal',
                weapons: 'normal',
                propulsion: 'normal',
                construction: 'normal',
                electronics: 'normal',
                biotechnology: 'normal'
            },
            startAtLevel3: true
        };
    },

    /**
     * Render the wizard.
     */
    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="race-wizard-header">
                <h2>Race Designer</h2>
                <button class="btn-close" onclick="RaceWizard.hide()">&times;</button>
            </div>

            <div class="race-wizard-tabs">
                ${this.renderTabs()}
            </div>

            <div class="race-wizard-content">
                ${this.renderTabContent()}
            </div>

            <div class="race-wizard-footer">
                <div class="advantage-points ${this.advantagePoints >= 0 ? 'valid' : 'invalid'}">
                    Advantage Points: <strong>${this.advantagePoints}</strong>
                </div>
                <div class="wizard-buttons">
                    <button class="btn-small" onclick="RaceWizard.prevTab()" ${this.currentTab === 0 ? 'disabled' : ''}>Previous</button>
                    <button class="btn-small" onclick="RaceWizard.nextTab()" ${this.currentTab === this.tabs.length - 1 ? 'disabled' : ''}>Next</button>
                    <button class="btn-small btn-primary" onclick="RaceWizard.saveRace()" ${this.advantagePoints < 0 ? 'disabled' : ''}>Save Race</button>
                    <button class="btn-small" onclick="RaceWizard.hide()">Cancel</button>
                </div>
            </div>
        `;

        this.bindEvents();
    },

    /**
     * Render tab buttons.
     */
    renderTabs() {
        return this.tabs.map((tab, index) => `
            <button class="wizard-tab ${index === this.currentTab ? 'active' : ''}"
                    onclick="RaceWizard.goToTab(${index})">
                ${this.tabNames[index]}
            </button>
        `).join('');
    },

    /**
     * Render current tab content.
     */
    renderTabContent() {
        switch (this.tabs[this.currentTab]) {
            case 'race': return this.renderRaceTab();
            case 'traits': return this.renderTraitsTab();
            case 'production': return this.renderProductionTab();
            case 'environment': return this.renderEnvironmentTab();
            case 'research': return this.renderResearchTab();
            default: return '<p>Unknown tab</p>';
        }
    },

    /**
     * Render Race tab.
     */
    renderRaceTab() {
        const icons = Array.from({ length: 16 }, (_, i) => i);

        return `
            <div class="wizard-section">
                <h3>Race Identity</h3>

                <div class="form-group">
                    <label for="race-name">Race Name</label>
                    <input type="text" id="race-name" class="form-input"
                           value="${this.raceData.name}"
                           onchange="RaceWizard.updateField('name', this.value)">
                </div>

                <div class="form-group">
                    <label for="race-plural">Plural Name</label>
                    <input type="text" id="race-plural" class="form-input"
                           value="${this.raceData.pluralName}"
                           onchange="RaceWizard.updateField('pluralName', this.value)">
                </div>

                <div class="form-group">
                    <label>Race Icon</label>
                    <div class="icon-grid">
                        ${icons.map(i => `
                            <div class="icon-option ${this.raceData.icon === i ? 'selected' : ''}"
                                 onclick="RaceWizard.selectIcon(${i})">
                                ${i + 1}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>

            <div class="wizard-section">
                <h3>Primary Racial Trait</h3>
                <p class="section-desc">Choose one trait that defines your race's fundamental abilities.</p>

                <div class="prt-grid">
                    ${Object.entries(this.primaryTraits).map(([key, trait]) => `
                        <label class="prt-option ${this.raceData.prt === key ? 'selected' : ''}">
                            <input type="radio" name="prt" value="${key}"
                                   ${this.raceData.prt === key ? 'checked' : ''}
                                   onchange="RaceWizard.selectPRT('${key}')">
                            <span class="prt-name">${trait.name}</span>
                            <span class="prt-points">${trait.points >= 0 ? '+' : ''}${trait.points}</span>
                            <span class="prt-desc">${trait.description}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `;
    },

    /**
     * Render Traits tab.
     */
    renderTraitsTab() {
        return `
            <div class="wizard-section">
                <h3>Lesser Racial Traits</h3>
                <p class="section-desc">Select additional traits to customize your race. Positive points are bonuses, negative are costs.</p>

                <div class="lrt-grid">
                    ${Object.entries(this.lesserTraits).map(([key, trait]) => `
                        <label class="lrt-option ${this.raceData.lrts.includes(key) ? 'selected' : ''}">
                            <input type="checkbox" value="${key}"
                                   ${this.raceData.lrts.includes(key) ? 'checked' : ''}
                                   onchange="RaceWizard.toggleLRT('${key}')">
                            <span class="lrt-name">${trait.name}</span>
                            <span class="lrt-points ${trait.points >= 0 ? 'positive' : 'negative'}">${trait.points >= 0 ? '+' : ''}${trait.points}</span>
                            <span class="lrt-desc">${trait.description}</span>
                        </label>
                    `).join('')}
                </div>
            </div>
        `;
    },

    /**
     * Render Production tab.
     */
    renderProductionTab() {
        return `
            <div class="wizard-section">
                <h3>Factory Settings</h3>

                <div class="slider-group">
                    <label>Factories cost <span id="factory-cost-val">${this.raceData.factoryCost}</span> resources</label>
                    <input type="range" min="5" max="25" value="${this.raceData.factoryCost}"
                           oninput="RaceWizard.updateSlider('factoryCost', this.value, 'factory-cost-val')">
                    <span class="slider-range">5-25</span>
                </div>

                <div class="slider-group">
                    <label>Factories produce <span id="factory-eff-val">${this.raceData.factoryEfficiency}</span> resources/year</label>
                    <input type="range" min="5" max="15" value="${this.raceData.factoryEfficiency}"
                           oninput="RaceWizard.updateSlider('factoryEfficiency', this.value, 'factory-eff-val')">
                    <span class="slider-range">5-15</span>
                </div>

                <div class="slider-group">
                    <label>10,000 colonists operate <span id="factory-num-val">${this.raceData.factoryNumberPer10k}</span> factories</label>
                    <input type="range" min="5" max="25" value="${this.raceData.factoryNumberPer10k}"
                           oninput="RaceWizard.updateSlider('factoryNumberPer10k', this.value, 'factory-num-val')">
                    <span class="slider-range">5-25</span>
                </div>
            </div>

            <div class="wizard-section">
                <h3>Mine Settings</h3>

                <div class="slider-group">
                    <label>Mines cost <span id="mine-cost-val">${this.raceData.mineCost}</span> resources</label>
                    <input type="range" min="2" max="15" value="${this.raceData.mineCost}"
                           oninput="RaceWizard.updateSlider('mineCost', this.value, 'mine-cost-val')">
                    <span class="slider-range">2-15</span>
                </div>

                <div class="slider-group">
                    <label>Mines produce <span id="mine-eff-val">${this.raceData.mineEfficiency}</span> kT/year</label>
                    <input type="range" min="5" max="25" value="${this.raceData.mineEfficiency}"
                           oninput="RaceWizard.updateSlider('mineEfficiency', this.value, 'mine-eff-val')">
                    <span class="slider-range">5-25</span>
                </div>

                <div class="slider-group">
                    <label>10,000 colonists operate <span id="mine-num-val">${this.raceData.mineNumberPer10k}</span> mines</label>
                    <input type="range" min="5" max="25" value="${this.raceData.mineNumberPer10k}"
                           oninput="RaceWizard.updateSlider('mineNumberPer10k', this.value, 'mine-num-val')">
                    <span class="slider-range">5-25</span>
                </div>
            </div>

            <div class="wizard-section">
                <h3>Other Production</h3>

                <div class="slider-group">
                    <label><span id="col-res-val">${this.raceData.colonistsPerResource}</span> colonists generate 1 resource</label>
                    <input type="range" min="500" max="2500" step="100" value="${this.raceData.colonistsPerResource}"
                           oninput="RaceWizard.updateSlider('colonistsPerResource', this.value, 'col-res-val')">
                    <span class="slider-range">500-2500</span>
                </div>

                <label class="checkbox-option">
                    <input type="checkbox" ${this.raceData.canOperateOtherRaces ? 'checked' : ''}
                           onchange="RaceWizard.updateField('canOperateOtherRaces', this.checked)">
                    <span>Colonists can operate other races' factories and mines</span>
                </label>
            </div>
        `;
    },

    /**
     * Render Environment tab.
     */
    renderEnvironmentTab() {
        return `
            <div class="wizard-section">
                <h3>Habitability Ranges</h3>
                <p class="section-desc">Define the environmental conditions your race can tolerate.</p>

                <div class="env-group">
                    <label>Gravity Range</label>
                    <div class="range-inputs">
                        <input type="number" min="0" max="100" value="${this.raceData.gravityMin}"
                               onchange="RaceWizard.updateField('gravityMin', parseInt(this.value))" ${this.raceData.immuneGravity ? 'disabled' : ''}>
                        <span>to</span>
                        <input type="number" min="0" max="100" value="${this.raceData.gravityMax}"
                               onchange="RaceWizard.updateField('gravityMax', parseInt(this.value))" ${this.raceData.immuneGravity ? 'disabled' : ''}>
                        <label class="immune-check">
                            <input type="checkbox" ${this.raceData.immuneGravity ? 'checked' : ''}
                                   onchange="RaceWizard.updateField('immuneGravity', this.checked)">
                            Immune
                        </label>
                    </div>
                </div>

                <div class="env-group">
                    <label>Temperature Range</label>
                    <div class="range-inputs">
                        <input type="number" min="0" max="100" value="${this.raceData.temperatureMin}"
                               onchange="RaceWizard.updateField('temperatureMin', parseInt(this.value))" ${this.raceData.immuneTemperature ? 'disabled' : ''}>
                        <span>to</span>
                        <input type="number" min="0" max="100" value="${this.raceData.temperatureMax}"
                               onchange="RaceWizard.updateField('temperatureMax', parseInt(this.value))" ${this.raceData.immuneTemperature ? 'disabled' : ''}>
                        <label class="immune-check">
                            <input type="checkbox" ${this.raceData.immuneTemperature ? 'checked' : ''}
                                   onchange="RaceWizard.updateField('immuneTemperature', this.checked)">
                            Immune
                        </label>
                    </div>
                </div>

                <div class="env-group">
                    <label>Radiation Range</label>
                    <div class="range-inputs">
                        <input type="number" min="0" max="100" value="${this.raceData.radiationMin}"
                               onchange="RaceWizard.updateField('radiationMin', parseInt(this.value))" ${this.raceData.immuneRadiation ? 'disabled' : ''}>
                        <span>to</span>
                        <input type="number" min="0" max="100" value="${this.raceData.radiationMax}"
                               onchange="RaceWizard.updateField('radiationMax', parseInt(this.value))" ${this.raceData.immuneRadiation ? 'disabled' : ''}>
                        <label class="immune-check">
                            <input type="checkbox" ${this.raceData.immuneRadiation ? 'checked' : ''}
                                   onchange="RaceWizard.updateField('immuneRadiation', this.checked)">
                            Immune
                        </label>
                    </div>
                </div>
            </div>

            <div class="wizard-section">
                <h3>Population Growth</h3>

                <div class="slider-group">
                    <label>Maximum growth rate: <span id="growth-val">${this.raceData.growthRate}</span>%</label>
                    <input type="range" min="1" max="20" value="${this.raceData.growthRate}"
                           oninput="RaceWizard.updateSlider('growthRate', this.value, 'growth-val')">
                    <span class="slider-range">1-20%</span>
                </div>
            </div>
        `;
    },

    /**
     * Render Research tab.
     */
    renderResearchTab() {
        const fields = ['energy', 'weapons', 'propulsion', 'construction', 'electronics', 'biotechnology'];
        const fieldNames = {
            energy: 'Energy',
            weapons: 'Weapons',
            propulsion: 'Propulsion',
            construction: 'Construction',
            electronics: 'Electronics',
            biotechnology: 'Biotechnology'
        };
        const costs = ['cheap', 'normal', 'expensive'];
        const costLabels = { cheap: 'Cheap (-50%)', normal: 'Normal', expensive: 'Expensive (+75%)' };

        return `
            <div class="wizard-section">
                <h3>Research Costs</h3>
                <p class="section-desc">Set the cost modifier for each research field.</p>

                <div class="research-grid">
                    ${fields.map(field => `
                        <div class="research-field">
                            <label>${fieldNames[field]}</label>
                            <select onchange="RaceWizard.updateResearchCost('${field}', this.value)">
                                ${costs.map(cost => `
                                    <option value="${cost}" ${this.raceData.researchCosts[field] === cost ? 'selected' : ''}>
                                        ${costLabels[cost]}
                                    </option>
                                `).join('')}
                            </select>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="wizard-section">
                <h3>Starting Technology</h3>

                <label class="checkbox-option">
                    <input type="checkbox" ${this.raceData.startAtLevel3 ? 'checked' : ''}
                           onchange="RaceWizard.updateField('startAtLevel3', this.checked)">
                    <span>Start at tech level 3 in all fields (costs points)</span>
                </label>
            </div>
        `;
    },

    /**
     * Bind events for the current tab.
     */
    bindEvents() {
        // Events are bound inline via onclick/onchange attributes
    },

    /**
     * Go to specific tab.
     */
    goToTab(index) {
        this.currentTab = index;
        this.render();
    },

    /**
     * Go to next tab.
     */
    nextTab() {
        if (this.currentTab < this.tabs.length - 1) {
            this.currentTab++;
            this.render();
        }
    },

    /**
     * Go to previous tab.
     */
    prevTab() {
        if (this.currentTab > 0) {
            this.currentTab--;
            this.render();
        }
    },

    /**
     * Update a field value.
     */
    updateField(field, value) {
        this.raceData[field] = value;
        this.calculatePoints();
        this.render();
    },

    /**
     * Update a slider value.
     */
    updateSlider(field, value, displayId) {
        this.raceData[field] = parseInt(value);
        document.getElementById(displayId).textContent = value;
        this.calculatePoints();
        // Update just the points display without full re-render
        this.updatePointsDisplay();
    },

    /**
     * Select race icon.
     */
    selectIcon(index) {
        this.raceData.icon = index;
        this.render();
    },

    /**
     * Select Primary Racial Trait.
     */
    selectPRT(key) {
        this.raceData.prt = key;
        this.calculatePoints();
        this.render();
    },

    /**
     * Toggle Lesser Racial Trait.
     */
    toggleLRT(key) {
        const index = this.raceData.lrts.indexOf(key);
        if (index === -1) {
            this.raceData.lrts.push(key);
        } else {
            this.raceData.lrts.splice(index, 1);
        }
        this.calculatePoints();
        this.render();
    },

    /**
     * Update research cost for a field.
     */
    updateResearchCost(field, value) {
        this.raceData.researchCosts[field] = value;
        this.calculatePoints();
        this.updatePointsDisplay();
    },

    /**
     * Calculate advantage points.
     */
    calculatePoints() {
        let points = 25;  // Base points

        // PRT cost
        const prtData = this.primaryTraits[this.raceData.prt];
        if (prtData) {
            points += prtData.points;
        }

        // LRT costs
        for (const lrt of this.raceData.lrts) {
            const lrtData = this.lesserTraits[lrt];
            if (lrtData) {
                points += lrtData.points;
            }
        }

        // Production costs (simplified)
        // Cheaper factories/mines cost points
        points -= (10 - this.raceData.factoryCost) * 2;
        points -= (10 - this.raceData.factoryEfficiency) * 3;
        points -= (this.raceData.factoryNumberPer10k - 10) * 2;
        points -= (5 - this.raceData.mineCost) * 2;
        points -= (10 - this.raceData.mineEfficiency) * 2;
        points -= (this.raceData.mineNumberPer10k - 10) * 2;
        points -= (1000 - this.raceData.colonistsPerResource) / 100;

        // Environment costs
        // Wider habitat ranges cost points
        const gravRange = this.raceData.immuneGravity ? 100 : (this.raceData.gravityMax - this.raceData.gravityMin);
        const tempRange = this.raceData.immuneTemperature ? 100 : (this.raceData.temperatureMax - this.raceData.temperatureMin);
        const radRange = this.raceData.immuneRadiation ? 100 : (this.raceData.radiationMax - this.raceData.radiationMin);

        points -= (gravRange - 70) / 5;
        points -= (tempRange - 70) / 5;
        points -= (radRange - 70) / 5;

        // Immunity is expensive
        if (this.raceData.immuneGravity) points -= 20;
        if (this.raceData.immuneTemperature) points -= 20;
        if (this.raceData.immuneRadiation) points -= 20;

        // Growth rate cost
        points -= (this.raceData.growthRate - 15) * 3;

        // Research costs
        const researchCostMod = { cheap: -15, normal: 0, expensive: 10 };
        for (const field of Object.keys(this.raceData.researchCosts)) {
            const cost = this.raceData.researchCosts[field];
            points += researchCostMod[cost] || 0;
        }

        // Starting tech cost
        if (this.raceData.startAtLevel3) {
            points -= 10;
        }

        this.advantagePoints = Math.round(points);
    },

    /**
     * Update just the points display.
     */
    updatePointsDisplay() {
        const pointsEl = this.container.querySelector('.advantage-points strong');
        const containerEl = this.container.querySelector('.advantage-points');
        if (pointsEl) {
            pointsEl.textContent = this.advantagePoints;
        }
        if (containerEl) {
            containerEl.classList.toggle('valid', this.advantagePoints >= 0);
            containerEl.classList.toggle('invalid', this.advantagePoints < 0);
        }
        // Update save button
        const saveBtn = this.container.querySelector('.btn-primary');
        if (saveBtn) {
            saveBtn.disabled = this.advantagePoints < 0;
        }
    },

    /**
     * Validate the race configuration.
     */
    validate() {
        const errors = [];

        if (!this.raceData.name || this.raceData.name.trim() === '') {
            errors.push('Race name is required');
        }

        if (!this.raceData.pluralName || this.raceData.pluralName.trim() === '') {
            errors.push('Plural name is required');
        }

        if (this.advantagePoints < 0) {
            errors.push(`You are ${-this.advantagePoints} points over budget`);
        }

        return errors;
    },

    /**
     * Save the race.
     */
    async saveRace() {
        const errors = this.validate();
        if (errors.length > 0) {
            alert('Cannot save race:\n' + errors.join('\n'));
            return;
        }

        try {
            // For now, store in localStorage - backend API can be added later
            const races = JSON.parse(localStorage.getItem('customRaces') || '[]');
            races.push({
                ...this.raceData,
                id: Date.now(),
                created: new Date().toISOString()
            });
            localStorage.setItem('customRaces', JSON.stringify(races));

            alert(`Race "${this.raceData.name}" saved successfully!`);
            this.hide();
        } catch (error) {
            alert('Failed to save race: ' + error.message);
        }
    },

    /**
     * Load saved races.
     */
    loadSavedRaces() {
        try {
            return JSON.parse(localStorage.getItem('customRaces') || '[]');
        } catch {
            return [];
        }
    }
};

// Export
window.RaceWizard = RaceWizard;
