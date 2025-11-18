// Game state
let gameState = {
    gooncoins: 0,
    astma: 0,
    poharky: 0,
    mrkev: 0,
    uzené: 0,
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
    uzené: 'Uzené'
};

const RESOURCE_KEYS = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'];

const RESOURCE_LABELS = {
    gooncoins: 'Gooncoiny',
    astma: 'Astma',
    poharky: 'Pohárky',
    mrkev: 'Mrkev',
    uzené: 'Uzené',
    favor: 'Přízeň'
};

const CASE_CURRENCY_ICONS = {
    gooncoins: '💰',
    astma: '💨',
    poharky: '🥃',
    mrkev: '🥕',
    uzené: '🍖'
};

const CASE_SLOT_WIDTH = 120;
const CASE_SPIN_DURATION = 3400;

let lastInflationRate = 0;

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
    auto_gooncoin: {
        name: '💰 Auto-generátor Gooncoinů',
        description: 'Automaticky generuje Gooncoiny každou sekundu',
        icon: '💰'
    },
    astma_collector: {
        name: '💨 Sběrač Astma',
        description: 'Automaticky sbírá inhalátory (Astma) z lékáren Lugog',
        icon: '💨'
    },
    poharky_collector: {
        name: '🥃 Sběrač Pohárků',
        description: 'Automaticky sbírá pohárky z hospod Lugog',
        icon: '🥃'
    },
    mrkev_collector: {
        name: '🥕 Sběrač Mrkve',
        description: 'Automaticky sbírá mrkev z polí Lugog',
        icon: '🥕'
    },
    uzené_collector: {
        name: '🍖 Sběrač Uzeného',
        description: 'Automaticky sbírá uzené z uzenářství Lugog',
        icon: '🍖'
    }
};

const autoGeneratorBlueprints = {
    auto_gooncoin: {
        resourceKey: 'gooncoins',
        ratePerLevel: 0.1,
        flavor: 'Najímá účetní, kteří ti sypou drobné na účet.'
    },
    astma_collector: {
        resourceKey: 'astma',
        ratePerLevel: 0.05,
        flavor: 'Kurýři objíždí lékárny a přiváží inhalátory.'
    },
    poharky_collector: {
        resourceKey: 'poharky',
        ratePerLevel: 0.03,
        flavor: 'Noční směna z klubů odnáší všechny pohárky.'
    },
    mrkev_collector: {
        resourceKey: 'mrkev',
        ratePerLevel: 0.02,
        flavor: 'Farmáři sklízí mrkve pomocí autonomních kombajnů.'
    },
    uzené_collector: {
        resourceKey: 'uzené',
        ratePerLevel: 0.01,
        flavor: 'Udírny pracují nonstop a posílají zásoby k tobě.'
    }
};

// Story and game data
let storyData = {};
let equipmentDefs = {};
let buildingsDefs = {};
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

const EQUIPMENT_SLOTS = ['weapon', 'armor', 'helmet', 'ring', 'amulet', 'special', 'accessory', 'vehicle'];
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
try {
    if (typeof localStorage !== 'undefined') {
        selectedCraftSort = localStorage.getItem('craftSortPreference') || 'unlocked';
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
    setupClickButton();
    setupUpgrades();
    setupAutoGenerators();
    setupCrafting();
    setupBuildings();
    setupQuests();
    setupEquipment();
    setupPlayerView();
    setupMarket();
    await setupCases();
    setupCombat();
    setupTempleSection();
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
            document.getElementById(`${tab}-tab`).classList.add('active');

            closeMobileNav();
            updateDisplay();
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

function updateEconomyPanel() {
    const inflationRate = gameState.economy?.inflation_rate || 0;
    const supply = gameState.economy?.gooncoin_supply || 0;
    const multiplier = getInflationMultiplier();
    
    const rateEl = document.getElementById('inflationRate');
    const supplyEl = document.getElementById('gooncoinSupply');
    const multiplierEl = document.getElementById('inflationMultiplier');
    const trendEl = document.getElementById('inflationTrend');
    
    if (rateEl) rateEl.textContent = formatPercent(inflationRate);
    if (supplyEl) supplyEl.textContent = formatNumber(supply);
    if (multiplierEl) multiplierEl.textContent = `${multiplier.toFixed(2)}×`;
    
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
    
    entries.forEach(([currency, data]) => {
        const row = document.createElement('div');
        const isUnlocked = unlocked.has(currency);
        row.className = `market-rate-row ${isUnlocked ? '' : 'locked'}`;
        row.innerHTML = `
            <div class="market-rate-label">
                <span class="resource-icon">${getResourceIcon(currency)}</span>
                <div>
                    <strong>${getCurrencyLabel(currency)}</strong>
                    ${!isUnlocked ? '<small>🔒 Odemkni v příběhu</small>' : ''}
                </div>
            </div>
            <div class="market-rate-values">
                <span>Koupě: ${data.buy.toFixed(2)} 💰</span>
                <span>Prodej: ${data.sell.toFixed(2)} 💰</span>
            </div>
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
    
    let hasUnlocked = false;
    Array.from(select.options).forEach(option => {
        const isUnlocked = unlocked.has(option.value);
        option.disabled = !isUnlocked;
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
            <div>
                <span>⚔ Síla</span>
                <strong>${stats.attack.toFixed(1)}</strong>
            </div>
            <div>
                <span>🛡 Obrana</span>
                <strong>${stats.defense.toFixed(1)}</strong>
            </div>
            <div>
                <span>💫 Štěstí</span>
                <strong>${stats.luck.toFixed(2)}</strong>
            </div>
            <div>
                <span>❤️ Výdrž</span>
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
            return (gameState[resource] || 0) >= value;
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
            : (gameState[resource] || 0) >= value;
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
    if (logEl) logEl.textContent = 'Boj začíná...';
    
    updateHpFill(playerHpFill, 100);
    updateHpFill(enemyHpFill, 100);
    
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
                updateHpFill(enemyHpFill, (enemyHp / enemyTotalHp) * 100);
            } else if (entry.actor === 'defender' && !dodged) {
                playerHp = Math.max(0, playerHp - damage);
                updateHpFill(playerHpFill, (playerHp / playerTotalHp) * 100);
            }
            
            animateFighter(attackerSide, targetSide, damage, dodged, entry.crit);
            if (logEl) {
                if (dodged) {
                    logEl.textContent = entry.actor === 'attacker'
                        ? `${context.playerLabel || 'Ty'} míjí`
                        : `${context.enemyLabel || 'Protivník'} míjí`;
                } else {
                    logEl.textContent = entry.actor === 'attacker'
                        ? `Útočíš za ${damage.toFixed(1)}`
                        : `${context.enemyLabel || 'Protivník'} zasazuje ${damage.toFixed(1)}`;
                }
            }
        }, stepDuration * index);
        combatAnimationTimers.push(timer);
    });
    
    const endTimer = setTimeout(() => {
        if (logEl) {
            if (battle.winner === 'attacker') {
                logEl.textContent = 'Výhra!';
            } else if (battle.winner === 'defender') {
                logEl.textContent = 'Porážka.';
            } else {
                logEl.textContent = 'Remíza.';
            }
        }
    }, stepDuration * (rounds.length + 1));
    combatAnimationTimers.push(endTimer);
}

function updateHpFill(element, percent) {
    const clamped = Math.max(0, Math.min(100, percent));
    element.style.width = `${clamped}%`;
    if (clamped <= 35) {
        element.classList.add('low');
    } else {
        element.classList.remove('low');
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

// Auto-refresh upgrades every 2 seconds
let lastQuestState = '';
function startAutoRefresh() {
    setInterval(async () => {
        await loadGameState();
        // Only refresh upgrades if we're on the gather tab
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab && activeTab.id === 'gather-tab') {
            setupUpgrades();
            setupAutoGenerators();
        }
        // Update display but don't reload equipment if we're on equipment tab (prevents flickering)
        const currentTab = document.querySelector('.tab-content.active');
        if (currentTab && currentTab.id !== 'equipment-tab') {
            updateDisplay();
        } else {
            // Just update resources, not equipment
            updateResourcesOnly();
        }
        
        // Only reload quests if they actually changed (prevents flickering)
        const questState = JSON.stringify(gameState.story?.completed_quests || []);
        if (questState !== lastQuestState) {
            lastQuestState = questState;
            loadQuests();
        }
    }, 2000);
}

// Load game state from server
async function loadGameState() {
    try {
        const response = await fetch('/api/game-state');
        if (response.ok) {
            const data = await response.json();
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
            updateDisplay();
            setupAutoGenerators();
            if (data.temple) {
                templeSnapshot = data.temple;
                renderTempleSection();
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
function startAutoGeneration() {
    let lastUpdate = Date.now();
    
    // Use requestAnimationFrame for smooth updates, but also works in background
    function generateLoop() {
        const now = Date.now();
        const elapsed = (now - lastUpdate) / 1000; // seconds
        
        if (elapsed >= 1.0) {
            // Generate resources
            fetch('/api/auto-generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.gooncoins !== undefined) {
                    gameState.gooncoins = data.gooncoins;
                    gameState.astma = data.astma;
                    gameState.poharky = data.poharky;
                    gameState.mrkev = data.mrkev;
                    gameState.uzené = data.uzené;
                    updateResourcesOnly();
                }
            })
            .catch(error => console.error('Error auto-generating:', error));
            
            lastUpdate = now;
        }
        
        requestAnimationFrame(generateLoop);
    }
    
    // Also use setInterval as backup for when tab is in background
    setInterval(async () => {
        try {
            const response = await fetch('/api/auto-generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            if (response.ok) {
                const data = await response.json();
                gameState.gooncoins = data.gooncoins;
                gameState.astma = data.astma;
                gameState.poharky = data.poharky;
                gameState.mrkev = data.mrkev;
                gameState.uzené = data.uzené;
                if (data.generation_rates) {
                    gameState.generation_rates = data.generation_rates;
                }
                updateResourcesOnly();
            }
        } catch (error) {
            console.error('Error auto-generating:', error);
        }
    }, 1000);
    
    generateLoop();
}

// Setup upgrades
function setupUpgrades() {
    const upgradesList = document.getElementById('upgradesList');
    if (!upgradesList) return; // Don't update if element doesn't exist
    
    upgradesList.innerHTML = '';
    
    for (const [key, upgrade] of Object.entries(upgrades)) {
        const level = gameState.upgrades[key] || 0;
        const upgradeItem = createUpgradeItem(key, upgrade, level);
        upgradesList.appendChild(upgradeItem);
    }
}

function setupAutoGenerators() {
    const list = document.getElementById('autoGeneratorsList');
    if (!list) return;
    
    const entries = Object.entries(autoGeneratorBlueprints);
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
            const currentAmount = Number(gameState[resource] || 0);
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
    const baseCosts = {
        click_power_1: { gooncoins: 10, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        click_power_2: { gooncoins: 50, astma: 5, poharky: 0, mrkev: 0, uzené: 0 },
        auto_gooncoin: { gooncoins: 100, astma: 10, poharky: 0, mrkev: 0, uzené: 0 },
        astma_collector: { gooncoins: 50, astma: 0, poharky: 0, mrkev: 0, uzené: 0 },
        poharky_collector: { gooncoins: 75, astma: 5, poharky: 0, mrkev: 0, uzené: 0 },
        mrkev_collector: { gooncoins: 100, astma: 10, poharky: 5, mrkev: 0, uzené: 0 },
        uzené_collector: { gooncoins: 150, astma: 15, poharky: 10, mrkev: 5, uzené: 0 }
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

// Get resource icon
function getResourceIcon(resource) {
    const icons = {
        gooncoins: '💰',
        astma: '💨',
        poharky: '🥃',
        mrkev: '🥕',
        uzené: '🍖',
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
            alert(errorData.error || 'Chyba při nákupu upgradů');
            return;
        }
        
        const data = await response.json();
        if (data.success) {
            gameState.gooncoins = data.gooncoins;
            gameState.astma = data.astma;
            gameState.poharky = data.poharky;
            gameState.mrkev = data.mrkev;
            gameState.uzené = data.uzené;
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
            alert(data.error || 'Chyba při nákupu upgradů');
        }
    } catch (error) {
        console.error('Error buying upgrade:', error);
        alert('Chyba připojení k serveru: ' + error.message);
    }
}

// Update display - old function removed, using new one below

// Format number
function formatNumber(num) {
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
    loadCrafting();
}

function loadCrafting() {
    const craftingList = document.getElementById('craftingList');
    if (!craftingList || !equipmentDefs || Object.keys(equipmentDefs).length === 0) return;
    
    craftingList.innerHTML = '';
    
    const playerCounts = gameState.equipmentCounts || {};
    
    const items = Object.entries(equipmentDefs).map(([id, def]) => {
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
    }).sort((a, b) => sortCraftItems(a, b, selectedCraftSort));
    
    if (!items.length) return;
    
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
        gameState[resource] >= amount
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
                loadEquipment();
            } else {
                alert(data.error || 'Chyba při výrobě');
            }
        }
    } catch (error) {
        console.error('Error crafting:', error);
    }
}

// Setup buildings
function setupBuildings() {
    // Will be populated when game state loads
}

function loadBuildings() {
    const buildingsList = document.getElementById('buildingsList');
    if (!buildingsList) return;
    
    buildingsList.innerHTML = '';
    
    const unlocked = gameState.story?.unlocked_buildings || [];
    
    for (const [id, def] of Object.entries(buildingsDefs)) {
        const item = document.createElement('div');
        item.className = 'building-item';
        
        const isBuilt = gameState.buildings?.[id] > 0;
        const isUnlocked = id === 'workshop' || unlocked.includes(id);
        
        if (!isUnlocked) {
            item.classList.add('locked');
        }
        
        const baseCost = def.cost;
        const effectiveCost = applyInflationToCostMap(baseCost);
        const canAfford = isUnlocked && canAffordCraft(effectiveCost);
        
        item.innerHTML = `
            <h4>${def.name} ${isBuilt ? '(Postaveno)' : ''}</h4>
            <p>${def.description}</p>
            ${!isUnlocked ? '<p style="color: #f44336;">Ještě není odemčeno</p>' : ''}
            ${!isBuilt ? `
                <div class="upgrade-cost">
                    ${Object.entries(effectiveCost).filter(([_, c]) => c > 0).map(([resource, c]) => 
                        `<span class="cost-item ${gameState[resource] < c ? 'insufficient' : ''}">
                            ${getResourceIcon(resource)} ${formatCostValue(c)}
                        </span>`
                    ).join('')}
                </div>
                <button class="btn-buy" onclick="buildBuilding('${id}')" ${!canAfford ? 'disabled' : ''}>
                    Postavit
                </button>
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
                gameState.gooncoins = data.gooncoins;
                gameState.astma = data.astma;
                gameState.poharky = data.poharky;
                if (!gameState.buildings) gameState.buildings = {};
                gameState.buildings[buildingType] = 1;
                updateDisplay();
                loadBuildings();
            } else {
                alert(data.error || 'Chyba při stavbě');
            }
        }
    } catch (error) {
        console.error('Error building:', error);
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
            alert(errorData.error || 'Quest nelze dokončit');
            return;
        }
        
        const data = await response.json();
        if (data.success) {
            gameState.gooncoins = data.gooncoins;
            gameState.astma = data.astma;
            if (data.poharky !== undefined) gameState.poharky = data.poharky;
            if (data.mrkev !== undefined) gameState.mrkev = data.mrkev;
            if (data.uzené !== undefined) gameState.uzené = data.uzené;
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
            alert(data.error || 'Quest nelze dokončit');
        }
    } catch (error) {
        console.error('Error completing quest:', error);
    }
}

// Setup equipment
function setupEquipment() {
    // Will be populated when game state loads
}

let lastEquipmentState = '';

function loadEquipment() {
    const equipped = gameState.equipment || {};
    
    // Create state string to check if equipment changed
    const currentState = JSON.stringify(equipped);
    if (currentState === lastEquipmentState) {
        return; // No change, don't update to prevent flickering
    }
    lastEquipmentState = currentState;
    
    EQUIPMENT_SLOTS.forEach(slot => {
        const slotElement = document.getElementById(`${slot}Slot`);
        if (slotElement) {
            const eqId = equipped[slot];
            if (eqId && equipmentDefs[eqId]) {
                const def = equipmentDefs[eqId];
                const newContent = `
                    ${def.image ? `<img src="/images/${def.image}" alt="${def.name}" class="equipment-slot-image" onerror="this.style.display='none'">` : ''}
                    <div>${def.name}</div>
                `;
                // Only update if content changed
                if (slotElement.innerHTML !== newContent) {
                    slotElement.innerHTML = newContent;
                }
            } else {
                if (slotElement.textContent !== 'Prázdné') {
                    slotElement.textContent = 'Prázdné';
                }
            }
        }
    });
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
        if (inventoryFilters.rarity !== 'all' && item.rarity !== inventoryFilters.rarity) {
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
        const trendClass = item.market_trend === 'up' ? 'trend-up' : item.market_trend === 'down' ? 'trend-down' : 'trend-flat';
        const trendSymbol = item.market_trend === 'up' ? '▲' : item.market_trend === 'down' ? '▼' : '↔';
        return `
            <div class="inventory-item ${item.equipped ? 'equipped' : ''}">
                <div class="inventory-item-header">
                    <div class="inventory-item-title">
                        <h4>${item.name}</h4>
                        <div class="inventory-item-meta">
                            <span class="inventory-chip rarity-pill rarity-${rarity.key}">${rarity.label}</span>
                            <span class="inventory-chip">${getSlotLabel(item.slot)}</span>
                            ${item.equipped ? '<span class="inventory-chip">Vybaveno</span>' : ''}
                        </div>
                    </div>
                    <div class="inventory-item-value">
                        <span>Tržní cena</span>
                        <strong>${formatInventoryValue(item.market_value || item.base_value)} 💰</strong>
                        <small class="${trendClass}">${trendSymbol} ${marketInfo.price_multiplier ? marketInfo.price_multiplier.toFixed(2) : '1.00'}×</small>
                    </div>
                </div>
                <div class="inventory-item-meta">
                    <span>${item.acquisition_note || 'Získáno'} • ${formatInventoryTimestamp(item.acquired_at)}</span>
                    ${typeof marketInfo.current_supply === 'number' ? `<span>V oběhu: ${marketInfo.current_supply}</span>` : ''}
                </div>
                <div class="inventory-item-actions">
                    <button class="btn-red" data-sell-id="${item.instance_id}" onclick="sellInventoryItem(${item.instance_id})">
                        Prodat za ${formatInventoryValue(item.sell_value || item.market_value || item.base_value)} 💰
                    </button>
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
    if (button) {
        button.disabled = true;
        button.dataset.original = button.textContent;
        button.textContent = 'Prodávám...';
    }
    try {
        const response = await fetch('/api/inventory/sell', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ instance_id: instanceId })
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
                alert('Zadej jméno hráče');
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
                    alert('Hráč nenalezen');
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
    
    const astmaStatus = document.getElementById('astmaStatus');
    if (astmaStatus) {
        const rate = rates.astma || 0;
        const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}`;
        astmaStatus.innerHTML = `💨 <span id="astmaValue">${formatNumber(gameState.astma)}</span> (${formattedRate}/s)`;
    }
    
    const poharkyStatus = document.getElementById('poharkyStatus');
    if (poharkyStatus) {
        const rate = rates.poharky || 0;
        const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}`;
        poharkyStatus.innerHTML = `🥃 <span id="poharkyValue">${formatNumber(gameState.poharky)}</span> (${formattedRate}/s)`;
    }
    
    const mrkevStatus = document.getElementById('mrkevStatus');
    if (mrkevStatus) {
        const rate = rates.mrkev || 0;
        const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}`;
        mrkevStatus.innerHTML = `🥕 <span id="mrkevValue">${formatNumber(gameState.mrkev)}</span> (${formattedRate}/s)`;
    }
    
    const uzenéStatus = document.getElementById('uzenéStatus');
    if (uzenéStatus) {
        const rate = rates.uzené || 0;
        const formattedRate = `${rate >= 0 ? '+' : ''}${rate.toFixed(2)}`;
        uzenéStatus.innerHTML = `🍖 <span id="uzenéValue">${formatNumber(gameState.uzené)}</span> (${formattedRate}/s)`;
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
        if (el) el.textContent = formatNumber(gameState[resources[idx]]);
    });
    
    refreshCaseButtonState();
}

// Update display to include all new elements
function updateDisplay() {
    updateResourcesOnly();
    updateEconomyPanel();
    
    // Update click value
    const clickValueEl = document.getElementById('clickValue');
    if (clickValueEl) clickValueEl.textContent = gameState.clickValue.toFixed(1);
    
    // Reload dynamic content only if on relevant tabs
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab) {
        if (activeTab.id === 'crafting-tab') {
            loadCrafting();
        } else if (activeTab.id === 'buildings-tab') {
            loadBuildings();
        } else if (activeTab.id === 'equipment-tab') {
            loadEquipment(); // Only update equipment when on equipment tab
        } else if (activeTab.id === 'inventory-tab') {
            loadInventory();
        } else if (activeTab.id === 'leaderboard-tab') {
            loadLeaderboard();
        }
        
        // Only update quests if we're not on equipment tab (prevents flickering)
        if (activeTab.id !== 'equipment-tab' && activeTab.id !== 'inventory-tab') {
            loadQuests();
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initGame);

