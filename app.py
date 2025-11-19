from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
from datetime import datetime, timedelta, timezone
import os
import random
import time
import math
from functools import wraps

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
    'uzené': 'Uzené',
    'logs': 'Klády',
    'planks': 'Prkna',
    'grain': 'Obilí',
    'flour': 'Mouka',
    'bread': 'Chleba',
    'fish': 'Ryby'
}

RESOURCE_ALIAS_MAP = {
    'astma': ['astma', 'wood'],
    'poharky': ['poharky', 'water'],
    'mrkev': ['mrkev', 'fire'],
    'uzené': ['uzené', 'earth']
}

def hydrate_state_resources(row):
    base = {key: 0.0 for key in RESOURCE_FIELDS}
    if not row:
        return base
    if hasattr(row, 'keys'):
        mapping = {key: row[key] for key in row.keys()}
    elif isinstance(row, dict):
        mapping = row
    else:
        return base
    for key in RESOURCE_FIELDS:
        value = mapping.get(key)
        if value is None and key in RESOURCE_ALIAS_MAP:
            for alias in RESOURCE_ALIAS_MAP[key]:
                if alias in mapping and mapping[alias] is not None:
                    value = mapping[alias]
                    break
        if value is None and key in RESOURCE_FALLBACKS:
            fallback = RESOURCE_FALLBACKS.get(key)
            if fallback:
                value = mapping.get(fallback)
        base[key] = float(value if value is not None else 0)
    return base


def persist_state_resources(cursor, user_id, balances):
    persist_resources(cursor, user_id, balances)

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
        'cost': {'favor': 1250, 'poharky': 750, 'gooncoins': 20000},
        'bonus': {'attack': 12},
        'duration': 1800
    },
    'bulwark': {
        'name': 'Štít Balkónů',
        'description': 'Chrám generuje ochranné pole, které zvyšuje obranu i HP.',
        'cost': {'favor': 1100, 'uzené': 400, 'gooncoins': 17500},
        'bonus': {'defense': 14, 'hp': 120},
        'duration': 1800
    },
    'omen': {
        'name': 'Šepot Neonů',
        'description': 'Štěstí chrámu posiluje kritické zásahy a úhyby.',
        'cost': {'favor': 1000, 'mrkev': 700, 'gooncoins': 15000},
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

# Character Classes
CHARACTER_CLASSES = {
    'warrior': {
        'name': 'Warrior',
        'main_stat': 'strength',
        'damage_coefficient': 1.2,
        'initiative_stat': 'dexterity',
        'description': 'Bojovník s vysokou silou a obranou'
    },
    'mage': {
        'name': 'Mage',
        'main_stat': 'intelligence',
        'damage_coefficient': 1.3,
        'initiative_stat': 'intelligence',
        'description': 'Mág s vysokou inteligencí a magickým poškozením'
    },
    'scout': {
        'name': 'Scout',
        'main_stat': 'dexterity',
        'damage_coefficient': 1.15,
        'initiative_stat': 'dexterity',
        'description': 'Zvěd s vysokou obratností a kritickými zásahy'
    }
}

# Quest System Definitions
QUEST_DIFFICULTIES = {
    1: {'name': 'Easy', 'exp_mult': 1.0, 'gold_mult': 1.0, 'duration_base': 300},
    2: {'name': 'Medium', 'exp_mult': 1.5, 'gold_mult': 1.5, 'duration_base': 600},
    3: {'name': 'Hard', 'exp_mult': 2.5, 'gold_mult': 2.5, 'duration_base': 1200},
    4: {'name': 'Expert', 'exp_mult': 4.0, 'gold_mult': 4.0, 'duration_base': 2400},
    5: {'name': 'Master', 'exp_mult': 6.5, 'gold_mult': 6.5, 'duration_base': 3600}
}

QUEST_TEMPLATES = [
    {'name': 'Zabij 10 goblinů', 'type': 'combat'},
    {'name': 'Sesbírej 50 bylin', 'type': 'gather'},
    {'name': 'Doruč dopis do sousední vesnice', 'type': 'delivery'},
    {'name': 'Vyčisti jeskyni od pavouků', 'type': 'dungeon'},
    {'name': 'Najdi ztracený poklad', 'type': 'explore'},
    {'name': 'Ochraň karavanu', 'type': 'escort'},
    {'name': 'Zabij draka', 'type': 'boss'},
    {'name': 'Vyřeš záhadu zmizelých vesničanů', 'type': 'mystery'},
    {'name': 'Zabij 20 vlků', 'type': 'combat'},
    {'name': 'Poraz bandity na silnici', 'type': 'combat'},
    {'name': 'Vyčisti les od skřetů', 'type': 'combat'},
    {'name': 'Zabij 15 orků', 'type': 'combat'},
    {'name': 'Poraz trolla', 'type': 'boss'},
    {'name': 'Sesbírej 30 hub', 'type': 'gather'},
    {'name': 'Najdi 25 kamenů', 'type': 'gather'},
    {'name': 'Sesbírej léčivé byliny', 'type': 'gather'},
    {'name': 'Doruč balíček do města', 'type': 'delivery'},
    {'name': 'Přines zprávu z hradu', 'type': 'delivery'},
    {'name': 'Doruč jídlo do hospody', 'type': 'delivery'},
    {'name': 'Prozkoumej opuštěný hrad', 'type': 'explore'},
    {'name': 'Najdi skrytou jeskyni', 'type': 'explore'},
    {'name': 'Prozkoumej starý les', 'type': 'explore'},
    {'name': 'Najdi ztracený meč', 'type': 'explore'},
    {'name': 'Ochraň obchodníka', 'type': 'escort'},
    {'name': 'Doprovod princeznu', 'type': 'escort'},
    {'name': 'Ochraň vesnici před útokem', 'type': 'escort'},
    {'name': 'Vyčisti kobky pod hradem', 'type': 'dungeon'},
    {'name': 'Projdi magickou jeskyni', 'type': 'dungeon'},
    {'name': 'Vyčisti ruiny chrámu', 'type': 'dungeon'},
    {'name': 'Zabij obřího pavouka', 'type': 'boss'},
    {'name': 'Poraz temného mága', 'type': 'boss'},
    {'name': 'Zabij lich krále', 'type': 'boss'},
    {'name': 'Vyřeš záhadu zmizelých dětí', 'type': 'mystery'},
    {'name': 'Najdi vraha', 'type': 'mystery'},
    {'name': 'Vyřeš krádež v obchodě', 'type': 'mystery'},
    {'name': 'Zabij 30 zombie', 'type': 'combat'},
    {'name': 'Poraz kostlivce', 'type': 'combat'},
    {'name': 'Zabij 25 netopýrů', 'type': 'combat'},
    {'name': 'Sesbírej 40 jablek', 'type': 'gather'},
    {'name': 'Najdi 20 perel', 'type': 'gather'},
    {'name': 'Sesbírej magické krystaly', 'type': 'gather'},
    {'name': 'Doruč dopis králi', 'type': 'delivery'},
    {'name': 'Přines zprávu z fronty', 'type': 'delivery'},
    {'name': 'Prozkoumej podzemní tunely', 'type': 'explore'},
    {'name': 'Najdi poklad pirátů', 'type': 'explore'},
    {'name': 'Ochraň farmáře', 'type': 'escort'},
    {'name': 'Doprovod karavanu zlata', 'type': 'escort'},
    {'name': 'Vyčisti hrobku', 'type': 'dungeon'},
    {'name': 'Projdi ohnivou jeskyni', 'type': 'dungeon'},
    {'name': 'Zabij dračího pána', 'type': 'boss'},
    {'name': 'Poraz démona', 'type': 'boss'},
    {'name': 'Vyřeš záhadu prokletého lesa', 'type': 'mystery'}
]

# Mount System
MOUNT_TYPES = {
    'none': {'name': 'Bez koně', 'speed_reduction': 0, 'cost': 0},
    'basic_horse': {'name': 'Základní kůň', 'speed_reduction': 20, 'cost': 25000},
    'fast_horse': {'name': 'Rychlý kůň', 'speed_reduction': 30, 'cost': 100000},
    'epic_horse': {'name': 'Epický kůň', 'speed_reduction': 50, 'cost': 500000}
}

# Dungeon System
DUNGEON_DEFINITIONS = {
    'kmochova_residence': {
        'name': 'Kmochova Residence',
        'floors': 11,
        'base_level': 1,
        'locations': [
            {'id': 'jitcina_kuchyne', 'name': 'Jitčina kuchyně', 'floor_range': [1, 2]},
            {'id': 'maly_lugy_room', 'name': "Malý Lugy's room", 'floor_range': [3, 4]},
            {'id': 'kikin_pokoj', 'name': 'Kikin pokoj', 'floor_range': [5, 6]},
            {'id': 'arkadova_zona', 'name': 'Arkádová zóna', 'floor_range': [7, 8]},
            {'id': 'chodba_kure_kari', 'name': 'Chodba kuře-kari', 'floor_range': [9]},
            {'id': 'rajcatova_svatyne', 'name': 'Rajčatová svatyně', 'floor_range': [10]},
            {'id': 'predni_dvur', 'name': 'Přední dvůr – Řvoucí Fabie Arena', 'floor_range': [11]}
        ],
        'main_boss': {
            'name': 'Jitka – Vládce Kuchyňského Chaosu',
            'floor': 11,
            'level': 15,
            'hp': 8000,
            'attack': 450,
            'defense': 300,
            'luck': 40,
            'armor': 50,
            'ultimate_attack': 'To sníš, nebo ti to ohřeju znova?',
            'rewards': {'gooncoins': 5000, 'exp': 2000, 'rare_materials': {'kitchen_chaos': 1}}
        },
        'minibosses': [
            {
                'name': 'Malý Lugy – Mistr Impulzivity',
                'floor': 4,
                'level': 8,
                'hp': 3000,
                'attack': 280,
                'defense': 180,
                'luck': 25,
                'armor': 30,
                'rewards': {'gooncoins': 1500, 'exp': 800}
            },
            {
                'name': 'Kiki – Tiše Pozorující Orákulum',
                'floor': 6,
                'level': 10,
                'hp': 4000,
                'attack': 320,
                'defense': 220,
                'luck': 35,
                'armor': 35,
                'rewards': {'gooncoins': 2000, 'exp': 1000}
            },
            {
                'name': 'Zlá Arkádovka – Stroj Frustrace',
                'floor': 8,
                'level': 12,
                'hp': 5000,
                'attack': 380,
                'defense': 260,
                'luck': 30,
                'armor': 40,
                'rewards': {'gooncoins': 2500, 'exp': 1200}
            },
            {
                'name': 'Řvoucí Fabie – Motorový Démon Před Domem',
                'floor': 10,
                'level': 13,
                'hp': 5500,
                'attack': 400,
                'defense': 280,
                'luck': 20,
                'armor': 45,
                'rewards': {'gooncoins': 3000, 'exp': 1500}
            }
        ],
        'common_enemies': [
            {'name': 'Kuře a Kari Elementál', 'hp': 500, 'attack': 80, 'defense': 50, 'luck': 10, 'armor': 10, 'exp': 50, 'gooncoins': 100},
            {'name': 'Normální Rajče', 'hp': 300, 'attack': 60, 'defense': 40, 'luck': 15, 'armor': 5, 'exp': 30, 'gooncoins': 50},
            {'name': 'Malina Pissing Slime', 'hp': 400, 'attack': 70, 'defense': 45, 'luck': 12, 'armor': 8, 'exp': 40, 'gooncoins': 75},
            {'name': 'Polévka z Actionu Blob', 'hp': 600, 'attack': 90, 'defense': 55, 'luck': 8, 'armor': 12, 'exp': 60, 'gooncoins': 120},
            {'name': 'Ice Bucket Specter', 'hp': 450, 'attack': 75, 'defense': 48, 'luck': 18, 'armor': 10, 'exp': 45, 'gooncoins': 90},
            {'name': 'Mazda Tuning Gremlin', 'hp': 550, 'attack': 85, 'defense': 52, 'luck': 20, 'armor': 15, 'exp': 55, 'gooncoins': 110}
        ]
    },
    'gympl': {
        'name': 'Gympl',
        'floors': 10,
        'base_level': 5,
        'locations': [
            {'id': 'skrinkovy_koridor', 'name': 'Skříňkový koridor', 'floor_range': [1, 2]},
            {'id': 'lustig_ucebna', 'name': 'Linguistická učebna Lustiga', 'floor_range': [3, 4]},
            {'id': 'tumov_kabinet', 'name': 'Tůmov kabinet', 'floor_range': [5]},
            {'id': 'strechy_atelier', 'name': 'Střešní ateliér', 'floor_range': [6]},
            {'id': 'dolezalove_kancelar', 'name': 'Doležalové kancelář', 'floor_range': [7]},
            {'id': 'skully_shrine', 'name': 'Skully shrine', 'floor_range': [8]},
            {'id': 'nejvetsi_nakup_treasury', 'name': 'Treasury of Největší Nákup', 'floor_range': [9]},
            {'id': 'rodicak_hall', 'name': 'Rodičák Hall', 'floor_range': [10]}
        ],
        'main_boss': {
            'name': 'Jindra – Examinátor Osudu',
            'floor': 10,
            'level': 20,
            'hp': 12000,
            'attack': 650,
            'defense': 450,
            'luck': 50,
            'armor': 70,
            'ultimate_attack': 'Tak mi to nějak shrňte…',
            'rewards': {'gooncoins': 8000, 'exp': 3500, 'rare_materials': {'examination_seal': 1}}
        },
        'minibosses': [
            {
                'name': 'Tůma – Neochvějný Strážce Přísnosti',
                'floor': 5,
                'level': 15,
                'hp': 6000,
                'attack': 450,
                'defense': 350,
                'luck': 40,
                'armor': 60,
                'rewards': {'gooncoins': 3000, 'exp': 1500}
            },
            {
                'name': 'Hana Doležalová – Administrativní Architektka',
                'floor': 7,
                'level': 17,
                'hp': 7000,
                'attack': 500,
                'defense': 380,
                'luck': 45,
                'armor': 65,
                'rewards': {'gooncoins': 3500, 'exp': 1800}
            },
            {
                'name': 'Lustig – Bard Didaktického Humorismu',
                'floor': 4,
                'level': 13,
                'hp': 5500,
                'attack': 420,
                'defense': 320,
                'luck': 50,
                'armor': 55,
                'rewards': {'gooncoins': 2800, 'exp': 1400}
            },
            {
                'name': 'Dřevíček – Duch Ztraceného Času',
                'floor': 9,
                'level': 18,
                'hp': 7500,
                'attack': 520,
                'defense': 400,
                'luck': 35,
                'armor': 68,
                'rewards': {'gooncoins': 4000, 'exp': 2000}
            }
        ],
        'common_enemies': [
            {'name': 'Promáčklá Skříňka Golem', 'hp': 800, 'attack': 120, 'defense': 80, 'luck': 15, 'armor': 20, 'exp': 80, 'gooncoins': 150},
            {'name': 'Střechařská Přítvora (Skica Elementál)', 'hp': 700, 'attack': 110, 'defense': 75, 'luck': 20, 'armor': 18, 'exp': 70, 'gooncoins': 130},
            {'name': 'Skully Spirit', 'hp': 600, 'attack': 100, 'defense': 70, 'luck': 25, 'armor': 15, 'exp': 60, 'gooncoins': 120},
            {'name': 'Rodičák Specter', 'hp': 900, 'attack': 130, 'defense': 85, 'luck': 12, 'armor': 22, 'exp': 90, 'gooncoins': 170},
            {'name': 'Největší Nákup Goblin', 'hp': 750, 'attack': 115, 'defense': 78, 'luck': 18, 'armor': 19, 'exp': 75, 'gooncoins': 140},
            {'name': 'Třídní Kruh Šepotů', 'hp': 650, 'attack': 105, 'defense': 72, 'luck': 22, 'armor': 16, 'exp': 65, 'gooncoins': 125}
        ]
    },
    'trebic_downtown': {
        'name': 'Třebíč Downtown (Zoubelec Quarter)',
        'floors': 6,
        'base_level': 8,
        'locations': [
            {'id': 'panel_hell_gate', 'name': 'Panel Hell Gate', 'floor_range': [1, 2]},
            {'id': 'balikovna_stronghold', 'name': 'Balíkovna stronghold', 'floor_range': [3]},
            {'id': 'zoubo_passage', 'name': 'Zoubo-passage', 'floor_range': [4]},
            {'id': 'vodarna_peak', 'name': 'Vodárna peak', 'floor_range': [5]},
            {'id': 'parkoviste_sedikova', 'name': 'Parkoviště Šeříková', 'floor_range': [6]}
        ],
        'main_boss': {
            'name': 'Zoubelec – Obchodník s Chaosem',
            'floor': 6,
            'level': 25,
            'hp': 15000,
            'attack': 800,
            'defense': 600,
            'luck': 60,
            'armor': 90,
            'ultimate_attack': 'Neprodá ti to, co jsi chtěl – prodá ti to, co tě později bude mrzet.',
            'rewards': {'gooncoins': 12000, 'exp': 5000, 'rare_materials': {'chaos_merchant_token': 1}}
        },
        'minibosses': [
            {
                'name': 'Balíkovna Sentinel',
                'floor': 3,
                'level': 20,
                'hp': 9000,
                'attack': 600,
                'defense': 500,
                'luck': 45,
                'armor': 80,
                'rewards': {'gooncoins': 5000, 'exp': 2500}
            },
            {
                'name': 'Vodárna Guardian',
                'floor': 5,
                'level': 22,
                'hp': 10000,
                'attack': 650,
                'defense': 520,
                'luck': 50,
                'armor': 85,
                'rewards': {'gooncoins': 5500, 'exp': 2800}
            },
            {
                'name': 'Nocní Dealer Záhadných Předmětů',
                'floor': 4,
                'level': 21,
                'hp': 9500,
                'attack': 625,
                'defense': 510,
                'luck': 55,
                'armor': 82,
                'rewards': {'gooncoins': 5200, 'exp': 2600}
            }
        ],
        'common_enemies': [
            {'name': 'Panelákový Šramot', 'hp': 1000, 'attack': 150, 'defense': 100, 'luck': 20, 'armor': 25, 'exp': 100, 'gooncoins': 200},
            {'name': 'Passage Goblin (Zoubo Runner)', 'hp': 900, 'attack': 140, 'defense': 95, 'luck': 25, 'armor': 22, 'exp': 90, 'gooncoins': 180},
            {'name': 'Parkovištní Stínový Řidič', 'hp': 1100, 'attack': 160, 'defense': 105, 'luck': 18, 'armor': 28, 'exp': 110, 'gooncoins': 220},
            {'name': 'Vítr z Vodárny Elementál', 'hp': 950, 'attack': 145, 'defense': 98, 'luck': 22, 'armor': 24, 'exp': 95, 'gooncoins': 190},
            {'name': 'Zoubo Flyer Swarm', 'hp': 850, 'attack': 135, 'defense': 92, 'luck': 28, 'armor': 20, 'exp': 85, 'gooncoins': 170}
        ]
    },
    'ota_asthma_citadel': {
        'name': "Ota's Asthma Citadel",
        'floors': 6,
        'base_level': 12,
        'locations': [
            {'id': 'inhalatorova_komnata', 'name': 'Inhalátorová komnata', 'floor_range': [1, 2]},
            {'id': 'anti_apple_zona', 'name': 'Anti-Apple zóna', 'floor_range': [3]},
            {'id': 'strechy_treninkove_pole', 'name': 'Střešní tréninkové pole', 'floor_range': [4]},
            {'id': 'fabia_workshop', 'name': 'Fabia Workshop', 'floor_range': [5]},
            {'id': 'venkovni_astmaticky_dvur', 'name': 'Venkovní astmatický dvůr', 'floor_range': [6]}
        ],
        'main_boss': {
            'name': 'Ota – Astmatický Král Odporu',
            'floor': 6,
            'level': 30,
            'hp': 20000,
            'attack': 1000,
            'defense': 750,
            'luck': 70,
            'armor': 120,
            'ultimate_attack': 'Tilt z Clash Royale + Střechařská magie',
            'weakness': ['uzené mrkve', 'jablka', 'běh do kopce'],
            'strength': ['tilt z Clash Royale', 'skicování střech', 'mechanická Fabia magie'],
            'rewards': {'gooncoins': 20000, 'exp': 8000, 'rare_materials': {'asthma_crown': 1}}
        },
        'minibosses': [
            {
                'name': 'Elementál Uzené Mrkve – Dusivý Revenant',
                'floor': 2,
                'level': 18,
                'hp': 8000,
                'attack': 550,
                'defense': 450,
                'luck': 40,
                'armor': 70,
                'rewards': {'gooncoins': 4000, 'exp': 2000}
            },
            {
                'name': 'Clash Royale Spirit – Přízrak Tiltu',
                'floor': 4,
                'level': 24,
                'hp': 11000,
                'attack': 700,
                'defense': 580,
                'luck': 50,
                'armor': 90,
                'rewards': {'gooncoins': 6000, 'exp': 3000}
            },
            {
                'name': 'Anti-Apple Golem – Strážce Ovocného Zákazu',
                'floor': 3,
                'level': 20,
                'hp': 9500,
                'attack': 600,
                'defense': 500,
                'luck': 35,
                'armor': 80,
                'rewards': {'gooncoins': 4500, 'exp': 2200}
            },
            {
                'name': 'Sestřina Hot-Aura',
                'floor': 5,
                'level': 26,
                'hp': 12000,
                'attack': 750,
                'defense': 600,
                'luck': 45,
                'armor': 100,
                'rewards': {'gooncoins': 6500, 'exp': 3200}
            }
        ],
        'common_enemies': [
            {'name': 'Inhalátorový Imp', 'hp': 1200, 'attack': 180, 'defense': 120, 'luck': 25, 'armor': 30, 'exp': 120, 'gooncoins': 250},
            {'name': 'Fabia Mechanic Gremlin', 'hp': 1300, 'attack': 190, 'defense': 125, 'luck': 22, 'armor': 32, 'exp': 130, 'gooncoins': 270},
            {'name': 'Střechařský Sketch Fiend', 'hp': 1100, 'attack': 170, 'defense': 115, 'luck': 28, 'armor': 28, 'exp': 110, 'gooncoins': 230},
            {'name': 'Astma Fog', 'hp': 1000, 'attack': 160, 'defense': 110, 'luck': 30, 'armor': 25, 'exp': 100, 'gooncoins': 210},
            {'name': 'Jablečné Přeludy', 'hp': 1400, 'attack': 200, 'defense': 130, 'luck': 20, 'armor': 35, 'exp': 140, 'gooncoins': 290}
        ]
    }
}

# Blacksmith System
BLACKSMITH_UPGRADE_COSTS = {
    1: {'metal': 500, 'souls': 50},
    2: {'metal': 1250, 'souls': 125},
    3: {'metal': 2500, 'souls': 250},
    4: {'metal': 5000, 'souls': 500},
    5: {'metal': 10000, 'souls': 1000}
}

BLACKSMITH_REFORGE_COST = {'metal': 2500, 'souls': 250, 'gold': 25000}
BLACKSMITH_DISASSEMBLE_RETURN = 0.5  # 50% materials back

# Guild System
GUILD_BONUS_BASE = {
    'exp': 0.05,  # 5% base exp bonus
    'gold': 0.05  # 5% base gooncoins bonus (kept as 'gold' in DB for compatibility)
}

GUILD_WAR_DURATION = 3600  # 1 hour in seconds

# Arena Honor System
ARENA_HONOR_REWARDS = {
    'win': 10,
    'loss': 2,
    'draw': 5
}

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
    for column, ddl in [
        ('is_admin', 'INTEGER DEFAULT 0'),
        ('hide_from_leaderboard', 'INTEGER DEFAULT 0')
    ]:
        try:
            c.execute(f'ALTER TABLE users ADD COLUMN {column} {ddl}')
        except sqlite3.OperationalError:
            pass
    
    # Game state table
    c.execute('''CREATE TABLE IF NOT EXISTS game_state
                 (user_id INTEGER PRIMARY KEY,
                  gooncoins REAL DEFAULT 0,
                  astma REAL DEFAULT 0,
                  poharky REAL DEFAULT 0,
                  mrkev REAL DEFAULT 0,
                  uzené REAL DEFAULT 0,
                  logs REAL DEFAULT 0,
                  planks REAL DEFAULT 0,
                  grain REAL DEFAULT 0,
                  flour REAL DEFAULT 0,
                  bread REAL DEFAULT 0,
                  fish REAL DEFAULT 0,
                  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  total_clicks INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Migration: ensure all resource columns exist (older DBs may miss them)
    for column in ['astma', 'poharky', 'mrkev', 'uzené', *SECONDARY_RESOURCES]:
        try:
            c.execute(f'ALTER TABLE game_state ADD COLUMN "{column}" REAL DEFAULT 0')
        except sqlite3.OperationalError:
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
        ('last_valuation', "REAL DEFAULT 0"),
        ('upgrade_level', "INTEGER DEFAULT 0")
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
    
    # Gems table - Drahokamy
    c.execute('''CREATE TABLE IF NOT EXISTS gems
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  gem_type TEXT NOT NULL,
                  level INTEGER DEFAULT 1,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  UNIQUE(user_id, gem_type))''')
    
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
    
    # Gambling log table
    c.execute('''CREATE TABLE IF NOT EXISTS gambling_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  game_type TEXT NOT NULL,
                  bet_amount REAL NOT NULL,
                  currency TEXT NOT NULL,
                  result TEXT DEFAULT '{}',
                  winnings REAL DEFAULT 0,
                  net_gain REAL DEFAULT 0,
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
    now_iso = datetime.now(timezone.utc).isoformat()
    for currency in TRADEABLE_CURRENCIES:
        c.execute('''INSERT OR IGNORE INTO market_state (currency, price_multiplier, net_flow, last_update)
                     VALUES (?, 1.0, 0, ?)''', (currency, now_iso))
    
    # Character stats table
    c.execute('''CREATE TABLE IF NOT EXISTS character_stats
                 (user_id INTEGER PRIMARY KEY,
                  level INTEGER DEFAULT 1,
                  experience REAL DEFAULT 0,
                  strength INTEGER DEFAULT 10,
                  dexterity INTEGER DEFAULT 10,
                  intelligence INTEGER DEFAULT 10,
                  constitution INTEGER DEFAULT 10,
                  luck INTEGER DEFAULT 10,
                  available_points INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Item definitions table (all available items in the game)
    c.execute('''CREATE TABLE IF NOT EXISTS item_definitions
                 (item_id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  slot TEXT NOT NULL,
                  bonus TEXT NOT NULL,
                  cost TEXT NOT NULL,
                  image TEXT,
                  unlock_requirement TEXT,
                  rarity TEXT DEFAULT 'common',
                  power INTEGER DEFAULT 0,
                  release_order INTEGER DEFAULT 0,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Item marketplace table (player-to-player trading)
    c.execute('''CREATE TABLE IF NOT EXISTS item_marketplace
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  seller_id INTEGER NOT NULL,
                  item_instance_id INTEGER NOT NULL,
                  price REAL NOT NULL,
                  currency TEXT DEFAULT 'gooncoins',
                  status TEXT DEFAULT 'active',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  expires_at TIMESTAMP,
                  FOREIGN KEY (seller_id) REFERENCES users(id),
                  FOREIGN KEY (item_instance_id) REFERENCES equipment(id))''')
    
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
    
    # Microtransactions: Premium currency (Gems/Drahokamy)
    c.execute('''CREATE TABLE IF NOT EXISTS premium_currency
                 (user_id INTEGER PRIMARY KEY,
                  gems INTEGER DEFAULT 0,
                  total_spent REAL DEFAULT 0,
                  total_earned INTEGER DEFAULT 0,
                  last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Microtransactions: Purchase history
    c.execute('''CREATE TABLE IF NOT EXISTS microtransactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  purchase_type TEXT NOT NULL,
                  item_id TEXT,
                  item_name TEXT,
                  cost_gems INTEGER DEFAULT 0,
                  cost_real_money REAL DEFAULT 0,
                  rewards TEXT DEFAULT '{}',
                  status TEXT DEFAULT 'completed',
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Active boosts from microtransactions
    c.execute('''CREATE TABLE IF NOT EXISTS active_boosts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  boost_type TEXT NOT NULL,
                  multiplier REAL DEFAULT 1.0,
                  expires_at TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Quest system (Tavern/Hospoda)
    c.execute('''CREATE TABLE IF NOT EXISTS quests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  quest_id TEXT NOT NULL,
                  duration_seconds INTEGER NOT NULL,
                  reward_exp REAL NOT NULL,
                  reward_gold REAL NOT NULL,
                  reward_item_id TEXT,
                  difficulty INTEGER DEFAULT 1,
                  started_at TEXT NOT NULL,
                  completed_at TEXT,
                  status TEXT DEFAULT 'active',
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Available quests pool (3 random quests per user)
    c.execute('''CREATE TABLE IF NOT EXISTS available_quests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  quest_id TEXT NOT NULL,
                  duration_seconds INTEGER NOT NULL,
                  reward_exp REAL NOT NULL,
                  reward_gold REAL NOT NULL,
                  reward_item_id TEXT,
                  difficulty INTEGER DEFAULT 1,
                  generated_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Dungeons system
    c.execute('''CREATE TABLE IF NOT EXISTS dungeons
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  dungeon_id TEXT NOT NULL,
                  current_floor INTEGER DEFAULT 1,
                  max_floor INTEGER DEFAULT 10,
                  completed_floors TEXT DEFAULT '[]',
                  last_attempt TEXT,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Guilds system
    c.execute('''CREATE TABLE IF NOT EXISTS guilds
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL UNIQUE,
                  description TEXT,
                  leader_id INTEGER,
                  exp_bonus REAL DEFAULT 0,
                  gold_bonus REAL DEFAULT 0,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (leader_id) REFERENCES users(id))''')
    
    # Guild members
    c.execute('''CREATE TABLE IF NOT EXISTS guild_members
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  role TEXT DEFAULT 'member',
                  joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (guild_id) REFERENCES guilds(id),
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  UNIQUE(guild_id, user_id))''')
    
    # Guild wars
    c.execute('''CREATE TABLE IF NOT EXISTS guild_wars
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  guild1_id INTEGER NOT NULL,
                  guild2_id INTEGER NOT NULL,
                  started_at TEXT NOT NULL,
                  ended_at TEXT,
                  winner_id INTEGER,
                  status TEXT DEFAULT 'active',
                  FOREIGN KEY (guild1_id) REFERENCES guilds(id),
                  FOREIGN KEY (guild2_id) REFERENCES guilds(id),
                  FOREIGN KEY (winner_id) REFERENCES guilds(id))''')
    
    # Blacksmith materials
    c.execute('''CREATE TABLE IF NOT EXISTS blacksmith_materials
                 (user_id INTEGER PRIMARY KEY,
                  metal INTEGER DEFAULT 0,
                  souls INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Mount system
    c.execute('''CREATE TABLE IF NOT EXISTS mounts
                 (user_id INTEGER PRIMARY KEY,
                  mount_type TEXT DEFAULT 'none',
                  speed_reduction INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Honor/Čest for Arena
    c.execute('''CREATE TABLE IF NOT EXISTS arena_honor
                 (user_id INTEGER PRIMARY KEY,
                  honor INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Add class to character_stats (migration)
    try:
        c.execute('ALTER TABLE character_stats ADD COLUMN class TEXT DEFAULT "warrior"')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add mushrooms to premium_currency (migration)
    try:
        c.execute('ALTER TABLE premium_currency ADD COLUMN mushrooms INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add gold to game_state (migration) - separate from gooncoins
    try:
        c.execute('ALTER TABLE game_state ADD COLUMN gold REAL DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add equipped equipment to character_stats (merge equipment + postava)
    for column, ddl in [
        ('equipped_weapon', 'TEXT'),
        ('equipped_armor', 'TEXT'),
        ('equipped_helmet', 'TEXT'),
        ('equipped_ring', 'TEXT'),
        ('equipped_amulet', 'TEXT'),
        ('equipped_boots', 'TEXT'),
        ('equipped_shield', 'TEXT'),
        ('equipped_vehicle', 'TEXT')
    ]:
        try:
            c.execute(f'ALTER TABLE character_stats ADD COLUMN {column} {ddl}')
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Add battle data to dungeons (merge dungeons + boj)
    for column, ddl in [
        ('last_battle_result', 'TEXT'),
        ('last_battle_enemy', 'TEXT'),
        ('last_battle_rounds', 'INTEGER DEFAULT 0'),
        ('total_battles', 'INTEGER DEFAULT 0'),
        ('total_wins', 'INTEGER DEFAULT 0'),
        ('total_losses', 'INTEGER DEFAULT 0'),
        ('battle_history', 'TEXT DEFAULT "[]"')
    ]:
        try:
            c.execute(f'ALTER TABLE dungeons ADD COLUMN {column} {ddl}')
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Friendships table
    c.execute('''CREATE TABLE IF NOT EXISTS friendships
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user1_id INTEGER NOT NULL,
                  user2_id INTEGER NOT NULL,
                  status TEXT DEFAULT 'pending',
                  requested_by INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user1_id) REFERENCES users(id),
                  FOREIGN KEY (user2_id) REFERENCES users(id),
                  FOREIGN KEY (requested_by) REFERENCES users(id),
                  UNIQUE(user1_id, user2_id),
                  CHECK(user1_id != user2_id))''')
    
    # Garden system tables
    c.execute('''CREATE TABLE IF NOT EXISTS garden_plots
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  seed_id TEXT NOT NULL,
                  seed_name TEXT NOT NULL,
                  produces TEXT NOT NULL,
                  planted_at TEXT NOT NULL,
                  growth_time INTEGER NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Migration: add missing columns to garden_plots if they don't exist
    for column, ddl in [
        ('seed_name', 'TEXT DEFAULT ""'),
        ('produces', 'TEXT DEFAULT ""'),
        ('planted_at', 'TEXT DEFAULT CURRENT_TIMESTAMP'),
        ('growth_time', 'INTEGER DEFAULT 0'),
        ('ready_at', 'TEXT')
    ]:
        try:
            c.execute(f'ALTER TABLE garden_plots ADD COLUMN {column} {ddl}')
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    c.execute('''CREATE TABLE IF NOT EXISTS garden_fruits
                 (user_id INTEGER PRIMARY KEY,
                  fruit_common INTEGER DEFAULT 0,
                  fruit_rare INTEGER DEFAULT 0,
                  fruit_epic INTEGER DEFAULT 0,
                  fruit_legendary INTEGER DEFAULT 0,
                  fruit_unique INTEGER DEFAULT 0,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Pets table
    c.execute('''CREATE TABLE IF NOT EXISTS pets
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  pet_id TEXT NOT NULL,
                  level INTEGER DEFAULT 1,
                  experience INTEGER DEFAULT 0,
                  active INTEGER DEFAULT 0,
                  acquired_at TEXT DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Migration: add custom_name column to pets
    try:
        c.execute('ALTER TABLE pets ADD COLUMN custom_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()

def ensure_admin_account():
    """
    Create or refresh a default admin testing account so that we always
    have a dedicated profile which can be hidden from the leaderboard.
    """
    admin_username = os.environ.get('LUGOG_ADMIN_USER', 'Ota')
    admin_password = os.environ.get('LUGOG_ADMIN_PASS', 'Ota')
    password_hash = generate_password_hash(admin_password)
    
    conn = sqlite3.connect('lugog_clicker.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('SELECT id FROM users WHERE username = ?', (admin_username,))
    user = c.fetchone()
    
    if user:
        user_id = user['id']
        c.execute('''UPDATE users
                     SET password_hash = ?, is_admin = 1, hide_from_leaderboard = 1
                     WHERE id = ?''', (password_hash, user_id))
    else:
        c.execute('''INSERT INTO users (username, password_hash, is_admin, hide_from_leaderboard)
                     VALUES (?, ?, 1, 1)''', (admin_username, password_hash))
        user_id = c.lastrowid
    
    c.execute('''INSERT OR IGNORE INTO game_state
                 (user_id, gooncoins, astma, poharky, mrkev, uzené)
                 VALUES (?, 0, 0, 0, 0, 0)''', (user_id,))
    c.execute('''INSERT OR IGNORE INTO story_progress
                 (user_id, current_chapter, completed_quests, unlocked_buildings, unlocked_currencies)
                 VALUES (?, 1, '[]', '[]', '["gooncoins"]')''', (user_id,))
    c.execute('INSERT OR IGNORE INTO rare_materials (user_id) VALUES (?)', (user_id,))
    c.execute('INSERT OR IGNORE INTO combat_profiles (user_id) VALUES (?)', (user_id,))
    
    conn.commit()
    conn.close()

init_db()
ensure_admin_account()

def get_db():
    conn = sqlite3.connect('lugog_clicker.db', timeout=20.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent access
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def get_item_definition(item_id):
    """Get item definition from database, fallback to EQUIPMENT_DEFS"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM item_definitions WHERE item_id = ?', (item_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'item_id': row['item_id'],
            'name': row['name'],
            'slot': row['slot'],
            'bonus': json.loads(row['bonus']) if row['bonus'] else {},
            'cost': json.loads(row['cost']) if row['cost'] else {},
            'image': row['image'],
            'unlock_requirement': json.loads(row['unlock_requirement']) if row['unlock_requirement'] else None,
            'rarity': row['rarity'],
            'power': row['power'],
            'release_order': row['release_order'],
            'description': row['description'] if 'description' in row.keys() else None
        }
    # Fallback to EQUIPMENT_DEFS for backwards compatibility
    return EQUIPMENT_DEFS.get(item_id, {})

def get_all_item_definitions():
    """Get all item definitions from database as dict"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM item_definitions ORDER BY release_order, name')
    rows = c.fetchall()
    conn.close()
    
    items = {}
    for row in rows:
        items[row['item_id']] = {
            'item_id': row['item_id'],
            'name': row['name'],
            'slot': row['slot'],
            'bonus': json.loads(row['bonus']) if row['bonus'] else {},
            'cost': json.loads(row['cost']) if row['cost'] else {},
            'image': row['image'],
            'unlock_requirement': json.loads(row['unlock_requirement']) if row['unlock_requirement'] else None,
            'rarity': row['rarity'],
            'power': row['power'],
            'release_order': row['release_order'],
            'description': row['description'] if 'description' in row.keys() else None
        }
    return items

# Migrate EQUIPMENT_DEFS to database
def migrate_equipment_to_db():
    """Migrate EQUIPMENT_DEFS to item_definitions table"""
    conn = get_db()
    c = conn.cursor()
    
    for item_id, item_def in EQUIPMENT_DEFS.items():
        bonus_json = json.dumps(item_def.get('bonus', {}))
        cost_json = json.dumps(item_def.get('cost', {}))
        unlock_req_json = json.dumps(item_def.get('unlock_requirement')) if item_def.get('unlock_requirement') else None
        
        c.execute('''INSERT OR REPLACE INTO item_definitions
                     (item_id, name, slot, bonus, cost, image, unlock_requirement, rarity, power, release_order, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                 (item_id,
                  item_def.get('name', item_id),
                  item_def.get('slot', 'special'),
                  bonus_json,
                  cost_json,
                  item_def.get('image'),
                  unlock_req_json,
                  item_def.get('rarity', 'common'),
                  item_def.get('power', 0),
                  item_def.get('release_order', 0)))
    
    conn.commit()
    conn.close()

# Migration will be called after EQUIPMENT_DEFS is defined (see end of file)

def admin_api_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            return jsonify({'error': 'Admin access required'}), 403
        return func(*args, **kwargs)
    return wrapper

def ensure_economy_row(cursor):
    cursor.execute('''INSERT OR IGNORE INTO economy_state (id, gooncoin_supply, inflation_rate, last_adjustment)
                      VALUES (1, 0, ?, CURRENT_TIMESTAMP)''', (BASE_INFLATION_RATE,))

def parse_timestamp(value):
    if not value:
        return None
    # If it's already a datetime object, return it
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
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
    definition = get_item_definition(item_id)
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
    now_iso = datetime.now(timezone.utc).isoformat()
    all_items = get_all_item_definitions()
    for item_id in all_items.keys():
        base_value = calculate_item_base_value(item_id)
        cursor.execute('''INSERT OR IGNORE INTO item_market_state
                          (item_id, price_multiplier, net_flow, base_value, last_price, last_trend, total_minted, total_burned, last_update)
                          VALUES (?, 1.0, 0, ?, ?, 'flat', 0, 0, ?)''',
                       (item_id, base_value, base_value, now_iso))
        cursor.execute('UPDATE item_market_state SET base_value = ? WHERE item_id = ?', (base_value, item_id))


def _decay_item_market_row(row, now):
    last_update = parse_timestamp(row['last_update'])
    if last_update is None:
        last_update = now
    # Ensure both are datetime objects
    if not isinstance(now, datetime) or not isinstance(last_update, datetime):
        raise TypeError(f"Invalid datetime types: now={type(now)}, last_update={type(last_update)}")
    # Normalize timezone: if last_update is naive, assume it's UTC and make it aware
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    # Ensure now is also timezone-aware (should be, but just in case)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
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
    now = now or datetime.now(timezone.utc)
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
    now = now or datetime.now(timezone.utc)
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
        # Prodáváme za plnou tržní cenu (100%)
        sell_value = round(market_value, 2)
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
        definition = get_item_definition(equipment_id)
        
        # Check if it's a fruit - use fruit definition if available
        fruit_def = FRUIT_DEFS.get(equipment_id)
        if fruit_def:
            item_name = fruit_def['name']
            item_icon = fruit_def['icon']
            rarity = fruit_def['rarity']
            slot = row['equipment_slot'] or 'special'
        else:
            item_name = definition.get('name', equipment_id)
            item_icon = definition.get('icon') or definition.get('image')
            rarity = definition.get('rarity', 'common')
            slot = definition.get('slot', row['equipment_slot'])
        
        market_info = item_market.get(equipment_id, {})
        base_value = market_info.get('base_value', calculate_item_base_value(equipment_id))
        market_value = market_info.get('market_value', base_value)
        # Prodáváme za plnou tržní cenu (100%)
        sell_value = market_info.get('sell_value', round(market_value, 2))
        estimated_value += sell_value
        if row['equipped']:
            equipped_count += 1
        rarity_breakdown[rarity] = rarity_breakdown.get(rarity, 0) + 1
        per_item_counts[equipment_id] = per_item_counts.get(equipment_id, 0) + 1
        
        item_data = {
            'instance_id': row['id'],
            'equipment_id': equipment_id,
            'slot': slot,
            'name': item_name,
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
        }
        
        # Add icon and image for items
        if fruit_def:
            # For fruits, use emoji icon
            item_data['icon'] = item_icon
            item_data['item_type'] = 'fruit'
        else:
            # For equipment, prefer image over icon
            if definition.get('image'):
                item_data['image'] = definition['image']
            elif item_icon:
                item_data['icon'] = item_icon
        
        items.append(item_data)
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
        'updated_at': datetime.now(timezone.utc).isoformat()
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
    now_iso = datetime.now(timezone.utc).isoformat()
    for currency in TRADEABLE_CURRENCIES:
        cursor.execute('''INSERT OR IGNORE INTO market_state (currency, price_multiplier, net_flow, last_update)
                          VALUES (?, 1.0, 0, ?)''', (currency, now_iso))


def _decay_market_row(row, now):
    last_update = parse_timestamp(row['last_update'])
    if last_update is None:
        last_update = now
    # Ensure both are datetime objects
    if not isinstance(now, datetime) or not isinstance(last_update, datetime):
        raise TypeError(f"Invalid datetime types: now={type(now)}, last_update={type(last_update)}")
    # Normalize timezone: if last_update is naive, assume it's UTC and make it aware
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    # Ensure now is also timezone-aware (should be, but just in case)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
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
    now = now or datetime.now(timezone.utc)
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
    now = now or datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
    last_adjustment = parse_timestamp(row['last_adjustment']) if row else None
    if last_adjustment and last_adjustment.tzinfo is None:
        last_adjustment = last_adjustment.replace(tzinfo=timezone.utc)
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
    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor.execute('INSERT OR IGNORE INTO rare_materials (user_id) VALUES (?)', (user_id,))
            cursor.connection.commit()
            cursor.execute('SELECT * FROM rare_materials WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                continue
            raise

def ensure_combat_profile(cursor, user_id):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor.execute('INSERT OR IGNORE INTO combat_profiles (user_id) VALUES (?)', (user_id,))
            cursor.connection.commit()
            cursor.execute('SELECT * FROM combat_profiles WHERE user_id = ?', (user_id,))
            return cursor.fetchone()
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower() and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                continue
            raise

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
    now = datetime.now(timezone.utc)
    
    cooldown_until = parse_timestamp(temple_row['cooldown_until'] if temple_row and 'cooldown_until' in temple_row.keys() else None)
    if cooldown_until and cooldown_until.tzinfo is None:
        cooldown_until = cooldown_until.replace(tzinfo=timezone.utc)
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
        if expires and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
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

def ensure_character_stats(cursor, user_id):
    cursor.execute('SELECT * FROM character_stats WHERE user_id = ?', (user_id,))
    stats = cursor.fetchone()
    if not stats:
        cursor.execute('''INSERT INTO character_stats 
                          (user_id, level, experience, strength, dexterity, intelligence, constitution, luck, available_points, class)
                          VALUES (?, 1, 0, 10, 10, 10, 10, 10, 0, 'warrior')''', (user_id,))
        cursor.connection.commit()
        cursor.execute('SELECT * FROM character_stats WHERE user_id = ?', (user_id,))
        stats = cursor.fetchone()
    # Ensure class exists (migration)
    if stats:
        # Check if 'class' column exists and has a value
        try:
            class_value = stats['class']
            if not class_value:
                cursor.execute('UPDATE character_stats SET class = ? WHERE user_id = ?', ('warrior', user_id))
                cursor.connection.commit()
                cursor.execute('SELECT * FROM character_stats WHERE user_id = ?', (user_id,))
                stats = cursor.fetchone()
        except (KeyError, IndexError):
            # Column doesn't exist, try to add it
            try:
                cursor.execute('ALTER TABLE character_stats ADD COLUMN class TEXT DEFAULT "warrior"')
                cursor.connection.commit()
                cursor.execute('SELECT * FROM character_stats WHERE user_id = ?', (user_id,))
                stats = cursor.fetchone()
            except sqlite3.OperationalError:
                # Column already exists or other error, just set default
                cursor.execute('UPDATE character_stats SET class = ? WHERE user_id = ? AND (class IS NULL OR class = "")', ('warrior', user_id))
                cursor.connection.commit()
                cursor.execute('SELECT * FROM character_stats WHERE user_id = ?', (user_id,))
                stats = cursor.fetchone()
    return stats

def sync_equipped_to_character_stats(cursor, user_id):
    """Sync currently equipped items to character_stats table (merge equipment + postava)"""
    cursor.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_items = {row['equipment_slot']: row['equipment_id'] for row in cursor.fetchall()}
    
    # Map slots to column names
    slot_to_column = {
        'weapon': 'equipped_weapon',
        'armor': 'equipped_armor',
        'helmet': 'equipped_helmet',
        'ring': 'equipped_ring',
        'amulet': 'equipped_amulet',
        'boots': 'equipped_boots',
        'shield': 'equipped_shield',
        'vehicle': 'equipped_vehicle'  # Vehicle slot
    }
    
    # Build update query
    updates = []
    values = []
    for slot, column in slot_to_column.items():
        equipment_id = equipped_items.get(slot)
        updates.append(f'{column} = ?')
        values.append(equipment_id if equipment_id else None)
    
    if updates:
        values.append(user_id)
        cursor.execute(f'''UPDATE character_stats 
                          SET {', '.join(updates)}
                          WHERE user_id = ?''', values)

def get_effective_character_stats(cursor, user_id):
    """Get character stats with equipment bonuses applied"""
    char_stats = ensure_character_stats(cursor, user_id)
    strength = char_stats['strength'] if char_stats else 10
    dexterity = char_stats['dexterity'] if char_stats else 10
    intelligence = char_stats['intelligence'] if char_stats else 10
    constitution = char_stats['constitution'] if char_stats else 10
    luck_stat = char_stats['luck'] if char_stats else 10
    
    # Get equipment stat bonuses with upgrade levels
    try:
        cursor.execute('SELECT equipment_id, upgrade_level FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
        equipped_items = cursor.fetchall()
    except:
        # Fallback if upgrade_level column doesn't exist
        cursor.execute('SELECT equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
        equipped_items = [{'equipment_id': row['equipment_id'], 'upgrade_level': 0} for row in cursor.fetchall()]
    
    for row in equipped_items:
        equipment_id = row['equipment_id']
        try:
            upgrade_level = row['upgrade_level'] if row['upgrade_level'] is not None else 0
        except (KeyError, IndexError):
            upgrade_level = 0
        definition = get_item_definition(equipment_id)
        bonus = definition.get('bonus', {})
        # Each upgrade level adds +1 to all stats that the item has
        upgrade_bonus = upgrade_level
        strength += (bonus.get('strength', 0) or 0) + (upgrade_bonus if bonus.get('strength') else 0)
        dexterity += (bonus.get('dexterity', 0) or 0) + (upgrade_bonus if bonus.get('dexterity') else 0)
        intelligence += (bonus.get('intelligence', 0) or 0) + (upgrade_bonus if bonus.get('intelligence') else 0)
        constitution += (bonus.get('constitution', 0) or 0) + (upgrade_bonus if bonus.get('constitution') else 0)
        luck_stat += (bonus.get('luck_stat', 0) or 0) + (upgrade_bonus if bonus.get('luck_stat') else 0)
    
    # Get class from char_stats (sqlite3.Row object, use bracket notation)
    char_class = 'warrior'
    if char_stats:
        try:
            char_class = char_stats['class'] if char_stats['class'] else 'warrior'
        except (KeyError, IndexError):
            char_class = 'warrior'
    
    return {
        'strength': strength,
        'dexterity': dexterity,
        'intelligence': intelligence,
        'constitution': constitution,
        'luck': luck_stat,
        'class': char_class
    }

def calculate_player_combat_stats(cursor, user_id):
    try:
        cursor.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ?', (user_id,))
        upgrades = {row['upgrade_type']: row['level'] for row in cursor.fetchall()}
    except Exception:
        upgrades = {}
    
    try:
        cursor.execute('SELECT building_type, level FROM buildings WHERE user_id = ?', (user_id,))
        buildings = {row['building_type']: row['level'] for row in cursor.fetchall()}
    except Exception:
        buildings = {}
    
    try:
        story = ensure_story_progress(cursor, user_id)
        current_chapter = story.get('current_chapter', 1) if story else 1
    except Exception:
        current_chapter = 1
    
    # Get character stats with equipment bonuses
    try:
        effective_stats = get_effective_character_stats(cursor, user_id)
        strength = effective_stats.get('strength', 10)
        dexterity = effective_stats.get('dexterity', 10)
        intelligence = effective_stats.get('intelligence', 10)
        constitution = effective_stats.get('constitution', 10)
        luck_stat = effective_stats.get('luck', 10)
    except Exception:
        strength = dexterity = intelligence = constitution = luck_stat = 10
    
    # Get gem bonuses
    gem_bonuses = {'strength': 0, 'dexterity': 0, 'intelligence': 0, 'constitution': 0, 'luck': 0}
    try:
        cursor.execute('SELECT gem_type, level FROM gems WHERE user_id = ?', (user_id,))
        gems = cursor.fetchall()
        for gem_row in gems:
            gem_type = gem_row['gem_type']
            gem_level = gem_row['level']
            gem_def = GEM_DEFINITIONS.get(gem_type)
            if gem_def:
                level_data = gem_def['levels'].get(gem_level, {})
                bonus = level_data.get('bonus', 0)
                stat_type = gem_def.get('stat_type')
                
                if stat_type == 'universal':
                    # Univerzální drahokam zvyšuje všechny staty
                    gem_bonuses['strength'] += bonus
                    gem_bonuses['dexterity'] += bonus
                    gem_bonuses['intelligence'] += bonus
                    gem_bonuses['constitution'] += bonus
                    gem_bonuses['luck'] += bonus
                elif stat_type in gem_bonuses:
                    gem_bonuses[stat_type] += bonus
    except Exception:
        pass
    
    # Apply gem bonuses to stats
    strength += gem_bonuses['strength']
    dexterity += gem_bonuses['dexterity']
    intelligence += gem_bonuses['intelligence']
    constitution += gem_bonuses['constitution']
    luck_stat += gem_bonuses['luck']
    
    try:
        cursor.execute('SELECT equipment_slot, equipment_id, upgrade_level FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
        equipped_items = cursor.fetchall()
    except Exception:
        # Fallback if upgrade_level column doesn't exist
        try:
            cursor.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
            equipped_items = [{'equipment_id': row['equipment_id'], 'upgrade_level': 0} for row in cursor.fetchall()]
        except:
            equipped_items = []
    
    eq_attack = 0
    eq_defense = 0
    eq_luck = 0
    for row in equipped_items:
        try:
            equipment_id = row['equipment_id']
            try:
                upgrade_level = row['upgrade_level'] if row['upgrade_level'] is not None else 0
            except (KeyError, IndexError):
                upgrade_level = 0
            definition = get_item_definition(equipment_id)
            bonus = definition.get('bonus', {})
            # Each upgrade level adds +1 to all stats that the item has
            upgrade_bonus = upgrade_level
            click_power = _bonus_value(bonus.get('click_power'))
            defense = _bonus_value(bonus.get('defense'))
            luck = _bonus_value(bonus.get('luck'))
            eq_attack += click_power + (upgrade_bonus if bonus.get('click_power') else 0)
            eq_defense += defense + (upgrade_bonus if bonus.get('defense') else 0)
            eq_luck += luck + (upgrade_bonus if bonus.get('luck') else 0)
        except Exception:
            continue
    
    # Get active pets and apply their bonuses
    try:
        cursor.execute('SELECT pet_id FROM pets WHERE user_id = ? AND active = 1', (user_id,))
        active_pets = [row['pet_id'] for row in cursor.fetchall()]
    except Exception:
        active_pets = []
    
    pet_attack_mult = 1.0
    pet_defense_mult = 1.0
    pet_luck_mult = 1.0
    pet_hp_mult = 1.0
    for pet_id in active_pets:
        try:
            pet_def = PET_DEFS.get(pet_id, {})
            bonus = pet_def.get('bonus', {})
            if 'click_power' in bonus:
                pet_attack_mult *= bonus['click_power']
            if 'defense' in bonus:
                pet_defense_mult *= bonus['defense']
            if 'luck' in bonus:
                pet_luck_mult *= bonus['luck']
            if 'hp' in bonus:
                pet_hp_mult *= bonus['hp']
        except Exception:
            continue
    
    blessing_bonus = {}
    try:
        temple_row = ensure_temple_state(cursor, user_id)
        if temple_row:
            try:
                active_blessing = temple_row['active_blessing'] if 'active_blessing' in temple_row.keys() else None
            except (KeyError, IndexError):
                active_blessing = None
            
            if active_blessing:
                blessing_def = TEMPLE_BLESSINGS.get(active_blessing)
                try:
                    expires_at = temple_row['blessing_expires_at'] if 'blessing_expires_at' in temple_row.keys() else None
                except (KeyError, IndexError):
                    expires_at = None
                expires = parse_timestamp(expires_at)
                now = datetime.now(timezone.utc)
                if blessing_def and expires and expires > now:
                    blessing_bonus = blessing_def.get('bonus', {})
                elif active_blessing:
                    cursor.execute('UPDATE temple_state SET active_blessing = NULL, blessing_expires_at = NULL WHERE user_id = ?', (user_id,))
                    cursor.connection.commit()
    except Exception:
        pass
    
    click_power_levels = (upgrades.get('click_power_1', 0) + upgrades.get('click_power_2', 0))
    auto_generators = upgrades.get('auto_gooncoin', 0)
    
    # Character stats bonuses: strength affects attack, dexterity affects evasion/crit, intelligence affects earnings, constitution affects HP, luck affects crit/dodge
    char_attack_bonus = (strength - 10) * 1.2  # Each point above 10 adds 1.2 attack
    char_defense_bonus = (constitution - 10) * 0.8  # Each point above 10 adds 0.8 defense
    char_luck_bonus = (luck_stat - 10) * 0.15  # Each point above 10 adds 0.15 luck multiplier
    char_hp_bonus = (constitution - 10) * 8  # Each point above 10 adds 8 HP
    
    base_attack = 15 + click_power_levels * 4 + auto_generators * 0.8 + char_attack_bonus
    base_defense = 12 + buildings.get('temple', 0) * 5 + upgrades.get('uzené_collector', 0) * 1.5 + char_defense_bonus
    base_luck = 1 + (current_chapter - 1) * 0.2 + buildings.get('market', 0) * 0.1 + char_luck_bonus
    base_hp = 150 + buildings.get('workshop', 0) * 20 + upgrades.get('auto_gooncoin', 0) * 4 + char_hp_bonus
    
    # Apply pet multipliers
    final_attack = (base_attack + eq_attack + blessing_bonus.get('attack', 0)) * pet_attack_mult
    final_defense = (base_defense + eq_defense + blessing_bonus.get('defense', 0)) * pet_defense_mult
    final_luck = (base_luck + eq_luck + blessing_bonus.get('luck', 0)) * pet_luck_mult
    final_hp = (base_hp + (eq_defense * 6) + blessing_bonus.get('hp', 0)) * pet_hp_mult
    
    stats = {
        'attack': round(final_attack, 2),
        'defense': round(final_defense, 2),
        'luck': round(final_luck, 2),
        'hp': int(final_hp),
        'chapter': current_chapter,
        'evasion': round(5 + (dexterity - 10) * 0.5, 1),  # Dexterity affects evasion
        'critical_hit': round(5 + (dexterity - 10) * 0.3 + (luck_stat - 10) * 0.5, 1)  # Both dexterity and luck affect crit
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
        c.execute('SELECT id, password_hash, is_admin FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = username
            session['is_admin'] = bool(user['is_admin'])
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
        
        # Initialize character stats
        c.execute('''INSERT INTO character_stats 
                     (user_id, level, experience, strength, dexterity, intelligence, constitution, luck, available_points)
                     VALUES (?, 1, 0, 10, 10, 10, 10, 10, 0)''', (user_id,))
        
        # Initialize premium currency
        c.execute('INSERT INTO premium_currency (user_id, gems) VALUES (?, 0)', (user_id,))
        
        conn.commit()
        session['user_id'] = user_id
        session['username'] = username
        session['is_admin'] = False
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Uživatelské jméno již existuje'})

@app.route('/game')
def game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('game.html',
                           username=session.get('username', 'Hráč'),
                           is_admin=session.get('is_admin', False))

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
    
    # Get gems
    c.execute('SELECT gem_type, level FROM gems WHERE user_id = ?', (user_id,))
    gems_data = {row['gem_type']: row['level'] for row in c.fetchall()}
    
    rare_row = ensure_rare_materials(c, user_id)
    combat_profile = ensure_combat_profile(c, user_id)
    inventory_payload = build_inventory_payload(c, user_id)
    
    # Get premium currency
    c.execute('SELECT gems FROM premium_currency WHERE user_id = ?', (user_id,))
    premium_row = c.fetchone()
    gems = premium_row['gems'] if premium_row else 0
    
    # Get active boosts
    c.execute('''SELECT boost_type, multiplier, expires_at FROM active_boosts 
                 WHERE user_id = ? AND (expires_at IS NULL OR expires_at > datetime('now'))''', (user_id,))
    active_boosts = []
    for boost_row in c.fetchall():
        expires_at = boost_row['expires_at']
        if expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_dt < datetime.now(timezone.utc):
                    continue
            except:
                pass
        active_boosts.append({
            'type': boost_row['boost_type'],
            'multiplier': boost_row['multiplier'],
            'expires_at': expires_at
        })
    
    # Get pets
    c.execute('''SELECT id, pet_id, level, experience, active, acquired_at 
                 FROM pets WHERE user_id = ?''', (user_id,))
    pets_list = []
    active_pets = []
    for pet_row in c.fetchall():
        pet_def = PET_DEFS.get(pet_row['pet_id'], {})
        pet_data = {
            'id': pet_row['id'],
            'pet_id': pet_row['pet_id'],
            'name': pet_def.get('name', pet_row['pet_id']),
            'level': pet_row['level'],
            'experience': pet_row['experience'],
            'active': bool(pet_row['active']),
            'acquired_at': pet_row['acquired_at'],
            'max_level': pet_def.get('max_level', 20),
            'exp_per_level': pet_def.get('exp_per_level', 100),
            'rarity': pet_def.get('rarity', 'common'),
            'bonus': pet_def.get('bonus', {})
        }
        pets_list.append(pet_data)
        if pet_row['active']:
            active_pets.append(pet_data)
    
    if not state:
        return jsonify({'error': 'Game state not found'}), 404
    
    resources = extract_player_resources(state)
    
    # Parse story data
    completed_quests = json.loads(story['completed_quests']) if story and story['completed_quests'] else []
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    
    # Get generation rates
    generation_rates = {
        'gooncoins': upgrades.get('auto_gooncoin', 0) * 0.1
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
        'gems': gems,
        'active_boosts': active_boosts,
        'story': {
            'current_chapter': story['current_chapter'] if story else 1,
            'completed_quests': completed_quests,
            'unlocked_buildings': unlocked_buildings,
            'unlocked_currencies': unlocked_currencies
        },
        'equipment': equipped,
        'equipment_counts': equipment_counts,
        'buildings': buildings,
        'gems': gems_data,
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
    
    # Calculate click value (base + upgrades + intelligence bonus)
    click_value = 1.0
    c.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ? AND upgrade_type LIKE "click_power%"', (user_id,))
    for row in c.fetchall():
        click_value += row['level'] * 0.5
    
    # Intelligence bonus: each point above 10 adds 2% to click value
    effective_stats = get_effective_character_stats(c, user_id)
    intelligence = effective_stats['intelligence']
    intelligence_bonus = 1.0 + ((intelligence - 10) * 0.02)
    click_value = click_value * intelligence_bonus
    
    # Apply active pets bonuses
    c.execute('SELECT pet_id FROM pets WHERE user_id = ? AND active = 1', (user_id,))
    active_pets = [row['pet_id'] for row in c.fetchall()]
    pet_click_mult = 1.0
    for pet_id in active_pets:
        pet_def = PET_DEFS.get(pet_id, {})
        bonus = pet_def.get('bonus', {})
        if 'click_power' in bonus:
            pet_click_mult *= bonus['click_power']
    click_value = click_value * pet_click_mult
    
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
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            time_passed = (now - last_update).total_seconds()
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
    astma_rate = upgrades.get('auto_astma', 0) * 0.05
    poharky_rate = upgrades.get('auto_poharky', 0) * 0.03
    mrkev_rate = upgrades.get('auto_mrkev', 0) * 0.02
    uzené_rate = upgrades.get('auto_uzené', 0) * 0.01
    
    # Intelligence bonus: each point above 10 adds 2% to all generation rates
    effective_stats = get_effective_character_stats(c, user_id)
    intelligence = effective_stats['intelligence']
    intelligence_bonus = 1.0 + ((intelligence - 10) * 0.02)
    
    # Generation multiplier upgrades (multiplicative)
    gen_multiplier = 1.0
    for i in range(1, 5):  # generation_multiplier_1 through _4
        key = f'generation_multiplier_{i}'
        level = upgrades.get(key, 0)
        if level > 0:
            gen_multiplier *= (1.0 + level * 0.2)  # Each level adds 20% to generation
    
    # Global power upgrades (affects everything)
    global_multiplier = 1.0
    for i in range(1, 4):  # global_power_1 through _3
        key = f'global_power_{i}'
        level = upgrades.get(key, 0)
        if level > 0:
            global_multiplier *= (1.0 + level * 0.15)  # Each level adds 15%
    
    # Time acceleration upgrade
    time_accel = upgrades.get('time_acceleration', 0)
    if time_accel > 0:
        gen_multiplier *= (1.0 + time_accel * 0.3)  # Each level adds 30% generation speed
    
    # Infinity boost (affects everything)
    infinity = upgrades.get('infinity_boost', 0)
    if infinity > 0:
        gen_multiplier *= (1.0 + infinity * 1.0)  # Each level adds 100%
        global_multiplier *= (1.0 + infinity * 0.5)  # Also affects global
    
    # Apply all multipliers
    gooncoin_rate *= intelligence_bonus * gen_multiplier * global_multiplier
    astma_rate *= intelligence_bonus * gen_multiplier * global_multiplier
    poharky_rate *= intelligence_bonus * gen_multiplier * global_multiplier
    mrkev_rate *= intelligence_bonus * gen_multiplier * global_multiplier
    uzené_rate *= intelligence_bonus * gen_multiplier * global_multiplier
    
    if gooncoin_rate:
        generation['gooncoins'] = gooncoin_rate * time_passed
        resources['gooncoins'] += generation['gooncoins']
    
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
        # Basic click power upgrades
        'click_power_1': {'gooncoins': 10, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_power_2': {'gooncoins': 50, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_power_3': {'gooncoins': 500, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_power_4': {'gooncoins': 2500, 'astma': 50, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_power_5': {'gooncoins': 10000, 'astma': 200, 'poharky': 100, 'mrkev': 0, 'uzené': 0},
        'click_power_6': {'gooncoins': 50000, 'astma': 500, 'poharky': 300, 'mrkev': 150, 'uzené': 0},
        'click_power_7': {'gooncoins': 200000, 'astma': 1500, 'poharky': 1000, 'mrkev': 500, 'uzené': 300},
        'click_power_8': {'gooncoins': 1000000, 'astma': 5000, 'poharky': 3500, 'mrkev': 2000, 'uzené': 1500},
        
        # Auto-generators
        'auto_gooncoin': {'gooncoins': 100, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'auto_astma': {'gooncoins': 500, 'astma': 0, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'auto_poharky': {'gooncoins': 2000, 'astma': 100, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'auto_mrkev': {'gooncoins': 8000, 'astma': 300, 'poharky': 200, 'mrkev': 0, 'uzené': 0},
        'auto_uzené': {'gooncoins': 30000, 'astma': 800, 'poharky': 500, 'mrkev': 300, 'uzené': 0},
        
        # Multiplier upgrades (expensive, powerful)
        'click_multiplier_1': {'gooncoins': 5000, 'astma': 100, 'poharky': 0, 'mrkev': 0, 'uzené': 0},
        'click_multiplier_2': {'gooncoins': 25000, 'astma': 500, 'poharky': 300, 'mrkev': 0, 'uzené': 0},
        'click_multiplier_3': {'gooncoins': 150000, 'astma': 2000, 'poharky': 1500, 'mrkev': 800, 'uzené': 0},
        'click_multiplier_4': {'gooncoins': 750000, 'astma': 8000, 'poharky': 6000, 'mrkev': 4000, 'uzené': 2500},
        
        'generation_multiplier_1': {'gooncoins': 10000, 'astma': 200, 'poharky': 100, 'mrkev': 0, 'uzené': 0},
        'generation_multiplier_2': {'gooncoins': 50000, 'astma': 1000, 'poharky': 600, 'mrkev': 400, 'uzené': 0},
        'generation_multiplier_3': {'gooncoins': 300000, 'astma': 4000, 'poharky': 3000, 'mrkev': 2000, 'uzené': 1200},
        'generation_multiplier_4': {'gooncoins': 1500000, 'astma': 15000, 'poharky': 12000, 'mrkev': 8000, 'uzené': 5000},
        
        # Efficiency upgrades
        'cost_reduction_1': {'gooncoins': 15000, 'astma': 300, 'poharky': 200, 'mrkev': 100, 'uzené': 0},
        'cost_reduction_2': {'gooncoins': 100000, 'astma': 2000, 'poharky': 1500, 'mrkev': 1000, 'uzené': 600},
        'cost_reduction_3': {'gooncoins': 600000, 'astma': 10000, 'poharky': 8000, 'mrkev': 5000, 'uzené': 3000},
        
        # Prestige-like global upgrades
        'global_power_1': {'gooncoins': 50000, 'astma': 1000, 'poharky': 700, 'mrkev': 500, 'uzené': 300},
        'global_power_2': {'gooncoins': 300000, 'astma': 5000, 'poharky': 3500, 'mrkev': 2500, 'uzené': 1500},
        'global_power_3': {'gooncoins': 2000000, 'astma': 20000, 'poharky': 15000, 'mrkev': 10000, 'uzené': 8000},
        
        # Special late-game upgrades
        'quantum_click': {'gooncoins': 5000000, 'astma': 50000, 'poharky': 40000, 'mrkev': 30000, 'uzené': 20000},
        'time_acceleration': {'gooncoins': 10000000, 'astma': 100000, 'poharky': 80000, 'mrkev': 60000, 'uzené': 50000},
        'infinity_boost': {'gooncoins': 50000000, 'astma': 500000, 'poharky': 400000, 'mrkev': 300000, 'uzené': 250000},
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
    
    # Apply cost reduction upgrades
    c.execute('SELECT upgrade_type, level FROM upgrades WHERE user_id = ? AND upgrade_type LIKE "cost_reduction%"', (user_id,))
    cost_reduction = 1.0
    for row in c.fetchall():
        cost_reduction *= (1.0 - row['level'] * 0.05)  # Each level reduces cost by 5% (multiplicative)
    cost_reduction = max(0.1, cost_reduction)  # Cap at 90% reduction
    actual_cost = {
        'gooncoins': actual_cost['gooncoins'] * cost_reduction,
        'astma': actual_cost['astma'] * cost_reduction,
        'poharky': actual_cost['poharky'] * cost_reduction,
        'mrkev': actual_cost['mrkev'] * cost_reduction,
        'uzené': actual_cost['uzené'] * cost_reduction
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
                 WHERE COALESCE(u.hide_from_leaderboard, 0) = 0
                 ORDER BY gs.gooncoins DESC
                 LIMIT 10''')
    
    leaders = [{'username': row['username'], 
                'gooncoins': row['gooncoins'], 
                'total_clicks': row['total_clicks']} 
               for row in c.fetchall()]
    
    conn.close()
    return jsonify(leaders)

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if not session.get('is_admin'):
        return redirect(url_for('game'))
    return render_template('admin.html',
                           username=session.get('username', 'Admin'),
                           is_admin=True)

@app.route('/api/admin/overview')
@admin_api_required
def admin_overview():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) as count FROM users')
    total_users = c.fetchone()['count']
    
    c.execute('SELECT COUNT(*) as count FROM users WHERE COALESCE(hide_from_leaderboard, 0) = 1')
    hidden_players = c.fetchone()['count']
    
    c.execute('''SELECT COUNT(*) as count FROM game_state
                 WHERE COALESCE(gooncoins, 0) > 0 OR COALESCE(total_clicks, 0) > 0''')
    active_players = c.fetchone()['count']
    
    c.execute('SELECT COALESCE(SUM(gooncoins), 0) as total_gooncoins, '
              'COALESCE(AVG(gooncoins), 0) as average_gooncoins FROM game_state')
    totals_row = c.fetchone()
    total_gooncoins = totals_row['total_gooncoins'] if totals_row else 0
    average_gooncoins = totals_row['average_gooncoins'] if totals_row else 0
    
    c.execute('''SELECT u.id, u.username, u.created_at,
                        COALESCE(u.is_admin, 0) as is_admin,
                        COALESCE(u.hide_from_leaderboard, 0) as hide_from_leaderboard,
                        COALESCE(gs.gooncoins, 0) as gooncoins,
                        COALESCE(gs.total_clicks, 0) as total_clicks
                 FROM users u
                 LEFT JOIN game_state gs ON u.id = gs.user_id
                 ORDER BY gooncoins DESC, u.created_at ASC''')
    users = [{
        'id': row['id'],
        'username': row['username'],
        'created_at': row['created_at'],
        'is_admin': bool(row['is_admin']),
        'hidden': bool(row['hide_from_leaderboard']),
        'gooncoins': row['gooncoins'],
        'total_clicks': row['total_clicks']
    } for row in c.fetchall()]
    
    c.execute('SELECT username, created_at FROM users ORDER BY created_at DESC LIMIT 5')
    recent_users = [{
        'username': row['username'],
        'created_at': row['created_at']
    } for row in c.fetchall()]
    
    conn.close()
    return jsonify({
        'total_users': total_users,
        'active_players': active_players,
        'hidden_players': hidden_players,
        'total_gooncoins': total_gooncoins,
        'average_gooncoins': average_gooncoins,
        'recent_users': recent_users,
        'users': users
    })

@app.route('/api/admin/users/<int:user_id>/leaderboard', methods=['POST'])
@admin_api_required
def set_leaderboard_visibility(user_id):
    data = request.get_json() or {}
    hide = bool(data.get('hide', True))
    
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE users SET hide_from_leaderboard = ? WHERE id = ?', (1 if hide else 0, user_id))
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Uživatel nebyl nalezen'}), 404
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'user_id': user_id, 'hidden': hide})

# Equipment definitions - using actual image filenames from obrazky folder
# unlock_requirement: {'equipment_id': count} - odemkne se když máš X kusů daného equipmentu
# bonus can include:
#   - click_power, defense, luck: multipliers (e.g., 1.2 = +20%)
#   - strength, dexterity, intelligence, constitution, luck_stat: flat stat bonuses (e.g., 5 = +5 to that stat)
# Equipment stat bonuses are added to character base stats and affect all calculations
EQUIPMENT_DEFS = {
    'sword_basic': {
        'name': 'Základní Meč',
        'slot': 'weapon',
        'bonus': {'click_power': 1.2},
        'cost': {'gooncoins': 5000},
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
        'cost': {'gooncoins': 25000, 'astma': 500},
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
        'cost': {'gooncoins': 10000, 'poharky': 250},
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
        'cost': {'gooncoins': 7500},
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
        'cost': {'gooncoins': 15000, 'mrkev': 150},
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
        'cost': {'gooncoins': 20000, 'uzené': 100},
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
        'cost': {'gooncoins': 50000, 'astma': 2500, 'poharky': 1000},
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
        'cost': {'gooncoins': 75000, 'mrkev': 1500},
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
        'cost': {'gooncoins': 40000, 'poharky': 750},
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
        'cost': {'gooncoins': 45000, 'astma': 1250},
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
        'cost': {'gooncoins': 100000, 'uzené': 500},
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
        'cost': {'gooncoins': 35000, 'mrkev': 1000},
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
        'cost': {'gooncoins': 30000, 'astma': 2000},
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
        'cost': {'gooncoins': 60000, 'poharky': 1250},
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
        'cost': {'gooncoins': 25000, 'astma': 1500},
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
        'cost': {'gooncoins': 20000, 'poharky': 500},
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
        'cost': {'gooncoins': 17500, 'mrkev': 750},
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
        'cost': {'gooncoins': 55000, 'uzené': 250},
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
        'cost': {'gooncoins': 40000, 'poharky': 900},
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
        'cost': {'gooncoins': 65000, 'mrkev': 1250},
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
        'cost': {'gooncoins': 125000, 'uzené': 750, 'poharky': 1500},
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
        'cost': {'gooncoins': 125000, 'astma': 2000, 'mrkev': 1250},
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
        'cost': {'gooncoins': 105000, 'poharky': 1100, 'uzené': 600},
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
        'cost': {'gooncoins': 115000, 'poharky': 1600, 'mrkev': 600},
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
        'cost': {'gooncoins': 120000, 'poharky': 2000, 'uzené': 300},
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
        'cost': {'gooncoins': 100000, 'astma': 1250, 'mrkev': 900},
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
        'cost': {'gooncoins': 80000, 'astma': 1000, 'poharky': 750},
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
        'cost': {'gooncoins': 175000, 'poharky': 2250, 'uzené': 1000},
        'image': 'lugog.png',
        'unlock_requirement': {'opel': 5},
        'rarity': 'unique',
        'power': 58,
        'release_order': 28
    },
    # Dungeon-themed items - Kmochova Residence
    'jitcina_kuchyne_meč': {
        'name': 'Jitčin Kuchyňský Meč',
        'slot': 'weapon',
        'bonus': {'attack': 45, 'click_power': 1.3},
        'cost': {'gooncoins': 150000, 'astma': 1500, 'poharky': 800},
        'image': 'lugog.png',
        'unlock_requirement': {'sword_iron': 3},
        'rarity': 'epic',
        'power': 38,
        'release_order': 29,
        'description': 'Meč vykovaný v Jitčině kuchyni. Zvyšuje útok a sílu kliků. Získat lze v dungeonu Kmochova Residence.'
    },
    'rajcatova_svatyne_brneni': {
        'name': 'Rajčatové Brnění',
        'slot': 'armor',
        'bonus': {'defense': 55, 'hp': 200},
        'cost': {'gooncoins': 180000, 'mrkev': 2000, 'uzené': 1000},
        'image': 'lugog.png',
        'unlock_requirement': {'armor_leather': 5},
        'rarity': 'epic',
        'power': 42,
        'release_order': 30,
        'description': 'Brnění posvěcené v Rajčatové svatyni. Poskytuje silnou obranu. Získat lze v dungeonu Kmochova Residence.'
    },
    'fabie_arena_helma': {
        'name': 'Helma Řvoucí Fabie',
        'slot': 'helmet',
        'bonus': {'defense': 35, 'attack': 30, 'luck': 1.2},
        'cost': {'gooncoins': 200000, 'uzené': 1500, 'poharky': 1200},
        'image': 'lugog.png',
        'unlock_requirement': {'helmet_basic': 5},
        'rarity': 'legendary',
        'power': 48,
        'release_order': 31,
        'description': 'Helma z Předního dvora, kde řve Fabie. Kombinuje útok i obranu. Získat lze v dungeonu Kmochova Residence.'
    },
    # Dungeon-themed items - Gympl
    'skrinkovy_koridor_meč': {
        'name': 'Meč ze Skříňkového Koridoru',
        'slot': 'weapon',
        'bonus': {'attack': 60, 'strength': 15},
        'cost': {'gooncoins': 220000, 'astma': 2000, 'mrkev': 1500},
        'image': 'lugog.png',
        'unlock_requirement': {'rezava_katana': 2},
        'rarity': 'legendary',
        'power': 52,
        'release_order': 32,
        'description': 'Meč nalezený v temných skříňkách gymplu. Zvyšuje útok a sílu. Získat lze v dungeonu Gympl.'
    },
    'lustig_ucebna_amulet': {
        'name': 'Amulet z Lustigovy Učebny',
        'slot': 'amulet',
        'bonus': {'attack': 40, 'intelligence': 20, 'luck': 1.4},
        'cost': {'gooncoins': 190000, 'poharky': 1800, 'mrkev': 1200},
        'image': 'lugog.png',
        'unlock_requirement': {'amulet_luck': 5},
        'rarity': 'epic',
        'power': 44,
        'release_order': 33,
        'description': 'Amulet z linguistické učebny. Zvyšuje útok a inteligenci. Získat lze v dungeonu Gympl.'
    },
    'skully_shrine_prsten': {
        'name': 'Prsten ze Skully Shrine',
        'slot': 'ring',
        'bonus': {'attack': 50, 'defense': 40, 'luck': 1.3},
        'cost': {'gooncoins': 250000, 'uzené': 2000, 'poharky': 2000},
        'image': 'lugog.png',
        'unlock_requirement': {'ring_power': 5},
        'rarity': 'legendary',
        'power': 50,
        'release_order': 34,
        'description': 'Prsten z posvátné svatyně. Silně zvyšuje útok i obranu. Získat lze v dungeonu Gympl.'
    },
    'rodicak_hall_brneni': {
        'name': 'Brnění z Rodičáku',
        'slot': 'armor',
        'bonus': {'defense': 70, 'hp': 300, 'constitution': 25},
        'cost': {'gooncoins': 280000, 'uzené': 2500, 'astma': 1800},
        'image': 'lugog.png',
        'unlock_requirement': {'kevlar_vesta': 2},
        'rarity': 'unique',
        'power': 62,
        'release_order': 35,
        'description': 'Nejlepší brnění z Rodičáku. Poskytuje obrovskou obranu a HP. Získat lze v dungeonu Gympl.'
    },
    # Dungeon-themed items - Ota's Asthma Citadel
    'inhalatorova_komnata_meč': {
        'name': 'Astmatický Meč',
        'slot': 'weapon',
        'bonus': {'attack': 75, 'dexterity': 20, 'click_power': 1.4},
        'cost': {'gooncoins': 300000, 'astma': 3000, 'poharky': 2000},
        'image': 'inhalator.png',
        'unlock_requirement': {'sword_iron': 10},
        'rarity': 'legendary',
        'power': 58,
        'release_order': 36,
        'description': 'Meč z Inhalátorové komnaty. Silně zvyšuje útok a obratnost. Získat lze v dungeonu Ota\'s Asthma Citadel.'
    },
    'fabia_workshop_brneni': {
        'name': 'Fabia Workshop Brnění',
        'slot': 'armor',
        'bonus': {'defense': 80, 'attack': 35, 'hp': 250},
        'cost': {'gooncoins': 320000, 'uzené': 3000, 'astma': 2500},
        'image': 'opel.png',
        'unlock_requirement': {'bunda_po_dedovi': 5},
        'rarity': 'unique',
        'power': 65,
        'release_order': 37,
        'description': 'Brnění vyrobené v Fabia Workshopu. Kombinuje útok i obranu. Získat lze v dungeonu Ota\'s Asthma Citadel.'
    },
    'astmaticky_dvur_helma': {
        'name': 'Helma z Astmatického Dvora',
        'slot': 'helmet',
        'bonus': {'defense': 50, 'attack': 45, 'luck': 1.5, 'constitution': 20},
        'cost': {'gooncoins': 350000, 'astma': 3500, 'uzené': 2500},
        'image': 'lugog.png',
        'unlock_requirement': {'koruna_lugogu': 2},
        'rarity': 'unique',
        'power': 68,
        'release_order': 38,
        'description': 'Nejlepší helma z Venkovního astmatického dvora. Zvyšuje všechny bojové staty. Získat lze v dungeonu Ota\'s Asthma Citadel.'
    },
    'anti_apple_zona_meč': {
        'name': 'Anti-Apple Meč',
        'slot': 'weapon',
        'bonus': {'attack': 90, 'strength': 30, 'click_power': 1.5},
        'cost': {'gooncoins': 400000, 'mrkev': 4000, 'astma': 3000},
        'image': 'lugog.png',
        'unlock_requirement': {'jitcina_kuchyne_meč': 3},
        'rarity': 'unique',
        'power': 72,
        'release_order': 39,
        'description': 'Nejsilnější meč z Anti-Apple zóny. Obrovský útok. Získat lze v dungeonu Ota\'s Asthma Citadel.'
    },
    'ota_crown': {
        'name': 'Ota Koruna',
        'slot': 'helmet',
        'bonus': {'attack': 100, 'defense': 60, 'hp': 400, 'luck': 1.6, 'strength': 35},
        'cost': {'gooncoins': 500000, 'astma': 5000, 'uzené': 4000, 'mrkev': 3000},
        'image': 'lugog.png',
        'unlock_requirement': {'astmaticky_dvur_helma': 1},
        'rarity': 'unique',
        'power': 85,
        'release_order': 40,
        'description': 'Koruna Astmatického Krále. Nejlepší item z Ota\'s Asthma Citadel. Zvyšuje všechny staty.'
    },
    # Cross-dungeon items
    'dungeon_master_ring': {
        'name': 'Prsten Pána Dungeonů',
        'slot': 'ring',
        'bonus': {'attack': 70, 'defense': 50, 'luck': 1.8, 'hp': 350},
        'cost': {'gooncoins': 450000, 'uzené': 3500, 'poharky': 3000, 'mrkev': 2500},
        'image': 'lugog.png',
        'unlock_requirement': {'skully_shrine_prsten': 2, 'chytry_prsten': 2},
        'rarity': 'unique',
        'power': 75,
        'release_order': 41,
        'description': 'Prsten pro ty, kteří dokončili více dungeonů. Kombinuje sílu všech dungeonů.'
    },
    'dungeon_conqueror_armor': {
        'name': 'Brnění Dobyvatele Dungeonů',
        'slot': 'armor',
        'bonus': {'defense': 100, 'attack': 60, 'hp': 500, 'constitution': 40},
        'cost': {'gooncoins': 550000, 'uzené': 4500, 'astma': 4000, 'poharky': 3500},
        'image': 'lugog.png',
        'unlock_requirement': {'rodicak_hall_brneni': 1, 'fabia_workshop_brneni': 1},
        'rarity': 'unique',
        'power': 88,
        'release_order': 42,
        'description': 'Nejlepší brnění pro dobyvatele dungeonů. Kombinuje sílu všech tří hlavních dungeonů.'
    },
    # Crate items - Low tier
    'crate_sony_phone': {
        'name': 'Sony Telefon',
        'slot': 'accessory',
        'bonus': {'luck': 1.15},
        'cost': {'gooncoins': 8000},
        'image': 'sony.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 12,
        'release_order': 100
    },
    'crate_swiss_socks': {
        'name': 'Švýcarské Ponožky',
        'slot': 'accessory',
        'bonus': {'defense': 1.08},
        'cost': {'gooncoins': 6000},
        'image': 'switzerlandPonozky.png',
        'unlock_requirement': None,
        'rarity': 'common',
        'power': 10,
        'release_order': 101
    },
    'crate_basic_ring': {
        'name': 'Základní Prsten',
        'slot': 'ring',
        'bonus': {'click_power': 1.12, 'luck': 1.05},
        'cost': {'gooncoins': 12000},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 15,
        'release_order': 102
    },
    # Crate items - Mid tier
    'crate_samsung_phone': {
        'name': 'Samsung Telefon',
        'slot': 'accessory',
        'bonus': {'click_power': 1.25},
        'cost': {'gooncoins': 45000},
        'image': 'Samsung.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 22,
        'release_order': 103
    },
    'crate_realme_phone': {
        'name': 'Realme Telefon',
        'slot': 'accessory',
        'bonus': {'click_power': 1.18, 'luck': 1.1},
        'cost': {'gooncoins': 35000},
        'image': 'realme.png',
        'unlock_requirement': None,
        'rarity': 'rare',
        'power': 20,
        'release_order': 104
    },
    'crate_valley_cap': {
        'name': 'Valley Čepice',
        'slot': 'helmet',
        'bonus': {'defense': 1.25, 'click_power': 1.1},
        'cost': {'gooncoins': 40000},
        'image': 'valleyCepice.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 28,
        'release_order': 105
    },
    'crate_jordan_hoodie': {
        'name': 'Jordan Mikina',
        'slot': 'armor',
        'bonus': {'defense': 1.3, 'click_power': 1.15},
        'cost': {'gooncoins': 65000},
        'image': 'JordanMikina.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 32,
        'release_order': 106
    },
    # Crate items - High tier
    'crate_vivobook': {
        'name': 'Vivobook Laptop',
        'slot': 'accessory',
        'bonus': {'click_power': 1.5, 'luck': 1.2, 'intelligence': 25},
        'cost': {'gooncoins': 60000},
        'image': 'vivobook.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 45,
        'release_order': 107
    },
    'crate_premium_inhalator': {
        'name': 'Prémiový Inhalátor',
        'slot': 'accessory',
        'bonus': {'defense': 1.4, 'constitution': 20},
        'cost': {'gooncoins': 50000},
        'image': 'inhalator.png',
        'unlock_requirement': None,
        'rarity': 'epic',
        'power': 38,
        'release_order': 108
    },
    'crate_opel_vehicle': {
        'name': 'Opel Vozidlo',
        'slot': 'vehicle',
        'bonus': {'defense': 1.5, 'luck': 1.3, 'click_power': 1.2},
        'cost': {'gooncoins': 100000},
        'image': 'opel.png',
        'unlock_requirement': None,
        'rarity': 'legendary',
        'power': 55,
        'release_order': 109
    },
    'crate_grandpa_jacket': {
        'name': 'Bunda po Dědovi',
        'slot': 'armor',
        'bonus': {'defense': 1.6, 'luck': 1.2, 'hp': 200},
        'cost': {'gooncoins': 80000},
        'image': 'BundaPoDedovi.png',
        'unlock_requirement': None,
        'rarity': 'legendary',
        'power': 58,
        'release_order': 110
    },
    'crate_legendary_ring': {
        'name': 'Legendární Prsten',
        'slot': 'ring',
        'bonus': {'click_power': 1.4, 'luck': 1.5, 'attack': 50, 'defense': 40},
        'cost': {'gooncoins': 150000},
        'image': 'lugog.png',
        'unlock_requirement': None,
        'rarity': 'legendary',
        'power': 65,
        'release_order': 111
    }
}

# Run migration after EQUIPMENT_DEFS is defined
migrate_equipment_to_db()

# Battle Cats Pets definitions
PET_DEFS = {
    'cat_basic': {
        'name': 'Základní Kočka',
        'description': 'Klasická kočka z Battle Cats. Zvyšuje click power.',
        'bonus': {'click_power': 1.15},
        'cost': {'gooncoins': 500000},
        'image': 'lugog.png',
        'rarity': 'common',
        'max_level': 20,
        'exp_per_level': 100,
        'release_order': 1,
        'required_fruit_rarity': 'common'
    },
    'cat_tank': {
        'name': 'Tank Kočka',
        'description': 'Obrněná kočka s vysokou obranou. Zvyšuje defense.',
        'bonus': {'defense': 1.2},
        'cost': {'gooncoins': 1000000, 'astma': 500},
        'image': 'lugog.png',
        'rarity': 'rare',
        'max_level': 30,
        'exp_per_level': 150,
        'release_order': 2,
        'required_fruit_rarity': 'rare'
    },
    'cat_axe': {
        'name': 'Sekera Kočka',
        'description': 'Bojovná kočka s sekerou. Zvyšuje attack power.',
        'bonus': {'click_power': 1.3, 'attack': 1.1},
        'cost': {'gooncoins': 1200000, 'mrkev': 300},
        'image': 'lugog.png',
        'rarity': 'rare',
        'max_level': 30,
        'exp_per_level': 150,
        'release_order': 3,
        'required_fruit_rarity': 'rare'
    },
    'cat_ufo': {
        'name': 'UFO Kočka',
        'description': 'Mimozemská kočka z vesmíru. Zvyšuje luck a click power.',
        'bonus': {'luck': 1.25, 'click_power': 1.2},
        'cost': {'gooncoins': 2000000, 'poharky': 400},
        'image': 'lugog.png',
        'rarity': 'epic',
        'max_level': 40,
        'exp_per_level': 200,
        'release_order': 4,
        'required_fruit_rarity': 'epic'
    },
    'cat_dragon': {
        'name': 'Drak Kočka',
        'description': 'Mocný dračí kočka. Zvyšuje všechny statistiky.',
        'bonus': {'click_power': 1.4, 'defense': 1.3, 'luck': 1.2},
        'cost': {'gooncoins': 5000000, 'uzené': 800, 'mrkev': 600},
        'image': 'lugog.png',
        'rarity': 'legendary',
        'max_level': 50,
        'exp_per_level': 250,
        'release_order': 5,
        'required_fruit_rarity': 'legendary'
    },
    'cat_bahamut': {
        'name': 'Bahamut Kočka',
        'description': 'Legendární kočka s obrovskou silou. Masivní bonusy ke všem statistikám.',
        'bonus': {'click_power': 1.6, 'defense': 1.5, 'luck': 1.4, 'attack': 1.3},
        'cost': {'gooncoins': 10000000, 'uzené': 2000, 'poharky': 2000, 'mrkev': 2000},
        'image': 'lugog.png',
        'rarity': 'unique',
        'max_level': 60,
        'exp_per_level': 300,
        'release_order': 6,
        'required_fruit_rarity': 'unique'
    },
    'cat_eraser': {
        'name': 'Guma Kočka',
        'description': 'Obranná kočka s vysokou HP. Zvyšuje defense a HP.',
        'bonus': {'defense': 1.35, 'hp': 1.2},
        'cost': {'gooncoins': 1800000, 'astma': 350},
        'image': 'lugog.png',
        'rarity': 'epic',
        'max_level': 40,
        'exp_per_level': 200,
        'release_order': 7,
        'required_fruit_rarity': 'epic'
    },
    'cat_paris': {
        'name': 'Pařížská Kočka',
        'description': 'Elegantní kočka z Paříže. Zvyšuje luck a click power.',
        'bonus': {'luck': 1.3, 'click_power': 1.25},
        'cost': {'gooncoins': 2200000, 'poharky': 450, 'astma': 300},
        'image': 'lugog.png',
        'rarity': 'epic',
        'max_level': 40,
        'exp_per_level': 200,
        'release_order': 8,
        'required_fruit_rarity': 'epic'
    },
    'cat_cyborg': {
        'name': 'Kyborg Kočka',
        'description': 'Mechanická kočka s technologickými vylepšeními. Zvyšuje všechny statistiky.',
        'bonus': {'click_power': 1.35, 'defense': 1.25, 'luck': 1.15},
        'cost': {'gooncoins': 6000000, 'mrkev': 1000, 'poharky': 900},
        'image': 'lugog.png',
        'rarity': 'legendary',
        'max_level': 50,
        'exp_per_level': 250,
        'release_order': 9,
        'required_fruit_rarity': 'legendary'
    },
    'cat_ururun': {
        'name': 'Ururun Kočka',
        'description': 'Vzácná kočka s mystickou silou. Obrovské bonusy.',
        'bonus': {'click_power': 1.5, 'defense': 1.4, 'luck': 1.35, 'attack': 1.2},
        'cost': {'gooncoins': 12000000, 'uzené': 2500, 'poharky': 2500, 'mrkev': 2500, 'astma': 2500},
        'image': 'lugog.png',
        'rarity': 'unique',
        'max_level': 60,
        'exp_per_level': 300,
        'release_order': 10,
        'required_fruit_rarity': 'unique'
    }
}

# Garden System - Seed Definitions
SEED_DEFS = {
    'seed_common': {
        'seed_id': 'seed_common',
        'name': 'Základní Semínko',
        'description': 'Jednoduché semínko pro začátečníky. Roste rychle a produkuje základní ovoce.',
        'rarity': 'common',
        'cost': {'gooncoins': 100},
        'growth_time': 300,  # 5 minutes in seconds
        'fruit_id': 'fruit_common',
        'fruit_name': 'Základní Ovoce',
        'fruit_icon': '🍎'
    },
    'seed_rare': {
        'seed_id': 'seed_rare',
        'name': 'Vzácné Semínko',
        'description': 'Vzácné semínko s lepšími plody. Vyžaduje více času na růst.',
        'rarity': 'rare',
        'cost': {'gooncoins': 500, 'astma': 10},
        'growth_time': 900,  # 15 minutes
        'fruit_id': 'fruit_rare',
        'fruit_name': 'Vzácné Ovoce',
        'fruit_icon': '🍊'
    },
    'seed_epic': {
        'seed_id': 'seed_epic',
        'name': 'Epické Semínko',
        'description': 'Epické semínko produkující kvalitní ovoce pro pokročilé pěstitele.',
        'rarity': 'epic',
        'cost': {'gooncoins': 1500, 'poharky': 15},
        'growth_time': 1800,  # 30 minutes
        'fruit_id': 'fruit_epic',
        'fruit_name': 'Epické Ovoce',
        'fruit_icon': '🍇'
    },
    'seed_legendary': {
        'seed_id': 'seed_legendary',
        'name': 'Legendární Semínko',
        'description': 'Výjimečné semínko s dlouhou dobou růstu, ale skvělými plody.',
        'rarity': 'legendary',
        'cost': {'gooncoins': 3000, 'mrkev': 20, 'uzené': 10},
        'growth_time': 3600,  # 1 hour
        'fruit_id': 'fruit_legendary',
        'fruit_name': 'Legendární Ovoce',
        'fruit_icon': '🍑'
    },
    'seed_unique': {
        'seed_id': 'seed_unique',
        'name': 'Unikátní Semínko',
        'description': 'Nejvzácnější semínko. Vyžaduje trpělivost, ale odměna je obrovská.',
        'rarity': 'unique',
        'cost': {'gooncoins': 5000, 'uzené': 25, 'poharky': 20, 'mrkev': 25},
        'growth_time': 7200,  # 2 hours
        'fruit_id': 'fruit_unique',
        'fruit_name': 'Unikátní Ovoce',
        'fruit_icon': '🍒'
    },
    # Otova zahrada
    'seed_pochcane_maliny': {
        'seed_id': 'seed_pochcane_maliny',
        'name': 'Pochcané Maliny',
        'description': 'Speciální maliny z Otovy zahrady. Mají... unikátní chuť.',
        'rarity': 'rare',
        'cost': {'gooncoins': 300, 'astma': 5},
        'growth_time': 600,  # 10 minutes
        'fruit_id': 'pochcane_maliny',
        'fruit_name': 'Pochcané Maliny',
        'fruit_icon': '🫐'
    },
    'seed_rajcata': {
        'seed_id': 'seed_rajcata',
        'name': 'Normální Rajčata',
        'description': 'Klasická rajčata z Otovy zahrady. Čerstvá a šťavnatá.',
        'rarity': 'common',
        'cost': {'gooncoins': 150},
        'growth_time': 450,  # 7.5 minutes
        'fruit_id': 'rajcata',
        'fruit_name': 'Rajčata',
        'fruit_icon': '🍅'
    },
    'seed_mata': {
        'seed_id': 'seed_mata',
        'name': 'Máta',
        'description': 'Čerstvá máta pro osvěžení. Voní skvěle!',
        'rarity': 'common',
        'cost': {'gooncoins': 80},
        'growth_time': 300,  # 5 minutes
        'fruit_id': 'mata',
        'fruit_name': 'Máta',
        'fruit_icon': '🌿'
    },
    'seed_slepice': {
        'seed_id': 'seed_slepice',
        'name': 'Slepičí Vejce',
        'description': 'Čerstvá vejce od Otových slepic. Vždy čerstvá!',
        'rarity': 'rare',
        'cost': {'gooncoins': 400, 'astma': 8},
        'growth_time': 900,  # 15 minutes
        'fruit_id': 'slepici_vejce',
        'fruit_name': 'Slepičí Vejce',
        'fruit_icon': '🥚'
    },
    'seed_okurky': {
        'seed_id': 'seed_okurky',
        'name': 'Okurky',
        'description': 'Křupavé okurky z Otovy zahrady. Perfektní na salát!',
        'rarity': 'common',
        'cost': {'gooncoins': 120},
        'growth_time': 360,  # 6 minutes
        'fruit_id': 'okurky',
        'fruit_name': 'Okurky',
        'fruit_icon': '🥒'
    },
    'seed_papriky': {
        'seed_id': 'seed_papriky',
        'name': 'Papriky',
        'description': 'Barevné papriky plné vitamínů. Sladké a křupavé!',
        'rarity': 'rare',
        'cost': {'gooncoins': 350, 'poharky': 5},
        'growth_time': 750,  # 12.5 minutes
        'fruit_id': 'papriky',
        'fruit_name': 'Papriky',
        'fruit_icon': '🫑'
    },
    'seed_cibule': {
        'seed_id': 'seed_cibule',
        'name': 'Cibule',
        'description': 'Ostrá cibule pro každou kuchyni. Pozor na slzy!',
        'rarity': 'common',
        'cost': {'gooncoins': 90},
        'growth_time': 420,  # 7 minutes
        'fruit_id': 'cibule',
        'fruit_name': 'Cibule',
        'fruit_icon': '🧅'
    }
}

# Fruit definitions for inventory display
FRUIT_DEFS = {
    'rajcata': {'name': 'Rajčata', 'icon': '🍅', 'rarity': 'common'},
    'okurky': {'name': 'Okurky', 'icon': '🥒', 'rarity': 'common'},
    'papriky': {'name': 'Papriky', 'icon': '🫑', 'rarity': 'rare'},
    'cibule': {'name': 'Cibule', 'icon': '🧅', 'rarity': 'common'},
    'mata': {'name': 'Máta', 'icon': '🌿', 'rarity': 'common'},
    'slepici_vejce': {'name': 'Slepičí Vejce', 'icon': '🥚', 'rarity': 'rare'},
    'pochcane_maliny': {'name': 'Pochcané Maliny', 'icon': '🫐', 'rarity': 'rare'},
    'fruit_common': {'name': 'Základní Ovoce', 'icon': '🍎', 'rarity': 'common'},
    'fruit_rare': {'name': 'Vzácné Ovoce', 'icon': '🍊', 'rarity': 'rare'},
    'fruit_epic': {'name': 'Epické Ovoce', 'icon': '🍇', 'rarity': 'epic'},
    'fruit_legendary': {'name': 'Legendární Ovoce', 'icon': '🍑', 'rarity': 'legendary'},
    'fruit_unique': {'name': 'Unikátní Ovoce', 'icon': '🍒', 'rarity': 'unique'}
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
            make_quest('first_click', 'První Kliknutí', 'Probuď systém prvním kliknutím do Lugoga.', {'total_clicks': 1}, {'gooncoins': 500}),
            make_quest('first_100', 'Prvních 100', 'Nasbírej 5000 Gooncoinů, aby se panelák nadechl nového života.', {'gooncoins': 5000}, {'gooncoins': 2500}),
            make_quest('click_combo', 'Klikací Kombajn', 'Rozjeď prsty – dosáhni 12500 kliknutí.', {'total_clicks': 12500}, {'gooncoins': 3750}),
            make_quest('starter_cache', 'Základní Fond', 'Nashromáždi 25000 Gooncoinů pro první investice.', {'gooncoins': 25000}, {'gooncoins': 50000}),
            make_quest('first_building', 'První Budova', 'Postav Dílna a připrav stůl pro další dobrodruhy.', {'buildings': ['workshop']}, {'gooncoins': 10000}),
            make_quest('speedrunner', 'Klikací Sprinter', 'Vyklikni 500 kliknutí bez ohledu na mozoly.', {'total_clicks': 500}, {'gooncoins': 10000}, optional=True),
            make_quest('rookie_hoarder', 'Panelákový Hamoun', 'Udrž 12500 Gooncoinů v zásobě a neutrať ani korunu navíc.', {'gooncoins': 12500}, {'gooncoins': 15000}, optional=True)
        ]
    },
    2: {
        'title': 'Rostoucí Bohatství',
        'description': 'Gooncoiny se hromadí a panelák se probouzí. Každý další poklad otevírá nové možnosti a cesty k moci.',
        'quests': [
            make_quest('collect_gooncoins_1', 'První Poklad', 'Nasbírej 50000 Gooncoinů a rozfoukej prach ze starých systémů.', {'gooncoins': 50000}, {'gooncoins': 25000}),
            make_quest('collect_gooncoins_2', 'Rostoucí Bohatství', 'Nashromáždi 75000 Gooncoinů a zjisti, kdo drží hospodský trůn.', {'gooncoins': 75000}, {'gooncoins': 50000}),
            make_quest('collect_gooncoins_3', 'Pokladnice Roste', 'Gooncoiny z polí Lugogu dodají očím ostrost. Nasbírej jich 100000.', {'gooncoins': 100000}, {'gooncoins': 75000}),
            make_quest('first_equipment', 'První Equipment', 'Vyrob si první equipment a obleč se do legend.', {'equipment_count': 1}, {'gooncoins': 15000}),
            make_quest('arkadovka_master', 'Král Arkadovek', 'Vyrob 10× Arkadovka a rozjeď herní maraton.', {'equipment_owned': {'arkadovka': 10}}, {'gooncoins': 5000}, optional=True),
            make_quest('inhalator_guru', 'Inhalátor Guru', 'Vyrob 10× Inhalator a rozdávej klidný dech.', {'equipment_owned': {'inhalator': 10}}, {'gooncoins': 8000}, optional=True),
            make_quest('jordan_collector', 'Jordan Kolekce', 'Vyrob 10× Jordan Mikina pro celou squad.', {'equipment_owned': {'jordan_mikina': 10}}, {'gooncoins': 10000}, optional=True),
            make_quest('deduv_wardrobe', 'Dědův Šatník', 'Nasbírej 10× Bunda po Dědovi a obleč panelákovou gardu.', {'equipment_owned': {'bunda_po_dedovi': 10}}, {'gooncoins': 6000}, optional=True),
            make_quest('crafting_frenzy', 'Výrobní Šílenství', 'Udrž současně 6 kusů vybavení.', {'equipment_count': 6}, {'gooncoins': 600}, optional=True)
        ]
    },
    3: {
        'title': 'Citadela Paneláku 244',
        'description': 'Když se chodby 244 znovu rozzáří, Lugog potřebuje zásobování, obchodníky a ozbrojenou eskortu.',
        'quests': [
            make_quest('market_blueprints', 'Plány Tržiště', 'Doruč 200000 Gooncoinů stavební radě a získej povolení k Tržišti.', {'gooncoins': 200000}, {'gooncoins': 25000}, ['market']),
            make_quest('build_market', 'Tržnice ožívá', 'Postav Tržiště, aby se zboží dostalo z výtahů až na střechu.', {'buildings': ['market']}, {'gooncoins': 40000}),
            make_quest('temple_permit', 'Chrámové Pověření', 'Získej požehnání rady – přines 250000 Gooncoinů.', {'gooncoins': 250000}, {'gooncoins': 50000}, ['temple']),
            make_quest('sacred_blueprint', 'Posvěcené výkresy', 'Postav Dílna, Tržiště i Chrám – panelák musí fungovat jako jeden celek.', {'buildings': ['workshop', 'market', 'temple']}, {'gooncoins': 75000}),
            make_quest('smokehouse_supreme', 'Mistr Pokladů', 'Nasbírej 500000 Gooncoinů pro noční hostinu.', {'gooncoins': 500000}, {'gooncoins': 100000}, optional=True),
            make_quest('opel_convoy', 'Opel Konvoj', 'Vyrob 5 vozidel Opel a doprav zásoby bezpečně domů.', {'equipment_owned': {'opel': 5}}, {'gooncoins': 40000}, optional=True),
            make_quest('citadel_stockpile', 'Citadela Skaldí zásoby', 'Drž 400000 Gooncoinů pro případ obléhání.', {'gooncoins': 400000}, {'gooncoins': 150000}, optional=True),
            make_quest('armored_procession', 'Opevněný průvod', 'Získej 2× Rezavá Katana a 2× Kevlarová Vesta.', {'equipment_owned': {'rezava_katana': 2, 'kevlar_vesta': 2}}, {'gooncoins': 30000}, optional=True)
        ]
    },
    4: {
        'title': 'Legenda Plechových Bohů',
        'description': 'Ze střechy je vidět celé Lugogovo údolí. Poslední kapitola prověří tvoji výdrž, zásoby i víru.',
        'quests': [
            make_quest('click_master', 'Klikací Maestro', 'Získej 2 500 000 kliknutí a udrž systém vzhůru celou noc.', {'total_clicks': 2500000}, {'gooncoins': 250000}),
            make_quest('final_blessing', 'Noc Požehnání', 'Připrav 1800000 Gooncoinů pro chrámové obřady.', {'gooncoins': 1800000}, {'gooncoins': 200000}),
            make_quest('wealth_of_lugog', 'Poklad Lugogu', 'Nasbírej 3 750 000 Gooncoinů pro obnovu paneláku.', {'gooncoins': 3750000}, {'gooncoins': 400000}),
            make_quest('skrinka_legend', 'Skříňka Legend', 'Získej 1× Skříňka 244 a odemkni tajemství schovaná za šedým plechem.', {'equipment_owned': {'skrinka_244': 1}}, {'gooncoins': 8000}, optional=True),
            make_quest('amulet_conclave', 'Konkláve Amuletů', 'Nasbírej 10× Amulet Štěstí a rozdej požehnání každému patru.', {'equipment_owned': {'amulet_luck': 10}}, {'gooncoins': 16000}, optional=True),
            make_quest('hoverboard_fleet', 'Letka Hoverboardů', 'Vyrob 3× Turbo Hoverboard pro střechové hlídky.', {'equipment_owned': {'turbo_hoverboard': 3}}, {'gooncoins': 12000}, optional=True),
            make_quest('crown_collection', 'Lugogova Korunovace', 'Získej 1× Koruna Lugogu a ukaž, kdo vládne paneláku.', {'equipment_owned': {'koruna_lugogu': 1}}, {'gooncoins': 10000}, optional=True)
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

# Gem definitions - Drahokamy zvyšují atributy postavy
GEM_DEFINITIONS = {
    'gem_strength': {
        'name': 'Drahokam Síly',
        'icon': '💎',
        'color': '#FF4444',
        'stat_type': 'strength',
        'description': 'Zvyšuje sílu postavy',
        'levels': {
            1: {'bonus': 2, 'cost': {'gooncoins': 5000}},
            2: {'bonus': 4, 'cost': {'gooncoins': 15000}},
            3: {'bonus': 7, 'cost': {'gooncoins': 40000}},
            4: {'bonus': 12, 'cost': {'gooncoins': 100000}},
            5: {'bonus': 20, 'cost': {'gooncoins': 250000}},
            6: {'bonus': 35, 'cost': {'gooncoins': 600000}},
            7: {'bonus': 60, 'cost': {'gooncoins': 1500000}},
            8: {'bonus': 100, 'cost': {'gooncoins': 4000000}}
        }
    },
    'gem_dexterity': {
        'name': 'Drahokam Obratnosti',
        'icon': '💠',
        'color': '#44AAFF',
        'stat_type': 'dexterity',
        'description': 'Zvyšuje obratnost postavy',
        'levels': {
            1: {'bonus': 2, 'cost': {'gooncoins': 5000}},
            2: {'bonus': 4, 'cost': {'gooncoins': 15000}},
            3: {'bonus': 7, 'cost': {'gooncoins': 40000}},
            4: {'bonus': 12, 'cost': {'gooncoins': 100000}},
            5: {'bonus': 20, 'cost': {'gooncoins': 250000}},
            6: {'bonus': 35, 'cost': {'gooncoins': 600000}},
            7: {'bonus': 60, 'cost': {'gooncoins': 1500000}},
            8: {'bonus': 100, 'cost': {'gooncoins': 4000000}}
        }
    },
    'gem_intelligence': {
        'name': 'Drahokam Inteligence',
        'icon': '🔮',
        'color': '#AA44FF',
        'stat_type': 'intelligence',
        'description': 'Zvyšuje inteligenci postavy',
        'levels': {
            1: {'bonus': 2, 'cost': {'gooncoins': 5000}},
            2: {'bonus': 4, 'cost': {'gooncoins': 15000}},
            3: {'bonus': 7, 'cost': {'gooncoins': 40000}},
            4: {'bonus': 12, 'cost': {'gooncoins': 100000}},
            5: {'bonus': 20, 'cost': {'gooncoins': 250000}},
            6: {'bonus': 35, 'cost': {'gooncoins': 600000}},
            7: {'bonus': 60, 'cost': {'gooncoins': 1500000}},
            8: {'bonus': 100, 'cost': {'gooncoins': 4000000}}
        }
    },
    'gem_constitution': {
        'name': 'Drahokam Odolnosti',
        'icon': '🛡️',
        'color': '#44FF44',
        'stat_type': 'constitution',
        'description': 'Zvyšuje odolnost postavy',
        'levels': {
            1: {'bonus': 2, 'cost': {'gooncoins': 5000}},
            2: {'bonus': 4, 'cost': {'gooncoins': 15000}},
            3: {'bonus': 7, 'cost': {'gooncoins': 40000}},
            4: {'bonus': 12, 'cost': {'gooncoins': 100000}},
            5: {'bonus': 20, 'cost': {'gooncoins': 250000}},
            6: {'bonus': 35, 'cost': {'gooncoins': 600000}},
            7: {'bonus': 60, 'cost': {'gooncoins': 1500000}},
            8: {'bonus': 100, 'cost': {'gooncoins': 4000000}}
        }
    },
    'gem_luck': {
        'name': 'Drahokam Štěstí',
        'icon': '✨',
        'color': '#FFD700',
        'stat_type': 'luck',
        'description': 'Zvyšuje štěstí postavy',
        'levels': {
            1: {'bonus': 2, 'cost': {'gooncoins': 5000}},
            2: {'bonus': 4, 'cost': {'gooncoins': 15000}},
            3: {'bonus': 7, 'cost': {'gooncoins': 40000}},
            4: {'bonus': 12, 'cost': {'gooncoins': 100000}},
            5: {'bonus': 20, 'cost': {'gooncoins': 250000}},
            6: {'bonus': 35, 'cost': {'gooncoins': 600000}},
            7: {'bonus': 60, 'cost': {'gooncoins': 1500000}},
            8: {'bonus': 100, 'cost': {'gooncoins': 4000000}}
        }
    },
    'gem_universal': {
        'name': 'Univerzální Drahokam',
        'icon': '💫',
        'color': '#FF88FF',
        'stat_type': 'universal',
        'description': 'Zvyšuje všechny atributy postavy',
        'levels': {
            1: {'bonus': 1, 'cost': {'gooncoins': 10000}},
            2: {'bonus': 2, 'cost': {'gooncoins': 30000}},
            3: {'bonus': 3, 'cost': {'gooncoins': 80000}},
            4: {'bonus': 5, 'cost': {'gooncoins': 200000}},
            5: {'bonus': 8, 'cost': {'gooncoins': 500000}},
            6: {'bonus': 12, 'cost': {'gooncoins': 1200000}},
            7: {'bonus': 20, 'cost': {'gooncoins': 3000000}},
            8: {'bonus': 35, 'cost': {'gooncoins': 8000000}}
        }
    }
}

GEM_SLOTS = ['gem_strength', 'gem_dexterity', 'gem_intelligence', 'gem_constitution', 'gem_luck', 'gem_universal']

# Building definitions
BUILDINGS_DEFS = {
    'lumberjack_hut': {
        'order': 1,
        'category': 'production',
        'name': 'Dřevorubecká chata',
        'description': 'Seká kmeny, ale jen pokud máš postavenou cestu pro nosiče.',
        'cost': {'gooncoins': 7500},
        'always_available': True,
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 120,
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
        'cost': {'gooncoins': 6000},
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
        'cost': {'gooncoins': 12500, 'logs': 500},
        'always_available': True,
        'prerequisites': ['lumberjack_hut', 'forest_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 140,
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
        'cost': {'gooncoins': 7000, 'logs': 400},
        'always_available': True,
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
        'cost': {'gooncoins': 9000},
        'always_available': True,
        'prerequisites': ['lumberjack_hut'],
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 150,
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
        'cost': {'gooncoins': 7500},
        'always_available': True,
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
        'cost': {'gooncoins': 13000, 'grain': 500},
        'always_available': True,
        'prerequisites': ['farmstead', 'field_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 130,
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
        'cost': {'gooncoins': 8000, 'planks': 200},
        'always_available': True,
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
        'cost': {'gooncoins': 16000, 'flour': 300},
        'always_available': True,
        'prerequisites': ['bakery_route'],
        'logistics': {
            'kind': 'process',
            'role': 'processor',
            'base_cycle': 160,
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
        'cost': {'gooncoins': 10500, 'planks': 200},
        'always_available': True,
        'prerequisites': ['plank_route'],
        'logistics': {
            'kind': 'process',
            'role': 'gatherer',
            'base_cycle': 140,
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
        'cost': {'gooncoins': 6500, 'planks': 200},
        'always_available': True,
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
        'cost': {'gooncoins': 14000, 'planks': 300, 'bread': 100},
        'always_available': True,
        'prerequisites': ['forest_route'],
        'repeatable': True,
        'max_level': 5,
        'level_cost_multiplier': 2.5,
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
        'cost': {'gooncoins': 25000, 'planks': 600, 'bread': 100},
        'prerequisites': ['sawmill', 'plank_route'],
        'unlocks': ['crafting']
    },
    'market': {
        'order': 21,
        'category': 'infrastructure',
        'name': 'Tržiště',
        'description': 'Otevře měnový trh a propojí logistiku s ekonomikou.',
        'cost': {'gooncoins': 50000, 'planks': 400, 'bread': 300, 'fish': 300},
        'prerequisites': ['bakery', 'fishery'],
        'unlocks': ['trading'],
        'unlock_currencies': TRADEABLE_CURRENCIES
    },
    'temple': {
        'order': 22,
        'category': 'infrastructure',
        'name': 'Chrám',
        'description': 'Otevírá chrámové místnosti, požehnání a speciální bojové eventy.',
        'cost': {'gooncoins': 100000, 'poharky': 500, 'bread': 600, 'fish': 300},
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
    'low_tier_crate': {
        'name': 'Základní Bedna',
        'icon': '📦',
        'description': 'Základní bedna s běžnými předměty a malými odměnami.',
        'tagline': 'Začátek tvé cesty k pokladům.',
        'price': 10000,
        'currency': 'gooncoins',
        'order': 1,
        'items': [
            {
                'id': 'low_coins_small',
                'type': 'currency',
                'name': 'Malý balík Gooncoinů',
                'description': '+2 000 Gooncoinů',
                'rarity': 'common',
                'icon': '💰',
                'weight': 40,
                'payout': {'resources': {'gooncoins': 2000}}
            },
            {
                'id': 'low_coins_medium',
                'type': 'currency',
                'name': 'Střední balík Gooncoinů',
                'description': '+5 000 Gooncoins',
                'rarity': 'rare',
                'icon': '💰',
                'weight': 25,
                'payout': {'resources': {'gooncoins': 5000}}
            },
            {
                'id': 'low_sony_phone',
                'type': 'equipment',
                'name': 'Sony Telefon',
                'description': 'Základní telefon s bonusem k štěstí.',
                'rarity': 'common',
                'icon': '📱',
                'weight': 15,
                'payout': {'equipment_id': 'crate_sony_phone', 'amount': 1}
            },
            {
                'id': 'low_swiss_socks',
                'type': 'equipment',
                'name': 'Švýcarské Ponožky',
                'description': 'Pohodlné ponožky s obranným bonusem.',
                'rarity': 'common',
                'icon': '🧦',
                'weight': 12,
                'payout': {'equipment_id': 'crate_swiss_socks', 'amount': 1}
            },
            {
                'id': 'low_basic_ring',
                'type': 'equipment',
                'name': 'Základní Prsten',
                'description': 'Jednoduchý prsten s malým bonusem.',
                'rarity': 'rare',
                'icon': '💍',
                'weight': 8,
                'payout': {'equipment_id': 'crate_basic_ring', 'amount': 1}
            }
        ]
    },
    'mid_tier_crate': {
        'name': 'Prémiová Bedna',
        'icon': '🎁',
        'description': 'Prémiová bedna s lepšími předměty a většími odměnami.',
        'tagline': 'Kvalitní gear pro pokročilé hráče.',
        'price': 100000,
        'currency': 'gooncoins',
        'order': 2,
        'items': [
            {
                'id': 'mid_coins_medium',
                'type': 'currency',
                'name': 'Velký balík Gooncoinů',
                'description': '+25 000 Gooncoinů',
                'rarity': 'common',
                'icon': '💰',
                'weight': 30,
                'payout': {'resources': {'gooncoins': 25000}}
            },
            {
                'id': 'mid_coins_large',
                'type': 'currency',
                'name': 'Obrovský balík Gooncoinů',
                'description': '+50 000 Gooncoinů',
                'rarity': 'rare',
                'icon': '💰',
                'weight': 20,
                'payout': {'resources': {'gooncoins': 50000}}
            },
            {
                'id': 'mid_samsung_phone',
                'type': 'equipment',
                'name': 'Samsung Telefon',
                'description': 'Výkonný telefon s bonusem k síle kliků.',
                'rarity': 'rare',
                'icon': '📱',
                'weight': 18,
                'payout': {'equipment_id': 'crate_samsung_phone', 'amount': 1}
            },
            {
                'id': 'mid_realme_phone',
                'type': 'equipment',
                'name': 'Realme Telefon',
                'description': 'Moderní telefon s vyváženými bonusy.',
                'rarity': 'rare',
                'icon': '📱',
                'weight': 15,
                'payout': {'equipment_id': 'crate_realme_phone', 'amount': 1}
            },
            {
                'id': 'mid_valley_cap',
                'type': 'equipment',
                'name': 'Valley Čepice',
                'description': 'Stylová čepice s obranným bonusem.',
                'rarity': 'epic',
                'icon': '🧢',
                'weight': 10,
                'payout': {'equipment_id': 'crate_valley_cap', 'amount': 1}
            },
            {
                'id': 'mid_jordan_hoodie',
                'type': 'equipment',
                'name': 'Jordan Mikina',
                'description': 'Prémiová mikina s kombinovanými bonusy.',
                'rarity': 'epic',
                'icon': '👕',
                'weight': 7,
                'payout': {'equipment_id': 'crate_jordan_hoodie', 'amount': 1}
            }
        ]
    },
    'high_tier_crate': {
        'name': 'Legendární Bedna',
        'icon': '💎',
        'description': 'Nejlepší bedna s legendárními předměty a obrovskými odměnami.',
        'tagline': 'Nejvzácnější poklady pro elitu.',
        'price': 1000000,
        'currency': 'gooncoins',
        'order': 3,
        'items': [
            {
                'id': 'high_coins_large',
                'type': 'currency',
                'name': 'Mega balík Gooncoinů',
                'description': '+200 000 Gooncoinů',
                'rarity': 'rare',
                'icon': '💰',
                'weight': 25,
                'payout': {'resources': {'gooncoins': 200000}}
            },
            {
                'id': 'high_coins_ultra',
                'type': 'currency',
                'name': 'Ultra balík Gooncoinů',
                'description': '+500 000 Gooncoinů',
                'rarity': 'epic',
                'icon': '💰',
                'weight': 15,
                'payout': {'resources': {'gooncoins': 500000}}
            },
            {
                'id': 'high_vivobook',
                'type': 'equipment',
                'name': 'Vivobook Laptop',
                'description': 'Výkonný laptop s obrovskými bonusy.',
                'rarity': 'epic',
                'icon': '💻',
                'weight': 20,
                'payout': {'equipment_id': 'crate_vivobook', 'amount': 1}
            },
            {
                'id': 'high_inhalator',
                'type': 'equipment',
                'name': 'Prémiový Inhalátor',
                'description': 'Nejlepší inhalátor s maximální obranou.',
                'rarity': 'epic',
                'icon': '💨',
                'weight': 15,
                'payout': {'equipment_id': 'crate_premium_inhalator', 'amount': 1}
            },
            {
                'id': 'high_opel_vehicle',
                'type': 'equipment',
                'name': 'Opel Vozidlo',
                'description': 'Legendární vozidlo s kombinovanými bonusy.',
                'rarity': 'legendary',
                'icon': '🚗',
                'weight': 12,
                'payout': {'equipment_id': 'crate_opel_vehicle', 'amount': 1}
            },
            {
                'id': 'high_grandpa_jacket',
                'type': 'equipment',
                'name': 'Bunda po Dědovi',
                'description': 'Legendární bunda s obrovskými bonusy.',
                'rarity': 'legendary',
                'icon': '🧥',
                'weight': 8,
                'payout': {'equipment_id': 'crate_grandpa_jacket', 'amount': 1}
            },
            {
                'id': 'high_legendary_ring',
                'type': 'equipment',
                'name': 'Legendární Prsten',
                'description': 'Nejlepší prsten s maximálními bonusy.',
                'rarity': 'legendary',
                'icon': '💍',
                'weight': 5,
                'payout': {'equipment_id': 'crate_legendary_ring', 'amount': 1}
            }
        ]
    }
}

# Shop definitions for microtransactions
SHOP_ITEMS = {
    # Gems packages (premium currency)
    'gems_small': {
        'id': 'gems_small',
        'name': 'Malý balíček Drahokamů',
        'description': '50 Drahokamů',
        'icon': '💎',
        'category': 'gems',
        'cost_real_money': 0.99,  # In real implementation, integrate with payment gateway
        'rewards': {'gems': 50},
        'popular': False
    },
    'gems_medium': {
        'id': 'gems_medium',
        'name': 'Střední balíček Drahokamů',
        'description': '150 Drahokamů + 10 bonus',
        'icon': '💎',
        'category': 'gems',
        'cost_real_money': 2.99,
        'rewards': {'gems': 160},
        'popular': True
    },
    'gems_large': {
        'id': 'gems_large',
        'name': 'Velký balíček Drahokamů',
        'description': '500 Drahokamů + 100 bonus',
        'icon': '💎',
        'category': 'gems',
        'cost_real_money': 9.99,
        'rewards': {'gems': 600},
        'popular': False
    },
    'gems_mega': {
        'id': 'gems_mega',
        'name': 'Mega balíček Drahokamů',
        'description': '1500 Drahokamů + 500 bonus',
        'icon': '💎',
        'category': 'gems',
        'cost_real_money': 24.99,
        'rewards': {'gems': 2000},
        'popular': False
    },
    
    # Gooncoins packages
    'gooncoins_starter': {
        'id': 'gooncoins_starter',
        'name': 'Startovní balíček',
        'description': '5,000 Gooncoinů',
        'icon': '💰',
        'category': 'resources',
        'cost_gems': 25,
        'rewards': {'gooncoins': 5000},
        'popular': False
    },
    'gooncoins_boost': {
        'id': 'gooncoins_boost',
        'name': 'Boost balíček',
        'description': '25,000 Gooncoinů',
        'icon': '💰',
        'category': 'resources',
        'cost_gems': 100,
        'rewards': {'gooncoins': 25000},
        'popular': True
    },
    'gooncoins_mega': {
        'id': 'gooncoins_mega',
        'name': 'Mega balíček',
        'description': '100,000 Gooncoinů',
        'icon': '💰',
        'category': 'resources',
        'cost_gems': 350,
        'rewards': {'gooncoins': 100000},
        'popular': False
    },
    
    # Resource packages
    'resources_pack': {
        'id': 'resources_pack',
        'name': 'Balíček zdrojů',
        'description': 'Astma, Pohárky, Mrkev, Uzené',
        'icon': '📦',
        'category': 'resources',
        'cost_gems': 50,
        'rewards': {
            'astma': 500,
            'poharky': 300,
            'mrkev': 200,
            'uzené': 150
        },
        'popular': False
    },
    
    # Time boosts
    'boost_2x_1h': {
        'id': 'boost_2x_1h',
        'name': '2× Produkce (1 hodina)',
        'description': 'Dvojnásobná produkce všech zdrojů na 1 hodinu',
        'icon': '⚡',
        'category': 'boosts',
        'cost_gems': 30,
        'rewards': {'boost': {'type': 'production', 'multiplier': 2.0, 'duration': 3600}},
        'popular': True
    },
    'boost_3x_2h': {
        'id': 'boost_3x_2h',
        'name': '3× Produkce (2 hodiny)',
        'description': 'Trojnásobná produkce všech zdrojů na 2 hodiny',
        'icon': '⚡',
        'category': 'boosts',
        'cost_gems': 80,
        'rewards': {'boost': {'type': 'production', 'multiplier': 3.0, 'duration': 7200}},
        'popular': False
    },
    'boost_click_2x_24h': {
        'id': 'boost_click_2x_24h',
        'name': '2× Kliknutí (24 hodin)',
        'description': 'Dvojnásobná hodnota kliknutí na 24 hodin',
        'icon': '👆',
        'category': 'boosts',
        'cost_gems': 60,
        'rewards': {'boost': {'type': 'click_power', 'multiplier': 2.0, 'duration': 86400}},
        'popular': False
    },
    
    # Case keys
    'case_key_5': {
        'id': 'case_key_5',
        'name': '5× Klíče k bednám',
        'description': '5 klíčů pro otevření beden',
        'icon': '🗝️',
        'category': 'keys',
        'cost_gems': 40,
        'rewards': {'case_keys': 5},
        'popular': False
    },
    'case_key_10': {
        'id': 'case_key_10',
        'name': '10× Klíče k bednám',
        'description': '10 klíčů pro otevření beden + 2 bonus',
        'icon': '🗝️',
        'category': 'keys',
        'cost_gems': 70,
        'rewards': {'case_keys': 12},
        'popular': True
    },
    
    # Special items
    'rare_material_pack': {
        'id': 'rare_material_pack',
        'name': 'Balíček vzácných materiálů',
        'description': 'Náhodný vzácný materiál',
        'icon': '✨',
        'category': 'special',
        'cost_gems': 150,
        'rewards': {'rare_material_random': 1},
        'popular': False
    },
    'equipment_chest': {
        'id': 'equipment_chest',
        'name': 'Truhla s Equipmentem',
        'description': 'Náhodný equipment (Epic nebo lepší)',
        'icon': '🎁',
        'category': 'special',
        'cost_gems': 200,
        'rewards': {'equipment_random': {'min_rarity': 'epic'}},
        'popular': False
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
    
    equipment_def = get_item_definition(equipment_id)
    if not equipment_def:
        return jsonify({'success': False, 'error': 'Neplatný equipment'})
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
                req_def = get_item_definition(req_eq_id)
                req_name = req_def.get('name', req_eq_id) if req_def else req_eq_id
                return jsonify({'success': False, 'error': f'Musíš mít {req_count}x {req_name} aby sis mohl vyrobit {equipment_def["name"]}'})
    
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
    acquired_at = datetime.now(timezone.utc).isoformat()
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
    
    # Sync equipped items to character_stats (merge equipment + postava)
    sync_equipped_to_character_stats(c, user_id)
    
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

@app.route('/api/pets', methods=['GET'])
def get_pets():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get user's pets
    c.execute('''SELECT id, pet_id, level, experience, active, acquired_at, custom_name 
                 FROM pets WHERE user_id = ? ORDER BY acquired_at DESC''', (user_id,))
    pets_list = []
    for pet_row in c.fetchall():
        pet_def = PET_DEFS.get(pet_row['pet_id'], {})
        display_name = pet_row['custom_name'] if pet_row['custom_name'] else pet_def.get('name', pet_row['pet_id'])
        pets_list.append({
            'id': pet_row['id'],
            'pet_id': pet_row['pet_id'],
            'name': display_name,
            'original_name': pet_def.get('name', pet_row['pet_id']),
            'custom_name': pet_row['custom_name'],
            'description': pet_def.get('description', ''),
            'level': pet_row['level'],
            'experience': pet_row['experience'],
            'active': bool(pet_row['active']),
            'acquired_at': pet_row['acquired_at'],
            'max_level': pet_def.get('max_level', 20),
            'exp_per_level': pet_def.get('exp_per_level', 100),
            'rarity': pet_def.get('rarity', 'common'),
            'bonus': pet_def.get('bonus', {}),
            'image': pet_def.get('image', 'lugog.png'),
            'required_fruit_rarity': pet_def.get('required_fruit_rarity', 'common')
        })
    
    # Get available pets (all pet definitions)
    available_pets = []
    for pet_id, pet_def in PET_DEFS.items():
        available_pets.append({
            'pet_id': pet_id,
            'name': pet_def.get('name', pet_id),
            'description': pet_def.get('description', ''),
            'cost': pet_def.get('cost', {}),
            'rarity': pet_def.get('rarity', 'common'),
            'bonus': pet_def.get('bonus', {}),
            'max_level': pet_def.get('max_level', 20),
            'exp_per_level': pet_def.get('exp_per_level', 100),
            'image': pet_def.get('image', 'lugog.png'),
            'required_fruit_rarity': pet_def.get('required_fruit_rarity', 'common')
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'pets': pets_list,
        'available_pets': available_pets
    })

@app.route('/api/pets/buy', methods=['POST'])
def buy_pet():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    pet_id = data.get('pet_id')
    
    if not pet_id or pet_id not in PET_DEFS:
        return jsonify({'success': False, 'error': 'Neplatný mazlíček'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user already has this pet type (max one of each type)
    c.execute('SELECT id FROM pets WHERE user_id = ? AND pet_id = ?', (user_id, pet_id))
    existing_pet = c.fetchone()
    if existing_pet:
        conn.close()
        return jsonify({'success': False, 'error': 'Už máš tohoto mazlíčka! Můžeš mít max jednoho od každého druhu.'}), 400
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    resources = hydrate_state_resources(state)
    
    pet_def = PET_DEFS[pet_id]
    cost = pet_def['cost']
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    # Check if affordable
    affordable, lacking = deduct_cost(resources, effective_cost)
    if not affordable:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáte dostatek zdrojů ({lacking})'}), 400
    
    # Add pet
    acquired_at = datetime.now(timezone.utc).isoformat()
    c.execute('''INSERT INTO pets (user_id, pet_id, level, experience, active, acquired_at, custom_name)
                 VALUES (?, ?, 1, 0, 0, ?, NULL)''',
              (user_id, pet_id, acquired_at))
    
    persist_resources(c, user_id, resources)
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    resource_payload = resources_payload(resources)
    
    return jsonify({
        'success': True,
        **resource_payload,
        'message': f'Získal jsi {pet_def["name"]}!'
    })

@app.route('/api/pets/activate', methods=['POST'])
def activate_pet():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    pet_instance_id = data.get('pet_id')  # This is the instance ID from pets table
    
    if not pet_instance_id:
        return jsonify({'success': False, 'error': 'Chybí ID mazlíčka'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if pet exists and belongs to user
    c.execute('SELECT id, pet_id, active FROM pets WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    pet = c.fetchone()
    if not pet:
        conn.close()
        return jsonify({'success': False, 'error': 'Mazlíček nenalezen'}), 404
    
    # Activate pet (deactivate others first if needed)
    c.execute('UPDATE pets SET active = 0 WHERE user_id = ?', (user_id,))
    c.execute('UPDATE pets SET active = 1 WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Mazlíček aktivován'})

@app.route('/api/pets/deactivate', methods=['POST'])
def deactivate_pet():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    pet_instance_id = data.get('pet_id')
    
    if not pet_instance_id:
        return jsonify({'success': False, 'error': 'Chybí ID mazlíčka'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if pet exists and belongs to user
    c.execute('SELECT id FROM pets WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    pet = c.fetchone()
    if not pet:
        conn.close()
        return jsonify({'success': False, 'error': 'Mazlíček nenalezen'}), 404
    
    # Deactivate pet
    c.execute('UPDATE pets SET active = 0 WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Mazlíček deaktivován'})

@app.route('/api/pets/feed', methods=['POST'])
def feed_pet():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    pet_instance_id = data.get('pet_id')
    fruit_id = data.get('fruit_id')
    
    if not pet_instance_id or not fruit_id:
        return jsonify({'success': False, 'error': 'Chybí ID mazlíčka nebo ovoce'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if pet exists and belongs to user
    c.execute('SELECT id, pet_id, level, experience FROM pets WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    pet = c.fetchone()
    if not pet:
        conn.close()
        return jsonify({'success': False, 'error': 'Mazlíček nenalezen'}), 404
    
    # Get pet definition
    pet_def = PET_DEFS.get(pet['pet_id'], {})
    required_rarity = pet_def.get('required_fruit_rarity', 'common')
    
    # Get fruit definition
    fruit_def = FRUIT_DEFS.get(fruit_id)
    if not fruit_def:
        conn.close()
        return jsonify({'success': False, 'error': 'Neplatné ovoce'}), 400
    
    fruit_rarity = fruit_def.get('rarity', 'common')
    
    # Check if fruit rarity matches or is better than required
    rarity_order = {'common': 1, 'rare': 2, 'epic': 3, 'legendary': 4, 'unique': 5}
    if rarity_order.get(fruit_rarity, 0) < rarity_order.get(required_rarity, 0):
        conn.close()
        return jsonify({'success': False, 'error': f'Tento mazlíček potřebuje {required_rarity} ovoce nebo lepší!'}), 400
    
    # Check if user has the fruit in equipment table
    c.execute('''SELECT id FROM equipment 
                 WHERE user_id = ? AND equipment_id = ? AND equipment_slot = 'fruit' 
                 LIMIT 1''', (user_id, fruit_id))
    fruit_item = c.fetchone()
    if not fruit_item:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš toto ovoce!'}), 400
    
    # Feed pet - each fruit = +1 level (no XP system)
    pet_level = pet['level']
    max_level = pet_def.get('max_level', 20)
    
    # Level up by 1 if not at max level
    new_level = min(pet_level + 1, max_level)
    leveled_up = new_level > pet_level
    
    # Update pet (keep experience at 0 since we don't use XP)
    c.execute('''UPDATE pets SET level = ?, experience = 0 WHERE id = ? AND user_id = ?''',
              (new_level, pet_instance_id, user_id))
    
    # Remove fruit from equipment
    c.execute('''DELETE FROM equipment WHERE id = ? AND user_id = ?''', (fruit_item['id'], user_id))
    
    conn.commit()
    conn.close()
    
    level_up_msg = f' a získal level {new_level}!' if leveled_up else ''
    return jsonify({
        'success': True,
        'message': f'Mazlíček nakrmen{level_up_msg}',
        'level': new_level,
        'leveled_up': leveled_up
    })

@app.route('/api/pets/rename', methods=['POST'])
def rename_pet():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    pet_instance_id = data.get('pet_id')
    new_name = data.get('name', '').strip()
    
    if not pet_instance_id:
        return jsonify({'success': False, 'error': 'Chybí ID mazlíčka'}), 400
    
    if not new_name:
        return jsonify({'success': False, 'error': 'Jméno nemůže být prázdné'}), 400
    
    if len(new_name) > 50:
        return jsonify({'success': False, 'error': 'Jméno je příliš dlouhé (max 50 znaků)'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if pet exists and belongs to user
    c.execute('SELECT id FROM pets WHERE id = ? AND user_id = ?', (pet_instance_id, user_id))
    pet = c.fetchone()
    if not pet:
        conn.close()
        return jsonify({'success': False, 'error': 'Mazlíček nenalezen'}), 404
    
    # Update custom name
    c.execute('''UPDATE pets SET custom_name = ? WHERE id = ? AND user_id = ?''',
              (new_name, pet_instance_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Mazlíček přejmenován na "{new_name}"'})

@app.route('/api/garden', methods=['GET'])
def get_garden():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get user's garden plots
    c.execute('''SELECT id, seed_id, seed_name, produces, planted_at, growth_time
                 FROM garden_plots WHERE user_id = ? ORDER BY planted_at DESC''', (user_id,))
    plots = []
    now = datetime.now(timezone.utc)
    
    for plot_row in c.fetchall():
        planted_at = parse_timestamp(plot_row['planted_at'])
        elapsed = (now - planted_at).total_seconds()
        time_remaining = max(0, plot_row['growth_time'] - elapsed)
        is_ready = time_remaining <= 0
        
        plots.append({
            'id': plot_row['id'],
            'seed_id': plot_row['seed_id'],
            'seed_name': plot_row['seed_name'],
            'produces': plot_row['produces'],
            'time_remaining': int(time_remaining),
            'is_ready': is_ready
        })
    
    # Get user's fruits
    c.execute('''SELECT fruit_common, fruit_rare, fruit_epic, fruit_legendary, fruit_unique
                 FROM garden_fruits WHERE user_id = ?''', (user_id,))
    fruit_row = c.fetchone()
    fruits = {
        'fruit_common': fruit_row['fruit_common'] if fruit_row else 0,
        'fruit_rare': fruit_row['fruit_rare'] if fruit_row else 0,
        'fruit_epic': fruit_row['fruit_epic'] if fruit_row else 0,
        'fruit_legendary': fruit_row['fruit_legendary'] if fruit_row else 0,
        'fruit_unique': fruit_row['fruit_unique'] if fruit_row else 0
    }
    
    # Get available seeds
    available_seeds = []
    for seed_id, seed_def in SEED_DEFS.items():
        available_seeds.append({
            'seed_id': seed_def['seed_id'],
            'name': seed_def['name'],
            'description': seed_def['description'],
            'rarity': seed_def['rarity'],
            'cost': seed_def['cost'],
            'growth_time': seed_def['growth_time'],
            'fruit_id': seed_def['fruit_id'],
            'fruit_name': seed_def['fruit_name'],
            'fruit_icon': seed_def['fruit_icon']
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'plots': plots,
        'fruits': fruits,
        'available_seeds': available_seeds
    })

@app.route('/api/garden/buy-seed', methods=['POST'])
def buy_seed():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    seed_id = data.get('seed_id')
    
    if not seed_id or seed_id not in SEED_DEFS:
        return jsonify({'success': False, 'error': 'Neplatné semínko'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    resources = hydrate_state_resources(state)
    
    seed_def = SEED_DEFS[seed_id]
    cost = seed_def['cost']
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    # Check if affordable
    affordable, lacking = deduct_cost(resources, effective_cost)
    if not affordable:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáte dostatek zdrojů ({lacking})'}), 400
    
    # Plant seed
    planted_at = datetime.now(timezone.utc)
    ready_at = planted_at + timedelta(seconds=seed_def['growth_time'])
    planted_at_str = planted_at.isoformat()
    ready_at_str = ready_at.isoformat()
    c.execute('''INSERT INTO garden_plots (user_id, seed_id, seed_name, produces, planted_at, growth_time, ready_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, seed_id, seed_def['name'], seed_def['fruit_name'], planted_at_str, seed_def['growth_time'], ready_at_str))
    
    persist_resources(c, user_id, resources)
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    resource_payload = resources_payload(resources)
    
    return jsonify({
        'success': True,
        **resource_payload,
        'message': f'Semínko {seed_def["name"]} zasazeno!'
    })

@app.route('/api/garden/harvest', methods=['POST'])
def harvest_plot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    plot_id = data.get('plot_id')
    
    if not plot_id:
        return jsonify({'success': False, 'error': 'Chybí ID záhonku'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get plot
    c.execute('''SELECT id, seed_id, seed_name, produces, planted_at, growth_time
                 FROM garden_plots WHERE id = ? AND user_id = ?''', (plot_id, user_id))
    plot = c.fetchone()
    
    if not plot:
        conn.close()
        return jsonify({'success': False, 'error': 'Záhon nenalezen'}), 404
    
    # Check if ready
    planted_at = parse_timestamp(plot['planted_at'])
    now = datetime.now(timezone.utc)
    elapsed = (now - planted_at).total_seconds()
    time_remaining = plot['growth_time'] - elapsed
    
    if time_remaining > 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Záhon ještě není připraven ke sklizni'}), 400
    
    # Get seed definition to find fruit_id
    seed_def = SEED_DEFS.get(plot['seed_id'])
    if not seed_def:
        conn.close()
        return jsonify({'success': False, 'error': 'Neplatné semínko'}), 400
    
    fruit_id = seed_def['fruit_id']
    fruit_name = seed_def['fruit_name']
    fruit_icon = seed_def['fruit_icon']
    
    # Add fruit to inventory as equipment item (not special - just a regular fruit/consumable)
    # Custom fruits from garden are not special items, they have no attributes and cannot be equipped as special
    acquired_at = datetime.now(timezone.utc).isoformat()
    c.execute('''INSERT INTO equipment 
                 (user_id, equipment_slot, equipment_id, equipped, acquired_at, acquired_via, acquisition_note)
                 VALUES (?, 'fruit', ?, 0, ?, 'garden', ?)''',
              (user_id, fruit_id, acquired_at, f'Sklizeno ze zahrady: {fruit_name}'))
    
    # Remove plot
    c.execute('DELETE FROM garden_plots WHERE id = ? AND user_id = ?', (plot_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Sklizeno! Získal jsi {fruit_icon} {fruit_name}!'
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
    sell_amount = data.get('amount')  # For resources, can sell partial amount
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state not found'}), 404
    
    resources = extract_player_resources(state)
    
    # Check if it's a resource (starts with 'resource_')
    if isinstance(instance_id, str) and instance_id.startswith('resource_'):
        resource_key = instance_id.replace('resource_', '')
        if resource_key not in TRADEABLE_CURRENCIES:
            conn.close()
            return jsonify({'success': False, 'error': 'Neplatný zdroj'}), 400
        
        current_amount = resources.get(resource_key, 0)
        if current_amount <= 0:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš tento zdroj'}), 400
        
        # Determine how much to sell
        amount_to_sell = current_amount
        if sell_amount is not None:
            try:
                amount_to_sell = float(sell_amount)
                if amount_to_sell <= 0 or amount_to_sell > current_amount:
                    conn.close()
                    return jsonify({'success': False, 'error': 'Neplatné množství'}), 400
            except (TypeError, ValueError):
                conn.close()
                return jsonify({'success': False, 'error': 'Neplatné množství'}), 400
        
        # Calculate sell value using market rates
        inflation_rate = get_current_inflation_rate(c)
        market_rates = get_dynamic_market_rates(c, inflation_rate)
        rate_info = market_rates.get(resource_key, {})
        sell_price_per_unit = rate_info.get('sell', BASE_EXCHANGE_RATES.get(resource_key, 0))
        total_sell_value = round(amount_to_sell * sell_price_per_unit, 2)
        
        if total_sell_value <= 0:
            conn.close()
            return jsonify({'success': False, 'error': 'Cena je příliš nízká'}), 400
        
        # Update resources
        resources[resource_key] = current_amount - amount_to_sell
        resources['gooncoins'] = resources.get('gooncoins', 0) + total_sell_value
        
        # Apply market trade effect
        apply_market_trade(c, resource_key, 'sell', amount_to_sell)
        
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
            'message': f'Prodáno {amount_to_sell:.2f} {RESOURCE_LABELS_BACKEND.get(resource_key, resource_key)} za {total_sell_value:.2f} 💰',
            **resource_payload,
            'equipment_counts': player_equipment_counts,
            'equipment': equipped_items,
            'inventory': inventory_payload
        })
    
    # Handle equipment items (original logic)
    try:
        instance_id = int(instance_id)
    except (TypeError, ValueError):
        instance_id = None
    
    if not instance_id:
        return jsonify({'success': False, 'error': 'Neplatná položka inventáře'}), 400
    
    c.execute('SELECT * FROM equipment WHERE id = ? AND user_id = ?', (instance_id, user_id))
    equipment_row = c.fetchone()
    if not equipment_row:
        conn.close()
        return jsonify({'success': False, 'error': 'Předmět nebyl nalezen'}), 404
    
    equipment_id = equipment_row['equipment_id']
    market_value = register_item_supply_change(c, equipment_id, -1) or calculate_item_base_value(equipment_id)
    # Prodáváme za plnou tržní cenu (100%)
    sell_value = round(market_value, 2)
    if sell_value <= 0:
        sell_value = max(1.0, calculate_item_base_value(equipment_id))
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
    
    data = request.get_json() or {}
    building_type = data.get('building_type')
    
    if building_type not in BUILDINGS_DEFS:
        return jsonify({'success': False, 'error': 'Neplatná budova'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state and story
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    story = ensure_story_progress(c, user_id)
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    building_def = BUILDINGS_DEFS[building_type]
    prerequisites = building_def.get('prerequisites', [])
    
    c.execute('SELECT building_type, level FROM buildings WHERE user_id = ?', (user_id,))
    player_buildings = {row['building_type']: row['level'] for row in c.fetchall()}
    if player_buildings.get(building_type, 0) > 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Budova již je postavena'})
    
    missing_prereq = next((req for req in prerequisites if player_buildings.get(req, 0) <= 0), None)
    if missing_prereq:
        conn.close()
        missing_label = BUILDINGS_DEFS.get(missing_prereq, {}).get('name', missing_prereq)
        return jsonify({'success': False, 'error': f'Nejdřív postav {missing_label}'})
    
    is_workshop = building_type == 'workshop'
    is_always_available = building_def.get('always_available', False)
    is_story_unlocked = building_type in unlocked_buildings
    if not (is_workshop or is_always_available or is_story_unlocked):
        conn.close()
        return jsonify({'success': False, 'error': 'Budova ještě není odemčena'})
    
    resources = extract_player_resources(state)
    cost = building_def['cost']
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    lacking_resource = next(
        (resource for resource, amount in (effective_cost or {}).items()
         if amount and resources.get(resource, 0) < amount),
        None
    )
    if lacking_resource:
        conn.close()
        label = RESOURCE_LABELS_BACKEND.get(lacking_resource, lacking_resource)
        return jsonify({'success': False, 'error': f'Nemáte dostatek: {label}'})
    
    for resource, amount in (effective_cost or {}).items():
        if not amount:
            continue
        resources[resource] = resources.get(resource, 0) - amount
    
    c.execute('INSERT INTO buildings (user_id, building_type, level) VALUES (?, ?, 1)',
             (user_id, building_type))
    
    # Unlock currencies if building has unlock_currencies
    currencies_to_unlock = building_def.get('unlock_currencies', [])
    if currencies_to_unlock:
        unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
        updated_currencies = list(set(unlocked_currencies + currencies_to_unlock))
        c.execute('''UPDATE story_progress 
                     SET unlocked_currencies = ?
                     WHERE user_id = ?''',
                 (json.dumps(updated_currencies), user_id))
    
    persist_resources(c, user_id, resources)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        **resources_payload(resources),
        'building_type': building_type,
        'unlocked_currencies': currencies_to_unlock if currencies_to_unlock else []
    })

@app.route('/api/upgrade-building', methods=['POST'])
def upgrade_building():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    building_type = data.get('building_type')
    
    if building_type not in BUILDINGS_DEFS:
        return jsonify({'success': False, 'error': 'Neplatná budova'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    building_def = BUILDINGS_DEFS[building_type]
    
    # Check if building is repeatable
    if not building_def.get('repeatable', False):
        conn.close()
        return jsonify({'success': False, 'error': 'Tato budova není upgradovatelná'})
    
    # Get current building level
    c.execute('SELECT level FROM buildings WHERE user_id = ? AND building_type = ?', (user_id, building_type))
    building = c.fetchone()
    
    if not building or building['level'] <= 0:
        conn.close()
        return jsonify({'success': False, 'error': 'Budova ještě není postavena'})
    
    current_level = building['level']
    max_level = building_def.get('max_level', 1)
    
    if current_level >= max_level:
        conn.close()
        return jsonify({'success': False, 'error': 'Budova je již na maximální úrovni'})
    
    # Calculate upgrade cost (matching frontend logic: multiplier^(currentLevel-1))
    base_cost = building_def['cost']
    level_cost_multiplier = building_def.get('level_cost_multiplier', 2.0)
    cost_multiplier = level_cost_multiplier ** (current_level - 1)
    
    upgrade_cost = {}
    for resource, amount in base_cost.items():
        upgrade_cost[resource] = int(amount * cost_multiplier)
    
    # Apply inflation
    resources = extract_player_resources(state)
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(upgrade_cost, inflation_multiplier)
    
    # Check if affordable
    lacking_resource = next(
        (resource for resource, amount in (effective_cost or {}).items()
         if amount and resources.get(resource, 0) < amount),
        None
    )
    if lacking_resource:
        conn.close()
        label = RESOURCE_LABELS_BACKEND.get(lacking_resource, lacking_resource)
        return jsonify({'success': False, 'error': f'Nemáte dostatek: {label}'})
    
    # Deduct resources
    for resource, amount in (effective_cost or {}).items():
        if not amount:
            continue
        resources[resource] = resources.get(resource, 0) - amount
    
    # Update building level
    new_level = current_level + 1
    c.execute('UPDATE buildings SET level = ? WHERE user_id = ? AND building_type = ?',
              (new_level, user_id, building_type))
    
    persist_resources(c, user_id, resources)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        **resources_payload(resources),
        'building_type': building_type,
        'new_level': new_level
    })

@app.route('/api/gems', methods=['GET'])
def get_gems():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get player's gems
    c.execute('SELECT gem_type, level FROM gems WHERE user_id = ?', (user_id,))
    player_gems = {row['gem_type']: row['level'] for row in c.fetchall()}
    
    # Build gems payload
    gems_data = {}
    for gem_type in GEM_SLOTS:
        gem_def = GEM_DEFINITIONS[gem_type]
        current_level = player_gems.get(gem_type, 0)
        max_level = max(gem_def['levels'].keys())
        
        gems_data[gem_type] = {
            'name': gem_def['name'],
            'icon': gem_def['icon'],
            'color': gem_def['color'],
            'description': gem_def['description'],
            'stat_type': gem_def['stat_type'],
            'current_level': current_level,
            'max_level': max_level,
            'current_bonus': gem_def['levels'].get(current_level, {}).get('bonus', 0) if current_level > 0 else 0,
            'next_level': current_level + 1 if current_level < max_level else None,
            'next_bonus': gem_def['levels'].get(current_level + 1, {}).get('bonus', 0) if current_level < max_level else None,
            'next_cost': gem_def['levels'].get(current_level + 1, {}).get('cost', {}) if current_level < max_level else None
        }
    
    conn.close()
    return jsonify({'gems': gems_data})

@app.route('/api/gems/upgrade', methods=['POST'])
def upgrade_gem():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    gem_type = data.get('gem_type')
    
    if not gem_type or gem_type not in GEM_DEFINITIONS:
        return jsonify({'success': False, 'error': 'Neplatný drahokam'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    gem_def = GEM_DEFINITIONS[gem_type]
    max_level = max(gem_def['levels'].keys())
    
    # Get current gem level
    c.execute('SELECT level FROM gems WHERE user_id = ? AND gem_type = ?', (user_id, gem_type))
    gem_row = c.fetchone()
    
    current_level = gem_row['level'] if gem_row and gem_row['level'] else 0
    
    if current_level >= max_level:
        conn.close()
        return jsonify({'success': False, 'error': f'Drahokam je již na maximální úrovni ({max_level})'})
    
    # Determine if this is initial purchase or upgrade
    next_level = current_level + 1
    level_data = gem_def['levels'].get(next_level)
    
    if not level_data:
        conn.close()
        return jsonify({'success': False, 'error': 'Neplatná úroveň'})
    
    cost = level_data.get('cost', {})
    resources = extract_player_resources(state)
    inflation_rate = get_current_inflation_rate(c)
    inflation_multiplier = calculate_inflation_multiplier(inflation_rate)
    effective_cost = apply_inflation_to_cost(cost, inflation_multiplier)
    
    # Check if player has enough resources
    lacking_resource = next(
        (resource for resource, amount in (effective_cost or {}).items()
         if amount and resources.get(resource, 0) < amount),
        None
    )
    if lacking_resource:
        conn.close()
        label = RESOURCE_LABELS_BACKEND.get(lacking_resource, lacking_resource)
        return jsonify({'success': False, 'error': f'Nemáte dostatek: {label}'})
    
    # Deduct resources
    for resource, amount in (effective_cost or {}).items():
        if not amount:
            continue
        resources[resource] = resources.get(resource, 0) - amount
    
    # Update or insert gem
    if gem_row:
        c.execute('UPDATE gems SET level = ? WHERE user_id = ? AND gem_type = ?',
                  (next_level, user_id, gem_type))
    else:
        c.execute('INSERT INTO gems (user_id, gem_type, level) VALUES (?, ?, ?)',
                  (user_id, gem_type, next_level))
    
    persist_resources(c, user_id, resources)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        **resources_payload(resources),
        'gem_type': gem_type,
        'new_level': next_level,
        'new_bonus': level_data.get('bonus', 0)
    })

@app.route('/api/character-stats', methods=['GET'])
def get_character_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    char_stats = ensure_character_stats(c, user_id)
    combat_stats = calculate_player_combat_stats(c, user_id)
    
    # Calculate experience needed for next level
    current_level = char_stats['level']
    exp_needed = 100 * (current_level ** 1.5)
    
    # Get equipped items for character panel
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_rows = c.fetchall()
    equipped_items = {}
    equipped_items_detail = {}
    for row in equipped_rows:
        slot = row['equipment_slot']
        equipment_id = row['equipment_id']
        equipped_items[slot] = equipment_id
        definition = get_item_definition(equipment_id)
        # Map equipment slots to character panel slots
        for char_slot, eq_slot in CHARACTER_SLOT_MAP.items():
            if eq_slot == slot:
                equipped_items_detail[char_slot] = {
                    'equipment_id': equipment_id,
                    'name': definition.get('name', equipment_id),
                    'slot': slot,
                    'rarity': definition.get('rarity', 'common'),
                    'bonus': definition.get('bonus', {}),
                    'image': definition.get('image')
                }
    
    conn.close()
    
    # Get class from char_stats
    char_class = 'warrior'
    try:
        char_class = char_stats['class'] if char_stats['class'] else 'warrior'
    except (KeyError, IndexError):
        char_class = 'warrior'
    
    return jsonify({
        'level': char_stats['level'],
        'experience': char_stats['experience'],
        'experience_needed': exp_needed,
        'strength': char_stats['strength'],
        'dexterity': char_stats['dexterity'],
        'intelligence': char_stats['intelligence'],
        'constitution': char_stats['constitution'],
        'luck': char_stats['luck'],
        'available_points': char_stats['available_points'],
        'class': char_class,
        'combat_stats': combat_stats,
        'equipped_items': equipped_items_detail
    })

@app.route('/api/character-stats/exchange-points', methods=['POST'])
def exchange_character_points():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    gooncoins_amount = data.get('gooncoins', 0)
    
    try:
        gooncoins_amount = float(gooncoins_amount)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Neplatné množství'})
    
    if gooncoins_amount < 1000:
        return jsonify({'success': False, 'error': 'Minimální směna je 1000 Gooncoinů'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    try:
        # Check if user has enough gooncoins
        c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
        state = c.fetchone()
        if not state:
            conn.close()
            return jsonify({'success': False, 'error': 'Stav hry nenalezen'})
        
        current_gooncoins = float(state['gooncoins'] or 0)
        if current_gooncoins < gooncoins_amount:
            conn.close()
            return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Máš {current_gooncoins:.2f}'})
        
        # Exchange rate: 1000 gooncoins = 1 character point
        points_gained = int(gooncoins_amount / 1000)
        gooncoins_used = points_gained * 1000  # Use exact amount for points gained
        new_gooncoins = current_gooncoins - gooncoins_used
        
        # Update game state
        c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
        
        # Update character stats
        char_stats = ensure_character_stats(c, user_id)
        current_points = int(char_stats['available_points'] or 0)
        new_points = current_points + points_gained
        c.execute('''UPDATE character_stats 
                     SET available_points = ? 
                     WHERE user_id = ?''', (new_points, user_id))
        
        conn.commit()
        conn.close()
        
        refresh_economy_after_change()
        
        return jsonify({
            'success': True,
            'points_gained': points_gained,
            'available_points': new_points,
            'gooncoins_remaining': new_gooncoins,
            'gooncoins_used': gooncoins_used
        })
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error in exchange_character_points: {e}")
        return jsonify({'success': False, 'error': f'Chyba při směně: {str(e)}'}), 500

@app.route('/api/character-stats/upgrade', methods=['POST'])
def upgrade_character_stat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    stat_name = data.get('stat')
    
    if stat_name not in ['strength', 'dexterity', 'intelligence', 'constitution', 'luck']:
        return jsonify({'success': False, 'error': 'Neplatný stat'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    char_stats = ensure_character_stats(c, user_id)
    
    if char_stats['available_points'] < 1:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek bodů'})
    
    # Update stat
    current_value = char_stats[stat_name]
    new_value = current_value + 1
    new_points = char_stats['available_points'] - 1
    
    c.execute(f'''UPDATE character_stats 
                 SET {stat_name} = ?, available_points = ?
                 WHERE user_id = ?''', (new_value, new_points, user_id))
    
    # Recalculate combat stats
    combat_stats = calculate_player_combat_stats(c, user_id)
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'stat': stat_name,
        'new_value': new_value,
        'available_points': new_points,
        'combat_stats': combat_stats
    })

@app.route('/api/character-stats/change-class', methods=['POST'])
def change_character_class():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    new_class = data.get('class')
    
    if new_class not in CHARACTER_CLASSES:
        return jsonify({'success': False, 'error': 'Neplatná třída'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Update class
    c.execute('UPDATE character_stats SET class = ? WHERE user_id = ?', (new_class, user_id))
    
    # Recalculate combat stats
    combat_stats = calculate_player_combat_stats(c, user_id)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'class': new_class,
        'combat_stats': combat_stats
    })

# Map character panel slots to equipment system slots
CHARACTER_SLOT_MAP = {
    'helmet': 'helmet',
    'necklace': 'amulet',
    'weapon': 'weapon',
    'armor': 'armor',
    'belt': 'special',  # Belt maps to special for now
    'ring': 'ring',
    'gloves': 'special',  # Gloves maps to special for now
    'boots': 'boots',
    'special': 'special',
    'vehicle': 'vehicle'  # Vehicle slot
}

@app.route('/api/character/equipment/slot/<slot>', methods=['GET'])
def get_items_for_slot(slot):
    """Get all items available for a specific slot"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    # Map character panel slot to equipment slot
    equipment_slot = CHARACTER_SLOT_MAP.get(slot, slot)
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get all items for this slot
    c.execute('''SELECT id, equipment_id, equipment_slot, equipped,
                         acquired_at, acquired_via, acquisition_note
                  FROM equipment
                  WHERE user_id = ? AND equipment_slot = ?
                  ORDER BY equipped DESC, acquired_at DESC''', (user_id, equipment_slot))
    rows = c.fetchall()
    
    items = []
    for row in rows:
        equipment_id = row['equipment_id']
        definition = get_item_definition(equipment_id)
        items.append({
            'instance_id': row['id'],
            'equipment_id': equipment_id,
            'name': definition.get('name', equipment_id),
            'slot': definition.get('slot', equipment_slot),
            'rarity': definition.get('rarity', 'common'),
            'bonus': definition.get('bonus', {}),
            'image': definition.get('image'),
            'equipped': bool(row['equipped']),
            'acquired_at': row['acquired_at']
        })
    
    # Also get currently equipped item for this slot
    c.execute('SELECT equipment_id FROM equipment WHERE user_id = ? AND equipment_slot = ? AND equipped = 1', 
              (user_id, equipment_slot))
    equipped_row = c.fetchone()
    currently_equipped = equipped_row['equipment_id'] if equipped_row else None
    
    conn.close()
    
    return jsonify({
        'success': True,
        'slot': slot,
        'equipment_slot': equipment_slot,
        'items': items,
        'currently_equipped': currently_equipped
    })

@app.route('/api/character/equipment/equip', methods=['POST'])
def equip_item():
    """Equip an item to a slot"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    slot = data.get('slot')
    
    if not instance_id or not slot:
        return jsonify({'success': False, 'error': 'Chybí instance_id nebo slot'}), 400
    
    # Map character panel slot to equipment slot
    equipment_slot = CHARACTER_SLOT_MAP.get(slot, slot)
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Verify item exists and belongs to user
    c.execute('SELECT * FROM equipment WHERE id = ? AND user_id = ?', (instance_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return jsonify({'success': False, 'error': 'Item nenalezen'}), 404
    
    # Verify slot matches
    if item['equipment_slot'] != equipment_slot:
        conn.close()
        return jsonify({'success': False, 'error': 'Item nepatří do tohoto slotu'}), 400
    
    # Unequip other items in this slot
    c.execute('UPDATE equipment SET equipped = 0 WHERE user_id = ? AND equipment_slot = ?', 
              (user_id, equipment_slot))
    
    # Equip this item
    c.execute('UPDATE equipment SET equipped = 1 WHERE id = ? AND user_id = ?', 
              (instance_id, user_id))
    
    # Sync equipped items to character_stats
    sync_equipped_to_character_stats(c, user_id)
    
    # Get updated equipment and stats
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_rows = c.fetchall()
    equipped_items = {}
    equipped_items_detail = {}
    for row in equipped_rows:
        slot = row['equipment_slot']
        equipment_id = row['equipment_id']
        equipped_items[slot] = equipment_id
        definition = get_item_definition(equipment_id)
        # Map equipment slots to character panel slots
        for char_slot, eq_slot in CHARACTER_SLOT_MAP.items():
            if eq_slot == slot:
                equipped_items_detail[char_slot] = {
                    'equipment_id': equipment_id,
                    'name': definition.get('name', equipment_id),
                    'slot': slot,
                    'rarity': definition.get('rarity', 'common'),
                    'bonus': definition.get('bonus', {}),
                    'image': definition.get('image')
                }
    
    combat_stats = calculate_player_combat_stats(c, user_id)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'equipped': True,
        'equipment': equipped_items,
        'equipped_items': equipped_items_detail,
        'combat_stats': combat_stats
    })

@app.route('/api/character/equipment/unequip', methods=['POST'])
def unequip_item():
    """Unequip an item from a slot"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    slot = data.get('slot')
    
    if not slot:
        return jsonify({'success': False, 'error': 'Chybí slot'}), 400
    
    # Map character panel slot to equipment slot
    equipment_slot = CHARACTER_SLOT_MAP.get(slot, slot)
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Unequip item in this slot
    c.execute('UPDATE equipment SET equipped = 0 WHERE user_id = ? AND equipment_slot = ?', 
              (user_id, equipment_slot))
    
    # Sync equipped items to character_stats
    sync_equipped_to_character_stats(c, user_id)
    
    # Get updated equipment and stats
    c.execute('SELECT equipment_slot, equipment_id FROM equipment WHERE user_id = ? AND equipped = 1', (user_id,))
    equipped_rows = c.fetchall()
    equipped_items = {}
    equipped_items_detail = {}
    for row in equipped_rows:
        slot = row['equipment_slot']
        equipment_id = row['equipment_id']
        equipped_items[slot] = equipment_id
        definition = get_item_definition(equipment_id)
        # Map equipment slots to character panel slots
        for char_slot, eq_slot in CHARACTER_SLOT_MAP.items():
            if eq_slot == slot:
                equipped_items_detail[char_slot] = {
                    'equipment_id': equipment_id,
                    'name': definition.get('name', equipment_id),
                    'slot': slot,
                    'rarity': definition.get('rarity', 'common'),
                    'bonus': definition.get('bonus', {}),
                    'image': definition.get('image')
                }
    
    combat_stats = calculate_player_combat_stats(c, user_id)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'equipped': False,
        'equipment': equipped_items,
        'equipped_items': equipped_items_detail,
        'combat_stats': combat_stats
    })

# API for item definitions and marketplace
@app.route('/api/items/definitions', methods=['GET'])
def get_all_items_api():
    """Get all item definitions from database"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    all_items = get_all_item_definitions()
    return jsonify({
        'success': True,
        'items': all_items
    })

@app.route('/api/marketplace/list', methods=['GET'])
def get_marketplace_list():
    """Get all items for sale on marketplace"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get active listings
    c.execute('''SELECT m.id, m.seller_id, m.item_instance_id, m.price, m.currency, m.created_at,
                        e.equipment_id, e.equipment_slot, e.acquired_at,
                        u.username as seller_name
                 FROM item_marketplace m
                 JOIN equipment e ON m.item_instance_id = e.id
                 JOIN users u ON m.seller_id = u.id
                 WHERE m.status = 'active' AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))
                 ORDER BY m.created_at DESC
                 LIMIT 100''')
    listings = []
    for row in c.fetchall():
        item_def = get_item_definition(row['equipment_id'])
        listings.append({
            'listing_id': row['id'],
            'seller_id': row['seller_id'],
            'seller_name': row['seller_name'],
            'item_instance_id': row['item_instance_id'],
            'equipment_id': row['equipment_id'],
            'item_name': item_def.get('name', row['equipment_id']),
            'slot': item_def.get('slot', row['equipment_slot']),
            'rarity': item_def.get('rarity', 'common'),
            'image': item_def.get('image'),
            'price': row['price'],
            'currency': row['currency'],
            'created_at': row['created_at']
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'listings': listings
    })

@app.route('/api/marketplace/sell', methods=['POST'])
def marketplace_sell():
    """List an item for sale on marketplace"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    price = data.get('price')
    currency = data.get('currency', 'gooncoins')
    
    if not instance_id or not price:
        return jsonify({'success': False, 'error': 'Chybí instance_id nebo price'}), 400
    
    if price <= 0:
        return jsonify({'success': False, 'error': 'Cena musí být větší než 0'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Verify item exists and belongs to user
    c.execute('SELECT * FROM equipment WHERE id = ? AND user_id = ?', (instance_id, user_id))
    item = c.fetchone()
    if not item:
        conn.close()
        return jsonify({'success': False, 'error': 'Item nenalezen'}), 404
    
    # Check if item is equipped
    if item['equipped']:
        conn.close()
        return jsonify({'success': False, 'error': 'Nelze prodat vybavený item'}), 400
    
    # Check if already listed
    c.execute('SELECT id FROM item_marketplace WHERE item_instance_id = ? AND status = "active"', (instance_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Item je již na trhu'}), 400
    
    # Create listing (expires in 7 days)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    c.execute('''INSERT INTO item_marketplace (seller_id, item_instance_id, price, currency, status, expires_at)
                 VALUES (?, ?, ?, ?, 'active', ?)''',
             (user_id, instance_id, price, currency, expires_at))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Item přidán na trh'
    })

@app.route('/api/marketplace/buy', methods=['POST'])
def marketplace_buy():
    """Buy an item from marketplace"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    listing_id = data.get('listing_id')
    
    if not listing_id:
        return jsonify({'success': False, 'error': 'Chybí listing_id'}), 400
    
    buyer_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get listing
    c.execute('''SELECT m.*, e.equipment_id, e.equipment_slot, e.user_id as current_owner
                 FROM item_marketplace m
                 JOIN equipment e ON m.item_instance_id = e.id
                 WHERE m.id = ? AND m.status = 'active' AND (m.expires_at IS NULL OR m.expires_at > datetime('now'))''',
             (listing_id,))
    listing = c.fetchone()
    
    if not listing:
        conn.close()
        return jsonify({'success': False, 'error': 'Nabídka nenalezena nebo již není aktivní'}), 404
    
    if listing['seller_id'] == buyer_id:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemůžeš koupit svůj vlastní item'}), 400
    
    if listing['current_owner'] != listing['seller_id']:
        conn.close()
        return jsonify({'success': False, 'error': 'Item již nepatří prodejci'}), 400
    
    # Get buyer resources
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (buyer_id,))
    buyer_state = c.fetchone()
    if not buyer_state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    buyer_resources = extract_player_resources(buyer_state)
    price = listing['price']
    currency = listing['currency']
    
    # Check if buyer has enough
    if buyer_resources.get(currency, 0) < price:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek {RESOURCE_LABELS_BACKEND.get(currency, currency)}'}), 400
    
    # Transfer item
    c.execute('UPDATE equipment SET user_id = ? WHERE id = ?', (buyer_id, listing['item_instance_id']))
    
    # Transfer payment
    buyer_resources[currency] = buyer_resources.get(currency, 0) - price
    persist_resources(c, buyer_id, buyer_resources)
    
    # Give money to seller
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (listing['seller_id'],))
    seller_state = c.fetchone()
    if seller_state:
        seller_resources = extract_player_resources(seller_state)
        seller_resources[currency] = seller_resources.get(currency, 0) + price
        persist_resources(c, listing['seller_id'], seller_resources)
    
    # Mark listing as sold
    c.execute('UPDATE item_marketplace SET status = ? WHERE id = ?', ('sold', listing_id))
    
    # Update item market supply
    register_item_supply_change(c, listing['equipment_id'], 0)  # No change, just transfer
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'message': 'Item zakoupen',
        **resources_payload(buyer_resources)
    })

@app.route('/api/marketplace/cancel', methods=['POST'])
def marketplace_cancel():
    """Cancel a marketplace listing"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    listing_id = data.get('listing_id')
    
    if not listing_id:
        return jsonify({'success': False, 'error': 'Chybí listing_id'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Verify listing belongs to user
    c.execute('SELECT * FROM item_marketplace WHERE id = ? AND seller_id = ? AND status = "active"', 
             (listing_id, user_id))
    listing = c.fetchone()
    
    if not listing:
        conn.close()
        return jsonify({'success': False, 'error': 'Nabídka nenalezena'}), 404
    
    # Cancel listing
    c.execute('UPDATE item_marketplace SET status = ? WHERE id = ?', ('cancelled', listing_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Nabídka zrušena'
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
    
    resources = extract_player_resources(state)
    message = ''
    
    if action == 'buy':
        total_cost = rate_data['buy'] * amount
        if resources.get('gooncoins', 0) < total_cost:
            conn.close()
            return jsonify({'success': False, 'error': 'Nemáš dost Gooncoinů'})
        resources['gooncoins'] = resources.get('gooncoins', 0) - total_cost
        resources[currency] = resources.get(currency, 0) + amount
        message = f'Nakoupil jsi {amount} {currency}.'
    else:
        current_amount = resources.get(currency, 0)
        if current_amount < amount:
            conn.close()
            currency_labels = {
                'astma': 'Astma',
                'poharky': 'Pohárků',
                'mrkev': 'Mrkve',
                'uzené': 'Uzeného',
                'logs': 'Klád',
                'planks': 'Prken',
                'grain': 'Obilí',
                'flour': 'Mouky',
                'bread': 'Chleba',
                'fish': 'Ryby'
            }
            label = currency_labels.get(currency, currency)
            return jsonify({'success': False, 'error': f'Nemáš dost {label}'})
        
        total_return = rate_data['sell'] * amount
        resources['gooncoins'] = resources.get('gooncoins', 0) + total_return
        resources[currency] = current_amount - amount
        message = f'Prodal jsi {amount} {currency}.'
    
    apply_market_trade(c, currency, action, amount)
    persist_resources(c, user_id, resources)
    
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
        **resources_payload(resources),
        'economy': economy_snapshot
    })

@app.route('/api/reduce-inflation', methods=['POST'])
def reduce_inflation():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    amount = data.get('amount', 0)
    
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Neplatné množství'})
    
    if amount < 1000:
        return jsonify({'success': False, 'error': 'Minimální investice je 1000 Gooncoinů'})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state not found'}), 404
    
    current_gooncoins = state['gooncoins'] or 0
    if current_gooncoins < amount:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Máš {current_gooncoins:.0f}, potřebuješ {amount:.0f}'})
    
    # Get current inflation
    ensure_economy_row(c)
    c.execute('SELECT inflation_rate, gooncoin_supply FROM economy_state WHERE id = 1')
    economy = c.fetchone()
    current_inflation = economy['inflation_rate'] if economy and economy['inflation_rate'] is not None else BASE_INFLATION_RATE
    
    # Calculate reduction effect (non-linear - more effective at higher inflation)
    # Base reduction: 0.001 per 10k gooncoins, scaled by current inflation
    base_reduction = (amount / 10000) * 0.001
    inflation_factor = max(1.0, current_inflation / BASE_INFLATION_RATE)
    actual_reduction = base_reduction * inflation_factor
    
    # Apply reduction (but don't go below minimum)
    new_inflation = max(MIN_INFLATION_RATE, current_inflation - actual_reduction)
    reduction_applied = current_inflation - new_inflation
    
    # Update economy state
    now = datetime.now(timezone.utc)
    c.execute('''UPDATE economy_state 
                 SET inflation_rate = ?, last_adjustment = ?
                 WHERE id = 1''',
              (new_inflation, now.isoformat()))
    
    # Deduct gooncoins from user
    new_gooncoins = current_gooncoins - amount
    c.execute('''UPDATE game_state 
                 SET gooncoins = ?, last_update = CURRENT_TIMESTAMP
                 WHERE user_id = ?''',
              (new_gooncoins, user_id))
    
    conn.commit()
    conn.close()
    
    # Refresh economy snapshot
    economy_snapshot = fetch_economy_snapshot(force=True)
    
    return jsonify({
        'success': True,
        'message': f'Inflace snížena o {reduction_applied * 100:.2f}%! Nová inflace: {new_inflation * 100:.2f}%',
        'old_inflation': current_inflation,
        'new_inflation': new_inflation,
        'reduction': reduction_applied,
        'gooncoins_spent': amount,
        'gooncoins_remaining': new_gooncoins,
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

# Coin Flip Gambling
@app.route('/api/gamble/coinflip', methods=['POST'])
def api_coinflip():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    choice = data.get('choice', 'heads')  # 'heads' or 'tails'
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    if choice not in ['heads', 'tails']:
        return jsonify({'success': False, 'error': 'Neplatná volba'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Flip coin (50/50 chance)
    result = random.choice(['heads', 'tails'])
    won = (choice == result)
    
    # 1.5x multiplier if win (house edge ~25%)
    if won:
        winnings = bet_amount * 1.5
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        winnings = 0
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'coinflip', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'choice': choice, 'result': result, 'won': won}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'result': result,
        'choice': choice,
        'won': won,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Dice Roll Gambling
@app.route('/api/gamble/dice', methods=['POST'])
def api_dice():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    guess = int(data.get('guess', 1))  # 1-6
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    if guess < 1 or guess > 6:
        return jsonify({'success': False, 'error': 'Hádej číslo 1-6'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Roll dice (1-6)
    result = random.randint(1, 6)
    won = (guess == result)
    
    # 4x multiplier if win (house edge ~33.33%)
    if won:
        winnings = bet_amount * 4
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        winnings = 0
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'dice', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'guess': guess, 'result': result, 'won': won}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'result': result,
        'guess': guess,
        'won': won,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Slot Machine Gambling
@app.route('/api/gamble/slot', methods=['POST'])
def api_slot():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Slot symbols: 💰, 💎, 🍖, 🥕, 🥃, 💨, ⚔️, 👑
    symbols = ['💰', '💎', '🍖', '🥕', '🥃', '💨', '⚔️', '👑']
    
    # Roll 3 reels
    reel1 = random.choice(symbols)
    reel2 = random.choice(symbols)
    reel3 = random.choice(symbols)
    
    result = [reel1, reel2, reel3]
    
    # Calculate winnings based on combinations
    winnings = 0
    multiplier = 0
    
    if reel1 == reel2 == reel3:
        # Three of a kind
        if reel1 == '👑':
            multiplier = 30  # Jackpot! (reduced from 50)
        elif reel1 == '⚔️':
            multiplier = 15  # (reduced from 25)
        elif reel1 == '💎':
            multiplier = 10  # (reduced from 15)
        elif reel1 == '💰':
            multiplier = 6  # (reduced from 10)
        else:
            multiplier = 3  # (reduced from 5)
    elif reel1 == reel2 or reel2 == reel3 or reel1 == reel3:
        # Two of a kind
        multiplier = 1.5  # (reduced from 2)
    
    if multiplier > 0:
        winnings = bet_amount * multiplier
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'slot', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'reels': result, 'multiplier': multiplier}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'reels': result,
        'multiplier': multiplier,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Roulette Gambling
@app.route('/api/gamble/roulette', methods=['POST'])
def api_roulette():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    bet_type = data.get('bet_type', 'red')  # 'red', 'black', 'green', or number 0-36
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Spin roulette (0-36, 0 is green)
    result = random.randint(0, 36)
    
    # Determine color
    if result == 0:
        color = 'green'
    elif result in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
        color = 'red'
    else:
        color = 'black'
    
    won = False
    multiplier = 0
    
    if bet_type == 'red' and color == 'red':
        won = True
        multiplier = 2  # 2x for color bet
    elif bet_type == 'black' and color == 'black':
        won = True
        multiplier = 2
    elif bet_type == 'green' and color == 'green':
        won = True
        multiplier = 35  # 35x for green (0)
    elif bet_type.isdigit() and int(bet_type) == result:
        won = True
        multiplier = 35  # 35x for exact number
    
    if won:
        winnings = bet_amount * multiplier
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        winnings = 0
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'roulette', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'bet_type': bet_type, 'result': result, 'color': color, 'won': won}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'result': result,
        'color': color,
        'bet_type': bet_type,
        'won': won,
        'multiplier': multiplier,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Number Guess Gambling (1-100)
@app.route('/api/gamble/number', methods=['POST'])
def api_number_guess():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    guess = int(data.get('guess', 50))  # 1-100
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    if guess < 1 or guess > 100:
        return jsonify({'success': False, 'error': 'Hádej číslo 1-100'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Generate random number 1-100
    result = random.randint(1, 100)
    won = (guess == result)
    
    # 80x multiplier if win (house edge ~1%)
    if won:
        winnings = bet_amount * 80
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        winnings = 0
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'number_guess', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'guess': guess, 'result': result, 'won': won}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'result': result,
        'guess': guess,
        'won': won,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Blackjack-style Gambling (simplified)
@app.route('/api/gamble/blackjack', methods=['POST'])
def api_blackjack():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = float(data.get('bet_amount', 0))
    action = data.get('action', 'stand')  # 'hit' or 'stand'
    currency = data.get('currency', 'gooncoins')
    
    if bet_amount <= 0:
        return jsonify({'success': False, 'error': 'Sázka musí být větší než 0'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state nenalezen'}), 404
    
    balances = hydrate_state_resources(state)
    
    if balances.get(currency, 0) < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dostatek měny'}), 400
    
    balances[currency] -= bet_amount
    
    # Simplified blackjack: player gets 2 cards, dealer gets 2 cards
    # Player can hit (get one more card) or stand
    player_cards = [random.randint(1, 11) for _ in range(2)]
    dealer_cards = [random.randint(1, 11) for _ in range(2)]
    
    if action == 'hit':
        player_cards.append(random.randint(1, 11))
    
    player_total = sum(player_cards)
    dealer_total = sum(dealer_cards)
    
    # Dealer hits if total < 17
    while dealer_total < 17:
        dealer_cards.append(random.randint(1, 11))
        dealer_total = sum(dealer_cards)
    
    # Determine winner
    won = False
    if player_total > 21:
        won = False  # Player bust
    elif dealer_total > 21:
        won = True  # Dealer bust
    elif player_total > dealer_total:
        won = True  # Player wins
    elif player_total == dealer_total:
        won = False  # Push (tie)
    else:
        won = False  # Dealer wins
    
    # 2x multiplier if win (house edge ~8% with simplified rules)
    if won:
        winnings = bet_amount * 2
        balances[currency] += winnings
        net_gain = winnings - bet_amount
    else:
        winnings = 0
        net_gain = -bet_amount
    
    persist_state_resources(c, user_id, balances)
    
    # Log gambling activity
    c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                 VALUES (?, 'blackjack', ?, ?, ?, ?, ?)''',
              (user_id, bet_amount, currency, json.dumps({'player_cards': player_cards, 'dealer_cards': dealer_cards, 'player_total': player_total, 'dealer_total': dealer_total, 'action': action, 'won': won}), winnings, net_gain))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'player_cards': player_cards,
        'dealer_cards': dealer_cards,
        'player_total': player_total,
        'dealer_total': dealer_total,
        'action': action,
        'won': won,
        'bet_amount': bet_amount,
        'winnings': winnings,
        'net_gain': net_gain,
        'balances': {k: balances.get(k, 0) for k in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené']}
    })

# Shop/Microtransactions API endpoints
@app.route('/api/shop')
def api_shop():
    """Get shop items list"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get user's gems
    c.execute('SELECT gems FROM premium_currency WHERE user_id = ?', (user_id,))
    premium_row = c.fetchone()
    gems = premium_row['gems'] if premium_row else 0
    
    # Serialize shop items
    shop_items = []
    for item_id, item_def in SHOP_ITEMS.items():
        shop_items.append({
            'id': item_id,
            'name': item_def.get('name'),
            'description': item_def.get('description'),
            'icon': item_def.get('icon', '💎'),
            'category': item_def.get('category'),
            'cost_gems': item_def.get('cost_gems', 0),
            'cost_real_money': item_def.get('cost_real_money', 0),
            'popular': item_def.get('popular', False)
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'gems': gems,
        'items': shop_items
    })

@app.route('/api/shop/purchase', methods=['POST'])
def api_shop_purchase():
    """Purchase item from shop"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    item_id = data.get('item_id')
    
    if not item_id or item_id not in SHOP_ITEMS:
        return jsonify({'success': False, 'error': 'Neplatný item'}), 400
    
    item_def = SHOP_ITEMS[item_id]
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get user's gems and game state
    c.execute('SELECT gems FROM premium_currency WHERE user_id = ?', (user_id,))
    premium_row = c.fetchone()
    if not premium_row:
        c.execute('INSERT INTO premium_currency (user_id, gems) VALUES (?, 0)', (user_id,))
        gems = 0
    else:
        gems = premium_row['gems'] or 0
    
    c.execute('SELECT * FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Game state not found'}), 404
    
    resources = extract_player_resources(state)
    
    # Check if purchase requires real money (for future payment gateway integration)
    cost_real_money = item_def.get('cost_real_money', 0)
    if cost_real_money > 0:
        # In production, verify payment with payment gateway here
        # For now, we'll just add gems directly (testing mode)
        gems_to_add = item_def.get('rewards', {}).get('gems', 0)
        if gems_to_add > 0:
            new_gems = gems + gems_to_add
            c.execute('''UPDATE premium_currency 
                         SET gems = ?, total_earned = total_earned + ?, last_update = CURRENT_TIMESTAMP
                         WHERE user_id = ?''', (new_gems, gems_to_add, user_id))
            c.execute('''INSERT INTO microtransactions 
                         (user_id, purchase_type, item_id, item_name, cost_real_money, rewards, status)
                         VALUES (?, 'gems_purchase', ?, ?, ?, ?, 'completed')''',
                     (user_id, item_id, item_def.get('name'), cost_real_money, json.dumps(item_def.get('rewards', {}))))
            conn.commit()
            conn.close()
            return jsonify({
                'success': True,
                'message': f'Získal jsi {gems_to_add} Drahokamů!',
                'gems': new_gems
            })
    
    # Check gems cost
    cost_gems = item_def.get('cost_gems', 0)
    if cost_gems > 0 and gems < cost_gems:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Drahokamů. Potřebuješ {cost_gems}, máš {gems}'}), 400
    
    # Apply rewards
    rewards = item_def.get('rewards', {})
    reward_summary = {}
    
    # Apply resource rewards
    for resource in ['gooncoins', 'astma', 'poharky', 'mrkev', 'uzené'] + SECONDARY_RESOURCES:
        if resource in rewards:
            amount = rewards[resource]
            resources[resource] = resources.get(resource, 0) + amount
            reward_summary[resource] = amount
    
    # Apply boost rewards
    if 'boost' in rewards:
        boost_def = rewards['boost']
        boost_type = boost_def.get('type')
        multiplier = boost_def.get('multiplier', 1.0)
        duration = boost_def.get('duration', 0)
        
        expires_at = None
        if duration > 0:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()
        
        c.execute('''INSERT INTO active_boosts (user_id, boost_type, multiplier, expires_at)
                     VALUES (?, ?, ?, ?)''', (user_id, boost_type, multiplier, expires_at))
        reward_summary['boost'] = {
            'type': boost_type,
            'multiplier': multiplier,
            'duration': duration
        }
    
    # Apply case keys (stored in game state or separate table - for now, we'll add a simple counter)
    if 'case_keys' in rewards:
        # In a full implementation, you'd store this in a separate table
        # For now, we'll just add it to rewards summary
        reward_summary['case_keys'] = rewards['case_keys']
    
    # Apply rare material rewards
    if 'rare_material_random' in rewards:
        material_keys = list(RARE_MATERIAL_DEFS.keys())
        if material_keys:
            random_material = random.choice(material_keys)
            rare_row = ensure_rare_materials(c, user_id)
            try:
                current_value = rare_row[random_material] if rare_row[random_material] is not None else 0
            except (KeyError, IndexError):
                current_value = 0
            c.execute(f'UPDATE rare_materials SET {random_material} = ? WHERE user_id = ?',
                     (current_value + 1, user_id))
            reward_summary['rare_material'] = random_material
    
    # Apply equipment rewards
    if 'equipment_random' in rewards:
        eq_filter = rewards['equipment_random']
        min_rarity = eq_filter.get('min_rarity', 'common')
        rarity_order = ['common', 'rare', 'epic', 'legendary', 'unique']
        min_rarity_idx = rarity_order.index(min_rarity) if min_rarity in rarity_order else 0
        
        eligible_items = []
        all_items = get_all_item_definitions()
        for eq_id, eq_def in all_items.items():
            eq_rarity = eq_def.get('rarity', 'common')
            if eq_rarity in rarity_order:
                eq_rarity_idx = rarity_order.index(eq_rarity)
                if eq_rarity_idx >= min_rarity_idx:
                    eligible_items.append(eq_id)
        
        if eligible_items:
            random_eq = random.choice(eligible_items)
            eq_def = get_item_definition(random_eq)
            slot = eq_def.get('slot', 'special')
            c.execute('''INSERT INTO equipment (user_id, equipment_slot, equipment_id, equipped, acquired_via, acquisition_note)
                         VALUES (?, ?, ?, 0, 'shop', ?)''',
                     (user_id, slot, random_eq, f'Zakoupeno v shopu: {item_def.get("name")}'))
            reward_summary['equipment'] = random_eq
    
    # Deduct gems
    if cost_gems > 0:
        new_gems = gems - cost_gems
        c.execute('''UPDATE premium_currency 
                     SET gems = ?, total_spent = total_spent + ?, last_update = CURRENT_TIMESTAMP
                     WHERE user_id = ?''', (new_gems, cost_gems, user_id))
    
    # Persist resources
    persist_resources(c, user_id, resources)
    
    # Log purchase
    c.execute('''INSERT INTO microtransactions 
                 (user_id, purchase_type, item_id, item_name, cost_gems, rewards, status)
                 VALUES (?, 'shop_purchase', ?, ?, ?, ?, 'completed')''',
             (user_id, item_id, item_def.get('name'), cost_gems, json.dumps(reward_summary)))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Zakoupil jsi: {item_def.get("name")}',
        'gems': new_gems if cost_gems > 0 else gems,
        'rewards': reward_summary
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
    now = datetime.now(timezone.utc)
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
    
    now = datetime.now(timezone.utc)
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
        cooldown_iso = (datetime.now(timezone.utc) + timedelta(seconds=TEMPLE_DEFEAT_COOLDOWN)).isoformat()
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
    
    req = quest['requirement']
    if 'total_clicks' in req and state['total_clicks'] < req['total_clicks']:
        conn.close()
        return jsonify({'success': False, 'error': 'Požadavky nejsou splněny'})
    if 'gooncoins' in req and state['gooncoins'] < req['gooncoins']:
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
    # Get current values for database update (keep existing values, don't add rewards for removed currencies)
    current_astma = state.get('astma', 0) if 'astma' in state.keys() else (state.get('wood', 0) if 'wood' in state.keys() else 0)
    current_poharky = state.get('poharky', 0) if 'poharky' in state.keys() else (state.get('water', 0) if 'water' in state.keys() else 0)
    current_mrkev = state.get('mrkev', 0) if 'mrkev' in state.keys() else (state.get('fire', 0) if 'fire' in state.keys() else 0)
    new_astma = current_astma
    new_poharky = current_poharky
    new_mrkev = current_mrkev
    current_uzené = state.get('uzené', 0) if 'uzené' in state.keys() else (state.get('earth', 0) if 'earth' in state.keys() else 0)
    new_uzené = current_uzené
    
    # Unlock new things
    unlocked_currencies = json.loads(story['unlocked_currencies']) if story and story['unlocked_currencies'] else ['gooncoins']
    unlocked_buildings = json.loads(story['unlocked_buildings']) if story and story['unlocked_buildings'] else []
    
    if 'unlocks' in quest:
        for unlock in quest['unlocks']:
            if unlock not in unlocked_currencies and unlock not in unlocked_buildings:
                # Only unlock buildings now, not currencies (astma, poharky, mrkev, uzené removed)
                if unlock not in ['astma', 'poharky', 'mrkev', 'uzené']:
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
    all_items = get_all_item_definitions()
    for eq_id in all_items.keys():
        c.execute('SELECT COUNT(*) as count FROM equipment WHERE equipment_id = ?', (eq_id,))
        result = c.fetchone()
        equipment_counts[eq_id] = result['count'] if result else 0
    conn.close()
    
    return jsonify({
        'chapters': STORY_CHAPTERS,
        'lore_entries': LORE_ENTRIES,
        'equipment': EQUIPMENT_DEFS,
        'buildings': BUILDINGS_DEFS,
        'gems': GEM_DEFINITIONS,
        'equipment_counts': equipment_counts
    })

# Friends system API endpoints
@app.route('/api/friends', methods=['GET'])
def get_friends():
    """Get all friends, pending requests, and sent requests"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Get accepted friends
    c.execute('''SELECT f.id, f.user1_id, f.user2_id, f.status, f.created_at,
                  CASE 
                      WHEN f.user1_id = ? THEN u2.id
                      ELSE u1.id
                  END as friend_id,
                  CASE 
                      WHEN f.user1_id = ? THEN u2.username
                      ELSE u1.username
                  END as friend_username
                  FROM friendships f
                  JOIN users u1 ON f.user1_id = u1.id
                  JOIN users u2 ON f.user2_id = u2.id
                  WHERE (f.user1_id = ? OR f.user2_id = ?) AND f.status = 'accepted'
                  ORDER BY f.updated_at DESC''', (user_id, user_id, user_id, user_id))
    friends = []
    for row in c.fetchall():
        friends.append({
            'id': row['id'],
            'friend_id': row['friend_id'],
            'username': row['friend_username'],
            'created_at': row['created_at']
        })
    
    # Get pending incoming requests (requests sent TO me)
    c.execute('''SELECT f.id, f.user1_id, f.user2_id, f.status, f.created_at,
                  CASE 
                      WHEN f.user1_id = ? THEN u1.id
                      ELSE u2.id
                  END as requester_id,
                  CASE 
                      WHEN f.user1_id = ? THEN u1.username
                      ELSE u2.username
                  END as requester_username
                  FROM friendships f
                  JOIN users u1 ON f.user1_id = u1.id
                  JOIN users u2 ON f.user2_id = u2.id
                  WHERE (f.user1_id = ? OR f.user2_id = ?) 
                  AND f.status = 'pending' 
                  AND f.requested_by != ?
                  ORDER BY f.created_at DESC''', (user_id, user_id, user_id, user_id, user_id))
    pending_incoming = []
    for row in c.fetchall():
        pending_incoming.append({
            'id': row['id'],
            'requester_id': row['requester_id'],
            'username': row['requester_username'],
            'created_at': row['created_at']
        })
    
    # Get pending outgoing requests (requests sent BY me)
    c.execute('''SELECT f.id, f.user1_id, f.user2_id, f.status, f.created_at,
                  CASE 
                      WHEN f.user1_id = ? THEN u2.id
                      ELSE u1.id
                  END as requested_id,
                  CASE 
                      WHEN f.user1_id = ? THEN u2.username
                      ELSE u1.username
                  END as requested_username
                  FROM friendships f
                  JOIN users u1 ON f.user1_id = u1.id
                  JOIN users u2 ON f.user2_id = u2.id
                  WHERE (f.user1_id = ? OR f.user2_id = ?) 
                  AND f.status = 'pending' 
                  AND f.requested_by = ?
                  ORDER BY f.created_at DESC''', (user_id, user_id, user_id, user_id, user_id))
    pending_outgoing = []
    for row in c.fetchall():
        pending_outgoing.append({
            'id': row['id'],
            'requested_id': row['requested_id'],
            'username': row['requested_username'],
            'created_at': row['created_at']
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'friends': friends,
        'pending_incoming': pending_incoming,
        'pending_outgoing': pending_outgoing
    })

@app.route('/api/friends/search', methods=['GET'])
def search_users():
    """Search for users to add as friends"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'success': True, 'users': []})
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Search users (exclude self and already friends/pending)
    c.execute('''SELECT u.id, u.username, u.created_at
                  FROM users u
                  WHERE u.id != ? 
                  AND u.username LIKE ?
                  AND u.id NOT IN (
                      SELECT CASE 
                          WHEN user1_id = ? THEN user2_id
                          ELSE user1_id
                      END
                      FROM friendships
                      WHERE user1_id = ? OR user2_id = ?
                  )
                  ORDER BY u.username
                  LIMIT 20''', (user_id, f'%{query}%', user_id, user_id, user_id))
    
    users = []
    for row in c.fetchall():
        users.append({
            'id': row['id'],
            'username': row['username'],
            'created_at': row['created_at']
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'users': users
    })

@app.route('/api/friends/request', methods=['POST'])
def send_friend_request():
    """Send a friend request to another user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    friend_id = data.get('friend_id')
    
    if not friend_id:
        return jsonify({'success': False, 'error': 'Chybí ID uživatele'}), 400
    
    user_id = session['user_id']
    
    if user_id == friend_id:
        return jsonify({'success': False, 'error': 'Nemůžete si přidat sami sebe'}), 400
    
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Check if user exists
    c.execute('SELECT id FROM users WHERE id = ?', (friend_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Uživatel nenalezen'}), 404
    
    # Check if friendship already exists
    c.execute('''SELECT id, status FROM friendships 
                 WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)''',
              (user_id, friend_id, friend_id, user_id))
    existing = c.fetchone()
    
    if existing:
        if existing['status'] == 'accepted':
            conn.close()
            return jsonify({'success': False, 'error': 'Už jste přátelé'}), 400
        elif existing['status'] == 'pending':
            conn.close()
            return jsonify({'success': False, 'error': 'Žádost již existuje'}), 400
    
    # Create friendship (always store with smaller ID first for consistency)
    user1_id, user2_id = (user_id, friend_id) if user_id < friend_id else (friend_id, user_id)
    now = datetime.now(timezone.utc).isoformat()
    
    c.execute('''INSERT INTO friendships (user1_id, user2_id, status, requested_by, created_at, updated_at)
                  VALUES (?, ?, 'pending', ?, ?, ?)''',
              (user1_id, user2_id, user_id, now, now))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Žádost o přátelství odeslána'
    })

@app.route('/api/friends/accept', methods=['POST'])
def accept_friend_request():
    """Accept a friend request"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    request_id = data.get('request_id')
    
    if not request_id:
        return jsonify({'success': False, 'error': 'Chybí ID žádosti'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Check if request exists and is pending
    c.execute('''SELECT id, user1_id, user2_id, status FROM friendships 
                 WHERE id = ? AND status = 'pending''', (request_id,))
    friendship = c.fetchone()
    
    if not friendship:
        conn.close()
        return jsonify({'success': False, 'error': 'Žádost nenalezena'}), 404
    
    # Verify user is the recipient
    if friendship['user1_id'] != user_id and friendship['user2_id'] != user_id:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáte oprávnění'}), 403
    
    # Update status to accepted
    now = datetime.now(timezone.utc).isoformat()
    c.execute('''UPDATE friendships 
                  SET status = 'accepted', updated_at = ?
                  WHERE id = ?''', (now, request_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Žádost přijata'
    })

@app.route('/api/friends/reject', methods=['POST'])
def reject_friend_request():
    """Reject or cancel a friend request"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    request_id = data.get('request_id')
    
    if not request_id:
        return jsonify({'success': False, 'error': 'Chybí ID žádosti'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Check if request exists
    c.execute('''SELECT id, user1_id, user2_id, status, requested_by FROM friendships 
                 WHERE id = ?''', (request_id,))
    friendship = c.fetchone()
    
    if not friendship:
        conn.close()
        return jsonify({'success': False, 'error': 'Žádost nenalezena'}), 404
    
    # Verify user is involved in the friendship
    if friendship['user1_id'] != user_id and friendship['user2_id'] != user_id:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáte oprávnění'}), 403
    
    # Delete the friendship
    c.execute('DELETE FROM friendships WHERE id = ?', (request_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Žádost zamítnuta'
    })

@app.route('/api/friends/remove', methods=['POST'])
def remove_friend():
    """Remove an accepted friend"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    friend_id = data.get('friend_id')
    
    if not friend_id:
        return jsonify({'success': False, 'error': 'Chybí ID přítele'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    c.row_factory = sqlite3.Row
    
    # Find and delete friendship
    c.execute('''SELECT id FROM friendships 
                 WHERE ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))
                 AND status = 'accepted' ''',
              (user_id, friend_id, friend_id, user_id))
    friendship = c.fetchone()
    
    if not friendship:
        conn.close()
        return jsonify({'success': False, 'error': 'Přátelství nenalezeno'}), 404
    
    c.execute('DELETE FROM friendships WHERE id = ?', (friendship['id'],))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Přítel odstraněn'
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

# ========== QUEST SYSTEM (TAVERN/HOSPODA) ==========

def generate_quest(user_level, difficulty=None):
    """Generate a random quest based on user level"""
    if difficulty is None:
        difficulty = min(5, max(1, (user_level // 5) + 1))
    
    diff_def = QUEST_DIFFICULTIES.get(difficulty, QUEST_DIFFICULTIES[1])
    template = random.choice(QUEST_TEMPLATES)
    
    # Base rewards scale with level
    base_exp = user_level * 10 * diff_def['exp_mult']
    base_gooncoins = user_level * 5 * diff_def['gold_mult']
    
    # RNG variation ±20%
    exp_variation = random.uniform(0.8, 1.2)
    gooncoins_variation = random.uniform(0.8, 1.2)
    
    reward_exp = int(base_exp * exp_variation)
    reward_gooncoins = int(base_gooncoins * gooncoins_variation)
    duration = int(diff_def['duration_base'] * (1 + user_level * 0.1))
    
    # Chance for item reward (higher difficulty = higher chance)
    reward_item_id = None
    if random.random() < (difficulty * 0.15):
        # Random item from equipment pool
        item_ids = list(EQUIPMENT_DEFS.keys())
        if item_ids:
            reward_item_id = random.choice(item_ids)
    
    quest_id = f"quest_{template['type']}_{difficulty}_{int(datetime.now(timezone.utc).timestamp())}"
    
    return {
        'quest_id': quest_id,
        'name': template['name'],
        'type': template['type'],
        'difficulty': difficulty,
        'difficulty_name': diff_def['name'],
        'duration_seconds': duration,
        'reward_exp': reward_exp,
        'reward_gold': reward_gooncoins,  # Stored as reward_gold in DB for compatibility
        'reward_item_id': reward_item_id
    }

def ensure_available_quests(cursor, user_id, force_regenerate=False):
    """Ensure user has 3 available quests. Questy mají minimální životnost 1 hodinu."""
    # Minimální životnost questu v sekundách (1 hodina)
    MIN_QUEST_LIFETIME = 3600
    
    now = datetime.now(timezone.utc)
    min_lifetime_ago = now - timedelta(seconds=MIN_QUEST_LIFETIME)
    min_lifetime_ago_str = min_lifetime_ago.isoformat()
    day_ago = now - timedelta(hours=24)
    day_ago_str = day_ago.isoformat()
    
    # Odstranit staré questy (starší než 24 hodin)
    cursor.execute('''DELETE FROM available_quests 
                     WHERE user_id = ? AND generated_at < ?''', 
                  (user_id, day_ago_str))
    
    # Vždy počítat všechny dostupné questy (ne jen staré)
    cursor.execute('SELECT COUNT(*) as count FROM available_quests WHERE user_id = ?', (user_id,))
    count = cursor.fetchone()['count']
    
    # Pokud je méně než 3 questy, vygenerovat chybějící
    if count < 3:
        # Get user level
        cursor.execute('SELECT level FROM character_stats WHERE user_id = ?', (user_id,))
        char = cursor.fetchone()
        user_level = char['level'] if char else 1
        
        # Generate missing quests
        for _ in range(3 - count):
            quest = generate_quest(user_level)
            cursor.execute('''INSERT INTO available_quests 
                            (user_id, quest_id, duration_seconds, reward_exp, reward_gold, reward_item_id, difficulty, generated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                         (user_id, quest['quest_id'], quest['duration_seconds'], quest['reward_exp'], 
                          quest['reward_gold'], quest['reward_item_id'], quest['difficulty'], 
                          now.isoformat()))

@app.route('/api/quests/available', methods=['GET'])
def get_available_quests():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Pouze zkontrolovat a doplnit questy, ale ne regenerovat existující
    ensure_available_quests(c, user_id, force_regenerate=False)
    conn.commit()
    
    c.execute('''SELECT * FROM available_quests WHERE user_id = ? ORDER BY generated_at DESC LIMIT 3''', (user_id,))
    quests = []
    for row in c.fetchall():
        row_dict = dict(row)
        # Získat typ z quest_id (formát: quest_{type}_{difficulty}_{timestamp})
        quest_type = 'combat'
        quest_name = 'Quest'
        if row['quest_id']:
            parts = row['quest_id'].split('_')
            if len(parts) >= 2:
                quest_type = parts[1]
                # Najít jméno z template podle typu
                for template in QUEST_TEMPLATES:
                    if template['type'] == quest_type:
                        quest_name = template['name']
                        break
        
        quests.append({
            'id': row['id'],
            'quest_id': row['quest_id'],
            'name': row_dict.get('name') or quest_name,
            'type': row_dict.get('type') or quest_type,
            'difficulty_name': row_dict.get('difficulty_name') or QUEST_DIFFICULTIES.get(row['difficulty'], {}).get('name', 'Easy'),
            'duration_seconds': row['duration_seconds'],
            'reward_exp': row['reward_exp'],
            'reward_gold': row['reward_gold'],
            'reward_item_id': row['reward_item_id'],
            'difficulty': row['difficulty']
        })
    
    # Get active quest
    c.execute('''SELECT * FROM quests WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1''', (user_id,))
    active_quest = None
    row = c.fetchone()
    if row:
        started = datetime.fromisoformat(row['started_at'])
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration = timedelta(seconds=row['duration_seconds'])
        completed_at = started + duration
        now = datetime.now(timezone.utc)
        remaining = max(0, (completed_at - now).total_seconds())
        
        row_dict = dict(row)
        # Získat typ z quest_id (formát: quest_{type}_{difficulty}_{timestamp})
        quest_type = 'combat'
        quest_name = 'Quest'
        if row['quest_id']:
            parts = row['quest_id'].split('_')
            if len(parts) >= 2:
                quest_type = parts[1]
                # Najít jméno z template podle typu
                for template in QUEST_TEMPLATES:
                    if template['type'] == quest_type:
                        quest_name = template['name']
                        break
        
        active_quest = {
            'id': row['id'],
            'quest_id': row['quest_id'],
            'name': row_dict.get('name') or quest_name,
            'type': row_dict.get('type') or quest_type,
            'difficulty_name': row_dict.get('difficulty_name') or QUEST_DIFFICULTIES.get(row['difficulty'], {}).get('name', 'Easy'),
            'duration_seconds': row['duration_seconds'],
            'reward_exp': row['reward_exp'],
            'reward_gold': row['reward_gold'],
            'reward_item_id': row['reward_item_id'],
            'difficulty': row['difficulty'],
            'started_at': row['started_at'],
            'remaining_seconds': int(remaining),
            'completed': remaining <= 0
        }
    
    conn.close()
    return jsonify({'success': True, 'available_quests': quests, 'active_quest': active_quest})

@app.route('/api/quests/start', methods=['POST'])
def start_quest():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    quest_pool_id = data.get('quest_pool_id')
    
    if not quest_pool_id:
        return jsonify({'success': False, 'error': 'Missing quest_pool_id'}), 400
    
    # Convert to int if it's a string
    try:
        quest_pool_id = int(quest_pool_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid quest_pool_id'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if already has active quest
    c.execute('SELECT id FROM quests WHERE user_id = ? AND status = "active"', (user_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Už máš aktivní quest'}), 400
    
    # Get quest from pool - try both id and quest_id in case of confusion
    # Použít transakci pro zajištění konzistence
    c.execute('BEGIN TRANSACTION')
    try:
        c.execute('SELECT * FROM available_quests WHERE id = ? AND user_id = ?', (quest_pool_id, user_id))
        pool_quest = c.fetchone()
        if not pool_quest:
            # Try to find by quest_id as fallback
            c.execute('SELECT * FROM available_quests WHERE quest_id = ? AND user_id = ?', (str(quest_pool_id), user_id))
            pool_quest = c.fetchone()
            if not pool_quest:
                # Quest not found - try to regenerate quests and check again
                c.execute('ROLLBACK')
                ensure_available_quests(c, user_id, force_regenerate=False)
                conn.commit()
                # Try one more time
                c.execute('SELECT * FROM available_quests WHERE id = ? AND user_id = ?', (quest_pool_id, user_id))
                pool_quest = c.fetchone()
                if not pool_quest:
                    c.execute('SELECT * FROM available_quests WHERE quest_id = ? AND user_id = ?', (str(quest_pool_id), user_id))
                    pool_quest = c.fetchone()
                    if not pool_quest:
                        conn.close()
                        return jsonify({'success': False, 'error': 'Quest nenalezen'}), 404
                # Restart transaction if we found it
                c.execute('BEGIN TRANSACTION')
        
        # Get mount speed reduction
        c.execute('SELECT speed_reduction FROM mounts WHERE user_id = ?', (user_id,))
        mount = c.fetchone()
        speed_reduction = mount['speed_reduction'] if mount else 0
        
        # Calculate actual duration with mount
        base_duration = pool_quest['duration_seconds']
        actual_duration = int(base_duration * (1 - speed_reduction / 100))
        
        # Create active quest
        started_at = datetime.now(timezone.utc).isoformat()
        c.execute('''INSERT INTO quests 
                    (user_id, quest_id, duration_seconds, reward_exp, reward_gold, reward_item_id, difficulty, started_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')''',
                 (user_id, pool_quest['quest_id'], actual_duration, pool_quest['reward_exp'], 
                  pool_quest['reward_gold'], pool_quest['reward_item_id'], pool_quest['difficulty'], started_at))
        
        # Remove from pool
        c.execute('DELETE FROM available_quests WHERE id = ?', (quest_pool_id,))
        
        # Regenerate quests to keep 3 available (force regenerate to fill the gap)
        ensure_available_quests(c, user_id, force_regenerate=False)
        
        c.execute('COMMIT')
        conn.commit()
    except Exception as e:
        c.execute('ROLLBACK')
        conn.close()
        return jsonify({'success': False, 'error': f'Chyba při startu questu: {str(e)}'}), 500
    
    conn.close()
    return jsonify({'success': True})

@app.route('/api/quests/complete', methods=['POST'])
def complete_active_quest():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get active quest
    c.execute('SELECT * FROM quests WHERE user_id = ? AND status = "active" ORDER BY started_at DESC LIMIT 1', (user_id,))
    quest = c.fetchone()
    if not quest:
        conn.close()
        return jsonify({'success': False, 'error': 'Žádný aktivní quest'}), 400
    
    started = datetime.fromisoformat(quest['started_at'])
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    duration = timedelta(seconds=quest['duration_seconds'])
    completed_at_time = started + duration
    now = datetime.now(timezone.utc)
    
    if now < completed_at_time:
        remaining = (completed_at_time - now).total_seconds()
        conn.close()
        return jsonify({'success': False, 'error': f'Quest ještě není hotový. Zbývá {int(remaining)} sekund'}), 400
    
    # Get guild bonuses
    c.execute('''SELECT g.exp_bonus, g.gold_bonus FROM guilds g
                 JOIN guild_members gm ON g.id = gm.guild_id
                 WHERE gm.user_id = ?''', (user_id,))
    guild = c.fetchone()
    exp_bonus = 1.0 + (guild['exp_bonus'] if guild else 0)
    gooncoins_bonus = 1.0 + (guild['gold_bonus'] if guild else 0)  # gold_bonus in DB is actually gooncoins_bonus
    
    # Calculate rewards
    reward_exp = int(quest['reward_exp'] * exp_bonus)
    reward_gooncoins = int(quest['reward_gold'] * gooncoins_bonus)  # reward_gold from DB is actually gooncoins
    
    # Get character stats
    char_stats = ensure_character_stats(c, user_id)
    current_exp = char_stats['experience']
    new_exp = current_exp + reward_exp
    
    # Level up check
    level = char_stats['level']
    exp_needed = 100 * (level ** 1.5)
    new_level = level
    available_points = char_stats['available_points']
    
    while new_exp >= exp_needed:
        new_exp -= exp_needed
        new_level += 1
        available_points += 5
        exp_needed = 100 * (new_level ** 1.5)
    
    # Update character stats
    c.execute('''UPDATE character_stats 
                 SET experience = ?, level = ?, available_points = ?
                 WHERE user_id = ?''',
             (new_exp, new_level, available_points, user_id))
    
    # Update gooncoins (not gold)
    try:
        c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
        state = c.fetchone()
        if state:
            current_gooncoins = state['gooncoins'] or 0
            new_gooncoins = current_gooncoins + reward_gooncoins
            c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    except sqlite3.OperationalError as e:
        # Column might not exist, but we'll try to continue
        print(f"Warning: Could not update gooncoins: {e}")
    
    # Give item if any
    reward_item = None
    if quest['reward_item_id']:
        item_id = quest['reward_item_id']
        item_def = get_item_definition(item_id)
        if item_def:
            # Add to equipment table
            slot = item_def.get('slot', 'misc')
            try:
                c.execute('''INSERT INTO equipment (user_id, equipment_slot, equipment_id, equipped, acquired_via, acquisition_note)
                            VALUES (?, ?, ?, 0, 'quest_reward', ?)''',
                         (user_id, slot, item_id, f'Quest reward: {quest.get("name", "Quest")}'))
                reward_item = {
                    'id': item_id,
                    'name': item_def.get('name', item_id),
                    'slot': slot
                }
            except sqlite3.OperationalError as e:
                print(f"Warning: Could not insert equipment: {e}")
                # Continue without item reward
    
    # Regenerate available quests
    ensure_available_quests(c, user_id, force_regenerate=False)
    
    # Mark quest as completed
    c.execute('''UPDATE quests SET status = 'completed', completed_at = ? WHERE id = ?''',
             (datetime.now(timezone.utc).isoformat(), quest['id']))
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'rewards': {
            'exp': reward_exp,
            'gooncoins': reward_gooncoins,
            'item': reward_item
        },
        'new_level': new_level,
        'new_exp': new_exp,
        'available_points': available_points
    })

# ========== MOUNT SYSTEM ==========

@app.route('/api/mount/status', methods=['GET'])
def get_mount_status():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT mount_type, speed_reduction FROM mounts WHERE user_id = ?', (user_id,))
    mount = c.fetchone()
    
    if not mount:
        mount_type = 'none'
        speed_reduction = 0
    else:
        mount_type = mount['mount_type']
        speed_reduction = mount['speed_reduction']
    
    conn.close()
    return jsonify({
        'success': True,
        'mount_type': mount_type,
        'speed_reduction': speed_reduction,
        'available_mounts': MOUNT_TYPES
    })

@app.route('/api/mount/buy', methods=['POST'])
def buy_mount():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    mount_type = data.get('mount_type')
    
    if not mount_type or mount_type not in MOUNT_TYPES:
        return jsonify({'success': False, 'error': 'Neplatný typ koně'}), 400
    
    mount_def = MOUNT_TYPES[mount_type]
    cost = mount_def['cost']
    
    if mount_type == 'none':
        return jsonify({'success': False, 'error': 'Nemůžeš koupit "bez koně"'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    current_gooncoins = state['gooncoins'] if state and state['gooncoins'] else 0
    
    if current_gooncoins < cost:
        conn.close()
        return jsonify({'success': False, 'error': 'Nemáš dost gooncoinů'}), 400
    
    # Buy mount
    new_gooncoins = current_gooncoins - cost
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    c.execute('''INSERT OR REPLACE INTO mounts (user_id, mount_type, speed_reduction)
                 VALUES (?, ?, ?)''',
             (user_id, mount_type, mount_def['speed_reduction']))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'new_gooncoins': new_gooncoins})

# ========== TAVERN ACTIVITIES ==========

@app.route('/api/tavern/beer', methods=['POST'])
def buy_tavern_beer():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    stat_type = data.get('stat_type')
    
    if stat_type not in ['strength', 'luck']:
        return jsonify({'success': False, 'error': 'Neplatný typ bonusu'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    beer_cost = 500
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < beer_cost:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {beer_cost}, máš {current_gooncoins}'}), 400
    
    # Deduct gooncoins
    new_gooncoins = current_gooncoins - beer_cost
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    
    # Add temporary boost (30 minutes)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    boost_type = f'beer_{stat_type}'
    c.execute('''INSERT OR REPLACE INTO active_boosts 
                 (user_id, boost_type, multiplier, expires_at)
                 VALUES (?, ?, 1.1, ?)''',
             (user_id, boost_type, expires_at))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'stat_type': stat_type,
        'new_gooncoins': new_gooncoins,
        'expires_at': expires_at
    })

@app.route('/api/tavern/cards', methods=['POST'])
def play_tavern_cards():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = data.get('bet_amount', 0)
    
    if bet_amount < 100 or bet_amount > 1000:
        return jsonify({'success': False, 'error': 'Sázka musí být mezi 100 a 1000 Gooncoinů'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {bet_amount}, máš {current_gooncoins}'}), 400
    
    # Simple card game: 50% chance to win 2x bet
    won = random.random() < 0.5
    
    if won:
        winnings = bet_amount * 2
        new_gooncoins = current_gooncoins - bet_amount + winnings
        net_gain = winnings - bet_amount
    else:
        new_gooncoins = current_gooncoins - bet_amount
        net_gain = -bet_amount
    
    # Update gooncoins
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    
    # Log gambling activity
    try:
        c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                     VALUES (?, 'tavern_cards', ?, 'gooncoins', ?, ?, ?)''',
                 (user_id, bet_amount, json.dumps({'won': won}), bet_amount * 2 if won else 0, net_gain))
    except sqlite3.OperationalError:
        # Table might not exist, skip logging
        pass
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'won': won,
        'winnings': bet_amount * 2 if won else 0,
        'net_gain': net_gain,
        'new_gooncoins': new_gooncoins
    })

@app.route('/api/tavern/darts', methods=['POST'])
def play_tavern_darts():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    dart_cost = 200
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < dart_cost:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {dart_cost}, máš {current_gooncoins}'}), 400
    
    # Deduct gooncoins
    new_gooncoins = current_gooncoins - dart_cost
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    
    # Calculate EXP reward (random between 50-200)
    exp_reward = random.randint(50, 200)
    
    # Get character stats
    char_stats = ensure_character_stats(c, user_id)
    current_exp = char_stats['experience']
    new_exp = current_exp + exp_reward
    
    # Level up check
    level = char_stats['level']
    exp_needed = 100 * (level ** 1.5)
    new_level = level
    available_points = char_stats['available_points']
    
    while new_exp >= exp_needed:
        new_exp -= exp_needed
        new_level += 1
        available_points += 5
        exp_needed = 100 * (new_level ** 1.5)
    
    # Update character stats
    c.execute('''UPDATE character_stats 
                 SET experience = ?, level = ?, available_points = ?
                 WHERE user_id = ?''',
             (new_exp, new_level, available_points, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'exp_reward': exp_reward,
        'new_gooncoins': new_gooncoins,
        'new_level': new_level,
        'new_exp': new_exp,
        'available_points': available_points
    })

# ========== INTERACTIVE GAMBLE GAMES ==========

# Active game sessions (in-memory for simplicity, could be moved to DB)
active_games = {}

@app.route('/api/tavern/dice', methods=['POST'])
def play_tavern_dice():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = data.get('bet_amount', 0)
    guess = data.get('guess', 7)
    
    if bet_amount < 50 or bet_amount > 500:
        return jsonify({'success': False, 'error': 'Sázka musí být mezi 50 a 500 Gooncoinů'}), 400
    
    if guess < 2 or guess > 12:
        return jsonify({'success': False, 'error': 'Tip musí být mezi 2 a 12'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {bet_amount}, máš {current_gooncoins}'}), 400
    
    # Roll dice
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    dice_sum = dice1 + dice2
    
    won = (dice_sum == guess)
    
    if won:
        # Payout based on probability (1/11 chance, so ~10x payout)
        winnings = bet_amount * 10
        new_gooncoins = current_gooncoins - bet_amount + winnings
        net_gain = winnings - bet_amount
    else:
        new_gooncoins = current_gooncoins - bet_amount
        net_gain = -bet_amount
        winnings = 0
    
    # Update gooncoins
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    
    # Log gambling activity
    try:
        c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                     VALUES (?, 'tavern_dice', ?, 'gooncoins', ?, ?, ?)''',
                 (user_id, bet_amount, json.dumps({'guess': guess, 'dice1': dice1, 'dice2': dice2, 'sum': dice_sum, 'won': won}), winnings, net_gain))
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()
    
    refresh_economy_after_change()
    
    return jsonify({
        'success': True,
        'dice1': dice1,
        'dice2': dice2,
        'sum': dice_sum,
        'guess': guess,
        'won': won,
        'winnings': winnings,
        'net_gain': net_gain,
        'new_gooncoins': new_gooncoins
    })

@app.route('/api/tavern/blackjack/start', methods=['POST'])
def start_tavern_blackjack():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = data.get('bet_amount', 0)
    
    if bet_amount < 100 or bet_amount > 1000:
        return jsonify({'success': False, 'error': 'Sázka musí být mezi 100 a 1000 Gooncoinů'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {bet_amount}, máš {current_gooncoins}'}), 400
    
    # Deduct bet
    new_gooncoins = current_gooncoins - bet_amount
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    conn.commit()
    
    # Create game session
    game_id = f"bj_{user_id}_{int(time.time())}"
    player_cards = [min(random.randint(1, 13), 10), min(random.randint(1, 13), 10)]
    dealer_cards = [min(random.randint(1, 13), 10), min(random.randint(1, 13), 10)]
    
    # Calculate totals (Ace = 1 or 11)
    player_total = sum(player_cards)
    if 1 in player_cards and player_total <= 11:
        player_total += 10
    
    dealer_total = dealer_cards[0]  # Only show first card
    
    active_games[game_id] = {
        'user_id': user_id,
        'bet_amount': bet_amount,
        'player_cards': player_cards,
        'dealer_cards': dealer_cards,
        'player_total': player_total,
        'game_over': False
    }
    
    conn.close()
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'player_cards': player_cards,
        'dealer_cards': dealer_cards,
        'player_total': player_total,
        'dealer_total': dealer_total,
        'game_over': False,
        'bet_amount': bet_amount,
        'new_gooncoins': new_gooncoins
    })

@app.route('/api/tavern/blackjack/hit', methods=['POST'])
def hit_tavern_blackjack():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    game_id = data.get('game_id')
    
    if not game_id or game_id not in active_games:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 400
    
    game = active_games[game_id]
    if game['user_id'] != session['user_id']:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 403
    
    if game['game_over']:
        return jsonify({'success': False, 'error': 'Hra už skončila'}), 400
    
    # Add card
    new_card = min(random.randint(1, 13), 10)
    game['player_cards'].append(new_card)
    game['player_total'] = sum(game['player_cards'])
    
    # Check for Ace
    if 1 in game['player_cards'] and game['player_total'] <= 11:
        game['player_total'] += 10
    
    # Check if bust
    if game['player_total'] > 21:
        game['game_over'] = True
        game['won'] = False
        game['winnings'] = 0
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'player_cards': game['player_cards'],
        'dealer_cards': game['dealer_cards'],
        'player_total': game['player_total'],
        'dealer_total': game['dealer_cards'][0] if not game['game_over'] else sum(game['dealer_cards']),
        'game_over': game['game_over'],
        'won': game.get('won', False),
        'winnings': game.get('winnings', 0),
        'bet_amount': game['bet_amount']
    })

@app.route('/api/tavern/blackjack/stand', methods=['POST'])
def stand_tavern_blackjack():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    game_id = data.get('game_id')
    
    if not game_id or game_id not in active_games:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 400
    
    game = active_games[game_id]
    if game['user_id'] != session['user_id']:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 403
    
    if game['game_over']:
        return jsonify({'success': False, 'error': 'Hra už skončila'}), 400
    
    # Dealer plays
    dealer_total = sum(game['dealer_cards'])
    while dealer_total < 17:
        new_card = min(random.randint(1, 13), 10)
        game['dealer_cards'].append(new_card)
        dealer_total = sum(game['dealer_cards'])
        if 1 in game['dealer_cards'] and dealer_total <= 11:
            dealer_total += 10
    
    game['dealer_total'] = dealer_total
    game['game_over'] = True
    
    # Determine winner
    player_total = game['player_total']
    if player_total > 21:
        won = False
    elif dealer_total > 21:
        won = True
    elif player_total > dealer_total:
        won = True
    else:
        won = False
    
    game['won'] = won
    
    # Calculate winnings
    if won:
        winnings = game['bet_amount'] * 2
        game['winnings'] = winnings
        
        # Add winnings
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (game['user_id'],))
        state = c.fetchone()
        if state:
            new_gooncoins = (state['gooncoins'] or 0) + winnings
            c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, game['user_id']))
            conn.commit()
            refresh_economy_after_change()
        conn.close()
    else:
        game['winnings'] = 0
    
    # Log gambling activity
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                     VALUES (?, 'tavern_blackjack', ?, 'gooncoins', ?, ?, ?)''',
                 (game['user_id'], game['bet_amount'], 
                  json.dumps({'player_cards': game['player_cards'], 'dealer_cards': game['dealer_cards'], 
                             'player_total': player_total, 'dealer_total': dealer_total, 'won': won}),
                  game['winnings'], game['winnings'] - game['bet_amount']))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'player_cards': game['player_cards'],
        'dealer_cards': game['dealer_cards'],
        'player_total': player_total,
        'dealer_total': dealer_total,
        'game_over': True,
        'won': won,
        'winnings': game['winnings'],
        'bet_amount': game['bet_amount']
    })

@app.route('/api/tavern/shells/start', methods=['POST'])
def start_tavern_shells():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    bet_amount = data.get('bet_amount', 0)
    
    if bet_amount < 100 or bet_amount > 500:
        return jsonify({'success': False, 'error': 'Sázka musí být mezi 100 a 500 Gooncoinů'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user has enough gooncoins
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    if not state:
        conn.close()
        return jsonify({'success': False, 'error': 'Chyba při načítání stavu'}), 500
    
    current_gooncoins = state['gooncoins'] or 0
    
    if current_gooncoins < bet_amount:
        conn.close()
        return jsonify({'success': False, 'error': f'Nemáš dostatek Gooncoinů. Potřebuješ {bet_amount}, máš {current_gooncoins}'}), 400
    
    # Deduct bet
    new_gooncoins = current_gooncoins - bet_amount
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    conn.commit()
    
    # Create game session
    game_id = f"shells_{user_id}_{int(time.time())}"
    ball_position = random.randint(0, 2)
    
    active_games[game_id] = {
        'user_id': user_id,
        'bet_amount': bet_amount,
        'ball_position': ball_position
    }
    
    conn.close()
    
    return jsonify({
        'success': True,
        'game_id': game_id,
        'ball_position': ball_position,
        'bet_amount': bet_amount,
        'new_gooncoins': new_gooncoins
    })

@app.route('/api/tavern/shells/check', methods=['POST'])
def check_tavern_shells():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    game_id = data.get('game_id')
    selected_shell = data.get('selected_shell')
    
    if not game_id or game_id not in active_games:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 400
    
    game = active_games[game_id]
    if game['user_id'] != session['user_id']:
        return jsonify({'success': False, 'error': 'Neplatná hra'}), 403
    
    won = (selected_shell == game['ball_position'])
    
    if won:
        # 3x payout (1/3 chance)
        winnings = game['bet_amount'] * 3
        game['winnings'] = winnings
        
        # Add winnings
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (game['user_id'],))
        state = c.fetchone()
        if state:
            new_gooncoins = (state['gooncoins'] or 0) + winnings
            c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, game['user_id']))
            conn.commit()
            refresh_economy_after_change()
        conn.close()
    else:
        game['winnings'] = 0
    
    # Log gambling activity
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO gambling_log (user_id, game_type, bet_amount, currency, result, winnings, net_gain)
                     VALUES (?, 'tavern_shells', ?, 'gooncoins', ?, ?, ?)''',
                 (game['user_id'], game['bet_amount'],
                  json.dumps({'selected_shell': selected_shell, 'ball_position': game['ball_position'], 'won': won}),
                  game['winnings'], game['winnings'] - game['bet_amount']))
        conn.commit()
        conn.close()
    except sqlite3.OperationalError:
        pass
    
    # Clean up game
    del active_games[game_id]
    
    return jsonify({
        'success': True,
        'won': won,
        'ball_position': game['ball_position'],
        'winnings': game['winnings'],
        'bet_amount': game['bet_amount']
    })

# ========== ARENA IMPROVEMENTS ==========

def calculate_damage(attacker_stats, defender_stats, attacker_class='warrior'):
    """Calculate damage with class-based formulas"""
    class_def = CHARACTER_CLASSES.get(attacker_class, CHARACTER_CLASSES['warrior'])
    main_stat = attacker_stats.get(class_def['main_stat'], 10)
    
    # Base damage
    base_damage = main_stat * class_def['damage_coefficient']
    
    # RNG variation ±15%
    rng_variation = random.uniform(0.85, 1.15)
    damage = base_damage * rng_variation
    
    # Critical hit (based on luck)
    luck = attacker_stats.get('luck', 10)
    crit_chance = min(0.5, luck / 100)
    if random.random() < crit_chance:
        damage *= 2.0
    
    # Armor reduction
    defender_armor = defender_stats.get('armor', 0)
    damage = max(1, damage - defender_armor)
    
    return int(damage)

def calculate_initiative(player_stats, player_class='warrior'):
    """Calculate initiative for combat"""
    class_def = CHARACTER_CLASSES.get(player_class, CHARACTER_CLASSES['warrior'])
    initiative_stat = player_stats.get(class_def['initiative_stat'], 10)
    
    # Base initiative + RNG
    initiative = initiative_stat + random.randint(1, 20)
    return initiative

@app.route('/api/arena/fight', methods=['POST'])
def arena_fight_improved():
    """Improved arena fight with class-based damage and initiative"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    opponent_id = data.get('opponent_id')
    
    if not opponent_id:
        return jsonify({'success': False, 'error': 'Missing opponent_id'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get player stats
    char_stats = ensure_character_stats(c, user_id)
    try:
        player_class = char_stats['class'] if char_stats['class'] else 'warrior'
    except (KeyError, IndexError, TypeError):
        player_class = 'warrior'
    
    # Get opponent stats
    c.execute('SELECT * FROM character_stats WHERE user_id = ?', (opponent_id,))
    opponent_char = c.fetchone()
    if not opponent_char:
        conn.close()
        return jsonify({'success': False, 'error': 'Protivník nenalezen'}), 404
    
    try:
        opponent_class = opponent_char['class'] if opponent_char['class'] else 'warrior'
    except (KeyError, IndexError, TypeError):
        opponent_class = 'warrior'
    
    # Build stats dictionaries
    player_stats = {
        'strength': char_stats['strength'],
        'dexterity': char_stats['dexterity'],
        'intelligence': char_stats['intelligence'],
        'constitution': char_stats['constitution'],
        'luck': char_stats['luck'],
        'armor': 0  # TODO: calculate from equipment
    }
    
    opponent_stats = {
        'strength': opponent_char['strength'],
        'dexterity': opponent_char['dexterity'],
        'intelligence': opponent_char['intelligence'],
        'constitution': opponent_char['constitution'],
        'luck': opponent_char['luck'],
        'armor': 0  # TODO: calculate from equipment
    }
    
    # Calculate HP
    player_hp = player_stats['constitution'] * 10
    opponent_hp = opponent_stats['constitution'] * 10
    
    # Calculate initiative
    player_init = calculate_initiative(player_stats, player_class)
    opponent_init = calculate_initiative(opponent_stats, opponent_class)
    
    # Determine first attacker
    attacker_is_player = player_init >= opponent_init
    
    # Simulate combat
    rounds = []
    max_rounds = MAX_COMBAT_ROUNDS
    
    for round_num in range(1, max_rounds + 1):
        if player_hp <= 0 or opponent_hp <= 0:
            break
        
        if attacker_is_player:
            damage = calculate_damage(player_stats, opponent_stats, player_class)
            opponent_hp -= damage
            rounds.append({
                'round': round_num,
                'attacker': 'player',
                'damage': damage,
                'player_hp': max(0, player_hp),
                'opponent_hp': max(0, opponent_hp)
            })
        else:
            damage = calculate_damage(opponent_stats, player_stats, opponent_class)
            player_hp -= damage
            rounds.append({
                'round': round_num,
                'attacker': 'opponent',
                'damage': damage,
                'player_hp': max(0, player_hp),
                'opponent_hp': max(0, opponent_hp)
            })
        
        attacker_is_player = not attacker_is_player
    
    # Determine winner
    if player_hp > opponent_hp:
        winner = 'player'
        honor_gain = ARENA_HONOR_REWARDS['win']
    elif opponent_hp > player_hp:
        winner = 'opponent'
        honor_gain = ARENA_HONOR_REWARDS['loss']
    else:
        winner = 'draw'
        honor_gain = ARENA_HONOR_REWARDS['draw']
    
    # Update honor
    c.execute('SELECT honor FROM arena_honor WHERE user_id = ?', (user_id,))
    honor_row = c.fetchone()
    current_honor = honor_row['honor'] if honor_row else 0
    new_honor = current_honor + honor_gain
    c.execute('''INSERT OR REPLACE INTO arena_honor (user_id, honor) VALUES (?, ?)''',
             (user_id, new_honor))
    
    # Gooncoins reward
    gooncoins_reward = PVP_BASE_REWARD if winner == 'player' else PVP_BASE_REWARD // 2
    c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
    state = c.fetchone()
    current_gooncoins = state['gooncoins'] if state and state['gooncoins'] else 0
    new_gooncoins = current_gooncoins + gooncoins_reward
    c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'winner': winner,
        'rounds': rounds,
        'rewards': {
            'gooncoins': gooncoins_reward,
            'honor': honor_gain
        },
        'new_honor': new_honor,
        'new_gooncoins': new_gooncoins
    })

# ========== BLACKSMITH SYSTEM ==========

@app.route('/api/blacksmith/materials', methods=['GET'])
def get_blacksmith_materials():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT metal, souls FROM blacksmith_materials WHERE user_id = ?', (user_id,))
    materials = c.fetchone()
    
    if not materials:
        c.execute('INSERT INTO blacksmith_materials (user_id, metal, souls) VALUES (?, 0, 0)', (user_id,))
        conn.commit()
        metal = 0
        souls = 0
    else:
        metal = materials['metal']
        souls = materials['souls']
    
    conn.close()
    return jsonify({'success': True, 'metal': metal, 'souls': souls})

@app.route('/api/blacksmith/upgrade', methods=['POST'])
def blacksmith_upgrade():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    item_ids = data.get('item_ids', [])  # List of instance IDs
    
    if not item_ids:
        # Backward compatibility: single item_id
        item_id = data.get('item_id')
        if item_id:
            item_ids = [item_id]
        else:
            return jsonify({'success': False, 'error': 'Missing item_id or item_ids'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get materials (metal and souls)
    c.execute('SELECT metal, souls FROM blacksmith_materials WHERE user_id = ?', (user_id,))
    materials = c.fetchone()
    metal = materials['metal'] if materials else 0
    souls = materials['souls'] if materials else 0
    
    # Try to upgrade items
    upgraded = []
    total_metal_spent = 0
    total_souls_spent = 0
    
    for instance_id in item_ids:
        # Get item from equipment by instance ID
        c.execute('SELECT * FROM equipment WHERE user_id = ? AND id = ?', (user_id, instance_id))
        item = c.fetchone()
        if not item:
            continue
        
        # Get upgrade level, default to 0 if column doesn't exist or is None
        try:
            current_level = item['upgrade_level'] or 0
        except (KeyError, IndexError):
            current_level = 0
        next_level = current_level + 1
        
        if next_level > 5:
            continue
        
        cost = BLACKSMITH_UPGRADE_COSTS.get(next_level)
        if not cost:
            continue
        
        # Check if we can afford
        if metal < cost['metal']:
            continue
        if souls < cost['souls']:
            continue
        
        # Upgrade item
        try:
            c.execute('ALTER TABLE equipment ADD COLUMN upgrade_level INTEGER DEFAULT 0')
        except:
            pass
        
        c.execute('UPDATE equipment SET upgrade_level = ? WHERE user_id = ? AND id = ?',
                 (next_level, user_id, instance_id))
        
        total_metal_spent += cost['metal']
        total_souls_spent += cost['souls']
        upgraded.append({
            'instance_id': instance_id,
            'equipment_id': item['equipment_id'],
            'new_level': next_level
        })
    
    if not upgraded:
        conn.close()
        return jsonify({'success': False, 'error': 'Nelze upgradovat žádné itemy'}), 400
    
    # Update materials
    new_metal = metal - total_metal_spent
    new_souls = souls - total_souls_spent
    
    c.execute('UPDATE blacksmith_materials SET metal = ?, souls = ? WHERE user_id = ?', 
              (new_metal, new_souls, user_id))
    
    conn.commit()
    conn.close()
    return jsonify({
        'success': True,
        'upgraded': upgraded,
        'total_metal_spent': total_metal_spent,
        'total_souls_spent': total_souls_spent,
        'new_metal': new_metal,
        'new_souls': new_souls
    })

@app.route('/api/blacksmith/items', methods=['GET'])
def get_blacksmith_items():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    conn = None
    try:
        user_id = session['user_id']
        conn = get_db()
        c = conn.cursor()
        
        # Ensure upgrade_level column exists
        # Check if column exists first
        c.execute("PRAGMA table_info(equipment)")
        columns = [row[1] for row in c.fetchall()]
        has_upgrade_level = 'upgrade_level' in columns
        
        if not has_upgrade_level:
            try:
                c.execute('ALTER TABLE equipment ADD COLUMN upgrade_level INTEGER DEFAULT 0')
                conn.commit()
                has_upgrade_level = True
            except sqlite3.OperationalError as e:
                print(f"Error adding upgrade_level column: {e}")
        
        # Get all equipment items
        # Build query based on whether upgrade_level column exists
        if has_upgrade_level:
            c.execute('''SELECT id, equipment_id, equipment_slot, upgrade_level
                         FROM equipment
                         WHERE user_id = ?
                         ORDER BY equipment_id, id''', (user_id,))
        else:
            c.execute('''SELECT id, equipment_id, equipment_slot
                         FROM equipment
                         WHERE user_id = ?
                         ORDER BY equipment_id, id''', (user_id,))
        rows = c.fetchall()
        
        items = []
        for row in rows:
            try:
                equipment_id = row['equipment_id']
                definition = get_item_definition(equipment_id)
                if not definition:
                    definition = {}
                upgrade_level = row['upgrade_level'] if has_upgrade_level else 0
                upgrade_level = upgrade_level or 0
                
                # Get base bonuses from item definition
                base_bonus = definition.get('bonus', {})
                
                items.append({
                    'instance_id': row['id'],
                    'equipment_id': equipment_id,
                    'name': definition.get('name', equipment_id),
                    'rarity': definition.get('rarity', 'common'),
                    'slot': definition.get('slot', row['equipment_slot']),
                    'upgrade_level': upgrade_level,
                    'max_level': 5,
                    'bonus': base_bonus  # Include base bonuses for display
                })
            except Exception as e:
                equipment_id_for_error = row['equipment_id'] if 'equipment_id' in row else 'unknown'
                print(f"Error processing item {equipment_id_for_error}: {e}")
                continue
        
        # If no items, add test item (Lugogova koruna)
        if len(items) == 0:
            test_equipment_id = 'koruna_lugogu'
            eq_def = get_item_definition(test_equipment_id)
            if eq_def:
                slot = eq_def.get('slot', 'helmet')
                try:
                    if has_upgrade_level:
                        c.execute('''INSERT INTO equipment 
                                     (user_id, equipment_id, equipment_slot, equipped, upgrade_level, acquired_via, acquisition_note)
                                     VALUES (?, ?, ?, 0, 0, 'test', 'Testovací item pro kováře')''',
                                 (user_id, test_equipment_id, slot))
                    else:
                        c.execute('''INSERT INTO equipment 
                                     (user_id, equipment_id, equipment_slot, equipped, acquired_via, acquisition_note)
                                     VALUES (?, ?, ?, 0, 'test', 'Testovací item pro kováře')''',
                                 (user_id, test_equipment_id, slot))
                    conn.commit()
                    
                    # Get the newly inserted item
                    if has_upgrade_level:
                        c.execute('''SELECT id, equipment_id, equipment_slot, upgrade_level
                                     FROM equipment
                                     WHERE user_id = ? AND equipment_id = ?
                                     ORDER BY id DESC LIMIT 1''', (user_id, test_equipment_id))
                    else:
                        c.execute('''SELECT id, equipment_id, equipment_slot
                                     FROM equipment
                                     WHERE user_id = ? AND equipment_id = ?
                                     ORDER BY id DESC LIMIT 1''', (user_id, test_equipment_id))
                    new_row = c.fetchone()
                    if new_row:
                        items.append({
                            'instance_id': new_row['id'],
                            'equipment_id': test_equipment_id,
                            'name': eq_def.get('name', test_equipment_id),
                            'rarity': eq_def.get('rarity', 'common'),
                            'slot': eq_def.get('slot', slot),
                            'upgrade_level': 0,
                            'max_level': 5
                        })
                except Exception as e:
                    print(f"Error adding test item: {e}")
        
        if conn:
            conn.close()
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        if conn:
            conn.close()
        print(f"Error in get_blacksmith_items: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'Chyba při načítání itemů: {str(e)}'}), 500

@app.route('/api/blacksmith/disassemble', methods=['POST'])
def blacksmith_disassemble():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    item_ids = data.get('item_ids', [])  # List of instance IDs
    
    if not item_ids:
        # Backward compatibility: single item_id
        item_id = data.get('item_id')
        if item_id:
            # Try to find instance ID from equipment_id
            user_id = session['user_id']
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT id FROM equipment WHERE user_id = ? AND equipment_id = ? LIMIT 1', (user_id, item_id))
            row = c.fetchone()
            conn.close()
            if row:
                item_ids = [row['id']]
            else:
                return jsonify({'success': False, 'error': 'Item nenalezen'}), 404
        else:
            return jsonify({'success': False, 'error': 'Missing item_id or item_ids'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get materials
    c.execute('SELECT metal, souls FROM blacksmith_materials WHERE user_id = ?', (user_id,))
    materials = c.fetchone()
    current_metal = materials['metal'] if materials else 0
    current_souls = materials['souls'] if materials else 0
    
    total_metal_gained = 0
    total_souls_gained = 0
    disassembled = []
    
    for instance_id in item_ids:
        # Get item from equipment by instance ID
        c.execute('SELECT * FROM equipment WHERE user_id = ? AND id = ?', (user_id, instance_id))
        item = c.fetchone()
        if not item:
            continue
        
        equipment_id = item['equipment_id']
        definition = get_item_definition(equipment_id)
        rarity = definition.get('rarity', 'common')
        # Get upgrade level, default to 0 if column doesn't exist or is None
        try:
            level = item['upgrade_level'] or 0
        except (KeyError, IndexError):
            level = 0
        
        # Base values based on rarity (higher rarity = more materials)
        # Common: 100 metal, 10 souls
        # Rare: 250 metal, 25 souls  
        # Epic: 500 metal, 50 souls
        # Legendary: 1000 metal, 100 souls
        # Unique: 2000 metal, 200 souls
        rarity_base = {
            'common': {'metal': 100, 'souls': 10},
            'rare': {'metal': 250, 'souls': 25},
            'epic': {'metal': 500, 'souls': 50},
            'legendary': {'metal': 1000, 'souls': 100},
            'unique': {'metal': 2000, 'souls': 200}
        }
        
        base = rarity_base.get(rarity, rarity_base['common'])
        base_metal = base['metal']
        base_souls = base['souls']
        
        # Level bonus: +20% per level
        level_mult = 1 + (level * 0.2)
        
        metal_return = int(base_metal * level_mult)
        souls_return = int(base_souls * level_mult)
        
        total_metal_gained += metal_return
        total_souls_gained += souls_return
        
        disassembled.append({
            'instance_id': instance_id,
            'equipment_id': equipment_id,
            'metal_gained': metal_return,
            'souls_gained': souls_return
        })
        
        # Remove item
        c.execute('DELETE FROM equipment WHERE user_id = ? AND id = ?', (user_id, instance_id))
    
    if not disassembled:
        conn.close()
        return jsonify({'success': False, 'error': 'Nelze rozbít žádné itemy'}), 400
    
    # Update materials
    new_metal = current_metal + total_metal_gained
    new_souls = current_souls + total_souls_gained
    
    c.execute('''INSERT OR REPLACE INTO blacksmith_materials (user_id, metal, souls)
                 VALUES (?, ?, ?)''', (user_id, new_metal, new_souls))
    
    conn.commit()
    conn.close()
    return jsonify({
        'success': True,
        'disassembled': disassembled,
        'total_metal_gained': total_metal_gained,
        'total_souls_gained': total_souls_gained,
        'new_metal': new_metal,
        'new_souls': new_souls
    })

# ========== DUNGEON SYSTEM ==========

@app.route('/api/dungeons/list', methods=['GET'])
def get_dungeons_list():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Get character level
    char_stats = ensure_character_stats(c, user_id)
    user_level = char_stats['level']
    
    # Get user dungeon progress
    c.execute('SELECT * FROM dungeons WHERE user_id = ?', (user_id,))
    user_dungeons = {row['dungeon_id']: row for row in c.fetchall()}
    
    # Build dungeon list
    dungeons = []
    for dungeon_id, dungeon_def in DUNGEON_DEFINITIONS.items():
        user_dungeon = user_dungeons.get(dungeon_id)
        current_floor = user_dungeon['current_floor'] if user_dungeon else 1
        completed_floors = json.loads(user_dungeon['completed_floors']) if user_dungeon and user_dungeon['completed_floors'] else []
        
        unlocked = user_level >= dungeon_def['base_level']
        
        # Build enemy info
        main_boss = dungeon_def.get('main_boss', {})
        minibosses = dungeon_def.get('minibosses', [])
        common_enemies = dungeon_def.get('common_enemies', [])
        locations = dungeon_def.get('locations', [])
        
        dungeons.append({
            'id': dungeon_id,
            'name': dungeon_def['name'],
            'base_level': dungeon_def['base_level'],
            'unlocked': unlocked,
            'current_floor': current_floor,
            'max_floor': dungeon_def['floors'],
            'completed_floors': completed_floors,
            'main_boss': main_boss,
            'minibosses': minibosses,
            'common_enemies': common_enemies,
            'locations': locations
        })
    
    conn.close()
    return jsonify({'success': True, 'dungeons': dungeons})

def get_enemy_for_floor(dungeon_def, floor):
    """Determine which enemy type is on this floor"""
    # Check main boss
    main_boss = dungeon_def.get('main_boss', {})
    if main_boss.get('floor') == floor:
        return 'main_boss', main_boss
    
    # Check minibosses
    minibosses = dungeon_def.get('minibosses', [])
    for miniboss in minibosses:
        if miniboss.get('floor') == floor:
            return 'miniboss', miniboss
    
    # Otherwise, it's a common enemy
    common_enemies = dungeon_def.get('common_enemies', [])
    if common_enemies:
        # Scale enemy stats based on floor
        base_enemy = random.choice(common_enemies).copy()
        floor_multiplier = 1 + (floor - 1) * 0.15  # 15% increase per floor
        base_enemy['hp'] = int(base_enemy['hp'] * floor_multiplier)
        base_enemy['attack'] = int(base_enemy['attack'] * floor_multiplier)
        base_enemy['defense'] = int(base_enemy['defense'] * floor_multiplier)
        base_enemy['exp'] = int(base_enemy['exp'] * floor_multiplier)
        base_enemy['gooncoins'] = int(base_enemy['gooncoins'] * floor_multiplier)
        return 'common', base_enemy
    
    return None, None

def build_enemy_stats(enemy_data):
    """Convert enemy data to combat stats format"""
    return {
        'hp': enemy_data.get('hp', 1000),
        'attack': enemy_data.get('attack', 100),
        'defense': enemy_data.get('defense', 50),
        'luck': enemy_data.get('luck', 10),
        'armor': enemy_data.get('armor', 0)
    }

@app.route('/api/dungeons/fight', methods=['POST'])
def dungeon_fight():
    conn = None
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        
        data = request.get_json() or {}
        dungeon_id = data.get('dungeon_id')
        floor = data.get('floor', 1)
        
        if not dungeon_id or dungeon_id not in DUNGEON_DEFINITIONS:
            return jsonify({'success': False, 'error': 'Neplatný dungeon'}), 400
        
        if not isinstance(floor, int) or floor < 1:
            return jsonify({'success': False, 'error': 'Neplatné patro'}), 400
        
        user_id = session['user_id']
        conn = get_db()
        c = conn.cursor()
        
        # Get character stats
        char_stats = ensure_character_stats(c, user_id)
        # Convert sqlite3.Row to dict if needed
        if hasattr(char_stats, 'keys'):
            char_stats_dict = dict(char_stats)
        else:
            char_stats_dict = char_stats
        
        try:
            player_class = char_stats_dict.get('class', 'warrior') or 'warrior'
        except (KeyError, IndexError, TypeError, AttributeError):
            player_class = 'warrior'
        
        # Safely get player stats with defaults
        player_stats = {
            'strength': char_stats_dict.get('strength', 10),
            'dexterity': char_stats_dict.get('dexterity', 10),
            'intelligence': char_stats_dict.get('intelligence', 10),
            'constitution': char_stats_dict.get('constitution', 10),
            'luck': char_stats_dict.get('luck', 10)
        }
        
        dungeon_def = DUNGEON_DEFINITIONS[dungeon_id]
        
        # Validate floor
        if floor > dungeon_def.get('floors', 1):
            conn.close()
            return jsonify({'success': False, 'error': f'Patro {floor} neexistuje v tomto dungeonu'}), 400
        
        # Determine enemy type
        enemy_type, enemy_data = get_enemy_for_floor(dungeon_def, floor)
        
        if not enemy_data:
            conn.close()
            return jsonify({'success': False, 'error': 'Nepřítel nenalezen pro toto patro'}), 400
        
        # Build enemy stats for combat
        enemy_stats = build_enemy_stats(enemy_data)
        
        # Calculate player combat stats properly
        player_combat_stats = calculate_player_combat_stats(c, user_id)
        player_hp = player_combat_stats.get('hp', 100)
        
        # Build combat-ready stats with validation
        attacker_stats = {
            'hp': max(1, player_hp),
            'attack': max(1, player_combat_stats.get('attack', 10)),
            'defense': max(0, player_combat_stats.get('defense', 5)),
            'luck': max(0, player_combat_stats.get('luck', 10))
        }
        
        defender_stats = {
            'hp': max(1, enemy_stats.get('hp', 100)),
            'attack': max(1, enemy_stats.get('attack', 10)),
            'defense': max(0, enemy_stats.get('defense', 5)),
            'luck': max(0, enemy_stats.get('luck', 10))
        }
        
        battle = simulate_combat(attacker_stats, defender_stats, max_rounds=20)
        # Add initial HP values for animation
        battle['attacker_hp'] = attacker_stats['hp']
        battle['defender_hp'] = defender_stats['hp']
        player_won = battle.get('winner') == 'attacker'
        
        if player_won:
            # Victory - Update dungeon progress
            c.execute('SELECT * FROM dungeons WHERE user_id = ? AND dungeon_id = ?', (user_id, dungeon_id))
            dungeon = c.fetchone()
            
            completed_floors = []
            if dungeon:
                completed_floors = json.loads(dungeon['completed_floors']) if dungeon['completed_floors'] else []
            
            if floor not in completed_floors:
                completed_floors.append(floor)
            
            new_floor = min(floor + 1, dungeon_def['floors'])
            
            # Get existing dungeon data for battle stats
            c.execute('SELECT * FROM dungeons WHERE user_id = ? AND dungeon_id = ?', (user_id, dungeon_id))
            existing_dungeon = c.fetchone()
            # Convert sqlite3.Row to dict if needed
            if existing_dungeon and hasattr(existing_dungeon, 'keys'):
                existing_dungeon_dict = dict(existing_dungeon)
            else:
                existing_dungeon_dict = existing_dungeon if existing_dungeon else {}
            
            # Update battle statistics (merge dungeons + boj)
            total_battles = (existing_dungeon_dict.get('total_battles', 0) if existing_dungeon_dict else 0) + 1
            total_wins = (existing_dungeon_dict.get('total_wins', 0) if existing_dungeon_dict else 0) + 1
            total_losses = existing_dungeon_dict.get('total_losses', 0) if existing_dungeon_dict else 0
            
            # Get battle history
            battle_history = []
            if existing_dungeon_dict and existing_dungeon_dict.get('battle_history'):
                try:
                    battle_history = json.loads(existing_dungeon_dict['battle_history'])
                except:
                    battle_history = []
            
            # Add current battle to history (keep last 20)
            battle_entry = {
                'floor': floor,
                'enemy': enemy_data.get('name', 'Nepřítel'),
                'enemy_type': enemy_type,
                'result': 'victory',
                'rounds': len(battle.get('log', [])),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            battle_history.append(battle_entry)
            if len(battle_history) > 20:
                battle_history = battle_history[-20:]
            
            c.execute('''INSERT OR REPLACE INTO dungeons 
                        (user_id, dungeon_id, current_floor, max_floor, completed_floors, last_attempt,
                         last_battle_result, last_battle_enemy, last_battle_rounds,
                         total_battles, total_wins, total_losses, battle_history)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (user_id, dungeon_id, new_floor, dungeon_def['floors'], 
                      json.dumps(completed_floors), datetime.now(timezone.utc).isoformat(),
                      'victory', enemy_data.get('name', 'Nepřítel'), len(battle.get('log', [])),
                      total_battles, total_wins, total_losses, json.dumps(battle_history)))
            
            # Calculate rewards based on enemy type
            rewards = {}
            if enemy_type == 'main_boss':
                rewards = enemy_data.get('rewards', {}).copy()
            elif enemy_type == 'miniboss':
                rewards = enemy_data.get('rewards', {}).copy()
            else:  # common enemy
                rewards = {
                    'gooncoins': enemy_data.get('gooncoins', 100),
                    'exp': enemy_data.get('exp', 50)
                }
            
            # Handle rare materials
            rare_materials = rewards.pop('rare_materials', {})
            if rare_materials:
                ensure_rare_materials(c, user_id)
                adjust_rare_materials(c, user_id, rare_materials)
            
            # Update character experience
            current_exp = char_stats_dict.get('experience', 0)
            exp_gain = rewards.get('exp', 0)
            new_exp = current_exp + exp_gain
            level = char_stats_dict.get('level', 1)
            exp_needed = 100 * (level ** 1.5)
            new_level = level
            available_points = char_stats_dict.get('available_points', 0)
            
            while new_exp >= exp_needed:
                new_exp -= exp_needed
                new_level += 1
                available_points += 5
                exp_needed = 100 * (new_level ** 1.5)
            
            c.execute('''UPDATE character_stats 
                         SET experience = ?, level = ?, available_points = ?
                         WHERE user_id = ?''',
                     (new_exp, new_level, available_points, user_id))
            
            # Update gooncoins
            gooncoins_gain = rewards.get('gooncoins', 0)
            if gooncoins_gain > 0:
                c.execute('SELECT gooncoins FROM game_state WHERE user_id = ?', (user_id,))
                state = c.fetchone()
                current_gooncoins = state['gooncoins'] if state and state['gooncoins'] else 0
                new_gooncoins = current_gooncoins + gooncoins_gain
                c.execute('UPDATE game_state SET gooncoins = ? WHERE user_id = ?', (new_gooncoins, user_id))
            else:
                new_gooncoins = None
            
            # Chance for item drop (only for bosses)
            item_drop = None
            if enemy_type in ['main_boss', 'miniboss'] and random.random() < 0.3:
                all_items = get_all_item_definitions()
                item_ids = list(all_items.keys())
                if item_ids:
                    item_drop = random.choice(item_ids)
                    rewards['item'] = item_drop
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'victory': True,
                'enemy_type': enemy_type,
                'enemy_name': enemy_data.get('name', 'Nepřítel'),
                'battle': battle,
                'rewards': rewards,
                'new_level': new_level,
                'new_gooncoins': new_gooncoins
            })
        else:
            # Defeat - Update battle statistics (merge dungeons + boj)
            c.execute('SELECT * FROM dungeons WHERE user_id = ? AND dungeon_id = ?', (user_id, dungeon_id))
            existing_dungeon = c.fetchone()
            # Convert sqlite3.Row to dict if needed
            if existing_dungeon and hasattr(existing_dungeon, 'keys'):
                existing_dungeon_dict = dict(existing_dungeon)
            else:
                existing_dungeon_dict = existing_dungeon if existing_dungeon else {}
            
            # Update battle statistics
            total_battles = (existing_dungeon_dict.get('total_battles', 0) if existing_dungeon_dict else 0) + 1
            total_wins = existing_dungeon_dict.get('total_wins', 0) if existing_dungeon_dict else 0
            total_losses = (existing_dungeon_dict.get('total_losses', 0) if existing_dungeon_dict else 0) + 1
            
            # Get battle history
            battle_history = []
            if existing_dungeon_dict and existing_dungeon_dict.get('battle_history'):
                try:
                    battle_history = json.loads(existing_dungeon_dict['battle_history'])
                except:
                    battle_history = []
            
            # Add current battle to history (keep last 20)
            battle_entry = {
                'floor': floor,
                'enemy': enemy_data.get('name', 'Nepřítel'),
                'enemy_type': enemy_type,
                'result': 'defeat',
                'rounds': len(battle.get('log', [])),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            battle_history.append(battle_entry)
            if len(battle_history) > 20:
                battle_history = battle_history[-20:]
            
            # Get or create dungeon entry
            current_floor = existing_dungeon_dict.get('current_floor', 1) if existing_dungeon_dict else 1
            max_floor = existing_dungeon_dict.get('max_floor', dungeon_def['floors']) if existing_dungeon_dict else dungeon_def['floors']
            completed_floors = existing_dungeon_dict.get('completed_floors', '[]') if existing_dungeon_dict else '[]'
            last_attempt = datetime.now(timezone.utc).isoformat()
            
            c.execute('''INSERT OR REPLACE INTO dungeons 
                        (user_id, dungeon_id, current_floor, max_floor, completed_floors, last_attempt,
                         last_battle_result, last_battle_enemy, last_battle_rounds,
                         total_battles, total_wins, total_losses, battle_history)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                     (user_id, dungeon_id, current_floor, max_floor, completed_floors, last_attempt,
                      'defeat', enemy_data.get('name', 'Nepřítel'), len(battle.get('log', [])),
                      total_battles, total_wins, total_losses, json.dumps(battle_history)))
            
            conn.commit()
            conn.close()
            return jsonify({
                'success': True,
                'victory': False,
                'enemy_type': enemy_type,
                'enemy_name': enemy_data.get('name', 'Nepřítel'),
                'battle': battle
            })
    except Exception as e:
        # Log the error for debugging
        import traceback
        print(f"Error in dungeon_fight: {str(e)}")
        print(traceback.format_exc())
        
        # Close connection if it exists
        if conn:
            try:
                conn.close()
            except:
                pass
        
        # Return user-friendly error message
        return jsonify({
            'success': False,
            'error': f'Chyba při boji: {str(e)}'
        }), 500

# ========== GUILD SYSTEM ==========

@app.route('/api/guilds/list', methods=['GET'])
def get_guilds_list():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''SELECT g.*, COUNT(gm.user_id) as member_count
                 FROM guilds g
                 LEFT JOIN guild_members gm ON g.id = gm.guild_id
                 GROUP BY g.id
                 ORDER BY member_count DESC''')
    
    guilds = []
    for row in c.fetchall():
        guilds.append({
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'exp_bonus': row['exp_bonus'],
            'gold_bonus': row['gold_bonus'],
            'member_count': row['member_count']
        })
    
    conn.close()
    return jsonify({'success': True, 'guilds': guilds})

@app.route('/api/guilds/create', methods=['POST'])
def create_guild():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    name = data.get('name')
    description = data.get('description', '')
    
    if not name:
        return jsonify({'success': False, 'error': 'Chybí název guildy'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user is already in a guild
    c.execute('SELECT guild_id FROM guild_members WHERE user_id = ?', (user_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Už jsi v guildě'}), 400
    
    # Create guild
    try:
        c.execute('''INSERT INTO guilds (name, description, leader_id, exp_bonus, gold_bonus)
                     VALUES (?, ?, ?, ?, ?)''',
                 (name, description, user_id, GUILD_BONUS_BASE['exp'], GUILD_BONUS_BASE['gold']))
        guild_id = c.lastrowid
        
        # Add creator as leader
        c.execute('''INSERT INTO guild_members (guild_id, user_id, role)
                     VALUES (?, ?, 'leader')''', (guild_id, user_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'guild_id': guild_id})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Guilda s tímto názvem už existuje'}), 400

@app.route('/api/guilds/join', methods=['POST'])
def join_guild():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    data = request.get_json() or {}
    guild_id = data.get('guild_id')
    
    if not guild_id:
        return jsonify({'success': False, 'error': 'Chybí guild_id'}), 400
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    # Check if user is already in a guild
    c.execute('SELECT guild_id FROM guild_members WHERE user_id = ?', (user_id,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Už jsi v guildě'}), 400
    
    # Check if guild exists
    c.execute('SELECT id FROM guilds WHERE id = ?', (guild_id,))
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Guilda nenalezena'}), 404
    
    # Join guild
    try:
        c.execute('''INSERT INTO guild_members (guild_id, user_id, role)
                     VALUES (?, ?, 'member')''', (guild_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'success': False, 'error': 'Už jsi v této guildě'}), 400

@app.route('/api/guilds/my', methods=['GET'])
def get_my_guild():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    user_id = session['user_id']
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''SELECT g.*, gm.role
                 FROM guilds g
                 JOIN guild_members gm ON g.id = gm.guild_id
                 WHERE gm.user_id = ?''', (user_id,))
    guild = c.fetchone()
    
    if not guild:
        conn.close()
        return jsonify({'success': True, 'guild': None})
    
    # Get members
    c.execute('''SELECT u.username, gm.role, gm.joined_at
                 FROM guild_members gm
                 JOIN users u ON gm.user_id = u.id
                 WHERE gm.guild_id = ?
                 ORDER BY gm.role DESC, gm.joined_at ASC''', (guild['id'],))
    
    members = []
    for row in c.fetchall():
        members.append({
            'username': row['username'],
            'role': row['role'],
            'joined_at': row['joined_at']
        })
    
    conn.close()
    return jsonify({
        'success': True,
        'guild': {
            'id': guild['id'],
            'name': guild['name'],
            'description': guild['description'],
            'exp_bonus': guild['exp_bonus'],
            'gold_bonus': guild['gold_bonus'],
            'role': guild['role'],
            'members': members
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

