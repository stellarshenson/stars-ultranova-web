/**
 * Stars Nova Web - Battle Viewer
 * Replays combat sequences from server battle reports.
 * Ported from original Stars! visual style.
 *
 * Report format (backend/server/battle/battle_report.py):
 *   { location, space_size, grid_size, year, steps, stacks, losses }
 * Step types (backend/server/battle/battle_step.py):
 *   Movement { stack_key, position:{x,y} }
 *   Target   { stack_key, target_key, percent_to_fire, priority,
 *              target_role }
 *   Weapons  { weapon_target:{stack_key, target_key}, damage, targeting }
 *   Withdraw { stack_key }
 *   Board    { stack_key, target_key, chance, success, design_name }
 *   Destroy  { stack_key }
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
    gridScale: 1,
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
    },

    /**
     * Fetch the empire's battle reports from the last generated turn.
     */
    async loadBattles() {
        return ApiClient.request('GET',
            `/games/${GameState.game.id}/empires/${GameState.empireId}/battles`
        );
    },

    /**
     * Load battle reports and show the list (or the single report).
     */
    async showBattleList() {
        let battles;
        try {
            battles = await this.loadBattles();
        } catch (error) {
            // ApiClient.request already surfaced the error status
            return;
        }

        if (!battles || battles.length === 0) {
            ApiClient.showStatus('No battles were fought last turn', 'info');
            return;
        }

        if (battles.length === 1) {
            this.show(battles[0]);
            return;
        }

        const labels = battles.map(b => {
            const stackCount = Object.keys(b.stacks || {}).length;
            return `${b.year} - Battle at ${b.location} (${stackCount} stacks)`;
        });

        const index = await Dialogs.selectOption(
            'Battle Reports', 'Select a battle to view', labels
        );
        if (index === null || index === undefined) return;

        this.show(battles[index]);
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

        // The report's grid_size is the number of position units per
        // board square (RonBattleEngine.GRID_SCALE = 100 over a 0-1000
        // board), not a count of squares - the board is the canonical
        // 10 x 10 regardless
        this.gridScale = battleReport?.grid_size || 1;
        this.gridSize = 10;
        this.cellSize = this.canvasWidth / this.gridSize;

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

        const title = this.battleReport
            ? `Battle at ${this.battleReport.location} - ${this.battleReport.year}`
            : 'Battle Viewer';

        const html = `
            <div class="battle-viewer-header">
                <h2>${title}</h2>
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
     * Get a stack record from the report by key.
     */
    getStack(key) {
        if (!this.battleReport || !this.battleReport.stacks) return null;
        return this.battleReport.stacks[String(key)] || this.battleReport.stacks[key] || null;
    },

    /**
     * Human-readable stack name.
     */
    stackName(key) {
        const stack = this.getStack(key);
        if (!stack) return `Stack ${key}`;
        return stack.name || stack.token?.design_name || `Stack ${key}`;
    },

    /**
     * Build playback state by applying steps up to the current index.
     *
     * Returns:
     *   positions  - stack key -> {x, y} (start positions + Movement steps)
     *   removed    - set of stack keys destroyed BEFORE the current step
     *   explosions - stack keys destroyed AT the current step
     *   fires      - weapon fire happening AT the current step
     */
    computePlaybackState() {
        const positions = {};
        const removed = new Set();
        const explosions = [];
        const fires = [];

        const stacks = this.battleReport?.stacks || {};
        for (const [key, stack] of Object.entries(stacks)) {
            positions[key] = {
                x: stack.position?.x || 0,
                y: stack.position?.y || 0
            };
        }

        for (let i = 0; i <= this.currentStep && i < this.battleSteps.length; i++) {
            const step = this.battleSteps[i];
            if (!step) continue;

            if (step.type === 'Movement') {
                positions[String(step.stack_key)] = {
                    x: step.position?.x || 0,
                    y: step.position?.y || 0
                };
            } else if (step.type === 'Destroy') {
                if (i < this.currentStep) {
                    removed.add(String(step.stack_key));
                } else {
                    explosions.push(String(step.stack_key));
                }
            } else if (step.type === 'Weapons' && i === this.currentStep) {
                const wt = step.weapon_target || {};
                fires.push({
                    attackerKey: String(wt.stack_key),
                    targetKey: String(wt.target_key),
                    damage: step.damage || 0
                });
            }
        }

        return { positions, removed, explosions, fires };
    },

    /**
     * Render the battle at current step.
     */
    renderBattle() {
        if (!this.ctx) return;

        const ctx = this.ctx;

        // Clear
        ctx.fillStyle = this.colors.background;
        ctx.fillRect(0, 0, this.canvasWidth, this.canvasHeight);

        // Draw grid
        this.renderGrid();

        if (this.battleReport) {
            const state = this.computePlaybackState();

            // Stacks still alive (destroyed-this-step drawn as explosion)
            for (const [key, stack] of Object.entries(this.battleReport.stacks || {})) {
                if (state.removed.has(key) || state.explosions.includes(key)) continue;
                this.renderStack(stack, state.positions[key]);
            }

            // Weapon fire for the current step
            for (const fire of state.fires) {
                this.renderWeaponFire(fire, state.positions);
            }

            // Explosions for stacks destroyed this step
            for (const key of state.explosions) {
                this.renderExplosion(state.positions[key]);
            }
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
     * Canvas pixel position of a board position.
     *
     * Stack and Movement positions are in grid units - gridScale units
     * per board square - so divide by the scale before scaling to
     * pixels. They are points on the board rather than cell indices,
     * so no half-cell offset applies.
     */
    cellCenter(pos) {
        return {
            x: (pos.x / this.gridScale) * this.cellSize,
            y: (pos.y / this.gridScale) * this.cellSize
        };
    },

    /**
     * Render a stack (group of ships).
     * Friendly stacks are green triangles, enemy stacks red squares.
     */
    renderStack(stack, pos) {
        if (!pos) return;
        const ctx = this.ctx;
        const { x, y } = this.cellCenter(pos);
        const size = 10;

        const friendly = stack.owner === GameState.empireId;
        ctx.fillStyle = friendly ? this.colors.friendlyShip : this.colors.enemyShip;

        if (friendly) {
            // Triangle pointing up
            ctx.beginPath();
            ctx.moveTo(x, y - size);
            ctx.lineTo(x - size, y + size);
            ctx.lineTo(x + size, y + size);
            ctx.closePath();
            ctx.fill();
        } else {
            // Square
            ctx.fillRect(x - size, y - size, size * 2, size * 2);
        }

        // Shield ring if the stack still has shields
        const shields = stack.token?.shields || 0;
        if (shields > 0) {
            ctx.strokeStyle = this.colors.shield;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, size + 5, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Quantity + design name label
        const quantity = stack.token?.quantity || 1;
        const designName = stack.token?.design_name || stack.name || '';
        ctx.fillStyle = this.colors.text;
        ctx.font = '9px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${quantity}x ${designName}`, x, y + size + 10);
    },

    /**
     * Render weapon fire as a line from attacker to target with damage text.
     */
    renderWeaponFire(fire, positions) {
        const fromPos = positions[fire.attackerKey];
        const toPos = positions[fire.targetKey];
        if (!fromPos || !toPos) return;

        const ctx = this.ctx;
        const from = this.cellCenter(fromPos);
        const to = this.cellCenter(toPos);

        const attacker = this.getStack(fire.attackerKey);
        const friendly = attacker && attacker.owner === GameState.empireId;
        const color = friendly ? this.colors.friendlyMissile : this.colors.enemyMissile;

        // Draw weapon line
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();

        // Draw damage number if hit
        if (fire.damage > 0) {
            ctx.fillStyle = this.colors.explosion;
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`-${Math.round(fire.damage)}`, to.x, to.y - 15);
        }
    },

    /**
     * Render explosion effect at a grid cell.
     */
    renderExplosion(pos) {
        if (!pos) return;
        const ctx = this.ctx;
        const { x, y } = this.cellCenter(pos);

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

        if (currentEl) currentEl.textContent = this.battleSteps.length ? this.currentStep + 1 : 0;
        if (totalEl) totalEl.textContent = this.battleSteps.length;
        if (playBtn) playBtn.textContent = this.isPlaying ? 'Pause' : 'Play';

        // Update combatants
        this.updateCombatants();

        // Update log
        this.updateLog();
    },

    /**
     * Update combatants panel: stacks grouped by owning empire, each
     * stack's battle role and the plan it fought under, plus losses
     * once playback reaches the end.
     */
    updateCombatants() {
        const container = document.getElementById('battle-combatants');
        if (!container || !this.battleReport) return;

        const byOwner = {};
        for (const stack of Object.values(this.battleReport.stacks || {})) {
            const owner = stack.owner;
            if (!byOwner[owner]) {
                byOwner[owner] = { stacks: 0, ships: 0, roster: [] };
            }
            byOwner[owner].stacks++;
            byOwner[owner].ships += stack.token?.quantity || 1;
            byOwner[owner].roster.push({
                name: stack.token?.design_name || stack.name,
                quantity: stack.token?.quantity || 1,
                role: stack.battle_role || '',
                plan: stack.battle_plan || ''
            });
        }

        let html = '';
        for (const [owner, info] of Object.entries(byOwner)) {
            const colorClass = Number(owner) === GameState.empireId ? 'friendly' : 'enemy';
            const roster = info.roster.map(s => {
                const detail = [s.role, s.plan ? `plan: ${s.plan}` : null]
                    .filter(Boolean).join(' - ');
                return `<div class="combatant-stack">${s.quantity} x ${s.name}`
                    + (detail ? ` <span class="combatant-role">(${detail})</span>` : '')
                    + '</div>';
            }).join('');
            html += `
                <div class="combatant ${colorClass}">
                    <span class="combatant-name">Empire ${owner}</span>
                    <span class="combatant-ships">${info.stacks} stacks, ${info.ships} ships</span>
                    ${roster}
                </div>
            `;
        }

        // Show losses once the replay has reached the final step
        const atEnd = this.currentStep >= this.battleSteps.length - 1;
        const losses = this.battleReport.losses || {};
        if (atEnd && Object.keys(losses).length > 0) {
            html += '<h4>Losses</h4>';
            for (const [owner, count] of Object.entries(losses)) {
                html += `<div class="combatant-losses">Empire ${owner} lost ${count} ships</div>`;
            }
        }

        container.innerHTML = html || '<p>No combatants.</p>';
    },

    // Plan tier that picked a target, as recorded on Target steps
    // (backend/server/battle/battle_plan.py PRIORITY_TIER_LABELS)
    PRIORITY_TIER_LABELS: {
        7: 'Primary', 6: 'Secondary', 5: 'Tertiary',
        4: 'Quaternary', 3: 'Quinary'
    },

    /**
     * Describe a battle step for the log.
     */
    describeStep(step) {
        if (!step) return '';

        switch (step.type) {
            case 'Movement': {
                const pos = step.position || {};
                return `${this.stackName(step.stack_key)} moves to (${pos.x}, ${pos.y})`;
            }
            case 'Target': {
                // Why this target: the plan tier that matched and the
                // role it matched (backend battle_plan.PRIORITY_TIER_LABELS)
                const tier = this.PRIORITY_TIER_LABELS[step.priority];
                const why = [tier ? `${tier} target` : null, step.target_role]
                    .filter(Boolean).join(', ');
                return `${this.stackName(step.stack_key)} targets `
                    + `${this.stackName(step.target_key)}`
                    + (why ? ` [${why}]` : '')
                    + ` (${step.percent_to_fire}% fire)`;
            }
            case 'Weapons': {
                const wt = step.weapon_target || {};
                // targeting is TokenDefence: 0 = shields, 1 = armor
                const targeting = step.targeting === 1 || step.targeting === 'ARMOR'
                    ? 'armor' : 'shields';
                return `${this.stackName(wt.stack_key)} fires at `
                    + `${this.stackName(wt.target_key)} for `
                    + `${Math.round(step.damage || 0)} damage (${targeting})`;
            }
            case 'Withdraw':
                return `${this.stackName(step.stack_key)} withdraws from the battle`;
            case 'Board': {
                // A boarding gamble, with the odds it was taken at, so
                // a lost prize reads as a lost bet rather than a bug
                const odds = `${Math.round((step.chance || 0) * 100)}%`;
                const prize = step.design_name || this.stackName(step.target_key);
                return step.success
                    ? `${this.stackName(step.stack_key)} boards and CAPTURES `
                        + `${prize} (${odds} odds)`
                    : `${this.stackName(step.stack_key)} boards ${prize} and is `
                        + `REPELLED (${odds} odds) - boarding party lost, `
                        + `boarder crippled`;
            }
            case 'Destroy':
                return `${this.stackName(step.stack_key)} destroyed`;
            default:
                return step.type;
        }
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
            const text = this.describeStep(this.battleSteps[i]);
            if (text) {
                entries.push(`<div class="log-entry">[${i + 1}] ${text}</div>`);
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
    }
};

// Export
window.BattleViewer = BattleViewer;
