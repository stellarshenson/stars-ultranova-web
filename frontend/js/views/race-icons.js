/**
 * Stars Nova Web - Race Emblem Icons
 *
 * 16 designed SVG emblems for the race designer, race selector, empire
 * summary and reports (user directive, wave 5 - replaces the numbered
 * placeholder boxes). The C# RaceIcon.cs loads bitmap files from disk;
 * the web ships inline SVG keyed 0-15 plus support for a per-player
 * uploaded custom icon (base64 data URI stored with the race).
 *
 * Design language: dark emblem disc, silver linework with one accent
 * colour per sigil - classic sci-fi heraldry, readable at 24-64 px.
 */

const RaceIcons = {
    COUNT: 16,

    // Shared palette (matches the game's dark UI)
    DISC_FILL: '#0d1420',
    DISC_STROKE: '#2c3e52',
    SILVER: '#c7d3e0',

    // Emblem names (tooltips in the wizard grid)
    NAMES: [
        'Star Shield', 'Crescent Dominion', 'Mandible Swarm',
        'Crystal Facet', 'Comet Riders', 'Watchful Eye',
        'Trident Deep', 'Serpent Coil', 'Iron Cog',
        'Twin Pylons', 'Raptor Wing', 'Atomic Core',
        'Rune Gate', 'Triune Orbs', 'Crossed Sabers',
        'Void Crown'
    ],

    // Inner SVG markup per emblem (48x48 viewBox, disc added by svg())
    SIGILS: [
        // 0 Star Shield - shield outline with a five-point star
        `<path d="M24 9 L36 13 L36 24 Q36 33 24 39 Q12 33 12 24 L12 13 Z"
              fill="none" stroke="#c7d3e0" stroke-width="2" stroke-linejoin="round"/>
         <polygon points="24.0,14.0 26.2,19.9 32.6,20.2 27.6,24.2 29.3,30.3 24.0,26.8 18.7,30.3 20.4,24.2 15.4,20.2 21.8,19.9"
              fill="#6fc9e0"/>`,
        // 1 Crescent Dominion - waning crescent with companion star
        `<path d="M28 9 A15 15 0 1 0 28 39 A12.5 12.5 0 1 1 28 9 Z"
              fill="#e0b56f" stroke="#c7d3e0" stroke-width="1.5" stroke-linejoin="round"/>
         <polygon points="31.0,11.0 32.2,14.3 35.8,14.5 33.0,16.6 33.9,20.0 31.0,18.1 28.1,20.0 29.0,16.6 26.2,14.5 29.8,14.3"
              fill="#c7d3e0"/>`,
        // 2 Mandible Swarm - paired mandibles around a compound eye
        `<path d="M14 10 Q8 22 16 34 Q19 38 23 39" fill="none"
              stroke="#c7d3e0" stroke-width="2.5" stroke-linecap="round"/>
         <path d="M34 10 Q40 22 32 34 Q29 38 25 39" fill="none"
              stroke="#c7d3e0" stroke-width="2.5" stroke-linecap="round"/>
         <path d="M14 10 L19 16 M34 10 L29 16" stroke="#c7d3e0"
              stroke-width="2" stroke-linecap="round"/>
         <circle cx="24" cy="24" r="5.5" fill="#8fce7a"/>
         <circle cx="24" cy="24" r="2.2" fill="#0d1420"/>`,
        // 3 Crystal Facet - faceted gem sigil
        `<polygon points="24,8 34,16 30,38 18,38 14,16"
              fill="none" stroke="#c7d3e0" stroke-width="2" stroke-linejoin="round"/>
         <path d="M24 8 L24 38 M14 16 L24 22 L34 16 M18 38 L24 22 L30 38"
              fill="none" stroke="#a98fd9" stroke-width="1.5" stroke-linejoin="round"/>`,
        // 4 Comet Riders - comet head with three sweeping trails
        `<path d="M36 12 Q22 14 10 34" fill="none" stroke="#6fc9e0"
              stroke-width="2.5" stroke-linecap="round"/>
         <path d="M38 18 Q26 20 16 36" fill="none" stroke="#6fc9e0"
              stroke-width="1.8" stroke-linecap="round" opacity="0.7"/>
         <path d="M32 8 Q20 12 8 28" fill="none" stroke="#6fc9e0"
              stroke-width="1.8" stroke-linecap="round" opacity="0.7"/>
         <circle cx="36" cy="12" r="5" fill="#c7d3e0"/>`,
        // 5 Watchful Eye - almond eye with amber iris
        `<path d="M8 24 Q24 8 40 24 Q24 40 8 24 Z" fill="none"
              stroke="#c7d3e0" stroke-width="2" stroke-linejoin="round"/>
         <circle cx="24" cy="24" r="7" fill="#e0b56f"/>
         <circle cx="24" cy="24" r="3" fill="#0d1420"/>
         <circle cx="26" cy="21.5" r="1.3" fill="#c7d3e0"/>`,
        // 6 Trident Deep - rising trident
        `<path d="M24 40 L24 14 M24 14 L24 10" fill="none" stroke="#6fc9e0"
              stroke-width="2.5" stroke-linecap="round"/>
         <path d="M14 12 L14 20 Q14 27 21 27 M34 12 L34 20 Q34 27 27 27"
              fill="none" stroke="#6fc9e0" stroke-width="2.5" stroke-linecap="round"/>
         <path d="M24 10 L21 14 M24 10 L27 14 M14 12 L11.5 15.5 M14 12 L16.5 15.5 M34 12 L31.5 15.5 M34 12 L36.5 15.5"
              fill="none" stroke="#c7d3e0" stroke-width="1.8" stroke-linecap="round"/>
         <path d="M18 40 L30 40" stroke="#c7d3e0" stroke-width="2" stroke-linecap="round"/>`,
        // 7 Serpent Coil - S-curved serpent with raised head
        `<path d="M13 36 Q24 40 30 33 Q35 26 26 24 Q17 22 20 15 Q22 10 29 11"
              fill="none" stroke="#8fce7a" stroke-width="3" stroke-linecap="round"/>
         <circle cx="31" cy="11.5" r="3.4" fill="#8fce7a"/>
         <circle cx="32" cy="10.6" r="1" fill="#0d1420"/>
         <path d="M34 12.5 L37.5 13.5" stroke="#d97666" stroke-width="1.5" stroke-linecap="round"/>`,
        // 8 Iron Cog - eight-tooth gear with forge-red core
        `<polygon points="33.5,24.0 36.8,26.5 36.0,29.0 31.9,29.3 30.7,30.7 31.2,34.8 29.0,36.0 25.9,33.3 24.0,33.5 21.5,36.8 19.0,36.0 18.7,31.9 17.3,30.7 13.2,31.2 12.0,29.0 14.7,25.9 14.5,24.0 11.2,21.5 12.0,19.0 16.1,18.7 17.3,17.3 16.8,13.2 19.0,12.0 22.1,14.7 24.0,14.5 26.5,11.2 29.0,12.0 29.3,16.1 30.7,17.3 34.8,16.8 36.0,19.0 33.3,22.1"
              fill="none" stroke="#c7d3e0" stroke-width="2" stroke-linejoin="round"/>
         <circle cx="24" cy="24" r="4.5" fill="#d97666"/>`,
        // 9 Twin Pylons - mirrored triangles over a horizon line
        `<polygon points="24,10 33,26 15,26" fill="none"
              stroke="#a98fd9" stroke-width="2" stroke-linejoin="round"/>
         <polygon points="24,38 33,22 15,22" fill="none"
              stroke="#c7d3e0" stroke-width="2" stroke-linejoin="round"/>
         <circle cx="24" cy="24" r="2.4" fill="#a98fd9"/>`,
        // 10 Raptor Wing - triple swept wing chevrons
        `<path d="M10 32 Q22 30 38 14 L30 15 Z" fill="#e0b56f"
              stroke="#c7d3e0" stroke-width="1.2" stroke-linejoin="round"/>
         <path d="M12 37 Q24 35 36 24 L29 25 Z" fill="none"
              stroke="#c7d3e0" stroke-width="1.8" stroke-linejoin="round"/>
         <path d="M16 42 Q26 40 34 32 L28 33 Z" fill="none"
              stroke="#c7d3e0" stroke-width="1.5" stroke-linejoin="round"/>
         <circle cx="38" cy="12" r="2.6" fill="#e0b56f"/>`,
        // 11 Atomic Core - crossed electron orbits around a nucleus
        `<ellipse cx="24" cy="24" rx="15" ry="6.5" fill="none"
              stroke="#6fc9e0" stroke-width="1.8" transform="rotate(30 24 24)"/>
         <ellipse cx="24" cy="24" rx="15" ry="6.5" fill="none"
              stroke="#6fc9e0" stroke-width="1.8" transform="rotate(-30 24 24)"/>
         <ellipse cx="24" cy="24" rx="15" ry="6.5" fill="none"
              stroke="#c7d3e0" stroke-width="1.2" transform="rotate(90 24 24)"/>
         <circle cx="24" cy="24" r="3.6" fill="#c7d3e0"/>`,
        // 12 Rune Gate - keyed archway rune
        `<path d="M14 40 L14 20 Q14 10 24 10 Q34 10 34 20 L34 40"
              fill="none" stroke="#c7d3e0" stroke-width="2.5" stroke-linecap="round"/>
         <path d="M10 40 L38 40" stroke="#c7d3e0" stroke-width="2" stroke-linecap="round"/>
         <circle cx="24" cy="22" r="4" fill="none" stroke="#e0b56f" stroke-width="2"/>
         <path d="M24 26 L24 34" stroke="#e0b56f" stroke-width="2" stroke-linecap="round"/>`,
        // 13 Triune Orbs - three linked orbs in a triad
        `<path d="M24 13 L15 32 L33 32 Z" fill="none"
              stroke="#c7d3e0" stroke-width="1.5" stroke-linejoin="round"/>
         <circle cx="24" cy="13" r="4.6" fill="#8fce7a"/>
         <circle cx="15" cy="32" r="4.6" fill="none" stroke="#8fce7a" stroke-width="2"/>
         <circle cx="33" cy="32" r="4.6" fill="none" stroke="#c7d3e0" stroke-width="2"/>`,
        // 14 Crossed Sabers - two crossed blades, guards down
        `<path d="M13 11 L33 35" stroke="#c7d3e0" stroke-width="2.8" stroke-linecap="round"/>
         <path d="M35 11 L15 35" stroke="#c7d3e0" stroke-width="2.8" stroke-linecap="round"/>
         <path d="M30 38 L36 32 M12 32 L18 38" stroke="#d97666"
              stroke-width="2.4" stroke-linecap="round"/>
         <circle cx="24" cy="23" r="2.2" fill="#d97666"/>`,
        // 15 Void Crown - five-point crown over the void
        `<path d="M12 33 L12 17 L19 25 L24 13 L29 25 L36 17 L36 33 Z"
              fill="none" stroke="#e0b56f" stroke-width="2" stroke-linejoin="round"/>
         <path d="M12 37 L36 37" stroke="#c7d3e0" stroke-width="2" stroke-linecap="round"/>
         <circle cx="24" cy="30" r="2.2" fill="#c7d3e0"/>`
    ],

    /**
     * Standard emblem as an inline SVG string.
     * @param {number} index - Emblem index 0-15
     * @param {number} size - Rendered width/height in px
     * @returns {string} SVG markup
     */
    svg(index, size = 32) {
        const i = ((index | 0) % this.COUNT + this.COUNT) % this.COUNT;
        return `<svg class="race-icon" viewBox="0 0 48 48" width="${size}" height="${size}"
                     role="img" aria-label="${this.NAMES[i]}">
            <circle cx="24" cy="24" r="22" fill="${this.DISC_FILL}"
                    stroke="${this.DISC_STROKE}" stroke-width="2"/>
            ${this.SIGILS[i]}
        </svg>`;
    },

    /**
     * Render a race's icon: the uploaded custom icon when present,
     * otherwise the standard emblem for the index.
     * @param {number} index - Standard emblem index 0-15
     * @param {?string} customIcon - Base64 data URI or null/empty
     * @param {number} size - Rendered width/height in px
     * @returns {string} HTML markup
     */
    render(index, customIcon, size = 32) {
        if (customIcon && customIcon.startsWith('data:image/')) {
            return `<img class="race-icon race-icon-custom" src="${customIcon}"
                         width="${size}" height="${size}" alt="Custom race icon">`;
        }
        return this.svg(index, size);
    },

    /**
     * Render from a server-side race dict (snake_case keys).
     * @param {?Object} race - Race dict from player state (or null)
     * @param {number} size - Rendered width/height in px
     * @returns {string} HTML markup
     */
    renderRace(race, size = 32) {
        if (!race) return this.svg(0, size);
        return this.render(race.icon || 0, race.custom_icon || null, size);
    }
};

// Export
window.RaceIcons = RaceIcons;
