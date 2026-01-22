/**
 * Stars Nova Web - Reports Screen
 * Displays game reports: Planet Summary, Fleet Summary, Research Status
 */

const Reports = {
    container: null,
    currentTab: 'planets',
    sortColumn: null,
    sortDirection: 'asc',

    /**
     * Tab definitions
     */
    TABS: {
        planets: { label: 'Planets', icon: '\uD83C\uDF0D' },
        fleets: { label: 'Fleets', icon: '\uD83D\uDE80' },
        research: { label: 'Research', icon: '\uD83D\uDD2C' }
    },

    /**
     * Initialize the reports component.
     * @param {string} containerId - Container element ID
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            // Create container if it doesn't exist
            this.container = document.createElement('div');
            this.container.id = containerId;
            this.container.className = 'floating-panel reports-panel hidden';
            document.querySelector('main')?.appendChild(this.container);
        }
        console.log('Reports initialized');
    },

    /**
     * Show the reports panel.
     * @param {string} tab - Initial tab to show ('planets', 'fleets', 'research')
     */
    show(tab = 'planets') {
        this.currentTab = tab;
        this.render();
        this.container.classList.remove('hidden');
    },

    /**
     * Hide the reports panel.
     */
    hide() {
        this.container.classList.add('hidden');
    },

    /**
     * Toggle reports panel visibility.
     */
    toggle() {
        if (this.container.classList.contains('hidden')) {
            this.show();
        } else {
            this.hide();
        }
    },

    /**
     * Render the reports panel.
     */
    render() {
        this.container.innerHTML = `
            <div class="reports-header">
                <h2>Reports</h2>
                <button class="btn-close" onclick="Reports.hide()">&times;</button>
            </div>
            <div class="reports-tabs">
                ${Object.entries(this.TABS).map(([id, tab]) => `
                    <button class="report-tab ${id === this.currentTab ? 'active' : ''}"
                            data-tab="${id}">
                        <span class="tab-icon">${tab.icon}</span>
                        <span class="tab-label">${tab.label}</span>
                    </button>
                `).join('')}
            </div>
            <div class="reports-content">
                ${this.renderTabContent()}
            </div>
            <div class="reports-footer">
                <button class="btn-small" onclick="Reports.exportCSV()">Export CSV</button>
                <button class="btn-small btn-primary" onclick="Reports.hide()">Close</button>
            </div>
        `;

        // Bind tab events
        this.container.querySelectorAll('.report-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.currentTab = tab.dataset.tab;
                this.sortColumn = null;
                this.render();
            });
        });

        // Bind sort events
        this.container.querySelectorAll('.sortable').forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                if (this.sortColumn === column) {
                    this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortColumn = column;
                    this.sortDirection = 'asc';
                }
                this.render();
            });
        });

        // Bind row click events for navigation
        this.container.querySelectorAll('.report-row[data-name]').forEach(row => {
            row.addEventListener('click', () => {
                this.navigateTo(row.dataset.name, row.dataset.type);
            });
        });
    },

    /**
     * Render content for current tab.
     * @returns {string} HTML content
     */
    renderTabContent() {
        switch (this.currentTab) {
            case 'planets':
                return this.renderPlanets();
            case 'fleets':
                return this.renderFleets();
            case 'research':
                return this.renderResearch();
            default:
                return '<p>Unknown tab</p>';
        }
    },

    /**
     * Render planet summary table.
     * @returns {string} HTML content
     */
    renderPlanets() {
        if (!window.GameState || !GameState.stars) {
            return '<p class="info-text">No game loaded</p>';
        }

        // Filter to player's planets
        const planets = GameState.stars.filter(s => s.owner === 1);

        if (planets.length === 0) {
            return '<p class="info-text">No planets colonized</p>';
        }

        // Sort planets
        let sortedPlanets = [...planets];
        if (this.sortColumn) {
            sortedPlanets.sort((a, b) => {
                let aVal = this.getPlanetValue(a, this.sortColumn);
                let bVal = this.getPlanetValue(b, this.sortColumn);

                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
        }

        return `
            <div class="report-table-container">
                <table class="report-table">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="name">
                                Planet ${this.getSortIndicator('name')}
                            </th>
                            <th class="sortable" data-column="population">
                                Pop ${this.getSortIndicator('population')}
                            </th>
                            <th class="sortable" data-column="mines">
                                Mines ${this.getSortIndicator('mines')}
                            </th>
                            <th class="sortable" data-column="factories">
                                Factories ${this.getSortIndicator('factories')}
                            </th>
                            <th class="sortable" data-column="ironium">
                                Ir ${this.getSortIndicator('ironium')}
                            </th>
                            <th class="sortable" data-column="boranium">
                                Bo ${this.getSortIndicator('boranium')}
                            </th>
                            <th class="sortable" data-column="germanium">
                                Ge ${this.getSortIndicator('germanium')}
                            </th>
                            <th class="sortable" data-column="resources">
                                Res/yr ${this.getSortIndicator('resources')}
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        ${sortedPlanets.map(p => `
                            <tr class="report-row" data-name="${p.name}" data-type="star">
                                <td class="planet-name">${p.name}</td>
                                <td class="number">${this.formatPopulation(p.colonists || 0)}</td>
                                <td class="number">${p.mines || 0}/${p.max_mines || 0}</td>
                                <td class="number">${p.factories || 0}/${p.max_factories || 0}</td>
                                <td class="number resource-ir">${p.ironium || 0}</td>
                                <td class="number resource-bo">${p.boranium || 0}</td>
                                <td class="number resource-ge">${p.germanium || 0}</td>
                                <td class="number">${this.calculateResources(p)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                    <tfoot>
                        <tr class="report-totals">
                            <td>Total: ${sortedPlanets.length}</td>
                            <td class="number">${this.formatPopulation(
                                sortedPlanets.reduce((sum, p) => sum + (p.colonists || 0), 0)
                            )}</td>
                            <td class="number">${sortedPlanets.reduce((sum, p) => sum + (p.mines || 0), 0)}</td>
                            <td class="number">${sortedPlanets.reduce((sum, p) => sum + (p.factories || 0), 0)}</td>
                            <td class="number resource-ir">${sortedPlanets.reduce((sum, p) => sum + (p.ironium || 0), 0)}</td>
                            <td class="number resource-bo">${sortedPlanets.reduce((sum, p) => sum + (p.boranium || 0), 0)}</td>
                            <td class="number resource-ge">${sortedPlanets.reduce((sum, p) => sum + (p.germanium || 0), 0)}</td>
                            <td class="number">${sortedPlanets.reduce((sum, p) => sum + this.calculateResources(p), 0)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
    },

    /**
     * Get planet value for sorting.
     * @param {Object} planet - Planet object
     * @param {string} column - Column name
     * @returns {*} Value for sorting
     */
    getPlanetValue(planet, column) {
        switch (column) {
            case 'name': return planet.name || '';
            case 'population': return planet.colonists || 0;
            case 'mines': return planet.mines || 0;
            case 'factories': return planet.factories || 0;
            case 'ironium': return planet.ironium || 0;
            case 'boranium': return planet.boranium || 0;
            case 'germanium': return planet.germanium || 0;
            case 'resources': return this.calculateResources(planet);
            default: return 0;
        }
    },

    /**
     * Render fleet summary table.
     * @returns {string} HTML content
     */
    renderFleets() {
        if (!window.GameState || !GameState.fleets) {
            return '<p class="info-text">No game loaded</p>';
        }

        // Filter to player's fleets
        const fleets = GameState.fleets.filter(f => f.owner === 1);

        if (fleets.length === 0) {
            return '<p class="info-text">No fleets</p>';
        }

        // Sort fleets
        let sortedFleets = [...fleets];
        if (this.sortColumn) {
            sortedFleets.sort((a, b) => {
                let aVal = this.getFleetValue(a, this.sortColumn);
                let bVal = this.getFleetValue(b, this.sortColumn);

                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = bVal.toLowerCase();
                }

                if (aVal < bVal) return this.sortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
        }

        return `
            <div class="report-table-container">
                <table class="report-table">
                    <thead>
                        <tr>
                            <th class="sortable" data-column="name">
                                Fleet ${this.getSortIndicator('name')}
                            </th>
                            <th class="sortable" data-column="location">
                                Location ${this.getSortIndicator('location')}
                            </th>
                            <th class="sortable" data-column="ships">
                                Ships ${this.getSortIndicator('ships')}
                            </th>
                            <th class="sortable" data-column="fuel">
                                Fuel ${this.getSortIndicator('fuel')}
                            </th>
                            <th class="sortable" data-column="cargo">
                                Cargo ${this.getSortIndicator('cargo')}
                            </th>
                            <th>Task</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${sortedFleets.map(f => `
                            <tr class="report-row" data-name="${f.name}" data-type="fleet" data-key="${f.key}">
                                <td class="fleet-name">${f.name}</td>
                                <td>${this.getFleetLocation(f)}</td>
                                <td class="number">${this.getShipCount(f)}</td>
                                <td class="number">${f.fuel || 0}/${f.fuel_capacity || 0}</td>
                                <td class="number">${this.getCargoTotal(f)}/${f.cargo_capacity || 0}</td>
                                <td>${this.getFleetTask(f)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                    <tfoot>
                        <tr class="report-totals">
                            <td>Total: ${sortedFleets.length}</td>
                            <td></td>
                            <td class="number">${sortedFleets.reduce((sum, f) => sum + this.getShipCount(f), 0)}</td>
                            <td class="number">${sortedFleets.reduce((sum, f) => sum + (f.fuel || 0), 0)}</td>
                            <td class="number">${sortedFleets.reduce((sum, f) => sum + this.getCargoTotal(f), 0)}</td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
    },

    /**
     * Get fleet value for sorting.
     * @param {Object} fleet - Fleet object
     * @param {string} column - Column name
     * @returns {*} Value for sorting
     */
    getFleetValue(fleet, column) {
        switch (column) {
            case 'name': return fleet.name || '';
            case 'location': return this.getFleetLocation(fleet);
            case 'ships': return this.getShipCount(fleet);
            case 'fuel': return fleet.fuel || 0;
            case 'cargo': return this.getCargoTotal(fleet);
            default: return 0;
        }
    },

    /**
     * Get fleet location string.
     * @param {Object} fleet - Fleet object
     * @returns {string} Location description
     */
    getFleetLocation(fleet) {
        if (fleet.in_orbit_name) {
            return fleet.in_orbit_name;
        }
        return `(${Math.round(fleet.x)}, ${Math.round(fleet.y)})`;
    },

    /**
     * Get ship count for fleet.
     * @param {Object} fleet - Fleet object
     * @returns {number} Total ships
     */
    getShipCount(fleet) {
        if (!fleet.tokens) return 0;
        return fleet.tokens.reduce((sum, t) => sum + (t.quantity || 1), 0);
    },

    /**
     * Get total cargo for fleet.
     * @param {Object} fleet - Fleet object
     * @returns {number} Total cargo
     */
    getCargoTotal(fleet) {
        return (fleet.ironium || 0) +
               (fleet.boranium || 0) +
               (fleet.germanium || 0) +
               (fleet.colonists || 0);
    },

    /**
     * Get fleet current task.
     * @param {Object} fleet - Fleet object
     * @returns {string} Task description
     */
    getFleetTask(fleet) {
        if (!fleet.waypoints || fleet.waypoints.length === 0) {
            return 'Idle';
        }
        const wp = fleet.waypoints[0];
        return wp.task || 'Move';
    },

    /**
     * Render research status.
     * @returns {string} HTML content
     */
    renderResearch() {
        // Default research data (would come from empire data in full implementation)
        const research = {
            budget: 15,
            fields: [
                { name: 'Energy', level: 3, progress: 45, color: '#ffcc00' },
                { name: 'Weapons', level: 3, progress: 30, color: '#ff4444' },
                { name: 'Propulsion', level: 3, progress: 60, color: '#44ff44' },
                { name: 'Construction', level: 3, progress: 15, color: '#888888' },
                { name: 'Electronics', level: 3, progress: 50, color: '#4488ff' },
                { name: 'Biotechnology', level: 3, progress: 25, color: '#ff88ff' }
            ],
            currentField: 'Propulsion'
        };

        return `
            <div class="research-status">
                <div class="research-summary">
                    <div class="research-budget">
                        <span class="label">Research Budget:</span>
                        <span class="value">${research.budget}%</span>
                    </div>
                    <div class="current-research">
                        <span class="label">Currently Researching:</span>
                        <span class="value">${research.currentField}</span>
                    </div>
                </div>

                <div class="research-fields">
                    ${research.fields.map(field => `
                        <div class="research-field ${field.name === research.currentField ? 'active' : ''}">
                            <div class="field-header">
                                <span class="field-name">${field.name}</span>
                                <span class="field-level">Level ${field.level}</span>
                            </div>
                            <div class="field-progress">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${field.progress}%; background-color: ${field.color}"></div>
                                </div>
                                <span class="progress-text">${field.progress}%</span>
                            </div>
                        </div>
                    `).join('')}
                </div>

                <div class="research-info">
                    <p class="info-text">
                        Click on a field to set it as the current research priority.
                        Higher budget allocation speeds up research progress.
                    </p>
                </div>
            </div>
        `;
    },

    /**
     * Get sort indicator for column.
     * @param {string} column - Column name
     * @returns {string} Sort indicator HTML
     */
    getSortIndicator(column) {
        if (this.sortColumn !== column) {
            return '<span class="sort-indicator"></span>';
        }
        const arrow = this.sortDirection === 'asc' ? '\u25B2' : '\u25BC';
        return `<span class="sort-indicator active">${arrow}</span>`;
    },

    /**
     * Calculate resources per year for a planet.
     * @param {Object} planet - Planet object
     * @returns {number} Resources per year
     */
    calculateResources(planet) {
        // Simplified formula: colonists/100 + factories
        const popResources = Math.floor((planet.colonists || 0) / 100);
        const factoryResources = planet.factories || 0;
        return popResources + factoryResources;
    },

    /**
     * Format population for display.
     * @param {number} pop - Population value
     * @returns {string} Formatted string
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
     * Navigate to selected item on map.
     * @param {string} name - Item name
     * @param {string} type - Item type ('star' or 'fleet')
     */
    navigateTo(name, type) {
        if (!window.GameState || !window.GalaxyMap) return;

        if (type === 'star') {
            const star = GameState.stars.find(s => s.name === name);
            if (star) {
                GalaxyMap.centerOn(star.x, star.y);
                GameState.selectStar(star);
            }
        } else if (type === 'fleet') {
            const fleet = GameState.fleets.find(f => f.name === name);
            if (fleet) {
                GalaxyMap.centerOn(fleet.x, fleet.y);
                GameState.selectFleet(fleet);
            }
        }

        this.hide();
    },

    /**
     * Export current report to CSV.
     */
    exportCSV() {
        let csv = '';
        let filename = '';

        if (this.currentTab === 'planets') {
            csv = this.exportPlanetsCSV();
            filename = 'planets.csv';
        } else if (this.currentTab === 'fleets') {
            csv = this.exportFleetsCSV();
            filename = 'fleets.csv';
        } else if (this.currentTab === 'research') {
            csv = this.exportResearchCSV();
            filename = 'research.csv';
        }

        // Download
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },

    /**
     * Export planets to CSV.
     * @returns {string} CSV content
     */
    exportPlanetsCSV() {
        const planets = (GameState.stars || []).filter(s => s.owner === 1);
        let csv = 'Planet,Population,Mines,MaxMines,Factories,MaxFactories,Ironium,Boranium,Germanium,Resources/yr\n';

        for (const p of planets) {
            csv += `${p.name},${p.colonists || 0},${p.mines || 0},${p.max_mines || 0},`;
            csv += `${p.factories || 0},${p.max_factories || 0},`;
            csv += `${p.ironium || 0},${p.boranium || 0},${p.germanium || 0},`;
            csv += `${this.calculateResources(p)}\n`;
        }

        return csv;
    },

    /**
     * Export fleets to CSV.
     * @returns {string} CSV content
     */
    exportFleetsCSV() {
        const fleets = (GameState.fleets || []).filter(f => f.owner === 1);
        let csv = 'Fleet,Location,Ships,Fuel,FuelCapacity,Cargo,CargoCapacity,Task\n';

        for (const f of fleets) {
            csv += `${f.name},${this.getFleetLocation(f)},${this.getShipCount(f)},`;
            csv += `${f.fuel || 0},${f.fuel_capacity || 0},`;
            csv += `${this.getCargoTotal(f)},${f.cargo_capacity || 0},`;
            csv += `${this.getFleetTask(f)}\n`;
        }

        return csv;
    },

    /**
     * Export research to CSV.
     * @returns {string} CSV content
     */
    exportResearchCSV() {
        let csv = 'Field,Level,Progress\n';
        const fields = ['Energy', 'Weapons', 'Propulsion', 'Construction', 'Electronics', 'Biotechnology'];

        for (const field of fields) {
            csv += `${field},3,0\n`;  // Placeholder values
        }

        return csv;
    }
};

window.Reports = Reports;
