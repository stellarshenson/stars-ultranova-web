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

    // Item costs (from game data - simplified for now)
    itemCosts: {
        factory: { ironium: 4, boranium: 0, germanium: 4, resources: 10 },
        mine: { ironium: 0, boranium: 0, germanium: 4, resources: 5 },
        defense: { ironium: 5, boranium: 5, germanium: 5, resources: 15 },
        scout: { ironium: 8, boranium: 2, germanium: 7, resources: 25 },
        colony_ship: { ironium: 20, boranium: 10, germanium: 15, resources: 50 }
    },

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
     * Get the cost of a production item.
     */
    getItemCost(item) {
        const itemType = (item.type || item.name || '').toLowerCase().replace(' ', '_');
        return this.itemCosts[itemType] || { ironium: 10, boranium: 10, germanium: 10, resources: 20 };
    },

    /**
     * Calculate completion time for a queue item.
     */
    calculateCompletionTime(star, item, queuePosition = 0) {
        const cost = this.getItemCost(item);
        const resourcesPerYear = star.resources_per_year || 1;
        const totalResourceCost = cost.resources * item.quantity;

        // Account for items ahead in queue
        const queue = star.production_queue || [];
        let resourcesUsedByPrior = 0;
        for (let i = 0; i < queuePosition; i++) {
            const priorItem = queue[i];
            const priorCost = this.getItemCost(priorItem);
            resourcesUsedByPrior += priorCost.resources * priorItem.quantity;
        }

        // Calculate years including queue wait
        const startYear = Math.floor(resourcesUsedByPrior / resourcesPerYear);
        const endYear = Math.ceil((resourcesUsedByPrior + totalResourceCost) / resourcesPerYear);

        const currentYear = GameState.game ? GameState.game.turn + 2400 : 2400;
        return {
            startYear: currentYear + startYear,
            endYear: currentYear + endYear,
            turnsRemaining: endYear - startYear
        };
    },

    /**
     * Check if star has enough minerals for item.
     */
    hasEnoughMinerals(star, item) {
        const cost = this.getItemCost(item);
        return (
            (star.ironium || 0) >= cost.ironium * item.quantity &&
            (star.boranium || 0) >= cost.boranium * item.quantity &&
            (star.germanium || 0) >= cost.germanium * item.quantity
        );
    },

    /**
     * Get queue item status class.
     */
    getQueueItemStatus(star, item, queuePosition) {
        const completion = this.calculateCompletionTime(star, item, queuePosition);
        const hasMinerals = this.hasEnoughMinerals(star, item);

        if (!hasMinerals) {
            return 'queue-insufficient';
        }
        if (completion.turnsRemaining === 0) {
            return 'queue-this-turn';
        }
        return 'queue-future';
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
            for (let i = 0; i < queue.length; i++) {
                const item = queue[i];
                const completion = this.calculateCompletionTime(star, item, i);
                const statusClass = this.getQueueItemStatus(star, item, i);
                const hasMinerals = this.hasEnoughMinerals(star, item);

                let completionText = '';
                if (!hasMinerals) {
                    completionText = `<span class="queue-status insufficient">Insufficient minerals</span>`;
                } else if (completion.turnsRemaining === 0) {
                    completionText = `<span class="queue-status this-turn">Completes this turn</span>`;
                } else if (completion.startYear === completion.endYear) {
                    completionText = `<span class="queue-status">Year ${completion.endYear}</span>`;
                } else {
                    completionText = `<span class="queue-status">Year ${completion.startYear}-${completion.endYear}</span>`;
                }

                queueHtml += `
                    <li class="queue-item ${statusClass}">
                        <div class="queue-item-main">
                            <span class="queue-name">${item.name || item.type}</span>
                            <span class="queue-quantity">x${item.quantity}</span>
                        </div>
                        <div class="queue-item-details">
                            ${completionText}
                        </div>
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
                <div class="production-hint">
                    <small>Shift+click: 10 | Ctrl+click: 100 | Both: 1000</small>
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
            addBtn.addEventListener('click', (e) => this.showProductionDialog(e));
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearProductionQueue());
        }
    },

    /**
     * Show production dialog.
     */
    showProductionDialog(event) {
        // Calculate default quantity based on modifier keys
        let defaultQuantity = 1;
        if (event && event.shiftKey && event.ctrlKey) {
            defaultQuantity = 1000;
        } else if (event && event.ctrlKey) {
            defaultQuantity = 100;
        } else if (event && event.shiftKey) {
            defaultQuantity = 10;
        }

        // Build options with costs
        const options = [
            '1. Factories (4 Ir, 4 Ge, 10 res)',
            '2. Mines (4 Ge, 5 res)',
            '3. Defenses (5 Ir, 5 Bo, 5 Ge, 15 res)',
            '4. Scout Ship (8 Ir, 2 Bo, 7 Ge, 25 res)',
            '5. Colony Ship (20 Ir, 10 Bo, 15 Ge, 50 res)'
        ].join('\n');

        const choice = prompt(`Add to production queue:\n${options}\n\nEnter number:`);
        if (!choice) return;

        const types = ['factory', 'mine', 'defense', 'scout', 'colony_ship'];
        const index = parseInt(choice) - 1;

        if (index >= 0 && index < types.length) {
            const quantityHint = defaultQuantity > 1 ? ` (default ${defaultQuantity} from modifier keys)` : '';
            const quantity = parseInt(prompt(`Quantity${quantityHint}:`, defaultQuantity.toString())) || 1;
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
