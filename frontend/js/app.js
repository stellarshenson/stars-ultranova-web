/**
 * Stars Nova Web - Main Application
 * Initializes the application and handles UI interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    const App = {
        init() {
            this.bindEvents();
            this.setupGameState();
        },

        bindEvents() {
            // Menu buttons
            document.getElementById('menu-new-game')?.addEventListener('click', () => {
                this.showNewGameDialog();
            });

            document.getElementById('menu-continue')?.addEventListener('click', () => {
                this.showLoadGameDialog();
            });

            // Header buttons
            document.getElementById('btn-new-game')?.addEventListener('click', () => {
                this.showNewGameDialog();
            });

            document.getElementById('btn-load-game')?.addEventListener('click', () => {
                this.showLoadGameDialog();
            });
        },

        setupGameState() {
            GameState.on('gameCreated', (game) => {
                this.hideMenu();
                this.showGame();
                console.log('Game created:', game);
            });

            GameState.on('gameLoaded', (game) => {
                this.hideMenu();
                this.showGame();
                console.log('Game loaded:', game);
            });

            GameState.on('starSelected', (star) => {
                this.showStarPanel(star);
            });

            GameState.on('fleetSelected', (fleet) => {
                this.showFleetPanel(fleet);
            });

            GameState.on('turnGenerated', (turn) => {
                console.log('Turn generated:', turn);
            });
        },

        async showNewGameDialog() {
            const name = prompt('Enter game name:', 'New Game');
            if (!name) return;

            try {
                await GameState.createGame(name, 2, 'medium');
            } catch (error) {
                alert('Failed to create game: ' + error.message);
            }
        },

        async showLoadGameDialog() {
            try {
                const games = await ApiClient.listGames();
                if (games.length === 0) {
                    alert('No saved games found.');
                    return;
                }

                const gameList = games.map((g, i) => `${i + 1}. ${g.name} (Turn ${g.turn})`).join('\n');
                const choice = prompt(`Select a game:\n${gameList}\n\nEnter number:`);

                if (!choice) return;
                const index = parseInt(choice) - 1;

                if (index >= 0 && index < games.length) {
                    await GameState.loadGame(games[index].id);
                }
            } catch (error) {
                alert('Failed to load games: ' + error.message);
            }
        },

        hideMenu() {
            document.getElementById('menu-container')?.classList.add('hidden');
        },

        showMenu() {
            document.getElementById('menu-container')?.classList.remove('hidden');
        },

        showGame() {
            document.getElementById('game-container')?.classList.remove('hidden');
        },

        showStarPanel(star) {
            const panel = document.getElementById('star-panel');
            const info = document.getElementById('star-info');

            if (!panel || !info || !star) return;

            document.getElementById('fleet-panel')?.classList.add('hidden');
            panel.classList.remove('hidden');

            info.innerHTML = `
                <p><strong>Name:</strong> ${star.name}</p>
                <p><strong>Position:</strong> (${star.position_x}, ${star.position_y})</p>
                <p><strong>Colonists:</strong> ${star.colonists.toLocaleString()}</p>
                <p><strong>Factories:</strong> ${star.factories}</p>
                <p><strong>Mines:</strong> ${star.mines}</p>
            `;
        },

        showFleetPanel(fleet) {
            const panel = document.getElementById('fleet-panel');
            const info = document.getElementById('fleet-info');

            if (!panel || !info || !fleet) return;

            document.getElementById('star-panel')?.classList.add('hidden');
            panel.classList.remove('hidden');

            info.innerHTML = `
                <p><strong>Name:</strong> ${fleet.name}</p>
                <p><strong>Position:</strong> (${fleet.position_x}, ${fleet.position_y})</p>
                <p><strong>Fuel:</strong> ${Math.round(fleet.fuel_available)} mg</p>
                <p><strong>Cargo:</strong> ${fleet.cargo_mass} kT</p>
            `;
        }
    };

    App.init();
});
