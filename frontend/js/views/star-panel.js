/**
 * Stars Nova Web - Star Panel
 * Displays planet details, resources, and production queue.
 * Ported from original Stars! visual style.
 */

const StarPanel = {
    // DOM elements
    container: null,

    // Planet canvas for procedural rendering
    planetCanvas: null,
    planetCtx: null,

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

        // Calculate habitability value (simplified - based on whether colonized and environment)
        const habitability = this.calculateHabitability(star);

        let html = `
            <div class="star-panel-header">
                <div class="planet-display">
                    <canvas id="planet-canvas" width="80" height="80"></canvas>
                    <div class="habitability-indicator ${habitability >= 0 ? 'positive' : 'negative'}">
                        ${habitability >= 0 ? '+' : ''}${habitability}%
                    </div>
                </div>
                <div class="star-info">
                    <h2>${star.name}</h2>
                    <span class="star-position">(${star.position_x}, ${star.position_y})</span>
                </div>
            </div>
        `;

        if (isColonized) {
            html += this.renderColonizedPlanet(star, isOwned);
        } else {
            html += this.renderUncolonizedPlanet(star);
        }

        this.container.innerHTML = html;

        // Render the procedural planet
        this.renderPlanetGraphic(star);

        // Bind production queue events if owned
        if (isOwned && isColonized) {
            this.bindProductionEvents();
        }
    },

    /**
     * Calculate habitability value for display.
     * Returns percentage from -45 to 100.
     */
    calculateHabitability(star) {
        // Use stored value if available
        if (star.habitability !== undefined) {
            return Math.round(star.habitability);
        }

        // Calculate based on environment (simplified)
        const gravity = star.gravity || 50;
        const temperature = star.temperature || 50;
        const radiation = star.radiation || 50;

        // Ideal ranges (can be customized per race)
        const gravityDiff = Math.abs(gravity - 50);
        const tempDiff = Math.abs(temperature - 50);
        const radDiff = Math.abs(radiation - 50);

        // Each diff reduces habitability
        const penalty = (gravityDiff + tempDiff + radDiff) / 3;
        const value = Math.round(100 - penalty * 2);

        return Math.max(-45, Math.min(100, value));
    },

    /**
     * Render procedural planet graphic on canvas.
     */
    renderPlanetGraphic(star) {
        this.planetCanvas = document.getElementById('planet-canvas');
        if (!this.planetCanvas) return;

        this.planetCtx = this.planetCanvas.getContext('2d');
        const ctx = this.planetCtx;
        const width = this.planetCanvas.width;
        const height = this.planetCanvas.height;

        // Clear canvas
        ctx.clearRect(0, 0, width, height);

        // Get environmental values (0-100 scale)
        const gravity = star.gravity || 50;
        const temperature = star.temperature || 50;
        const radiation = star.radiation || 50;

        // Planet size based on gravity (larger gravity = larger planet)
        const baseRadius = 25;
        const radiusVariation = (gravity - 50) / 50 * 8;
        const radius = baseRadius + radiusVariation;

        const centerX = width / 2;
        const centerY = height / 2;

        // Determine planet colors based on temperature
        const colors = this.getPlanetColors(temperature, radiation);

        // Draw atmosphere glow (radiation based)
        if (radiation > 30) {
            const glowIntensity = (radiation - 30) / 70;
            const gradient = ctx.createRadialGradient(
                centerX, centerY, radius,
                centerX, centerY, radius + 10 + glowIntensity * 8
            );
            gradient.addColorStop(0, `rgba(${colors.glow}, ${0.3 + glowIntensity * 0.3})`);
            gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius + 15, 0, Math.PI * 2);
            ctx.fill();
        }

        // Draw planet base with gradient
        const planetGradient = ctx.createRadialGradient(
            centerX - radius * 0.3, centerY - radius * 0.3, 0,
            centerX, centerY, radius
        );
        planetGradient.addColorStop(0, colors.highlight);
        planetGradient.addColorStop(0.5, colors.base);
        planetGradient.addColorStop(1, colors.shadow);

        ctx.fillStyle = planetGradient;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();

        // Add surface texture/bands based on star name hash for consistency
        this.drawPlanetTexture(ctx, centerX, centerY, radius, star.name, colors);

        // Draw terminator (shadow edge)
        const shadowGradient = ctx.createLinearGradient(
            centerX - radius, centerY,
            centerX + radius, centerY
        );
        shadowGradient.addColorStop(0, 'rgba(0, 0, 0, 0)');
        shadowGradient.addColorStop(0.6, 'rgba(0, 0, 0, 0)');
        shadowGradient.addColorStop(1, 'rgba(0, 0, 0, 0.5)');

        ctx.fillStyle = shadowGradient;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();

        // Add specular highlight
        const specGradient = ctx.createRadialGradient(
            centerX - radius * 0.4, centerY - radius * 0.4, 0,
            centerX - radius * 0.4, centerY - radius * 0.4, radius * 0.5
        );
        specGradient.addColorStop(0, 'rgba(255, 255, 255, 0.3)');
        specGradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

        ctx.fillStyle = specGradient;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
    },

    /**
     * Get planet colors based on temperature and radiation.
     */
    getPlanetColors(temperature, radiation) {
        // Temperature determines base color
        // 0-20: Frozen (white/blue)
        // 20-40: Cold (light blue/gray)
        // 40-60: Temperate (green/brown)
        // 60-80: Hot (orange/brown)
        // 80-100: Scorching (red/orange)

        let base, highlight, shadow, glow;

        if (temperature < 20) {
            // Frozen
            base = '#a0c8e8';
            highlight = '#e8f4ff';
            shadow = '#4080a0';
            glow = '150, 200, 255';
        } else if (temperature < 40) {
            // Cold
            base = '#7090a8';
            highlight = '#b0d0e8';
            shadow = '#304050';
            glow = '100, 150, 200';
        } else if (temperature < 60) {
            // Temperate (habitable)
            base = '#408040';
            highlight = '#80c080';
            shadow = '#204020';
            glow = '100, 200, 100';
        } else if (temperature < 80) {
            // Hot
            base = '#a08050';
            highlight = '#d0b080';
            shadow = '#604020';
            glow = '255, 150, 50';
        } else {
            // Scorching
            base = '#c04020';
            highlight = '#ff8060';
            shadow = '#601008';
            glow = '255, 100, 50';
        }

        // Radiation shifts toward purple/magenta
        if (radiation > 70) {
            const shift = (radiation - 70) / 30;
            base = this.shiftTowardPurple(base, shift * 0.3);
            glow = `${180 + shift * 75}, ${80 - shift * 30}, ${180 + shift * 75}`;
        }

        return { base, highlight, shadow, glow };
    },

    /**
     * Shift a color toward purple/magenta.
     */
    shiftTowardPurple(hexColor, amount) {
        const r = parseInt(hexColor.slice(1, 3), 16);
        const g = parseInt(hexColor.slice(3, 5), 16);
        const b = parseInt(hexColor.slice(5, 7), 16);

        const newR = Math.min(255, Math.round(r + (180 - r) * amount));
        const newG = Math.max(0, Math.round(g - g * amount * 0.5));
        const newB = Math.min(255, Math.round(b + (200 - b) * amount));

        return `#${newR.toString(16).padStart(2, '0')}${newG.toString(16).padStart(2, '0')}${newB.toString(16).padStart(2, '0')}`;
    },

    /**
     * Draw texture/bands on planet surface.
     */
    drawPlanetTexture(ctx, cx, cy, radius, starName, colors) {
        // Use star name hash for consistent texture per planet
        let hash = 0;
        for (let i = 0; i < starName.length; i++) {
            hash = ((hash << 5) - hash) + starName.charCodeAt(i);
            hash = hash & hash;
        }

        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.clip();

        // Draw horizontal bands
        const numBands = 3 + (Math.abs(hash) % 4);
        for (let i = 0; i < numBands; i++) {
            const y = cy - radius + (radius * 2 / numBands) * (i + 0.5);
            const bandHeight = radius * 0.15 + (Math.abs(hash >> (i * 4)) % 10) / 50;
            const offset = ((hash >> (i * 2)) % 20) - 10;

            ctx.fillStyle = `rgba(0, 0, 0, 0.1)`;
            ctx.beginPath();
            ctx.ellipse(cx + offset, y, radius * 0.9, bandHeight * radius, 0, 0, Math.PI * 2);
            ctx.fill();
        }

        // Add some spot features
        const numSpots = 1 + (Math.abs(hash >> 8) % 3);
        for (let i = 0; i < numSpots; i++) {
            const angle = (hash >> (i * 6)) % 360 * Math.PI / 180;
            const dist = radius * 0.3 + (Math.abs(hash >> (i * 3)) % 30) / 100 * radius;
            const spotX = cx + Math.cos(angle) * dist * 0.7;
            const spotY = cy + Math.sin(angle) * dist * 0.5;
            const spotRadius = radius * 0.08 + (Math.abs(hash >> (i * 5)) % 10) / 100 * radius;

            ctx.fillStyle = `rgba(0, 0, 0, 0.15)`;
            ctx.beginPath();
            ctx.ellipse(spotX, spotY, spotRadius, spotRadius * 0.7, angle, 0, Math.PI * 2);
            ctx.fill();
        }

        ctx.restore();
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
