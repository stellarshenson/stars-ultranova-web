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
        research: { label: 'Research', icon: '\uD83D\uDD2C' },
        score: { label: 'Score', icon: '\uD83C\uDFC6' }
    },

    // Line colors for the score history graph, indexed by empire id
    SCORE_GRAPH_COLORS: [
        '#66ccff', '#ff6666', '#66ff66', '#ffcc44',
        '#cc66ff', '#ff9944', '#44ffcc', '#ff66cc'
    ],

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
            case 'score':
                return this.renderScore();
            default:
                return '<p>Unknown tab</p>';
        }
    },

    /**
     * Render the score report: one row per empire with the C# Score
     * report columns (ScoreReport.Designer.cs:91-146), plus a score
     * history graph. Scores are public to all players (Intel.AllScores).
     * @returns {string} HTML content
     */
    renderScore() {
        const scores = (window.GameState && GameState.scores) || [];
        if (scores.length === 0) {
            return '<p class="info-text">No score data available.</p>';
        }

        // C# column order: Race, Rank, Score, Planets, Starbases,
        // Unarmed Ships, Escort Ships, Capital Ships, Tech Levels,
        // Resources (the web shows the race name where C# rendered
        // the EmpireId as hex, ScoreReport.cs:68)
        const columns = [
            ['race_name', 'Race'],
            ['rank', 'Rank'],
            ['score', 'Score'],
            ['planets', 'Planets'],
            ['starbases', 'Starbases'],
            ['unarmed_ships', 'Unarmed Ships'],
            ['escort_ships', 'Escort Ships'],
            ['capital_ships', 'Capital Ships'],
            ['tech_level', 'Tech Levels'],
            ['resources', 'Resources']
        ];

        let sortedScores = [...scores];
        if (this.sortColumn) {
            sortedScores.sort((a, b) => {
                let aVal = a[this.sortColumn] ?? 0;
                let bVal = b[this.sortColumn] ?? 0;
                if (typeof aVal === 'string') {
                    aVal = aVal.toLowerCase();
                    bVal = (bVal || '').toLowerCase();
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
                            ${columns.map(([key, label]) => `
                            <th class="sortable" data-column="${key}">
                                ${label} ${this.getSortIndicator(key)}
                            </th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${sortedScores.map(s => `
                            <tr class="report-row">
                                <td class="race-cell">${s.empire_id === GameState.empireId && window.RaceIcons
                                    ? RaceIcons.renderRace(GameState.race, 18) : ''}${s.race_name || `Empire ${s.empire_id}`}</td>
                                <td class="number">${s.rank}</td>
                                <td class="number">${s.score}</td>
                                <td class="number">${s.planets}</td>
                                <td class="number">${s.starbases}</td>
                                <td class="number">${s.unarmed_ships}</td>
                                <td class="number">${s.escort_ships}</td>
                                <td class="number">${s.capital_ships}</td>
                                <td class="number">${s.tech_level}</td>
                                <td class="number">${s.resources}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            ${this.renderScoreHistoryGraph(scores)}
        `;
    },

    /**
     * Score history line graph (SVG): one polyline per empire,
     * x = year, y = score. Canonical Stars! shows this graph in its
     * Score report; the history itself is a web extension.
     * @param {Array} scores - Current score records (for race names)
     * @returns {string} SVG markup or empty string
     */
    renderScoreHistoryGraph(scores) {
        const history = (window.GameState && GameState.scoreHistory) || {};
        const series = Object.entries(history)
            .filter(([, entries]) => entries && entries.length > 0);
        if (series.length === 0) {
            return '';
        }

        const width = 560;
        const height = 200;
        const pad = 30;

        let minYear = Infinity;
        let maxYear = -Infinity;
        let maxScore = 1;
        for (const [, entries] of series) {
            for (const e of entries) {
                minYear = Math.min(minYear, e.year);
                maxYear = Math.max(maxYear, e.year);
                maxScore = Math.max(maxScore, e.score);
            }
        }
        const yearSpan = Math.max(1, maxYear - minYear);

        const x = (year) => pad + ((year - minYear) / yearSpan) * (width - 2 * pad);
        const y = (score) => height - pad - (score / maxScore) * (height - 2 * pad);

        const raceName = (empireId) => {
            const record = scores.find(s => s.empire_id === parseInt(empireId));
            return record ? record.race_name : `Empire ${empireId}`;
        };

        const lines = series.map(([empireId, entries]) => {
            const color = this.SCORE_GRAPH_COLORS[
                parseInt(empireId) % this.SCORE_GRAPH_COLORS.length];
            const points = entries
                .map(e => `${x(e.year).toFixed(1)},${y(e.score).toFixed(1)}`)
                .join(' ');
            return `<polyline points="${points}" fill="none"
                        stroke="${color}" stroke-width="2"/>`;
        }).join('');

        const legend = series.map(([empireId], i) => {
            const color = this.SCORE_GRAPH_COLORS[
                parseInt(empireId) % this.SCORE_GRAPH_COLORS.length];
            return `<span style="color: ${color}; margin-right: 12px;">
                        &#9632; ${raceName(empireId)}</span>`;
        }).join('');

        return `
            <div class="score-history-graph">
                <h3>Score History</h3>
                <svg viewBox="0 0 ${width} ${height}" width="100%"
                     style="max-width: ${width}px; background: rgba(0,0,0,0.3);">
                    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}"
                          y2="${height - pad}" stroke="#666"/>
                    <line x1="${pad}" y1="${pad}" x2="${pad}"
                          y2="${height - pad}" stroke="#666"/>
                    <text x="${pad}" y="${height - pad + 14}" fill="#999"
                          font-size="10">${minYear}</text>
                    <text x="${width - pad}" y="${height - pad + 14}" fill="#999"
                          font-size="10" text-anchor="end">${maxYear}</text>
                    <text x="${pad - 4}" y="${pad}" fill="#999" font-size="10"
                          text-anchor="end">${maxScore}</text>
                    ${lines}
                </svg>
                <div>${legend}</div>
            </div>
        `;
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
        return `(${Math.round(fleet.position_x)}, ${Math.round(fleet.position_y)})`;
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
        const rs = GameState.research;
        if (!rs) {
            return '<p class="info-text">No research data available.</p>';
        }

        const colors = {
            Energy: '#ffcc00', Weapons: '#ff4444', Propulsion: '#44ff44',
            Construction: '#888888', Electronics: '#4488ff', Biotechnology: '#ff88ff'
        };
        const fieldNames = ['Energy', 'Weapons', 'Propulsion', 'Construction', 'Electronics', 'Biotechnology'];
        const currentField = fieldNames.find(f => (rs.topics || {})[f] === 1) || 'Energy';

        const fields = fieldNames.map(name => {
            const level = (rs.levels || {})[name] || 0;
            const progress = (rs.progress || {})[name] || 0;
            const cost = (rs.next_costs || {})[name] || 1;
            return {
                name, level,
                progress: Math.min(100, Math.round((progress / cost) * 100)),
                progressText: `${progress} / ${cost}`,
                color: colors[name]
            };
        });

        return `
            <div class="research-status">
                <div class="research-summary">
                    <div class="research-budget">
                        <span class="label">Research Budget:</span>
                        <span class="value">${rs.budget}%</span>
                    </div>
                    <div class="current-research">
                        <span class="label">Currently Researching:</span>
                        <span class="value">${currentField}</span>
                    </div>
                </div>

                <div class="research-fields">
                    ${fields.map(field => `
                        <div class="research-field ${field.name === currentField ? 'active' : ''}">
                            <div class="field-header">
                                <span class="field-name">${field.name}</span>
                                <span class="field-level">Level ${field.level}</span>
                            </div>
                            <div class="field-progress">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${field.progress}%; background-color: ${field.color}"></div>
                                </div>
                                <span class="progress-text">${field.progressText}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>

                <div class="research-info">
                    <p class="info-text">
                        Use Commands &gt; Research... to change the research field and budget.
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
                GalaxyMap.centerOn(star.position_x, star.position_y);
                GameState.selectStar(star);
            }
        } else if (type === 'fleet') {
            const fleet = GameState.fleets.find(f => f.name === name);
            if (fleet) {
                GalaxyMap.centerOn(fleet.position_x, fleet.position_y);
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
        } else if (this.currentTab === 'score') {
            csv = this.exportScoresCSV();
            filename = 'scores.csv';
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
     * Export scores to CSV.
     * @returns {string} CSV content
     */
    exportScoresCSV() {
        const scores = (GameState.scores || []);
        let csv = 'Race,Rank,Score,Planets,Starbases,UnarmedShips,EscortShips,CapitalShips,TechLevels,Resources\n';

        for (const s of scores) {
            csv += `${s.race_name || s.empire_id},${s.rank},${s.score},${s.planets},`;
            csv += `${s.starbases},${s.unarmed_ships},${s.escort_ships},`;
            csv += `${s.capital_ships},${s.tech_level},${s.resources}\n`;
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
