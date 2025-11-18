from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from datetime import datetime, timedelta
import os
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
Session(app)

BASE_INFLATION_RATE = 0.02
MIN_INFLATION_RATE = 0.01
MAX_INFLATION_RATE = 0.45
ECONOMY_UPDATE_INTERVAL = 10  # seconds
INFLATION_MULTIPLIER_FACTOR = 4
MARKET_SPREAD = 0.12
MARKET_MIN_MULTIPLIER = 0.4
MARKET_MAX_MULTIPLIER = 3.5
MARKET_SENSITIVITY = 0.04
MARKET_REVERSION_RATE = 0.08
MARKET_REVERSION_WINDOW = 900  # seconds
MARKET_FLOW_HALFLIFE = 240  # seconds
MARKET_RANDOM_SWING = 0.01
MARKET_DEFAULT_LIQUIDITY = 250

ITEM_VALUE_FACTORS = {
    'gooncoins': 1.0,
    'astma': 42,
    'poharky': 38,
    'mrkev': 32,
    'uzené': 55
}
RARITY_VALUE_MULTIPLIERS = {
    'common': 1.0,
    'rare': 1.25,
    'epic': 1.65,
    'legendary': 2.4,
    'unique': 3.2
}
ITEM_MARKET_MIN_MULTIPLIER = 0.35
ITEM_MARKET_MAX_MULTIPLIER = 4.5
ITEM_MARKET_SENSITIVITY = 0.02
ITEM_MARKET_REVERSION_RATE = 0.06
ITEM_MARKET_REVERSION_WINDOW = 2400  # seconds
ITEM_MARKET_FLOW_HALFLIFE = 900  # seconds
ITEM_MARKET_RANDOM_SWING = 0.012
ITEM_MARKET_SELL_TAX = 0.88
SECONDARY_RESOURCES = ['logs', 'planks', 'grain', 'flour', 'bread', 'fish']
RESOURCE_FIELDS = ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené', *SECONDARY_RESOURCES]
RESOURCE_FALLBACKS = {
    'astma': 'wood',
    'poharky': 'water',
    'mrkev': 'fire',
    'uzené': 'earth'
}

BASE_EXCHANGE_RATES = {
    'astma': 35,
    'poharky': 80,
    'mrkev': 140,
    'uzené': 220,
    'logs': 40,
    'planks': 120,
    'grain': 55,
    'flour': 110,
    'bread': 240,
    'fish': 160
}
TRADEABLE_CURRENCIES = ['astma', 'poharky', 'mrkev', 'uzené', *SECONDARY_RESOURCES]
MARKET_LIQUIDITY = {
    'astma': 420,
    'poharky': 340,
    'mrkev': 260,
    'uzené': 190,
    'logs': 320,
    'planks': 260,
    'grain': 380,
    'flour': 260,
    'bread': 180,
    'fish': 210
}

RARE_MATERIAL_DEFS = {
    'mrkvovy_totem': {
        'name': 'Mrkvový Totem',
        'icon': '🥕',
        'description': 'Totem vyřezaný z mrkvového jádra, vibruje, když se blíží Uezen.'
    },
    'kiki_oko': {
        'name': 'Kikiho Oko',
        'icon': '👁️',
        'description': 'Zmrzlý slzný kanálek Kiki dokáže odhalit slabiny protivníků.'
    },
    'vaclava_ampule': {
        'name': 'Ampule Václava Vody',
        'icon': '💧',
        'description': 'Ampule naplněná proudem z vodního žilního systému Václava Vody.'
    },
    'roza_trn': {
        'name': 'Rózin Trn',
        'icon': '🌹',
        'description': 'Ostrý trn, který dokáže probudit staré rituály v Chrámu.'
    },
    'jitka_manifest': {
        'name': 'Manifest Jitky',
        'icon': '📜',
        'description': 'Svitky Jitčina hnutí, které otevírají tajné panely ve 244.'
    }
}

RESOURCE_LABELS_BACKEND = {
    'gooncoins': 'Gooncoiny',
    'astma': 'Astma',
    'poharky': 'Pohárky',
    'mrkev': 'Mrkev',
    'uzené': 'Uzené'
}

RESOURCE_ALIAS_MAP = {
    'astma': ['astma', 'wood'],
    'poharky': ['poharky', 'water'],
    'mrkev': ['mrkev', 'fire'],
    'uzené': ['uzené', 'earth']
}

def hydrate_state_resources(row):
    if not row:
        return {key: 0 for key in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    resources = {
        'gooncoins': float(row['gooncoins']) if row['gooncoins'] is not None else 0
    }
    for key, aliases in RESOURCE_ALIAS_MAP.items():
        value = 0
        for alias in aliases:
            if alias in row.keys() and row[alias] is not None:
                value = row[alias]
                break
        resources[key] = float(value)
    return resources

def persist_state_resources(cursor, user_id, balances):
    cursor.execute('''UPDATE game_state 
                      SET gooncoins = ?, astma = ?, poharky = ?, mrkev = ?, uzené = ?, last_update = CURRENT_TIMESTAMP
                      WHERE user_id = ?''',
                   (balances['gooncoins'], balances['astma'], balances['poharky'],
                    balances['mrkev'], balances['uzené'], user_id))

CAMPAIGN_MONSTERS = [
    {
        'id': 'uezen_mrkvi',
        'name': 'Uezen s Mrkví',
        'tier': 1,
        'description': 'Zmutovaný kominík, který žije na mrkvových výparech.',
        'stats': {'attack': 18, 'defense': 10, 'hp': 140, 'luck': 0.9},
        'rewards': {'gooncoins': 200, 'rare_materials': {'mrkvovy_totem': 1}}
    },
    {
        'id': 'kiki',
        'name': 'Kiki',
        'tier': 2,
        'description': 'Kiki sbírá všední sny a mění je v ostré projektily.',
        'stats': {'attack': 26, 'defense': 18, 'hp': 220, 'luck': 1.2},
        'rewards': {'gooncoins': 320, 'rare_materials': {'kiki_oko': 1}}
    },
    {
        'id': 'vaclav_voda',
        'name': 'Václav Voda',
        'tier': 3,
        'description': 'Vodní architekt, který dokáže zvednout celé patro paneláku vodním sloupcem.',
        'stats': {'attack': 32, 'defense': 28, 'hp': 320, 'luck': 1.0},
        'rewards': {'gooncoins': 450, 'rare_materials': {'vaclava_ampule': 1}}
    },
    {
        'id': 'roza',
        'name': 'Róza',
        'tier': 4,
        'description': 'Královna komunitních záhonů, jejíž trny rostou z betonu.',
        'stats': {'attack': 38, 'defense': 34, 'hp': 420, 'luck': 1.3},
        'rewards': {'gooncoins': 600, 'rare_materials': {'roza_trn': 1}}
    },
    {
        'id': 'jitka',
        'name': 'Jitka',
        'tier': 5,
        'description': 'Poslední tribun lidu, která bojuje slovem i blýskavým manifestem.',
        'stats': {'attack': 46, 'defense': 40, 'hp': 520, 'luck': 1.5},
        'rewards': {'gooncoins': 850, 'rare_materials': {'jitka_manifest': 1}}
    }
]

TEMPLE_DEFEAT_COOLDOWN = 600  # seconds

TEMPLE_BLESSINGS = {
    'wrath': {
        'name': 'Vztek Radiátorů',
        'description': 'Dočasně zvyšuje tvůj útok v PvP i kampani.',
        'cost': {'favor': 25, 'poharky': 15, 'gooncoins': 400},
        'bonus': {'attack': 12},
        'duration': 1800
    },
    'bulwark': {
        'name': 'Štít Balkónů',
        'description': 'Chrám generuje ochranné pole, které zvyšuje obranu i HP.',
        'cost': {'favor': 22, 'uzené': 8, 'gooncoins': 350},
        'bonus': {'defense': 14, 'hp': 120},
        'duration': 1800
    },
    'omen': {
        'name': 'Šepot Neonů',
        'description': 'Štěstí chrámu posiluje kritické zásahy a úhyby.',
        'cost': {'favor': 20, 'mrkev': 14, 'gooncoins': 300},
        'bonus': {'luck': 1.1},
        'duration': 1800
    }
}

TEMPLE_ENEMIES = {
    'smoke_disciple': {
        'name': 'Učenec Dýmu',
        'description': 'Stínová postava, která používá inhalátory jako granáty.',
        'stats': {'attack': 22, 'defense': 14, 'hp': 190, 'luck': 0.9},
        'favor': 3,
        'gooncoins': 120
    },
    'bronze_lugog': {
        'name': 'Bronzový Lugog',
        'description': 'Mechanická replika, která se učí z tvých kliků.',
        'stats': {'attack': 26, 'defense': 16, 'hp': 210, 'luck': 1.0},
        'favor': 3,
        'gooncoins': 150
    },
    'coil_adept': {
        'name': 'Adepta Cívky',
        'description': 'Strážce kabeláže, která živí celý chrám.',
        'stats': {'attack': 32, 'defense': 20, 'hp': 260, 'luck': 1.1},
        'favor': 4,
        'gooncoins': 190
    },
    'panel_specter': {
        'name': 'Specter Panelu',
        'description': 'Zhmotněná paměť jedné z balkonových stráží.',
        'stats': {'attack': 34, 'defense': 22, 'hp': 280, 'luck': 1.25},
        'favor': 4,
        'gooncoins': 210
    },
    'signal_prophet': {
        'name': 'Prorok Signálu',
        'description': 'Legendy říkají, že slyší všechny kliky zároveň.',
        'stats': {'attack': 40, 'defense': 28, 'hp': 320, 'luck': 1.4},
        'favor': 5,
        'gooncoins': 260
    }
}

TEMPLE_ROOMS = [
    {
        'id': 'atrium',
        'name': 'Atrium Výparů',
        'description': 'Vstupní hala chrámu vibruje starými neonky a dýmem.',
        'required_kills': 3,
        'enemy_pool': ['smoke_disciple', 'bronze_lugog'],
        'boss': {
            'id': 'echo_guardian',
            'name': 'Echa Strážce',
            'stats': {'attack': 36, 'defense': 24, 'hp': 340, 'luck': 1.2},
            'rewards': {
                'gooncoins': 500,
                'favor': 12,
                'rare_materials': {'mrkvovy_totem': 1}
            }
        },
        'unlock_after': None
    },
    {
        'id': 'relikviarium',
        'name': 'Relikviárium 244',
        'description': 'Panely jsou pokryté plakáty a každý skrývá relikvii.',
        'required_kills': 4,
        'enemy_pool': ['coil_adept', 'panel_specter'],
        'boss': {
            'id': 'archivist',
            'name': 'Archivní Správce',
            'stats': {'attack': 44, 'defense': 30, 'hp': 400, 'luck': 1.4},
            'rewards': {
                'gooncoins': 900,
                'favor': 20,
                'rare_materials': {'kiki_oko': 1}
            }
        },
        'unlock_after': 'atrium'
    },
    {
        'id': 'svatyne',
        'name': 'Svatyně Neonů',
        'description': 'Srdce chrámu, kde rezonuje legenda Lugogu.',
        'required_kills': 5,
        'enemy_pool': ['panel_specter', 'signal_prophet', 'bronze_lugog'],
        'boss': {
            'id': 'neon_prophet',
            'name': 'Průvodce Neonů',
            'stats': {'attack': 58, 'defense': 38, 'hp': 480, 'luck': 1.7},
            'rewards': {
                'gooncoins': 1500,
                'favor': 35,
                'rare_materials': {'roza_trn': 1, 'jitka_manifest': 1}
            }
        },
        'unlock_after': 'relikviarium'
    }
]

PVP_BASE_REWARD = 75
MAX_COMBAT_ROUNDS = 8

# Database initialization
def init_db():
    conn = sqlite3.connect('lugog_clicker.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Game state table
    c.execute('''CREATE TABLE IF NOT EXISTS game_state
                 (user_id INTEGER PRIMARY KEY,
                  gooncoins REAL DEFAULT 0,
                  astma REAL DEFAULT 0,
                  poharky REAL DEFAULT 0,
                  mrkev REAL DEFAULT 0,
                  uzené REAL DEFAULT 0,
                  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  total_clicks INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Migration: rename old columns if they exist
    try:
        c.execute('ALTER TABLE game_state ADD COLUMN astma REAL DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE game_state ADD COLUMN poharky REAL DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE game_state ADD COLUMN mrkev REAL DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE game_state ADD COLUMN uzené REAL DEFAULT 0')
    except:
        pass
    
    # Upgrades table
    c.execute('''CREATE TABLE IF NOT EXISTS upgrades
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  upgrade_type TEXT NOT NULL,
                  level INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Equipment table (+ acquisition metadata)
    c.execute('''CREATE TABLE IF NOT EXISTS equipment
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  equipment_slot TEXT NOT NULL,
                  equipment_id TEXT NOT NULL,
                  equipped INTEGER DEFAULT 0,
                  acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  acquired_via TEXT,
                  acquisition_note TEXT,
                  acquisition_payload TEXT,
                  last_valuation REAL DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    for column, ddl in [
        ('acquired_at', "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ('acquired_via', "TEXT"),
        ('acquisition_note', "TEXT"),
        ('acquisition_payload', "TEXT"),
        ('last_valuation', "REAL DEFAULT 0")
    ]:
        try:
            c.execute(f'ALTER TABLE equipment ADD COLUMN {column} {ddl}')
        except sqlite3.OperationalError:
            pass
    try:
        c.execute("UPDATE equipment SET acquired_at = COALESCE(acquired_at, CURRENT_TIMESTAMP)")
    except sqlite3.OperationalError:
        pass
    
    # Story progress table
    c.execute('''CREATE TABLE IF NOT EXISTS story_progress
                 (user_id INTEGER PRIMARY KEY,
                  current_chapter INTEGER DEFAULT 1,
                  completed_quests TEXT DEFAULT '[]',
                  unlocked_buildings TEXT DEFAULT '[]',
                  unlocked_currencies TEXT DEFAULT '["gooncoins"]',
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Buildings table
    c.execute('''CREATE TABLE IF NOT EXISTS buildings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  building_type TEXT NOT NULL,
                  level INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Rare materials table
    columns_sql = ', '.join([f"{key} INTEGER DEFAULT 0" for key in RARE_MATERIAL_DEFS.keys()])
    c.execute(f'''CREATE TABLE IF NOT EXISTS rare_materials
                 (user_id INTEGER PRIMARY KEY,
                  {columns_sql},
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS case_openings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  case_id TEXT NOT NULL,
                  reward_type TEXT NOT NULL,
                  reward_id TEXT,
                  reward_label TEXT,
                  rarity TEXT,
                  amount REAL DEFAULT 0,
                  metadata TEXT DEFAULT '{}',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Combat profiles (PvP + campaign progression)
    c.execute('''CREATE TABLE IF NOT EXISTS combat_profiles
                 (user_id INTEGER PRIMARY KEY,
                  rating REAL DEFAULT 1000,
                  wins INTEGER DEFAULT 0,
                  losses INTEGER DEFAULT 0,
                  campaign_stage INTEGER DEFAULT 0,
                  defeated_monsters TEXT DEFAULT '[]',
                  last_battle TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Combat logs for recent battles
    c.execute('''CREATE TABLE IF NOT EXISTS combat_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  attacker_id INTEGER,
                  defender_id INTEGER,
                  mode TEXT NOT NULL,
                  winner_id INTEGER,
                  summary TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (attacker_id) REFERENCES users(id),
                  FOREIGN KEY (defender_id) REFERENCES users(id))''')
    
    # Temple progression state
    c.execute('''CREATE TABLE IF NOT EXISTS temple_state
                 (user_id INTEGER PRIMARY KEY,
                  progress TEXT DEFAULT '{}',
                  favor REAL DEFAULT 0,
                  active_blessing TEXT,
                  blessing_expires_at TEXT,
                  cooldown_until TEXT,
                  last_room TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Economy state table (global metrics)
    c.execute(f'''CREATE TABLE IF NOT EXISTS economy_state
                 (id INTEGER PRIMARY KEY CHECK (id = 1),
                  gooncoin_supply REAL DEFAULT 0,
                  inflation_rate REAL DEFAULT {BASE_INFLATION_RATE},
                  last_adjustment TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''INSERT OR IGNORE INTO economy_state (id, gooncoin_supply, inflation_rate, last_adjustment)
                 VALUES (1, 0, ?, CURRENT_TIMESTAMP)''', (BASE_INFLATION_RATE,))
    
    # Market state table
    c.execute('''CREATE TABLE IF NOT EXISTS market_state
                 (currency TEXT PRIMARY KEY,
                  price_multiplier REAL DEFAULT 1.0,
                  net_flow REAL DEFAULT 0,
                  last_update TEXT DEFAULT CURRENT_TIMESTAMP)''')
    now_iso = datetime.utcnow().isoformat()
    for currency in TRADEABLE_CURRENCIES:
        c.execute('''INSERT OR IGNORE INTO market_state (currency, price_multiplier, net_flow, last_update)
                     VALUES (?, 1.0, 0, ?)''', (currency, now_iso))
    
    # Item market state table (global economy for items)
    c.execute('''CREATE TABLE IF NOT EXISTS item_market_state
                 (item_id TEXT PRIMARY KEY,
                  price_multiplier REAL DEFAULT 1.0,
                  net_flow REAL DEFAULT 0,
                  base_value REAL DEFAULT 0,
                  last_price REAL DEFAULT 0,
                  last_trend TEXT DEFAULT 'flat',
                  total_minted INTEGER DEFAULT 0,
                  total_burned INTEGER DEFAULT 0,
                  last_update TEXT DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('lugog_clicker.db')
    conn.row_factory = sqlite3.Row
    return conn

def ensure_economy_row(cursor):
    cursor.execute('''INSERT OR IGNORE INTO economy_state (id, gooncoin_supply, inflation_rate, last_adjustment)
                      VALUES (1, 0, ?, CURRENT_TIMESTAMP)''', (BASE_INFLATION_RATE,))

def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except Exception:
            return None

def calculate_inflation_multiplier(inflation_rate):
    return 1 + (inflation_rate * INFLATION_MULTIPLIER_FACTOR)

def apply_inflation_to_cost(cost_dict, multiplier):
    inflated = dict(cost_dict)
    if 'gooncoins' in inflated and inflated['gooncoins'] is not None:
        inflated['gooncoins'] = float(inflated['gooncoins']) * multiplier
    return inflated

def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def calculate_item_base_value(item_id):
    definition = EQUIPMENT_DEFS.get(item_id, {})
    cost = definition.get('cost', {}) or {}
    base_value = 0
    for resource, factor in ITEM_VALUE_FACTORS.items():
        base_value += (cost.get(resource, 0) or 0) * factor
    if base_value <= 0:
        power = definition.get('power') or sum((definition.get('bonus') or {}).values()) or 1
        base_value = 150 + power * 12
    rarity = definition.get('rarity')
    base_value *= RARITY_VALUE_MULTIPLIERS.get(rarity, 1.0)
    return round(base_value, 2)


def ensure_item_market_state(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS item_market_state
                      (item_id TEXT PRIMARY KEY,
                       price_multiplier REAL DEFAULT 1.0,
                       net_flow REAL DEFAULT 0,
                       base_value REAL DEFAULT 0,
                       last_price REAL DEFAULT 0,
                       last_trend TEXT DEFAULT 'flat',
                       total_minted INTEGER DEFAULT 0,
                       total_burned INTEGER DEFAULT 0,
                       last_update TEXT DEFAULT CURRENT_TIMESTAMP)''')
    now_iso = datetime.utcnow().isoformat()
    for item_id in EQUIPMENT_DEFS.keys():
        base_value = calculate_item_base_value(item_id)
        cursor.execute('''INSERT OR IGNORE INTO item_market_state
                          (item_id, price_multiplier, net_flow, base_value, last_price, last_trend, total_minted, total_burned, last_update)
                          VALUES (?, 1.0, 0, ?, ?, 'flat', 0, 0, ?)''',
                       (item_id, base_value, base_value, now_iso))
        cursor.execute('UPDATE item_market_state SET base_value = ? WHERE item_id = ?', (base_value, item_id))


def _decay_item_market_row(row, now):
    last_update = parse_timestamp(row['last_update']) or now
    elapsed = max(0, (now - last_update).total_seconds())
    net_flow = row['net_flow'] or 0
    price_multiplier = row['price_multiplier'] or 1.0
    if elapsed > 0:
        decay = pow(0.5, elapsed / ITEM_MARKET_FLOW_HALFLIFE)
        net_flow *= decay
        reversion_strength = min(1.0, elapsed / ITEM_MARKET_REVERSION_WINDOW) * ITEM_MARKET_REVERSION_RATE
        price_multiplier += (1 - price_multiplier) * reversion_strength
    return net_flow, clamp(price_multiplier, ITEM_MARKET_MIN_MULTIPLIER, ITEM_MARKET_MAX_MULTIPLIER)


def stabilize_item_market_state(cursor, now=None):
    ensure_item_market_state(cursor)
    now = now or datetime.utcnow()
    cursor.execute('SELECT item_id, price_multiplier, net_flow, last_update FROM item_market_state')
    rows = cursor.fetchall()
    for row in rows:
        net_flow, price_multiplier = _decay_item_market_row(row, now)
        price_multiplier = clamp(
            price_multiplier + random.uniform(-ITEM_MARKET_RANDOM_SWING, ITEM_MARKET_RANDOM_SWING),
            ITEM_MARKET_MIN_MULTIPLIER,
            ITEM_MARKET_MAX_MULTIPLIER
        )
        cursor.execute('''UPDATE item_market_state
                          SET price_multiplier = ?, net_flow = ?, last_update = ?
                          WHERE item_id = ?''',
                       (price_multiplier, net_flow, now.isoformat(), row['item_id']))


def register_item_supply_change(cursor, item_id, delta_supply, now=None):
    if not delta_supply:
        return
    ensure_item_market_state(cursor)
    now = now or datetime.utcnow()
    cursor.execute('SELECT * FROM item_market_state WHERE item_id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        base_value = calculate_item_base_value(item_id)
        cursor.execute('''INSERT INTO item_market_state
                          (item_id, price_multiplier, net_flow, base_value, last_price, last_trend, total_minted, total_burned, last_update)
                          VALUES (?, 1.0, 0, ?, ?, 'flat', ?, ?, ?)''',
                       (item_id, base_value, base_value, max(0, delta_supply), max(0, -delta_supply), now.isoformat()))
        cursor.execute('SELECT * FROM item_market_state WHERE item_id = ?', (item_id,))
        row = cursor.fetchone()
    net_flow, price_multiplier = _decay_item_market_row(row, now)
    net_flow += delta_supply
    adjustment = ITEM_MARKET_SENSITIVITY * abs(delta_supply)
    if delta_supply > 0:
        price_multiplier -= adjustment
    else:
        price_multiplier += adjustment
    price_multiplier = clamp(price_multiplier, ITEM_MARKET_MIN_MULTIPLIER, ITEM_MARKET_MAX_MULTIPLIER)
    base_value = calculate_item_base_value(item_id)
    previous_price = row['last_price'] if row and row['last_price'] else base_value
    market_value = round(base_value * price_multiplier, 2)
    trend = 'up' if market_value > previous_price + 0.1 else ('down' if market_value < previous_price - 0.1 else 'flat')
    total_minted = (row['total_minted'] or 0) + max(0, delta_supply)
    total_burned = (row['total_burned'] or 0) + max(0, -delta_supply)
    cursor.execute('''UPDATE item_market_state
                      SET price_multiplier = ?, net_flow = ?, base_value = ?, last_price = ?, last_trend = ?,
                          total_minted = ?, total_burned = ?, last_update = ?
                      WHERE item_id = ?''',
                   (price_multiplier, net_flow, base_value, market_value, trend,
                    total_minted, total_burned, now.isoformat(), item_id))
    return market_value


def get_item_market_snapshot(cursor):
    ensure_item_market_state(cursor)
    stabilize_item_market_state(cursor)
    cursor.execute('SELECT * FROM item_market_state')
    rows = cursor.fetchall()
    snapshot = {}
    for row in rows:
        base_value = row['base_value'] or calculate_item_base_value(row['item_id'])
        price_multiplier = row['price_multiplier'] or 1.0
        market_value = round(base_value * price_multiplier, 2)
        sell_value = round(market_value * ITEM_MARKET_SELL_TAX, 2)
        snapshot[row['item_id']] = {
            'item_id': row['item_id'],
            'base_value': base_value,
            'price_multiplier': round(price_multiplier, 4),
            'market_value': market_value,
            'sell_value': sell_value,
            'trend': row['last_trend'] or 'flat',
            'total_minted': row['total_minted'] or 0,
            'total_burned': row['total_burned'] or 0,
            'current_supply': (row['total_minted'] or 0) - (row['total_burned'] or 0),
            'last_update': row['last_update']
        }
    return snapshot


def _safe_json_loads(raw_value):
    if not raw_value:
        return None
    try:
        return json.loads(raw_value)
    except Exception:
        return None


def build_inventory_payload(cursor, user_id):
    item_market = get_item_market_snapshot(cursor)
    cursor.execute('''SELECT id, equipment_id, equipment_slot, equipped,
                             acquired_at, acquired_via, acquisition_note,
                             acquisition_payload, last_valuation
                      FROM equipment
                      WHERE user_id = ?
                      ORDER BY COALESCE(acquired_at, CURRENT_TIMESTAMP) DESC, id DESC''', (user_id,))
    rows = cursor.fetchall()
    items = []
    rarity_breakdown = {}
    estimated_value = 0
    equipped_count = 0
    per_item_counts = {}
    for row in rows:
        equipment_id = row['equipment_id']
        definition = EQUIPMENT_DEFS.get(equipment_id, {})
        rarity = definition.get('rarity', 'common')
        market_info = item_market.get(equipment_id, {})
        base_value = market_info.get('base_value', calculate_item_base_value(equipment_id))
        market_value = market_info.get('market_value', base_value)
        sell_value = market_info.get('sell_value', round(market_value * ITEM_MARKET_SELL_TAX, 2))
        estimated_value += sell_value
        if row['equipped']:
            equipped_count += 1
        rarity_breakdown[rarity] = rarity_breakdown.get(rarity, 0) + 1
        per_item_counts[equipment_id] = per_item_counts.get(equipment_id, 0) + 1
        items.append({
            'instance_id': row['id'],
            'equipment_id': equipment_id,
            'slot': definition.get('slot', row['equipment_slot']),
            'name': definition.get('name', equipment_id),
            'rarity': rarity,
            'equipped': bool(row['equipped']),
            'acquired_at': row['acquired_at'],
            'acquired_via': row['acquired_via'] or 'unknown',
            'acquisition_note': row['acquisition_note'],
            'acquisition_payload': _safe_json_loads(row['acquisition_payload']),
            'base_value': base_value,
            'market_value': market_value,
            'sell_value': round(sell_value, 2),
            'price_multiplier': market_info.get('price_multiplier', 1.0),
            'market_trend': market_info.get('trend', 'flat')
        })
    duplicates = sum(max(0, count - 1) for count in per_item_counts.values())
    summary = {
        'total_items': len(items),
        'equipped_items': equipped_count,
        'duplicates': duplicates,
        'estimated_sell_value': round(estimated_value, 2),
        'rarity_breakdown': rarity_breakdown
    }
    return {
        'items': items,
        'summary': summary,
        'market': item_market,
        'updated_at': datetime.utcnow().isoformat()
    }


def _row_to_mapping(row):
    if isinstance(row, dict):
        return row
    if hasattr(row, 'keys'):
        return {key: row[key] for key in row.keys()}
    return {}


def extract_player_resources(state_row):
    mapping = _row_to_mapping(state_row)
    resources = {}
    for key in RESOURCE_FIELDS:
        if key in mapping and mapping[key] is not None:
            resources[key] = float(mapping[key])
        else:
            fallback = RESOURCE_FALLBACKS.get(key)
            fallback_value = mapping.get(fallback) if fallback else 0
            resources[key] = float(fallback_value or 0)
    return resources


def clone_resources(resources):
    return {key: float(resources.get(key, 0) or 0) for key in RESOURCE_FIELDS}


def can_afford_cost(resources, cost):
    for resource, amount in (cost or {}).items():
        if amount is None or amount <= 0:
            continue
        if resources.get(resource, 0) + 1e-9 < amount:
            return False, resource
    return True, None


def deduct_cost(resources, cost):
    affordable, lacking = can_afford_cost(resources, cost)
    if not affordable:
        return False, lacking
    for resource, amount in (cost or {}).items():
        if amount is None or amount <= 0:
            continue
        resources[resource] = resources.get(resource, 0) - amount
    return True, None


def apply_rewards(resources, reward):
    for resource, amount in (reward or {}).items():
        if amount is None or amount == 0:
            continue
        resources[resource] = resources.get(resource, 0) + amount


def persist_resources(cursor, user_id, resources):
    set_clause = ', '.join([f"{key} = ?" for key in RESOURCE_FIELDS])
    values = [resources.get(key, 0) for key in RESOURCE_FIELDS]
    values.append(user_id)
    cursor.execute(
        f'''UPDATE game_state 
            SET {set_clause}, last_update = CURRENT_TIMESTAMP
            WHERE user_id = ?''',
        values
    )


def resources_payload(resources):
    return {key: resources.get(key, 0) for key in RESOURCE_FIELDS}

def ensure_market_state(cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS market_state
                      (currency TEXT PRIMARY KEY,
                       price_multiplier REAL DEFAULT 1.0,
                       net_flow REAL DEFAULT 0,
                       last_update TEXT DEFAULT CURRENT_TIMESTAMP)''')
    now_iso = datetime.utcnow().isoformat()
    for currency in TRADEABLE_CURRENCIES:
        cursor.execute('''INSERT OR IGNORE INTO market_state (currency, price_multiplier, net_flow, last_update)
                          VALUES (?, 1.0, 0, ?)''', (currency, now_iso))

def _decay_market_row(row, now):
    last_update = parse_timestamp(row['last_update']) or now
    elapsed = max(0, (now - last_update).total_seconds())
    net_flow = row['net_flow']
    price_multiplier = row['price_multiplier']
    if elapsed > 0:
        decay = pow(0.5, elapsed / MARKET_FLOW_HALFLIFE)
        net_flow *= decay
        reversion_strength = min(1.0, elapsed / MARKET_REVERSION_WINDOW) * MARKET_REVERSION_RATE
        price_multiplier += (1 - price_multiplier) * reversion_strength
    return net_flow, clamp(price_multiplier, MARKET_MIN_MULTIPLIER, MARKET_MAX_MULTIPLIER)

def stabilize_market_state(cursor, now=None):
    ensure_market_state(cursor)
    now = now or datetime.utcnow()
    cursor.execute('SELECT currency, price_multiplier, net_flow, last_update FROM market_state')
    rows = cursor.fetchall()
    for row in rows:
        net_flow, price_multiplier = _decay_market_row(row, now)
        price_multiplier = clamp(
            price_multiplier + random.uniform(-MARKET_RANDOM_SWING, MARKET_RANDOM_SWING),
            MARKET_MIN_MULTIPLIER,
            MARKET_MAX_MULTIPLIER
        )
        cursor.execute('''UPDATE market_state
                          SET price_multiplier = ?, net_flow = ?, last_update = ?
                          WHERE currency = ?''',
                       (price_multiplier, net_flow, now.isoformat(), row['currency']))

def apply_market_trade(cursor, currency, action, amount, now=None):
    ensure_market_state(cursor)
    now = now or datetime.utcnow()
    cursor.execute('SELECT currency, price_multiplier, net_flow, last_update FROM market_state WHERE currency = ?', (currency,))
    row = cursor.fetchone()
    if not row:
        return
    net_flow, price_multiplier = _decay_market_row(row, now)
    direction = 1 if action == 'buy' else -1
    net_flow += direction * amount
    liquidity = MARKET_LIQUIDITY.get(currency, MARKET_DEFAULT_LIQUIDITY)
    pressure = max(-5.0, min(5.0, (direction * amount) / max(1.0, liquidity)))
    price_multiplier = clamp(
        price_multiplier + pressure * MARKET_SENSITIVITY + random.uniform(-MARKET_RANDOM_SWING, MARKET_RANDOM_SWING),
        MARKET_MIN_MULTIPLIER,
        MARKET_MAX_MULTIPLIER
    )
    cursor.execute('''UPDATE market_state
                      SET price_multiplier = ?, net_flow = ?, last_update = ?
                      WHERE currency = ?''',
                   (price_multiplier, net_flow, now.isoformat(), currency))

def get_dynamic_market_rates(cursor, inflation_rate):
    ensure_market_state(cursor)
    stabilize_market_state(cursor)
    cursor.execute('SELECT currency, price_multiplier FROM market_state')
    rows = cursor.fetchall()
    rates = {}
    inflation_value = inflation_rate if inflation_rate is not None else BASE_INFLATION_RATE
    inflation_component = get_market_multiplier(inflation_value)
    for row in rows:
        currency = row['currency']
        base_price = BASE_EXCHANGE_RATES.get(currency, 100)
        mid_price = base_price * row['price_multiplier'] * inflation_component
        buy_price = max(mid_price * (1 + MARKET_SPREAD / 2), 0.01)
        sell_price = max(mid_price * (1 - MARKET_SPREAD / 2), 0.01)
        rates[currency] = {
            'buy': round(buy_price, 2),
            'sell': round(sell_price, 2)
        }
    return rates

def get_market_multiplier(inflation_rate):
    return 1 + inflation_rate * 5

def fetch_economy_snapshot(force=False):
    conn = get_db()
    c = conn.cursor()
    ensure_economy_row(c)
    ensure_market_state(c)
    c.execute('SELECT gooncoin_supply, inflation_rate, last_adjustment FROM economy_state WHERE id = 1')
    row = c.fetchone()
    now = datetime.utcnow()
    last_adjustment = parse_timestamp(row['last_adjustment']) if row else None
    inflation_rate = row['inflation_rate'] if row and row['inflation_rate'] is not None else BASE_INFLATION_RATE
    gooncoin_supply = row['gooncoin_supply'] if row and row['gooncoin_supply'] is not None else 0
    needs_update = force or not last_adjustment or (now - last_adjustment).total_seconds() >= ECONOMY_UPDATE_INTERVAL
    
    if needs_update:
        c.execute('SELECT SUM(gooncoins) as total FROM game_state')
        total_supply_row = c.fetchone()
        total_supply = total_supply_row['total'] if total_supply_row and total_supply_row['total'] is not None else 0
        gooncoin_supply = total_supply
        
        supply_factor = min(0.3, (gooncoin_supply / 250000) if gooncoin_supply else 0)
        target_rate = BASE_INFLATION_RATE + supply_factor
        shock = random.uniform(-0.004, 0.006)
        new_rate = inflation_rate + (target_rate - inflation_rate) * 0.35 + shock
        inflation_rate = max(MIN_INFLATION_RATE, min(MAX_INFLATION_RATE, new_rate))
        
        c.execute('''UPDATE economy_state 
                     SET gooncoin_supply = ?, inflation_rate = ?, last_adjustment = ?
                     WHERE id = 1''',
                  (gooncoin_supply, inflation_rate, now.isoformat()))
        conn.commit()
    
    market_rates = get_dynamic_market_rates(c, inflation_rate)
    conn.commit()
    snapshot = {
        'inflation_rate': inflation_rate,
        'inflation_multiplier': round(calculate_inflation_multiplier(inflation_rate), 4),
        'gooncoin_supply': gooncoin_supply,
        'market_multiplier': round(get_market_multiplier(inflation_rate), 3),
        'market_rates': market_rates
    }
    conn.close()
    return snapshot

def refresh_economy_after_change():
    try:
        fetch_economy_snapshot(force=True)
    except Exception:
        pass

def get_current_inflation_rate(cursor):
    ensure_economy_row(cursor)
    cursor.execute('SELECT inflation_rate FROM economy_state WHERE id = 1')
    row = cursor.fetchone()
    return row['inflation_rate'] if row and row['inflation_rate'] is not None else BASE_INFLATION_RATE

def ensure_story_progress(cursor, user_id):
    cursor.execute('SELECT * FROM story_progress WHERE user_id = ?', (user_id,))
    story = cursor.fetchone()
    if not story:
        cursor.execute('''INSERT INTO story_progress 
                          (user_id, current_chapter, completed_quests, unlocked_buildings, unlocked_currencies)
                          VALUES (?, 1, '[]', '[]', '["gooncoins"]')''', (user_id,))
        cursor.connection.commit()
        cursor.execute('SELECT * FROM story_progress WHERE user_id = ?', (user_id,))
        story = cursor.fetchone()
    return story

def ensure_rare_materials(cursor, user_id):
    cursor.execute('INSERT OR IGNORE INTO rare_materials (user_id) VALUES (?)', (user_id,))
    cursor.connection.commit()
    cursor.execute('SELECT * FROM rare_materials WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def ensure_combat_profile(cursor, user_id):
    cursor.execute('INSERT OR IGNORE INTO combat_profiles (user_id) VALUES (?)', (user_id,))
    cursor.connection.commit()
    cursor.execute('SELECT * FROM combat_profiles WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def ensure_temple_state(cursor, user_id):
    cursor.execute('INSERT OR IGNORE INTO temple_state (user_id) VALUES (?)', (user_id,))
    if cursor.rowcount:
        cursor.connection.commit()
    cursor.execute('SELECT * FROM temple_state WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def serialize_rare_materials(row):
    materials = {}
    for key in RARE_MATERIAL_DEFS.keys():
        materials[key] = row[key] if row and key in row.keys() and row[key] is not None else 0
    return materials

def adjust_rare_materials(cursor, user_id, adjustments):
    if not adjustments:
        return
    valid_updates = []
    values = []
    for key, amount in adjustments.items():
        if key not in RARE_MATERIAL_DEFS:
            continue
        valid_updates.append(f"{key} = {key} + ?")
        values.append(amount)
    if not valid_updates:
        return
    values.append(user_id)
    cursor.execute(f'''UPDATE rare_materials SET {', '.join(valid_updates)} WHERE user_id = ?''', values)

def _temple_default_progress():
    return {'kills': 0, 'loops': 0, 'ever_cleared': False}

def _temple_load_progress(row):
    if not row:
        return {}
    raw = row['progress'] if 'progress' in row.keys() else '{}'
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {}
    except (TypeError, json.JSONDecodeError):
        return {}

def _temple_room_index(room_id):
    for idx, room in enumerate(TEMPLE_ROOMS):
        if room['id'] == room_id:
            return idx
    return None

def _temple_get_room(room_id):
    for room in TEMPLE_ROOMS:
        if room['id'] == room_id:
            return room
    return None

def _temple_is_room_unlocked(progress_map, room):
    if not room:
        return False
    unlock_after = room.get('unlock_after')
    if not unlock_after:
        return True
    prereq = progress_map.get(unlock_after)
    return bool(prereq and prereq.get('ever_cleared'))

def _temple_first_unlocked_room(progress_map):
    for room in TEMPLE_ROOMS:
        if _temple_is_room_unlocked(progress_map, room):
            return room['id']
    return TEMPLE_ROOMS[0]['id'] if TEMPLE_ROOMS else None

def build_temple_snapshot(cursor, user_id):
    temple_row = ensure_temple_state(cursor, user_id)
    cursor.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = "temple"', (user_id,))
    building = cursor.fetchone()
    built = bool(building and building['level'] and building['level'] > 0)
    if not built:
        return {
            'unlocked': False,
            'reason': 'Postav Chrám, aby ses dostal k rituálům a chrámovým bojům.'
        }
    
    progress_map = _temple_load_progress(temple_row)
    now = datetime.utcnow()
    
    cooldown_until = parse_timestamp(temple_row['cooldown_until'] if temple_row and 'cooldown_until' in temple_row.keys() else None)
    cooldown_seconds = 0
    cooldown_iso = None
    if cooldown_until and cooldown_until > now:
        cooldown_seconds = int((cooldown_until - now).total_seconds())
        cooldown_iso = cooldown_until.isoformat()
    else:
        cooldown_until = None
    
    active_room = temple_row['last_room'] if temple_row and temple_row['last_room'] else None
    if active_room:
        active_obj = _temple_get_room(active_room)
        if not active_obj or not _temple_is_room_unlocked(progress_map, active_obj):
            active_room = None
    if not active_room:
        active_room = _temple_first_unlocked_room(progress_map)
    
    blessings = []
    for blessing_id, definition in TEMPLE_BLESSINGS.items():
        blessings.append({
            'id': blessing_id,
            'name': definition['name'],
            'description': definition['description'],
            'cost': definition['cost'],
            'bonus': definition['bonus'],
            'duration': definition['duration']
        })
    
    active_blessing_data = None
    if temple_row and temple_row['active_blessing']:
        blessing_def = TEMPLE_BLESSINGS.get(temple_row['active_blessing'])
        expires = parse_timestamp(temple_row['blessing_expires_at'])
        if blessing_def and expires and expires > now:
            active_blessing_data = {
                'id': temple_row['active_blessing'],
                'name': blessing_def['name'],
                'expires_in': int((expires - now).total_seconds()),
                'expires_at': expires.isoformat()
            }
        elif temple_row['active_blessing']:
            cursor.execute('UPDATE temple_state SET active_blessing = NULL, blessing_expires_at = NULL WHERE user_id = ?', (user_id,))
            cursor.connection.commit()
    
    rooms_payload = []
    for room in TEMPLE_ROOMS:
        unlocked = _temple_is_room_unlocked(progress_map, room)
        room_progress = progress_map.get(room['id'], _temple_default_progress())
        kills = room_progress.get('kills', 0)
        loops = room_progress.get('loops', 0)
        boss_ready = unlocked and kills >= room['required_kills']
        status = 'locked'
        if unlocked:
            if room_progress.get('ever_cleared'):
                status = 'cleared'
            elif room['id'] == active_room:
                status = 'active'
            else:
                status = 'available'
        rooms_payload.append({
            'id': room['id'],
            'name': room['name'],
            'description': room['description'],
            'required_kills': room['required_kills'],
            'kills': kills,
            'loops': loops,
            'boss_ready': boss_ready,
            'status': status,
            'unlocked': unlocked,
            'boss_name': room['boss']['name'],
            'boss_rewards': room['boss']['rewards'],
            'enemy_preview': [TEMPLE_ENEMIES[e]['name'] for e in room['enemy_pool'] if e in TEMPLE_ENEMIES]
        })
    
    return {
        'unlocked': True,
        'favor': temple_row['favor'] if temple_row and temple_row['favor'] is not None else 0,
        'active_room': active_room,
        'rooms': rooms_payload,
        'blessings': blessings,
        'active_blessing': active_blessing_data,
        'cooldown_seconds': cooldown_seconds,
        'cooldown_until': cooldown_iso
    }

def _bonus_value(raw_value):
    if raw_value is None:
        return 0
    if isinstance(raw_value, (int, float)):
        if raw_value > 1:
            return (raw_value - 1) * 10
        return raw_value
    return 0

def calculate_player_combat_stats(cursor, user_id):
    cursor.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ?', (user_id,))
    upgrades = {row['upgrade_type']: row['level'] for row in cursor.fetchall()}
    
    cursor.execute('SELECT building_type, level FROM buildings WHERE user_id = ?', (user_id,))
    buildings = {row['building_type']: row['level'] for row in cursor.fetchall()}
    
    story = ensure_story_progress(cursor, user_id)
    current_chapter = story['current_chapter'] if story else 1
    
    cursor.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_items = [row['equipment_id'] for row in cursor.fetchall()]
    
    eq_attack = 0
    eq_defense = 0
    eq_luck = 0
    for equipment_id in equipped_items:
        definition = EQUIPMENT_DEFS.get(equipment_id, {})
        bonus = definition.get('bonus', {})
        eq_attack += _bonus_value(bonus.get('click_power'))
        eq_defense += _bonus_value(bonus.get('defense'))
        eq_luck += _bonus_value(bonus.get('luck'))
    
    temple_row = ensure_temple_state(cursor, user_id)
    blessing_bonus = {}
    if temple_row and temple_row['active_blessing']:
        blessing_def = TEMPLE_BLESSINGS.get(temple_row['active_blessing'])
        expires = parse_timestamp(temple_row['blessing_expires_at'])
        now = datetime.utcnow()
        if blessing_def and expires and expires > now:
            blessing_bonus = blessing_def.get('bonus', {})
        elif temple_row['active_blessing']:
            cursor.execute('UPDATE temple_state SET active_blessing = NULL, blessing_expires_at = NULL WHERE user_id = ?', (user_id,))
            cursor.connection.commit()
    
    click_power_levels = (upgrades.get('click_power_1', 0) + upgrades.get('click_power_2', 0))
    auto_generators = upgrades.get('auto_gooncoin', 0) + sum(upgrades.get(gen, 0) for gen in [
        'astma_collector', 'poharky_collector', 'mrkev_collector', 'uzené_collector'
    ])
    
    base_attack = 15 + click_power_levels * 4 + auto_generators * 0.8
    base_defense = 12 + buildings.get('temple', 0) * 5 + upgrades.get('uzené_collector', 0) * 1.5
    base_luck = 1 + (current_chapter - 1) * 0.2 + buildings.get('market', 0) * 0.1
    base_hp = 150 + buildings.get('workshop', 0) * 20 + upgrades.get('auto_gooncoin', 0) * 4
    
    stats = {
        'attack': round(base_attack + eq_attack + blessing_bonus.get('attack', 0), 2),
        'defense': round(base_defense + eq_defense + blessing_bonus.get('defense', 0), 2),
        'luck': round(base_luck + eq_luck + blessing_bonus.get('luck', 0), 2),
        'hp': int(base_hp + (eq_defense * 6) + blessing_bonus.get('hp', 0)),
        'chapter': current_chapter
    }
    stats['power_score'] = round(stats['attack'] * 1.4 + stats['defense'] * 1.2 + stats['luck'] * 12, 2)
    return stats

def simulate_combat(attacker, defender, max_rounds=MAX_COMBAT_ROUNDS):
    attacker_hp = attacker['hp']
    defender_hp = defender['hp']
    log = []
    rounds_played = 0
    
    def _roll_damage(source, target):
        attack_roll = source['attack'] * random.uniform(0.85, 1.25)
        defense_roll = target['defense'] * random.uniform(0.45, 0.85)
        dodge_chance = clamp(0.04 + target['luck'] * 0.015 - source['luck'] * 0.01, 0.04, 0.45)
        if random.random() < dodge_chance:
            return 0, False, True
        crit_chance = clamp(0.05 + source['luck'] * 0.02, 0.05, 0.45)
        crit = random.random() < crit_chance
        damage = max(4, attack_roll - defense_roll)
        if crit:
            damage *= random.uniform(1.35, 1.6)
        return damage, crit, False
    
    while rounds_played < max_rounds and attacker_hp > 0 and defender_hp > 0:
        rounds_played += 1
        # Attacker strikes
        damage, crit, dodged = _roll_damage(attacker, defender)
        if not dodged:
            defender_hp -= damage
        log.append({
            'round': rounds_played,
            'actor': 'attacker',
            'damage': round(damage if not dodged else 0, 1),
            'crit': crit,
            'dodged': dodged,
            'defender_hp': max(0, round(defender_hp, 1))
        })
        if defender_hp <= 0:
            break
        
        # Defender counters
        damage, crit, dodged = _roll_damage(defender, attacker)
        if not dodged:
            attacker_hp -= damage
        log.append({
            'round': rounds_played,
            'actor': 'defender',
            'damage': round(damage if not dodged else 0, 1),
            'crit': crit,
            'dodged': dodged,
            'defender_hp': max(0, round(attacker_hp, 1))
        })
    
    if attacker_hp <= 0 and defender_hp <= 0:
        winner = 'draw'
    elif defender_hp <= 0:
        winner = 'attacker'
    elif attacker_hp <= 0:
        winner = 'defender'
    else:
        winner = 'attacker' if attacker_hp >= defender_hp else 'defender'
    
    return {
        'winner': winner,
        'rounds': rounds_played,
        'log': log,
        'attacker_remaining_hp': max(0, round(attacker_hp, 1)),
        'defender_remaining_hp': max(0, round(defender_hp, 1))
    }

def record_combat_log(cursor, attacker_id, defender_id, mode, winner_id, summary):
    cursor.execute('''INSERT INTO combat_logs (attacker_id, defender_id, mode, winner_id, summary)
                      VALUES (?, ?, ?, ?, ?)''',
                   (attacker_id, defender_id, mode, winner_id, json.dumps(summary)))

def build_campaign_snapshot(profile):
    stage = profile['campaign_stage']
    defeated = set(json.loads(profile['defeated_monsters']) if profile['defeated_monsters'] else [])
    monsters = []
    next_monster = None
    for index, monster in enumerate(CAMPAIGN_MONSTERS):
        status = 'locked'
        if index < stage:
            status = 'repeatable'
        elif index == stage:
            status = 'next'
            next_monster = monster
        elif monster['id'] in defeated:
            status = 'defeated'
        monsters.append({
            **monster,
            'status': status
        })
    if stage >= len(CAMPAIGN_MONSTERS):
        next_monster = CAMPAIGN_MONSTERS[-1]
    return {
        'stage': stage,
        'monsters': monsters,
        'next_monster': next_monster,
        'defeated': list(defeated)
    }
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('game'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Neplatné přihlašovací údaje'})
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'error': 'Vyplňte všechna pole'})
    
    conn = get_db()
    c = conn.cursor()
    
    try:
        password_hash = generate_password_hash(password)
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                 (username, password_hash))
        user_id = c.lastrowid
        
        # Initialize game state
        c.execute('''INSERT INTO game_state 
                     (user_id, gooncoins, astma, poharky, mrkev, uzené) 
                     VALUES (?, 0, 0, 0, 0, 0)''', (user_id,))
        
        # Initialize story progress
        c.execute('''INSERT INTO story_progress 
                     (user_id, current_chapter, completed_quests, unlocked_buildings, unlocked_currencies)
                     VALUES (?, 1, '[]', '[]', '["gooncoins"]')''', (user_id,))
        
        # Initialize rare materials & combat profile
        c.execute('INSERT INTO rare_materials (user_id) VALUES (?)', (user_id,))
        c.execute('INSERT INTO combat_profiles (user_id) VALUES (?)', (user_id,))
        
        conn.commit()
        session['user_id'] = user_id
        session['username'] = username
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Uživatelské jméno již existuje'})

@app.route('/game')
def game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('game.html', username=session.get('username', 'Hráč'))

@app.route('/api/game-state')
def get_game_state():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get game state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    resources = extract_player_resources(state)
    
    # Get upgrades
    c.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ?', (user_id,))
    upgrades = {row['upgrade_type']: row['level'] for row in c.fetchall()}
    
    # Get story progress
    story = ensure_story_progress(c, user_id)
    
    # Get equipment
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped = {row['equipment_slot']: row['equipment_id'] for row in c.fetchall()}
    
    # Player equipment counts (inventář)
    c.execute('SELECT equipment_id, COUNT(*) as count FROM equipment WHERE user_id = ? GROUP BY equipment_id', (user_id,))
    equipment_counts = {row['equipment_id']: row['count'] for row in c.fetchall()}
    
    # Get buildings
    c.execute('SELECT building_type, level FROM buildings WHERE user_id = ?', (user_id,))
    buildings = {row['building_type']: row['level'] for row in c.fetchall()}
    
    rare_row = ensure_rare_materials(c, user_id)
    combat_profile = ensure_combat_profile(c, user_id)
    inventory_payload = build_inventory_payload(c, user_id)
    
    if not state:
        return jsonify({'error': 'Game state not found'}), 404
    
    resources = extract_player_resources(state)
    
    # Parse story data
    completed_quests = json.loads(story['completed_quests']) if story and story['completed_quests'] else []
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    
    # Get generation rates
    generation_rates = {
        'gooncoins': upgrades.get('auto_gooncoin', 0) * 0.1,
        'astma': upgrades.get('astma_collector', 0) * 0.05,
        'poharky': upgrades.get('poharky_collector', 0) * 0.03,
        'mrkev': upgrades.get('mrkev_collector', 0) * 0.02,
        'uzené': upgrades.get('uzené_collector', 0) * 0.01
    }
    _, logistic_rates, logistics_snapshot = evaluate_logistics(resources, buildings, time_window=1.0, mutate=False)
    for resource in SECONDARY_RESOURCES:
        generation_rates[resource] = logistic_rates.get(resource, 0.0)
    
    conn.close()
    
    economy_snapshot = fetch_economy_snapshot()
    resource_payload = resources_payload(resources)
    
    return jsonify({
        **resource_payload,
        'total_clicks': state['total_clicks'],
        'upgrades': upgrades,
        'last_update': state['last_update'],
        'story': {
            'current_chapter': story['current_chapter'] if story else 1,
            'completed_quests': completed_quests,
            'unlocked_buildings': unlocked_buildings,
            'unlocked_currencies': unlocked_currencies
        },
        'equipment': equipped,
        'equipment_counts': equipment_counts,
        'buildings': buildings,
        'generation_rates': generation_rates,
        'logistics': logistics_snapshot,
        'economy': economy_snapshot,
        'rare_materials': serialize_rare_materials(rare_row),
        'combat': {
            'rating': combat_profile['rating'],
            'wins': combat_profile['wins'],
            'losses': combat_profile['losses'],
            'campaign_stage': combat_profile['campaign_stage'],
            'defeated_monsters': json.loads(combat_profile['defeated_monsters']) if combat_profile['defeated_monsters'] else []
        },
        'inventory': inventory_payload
    })

@app.route('/api/click', methods=['POST'])
def click():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    c.execute('SELECT gooncoins, total_clicks FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    
    # Calculate click value (base + upgrades)
    click_value = 1.0
    c.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ? AND upgrade_type LIKE "click_power%"', (user_id,))
    for row in c.fetchall():
        click_value += row['level'] * 0.5
    
    new_gooncoins = state['gooncoins'] + click_value
    new_clicks = state['total_clicks'] + 1
    
    c.execute('''UPDATE game_state 
                 SET gooncoins = ?, total_clicks = ?, last_update = CURRENT_TIMESTAMP
                 WHERE user_id = ?''',
             (new_gooncoins, new_clicks, user_id))
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'gooncoins': new_gooncoins,
        'click_value': click_value,
        'total_clicks': new_clicks
    })

@app.route('/api/auto-generate', methods=['POST'])
def auto_generate():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state and upgrades
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    
    c.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ?', (user_id,))
    upgrades = {row['upgrade_type']: row['level'] for row in c.fetchall()}
    
    c.execute('SELECT building_type, level FROM buildings WHERE user_id = ?', (user_id,))
    buildings = {row['building_type']: row['level'] for row in c.fetchall()}
    
    # Calculate time passed since last update
    last_update_str = state['last_update']
    if last_update_str:
        try:
            last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
            time_passed = (datetime.now() - last_update.replace(tzinfo=None)).total_seconds()
            # Cap at 60 seconds to prevent abuse
            time_passed = min(time_passed, 60.0)
        except:
            time_passed = 1.0
    else:
        time_passed = 1.0
    
    # Calculate generation rates
    generation = {
        'gooncoins': 0,
        'astma': 0,
        'poharky': 0,
        'mrkev': 0,
        'uzené': 0
    }
    
    resources = extract_player_resources(state)
    
    # Auto-generators - calculate rates per second
    gooncoin_rate = upgrades.get('auto_gooncoin', 0) * 0.1
    astma_rate = upgrades.get('astma_collector', 0) * 0.05
    poharky_rate = upgrades.get('poharky_collector', 0) * 0.03
    mrkev_rate = upgrades.get('mrkev_collector', 0) * 0.02
    uzené_rate = upgrades.get('uzené_collector', 0) * 0.01
    
    if gooncoin_rate:
        generation['gooncoins'] = gooncoin_rate * time_passed
        resources['gooncoins'] += generation['gooncoins']
    if astma_rate:
        generation['astma'] = astma_rate * time_passed
        resources['astma'] += generation['astma']
    if poharky_rate:
        generation['poharky'] = poharky_rate * time_passed
        resources['poharky'] += generation['poharky']
    if mrkev_rate:
        generation['mrkev'] = mrkev_rate * time_passed
        resources['mrkev'] += generation['mrkev']
    if uzené_rate:
        generation['uzené'] = uzené_rate * time_passed
        resources['uzené'] += generation['uzené']
    
    resources, logistic_rates, logistics_snapshot = evaluate_logistics(resources, buildings, time_passed, mutate=True)
    for logistic_resource, rate in logistic_rates.items():
        generation[logistic_resource] = generation.get(logistic_resource, 0) + rate * time_passed
    
    persist_resources(c, user_id, resources)
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    generation_rates = {
        'gooncoins': gooncoin_rate,
        'astma': astma_rate,
        'poharky': poharky_rate,
        'mrkev': mrkev_rate,
        'uzené': uzené_rate
    }
    for resource_name in SECONDARY_RESOURCES:
        generation_rates[resource_name] = logistic_rates.get(resource_name, 0.0)
    
    resource_payload = resources_payload(resources)
    
    return jsonify({
        **resource_payload,
        'generation': generation,
        'generation_rates': generation_rates,
        'logistics': logistics_snapshot
    })

@app.route('/api/buy-upgrade', methods=['POST'])
def buy_upgrade():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        upgrade_type = data.get('upgrade_type')
        
        if not upgrade_type:
            return jsonify({'success': False, 'error': 'Invalid upgrade type'})
        
        user_id = session['user_id']
        conn = get_db()
        c = conn.cursor()
    except Exception as e:
        return jsonify({'success': False, 'error': f'Chyba: {str(e)}'}), 500
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    resources = extract_player_resources(state)
    
    # Get current upgrade level
    c.execute('SELECT level FROM upgrades WHERE user_id = ? AND upgrade_type = ?', 
             (user_id, upgrade_type))
    upgrade = c.fetchone()
    current_level = upgrade['level'] if upgrade else 0
    
    # Define upgrade costs
    upgrade_costs = {
        'click_power_1': {'gooncoins': 10, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_power_2': {'gooncoins': 50, 'astma': 5, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'auto_gooncoin': {'gooncoins': 100, 'astma': 10, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'astma_collector': {'gooncoins': 50, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'poharky_collector': {'gooncoins': 75, 'astma': 5, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'mrkev_collector': {'gooncoins': 100, 'astma': 10, 'poharky': 5, 'mrkev': 0, 'uzené': 0},
        'uzené_collector': {'gooncoins': 150, 'astma': 15, 'poharky': 10, 'mrkev': 5, 'uzené': 0},
    }
    
    if upgrade_type not in upgrade_costs:
        conn.close()
        return jsonify({'success': False, 'error': 'Unknown upgrade type'})
    
    cost = upgrade_costs[upgrade_type]
    # Scale cost with level
    multiplier = 1.5 ** current_level
    actual_cost = {
        'gooncoins': cost['gooncoins'] * multiplier,
        'astma': cost['astma'] * multiplier,
        'poharky': cost['poharky'] * multiplier,
        'mrkev': cost['mrkev'] * multiplier,
        'uzené': cost['uzené'] * multiplier
    }
    
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    actual_cost = apply_inflation_to_cost(actual_cost, inflation_multiplier)
    
    # Handle migration - get old or new values
    current_astma = state['astma'] if 'astma' in state.keys() else (state['wood'] if 'wood' in state.keys() else 0)
    current_poharky = state['poharky'] if 'poharky' in state.keys() else (state['water'] if 'water' in state.keys() else 0)
    current_mrkev = state['mrkev'] if 'mrkev' in state.keys() else (state['fire'] if 'fire' in state.keys() else 0)
    current_uzené = state['uzené'] if 'uzené' in state.keys() else (state['earth'] if 'earth' in state.keys() else 0)
    
    # Check if player can afford
    if (state['gooncoins'] < actual_cost['gooncoins'] or
        current_astma < actual_cost['astma'] or
        current_poharky < actual_cost['poharky'] or
        current_mrkev < actual_cost['mrkev'] or
        current_uzené < actual_cost['uzené']):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáte dostatek zdrojů'})
    
    try:
        # Deduct costs
        new_gooncoins = state['gooncoins'] - actual_cost['gooncoins']
        new_astma = current_astma - actual_cost['astma']
        new_poharky = current_poharky - actual_cost['poharky']
        new_mrkev = current_mrkev - actual_cost['mrkev']
        new_uzené = current_uzené - actual_cost['uzené']
        
        # Update upgrade level
        if upgrade:
            c.execute('''UPDATE upgrades SET level = level + 1 
                         WHERE user_id = ? AND upgrade_type = ?''',
                     (user_id, upgrade_type))
        else:
            c.execute('INSERT INTO upgrades (user_id, upgrade_type, level) VALUES (?, ?, 1)',
                     (user_id, upgrade_type))
        
        # Update game state
        c.execute('''UPDATE game_state 
                     SET gooncoins = ?, astma = ?, poharky = ?, mrkev = ?, uzené = ?, last_update = CURRENT_TIMESTAMP
                     WHERE user_id = ?''',
                 (new_gooncoins, new_astma, new_poharky, new_mrkev, new_uzené, user_id))
        
        conn.commit()
        conn.close()
        
        refresh_economy_after_change()
        
        return jsonify({
            'success': True,
            'new_level': current_level + 1,
            'gooncoins': new_gooncoins,
            'astma': new_astma,
            'poharky': new_poharky,
            'mrkev': new_mrkev,
            'uzené': new_uzené
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': f'Chyba při nákupu upgradů: {str(e)}'}), 500

@app.route('/api/leaderboard')
def leaderboard():
    conn = get_db()
    c = conn.cursor()
    
    # Get top players by gooncoins
    c.execute('''SELECT u.username, gs.gooncoins, gs.total_clicks
                 FROM users u
                 JOIN game_state gs ON u.id = gs.user_id
                 ORDER BY gs.gooncoins DESC
                 LIMIT 10''')
    
    leaders = [{'username': row['username'], 
                'gooncoins': row['gooncoins'], 
                'total_clicks': row['total_clicks']} 
               for row in c.fetchall()]
    
    conn.close()
    return jsonify(leaders)

# Equipment definitions - using actual image filenames from obrazky folder
# unlock_requirement: {'equipment_id': count} - odemkne se když máš X kusů daného equipmentu
EQUIPMENT_DEFS = {
    'sword_basic': {
        'name': 'Základní Meč',
        'slot': 'weapon',
        'bonus': {'click_power': 1.2},
        'cost': {'gooncoins': 100},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 10,
        'release_order': 1
    },
    'sword_iron': {
        'name': 'Železný Meč',
        'slot': 'weapon',
        'bonus': {'click_power': 1.5},
        'cost': {'gooncoins': 500, 'astma': 10},
        'image': 'lugog.png',
        'unlock_requirement': {'sword_basic': 5},
        'rarity': 'rare',
        'power': 20,
        'release_order': 2
    },
    'armor_leather': {
        'name': 'Kožená Zbroj',
        'slot': 'armor',
        'bonus': {'defense': 1.1},
        'cost': {'gooncoins': 200, 'poharky': 5},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 12,
        'release_order': 3
    },
    'helmet_basic': {
        'name': 'Základní Helma',
        'slot': 'helmet',
        'bonus': {'defense': 1.05},
        'cost': {'gooncoins': 150},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 9,
        'release_order': 4
    },
    'ring_power': {
        'name': 'Prsten Síly',
        'slot': 'ring',
        'bonus': {'click_power': 1.3},
        'cost': {'gooncoins': 300, 'mrkev': 3},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 18,
        'release_order': 5
    },
    'amulet_luck': {
        'name': 'Amulet Štěstí',
        'slot': 'amulet',
        'bonus': {'luck': 1.2},
        'cost': {'gooncoins': 400, 'uzené': 2},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 18,
        'release_order': 6
    },
    'kmochova': {
        'name': 'Kmochova',
        'slot': 'special',
        'bonus': {'click_power': 1.8, 'luck': 1.3},
        'cost': {'gooncoins': 1000, 'astma': 50, 'poharky': 20},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 35,
        'release_order': 7
    },
    'arkadovka': {
        'name': 'Arkadovka',
        'slot': 'special',
        'bonus': {'click_power': 2.0},
        'cost': {'gooncoins': 1500, 'mrkev': 30},
        'image': 'lugog.png',
        'unlock_requirement': {'amulet_luck': 10},
        'rarity': 'epic',
        'power': 40,
        'release_order': 8
    },
    'sony': {
        'name': 'Sony',
        'slot': 'accessory',
        'bonus': {'luck': 1.5},
        'cost': {'gooncoins': 800, 'poharky': 15},
        'image': 'sony.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 22,
        'release_order': 9
    },
    'samsung': {
        'name': 'Samsung',
        'slot': 'accessory',
        'bonus': {'click_power': 1.6},
        'cost': {'gooncoins': 900, 'astma': 25},
        'image': 'Samsung.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 24,
        'release_order': 10
    },
    'opel': {
        'name': 'Opel',
        'slot': 'vehicle',
        'bonus': {'defense': 1.4, 'luck': 1.2},
        'cost': {'gooncoins': 2000, 'uzené': 10},
        'image': 'opel.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 32,
        'release_order': 11
    },
    'realme': {
        'name': 'Realme',
        'slot': 'accessory',
        'bonus': {'click_power': 1.4},
        'cost': {'gooncoins': 700, 'mrkev': 20},
        'image': 'realme.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 20,
        'release_order': 12
    },
    'inhalator': {
        'name': 'Inhalator',
        'slot': 'accessory',
        'bonus': {'defense': 1.3},
        'cost': {'gooncoins': 600, 'astma': 40},
        'image': 'inhalator.png',
        'unlock_requirement': {'arkadovka': 10},
        'rarity': 'epic',
        'power': 28,
        'release_order': 13
    },
    'vivobook': {
        'name': 'Vivobook',
        'slot': 'accessory',
        'bonus': {'click_power': 1.7, 'luck': 1.1},
        'cost': {'gooncoins': 1200, 'poharky': 25},
        'image': 'vivobook.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 30,
        'release_order': 14
    },
    'o2pody': {
        'name': 'O2 Pody',
        'slot': 'accessory',
        'bonus': {'luck': 1.4},
        'cost': {'gooncoins': 500, 'astma': 30},
        'image': 'o2pods.png',
        'unlock_requirement': {'mulet': 5},
        'rarity': 'rare',
        'power': 19,
        'release_order': 15
    },
    'switzerland_ponozky': {
        'name': 'Switzerland Ponozky',
        'slot': 'accessory',
        'bonus': {'defense': 1.2},
        'cost': {'gooncoins': 400, 'poharky': 10},
        'image': 'switzerlandPonozky.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 16,
        'release_order': 16
    },
    'mulet': {
        'name': 'Mulet',
        'slot': 'accessory',
        'bonus': {'click_power': 1.3},
        'cost': {'gooncoins': 350, 'mrkev': 15},
        'image': 'mulet.png',
        'unlock_requirement': {'kmochova': 10},
        'rarity': 'rare',
        'power': 17,
        'release_order': 17
    },
    'bunda_po_dedovi': {
        'name': 'Bunda po Dědovi',
        'slot': 'armor',
        'bonus': {'defense': 1.5, 'luck': 1.1},
        'cost': {'gooncoins': 1100, 'uzené': 5},
        'image': 'BundaPoDedovi.png',
        'unlock_requirement': {'jordan_mikina': 10},
        'rarity': 'epic',
        'power': 34,
        'release_order': 18
    },
    'valley_cepice': {
        'name': 'Valley Čepice',
        'slot': 'helmet',
        'bonus': {'defense': 1.3, 'click_power': 1.1},
        'cost': {'gooncoins': 800, 'poharky': 18},
        'image': 'valleyCepice.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 23,
        'release_order': 19
    },
    'jordan_mikina': {
        'name': 'Jordan Mikina',
        'slot': 'armor',
        'bonus': {'defense': 1.4, 'click_power': 1.2},
        'cost': {'gooncoins': 1300, 'mrkev': 25},
        'image': 'JordanMikina.png',
        'unlock_requirement': {'inhalator': 10},
        'rarity': 'epic',
        'power': 36,
        'release_order': 20
    },
    'skrinka_244': {
        'name': 'Skříňka 244',
        'slot': 'special',
        'bonus': {'luck': 2.0, 'defense': 1.3},
        'cost': {'gooncoins': 2500, 'uzené': 15, 'poharky': 30},
        'image': 'skrinka244.png',
        'unlock_requirement': {'samsung': 10},
        'rarity': 'unique',
        'power': 60,
        'release_order': 21
    },
    'rezava_katana': {
        'name': 'Rezavá Katana',
        'slot': 'weapon',
        'bonus': {'click_power': 2.3},
        'cost': {'gooncoins': 2500, 'astma': 40, 'mrkev': 25},
        'image': 'lugog.png',
        'unlock_requirement': {'sword_iron': 5},
        'rarity': 'legendary',
        'power': 45,
        'release_order': 22
    },
    'kevlar_vesta': {
        'name': 'Kevlarová Vesta',
        'slot': 'armor',
        'bonus': {'defense': 1.9, 'luck': 1.05},
        'cost': {'gooncoins': 2100, 'poharky': 22, 'uzené': 12},
        'image': 'lugog.png',
        'unlock_requirement': {'bunda_po_dedovi': 5},
        'rarity': 'legendary',
        'power': 48,
        'release_order': 23
    },
    'koruna_lugogu': {
        'name': 'Koruna Lugogu',
        'slot': 'helmet',
        'bonus': {'defense': 1.6, 'luck': 1.4},
        'cost': {'gooncoins': 2300, 'poharky': 32, 'mrkev': 12},
        'image': 'lugog.png',
        'unlock_requirement': {'valley_cepice': 3},
        'rarity': 'unique',
        'power': 55,
        'release_order': 24
    },
    'zlaty_retez': {
        'name': 'Zlatý Řetěz',
        'slot': 'amulet',
        'bonus': {'luck': 1.7, 'click_power': 1.15},
        'cost': {'gooncoins': 2400, 'poharky': 40, 'uzené': 6},
        'image': 'lugog.png',
        'unlock_requirement': {'amulet_luck': 7},
        'rarity': 'legendary',
        'power': 42,
        'release_order': 25
    },
    'chytry_prsten': {
        'name': 'Chytrý Prsten',
        'slot': 'ring',
        'bonus': {'luck': 1.5, 'click_power': 1.25},
        'cost': {'gooncoins': 2000, 'astma': 25, 'mrkev': 18},
        'image': 'lugog.png',
        'unlock_requirement': {'ring_power': 5},
        'rarity': 'legendary',
        'power': 40,
        'release_order': 26
    },
    'vr_bryle': {
        'name': 'VR Brýle',
        'slot': 'accessory',
        'bonus': {'luck': 1.55, 'click_power': 1.1},
        'cost': {'gooncoins': 1600, 'astma': 20, 'poharky': 15},
        'image': 'lugog.png',
        'unlock_requirement': {'sony': 5},
        'rarity': 'epic',
        'power': 33,
        'release_order': 27
    },
    'turbo_hoverboard': {
        'name': 'Turbo Hoverboard',
        'slot': 'vehicle',
        'bonus': {'click_power': 1.35, 'luck': 1.7, 'defense': 1.1},
        'cost': {'gooncoins': 3500, 'poharky': 45, 'uzené': 20},
        'image': 'lugog.png',
        'unlock_requirement': {'opel': 5},
        'rarity': 'unique',
        'power': 58,
        'release_order': 28
    }
}

def make_quest(quest_id, name, description, requirement, reward=None, unlocks=None, optional=False):
    quest = {
        'id': quest_id,
        'name': name,
        'description': description,
        'requirement': requirement or {},
        'reward': reward or {}
    }
    if unlocks:
        quest['unlocks'] = unlocks
    if optional:
        quest['optional'] = True
    return quest

# Story chapters and quests
STORY_CHAPTERS = {
    1: {
        'title': 'Začátek Cesty',
        'description': 'Lugog se probouzí v panelácích Kmochovy čtvrti. Každé kliknutí rozžíná staré neonky a přivolává první proud Gooncoinů.',
        'quests': [
            make_quest('first_click', 'První Kliknutí', 'Probuď systém prvním kliknutím do Lugoga.', {'total_clicks': 1}, {'gooncoins': 10}),
            make_quest('first_100', 'Prvních 100', 'Nasbírej 100 Gooncoinů, aby se panelák nadechl nového života.', {'gooncoins': 100}, {'gooncoins': 50}, ['astma']),
            make_quest('click_combo', 'Klikací Kombajn', 'Rozjeď prsty – dosáhni 250 kliknutí.', {'total_clicks': 250}, {'gooncoins': 75}),
            make_quest('starter_cache', 'Základní Fond', 'Nashromáždi 500 Gooncoinů pro první investice.', {'gooncoins': 500}, {'astma': 15}),
            make_quest('first_building', 'První Budova', 'Postav Dílna a připrav stůl pro další dobrodruhy.', {'buildings': ['workshop']}, {'gooncoins': 200}),
            make_quest('speedrunner', 'Klikací Sprinter', 'Vyklikni 1000 kliknutí bez ohledu na mozoly.', {'total_clicks': 1000}, {'gooncoins': 200}, optional=True),
            make_quest('rookie_hoarder', 'Panelákový Hamoun', 'Udrž 250 Gooncoinů v zásobě a neutrať ani korunu navíc.', {'gooncoins': 250}, {'astma': 5}, optional=True)
        ]
    },
    2: {
        'title': 'Objevování Astma',
        'description': 'Astmatická mlha voní po uzeném a pohárky tečou proudem. Obyvatelé Lugogu chtějí dýchat rychleji a vyrábět lepší gear.',
        'quests': [
            make_quest('collect_astma', 'Sběr Astma', 'Nasbírej 50 Astma a rozfoukej prach ze starých inhalátorů.', {'astma': 50}, {'astma': 20}, ['poharky']),
            make_quest('collect_poharky', 'Sběr Pohárků', 'Naplň 30 pohárků a zjisti, kdo drží hospodský trůn.', {'poharky': 30}, {'poharky': 10}, ['mrkev']),
            make_quest('collect_mrkev', 'Sběr Mrkve', 'Mrkev z polí Lugogu dodá očím ostrost. Nasbírej jí 20.', {'mrkev': 20}, {'mrkev': 5}, ['uzené']),
            make_quest('first_equipment', 'První Equipment', 'Vyrob si první equipment a obleč se do legend.', {'equipment_count': 1}, {'gooncoins': 300}),
            make_quest('arkadovka_master', 'Král Arkadovek', 'Vyrob 10× Arkadovka a rozjeď herní maraton.', {'equipment_owned': {'arkadovka': 10}}, {'poharky': 25}, optional=True),
            make_quest('inhalator_guru', 'Inhalátor Guru', 'Vyrob 10× Inhalator a rozdávej klidný dech.', {'equipment_owned': {'inhalator': 10}}, {'astma': 40}, optional=True),
            make_quest('jordan_collector', 'Jordan Kolekce', 'Vyrob 10× Jordan Mikina pro celou squad.', {'equipment_owned': {'jordan_mikina': 10}}, {'mrkev': 40}, optional=True),
            make_quest('deduv_wardrobe', 'Dědův Šatník', 'Nasbírej 10× Bunda po Dědovi a obleč panelákovou gardu.', {'equipment_owned': {'bunda_po_dedovi': 10}}, {'uzené': 25}, optional=True),
            make_quest('crafting_frenzy', 'Výrobní Šílenství', 'Udrž současně 6 kusů vybavení.', {'equipment_count': 6}, {'gooncoins': 600}, optional=True)
        ]
    },
    3: {
        'title': 'Citadela Paneláku 244',
        'description': 'Když se chodby 244 znovu rozzáří, Lugog potřebuje zásobování, obchodníky a ozbrojenou eskortu.',
        'quests': [
            make_quest('market_blueprints', 'Plány Tržiště', 'Doruč 35 Pohárků a 10 Uzeného stavební radě a získej povolení k Tržišti.', {'poharky': 35, 'uzené': 10}, {'gooncoins': 500}, ['market']),
            make_quest('build_market', 'Tržnice ožívá', 'Postav Tržiště, aby se zboží dostalo z výtahů až na střechu.', {'buildings': ['market']}, {'gooncoins': 800}),
            make_quest('temple_permit', 'Chrámové Pověření', 'Získej požehnání rady – přines 40 Pohárků a 3000 Gooncoinů.', {'poharky': 40, 'gooncoins': 3000}, {'poharky': 15}, ['temple']),
            make_quest('sacred_blueprint', 'Posvěcené výkresy', 'Postav Dílna, Tržiště i Chrám – panelák musí fungovat jako jeden celek.', {'buildings': ['workshop', 'market', 'temple']}, {'gooncoins': 1500}),
            make_quest('smokehouse_supreme', 'Mistr Uzenář', 'Nasbírej 60 Uzeného pro noční hostinu.', {'uzené': 60}, {'uzené': 20}, optional=True),
            make_quest('opel_convoy', 'Opel Konvoj', 'Vyrob 5 vozidel Opel a doprav zásoby bezpečně domů.', {'equipment_owned': {'opel': 5}}, {'poharky': 40}, optional=True),
            make_quest('citadel_stockpile', 'Citadela Skaldí zásoby', 'Drž 8000 Gooncoinů a 50 Uzeného pro případ obléhání.', {'gooncoins': 8000, 'uzené': 50}, {'mrkev': 30}, optional=True),
            make_quest('armored_procession', 'Opevněný průvod', 'Získej 2× Rezavá Katana a 2× Kevlarová Vesta.', {'equipment_owned': {'rezava_katana': 2, 'kevlar_vesta': 2}}, {'uzené': 30}, optional=True)
        ]
    },
    4: {
        'title': 'Legenda Plechových Bohů',
        'description': 'Ze střechy je vidět celé Lugogovo údolí. Poslední kapitola prověří tvoji výdrž, zásoby i víru.',
        'quests': [
            make_quest('click_master', 'Klikací Maestro', 'Získej 50 000 kliknutí a udrž systém vzhůru celou noc.', {'total_clicks': 50000}, {'gooncoins': 5000}),
            make_quest('final_blessing', 'Noc Požehnání', 'Připrav 120 Mrkví a 80 Uzeného pro chrámové obřady.', {'mrkev': 120, 'uzené': 80}, {'gooncoins': 4000}),
            make_quest('wealth_of_lugog', 'Poklad Lugogu', 'Nasbírej 75 000 Gooncoinů pro obnovu paneláku.', {'gooncoins': 75000}, {'mrkev': 80}),
            make_quest('skrinka_legend', 'Skříňka Legend', 'Získej 1× Skříňka 244 a odemkni tajemství schovaná za šedým plechem.', {'equipment_owned': {'skrinka_244': 1}}, {'uzené': 40}, optional=True),
            make_quest('amulet_conclave', 'Konkláve Amuletů', 'Nasbírej 10× Amulet Štěstí a rozdej požehnání každému patru.', {'equipment_owned': {'amulet_luck': 10}}, {'astma': 80}, optional=True),
            make_quest('hoverboard_fleet', 'Letka Hoverboardů', 'Vyrob 3× Turbo Hoverboard pro střechové hlídky.', {'equipment_owned': {'turbo_hoverboard': 3}}, {'poharky': 60}, optional=True),
            make_quest('crown_collection', 'Lugogova Korunovace', 'Získej 1× Koruna Lugogu a ukaž, kdo vládne paneláku.', {'equipment_owned': {'koruna_lugogu': 1}}, {'uzené': 50}, optional=True)
        ]
    }
}

LORE_ENTRIES = [
    {
        'id': 'kronika_kliknuti',
        'title': 'Kronika Prvního Kliknutí',
        'era': 'Éra Probuzení',
        'summary': 'Panelák 244 býval jen šedou kulisou. První klik změnil beton v živou konzoli.',
        'body': [
            'Když Lugog poprvé zazářil, nikdo si nebyl jistý, jestli jde o chybu v síti, nebo pozvánku. Metalické cvaknutí se rozběhlo po radiátorech a přepsalo pravidla noci.',
            'Staří správci paneláku tvrdí, že každý Gooncoin je vlastně vzpomínka. Čím víc jich držíš, tím hlasitěji mluví chodby a tím jasněji víš, kam kliknout dál.'
        ],
        'required_chapter': 1
    },
    {
        'id': 'astmaticka_mlha',
        'title': 'Astmatická Mlha',
        'era': 'Mlhy a Inhalátory',
        'summary': 'Astma je víc než jen inhalátor – je to měna, která kupuje čas a dech.',
        'body': [
            'V laboratořích pod panelákem se míchá astmatická mlha s uzeným kouřem. Dýcháš ji, aby ses pohyboval rychleji, ale taky abys vydržel nekonečné klikání bez křečí.',
            'Pohárky z hospod Lugogu se naplňují destilovanou mrkví. Bez jejich žáru se žádný upgrade nespustí a žádná Arkaďárna neotevře dveře.'
        ],
        'required_chapter': 2
    },
    {
        'id': 'strojovna_klikani',
        'title': 'Strojovna Klikání',
        'era': 'Kabely a Rytmy',
        'summary': 'V suterénu paneláku běží stroj, který přepisuje každý klik a drží Lugog vzhůru.',
        'body': [
            'Strojovna je spleť kabelů, které cvakají jako orchestr. Každý hráč tu nechává otisk dlaně, aby kliky dostaly jedinečný rytmus a nedalo se je napodobit.',
            'Metronomové paneláku hlídají, aby frekvence neklesla. Když rytmus zaváhá, rozsvítí se červená světla a veškerá výroba se zpomalí, dokud někdo nepřinese čerstvé pohárky.'
        ],
        'required_chapter': 2
    },
    {
        'id': 'citadela_244',
        'title': 'Citadela 244',
        'era': 'Zlaté patro',
        'summary': 'Panelák 244 je pevnost, která se skládá z dílen, tržnic a tajných kaplí.',
        'body': [
            'Dílna je srdce, Tržiště plíce a Chrám nervová soustava Lugogu. Každé patro má svého správce a každý správce hlídá, aby výtahy jezdily jen těm, kteří platí Gooncoinem.',
            'Opel konvoje projíždějí mezi paneláky, aby přivezly mrkev z polí a uzené z komínů. Když se konvoj zastaví, přestane růst i tvá legenda.'
        ],
        'required_chapter': 3
    },
    {
        'id': 'balkonova_hradba',
        'title': 'Balkonová Hradba',
        'era': 'Obrana Kulisy',
        'summary': 'Balkony 244 vytvářejí mozaiku stráží, která chrání zásoby i legendy.',
        'body': [
            'Každý balkon slouží jako hláska. Z provazů visí amulety štěstí a kovové šňůry, které přenášejí signály do strojovny. Pokud se kabely rozechvějí, ví se, že někdo porušil klikací pořádek.',
            'Na balkonech se také suší uzené a mrkev; když zásoby mizí, správci spustí sirénu a všechny výtahy zamknou, dokud hráči nesplní nový úkol.'
        ],
        'required_chapter': 3
    },
    {
        'id': 'plechovi_bohove',
        'title': 'Plechoví Bohové',
        'era': 'Noční střechy',
        'summary': 'Na střeše paneláku sídlí digitální bohové. Naslouchají, jen když cvakají všechny klikátka najednou.',
        'body': [
            'Chrám není stavba, ale signál. Když vlastníš Skříňku 244, slyšíš šepot plechových bohů a dokážeš přenastavit celý Lugog jedním příkazem.',
            'Konkláve Amuletů je obřad, při kterém se desítky Amuletů Štěstí zavěsí na telefonní kabely nad střechou. Pokud kabely zazvoní, víš, že jsi paneláku dopřál nový příběh.'
        ],
        'required_chapter': 4
    }
]

# Building definitions
BUILDINGS_DEFS = {
    'lumberjack_hut': {
        'order': 1,
        'category': 'production',
        'name': 'Dřevorubecká chata',
        'description': 'Seká kmeny, ale jen pokud máš postavenou cestu pro nosiče.',
        'cost': {'gooncoins': 150},
        'always_available': True,
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 24,
            'routes': ['forest_route'],
            'outputs': {'logs': 1}
        },
        'unlock_currencies': ['logs']
    },
    'forest_route': {
        'order': 2,
        'category': 'logistics',
        'name': 'Lesní stezka',
        'description': 'Každý úsek má jednoho nosiče. Spojí dřevorubce se skladem.',
        'cost': {'gooncoins': 120},
        'always_available': True,
        'logistics': {
            'kind': 'route',
            'segments': 3,
            'connects': ['lumberjack_hut', 'sawmill']
        }
    },
    'sawmill': {
        'order': 3,
        'category': 'production',
        'name': 'Pila',
        'description': 'Z klád vyrábí prkna. Potřebuje stejnou cestu tam i zpět.',
        'cost': {'gooncoins': 250, 'logs': 10},
        'prerequisites': ['lumberjack_hut', 'forest_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 28,
            'routes': ['forest_route', 'plank_route'],
            'inputs': {'logs': 1},
            'outputs': {'planks': 1}
        },
        'unlock_currencies': ['planks']
    },
    'plank_route': {
        'order': 4,
        'category': 'logistics',
        'name': 'Trámy k výtahu',
        'description': 'Krátké rameno, které odvádí prkna do paneláku.',
        'cost': {'gooncoins': 140, 'logs': 8},
        'prerequisites': ['sawmill'],
        'logistics': {
            'kind': 'route',
            'segments': 2,
            'connects': ['sawmill', 'workshop']
        }
    },
    'farmstead': {
        'order': 5,
        'category': 'production',
        'name': 'Farma na obilí',
        'description': 'Farmář pěstuje obilí a posílá pytle po vyznačených trasách.',
        'cost': {'gooncoins': 180},
        'prerequisites': ['lumberjack_hut'],
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 30,
            'routes': ['field_route'],
            'outputs': {'grain': 1}
        },
        'unlock_currencies': ['grain']
    },
    'field_route': {
        'order': 6,
        'category': 'logistics',
        'name': 'Polní rozcestí',
        'description': 'Zajišťuje přenos pytlů s obilím směrem do mlýna.',
        'cost': {'gooncoins': 150},
        'prerequisites': ['farmstead'],
        'logistics': {
            'kind': 'route',
            'segments': 4,
            'connects': ['farmstead', 'mill']
        }
    },
    'mill': {
        'order': 7,
        'category': 'production',
        'name': 'Mlýn',
        'description': 'Z obilí mele mouku, když dorazí pytle a cesta je průchozí.',
        'cost': {'gooncoins': 260, 'grain': 10},
        'prerequisites': ['farmstead', 'field_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 26,
            'routes': ['field_route', 'bakery_route'],
            'inputs': {'grain': 1},
            'outputs': {'flour': 1}
        },
        'unlock_currencies': ['flour']
    },
    'bakery_route': {
        'order': 8,
        'category': 'logistics',
        'name': 'Křižovatka pro pekárnu',
        'description': 'Uzly, kde se potkává mouka, voda a uhlí. Každý směr je vidět.',
        'cost': {'gooncoins': 160, 'planks': 4},
        'prerequisites': ['mill'],
        'logistics': {
            'kind': 'route',
            'segments': 3,
            'connects': ['mill', 'bakery']
        }
    },
    'bakery': {
        'order': 9,
        'category': 'production',
        'name': 'Pekárna',
        'description': 'Pekař čeká, dokud mouka reálně nedorazí. Pak upeče chleba.',
        'cost': {'gooncoins': 320, 'flour': 6},
        'prerequisites': ['bakery_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 32,
            'routes': ['bakery_route'],
            'inputs': {'flour': 1},
            'outputs': {'bread': 1}
        },
        'unlock_currencies': ['bread']
    },
    'fishery': {
        'order': 10,
        'category': 'production',
        'name': 'Rybářská chata',
        'description': 'Rybář chytá ryby a nosiči je nosí po molu nahoru.',
        'cost': {'gooncoins': 210, 'planks': 4},
        'prerequisites': ['plank_route'],
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 28,
            'routes': ['dock_route'],
            'outputs': {'fish': 1}
        },
        'unlock_currencies': ['fish']
    },
    'dock_route': {
        'order': 11,
        'category': 'logistics',
        'name': 'Přístavní molo',
        'description': 'Segmenty mola, které dovedou košíky z vody až na střechu.',
        'cost': {'gooncoins': 130, 'planks': 4},
        'prerequisites': ['fishery'],
        'logistics': {
            'kind': 'route',
            'segments': 4,
            'connects': ['fishery', 'market']
        }
    },
    'courier_guild': {
        'order': 12,
        'category': 'support',
        'name': 'Cech nosičů',
        'description': 'Přidává na každou cestu dalšího nosiče. Level = počet směn denně.',
        'cost': {'gooncoins': 280, 'planks': 6, 'bread': 2},
        'prerequisites': ['forest_route'],
        'repeatable': True,
        'max_level': 5,
        'level_cost_multiplier': 1.6,
        'logistics': {
            'kind': 'support',
            'speed_bonus': 0.15
        }
    },
    'workshop': {
        'order': 20,
        'category': 'infrastructure',
        'name': 'Dílna',
        'description': 'Umožňuje craftění equipmentu – funguje jen, pokud proudí prkna.',
        'cost': {'gooncoins': 500, 'planks': 12, 'bread': 2},
        'prerequisites': ['sawmill', 'plank_route'],
        'unlocks': ['crafting']
    },
    'market': {
        'order': 21,
        'category': 'infrastructure',
        'name': 'Tržiště',
        'description': 'Otevře měnový trh a propojí logistiku s ekonomikou.',
        'cost': {'gooncoins': 1000, 'planks': 8, 'bread': 6, 'fish': 6},
        'prerequisites': ['bakery', 'fishery'],
        'unlocks': ['trading'],
        'unlock_currencies': TRADEABLE_CURRENCIES
    },
    'temple': {
        'order': 22,
        'category': 'infrastructure',
        'name': 'Chrám',
        'description': 'Otevírá chrámové místnosti, požehnání a speciální bojové eventy.',
        'cost': {'gooncoins': 2000, 'poharky': 10, 'bread': 12, 'fish': 6},
        'prerequisites': ['market'],
        'unlocks': ['blessings']
    }
}

LOGISTICS_CHAIN_DEFS = [
    {
        'id': 'wood_chain',
        'name': 'Dřevo → Prkna',
        'steps': ['lumberjack_hut', 'forest_route', 'sawmill', 'plank_route']
    },
    {
        'id': 'bread_chain',
        'name': 'Obilí → Chleba',
        'steps': ['farmstead', 'field_route', 'mill', 'bakery_route', 'bakery']
    },
    {
        'id': 'harbor_chain',
        'name': 'Rybář → Tržiště',
        'steps': ['fishery', 'dock_route', 'market']
    }
]

LOGISTICS_SEGMENT_TIME = 6.0


def _build_logistic_support(buildings):
    support = {'speed_bonus': 0.0}
    for building_id, level in (buildings or {}).items():
        if not level:
            continue
        building_def = BUILDINGS_DEFS.get(building_id, {})
        logistics_meta = building_def.get('logistics') or {}
        if logistics_meta.get('kind') != 'support':
            continue
        bonus = logistics_meta.get('speed_bonus', 0.0) * level
        support['speed_bonus'] = support.get('speed_bonus', 0.0) + bonus
    support['speed_multiplier'] = 1 + support.get('speed_bonus', 0.0)
    return support


def evaluate_logistics(resources, buildings, time_window=1.0, mutate=False):
    time_factor = max(time_window, 1e-6)
    working_resources = resources if mutate else clone_resources(resources)
    logistic_rates = {key: 0.0 for key in SECONDARY_RESOURCES}
    snapshot = {
        'support': {},
        'routes': {},
        'processes': {}
    }
    buildings = buildings or {}
    support = _build_logistic_support(buildings)
    snapshot['support'] = support
    
    for building_id, building_def in BUILDINGS_DEFS.items():
        logistics_meta = building_def.get('logistics')
        if not logistics_meta or logistics_meta.get('kind') != 'route':
            continue
        snapshot['routes'][building_id] = {
            'segments': logistics_meta.get('segments', 0),
            'connects': logistics_meta.get('connects', []),
            'built': buildings.get(building_id, 0) > 0
        }
    
    for building_id, building_def in BUILDINGS_DEFS.items():
        logistics_meta = building_def.get('logistics')
        if not logistics_meta or logistics_meta.get('kind') != 'process':
            continue
        level = buildings.get(building_id, 0)
        process_state = {
            'level': level,
            'role': logistics_meta.get('role'),
            'routes': logistics_meta.get('routes', []),
            'blocked_reason': None,
            'active': False,
            'cycle_time': logistics_meta.get('base_cycle', 30),
            'per_second': {},
            'storage': {}
        }
        snapshot['processes'][building_id] = process_state
        route_ids = process_state['routes']
        if level <= 0:
            process_state['blocked_reason'] = 'unbuilt'
            continue
        missing_route = next((route_id for route_id in route_ids if buildings.get(route_id, 0) <= 0), None)
        if missing_route:
            process_state['blocked_reason'] = f'missing_route:{missing_route}'
            continue
        cycle_time = logistics_meta.get('base_cycle', 30)
        for route_id in route_ids:
            route_def = BUILDINGS_DEFS.get(route_id, {})
            route_meta = route_def.get('logistics', {})
            segments = route_meta.get('segments', 0)
            cycle_time += (segments * LOGISTICS_SEGMENT_TIME) / max(0.2, support.get('speed_multiplier', 1.0))
        process_state['cycle_time'] = cycle_time
        cycles_available = (time_window / cycle_time) * level if time_window > 0 else 0
        inputs = logistics_meta.get('inputs', {})
        if inputs:
            for resource, amount in inputs.items():
                if amount <= 0:
                    continue
                available = working_resources.get(resource, 0)
                possible = available / amount if amount else cycles_available
                cycles_available = min(cycles_available, possible)
        if cycles_available <= 0:
            process_state['blocked_reason'] = 'no_inputs' if inputs else 'waiting'
            continue
        # Deduct inputs
        for resource, amount in inputs.items():
            if amount <= 0:
                continue
            working_resources[resource] = max(0, working_resources.get(resource, 0) - amount * cycles_available)
        outputs = logistics_meta.get('outputs', {})
        for resource, amount in outputs.items():
            if amount <= 0:
                continue
            produced = amount * cycles_available
            working_resources[resource] = working_resources.get(resource, 0) + produced
            logistic_rates[resource] = logistic_rates.get(resource, 0) + produced / time_factor
            process_state['per_second'][resource] = produced / time_factor
        process_state['active'] = True
        tracked_resources = set(inputs.keys()) | set(outputs.keys())
        process_state['storage'] = {res: working_resources.get(res, 0) for res in tracked_resources}
    
    return working_resources, logistic_rates, snapshot

CASE_DEFINITIONS = {
    'panelak_basic': {
        'name': 'Paneláková Bedna',
        'icon': '📦',
        'description': 'Základní balíček z kotelny 244. Dropne Gooncoiny i street gear.',
        'tagline': 'Šance na Arkadovku nebo Rezavou Katanu.',
        'price': 750,
        'currency': 'gooncoins',
        'order': 1,
        'items': [
            {
                'id': 'panelak_coins_small',
                'type': 'currency',
                'name': 'Balík Gooncoinů',
                'description': '+450 Gooncoinů',
                'rarity': 'common',
                'icon': '💰',
                'weight': 40,
                'payout': {'resources': {'gooncoins': 450}}
            },
            {
                'id': 'panelak_coins_big',
                'type': 'currency',
                'name': 'Prémiový balík Gooncoinů',
                'description': '+950 Gooncoinů',
                'rarity': 'rare',
                'icon': '💰',
                'weight': 20,
                'payout': {'resources': {'gooncoins': 950}}
            },
            {
                'id': 'panelak_arkadovka',
                'type': 'equipment',
                'name': 'Arkadovka',
                'description': 'Retro konzole z klubovny.',
                'rarity': 'rare',
                'icon': '🕹️',
                'weight': 14,
                'payout': {'equipment_id': 'arkadovka', 'amount': 1}
            },
            {
                'id': 'panelak_inhalator',
                'type': 'equipment',
                'name': 'Inhalátor',
                'description': 'Astmatická aura + styl.',
                'rarity': 'rare',
                'icon': '💨',
                'weight': 10,
                'payout': {'equipment_id': 'inhalator', 'amount': 1}
            },
            {
                'id': 'panelak_bunda',
                'type': 'equipment',
                'name': 'Bunda po Dědovi',
                'description': 'Panelákový drip, který jen tak nepadá.',
                'rarity': 'epic',
                'icon': '🧥',
                'weight': 8,
                'payout': {'equipment_id': 'bunda_po_dedovi', 'amount': 1}
            },
            {
                'id': 'panelak_katana',
                'type': 'equipment',
                'name': 'Rezavá Katana',
                'description': 'Ikona nočních výprav.',
                'rarity': 'legendary',
                'icon': '⚔️',
                'weight': 5,
                'payout': {'equipment_id': 'rezava_katana', 'amount': 1}
            },
            {
                'id': 'panelak_hover',
                'type': 'equipment',
                'name': 'Turbo Hoverboard',
                'description': 'Vstupenka na střechu 244.',
                'rarity': 'legendary',
                'icon': '🛹',
                'weight': 3,
                'payout': {'equipment_id': 'turbo_hoverboard', 'amount': 1}
            }
        ]
    },
    'rooftop_elite': {
        'name': 'Střešní Legendy',
        'icon': '🎇',
        'description': 'Luxusní bedna s dropy z chrámu, střechy i tajných skrýší.',
        'tagline': 'Legendární gear + šance na vzácné materiály.',
        'price': 3200,
        'currency': 'gooncoins',
        'order': 2,
        'items': [
            {
                'id': 'rooftop_coin_rain',
                'type': 'currency',
                'name': 'Déšť Gooncoinů',
                'description': '+3 200 Gooncoinů',
                'rarity': 'rare',
                'icon': '💸',
                'weight': 25,
                'payout': {'resources': {'gooncoins': 3200}}
            },
            {
                'id': 'rooftop_opel',
                'type': 'equipment',
                'name': 'Opel Konvoj',
                'description': 'Panelákový dopravní symbol.',
                'rarity': 'epic',
                'icon': '🚐',
                'weight': 20,
                'payout': {'equipment_id': 'opel', 'amount': 1}
            },
            {
                'id': 'rooftop_kevlar',
                'type': 'equipment',
                'name': 'Kevlarová Vesta',
                'description': 'Pro noční patro patrol.',
                'rarity': 'legendary',
                'icon': '🛡️',
                'weight': 15,
                'payout': {'equipment_id': 'kevlar_vesta', 'amount': 1}
            },
            {
                'id': 'rooftop_hover',
                'type': 'equipment',
                'name': 'Turbo Hoverboard',
                'description': 'Rychlá linka mezi střechami.',
                'rarity': 'legendary',
                'icon': '🛹',
                'weight': 12,
                'payout': {'equipment_id': 'turbo_hoverboard', 'amount': 1}
            },
            {
                'id': 'rooftop_totem',
                'type': 'rare_material',
                'name': 'Mrkvový Totem',
                'description': 'Rituální drop z chrámu.',
                'rarity': 'epic',
                'icon': '🥕',
                'weight': 10,
                'payout': {'rare_materials': {'mrkvovy_totem': 1}}
            },
            {
                'id': 'rooftop_manifest',
                'type': 'rare_material',
                'name': 'Manifest Jitky',
                'description': 'Syrový text, který otevírá dveře.',
                'rarity': 'legendary',
                'icon': '📜',
                'weight': 8,
                'payout': {'rare_materials': {'jitka_manifest': 1}}
            },
            {
                'id': 'rooftop_crown',
                'type': 'equipment',
                'name': 'Koruna Lugogu',
                'description': 'Nejvyšší možný flex.',
                'rarity': 'unique',
                'icon': '👑',
                'weight': 5,
                'payout': {'equipment_id': 'koruna_lugogu', 'amount': 1}
            },
            {
                'id': 'rooftop_roza_trn',
                'type': 'rare_material',
                'name': 'Rózin Trn',
                'description': 'Tajemný booster chrámu.',
                'rarity': 'legendary',
                'icon': '🌹',
                'weight': 5,
                'payout': {'rare_materials': {'roza_trn': 1}}
            }
        ]
    }
}

def serialize_case_definitions():
    cases = []
    for case_id, definition in CASE_DEFINITIONS.items():
        sanitized_items = []
        for item in definition.get('items', []):
            sanitized_items.append({
                'id': item.get('id'),
                'type': item.get('type'),
                'name': item.get('name'),
                'description': item.get('description'),
                'rarity': item.get('rarity', 'common'),
                'icon': item.get('icon'),
                'weight': item.get('weight', 1),
                'payout': item.get('payout', {})
            })
        cases.append({
            'id': case_id,
            'name': definition.get('name', case_id),
            'icon': definition.get('icon', '🎁'),
            'description': definition.get('description'),
            'tagline': definition.get('tagline'),
            'price': definition.get('price', 0),
            'currency': definition.get('currency', 'gooncoins'),
            'items': sanitized_items,
            'order': definition.get('order', 99)
        })
    cases.sort(key=lambda case_def: case_def.get('order', 99))
    return cases

def pick_case_reward(case_definition):
    items = case_definition.get('items', [])
    if not items:
        return None
    total_weight = sum(max(0, item.get('weight', 1)) for item in items) or 1
    roll = random.uniform(0, total_weight)
    cumulative = 0
    for item in items:
        cumulative += max(0, item.get('weight', 1))
        if roll <= cumulative:
            return item
    return items[-1]

def apply_case_reward(cursor, user_id, balances, reward_item):
    if not reward_item:
        return None, None, 0
    reward_type = reward_item.get('type')
    summary = {
        'id': reward_item.get('id'),
        'name': reward_item.get('name'),
        'type': reward_type,
        'rarity': reward_item.get('rarity', 'common'),
        'icon': reward_item.get('icon', '🎁'),
        'description': reward_item.get('description'),
        'payout': reward_item.get('payout', {})
    }
    reward_id = None
    recorded_amount = 0
    
    if reward_type == 'currency':
        resources = reward_item.get('payout', {}).get('resources', {})
        for key, amount in resources.items():
            if key in balances:
                balances[key] += amount
                reward_id = key
                recorded_amount = amount
        summary['resources'] = resources
    elif reward_type == 'equipment':
        equipment_id = reward_item.get('payout', {}).get('equipment_id')
        amount = int(reward_item.get('payout', {}).get('amount', 1) or 1)
        eq_def = EQUIPMENT_DEFS.get(equipment_id, {})
        slot = eq_def.get('slot', 'special')
        for _ in range(max(1, amount)):
            cursor.execute('''INSERT INTO equipment (user_id, equipment_slot, equipment_id, equipped)
                              VALUES (?, ?, ?, 0)''', (user_id, slot, equipment_id))
        summary['equipment'] = {
            'id': equipment_id,
            'name': eq_def.get('name', equipment_id),
            'amount': amount
        }
        reward_id = equipment_id
        recorded_amount = amount
    elif reward_type == 'rare_material':
        materials = reward_item.get('payout', {}).get('rare_materials', {})
        adjust_rare_materials(cursor, user_id, materials)
        summary['rare_materials'] = materials
        if materials:
            reward_id, recorded_amount = next(iter(materials.items()))
    else:
        summary['extra'] = reward_item.get('payout', {})
    
    return summary, reward_id, recorded_amount

def get_recent_case_history(cursor, user_id, limit=8):
    cursor.execute('''SELECT case_id, reward_type, reward_label, rarity, amount, created_at
                      FROM case_openings
                      WHERE user_id = ?
                      ORDER BY created_at DESC
                      LIMIT ?''', (user_id, limit))
    rows = cursor.fetchall()
    history = []
    for row in rows:
        case_meta = CASE_DEFINITIONS.get(row['case_id'], {})
        history.append({
            'case_id': row['case_id'],
            'case_name': case_meta.get('name', row['case_id']),
            'reward_type': row['reward_type'],
            'reward_label': row['reward_label'],
            'rarity': row['rarity'],
            'amount': row['amount'],
            'created_at': row['created_at']
        })
    return history

@app.route('/api/craft-equipment', methods=['POST'])
def craft_equipment():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    equipment_id = data.get('equipment_id')
    
    if equipment_id not in EQUIPMENT_DEFS:
        return jsonify({'success': False, 'error': 'Neplatný equipment'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    resources = hydrate_state_resources(state)
    
    # Get story to check unlocked currencies
    story = ensure_story_progress(c, user_id)
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    
    equipment_def = EQUIPMENT_DEFS[equipment_id]
    cost = equipment_def['cost']
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    # Check unlock requirement
    if equipment_def.get('unlock_requirement'):
        unlock_req = equipment_def['unlock_requirement']
        for req_eq_id, req_count in unlock_req.items():
            c.execute('SELECT COUNT(*) as count FROM equipment WHERE user_id = ? AND equipment_id = ?', (user_id, req_eq_id))
            count_result = c.fetchone()
            if not count_result or count_result['count'] < req_count:
                conn.close()
                return jsonify({'success': False, 'error': f'Musíš mít {req_count}x {EQUIPMENT_DEFS[req_eq_id]["name"]} aby sis mohl vyrobit {equipment_def["name"]}'})
    
    affordable, lacking = deduct_cost(resources, effective_cost)
    if not affordable:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáte dostatek zdrojů ({lacking})'})
    
    # Check if currency is unlocked
    for currency in cost.keys():
        if currency != 'gooncoins' and currency not in unlocked_currencies:
            conn.close()
            return jsonify({'success': False, 'error': f'Měna {currency} ještě není odemčena'})
    
    # Add new equipment instance and equip ho okamžitě
    acquisition_payload = json.dumps({
        'cost': effective_cost,
        'inflation_multiplier': inflation_multiplier
    })
    acquired_at = datetime.utcnow().isoformat()
    new_market_value = register_item_supply_change(c, equipment_id, 1) or calculate_item_base_value(equipment_id)
    c.execute('''INSERT INTO equipment
                 (user_id, equipment_slot, equipment_id, equipped, acquired_at, acquired_via, acquisition_note, acquisition_payload, last_valuation)
                 VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)''',
              (user_id, equipment_def['slot'], equipment_id, acquired_at, 'crafting', 'Vyrobeno v dílně',
               acquisition_payload, new_market_value))
    new_item_id = c.lastrowid
    # Unequip ostatní v tom samém slotu
    c.execute('UPDATE equipment SET equipped = 0 WHERE user_id = ? AND equipment_slot = ? AND id != ?',
             (user_id, equipment_def['slot'], new_item_id))
    
    persist_resources(c, user_id, resources)
    
    # Aktualizované počty equipmentu pro hráče
    c.execute('SELECT equipment_id, COUNT(*) as count FROM equipment WHERE user_id = ? GROUP BY equipment_id', (user_id,))
    player_equipment_counts = {row['equipment_id']: row['count'] for row in c.fetchall()}
    
    # Aktuálně equipnuté předměty pro rychlou aktualizaci klienta
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_items = {row['equipment_slot']: row['equipment_id'] for row in c.fetchall()}
    
    inventory_payload = build_inventory_payload(c, user_id)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    resource_payload = resources_payload(resources)
    
    return jsonify({
        'success': True,
        **resource_payload,
        'equipment_counts': player_equipment_counts,
        'equipment': equipped_items,
        'inventory': inventory_payload
    })

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    payload = build_inventory_payload(c, user_id)
    conn.close()
    return jsonify({'success': True, 'inventory': payload})

@app.route('/api/inventory/sell', methods=['POST'])
def sell_inventory_item():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    try:
        instance_id = int(instance_id)
    except (TypeError, ValueError):
        instance_id = None
    
    if not instance_id:
        return jsonify({'success': False, 'error': 'Neplatná položka inventáře'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM equipment WHERE id = ? AND user_id = ?', (instance_id, user_id))
    equipment_row = c.fetchone()
    if not equipment_row:
        conn.close()
        return jsonify({'success': False, 'error': 'Předmět nebyl nalezen'}), 404
    
    equipment_id = equipment_row['equipment_id']
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state not found'}), 404
    
    resources = extract_player_resources(state)
    market_value = register_item_supply_change(c, equipment_id, -1) or calculate_item_base_value(equipment_id)
    sell_value = round(market_value * ITEM_MARKET_SELL_TAX, 2)
    if sell_value <= 0:
        sell_value = max(1.0, calculate_item_base_value(equipment_id) * 0.5)
    resources['gooncoins'] = resources.get('gooncoins', 0) + sell_value
    
    c.execute('DELETE FROM equipment WHERE id = ? AND user_id = ?', (instance_id, user_id))
    
    persist_resources(c, user_id, resources)
    
    c.execute('SELECT equipment_id, COUNT(*) as count FROM equipment WHERE user_id = ? GROUP BY equipment_id', (user_id,))
    player_equipment_counts = {row['equipment_id']: row['count'] for row in c.fetchall()}
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_items = {row['equipment_slot']: row['equipment_id'] for row in c.fetchall()}
    inventory_payload = build_inventory_payload(c, user_id)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    resource_payload = resources_payload(resources)
    return jsonify({
        'success': True,
        'message': f'Prodáno za {sell_value:.2f} 💰',
        **resource_payload,
        'equipment_counts': player_equipment_counts,
        'equipment': equipped_items,
        'inventory': inventory_payload
    })

@app.route('/api/build-building', methods=['POST'])
def build_building():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    building_type = data.get('building_type')
    
    if building_type not in BUILDINGS_DEFS:
        return jsonify({'success': False, 'error': 'Neplatná budova'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state and story
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    
    story = ensure_story_progress(c, user_id)
    
    building_def = BUILDINGS_DEFS[building_type]
    cost = building_def['cost']
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    # Check if already built
    c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = ?', (user_id, building_type))
    existing = c.fetchone()
    if existing and existing['level'] > 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Budova již je postavena'})
    
    # Check if unlocked
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    if building_type not in unlocked_buildings and building_type != 'workshop':  # workshop is always available
        conn.close()
        return jsonify({'success': False, 'error': 'Budova ještě není odemčena'})
    
    # Check if can afford
    current_astma = state['astma'] if 'astma' in state.keys() else (state['wood'] if 'wood' in state.keys() else 0)
    current_poharky = state['poharky'] if 'poharky' in state.keys() else (state['water'] if 'water' in state.keys() else 0)
    
    if (state['gooncoins'] < effective_cost.get('gooncoins', 0) or
        current_astma < effective_cost.get('astma', 0) or
        current_poharky < effective_cost.get('poharky', 0)):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáte dostatek zdrojů'})
    
    # Deduct costs and build
    new_gooncoins = state['gooncoins'] - effective_cost.get('gooncoins', 0)
    new_astma = current_astma - effective_cost.get('astma', 0)
    new_poharky = current_poharky - effective_cost.get('poharky', 0)
    
    c.execute('INSERT INTO buildings (user_id, building_type, level) VALUES (?, ?, 1)',
             (user_id, building_type))
    
    # Update game state
    c.execute('''UPDATE game_state 
                 SET gooncoins = ?, astma = ?, poharky = ?, last_update = CURRENT_TIMESTAMP
                 WHERE user_id = ?''',
             (new_gooncoins, new_astma, new_poharky, user_id))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'gooncoins': new_gooncoins,
        'astma': new_astma,
        'poharky': new_poharky
    })

@app.route('/api/currency-market', methods=['GET', 'POST'])
def currency_market():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    if request.method == 'GET':
        user_id = session['user_id']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = "market"', (user_id,))
        market_building = c.fetchone()
        conn.close()
        
        if not market_building or market_building['level'] <= 0:
            return jsonify({'success': False, 'error': 'Postav Tržiště, aby ses dostal na trh'}), 400
        
        return jsonify({
            'success': True,
            'economy': fetch_economy_snapshot()
        })
    
    data = request.get_json() or {}
    currency = data.get('currency')
    action = data.get('action')
    amount_raw = data.get('amount')
    
    try:
        amount = round(float(amount_raw), 3)
    except (TypeError, ValueError):
        amount = 0
    
    if currency not in TRADEABLE_CURRENCIES:
        return jsonify({'success': False, 'error': 'Neplatná měna'})
    if action not in ('buy', 'sell'):
        return jsonify({'success': False, 'error': 'Neplatná akce'})
    if amount <= 0:
        return jsonify({'success': False, 'error': 'Zadejte platné množství'})
    if amount > 1_000_000:
        return jsonify({'success': False, 'error': 'Objem je příliš velký'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state not found'}), 404
    
    story = ensure_story_progress(c, user_id)
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    if currency not in unlocked_currencies:
        conn.close()
        return jsonify({'success': False, 'error': 'Tahle měna ještě není odemčena'})
    
    c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = "market"', (user_id,))
    market_building = c.fetchone()
    if not market_building or market_building['level'] <= 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Musíš nejdřív postavit Tržiště'}), 400
    
    market_snapshot = fetch_economy_snapshot()
    rate_data = market_snapshot['market_rates'].get(currency)
    if not rate_data:
        conn.close()
        return jsonify({'success': False, 'error': 'Market data nejsou k dispozici'})
    
    current_astma = state['astma'] if 'astma' in state.keys() else (state['wood'] if 'wood' in state.keys() else 0)
    current_poharky = state['poharky'] if 'poharky' in state.keys() else (state['water'] if 'water' in state.keys() else 0)
    current_mrkev = state['mrkev'] if 'mrkev' in state.keys() else (state['fire'] if 'fire' in state.keys() else 0)
    current_uzené = state['uzené'] if 'uzené' in state.keys() else (state['earth'] if 'earth' in state.keys() else 0)
    
    new_gooncoins = state['gooncoins']
    new_astma = current_astma
    new_poharky = current_poharky
    new_mrkev = current_mrkev
    new_uzené = current_uzené
    message = ''
    
    if action == 'buy':
        total_cost = rate_data['buy'] * amount
        if new_gooncoins < total_cost:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Gooncoinů'})
        new_gooncoins -= total_cost
        if currency == 'astma':
            new_astma += amount
        elif currency == 'poharky':
            new_poharky += amount
        elif currency == 'mrkev':
            new_mrkev += amount
        elif currency == 'uzené':
            new_uzené += amount
        message = f'Nakoupil jsi {amount} {currency}.'
    else:
        if currency == 'astma' and new_astma < amount:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Astma'})
        if currency == 'poharky' and new_poharky < amount:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Pohárků'})
        if currency == 'mrkev' and new_mrkev < amount:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Mrkve'})
        if currency == 'uzené' and new_uzené < amount:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Uzeného'})
        
        total_return = rate_data['sell'] * amount
        new_gooncoins += total_return
        if currency == 'astma':
            new_astma -= amount
        elif currency == 'poharky':
            new_poharky -= amount
        elif currency == 'mrkev':
            new_mrkev -= amount
        elif currency == 'uzené':
            new_uzené -= amount
        message = f'Prodal jsi {amount} {currency}.'
    
    apply_market_trade(c, currency, action, amount)
    c.execute('''UPDATE game_state 
                 SET gooncoins = ?, astma = ?, poharky = ?, mrkev = ?, uzené = ?, last_update = CURRENT_TIMESTAMP
                 WHERE user_id = ?''',
              (new_gooncoins, new_astma, new_poharky, new_mrkev, new_uzené, user_id))
    
    conn.commit()
    conn.close()
    
    economy_snapshot = fetch_economy_snapshot(force=True)
    
    return jsonify({
        'success': True,
        'message': message,
        'action': action,
        'currency': currency,
        'amount': amount,
        'rate': rate_data,
        'gooncoins': new_gooncoins,
        'astma': new_astma,
        'poharky': new_poharky,
        'mrkev': new_mrkev,
        'uzené': new_uzené,
        'economy': economy_snapshot
    })

@app.route('/api/cases')
def api_cases():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    history = get_recent_case_history(c, user_id)
    conn.close()
    return jsonify({'cases': serialize_case_definitions(), 'history': history})

@app.route('/api/cases/open', methods=['POST'])
def api_open_case():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    case_id = data.get('case_id')
    case_def = CASE_DEFINITIONS.get(case_id)
    if not case_def:
        return jsonify({'success': False, 'error': 'Neznámá bedna'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    currency = case_def.get('currency', 'gooncoins')
    price = float(case_def.get('price', 0) or 0)
    if balances.get(currency, 0) < price:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= price
    ensure_rare_materials(c, user_id)
    
    reward_item = pick_case_reward(case_def)
    reward_summary, reward_identifier, reward_amount = apply_case_reward(c, user_id, balances, reward_item)
    
    persist_state_resources(c, user_id, balances)
    
    c.execute('SELECT equipment_id, COUNT(*) as count FROM equipment WHERE user_id = ? GROUP BY equipment_id', (user_id,))
    equipment_counts = {row['equipment_id']: row['count'] for row in c.fetchall()}
    
    rare_row = ensure_rare_materials(c, user_id)
    
    reward_label = reward_summary['name'] if reward_summary else 'Nic'
    reward_type = reward_item.get('type') if reward_item else 'none'
    rarity = reward_item.get('rarity', 'common') if reward_item else 'common'
    metadata = json.dumps(reward_item.get('payout', {})) if reward_item else '{}'
    
    c.execute('''INSERT INTO case_openings (user_id, case_id, reward_type, reward_id, reward_label, rarity, amount, metadata)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, case_id, reward_type, reward_identifier, reward_label, rarity, reward_amount, metadata))
    
    history = get_recent_case_history(c, user_id)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'case_id': case_id,
        'reward': reward_summary,
        'gooncoins': balances['gooncoins'],
        'astma': balances['astma'],
        'poharky': balances['poharky'],
        'mrkev': balances['mrkev'],
        'uzené': balances['uzené'],
        'equipment_counts': equipment_counts,
        'rare_materials': serialize_rare_materials(rare_row),
        'history': history
    })

@app.route('/api/combat/overview')
def combat_overview():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    profile = ensure_combat_profile(c, user_id)
    rare_row = ensure_rare_materials(c, user_id)
    player_stats = calculate_player_combat_stats(c, user_id)
    campaign = build_campaign_snapshot(profile)
    
    c.execute('''SELECT u.id, u.username,
                        IFNULL(cp.rating, 1000) as rating,
                        IFNULL(cp.wins, 0) as wins,
                        IFNULL(cp.losses, 0) as losses
                 FROM users u
                 LEFT JOIN combat_profiles cp ON cp.user_id = u.id
                 WHERE u.id != ?
                 ORDER BY ABS(IFNULL(cp.rating, 1000) - ?) ASC, RANDOM()
                 LIMIT 5''', (user_id, profile['rating']))
    opponents = []
    for row in c.fetchall():
        opponent_stats = calculate_player_combat_stats(c, row['id'])
        opponents.append({
            'username': row['username'],
            'rating': row['rating'],
            'wins': row['wins'],
            'losses': row['losses'],
            'attack': opponent_stats['attack'],
            'defense': opponent_stats['defense'],
            'luck': opponent_stats['luck'],
            'hp': opponent_stats['hp'],
            'power_score': opponent_stats['power_score']
        })
    
    c.execute('''SELECT cl.*, ua.username AS attacker_name, ud.username AS defender_name
                 FROM combat_logs cl
                 LEFT JOIN users ua ON ua.id = cl.attacker_id
                 LEFT JOIN users ud ON ud.id = cl.defender_id
                 WHERE cl.attacker_id = ? OR cl.defender_id = ?
                 ORDER BY cl.created_at DESC
                 LIMIT 6''', (user_id, user_id))
    logs = []
    for row in c.fetchall():
        try:
            summary = json.loads(row['summary']) if row['summary'] else {}
        except json.JSONDecodeError:
            summary = {}
        logs.append({
            'mode': row['mode'],
            'winner_id': row['winner_id'],
            'created_at': row['created_at'],
            'attacker': {'id': row['attacker_id'], 'username': row['attacker_name']},
            'defender': {'id': row['defender_id'], 'username': row['defender_name']},
            'summary': summary
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'player_id': user_id,
        'player_stats': player_stats,
        'profile': {
            'rating': profile['rating'],
            'wins': profile['wins'],
            'losses': profile['losses'],
            'campaign_stage': profile['campaign_stage']
        },
        'rare_materials': serialize_rare_materials(rare_row),
        'pvp': {
            'opponents': opponents,
            'recent_logs': logs
        },
        'campaign': campaign,
        'rare_material_defs': RARE_MATERIAL_DEFS
    })

def _update_rating(current_rating, delta):
    return max(200, current_rating + delta)

@app.route('/api/combat/pvp', methods=['POST'])
def combat_pvp():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    opponent_name = data.get('opponent')
    if not opponent_name:
        return jsonify({'success': False, 'error': 'Vyber protivníka'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT id FROM users WHERE username = ?', (opponent_name,))
    opponent = c.fetchone()
    if not opponent:
        conn.close()
        return jsonify({'success': False, 'error': 'Hráč nenalezen'}), 404
    if opponent['id'] == user_id:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemůžeš útočit na sebe'}), 400
    
    attacker_profile = ensure_combat_profile(c, user_id)
    defender_profile = ensure_combat_profile(c, opponent['id'])
    attacker_stats = calculate_player_combat_stats(c, user_id)
    defender_stats = calculate_player_combat_stats(c, opponent['id'])
    
    battle = simulate_combat(attacker_stats, defender_stats)
    winner_tag = battle['winner']
    winner_id = None
    reward = 0
    player_won = False
    rating_delta = max(10, int(20 + (defender_profile['rating'] - attacker_profile['rating']) / 40))
    
    if winner_tag == 'attacker':
        player_won = True
        winner_id = user_id
        c.execute('UPDATE combat_profiles SET wins = wins + 1, rating = ? WHERE user_id = ?', (_update_rating(attacker_profile['rating'], rating_delta), user_id))
        c.execute('UPDATE combat_profiles SET losses = losses + 1, rating = ? WHERE user_id = ?', (_update_rating(defender_profile['rating'], -rating_delta // 2), opponent['id']))
        reward = int(PVP_BASE_REWARD + defender_stats['power_score'] * 0.6)
        c.execute('UPDATE game_state SET gooncoins = gooncoins + ?, last_update = CURRENT_TIMESTAMP WHERE user_id = ?', (reward, user_id))
    elif winner_tag == 'defender':
        winner_id = opponent['id']
        c.execute('UPDATE combat_profiles SET losses = losses + 1, rating = ? WHERE user_id = ?', (_update_rating(attacker_profile['rating'], -rating_delta // 2), user_id))
        c.execute('UPDATE combat_profiles SET wins = wins + 1, rating = ? WHERE user_id = ?', (_update_rating(defender_profile['rating'], rating_delta), opponent['id']))
        consolation = int(PVP_BASE_REWARD / 2)
        c.execute('UPDATE game_state SET gooncoins = gooncoins + ?, last_update = CURRENT_TIMESTAMP WHERE user_id = ?', (consolation, opponent['id']))
    else:
        c.execute('UPDATE combat_profiles SET rating = ? WHERE user_id = ?', (attacker_profile['rating'], user_id))
        c.execute('UPDATE combat_profiles SET rating = ? WHERE user_id = ?', (defender_profile['rating'], opponent['id']))
    
    record_combat_log(c, user_id, opponent['id'], 'pvp', winner_id, {
        'battle': battle,
        'attacker_stats': attacker_stats,
        'defender_stats': defender_stats
    })
    
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    player_state = c.fetchone()
    conn.commit()
    conn.close()
    
    if winner_tag == 'attacker':
        refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'battle': battle,
        'player_won': player_won,
        'reward': reward if player_won else 0,
        'gooncoins': player_state['gooncoins'] if player_state else None,
        'attacker_stats': attacker_stats,
        'defender_stats': defender_stats,
        'opponent': opponent_name
    })

def _campaign_find_monster(monster_id):
    for monster in CAMPAIGN_MONSTERS:
        if monster['id'] == monster_id:
            return monster
    return None

@app.route('/api/combat/campaign-battle', methods=['POST'])
def combat_campaign():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    monster_id = data.get('monster_id')
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    profile_row = ensure_combat_profile(c, user_id)
    profile = dict(profile_row)
    campaign = build_campaign_snapshot(profile)
    
    target_monster = None
    if monster_id:
        target_monster = _campaign_find_monster(monster_id)
    else:
        target_monster = campaign['next_monster']
    
    if not target_monster:
        conn.close()
        return jsonify({'success': False, 'error': 'Monstrum nebylo nalezeno'}), 404
    
    player_stats = calculate_player_combat_stats(c, user_id)
    monster_stats = {
        'attack': target_monster['stats']['attack'],
        'defense': target_monster['stats']['defense'],
        'luck': target_monster['stats'].get('luck', 1.0),
        'hp': target_monster['stats']['hp']
    }
    
    battle = simulate_combat(player_stats, monster_stats)
    defeated_list = json.loads(profile['defeated_monsters']) if profile['defeated_monsters'] else []
    rewards = target_monster['rewards']
    advanced = False
    
    if battle['winner'] == 'attacker':
        adjust_rare_materials(c, user_id, rewards.get('rare_materials', {}))
        goon_reward = rewards.get('gooncoins', 0)
        if goon_reward:
            c.execute('UPDATE game_state SET gooncoins = gooncoins + ?, last_update = CURRENT_TIMESTAMP WHERE user_id = ?',
                      (goon_reward, user_id))
        if target_monster['id'] not in defeated_list:
            defeated_list.append(target_monster['id'])
        if campaign['next_monster'] and target_monster['id'] == campaign['next_monster']['id']:
            new_stage = min(len(CAMPAIGN_MONSTERS), profile['campaign_stage'] + 1)
            c.execute('UPDATE combat_profiles SET campaign_stage = ?, defeated_monsters = ? WHERE user_id = ?',
                      (new_stage, json.dumps(defeated_list), user_id))
            profile['campaign_stage'] = new_stage
            advanced = True
        else:
            c.execute('UPDATE combat_profiles SET defeated_monsters = ? WHERE user_id = ?',
                      (json.dumps(defeated_list), user_id))
        profile['defeated_monsters'] = json.dumps(defeated_list)
        winner_id = user_id
    else:
        winner_id = None
    
    record_combat_log(c, user_id, None, 'campaign', winner_id, {
        'monster': target_monster['id'],
        'battle': battle
    })
    
    rare_row = ensure_rare_materials(c, user_id)
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    conn.commit()
    conn.close()
    
    if battle['winner'] == 'attacker' and rewards.get('gooncoins'):
        refresh_economy_after_change()
    
    updated_campaign = build_campaign_snapshot(profile)
    
    return jsonify({
        'success': True,
        'battle': battle,
        'player_won': battle['winner'] == 'attacker',
        'rewards': rewards if battle['winner'] == 'attacker' else {},
        'rare_materials': serialize_rare_materials(rare_row),
        'gooncoins': state['gooncoins'] if state else None,
        'campaign': updated_campaign,
        'player_stats': player_stats,
        'monster_stats': monster_stats,
        'monster_name': target_monster['name']
    })

@app.route('/api/temple/status')
def temple_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    snapshot = build_temple_snapshot(c, user_id)
    conn.close()
    return jsonify({'success': True, 'temple': snapshot})

@app.route('/api/temple/ritual', methods=['POST'])
def temple_ritual():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    blessing_id = data.get('blessing_id')
    blessing_def = TEMPLE_BLESSINGS.get(blessing_id)
    if not blessing_def:
        return jsonify({'success': False, 'error': 'Neplatné požehnání'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = "temple"', (user_id,))
    building = c.fetchone()
    if not building or building['level'] <= 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Chrám ještě není postavený'}), 400
    
    temple_row = ensure_temple_state(c, user_id)
    now = datetime.utcnow()
    active_expires = parse_timestamp(temple_row['blessing_expires_at'])
    if temple_row['active_blessing'] and active_expires and active_expires > now:
        conn.close()
        return jsonify({'success': False, 'error': 'Už máš aktivní požehnání'}), 400
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Stav hry nenalezen'}), 404
    
    current_astma = state['astma']
    current_poharky = state['poharky']
    current_mrkev = state['mrkev']
    current_uzené = state['uzené']
    
    favor_balance = temple_row['favor'] if temple_row and temple_row['favor'] is not None else 0
    cost = blessing_def.get('cost', {})
    if favor_balance < cost.get('favor', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost chrámové přízně'}), 400
    if state['gooncoins'] < cost.get('gooncoins', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost Gooncoinů'}), 400
    if current_poharky < cost.get('poharky', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost Pohárků'}), 400
    if current_mrkev < cost.get('mrkev', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost Mrkve'}), 400
    if current_uzené < cost.get('uzené', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost Uzeného'}), 400
    if current_astma < cost.get('astma', 0):
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost Astma'}), 400
    
    new_gooncoins = state['gooncoins'] - cost.get('gooncoins', 0)
    new_astma = current_astma - cost.get('astma', 0)
    new_poharky = current_poharky - cost.get('poharky', 0)
    new_mrkev = current_mrkev - cost.get('mrkev', 0)
    new_uzené = current_uzené - cost.get('uzené', 0)
    new_favor = favor_balance - cost.get('favor', 0)
    
    c.execute('''UPDATE game_state
                 SET gooncoins = ?, astma = ?, poharky = ?, mrkev = ?, uzené = ?, last_update = CURRENT_TIMESTAMP
                 WHERE user_id = ?''',
              (new_gooncoins, new_astma, new_poharky, new_mrkev, new_uzené, user_id))
    
    expires_at = (now + timedelta(seconds=blessing_def.get('duration', 1800))).isoformat()
    c.execute('''UPDATE temple_state
                 SET favor = ?, active_blessing = ?, blessing_expires_at = ?
                 WHERE user_id = ?''',
              (new_favor, blessing_id, expires_at, user_id))
    
    snapshot = build_temple_snapshot(c, user_id)
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'gooncoins': new_gooncoins,
        'astma': new_astma,
        'poharky': new_poharky,
        'mrkev': new_mrkev,
        'uzené': new_uzené,
        'temple': snapshot
    })

@app.route('/api/temple/fight', methods=['POST'])
def temple_fight():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    room_id = data.get('room_id')
    user_id = session['user_id']
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = "temple"', (user_id,))
    building = c.fetchone()
    if not building or building['level'] <= 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Chrám ještě není připraven'}), 400
    
    temple_row = ensure_temple_state(c, user_id)
    progress_map = _temple_load_progress(temple_row)
    if room_id:
        room = _temple_get_room(room_id)
    else:
        room = _temple_get_room(temple_row['last_room']) if temple_row and temple_row['last_room'] else None
    if not room:
        default_room_id = _temple_first_unlocked_room(progress_map)
        room = _temple_get_room(default_room_id)
    if not room:
        conn.close()
        return jsonify({'success': False, 'error': 'Chrám nemá dostupné místnosti'}), 400
    if not _temple_is_room_unlocked(progress_map, room):
        conn.close()
        return jsonify({'success': False, 'error': 'Nejprve dokonči předchozí místnost'}), 400
    
    now = datetime.utcnow()
    cooldown_until = parse_timestamp(temple_row['cooldown_until'])
    if cooldown_until and cooldown_until > now:
        remaining = int((cooldown_until - now).total_seconds())
        conn.close()
        return jsonify({'success': False, 'error': 'Musíš počkat, než se zotavíš z porážky.', 'cooldown_seconds': remaining}), 400
    
    room_progress = dict(progress_map.get(room['id'], _temple_default_progress()))
    is_boss = room_progress.get('kills', 0) >= room['required_kills']
    
    if is_boss:
        enemy_meta = room['boss']
        enemy_name = enemy_meta['name']
        enemy_stats = enemy_meta['stats']
    else:
        pool = [enemy_id for enemy_id in room['enemy_pool'] if enemy_id in TEMPLE_ENEMIES]
        if not pool:
            pool = list(TEMPLE_ENEMIES.keys())
        chosen_id = random.choice(pool)
        enemy_meta = TEMPLE_ENEMIES[chosen_id]
        enemy_name = enemy_meta['name']
        enemy_stats = enemy_meta['stats']
    
    player_stats = calculate_player_combat_stats(c, user_id)
    battle = simulate_combat(player_stats, enemy_stats)
    player_won = battle['winner'] == 'attacker'
    
    rewards = {}
    favor_gain = 0
    goon_reward = 0
    rare_rewards = {}
    
    if player_won:
        if is_boss:
            boss_rewards = room['boss'].get('rewards', {})
            goon_reward = boss_rewards.get('gooncoins', 0)
            favor_gain += boss_rewards.get('favor', 0)
            rare_rewards = boss_rewards.get('rare_materials', {})
            room_progress['kills'] = 0
            room_progress['loops'] = room_progress.get('loops', 0) + 1
            if not room_progress.get('ever_cleared'):
                room_progress['ever_cleared'] = True
        else:
            room_progress['kills'] = min(room['required_kills'], room_progress.get('kills', 0) + 1)
            favor_gain += enemy_meta.get('favor', 1)
            goon_reward = enemy_meta.get('gooncoins', 0)
        
        if rare_rewards:
            adjust_rare_materials(c, user_id, rare_rewards)
        if goon_reward:
            c.execute('UPDATE game_state SET gooncoins = gooncoins + ?, last_update = CURRENT_TIMESTAMP WHERE user_id = ?', (goon_reward, user_id))
        
        new_favor = (temple_row['favor'] if temple_row and temple_row['favor'] is not None else 0) + favor_gain
        progress_map[room['id']] = room_progress
        c.execute('''UPDATE temple_state
                     SET progress = ?, favor = ?, cooldown_until = NULL, last_room = ?
                     WHERE user_id = ?''',
                  (json.dumps(progress_map), new_favor, room['id'], user_id))
        
        record_combat_log(c, user_id, None, 'temple', user_id, {
            'room': room['id'],
            'boss': is_boss,
            'enemy_name': enemy_name,
            'battle': battle
        })
    else:
        progress_map[room['id']] = room_progress
        cooldown_iso = (datetime.utcnow() + timedelta(seconds=TEMPLE_DEFEAT_COOLDOWN)).isoformat()
        c.execute('''UPDATE temple_state
                     SET progress = ?, cooldown_until = ?, last_room = ?
                     WHERE user_id = ?''',
                  (json.dumps(progress_map), cooldown_iso, room['id'], user_id))
        record_combat_log(c, user_id, None, 'temple', None, {
            'room': room['id'],
            'boss': is_boss,
            'enemy_name': enemy_name,
            'battle': battle
        })
    
    rare_row = ensure_rare_materials(c, user_id)
    c.execute('SELECT gooncoins, astma, poharky, mrkev, uzené FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    
    snapshot = build_temple_snapshot(c, user_id)
    conn.commit()
    conn.close()
    
    if player_won and goon_reward:
        refresh_economy_after_change()
    
    rewards_payload = {}
    if goon_reward:
        rewards_payload['gooncoins'] = goon_reward
    if favor_gain:
        rewards_payload['favor'] = favor_gain
    if rare_rewards:
        rewards_payload['rare_materials'] = rare_rewards
    
    return jsonify({
        'success': True,
        'battle': battle,
        'player_won': player_won,
        'rewards': rewards_payload,
        'gooncoins': state['gooncoins'] if state else None,
        'rare_materials': serialize_rare_materials(rare_row),
        'temple': snapshot,
        'player_stats': player_stats,
        'enemy_stats': enemy_stats,
        'enemy_name': enemy_name
    })

@app.route('/api/complete-quest', methods=['POST'])
def complete_quest():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        quest_id = data.get('quest_id')
        if not quest_id:
            return jsonify({'success': False, 'error': 'Quest ID chybí'})
        
        user_id = session['user_id']
        conn = get_db()
        c = conn.cursor()
        
        # Get story progress
        story = ensure_story_progress(c, user_id)
        current_chapter = story['current_chapter'] if story else 1
        completed_quests = json.loads(story['completed_quests']) if story and story['completed_quests'] else []
    except Exception as e:
        return jsonify({'success': False, 'error': f'Chyba: {str(e)}'}), 500
    
    if quest_id in completed_quests:
        conn.close()
        return jsonify({'success': False, 'error': 'Quest již je dokončen'})
    
    # Find quest
    quest = None
    for chapter_num, chapter_data in STORY_CHAPTERS.items():
        if chapter_num <= current_chapter:
            for q in chapter_data['quests']:
                if q['id'] == quest_id:
                    quest = q
                    break
        if quest:
            break
    
    if not quest:
        conn.close()
        return jsonify({'success': False, 'error': 'Quest nenalezen'})
    
    # Check requirements
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    
    # Handle migration - get old or new values
    current_astma = state['astma'] if 'astma' in state.keys() else (state['wood'] if 'wood' in state.keys() else 0)
    current_poharky = state['poharky'] if 'poharky' in state.keys() else (state['water'] if 'water' in state.keys() else 0)
    current_mrkev = state['mrkev'] if 'mrkev' in state.keys() else (state['fire'] if 'fire' in state.keys() else 0)
    current_uzené = state['uzené'] if 'uzené' in state.keys() else (state['earth'] if 'earth' in state.keys() else 0)
    
    req = quest['requirement']
    if 'total_clicks' in req and state['total_clicks'] < req['total_clicks']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'gooncoins' in req and state['gooncoins'] < req['gooncoins']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'astma' in req and current_astma < req['astma']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'poharky' in req and current_poharky < req['poharky']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'mrkev' in req and current_mrkev < req['mrkev']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'uzené' in req and current_uzené < req['uzené']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'equipment_count' in req:
        c.execute('SELECT COUNT(*) as count FROM equipment WHERE user_id = ?', (user_id,))
        eq_count = c.fetchone()['count']
        if eq_count < req['equipment_count']:
            conn.close()
            return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'equipment_owned' in req:
        for req_eq_id, req_amount in req['equipment_owned'].items():
            c.execute('SELECT COUNT(*) as count FROM equipment WHERE user_id = ? AND equipment_id = ?', (user_id, req_eq_id))
            owned_count = c.fetchone()['count']
            if owned_count < req_amount:
                conn.close()
                return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'buildings' in req:
        for building_type in req['buildings']:
            c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = ?', (user_id, building_type))
            building = c.fetchone()
            if not building or building['level'] == 0:
                conn.close()
                return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    
    # Give rewards
    reward = quest.get('reward', {})
    new_gooncoins = state['gooncoins'] + reward.get('gooncoins', 0)
    new_astma = current_astma + reward.get('astma', 0)
    new_poharky = current_poharky + reward.get('poharky', 0)
    new_mrkev = current_mrkev + reward.get('mrkev', 0)
    new_uzené = current_uzené + reward.get('uzené', 0)
    
    # Unlock new things
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    
    if 'unlocks' in quest:
        for unlock in quest['unlocks']:
            if unlock not in unlocked_currencies and unlock not in unlocked_buildings:
                if unlock in ['astma', 'poharky', 'mrkev', 'uzené']:
                    unlocked_currencies.append(unlock)
                else:
                    unlocked_buildings.append(unlock)
    
    # Mark quest as completed
    if quest_id not in completed_quests:
        completed_quests.append(quest_id)
    
    # Determine chapter progression
    new_chapter = current_chapter
    current_chapter_data = STORY_CHAPTERS.get(current_chapter, {})
    chapter_quests = current_chapter_data.get('quests', [])
    if chapter_quests:
        required_quests = [q for q in chapter_quests if not q.get('optional')]
        all_completed = all(q['id'] in completed_quests for q in required_quests)
        next_chapter = current_chapter + 1
        if all_completed and next_chapter in STORY_CHAPTERS:
            new_chapter = next_chapter
    
    try:
        # Update
        c.execute('''UPDATE game_state 
                     SET gooncoins = ?, astma = ?, poharky = ?, mrkev = ?, uzené = ?, last_update = CURRENT_TIMESTAMP
                     WHERE user_id = ?''',
                 (new_gooncoins, new_astma, new_poharky, new_mrkev, new_uzené, user_id))
        
        c.execute('''UPDATE story_progress 
                     SET completed_quests = ?, unlocked_buildings = ?, unlocked_currencies = ?, current_chapter = ?
                     WHERE user_id = ?''',
                 (json.dumps(completed_quests), json.dumps(unlocked_buildings), json.dumps(unlocked_currencies), new_chapter, user_id))
        
        conn.commit()
        conn.close()
        
        refresh_economy_after_change()
        
        return jsonify({
            'success': True,
            'gooncoins': new_gooncoins,
            'astma': new_astma,
            'poharky': new_poharky,
            'mrkev': new_mrkev,
            'uzené': new_uzené,
            'unlocked_currencies': unlocked_currencies,
            'unlocked_buildings': unlocked_buildings,
            'current_chapter': new_chapter
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'success': False, 'error': f'Chyba při dokončování questu: {str(e)}'}), 500

@app.route('/api/player-equipment/<username>')
def get_player_equipment(username):
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'Uživatel nenalezen'}), 404
    
    c.execute('''SELECT e.equipment_id, e.equipment_slot, u.username
                 FROM equipment e
                 JOIN users u ON e.user_id = u.id
                 WHERE e.user_id = ? AND e.equipped = 1''', (user['id'],))
    
    equipment = [{'slot': row['equipment_slot'], 'id': row['equipment_id']} for row in c.fetchall()]
    conn.close()
    
    return jsonify({
        'username': username,
        'equipment': equipment
    })

@app.route('/api/story-data')
def get_story_data():
    # Get equipment ownership counts
    conn = get_db()
    c = conn.cursor()
    equipment_counts = {}
    for eq_id in EQUIPMENT_DEFS.keys():
        c.execute('SELECT COUNT(*) as count FROM equipment WHERE equipment_id = ?', (eq_id,))
        result = c.fetchone()
        equipment_counts[eq_id] = result['count'] if result else 0
    conn.close()
    
    return jsonify({
        'chapters': STORY_CHAPTERS,
        'lore_entries': LORE_ENTRIES,
        'equipment': EQUIPMENT_DEFS,
        'buildings': BUILDINGS_DEFS,
        'equipment_counts': equipment_counts
    })

@app.route('/images/<path:filename>')
def images(filename):
    return send_from_directory('obrazky', filename)

@app.route('/idle-prototype')
def idle_prototype():
    """
    Lehké front-end demo pro nový idle/adventure-communist engine.
    Nevyžaduje přihlášení a běží čistě na klientovi.
    """
    return render_template('idle.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

