(() => {
    const STORAGE_KEY = 'lugog_idle_engine_v1';

    class StorageManager {
        constructor(key) {
            this.key = key;
        }

        load() {
            try {
                const raw = localStorage.getItem(this.key);
                return raw ? JSON.parse(raw) : null;
            } catch (err) {
                console.warn('Nepodařilo se načíst stav:', err);
                return null;
            }
        }

        save(payload) {
            try {
                localStorage.setItem(this.key, JSON.stringify(payload));
                return true;
            } catch (err) {
                console.warn('Nepodařilo se uložit stav:', err);
                return false;
            }
        }
    }

    class Resource {
        constructor(data) {
            this.name = data.name;
            this.baseProduction = data.baseProduction ?? 0;
            this.baseMultiplier = data.multiplier ?? 1;
            this.reset();
        }

        reset() {
            this.amount = 0;
            this.multiplier = this.baseMultiplier;
            this.generated = 0;
        }

        add(value) {
            if (value <= 0) return;
            this.amount += value;
            this.generated += value;
        }

        spend(cost) {
            if (this.amount < cost) return false;
            this.amount -= cost;
            return true;
        }

        serialize() {
            return {
                name: this.name,
                amount: this.amount,
                multiplier: this.multiplier,
                generated: this.generated
            };
        }

        hydrate(payload) {
            this.amount = payload.amount ?? this.amount;
            this.multiplier = payload.multiplier ?? this.baseMultiplier;
            this.generated = payload.generated ?? this.generated;
        }
    }

    class Worker {
        constructor(data) {
            this.name = data.name;
            this.baseCost = data.cost.amount;
            this.costResource = data.cost.resource;
            this.baseProduction = data.baseProduction;
            this.costScaling = data.costScaling ?? 1.15;
            this.amountOwned = data.amountOwned ?? 0;
            this.multiplier = data.multiplier ?? 1;
            this.produces = data.produces;
            this.unlockRequirement = data.unlockRequirement || null;
            this.description = data.description || '';
        }

        currentCost() {
            return this.baseCost * Math.pow(this.costScaling, this.amountOwned);
        }

        isUnlocked(game) {
            if (!this.unlockRequirement) return true;
            const { resource, amount, totalGenerated } = this.unlockRequirement;
            if (resource && amount != null) {
                const res = game.resources.get(resource);
                if (res && res.generated >= amount) {
                    return true;
                }
            }
            if (totalGenerated != null) {
                return game.state.totals.totalGenerated >= totalGenerated;
            }
            return false;
        }

        canAfford(game) {
            const resource = game.resources.get(this.costResource);
            if (!resource) return false;
            return resource.amount >= this.currentCost();
        }

        buy(game) {
            const resource = game.resources.get(this.costResource);
            if (!resource) return false;
            const cost = this.currentCost();
            if (!resource.spend(cost)) return false;
            this.amountOwned += 1;
            return true;
        }

        productionPerSecond(game) {
            if (this.amountOwned === 0) return 0;
            const resource = game.resources.get(this.produces);
            if (!resource) return 0;
            const prestigeBonus = game.prestigeManager.globalMultiplier;
            return this.amountOwned * this.baseProduction * this.multiplier * prestigeBonus * resource.multiplier;
        }

        reset() {
            this.amountOwned = 0;
            this.multiplier = 1;
        }

        serialize() {
            return {
                name: this.name,
                amountOwned: this.amountOwned,
                multiplier: this.multiplier
            };
        }

        hydrate(payload) {
            this.amountOwned = payload.amountOwned ?? this.amountOwned;
            this.multiplier = payload.multiplier ?? this.multiplier;
        }
    }

    class Upgrade {
        constructor(data) {
            this.name = data.name;
            this.cost = data.cost;
            this.target = data.target;
            this.effectType = data.effectType;
            this.effectValue = data.effectValue;
            this.description = data.description || '';
            this.unlockRequirement = data.unlockRequirement || null;
            this.purchased = data.purchased ?? false;
        }

        isAffordable(game) {
            const res = game.resources.get(this.cost.resource);
            if (!res) return false;
            return res.amount >= this.cost.amount;
        }

        isVisible(game) {
            if (this.purchased) return true;
            if (!this.unlockRequirement) return true;
            const { totalGenerated, resource } = this.unlockRequirement;
            if (typeof totalGenerated === 'number' && game.state.totals.totalGenerated >= totalGenerated) {
                return true;
            }
            if (resource) {
                const res = game.resources.get(resource.name);
                if (res && res.generated >= (resource.generated ?? 0)) {
                    return true;
                }
            }
            return false;
        }

        apply(game) {
            if (this.purchased) return false;
            const resource = game.resources.get(this.cost.resource);
            if (!resource || resource.amount < this.cost.amount) return false;
            if (!resource.spend(this.cost.amount)) return false;

            if (this.target.type === 'resource') {
                const targetResource = game.resources.get(this.target.name);
                if (targetResource) {
                    if (this.effectType === 'multiply') {
                        targetResource.multiplier *= this.effectValue;
                    } else if (this.effectType === 'add') {
                        targetResource.multiplier += this.effectValue;
                    }
                }
            } else if (this.target.type === 'all_resources') {
                game.resources.forEach((targetResource) => {
                    if (this.effectType === 'multiply') {
                        targetResource.multiplier *= this.effectValue;
                    } else if (this.effectType === 'add') {
                        targetResource.multiplier += this.effectValue;
                    }
                });
            } else if (this.target.type === 'worker') {
                const worker = game.workers.find(w => w.name === this.target.name);
                if (worker) {
                    if (this.effectType === 'multiply') {
                        worker.multiplier *= this.effectValue;
                    } else if (this.effectType === 'add') {
                        worker.multiplier += this.effectValue;
                    }
                }
            }

            this.purchased = true;
            return true;
        }

        reset() {
            this.purchased = false;
        }

        serialize() {
            return {
                name: this.name,
                purchased: this.purchased
            };
        }

        hydrate(payload) {
            this.purchased = payload.purchased ?? this.purchased;
        }
    }

    class PrestigeManager {
        constructor(game, powerPerPoint = 0.05) {
            this.game = game;
            this.powerPerPoint = powerPerPoint;
        }

        get potentialPoints() {
            const total = this.game.state.totals.totalGenerated;
            if (total <= 0) return 0;
            return Math.floor(Math.log10(total));
        }

        get globalMultiplier() {
            return 1 + this.game.state.prestige.owned * this.powerPerPoint;
        }

        canPrestige() {
            return this.potentialPoints > 0;
        }

        execute() {
            if (!this.canPrestige()) return 0;
            const gained = this.potentialPoints;
            this.game.state.prestige.owned += gained;
            this.game.state.prestige.lifetime += gained;
            this.game.resetProgress();
            return gained;
        }
    }

    class UIManager {
        constructor(game) {
            this.game = game;
            this.elements = {
                resources: document.getElementById('resourceList'),
                workers: document.getElementById('workerList'),
                upgrades: document.getElementById('upgradeList'),
                prestigeInfo: document.getElementById('prestigeInfo'),
                prestigeButton: document.getElementById('prestigeButton'),
                clickButton: document.getElementById('clickButton'),
                manualGain: document.getElementById('manualGain'),
                saveStatus: document.getElementById('saveStatus'),
                manualSave: document.getElementById('manualSave')
            };

            this.bindEvents();
            this.renderAll();
        }

        bindEvents() {
            this.elements.clickButton?.addEventListener('click', () => {
                this.game.handleManualClick();
            });

            this.elements.manualSave?.addEventListener('click', () => {
                this.game.saveState(true);
            });

            this.elements.prestigeButton?.addEventListener('click', () => {
                const gained = this.game.prestigeManager.execute();
                if (gained) {
                    this.game.flashMessage(`Získáno ${gained} prestižních bodů!`);
                    this.game.saveState(true);
                    this.renderAll();
                }
            });
        }

        renderAll() {
            this.renderResources();
            this.renderWorkers();
            this.renderUpgrades();
            this.renderPrestige();
        }

        renderResources() {
            if (!this.elements.resources) return;
            this.elements.resources.innerHTML = '';
            this.game.resources.forEach((resource) => {
                const row = document.createElement('li');
                row.className = 'resource-row';
                row.innerHTML = `
                    <strong>${resource.name}</strong>
                    <div>
                        <span>${this.game.formatNumber(resource.amount)}</span>
                        <span class="tag">${this.game.formatNumber(resource.multiplier)}×</span>
                    </div>
                `;
                this.elements.resources.appendChild(row);
            });

            if (this.elements.manualGain) {
                const base = this.game.config.manualClickBase;
                const primary = this.game.resources.get(this.game.config.primaryResource);
                const gain = base * primary.multiplier * this.game.prestigeManager.globalMultiplier;
                this.elements.manualGain.textContent = `+${this.game.formatNumber(gain)} / klik`;
            }
        }

        renderWorkers() {
            if (!this.elements.workers) return;
            this.elements.workers.innerHTML = '';
            this.game.workers
                .filter(worker => worker.isUnlocked(this.game) || worker.amountOwned > 0)
                .forEach((worker) => {
                    const card = document.createElement('article');
                    card.className = 'card';

                    const canAfford = worker.canAfford(this.game);
                    const unlocked = worker.isUnlocked(this.game);
                    if (canAfford) card.classList.add('available');
                    if (!unlocked) card.classList.add('locked');

                    const button = document.createElement('button');
                    button.textContent = unlocked ? 'Najmout' : 'Zamčeno';
                    button.className = 'primary-button';
                    button.disabled = !canAfford || !unlocked;
                    button.addEventListener('click', () => {
                        if (this.game.purchaseWorker(worker.name)) {
                            this.renderAll();
                        }
                    });

                    card.innerHTML = `
                        <h3>${worker.name}</h3>
                        <p>${worker.description}</p>
                        <p>Výroba: ${this.game.formatNumber(worker.baseProduction * worker.multiplier)} / s</p>
                        <footer>
                            <span>${worker.amountOwned}×</span>
                            <span>${this.game.formatNumber(worker.currentCost())} ${worker.costResource}</span>
                        </footer>
                    `;

                    card.appendChild(button);
                    this.elements.workers.appendChild(card);
                });
        }

        renderUpgrades() {
            if (!this.elements.upgrades) return;
            this.elements.upgrades.innerHTML = '';
            this.game.upgrades
                .filter((upgrade) => !upgrade.purchased || upgrade.isVisible(this.game))
                .forEach((upgrade) => {
                    if (!upgrade.isVisible(this.game)) return;

                    const card = document.createElement('article');
                    card.className = 'card';
                    if (upgrade.purchased) card.classList.add('locked');
                    if (upgrade.isAffordable(this.game) && !upgrade.purchased) card.classList.add('available');

                    const button = document.createElement('button');
                    button.textContent = upgrade.purchased ? 'Koupeno' : 'Koupit';
                    button.className = 'primary-button';
                    button.disabled = upgrade.purchased || !upgrade.isAffordable(this.game);
                    button.addEventListener('click', () => {
                        if (this.game.purchaseUpgrade(upgrade.name)) {
                            this.renderAll();
                        }
                    });

                    card.innerHTML = `
                        <h3>${upgrade.name}</h3>
                        <p>${upgrade.description}</p>
                        <footer>
                            <span>${this.game.formatNumber(upgrade.cost.amount)} ${upgrade.cost.resource}</span>
                            <span>${upgrade.effectType === 'multiply' ? `×${upgrade.effectValue}` : `+${upgrade.effectValue}`}</span>
                        </footer>
                    `;
                    card.appendChild(button);
                    this.elements.upgrades.appendChild(card);
                });
        }

        renderPrestige() {
            const { prestigeInfo, prestigeButton } = this.elements;
            if (!prestigeInfo) return;
            prestigeInfo.querySelector('[data-field="totalGenerated"]').textContent =
                this.game.formatNumber(this.game.state.totals.totalGenerated);
            prestigeInfo.querySelector('[data-field="potentialPrestige"]').textContent =
                this.game.prestigeManager.potentialPoints;
            prestigeInfo.querySelector('[data-field="ownedPrestige"]').textContent =
                this.game.formatNumber(this.game.state.prestige.owned);

            if (prestigeButton) {
                prestigeButton.disabled = !this.game.prestigeManager.canPrestige();
            }
        }

        setSaveStatus(message) {
            if (this.elements.saveStatus) {
                this.elements.saveStatus.textContent = message;
            }
        }
    }

    class GameEngine {
        constructor(config) {
            this.config = config;
            this.storage = new StorageManager(STORAGE_KEY);
            this.resources = new Map();
            this.workers = [];
            this.upgrades = [];
            this.state = {
                totals: {
                    totalGenerated: 0
                },
                prestige: {
                    owned: 0,
                    lifetime: 0
                }
            };

            this.setupFromConfig();
            this.prestigeManager = new PrestigeManager(this, config.prestigePowerPerPoint);
            this.ui = new UIManager(this);
            this.loadState();
            this.startLoops();
        }

        setupFromConfig() {
            this.resources.clear();
            this.config.resources.forEach((res) => {
                this.resources.set(res.name, new Resource(res));
            });
            this.workers = this.config.workers.map((worker) => new Worker(worker));
            this.upgrades = this.config.upgrades.map((upgrade) => new Upgrade(upgrade));
        }

        loadState() {
            const saved = this.storage.load();
            if (!saved) {
                this.ui.setSaveStatus('Nová session');
                return;
            }

            saved.resources?.forEach((payload) => {
                const resource = this.resources.get(payload.name);
                if (resource) resource.hydrate(payload);
            });

            saved.workers?.forEach((payload) => {
                const worker = this.workers.find((w) => w.name === payload.name);
                if (worker) worker.hydrate(payload);
            });

            saved.upgrades?.forEach((payload) => {
                const upgrade = this.upgrades.find((u) => u.name === payload.name);
                if (upgrade) upgrade.hydrate(payload);
            });

            this.state = {
                totals: {
                    totalGenerated: saved.totals?.totalGenerated ?? 0
                },
                prestige: {
                    owned: saved.prestige?.owned ?? 0,
                    lifetime: saved.prestige?.lifetime ?? (saved.prestige?.owned ?? 0)
                }
            };

            this.ui.setSaveStatus('Stav načten');
            this.ui.renderAll();
        }

        saveState(manual = false) {
            const payload = {
                resources: Array.from(this.resources.values()).map((res) => res.serialize()),
                workers: this.workers.map((worker) => worker.serialize()),
                upgrades: this.upgrades.map((upgrade) => upgrade.serialize()),
                totals: this.state.totals,
                prestige: this.state.prestige,
                savedAt: Date.now()
            };
            this.storage.save(payload);
            this.ui.setSaveStatus(manual ? 'Uloženo manuálně' : 'Auto-uloženo');
        }

        startLoops() {
            let last = performance.now();
            const tick = (now) => {
                const delta = (now - last) / 1000;
                last = now;
                this.update(delta);
                requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
            setInterval(() => this.saveState(false), 10000);
        }

        update(delta) {
            this.workers.forEach((worker) => {
                if (!worker.amountOwned) return;
                const resource = this.resources.get(worker.produces);
                if (!resource) return;
                const produced = worker.amountOwned * worker.baseProduction * worker.multiplier * delta * this.prestigeManager.globalMultiplier * resource.multiplier;
                resource.add(produced);
                this.state.totals.totalGenerated += produced;
            });
            this.ui.renderAll();
        }

        handleManualClick() {
            const resource = this.resources.get(this.config.primaryResource);
            if (!resource) return;
            const gain = this.config.manualClickBase * resource.multiplier * this.prestigeManager.globalMultiplier;
            resource.add(gain);
            this.state.totals.totalGenerated += gain;
            this.ui.renderResources();
            this.ui.renderPrestige();
        }

        purchaseWorker(name) {
            const worker = this.workers.find((w) => w.name === name);
            if (!worker) return false;
            if (!worker.isUnlocked(this)) return false;
            if (!worker.buy(this)) return false;
            this.ui.renderWorkers();
            return true;
        }

        purchaseUpgrade(name) {
            const upgrade = this.upgrades.find((u) => u.name === name);
            if (!upgrade || upgrade.purchased) return false;
            if (!upgrade.apply(this)) return false;
            this.ui.renderUpgrades();
            this.ui.renderResources();
            return true;
        }

        resetProgress() {
            this.resources.forEach((resource) => resource.reset());
            this.workers.forEach((worker) => worker.reset());
            this.upgrades.forEach((upgrade) => upgrade.reset());
            this.state.totals.totalGenerated = 0;
            this.saveState(true);
            this.ui.renderAll();
        }

        flashMessage(message) {
            this.ui.setSaveStatus(message);
            setTimeout(() => this.ui.setSaveStatus(''), 3000);
        }

        formatNumber(value) {
            if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
            if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
            if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
            return value.toFixed(2);
        }
    }

    const gameConfig = {
        primaryResource: 'Kolektivní Vůle',
        manualClickBase: 1,
        prestigePowerPerPoint: 0.08,
        resources: [
            { name: 'Kolektivní Vůle', amount: 0, baseProduction: 0, multiplier: 1 },
            { name: 'Agro Poukázky', amount: 0, baseProduction: 0, multiplier: 1.2 },
            { name: 'Průmyslové Kredity', amount: 0, baseProduction: 0, multiplier: 1 }
        ],
        workers: [
            {
                name: 'Uliční agitátor',
                description: 'Sbírá podpisy a zvyšuje základní produkci ideologie.',
                cost: { resource: 'Kolektivní Vůle', amount: 10 },
                baseProduction: 0.5,
                amountOwned: 0,
                costScaling: 1.15,
                produces: 'Kolektivní Vůle',
                unlockRequirement: null
            },
            {
                name: 'Agrární kooperátor',
                description: 'Automatizuje zásobování záhonů, tím odemyká Agro poukázky.',
                cost: { resource: 'Kolektivní Vůle', amount: 60 },
                baseProduction: 0.8,
                amountOwned: 0,
                costScaling: 1.17,
                produces: 'Agro Poukázky',
                unlockRequirement: { resource: 'Kolektivní Vůle', amount: 50 }
            },
            {
                name: 'Panelový inženýr',
                description: 'Přepočítává potrubí a vyrábí průmyslové kredity.',
                cost: { resource: 'Agro Poukázky', amount: 120 },
                baseProduction: 1.5,
                amountOwned: 0,
                costScaling: 1.2,
                produces: 'Průmyslové Kredity',
                unlockRequirement: { totalGenerated: 500 }
            }
        ],
        upgrades: [
            {
                name: 'Duplikát letáků',
                description: 'Zdvojnásobí multiplikátor pro Kolektivní Vůli.',
                cost: { resource: 'Kolektivní Vůle', amount: 80 },
                target: { type: 'resource', name: 'Kolektivní Vůle' },
                effectType: 'multiply',
                effectValue: 2,
                unlockRequirement: null
            },
            {
                name: 'Kompostové pásy',
                description: 'Agrární kooperátoři produkují o 50 % více.',
                cost: { resource: 'Agro Poukázky', amount: 150 },
                target: { type: 'worker', name: 'Agrární kooperátor' },
                effectType: 'multiply',
                effectValue: 1.5,
                unlockRequirement: { resource: { name: 'Agro Poukázky', generated: 100 } }
            },
            {
                name: 'Tovární rozhlas',
                description: 'Všechny resources dostanou +0.25 multiplikátoru.',
                cost: { resource: 'Průmyslové Kredity', amount: 200 },
                target: { type: 'all_resources' },
                effectType: 'add',
                effectValue: 0.25,
                unlockRequirement: { totalGenerated: 1500 }
            }
        ]
    };

    document.addEventListener('DOMContentLoaded', () => {
        window.lugogIdleEngine = new GameEngine(gameConfig);
    });
})();

