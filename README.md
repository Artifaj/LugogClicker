# 🌲 Lugog Clicker 🌲

Moderní incremental/idle hra inspirovaná Cookie Clicker, ale s vlastním příběhem a mechanikami.

## 🎮 O hře

Lugog Clicker je webová incremental hra, kde začínáš klikáním a postupně odemykáš automatické generátory a upgrady. Hra obsahuje:

- **5 různých měn**: Gooncoiny (hlavní měna), Dřevo, Voda, Oheň a Země
- **Systém upgradů**: Zvyšuj sílu kliknutí a odemykej automatické generátory
- **Síň slávy**: Soutež s ostatními hráči o nejvyšší skóre
- **LORE**: Příběh o říši Lugog a obnovení magie elementů
- **Login systém**: Uložení pokroku a bezpečné přihlášení
- **Bojový hub**: PvP souboje mezi hráči a kampaň proti bossům s unikátními dropy
- **CS:GO styl bedny**: Nový opening hub s vizuální ruletou a loot tabulkou jako v CSGO
- **Inventář a item ekonomika**: Kompletní inventář se záznamem původu, raritou a dynamickou tržní hodnotou včetně možnosti předměty prodávat zpět za Gooncoiny.

## 🚀 Instalace

1. **Nainstaluj Python 3.8+** (pokud ještě nemáš)

2. **Nainstaluj závislosti**:
```bash
pip install -r requirements.txt
```

3. **Spusť aplikaci**:
```bash
python app.py
```

4. **Otevři prohlížeč** a jdi na `http://localhost:5000`

## 🛡️ Admin panel pro testování

- Výchozí admin účet: **uživatel `Ota`, heslo `Ota`** (lze změnit přes proměnné `LUGOG_ADMIN_USER` a `LUGOG_ADMIN_PASS`).
- Po přihlášení klikni na tlačítko **Admin panel** v horní liště (nebo navštiv `/admin`) a uvidíš přehled hráčů, statistiky a přepínač viditelnosti v síni slávy.
- Admin účet je automaticky **skrytý z leaderboardu**, takže můžeš testovat bez ovlivnění žebříčku.
- V Admin panelu můžeš kdykoliv skrýt nebo odkrýt libovolného hráče z výsledkové tabulky.

## 📦 Nasazení na web

Pro nasazení na produkční server (např. Heroku, Railway, nebo vlastní VPS):

1. **Nastav environment variable** pro SECRET_KEY:
```bash
export SECRET_KEY="tvoje-super-tajny-klic-produkce"
```

2. **Uprav app.py** - změň debug režim:
```python
app.run(debug=False, host='0.0.0.0', port=5000)
```

3. **Použij produkční WSGI server** (např. Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 🎯 Herní mechaniky

### Měny
- **💰 Gooncoiny**: Hlavní měna, získáváš klikáním a auto-generátory
- **🪵 Dřevo**: Potřebné pro pokročilejší upgrady
- **💧 Voda**: Sběrá se automaticky sběračem vody
- **🔥 Oheň**: Energie z vulkánů Lugog
- **🌍 Země**: Krystaly z hlubin země
- **📈 Inflace**: Globální ekonomika hlídá množství Gooncoinů v oběhu a podle toho upravuje ceny i směnné kurzy.
- **💱 Měnový trh**: Prezidentka Gooncoinu otevřela burzu, kde můžeš obchodovat Astma, Pohárky, Mrkev a Uzené za Gooncoiny podle dynamických kurzů.

### Vzácné materiály & kampaň
- **Mrkvový Totem, Kikiho Oko, Ampule Václava, Rózin Trn, Jitčin Manifest**
- Získáš je pouze v nové kampaňové linii proti bossům jako „Uezen s Mrkví“, „Kiki“, „Václav Voda“, „Róza“ a „Jitka“.
- Každý boss přináší unikátní drop i Gooncoiny – materiály pak používáš pro speciální craftění a budoucí eventy.
- Součástí hubu je i PvP žebříček s ratingem, výhrami / prohrami a záznamem posledních soubojů.

### Upgrady
- **Síla kliku**: Zvyšuje hodnotu každého kliknutí
- **Auto-generátory**: Automaticky generují zdroje každou sekundu
- Ceny upgradů rostou exponenciálně s každou úrovní

## 🧠 Adventure Communist Blueprint

Chci vytvořit jednoduchou idle/adventure-communist styl hru pro web. Potřebuju systém resources, workers, upgrades a prestige. Vytvoř mi modulární architekturu:

- `Resource = {name, amount, baseProduction, multiplier}`
- `Worker = {name, cost, baseProduction, amountOwned, costScaling}`
- `Upgrade = {name, cost, target, effectType (‘multiply’/’add’), effectValue}`
- `Prestige = výpočet podle log10(totalResourcesGenerated)`

Mechaniky:

- klik = manuální přidání resource
- workers generují resource za sekundu
- upgrades zvyšují multipliers
- ceny workerů rostou exponenciálně (např. 1.15^amountOwned)
- UI zobrazí vždy jen dostupné a relevantní věci
- uložení do localStorage

Základní design, který dává “Adventure Communist” feeling:

- `Potatoes` → `Field Collectives`
- `Steel` → `State Miners`
- `Tractors` → `Factory Engineers`
- `Propaganda` → `Cultural Officers`
- `Soldiers` → `Conscription Offices`
- `Research` → `Academy Scientists`
- `Satellites` → `Space Bureaucrats`

Upgrade vrstvy:

1. Lokální (např. `Sharper Shovels`, `Reinforced Helmets`)
2. Větvové (`Five-Year Farm Plan`, `Industrial Overdrive`, `Unified Command`)
3. Globální (`Central Committee Directives`, `Logistics AI`, `People’s Spirit`)

Prestige:

- `prestigeReset()` smaže current progress a udělí `Collective Influence = floor(log10(totalResourcesGenerated))`
- Každý bod dává +4 % global production a -0.5 % worker cost scaling (stackuje se)

### Síň slávy
Top 10 hráčů podle celkových Gooncoinů se zobrazuje v reálném čase.

## 🛠️ Technologie

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Databáze**: SQLite
- **Autentifikace**: Session-based s hashovanými hesly

## 📝 Struktura projektu

```
LugogClicker/
├── app.py                 # Hlavní Flask aplikace
├── requirements.txt       # Python závislosti
├── README.md             # Tento soubor
├── templates/            # HTML šablony
│   ├── login.html
│   └── game.html
├── static/               # Statické soubory
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── login.js
│       └── game.js
└── lugog_clicker.db      # SQLite databáze (vytvoří se automaticky)
```

## 🔒 Bezpečnost

- Hesla jsou hashována pomocí Werkzeug
- Session management pomocí Flask-Session
- SQL injection ochrana pomocí parametrizovaných dotazů

## 🎨 Vlastní úpravy

Můžeš snadno upravit:
- **Ceny upgradů**: V `app.py` v sekci `upgrade_costs`
- **Generační rychlosti**: V `app.py` v funkci `auto_generate`
- **LORE texty**: V `templates/game.html` a `templates/login.html`
- **Vzhled**: V `static/css/style.css`

## 📄 Licence

Vytvořeno pro zábavu! Můžeš použít a upravit jak chceš.

## 🐛 Hlášení chyb

Pokud najdeš nějaké chyby nebo máš návrhy na vylepšení, vytvoř issue nebo pull request!

---

**Užij si hru a dobýj říši Lugog! 🌲✨**

