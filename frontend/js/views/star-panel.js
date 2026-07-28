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

    // Infrastructure costs (server-authoritative values mirrored for
    // completion estimates; ship costs come from GameState.designs)
    infraCosts: {
        FACTORY: { ironium: 0, boranium: 0, germanium: 4, resources: 10 },
        MINE: { ironium: 0, boranium: 0, germanium: 0, resources: 5 },
        DEFENSE: { ironium: 5, boranium: 5, germanium: 5, resources: 15 },
        // Per point; 70 for Total Terraforming races (set in
        // showProductionDialog)
        TERRAFORM: { ironium: 0, boranium: 0, germanium: 0, resources: 100 }
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
        GameState.on('stateRefreshed', () => this.refresh());
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
        const isOwned = star.intel === 'owned';

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

        // Mass driver fling button (owned stars with a driver)
        document.getElementById('btn-fling-packet')
            ?.addEventListener('click', () => this.showFlingDialog());
    },

    /**
     * Calculate habitability value for display.
     * Returns percentage from -45 to 100.
     */
    calculateHabitability(star) {
        // Use server-computed value when available
        if (star.habitability !== undefined && star.habitability !== null) {
            return Math.round(star.habitability);
        }
        if (star.intel === 'unknown') {
            return 0;
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
     * Render the procedural planet graphic. PlanetArt (planet-art.js)
     * owns the pixels; the panel keeps the canvas sizing, and the
     * gravity-based radius lives in the renderer.
     */
    renderPlanetGraphic(star) {
        this.planetCanvas = document.getElementById('planet-canvas');
        if (!this.planetCanvas) return;

        this.planetCtx = this.planetCanvas.getContext('2d');
        PlanetArt.render(this.planetCanvas, star);
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
                    <span class="stat-value">${Dialogs.formatNumber(star.colonists)}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill population" style="width: ${popPercent}%"></div>
                </div>
                <div class="stat-row">
                    <span>Capacity:</span>
                    <span class="stat-value">${Dialogs.formatNumber(maxPop)}</span>
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
                    <span class="stat-value">${star.defenses || 0} (${star.defense_type || 'None'}, ${star.defense_coverage || 0}%)</span>
                </div>
                <div class="stat-row">
                    <span>Scanner:</span>
                    <span class="stat-value">${star.scanner_type || 'None'} (${star.scan_range || 0} ly)</span>
                </div>
                ${isOwned ? `
                <div class="stat-row">
                    <span>Mass Driver:</span>
                    <span class="stat-value">${star.mass_driver ? 'Warp ' + star.mass_driver : 'None'}</span>
                </div>` : ''}
                ${isOwned && star.mass_driver ? `
                <div class="production-buttons">
                    <button class="btn-small" id="btn-fling-packet">Fling Mineral Packet</button>
                </div>` : ''}
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
                <span class="resource-value">${Dialogs.formatNumber(amount)}</span>
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
        const ptype = item.production_type || '';
        if (ptype === 'ALCHEMY') {
            // Race-dependent: 25 resources with the MA LRT, else 100
            const hasMA = ((GameState.race || {}).traits || []).includes('MA');
            return { ironium: 0, boranium: 0, germanium: 0, resources: hasMA ? 25 : 100 };
        }
        if (this.infraCosts[ptype]) return this.infraCosts[ptype];
        // Ship or starbase - look up the design cost
        let key = item.design_key;
        if (typeof key === 'string') key = parseInt(key, 16);
        const design = (GameState.designs || []).find(d => d.key === key);
        if (design && design.cost) {
            return {
                ironium: design.cost.ironium || 0,
                boranium: design.cost.boranium || 0,
                germanium: design.cost.germanium || 0,
                resources: design.cost.energy || 0
            };
        }
        return { ironium: 0, boranium: 0, germanium: 0, resources: 20 };
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

        const currentYear = GameState.game ? GameState.game.turn : 2100;
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

                // Auto-build orders are skipped without blocking when
                // unaffordable and persist in the queue (server-side
                // ProductionOrder.IsAutoBuild semantics)
                const autoSuffix = item.is_auto_build
                    ? ' <span class="queue-auto">(Auto Build)</span>' : '';

                // Percent complete for partially built items. Web
                // adaptation of ProductionDialog.cs:823-846 whose
                // max-over-resources formula needs the per-resource
                // RemainingCost the web does not track - the web banks
                // resources (energy) only
                let percentText = '';
                const cost = this.getItemCost(item);
                if ((item.partial_resources_spent || 0) > 0 && cost.resources > 0) {
                    const pct = Math.round(
                        100 * item.partial_resources_spent / cost.resources);
                    percentText = `<span class="queue-percent">${pct}% done</span>`;
                }

                queueHtml += `
                    <li class="queue-item ${statusClass}">
                        <div class="queue-item-main">
                            <span class="queue-name">${item.name || item.type}${autoSuffix}</span>
                            <span class="queue-quantity">x${item.quantity}</span>
                            <span class="queue-item-buttons">
                                <button class="btn-small btn-queue-up" data-index="${i}" ${i === 0 ? 'disabled' : ''}>&#9650;</button>
                                <button class="btn-small btn-queue-down" data-index="${i}" ${i === queue.length - 1 ? 'disabled' : ''}>&#9660;</button>
                                <button class="btn-small btn-queue-remove" data-index="${i}">&#10005;</button>
                            </span>
                        </div>
                        <div class="queue-item-details">
                            ${completionText}
                            ${percentText}
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

        // Per-item reorder and remove buttons
        this.container.querySelectorAll('.btn-queue-up').forEach(btn => {
            btn.addEventListener('click', () => {
                const i = parseInt(btn.dataset.index);
                this.moveQueueItem(i, i - 1);
            });
        });
        this.container.querySelectorAll('.btn-queue-down').forEach(btn => {
            btn.addEventListener('click', () => {
                const i = parseInt(btn.dataset.index);
                this.moveQueueItem(i, i + 1);
            });
        });
        this.container.querySelectorAll('.btn-queue-remove').forEach(btn => {
            btn.addEventListener('click', () => {
                this.removeQueueItem(parseInt(btn.dataset.index));
            });
        });
    },

    /**
     * Move a queue item to a new position. The server performs the
     * move on its own state (single Move command) - a deviation from
     * C#, which swaps rows via two Edit commands carrying full
     * client-side orders (ProductionDialog.cs:365-406).
     */
    async moveQueueItem(index, toIndex) {
        if (!this.currentStar || !GameState.game) return;
        const queue = this.currentStar.production_queue || [];
        if (toIndex < 0 || toIndex >= queue.length) return;

        try {
            await GameState.submitCommand('production', {
                mode: 'Move',
                star_key: this.currentStar.name,
                index: index,
                to_index: toIndex
            });
            await GameState.refreshState();
            this.refresh();
        } catch (error) {
            ApiClient.showStatus('Failed to move item: ' + error.message, 'error');
        }
    },

    /**
     * Remove a queue item entirely.
     */
    async removeQueueItem(index) {
        if (!this.currentStar || !GameState.game) return;

        try {
            await GameState.submitCommand('production', {
                mode: 'Delete',
                star_key: this.currentStar.name,
                index: index
            });
            await GameState.refreshState();
            this.refresh();
        } catch (error) {
            ApiClient.showStatus('Failed to remove item: ' + error.message, 'error');
        }
    },

    /**
     * Show production dialog.
     */
    async showProductionDialog(event) {
        // Calculate default quantity based on modifier keys
        let defaultQuantity = 1;
        if (event && event.shiftKey && event.ctrlKey) {
            defaultQuantity = 1000;
        } else if (event && event.ctrlKey) {
            defaultQuantity = 100;
        } else if (event && event.shiftKey) {
            defaultQuantity = 10;
        }

        // Buildable items: infrastructure + own ship designs
        const items = [
            { label: 'Factory (4 Ge, 10 res)', production_type: 'FACTORY', name: 'Factory' },
            { label: 'Mine (5 res)', production_type: 'MINE', name: 'Mine' },
            { label: 'Defense (5 Ir, 5 Bo, 5 Ge, 15 res)', production_type: 'DEFENSE', name: 'Defense' }
        ];
        // Alchemy: 100 resources -> 1 kT of each mineral, 25 with the
        // Mineral Alchemy LRT (server-authoritative values mirrored)
        const alchemyCost = ((GameState.race || {}).traits || []).includes('MA') ? 25 : 100;
        items.push({
            label: `Alchemy (${alchemyCost} res, +1 kT each mineral)`,
            production_type: 'ALCHEMY', name: 'Alchemy'
        });
        // Auto-build variants: skipped without blocking the queue when
        // unbuildable, persist until their quantity completes.
        // "(Auto Build)" naming is canonical Stars!; Nova C# provides
        // only the engine flag (ProductionOrder.IsAutoBuild), no
        // creation UI for auto orders
        items.push(
            { label: 'Factory (Auto Build)', production_type: 'FACTORY',
              name: 'Factory', is_auto_build: true },
            { label: 'Mine (Auto Build)', production_type: 'MINE',
              name: 'Mine', is_auto_build: true },
            { label: 'Defense (Auto Build)', production_type: 'DEFENSE',
              name: 'Defense', is_auto_build: true },
            { label: 'Alchemy (Auto Build)', production_type: 'ALCHEMY',
              name: 'Alchemy', is_auto_build: true }
        );
        // Terraform: offered when the race can use any terraform
        // component - TT races always can (Total ±3 has no tech
        // requirement), others need Bio 1 plus Prop/Energy/Weapons 1
        // (the dedicated ±3 components in components.xml)
        const isTT = ((GameState.race || {}).traits || []).includes('TT');
        const levels = (GameState.research || {}).levels || {};
        const hasTerraformTech = isTT || (
            (levels.Biotechnology || 0) >= 1 && (
                (levels.Propulsion || 0) >= 1 ||
                (levels.Energy || 0) >= 1 ||
                (levels.Weapons || 0) >= 1));
        if (hasTerraformTech) {
            const terraformCost = isTT ? 70 : 100;
            this.infraCosts.TERRAFORM.resources = terraformCost;
            items.push({
                label: `Terraform (${terraformCost} res)`,
                production_type: 'TERRAFORM', name: 'Terraform'
            });
        }
        for (const design of (GameState.designs || [])) {
            if (design.obsolete) continue;
            const c = design.cost || {};
            const ptype = design.is_starbase ? 'STARBASE' : 'SHIP';
            items.push({
                label: `${design.name} (${c.ironium || 0} Ir, ${c.boranium || 0} Bo, ` +
                       `${c.germanium || 0} Ge, ${c.energy || 0} res)`,
                production_type: ptype,
                name: design.name,
                design_key: design.key
            });
        }

        const choiceIdx = await Dialogs.selectOption(
            'Add to Production Queue',
            'Select an item to build:',
            items.map(i => i.label)
        );
        if (choiceIdx === null || choiceIdx === undefined) return;
        const item = items[choiceIdx];

        const quantityStr = await Dialogs.promptText(
            'Quantity', `How many ${item.name}s to build?`, defaultQuantity.toString()
        );
        if (quantityStr === null) return;
        const quantity = parseInt(quantityStr) || 1;

        this.addToProductionQueue(item, quantity);
    },

    /**
     * Add item to production queue.
     */
    async addToProductionQueue(item, quantity) {
        if (!this.currentStar || !GameState.game) return;

        try {
            const queueLength = (this.currentStar.production_queue || []).length;
            const order = {
                production_type: item.production_type,
                quantity: quantity,
                name: item.name,
                is_auto_build: !!item.is_auto_build
            };
            if (item.design_key !== undefined) {
                order.design_key = '0x' + item.design_key.toString(16);
            }
            await GameState.submitCommand('production', {
                mode: 'Add',
                star_key: this.currentStar.name,
                index: queueLength,
                production_order: order
            });
            await GameState.refreshState();
            this.refresh();
            ApiClient.showStatus(`Queued ${quantity} x ${item.name}`, 'info');
        } catch (error) {
            ApiClient.showStatus('Failed to add to queue: ' + error.message, 'error');
        }
    },

    /**
     * Show the mineral packet fling dialog (canonical mass driver
     * rules: fling at the driver's rating up to 3 warp over, capped
     * at warp 13; overflinging decays the packet 10/25/50% per year).
     */
    showFlingDialog() {
        const star = this.currentStar;
        if (!star || !star.mass_driver || !GameState.game) return;

        const rating = star.mass_driver;
        const maxWarp = Math.min(rating + 3, 13);
        const decayPct = [0, 10, 25, 50];

        const targetOptions = (GameState.stars || [])
            .filter(s => s.name !== star.name)
            .map(s => s.name)
            .sort()
            .map(name => `<option value="${name}">${name}</option>`)
            .join('');
        let warpOptions = '';
        for (let w = rating; w <= maxWarp; w++) {
            const note = w === rating
                ? 'safe' : `decay ${decayPct[w - rating]}%/yr`;
            warpOptions += `<option value="${w}">Warp ${w} (${note})</option>`;
        }
        const mineralInput = (id, label, max) => `
            <div class="form-group">
                <label for="${id}">${label} (max ${max})</label>
                <input type="number" id="${id}" class="form-input"
                       value="0" min="0" max="${max}">
            </div>`;

        const html = `
            <div class="dialog-header">
                <h2>Fling Mineral Packet</h2>
                <button class="btn-close" onclick="Dialogs.close()">X</button>
            </div>
            <div class="dialog-body">
                <p class="info-text">Mass driver at ${star.name}
                (warp ${rating}). Packets fly at warp&sup2; ly per year
                straight at the target; a weaker or missing receiving
                driver means impact damage.</p>
                <div class="form-group">
                    <label for="fling-target">Target star</label>
                    <select id="fling-target" class="form-select">
                        ${targetOptions}
                    </select>
                </div>
                <div class="form-group">
                    <label for="fling-warp">Fling warp</label>
                    <select id="fling-warp" class="form-select">
                        ${warpOptions}
                    </select>
                </div>
                ${mineralInput('fling-ironium', 'Ironium (kT)', star.ironium || 0)}
                ${mineralInput('fling-boranium', 'Boranium (kT)', star.boranium || 0)}
                ${mineralInput('fling-germanium', 'Germanium (kT)', star.germanium || 0)}
            </div>
            <div class="dialog-footer">
                <button class="btn-primary" id="btn-fling-send">Fling</button>
                <button class="btn-secondary" onclick="Dialogs.close()">Cancel</button>
            </div>
        `;
        Dialogs.show(html);

        document.getElementById('btn-fling-send')
            ?.addEventListener('click', async () => {
                const amount = id =>
                    parseInt(document.getElementById(id).value) || 0;
                const data = {
                    star: star.name,
                    target: document.getElementById('fling-target').value,
                    warp: parseInt(document.getElementById('fling-warp').value),
                    ironium: amount('fling-ironium'),
                    boranium: amount('fling-boranium'),
                    germanium: amount('fling-germanium')
                };
                const result = await ApiClient.flingPacket(
                    GameState.game.id, GameState.empireId, data);
                if (result.status === 'error') {
                    ApiClient.showStatus(
                        'Fling failed: ' + (result.error || 'rejected'),
                        'error');
                    return;
                }
                Dialogs.close();
                await GameState.refreshState();
                ApiClient.showStatus('Mineral packet flung', 'info');
            });
    },

    /**
     * Clear production queue.
     */
    async clearProductionQueue() {
        if (!this.currentStar || !GameState.game) return;

        const confirmed = await Dialogs.confirm('Clear Queue', 'Clear the production queue?');
        if (!confirmed) return;

        try {
            const queue = this.currentStar.production_queue || [];
            // Delete entries back to front so indices stay valid
            for (let i = queue.length - 1; i >= 0; i--) {
                await GameState.submitCommand('production', {
                    mode: 'Delete',
                    star_key: this.currentStar.name,
                    index: i
                });
            }
            await GameState.refreshState();
            this.refresh();
        } catch (error) {
            ApiClient.showStatus('Failed to clear queue: ' + error.message, 'error');
        }
    }
};

// Export
window.StarPanel = StarPanel;
