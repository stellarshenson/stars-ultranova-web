/**
 * Stars Nova Web - Message Panel
 * Displays turn messages with navigation controls.
 * Ported from original Stars! visual style.
 */

const MessagePanel = {
    // DOM elements
    container: null,

    // Messages state
    messages: [],
    currentIndex: 0,
    isCollapsed: false,

    // Message types with colors
    messageTypes: {
        info: { color: '#7cb3ff', icon: 'i' },
        warning: { color: '#ffaa00', icon: '!' },
        research: { color: '#cc66ff', icon: 'R' },
        combat: { color: '#ff4444', icon: 'X' },
        colonization: { color: '#44ff44', icon: 'C' },
        production: { color: '#ffff44', icon: 'P' },
        default: { color: '#888888', icon: '*' }
    },

    /**
     * Initialize the message panel.
     */
    init(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error('Message panel container not found:', containerId);
            return;
        }

        // Listen to game state changes
        GameState.on('gameLoaded', () => this.loadMessages());
        GameState.on('gameCreated', () => this.loadMessages());
        GameState.on('turnGenerated', () => this.loadMessages());

        // Initial render
        this.render();

        console.log('Message panel initialized');
    },

    /**
     * Load messages from game state.
     */
    loadMessages() {
        if (!GameState.game) {
            this.messages = [];
            this.currentIndex = 0;
            this.hide();
            return;
        }

        // Get messages from game state
        this.messages = GameState.game.messages || [];

        // Also include any events that occurred this turn
        if (GameState.game.turn_events) {
            this.messages = [...this.messages, ...GameState.game.turn_events];
        }

        // Reset to first message if we have new messages
        if (this.messages.length > 0) {
            this.currentIndex = 0;
            this.show();
        } else {
            this.hide();
        }

        this.render();
    },

    /**
     * Show the panel.
     */
    show() {
        if (this.container) {
            this.container.classList.remove('hidden');
        }
    },

    /**
     * Hide the panel.
     */
    hide() {
        if (this.container) {
            this.container.classList.add('hidden');
        }
    },

    /**
     * Toggle collapsed state.
     */
    toggle() {
        this.isCollapsed = !this.isCollapsed;
        this.render();
    },

    /**
     * Go to previous message.
     */
    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.render();
        }
    },

    /**
     * Go to next message.
     */
    next() {
        if (this.currentIndex < this.messages.length - 1) {
            this.currentIndex++;
            this.render();
        }
    },

    /**
     * Go to first message.
     */
    first() {
        this.currentIndex = 0;
        this.render();
    },

    /**
     * Go to last message.
     */
    last() {
        this.currentIndex = Math.max(0, this.messages.length - 1);
        this.render();
    },

    /**
     * Render the panel.
     */
    render() {
        if (!this.container) return;

        const year = GameState.game ? GameState.game.turn + 2400 : 2400;
        const msgCount = this.messages.length;
        const currentNum = msgCount > 0 ? this.currentIndex + 1 : 0;

        if (this.isCollapsed) {
            this.container.innerHTML = `
                <div class="message-panel-collapsed" onclick="MessagePanel.toggle()">
                    <span class="message-panel-title">Messages: ${currentNum} of ${msgCount}</span>
                    <span class="message-panel-expand">+</span>
                </div>
            `;
            return;
        }

        const currentMessage = this.messages[this.currentIndex];
        const messageType = currentMessage ? (currentMessage.type || 'default') : 'default';
        const typeConfig = this.messageTypes[messageType] || this.messageTypes.default;

        let messageHtml = '';
        if (currentMessage) {
            messageHtml = `
                <div class="message-content" style="border-left-color: ${typeConfig.color}">
                    <span class="message-type-icon" style="background-color: ${typeConfig.color}">${typeConfig.icon}</span>
                    <div class="message-text">
                        ${currentMessage.text || currentMessage.message || 'No message content'}
                    </div>
                    ${currentMessage.details ? `<div class="message-details">${currentMessage.details}</div>` : ''}
                </div>
            `;
        } else {
            messageHtml = `
                <div class="message-content message-empty">
                    <span class="message-text">No messages this turn</span>
                </div>
            `;
        }

        this.container.innerHTML = `
            <div class="message-panel-header">
                <span class="message-panel-title">Year ${year} - Messages: ${currentNum} of ${msgCount}</span>
                <button class="message-panel-collapse" onclick="MessagePanel.toggle()">-</button>
            </div>

            ${messageHtml}

            <div class="message-panel-nav">
                <button class="btn-small" onclick="MessagePanel.first()" ${currentNum <= 1 ? 'disabled' : ''}>|&lt;</button>
                <button class="btn-small" onclick="MessagePanel.prev()" ${currentNum <= 1 ? 'disabled' : ''}>&lt; Prev</button>
                <button class="btn-small" onclick="MessagePanel.next()" ${currentNum >= msgCount ? 'disabled' : ''}>Next &gt;</button>
                <button class="btn-small" onclick="MessagePanel.last()" ${currentNum >= msgCount ? 'disabled' : ''}>&gt;|</button>
                <button class="btn-small btn-goto" onclick="MessagePanel.showGotoDialog()">Goto...</button>
            </div>
        `;
    },

    /**
     * Show goto dialog for jumping to specific message.
     */
    showGotoDialog() {
        if (this.messages.length === 0) return;

        const target = prompt(`Go to message (1-${this.messages.length}):`, this.currentIndex + 1);
        if (target === null) return;

        const index = parseInt(target) - 1;
        if (index >= 0 && index < this.messages.length) {
            this.currentIndex = index;
            this.render();
        }
    },

    /**
     * Add a new message programmatically.
     */
    addMessage(type, text, details = null) {
        this.messages.push({ type, text, details, timestamp: Date.now() });
        this.currentIndex = this.messages.length - 1;
        this.show();
        this.render();
    }
};

// Export
window.MessagePanel = MessagePanel;
