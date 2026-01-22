/**
 * Stars Nova Web - Battle Viewer
 * Replays combat sequences from battle reports.
 * Ported from original Stars! visual style.
 */

const BattleViewer = {
    // DOM elements
    container: null,
    canvas: null,
    ctx: null,

    // Battle data
    battleReport: null,
    battleSteps: [],
    currentStep: 0,

    // Playback state
    isPlaying: false,
    playbackSpeed: 1.0,
    playbackTimer: null,

    // Visual settings
    gridSize: 10,
    cellSize: 40,
    canvasWidth: 400,
    canvasHeight: 400,

    // Colors
    colors: {
        background: '#050510',
        grid: '#101030',
        friendlyShip: '#00ff00',
        enemyShip: '#ff0000',
        friendlyMissile: '#00ffff',
        enemyMissile: '#ff8800',
        explosion: '#ffff00',
        shield: '#4040ff',
        text: '#c0c0c0'
    },

    /**
     * Initialize the battle viewer.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Battle viewer container not found:', containerId);
            return;
        }

        this.render();
        console.log('Battle viewer initialized');
    },

    /**
     * Show battle viewer with a battle report.
     */
    show(battleReport) {
        if (!this.container) return;

        this.battleReport = battleReport;
        this.battleSteps = battleReport?.steps || [];
        this.currentStep = 0;
        this.isPlaying = false;

        this.container.classList.remove('hidden');
        this.render();
        this.renderBattle();
    },

    /**
     * Hide the battle viewer.
     */
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
        this.stop();
        this.battleReport = null;
    },

    /**
     * Render the viewer UI.
     */
    render() {
        if (!this.container) return;

        const html = `
            <div class="battle-viewer-header">
                <h2>Battle Viewer</h2>
                <button class="btn-close" id="btn-close-battle">X</button>
            </div>

            <div class="battle-viewer-content">
                <canvas id="battle-canvas" width="${this.canvasWidth}" height="${this.canvasHeight}"></canvas>

                <div class="battle-info">
                    <div class="battle-participants">
                        <h3>Combatants</h3>
                        <div id="battle-combatants"></div>
                    </div>

                    <div class="battle-log">
                        <h3>Battle Log</h3>
                        <div id="battle-log-content"></div>
                    </div>
                </div>
            </div>

            <div class="battle-viewer-controls">
                <button class="btn-small" id="btn-battle-start">|&lt;</button>
                <button class="btn-small" id="btn-battle-prev">&lt;</button>
                <button class="btn-small" id="btn-battle-play">Play</button>
                <button class="btn-small" id="btn-battle-next">&gt;</button>
                <button class="btn-small" id="btn-battle-end">&gt;|</button>

                <span class="step-indicator">
                    Step: <span id="current-step">0</span> / <span id="total-steps">0</span>
                </span>

                <select id="playback-speed" class="speed-select">
                    <option value="0.5">0.5x</option>
                    <option value="1" selected>1x</option>
                    <option value="2">2x</option>
                    <option value="4">4x</option>
                </select>
            </div>
        `;

        this.container.innerHTML = html;

        // Get canvas
        this.canvas = document.getElementById('battle-canvas');
        this.ctx = this.canvas?.getContext('2d');

        this.bindEvents();
    },

    /**
     * Bind event handlers.
     */
    bindEvents() {
        const closeBtn = document.getElementById('btn-close-battle');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }

        const startBtn = document.getElementById('btn-battle-start');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.goToStart());
        }

        const prevBtn = document.getElementById('btn-battle-prev');
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.prevStep());
        }

        const playBtn = document.getElementById('btn-battle-play');
        if (playBtn) {
            playBtn.addEventListener('click', () => this.togglePlay());
        }

        const nextBtn = document.getElementById('btn-battle-next');
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextStep());
        }

        const endBtn = document.getElementById('btn-battle-end');
        if (endBtn) {
            endBtn.addEventListener('click', () => this.goToEnd());
        }

        const speedSelect = document.getElementById('playback-speed');
        if (speedSelect) {
            speedSelect.addEventListener('change', (e) => {
                this.playbackSpeed = parseFloat(e.target.value);
            });
        }
    },

    /**
     * Render the battle at current step.
     */
    renderBattle() {
        if (!this.ctx) return;

        const ctx = this.ctx;
        const w = this.canvasWidth;
        const h = this.canvasHeight;

        // Clear
        ctx.fillStyle = this.colors.background;
        ctx.fillRect(0, 0, w, h);

        // Draw grid
        this.renderGrid();

        // Get current step data
        const step = this.battleSteps[this.currentStep];
        if (step) {
            this.renderStep(step);
        }

        // Update UI
        this.updateUI();
    },

    /**
     * Render battle grid.
     */
    renderGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = this.colors.grid;
        ctx.lineWidth = 1;

        for (let x = 0; x <= this.gridSize; x++) {
            const px = x * this.cellSize;
            ctx.beginPath();
            ctx.moveTo(px, 0);
            ctx.lineTo(px, this.canvasHeight);
            ctx.stroke();
        }

        for (let y = 0; y <= this.gridSize; y++) {
            const py = y * this.cellSize;
            ctx.beginPath();
            ctx.moveTo(0, py);
            ctx.lineTo(this.canvasWidth, py);
            ctx.stroke();
        }
    },

    /**
     * Render a battle step.
     */
    renderStep(step) {
        const ctx = this.ctx;

        // Render stacks/ships
        if (step.stacks) {
            for (const stack of step.stacks) {
                this.renderStack(stack);
            }
        }

        // Render weapons fire
        if (step.weapons) {
            for (const weapon of step.weapons) {
                this.renderWeaponFire(weapon);
            }
        }

        // Render explosions
        if (step.destroyed) {
            for (const destroyed of step.destroyed) {
                this.renderExplosion(destroyed);
            }
        }
    },

    /**
     * Render a stack (group of ships).
     */
    renderStack(stack) {
        const ctx = this.ctx;
        const x = stack.x * this.cellSize + this.cellSize / 2;
        const y = stack.y * this.cellSize + this.cellSize / 2;
        const radius = 12;

        // Determine color based on owner
        const color = stack.owner === 1 ? this.colors.friendlyShip : this.colors.enemyShip;

        // Draw ship
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();

        // Draw shield if present
        if (stack.shields > 0) {
            ctx.strokeStyle = this.colors.shield;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw quantity
        if (stack.quantity > 1) {
            ctx.fillStyle = this.colors.text;
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`x${stack.quantity}`, x, y + radius + 12);
        }
    },

    /**
     * Render weapon fire.
     */
    renderWeaponFire(weapon) {
        const ctx = this.ctx;
        const fromX = weapon.from_x * this.cellSize + this.cellSize / 2;
        const fromY = weapon.from_y * this.cellSize + this.cellSize / 2;
        const toX = weapon.to_x * this.cellSize + this.cellSize / 2;
        const toY = weapon.to_y * this.cellSize + this.cellSize / 2;

        // Determine color based on attacker
        const color = weapon.attacker_owner === 1
            ? this.colors.friendlyMissile
            : this.colors.enemyMissile;

        // Draw weapon line
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(fromX, fromY);
        ctx.lineTo(toX, toY);
        ctx.stroke();

        // Draw damage number if hit
        if (weapon.damage > 0) {
            ctx.fillStyle = this.colors.explosion;
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`-${weapon.damage}`, toX, toY - 15);
        }
    },

    /**
     * Render explosion effect.
     */
    renderExplosion(destroyed) {
        const ctx = this.ctx;
        const x = destroyed.x * this.cellSize + this.cellSize / 2;
        const y = destroyed.y * this.cellSize + this.cellSize / 2;

        // Draw explosion
        ctx.fillStyle = this.colors.explosion;
        ctx.beginPath();
        ctx.arc(x, y, 20, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#ff8800';
        ctx.beginPath();
        ctx.arc(x, y, 12, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fill();
    },

    /**
     * Update UI elements.
     */
    updateUI() {
        const currentEl = document.getElementById('current-step');
        const totalEl = document.getElementById('total-steps');
        const playBtn = document.getElementById('btn-battle-play');

        if (currentEl) currentEl.textContent = this.currentStep + 1;
        if (totalEl) totalEl.textContent = this.battleSteps.length;
        if (playBtn) playBtn.textContent = this.isPlaying ? 'Pause' : 'Play';

        // Update combatants
        this.updateCombatants();

        // Update log
        this.updateLog();
    },

    /**
     * Update combatants panel.
     */
    updateCombatants() {
        const container = document.getElementById('battle-combatants');
        if (!container || !this.battleReport) return;

        const combatants = this.battleReport.combatants || [];

        let html = '';
        for (const combatant of combatants) {
            const colorClass = combatant.owner === 1 ? 'friendly' : 'enemy';
            html += `
                <div class="combatant ${colorClass}">
                    <span class="combatant-name">${combatant.name}</span>
                    <span class="combatant-ships">${combatant.ships} ships</span>
                </div>
            `;
        }

        container.innerHTML = html || '<p>No combatants.</p>';
    },

    /**
     * Update battle log.
     */
    updateLog() {
        const container = document.getElementById('battle-log-content');
        if (!container) return;

        // Show log entries up to current step
        const entries = [];
        for (let i = 0; i <= this.currentStep && i < this.battleSteps.length; i++) {
            const step = this.battleSteps[i];
            if (step.log) {
                entries.push(`<div class="log-entry">[${i + 1}] ${step.log}</div>`);
            }
        }

        container.innerHTML = entries.join('') || '<p>No events.</p>';
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Playback controls.
     */
    goToStart() {
        this.stop();
        this.currentStep = 0;
        this.renderBattle();
    },

    goToEnd() {
        this.stop();
        this.currentStep = Math.max(0, this.battleSteps.length - 1);
        this.renderBattle();
    },

    prevStep() {
        this.stop();
        if (this.currentStep > 0) {
            this.currentStep--;
            this.renderBattle();
        }
    },

    nextStep() {
        if (this.currentStep < this.battleSteps.length - 1) {
            this.currentStep++;
            this.renderBattle();
            return true;
        }
        return false;
    },

    togglePlay() {
        if (this.isPlaying) {
            this.stop();
        } else {
            this.play();
        }
    },

    play() {
        if (this.currentStep >= this.battleSteps.length - 1) {
            this.currentStep = 0;
        }

        this.isPlaying = true;
        this.playbackTimer = setInterval(() => {
            if (!this.nextStep()) {
                this.stop();
            }
        }, 500 / this.playbackSpeed);

        this.updateUI();
    },

    stop() {
        this.isPlaying = false;
        if (this.playbackTimer) {
            clearInterval(this.playbackTimer);
            this.playbackTimer = null;
        }
        this.updateUI();
    },

    /**
     * Load and show a battle report from the API.
     */
    async loadBattle(battleId) {
        try {
            const report = await ApiClient.request('GET',
                `/games/${GameState.game.id}/battles/${battleId}`
            );
            this.show(report);
        } catch (error) {
            alert('Failed to load battle: ' + error.message);
        }
    }
};

// Export
window.BattleViewer = BattleViewer;
