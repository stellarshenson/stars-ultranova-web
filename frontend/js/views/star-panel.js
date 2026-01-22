/**
 * Stars Nova Web - Star Panel
 * Displays planet details, resources, and production queue.
 * Ported from original Stars! visual style.
 */

const StarPanel = {
    // DOM elements
    container: null,

    // Current star being displayed
    currentStar: null,

    /**
     * Initialize the star panel.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Star panel container not found:', containerId);
            return;
        }

        // Listen to game state changes
        GameState.on('starSelected', (star) => this.show(star));
        GameState.on('fleetSelected', () => this.hide());
        GameState.on('selectionCleared', () => this.hide());
        GameState.on('turnGenerated', () => this.refresh());

        console.log('Star panel initialized');
    },

    /**
     * Show panel with star data.
     */
    show(star) {
        if (!star || !this.container) return;

        this.currentStar = star;
        this.container.classList.remove('hidden');
        this.render();
    },

    /**
     * Hide panel.
     */
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
        this.currentStar = null;
    },

    /**
     * Refresh current display.
     */
    refresh() {
        if (this.currentStar) {
            // Re-fetch star data
            const updated = GameState.stars.find(s => s.name === this.currentStar.name);
            if (updated) {
                this.currentStar = updated;
                this.render();
            }
        }
    },

    /**
     * Render the panel contents.
     */
    render() {
        const star = this.currentStar;
        if (!star || !this.container) return;

        const isColonized = star.colonists > 0;
        const isOwned = star.owner === 1;  // Player owns it

        let html = `
            <div class="star-panel-header">
                <h2>${star.name}</h2>
                <span class="star-position">(${star.position_x}, ${star.position_y})</span>
            </div>
        `;

        if (isColonized) {
            html += this.renderColonizedPlanet(star, isOwned);
        } else {
            html += this.renderUncolonizedPlanet(star);
        }

        this.container.innerHTML = html;

        // Bind production queue events if owned
        if (isOwned && isColonized) {
            this.bindProductionEvents();
        }
    },

    /**
     * Render colonized planet details.
     */
    renderColonizedPlanet(star, isOwned) {
        const maxPop = star.max_population || 1000000;
        const popPercent = Math.min(100, (star.colonists / maxPop) * 100);

        let html = `
            <div class="star-section">
                <h3>Population</h3>
                <div class="stat-row">
                    <span>Colonists:</span>
                    <span class="stat-value">${this.formatNumber(star.colonists)}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill population" style="width: ${popPercent}%"></div>
                </div>
                <div class="stat-row">
                    <span>Capacity:</span>
                    <span class="stat-value">${this.formatNumber(maxPop)}</span>
                </div>
            </div>

            <div class="star-section">
                <h3>Infrastructure</h3>
                <div class="stat-row">
                    <span>Factories:</span>
                    <span class="stat-value">${star.factories || 0}</span>
                </div>
                <div class="stat-row">
                    <span>Mines:</span>
                    <span class="stat-value">${star.mines || 0}</span>
                </div>
                <div class="stat-row">
                    <span>Defenses:</span>
                    <span class="stat-value">${star.defenses || 0}</span>
                </div>
            </div>

            <div class="star-section">
                <h3>Resources On Hand</h3>
                ${this.renderResourceBar('Ironium', star.ironium || 0, 5000, 'ironium')}
                ${this.renderResourceBar('Boranium', star.boranium || 0, 5000, 'boranium')}
                ${this.renderResourceBar('Germanium', star.germanium || 0, 5000, 'germanium')}
            </div>

            <div class="star-section">
                <h3>Mineral Concentrations</h3>
                ${this.renderConcentrationBar('Ironium', star.ironium_concentration || 0)}
                ${this.renderConcentrationBar('Boranium', star.boranium_concentration || 0)}
                ${this.renderConcentrationBar('Germanium', star.germanium_concentration || 0)}
            </div>
        `;

        if (isOwned) {
            html += this.renderProductionQueue(star);
        }

        return html;
    },

    /**
     * Render uncolonized planet details.
     */
    renderUncolonizedPlanet(star) {
        return `
            <div class="star-section">
                <h3>Uncolonized</h3>
                <p class="info-text">This planet has no inhabitants.</p>
            </div>

            <div class="star-section">
                <h3>Environment</h3>
                <div class="stat-row">
                    <span>Gravity:</span>
                    <span class="stat-value">${star.gravity || 'Unknown'}</span>
                </div>
                <div class="stat-row">
                    <span>Temperature:</span>
                    <span class="stat-value">${star.temperature || 'Unknown'}</span>
                </div>
                <div class="stat-row">
                    <span>Radiation:</span>
                    <span class="stat-value">${star.radiation || 'Unknown'}</span>
                </div>
            </div>

            <div class="star-section">
                <h3>Mineral Concentrations</h3>
                ${this.renderConcentrationBar('Ironium', star.ironium_concentration || 0)}
                ${this.renderConcentrationBar('Boranium', star.boranium_concentration || 0)}
                ${this.renderConcentrationBar('Germanium', star.germanium_concentration || 0)}
            </div>
        `;
    },

    /**
     * Render a resource bar.
     */
    renderResourceBar(name, amount, max, cssClass) {
        const percent = Math.min(100, (amount / max) * 100);
        return `
            <div class="resource-row">
                <span class="resource-name">${name}:</span>
                <div class="resource-bar">
                    <div class="resource-fill ${cssClass}" style="width: ${percent}%"></div>
                </div>
                <span class="resource-value">${this.formatNumber(amount)}</span>
            </div>
        `;
    },

    /**
     * Render a concentration bar.
     */
    renderConcentrationBar(name, concentration) {
        const percent = Math.min(100, concentration);
        let cssClass = 'low';
        if (concentration >= 70) cssClass = 'high';
        else if (concentration >= 30) cssClass = 'medium';

        return `
            <div class="concentration-row">
                <span class="resource-name">${name}:</span>
                <div class="concentration-bar">
                    <div class="concentration-fill ${cssClass}" style="width: ${percent}%"></div>
                </div>
                <span class="concentration-value">${concentration}%</span>
            </div>
        `;
    },

    /**
     * Render production queue.
     */
    renderProductionQueue(star) {
        const queue = star.production_queue || [];

        let queueHtml = '';
        if (queue.length === 0) {
            queueHtml = '<p class="info-text">Production queue is empty.</p>';
        } else {
            queueHtml = '<ul class="production-queue">';
            for (const item of queue) {
                queueHtml += `
                    <li class="queue-item">
                        <span class="queue-name">${item.name || item.type}</span>
                        <span class="queue-quantity">x${item.quantity}</span>
                    </li>
                `;
            }
            queueHtml += '</ul>';
        }

        return `
            <div class="star-section">
                <h3>Production Queue</h3>
                ${queueHtml}
                <div class="production-buttons">
                    <button class="btn-small" id="btn-add-production">Add</button>
                    <button class="btn-small" id="btn-clear-queue">Clear</button>
                </div>
            </div>

            <div class="star-section">
                <h3>Output</h3>
                <div class="stat-row">
                    <span>Resources/Year:</span>
                    <span class="stat-value">${star.resources_per_year || 0}</span>
                </div>
            </div>
        `;
    },

    /**
     * Bind production queue button events.
     */
    bindProductionEvents() {
        const addBtn = document.getElementById('btn-add-production');
        const clearBtn = document.getElementById('btn-clear-queue');

        if (addBtn) {
            addBtn.addEventListener('click', () => this.showProductionDialog());
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearProductionQueue());
        }
    },

    /**
     * Show production dialog.
     */
    showProductionDialog() {
        // For now, use simple prompt - will be replaced with proper dialog
        const options = [
            '1. Factories',
            '2. Mines',
            '3. Defenses',
            '4. Scout Ship',
            '5. Colony Ship'
        ].join('\n');

        const choice = prompt(`Add to production queue:\n${options}\n\nEnter number:`);
        if (!choice) return;

        const types = ['factory', 'mine', 'defense', 'scout', 'colony_ship'];
        const index = parseInt(choice) - 1;

        if (index >= 0 && index < types.length) {
            const quantity = parseInt(prompt('Quantity:', '10')) || 1;
            this.addToProductionQueue(types[index], quantity);
        }
    },

    /**
     * Add item to production queue.
     */
    async addToProductionQueue(type, quantity) {
        if (!this.currentStar || !GameState.game) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'production',
                    star_name: this.currentStar.name,
                    action: 'add',
                    item_type: type,
                    quantity: quantity
                }
            );

            // Refresh star data
            this.refresh();
        } catch (error) {
            alert('Failed to add to queue: ' + error.message);
        }
    },

    /**
     * Clear production queue.
     */
    async clearProductionQueue() {
        if (!this.currentStar || !GameState.game) return;

        if (!confirm('Clear production queue?')) return;

        try {
            await ApiClient.request('POST',
                `/games/${GameState.game.id}/empires/1/commands`,
                {
                    type: 'production',
                    star_name: this.currentStar.name,
                    action: 'clear'
                }
            );

            this.refresh();
        } catch (error) {
            alert('Failed to clear queue: ' + error.message);
        }
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
window.StarPanel = StarPanel;
