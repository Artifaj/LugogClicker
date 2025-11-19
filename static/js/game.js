// Custom Alert Modal System
function showCustomAlert(message, options = {}) {
    // Remove existing alert if any
    const existingAlert = document.querySelector('.custom-alert-overlay');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    const type = options.type || 'info'; // success, error, warning, info
    const title = options.title || (type === 'error' ? 'Chyba' : type === 'success' ? 'Úspěch' : type === 'warning' ? 'Varování' : 'Informace');
    const rewards = options.rewards || null;
    const levelUp = options.levelUp || null;
    
    const overlay = document.createElement('div');
    overlay.className = 'custom-alert-overlay';
    
    let rewardsHtml = '';
    if (rewards) {
        rewardsHtml = '<div class="custom-alert-rewards">';
        rewardsHtml += '<div class="custom-alert-rewards-title">Odměny:</div>';
        if (rewards.gooncoins) {
            rewardsHtml += `<div class="custom-alert-reward-item"><span class="custom-alert-reward-icon">💰</span> ${rewards.gooncoins} Gooncoins</div>`;
        }
        if (rewards.exp) {
            rewardsHtml += `<div class="custom-alert-reward-item"><span class="custom-alert-reward-icon">⭐</span> ${rewards.exp} EXP</div>`;
        }
        if (rewards.metal_gained) {
            rewardsHtml += `<div class="custom-alert-reward-item"><span class="custom-alert-reward-icon">⚙️</span> ${rewards.metal_gained} kovu</div>`;
        }
        if (rewards.souls_gained) {
            rewardsHtml += `<div class="custom-alert-reward-item"><span class="custom-alert-reward-icon">👻</span> ${rewards.souls_gained} duší</div>`;
        }
        rewardsHtml += '</div>';
    }
    
    let levelUpHtml = '';
    if (levelUp) {
        levelUpHtml = `<div class="custom-alert-levelup"><span class="custom-alert-levelup-icon">🎉</span> Level up! Nový level: ${levelUp}</div>`;
    }
    
    overlay.innerHTML = `
        <div class="custom-alert-modal ${type}">
            <div class="custom-alert-header">
                <h3>${title}</h3>
                <button class="custom-alert-close" onclick="this.closest('.custom-alert-overlay').remove()">×</button>
            </div>
            <div class="custom-alert-body">
                <p>${message}</p>
                ${rewardsHtml}
                ${levelUpHtml}
            </div>
            <div class="custom-alert-footer">
                <button class="custom-alert-button" onclick="this.closest('.custom-alert-overlay').remove()">OK</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Close on overlay click
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
    
    // Close on Escape key
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', escapeHandler);
        }
    };
    document.addEventListener('keydown', escapeHandler);
}

// Game state
let gameState = {
    gooncoins: 0,
    astma: 0,
    poharky: 0,
    mrkev: 0,
    uzené: 0,
    logs: 0,
    planks: 0,
    grain: 0,
    flour: 0,
    bread: 0,
    fish: 0,
    total_clicks: 0,
    upgrades: {},
    clickValue: 1,
    equipmentCounts: {},
    economy: {
        inflation_rate: 0.02,
        inflation_multiplier: 1,
        gooncoin_supply: 0,
        market_rates: {}
    },
    rareMaterials: {},
    combat: {
        rating: 0,
        wins: 0,
        losses: 0,
        campaign_stage: 0,
        defeated_monsters: []
    },
    temple: {
        favor: 0,
        active_room: null,
        rooms: [],
        blessings: [],
        active_blessing: null,
        cooldown_seconds: 0
    },
    inventory: {
        items: [],
        summary: {},
        market: {},
        updated_at: null
    }
};

const MARKET_CURRENCY_LABELS = {
    astma: 'Astma',
    poharky: 'Pohárky',
    mrkev: 'Mrkev',
    uzené: 'Uzené',
    logs: 'Klády',
    planks: 'Prkna',
    grain: 'Obilí',
    flour: 'Mouka',
    bread: 'Chleba',
    fish: 'Ryby'
};

const SECONDARY_RESOURCES = ['logs', 'planks', 'grain', 'flour', 'bread', 'fish'];
const RESOURCE_KEYS = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'];

const RESOURCE_LABELS = {
    gooncoins: 'Gooncoiny',
    astma: 'Astma',
    poharky: 'Pohárky',
    mrkev: 'Mrkev',
    uzené: 'Uzené',
    logs: 'Klády',
    planks: 'Prkna',
    grain: 'Obilí',
    flour: 'Mouka',
    bread: 'Chleba',
    fish: 'Ryby',
    favor: 'Přízeň'
};

const CASE_CURRENCY_ICONS = {
    gooncoins: '💰',
    astma: '💨',
    poharky: '🥃',
    mrkev: '🥕',
    uzené: '🍖',
    logs: '🪵',
    planks: '🪚',
    grain: '🌾',
    flour: '🧯',
    bread: '🍞',
    fish: '🐟'
};

const CASE_SLOT_WIDTH = 120;
const CASE_SPIN_DURATION = 3400;

let lastInflationRate = 0;
let inventoryFilters = {
    search: '',
    rarity: 'all'
};

function getInflationMultiplier() {
    return gameState?.economy?.inflation_multiplier || 1;
}

function applyInflationToCostMap(costMap = {}) {
    const multiplier = getInflationMultiplier();
    const inflated = { ...costMap };
    if (inflated.gooncoins) {
        inflated.gooncoins = inflated.gooncoins * multiplier;
    }
    return inflated;
}

function formatPercent(value = 0) {
    return `${(value * 100).toFixed(2)}%`;
}

function getCurrencyLabel(currency) {
    return MARKET_CURRENCY_LABELS[currency] || currency;
}

function formatCostValue(value = 0) {
    if (value >= 1000) return formatNumber(value);
    if (Math.abs(value - Math.round(value)) < 0.01) {
        return Math.round(value).toString();
    }
    return value.toFixed(2);
}

// Upgrade definitions
const upgrades = {
    // Basic click power upgrades
    click_power_1: {
        name: '⚡ Síla kliku I',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_2: {
        name: '⚡ Síla kliku II',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_3: {
        name: '⚡ Síla kliku III',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_4: {
        name: '⚡ Síla kliku IV',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_5: {
        name: '⚡ Síla kliku V',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_6: {
        name: '⚡ Síla kliku VI',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_7: {
        name: '⚡ Síla kliku VII',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    click_power_8: {
        name: '⚡ Síla kliku VIII',
        description: 'Zvyšuje hodnotu každého kliknutí o 0.5 Gooncoin',
        icon: '⚡'
    },
    
    // Auto-generators
    auto_gooncoin: {
        name: '💰 Auto-generátor Gooncoinů',
        description: 'Automaticky generuje Gooncoiny každou sekundu (0.1/s na level)',
        icon: '💰'
    },
    auto_astma: {
        name: '💨 Auto-generátor Astma',
        description: 'Automaticky generuje Astma každou sekundu (0.05/s na level)',
        icon: '💨'
    },
    auto_poharky: {
        name: '🥃 Auto-generátor Pohárků',
        description: 'Automaticky generuje Pohárky každou sekundu (0.03/s na level)',
        icon: '🥃'
    },
    auto_mrkev: {
        name: '🥕 Auto-generátor Mrkve',
        description: 'Automaticky generuje Mrkev každou sekundu (0.02/s na level)',
        icon: '🥕'
    },
    auto_uzené: {
        name: '🍖 Auto-generátor Uzeného',
        description: 'Automaticky generuje Uzené každou sekundu (0.01/s na level)',
        icon: '🍖'
    },
    
    // Multiplier upgrades
    click_multiplier_1: {
        name: '🔥 Multiplikátor kliku I',
        description: 'Zvyšuje sílu kliku o 25% (multiplikativně)',
        icon: '🔥'
    },
    click_multiplier_2: {
        name: '🔥 Multiplikátor kliku II',
        description: 'Zvyšuje sílu kliku o 25% (multiplikativně)',
        icon: '🔥'
    },
    click_multiplier_3: {
        name: '🔥 Multiplikátor kliku III',
        description: 'Zvyšuje sílu kliku o 25% (multiplikativně)',
        icon: '🔥'
    },
    click_multiplier_4: {
        name: '🔥 Multiplikátor kliku IV',
        description: 'Zvyšuje sílu kliku o 25% (multiplikativně)',
        icon: '🔥'
    },
    
    generation_multiplier_1: {
        name: '⚙️ Multiplikátor generace I',
        description: 'Zvyšuje rychlost generace všech zdrojů o 20% (multiplikativně)',
        icon: '⚙️'
    },
    generation_multiplier_2: {
        name: '⚙️ Multiplikátor generace II',
        description: 'Zvyšuje rychlost generace všech zdrojů o 20% (multiplikativně)',
        icon: '⚙️'
    },
    generation_multiplier_3: {
        name: '⚙️ Multiplikátor generace III',
        description: 'Zvyšuje rychlost generace všech zdrojů o 20% (multiplikativně)',
        icon: '⚙️'
    },
    generation_multiplier_4: {
        name: '⚙️ Multiplikátor generace IV',
        description: 'Zvyšuje rychlost generace všech zdrojů o 20% (multiplikativně)',
        icon: '⚙️'
    },
    
    // Efficiency upgrades
    cost_reduction_1: {
        name: '💎 Snížení nákladů I',
        description: 'Snižuje náklady všech upgradů o 5% (multiplikativně)',
        icon: '💎'
    },
    cost_reduction_2: {
        name: '💎 Snížení nákladů II',
        description: 'Snižuje náklady všech upgradů o 5% (multiplikativně)',
        icon: '💎'
    },
    cost_reduction_3: {
        name: '💎 Snížení nákladů III',
        description: 'Snižuje náklady všech upgradů o 5% (multiplikativně)',
        icon: '💎'
    },
    
    // Global power upgrades
    global_power_1: {
        name: '🌟 Globální síla I',
        description: 'Zvyšuje VŠECHNO o 15% (kliky i generace)',
        icon: '🌟'
    },
    global_power_2: {
        name: '🌟 Globální síla II',
        description: 'Zvyšuje VŠECHNO o 15% (kliky i generace)',
        icon: '🌟'
    },
    global_power_3: {
        name: '🌟 Globální síla III',
        description: 'Zvyšuje VŠECHNO o 15% (kliky i generace)',
        icon: '🌟'
    },
    
    // Special late-game upgrades
    quantum_click: {
        name: '⚛️ Kvantový klik',
        description: 'MASSIVNÍ boost síly kliku (+50% na level, multiplikativně)',
        icon: '⚛️'
    },
    time_acceleration: {
        name: '⏱️ Zrychlení času',
        description: 'Zrychluje generaci všech zdrojů o 30% na level',
        icon: '⏱️'
    },
    infinity_boost: {
        name: '∞ Infinity Boost',
        description: 'ULTIMÁTNÍ upgrade - +100% generace a +50% všeho ostatního na level',
        icon: '∞'
    }
};

const autoGeneratorBlueprints = {
    auto_gooncoin: {
        resourceKey: 'gooncoins',
        ratePerLevel: 0.1,
        flavor: 'Najímá účetní, kteří ti sypou drobné na účet.'
    },
    auto_astma: {
        resourceKey: 'astma',
        ratePerLevel: 0.05,
        flavor: 'Větrné mlýny sbírají vzduch z Lugogových plání.'
    },
    auto_poharky: {
        resourceKey: 'poharky',
        ratePerLevel: 0.03,
        flavor: 'Automatické destilační aparáty produkují destilovanou mrkev.'
    },
    auto_mrkev: {
        resourceKey: 'mrkev',
        ratePerLevel: 0.02,
        flavor: 'Mrkvové plantáže pracují nepřetržitě pod dohledem robotů.'
    },
    auto_uzené: {
        resourceKey: 'uzené',
        ratePerLevel: 0.01,
        flavor: 'Uzené se připravuje v automatických udírnách.'
    }
};

// Story and game data
let storyData = {};
let equipmentDefs = {};
let buildingsDefs = {};
let gemsDefs = {};
let loreEntries = [];
let activeLoreId = null;
let templeSnapshot = null;
let templeRefreshTimer = null;
let templeCooldownInterval = null;
let combatAnimationTimers = [];
const QUEST_NUMERIC_RESOURCES = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'];
const QUEST_RESOURCE_LABELS = {
    gooncoins: 'Gooncoinů',
    astma: 'Astma',
    poharky: 'Pohárků',
    mrkev: 'Mrkve',
    'uzené': 'Uzeného'
};

function getQuestResourceLabel(resource) {
    return QUEST_RESOURCE_LABELS[resource] || getCurrencyLabel(resource);
}

function formatQuestRequirement(requirement = {}) {
    if (!requirement || Object.keys(requirement).length === 0) return '';
    
    if (requirement.total_clicks) {
        return `Požadavek: ${formatNumber(requirement.total_clicks)} kliknutí`;
    }
    
    const numericResources = QUEST_NUMERIC_RESOURCES.filter(key => requirement[key]);
    if (numericResources.length) {
        const needs = numericResources.map(key => `${formatNumber(requirement[key])} ${getQuestResourceLabel(key)}`);
        return `Dodej: ${needs.join(', ')}`;
    }
    
    if (requirement.buildings) {
        const labels = requirement.buildings.map(id => buildingsDefs[id]?.name || id);
        return `Postav: ${labels.join(', ')}`;
    }
    
    if (requirement.equipment_count) {
        return `Měj ${requirement.equipment_count} kusů vybavení.`;
    }
    
    if (requirement.equipment_owned) {
        const parts = Object.entries(requirement.equipment_owned).map(([eqId, count]) => {
            const name = equipmentDefs[eqId]?.name || eqId;
            return `${count}× ${name}`;
        });
        return `Získej: ${parts.join(', ')}`;
    }
    
    return '';
}

function getQuestProgressInfo(quest) {
    const req = quest?.requirement || {};
    if (!req || Object.keys(req).length === 0) {
        return { progress: 0, text: '' };
    }
    
    if (req.total_clicks) {
        const current = gameState.total_clicks || 0;
        return {
            progress: Math.min(100, (current / req.total_clicks) * 100),
            text: `${formatNumber(current)} / ${formatNumber(req.total_clicks)} kliknutí`
        };
    }
    
    if (req.equipment_count) {
        const eqCount = Object.keys(gameState.equipment || {}).length;
        return {
            progress: Math.min(100, (eqCount / req.equipment_count) * 100),
            text: `${eqCount} / ${req.equipment_count} vybavení`
        };
    }
    
    if (req.equipment_owned) {
        const requirements = Object.entries(req.equipment_owned);
        if (requirements.length > 0) {
            const ratios = requirements.map(([eqId, needed]) => {
                const owned = gameState.equipmentCounts?.[eqId] || 0;
                return needed ? owned / needed : 0;
            });
            const minRatio = Math.min(...ratios.map(r => Math.max(0, r)));
            const parts = requirements.map(([eqId, needed]) => {
                const owned = gameState.equipmentCounts?.[eqId] || 0;
                const eqName = equipmentDefs[eqId]?.name || eqId;
                return `${owned} / ${needed} × ${eqName}`;
            });
            return {
                progress: Math.min(100, minRatio * 100),
                text: parts.join(', ')
            };
        }
    }
    
    if (req.buildings) {
        const builtCount = req.buildings.filter(b => gameState.buildings?.[b] > 0).length;
        return {
            progress: Math.min(100, (builtCount / req.buildings.length) * 100),
            text: `${builtCount} / ${req.buildings.length} budov`
        };
    }
    
    const numericResources = QUEST_NUMERIC_RESOURCES.filter(key => req[key]);
    if (numericResources.length) {
        const ratios = numericResources.map(resource => {
            const current = gameState[resource] || 0;
            const needed = req[resource] || 0;
            return needed ? current / needed : 0;
        });
        const minRatio = Math.min(...ratios.map(r => Math.max(0, r)));
        const parts = numericResources.map(resource => {
            const current = gameState[resource] || 0;
            return `${formatNumber(current)} / ${formatNumber(req[resource])} ${getQuestResourceLabel(resource)}`;
        });
        return {
            progress: Math.min(100, minRatio * 100),
            text: parts.join(', ')
        };
    }
    
    return { progress: 0, text: '' };
}

// Equipment tab removed - using character panel instead
const SLOT_LABELS = {
    weapon: 'Zbraň',
    armor: 'Zbroj',
    helmet: 'Helma',
    ring: 'Prsten',
    amulet: 'Amulet',
    special: 'Speciální',
    accessory: 'Doplňky',
    vehicle: 'Vozidlo'
};
const RARITY_ORDER = ['common', 'rare', 'epic', 'legendary', 'unique'];
const RARITY_LABELS = {
    common: 'Common',
    rare: 'Rare',
    epic: 'Epic',
    legendary: 'Legendary',
    unique: 'Unique'
};

let selectedCraftSort = 'unlocked';
let craftingSearchQuery = '';
let craftingRarityFilter = 'all';
try {
    if (typeof localStorage !== 'undefined') {
        selectedCraftSort = localStorage.getItem('craftSortPreference') || 'unlocked';
        craftingRarityFilter = localStorage.getItem('craftingRarityFilter') || 'all';
    }
} catch (err) {
    console.warn('Cannot read craft sort preference', err);
}

function persistCraftSortPreference(value) {
    try {
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('craftSortPreference', value);
        }
    } catch (err) {
        console.warn('Cannot store craft sort preference', err);
    }
}

function getSlotLabel(slot) {
    if (slot === 'resource') {
        return 'Zdroj';
    }
    return SLOT_LABELS[slot] || slot || '–';
}

function getRarityMeta(rarity = 'common') {
    const normalized = RARITY_ORDER.includes(rarity) ? rarity : 'common';
    return {
        key: normalized,
        label: RARITY_LABELS[normalized] || normalized
    };
}

function getRarityIndex(rarity = 'common') {
    const idx = RARITY_ORDER.indexOf(rarity);
    return idx === -1 ? 0 : idx;
}

function getItemPower(def = {}) {
    if (typeof def.power === 'number') {
        return def.power;
    }
    if (!def.bonus) return 0;
    return Object.values(def.bonus).reduce((sum, value) => sum + (typeof value === 'number' ? value : 0), 0);
}

function getReleaseOrder(def = {}) {
    return typeof def.release_order === 'number' ? def.release_order : 0;
}

function getUnlockState(def = {}, playerCounts = {}) {
    const requirements = Object.entries(def.unlock_requirement || {}).map(([reqId, needed]) => {
        const owned = playerCounts[reqId] || 0;
        return {
            id: reqId,
            name: equipmentDefs[reqId]?.name || reqId,
            needed,
            owned,
            met: owned >= needed,
            ratio: needed ? Math.min(1, owned / needed) : 1
        };
    });
    const isUnlocked = requirements.every(req => req.met);
    const progress = requirements.length > 0 ? Math.min(...requirements.map(req => req.ratio)) : 1;
    return {
        isUnlocked,
        progress,
        requirements
    };
}

function sortCraftItems(a, b, mode = 'unlocked') {
    if (mode === 'rarity') {
        const rarityDiff = getRarityIndex(b.rarity) - getRarityIndex(a.rarity);
        if (rarityDiff !== 0) return rarityDiff;
    } else if (mode === 'power') {
        if (b.power !== a.power) return b.power - a.power;
    } else if (mode === 'newest') {
        if (b.release !== a.release) return b.release - a.release;
    } else if (mode === 'name') {
        return a.def.name.localeCompare(b.def.name, 'cs');
    } else {
        if (a.unlockState.isUnlocked !== b.unlockState.isUnlocked) {
            return a.unlockState.isUnlocked ? -1 : 1;
        }
    }
    const rarityTie = getRarityIndex(b.rarity) - getRarityIndex(a.rarity);
    if (rarityTie !== 0) return rarityTie;
    if (b.power !== a.power) return b.power - a.power;
    if (b.release !== a.release) return b.release - a.release;
    return a.def.name.localeCompare(b.def.name, 'cs');
}

// Initialize game
async function initGame() {
    const usernameElement = document.getElementById('usernameDisplay');
    if (usernameElement) {
        currentUsername = usernameElement.textContent.trim();
    }
    setupDarkMode();
    await loadStoryData();
    await loadGameState();
    setupTabs();
    setupMobileNavigation();
    setupMobileView();
    setupClickButton();
    setupUpgrades();
    setupAutoGenerators();
    setupCrafting();
    setupBuildings();
    setupGems();
    setupQuests();
    setupEquipment();
    setupPlayerView();
    setupMarket();
    setupEconomyPanel();
    await setupCases();
    setupCombat();
    setupTempleSection();
    setupInventory();
    initNewSystems();  // Initialize dungeon and other new systems
    loadQuests();
    startAutoGeneration();
    startAutoRefresh();
    updateDisplay();
}

// Load story data
async function loadStoryData() {
    try {
        const response = await fetch('/api/story-data');
        if (response.ok) {
            const data = await response.json();
            storyData = data.chapters;
            equipmentDefs = data.equipment;
            buildingsDefs = data.buildings;
            if (data.gems) {
                gemsDefs = data.gems;
            }
            storyEquipmentCounts = data.equipment_counts || {};
            loreEntries = data.lore_entries || [];
        }
    } catch (error) {
        console.error('Error loading story data:', error);
    }
    
    renderLoreCodex();
}

function renderLoreCodex(selectedId = null) {
    const tabs = document.getElementById('loreCodexTabs');
    const content = document.getElementById('loreCodexContent');
    const summary = document.getElementById('loreCodexSummary');
    if (!tabs || !content) return;
    
    const currentChapter = gameState.story?.current_chapter || 1;
    const availableEntries = loreEntries.filter(entry => 
        !entry.required_chapter || entry.required_chapter <= currentChapter
    );
    
    if (availableEntries.length === 0) {
        tabs.innerHTML = '';
        content.innerHTML = '<p class="lore-placeholder">Dokonči kapitolu 1, aby se odemkl první zápis.</p>';
        if (summary) {
            summary.textContent = 'Lore se odemyká postupem v kapitolách.';
        }
        activeLoreId = null;
        return;
    }
    
    if (selectedId) {
        activeLoreId = selectedId;
    } else if (!activeLoreId || !availableEntries.some(entry => entry.id === activeLoreId)) {
        activeLoreId = availableEntries[0].id;
    }
    
    tabs.innerHTML = '';
    availableEntries.forEach(entry => {
        const tab = document.createElement('button');
        tab.className = `lore-tab ${entry.id === activeLoreId ? 'active' : ''}`;
        tab.textContent = entry.title;
        tab.addEventListener('click', () => renderLoreCodex(entry.id));
        tabs.appendChild(tab);
    });
    
    const currentEntry = availableEntries.find(entry => entry.id === activeLoreId);
    if (!currentEntry) return;
    
    if (summary) {
        summary.textContent = currentEntry.summary || '';
    }
    
    const paragraphs = Array.isArray(currentEntry.body)
        ? currentEntry.body.map(paragraph => `<p>${paragraph}</p>`).join('')
        : `<p>${currentEntry.body}</p>`;
    
    const lockLabel = currentEntry.required_chapter && currentEntry.required_chapter > 1
        ? `<span class="lore-lock">Odemčeno v kapitole ${currentEntry.required_chapter}</span>`
        : '';
    
    content.innerHTML = `
        <div class="lore-meta">
            <span class="lore-era">${currentEntry.era || ''}</span>
            ${lockLabel}
        </div>
        ${paragraphs}
    `;
}

let storyEquipmentCounts = {};
let selectedCraftItem = null;
let currentUsername = '';
let combatOverview = null;
let rareMaterialDefs = {};
let combatRefreshTimer = null;
let combatMessageTimer = null;
let caseDefinitions = [];
let caseDefinitionMap = {};
let selectedCaseId = null;
let caseHistoryEntries = [];
let caseSpinInProgress = false;
let caseSpinTimeout = null;

// Setup tabs
function setupTabs() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const tab = item.dataset.tab;
            
            // Update active nav item
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Show correct tab
            const tabs = document.querySelectorAll('.tab-content');
            tabs.forEach(t => t.classList.remove('active'));
            const targetTab = document.getElementById(`${tab}-tab`);
            if (targetTab) {
                targetTab.classList.add('active');
            }

            closeMobileNav();
            updateDisplay();
            
            // Load tab-specific data
            if (tab === 'shop') {
                loadShop();
                setupShopCategories();
            } else if (tab === 'cases') {
                loadCases();
            } else if (tab === 'leaderboard') {
                loadLeaderboard();
            } else if (tab === 'inventory') {
                loadInventory();
            } else if (tab === 'pets') {
                loadPets();
            } else if (tab === 'garden') {
                loadGarden();
            } else if (tab === 'friends') {
                loadFriends();
            }
        });
    });
}

function openMobileNav() {
    document.body.classList.add('nav-open');
}

function closeMobileNav() {
    document.body.classList.remove('nav-open');
}

function setupMobileNavigation() {
    const nav = document.querySelector('.left-nav');
    if (!nav) {
        return;
    }

    const menuToggle = document.getElementById('mobileMenuToggle');
    const menuClose = document.getElementById('mobileMenuClose');
    const overlay = document.getElementById('mobileNavOverlay');

    if (menuToggle) {
        menuToggle.addEventListener('click', openMobileNav);
    }

    if (menuClose) {
        menuClose.addEventListener('click', closeMobileNav);
    }

    if (overlay) {
        overlay.addEventListener('click', closeMobileNav);
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeMobileNav();
        }
    });

    const desktopQuery = window.matchMedia('(min-width: 769px)');
    const handleDesktopChange = (event) => {
        if (event.matches) {
            closeMobileNav();
        }
    };

    if (desktopQuery.addEventListener) {
        desktopQuery.addEventListener('change', handleDesktopChange);
    } else if (desktopQuery.addListener) {
        desktopQuery.addListener(handleDesktopChange);
    }
}

let marketMessageTimer = null;

function setupMarket() {
    const buyBtn = document.getElementById('marketBuyBtn');
    const sellBtn = document.getElementById('marketSellBtn');
    const refreshBtn = document.getElementById('marketRefreshBtn');
    
    if (buyBtn) {
        buyBtn.addEventListener('click', () => handleMarketAction('buy'));
    }
    if (sellBtn) {
        sellBtn.addEventListener('click', () => handleMarketAction('sell'));
    }
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshMarketRates);
    }
    
    updateMarketCurrencyOptions();
    updateEconomyPanel();
}

async function handleMarketAction(action) {
    const currencySelect = document.getElementById('marketCurrency');
    const amountInput = document.getElementById('marketAmount');
    
    if (!currencySelect || !amountInput) return;
    
    const currency = currencySelect.value;
    const amount = parseFloat(amountInput.value);
    
    if (isNaN(amount) || amount <= 0) {
        setMarketMessage('Zadej platné množství.', true);
        return;
    }
    
    try {
        const response = await fetch('/api/currency-market', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ currency, action, amount })
        });
        
        const data = await response.json();
        if (!response.ok || !data.success) {
            setMarketMessage(data.error || 'Obchod se nezdařil.', true);
            return;
        }
        
        gameState.gooncoins = data.gooncoins;
        gameState.astma = data.astma;
        gameState.poharky = data.poharky;
        gameState.mrkev = data.mrkev;
        gameState.uzené = data.uzené;
        if (data.economy) {
            gameState.economy = data.economy;
        }
        
        updateResourcesOnly();
        updateEconomyPanel();
        setMarketMessage(data.message || 'Obchod dokončen.', false);
    } catch (error) {
        console.error('Error trading currencies:', error);
        setMarketMessage('Chyba spojení se serverem.', true);
    }
}

function openMarketCalculator(currency, rateData) {
    // Remove existing modal if any
    const existingModal = document.getElementById('marketCalculatorModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const currentGooncoins = gameState.gooncoins || 0;
    const currentCurrency = gameState[currency] || 0;
    const currencyLabel = getCurrencyLabel(currency);
    const currencyIcon = getResourceIcon(currency);
    
    const modal = document.createElement('div');
    modal.id = 'marketCalculatorModal';
    modal.className = 'market-calculator-overlay';
    
    const updateCalculations = () => {
        const amountInput = document.getElementById('marketCalcAmount');
        const amount = parseFloat(amountInput?.value || 1) || 0;
        const buyCost = rateData.buy * amount;
        const sellReturn = rateData.sell * amount;
        const remainingAfterBuy = currentGooncoins - buyCost;
        const remainingAfterSell = currentGooncoins + sellReturn;
        const newCurrencyAfterBuy = currentCurrency + amount;
        const newCurrencyAfterSell = currentCurrency - amount;
        
        const buyCostEl = document.getElementById('marketCalcBuyCost');
        const sellReturnEl = document.getElementById('marketCalcSellReturn');
        const remainingBuyEl = document.getElementById('marketCalcRemainingBuy');
        const remainingSellEl = document.getElementById('marketCalcRemainingSell');
        const newCurrencyBuyEl = document.getElementById('marketCalcNewCurrencyBuy');
        const newCurrencySellEl = document.getElementById('marketCalcNewCurrencySell');
        const buyBtn = document.getElementById('marketCalcBuyBtn');
        const sellBtn = document.getElementById('marketCalcSellBtn');
        
        if (buyCostEl) buyCostEl.textContent = formatNumber(buyCost.toFixed(2));
        if (sellReturnEl) sellReturnEl.textContent = formatNumber(sellReturn.toFixed(2));
        if (remainingBuyEl) {
            remainingBuyEl.textContent = formatNumber(remainingAfterBuy.toFixed(2));
            remainingBuyEl.className = remainingAfterBuy < 0 ? 'insufficient' : '';
        }
        if (remainingSellEl) {
            remainingSellEl.textContent = formatNumber(remainingAfterSell.toFixed(2));
        }
        if (newCurrencyBuyEl) newCurrencyBuyEl.textContent = formatNumber(newCurrencyAfterBuy.toFixed(2));
        if (newCurrencySellEl) {
            newCurrencySellEl.textContent = formatNumber(newCurrencyAfterSell.toFixed(2));
            newCurrencySellEl.className = newCurrencyAfterSell < 0 ? 'insufficient' : '';
        }
        
        if (buyBtn) {
            buyBtn.disabled = amount <= 0 || remainingAfterBuy < 0 || isNaN(amount);
        }
        if (sellBtn) {
            sellBtn.disabled = amount <= 0 || newCurrencyAfterSell < 0 || amount > currentCurrency || isNaN(amount);
        }
    };
    
    modal.innerHTML = `
        <div class="market-calculator-modal">
            <div class="market-calculator-header">
                <div class="market-calculator-title">
                    <span class="market-calc-icon">${currencyIcon}</span>
                    <h3>${currencyLabel}</h3>
                </div>
                <button class="market-calculator-close" onclick="closeMarketCalculator()">×</button>
            </div>
            <div class="market-calculator-body">
                <div class="market-calc-current">
                    <div class="market-calc-resource">
                        <span>💰 Gooncoiny:</span>
                        <strong>${formatNumber(currentGooncoins.toFixed(2))}</strong>
                    </div>
                    <div class="market-calc-resource">
                        <span>${currencyIcon} ${currencyLabel}:</span>
                        <strong>${formatNumber(currentCurrency.toFixed(2))}</strong>
                    </div>
                </div>
                
                <div class="market-calc-input-section">
                    <label for="marketCalcAmount">Množství</label>
                    <input type="number" id="marketCalcAmount" min="0.001" step="0.001" value="1" 
                           oninput="updateMarketCalculator()">
                    <div class="market-calc-quick-buttons">
                        <button onclick="setMarketCalcAmount(0.1)">0.1</button>
                        <button onclick="setMarketCalcAmount(1)">1</button>
                        <button onclick="setMarketCalcAmount(10)">10</button>
                        <button onclick="setMarketCalcAmount(100)">100</button>
                        <button onclick="setMarketCalcMax()">MAX</button>
                    </div>
                </div>
                
                <div class="market-calc-info">
                    <div class="market-calc-buy-info">
                        <h4>📈 Koupě</h4>
                        <div class="market-calc-detail">
                            <span>Cena:</span>
                            <strong id="marketCalcBuyCost">${formatNumber((rateData.buy * amount).toFixed(2))}</strong>
                            <span>💰</span>
                        </div>
                        <div class="market-calc-detail">
                            <span>Zbyde Gooncoinů:</span>
                            <strong id="marketCalcRemainingBuy">${formatNumber((currentGooncoins - rateData.buy * amount).toFixed(2))}</strong>
                            <span>💰</span>
                        </div>
                        <div class="market-calc-detail">
                            <span>Budeš mít ${currencyLabel}:</span>
                            <strong id="marketCalcNewCurrencyBuy">${formatNumber((currentCurrency + amount).toFixed(2))}</strong>
                        </div>
                    </div>
                    
                    <div class="market-calc-sell-info">
                        <h4>📉 Prodej</h4>
                        <div class="market-calc-detail">
                            <span>Získáš:</span>
                            <strong id="marketCalcSellReturn">${formatNumber((rateData.sell * amount).toFixed(2))}</strong>
                            <span>💰</span>
                        </div>
                        <div class="market-calc-detail">
                            <span>Budeš mít Gooncoinů:</span>
                            <strong id="marketCalcRemainingSell">${formatNumber((currentGooncoins + rateData.sell * amount).toFixed(2))}</strong>
                            <span>💰</span>
                        </div>
                        <div class="market-calc-detail">
                            <span>Zbyde ${currencyLabel}:</span>
                            <strong id="marketCalcNewCurrencySell">${formatNumber((currentCurrency - amount).toFixed(2))}</strong>
                        </div>
                    </div>
                </div>
            </div>
            <div class="market-calculator-footer">
                <button id="marketCalcBuyBtn" class="btn-green" onclick="executeMarketCalcAction('buy', '${currency}')">
                    Nakoupit
                </button>
                <button id="marketCalcSellBtn" class="btn-red" onclick="executeMarketCalcAction('sell', '${currency}')">
                    Prodat
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Store references for updates
    window.marketCalcData = { currency, rateData, updateCalculations, currentGooncoins, currentCurrency };
    
    // Setup input handler
    const amountInput = document.getElementById('marketCalcAmount');
    if (amountInput) {
        amountInput.addEventListener('input', updateCalculations);
    }
    
    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeMarketCalculator();
        }
    });
    
    // Close on Escape
    const escapeHandler = (e) => {
        if (e.key === 'Escape') {
            closeMarketCalculator();
            document.removeEventListener('keydown', escapeHandler);
        }
    };
    document.addEventListener('keydown', escapeHandler);
    
    updateCalculations();
    amountInput?.focus();
}

function closeMarketCalculator() {
    const modal = document.getElementById('marketCalculatorModal');
    if (modal) {
        modal.remove();
    }
    window.marketCalcData = null;
}

function updateMarketCalculator() {
    if (!window.marketCalcData) return;
    const amountInput = document.getElementById('marketCalcAmount');
    if (amountInput) {
        const amount = parseFloat(amountInput.value) || 0;
        window.marketCalcData.updateCalculations();
    }
}

function setMarketCalcAmount(value) {
    const amountInput = document.getElementById('marketCalcAmount');
    if (amountInput) {
        amountInput.value = value;
        amountInput.dispatchEvent(new Event('input'));
    }
}

function setMarketCalcMax() {
    if (!window.marketCalcData) return;
    const { currency, rateData, currentGooncoins, currentCurrency } = window.marketCalcData;
    const amountInput = document.getElementById('marketCalcAmount');
    if (amountInput) {
        // For buy: max based on gooncoins
        // For sell: max based on current currency
        const maxBuy = Math.floor(currentGooncoins / rateData.buy * 1000) / 1000;
        const maxSell = currentCurrency;
        const max = Math.max(maxBuy, maxSell);
        amountInput.value = max;
        amountInput.dispatchEvent(new Event('input'));
    }
}

async function executeMarketCalcAction(action, currency) {
    const amountInput = document.getElementById('marketCalcAmount');
    if (!amountInput || !window.marketCalcData) return;
    
    const amount = parseFloat(amountInput.value);
    if (isNaN(amount) || amount <= 0) {
        setMarketMessage('Zadej platné množství.', true);
        return;
    }
    
    try {
        const response = await fetch('/api/currency-market', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ currency, action, amount })
        });
        
        const data = await response.json();
        if (!response.ok || !data.success) {
            setMarketMessage(data.error || 'Obchod se nezdařil.', true);
            return;
        }
        
        gameState.gooncoins = data.gooncoins;
        gameState.astma = data.astma;
        gameState.poharky = data.poharky;
        gameState.mrkev = data.mrkev;
        gameState.uzené = data.uzené;
        if (data.economy) {
            gameState.economy = data.economy;
        }
        
        updateResourcesOnly();
        updateEconomyPanel();
        closeMarketCalculator();
        setMarketMessage(data.message || 'Obchod dokončen.', false);
        
        // Refresh market rates
        await refreshMarketRates();
    } catch (error) {
        console.error('Error trading currencies:', error);
        setMarketMessage('Chyba spojení se serverem.', true);
    }
}

async function refreshMarketRates() {
    try {
        const response = await fetch('/api/currency-market');
        const data = await response.json();
        if (response.ok && data.success && data.economy) {
            gameState.economy = data.economy;
            updateEconomyPanel();
            setMarketMessage('Kurzy aktualizovány.', false);
        } else {
            setMarketMessage(data.error || 'Kurzy se nepodařilo načíst.', true);
        }
    } catch (error) {
        console.error('Error refreshing market:', error);
        setMarketMessage('Kurzy se nepodařilo načíst.', true);
    }
}

async function quickMarketTrade(currency, action, amount, event) {
    // Zastavit propagaci eventu, aby se neotevřela kalkulačka
    if (event) {
        event.stopPropagation();
    }
    
    let tradeAmount = amount;
    
    // Pokud je amount 'max', vypočítat maximum
    if (amount === 'max') {
        const currentGooncoins = gameState.gooncoins || 0;
        const currentCurrency = gameState[currency] || 0;
        const rates = gameState.economy?.market_rates?.[currency];
        
        if (!rates) {
            setMarketMessage('Kurzy nejsou k dispozici.', true);
            return;
        }
        
        if (action === 'buy') {
            // Maximum co můžeme koupit za dostupné gooncoiny
            tradeAmount = Math.floor(currentGooncoins / rates.buy * 1000) / 1000;
        } else {
            // Prodat všechno co máme
            tradeAmount = Math.floor(currentCurrency * 1000) / 1000;
        }
    }
    
    if (tradeAmount <= 0) {
        setMarketMessage('Nelze obchodovat s nulovým nebo záporným množstvím.', true);
        return;
    }
    
    try {
        const response = await fetch('/api/currency-market', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ currency, action, amount: tradeAmount })
        });
        
        const data = await response.json();
        if (!response.ok || !data.success) {
            setMarketMessage(data.error || 'Obchod se nezdařil.', true);
            return;
        }
        
        // Aktualizovat gameState - aktualizovat všechny zdroje z odpovědi
        if (data.gooncoins !== undefined) gameState.gooncoins = data.gooncoins;
        if (data.astma !== undefined) gameState.astma = data.astma;
        if (data.poharky !== undefined) gameState.poharky = data.poharky;
        if (data.mrkev !== undefined) gameState.mrkev = data.mrkev;
        if (data.uzené !== undefined) gameState.uzené = data.uzené;
        // Aktualizovat sekundární zdroje
        if (data.logs !== undefined) gameState.logs = data.logs;
        if (data.planks !== undefined) gameState.planks = data.planks;
        if (data.grain !== undefined) gameState.grain = data.grain;
        if (data.flour !== undefined) gameState.flour = data.flour;
        if (data.bread !== undefined) gameState.bread = data.bread;
        if (data.fish !== undefined) gameState.fish = data.fish;
        if (data.economy) {
            gameState.economy = data.economy;
        }
        
        updateResourcesOnly();
        updateEconomyPanel();
        renderMarketRates(gameState.economy?.market_rates);
        setMarketMessage(data.message || 'Obchod dokončen.', false);
    } catch (error) {
        console.error('Error trading currencies:', error);
        setMarketMessage('Chyba spojení se serverem.', true);
    }
}

function updateEconomyPanel() {
    const inflationRate = gameState.economy?.inflation_rate || 0;
    const supply = gameState.economy?.gooncoin_supply || 0;
    const multiplier = getInflationMultiplier();
    
    const rateEl = document.getElementById('inflationRate');
    const supplyEl = document.getElementById('gooncoinSupply');
    const multiplierEl = document.getElementById('inflationMultiplier');
    const trendEl = document.getElementById('inflationTrend');
    
    // Stats panel elements
    const statInflationEl = document.getElementById('statInflationRate');
    const statSupplyEl = document.getElementById('statTotalSupply');
    const statMultiplierEl = document.getElementById('statMultiplier');
    
    if (rateEl) rateEl.textContent = formatPercent(inflationRate);
    if (supplyEl) supplyEl.textContent = formatNumber(supply);
    if (multiplierEl) multiplierEl.textContent = `${multiplier.toFixed(2)}×`;
    
    if (statInflationEl) statInflationEl.textContent = formatPercent(inflationRate);
    if (statSupplyEl) statSupplyEl.textContent = formatNumber(supply);
    if (statMultiplierEl) statMultiplierEl.textContent = `${multiplier.toFixed(2)}×`;
    
    if (trendEl) {
        trendEl.classList.remove('trend-up', 'trend-down', 'trend-flat');
        if (inflationRate > lastInflationRate + 0.001) {
            trendEl.textContent = '↗';
            trendEl.classList.add('trend-up');
        } else if (inflationRate < lastInflationRate - 0.001) {
            trendEl.textContent = '↘';
            trendEl.classList.add('trend-down');
        } else {
            trendEl.textContent = '↔';
            trendEl.classList.add('trend-flat');
        }
        lastInflationRate = inflationRate;
    }
    
    renderMarketRates(gameState.economy?.market_rates);
    updateMarketCurrencyOptions();
    updateInflationReductionPreview();
    renderResourceOverview();
}

function updateInflationReductionPreview() {
    const amountInput = document.getElementById('inflationReductionAmount');
    const previewEl = document.getElementById('inflationReductionPreview');
    const messageEl = document.getElementById('inflationReductionMessage');
    
    if (!amountInput || !previewEl) return;
    
    const amount = parseFloat(amountInput.value) || 0;
    const currentInflation = gameState.economy?.inflation_rate || 0;
    const currentGooncoins = gameState.gooncoins || 0;
    
    if (amount < 1000) {
        previewEl.innerHTML = '<p class="muted">Zadej minimálně 1000 Gooncoinů</p>';
        return;
    }
    
    if (amount > currentGooncoins) {
        previewEl.innerHTML = `<p class="error">Nemáš dostatek Gooncoinů. Máš ${formatNumber(currentGooncoins)}</p>`;
        return;
    }
    
    // Calculate expected reduction (same formula as backend)
    const baseReduction = (amount / 10000) * 0.001;
    const inflationFactor = Math.max(1.0, currentInflation / 0.02);
    const expectedReduction = baseReduction * inflationFactor;
    const newInflation = Math.max(0.01, currentInflation - expectedReduction);
    const newMultiplier = 1 + (newInflation * 4);
    const currentMultiplier = 1 + (currentInflation * 4);
    
    previewEl.innerHTML = `
        <div class="preview-content">
            <p><strong>Očekávaný efekt:</strong></p>
            <p>Inflace: ${formatPercent(currentInflation)} → ${formatPercent(newInflation)}</p>
            <p>Snížení: ${formatPercent(expectedReduction)}</p>
            <p>Multiplikátor: ${currentMultiplier.toFixed(2)}× → ${newMultiplier.toFixed(2)}×</p>
        </div>
    `;
}

async function reduceInflation() {
    const amountInput = document.getElementById('inflationReductionAmount');
    const messageEl = document.getElementById('inflationReductionMessage');
    const button = document.getElementById('reduceInflationBtn');
    
    if (!amountInput || !button) return;
    
    const amount = parseFloat(amountInput.value) || 0;
    
    if (amount < 1000) {
        if (messageEl) {
            messageEl.textContent = 'Minimální investice je 1000 Gooncoinů';
            messageEl.className = 'inflation-message error';
        }
        return;
    }
    
    if (amount > (gameState.gooncoins || 0)) {
        if (messageEl) {
            messageEl.textContent = `Nemáš dostatek Gooncoinů. Máš ${formatNumber(gameState.gooncoins || 0)}`;
            messageEl.className = 'inflation-message error';
        }
        return;
    }
    
    button.disabled = true;
    button.textContent = 'Zpracovávám...';
    
    if (messageEl) {
        messageEl.textContent = '';
        messageEl.className = 'inflation-message';
    }
    
    try {
        const response = await fetch('/api/reduce-inflation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ amount: amount })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update game state
            gameState.gooncoins = data.gooncoins_remaining;
            gameState.economy = data.economy;
            
            // Show success message
            if (messageEl) {
                messageEl.textContent = data.message;
                messageEl.className = 'inflation-message success';
            }
            
            // Update display
            updateDisplay();
            
            // Clear input
            amountInput.value = '10000';
            updateInflationReductionPreview();
        } else {
            if (messageEl) {
                messageEl.textContent = data.error || 'Chyba při snižování inflace';
                messageEl.className = 'inflation-message error';
            }
        }
    } catch (error) {
        console.error('Error reducing inflation:', error);
        if (messageEl) {
            messageEl.textContent = 'Chyba připojení k serveru';
            messageEl.className = 'inflation-message error';
        }
    } finally {
        button.disabled = false;
        button.textContent = 'Snížit inflaci';
    }
}

function setupEconomyPanel() {
    const reduceBtn = document.getElementById('reduceInflationBtn');
    const amountInput = document.getElementById('inflationReductionAmount');
    
    if (reduceBtn) {
        reduceBtn.addEventListener('click', reduceInflation);
    }
    
    if (amountInput) {
        amountInput.addEventListener('input', updateInflationReductionPreview);
        amountInput.addEventListener('change', updateInflationReductionPreview);
    }
}

async function setupCases() {
    const openButton = document.getElementById('caseOpenButton');
    if (openButton) {
        openButton.addEventListener('click', openSelectedCase);
    }
    await loadCases();
}

async function loadCases() {
    const list = document.getElementById('caseList');
    if (!list) return;
    try {
        const response = await fetch('/api/cases');
        if (!response.ok) {
            list.innerHTML = '<p class="muted">Bedny se nepodařilo načíst.</p>';
            return;
        }
        const data = await response.json();
        caseDefinitions = data.cases || [];
        caseDefinitionMap = {};
        caseDefinitions.forEach(def => {
            caseDefinitionMap[def.id] = def;
        });
        if (!selectedCaseId && caseDefinitions.length) {
            selectedCaseId = caseDefinitions[0].id;
        } else if (selectedCaseId && !caseDefinitionMap[selectedCaseId] && caseDefinitions.length) {
            selectedCaseId = caseDefinitions[0].id;
        }
        caseHistoryEntries = data.history || [];
        renderCaseList();
        renderCaseDetail();
        renderCaseHistory();
        refreshCaseButtonState();
    } catch (error) {
        console.error('Error loading cases:', error);
        list.innerHTML = '<p class="muted">Bedny se nepodařilo načíst.</p>';
    }
}

function renderCaseList() {
    const list = document.getElementById('caseList');
    if (!list) return;
    if (!caseDefinitions.length) {
        list.innerHTML = '<p class="muted">Zatím tu není žádná bedna.</p>';
        return;
    }
    list.innerHTML = '';
    caseDefinitions.forEach(caseDef => {
        const card = document.createElement('button');
        card.type = 'button';
        card.className = `case-card ${caseDef.id === selectedCaseId ? 'active' : ''}`;
        card.innerHTML = `
            <div class="case-card-title">
                <span class="case-card-icon">${caseDef.icon || '🎁'}</span>
                <div>
                    <strong>${caseDef.name}</strong>
                    <p>${caseDef.tagline || caseDef.description || ''}</p>
                </div>
            </div>
            <div class="case-card-footer">
                <span class="case-card-price">${formatCasePriceLabel(caseDef)}</span>
            </div>
        `;
        card.addEventListener('click', () => {
            if (caseSpinInProgress) return;
            selectedCaseId = caseDef.id;
            renderCaseList();
            renderCaseDetail();
            refreshCaseButtonState();
        });
        list.appendChild(card);
    });
}

function renderCaseDetail() {
    const title = document.getElementById('caseDetailTitle');
    const description = document.getElementById('caseDetailDescription');
    const price = document.getElementById('caseDetailPrice');
    const itemsContainer = document.getElementById('caseItems');
    const caseDef = caseDefinitionMap[selectedCaseId];
    
    if (!title || !description || !price || !itemsContainer) {
        return;
    }
    
    if (!caseDef) {
        title.textContent = 'Vyber bednu';
        description.textContent = 'Klikni vlevo na jednu z beden a sleduj opening animaci.';
        price.textContent = '';
        itemsContainer.innerHTML = '<p class="muted">Drop tabulka se zobrazí po výběru bedny.</p>';
        primeCaseStrip(null);
        return;
    }
    
    title.textContent = caseDef.name;
    description.textContent = caseDef.description || caseDef.tagline || '';
    price.textContent = formatCasePriceLabel(caseDef);
    
    const items = (caseDef.items || []).slice();
    const totalWeight = items.reduce((sum, item) => sum + (item.weight || 1), 0) || 1;
    items.sort((a, b) => {
        const rarityDiff = getRarityIndex(b.rarity || 'common') - getRarityIndex(a.rarity || 'common');
        if (rarityDiff !== 0) return rarityDiff;
        return (b.weight || 0) - (a.weight || 0);
    });
    
    if (!items.length) {
        itemsContainer.innerHTML = '<p class="muted">Tahle bedna zatím nemá loot.</p>';
    } else {
        itemsContainer.innerHTML = '';
        items.forEach(item => {
            const entry = document.createElement('div');
            entry.className = `case-item-row rarity-${item.rarity || 'common'}`;
            const chance = ((item.weight || 0) / totalWeight) * 100;
            entry.innerHTML = `
                <div class="case-item-main">
                    <span class="case-item-icon">${item.icon || '🎁'}</span>
                    <div>
                        <strong>${item.name}</strong>
                        <p>${item.description || ''}</p>
                    </div>
                </div>
                <div class="case-item-meta">
                    <span>${getCaseRewardPreview(item)}</span>
                    <span class="case-item-chance">${chance.toFixed(1)}%</span>
                </div>
            `;
            itemsContainer.appendChild(entry);
        });
    }
    
    primeCaseStrip(caseDef);
}

function getCaseCurrencyIcon(currency) {
    return CASE_CURRENCY_ICONS[currency] || '💰';
}

function formatCasePriceLabel(caseDef) {
    const price = Number(caseDef?.price || 0);
    const currency = caseDef?.currency || 'gooncoins';
    const icon = getCaseCurrencyIcon(currency);
    if (price >= 1000) {
        return `${icon} ${formatNumber(price)}`;
    }
    return `${icon} ${Math.round(price).toLocaleString('cs-CZ')}`;
}

function getCaseRewardPreview(item = {}) {
    if (item.type === 'currency') {
        const entries = Object.entries(item.payout?.resources || {});
        if (entries.length) {
            const [currency, amount] = entries[0];
            return `+${formatNumber(amount)} ${RESOURCE_LABELS[currency] || currency}`;
        }
    } else if (item.type === 'equipment') {
        const equipmentId = item.payout?.equipment_id;
        const amount = item.payout?.amount || 1;
        const eqName = equipmentDefs[equipmentId]?.name || item.name || equipmentId;
        return `${amount}× ${eqName}`;
    } else if (item.type === 'rare_material') {
        const entries = Object.entries(item.payout?.rare_materials || {});
        if (entries.length) {
            const [matId, amount] = entries[0];
            const matName = rareMaterialDefs?.[matId]?.name || item.name || matId;
            return `${amount}× ${matName}`;
        }
    }
    return item.description || '';
}

function primeCaseStrip(caseDef) {
    const strip = document.getElementById('caseStrip');
    if (!strip) return;
    strip.style.transition = 'none';
    strip.style.transform = 'translateX(0)';
    if (!caseDef || !caseDef.items || !caseDef.items.length) {
        strip.innerHTML = '<div class="case-slot placeholder">Vyber bednu</div>';
        return;
    }
    const preview = caseDef.items.slice(0, 6);
    renderSpinStrip(preview);
}

function buildCaseSpinSequence(caseDef, forcedItem = null) {
    const items = caseDef?.items || [];
    if (!items.length) {
        return { sequence: [], targetIndex: 0 };
    }
    const pool = [];
    items.forEach(item => {
        const copies = Math.max(1, Math.round((item.weight || 1) / 5));
        for (let i = 0; i < copies; i += 1) {
            pool.push(item);
        }
    });
    if (!pool.length) {
        pool.push(items[0]);
    }
    const sequenceLength = 34;
    const sequence = [];
    for (let i = 0; i < sequenceLength; i += 1) {
        sequence.push(pool[Math.floor(Math.random() * pool.length)]);
    }
    const targetIndex = Math.floor(sequenceLength / 2);
    if (forcedItem) {
        sequence[targetIndex] = forcedItem;
    }
    return { sequence, targetIndex };
}

function renderSpinStrip(sequence = []) {
    const strip = document.getElementById('caseStrip');
    if (!strip) return;
    strip.innerHTML = '';
    if (!sequence.length) {
        strip.innerHTML = '<div class="case-slot placeholder">Vyber bednu</div>';
        return;
    }
    sequence.forEach(item => {
        const slot = document.createElement('div');
        slot.className = `case-slot rarity-${item?.rarity || 'common'}`;
        slot.innerHTML = `
            <div class="case-slot-icon">${item?.icon || '🎁'}</div>
            <div class="case-slot-name">${item?.name || ''}</div>
        `;
        strip.appendChild(slot);
    });
}

function animateCaseSpin(caseDef, rewardSummary) {
    if (caseSpinTimeout) {
        clearTimeout(caseSpinTimeout);
    }
    const strip = document.getElementById('caseStrip');
    if (!strip || !caseDef) return;
    const winningItem = caseDef.items?.find(item => item.id === rewardSummary?.id) || rewardSummary || null;
    const sequenceData = buildCaseSpinSequence(caseDef, winningItem);
    renderSpinStrip(sequenceData.sequence);
    const viewport = strip.parentElement;
    const viewportWidth = viewport ? viewport.offsetWidth : 600;
    const targetOffset = (sequenceData.targetIndex * CASE_SLOT_WIDTH) + (CASE_SLOT_WIDTH / 2);
    const translate = Math.max(0, targetOffset - (viewportWidth / 2));
    strip.style.transition = 'none';
    strip.style.transform = 'translateX(0)';
    requestAnimationFrame(() => {
        strip.style.transition = `transform ${CASE_SPIN_DURATION}ms cubic-bezier(.15,.63,.25,1)`;
        strip.style.transform = `translateX(-${translate}px)`;
    });
}

function renderCaseHistory() {
    const container = document.getElementById('caseHistoryList');
    if (!container) return;
    if (!caseHistoryEntries.length) {
        container.innerHTML = '<p class="muted">Zatím žádné otevření bedny.</p>';
        return;
    }
    container.innerHTML = '';
    caseHistoryEntries.forEach(entry => {
        const row = document.createElement('div');
        row.className = `case-history-item rarity-${entry.rarity || 'common'}`;
        row.innerHTML = `
            <div>
                <strong>${entry.reward_label}</strong>
                <p>${entry.case_name || ''}</p>
            </div>
            <span class="case-history-time">${formatCaseHistoryTime(entry.created_at)}</span>
        `;
        container.appendChild(row);
    });
}

function formatCaseHistoryTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }
    return date.toLocaleTimeString('cs-CZ', { hour: '2-digit', minute: '2-digit' });
}

function refreshCaseButtonState() {
    const button = document.getElementById('caseOpenButton');
    if (!button) return;
    const caseDef = caseDefinitionMap[selectedCaseId];
    if (!caseDef) {
        button.disabled = true;
        button.textContent = 'Vyber bednu';
        return;
    }
    if (caseSpinInProgress) {
        button.disabled = true;
        button.textContent = 'Točím...';
        return;
    }
    button.textContent = `Otevřít (${formatCasePriceLabel(caseDef)})`;
    const currency = caseDef.currency || 'gooncoins';
    const balance = (gameState && gameState[currency]) || 0;
    button.disabled = balance < (caseDef.price || 0);
}

function setCaseResultMessage(message, isError = false) {
    const result = document.getElementById('caseResult');
    if (!result) return;
    result.textContent = message;
    result.classList.toggle('error', !!isError);
    result.classList.toggle('success', !isError);
}

async function openSelectedCase() {
    const caseDef = caseDefinitionMap[selectedCaseId];
    if (!caseDef || caseSpinInProgress) {
        return;
    }
    setCaseResultMessage('Roztáčím bednu...', false);
    caseSpinInProgress = true;
    refreshCaseButtonState();
    
    try {
        const response = await fetch('/api/cases/open', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: caseDef.id })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            setCaseResultMessage(data.error || 'Bednu se nepodařilo otevřít.', true);
            caseSpinInProgress = false;
            refreshCaseButtonState();
            return;
        }
        
        gameState.gooncoins = data.gooncoins;
        gameState.astma = data.astma;
        gameState.poharky = data.poharky;
        gameState.mrkev = data.mrkev;
        gameState.uzené = data.uzené;
        if (data.equipment_counts) {
            gameState.equipmentCounts = data.equipment_counts;
        }
        if (data.rare_materials) {
            gameState.rareMaterials = data.rare_materials;
        }
        caseHistoryEntries = data.history || caseHistoryEntries;
        renderCaseHistory();
        updateResourcesOnly();
        
        animateCaseSpin(caseDef, data.reward);
        caseSpinTimeout = setTimeout(() => {
            setCaseResultMessage(describeCaseReward(data.reward), false);
            caseSpinInProgress = false;
            refreshCaseButtonState();
        }, CASE_SPIN_DURATION);
    } catch (error) {
        console.error('Error opening case:', error);
        setCaseResultMessage('Chyba připojení k serveru.', true);
        caseSpinInProgress = false;
        refreshCaseButtonState();
    }
}

function describeCaseReward(reward) {
    if (!reward) {
        return 'Bedna neobsahovala žádný drop.';
    }
    if (reward.type === 'currency') {
        const entries = Object.entries(reward.resources || reward.payout?.resources || {});
        if (entries.length) {
            const [currency, amount] = entries[0];
            return `Padlo ${formatNumber(amount)} ${RESOURCE_LABELS[currency] || currency}!`;
        }
    } else if (reward.type === 'equipment') {
        const eqName = reward.equipment?.name || reward.name;
        const amount = reward.equipment?.amount || 1;
        return `Drop: ${amount}× ${eqName}`;
    } else if (reward.type === 'rare_material') {
        const entries = Object.entries(reward.rare_materials || reward.payout?.rare_materials || {});
        if (entries.length) {
            const [matId, amount] = entries[0];
            const matName = rareMaterialDefs?.[matId]?.name || reward.name || matId;
            return `Získal jsi ${amount}× ${matName}`;
        }
    }
    return reward.name || 'Padl tajemný loot';
}

function renderMarketRates(rates = {}) {
    const container = document.getElementById('marketRates');
    if (!container) return;
    
    container.innerHTML = '';
    const entries = Object.entries(rates);
    if (entries.length === 0) {
        container.innerHTML = '<p class="muted">Tržní data nejsou dostupná.</p>';
        return;
    }
    
    const unlocked = new Set(gameState.story?.unlocked_currencies || []);
    
    // Seřadit podle odemčených a pak podle názvu
    const sortedEntries = entries.sort((a, b) => {
        const aUnlocked = unlocked.has(a[0]);
        const bUnlocked = unlocked.has(b[0]);
        if (aUnlocked !== bUnlocked) {
            return aUnlocked ? -1 : 1;
        }
        return getCurrencyLabel(a[0]).localeCompare(getCurrencyLabel(b[0]));
    });
    
    sortedEntries.forEach(([currency, data]) => {
        const row = document.createElement('div');
        const isUnlocked = unlocked.has(currency);
        const spread = ((data.buy - data.sell) / data.sell * 100).toFixed(1);
        row.className = `market-rate-row ${isUnlocked ? 'clickable' : 'locked'}`;
        
        // Přidat event listener pro otevření kalkulačky (pouze pokud není klik na tlačítko)
        if (isUnlocked) {
            row.addEventListener('click', (e) => {
                // Pokud klik není na tlačítko nebo jeho rodiče, otevři kalkulačku
                if (!e.target.closest('.market-quick-actions')) {
                    openMarketCalculator(currency, data);
                }
            });
        }
        
        const currentAmount = gameState[currency] || 0;
        const currentGooncoins = gameState.gooncoins || 0;
        const maxBuy = Math.floor(currentGooncoins / data.buy * 1000) / 1000;
        
        row.innerHTML = `
            <div class="market-rate-label">
                <span class="resource-icon">${getResourceIcon(currency)}</span>
                <div>
                    <strong>${getCurrencyLabel(currency)}</strong>
                    ${!isUnlocked ? '<small>🔒 Odemkni v příběhu</small>' : `<small>Spread: ${spread}%</small>`}
                </div>
            </div>
            <div class="market-rate-values">
                <span>📈 Koupě: ${data.buy.toFixed(2)} 💰</span>
                <span>📉 Prodej: ${data.sell.toFixed(2)} 💰</span>
            </div>
            ${isUnlocked ? `
            <div class="market-quick-actions" onclick="event.stopPropagation()">
                <div class="market-quick-buy">
                    <button class="market-quick-btn market-quick-btn-buy" 
                            onclick="quickMarketTrade('${currency}', 'buy', 1, event)" 
                            title="Koupit 1">+1</button>
                    <button class="market-quick-btn market-quick-btn-buy" 
                            onclick="quickMarketTrade('${currency}', 'buy', 10, event)" 
                            title="Koupit 10">+10</button>
                    <button class="market-quick-btn market-quick-btn-buy" 
                            onclick="quickMarketTrade('${currency}', 'buy', 100, event)" 
                            title="Koupit 100">+100</button>
                    <button class="market-quick-btn market-quick-btn-buy market-quick-btn-max" 
                            onclick="quickMarketTrade('${currency}', 'buy', 'max', event)" 
                            title="Koupit maximum">MAX</button>
                </div>
                <div class="market-quick-sell">
                    <button class="market-quick-btn market-quick-btn-sell" 
                            onclick="quickMarketTrade('${currency}', 'sell', 1, event)" 
                            ${currentAmount < 1 ? 'disabled' : ''} 
                            title="Prodat 1">-1</button>
                    <button class="market-quick-btn market-quick-btn-sell" 
                            onclick="quickMarketTrade('${currency}', 'sell', 10, event)" 
                            ${currentAmount < 10 ? 'disabled' : ''} 
                            title="Prodat 10">-10</button>
                    <button class="market-quick-btn market-quick-btn-sell" 
                            onclick="quickMarketTrade('${currency}', 'sell', 100, event)" 
                            ${currentAmount < 100 ? 'disabled' : ''} 
                            title="Prodat 100">-100</button>
                    <button class="market-quick-btn market-quick-btn-sell market-quick-btn-max" 
                            onclick="quickMarketTrade('${currency}', 'sell', 'max', event)" 
                            ${currentAmount <= 0 ? 'disabled' : ''} 
                            title="Prodat vše">ALL</button>
                </div>
            </div>
            ` : ''}
        `;
        container.appendChild(row);
    });
}

function updateMarketCurrencyOptions() {
    const select = document.getElementById('marketCurrency');
    const unlocked = new Set(gameState.story?.unlocked_currencies || []);
    const buttons = document.querySelectorAll('.market-buttons button');
    const hasMarket = (gameState.buildings?.market || 0) > 0;
    
    if (!select) return;
    
    if (!hasMarket) {
        Array.from(select.options).forEach(option => option.disabled = true);
        buttons.forEach(btn => btn.disabled = true);
        setMarketMessage('Postav Tržiště, aby ses dostal na měnový trh.', true);
        return;
    }
    
    // Aktualizovat texty optionů s ikonkami
    Array.from(select.options).forEach(option => {
        const currency = option.value;
        const icon = getResourceIcon(currency);
        const label = getCurrencyLabel(currency);
        option.textContent = `${icon} ${label}`;
    });
    
    let hasUnlocked = false;
    Array.from(select.options).forEach(option => {
        const isUnlocked = unlocked.has(option.value);
        option.disabled = !isUnlocked;
        if (!isUnlocked) {
            const currency = option.value;
            const icon = getResourceIcon(currency);
            const label = getCurrencyLabel(currency);
            option.textContent = `🔒 ${icon} ${label}`;
        }
        if (isUnlocked && !hasUnlocked) {
            hasUnlocked = true;
        }
    });
    
    if (!hasUnlocked) {
        Array.from(select.options).forEach(option => option.disabled = true);
    } else if (select.selectedOptions.length === 0 || select.selectedOptions[0].disabled) {
        const available = Array.from(select.options).find(opt => !opt.disabled);
        if (available) available.selected = true;
    }
    
    buttons.forEach(btn => {
        btn.disabled = !hasUnlocked;
    });
}

function renderResourceOverview() {
    const container = document.getElementById('resourceOverview');
    if (!container) return;
    
    const rates = getEffectiveGenerationRates();
    const buildings = gameState.buildings || {};
    const unlocked = new Set(gameState.story?.unlocked_currencies || []);
    
    // Primary resources from upgrades
    const upgradeSources = {
        'gooncoins': 'auto_gooncoin',
        'astma': 'auto_astma',
        'poharky': 'auto_poharky',
        'mrkev': 'auto_mrkev',
        'uzené': 'auto_uzené'
    };
    
    // Secondary resources from buildings
    const buildingOutputs = {};
    for (const [buildingId, def] of Object.entries(buildingsDefs)) {
        const logistics = def.logistics;
        if (logistics && logistics.outputs) {
            for (const [resource, amount] of Object.entries(logistics.outputs)) {
                if (!buildingOutputs[resource]) {
                    buildingOutputs[resource] = [];
                }
                buildingOutputs[resource].push({
                    buildingId: buildingId,
                    buildingName: def.name,
                    isBuilt: (buildings[buildingId] || 0) > 0
                });
            }
        }
    }
    
    // All resources
    const allResources = [
        { key: 'gooncoins', label: 'Gooncoiny', icon: '💰' },
        { key: 'astma', label: 'Astma', icon: '💨' },
        { key: 'poharky', label: 'Pohárky', icon: '🥃' },
        { key: 'mrkev', label: 'Mrkev', icon: '🥕' },
        { key: 'uzené', label: 'Uzené', icon: '🍖' },
        { key: 'logs', label: 'Klády', icon: '🪵' },
        { key: 'planks', label: 'Prkna', icon: '🪚' },
        { key: 'grain', label: 'Obilí', icon: '🌾' },
        { key: 'flour', label: 'Mouka', icon: '🧯' },
        { key: 'bread', label: 'Chleba', icon: '🍞' },
        { key: 'fish', label: 'Ryby', icon: '🐟' }
    ];
    
    container.innerHTML = '';
    
    allResources.forEach(resource => {
        const sources = [];
        const isUnlocked = unlocked.has(resource.key) || resource.key === 'gooncoins';
        
        // Check upgrade source
        const upgradeKey = upgradeSources[resource.key];
        if (upgradeKey) {
            const level = gameState.upgrades?.[upgradeKey] || 0;
            if (level > 0) {
                const upgradeDef = autoGeneratorBlueprints[upgradeKey];
                sources.push({
                    type: 'upgrade',
                    name: upgradeDef?.flavor || `Upgrade ${upgradeKey}`,
                    level: level,
                    rate: upgradeDef?.ratePerLevel * level || 0
                });
            }
        }
        
        // Check building sources
        if (buildingOutputs[resource.key]) {
            buildingOutputs[resource.key].forEach(source => {
                sources.push({
                    type: 'building',
                    name: source.buildingName,
                    buildingId: source.buildingId,
                    isBuilt: source.isBuilt
                });
            });
        }
        
        const currentAmount = gameState[resource.key] || 0;
        const generationRate = rates[resource.key] || 0;
        
        const row = document.createElement('div');
        row.className = `resource-overview-item ${isUnlocked ? '' : 'locked'}`;
        
        let sourcesHtml = '';
        if (sources.length > 0) {
            sourcesHtml = '<div class="resource-sources">';
            sources.forEach(source => {
                if (source.type === 'upgrade') {
                    sourcesHtml += `<span class="source-tag source-upgrade" title="Upgrade level ${source.level}">⚙️ ${source.name} (${source.level})</span>`;
                } else if (source.type === 'building') {
                    const status = source.isBuilt ? '✅' : '❌';
                    sourcesHtml += `<span class="source-tag source-building ${source.isBuilt ? 'built' : 'not-built'}" title="${source.isBuilt ? 'Postaveno' : 'Nepostaveno'}">${status} ${source.name}</span>`;
                }
            });
            sourcesHtml += '</div>';
        } else {
            sourcesHtml = '<div class="resource-sources"><span class="muted">Žádný zdroj</span></div>';
        }
        
        row.innerHTML = `
            <div class="resource-overview-item-header">
                <div class="resource-overview-icon">${resource.icon}</div>
                <div class="resource-overview-info">
                    <strong>${resource.label}</strong>
                    ${!isUnlocked ? '<small class="locked-badge">🔒 Zamčeno</small>' : ''}
                </div>
                <div class="resource-overview-values">
                    <span class="resource-amount">${formatNumber(currentAmount)}</span>
                    ${generationRate > 0 ? `<span class="resource-rate">+${formatNumber(generationRate)}/s</span>` : ''}
                </div>
            </div>
            ${sourcesHtml}
        `;
        
        container.appendChild(row);
    });
}

// Combat hub
function setupCombat() {
    const opponentsList = document.getElementById('opponentsList');
    if (opponentsList) {
        opponentsList.addEventListener('click', event => {
            const button = event.target.closest('.pvp-challenge-btn');
            if (button && button.dataset.opponent) {
                handlePvpBattle(button.dataset.opponent);
            }
        });
    }
    
    const campaignList = document.getElementById('campaignMonstersList');
    if (campaignList) {
        campaignList.addEventListener('click', event => {
            const button = event.target.closest('.campaign-fight-btn');
            if (button && !button.disabled) {
                handleCampaignBattle(button.dataset.monster);
            }
        });
    }
    
    const fightButton = document.getElementById('campaignFightButton');
    if (fightButton) {
        fightButton.addEventListener('click', () => {
            if (!fightButton.dataset.monster) {
                setCombatMessage('Vyber monstrum, které chceš napadnout.', true);
                return;
            }
            handleCampaignBattle(fightButton.dataset.monster);
        });
    }
    
    loadCombatOverview();
    if (!combatRefreshTimer) {
        combatRefreshTimer = setInterval(() => {
            const combatTab = document.getElementById('combat-tab');
            if (combatTab && combatTab.classList.contains('active')) {
                loadCombatOverview();
            }
        }, 7000);
    }
}

async function loadCombatOverview() {
    try {
        const response = await fetch('/api/combat/overview');
        if (!response.ok) return;
        const data = await response.json();
        if (!data.success) {
            setCombatMessage(data.error || 'Bojové informace se nepodařilo načíst.', true);
            return;
        }
        combatOverview = data;
        rareMaterialDefs = data.rare_material_defs || rareMaterialDefs;
        gameState.rareMaterials = data.rare_materials || gameState.rareMaterials;
        gameState.combat = data.profile || gameState.combat;
        renderCombatPanels();
    } catch (error) {
        console.error('Error loading combat overview:', error);
    }
}

function renderCombatPanels() {
    if (!combatOverview) return;
    renderPlayerCombatStats(combatOverview.player_stats, gameState.combat);
    renderRareMaterials(gameState.rareMaterials);
    renderOpponents(combatOverview.pvp?.opponents || []);
    renderCampaign(combatOverview.campaign);
    renderCombatLogs(combatOverview.pvp?.recent_logs || []);
}

function renderPlayerCombatStats(stats, profile = {}) {
    const container = document.getElementById('playerCombatStats');
    if (!container || !stats) return;
    container.innerHTML = `
        <div class="combat-stat-line">
            <span>⚖️ Rating</span>
            <strong>${Math.round(profile.rating || 1000)}</strong>
        </div>
        <div class="combat-stat-grid">
            <div class="stat-box stat-strength">
                <span>⚔️⚔️ Síla</span>
                <strong>${stats.attack.toFixed(1)}</strong>
            </div>
            <div class="stat-box stat-defense">
                <span>🛡️ Obrana</span>
                <strong>${stats.defense.toFixed(1)}</strong>
            </div>
            <div class="stat-box stat-luck">
                <span>🌙⭐ Štěstí</span>
                <strong>${stats.luck.toFixed(2)}</strong>
            </div>
            <div class="stat-box stat-stamina">
                <span>💗 Výdrž</span>
                <strong>${formatNumber(stats.hp)}</strong>
            </div>
        </div>
        <div class="combat-stat-meta">
            <span>Výhry: ${profile.wins || 0}</span>
            <span>Prohry: ${profile.losses || 0}</span>
        </div>
    `;
}

function renderRareMaterials(materials = {}) {
    const container = document.getElementById('rareMaterialList');
    if (!container) return;
    const defs = Object.keys(rareMaterialDefs || {}).length ? rareMaterialDefs : {
        mrkvovy_totem: { name: 'Mrkvový Totem', icon: '🥕' },
        kiki_oko: { name: 'Kikiho Oko', icon: '👁️' },
        vaclava_ampule: { name: 'Ampule Václava', icon: '💧' },
        roza_trn: { name: 'Rózin Trn', icon: '🌹' },
        jitka_manifest: { name: 'Manifest Jitky', icon: '📜' }
    };
    container.innerHTML = '';
    Object.entries(defs).forEach(([key, meta]) => {
        const value = materials[key] || 0;
        const card = document.createElement('div');
        card.className = 'rare-material-card';
        card.innerHTML = `
            <div class="rare-icon">${meta.icon || '✨'}</div>
            <div class="rare-info">
                <strong>${meta.name || key}</strong>
                <span>${value >= 1000 ? formatNumber(value) : Math.round(value)}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderOpponents(opponents = []) {
    const container = document.getElementById('opponentsList');
    if (!container) return;
    if (!opponents.length) {
        container.innerHTML = '<p class="muted">Žádní relevantní protivníci.</p>';
        return;
    }
    container.innerHTML = opponents.map(opponent => `
        <div class="opponent-card">
            <div class="opponent-header">
                <div>
                    <strong>${opponent.username}</strong>
                    <span class="opponent-rating">Rating ${Math.round(opponent.rating || 0)}</span>
                </div>
                <span>${opponent.wins}W / ${opponent.losses}L</span>
            </div>
            <div class="opponent-stats">
                <span>⚔ ${opponent.attack.toFixed(1)}</span>
                <span>🛡 ${opponent.defense.toFixed(1)}</span>
                <span>💫 ${opponent.luck.toFixed(2)}</span>
                <span>❤️ ${formatNumber(opponent.hp)}</span>
            </div>
            <button class="btn-blue pvp-challenge-btn" data-opponent="${opponent.username}">
                Vyzyvat
            </button>
        </div>
    `).join('');
}

function renderCampaign(campaign) {
    const list = document.getElementById('campaignMonstersList');
    const primaryButton = document.getElementById('campaignFightButton');
    if (!list || !campaign) return;
    
    list.innerHTML = '';
    const statusLabels = {
        next: 'Další cíl',
        repeatable: 'Farmení',
        defeated: 'Porazeno',
        locked: 'Zamčeno'
    };
    
    (campaign.monsters || []).forEach(monster => {
        const rewards = monster.rewards || {};
        const rareRewards = rewards.rare_materials || {};
        const rareText = Object.entries(rareRewards).map(([key, amount]) => {
            const meta = (rareMaterialDefs && rareMaterialDefs[key]) || {};
            return `${meta.icon || '✨'} ${meta.name || key} ×${amount}`;
        }).join(', ');
        const rewardLine = [
            rewards.gooncoins ? `+${formatNumber(rewards.gooncoins)} 💰` : '',
            rareText
        ].filter(Boolean).join(' · ');
        const canFight = monster.status !== 'locked';
        list.innerHTML += `
            <div class="campaign-monster-card status-${monster.status}">
                <div class="monster-row">
                    <div>
                        <strong>${monster.name}</strong>
                        <span class="monster-tier">Tier ${monster.tier}</span>
                    </div>
                    <span class="monster-status">${statusLabels[monster.status] || ''}</span>
                </div>
                <p class="monster-description">${monster.description}</p>
                <div class="monster-rewards">${rewardLine || 'Žádné speciální odměny'}</div>
                <button class="btn-green campaign-fight-btn" data-monster="${monster.id}" ${canFight ? '' : 'disabled'}>
                    ${monster.status === 'next' ? 'Bojovat' : monster.status === 'repeatable' ? 'Farmit' : 'Zamčeno'}
                </button>
            </div>
        `;
    });
    
    if (primaryButton) {
        if (campaign.next_monster) {
            primaryButton.disabled = false;
            primaryButton.dataset.monster = campaign.next_monster.id;
            primaryButton.textContent = `Zaútočit na ${campaign.next_monster.name}`;
        } else {
            primaryButton.disabled = true;
            primaryButton.dataset.monster = '';
            primaryButton.textContent = 'Žádné dostupné monstra';
        }
    }
}

function renderCombatLogs(logs = []) {
    const container = document.getElementById('combatLogs');
    if (!container) return;
    if (!logs.length) {
        container.innerHTML = '<p class="muted">Zatím žádné boje.</p>';
        return;
    }
    const playerId = combatOverview?.player_id;
    container.innerHTML = '';
    logs.forEach(log => {
        const isWin = playerId && log.winner_id && log.winner_id === playerId;
        const hasWinner = Boolean(log.winner_id);
        const modeLabel = log.mode === 'campaign'
            ? 'Kampaň'
            : log.mode === 'temple'
                ? 'Chrám'
                : 'PvP';
        const monsterName = log.summary?.monster ? getMonsterNameById(log.summary.monster) : null;
        let opponentName;
        if (log.mode === 'campaign') {
            opponentName = monsterName || 'Monstrum';
        } else if (log.mode === 'temple') {
            opponentName = log.summary?.enemy_name || 'Chrám';
        } else {
            opponentName = log.attacker?.username === currentUsername
                ? (log.defender?.username || '???')
                : (log.attacker?.username || '???');
        }
        const entry = document.createElement('div');
        entry.className = `combat-log ${isWin ? 'log-win' : hasWinner ? 'log-loss' : 'log-draw'}`;
        entry.innerHTML = `
            <div class="combat-log-header">
                <span>${modeLabel}</span>
                <span>${new Date(log.created_at).toLocaleString('cs-CZ')}</span>
            </div>
            <p>${opponentName ? `Souboj s ${opponentName}` : 'Souboj bez záznamu jména'}</p>
            <strong>${isWin ? 'Výhra' : hasWinner ? 'Prohra' : 'Remíza'}</strong>
        `;
        container.appendChild(entry);
    });
}

function getMonsterNameById(monsterId) {
    const monsters = combatOverview?.campaign?.monsters || [];
    const match = monsters.find(monster => monster.id === monsterId);
    return match ? match.name : monsterId;
}

async function handlePvpBattle(username) {
    if (!username) return;
    setCombatMessage(`Útočím na ${username}...`, false);
    try {
        const response = await fetch('/api/combat/pvp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ opponent: username })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setCombatMessage(data.error || 'Souboj se nezdařil.', true);
            return;
        }
        if (typeof data.gooncoins === 'number') {
            gameState.gooncoins = data.gooncoins;
            updateResourcesOnly();
        }
        await loadCombatOverview();
        playCombatAnimation(data.battle, {
            playerLabel: 'Ty',
            enemyLabel: data.opponent || username,
            playerStats: data.attacker_stats,
            enemyStats: data.defender_stats
        });
        const rewardText = data.player_won && data.reward ? ` +${formatNumber(data.reward)} 💰` : '';
        setCombatMessage(data.player_won ? `Vyhrál jsi souboj!${rewardText}` : 'Souboj skončil porážkou.', !data.player_won);
    } catch (error) {
        console.error('Error launching PvP battle:', error);
        setCombatMessage('Souboj se nepodařilo odehrát.', true);
    }
}

async function handleCampaignBattle(monsterId) {
    if (!monsterId) {
        setCombatMessage('Vyber monstrum, které chceš napadnout.', true);
        return;
    }
    setCombatMessage('Probíhá kampaňový boj...', false);
    try {
        const response = await fetch('/api/combat/campaign-battle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ monster_id: monsterId })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setCombatMessage(data.error || 'Kampaňový boj selhal.', true);
            return;
        }
        if (typeof data.gooncoins === 'number') {
            gameState.gooncoins = data.gooncoins;
            updateResourcesOnly();
        }
        if (data.rare_materials) {
            gameState.rareMaterials = data.rare_materials;
        }
        if (data.campaign) {
            gameState.combat.campaign_stage = data.campaign.stage;
        }
        await loadCombatOverview();
        const monsterName = getMonsterNameById(monsterId);
        playCombatAnimation(data.battle, {
            playerLabel: 'Ty',
            enemyLabel: data.monster_name || monsterName,
            playerStats: data.player_stats,
            enemyStats: data.monster_stats
        });
        const rewardParts = [];
        if (data.rewards?.gooncoins) {
            rewardParts.push(`+${formatNumber(data.rewards.gooncoins)} 💰`);
        }
        if (data.rewards?.rare_materials) {
            Object.entries(data.rewards.rare_materials).forEach(([key, amount]) => {
                const meta = rareMaterialDefs[key] || {};
                rewardParts.push(`${meta.icon || '✨'} ${meta.name || key} ×${amount}`);
            });
        }
        const rewardText = rewardParts.length ? ` (${rewardParts.join(', ')})` : '';
        setCombatMessage(
            data.player_won ? `Porazil jsi ${monsterName}!${rewardText}` : `Monstrum ${monsterName} tě přemohlo.`,
            !data.player_won
        );
    } catch (error) {
        console.error('Error launching campaign battle:', error);
        setCombatMessage('Souboj s monstrem selhal.', true);
    }
}

function setCombatMessage(message = '', isError = false) {
    const box = document.getElementById('combatMessage');
    if (!box) return;
    box.textContent = message;
    box.classList.remove('error', 'success');
    if (!message) {
        return;
    }
    box.classList.add(isError ? 'error' : 'success');
    if (combatMessageTimer) {
        clearTimeout(combatMessageTimer);
    }
    combatMessageTimer = setTimeout(() => {
        box.textContent = '';
        box.classList.remove('error', 'success');
    }, 5000);
}

function setupTempleSection() {
    const rooms = document.getElementById('templeRooms');
    if (rooms) {
        rooms.addEventListener('click', event => {
            const button = event.target.closest('.temple-fight-btn');
            if (button && button.dataset.room) {
                handleTempleFight(button.dataset.room);
            }
        });
    }
    const blessings = document.getElementById('templeBlessings');
    if (blessings) {
        blessings.addEventListener('click', event => {
            const button = event.target.closest('.temple-blessing-btn');
            if (button && button.dataset.blessing) {
                handleTempleRitual(button.dataset.blessing);
            }
        });
    }
    loadTempleStatus();
    if (!templeRefreshTimer) {
        templeRefreshTimer = setInterval(() => {
            const combatTab = document.getElementById('combat-tab');
            if (combatTab && combatTab.classList.contains('active')) {
                loadTempleStatus();
            }
        }, 9000);
    }
}

async function loadTempleStatus() {
    try {
        const response = await fetch('/api/temple/status');
        if (!response.ok) return;
        const data = await response.json();
        if (!data.success) return;
        templeSnapshot = data.temple;
        gameState.temple = data.temple;
        renderTempleSection();
    } catch (error) {
        console.error('Error loading temple status:', error);
    }
}

function renderTempleSection() {
    const favorEl = document.getElementById('templeFavorValue');
    const blessingStatusEl = document.getElementById('templeBlessingStatus');
    const roomsContainer = document.getElementById('templeRooms');
    const blessingsContainer = document.getElementById('templeBlessings');
    const cooldownEl = document.getElementById('templeCooldown');
    
    if (!roomsContainer || !blessingsContainer || !favorEl || !blessingStatusEl || !cooldownEl) {
        return;
    }
    
    if (!templeSnapshot || !templeSnapshot.unlocked) {
        favorEl.textContent = '0';
        blessingStatusEl.textContent = 'Postav Chrám';
        cooldownEl.textContent = '–';
        roomsContainer.innerHTML = '<p class="muted">Postav Chrám, aby se místnosti odemkly.</p>';
        blessingsContainer.innerHTML = '<p class="muted">Chrámové požehnání budou dostupná po stavbě Chrámu.</p>';
        return;
    }
    
    favorEl.textContent = formatNumber(templeSnapshot.favor || 0);
    if (templeSnapshot.active_blessing) {
        const minutes = Math.max(1, Math.ceil((templeSnapshot.active_blessing.expires_in || 0) / 60));
        blessingStatusEl.textContent = `${templeSnapshot.active_blessing.name} (${minutes} min)`;
    } else {
        blessingStatusEl.textContent = 'Žádné';
    }
    
    updateTempleCooldown(templeSnapshot.cooldown_seconds || 0);
    renderTempleRooms(templeSnapshot.rooms || []);
    renderTempleBlessings(templeSnapshot.blessings || []);
}

function updateTempleCooldown(seconds) {
    const cooldownEl = document.getElementById('templeCooldown');
    if (!cooldownEl) return;
    if (templeCooldownInterval) {
        clearInterval(templeCooldownInterval);
        templeCooldownInterval = null;
    }
    if (!seconds || seconds <= 0) {
        cooldownEl.textContent = 'Volno';
        return;
    }
    let remaining = seconds;
    const tick = () => {
        if (remaining <= 0) {
            cooldownEl.textContent = 'Volno';
            clearInterval(templeCooldownInterval);
            templeCooldownInterval = null;
            return;
        }
        const minutes = Math.floor(remaining / 60);
        const secs = remaining % 60;
        cooldownEl.textContent = `${minutes}:${secs.toString().padStart(2, '0')}`;
        remaining -= 1;
    };
    tick();
    templeCooldownInterval = setInterval(tick, 1000);
}

function renderTempleRooms(rooms = []) {
    const container = document.getElementById('templeRooms');
    if (!container) return;
    if (!rooms.length) {
        container.innerHTML = '<p class="muted">Chrám se probouzí...</p>';
        return;
    }
    const cooldownActive = (templeSnapshot?.cooldown_seconds || 0) > 0;
    const statusLabels = {
        active: 'Aktivní',
        available: 'Připraveno',
        cleared: 'Dokončeno',
        locked: 'Zamčeno'
    };
    container.innerHTML = rooms.map(room => {
        const progress = room.required_kills ? Math.min(100, (room.kills / room.required_kills) * 100) : 0;
        const rewardParts = [];
        if (room.boss_rewards?.gooncoins) {
            rewardParts.push(`+${formatNumber(room.boss_rewards.gooncoins)} ${getResourceIcon('gooncoins')}`);
        }
        if (room.boss_rewards?.favor) {
            rewardParts.push(`+${room.boss_rewards.favor} ${getResourceIcon('favor')}`);
        }
        if (room.boss_rewards?.rare_materials) {
            Object.entries(room.boss_rewards.rare_materials).forEach(([key, value]) => {
                const meta = rareMaterialDefs[key] || { name: key, icon: '✨' };
                rewardParts.push(`${meta.icon || '✨'} ${meta.name || key} ×${value}`);
            });
        }
        const disabled = !room.unlocked || cooldownActive;
        const buttonLabel = !room.unlocked
            ? 'Zamčeno'
            : room.boss_ready
                ? 'Boj s bossem'
                : 'Souboj';
        return `
            <div class="temple-room-card status-${room.status}">
                <div class="temple-room-meta">
                    <div>
                        <strong>${room.name}</strong>
                        <small>${statusLabels[room.status] || ''}</small>
                    </div>
                    <span>Boss: ${room.boss_name}</span>
                </div>
                <p class="muted">${room.description}</p>
                <div class="temple-progress">
                    <div class="temple-progress-fill" style="width: ${progress}%"></div>
                </div>
                <small>${room.kills} / ${room.required_kills} nepřátel ${room.boss_ready ? '· Boss připraven' : ''}</small>
                <small class="muted">Nepřátelé: ${Array.isArray(room.enemy_preview) && room.enemy_preview.length ? room.enemy_preview.join(', ') : '???'}</small>
                <div class="temple-rewards-line">
                    <strong>Odměna bosse:</strong> ${rewardParts.join(' · ') || 'Neznámá'}
                </div>
                <button class="btn-green temple-fight-btn" data-room="${room.id}" ${disabled ? 'disabled' : ''}>
                    ${buttonLabel}
                </button>
            </div>
        `;
    }).join('');
}

function renderTempleBlessings(blessings = []) {
    const container = document.getElementById('templeBlessings');
    if (!container) return;
    if (!blessings.length) {
        container.innerHTML = '<p class="muted">Žádná požehnání zatím nejsou k dispozici.</p>';
        return;
    }
    const favorBalance = templeSnapshot?.favor || 0;
    const cooldownActive = (templeSnapshot?.cooldown_seconds || 0) > 0;
    container.innerHTML = blessings.map(blessing => {
        const costChips = formatTempleCost(blessing.cost || {}, favorBalance);
        const bonusText = formatBlessingBonus(blessing.bonus || {});
        const active = templeSnapshot?.active_blessing?.id === blessing.id;
        const hasResources = Object.entries(blessing.cost || {}).every(([resource, value]) => {
            if (resource === 'favor') {
                return favorBalance >= value;
            }
            return getResourceAmount(resource) >= value;
        });
        const disabled = active || cooldownActive || !hasResources;
        const buttonLabel = active ? 'Aktivní' : 'Aktivovat';
        return `
            <div class="temple-blessing-card ${active ? 'active' : ''}">
                <div>
                    <strong>${blessing.name}</strong>
                    <small>${blessing.description}</small>
                </div>
                <div class="temple-cost">
                    ${costChips}
                </div>
                <small>Bonus: ${bonusText}</small>
                <small>Trvání: ${Math.round((blessing.duration || 0) / 60)} min</small>
                <button class="btn-blue temple-blessing-btn" data-blessing="${blessing.id}" ${disabled ? 'disabled' : ''}>
                    ${buttonLabel}
                </button>
            </div>
        `;
    }).join('');
}

function formatTempleCost(cost = {}, favorBalance = 0) {
    const entries = Object.entries(cost);
    if (!entries.length) return '';
    return entries.map(([resource, value]) => {
        const icon = getResourceIcon(resource) || '';
        const affordable = resource === 'favor'
            ? favorBalance >= value
            : getResourceAmount(resource) >= value;
        const chipClass = affordable ? 'resource-chip' : 'resource-chip insufficient';
        return `<span class="${chipClass}">${icon} ${formatCostValue(value)}</span>`;
    }).join('');
}

function formatBlessingBonus(bonus = {}) {
    const parts = [];
    if (bonus.attack) parts.push(`⚔ +${bonus.attack}`);
    if (bonus.defense) parts.push(`🛡 +${bonus.defense}`);
    if (bonus.luck) parts.push(`💫 +${bonus.luck}`);
    if (bonus.hp) parts.push(`❤️ +${bonus.hp}`);
    return parts.join(', ') || 'Žádný';
}

async function handleTempleFight(roomId) {
    setCombatMessage('Chrámový boj se připravuje...', false);
    try {
        const response = await fetch('/api/temple/fight', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: roomId })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setCombatMessage(data.error || 'Chrám tě odmítl.', true);
            if (data.temple) {
                templeSnapshot = data.temple;
                gameState.temple = data.temple;
                renderTempleSection();
            }
            if (typeof data.cooldown_seconds === 'number') {
                updateTempleCooldown(data.cooldown_seconds);
            }
            return;
        }
        if (typeof data.gooncoins === 'number') {
            gameState.gooncoins = data.gooncoins;
            updateResourcesOnly();
        }
        if (data.rare_materials) {
            gameState.rareMaterials = data.rare_materials;
            renderRareMaterials(gameState.rareMaterials);
        }
        if (data.temple) {
            templeSnapshot = data.temple;
            gameState.temple = data.temple;
            renderTempleSection();
        } else {
            await loadTempleStatus();
        }
        await loadCombatOverview();
        const rewardText = formatTempleRewards(data.rewards || {});
        setCombatMessage(
            data.player_won
                ? `Chrámový boj vyhraný! ${rewardText}`
                : 'Chrám tě srazil na kolena.',
            !data.player_won
        );
        playCombatAnimation(data.battle, {
            playerLabel: 'Ty',
            enemyLabel: data.enemy_name || 'Chrámový nepřítel',
            playerStats: data.player_stats,
            enemyStats: data.enemy_stats
        });
    } catch (error) {
        console.error('Temple fight failed:', error);
        setCombatMessage('Chrámový boj se nepodařilo odehrát.', true);
    }
}

async function handleTempleRitual(blessingId) {
    setCombatMessage('Chrám žehná...', false);
    try {
        const response = await fetch('/api/temple/ritual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ blessing_id: blessingId })
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setCombatMessage(data.error || 'Požehnání selhalo.', true);
            return;
        }
        ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'].forEach(key => {
            if (typeof data[key] === 'number') {
                gameState[key] = data[key];
            }
        });
        if (data.temple) {
            templeSnapshot = data.temple;
            gameState.temple = data.temple;
            renderTempleSection();
        } else {
            await loadTempleStatus();
        }
        updateResourcesOnly();
        setCombatMessage('Požehnání aktivováno.', false);
    } catch (error) {
        console.error('Temple ritual failed:', error);
        setCombatMessage('Chrám se na tebe rozhněval.', true);
    }
}

function formatTempleRewards(rewards = {}) {
    const parts = [];
    if (rewards.gooncoins) {
        parts.push(`+${formatNumber(rewards.gooncoins)} 💰`);
    }
    if (rewards.favor) {
        parts.push(`+${rewards.favor} ${getResourceIcon('favor')}`);
    }
    if (rewards.rare_materials) {
        Object.entries(rewards.rare_materials).forEach(([key, amount]) => {
            const meta = rareMaterialDefs[key] || { name: key, icon: '✨' };
            parts.push(`${meta.icon || '✨'} ${meta.name || key} ×${amount}`);
        });
    }
    return parts.length ? `(${parts.join(', ')})` : '';
}

function clearCombatAnimation() {
    combatAnimationTimers.forEach(timer => clearTimeout(timer));
    combatAnimationTimers = [];
    document.querySelectorAll('.damage-pop').forEach(pop => pop.remove());
}

function playCombatAnimation(battle, context = {}) {
    const visual = document.getElementById('combatVisual');
    const playerHpFill = document.getElementById('combatPlayerHp');
    const enemyHpFill = document.getElementById('combatEnemyHp');
    const playerHpText = document.getElementById('combatPlayerHpText');
    const enemyHpText = document.getElementById('combatEnemyHpText');
    const playerNameEl = document.getElementById('combatPlayerName');
    const enemyNameEl = document.getElementById('combatEnemyName');
    const logEl = document.getElementById('combatVisualLog');
    if (!visual || !battle || !playerHpFill || !enemyHpFill) return;
    
    clearCombatAnimation();
    
    const playerStats = context.playerStats || {};
    const enemyStats = context.enemyStats || {};
    const playerTotalHp = Math.max(1, playerStats.hp || 1);
    const enemyTotalHp = Math.max(1, enemyStats.hp || 1);
    let playerHp = playerTotalHp;
    let enemyHp = enemyTotalHp;
    
    if (playerNameEl) playerNameEl.textContent = context.playerLabel || 'Ty';
    if (enemyNameEl) enemyNameEl.textContent = context.enemyLabel || 'Protivník';
    if (logEl) logEl.textContent = '⚔️ Boj začíná...';
    
    updateHpFill(playerHpFill, 100, playerHp, playerTotalHp, playerHpText);
    updateHpFill(enemyHpFill, 100, enemyHp, enemyTotalHp, enemyHpText);
    
    const rounds = battle.log || [];
    const stepDuration = 900;
    
    rounds.forEach((entry, index) => {
        const timer = setTimeout(() => {
            const attackerSide = entry.actor === 'attacker' ? 'player' : 'enemy';
            const targetSide = entry.actor === 'attacker' ? 'enemy' : 'player';
            const damage = entry.damage || 0;
            const dodged = Boolean(entry.dodged);
            
            if (entry.actor === 'attacker' && !dodged) {
                enemyHp = Math.max(0, enemyHp - damage);
                updateHpFill(enemyHpFill, (enemyHp / enemyTotalHp) * 100, enemyHp, enemyTotalHp, enemyHpText);
            } else if (entry.actor === 'defender' && !dodged) {
                playerHp = Math.max(0, playerHp - damage);
                updateHpFill(playerHpFill, (playerHp / playerTotalHp) * 100, playerHp, playerTotalHp, playerHpText);
            }
            
            animateFighter(attackerSide, targetSide, damage, dodged, entry.crit);
            if (logEl) {
                if (dodged) {
                    logEl.textContent = entry.actor === 'attacker'
                        ? `⚡ ${context.playerLabel || 'Ty'} míjí útok!`
                        : `⚡ ${context.enemyLabel || 'Protivník'} míjí útok!`;
                } else {
                    const critText = entry.crit ? ' 💥 KRITICKÝ ÚDER!' : '';
                    logEl.textContent = entry.actor === 'attacker'
                        ? `⚔️ Útočíš za ${damage.toFixed(1)} damage${critText}`
                        : `⚔️ ${context.enemyLabel || 'Protivník'} zasazuje ${damage.toFixed(1)} damage${critText}`;
                }
            }
        }, stepDuration * index);
        combatAnimationTimers.push(timer);
    });
    
    const endTimer = setTimeout(() => {
        if (logEl) {
            if (battle.winner === 'attacker') {
                logEl.textContent = '🎉 VÝHRA!';
            } else if (battle.winner === 'defender') {
                logEl.textContent = '💀 Porážka...';
            } else {
                logEl.textContent = '🤝 Remíza.';
            }
        }
        // Final HP update
        updateHpFill(playerHpFill, (playerHp / playerTotalHp) * 100, playerHp, playerTotalHp, playerHpText);
        updateHpFill(enemyHpFill, (enemyHp / enemyTotalHp) * 100, enemyHp, enemyTotalHp, enemyHpText);
    }, stepDuration * (rounds.length + 1));
    combatAnimationTimers.push(endTimer);
}

function updateHpFill(element, percent, currentHp, totalHp, textElement) {
    const clamped = Math.max(0, Math.min(100, percent));
    element.style.width = `${clamped}%`;
    if (clamped <= 35) {
        element.classList.add('low');
    } else {
        element.classList.remove('low');
    }
    
    // Update HP text
    if (textElement && currentHp !== undefined && totalHp !== undefined) {
        const current = Math.max(0, Math.round(currentHp));
        const total = Math.max(1, Math.round(totalHp));
        textElement.textContent = `HP: ${current} / ${total}`;
        
        // Add visual feedback for low HP
        if (clamped <= 35) {
            textElement.style.color = '#ff5252';
            textElement.style.textShadow = '0 0 10px rgba(255, 82, 82, 0.8)';
        } else if (clamped <= 60) {
            textElement.style.color = '#ffb74d';
            textElement.style.textShadow = '0 0 8px rgba(255, 183, 77, 0.6)';
        } else {
            textElement.style.color = 'rgba(255, 255, 255, 0.95)';
            textElement.style.textShadow = '0 1px 3px rgba(0, 0, 0, 0.8)';
        }
    }
}

function animateFighter(actorSide, targetSide, damage, dodged, crit) {
    const attacker = document.getElementById(actorSide === 'player' ? 'combatFighterPlayer' : 'combatFighterEnemy');
    const target = document.getElementById(targetSide === 'player' ? 'combatFighterPlayer' : 'combatFighterEnemy');
    if (attacker) {
        attacker.classList.add('attacking');
        const timer = setTimeout(() => attacker.classList.remove('attacking'), 350);
        combatAnimationTimers.push(timer);
    }
    if (target) {
        target.classList.add('hit');
        const timer = setTimeout(() => target.classList.remove('hit'), 350);
        combatAnimationTimers.push(timer);
        spawnDamagePop(target, damage, dodged, crit);
    }
}

function spawnDamagePop(targetEl, damage, dodged, crit) {
    const pop = document.createElement('div');
    pop.className = 'damage-pop';
    if (dodged) {
        pop.textContent = 'MISS';
        pop.classList.add('dodged');
    } else {
        pop.textContent = `-${Math.round(damage)}`;
        if (crit) {
            pop.classList.add('crit');
        }
    }
    targetEl.appendChild(pop);
    const timer = setTimeout(() => pop.remove(), 900);
    combatAnimationTimers.push(timer);
}

function setMarketMessage(message, isError = false) {
    const box = document.getElementById('marketMessage');
    if (!box) return;
    
    box.textContent = message;
    box.classList.remove('error', 'success');
    box.classList.add(isError ? 'error' : 'success');
    
    if (marketMessageTimer) {
        clearTimeout(marketMessageTimer);
    }
    
    marketMessageTimer = setTimeout(() => {
        box.textContent = '';
        box.classList.remove('error', 'success');
    }, 4000);
}

// Auto-refresh upgrades - reduced frequency to prevent freezing
let lastQuestState = '';
let autoRefreshInterval = null;
let autoRefreshInProgress = false;
let autoRefreshRequestCount = 0;
let autoRefreshStartTime = Date.now();

function startAutoRefresh() {
    // Stop any existing interval
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        console.log('[DEBUG] Cleared existing auto-refresh interval');
    }
    
    console.log('[DEBUG] Starting auto-refresh');
    autoRefreshStartTime = Date.now();
    
    // Increased interval from 2s to 5s to reduce load
    autoRefreshInterval = setInterval(async () => {
        // Prevent overlapping requests
        if (autoRefreshInProgress) {
            console.warn('[DEBUG] Auto-refresh request already in progress, skipping');
            return;
        }
        
        autoRefreshInProgress = true;
        autoRefreshRequestCount++;
        const requestStart = performance.now();
        
        try {
            await loadGameState();
            const requestTime = performance.now() - requestStart;
            
            // Only refresh upgrades if we're on the gather tab
            const activeTab = document.querySelector('.tab-content.active');
            if (activeTab && activeTab.id === 'gather-tab') {
                setupUpgrades();
                setupAutoGenerators();
            }
            
            // Only reload quests if they actually changed (prevents flickering)
            const questState = JSON.stringify(gameState.story?.completed_quests || []);
            if (questState !== lastQuestState) {
                lastQuestState = questState;
                loadQuests();
            }
            
            if (autoRefreshRequestCount % 5 === 0) {
                const elapsed = ((Date.now() - autoRefreshStartTime) / 1000).toFixed(1);
                console.log(`[DEBUG] Auto-refresh: ${autoRefreshRequestCount} requests in ${elapsed}s, last request took ${requestTime.toFixed(0)}ms`);
            }
        } catch (error) {
            console.error('[DEBUG] Error in auto-refresh:', error);
        } finally {
            autoRefreshInProgress = false;
        }
    }, 5000); // Changed from 2000 to 5000 (5 seconds)
}

// Load game state from server
let lastDisplayUpdate = 0;
const DISPLAY_UPDATE_THROTTLE = 200; // Only update display max 5 times per second

async function loadGameState() {
    try {
        const response = await fetch('/api/game-state');
        if (response.ok) {
            const data = await response.json();
            applyResourcePayload(data);
            gameState = { 
                ...gameState, 
                gooncoins: data.gooncoins,
                astma: data.astma,
                poharky: data.poharky,
                mrkev: data.mrkev,
                uzené: data.uzené,
                total_clicks: data.total_clicks,
                upgrades: data.upgrades || {},
                story: data.story || {},
                equipment: data.equipment || {},
                equipmentCounts: data.equipment_counts || {},
                buildings: data.buildings || {},
                gems: data.gems || {},
                active_boosts: data.active_boosts || [],
                generation_rates: data.generation_rates || {
                    gooncoins: 0,
                    astma: 0,
                    poharky: 0,
                    mrkev: 0,
                    uzené: 0
                },
                economy: data.economy || gameState.economy,
                rareMaterials: data.rare_materials || gameState.rareMaterials,
                combat: data.combat || gameState.combat,
                temple: data.temple || gameState.temple
            };
            updateInventoryFromPayload(data.inventory);
            gameState.clickValue = 1 + (gameState.upgrades.click_power_1 || 0) * 0.5 + 
                                   (gameState.upgrades.click_power_2 || 0) * 0.5;
            
            // Throttle display updates to prevent freezing
            const now = Date.now();
            if (now - lastDisplayUpdate >= DISPLAY_UPDATE_THROTTLE) {
                updateDisplay();
                lastDisplayUpdate = now;
            } else {
                // Just update resources if throttled
                updateResourcesOnly();
            }
            
            updateGemsDisplay();
            setupAutoGenerators();
            if (data.temple) {
                templeSnapshot = data.temple;
                renderTempleSection();
            }
            // Sync character panel if on character tab
            const activeTab = document.querySelector('.tab-content.active');
            if (activeTab && activeTab.id === 'character-tab') {
                loadCharacterPanel();
            }
        }
    } catch (error) {
        console.error('Error loading game state:', error);
    }
}

// Setup click button - now clicking on lugog image
function setupClickButton() {
    const clickTargets = ['clickButton', 'lugogClickImage']
        .map(id => document.getElementById(id))
        .filter(Boolean);
    
    clickTargets.forEach(target => {
        target.addEventListener('click', handleClick);
    });
}

// Setup dark mode
function setupDarkMode() {
    const toggle = document.getElementById('darkModeToggle');
    if (toggle) {
        const currentTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', currentTheme);
        toggle.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
        
        toggle.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            toggle.textContent = newTheme === 'dark' ? '☀️' : '🌙';
        });
    }
}

// Handle click
async function handleClick() {
    try {
        const response = await fetch('/api/click', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            gameState.gooncoins = data.gooncoins;
            gameState.total_clicks = data.total_clicks;
            gameState.clickValue = data.click_value;
            updateDisplay();
            
            // Visual feedback
            showClickEffect();
        }
    } catch (error) {
        console.error('Error clicking:', error);
    }
}

// Show click effect
function showClickEffect() {
    const clickButton = document.getElementById('clickButton');
    if (!clickButton) return;
    const effect = document.createElement('div');
    effect.textContent = `+${gameState.clickValue.toFixed(1)}`;
    effect.style.position = 'absolute';
    effect.style.color = '#ffd700';
    effect.style.fontSize = '24px';
    effect.style.fontWeight = 'bold';
    effect.style.pointerEvents = 'none';
    effect.style.animation = 'floatUp 1s ease-out forwards';
    
    clickButton.style.position = 'relative';
    clickButton.appendChild(effect);
    
    setTimeout(() => effect.remove(), 1000);
}

// Auto generation - runs even when tab is in background
let autoGenInterval = null;
let autoGenInProgress = false;
let autoGenRequestCount = 0;
let autoGenStartTime = Date.now();

function startAutoGeneration() {
    // Stop any existing interval
    if (autoGenInterval) {
        clearInterval(autoGenInterval);
        console.log('[DEBUG] Cleared existing auto-gen interval');
    }
    
    console.log('[DEBUG] Starting auto-generation');
    autoGenStartTime = Date.now();
    
    // Use setInterval for reliable background updates
    autoGenInterval = setInterval(async () => {
        // Prevent overlapping requests
        if (autoGenInProgress) {
            console.warn('[DEBUG] Auto-gen request already in progress, skipping');
            return;
        }
        
        autoGenInProgress = true;
        autoGenRequestCount++;
        const requestStart = performance.now();
        
        try {
            const response = await fetch('/api/auto-generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const requestTime = performance.now() - requestStart;
            
            if (response.ok) {
                const data = await response.json();
                if (data && typeof data === 'object') {
                    applyResourcePayload(data);
                    if (data.generation_rates) {
                        gameState.generation_rates = data.generation_rates;
                    }
                    updateResourcesOnly();
                    
                    if (autoGenRequestCount % 10 === 0) {
                        const elapsed = ((Date.now() - autoGenStartTime) / 1000).toFixed(1);
                        console.log(`[DEBUG] Auto-gen: ${autoGenRequestCount} requests in ${elapsed}s, last request took ${requestTime.toFixed(0)}ms`);
                    }
                }
            } else {
                console.warn(`[DEBUG] Auto-gen request failed: ${response.status}`);
            }
        } catch (error) {
            console.error('[DEBUG] Error auto-generating:', error);
        } finally {
            autoGenInProgress = false;
        }
    }, 1000);
}

// Setup upgrades
function setupUpgrades() {
    const upgradesList = document.getElementById('upgradesList');
    if (!upgradesList) return; // Don't update if element doesn't exist
    
    upgradesList.innerHTML = '';
    
    // Exclude auto-generators for astma, poharky, mrkev, and uzené from home upgrades
    const excludedUpgrades = ['auto_astma', 'auto_poharky', 'auto_mrkev', 'auto_uzené'];
    
    for (const [key, upgrade] of Object.entries(upgrades)) {
        // Skip excluded upgrades
        if (excludedUpgrades.includes(key)) continue;
        
        const level = gameState.upgrades[key] || 0;
        const upgradeItem = createUpgradeItem(key, upgrade, level);
        upgradesList.appendChild(upgradeItem);
    }
}

function setupAutoGenerators() {
    const list = document.getElementById('autoGeneratorsList');
    if (!list) return;
    
    // Exclude auto-generators for astma, poharky, mrkev, and uzené
    const excludedGenerators = ['auto_astma', 'auto_poharky', 'auto_mrkev', 'auto_uzené'];
    const entries = Object.entries(autoGeneratorBlueprints).filter(([key]) => !excludedGenerators.includes(key));
    list.innerHTML = '';
    
    if (entries.length === 0) {
        list.innerHTML = '<p class="muted">Auto-generátory zatím nejsou dostupné.</p>';
        return;
    }
    
    entries.forEach(([upgradeKey, blueprint]) => {
        const upgradeDef = upgrades[upgradeKey] || {};
        const level = gameState.upgrades?.[upgradeKey] || 0;
        const totalRate = level * blueprint.ratePerLevel;
        const nextRate = blueprint.ratePerLevel;
        const costs = calculateUpgradeCost(upgradeKey, level);
        const canAfford = canAffordUpgrade(costs);
        
        const card = document.createElement('div');
        card.className = 'generator-item';
        card.innerHTML = `
            <div class="generator-header">
                <div class="generator-title">
                    <div class="generator-icon">${upgradeDef.icon || '⚙️'}</div>
                    <div>
                        <h4>${upgradeDef.name || 'Auto-generátor'}</h4>
                        <p>${(blueprint.flavor || upgradeDef.description || '').trim()}</p>
                    </div>
                </div>
                <span class="badge-level">Úroveň ${level}</span>
            </div>
            <div class="generator-meta">
                <div class="generator-stat">
                    <span class="label">Produkuje</span>
                    <strong>+${totalRate.toFixed(2)} ${getResourceLabel(blueprint.resourceKey)}/s</strong>
                </div>
                <div class="generator-stat">
                    <span class="label">Další úroveň</span>
                    <strong>+${nextRate.toFixed(2)} ${getResourceLabel(blueprint.resourceKey)}/s</strong>
                </div>
            </div>
            <div class="generator-cost">
                ${renderCostPills(costs) || '<span class="muted">Žádné náklady</span>'}
            </div>
            <div class="generator-footer">
                <span class="generator-resource-pill">${getResourceIcon(blueprint.resourceKey)} ${getResourceLabel(blueprint.resourceKey)}</span>
                <button class="btn-secondary" onclick="buyUpgrade('${upgradeKey}')" ${!canAfford ? 'disabled' : ''}>
                    Posílit (${level} → ${level + 1})
                </button>
            </div>
        `;
        
        list.appendChild(card);
    });
}

function calculateGeneratorRatesFromUpgrades() {
    const rates = {
        gooncoins: 0,
        astma: 0,
        poharky: 0,
        mrkev: 0,
        uzené: 0
    };
    
    Object.entries(autoGeneratorBlueprints).forEach(([upgradeKey, blueprint]) => {
        const level = gameState.upgrades?.[upgradeKey] || 0;
        if (!blueprint.resourceKey) return;
        rates[blueprint.resourceKey] = (rates[blueprint.resourceKey] || 0) + level * blueprint.ratePerLevel;
    });
    
    return rates;
}

function getEffectiveGenerationRates() {
    const calculated = calculateGeneratorRatesFromUpgrades();
    const serverRates = gameState.generation_rates || {};
    const effective = {};
    
    RESOURCE_KEYS.forEach(resource => {
        const serverValue = Number(serverRates[resource]);
        const calculatedValue = Number(calculated[resource]) || 0;
        effective[resource] = serverValue && serverValue > 0 ? serverValue : calculatedValue;
    });
    
    return effective;
}

// Create upgrade item
function createUpgradeItem(key, upgrade, level) {
    const item = document.createElement('div');
    item.className = 'upgrade-item';
    
    const costs = calculateUpgradeCost(key, level);
    const canAfford = canAffordUpgrade(costs);
    
    item.innerHTML = `
        <div class="upgrade-header">
            <div class="upgrade-title">
                <div class="upgrade-icon">${upgrade.icon}</div>
                <div>
                    <h4>${upgrade.name}</h4>
                    <p class="upgrade-description">${upgrade.description || ''}</p>
                </div>
            </div>
            <span class="badge-level">Úroveň ${level}</span>
        </div>
        <div class="upgrade-cost">
            ${renderCostPills(costs) || '<span class="muted">Žádné náklady</span>'}
        </div>
        <button class="btn-buy" onclick="buyUpgrade('${key}')" ${!canAfford ? 'disabled' : ''}>
            Koupit (${level} → ${level + 1})
        </button>
    `;
    
    return item;
}

function renderCostPills(costs = {}) {
    return Object.entries(costs)
        .filter(([, cost]) => cost > 0)
        .map(([resource, cost]) => {
            const currentAmount = getResourceAmount(resource);
            const insufficient = currentAmount < cost;
            return `
                <span class="cost-item ${insufficient ? 'insufficient' : ''}">
                    ${getResourceIcon(resource)} ${formatCostValue(cost)}
                </span>
            `;
        })
        .join('');
}

// Calculate upgrade cost
function calculateUpgradeCost(upgradeType, currentLevel) {
    // Base costs match backend (before scaling and inflation)
    const baseCosts = {
        // Basic click power upgrades
        click_power_1: { gooncoins: 10, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        click_power_2: { gooncoins: 50, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        click_power_3: { gooncoins: 500, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        click_power_4: { gooncoins: 2500, astma: 50, poharky: 0, mrkev: 0, uzené: 0 },
        click_power_5: { gooncoins: 10000, astma: 200, poharky: 100, mrkev: 0, uzené: 0 },
        click_power_6: { gooncoins: 50000, astma: 500, poharky: 300, mrkev: 150, uzené: 0 },
        click_power_7: { gooncoins: 200000, astma: 1500, poharky: 1000, mrkev: 500, uzené: 300 },
        click_power_8: { gooncoins: 1000000, astma: 5000, poharky: 3500, mrkev: 2000, uzené: 1500 },
        
        // Auto-generators
        auto_gooncoin: { gooncoins: 100, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        auto_astma: { gooncoins: 500, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        auto_poharky: { gooncoins: 2000, astma: 100, poharky: 0, mrkev: 0, uzené: 0 },
        auto_mrkev: { gooncoins: 8000, astma: 300, poharky: 200, mrkev: 0, uzené: 0 },
        auto_uzené: { gooncoins: 30000, astma: 800, poharky: 500, mrkev: 300, uzené: 0 },
        
        // Multiplier upgrades
        click_multiplier_1: { gooncoins: 5000, astma: 100, poharky: 0, mrkev: 0, uzené: 0 },
        click_multiplier_2: { gooncoins: 25000, astma: 500, poharky: 300, mrkev: 0, uzené: 0 },
        click_multiplier_3: { gooncoins: 150000, astma: 2000, poharky: 1500, mrkev: 800, uzené: 0 },
        click_multiplier_4: { gooncoins: 750000, astma: 8000, poharky: 6000, mrkev: 4000, uzené: 2500 },
        
        generation_multiplier_1: { gooncoins: 10000, astma: 200, poharky: 100, mrkev: 0, uzené: 0 },
        generation_multiplier_2: { gooncoins: 50000, astma: 1000, poharky: 600, mrkev: 400, uzené: 0 },
        generation_multiplier_3: { gooncoins: 300000, astma: 4000, poharky: 3000, mrkev: 2000, uzené: 1200 },
        generation_multiplier_4: { gooncoins: 1500000, astma: 15000, poharky: 12000, mrkev: 8000, uzené: 5000 },
        
        // Efficiency upgrades
        cost_reduction_1: { gooncoins: 15000, astma: 300, poharky: 200, mrkev: 100, uzené: 0 },
        cost_reduction_2: { gooncoins: 100000, astma: 2000, poharky: 1500, mrkev: 1000, uzené: 600 },
        cost_reduction_3: { gooncoins: 600000, astma: 10000, poharky: 8000, mrkev: 5000, uzené: 3000 },
        
        // Global power upgrades
        global_power_1: { gooncoins: 50000, astma: 1000, poharky: 700, mrkev: 500, uzené: 300 },
        global_power_2: { gooncoins: 300000, astma: 5000, poharky: 3500, mrkev: 2500, uzené: 1500 },
        global_power_3: { gooncoins: 2000000, astma: 20000, poharky: 15000, mrkev: 10000, uzené: 8000 },
        
        // Special late-game upgrades
        quantum_click: { gooncoins: 5000000, astma: 50000, poharky: 40000, mrkev: 30000, uzené: 20000 },
        time_acceleration: { gooncoins: 10000000, astma: 100000, poharky: 80000, mrkev: 60000, uzené: 50000 },
        infinity_boost: { gooncoins: 50000000, astma: 500000, poharky: 400000, mrkev: 300000, uzené: 250000 }
    };
    
    const base = baseCosts[upgradeType] || {};
    const multiplier = Math.pow(1.5, currentLevel);
    
    const scaledCost = {
        gooncoins: (base.gooncoins || 0) * multiplier,
        astma: (base.astma || 0) * multiplier,
        poharky: (base.poharky || 0) * multiplier,
        mrkev: (base.mrkev || 0) * multiplier,
        uzené: (base.uzené || 0) * multiplier
    };
    
    return applyInflationToCostMap(scaledCost);
}

// Check if can afford upgrade
function canAffordUpgrade(costs) {
    return gameState.gooncoins >= costs.gooncoins &&
           gameState.astma >= costs.astma &&
           gameState.poharky >= costs.poharky &&
           gameState.mrkev >= costs.mrkev &&
           gameState.uzené >= costs.uzené;
}

function getResourceLabel(resource) {
    return RESOURCE_LABELS[resource] || resource;
}

function getResourceAmount(resource) {
    return Number(gameState?.[resource] || 0);
}

// Get resource icon
function getResourceIcon(resource) {
    const icons = {
        gooncoins: '💰',
        astma: '💨',
        poharky: '🥃',
        mrkev: '🥕',
        uzené: '🍖',
        logs: '🪵',
        planks: '🪚',
        grain: '🌾',
        flour: '🧯',
        bread: '🍞',
        fish: '🐟',
        favor: '🔱'
    };
    return icons[resource] || '';
}

function applyResourcePayload(payload = {}) {
    if (!payload || typeof payload !== 'object') {
        return;
    }
    Object.entries(payload).forEach(([key, value]) => {
        if (typeof value === 'number') {
            gameState[key] = value;
        }
    });
}

// Update game state from API response
function updateGameState(data = {}) {
    if (!data || typeof data !== 'object') {
        return;
    }
    applyResourcePayload(data);
    updateResourcesOnly();
    if (data.gems !== undefined) {
        gameState.gems = typeof data.gems === 'number' ? data.gems : 0;
    }
}

// Buy upgrade
async function buyUpgrade(upgradeType) {
    try {
        const response = await fetch('/api/buy-upgrade', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ upgrade_type: upgradeType })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Chyba serveru' }));
            showCustomAlert(errorData.error || 'Chyba při nákupu upgradů', { type: 'error' });
            return;
        }
        
        const data = await response.json();
        if (data.success) {
            applyResourcePayload(data);
            gameState.upgrades[upgradeType] = data.new_level;
            
            // Recalculate click value
            gameState.clickValue = 1 + (gameState.upgrades.click_power_1 || 0) * 0.5 + 
                                   (gameState.upgrades.click_power_2 || 0) * 0.5;
            
            // Reload game state to get latest
            await loadGameState();
            updateDisplay();
            setupUpgrades();
            setupAutoGenerators();
        } else {
            showCustomAlert(data.error || 'Chyba při nákupu upgradů', { type: 'error' });
        }
    } catch (error) {
        console.error('Error buying upgrade:', error);
        showCustomAlert('Chyba připojení k serveru: ' + error.message, { type: 'error' });
    }
}

// Update display - old function removed, using new one below

// Format number
function formatNumber(num) {
    // Convert to number if it's not already
    if (typeof num !== 'number') {
        num = parseFloat(num) || 0;
    }
    if (num >= 1e12) return (num / 1e12).toFixed(2) + 'T';
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K';
    return num.toFixed(1);
}

// Load leaderboard
async function loadLeaderboard() {
    try {
        const response = await fetch('/api/leaderboard');
        if (response.ok) {
            const leaders = await response.json();
            displayLeaderboard(leaders);
        }
    } catch (error) {
        console.error('Error loading leaderboard:', error);
    }
}

// Display leaderboard
function displayLeaderboard(leaders) {
    const leaderboardList = document.getElementById('leaderboardList');
    if (!leaderboardList) return;
    
    leaderboardList.innerHTML = '';
    
    if (leaders.length === 0) {
        leaderboardList.innerHTML = '<p style="opacity: 0.7; text-align: center;">Zatím žádní hráči</p>';
        return;
    }
    
    leaders.forEach((leader, index) => {
        const item = document.createElement('div');
        item.className = `leaderboard-item rank-${index + 1}`;
        item.innerHTML = `
            <span class="leaderboard-rank">${index + 1}.</span>
            <span class="leaderboard-username">${leader.username}</span>
            <span class="leaderboard-score">${formatNumber(leader.gooncoins)} 💰</span>
        `;
        leaderboardList.appendChild(item);
    });
}

// Refresh leaderboard periodically
setInterval(loadLeaderboard, 30000); // Every 30 seconds

// Shop functions
let shopData = { items: [], gems: 0 };
let currentShopCategory = 'all';

async function loadShop() {
    try {
        const response = await fetch('/api/shop');
        if (response.ok) {
            const data = await response.json();
            shopData = data;
            renderShop();
            updateGemsDisplay();
        }
    } catch (error) {
        console.error('Error loading shop:', error);
    }
}

function renderShop() {
    const shopItemsList = document.getElementById('shopItemsList');
    if (!shopItemsList) return;
    
    shopItemsList.innerHTML = '';
    
    let filteredItems = shopData.items || [];
    if (currentShopCategory !== 'all') {
        filteredItems = filteredItems.filter(item => item.category === currentShopCategory);
    }
    
    if (filteredItems.length === 0) {
        shopItemsList.innerHTML = '<p class="muted">V této kategorii nejsou žádné položky.</p>';
        return;
    }
    
    filteredItems.forEach(item => {
        const itemCard = document.createElement('div');
        itemCard.className = `shop-item-card ${item.popular ? 'popular' : ''}`;
        
        const costDisplay = item.cost_gems > 0 
            ? `${item.cost_gems} 💎`
            : item.cost_real_money > 0
            ? `$${item.cost_real_money.toFixed(2)}`
            : 'Zdarma';
        
        const canAfford = item.cost_gems > 0 ? (shopData.gems || 0) >= item.cost_gems : true;
        
        itemCard.innerHTML = `
            <div class="shop-item-icon">${item.icon}</div>
            <div class="shop-item-content">
                <h3 class="shop-item-name">${item.name}</h3>
                <p class="shop-item-description">${item.description}</p>
                <div class="shop-item-footer">
                    <span class="shop-item-cost ${!canAfford ? 'insufficient' : ''}">${costDisplay}</span>
                    <button class="btn-shop-purchase ${!canAfford ? 'disabled' : ''}" 
                            data-item-id="${item.id}" ${!canAfford ? 'disabled' : ''}>
                        ${item.cost_real_money > 0 ? 'Koupit' : 'Zakoupit'}
                    </button>
                </div>
            </div>
        `;
        
        shopItemsList.appendChild(itemCard);
    });
    
    // Add event listeners
    document.querySelectorAll('.btn-shop-purchase').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const itemId = btn.getAttribute('data-item-id');
            if (itemId && !btn.disabled) {
                purchaseShopItem(itemId);
            }
        });
    });
}

function updateGemsDisplay() {
    const gemsValue = document.getElementById('gemsValue');
    const gemsValueTop = document.getElementById('gemsValueTop');
    // Safely extract numeric value from gems (could be object or number)
    const shopGems = typeof shopData.gems === 'number' ? shopData.gems : (typeof shopData.gems === 'object' && shopData.gems !== null ? 0 : 0);
    const stateGems = typeof gameState.gems === 'number' ? gameState.gems : (typeof gameState.gems === 'object' && gameState.gems !== null ? 0 : 0);
    if (gemsValue) gemsValue.textContent = formatNumber(shopGems || stateGems || 0);
    if (gemsValueTop) gemsValueTop.textContent = formatNumber(stateGems || 0);
    
    // Update active boosts display
    const activeBoostsDisplay = document.getElementById('activeBoostsDisplay');
    if (activeBoostsDisplay && gameState.active_boosts) {
        const boosts = gameState.active_boosts || [];
        if (boosts.length > 0) {
            activeBoostsDisplay.innerHTML = boosts.map(boost => {
                const typeLabel = boost.type === 'production' ? 'Produkce' : boost.type === 'click_power' ? 'Kliknutí' : boost.type;
                const multiplier = boost.multiplier || 1;
                let timeLeft = '';
                if (boost.expires_at) {
                    try {
                        const expires = new Date(boost.expires_at);
                        const now = new Date();
                        const diff = Math.max(0, Math.floor((expires - now) / 1000));
                        const hours = Math.floor(diff / 3600);
                        const minutes = Math.floor((diff % 3600) / 60);
                        timeLeft = ` (${hours}h ${minutes}m)`;
                    } catch (e) {}
                }
                return `<span class="active-boost-badge">${typeLabel} ${multiplier}×${timeLeft}</span>`;
            }).join('');
        } else {
            activeBoostsDisplay.innerHTML = '';
        }
    }
}

async function purchaseShopItem(itemId) {
    const shopMessage = document.getElementById('shopMessage');
    if (shopMessage) shopMessage.textContent = '';
    
    try {
        const response = await fetch('/api/shop/purchase', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item_id: itemId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (shopMessage) {
                shopMessage.textContent = data.message || 'Nákup úspěšný!';
                shopMessage.className = 'shop-message success';
            }
            
            // Reload shop and game state
            await loadShop();
            await loadGameState();
            
            // Show rewards if any
            if (data.rewards) {
                const rewardText = Object.entries(data.rewards)
                    .map(([key, value]) => {
                        if (key === 'boost') {
                            return `${value.multiplier}× ${value.type === 'production' ? 'Produkce' : 'Kliknutí'}`;
                        }
                        const label = RESOURCE_LABELS[key] || key;
                        return `+${formatNumber(value)} ${label}`;
                    })
                    .join(', ');
                
                if (shopMessage) {
                    shopMessage.textContent += ` Odměny: ${rewardText}`;
                }
            }
        } else {
            if (shopMessage) {
                shopMessage.textContent = data.error || 'Chyba při nákupu';
                shopMessage.className = 'shop-message error';
            }
        }
    } catch (error) {
        console.error('Error purchasing item:', error);
        if (shopMessage) {
            shopMessage.textContent = 'Chyba při nákupu';
            shopMessage.className = 'shop-message error';
        }
    }
}

// Setup shop category filters
function setupShopCategories() {
    document.querySelectorAll('.shop-category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.shop-category-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentShopCategory = btn.getAttribute('data-category');
            renderShop();
        });
    });
}

// Add CSS animation for click effect
const style = document.createElement('style');
style.textContent = `
    @keyframes floatUp {
        0% {
            opacity: 1;
            transform: translateY(0);
        }
        100% {
            opacity: 0;
            transform: translateY(-50px);
        }
    }
`;
document.head.appendChild(style);

// Setup crafting
function setupCrafting() {
    const sortSelect = document.getElementById('craftSortSelect');
    if (sortSelect) {
        sortSelect.value = selectedCraftSort;
        sortSelect.addEventListener('change', (event) => {
            selectedCraftSort = event.target.value;
            persistCraftSortPreference(selectedCraftSort);
            loadCrafting();
        });
    }
    
    const searchInput = document.getElementById('craftingSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            craftingSearchQuery = event.target.value.toLowerCase().trim();
            loadCrafting();
        });
    }
    
    const rarityFilter = document.getElementById('craftingRarityFilter');
    if (rarityFilter) {
        rarityFilter.value = craftingRarityFilter;
        rarityFilter.addEventListener('change', (event) => {
            craftingRarityFilter = event.target.value;
            try {
                if (typeof localStorage !== 'undefined') {
                    localStorage.setItem('craftingRarityFilter', craftingRarityFilter);
                }
            } catch (err) {
                console.warn('localStorage not available');
            }
            loadCrafting();
        });
    }
    
    loadCrafting();
}

function loadCrafting() {
    const craftingList = document.getElementById('craftingList');
    if (!craftingList || !equipmentDefs || Object.keys(equipmentDefs).length === 0) return;
    
    craftingList.innerHTML = '';
    
    const playerCounts = gameState.equipmentCounts || {};
    
    let items = Object.entries(equipmentDefs).map(([id, def]) => {
        const unlockState = getUnlockState(def, playerCounts);
        const rarityMeta = getRarityMeta(def.rarity);
        return {
            id,
            def,
            rarity: rarityMeta.key,
            rarityLabel: rarityMeta.label,
            unlockState,
            owned: playerCounts[id] || 0,
            globalOwned: storyEquipmentCounts?.[id] || 0,
            power: getItemPower(def),
            release: getReleaseOrder(def)
        };
    });
    
    // Apply search filter
    if (craftingSearchQuery) {
        items = items.filter(item => {
            const nameMatch = item.def.name.toLowerCase().includes(craftingSearchQuery);
            const slotMatch = getSlotLabel(item.def.slot).toLowerCase().includes(craftingSearchQuery);
            return nameMatch || slotMatch;
        });
    }
    
    // Apply rarity filter
    if (craftingRarityFilter && craftingRarityFilter !== 'all') {
        items = items.filter(item => item.rarity === craftingRarityFilter);
    }
    
    // Sort items
    items = items.sort((a, b) => sortCraftItems(a, b, selectedCraftSort));
    
    if (!items.length) {
        craftingList.innerHTML = '<p class="muted" style="text-align: center; padding: 20px;">Žádné položky neodpovídají filtru.</p>';
        const craftingDetail = document.getElementById('craftingDetail');
        if (craftingDetail) craftingDetail.innerHTML = '';
        return;
    }
    
    if (!selectedCraftItem || !items.some(item => item.id === selectedCraftItem)) {
        const preferred = items.find(item => item.unlockState.isUnlocked) || items[0];
        selectedCraftItem = preferred ? preferred.id : null;
    }
    
    items.forEach(itemData => {
        const { id, def, rarity, rarityLabel, unlockState, owned, globalOwned } = itemData;
        const item = document.createElement('div');
        const isSelected = selectedCraftItem === id;
        item.className = `craft-item ${isSelected ? 'selected' : ''} ${unlockState.isUnlocked ? '' : 'locked'}`;
        item.dataset.itemId = id;
        
        const imagePath = def.image || 'placeholder.png';
        const requirementSummary = unlockState.requirements.length
            ? unlockState.requirements.map(req => `${req.owned}/${req.needed}× ${req.name}`).join(', ')
            : 'Bez požadavků';
        const progressPercent = Math.round((unlockState.progress || 0) * 100);
        const progressWidth = Math.max(0, Math.min(100, progressPercent));
        const progressBar = unlockState.requirements.length
            ? `<div class="craft-item-progress"><span style="width:${progressWidth}%;"></span></div>`
            : '';
        
        item.innerHTML = `
            <div class="craft-item-compact" onclick="selectCraftItem('${id}')">
                ${def.image ? `<img src="/images/${imagePath}" alt="${def.name}" class="craft-item-image-small" onerror="this.style.display='none'; this.onerror=null;">` : ''}
                <div class="craft-item-info">
                    <div class="craft-item-header">
                        <h4>${def.name}</h4>
                        <span class="craft-item-owned-pill">x${owned}</span>
                    </div>
                    <div class="craft-item-meta">
                        <div class="craft-item-badges">
                            <span class="rarity-pill rarity-${rarity}">${rarityLabel}</span>
                            <span class="craft-item-slot">${getSlotLabel(def.slot)}</span>
                        </div>
                        <span class="craft-item-global">Ty: ${owned}× • Celkem hráčů: ${globalOwned}</span>
                    </div>
                    <div class="craft-item-status ${unlockState.isUnlocked ? 'unlocked' : 'locked'}">
                        <span>${unlockState.isUnlocked ? 'Odemčeno' : 'Zamčeno'}</span>
                        ${unlockState.isUnlocked ? '' : `<div class="craft-item-req-text">${requirementSummary}</div>`}
                        ${progressBar}
                    </div>
                </div>
            </div>
        `;
        
        craftingList.appendChild(item);
    });
    
    if (selectedCraftItem && equipmentDefs[selectedCraftItem]) {
        showCraftDetail(selectedCraftItem);
    } else {
        const craftingDetail = document.getElementById('craftingDetail');
        if (craftingDetail) craftingDetail.innerHTML = '';
    }
}

function selectCraftItem(itemId) {
    selectedCraftItem = itemId;
    loadCrafting();
}

function showCraftDetail(itemId) {
    const craftingDetail = document.getElementById('craftingDetail');
    if (!craftingDetail) return;
    
    const def = equipmentDefs[itemId];
    if (!def) return;
    
    const baseCost = def.cost;
    const effectiveCost = applyInflationToCostMap(baseCost);
    const canAfford = canAffordCraft(effectiveCost);
    const imagePath = def.image || 'placeholder.png';
    const globalOwners = storyEquipmentCounts[itemId] || 0;
    const ownedCount = gameState.equipmentCounts?.[itemId] || 0;
    const rarityMeta = getRarityMeta(def.rarity);
    const unlockState = getUnlockState(def, gameState.equipmentCounts || {});
    const isUnlocked = unlockState.isUnlocked;
    const bonusText = Object.entries(def.bonus || {}).map(([k, v]) => {
        const bonusNames = {
            'click_power': 'Síla kliku',
            'defense': 'Obrana',
            'luck': 'Štěstí'
        };
        return `${bonusNames[k] || k}: ${v}×`;
    }).join(', ');
    
    const unlockRequirements = unlockState.requirements.length
        ? `
            <div class="craft-detail-req">
                <strong>Odemčení:</strong>
                <div class="craft-requirements">
                    ${unlockState.requirements.map(req => `
                        <div class="craft-requirement ${req.met ? 'met' : 'pending'}">
                            <span>${req.name}</span>
                            <span>${req.owned}/${req.needed}</span>
                        </div>
                        <div class="craft-requirement-progress">
                            <span style="width:${Math.max(0, Math.min(100, Math.round(req.ratio * 100)))}%;"></span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `
        : '';
    
    const warningBlock = !isUnlocked
        ? `<div class="craft-detail-warning">Nejdřív odemkni předmět splněním požadavků výše.</div>`
        : '';
    const canCraft = isUnlocked && canAfford;
    
    craftingDetail.innerHTML = `
        <div class="craft-detail-content">
            ${def.image ? `<img src="/images/${imagePath}" alt="${def.name}" class="craft-detail-image" onerror="this.style.display='none'; this.onerror=null;">` : ''}
            <div class="craft-detail-header">
                <div>
                    <h3>${def.name}</h3>
                    <p class="craft-detail-owned">Ty: ${ownedCount}× • Celkem hráčů: ${globalOwners}</p>
                </div>
                <div class="craft-detail-rarity">
                    <span class="rarity-pill rarity-${rarityMeta.key}">${rarityMeta.label}</span>
                    <span class="craft-item-slot">${getSlotLabel(def.slot)}</span>
                </div>
            </div>
            <div class="craft-detail-info">
                <p><strong>Bonus:</strong> ${bonusText || '—'}</p>
                ${unlockRequirements}
                <p class="ownership-count">${globalOwners} hráčů má tento item</p>
            </div>
            <div class="craft-detail-cost">
                <h4>Cena:</h4>
                <div class="upgrade-cost">
                    ${Object.entries(effectiveCost).filter(([_, c]) => c > 0).map(([resource, c]) => 
                        `<span class="cost-item ${gameState[resource] < c ? 'insufficient' : ''}">
                            ${getResourceIcon(resource)} ${formatCostValue(c)}
                        </span>`
                    ).join('')}
                </div>
            </div>
            ${warningBlock}
            <button class="btn-buy btn-buy-large" onclick="craftEquipment('${itemId}')" ${!canCraft ? 'disabled' : ''}>
                ${isUnlocked ? 'Vyrobit' : 'Zamčeno'}
            </button>
        </div>
    `;
}

function canAffordCraft(cost) {
    return Object.entries(cost).every(([resource, amount]) => 
        getResourceAmount(resource) >= amount
    );
}

async function craftEquipment(equipmentId) {
    try {
        const response = await fetch('/api/craft-equipment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ equipment_id: equipmentId })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                applyResourcePayload(data);
                if (data.equipment_counts) {
                    gameState.equipmentCounts = data.equipment_counts;
                }
                if (data.equipment) {
                    gameState.equipment = data.equipment;
                }
                if (data.inventory) {
                    updateInventoryFromPayload(data.inventory);
                }
                await loadStoryData(); // Reload equipment counts
                updateDisplay();
                loadCrafting();
                // Sync character panel if on character tab
                const activeTab = document.querySelector('.tab-content.active');
                if (activeTab && activeTab.id === 'character-tab') {
                    loadCharacterPanel();
                }
            } else {
                showCustomAlert(data.error || 'Chyba při výrobě', { type: 'error' });
            }
        }
    } catch (error) {
        console.error('Error crafting:', error);
    }
}

// Building icons mapping
const BUILDING_ICONS = {
    'lumberjack_hut': '🪓',
    'forest_route': '🛤️',
    'sawmill': '⚙️',
    'plank_route': '🚛',
    'farmstead': '🌾',
    'field_route': '🛣️',
    'mill': '🏭',
    'bakery_route': '🚚',
    'bakery': '🍞',
    'fishery': '🎣',
    'dock_route': '⚓',
    'courier_guild': '📦',
    'workshop': '🔨',
    'market': '🏪',
    'temple': '🏛️'
};

// Category labels
const CATEGORY_LABELS = {
    'production': 'Výroba',
    'logistics': 'Logistika',
    'infrastructure': 'Infrastruktura',
    'support': 'Podpora'
};

// Setup buildings
function setupBuildings() {
    // Setup filter buttons
    const filterButtons = document.querySelectorAll('.buildings-filter-btn');
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const category = btn.dataset.category;
            filterBuildingsByCategory(category);
        });
    });
}

let currentBuildingFilter = 'all';

function filterBuildingsByCategory(category) {
    currentBuildingFilter = category;
    loadBuildings();
}

function loadBuildings() {
    const buildingsList = document.getElementById('buildingsList');
    if (!buildingsList) return;
    
    buildingsList.innerHTML = '';
    
    const unlocked = gameState.story?.unlocked_buildings || [];
    const builtMap = gameState.buildings || {};
    
    // Sort buildings by order property
    const sortedBuildings = Object.entries(buildingsDefs).sort((a, b) => {
        const orderA = a[1].order || 999;
        const orderB = b[1].order || 999;
        return orderA - orderB;
    });
    
    for (const [id, def] of sortedBuildings) {
        // Filter by category
        if (currentBuildingFilter !== 'all' && def.category !== currentBuildingFilter) {
            continue;
        }
        
        const item = document.createElement('div');
        item.className = 'building-item';
        item.dataset.buildingId = id;
        item.dataset.category = def.category || 'other';
        
        const currentLevel = builtMap?.[id] || 0;
        const isBuilt = currentLevel > 0;
        const prerequisites = def.prerequisites || [];
        const missingPrereqs = prerequisites.filter(req => (builtMap?.[req] || 0) <= 0);
        const prereqsMet = missingPrereqs.length === 0;
        const isUnlocked = id === 'workshop' || def.always_available || unlocked.includes(id);
        const canBuildNow = isUnlocked && prereqsMet && !isBuilt;
        
        const isRepeatable = def.repeatable || false;
        const maxLevel = def.max_level || 1;
        const canUpgrade = isBuilt && isRepeatable && currentLevel < maxLevel;
        
        if (isBuilt) {
            item.classList.add('built');
        }
        
        if (!isUnlocked) {
            item.classList.add('locked');
        }
        
        // Calculate build cost
        const baseCost = def.cost;
        const effectiveCost = applyInflationToCostMap(baseCost);
        const hasResources = canAffordCraft(effectiveCost);
        const canAfford = canBuildNow && hasResources;
        
        // Calculate upgrade cost if applicable
        let upgradeCost = {};
        let canAffordUpgrade = false;
        if (canUpgrade) {
            const levelCostMultiplier = def.level_cost_multiplier || 2.0;
            const costMultiplier = Math.pow(levelCostMultiplier, currentLevel - 1);
            for (const [resource, amount] of Object.entries(baseCost)) {
                upgradeCost[resource] = Math.floor(amount * costMultiplier);
            }
            const effectiveUpgradeCost = applyInflationToCostMap(upgradeCost);
            canAffordUpgrade = canAffordCraft(effectiveUpgradeCost);
        }
        
        let lockReason = '';
        if (!isUnlocked) {
            lockReason = 'Ještě není odemčeno';
        } else if (!prereqsMet) {
            const names = missingPrereqs.map(req => buildingsDefs[req]?.name || req);
            lockReason = `Nejdřív postav: ${names.join(', ')}`;
        }
        
        const icon = BUILDING_ICONS[id] || '🏗️';
        const category = def.category || 'other';
        const categoryLabel = CATEGORY_LABELS[category] || category;
        
        let statusHTML = '';
        if (isBuilt) {
            statusHTML = `
                <div class="building-status built">
                    <span class="building-status-icon">✅</span>
                    <span>Postaveno - Úroveň ${currentLevel}${maxLevel > 1 ? `/${maxLevel}` : ''}</span>
                </div>
            `;
        } else if (lockReason) {
            statusHTML = `
                <div class="building-status locked">
                    <span class="building-status-icon">🔒</span>
                    <span>Zamčeno</span>
                </div>
            `;
        }
        
        item.innerHTML = `
            <div class="building-header">
                <div class="building-icon">${icon}</div>
                <div class="building-info">
                    <span class="building-category ${category}">${categoryLabel}</span>
                    <h4>${def.name}</h4>
                </div>
            </div>
            <p class="building-description">${def.description}</p>
            ${statusHTML}
            ${lockReason ? `<div class="building-lock-reason">${lockReason}</div>` : ''}
            ${prerequisites.length > 0 && !isBuilt ? `
                <div class="building-prerequisites">
                    <div class="building-prerequisites-label">Požadavky:</div>
                    <div class="building-prerequisites-list">
                        ${prerequisites.map(req => {
                            const reqName = buildingsDefs[req]?.name || req;
                            const reqBuilt = (builtMap?.[req] || 0) > 0;
                            return `<span style="color: ${reqBuilt ? '#4caf50' : '#f44336'}">${reqBuilt ? '✅' : '❌'} ${reqName}</span>`;
                        }).join(', ')}
                    </div>
                </div>
            ` : ''}
            ${!isBuilt ? `
                <div class="building-cost">
                    <div class="building-cost-label">Cena stavby:</div>
                    <div class="building-cost-items">
                        ${Object.entries(effectiveCost).filter(([_, c]) => c > 0).map(([resource, c]) => 
                            `<span class="cost-item ${getResourceAmount(resource) < c ? 'insufficient' : ''}">
                                ${getResourceIcon(resource)} ${formatCostValue(c)}
                            </span>`
                        ).join('')}
                    </div>
                </div>
                <div class="building-actions">
                    <button class="btn-build" onclick="buildBuilding('${id}')" ${!canAfford ? 'disabled' : ''}>
                        <span>🏗️</span>
                        <span>Postavit</span>
                    </button>
                </div>
            ` : ''}
            ${canUpgrade && Object.keys(upgradeCost).length > 0 ? `
                <div class="building-upgrade-section">
                    <div class="building-upgrade-label">Upgrade na úroveň ${currentLevel + 1}:</div>
                    <div class="building-cost-items">
                        ${Object.entries(applyInflationToCostMap(upgradeCost)).filter(([_, c]) => c > 0).map(([resource, c]) => 
                            `<span class="cost-item ${getResourceAmount(resource) < c ? 'insufficient' : ''}">
                                ${getResourceIcon(resource)} ${formatCostValue(c)}
                            </span>`
                        ).join('')}
                    </div>
                    <div class="building-actions">
                        <button class="btn-upgrade-building" onclick="upgradeBuilding('${id}')" ${!canAffordUpgrade ? 'disabled' : ''}>
                            <span>⬆️</span>
                            <span>Upgradovat</span>
                        </button>
                    </div>
                </div>
            ` : ''}
        `;
        
        buildingsList.appendChild(item);
    }
}

async function buildBuilding(buildingType) {
    try {
        const response = await fetch('/api/build-building', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ building_type: buildingType })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                applyResourcePayload(data);
                if (!gameState.buildings) gameState.buildings = {};
                gameState.buildings[buildingType] = 1;
                updateDisplay();
                loadBuildings();
            } else {
                showCustomAlert(data.error || 'Chyba při stavbě', { type: 'error' });
            }
        }
    } catch (error) {
        console.error('Error building:', error);
    }
}

async function upgradeBuilding(buildingType) {
    try {
        const response = await fetch('/api/upgrade-building', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ building_type: buildingType })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                applyResourcePayload(data);
                if (!gameState.buildings) gameState.buildings = {};
                gameState.buildings[buildingType] = data.new_level;
                updateDisplay();
                loadBuildings();
            } else {
                showCustomAlert(data.error || 'Chyba při upgradu', { type: 'error' });
            }
        }
    } catch (error) {
        console.error('Error upgrading building:', error);
    }
}

// Setup gems
function setupGems() {
    // Will be populated when game state loads
}

function loadGems() {
    const gemsList = document.getElementById('gemsList');
    if (!gemsList) return;
    
    gemsList.innerHTML = '';
    
    const playerGems = gameState.gems || {};
    
    // Sort gems by order
    const gemOrder = ['gem_strength', 'gem_dexterity', 'gem_intelligence', 'gem_constitution', 'gem_luck', 'gem_universal'];
    
    for (const gemType of gemOrder) {
        const def = gemsDefs[gemType];
        if (!def) continue;
        
        const item = document.createElement('div');
        item.className = 'gem-item';
        item.style.borderLeft = `4px solid ${def.color || '#888'}`;
        
        const currentLevel = playerGems[gemType] || 0;
        const maxLevel = Math.max(...Object.keys(def.levels).map(Number));
        const canUpgrade = currentLevel < maxLevel;
        const nextLevel = currentLevel + 1;
        
        const currentBonus = currentLevel > 0 ? def.levels[currentLevel]?.bonus || 0 : 0;
        const nextBonus = canUpgrade ? def.levels[nextLevel]?.bonus || 0 : 0;
        const nextCost = canUpgrade ? def.levels[nextLevel]?.cost || {} : {};
        
        const effectiveCost = applyInflationToCostMap(nextCost);
        const canAfford = canUpgrade && canAffordCraft(effectiveCost);
        
        const statLabel = {
            'strength': 'Síla',
            'dexterity': 'Obratnost',
            'intelligence': 'Inteligence',
            'constitution': 'Odolnost',
            'luck': 'Štěstí',
            'universal': 'Všechny atributy'
        }[def.stat_type] || def.stat_type;
        
        item.innerHTML = `
            <div class="gem-header">
                <span class="gem-icon" style="font-size: 2em; color: ${def.color || '#888'};">${def.icon}</span>
                <div class="gem-info">
                    <h4>${def.name}</h4>
                    <p class="gem-description">${def.description}</p>
                    <p class="gem-stat-type" style="color: ${def.color || '#888'};">Zvyšuje: ${statLabel}</p>
                </div>
            </div>
            <div class="gem-level-info">
                ${currentLevel > 0 ? `
                    <div class="gem-current">
                        <strong>Úroveň ${currentLevel}/${maxLevel}</strong>
                        <span style="color: ${def.color || '#888'};">+${currentBonus} ${statLabel}</span>
                    </div>
                ` : `
                    <div class="gem-current">
                        <strong>Nevlastněno</strong>
                    </div>
                `}
                ${canUpgrade ? `
                    <div class="gem-upgrade">
                        <div class="upgrade-cost" style="margin: 10px 0;">
                            <strong>${currentLevel === 0 ? 'Zakoupit' : 'Upgrade na'} úroveň ${nextLevel}:</strong>
                            ${Object.entries(effectiveCost).filter(([_, c]) => c > 0).map(([resource, c]) => 
                                `<span class="cost-item ${getResourceAmount(resource) < c ? 'insufficient' : ''}">
                                    ${getResourceIcon(resource)} ${formatCostValue(c)}
                                </span>`
                            ).join('')}
                        </div>
                        <div class="gem-bonus-preview" style="color: ${def.color || '#888'}; margin-bottom: 10px;">
                            ${currentLevel > 0 ? `→ +${nextBonus}` : `+${nextBonus}`} ${statLabel}
                        </div>
                        <button class="btn-buy" onclick="upgradeGem('${gemType}')" ${!canAfford ? 'disabled' : ''} style="background: ${def.color || '#888'};">
                            ${currentLevel === 0 ? 'Zakoupit' : 'Upgradovat'}
                        </button>
                    </div>
                ` : currentLevel > 0 ? `
                    <div class="gem-max-level" style="color: #4CAF50; font-weight: bold; margin-top: 10px;">
                        ✓ Maximální úroveň dosažena
                    </div>
                ` : ''}
            </div>
        `;
        
        gemsList.appendChild(item);
    }
}

async function upgradeGem(gemType) {
    try {
        const response = await fetch('/api/gems/upgrade', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gem_type: gemType })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                applyResourcePayload(data);
                if (!gameState.gems) gameState.gems = {};
                gameState.gems[gemType] = data.new_level;
                updateDisplay();
                loadGems();
                // Refresh character stats if on character tab
                if (document.getElementById('character-tab')?.classList.contains('active')) {
                    loadCharacterPanel();
                }
            } else {
                showCustomAlert(data.error || 'Chyba při upgradu drahokamu', { type: 'error' });
            }
        }
    } catch (error) {
        console.error('Error upgrading gem:', error);
    }
}

// Setup quests
function setupQuests() {
    // Will be populated when game state loads
}

function loadQuests() {
    const questsList = document.getElementById('questsList');
    const currentChapter = document.getElementById('currentChapter');
    if (!questsList || !currentChapter) return;
    
    const chapterNum = gameState.story?.current_chapter || 1;
    const chapter = storyData[chapterNum];
    const completed = gameState.story?.completed_quests || [];
    
    if (chapter) {
        currentChapter.innerHTML = `
            <h4>Kapitola ${chapterNum}: ${chapter.title}</h4>
            <p>${chapter.description}</p>
        `;
        
        const questDefinitions = Array.isArray(chapter.quests) ? [...chapter.quests] : [];
        questDefinitions.sort((a, b) => {
            if (!!a.optional === !!b.optional) return 0;
            return a.optional ? 1 : -1;
        });
        
        const questSignature = questDefinitions.map(q => `${q.id}:${q.optional ? 1 : 0}`);
        const currentQuestState = JSON.stringify({ chapter: chapterNum, completed, questSignature });
        if (questsList.dataset.questState === currentQuestState) {
            return; // No change, skip rebuild
        }
        questsList.dataset.questState = currentQuestState;
        
        questsList.innerHTML = '';
        let storyHeaderRendered = false;
        let sideHeaderRendered = false;
        
        questDefinitions.forEach(quest => {
            const isCompleted = completed.includes(quest.id);
            if (!quest.optional && !storyHeaderRendered && !isCompleted) {
                const divider = document.createElement('div');
                divider.className = 'quest-divider';
                divider.textContent = 'Příběhové úkoly';
                questsList.appendChild(divider);
                storyHeaderRendered = true;
            }
            if (quest.optional && !sideHeaderRendered && !isCompleted) {
                const divider = document.createElement('div');
                divider.className = 'quest-divider';
                divider.textContent = 'Vedlejší úkoly';
                questsList.appendChild(divider);
                sideHeaderRendered = true;
            }
            
            if (isCompleted) return;
            
            const item = document.createElement('div');
            item.className = `quest-item`;
            
            const { progress, text: progressText } = getQuestProgressInfo(quest);
            const requirementSummary = formatQuestRequirement(quest.requirement);
            const tag = quest.optional
                ? '<span class="quest-tag quest-tag-optional">Volitelný</span>'
                : '<span class="quest-tag quest-tag-story">Příběh</span>';
            const rewardEntries = Object.entries(quest.reward || {}).filter(([, value]) => value);
            const rewardText = rewardEntries.length
                ? rewardEntries.map(([r, v]) => `${getResourceIcon(r)} ${formatNumber(v)}`).join(', ')
                : '';
            
            item.innerHTML = `
                <div class="quest-headline">
                    <h5>${quest.name}</h5>
                    ${tag}
                </div>
                <p>${quest.description}</p>
                ${requirementSummary ? `<p class="quest-requirement">${requirementSummary}</p>` : ''}
                ${progressText ? `
                    <div class="quest-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${Math.min(100, Math.max(0, progress))}%">
                                ${Math.max(0, progress).toFixed(0)}%
                            </div>
                        </div>
                        <div class="quest-progress-text">
                            ${progressText}
                        </div>
                    </div>
                ` : ''}
                <button class="btn-blue" onclick="completeQuest('${quest.id}')" style="margin-top: 8px;">
                    Dokončit
                </button>
                ${rewardText ? `
                    <div class="quest-reward">
                        Odměna: ${rewardText}
                    </div>
                ` : ''}
            `;
            
            questsList.appendChild(item);
        });
    }
}

async function completeQuest(questId) {
    try {
        const response = await fetch('/api/complete-quest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ quest_id: questId })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ error: 'Chyba serveru' }));
            showCustomAlert(errorData.error || 'Quest nelze dokončit', { type: 'error' });
            return;
        }
        
        const data = await response.json();
        if (data.success) {
            applyResourcePayload(data);
            if (data.unlocked_currencies) {
                if (!gameState.story) gameState.story = {};
                gameState.story.unlocked_currencies = data.unlocked_currencies;
            }
            if (data.unlocked_buildings) {
                if (!gameState.story) gameState.story = {};
                gameState.story.unlocked_buildings = data.unlocked_buildings;
            }
            if (!gameState.story) gameState.story = {};
            if (!gameState.story.completed_quests) {
                gameState.story.completed_quests = [];
            }
            if (!gameState.story.completed_quests.includes(questId)) {
                gameState.story.completed_quests.push(questId);
            }
            await loadGameState(); // Reload full state
            updateDisplay();
            loadQuests();
            loadBuildings();
            loadCrafting();
        } else {
            showCustomAlert(data.error || 'Quest nelze dokončit', { type: 'error' });
        }
    } catch (error) {
        console.error('Error completing quest:', error);
    }
}

// Equipment tab removed - using character panel instead
function setupEquipment() {
    // Equipment tab removed - all equipment management is in character panel
}

function loadEquipment() {
    // Equipment tab removed - all equipment management is in character panel
    // This function is kept for compatibility but does nothing
}

function normalizeInventoryPayload(payload = {}) {
    return {
        items: Array.isArray(payload.items) ? payload.items : [],
        summary: payload.summary || {},
        market: payload.market || {},
        updated_at: payload.updated_at || null
    };
}

function updateInventoryFromPayload(payload) {
    if (payload) {
        gameState.inventory = normalizeInventoryPayload(payload);
    }
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab && activeTab.id === 'inventory-tab') {
        loadInventory();
    }
}

function setupInventory() {
    const searchInput = document.getElementById('inventorySearch');
    if (searchInput) {
        searchInput.addEventListener('input', (event) => {
            inventoryFilters.search = event.target.value.toLowerCase().trim();
            loadInventory();
        });
    }
    const raritySelect = document.getElementById('inventoryRarityFilter');
    if (raritySelect) {
        raritySelect.addEventListener('change', (event) => {
            inventoryFilters.rarity = event.target.value;
            loadInventory();
        });
    }
    const refreshBtn = document.getElementById('inventoryRefreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshInventoryMarket);
    }
    loadInventory();
}

function loadInventory() {
    renderInventorySummary(gameState.inventory?.summary || {});
    renderInventoryList();
    renderInventoryMarket();
}

function renderInventorySummary(summary = {}) {
    const container = document.getElementById('inventorySummary');
    if (!container) return;
    const rarityEntries = Object.entries(summary.rarity_breakdown || {});
    const cards = [
        {
            label: 'Položek',
            value: summary.total_items || 0
        },
        {
            label: 'Vybaveno',
            value: summary.equipped_items || 0
        },
        {
            label: 'Duplikáty',
            value: summary.duplicates || 0
        },
        {
            label: 'Odhad hodnoty',
            value: `${formatInventoryValue(summary.estimated_sell_value || 0)} 💰`
        }
    ];
    let html = cards.map(card => `
        <div class="inventory-summary-card">
            <h4>${card.label}</h4>
            <strong>${card.value}</strong>
        </div>
    `).join('');
    if (rarityEntries.length) {
        const chips = rarityEntries.map(([rarity, count]) => {
            const meta = getRarityMeta(rarity);
            return `<span class="inventory-chip rarity-pill rarity-${meta.key}">${meta.label}: ${count}</span>`;
        }).join('');
        html += `
            <div class="inventory-summary-card">
                <h4>Rarity</h4>
                <div class="inventory-item-meta">${chips}</div>
            </div>
        `;
    }
    container.innerHTML = html;
}

function renderInventoryList() {
    const listEl = document.getElementById('inventoryList');
    if (!listEl) return;
    const items = (gameState.inventory?.items || []).slice();
    items.sort((a, b) => {
        const aDate = new Date(a.acquired_at || 0).getTime();
        const bDate = new Date(b.acquired_at || 0).getTime();
        return bDate - aDate;
    });
    const searchTerm = (inventoryFilters.search || '').trim();
    const filtered = items.filter(item => {
        // Resources should always show regardless of rarity filter
        if (inventoryFilters.rarity !== 'all' && item.rarity !== inventoryFilters.rarity && item.item_type !== 'resource') {
            return false;
        }
        if (searchTerm) {
            const haystack = [
                item.name,
                item.slot,
                item.equipment_id,
                item.acquired_via,
                item.acquisition_note
            ].filter(Boolean).join(' ').toLowerCase();
            return haystack.includes(searchTerm);
        }
        return true;
    });
    if (!filtered.length) {
        listEl.innerHTML = '<div class="inventory-empty">Inventář je zatím prázdný. Vyrob něco v dílně!</div>';
        return;
    }
    listEl.innerHTML = filtered.map(item => {
        const rarity = getRarityMeta(item.rarity);
        const marketInfo = gameState.inventory?.market?.[item.equipment_id] || {};
        const isResource = item.item_type === 'resource';
        const resourceIcon = isResource ? (CASE_CURRENCY_ICONS[item.equipment_id] || '📦') : '';
        const totalValue = isResource && item.amount ? (item.amount * (item.sell_value || item.market_value || item.base_value)) : (item.sell_value || item.market_value || item.base_value);
        
        // Get item icon - prefer icon from API, then image, then slot icon, then resource icon
        let itemIcon = '';
        if (item.icon) {
            // Use emoji icon directly (for fruits)
            itemIcon = item.icon;
        } else if (item.image) {
            itemIcon = `<img src="/images/${item.image}" alt="${item.name}" class="inventory-item-icon-img" onerror="this.style.display='none'; this.parentElement.innerHTML='${item.slot ? getSlotIcon(item.slot) : resourceIcon || '📦'}';" />`;
        } else if (item.slot) {
            itemIcon = getSlotIcon(item.slot);
        } else {
            itemIcon = resourceIcon || '📦';
        }
        
        const acquisitionText = item.acquisition_note || 'Získáno';
        const acquiredTime = item.acquired_at ? formatInventoryTimestamp(item.acquired_at) : '';
        const supplyText = typeof marketInfo.current_supply === 'number' ? `V oběhu: ${marketInfo.current_supply}` : '';
        
        const isFruit = item.item_type === 'fruit' || item.icon;
        return `
            <div class="inventory-item-card ${item.equipped ? 'equipped' : ''} ${isResource ? 'inventory-resource' : ''} ${isFruit ? 'inventory-fruit' : ''}" ${isFruit ? 'data-item-type="fruit"' : ''}>
                <div class="inventory-item-card-header">
                    <div class="inventory-item-icon-wrapper">
                        ${itemIcon}
                    </div>
                    <div class="inventory-item-card-content">
                        <h3 class="inventory-item-name">${item.name}</h3>
                        <div class="inventory-item-tags">
                            ${!isResource ? `<span class="inventory-tag rarity-tag rarity-${rarity.key}">${rarity.label}</span>` : ''}
                            ${item.slot ? `<span class="inventory-tag category-tag">${getSlotLabel(item.slot)}</span>` : ''}
                            ${item.equipped ? '<span class="inventory-tag equipped-tag">Vybaveno</span>' : ''}
                            ${isResource && item.amount ? `<span class="inventory-tag">${formatNumber(item.amount)} ks</span>` : ''}
                        </div>
                        <div class="inventory-item-info">
                            <span class="inventory-item-acquisition">${acquisitionText}${acquiredTime ? ` • ${acquiredTime}` : ''}</span>
                            ${supplyText ? `<span class="inventory-item-supply">${supplyText}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="inventory-item-card-footer">
                    ${isResource ? `
                        <input type="number" id="sellAmount_${item.instance_id}" 
                               class="inventory-sell-amount-input"
                               placeholder="Množství" 
                               min="0.01" 
                               max="${item.amount || 0}" 
                               step="0.01">
                        <button class="inventory-sell-btn" data-sell-id="${item.instance_id}" onclick="sellInventoryItem('${item.instance_id}')">
                            Prodat za ${formatInventoryValue(totalValue)} 💰
                        </button>
                    ` : `
                        <button class="inventory-sell-btn" data-sell-id="${item.instance_id}" onclick="sellInventoryItem(${item.instance_id})">
                            Prodat za ${formatInventoryValue(item.sell_value || item.market_value || item.base_value)} 💰
                        </button>
                    `}
                </div>
            </div>
        `;
    }).join('');
}

function renderInventoryMarket() {
    const panel = document.getElementById('inventoryMarketPanel');
    if (!panel) return;
    const market = gameState.inventory?.market || {};
    const entries = Object.entries(market);
    if (!entries.length) {
        panel.innerHTML = '<p class="muted">Tržní ekonomika položek se teprve probouzí.</p>';
        return;
    }
    const sortedByMultiplier = entries.slice().sort((a, b) => (b[1].price_multiplier || 0) - (a[1].price_multiplier || 0));
    const trending = sortedByMultiplier.slice(0, 4);
    const updatedAgo = formatInventoryTimestamp(gameState.inventory?.updated_at || new Date().toISOString());
    panel.innerHTML = `
        <div>
            <h3>🔥 Nejživější trh</h3>
            <ul class="inventory-market-list">
                ${trending.map(([itemId, info]) => {
                    const def = equipmentDefs[itemId] || {};
                    const trendClass = info.trend === 'up' ? 'trend-up' : info.trend === 'down' ? 'trend-down' : 'trend-flat';
                    const trendSymbol = info.trend === 'up' ? '▲' : info.trend === 'down' ? '▼' : '↔';
                    return `
                        <li class="inventory-market-row">
                            <div>
                                <strong>${def.name || itemId}</strong>
                                <small>V oběhu: ${info.current_supply || 0}</small>
                            </div>
                            <div class="${trendClass}">
                                ${formatInventoryValue(info.market_value || info.base_value)} 💰 ${trendSymbol}
                            </div>
                        </li>
                    `;
                }).join('')}
            </ul>
        </div>
        <div class="inventory-market-card">
            <strong>Poslední update:</strong>
            <div>${updatedAgo}</div>
            <p class="muted">Ceny reagují na výrobu i prodej hráčů.</p>
        </div>
    `;
}

function formatInventoryTimestamp(timestamp) {
    if (!timestamp) return 'Neznámý původ';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) {
        return timestamp;
    }
    const diffMs = Date.now() - date.getTime();
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return 'právě teď';
    if (minutes < 60) return `před ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `před ${hours} h`;
    const days = Math.floor(hours / 24);
    return `před ${days} dny`;
}

function formatInventoryValue(value = 0) {
    if (!Number.isFinite(value)) return '0';
    if (value >= 1_000_000) return formatNumber(value);
    if (value >= 10_000) return `${Math.round(value).toLocaleString('cs-CZ')}`;
    return value.toFixed(2);
}

function setInventoryMessage(message, isError = false) {
    const messageEl = document.getElementById('inventoryMessage');
    if (!messageEl) return;
    messageEl.textContent = message || '';
    messageEl.classList.toggle('error', Boolean(message) && isError);
    messageEl.classList.toggle('success', Boolean(message) && !isError);
}

async function refreshInventoryMarket() {
    try {
        setInventoryMessage('Aktualizuji inventář...', false);
        const response = await fetch('/api/inventory');
        const data = await response.json();
        if (!response.ok || !data.success) {
            setInventoryMessage(data.error || 'Inventář se nepodařilo načíst.', true);
            return;
        }
        updateInventoryFromPayload(data.inventory);
        setInventoryMessage('Inventář aktualizován.', false);
    } catch (error) {
        console.error('Error refreshing inventory:', error);
        setInventoryMessage('Chyba při načítání inventáře.', true);
    }
}

async function sellInventoryItem(instanceId) {
    if (!instanceId) return;
    const button = document.querySelector(`[data-sell-id="${instanceId}"]`);
    const isResource = typeof instanceId === 'string' && instanceId.startsWith('resource_');
    let sellAmount = null;
    
    if (isResource) {
        const amountInput = document.getElementById(`sellAmount_${instanceId}`);
        if (amountInput && amountInput.value) {
            sellAmount = parseFloat(amountInput.value);
            if (isNaN(sellAmount) || sellAmount <= 0) {
                setInventoryMessage('Neplatné množství', true);
                return;
            }
        }
    }
    
    if (button) {
        button.disabled = true;
        button.dataset.original = button.textContent;
        button.textContent = 'Prodávám...';
    }
    try {
        const requestBody = { instance_id: instanceId };
        if (sellAmount !== null) {
            requestBody.amount = sellAmount;
        }
        
        const response = await fetch('/api/inventory/sell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            setInventoryMessage(data.error || 'Předmět se nepodařilo prodat.', true);
            return;
        }
        applyResourcePayload(data);
        if (data.equipment_counts) {
            gameState.equipmentCounts = data.equipment_counts;
        }
        if (data.equipment) {
            gameState.equipment = data.equipment;
        }
        updateInventoryFromPayload(data.inventory);
        setInventoryMessage(data.message || 'Předmět prodán.', false);
        updateDisplay();
    } catch (error) {
        console.error('Error selling item:', error);
        setInventoryMessage('Prodej selhal, zkus to znovu.', true);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = button.dataset.original || 'Prodat';
        }
    }
}

// Setup player view
function setupPlayerView() {
    const viewBtn = document.getElementById('viewPlayerBtn');
    if (viewBtn) {
        viewBtn.addEventListener('click', async () => {
            const username = document.getElementById('playerSearch').value;
            if (!username) {
                showCustomAlert('Zadej jméno hráče', { type: 'warning' });
                return;
            }
            
            try {
                const response = await fetch(`/api/player-equipment/${username}`);
                if (response.ok) {
                    const data = await response.json();
                    const viewDiv = document.getElementById('playerEquipmentView');
                    if (viewDiv) {
                        if (data.equipment.length === 0) {
                            viewDiv.innerHTML = `<p>${username} nemá žádný equipment.</p>`;
                        } else {
                            viewDiv.innerHTML = `
                                <h4>Equipment hráče ${username}:</h4>
                                <ul>
                                    ${data.equipment.map(eq => {
                                        const def = equipmentDefs[eq.id];
                                        return `<li><strong>${eq.slot}:</strong> ${def ? def.name : eq.id}</li>`;
                                    }).join('')}
                                </ul>
                            `;
                        }
                    }
                } else {
                    showCustomAlert('Hráč nenalezen', { type: 'warning' });
                }
            } catch (error) {
                console.error('Error loading player equipment:', error);
            }
        });
    }
}

// Update only resources (for background updates)
function updateResourcesOnly() {
    const rates = getEffectiveGenerationRates();
    
    // Update top status bar with rates
    const gooncoinsStatus = document.getElementById('gooncoinsStatus');
    if (gooncoinsStatus) {
        const rate = rates.gooncoins || 0;
        const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}`;
        gooncoinsStatus.innerHTML = `💰 <span id="gooncoinsValue">${formatNumber(gameState.gooncoins)}</span> (${formattedRate}/s)`;
    }
    
    // Update nav resources with rates
    const navRates = ['gooncoinsRate', 'astmaRate', 'poharkyRate', 'mrkevRate', 'uzenéRate'];
    const rateKeys = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'];
    navRates.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (el) {
            const rate = rates[rateKeys[idx]] || 0;
            const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}/s`;
            el.textContent = formattedRate;
        }
    });
    
    const navValues = ['gooncoinsValueNav', 'astmaValueNav', 'poharkyValueNav', 'mrkevValueNav', 'uzenéValueNav'];
    const resources = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'];
    navValues.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (el) el.textContent = formatNumber(gameState[resources[idx]] || 0);
    });
    
    refreshCaseButtonState();
}

// Update display to include all new elements
let lastFullDisplayUpdate = 0;
const FULL_DISPLAY_UPDATE_INTERVAL = 1000; // Only reload heavy content once per second
let updateDisplayCallCount = 0;
let updateDisplayStartTime = Date.now();

function updateDisplay() {
    updateDisplayCallCount++;
    const updateStart = performance.now();
    
    updateResourcesOnly();
    updateEconomyPanel();
    
    // Update click value
    const clickValueEl = document.getElementById('clickValue');
    if (clickValueEl) clickValueEl.textContent = gameState.clickValue.toFixed(1);
    
    // Throttle heavy content reloads to prevent freezing
    const now = Date.now();
    const shouldReloadHeavyContent = (now - lastFullDisplayUpdate) >= FULL_DISPLAY_UPDATE_INTERVAL;
    
    // Reload dynamic content only if on relevant tabs
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        // Only reload heavy content if enough time has passed
        if (shouldReloadHeavyContent) {
            if (activeTab.id === 'crafting-tab') {
                loadCrafting();
            } else if (activeTab.id === 'buildings-tab') {
                loadBuildings();
            } else if (activeTab.id === 'gems-tab') {
                loadGems();
            } else if (activeTab.id === 'inventory-tab') {
                loadInventory();
            } else if (activeTab.id === 'leaderboard-tab') {
                loadLeaderboard();
            } else if (activeTab.id === 'character-tab') {
                loadCharacterPanel();
            }
            
            // Only update quests if we're not on inventory tab (prevents flickering)
            if (activeTab.id !== 'inventory-tab') {
                loadQuests();
            }
            
            lastFullDisplayUpdate = now;
        }
    }
    
    const updateTime = performance.now() - updateStart;
    if (updateDisplayCallCount % 50 === 0) {
        const elapsed = ((Date.now() - updateDisplayStartTime) / 1000).toFixed(1);
        console.log(`[DEBUG] updateDisplay: ${updateDisplayCallCount} calls in ${elapsed}s, last call took ${updateTime.toFixed(1)}ms`);
    }
}

// Character Panel Functions
let characterStats = {
    level: 1,
    experience: 0,
    experience_needed: 100,
    strength: 10,
    dexterity: 10,
    intelligence: 10,
    constitution: 10,
    luck: 10,
    available_points: 0,
    combat_stats: {},
    equipped_items: {}
};

async function loadCharacterPanel() {
    try {
        const response = await fetch('/api/character-stats');
        if (response.ok) {
            const data = await response.json();
            characterStats = data;
            updateCharacterPanel();
            setupCharacterPanelEvents();
        } else {
            console.error('Failed to load character stats');
        }
    } catch (error) {
        console.error('Error loading character panel:', error);
    }
}

function updateCharacterPanel() {
    // Update level and experience
    const levelEl = document.getElementById('characterLevel');
    if (levelEl) levelEl.textContent = characterStats.level;
    
    const currentExpEl = document.getElementById('currentExp');
    const neededExpEl = document.getElementById('neededExp');
    const expFillEl = document.getElementById('experienceFill');
    
    if (currentExpEl) currentExpEl.textContent = Math.floor(characterStats.experience);
    if (neededExpEl) neededExpEl.textContent = Math.floor(characterStats.experience_needed);
    
    const expPercent = (characterStats.experience / characterStats.experience_needed) * 100;
    if (expFillEl) {
        expFillEl.style.width = `${Math.min(100, expPercent)}%`;
    }
    
    // Update stats
    document.getElementById('statStrength').textContent = characterStats.strength;
    document.getElementById('statDexterity').textContent = characterStats.dexterity;
    document.getElementById('statIntelligence').textContent = characterStats.intelligence;
    document.getElementById('statConstitution').textContent = characterStats.constitution;
    document.getElementById('statLuck').textContent = characterStats.luck;
    
    // Update available points
    const availablePointsEl = document.getElementById('availablePoints');
    if (availablePointsEl) availablePointsEl.textContent = characterStats.available_points;
    
    // Update class selector
    const classSelectEl = document.getElementById('characterClassSelect');
    if (classSelectEl && characterStats.class) {
        classSelectEl.value = characterStats.class;
        updateClassDescription(characterStats.class);
    }
    
    // Update upgrade buttons
    const upgradeButtons = document.querySelectorAll('.stat-upgrade-btn');
    upgradeButtons.forEach(btn => {
        btn.disabled = characterStats.available_points < 1;
    });
    
    // Update combat stats
    const combatStats = characterStats.combat_stats || {};
    const combatAttackEl = document.getElementById('combatAttack');
    const combatDefenseEl = document.getElementById('combatDefense');
    const combatHpEl = document.getElementById('combatHp');
    const combatEvasionEl = document.getElementById('combatEvasion');
    const combatCritEl = document.getElementById('combatCrit');
    const combatLuckEl = document.getElementById('combatLuck');
    
    if (combatAttackEl) combatAttackEl.textContent = combatStats.attack?.toFixed(1) || '0';
    if (combatDefenseEl) combatDefenseEl.textContent = combatStats.defense?.toFixed(1) || '0';
    if (combatHpEl) combatHpEl.textContent = combatStats.hp || '0';
    if (combatEvasionEl) combatEvasionEl.textContent = `${combatStats.evasion?.toFixed(1) || '0'}%`;
    if (combatCritEl) combatCritEl.textContent = `${combatStats.critical_hit?.toFixed(1) || '0'}%`;
    if (combatLuckEl) combatLuckEl.textContent = combatStats.luck?.toFixed(2) || '0';
    
    // Update equipment slots
    updateCharacterEquipmentSlots();
    
    // Update exchange preview
    updateExchangePreview();
}

function updateCharacterEquipmentSlots() {
    const equippedItems = characterStats.equipped_items || {};
    const slotIds = {
        'helmet': 'charHelmetSlot',
        'necklace': 'charNecklaceSlot',
        'weapon': 'charWeaponSlot',
        'armor': 'charArmorSlot',
        'belt': 'charBeltSlot',
        'ring': 'charRingSlot',
        'gloves': 'charGlovesSlot',
        'boots': 'charBootsSlot',
        'special': 'charSpecialSlot',
        'vehicle': 'charVehicleSlot'
    };
    
    Object.entries(slotIds).forEach(([slot, elementId]) => {
        const slotEl = document.getElementById(elementId);
        if (!slotEl) return;
        
        const item = equippedItems[slot];
        if (item) {
            slotEl.classList.add('has-item');
            const iconEl = slotEl.querySelector('.slot-icon');
            const labelEl = slotEl.querySelector('.slot-label');
            
            // Update icon with item image if available
            if (item.image && iconEl) {
                iconEl.innerHTML = `<img src="/images/${item.image}" alt="${item.name}" style="width: 32px; height: 32px; object-fit: contain;" onerror="this.style.display='none'; this.parentElement.innerHTML='${getSlotIcon(slot)}';">`;
            }
            
            // Update label with item name
            if (labelEl) {
                labelEl.textContent = item.name || getSlotLabel(slot);
            }
            
            // Add tooltip with item info
            slotEl.title = `${item.name}\nRarita: ${item.rarity}\nBonus: ${formatItemBonus(item.bonus)}`;
        } else {
            slotEl.classList.remove('has-item');
            const iconEl = slotEl.querySelector('.slot-icon');
            const labelEl = slotEl.querySelector('.slot-label');
            
            if (iconEl && !iconEl.textContent) {
                iconEl.innerHTML = getSlotIcon(slot);
            }
            if (labelEl) {
                labelEl.textContent = getSlotLabel(slot);
            }
            slotEl.title = `Klikni pro vybavení ${getSlotLabel(slot).toLowerCase()}`;
        }
    });
}

function getSlotIcon(slot) {
    const icons = {
        'helmet': '⛑️',
        'necklace': '💎',
        'weapon': '⚔️',
        'armor': '🛡️',
        'belt': '🔗',
        'ring': '💍',
        'gloves': '🧤',
        'boots': '👢',
        'special': '🍀',
        'vehicle': '🚗',
        'fruit': '🍎'
    };
    return icons[slot] || '📦';
}

function getSlotLabel(slot) {
    const labels = {
        'helmet': 'HELMA',
        'fruit': 'SPECIÁLNÍ',
        'necklace': 'NÁHRDELNÍK',
        'weapon': 'ZBRAŇ',
        'armor': 'ZBROJ',
        'belt': 'PÁS',
        'ring': 'PRSTEN',
        'gloves': 'RUKAVICE',
        'boots': 'BOTY',
        'special': 'SPECIÁLNÍ',
        'vehicle': 'VOZIDLO',
        'fruit': 'PLOD'
    };
    return labels[slot] || slot.toUpperCase();
}

function formatItemBonus(bonus) {
    if (!bonus || Object.keys(bonus).length === 0) return 'Žádný';
    const parts = [];
    for (const [key, value] of Object.entries(bonus)) {
        if (typeof value === 'number') {
            if (value > 1) {
                parts.push(`${key}: +${((value - 1) * 100).toFixed(0)}%`);
            } else {
                parts.push(`${key}: +${value}`);
            }
        }
    }
    return parts.join(', ') || 'Žádný';
}

const CLASS_DESCRIPTIONS = {
    'warrior': 'Bojovník s vysokou silou a obranou',
    'mage': 'Mág s vysokou inteligencí a magickým poškozením',
    'scout': 'Zvěd s vysokou obratností a kritickými zásahy'
};

function updateClassDescription(classValue) {
    const descEl = document.getElementById('classDescription');
    if (descEl) {
        descEl.textContent = CLASS_DESCRIPTIONS[classValue] || '';
    }
}

function setupCharacterPanelEvents() {
    // Setup equipment slot click handlers
    setupEquipmentSlotClicks();
    
    // Class selector
    const classSelectEl = document.getElementById('characterClassSelect');
    if (classSelectEl) {
        classSelectEl.addEventListener('change', async (e) => {
            const newClass = e.target.value;
            if (!newClass) return;
            
            classSelectEl.disabled = true;
            try {
                const response = await fetch('/api/character-stats/change-class', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ class: newClass })
                });
                
                const data = await response.json();
                if (data.success) {
                    characterStats.class = data.class;
                    characterStats.combat_stats = data.combat_stats;
                    updateClassDescription(newClass);
                    updateCharacterPanel();
                } else {
                    showCustomAlert(data.error || 'Změna třídy selhala', { type: 'error' });
                    // Revert selection
                    if (characterStats.class) {
                        classSelectEl.value = characterStats.class;
                    }
                }
            } catch (error) {
                console.error('Error changing class:', error);
                showCustomAlert('Chyba při změně třídy', { type: 'error' });
                // Revert selection
                if (characterStats.class) {
                    classSelectEl.value = characterStats.class;
                }
            } finally {
                classSelectEl.disabled = false;
            }
        });
        
        // Update description on hover/focus
        classSelectEl.addEventListener('focus', () => {
            updateClassDescription(classSelectEl.value);
        });
    }
    
    // Upgrade buttons
    const upgradeButtons = document.querySelectorAll('.stat-upgrade-btn');
    upgradeButtons.forEach(btn => {
        btn.replaceWith(btn.cloneNode(true)); // Remove old listeners
    });
    
    document.querySelectorAll('.stat-upgrade-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const stat = btn.dataset.stat;
            if (!stat) return;
            
            btn.disabled = true;
            try {
                const response = await fetch('/api/character-stats/upgrade', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ stat })
                });
                
                const data = await response.json();
                if (data.success) {
                    characterStats[stat] = data.new_value;
                    characterStats.available_points = data.available_points;
                    characterStats.combat_stats = data.combat_stats;
                    updateCharacterPanel();
                } else {
                    showCustomAlert(data.error || 'Upgrade selhal', { type: 'error' });
                }
            } catch (error) {
                console.error('Error upgrading stat:', error);
                showCustomAlert('Chyba při upgradu statu', { type: 'error' });
            } finally {
                btn.disabled = false;
            }
        });
    });
    
    // Exchange points - continuous hold-to-exchange
    const exchangeAmountEl = document.getElementById('exchangeAmount');
    const exchangeBtn = document.getElementById('exchangePointsBtn');
    
    // Remove input field functionality (optional, can keep for display)
    if (exchangeAmountEl) {
        exchangeAmountEl.style.display = 'none'; // Hide input field
    }
    
    // Continuous exchange state
    let exchangeInterval = null;
    let exchangeStartTime = null;
    let isExchanging = false;
    let totalPointsExchanged = 0;
    let totalGooncoinsUsed = 0;
    let exchangeIsRunning = false;
    
    // Speed calculation: starts at 1x, increases gradually
    function getSpeedMultiplier(secondsHeld) {
        // Starts at 1x, increases by 0.1x every 2 seconds, max 5x
        return Math.min(1.0 + (secondsHeld / 2) * 0.1, 5.0);
    }
    
    async function performExchange(speedMultiplier) {
        if (isExchanging) return; // Prevent overlapping requests
        if ((gameState.gooncoins || 0) < 1000) {
            stopExchange();
            setExchangeMessage('Nemáš dostatek Gooncoinů pro směnu', true);
            return;
        }
        
        isExchanging = true;
        const baseAmount = 1000; // Base exchange amount per cycle
        
        try {
            const response = await fetch('/api/character-stats/exchange-points', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    gooncoins: baseAmount,
                    speed_multiplier: speedMultiplier
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                characterStats.available_points = data.available_points;
                gameState.gooncoins = data.gooncoins_remaining;
                totalPointsExchanged += data.points_gained;
                totalGooncoinsUsed += data.gooncoins_used;
                updateCharacterPanel();
                updateResourcesOnly();
                
                // Update button text with speed info
                const secondsHeld = (Date.now() - exchangeStartTime) / 1000;
                const speed = getSpeedMultiplier(secondsHeld);
                exchangeBtn.textContent = `Drž pro směnu (${speed.toFixed(1)}x rychlost)`;
            } else {
                if (data.error && !data.error.includes('dostatek')) {
                    setExchangeMessage(data.error, true);
                }
                stopExchange();
            }
        } catch (error) {
            console.error('Error exchanging points:', error);
            stopExchange();
            setExchangeMessage('Chyba při směně: ' + error.message, true);
        } finally {
            isExchanging = false;
        }
    }
    
    function startExchange() {
        if (exchangeInterval) return; // Already running
        
        if ((gameState.gooncoins || 0) < 1000) {
            setExchangeMessage('Nemáš dostatek Gooncoinů. Potřebuješ alespoň 1000', true);
            return;
        }
        
        exchangeStartTime = Date.now();
        totalPointsExchanged = 0;
        totalGooncoinsUsed = 0;
        exchangeBtn.classList.add('exchanging');
        setExchangeMessage('Drž tlačítko pro kontinuální směnu...', false);
        
        let lastExchangeTime = Date.now();
        exchangeIsRunning = true;
        
        function exchangeLoop() {
            if (!exchangeIsRunning) return; // Stopped
            
            const now = Date.now();
            const secondsHeld = (now - exchangeStartTime) / 1000;
            const speedMultiplier = getSpeedMultiplier(secondsHeld);
            
            // Calculate interval based on speed (faster = shorter interval)
            // At 1x speed: 500ms, at 5x speed: 100ms
            const targetInterval = Math.max(100, 500 / speedMultiplier);
            
            if (now - lastExchangeTime >= targetInterval) {
                performExchange(speedMultiplier);
                lastExchangeTime = now;
            }
            
            // Update button text with current speed
            if (exchangeBtn && exchangeIsRunning) {
                const speed = getSpeedMultiplier(secondsHeld);
                exchangeBtn.textContent = `Drž pro směnu (${speed.toFixed(1)}x rychlost)`;
            }
            
            if (exchangeIsRunning) {
                exchangeInterval = setTimeout(exchangeLoop, 50); // Check every 50ms
            }
        }
        
        // Start the loop
        exchangeInterval = setTimeout(exchangeLoop, 0);
        
        // Also do immediate first exchange
        performExchange(1.0);
    }
    
    function stopExchange() {
        exchangeIsRunning = false;
        if (exchangeInterval) {
            clearTimeout(exchangeInterval);
            exchangeInterval = null;
        }
        exchangeStartTime = null;
        if (exchangeBtn) {
            exchangeBtn.classList.remove('exchanging');
            exchangeBtn.textContent = 'Drž pro směnu';
        }
        
        if (totalPointsExchanged > 0) {
            setExchangeMessage(
                `Získal jsi ${totalPointsExchanged} bod(ů) za ${formatNumber(totalGooncoinsUsed)} Gooncoinů!`, 
                false
            );
        }
    }
    
    if (exchangeBtn) {
        // Remove old click listener by cloning
        const newBtn = exchangeBtn.cloneNode(true);
        exchangeBtn.parentNode.replaceChild(newBtn, exchangeBtn);
        const btn = document.getElementById('exchangePointsBtn');
        
        btn.textContent = 'Drž pro směnu';
        
        // Mouse events
        btn.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startExchange();
        });
        
        btn.addEventListener('mouseup', (e) => {
            e.preventDefault();
            stopExchange();
        });
        
        btn.addEventListener('mouseleave', () => {
            stopExchange();
        });
        
        // Touch events for mobile
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startExchange();
        });
        
        btn.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopExchange();
        });
        
        btn.addEventListener('touchcancel', () => {
            stopExchange();
        });
    }
}

function updateExchangePreview() {
    const exchangeAmountEl = document.getElementById('exchangeAmount');
    const pointsPreviewEl = document.getElementById('pointsPreview');
    
    if (!exchangeAmountEl || !pointsPreviewEl) return;
    
    const amount = parseFloat(exchangeAmountEl.value || 0);
    const points = Math.floor(amount / 1000);
    pointsPreviewEl.textContent = points;
}

function setupEquipmentSlotClicks() {
    const slotElements = document.querySelectorAll('.equipment-slot-char');
    slotElements.forEach(slotEl => {
        // Remove old listeners
        const newSlotEl = slotEl.cloneNode(true);
        slotEl.parentNode.replaceChild(newSlotEl, slotEl);
        
        // Add click handler
        newSlotEl.addEventListener('click', () => {
            const slot = newSlotEl.dataset.slot;
            if (slot) {
                openEquipmentModal(slot);
            }
        });
    });
}

let currentEquipmentModalSlot = null;

async function openEquipmentModal(slot) {
    currentEquipmentModalSlot = slot;
    
    try {
        const response = await fetch(`/api/character/equipment/slot/${slot}`);
        const data = await response.json();
        
        if (!data.success) {
            showCustomAlert(data.error || 'Chyba při načítání itemů', { type: 'error' });
            return;
        }
        
        showEquipmentModal(data);
    } catch (error) {
        console.error('Error loading items for slot:', error);
        showCustomAlert('Chyba při načítání itemů', { type: 'error' });
    }
}

function showEquipmentModal(data) {
    // Remove existing modal if any
    const existingModal = document.getElementById('equipmentModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const slot = data.slot;
    const items = data.items || [];
    const currentlyEquipped = data.currently_equipped;
    
    const modal = document.createElement('div');
    modal.id = 'equipmentModal';
    modal.className = 'equipment-modal-overlay';
    modal.innerHTML = `
        <div class="equipment-modal">
            <div class="equipment-modal-header">
                <h3>Vybavit ${getSlotLabel(slot)}</h3>
                <button class="equipment-modal-close" onclick="closeEquipmentModal()">×</button>
            </div>
            <div class="equipment-modal-content">
                ${items.length === 0 ? `
                    <p class="muted">Nemáš žádné itemy pro tento slot.</p>
                ` : `
                    <div class="equipment-item-list">
                        ${items.map(item => {
                            const isEquipped = item.equipped || item.equipment_id === currentlyEquipped;
                            const rarityClass = `rarity-${item.rarity || 'common'}`;
                            return `
                                <div class="equipment-modal-item ${isEquipped ? 'equipped' : ''} ${rarityClass}" 
                                     data-instance-id="${item.instance_id}">
                                    <div class="equipment-modal-item-icon">
                                        ${item.image ? `<img src="/images/${item.image}" alt="${item.name}" onerror="this.style.display='none'">` : getSlotIcon(slot)}
                                    </div>
                                    <div class="equipment-modal-item-info">
                                        <div class="equipment-modal-item-name">${item.name}</div>
                                        <div class="equipment-modal-item-bonus">${formatItemBonus(item.bonus)}</div>
                                        <div class="equipment-modal-item-rarity rarity-pill ${rarityClass}">${item.rarity || 'common'}</div>
                                    </div>
                                    ${isEquipped ? '<div class="equipment-modal-item-status">Vybaveno</div>' : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                `}
            </div>
            <div class="equipment-modal-footer">
                <button class="btn-secondary" onclick="closeEquipmentModal()">Zavřít</button>
                ${currentlyEquipped ? `<button class="btn-red" onclick="unequipItem('${slot}')">Sundat</button>` : ''}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add click handlers to items
    modal.querySelectorAll('.equipment-modal-item').forEach(itemEl => {
        if (!itemEl.classList.contains('equipped')) {
            itemEl.addEventListener('click', () => {
                const instanceId = itemEl.dataset.instanceId;
                if (instanceId) {
                    equipItem(instanceId, slot);
                }
            });
        }
    });
    
    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeEquipmentModal();
        }
    });
}

function closeEquipmentModal() {
    const modal = document.getElementById('equipmentModal');
    if (modal) {
        modal.remove();
    }
    currentEquipmentModalSlot = null;
}

async function equipItem(instanceId, slot) {
    try {
        const response = await fetch('/api/character/equipment/equip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instance_id: instanceId, slot: slot })
        });
        
        const data = await response.json();
        if (data.success) {
            // Update character stats
            characterStats.combat_stats = data.combat_stats;
            characterStats.equipped_items = data.equipped_items || {};
            
            // Update gameState.equipment to sync
            if (data.equipment) {
                gameState.equipment = data.equipment;
            }
            
            // Update character panel
            updateCharacterEquipmentSlots();
            
            // Reload character panel to get updated equipped items
            await loadCharacterPanel();
            
            closeEquipmentModal();
        } else {
            showCustomAlert(data.error || 'Chyba při vybavování itemu', { type: 'error' });
        }
    } catch (error) {
        console.error('Error equipping item:', error);
        showCustomAlert('Chyba při vybavování itemu', { type: 'error' });
    }
}

async function unequipItem(slot) {
    try {
        const response = await fetch('/api/character/equipment/unequip', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ slot: slot })
        });
        
        const data = await response.json();
        if (data.success) {
            // Update character stats
            characterStats.combat_stats = data.combat_stats;
            characterStats.equipped_items = data.equipped_items || {};
            
            // Update gameState.equipment to sync
            if (data.equipment) {
                gameState.equipment = data.equipment;
            }
            
            // Update character panel
            updateCharacterEquipmentSlots();
            
            // Reload character panel to get updated equipped items
            await loadCharacterPanel();
            
            closeEquipmentModal();
        } else {
            showCustomAlert(data.error || 'Chyba při sundávání itemu', { type: 'error' });
        }
    } catch (error) {
        console.error('Error unequipping item:', error);
        showCustomAlert('Chyba při sundávání itemu', { type: 'error' });
    }
}

function setExchangeMessage(message, isError) {
    const messageEl = document.getElementById('exchangeMessage');
    if (messageEl) {
        messageEl.textContent = message;
        messageEl.className = `exchange-message ${isError ? 'error' : 'success'}`;
        setTimeout(() => {
            messageEl.textContent = '';
            messageEl.className = 'exchange-message';
        }, 5000);
    }
}

// ========== QUEST SYSTEM (TAVERN) ==========

async function loadTavernQuests() {
    try {
        const response = await fetch('/api/quests/available');
        const data = await response.json();
        
        if (data.success) {
            // Update navigation indicator
            const tavernNavItem = document.querySelector('.nav-item[data-tab="tavern"]');
            if (tavernNavItem) {
                const navIcon = tavernNavItem.querySelector('.nav-icon');
                if (data.active_quest && !data.active_quest.completed) {
                    // Show hourglass icon when quest is active
                    if (!navIcon.textContent.includes('⏳')) {
                        navIcon.textContent = '⏳';
                    }
                } else {
                    // Show normal beer icon when no active quest
                    if (navIcon.textContent.includes('⏳')) {
                        navIcon.textContent = '🍺';
                    }
                }
            }
            
            // Display active quest
            const activeQuestEl = document.getElementById('activeQuestDisplay');
            if (activeQuestEl) {
                if (data.active_quest) {
                    const quest = data.active_quest;
                    const minutes = Math.floor(quest.remaining_seconds / 60);
                    const seconds = quest.remaining_seconds % 60;
                    activeQuestEl.innerHTML = `
                        <div class="quest-info">
                            <h4>${quest.name || 'Quest'} [${quest.difficulty_name || 'Easy'}]</h4>
                            <p>Odmena: ${quest.reward_exp} EXP, ${quest.reward_gold} Gold</p>
                            ${quest.reward_item_id ? `<p>Item: ${quest.reward_item_id}</p>` : ''}
                            <p>Zbývá: ${minutes}:${seconds.toString().padStart(2, '0')}</p>
                            <div class="quest-actions">
                                ${quest.completed ? '<button class="btn-green" onclick="completeTavernQuest()">Dokončit</button>' : ''}
                            </div>
                        </div>
                    `;
                } else {
                    activeQuestEl.innerHTML = '<p class="muted">Žádný aktivní quest</p>';
                }
            }
            
            // Display available quests
            const availableQuestsEl = document.getElementById('availableQuestsList');
            if (availableQuestsEl) {
                if (data.available_quests && data.available_quests.length > 0) {
                    availableQuestsEl.innerHTML = data.available_quests.map(quest => {
                        const minutes = Math.floor(quest.duration_seconds / 60);
                        return `
                            <div class="quest-card">
                                <h4>${quest.name || 'Quest'} [${quest.difficulty_name || 'Easy'}]</h4>
                                <p>Trvání: ${minutes} min</p>
                                <p>Odmena: ${quest.reward_exp} EXP, ${quest.reward_gold} Gold</p>
                                ${quest.reward_item_id ? `<p>Item: ${quest.reward_item_id}</p>` : ''}
                                <button class="btn-blue" onclick="startQuest(${quest.id})">Začít</button>
                            </div>
                        `;
                    }).join('');
                } else {
                    availableQuestsEl.innerHTML = '<p class="muted">Žádné dostupné questy</p>';
                }
            }
        }
    } catch (error) {
        console.error('Error loading quests:', error);
    }
}

let questWaitingInterval = null;

async function startQuest(questPoolId) {
    // Prevent multiple clicks
    if (questWaitingInterval) {
        return;
    }
    
    try {
        // First, get quest info to know duration
        const questInfoResponse = await fetch('/api/quests/available');
        const questInfoData = await questInfoResponse.json();
        
        if (!questInfoData.success) {
            showCustomAlert('Chyba při načítání questů', { type: 'error' });
            return;
        }
        
        // Find the quest we're starting
        const questToStart = questInfoData.available_quests?.find(q => q.id == questPoolId);
        if (!questToStart) {
            showCustomAlert('Quest nenalezen', { type: 'warning' });
            return;
        }
        
        // Start the quest
        const response = await fetch('/api/quests/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({quest_pool_id: questPoolId})
        });
        const data = await response.json();
        
        if (data.success) {
            // Show waiting screen
            const modal = document.getElementById('questWaitingModal');
            const nameEl = document.getElementById('questWaitingName');
            const timerEl = document.getElementById('questWaitingTimer');
            
            if (modal && nameEl && timerEl) {
                nameEl.textContent = `${questToStart.name || 'Quest'} [${questToStart.difficulty_name || 'Easy'}]`;
                modal.style.display = 'flex';
                
                // Start countdown
                let remainingSeconds = questToStart.duration_seconds;
                const updateTimer = () => {
                    const minutes = Math.floor(remainingSeconds / 60);
                    const seconds = remainingSeconds % 60;
                    timerEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                    
                    if (remainingSeconds <= 0) {
                        clearInterval(questWaitingInterval);
                        questWaitingInterval = null;
                        modal.style.display = 'none';
                        // Reload quests after a short delay to prevent reset
                        setTimeout(() => {
                            loadTavernQuests();
                        }, 500);
                    } else {
                        remainingSeconds--;
                    }
                };
                
                updateTimer();
                questWaitingInterval = setInterval(updateTimer, 1000);
            }
            
            // Reload quests after a delay to prevent immediate reset
            setTimeout(() => {
                loadTavernQuests();
            }, 1000);
        } else {
            showCustomAlert(data.error || 'Chyba při startu questu', { type: 'error' });
        }
    } catch (error) {
        console.error('Error starting quest:', error);
        showCustomAlert('Chyba při startu questu', { type: 'error' });
        if (questWaitingInterval) {
            clearInterval(questWaitingInterval);
            questWaitingInterval = null;
        }
        const modal = document.getElementById('questWaitingModal');
        if (modal) modal.style.display = 'none';
    }
}

async function completeTavernQuest() {
    try {
        const response = await fetch('/api/quests/complete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await response.json();
        
        if (data.success) {
            // Hide waiting modal if visible
            if (questWaitingInterval) {
                clearInterval(questWaitingInterval);
                questWaitingInterval = null;
            }
            const modal = document.getElementById('questWaitingModal');
            if (modal) modal.style.display = 'none';
            
            // Update gooncoins in gameState
            if (data.rewards && data.rewards.gooncoins) {
                gameState.gooncoins = (gameState.gooncoins || 0) + data.rewards.gooncoins;
                updateResourcesOnly();
            }
            
            let itemMsg = '';
            if (data.rewards.item) {
                itemMsg = ` a ${data.rewards.item.name || data.rewards.item.id}`;
            }
            showCustomAlert(`Quest dokončen!${itemMsg}`, {
                type: 'success',
                rewards: { exp: data.rewards.exp, gooncoins: data.rewards.gooncoins }
            });
            loadTavernQuests();
            loadCharacterPanel();
        } else {
            showCustomAlert(data.error || 'Chyba při dokončení questu', { type: 'error' });
        }
    } catch (error) {
        console.error('Error completing quest:', error);
        showCustomAlert('Chyba při dokončení questu', { type: 'error' });
    }
}

// ========== MOUNT SYSTEM ==========

async function loadMountStatus() {
    try {
        const response = await fetch('/api/mount/status');
        const data = await response.json();
        
        if (data.success) {
            const mountStatusEl = document.getElementById('mountStatus');
            if (mountStatusEl) {
                mountStatusEl.innerHTML = `
                    <p>Aktuální kůň: <strong>${data.available_mounts[data.mount_type].name}</strong></p>
                    <p>Rychlostní bonus: <strong>-${data.speed_reduction}%</strong></p>
                `;
            }
            
            const mountsListEl = document.getElementById('mountsList');
            if (mountsListEl) {
                mountsListEl.innerHTML = Object.entries(data.available_mounts)
                    .filter(([key]) => key !== 'none')
                    .map(([key, mount]) => `
                        <div class="mount-item">
                            <h4>${mount.name}</h4>
                            <p>Rychlostní bonus: -${mount.speed_reduction}%</p>
                            <p>Cena: ${mount.cost} Gold</p>
                            <button class="btn-blue" onclick="buyMount('${key}')">Koupit</button>
                        </div>
                    `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading mount status:', error);
    }
}

async function buyMount(mountType) {
    try {
        const response = await fetch('/api/mount/buy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mount_type: mountType})
        });
        const data = await response.json();
        
        if (data.success) {
            showCustomAlert('Kůň zakoupen!', { type: 'success' });
            loadMountStatus();
        } else {
            showCustomAlert(data.error || 'Chyba při nákupu koně', { type: 'error' });
        }
    } catch (error) {
        console.error('Error buying mount:', error);
        showCustomAlert('Chyba při nákupu koně', { type: 'error' });
    }
}

// ========== TAVERN ACTIVITIES ==========

async function buyTavernBeer(statType) {
    try {
        const response = await fetch('/api/tavern/beer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({stat_type: statType})
        });
        const data = await response.json();
        
        if (data.success) {
            showCustomAlert(`Pivo zakoupeno! Získal jsi bonus +10% ${statType === 'strength' ? 'síly' : 'štěstí'} na 30 minut.`, { type: 'success' });
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při nákupu piva', { type: 'error' });
        }
    } catch (error) {
        console.error('Error buying beer:', error);
        showCustomAlert('Chyba při nákupu piva', { type: 'error' });
    }
}

async function playTavernCards() {
    const betAmount = prompt('Kolik chceš vsadit? (100-1000 Gooncoinů)', '100');
    if (!betAmount) return;
    
    const bet = parseInt(betAmount);
    if (isNaN(bet) || bet < 100 || bet > 1000) {
        showCustomAlert('Neplatná sázka! Musí být mezi 100 a 1000 Gooncoinů.', { type: 'warning' });
        return;
    }
    
    try {
        const response = await fetch('/api/tavern/cards', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bet_amount: bet})
        });
        const data = await response.json();
        
        if (data.success) {
            if (data.won) {
                showCustomAlert(`Vyhrál jsi! Získal jsi ${data.winnings} Gooncoinů!`, { type: 'success' });
            } else {
                showCustomAlert(`Prohrál jsi ${bet} Gooncoinů. Zkus to znovu!`, { type: 'warning' });
            }
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při hraní karet', { type: 'error' });
        }
    } catch (error) {
        console.error('Error playing cards:', error);
        showCustomAlert('Chyba při hraní karet', { type: 'error' });
    }
}

async function playTavernDarts() {
    try {
        const response = await fetch('/api/tavern/darts', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await response.json();
        
        if (data.success) {
            showCustomAlert(`Hrál jsi šipky! Získal jsi ${data.exp_reward} EXP!`, { type: 'success' });
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při hraní šipek', { type: 'error' });
        }
    } catch (error) {
        console.error('Error playing darts:', error);
        showCustomAlert('Chyba při hraní šipek', { type: 'error' });
    }
}

// ========== INTERACTIVE GAMBLE GAMES ==========

// Blackjack Game State
let blackjackGameState = null;

function openTavernBlackjack() {
    const modal = document.getElementById('tavernBlackjackModal');
    if (modal) {
        modal.style.display = 'flex';
        resetBlackjack();
    }
}

function closeQuestWaiting() {
    // Clear the quest waiting interval if it exists
    if (questWaitingInterval) {
        clearInterval(questWaitingInterval);
        questWaitingInterval = null;
    }
    // Hide the modal
    const modal = document.getElementById('questWaitingModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function closeTavernBlackjack() {
    const modal = document.getElementById('tavernBlackjackModal');
    if (modal) {
        modal.style.display = 'none';
        resetBlackjack();
    }
}

function resetBlackjack() {
    blackjackGameState = null;
    document.getElementById('blackjackSetup').style.display = 'block';
    document.getElementById('blackjackGame').style.display = 'none';
    document.getElementById('blackjackResult').innerHTML = '';
}

async function startBlackjack() {
    const bet = parseInt(document.getElementById('blackjackBet').value);
    if (isNaN(bet) || bet < 100 || bet > 1000) {
        showCustomAlert('Neplatná sázka! Musí být mezi 100 a 1000 Gooncoinů.', { type: 'warning' });
        return;
    }
    
    try {
        const response = await fetch('/api/tavern/blackjack/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bet_amount: bet})
        });
        const data = await response.json();
        
        if (data.success) {
            blackjackGameState = data;
            document.getElementById('blackjackSetup').style.display = 'none';
            document.getElementById('blackjackGame').style.display = 'block';
            updateBlackjackDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při startu hry', { type: 'error' });
        }
    } catch (error) {
        console.error('Error starting blackjack:', error);
        showCustomAlert('Chyba při startu hry', { type: 'error' });
    }
}

function updateBlackjackDisplay() {
    if (!blackjackGameState) return;
    
    // Player cards
    const playerCardsEl = document.getElementById('playerCards');
    playerCardsEl.innerHTML = blackjackGameState.player_cards.map(card => 
        `<div class="blackjack-card">${getCardDisplay(card)}</div>`
    ).join('');
    
    document.getElementById('playerTotal').textContent = `Součet: ${blackjackGameState.player_total}`;
    
    // Dealer cards
    const dealerCardsEl = document.getElementById('dealerCards');
    dealerCardsEl.innerHTML = blackjackGameState.dealer_cards.map((card, idx) => 
        `<div class="blackjack-card ${idx === 1 && !blackjackGameState.game_over ? 'hidden' : ''}">${getCardDisplay(card)}</div>`
    ).join('');
    
    if (blackjackGameState.game_over) {
        document.getElementById('dealerTotal').textContent = `Součet: ${blackjackGameState.dealer_total}`;
        document.getElementById('blackjackActions').style.display = 'none';
        
        const resultEl = document.getElementById('blackjackResult');
        if (blackjackGameState.won) {
            resultEl.className = 'blackjack-result win';
            resultEl.textContent = `Vyhrál jsi! Získal jsi ${blackjackGameState.winnings} Gooncoinů!`;
        } else {
            resultEl.className = 'blackjack-result lose';
            resultEl.textContent = `Prohrál jsi ${blackjackGameState.bet_amount} Gooncoinů.`;
        }
    } else {
        document.getElementById('dealerTotal').textContent = 'Součet: ?';
        document.getElementById('blackjackActions').style.display = 'flex';
    }
}

function getCardDisplay(value) {
    if (value === 1) return 'A';
    if (value === 11) return 'J';
    if (value === 12) return 'Q';
    if (value === 13) return 'K';
    return value;
}

async function blackjackHit() {
    if (!blackjackGameState || blackjackGameState.game_over) return;
    
    try {
        const response = await fetch('/api/tavern/blackjack/hit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: blackjackGameState.game_id})
        });
        const data = await response.json();
        
        if (data.success) {
            blackjackGameState = data;
            updateBlackjackDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při hraní', { type: 'error' });
        }
    } catch (error) {
        console.error('Error hitting:', error);
        showCustomAlert('Chyba při hraní', { type: 'error' });
    }
}

async function blackjackStand() {
    if (!blackjackGameState || blackjackGameState.game_over) return;
    
    try {
        const response = await fetch('/api/tavern/blackjack/stand', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({game_id: blackjackGameState.game_id})
        });
        const data = await response.json();
        
        if (data.success) {
            blackjackGameState = data;
            updateBlackjackDisplay();
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při hraní', { type: 'error' });
        }
    } catch (error) {
        console.error('Error standing:', error);
        showCustomAlert('Chyba při hraní', { type: 'error' });
    }
}

// Dice Game
function openTavernDice() {
    const modal = document.getElementById('tavernDiceModal');
    if (modal) {
        modal.style.display = 'flex';
        resetDice();
    }
}

function closeTavernDice() {
    const modal = document.getElementById('tavernDiceModal');
    if (modal) {
        modal.style.display = 'none';
        resetDice();
    }
}

function resetDice() {
    document.getElementById('diceSetup').style.display = 'block';
    document.getElementById('diceResult').style.display = 'none';
}

async function rollDice() {
    const bet = parseInt(document.getElementById('diceBet').value);
    const guess = parseInt(document.getElementById('diceGuess').value);
    
    if (isNaN(bet) || bet < 50 || bet > 500) {
        showCustomAlert('Neplatná sázka! Musí být mezi 50 a 500 Gooncoinů.', { type: 'warning' });
        return;
    }
    
    if (isNaN(guess) || guess < 2 || guess > 12) {
        showCustomAlert('Neplatný tip! Musí být mezi 2 a 12.', { type: 'warning' });
        return;
    }
    
    try {
        const response = await fetch('/api/tavern/dice', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bet_amount: bet, guess: guess})
        });
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('diceSetup').style.display = 'none';
            document.getElementById('diceResult').style.display = 'block';
            
            const diceDisplay = document.getElementById('diceDisplay');
            diceDisplay.innerHTML = `
                <div class="dice">${data.dice1}</div>
                <div class="dice">${data.dice2}</div>
            `;
            
            const outcome = document.getElementById('diceOutcome');
            if (data.won) {
                outcome.className = 'dice-outcome win';
                outcome.textContent = `Vyhrál jsi! Součet: ${data.sum}, Získal jsi ${data.winnings} Gooncoinů!`;
            } else {
                outcome.className = 'dice-outcome lose';
                outcome.textContent = `Prohrál jsi. Součet: ${data.sum}, Tvá sázka: ${guess}`;
            }
            
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při hraní kostek', { type: 'error' });
        }
    } catch (error) {
        console.error('Error rolling dice:', error);
        showCustomAlert('Chyba při hraní kostek', { type: 'error' });
    }
}

// Shells Game
let shellsGameState = null;
let shellsAnimationTimeout = null;

function openTavernShells() {
    const modal = document.getElementById('tavernShellsModal');
    if (modal) {
        modal.style.display = 'flex';
        resetShells();
    }
}

function closeTavernShells() {
    const modal = document.getElementById('tavernShellsModal');
    if (modal) {
        modal.style.display = 'none';
        resetShells();
    }
}

function resetShells() {
    shellsGameState = null;
    if (shellsAnimationTimeout) {
        clearTimeout(shellsAnimationTimeout);
        shellsAnimationTimeout = null;
    }
    document.getElementById('shellsSetup').style.display = 'block';
    document.getElementById('shellsGame').style.display = 'none';
    document.getElementById('shellsResult').innerHTML = '';
    document.getElementById('shellsResetBtn').style.display = 'none';
    
    // Reset shells
    const shells = document.querySelectorAll('.shell');
    shells.forEach(shell => {
        shell.classList.remove('selected', 'revealed');
        const ball = shell.querySelector('.ball');
        if (ball) ball.classList.remove('show');
        shell.innerHTML = '<div class="shell-top">🥚</div>';
    });
}

async function startShellsGame() {
    const bet = parseInt(document.getElementById('shellsBet').value);
    if (isNaN(bet) || bet < 100 || bet > 500) {
        showCustomAlert('Neplatná sázka! Musí být mezi 100 a 500 Gooncoinů.', { type: 'warning' });
        return;
    }
    
    try {
        const response = await fetch('/api/tavern/shells/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bet_amount: bet})
        });
        const data = await response.json();
        
        if (data.success) {
            shellsGameState = data;
            document.getElementById('shellsSetup').style.display = 'none';
            document.getElementById('shellsGame').style.display = 'block';
            
            // Show ball under correct shell
            const shells = document.querySelectorAll('.shell');
            shells[data.ball_position].innerHTML = `
                <div class="shell-top">🥚</div>
                <div class="ball show"></div>
            `;
            
            // Animate shuffling
            setTimeout(() => animateShellsShuffle(), 1000);
        } else {
            showCustomAlert(data.error || 'Chyba při startu hry', { type: 'error' });
        }
    } catch (error) {
        console.error('Error starting shells:', error);
        showCustomAlert('Chyba při startu hry', { type: 'error' });
    }
}

function animateShellsShuffle() {
    const shells = document.querySelectorAll('.shell');
    let shuffleCount = 0;
    const maxShuffles = 8;
    
    function shuffle() {
        shells.forEach(shell => {
            const randomX = (Math.random() - 0.5) * 100;
            const randomY = (Math.random() - 0.5) * 50;
            shell.style.transform = `translate(${randomX}px, ${randomY}px)`;
        });
        
        shuffleCount++;
        if (shuffleCount < maxShuffles) {
            shellsAnimationTimeout = setTimeout(shuffle, 200);
        } else {
            // Reset positions
            shells.forEach(shell => {
                shell.style.transform = '';
            });
            // Hide ball
            shells.forEach(shell => {
                const ball = shell.querySelector('.ball');
                if (ball) ball.classList.remove('show');
            });
        }
    }
    
    shuffle();
}

async function selectShell(shellIndex) {
    if (!shellsGameState || shellsGameState.selected) return;
    
    shellsGameState.selected = true;
    
    // Mark selected shell
    const shells = document.querySelectorAll('.shell');
    shells[shellIndex].classList.add('selected');
    
    // Reveal all shells
    setTimeout(() => {
        shells.forEach((shell, idx) => {
            shell.classList.add('revealed');
            if (idx === shellsGameState.ball_position) {
                const ball = shell.querySelector('.ball');
                if (ball) ball.classList.add('show');
            }
        });
        
        // Check result
        checkShellsResult(shellIndex);
    }, 500);
}

async function checkShellsResult(selectedIndex) {
    try {
        const response = await fetch('/api/tavern/shells/check', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                game_id: shellsGameState.game_id,
                selected_shell: selectedIndex
            })
        });
        const data = await response.json();
        
        if (data.success) {
            const resultEl = document.getElementById('shellsResult');
            if (data.won) {
                resultEl.className = 'shells-result win';
                resultEl.textContent = `Vyhrál jsi! Získal jsi ${data.winnings} Gooncoinů!`;
            } else {
                resultEl.className = 'shells-result lose';
                resultEl.textContent = `Prohrál jsi. Kulička byla pod skořápkou ${data.ball_position + 1}.`;
            }
            
            document.getElementById('shellsResetBtn').style.display = 'block';
            updateDisplay();
        } else {
            showCustomAlert(data.error || 'Chyba při kontrole výsledku', { type: 'error' });
        }
    } catch (error) {
        console.error('Error checking shells:', error);
        showCustomAlert('Chyba při kontrole výsledku', { type: 'error' });
    }
}

// ========== BLACKSMITH SYSTEM ==========

let blacksmithItems = [];
let blacksmithFilteredItems = [];
let blacksmithDisassembleFilteredItems = [];

async function loadBlacksmithMaterials() {
    try {
        const response = await fetch('/api/blacksmith/materials');
        const data = await response.json();
        
        if (data.success) {
            const metalEl = document.getElementById('metalAmount');
            const soulsEl = document.getElementById('soulsAmount');
            if (metalEl) metalEl.textContent = data.metal;
            if (soulsEl) soulsEl.textContent = data.souls;
        }
    } catch (error) {
        console.error('Error loading blacksmith materials:', error);
    }
}

async function loadBlacksmithItems() {
    try {
        const response = await fetch('/api/blacksmith/items');
        const data = await response.json();
        
        if (data.success) {
            blacksmithItems = data.items || [];
            filterBlacksmithItems();
            filterBlacksmithDisassembleItems();
        } else {
            console.error('API error:', data.error);
            const listEl = document.getElementById('blacksmithItemsList');
            if (listEl) {
                listEl.innerHTML = `<p class="muted" style="text-align: center; padding: 20px;">Chyba při načítání itemů: ${data.error || 'Neznámá chyba'}</p>`;
            }
        }
    } catch (error) {
        console.error('Error loading blacksmith items:', error);
        const listEl = document.getElementById('blacksmithItemsList');
        if (listEl) {
            listEl.innerHTML = '<p class="muted" style="text-align: center; padding: 20px;">Chyba při načítání itemů</p>';
        }
    }
}

function filterBlacksmithItems() {
    const searchTerm = (document.getElementById('blacksmithSearch')?.value || '').toLowerCase();
    const rarityFilter = document.getElementById('blacksmithFilter')?.value || '';
    
    blacksmithFilteredItems = blacksmithItems.filter(item => {
        const matchesSearch = !searchTerm || item.name.toLowerCase().includes(searchTerm) || 
                               item.equipment_id.toLowerCase().includes(searchTerm);
        const matchesRarity = !rarityFilter || item.rarity === rarityFilter;
        return matchesSearch && matchesRarity;
    });
    
    renderBlacksmithItems();
}

function renderBlacksmithItems() {
    const listEl = document.getElementById('blacksmithItemsList');
    if (!listEl) return;
    
    if (blacksmithFilteredItems.length === 0) {
        listEl.innerHTML = '<p class="muted" style="text-align: center; padding: 20px;">Žádné itemy nenalezeny</p>';
        return;
    }
    
    const rarityColors = {
        'common': '#9e9e9e',
        'uncommon': '#4caf50',
        'rare': '#2196f3',
        'epic': '#9c27b0',
        'legendary': '#ff9800'
    };
    
    listEl.innerHTML = blacksmithFilteredItems.map(item => {
        const rarityColor = rarityColors[item.rarity] || '#9e9e9e';
        const canUpgrade = item.upgrade_level < item.max_level;
        const nextLevel = item.upgrade_level + 1;
        const cost = BLACKSMITH_UPGRADE_COSTS[nextLevel] || {metal: 0, souls: 0};
        
        // Calculate stat bonuses with upgrade level
        const bonus = item.bonus || {};
        const upgradeBonus = item.upgrade_level; // Each upgrade level adds +1 to all stats
        
        // Build stats display
        const stats = [];
        if (bonus.strength) {
            const base = bonus.strength || 0;
            const total = base + upgradeBonus;
            stats.push(`Síla: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.dexterity) {
            const base = bonus.dexterity || 0;
            const total = base + upgradeBonus;
            stats.push(`Obratnost: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.intelligence) {
            const base = bonus.intelligence || 0;
            const total = base + upgradeBonus;
            stats.push(`Inteligence: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.constitution) {
            const base = bonus.constitution || 0;
            const total = base + upgradeBonus;
            stats.push(`Konstituce: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.luck_stat) {
            const base = bonus.luck_stat || 0;
            const total = base + upgradeBonus;
            stats.push(`Štěstí: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.click_power) {
            const base = bonus.click_power || 0;
            const total = base + upgradeBonus;
            stats.push(`Útok: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.defense) {
            const base = bonus.defense || 0;
            const total = base + upgradeBonus;
            stats.push(`Obrana: ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        if (bonus.luck) {
            const base = bonus.luck || 0;
            const total = base + upgradeBonus;
            stats.push(`Štěstí (combat): ${base}${upgradeBonus > 0 ? ` (+${upgradeBonus})` : ''} = ${total}`);
        }
        
        const statsHtml = stats.length > 0 ? `
            <div class="blacksmith-item-stats">
                ${stats.map(stat => `<span class="blacksmith-item-stat">${stat}</span>`).join('')}
            </div>
        ` : '';
        
        return `
            <div class="blacksmith-item-card ${!canUpgrade ? 'disabled' : ''}">
                <div class="blacksmith-item-checkbox-wrapper">
                    <input type="checkbox" class="blacksmith-item-checkbox" 
                           data-instance-id="${item.instance_id}" 
                           ${!canUpgrade ? 'disabled' : ''}>
                </div>
                <div class="blacksmith-item-content">
                    <div class="blacksmith-item-header">
                        <h4 class="blacksmith-item-name" style="color: ${rarityColor};">${item.name}</h4>
                        <span class="blacksmith-item-rarity ${item.rarity}">${item.rarity}</span>
                    </div>
                    <div class="blacksmith-item-level">
                        <span class="blacksmith-item-level-badge">
                            ⭐ Level: ${item.upgrade_level}/${item.max_level}
                        </span>
                        ${canUpgrade ? `
                            <span class="blacksmith-item-cost">
                                🔨 ${cost.metal} kovu, ${cost.souls} duší
                            </span>
                            <span style="color: var(--text-light); font-size: 11px;">
                                (+1 ke všem statům)
                            </span>
                        ` : `
                            <span class="blacksmith-item-cost max">MAX LEVEL</span>
                        `}
                    </div>
                    ${statsHtml}
                </div>
            </div>
        `;
    }).join('');
}

async function blacksmithUpgrade() {
    const checkboxes = document.querySelectorAll('.blacksmith-item-checkbox:checked');
    const selectedIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.instanceId));
    
    if (selectedIds.length === 0) {
        showCustomAlert('Vyber alespoň jeden item k upgradování', { type: 'warning' });
        return;
    }
    
    try {
        const response = await fetch('/api/blacksmith/upgrade', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                item_ids: selectedIds
            })
        });
        const data = await response.json();
        
        if (data.success) {
            const count = data.upgraded.length;
            showCustomAlert(`Úspěšně upgradováno ${count} item(ů)!`, { type: 'success' });
            loadBlacksmithMaterials();
            loadBlacksmithItems();
        } else {
            showCustomAlert(data.error || 'Chyba při upgradu', { type: 'error' });
        }
    } catch (error) {
        console.error('Error upgrading items:', error);
        showCustomAlert('Chyba při upgradu', { type: 'error' });
    }
}

// Blacksmith upgrade costs (should match backend)
const BLACKSMITH_UPGRADE_COSTS = {
    1: {metal: 500, souls: 50},
    2: {metal: 1250, souls: 125},
    3: {metal: 2500, souls: 250},
    4: {metal: 5000, souls: 500},
    5: {metal: 10000, souls: 1000}
};

function filterBlacksmithDisassembleItems() {
    const searchTerm = (document.getElementById('blacksmithDisassembleSearch')?.value || '').toLowerCase();
    const rarityFilter = document.getElementById('blacksmithDisassembleFilter')?.value || '';
    
    blacksmithDisassembleFilteredItems = blacksmithItems.filter(item => {
        const matchesSearch = !searchTerm || item.name.toLowerCase().includes(searchTerm) || 
                               item.equipment_id.toLowerCase().includes(searchTerm);
        const matchesRarity = !rarityFilter || item.rarity === rarityFilter;
        return matchesSearch && matchesRarity;
    });
    
    renderBlacksmithDisassembleItems();
}

function renderBlacksmithDisassembleItems() {
    const listEl = document.getElementById('blacksmithDisassembleItemsList');
    if (!listEl) return;
    
    if (blacksmithDisassembleFilteredItems.length === 0) {
        listEl.innerHTML = '<p class="muted" style="text-align: center; padding: 20px;">Žádné itemy nenalezeny</p>';
        return;
    }
    
    const rarityColors = {
        'common': '#9e9e9e',
        'uncommon': '#4caf50',
        'rare': '#2196f3',
        'epic': '#9c27b0',
        'legendary': '#ff9800'
    };
    
    listEl.innerHTML = blacksmithDisassembleFilteredItems.map(item => {
        const rarityColor = rarityColors[item.rarity] || '#9e9e9e';
        const level = item.upgrade_level || 0;
        
        // Calculate return values (50% of base) - match backend RARITY_VALUE_MULTIPLIERS
        const rarityMult = {'common': 1.0, 'rare': 1.25, 'epic': 1.65, 'legendary': 2.4, 'unique': 3.2}[item.rarity] || 1.0;
        const baseMetal = Math.floor(10 * rarityMult * (1 + level * 0.5));
        const baseSouls = Math.floor(1 * rarityMult * (1 + level * 0.3));
        const metalReturn = Math.floor(baseMetal * 0.5);
        const soulsReturn = Math.floor(baseSouls * 0.5);
        
        return `
            <div style="display: flex; align-items: center; gap: 10px; padding: 8px; border: 1px solid #444; border-radius: 6px; background: #2a2a2a;">
                <input type="checkbox" class="blacksmith-disassemble-item-checkbox" 
                       data-instance-id="${item.instance_id}" 
                       style="cursor: pointer;">
                <div style="flex: 1; min-width: 0;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <strong style="color: ${rarityColor};">${item.name}</strong>
                        <span style="font-size: 12px; color: #888;">(${item.rarity})</span>
                    </div>
                    <div style="font-size: 12px; color: #aaa;">
                        Level: ${level} | Vrátí: ${metalReturn} kovu, ${soulsReturn} duší
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function blacksmithDisassemble() {
    const checkboxes = document.querySelectorAll('.blacksmith-disassemble-item-checkbox:checked');
    const selectedIds = Array.from(checkboxes).map(cb => parseInt(cb.dataset.instanceId));
    
    if (selectedIds.length === 0) {
        showCustomAlert('Vyber alespoň jeden item k rozbití', { type: 'warning' });
        return;
    }
    
    if (!confirm(`Opravdu chceš rozbít ${selectedIds.length} item(ů)?`)) return;
    
    try {
        const response = await fetch('/api/blacksmith/disassemble', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item_ids: selectedIds})
        });
        const data = await response.json();
        
        if (data.success) {
            const count = data.disassembled ? data.disassembled.length : selectedIds.length;
            showCustomAlert(`Úspěšně rozbito ${count} item(ů)!`, {
                type: 'success',
                rewards: { metal_gained: data.total_metal_gained, souls_gained: data.total_souls_gained }
            });
            loadBlacksmithMaterials();
            loadBlacksmithItems();
        } else {
            alert(data.error || 'Chyba při rozbíjení');
        }
    } catch (error) {
        console.error('Error disassembling items:', error);
        showCustomAlert('Chyba při rozbíjení', { type: 'error' });
    }
}

// ========== DUNGEON SYSTEM ==========

let allDungeons = [];
let selectedDungeon = null;
let selectedFloor = 1;

async function loadDungeons() {
    try {
        const response = await fetch('/api/dungeons/list');
        const data = await response.json();
        
        if (data.success) {
            allDungeons = data.dungeons;
            const dungeonsListEl = document.getElementById('dungeonsList');
            if (dungeonsListEl) {
                if (data.dungeons.length === 0) {
                    dungeonsListEl.innerHTML = '<p class="muted">Žádné dungeony k dispozici</p>';
                    return;
                }
                
                dungeonsListEl.innerHTML = data.dungeons.map(dungeon => {
                    const completedCount = (dungeon.completed_floors || []).length;
                    const progress = dungeon.max_floor > 0 ? (completedCount / dungeon.max_floor * 100).toFixed(0) : 0;
                    
                    return `
                        <div class="dungeon-card ${dungeon.unlocked ? '' : 'locked'}" onclick="${dungeon.unlocked ? `selectDungeon('${dungeon.id}')` : ''}">
                            <h3>${dungeon.name}</h3>
                            <p class="dungeon-level">Level: ${dungeon.base_level}+</p>
                            <p class="dungeon-progress">Patro: ${dungeon.current_floor}/${dungeon.max_floor}</p>
                            <div class="dungeon-progress-bar">
                                <div class="dungeon-progress-fill" style="width: ${progress}%"></div>
                            </div>
                            ${dungeon.unlocked ? 
                                `<button class="btn-green" onclick="event.stopPropagation(); selectDungeon('${dungeon.id}')">Vstoupit</button>` :
                                '<p class="muted">Zamčeno - potřebuješ level ' + dungeon.base_level + '</p>'
                            }
                        </div>
                    `;
                }).join('');
            }
        } else {
            const dungeonsListEl = document.getElementById('dungeonsList');
            if (dungeonsListEl) {
                dungeonsListEl.innerHTML = '<p class="muted">Chyba při načítání dungeonů</p>';
            }
        }
    } catch (error) {
        console.error('Error loading dungeons:', error);
        const dungeonsListEl = document.getElementById('dungeonsList');
        if (dungeonsListEl) {
            dungeonsListEl.innerHTML = '<p class="muted">Chyba při načítání dungeonů</p>';
        }
    }
}

function selectDungeon(dungeonId) {
    selectedDungeon = dungeonId;
    const dungeon = allDungeons.find(d => d.id === dungeonId);
    if (!dungeon) {
        console.error('Dungeon not found:', dungeonId);
        return;
    }
    
    // Set floor to current floor or 1
    selectedFloor = dungeon.current_floor || 1;
    
    // Show dungeon detail
    const detailEl = document.getElementById('dungeonDetail');
    const detailNameEl = document.getElementById('dungeonDetailName');
    const detailContentEl = document.getElementById('dungeonDetailContent');
    
    if (detailEl && detailNameEl && detailContentEl) {
        detailEl.style.display = 'block';
        detailNameEl.textContent = dungeon.name;
        
        // Build detail content
        let content = `
            <div class="dungeon-info">
                <p><strong>Level požadavek:</strong> ${dungeon.base_level}</p>
                <p><strong>Aktuální patro:</strong> ${dungeon.current_floor}/${dungeon.max_floor}</p>
            </div>
            
            <div class="dungeon-floors">
                <h4>Výběr patra:</h4>
                <div class="floors-grid">
        `;
        
        // Floor buttons
        for (let floor = 1; floor <= dungeon.max_floor; floor++) {
            const isCompleted = (dungeon.completed_floors || []).includes(floor);
            const isCurrent = floor === dungeon.current_floor;
            const isLocked = floor > dungeon.current_floor;
            
            // Determine enemy type for this floor
            let enemyInfo = '';
            if (dungeon.main_boss && dungeon.main_boss.floor === floor) {
                enemyInfo = `<span class="enemy-badge boss">BOSS</span>`;
            } else if (dungeon.minibosses) {
                const miniboss = dungeon.minibosses.find(mb => mb.floor === floor);
                if (miniboss) {
                    enemyInfo = `<span class="enemy-badge miniboss">MINIBOSS</span>`;
                } else {
                    enemyInfo = `<span class="enemy-badge common">Nepřítel</span>`;
                }
            } else {
                enemyInfo = `<span class="enemy-badge common">Nepřítel</span>`;
            }
            
            content += `
                <button class="floor-btn ${isCurrent ? 'active' : ''} ${isLocked ? 'locked' : ''}" 
                        onclick="selectFloor(${floor})" 
                        ${isLocked ? 'disabled' : ''}>
                    Patro ${floor} ${enemyInfo}
                    ${isCompleted ? '✓' : ''}
                </button>
            `;
        }
        
        content += `
                </div>
            </div>
            
            <div class="dungeon-enemies">
        `;
        
        // Main boss info
        if (dungeon.main_boss) {
            content += `
                <div class="enemy-card boss-card">
                    <h4>👑 ${dungeon.main_boss.name}</h4>
                    <p><strong>Patro:</strong> ${dungeon.main_boss.floor}</p>
                    <p><strong>Level:</strong> ${dungeon.main_boss.level}</p>
                    <p><strong>HP:</strong> ${dungeon.main_boss.hp.toLocaleString()}</p>
                    <p><strong>Útok:</strong> ${dungeon.main_boss.attack}</p>
                    <p><strong>Obrana:</strong> ${dungeon.main_boss.defense}</p>
                    ${dungeon.main_boss.ultimate_attack ? `<p class="ultimate-attack">💥 ${dungeon.main_boss.ultimate_attack}</p>` : ''}
                </div>
            `;
        }
        
        // Minibosses
        if (dungeon.minibosses && dungeon.minibosses.length > 0) {
            content += `<h4>Minibossové:</h4><div class="minibosses-grid">`;
            dungeon.minibosses.forEach(miniboss => {
                content += `
                    <div class="enemy-card miniboss-card">
                        <h5>${miniboss.name}</h5>
                        <p>Patro ${miniboss.floor} | Level ${miniboss.level}</p>
                        <p>HP: ${miniboss.hp.toLocaleString()}</p>
                    </div>
                `;
            });
            content += `</div>`;
        }
        
        // Common enemies preview
        if (dungeon.common_enemies && dungeon.common_enemies.length > 0) {
            content += `<h4>Běžní nepřátelé:</h4><div class="common-enemies-list">`;
            dungeon.common_enemies.slice(0, 3).forEach(enemy => {
                content += `<span class="enemy-tag">${enemy.name}</span>`;
            });
            if (dungeon.common_enemies.length > 3) {
                content += `<span class="enemy-tag">+${dungeon.common_enemies.length - 3} dalších</span>`;
            }
            content += `</div>`;
        }
        
        content += `</div>`;
        
        detailContentEl.innerHTML = content;
        
        // Update fight button
        const fightBtn = document.getElementById('dungeonFightBtn');
        if (fightBtn) {
            fightBtn.textContent = `Bojovat na patře ${selectedFloor}`;
            fightBtn.disabled = false;
        }
    }
}

function selectFloor(floor) {
    if (!selectedDungeon) return;
    
    const dungeon = allDungeons.find(d => d.id === selectedDungeon);
    if (!dungeon) return;
    
    if (floor > dungeon.current_floor) {
        showCustomAlert('Toto patro ještě není odemčeno!', { type: 'warning' });
        return;
    }
    
    selectedFloor = floor;
    
    // Update active floor button
    document.querySelectorAll('.floor-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.closest('.floor-btn')?.classList.add('active');
    
    // Update fight button
    const fightBtn = document.getElementById('dungeonFightBtn');
    if (fightBtn) {
        fightBtn.textContent = `Bojovat na patře ${floor}`;
    }
}

let dungeonCombatAnimationTimers = [];

function clearDungeonCombatAnimation() {
    dungeonCombatAnimationTimers.forEach(timer => clearTimeout(timer));
    dungeonCombatAnimationTimers = [];
    document.querySelectorAll('#dungeonCombatVisual .damage-pop').forEach(pop => pop.remove());
}

function playDungeonCombatAnimation(battle, context = {}) {
    const visual = document.getElementById('dungeonCombatVisual');
    const playerHpFill = document.getElementById('dungeonPlayerHp');
    const enemyHpFill = document.getElementById('dungeonEnemyHp');
    const playerHpText = document.getElementById('dungeonPlayerHpText');
    const enemyHpText = document.getElementById('dungeonEnemyHpText');
    const playerNameEl = document.getElementById('dungeonPlayerName');
    const enemyNameEl = document.getElementById('dungeonEnemyName');
    const logEl = document.getElementById('dungeonCombatVisualLog');
    
    if (!visual || !battle || !playerHpFill || !enemyHpFill) return;
    
    clearDungeonCombatAnimation();
    
    const playerStats = context.playerStats || {};
    const enemyStats = context.enemyStats || {};
    const playerTotalHp = Math.max(1, playerStats.hp || battle.attacker_hp || 1);
    const enemyTotalHp = Math.max(1, enemyStats.hp || battle.defender_hp || 1);
    let playerHp = playerTotalHp;
    let enemyHp = enemyTotalHp;
    
    if (playerNameEl) playerNameEl.textContent = context.playerLabel || 'Ty';
    if (enemyNameEl) enemyNameEl.textContent = context.enemyLabel || 'Protivník';
    if (logEl) logEl.textContent = '⚔️ Boj začíná...';
    
    updateDungeonHpFill(playerHpFill, playerHpText, 100, playerTotalHp, playerHp);
    updateDungeonHpFill(enemyHpFill, enemyHpText, 100, enemyTotalHp, enemyHp);
    
    const rounds = battle.log || [];
    const stepDuration = 800;
    
    rounds.forEach((entry, index) => {
        const timer = setTimeout(() => {
            const attackerSide = entry.actor === 'attacker' ? 'player' : 'enemy';
            const targetSide = entry.actor === 'attacker' ? 'enemy' : 'player';
            const damage = entry.damage || 0;
            const dodged = Boolean(entry.dodged);
            
            if (entry.actor === 'attacker' && !dodged) {
                enemyHp = Math.max(0, enemyHp - damage);
                updateDungeonHpFill(enemyHpFill, enemyHpText, (enemyHp / enemyTotalHp) * 100, enemyTotalHp, enemyHp);
            } else if (entry.actor === 'defender' && !dodged) {
                playerHp = Math.max(0, playerHp - damage);
                updateDungeonHpFill(playerHpFill, playerHpText, (playerHp / playerTotalHp) * 100, playerTotalHp, playerHp);
            }
            
            animateDungeonFighter(attackerSide, targetSide, damage, dodged, entry.crit);
            if (logEl) {
                if (dodged) {
                    logEl.textContent = entry.actor === 'attacker'
                        ? `⚡ ${context.playerLabel || 'Ty'} míjí útok!`
                        : `⚡ ${context.enemyLabel || 'Protivník'} míjí útok!`;
                } else {
                    const critText = entry.crit ? ' 💥 KRITICKÝ ÚDER!' : '';
                    logEl.textContent = entry.actor === 'attacker'
                        ? `⚔️ Útočíš za ${damage.toFixed(1)} damage${critText}`
                        : `⚔️ ${context.enemyLabel || 'Protivník'} zasazuje ${damage.toFixed(1)} damage${critText}`;
                }
            }
        }, stepDuration * index);
        dungeonCombatAnimationTimers.push(timer);
    });
    
    const endTimer = setTimeout(() => {
        if (logEl) {
            if (battle.winner === 'attacker') {
                logEl.textContent = '🎉 VÝHRA! 🎉';
            } else if (battle.winner === 'defender') {
                logEl.textContent = '💀 Porážka...';
            } else {
                logEl.textContent = '🤝 Remíza.';
            }
        }
        // Final HP update
        updateDungeonHpFill(playerHpFill, playerHpText, (playerHp / playerTotalHp) * 100, playerTotalHp, playerHp);
        updateDungeonHpFill(enemyHpFill, enemyHpText, (enemyHp / enemyTotalHp) * 100, enemyTotalHp, enemyHp);
    }, stepDuration * (rounds.length + 1));
    dungeonCombatAnimationTimers.push(endTimer);
}

function updateDungeonHpFill(element, textElement, percent, totalHp, currentHp = null) {
    const clamped = Math.max(0, Math.min(100, percent));
    element.style.width = `${clamped}%`;
    
    if (currentHp === null) {
        currentHp = Math.round((clamped / 100) * totalHp);
    } else {
        currentHp = Math.round(currentHp);
    }
    
    if (textElement) {
        const total = Math.max(1, Math.round(totalHp));
        textElement.textContent = `HP: ${currentHp.toLocaleString()} / ${total.toLocaleString()}`;
        
        // Add visual feedback for low HP
        if (clamped <= 35) {
            textElement.style.color = '#ff5252';
            textElement.style.textShadow = '0 0 10px rgba(255, 82, 82, 0.8)';
        } else if (clamped <= 60) {
            textElement.style.color = '#ffb74d';
            textElement.style.textShadow = '0 0 8px rgba(255, 183, 77, 0.6)';
        } else {
            textElement.style.color = 'rgba(255, 255, 255, 0.95)';
            textElement.style.textShadow = '0 1px 3px rgba(0, 0, 0, 0.8)';
        }
    }
    
    if (clamped <= 35) {
        element.classList.add('low');
    } else {
        element.classList.remove('low');
    }
}

function animateDungeonFighter(actorSide, targetSide, damage, dodged, crit) {
    const attacker = document.getElementById(actorSide === 'player' ? 'dungeonFighterPlayer' : 'dungeonFighterEnemy');
    const target = document.getElementById(targetSide === 'player' ? 'dungeonFighterPlayer' : 'dungeonFighterEnemy');
    
    if (attacker) {
        attacker.classList.add('attacking');
        const timer = setTimeout(() => attacker.classList.remove('attacking'), 400);
        dungeonCombatAnimationTimers.push(timer);
    }
    
    if (target) {
        target.classList.add('hit');
        const timer = setTimeout(() => target.classList.remove('hit'), 400);
        dungeonCombatAnimationTimers.push(timer);
        spawnDungeonDamagePop(target, damage, dodged, crit);
    }
}

function spawnDungeonDamagePop(targetEl, damage, dodged, crit) {
    const pop = document.createElement('div');
    pop.className = 'damage-pop';
    if (dodged) {
        pop.textContent = 'MISS';
        pop.classList.add('dodged');
    } else {
        pop.textContent = `-${Math.round(damage)}`;
        if (crit) {
            pop.classList.add('crit');
            pop.textContent = `💥 CRIT! -${Math.round(damage)}`;
        }
    }
    targetEl.appendChild(pop);
    const timer = setTimeout(() => pop.remove(), 1000);
    dungeonCombatAnimationTimers.push(timer);
}

async function dungeonFight() {
    if (!selectedDungeon) {
        showCustomAlert('Vyber dungeon', { type: 'warning' });
        return;
    }
    
    // Ensure selectedFloor is set
    if (!selectedFloor || selectedFloor < 1) {
        const dungeon = allDungeons.find(d => d.id === selectedDungeon);
        selectedFloor = dungeon ? (dungeon.current_floor || 1) : 1;
    }
    
    const fightBtn = document.getElementById('dungeonFightBtn');
    if (fightBtn) {
        fightBtn.disabled = true;
        fightBtn.textContent = 'Bojuji...';
    }
    
    // Show combat visual
    const combatVisual = document.getElementById('dungeonCombatVisual');
    if (combatVisual) {
        combatVisual.style.display = 'block';
    }
    
    try {
        const response = await fetch('/api/dungeons/fight', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({dungeon_id: selectedDungeon, floor: selectedFloor})
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.battle) {
            // Get player stats for context
            const playerStats = {
                hp: data.battle.attacker_hp || 100
            };
            const enemyStats = {
                hp: data.battle.defender_hp || 100
            };
            
            // Play combat animation
            playDungeonCombatAnimation(data.battle, {
                playerLabel: 'Ty',
                enemyLabel: data.enemy_name || 'Protivník',
                playerStats: playerStats,
                enemyStats: enemyStats
            });
            
            // Wait for animation to finish before showing results
            const rounds = data.battle.log || [];
            const animationDuration = 800 * (rounds.length + 2);
            
            setTimeout(() => {
                if (data.victory) {
                    // Show battle results
                    let itemMsg = '';
                    if (data.rewards && data.rewards.item) {
                        itemMsg = `\n🎁 Předmět: ${data.rewards.item}`;
                    }
                    
                    showCustomAlert(`Vítězství! Porazil jsi ${data.enemy_name}${itemMsg}`, {
                        type: 'success',
                        rewards: {
                            gooncoins: data.rewards?.gooncoins,
                            exp: data.rewards?.exp
                        },
                        levelUp: data.new_level && data.new_level > 0 ? data.new_level : null
                    });
                    
                    // Reload dungeons and character
                    loadDungeons();
                    if (typeof loadCharacterPanel === 'function') {
                        loadCharacterPanel();
                    }
                    
                    // Refresh dungeon detail if still open
                    if (selectedDungeon) {
                        selectDungeon(selectedDungeon);
                    }
                } else {
                    showCustomAlert(`Prohra! ${data.enemy_name} tě porazil. Zkus to znovu s lepším vybavením.`, { type: 'warning' });
                }
                
                if (fightBtn) {
                    fightBtn.disabled = false;
                    fightBtn.textContent = `Bojovat na patře ${selectedFloor}`;
                }
            }, animationDuration);
        } else {
            if (data.success) {
                // No battle data, show simple message
                if (data.victory) {
                    showCustomAlert(`Vítězství! Porazil jsi ${data.enemy_name}`, { type: 'success' });
                } else {
                    showCustomAlert(`Prohra! ${data.enemy_name} tě porazil.`, { type: 'warning' });
                }
            } else {
                showCustomAlert(data.error || 'Chyba při boji', { type: 'error' });
            }
            if (fightBtn) {
                fightBtn.disabled = false;
                fightBtn.textContent = `Bojovat na patře ${selectedFloor}`;
            }
        }
    } catch (error) {
        console.error('Error fighting dungeon:', error);
        showCustomAlert('Chyba při boji: ' + (error.message || 'Neznámá chyba'), { type: 'error' });
        if (fightBtn) {
            fightBtn.disabled = false;
            fightBtn.textContent = `Bojovat na patře ${selectedFloor}`;
        }
    }
}

// ========== GUILD SYSTEM ==========

async function loadGuilds() {
    try {
        // Load my guild
        const myGuildResponse = await fetch('/api/guilds/my');
        const myGuildData = await myGuildResponse.json();
        
        if (myGuildData.success) {
            const myGuildEl = document.getElementById('myGuildDisplay');
            if (myGuildEl) {
                if (myGuildData.guild) {
                    const guild = myGuildData.guild;
                    myGuildEl.innerHTML = `
                        <h4>${guild.name}</h4>
                        <p>${guild.description || ''}</p>
                        <p>EXP bonus: +${(guild.exp_bonus * 100).toFixed(1)}%</p>
                        <p>Gold bonus: +${(guild.gold_bonus * 100).toFixed(1)}%</p>
                        <p>Role: ${guild.role}</p>
                        <h5>Členové:</h5>
                        <ul>
                            ${guild.members.map(m => `<li>${m.username} (${m.role})</li>`).join('')}
                        </ul>
                    `;
                } else {
                    myGuildEl.innerHTML = '<p class="muted">Nejsi v žádné guildě</p>';
                }
            }
        }
        
        // Load guilds list
        const guildsResponse = await fetch('/api/guilds/list');
        const guildsData = await guildsResponse.json();
        
        if (guildsData.success) {
            const guildsListEl = document.getElementById('guildsList');
            if (guildsListEl) {
                guildsListEl.innerHTML = guildsData.guilds.map(guild => `
                    <div class="guild-card">
                        <h4>${guild.name}</h4>
                        <p>${guild.description || ''}</p>
                        <p>Členů: ${guild.member_count}</p>
                        <p>EXP bonus: +${(guild.exp_bonus * 100).toFixed(1)}%</p>
                        <p>Gold bonus: +${(guild.gold_bonus * 100).toFixed(1)}%</p>
                        <button class="btn-blue" onclick="joinGuild(${guild.id})">Připojit se</button>
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading guilds:', error);
    }
}

async function createGuild() {
    const name = document.getElementById('guildNameInput').value;
    const description = document.getElementById('guildDescInput').value;
    
    if (!name) {
        alert('Zadej název guildy');
        return;
    }
    
    try {
        const response = await fetch('/api/guilds/create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, description})
        });
        const data = await response.json();
        
        if (data.success) {
            alert('Guilda vytvořena!');
            document.getElementById('guildNameInput').value = '';
            document.getElementById('guildDescInput').value = '';
            loadGuilds();
        } else {
            alert(data.error || 'Chyba při vytváření guildy');
        }
    } catch (error) {
        console.error('Error creating guild:', error);
        alert('Chyba při vytváření guildy');
    }
}

async function joinGuild(guildId) {
    try {
        const response = await fetch('/api/guilds/join', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({guild_id: guildId})
        });
        const data = await response.json();
        
        if (data.success) {
            alert('Připojil jsi se do guildy!');
            loadGuilds();
        } else {
            alert(data.error || 'Chyba při připojování');
        }
    } catch (error) {
        console.error('Error joining guild:', error);
        alert('Chyba při připojování');
    }
}

// Update updateDisplay to include new systems
const originalUpdateDisplay = updateDisplay;
updateDisplay = function() {
    originalUpdateDisplay();
    
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        if (activeTab.id === 'tavern-tab') {
            loadTavernQuests();
            loadMountStatus();
        } else if (activeTab.id === 'blacksmith-tab') {
            loadBlacksmithMaterials();
            loadBlacksmithItems();
        } else if (activeTab.id === 'dungeons-tab') {
            loadDungeons();
        } else if (activeTab.id === 'guilds-tab') {
            loadGuilds();
        } else if (activeTab.id === 'pets-tab') {
            loadPets();
        }
    }
};

// Add event listeners for new systems
function initNewSystems() {
    // Blacksmith
    const upgradeBtn = document.getElementById('blacksmithUpgradeBtn');
    if (upgradeBtn) {
        upgradeBtn.addEventListener('click', blacksmithUpgrade);
    }
    
    const disassembleBtn = document.getElementById('blacksmithDisassembleBtn');
    if (disassembleBtn) {
        disassembleBtn.addEventListener('click', blacksmithDisassemble);
    }
    
    // Blacksmith search and filter
    const searchInput = document.getElementById('blacksmithSearch');
    if (searchInput) {
        searchInput.addEventListener('input', filterBlacksmithItems);
    }
    
    const filterSelect = document.getElementById('blacksmithFilter');
    if (filterSelect) {
        filterSelect.addEventListener('change', filterBlacksmithItems);
    }
    
    // Blacksmith disassemble search and filter
    const disassembleSearchInput = document.getElementById('blacksmithDisassembleSearch');
    if (disassembleSearchInput) {
        disassembleSearchInput.addEventListener('input', filterBlacksmithDisassembleItems);
    }
    
    const disassembleFilterSelect = document.getElementById('blacksmithDisassembleFilter');
    if (disassembleFilterSelect) {
        disassembleFilterSelect.addEventListener('change', filterBlacksmithDisassembleItems);
    }
    
    // Dungeons
    const dungeonFightBtn = document.getElementById('dungeonFightBtn');
    if (dungeonFightBtn) {
        dungeonFightBtn.addEventListener('click', dungeonFight);
    }
    
    // Make selectFloor available globally
    window.selectFloor = selectFloor;
    window.selectDungeon = selectDungeon;
    
    // Guilds
    const createGuildBtn = document.getElementById('createGuildBtn');
    if (createGuildBtn) {
        createGuildBtn.addEventListener('click', createGuild);
    }
    
    // Pets
    const petRarityFilter = document.getElementById('petRarityFilter');
    if (petRarityFilter) {
        petRarityFilter.addEventListener('change', loadPets);
    }
}

// Pets functions
async function loadPets() {
    try {
        const response = await fetch('/api/pets');
        const data = await response.json();
        
        if (data.success) {
            displayMyPets(data.pets || []);
            displayAvailablePets(data.available_pets || [], data.pets || []);
        } else {
            console.error('Error loading pets:', data.error);
        }
    } catch (error) {
        console.error('Error loading pets:', error);
    }
}

function displayMyPets(pets) {
    const container = document.getElementById('myPetsList');
    if (!container) return;
    
    if (pets.length === 0) {
        container.innerHTML = '<p class="muted">Zatím nemáš žádné mazlíčky.</p>';
        return;
    }
    
    container.innerHTML = pets.map(pet => {
        const rarityClass = `rarity-${pet.rarity}`;
        const activeClass = pet.active ? 'active' : '';
        
        const bonusText = Object.entries(pet.bonus || {}).map(([key, value]) => {
            const labels = {
                'click_power': 'Click Power',
                'defense': 'Obrana',
                'luck': 'Štěstí',
                'attack': 'Útok',
                'hp': 'HP'
            };
            return `${labels[key] || key}: ${(value * 100 - 100).toFixed(0)}%`;
        }).join(', ');
        
        return `
            <div class="pet-card ${rarityClass} ${activeClass}" data-pet-id="${pet.id}">
                <div class="pet-header">
                    <span class="pet-rarity rarity-pill ${rarityClass}">${pet.rarity}</span>
                    ${pet.active ? '<span class="pet-active-badge">Aktivní</span>' : ''}
                </div>
                <div class="pet-image">
                    <img src="/images/${pet.image}" alt="${pet.name}" onerror="this.src='/images/lugog.png'">
                </div>
                <div class="pet-name">${pet.name}</div>
                <div class="pet-description">${pet.description || ''}</div>
                <div class="pet-level">Level ${pet.level} / ${pet.max_level}</div>
                <div class="pet-bonus">Bonusy: ${bonusText}</div>
                ${pet.required_fruit_rarity ? `<div class="pet-fruit-requirement">Potřebuje: ${pet.required_fruit_rarity} ovoce nebo lepší</div>` : ''}
                <div class="pet-actions">
                    ${pet.active 
                        ? `<button class="btn-red btn-small" onclick="deactivatePet(${pet.id})">Deaktivovat</button>`
                        : `<button class="btn-green btn-small" onclick="activatePet(${pet.id})">Aktivovat</button>`
                    }
                    <button class="btn-blue btn-small" onclick="toggleFeedPetFruits(${pet.id}, '${pet.required_fruit_rarity || 'common'}')">Nakrmit</button>
                    <button class="btn-yellow btn-small" onclick="showRenamePetModal(${pet.id}, '${pet.name || pet.original_name || ''}')">Přejmenovat</button>
                </div>
                <div class="pet-feed-fruits" id="pet-feed-${pet.id}" style="display: none;">
                    <div class="pet-feed-fruits-list" id="pet-feed-list-${pet.id}"></div>
                </div>
            </div>
        `;
    }).join('');
    
    // Load fruits for each pet
    pets.forEach(pet => {
        loadPetFruits(pet.id, pet.required_fruit_rarity || 'common');
    });
}

function displayAvailablePets(availablePets, ownedPets = []) {
    const container = document.getElementById('availablePetsList');
    if (!container) return;
    
    const rarityFilter = document.getElementById('petRarityFilter')?.value || 'all';
    const filtered = rarityFilter === 'all' 
        ? availablePets 
        : availablePets.filter(p => p.rarity === rarityFilter);
    
    if (filtered.length === 0) {
        container.innerHTML = '<p class="muted">Žádní dostupní mazlíčci.</p>';
        return;
    }
    
    const ownedPetIds = ownedPets.map(p => p.pet_id);
    
    container.innerHTML = filtered.map(pet => {
        const isOwned = ownedPetIds.includes(pet.pet_id);
        const rarityClass = `rarity-${pet.rarity}`;
        const costText = Object.entries(pet.cost || {}).map(([key, value]) => {
            const icons = {
                'gooncoins': '💰',
                'astma': '💨',
                'poharky': '🥃',
                'mrkev': '🥕',
                'uzené': '🍖'
            };
            return `${icons[key] || ''} ${value}`;
        }).join(' ');
        
        const bonusText = Object.entries(pet.bonus || {}).map(([key, value]) => {
            const labels = {
                'click_power': 'Click Power',
                'defense': 'Obrana',
                'luck': 'Štěstí',
                'attack': 'Útok',
                'hp': 'HP'
            };
            return `${labels[key] || key}: +${(value * 100 - 100).toFixed(0)}%`;
        }).join(', ');
        
        return `
            <div class="pet-card ${rarityClass}" data-pet-id="${pet.pet_id}">
                <div class="pet-header">
                    <span class="pet-rarity rarity-pill ${rarityClass}">${pet.rarity}</span>
                </div>
                <div class="pet-image">
                    <img src="/images/${pet.image}" alt="${pet.name}" onerror="this.src='/images/lugog.png'">
                </div>
                <div class="pet-name">${pet.name}</div>
                <div class="pet-description">${pet.description || ''}</div>
                <div class="pet-cost">Cena: ${costText}</div>
                <div class="pet-bonus">Bonusy: ${bonusText}</div>
                <div class="pet-max-level">Max Level: ${pet.max_level}</div>
                ${pet.required_fruit_rarity ? `<div class="pet-fruit-requirement">Potřebuje: ${pet.required_fruit_rarity} ovoce nebo lepší</div>` : ''}
                <div class="pet-actions">
                    ${isOwned 
                        ? '<span class="pet-owned-badge">Již vlastníš</span>'
                        : `<button class="btn-blue btn-small" onclick="buyPet('${pet.pet_id}')">Koupit</button>`
                    }
                </div>
            </div>
        `;
    }).join('');
}

async function buyPet(petId) {
    try {
        const response = await fetch('/api/pets/buy', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pet_id: petId})
        });
        const data = await response.json();
        
        if (data.success) {
            showPetsMessage(data.message || 'Mazlíček zakoupen!', 'success');
            updateGameState(data);
            loadPets();
        } else {
            showPetsMessage(data.error || 'Chyba při nákupu', 'error');
        }
    } catch (error) {
        console.error('Error buying pet:', error);
        showPetsMessage('Chyba při nákupu mazlíčka', 'error');
    }
}

async function activatePet(petId) {
    try {
        const response = await fetch('/api/pets/activate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pet_id: petId})
        });
        const data = await response.json();
        
        if (data.success) {
            showPetsMessage(data.message || 'Mazlíček aktivován!', 'success');
            loadPets();
            loadGameState(); // Reload to get updated bonuses
        } else {
            showPetsMessage(data.error || 'Chyba při aktivaci', 'error');
        }
    } catch (error) {
        console.error('Error activating pet:', error);
        showPetsMessage('Chyba při aktivaci mazlíčka', 'error');
    }
}

async function deactivatePet(petId) {
    try {
        const response = await fetch('/api/pets/deactivate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pet_id: petId})
        });
        const data = await response.json();
        
        if (data.success) {
            showPetsMessage(data.message || 'Mazlíček deaktivován!', 'success');
            loadPets();
            loadGameState(); // Reload to get updated bonuses
        } else {
            showPetsMessage(data.error || 'Chyba při deaktivaci', 'error');
        }
    } catch (error) {
        console.error('Error deactivating pet:', error);
        showPetsMessage('Chyba při deaktivaci mazlíčka', 'error');
    }
}

function showPetsMessage(message, type) {
    const msgEl = document.getElementById('petsMessage');
    if (!msgEl) return;
    
    msgEl.textContent = message;
    msgEl.className = `pets-message ${type}`;
    msgEl.style.display = 'block';
    
    setTimeout(() => {
        msgEl.style.display = 'none';
    }, 3000);
}

function toggleFeedPetFruits(petId, requiredRarity) {
    const feedSection = document.getElementById(`pet-feed-${petId}`);
    if (!feedSection) return;
    
    if (feedSection.style.display === 'none') {
        feedSection.style.display = 'block';
        loadPetFruits(petId, requiredRarity);
    } else {
        feedSection.style.display = 'none';
    }
}

function loadPetFruits(petId, requiredRarity) {
    const container = document.getElementById(`pet-feed-list-${petId}`);
    if (!container) return;
    
    // Get user's fruits from inventory
    const inventory = gameState.inventory?.items || [];
    const fruits = inventory.filter(item => item.item_type === 'fruit' || item.equipment_slot === 'fruit');
    
    // Filter fruits by rarity (must be required rarity or better)
    const rarityOrder = {'common': 1, 'rare': 2, 'epic': 3, 'legendary': 4, 'unique': 5};
    const requiredRarityOrder = rarityOrder[requiredRarity] || 1;
    const availableFruits = fruits.filter(fruit => {
        const fruitRarity = fruit.rarity || 'common';
        return (rarityOrder[fruitRarity] || 1) >= requiredRarityOrder;
    });
    
    if (availableFruits.length === 0) {
        container.innerHTML = `<p class="muted">Nemáš žádné ${requiredRarity} ovoce nebo lepší!</p>`;
        return;
    }
    
    // Group fruits by type and count
    const fruitCounts = {};
    availableFruits.forEach(fruit => {
        const fruitId = fruit.equipment_id;
        if (!fruitCounts[fruitId]) {
            fruitCounts[fruitId] = 0;
        }
        fruitCounts[fruitId]++;
    });
    
    container.innerHTML = `
        <div class="pet-feed-title">Vyber ovoce pro krmení:</div>
        <div class="pet-feed-fruits-grid">
            ${Object.entries(fruitCounts).map(([fruitId, count]) => {
                const fruitDef = getFruitDef(fruitId);
                return `
                    <button class="pet-feed-fruit-btn" onclick="feedPet(${petId}, '${fruitId}')">
                        <span class="pet-feed-fruit-icon">${fruitDef?.icon || '🍎'}</span>
                        <span class="pet-feed-fruit-name">${fruitDef?.name || fruitId}</span>
                        <span class="pet-feed-fruit-count">x${count}</span>
                    </button>
                `;
            }).join('')}
        </div>
    `;
}

function showRenamePetModal(petId, currentName) {
    // Remove existing modal if any
    const existingModal = document.querySelector('.pet-rename-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.className = 'pet-rename-modal';
    modal.innerHTML = `
        <div class="pet-rename-modal-overlay" onclick="this.closest('.pet-rename-modal').remove()"></div>
        <div class="pet-rename-modal-content">
            <h3>Přejmenovat mazlíčka</h3>
            <input type="text" id="petRenameInput" value="${currentName}" maxlength="50" placeholder="Nové jméno">
            <div class="pet-rename-modal-actions">
                <button class="btn-green" onclick="renamePet(${petId})">Uložit</button>
                <button class="btn-red" onclick="this.closest('.pet-rename-modal').remove()">Zrušit</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    const input = modal.querySelector('#petRenameInput');
    input.focus();
    input.select();
}

async function renamePet(petId) {
    const modal = document.querySelector('.pet-rename-modal');
    const input = modal?.querySelector('#petRenameInput');
    if (!input) return;
    
    const newName = input.value.trim();
    if (!newName) {
        showPetsMessage('Jméno nemůže být prázdné', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/pets/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pet_id: petId, name: newName})
        });
        const data = await response.json();
        
        if (data.success) {
            showPetsMessage(data.message || 'Mazlíček přejmenován!', 'success');
            loadPets();
            if (modal) modal.remove();
        } else {
            showPetsMessage(data.error || 'Chyba při přejmenování', 'error');
        }
    } catch (error) {
        console.error('Error renaming pet:', error);
        showPetsMessage('Chyba při přejmenování mazlíčka', 'error');
    }
}

function getFruitDef(fruitId) {
    const fruitDefs = {
        'fruit_common': { name: 'Základní Ovoce', rarity: 'common', icon: '🍎' },
        'fruit_rare': { name: 'Vzácné Ovoce', rarity: 'rare', icon: '🍊' },
        'fruit_epic': { name: 'Epické Ovoce', rarity: 'epic', icon: '🍇' },
        'fruit_legendary': { name: 'Legendární Ovoce', rarity: 'legendary', icon: '🍑' },
        'fruit_unique': { name: 'Unikátní Ovoce', rarity: 'unique', icon: '🍒' },
        'rajcata': { name: 'Rajčata', rarity: 'common', icon: '🍅' },
        'okurky': { name: 'Okurky', rarity: 'common', icon: '🥒' },
        'papriky': { name: 'Papriky', rarity: 'rare', icon: '🫑' },
        'cibule': { name: 'Cibule', rarity: 'common', icon: '🧅' },
        'mata': { name: 'Máta', rarity: 'common', icon: '🌿' },
        'slepici_vejce': { name: 'Slepičí Vejce', rarity: 'rare', icon: '🥚' },
        'pochcane_maliny': { name: 'Pochcané Maliny', rarity: 'rare', icon: '🫐' }
    };
    return fruitDefs[fruitId] || null;
}

// Garden System Functions
let gardenFruitsCache = {};
let gardenLoadingInProgress = false;

async function loadGarden() {
    // Prevent multiple simultaneous calls
    if (gardenLoadingInProgress) {
        return;
    }
    
    gardenLoadingInProgress = true;
    try {
        const response = await fetch('/api/garden');
        const data = await response.json();
        
        if (data.success) {
            gardenFruitsCache = data.fruits || {};
            displayGardenPlots(data.plots || []);
            displayGardenShop(data.available_seeds || []);
        } else {
            console.error('Error loading garden:', data.error);
            // Clear loading messages even on error
            displayGardenPlots([]);
            displayGardenShop([]);
            showGardenMessage(data.error || 'Chyba při načítání zahrady', 'error');
        }
    } catch (error) {
        console.error('Error loading garden:', error);
        // Clear loading messages even on error
        displayGardenPlots([]);
        displayGardenShop([]);
        showGardenMessage('Chyba při načítání zahrady', 'error');
    } finally {
        gardenLoadingInProgress = false;
    }
}

function displayGardenPlots(plots) {
    const container = document.getElementById('gardenPlotsList');
    if (!container) return;
    
    if (plots.length === 0) {
        container.innerHTML = '<p class="muted">Nemáš žádné zasazené semínka. Kupte si semínko v obchodě!</p>';
        return;
    }
    
    container.innerHTML = plots.map(plot => {
        const timeRemaining = plot.time_remaining || 0;
        const hours = Math.floor(timeRemaining / 3600);
        const minutes = Math.floor((timeRemaining % 3600) / 60);
        const seconds = timeRemaining % 60;
        const timeStr = hours > 0 
            ? `${hours}h ${minutes}m`
            : minutes > 0 
                ? `${minutes}m ${seconds}s`
                : `${seconds}s`;
        
        return `
            <div class="garden-plot-card">
                <div class="plot-info">
                    <h4>${plot.seed_name}</h4>
                    <p class="muted">Produkuje: ${plot.produces}</p>
                    ${plot.is_ready
                        ? '<p class="ready-text">✅ Připraveno ke sklizni!</p>'
                        : `<p class="time-text">⏱️ Zbývá: ${timeStr}</p>`
                    }
                </div>
                <div class="plot-actions">
                    ${plot.is_ready
                        ? `<button class="btn-green btn-small" onclick="harvestPlot(${plot.id})">Sklidit</button>`
                        : '<button class="btn-disabled btn-small" disabled>Čeká...</button>'
                    }
                </div>
            </div>
        `;
    }).join('');
}

function displayGardenShop(seeds) {
    const container = document.getElementById('gardenShopList');
    if (!container) return;
    
    if (seeds.length === 0) {
        container.innerHTML = '<p class="muted">Žádná semínka k dispozici.</p>';
        return;
    }
    
    container.innerHTML = seeds.map(seed => {
        const rarityClass = `rarity-${seed.rarity}`;
        const costText = Object.entries(seed.cost || {}).map(([key, value]) => {
            const icons = {
                'gooncoins': '💰',
                'astma': '💨',
                'poharky': '🥃',
                'mrkev': '🥕',
                'uzené': '🍖'
            };
            return `${icons[key] || ''} ${value.toLocaleString()}`;
        }).join(' ');
        
        const growthHours = Math.floor(seed.growth_time / 3600);
        const growthMinutes = Math.floor((seed.growth_time % 3600) / 60);
        const growthTimeStr = growthHours > 0 
            ? `${growthHours}h ${growthMinutes}m`
            : `${growthMinutes}m`;
        
        return `
            <div class="seed-card ${rarityClass}">
                <div class="seed-header">
                    <span class="seed-rarity rarity-pill ${rarityClass}">${seed.rarity}</span>
                </div>
                <div class="seed-name">${seed.name}</div>
                <div class="seed-description">${seed.description || ''}</div>
                <div class="seed-info">
                    <p>🌱 Růst: ${growthTimeStr}</p>
                    <p>${seed.fruit_icon} Produkuje: ${seed.fruit_name}</p>
                </div>
                <div class="seed-cost">Cena: ${costText}</div>
                <div class="seed-actions">
                    <button class="btn-blue btn-small" onclick="buySeed('${seed.seed_id}')">Koupit & Zasít</button>
                </div>
            </div>
        `;
    }).join('');
}

function displayGardenFruits(fruits) {
    const container = document.getElementById('gardenFruitsList');
    if (!container) return;
    
    const fruitEntries = Object.entries(fruits || {}).filter(([_, qty]) => qty > 0);
    
    if (fruitEntries.length === 0) {
        container.innerHTML = '<p class="muted">Nemáš žádné ovoce. Sklízej ze záhonů!</p>';
        return;
    }
    
    container.innerHTML = fruitEntries.map(([fruitId, quantity]) => {
        const fruitDef = getFruitDef(fruitId);
        if (!fruitDef) return '';
        
        return `
            <div class="fruit-item">
                <span class="fruit-icon">${fruitDef.icon}</span>
                <span class="fruit-name">${fruitDef.name}</span>
                <span class="fruit-quantity">x${quantity}</span>
            </div>
        `;
    }).join('');
}

async function loadGardenFruits() {
    try {
        const response = await fetch('/api/garden');
        const data = await response.json();
        if (data.success) {
            gardenFruitsCache = data.fruits || {};
            return gardenFruitsCache;
        }
    } catch (error) {
        console.error('Error loading garden fruits:', error);
    }
    return {};
}

async function buySeed(seedId) {
    try {
        const response = await fetch('/api/garden/buy-seed', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({seed_id: seedId})
        });
        const data = await response.json();
        
        if (data.success) {
            showGardenMessage(data.message || 'Semínko zakoupeno!', 'success');
            updateGameState(data);
            loadGarden();
        } else {
            showGardenMessage(data.error || 'Chyba při nákupu', 'error');
        }
    } catch (error) {
        console.error('Error buying seed:', error);
        showGardenMessage('Chyba při nákupu semínka', 'error');
    }
}

async function harvestPlot(plotId) {
    try {
        const response = await fetch('/api/garden/harvest', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({plot_id: plotId})
        });
        const data = await response.json();
        
        if (data.success) {
            showGardenMessage(data.message || 'Sklizeno!', 'success');
            loadGarden();
            loadPets();
        } else {
            showGardenMessage(data.error || 'Chyba při sklizni', 'error');
        }
    } catch (error) {
        console.error('Error harvesting plot:', error);
        showGardenMessage('Chyba při sklizni', 'error');
    }
}

async function feedPet(petId, fruitId) {
    try {
        const response = await fetch('/api/pets/feed', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pet_id: petId, fruit_id: fruitId})
        });
        const data = await response.json();
        
        if (data.success) {
            showPetsMessage(data.message || 'Mazlíček nakrmen!', 'success');
            // Reload game state to update inventory
            await loadGameState();
            // Reload pets to update levels
            await loadPets();
        } else {
            showPetsMessage(data.error || 'Chyba při krmení', 'error');
        }
    } catch (error) {
        console.error('Error feeding pet:', error);
        showPetsMessage('Chyba při krmení mazlíčka', 'error');
    }
}

function showGardenMessage(message, type) {
    const msgEl = document.getElementById('gardenMessage');
    if (!msgEl) return;
    msgEl.textContent = message;
    msgEl.className = `garden-message ${type}`;
    msgEl.style.display = 'block';
    setTimeout(() => {
        msgEl.style.display = 'none';
    }, 3000);
}

// Make functions globally available
window.buySeed = buySeed;
window.harvestPlot = harvestPlot;
window.feedPet = feedPet;

// Initialize on page load
// Funkce pro aktualizaci mobilního zobrazení
function setupMobileView() {
    function updateMobileView() {
        const isMobile = window.innerWidth <= 768;
        const combatTab = document.getElementById('combat-tab');
        const craftingTab = document.getElementById('crafting-tab');
        
        if (combatTab) {
            if (isMobile) {
                combatTab.classList.add('mobile-view');
            } else {
                combatTab.classList.remove('mobile-view');
            }
        }
        
        if (craftingTab) {
            if (isMobile) {
                craftingTab.classList.add('mobile-view');
            } else {
                craftingTab.classList.remove('mobile-view');
            }
        }
    }
    
    // Aktualizace při načtení
    updateMobileView();
    
    // Aktualizace při změně velikosti okna
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(updateMobileView, 100);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initGame();
    initNewSystems();
});


