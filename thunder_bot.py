#!/usr/bin/env python3
# ==============================================================================
# ╔════════════════════════════════════════════════════════════════════════════╗
# ║              MARCO & THE DARK  ::  THUNDER AUTO-FARM                     ║
# ║                    DARKNET TG ENGINE v3.0 (DIRECT CLI)                     ║
# ╚════════════════════════════════════════════════════════════════════════════╝
# ==============================================================================

import os
import sys
import time
import json
import math
import random
import base64
import hmac
import hashlib
import sqlite3
import threading
import html
import re
import socket
import logging
from typing import Optional, Dict, Any

# ── Direct IPv4 & DNS Cache for Fast Telegram Connection ──
_orig_getaddrinfo = socket.getaddrinfo
def cached_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == 'api.telegram.org':
        return [
            (socket.AF_INET, socket.SOCK_STREAM, proto or 6, '', ('149.154.166.110', port or 443)),
            (socket.AF_INET, socket.SOCK_STREAM, proto or 6, '', ('149.154.167.220', port or 443)),
        ]
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = cached_getaddrinfo

import requests
import telebot
from telebot import types

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ThunderBot")
logging.getLogger("TeleBot").setLevel(logging.CRITICAL)

# ── AES-256-GCM via pycryptodome / cryptography ──
try:
    from Crypto.Cipher import AES as _AES
    class AESGCM:
        def __init__(self, key: bytes):
            self.key = key

        def decrypt(self, iv: bytes, ciphertext: bytes, aad=None) -> bytes:
            ct, tag = ciphertext[:-16], ciphertext[-16:]
            cipher = _AES.new(self.key, _AES.MODE_GCM, nonce=iv)
            if aad:
                cipher.update(aad)
            return cipher.decrypt_and_verify(ct, tag)
except ImportError:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# ==============================================================================
# CONFIGURATION
# ==============================================================================
BOT_TOKEN = "8987643705:AAGuY33kM5_H9m8iyZvupglFkbXnGTpAkpI"
BASE_URL = os.environ.get("TU_BASE_URL", "https://thunder-zone.coke2home.com")
TU_KEY = os.environ.get("TU_KEY", "a9rc/DSXunC5PdkYlDB6KkX/evwfSTDUD8PQdaepxe0=")

# ── Timing defaults (browser-matched, per campaign reference) ──
DEFAULT_MIN_DURATION_S = 120         # 2 min minimum
DEFAULT_MAX_BOXES = 9999
OWNER_ID = 8327850869
OWNER_HANDLE = "@owatom"

# ── Heartbeat / drip-refill cadence (browser-matched) ──
HEARTBEAT_INTERVAL_S = 5.0           # ~5 sec cadence
DRIP_REFILL_EVERY_BOXES = 30         # refill every 30 boxes
PACE_TO_SIM_CLOCK = True             # human browser clock pacing
HB_FLOAT_BUFFER_MIN = 4              # top-up heartbeat when floats low

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thunder_bot.db")

GAME_CONFIG = {
    'startHp': 3,
    'maxHp': 3,
    'scoring': {
        'thunder': 15, 'thunder2': 15, 'gully': 50,
        'firefox': 50, 'heart': 0, 'trap': 0,
    },
    'distribution': {
        'full': {
            'thunder': 0.2, 'thunder2': 0.2, 'heart': 0.0,
            'trap': 0.45, 'gully': 0.075, 'firefox': 0.075,
        },
        'damaged': {
            'thunder': 0.175, 'thunder2': 0.175, 'heart': 0.2,
            'trap': 0.3, 'gully': 0.075, 'firefox': 0.075,
        },
    },
    'tiers': [
        {'id': 1, 'untilMs': 15000,  'spawnEveryMs': 1000, 'travelMs': 1950},
        {'id': 2, 'untilMs': 30000,  'spawnEveryMs': 800,  'travelMs': 1540},
        {'id': 3, 'untilMs': 45000,  'spawnEveryMs': 700,  'travelMs': 1350},
        {'id': 4, 'untilMs': 60000,  'spawnEveryMs': 600,  'travelMs': 1150},
        {'id': 5, 'untilMs': 75000,  'spawnEveryMs': 500,  'travelMs': 963},
        {'id': 6, 'untilMs': 90000,  'spawnEveryMs': 400,  'travelMs': 770},
        {'id': 7, 'untilMs': 105000, 'spawnEveryMs': 200,  'travelMs': 385},
        {'id': 8, 'untilMs': 120000, 'spawnEveryMs': 100,  'travelMs': 193},
    ],
}

BOX_TYPES = ['thunder', 'thunder2', 'heart', 'trap', 'gully', 'firefox']
DIRECTIONS = ['up', 'down', 'left', 'right']
OPPOSITE = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}

BOX_NAME_MAP = {
    "thunder": "thunder_box",
    "thunder2": "thunder_box",
    "thunderCan": "thunder_can",
    "gully": "gully_labs",
    "firefox": "firefox",
    "heart": "heart",
    "trap": "trap",
}

BOX_ICONS = {
    'thunder': '⚡ thunder',
    'thunder2': '⚡ thunder2',
    'heart': '♥ heart',
    'trap': '☠ trap',
    'gully': '◈ gully',
    'firefox': '✦ firefox',
}

def safe_html(text: Any) -> str:
    if text is None:
        return ""
    return html.escape(str(text))

def get_tier(elapsed_ms: float) -> dict:
    for t in GAME_CONFIG['tiers']:
        if elapsed_ms < t['untilMs']:
            return t
    return GAME_CONFIG['tiers'][-1]


# ==============================================================================
# DATABASE (SQLite)
# ==============================================================================
db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                name TEXT,
                cookies_json TEXT,
                pending_phone TEXT,
                last_target INTEGER DEFAULT 2000,
                banned INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                created_at REAL,
                games_played INTEGER DEFAULT 0,
                updated_at REAL
            )
        ''')
        for col_def in [
            "pending_phone TEXT",
            "last_target INTEGER DEFAULT 2000",
            "banned INTEGER DEFAULT 0",
            "role TEXT DEFAULT 'user'",
            "created_at REAL",
            "games_played INTEGER DEFAULT 0"
        ]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
            except Exception:
                pass

        c.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at REAL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Default settings
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('free_mode', '1')")
        conn.commit()
        conn.close()

def get_user(user_id: int) -> Optional[dict]:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id, phone, name, cookies_json, pending_phone, last_target FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "user_id": row[0],
            "phone": row[1],
            "name": row[2],
            "cookies": json.loads(row[3]) if row[3] else None,
            "pending_phone": row[4],
            "last_target": row[5] or 2000,
        }

def set_pending_phone(user_id: int, phone: str):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (user_id, pending_phone, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                pending_phone = excluded.pending_phone,
                updated_at = excluded.updated_at
        ''', (user_id, phone, time.time()))
        conn.commit()
        conn.close()

def save_session(user_id: int, phone: str, name: str, cookies: dict):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO users (user_id, phone, name, cookies_json, pending_phone, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                phone = excluded.phone,
                name = excluded.name,
                cookies_json = excluded.cookies_json,
                pending_phone = NULL,
                updated_at = excluded.updated_at
        ''', (user_id, phone, name, json.dumps(cookies), time.time()))
        conn.commit()
        conn.close()
    if user_id == OWNER_ID:
        try:
            sess_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json")
            with open(sess_file, "w") as f:
                json.dump(cookies, f)
        except Exception:
            pass

def update_target(user_id: int, target: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET last_target = ? WHERE user_id = ?", (target, user_id))
        conn.commit()
        conn.close()

def clear_session(user_id: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET cookies_json = NULL, pending_phone = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def get_admin_ids() -> set:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id FROM admins")
        rows = c.fetchall()
        conn.close()
    s = {r[0] for r in rows}
    s.add(OWNER_ID)
    return s

def is_admin(user_id: int) -> bool:
    return user_id in get_admin_ids()

def add_admin(user_id: int, added_by: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO admins (user_id, added_by, added_at) VALUES (?, ?, ?)",
                  (user_id, added_by, time.time()))
        c.execute("UPDATE users SET role = 'admin' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def remove_admin(user_id: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        c.execute("UPDATE users SET role = 'user' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def ban_user(user_id: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def unban_user(user_id: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET banned = 0 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def is_banned(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return False
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT banned FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
    return bool(row and row[0] == 1)

def get_setting(key: str, default: str = "") -> str:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()

def increment_user_games(user_id: int):
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET games_played = COALESCE(games_played, 0) + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

def get_all_user_ids() -> list:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        rows = c.fetchall()
        conn.close()
    return [r[0] for r in rows]

def get_all_users(limit: int = 15) -> list:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT user_id, phone, name, banned, games_played, updated_at FROM users ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
    res = []
    for r in rows:
        res.append({
            "user_id": r[0],
            "phone": r[1] or "N/A",
            "name": r[2] or "Operator",
            "banned": bool(r[3]),
            "games_played": r[4] or 0,
            "updated_at": r[5] or 0
        })
    return res

def get_system_stats() -> dict:
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), SUM(CASE WHEN cookies_json IS NOT NULL THEN 1 ELSE 0 END), SUM(CASE WHEN banned = 1 THEN 1 ELSE 0 END), SUM(COALESCE(games_played, 0)) FROM users")
        row = c.fetchone()
        c.execute("SELECT COUNT(*) FROM admins")
        adm_cnt = c.fetchone()[0]
        conn.close()
    
    total = row[0] or 0
    logged_in = row[1] or 0
    banned = row[2] or 0
    games = row[3] or 0
    free_mode = (get_setting("free_mode", "1") == "1")
    return {
        "total_users": total,
        "logged_in": logged_in,
        "banned_users": banned,
        "total_games": games,
        "total_admins": adm_cnt + 1,
        "active_sessions": len(active_games),
        "free_mode": free_mode,
    }



# ==============================================================================
# GAME SIMULATOR
# ==============================================================================
class GameSimulator:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.raw_key = base64.b64decode(TU_KEY)
        self.derived_key = hmac.new(
            self.raw_key, session_id.encode('utf-8'), hashlib.sha256
        ).digest()

        self.floats = []
        self.drip_cursor = 0

        self.hp = 3
        self.max_hp = 3
        self.score = 0
        self.elapsed_ms = 0
        self.last_spawn_types = []
        self.heart_gate = {'boxes': 0, 'traps': 0, 'others': 0, 'hpAtLastSpawn': 3}
        self.next_box_id = 1
        self.next_spawn_at_ms = 0

        self.input_log = []
        self.hit_counts = {}
        self.max_combo = 0
        self.current_combo = 0

    def add_drip_enc(self, drip_enc: str, drip_from_box: int = 0):
        if not drip_enc:
            return
        try:
            raw_enc = base64.b64decode(drip_enc)
            iv = raw_enc[:12]
            ciphertext = raw_enc[12:]
            aesgcm = AESGCM(self.derived_key)
            new_floats = json.loads(aesgcm.decrypt(iv, ciphertext, None).decode('utf-8'))

            start_idx = drip_from_box * 2
            if len(self.floats) < start_idx + len(new_floats):
                self.floats.extend([0.0] * (start_idx + len(new_floats) - len(self.floats)))
            for i, v in enumerate(new_floats):
                self.floats[start_idx + i] = v
        except Exception as e:
            logger.warning(f"Drip decrypt error: {e}")

    def has_enough_floats(self, required: int = 4) -> bool:
        return (len(self.floats) - self.drip_cursor) >= required

    def get_float(self) -> float:
        if self.drip_cursor < len(self.floats):
            val = self.floats[self.drip_cursor]
            self.drip_cursor += 1
            return val
        return random.random()

    def generate_next_box(self) -> dict:
        spawn_ms = self.next_spawn_at_ms
        tier = get_tier(spawn_ms)

        if self.hp < self.heart_gate['hpAtLastSpawn']:
            self.heart_gate['boxes'] = 0
            self.heart_gate['traps'] = 0
            self.heart_gate['others'] = 0
        self.heart_gate['hpAtLastSpawn'] = self.hp

        allow_heart = (
            self.heart_gate['boxes'] >= 7
            and self.heart_gate['traps'] >= 2
            and self.heart_gate['others'] >= 3
        )

        f_type = self.get_float()
        dist = GAME_CONFIG['distribution']['full'] if self.hp >= self.max_hp else GAME_CONFIG['distribution']['damaged']

        o = None
        if len(self.last_spawn_types) >= 2 and self.last_spawn_types[-1] == self.last_spawn_types[-2]:
            o = self.last_spawn_types[-1]
        is_first = (self.next_box_id == 1)

        eligible, weights = [], []
        for btype in BOX_TYPES:
            w = dist[btype]
            if w <= 0:
                continue
            if btype == 'heart' and not allow_heart:
                continue
            if btype == o:
                continue
            if btype == 'trap' and is_first:
                continue
            eligible.append(btype)
            weights.append(w)

        if not eligible:
            for btype in BOX_TYPES:
                w = dist[btype]
                if w <= 0:
                    continue
                if btype == 'heart' and not allow_heart:
                    continue
                if btype == 'trap' and is_first:
                    continue
                eligible.append(btype)
                weights.append(w)

        total_w = sum(weights) if weights else 1.0
        target = f_type * total_w
        sel_type = eligible[-1] if eligible else 'thunder'
        for idx, w in enumerate(weights):
            target -= w
            if target < 0:
                sel_type = eligible[idx]
                break

        if sel_type == 'heart':
            self.heart_gate['boxes'] = 0
            self.heart_gate['traps'] = 0
            self.heart_gate['others'] = 0
        else:
            self.heart_gate['boxes'] += 1
            if sel_type == 'trap':
                self.heart_gate['traps'] += 1
            else:
                self.heart_gate['others'] += 1

        f_dir = self.get_float()
        direction = DIRECTIONS[math.floor(f_dir * len(DIRECTIONS))]

        box_id = self.next_box_id
        self.next_box_id += 1
        self.next_spawn_at_ms += tier['spawnEveryMs']

        self.last_spawn_types.append(sel_type)
        if len(self.last_spawn_types) > 2:
            self.last_spawn_types.pop(0)

        return {
            'id': box_id,
            'type': sel_type,
            'arrow': direction,
            'spawnMs': spawn_ms,
            'travelMs': tier['travelMs'],
            'tier': tier['id'],
        }

    def play_box_correctly(self, box: dict):
        btype = box['type']
        arrow = box['arrow']
        spawn_ms = box['spawnMs']
        travel_ms = box['travelMs']

        swipe_dir = OPPOSITE[arrow] if btype == 'trap' else arrow
        reaction_offset = random.randint(80, 300)
        at_ms = int(spawn_ms + travel_ms - reaction_offset)

        if self.input_log and at_ms <= self.input_log[-1]['atMs']:
            at_ms = self.input_log[-1]['atMs'] + random.randint(1, 10)

        pts = GAME_CONFIG['scoring'].get(btype, 0)
        self.score += pts
        if pts > 0:
            self.current_combo += 1
            self.max_combo = max(self.max_combo, self.current_combo)
        self.hit_counts[btype] = self.hit_counts.get(btype, 0) + 1

        self.input_log.append({
            "boxId": box['id'],
            "dir": swipe_dir,
            "atMs": at_ms,
            "spawnAtMs": spawn_ms,
            "type": btype,
            "correct": True,
        })
        self.elapsed_ms = at_ms
        return pts, swipe_dir

    @staticmethod
    def compute_chain_hash(session_id: str, input_log: list) -> str:
        items = [f"{b['boxId']}:{b['dir']}" for b in input_log]
        s = f"{session_id}|{','.join(items)}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()


# ==============================================================================
# COKE2HOME CLIENT
# ==============================================================================
class CokeClient:
    def __init__(self, cookies: Optional[dict] = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/152.0.0.0 Safari/537.36'
            ),
            'Origin': BASE_URL,
            'Referer': f'{BASE_URL}/',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
        })
        if cookies:
            self.session.cookies.update(cookies)

    def send_otp(self, phone: str) -> tuple[bool, str]:
        try:
            resp = self.session.post(f"{BASE_URL}/api/auth/send-otp", json={"phone_number": phone}, timeout=15)
            try:
                data = resp.json()
            except Exception:
                data = {}
            if data.get('success'):
                return True, "OTP dispatched to target device."
            return False, data.get('error') or data.get('message') or resp.text
        except Exception as e:
            return False, f"Network error: {e}"

    def verify_otp(self, phone: str, otp: str) -> tuple[bool, str, Optional[dict]]:
        try:
            resp = self.session.post(f"{BASE_URL}/api/auth/verify-otp", json={
                "phone_number": phone, "otp": otp
            }, timeout=15)
            try:
                data = resp.json()
            except Exception:
                data = {}

            logger.info("verify-otp status %s: %s", resp.status_code, data)

            if not data.get('success') and not data.get('authenticated'):
                err = data.get('error') or data.get('message') or "Invalid or expired OTP"
                return False, err, None

            token = data.get('one_time_token') or data.get('data', {}).get('one_time_token')
            if token:
                val_resp = self.session.post(f"{BASE_URL}/api/auth/validate-token", json={"one_time_token": token}, timeout=15)
                val_data = val_resp.json() if val_resp.status_code == 200 else {}
                requires_signup = val_data.get('requires_signup') or data.get('requiresSignup')

                if requires_signup:
                    # New user: /api/auth/signup directly authenticates
                    signup_resp = self.session.post(f"{BASE_URL}/api/auth/signup", json={
                        "phone_number": phone, "name": "Operator"
                    }, timeout=15)
                    s_data = signup_resp.json() if signup_resp.status_code == 200 else {}
                    if not s_data.get('success') and signup_resp.status_code != 200:
                        return False, f"Signup failed: {signup_resp.text}", None
                else:
                    # Existing user: exchange token
                    ex_resp = self.session.post(f"{BASE_URL}/api/auth/exchange-token", json={"one_time_token": token}, timeout=15)
                    ex_data = ex_resp.json() if ex_resp.status_code == 200 else {}
                    if not (ex_data.get('authenticated') or ex_data.get('success') or len(self.session.cookies) > 0):
                        return False, f"Token exchange failed: {ex_resp.text}", None

            me_resp = self.session.get(f"{BASE_URL}/api/auth/me", timeout=15)
            me_data = me_resp.json() if me_resp.status_code == 200 else {}
            user = me_data.get('user') or {}

            return True, "Login successful", {
                "name": user.get('name') or 'Operator',
                "phone": user.get('phone_number') or phone,
                "cookies": self.session.cookies.get_dict(),
            }
        except Exception as e:
            return False, f"Verification error: {e}", None

    def get_stats(self) -> Optional[dict]:
        try:
            resp = self.session.get(f"{BASE_URL}/api/thunder-trail/me", timeout=12)
            try:
                data = resp.json()
            except Exception:
                data = {}
            if data.get('success'):
                return data.get('data') or {}
            return None
        except Exception:
            return None

    def _heartbeat(self, session_id: str, session_token: str, sim: GameSimulator, committed_count: int, start_time: float) -> int:
        sim_ms = int(sim.elapsed_ms)
        real_ms = int((time.time() - start_time) * 1000.0)
        curr_ms = max(sim_ms, real_ms)

        chain_hash = GameSimulator.compute_chain_hash(session_id, sim.input_log)
        delta = [
            {"boxId": b["boxId"], "dir": b["dir"], "atMs": int(b["atMs"]), "spawnAtMs": int(b["spawnAtMs"])}
            for b in sim.input_log[committed_count:]
        ]
        try:
            resp = self.session.post(
                f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/heartbeat",
                json={
                    "session_token": session_token,
                    "boxes_seen": len(sim.input_log),
                    "score_so_far": sim.score,
                    "paused": False,
                    "at_ms": curr_ms,
                    "boxes_committed": len(sim.input_log),
                    "chain_hash": chain_hash,
                    "input_log_delta": delta,
                },
                timeout=10
            )
            data = resp.json()
            if data.get('drip_enc'):
                sim.add_drip_enc(data['drip_enc'], data.get('drip_from_box', 0))
            return len(sim.input_log)
        except Exception as e:
            logger.warning(f"[heartbeat] failed at box {len(sim.input_log)}: {e}")
            return committed_count

    # ─────────────────────────────────────────────────────────────────────────
    # DRIP-REFILL (Browser-matched API called every 30 boxes)
    # ─────────────────────────────────────────────────────────────────────────
    def _drip_refill(self, session_id: str, session_token: str,
                     sim: GameSimulator, from_box: int) -> bool:
        try:
            resp = self.session.post(
                f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/drip-refill",
                json={"session_token": session_token, "from_box": from_box},
                timeout=10
            )
            data = resp.json()
            if data.get('success') and data.get('drip_enc'):
                sim.add_drip_enc(data['drip_enc'], data.get('drip_from_box', from_box))
                logger.info(f"[drip-refill] ok @ box {from_box}")
                return True
            logger.warning(f"[drip-refill] empty response @ box {from_box}: {data}")
            return False
        except Exception as e:
            logger.warning(f"[drip-refill] failed @ box {from_box}: {e}")
            return False

    def play_game(self, target_score: int, min_duration_s: int, progress_cb=None, cancel_event=None) -> dict:
        resp = self.session.post(f"{BASE_URL}/api/thunder-trail/sessions", json={}, timeout=15)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not data.get('success') or not data.get('data'):
            return {"success": False, "error": data.get('message') or data.get('error') or f"Failed to start session (HTTP {resp.status_code})"}

        session_id = data['data']['session_id']
        session_token = data['data']['session_token']
        drip_enc = data['data'].get('drip_enc')
        drip_from_box = data['data'].get('drip_from_box', 0)

        sim = GameSimulator(session_id)
        sim.add_drip_enc(drip_enc, drip_from_box)

        start_time = time.time()
        committed_count = 0
        prev_tier = 1
        milestones = [100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000]
        last_m = 0
        events = []

        # ── Pacing state (browser-matched) ──
        last_hb_wall = time.time()
        last_refill_box = 0
        last_cb_time = 0

        # ============================================================
        # Phase 1: Playing — PACED to simulated wall-clock time
        # ============================================================
        while sim.score < target_score and len(sim.input_log) < DEFAULT_MAX_BOXES:
            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Game stopped by user."}

            # Wall-clock pacing: never outrun simulated time
            if PACE_TO_SIM_CLOCK:
                target_wall = start_time + (sim.elapsed_ms / 1000.0)
                now = time.time()
                if now < target_wall:
                    time.sleep(min(target_wall - now, 0.25))
                    continue

            # Heartbeat on ~5s cadence OR when float buffer is low
            now = time.time()
            if (now - last_hb_wall) >= HEARTBEAT_INTERVAL_S or not sim.has_enough_floats(required=HB_FLOAT_BUFFER_MIN):
                committed_count = self._heartbeat(
                    session_id, session_token, sim, committed_count, start_time
                )
                last_hb_wall = now

            # Drip-refill every ~30 boxes (matches browser)
            if len(sim.input_log) - last_refill_box >= DRIP_REFILL_EVERY_BOXES:
                self._drip_refill(session_id, session_token, sim, len(sim.input_log))
                last_refill_box = len(sim.input_log)

            box = sim.generate_next_box()
            sim.play_box_correctly(box)

            if box.get('tier', 1) > prev_tier:
                events.append(f"T{box['tier']}")
                prev_tier = box['tier']

            for m in milestones:
                if sim.score >= m > last_m:
                    events.append(f"{m} pts")
                    last_m = m

            now_cb = time.time()
            if progress_cb and (now_cb - last_cb_time >= 1.5):
                progress_cb("playing", sim, target_score, now_cb - start_time, events)
                last_cb_time = now_cb

        # Notify callback that play phase completed
        if progress_cb:
            progress_cb("fast_play_done", sim, target_score, time.time() - start_time, events)

        # ============================================================
        # Phase 2: Cooldown Wait — keep heartbeats alive
        # ============================================================
        elapsed = time.time() - start_time
        if elapsed < min_duration_s:
            while elapsed < min_duration_s:
                if cancel_event and cancel_event.is_set():
                    return {"success": False, "error": "Game stopped by user."}

                # Heartbeat every ~5s during cooldown
                now = time.time()
                if (now - last_hb_wall) >= HEARTBEAT_INTERVAL_S:
                    committed_count = self._heartbeat(
                        session_id, session_token, sim, committed_count, start_time
                    )
                    last_hb_wall = now

                elapsed = time.time() - start_time
                if progress_cb:
                    progress_cb("cooldown", sim, min_duration_s, elapsed, events)
                time.sleep(1.8)

        # ============================================================
        # Phase 3: Submit Score & Journey
        # ============================================================
        if progress_cb:
            progress_cb("submitting", sim, target_score, time.time() - start_time, events)

        mapped_hits = {}
        for k, v in sim.hit_counts.items():
            mk = BOX_NAME_MAP.get(k, k)
            mapped_hits[mk] = mapped_hits.get(mk, 0) + v

        # duration_ms: max of simulated and wall clock (server-safe)
        wall_ms = (time.time() - start_time) * 1000.0
        duration_ms = int(max(sim.next_spawn_at_ms + 1000, wall_ms))

        self.session.post(f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/score", json={
            "session_token": session_token,
            "final_score": sim.score,
            "duration_ms": duration_ms,
            "max_combo": sim.max_combo,
            "box_counts": mapped_hits,
            "seed": 0,
            "input_log": sim.input_log,
        }, timeout=15)

        max_tier = 1
        for idx, t in enumerate(GAME_CONFIG['tiers'][:-1]):
            if duration_ms >= t['untilMs']:
                max_tier = idx + 2

        journey_resp = self.session.post(f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/journey", json={
            "session_token": session_token,
            "seed": 0,
            "input_log": sim.input_log,
            "final_score": sim.score,
            "duration_ms": duration_ms,
            "max_combo": sim.max_combo,
            "hit_counts": mapped_hits,
            "max_tier_reached": max_tier,
        }, timeout=15).json()

        verified = journey_resp.get('success') and journey_resp.get('data', {}).get('score_valid', False)

        stats = self.get_stats() or {}
        return {
            "success": True,
            "score": sim.score,
            "target": target_score,
            "max_combo": sim.max_combo,
            "duration_s": time.time() - start_time,
            "hit_counts": sim.hit_counts,
            "verified": verified,
            "rank": stats.get('rank'),
            "plays_remaining": stats.get('plays_remaining', 0),
            "best_score": stats.get('best_score', sim.score),
        }


# ==============================================================================
# TELEGRAM BOT (DIRECT CONVERSATIONAL CLI FORMAT)
# ==============================================================================
# ==============================================================================
# TELEGRAM BOT (USER-FRIENDLY INLINE & AUTO-RESUME ENGINE)
# ==============================================================================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

active_games = {}
active_lock = threading.Lock()

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

def make_progress_bar(current: float, target: float, width: int = 15) -> str:
    ratio = min(max(current / max(target, 1), 0.0), 1.0)
    filled = int(width * ratio)
    return "█" * filled + "░" * (width - filled)

def safe_edit(chat_id: int, message_id: int, text: str, reply_markup=None) -> Optional[types.Message]:
    try:
        return bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup, parse_mode="HTML")
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e).lower():
            return None
        logger.warning(f"safe_edit fallback due to: {e}")
        try:
            return bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception as e2:
            logger.error(f"safe_edit send_message error: {e2}")
            return None
    except Exception as e:
        logger.warning(f"safe_edit failed: {e}")
        return None

def try_recover_session(user_id: int) -> bool:
    if user_id != OWNER_ID:
        return False
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "session.json"),
        "/home/piyush/Downloads/Telegram Desktop/session.json",
        "/home/piyush/Desktop/thunder_bot/session.json"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    cookies = json.load(f)
                client = CokeClient(cookies)
                stats = client.get_stats()
                if stats and (stats.get("username") or stats.get("plays_remaining") is not None):
                    phone = cookies.get("phone") or "9911776852"
                    uname = stats.get("username") or "Operator"
                    save_session(user_id, phone, uname, cookies)
                    logger.info(f"Auto-recovered session from {p} for user {user_id}")
                    return True
            except Exception as e:
                logger.warning(f"Recovery attempt failed for {p}: {e}")
    return False

def get_banner() -> str:
    return (
        "<code>"
        "┌──────────────────────────┐\n"
        "│     MARCO & THE DARK     │\n"
        "│  AUTO-FARM ENGINE v3.5   │\n"
        "└──────────────────────────┘\n"
        "</code>"
    )

def get_main_keyboard(plays: int = 1, user_id: int = 0) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Start Game (2000)", callback_data="act_play_2000")
    b3 = types.InlineKeyboardButton("🎯 Choose Target", callback_data="act_target_menu")
    b4 = types.InlineKeyboardButton("📊 Refresh Status", callback_data="act_refresh")
    b5 = types.InlineKeyboardButton("📱 Switch Number", callback_data="act_login")
    b6 = types.InlineKeyboardButton("🚪 Logout", callback_data="act_logout")
    markup.add(b1, b3)
    markup.add(b4, b5)
    markup.add(b6)
    if user_id and is_admin(user_id):
        adm_title = "👑 MASTER OWNER PANEL" if is_owner(user_id) else "🔴 ADMIN PANEL"
        markup.add(types.InlineKeyboardButton(adm_title, callback_data="owner_panel"))
    return markup

def get_target_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=3)
    b1 = types.InlineKeyboardButton("500", callback_data="set_tgt_500")
    b2 = types.InlineKeyboardButton("1000", callback_data="set_tgt_1000")
    b3 = types.InlineKeyboardButton("1500", callback_data="set_tgt_1500")
    b4 = types.InlineKeyboardButton("2000", callback_data="set_tgt_2000")
    b5 = types.InlineKeyboardButton("2500", callback_data="set_tgt_2500")
    b6 = types.InlineKeyboardButton("3000", callback_data="set_tgt_3000")
    back = types.InlineKeyboardButton("« Back to Menu", callback_data="act_menu")
    markup.add(b1, b2, b3)
    markup.add(b4, b5, b6)
    markup.add(back)
    return markup

def get_playing_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛑 Stop / Cancel Session", callback_data="act_stop"))
    return markup

def execute_logout(message_or_call):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    user_id = message_or_call.from_user.id
    clear_session(user_id)
    with active_lock:
        if user_id in active_games:
            active_games[user_id].set()
    bot.send_message(
        chat_id,
        "<b>[✔] LOGGED OUT :: Session Cleared.</b>\n\n"
        "▸ <b>Phone number (10 digits) to login:</b>",
        reply_markup=types.ReplyKeyboardRemove()
    )

def execute_login(message_or_call):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    user_id = message_or_call.from_user.id
    clear_session(user_id)
    banner = get_banner()
    bot.send_message(
        chat_id,
        f"{banner}\n"
        "🔐 <b>Thums Up Login</b>\n\n"
        "Apna <b>10-digit mobile number</b> enter karein:\n"
        "<i>(Example: 9876543210)</i>",
        reply_markup=types.ReplyKeyboardRemove()
    )

def show_profile(message_or_call, edit_msg_id: Optional[int] = None):
    chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else message_or_call.message.chat.id
    user_id = message_or_call.from_user.id
    if is_banned(user_id):
        bot.send_message(chat_id, "🚫 <b>ACCESS DENIED:</b> Aapka account banned hai. Super Admin se contact karein.")
        return

    if not is_admin(user_id) and get_setting("free_mode", "1") == "0":
        bot.send_message(chat_id, "🔒 <b>MAINTENANCE MODE:</b> Bot currently Admin-Only mode me hai. Naye users ke liye jald open hoga.")
        return
    u = get_user(user_id)
    if not (u and u.get('cookies')):
        if try_recover_session(user_id):
            u = get_user(user_id)
        else:
            execute_login(message_or_call)
            return

    client = CokeClient(u['cookies'])
    stats = client.get_stats()
    if not stats:
        if try_recover_session(user_id):
            u = get_user(user_id)
            client = CokeClient(u['cookies'])
            stats = client.get_stats()

    if not stats:
        clear_session(user_id)
        bot.send_message(
            chat_id,
            "⚠️ <b>Session Expire Ho Gaya Hai!</b>\nKripya login karein.\n\n▸ <b>Phone number (10 digits):</b>",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    name = safe_html(stats.get('username') or u.get('name') or 'Operator')
    phone = safe_html(u.get('phone') or 'N/A')
    plays = stats.get('plays_remaining', 0)
    used = stats.get('plays_used_today', 0)
    best = stats.get('best_score', 0)
    rank = stats.get('rank')
    rank_str = f"#{rank}" if rank else "UNRANKED"
    hearts = "❤️ " * plays + "🖤 " * max(0, 5 - plays)
    banner = get_banner()

    profile_text = (
        f"{banner}\n"
        f"👤 <b>Account:</b> <code>{name}</code> (+91 {phone})\n"
        f"<code>────────────────────────────</code>\n"
        f"❤️ <b>Lives Left :</b> <code>{plays} / 5</code>\n"
        f"🏆 <b>Best Score :</b> <code>{best} pts</code>\n"
        f"🌐 <b>Global Rank:</b> <code>{rank_str}</code>\n"
        f"📅 <b>Played Today:</b> <code>{used} games</code>\n"
        f"<code>────────────────────────────</code>\n"
        f"Status: {hearts}\n\n"
        f"🎯 <i>Select action below or type target score:</i>"
    )
    markup = get_main_keyboard(plays, user_id)
    if edit_msg_id:
        safe_edit(chat_id, edit_msg_id, profile_text, reply_markup=markup)
    else:
        bot.send_message(chat_id, profile_text, reply_markup=markup)


def get_admin_keyboard(is_owner_user: bool = False) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("📊 System Analytics", callback_data="adm_stats")
    b2 = types.InlineKeyboardButton("👥 User Directory", callback_data="adm_users")
    b3 = types.InlineKeyboardButton("📢 Broadcast Alert", callback_data="adm_bcast_prompt")
    free_mode = get_setting("free_mode", "1") == "1"
    mode_text = "🟢 Mode: Public" if free_mode else "🔒 Mode: Admin-Only"
    b4 = types.InlineKeyboardButton(mode_text, callback_data="adm_toggle_freemode")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(types.InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="owner_panel"))
    markup.add(types.InlineKeyboardButton("« Back to User Menu", callback_data="act_menu"))
    return markup

def show_admin_panel(chat_id: int, user_id: int, edit_msg_id: Optional[int] = None):
    if not is_admin(user_id):
        bot.send_message(chat_id, "❌ <b>ACCESS DENIED:</b> Super Admin privileges required.")
        return

    stats = get_system_stats()
    role_title = "MASTER OWNER" if is_owner(user_id) else "SUB-ADMIN"
    free_mode_str = "🟢 PUBLIC (Open)" if stats['free_mode'] else "🔒 ADMIN-ONLY (Maintenance Mode)"

    panel_text = (
        f"<code>"
        f"┌──────────────────────────┐\n"
        f"│     MARCO & THE DARK     │\n"
        f"│  ★ MASTER ADMIN PANEL ★  │\n"
        f"└──────────────────────────┘\n"
        f"</code>\n"
        f"👑 <b>Access Level:</b> <code>{role_title}</code>\n"
        f"🌐 <b>System Access:</b> {free_mode_str}\n"
        f"<code>────────────────────────────</code>\n"
        f"👥 <b>Registered Users:</b> <code>{stats['total_users']}</code>\n"
        f"🔑 <b>Active Logins:</b> <code>{stats['logged_in']}</code>\n"
        f"⚡ <b>Active Threads:</b> <code>{stats['active_sessions']}</code>\n"
        f"🎮 <b>Total Games:</b> <code>{stats['total_games']}</code>\n"
        f"🚫 <b>Banned Accounts:</b> <code>{stats['banned_users']}</code>\n"
        f"<code>────────────────────────────</code>\n"
        f"<b>⚡ COMMAND SHORTCUTS:</b>\n"
        f"▸ <code>/broadcast [MSG]</code>\n"
        f"▸ <code>/stats</code> · Global stats\n"
        f"▸ <code>/user [ID]</code> · Inspect user\n"
        f"▸ <code>/ban [ID]</code> · Ban user\n"
        f"▸ <code>/unban [ID]</code> · Restore user\n"
        f"▸ <code>/freemode</code> · Public/Admin mode\n"
        + (f"▸ <code>/addadmin [ID]</code>\n▸ <code>/remadmin [ID]</code>\n" if is_owner(user_id) else "")
        + f"<code>────────────────────────────</code>"
    )
    markup = get_admin_keyboard(is_owner(user_id))
    if edit_msg_id:
        safe_edit(chat_id, edit_msg_id, panel_text, reply_markup=markup)
    else:
        bot.send_message(chat_id, panel_text, reply_markup=markup)

def show_user_card(chat_id: int, target_id: int, edit_msg_id: Optional[int] = None):
    u = get_user(target_id)
    if not u:
        text = f"❌ <b>User not found:</b> <code>{target_id}</code>"
        if edit_msg_id:
            safe_edit(chat_id, edit_msg_id, text, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("« Back", callback_data="adm_users")))
        else:
            bot.send_message(chat_id, text)
        return

    banned = is_banned(target_id)
    ban_badge = "🚫 BANNED" if banned else "✅ ACTIVE"
    has_session = "🟢 LOGGED IN" if u.get('cookies') else "⚪ LOGGED OUT"
    role = "OWNER" if is_owner(target_id) else ("ADMIN" if is_admin(target_id) else "USER")

    card_text = (
        f"👤 <b>USER PROFILE INSPECTOR</b>\n"
        f"<code>────────────────────────────</code>\n"
        f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n"
        f"🏷 <b>Name:</b> {safe_html(u.get('name', 'N/A'))}\n"
        f"📱 <b>Phone:</b> +91 {safe_html(u.get('phone', 'N/A'))}\n"
        f"👑 <b>Role:</b> <code>{role}</code>\n"
        f"🔑 <b>Session:</b> {has_session}\n"
        f"🛡 <b>Status:</b> {ban_badge}\n"
        f"🎯 <b>Last Target:</b> <code>{u.get('last_target', 2000)} pts</code>\n"
        f"<code>────────────────────────────</code>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_ban = types.InlineKeyboardButton("🚫 Ban User" if not banned else "✅ Unban User", callback_data=f"adm_bn_{target_id}")
    b_clear = types.InlineKeyboardButton("🗑 Clear Session", callback_data=f"adm_cs_{target_id}")
    markup.add(b_ban, b_clear)
    markup.add(types.InlineKeyboardButton("« Back to Users", callback_data="adm_users"))

    if edit_msg_id:
        safe_edit(chat_id, edit_msg_id, card_text, reply_markup=markup)
    else:
        bot.send_message(chat_id, card_text, reply_markup=markup)

# ── GAME RUNNER & WORKER ──
def launch_game(chat_id: int, user_id: int, user_data: dict, target_score: int, *args, **kwargs):
    with active_lock:
        if user_id in active_games:
            bot.send_message(chat_id, "⚠️ A game session is already running! Stop karne ke liye /stop use karein.", reply_markup=get_playing_keyboard())
            return
        cancel_event = threading.Event()
        active_games[user_id] = cancel_event

    t = threading.Thread(target=_game_worker, args=(chat_id, user_id, user_data, target_score, cancel_event))
    t.daemon = True
    t.start()

def _game_worker(chat_id: int, user_id: int, user_data: dict, target_score: int, cancel_event: threading.Event):
    client = CokeClient(user_data['cookies'])

    stats = client.get_stats() or {}
    plays = stats.get('plays_remaining', 0)
    if plays <= 0:
        bot.send_message(
            chat_id,
            "⚠️ <b>Aaj Ke Saare Lives Khatam Ho Gaye Hain (0/5)!</b>\n\n"
            "🕒 Agle plays <b>Raat 12:00 AM</b> ko refresh honge.\n"
            "Aapka best score aur rank leaderboard par update ho chuka hai.",
            reply_markup=get_main_keyboard(0, user_id)
        )
        with active_lock:
            active_games.pop(user_id, None)
        return

    status_msg = bot.send_message(
        chat_id,
        f"<code>[▸] Starting game for target {target_score} pts (Lives remaining: {plays})...</code>",
        reply_markup=get_playing_keyboard()
    )
    msg_id = status_msg.message_id
    last_edit = 0
    spinner_idx = 0

    def progress_callback(phase, sim, target, elapsed_s, events=None):
        nonlocal last_edit, spinner_idx
        now = time.time()
        if (now - last_edit < 1.5) and (phase not in ["fast_play_done", "submitting"]):
            return
        last_edit = now
        spin = SPINNERS[spinner_idx % len(SPINNERS)]
        spinner_idx += 1

        try:
            if phase == "playing":
                bar = make_progress_bar(sim.score, target, 12)
                pct = int(min(sim.score / max(target, 1), 1.0) * 100)
                cur_tier = get_tier(sim.elapsed_ms)['id']
                text = (
                    f"<code>"
                    f"◤ LIVE MISSION MONITOR ◢\n"
                    f"────────────────────────────\n"
                    f"[⚡] FARMING SCORE {spin}\n"
                    f"Score : {sim.score} / {target} pts\n"
                    f"Prog  : ▕{bar}▏ {pct:>3}%\n"
                    f"Tier  : T{cur_tier} · Combo: x{sim.max_combo}\n"
                    f"Boxes : {len(sim.input_log)} swiped\n"
                    f"Time  : {elapsed_s:.1f}s\n"
                    f"────────────────────────────\n"
                    f"Browser pacing active...\n"
                    f"</code>"
                )
                safe_edit(chat_id, msg_id, text, reply_markup=get_playing_keyboard())

            elif phase == "fast_play_done":
                bar = make_progress_bar(sim.score, target, 12)
                recent_ev = " · ".join(events[-3:]) if events else ""
                text = (
                    f"<code>"
                    f"◤ LIVE MISSION MONITOR ◢\n"
                    f"────────────────────────────\n"
                    f"[✓] TARGET MET {spin}\n"
                    f"Score : {sim.score} / {target} pts\n"
                    f"Prog  : ▕{bar}▏ 100%\n"
                    f"Boxes : {len(sim.input_log)} · Combo: x{sim.max_combo}\n"
                    f"Events: {recent_ev}\n"
                    f"────────────────────────────\n"
                    f"Anti-ban stealth cooldown...\n"
                    f"</code>"
                )
                safe_edit(chat_id, msg_id, text, reply_markup=get_playing_keyboard())

            elif phase == "cooldown":
                ratio = min(elapsed_s / max(target, 1), 1.0)
                bar = make_progress_bar(elapsed_s, target, 12)
                pct = int(ratio * 100)
                remain = max(0.0, target - elapsed_s)
                text = (
                    f"<code>"
                    f"◤ LIVE MISSION MONITOR ◢\n"
                    f"────────────────────────────\n"
                    f"[⌛] STEALTH COOLDOWN {spin}\n"
                    f"Score : {sim.score} pts (Target Met!)\n"
                    f"Time  : {elapsed_s:.1f}s / {target:.0f}s\n"
                    f"Prog  : ▕{bar}▏ {pct:>3}%\n"
                    f"Remain: {remain:.1f}s\n"
                    f"────────────────────────────\n"
                    f"Keeping heartbeats alive...\n"
                    f"</code>"
                )
                safe_edit(chat_id, msg_id, text, reply_markup=get_playing_keyboard())

            elif phase == "submitting":
                text = (
                    f"<code>"
                    f"◤ PAYLOAD SUBMISSION ◢\n"
                    f"────────────────────────────\n"
                    f"[»] Transmitting score {sim.score} pts {spin}\n"
                    f"Uploading signed journey data...\n"
                    f"────────────────────────────\n"
                    f"Verifying with Coke servers...\n"
                    f"</code>"
                )
                safe_edit(chat_id, msg_id, text, reply_markup=get_playing_keyboard())
        except Exception:
            pass

    try:
        res = client.play_game(
            target_score=target_score,
            min_duration_s=DEFAULT_MIN_DURATION_S,
            progress_cb=progress_callback,
            cancel_event=cancel_event
        )

        if not res.get('success'):
            err_msg = res.get('error', 'Failed')
            if "lives" in err_msg.lower():
                friendly_err = (
                    "⚠️ <b>Aaj Ke Saare Lives Khatam Ho Gaye Hain (0/5)!</b>\n\n"
                    "🕒 Agle plays <b>Raat 12:00 AM</b> ko refresh honge.\n"
                    "Aapka best score aur rank leaderboard par update ho chuka hai."
                )
                safe_edit(chat_id, msg_id, friendly_err, reply_markup=get_main_keyboard(0, user_id))
            elif "blocked" in err_msg.lower():
                friendly_err = (
                    "⚠️ <b>Account Notice:</b>\n"
                    "Yeh account campaign cooldown me hai. Kripya doosra number switch karein."
                )
                safe_edit(chat_id, msg_id, friendly_err, reply_markup=get_main_keyboard(0, user_id))
            else:
                safe_edit(chat_id, msg_id, f"<code>[✖] Error: {safe_html(err_msg)}</code>", reply_markup=get_main_keyboard(plays, user_id))
            return

        score = res['score']
        target = res['target']
        combo = res['max_combo']
        dur = res['duration_s']
        rank = f"#{res['rank']}" if res.get('rank') else "UNRANKED"
        verified_tag = "PAYLOAD VERIFIED · UPLOADED TO SERVER" if res.get('verified') else "SUBMISSION COMPLETE"

        breakdown_lines = []
        for btype, count in sorted(res.get('hit_counts', {}).items(), key=lambda x: -x[1]):
            lbl = BOX_ICONS.get(btype, btype)
            bar = "▓" * min(count, 14)
            breakdown_lines.append(f"  {lbl:<13}  {bar} {count}")

        breakdown_text = "\n".join(breakdown_lines)
        rem_plays = res.get('plays_remaining', 0)

        report = (
            f"<b>🏆 MISSION REPORT :: MARCO AUTO-FARM</b>\n"
            f"<code>────────────────────────────</code>\n"
            f"🎯 <b>Final Score :</b> <code>{score} pts</code> (Target: {target})\n"
            f"⚡ <b>Max Combo   :</b> <code>x{combo}</code>\n"
            f"⏱ <b>Runtime     :</b> <code>{dur:.1f}s</code>\n"
            f"🌐 <b>Global Rank :</b> <code>{rank}</code>\n"
            f"<code>────────────────────────────</code>\n"
            f"◈ <b>PAYLOAD BREAKDOWN:</b>\n"
            f"{breakdown_text}\n"
            f"<code>────────────────────────────</code>\n"
            f"✅ <b>{verified_tag}</b>\n\n"
            f"❤️ Lives remaining: <b>{rem_plays} / 5</b>"
        )

        increment_user_games(user_id)
        safe_edit(chat_id, msg_id, report, reply_markup=get_main_keyboard(rem_plays, user_id))

    except Exception as e:
        logger.exception("Game worker exception")
        safe_edit(chat_id, msg_id, f"<code>[✖] Unexpected error: {safe_html(str(e))}</code>", reply_markup=get_main_keyboard())

    finally:
        with active_lock:
            active_games.pop(user_id, None)


# ── CALLBACK QUERY HANDLER ──
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    if is_banned(user_id):
        try:
            bot.answer_callback_query(call.id, "🚫 Account Banned!", show_alert=True)
        except Exception:
            pass
        return

    if not is_admin(user_id) and get_setting("free_mode", "1") == "0":
        try:
            bot.answer_callback_query(call.id, "🔒 Bot is in Maintenance Mode!", show_alert=True)
        except Exception:
            pass
        return

    u = get_user(user_id)
    if not (u and u.get('cookies')):
        if try_recover_session(user_id):
            u = get_user(user_id)

    # Super Admin callbacks
    if data in ["owner_panel", "admin_panel"]:
        show_admin_panel(chat_id, user_id, edit_msg_id=call.message.message_id)
        return

    elif data == "adm_stats":
        stats = get_system_stats()
        text = (
            f"📊 <b>DETAILED SYSTEM ANALYTICS</b>\n"
            f"<code>────────────────────────────</code>\n"
            f"👥 <b>Total Users in DB:</b> <code>{stats['total_users']}</code>\n"
            f"🔑 <b>Users Logged In:</b> <code>{stats['logged_in']}</code>\n"
            f"⚡ <b>Active Threads:</b> <code>{stats['active_sessions']}</code>\n"
            f"🎮 <b>Games Farmed:</b> <code>{stats['total_games']}</code>\n"
            f"👑 <b>Admin Team:</b> <code>{stats['total_admins']}</code>\n"
            f"🚫 <b>Banned Users:</b> <code>{stats['banned_users']}</code>\n"
            f"🌐 <b>Free Mode Status:</b> {'🟢 PUBLIC' if stats['free_mode'] else '🔒 ADMIN-ONLY'}\n"
            f"<code>────────────────────────────</code>"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("« Back to Panel", callback_data="owner_panel"))
        safe_edit(chat_id, call.message.message_id, text, reply_markup=markup)
        return

    elif data == "adm_users":
        users_list = get_all_users(limit=10)
        markup = types.InlineKeyboardMarkup(row_width=1)
        text = "👥 <b>RECENT USERS (Top 10)</b>\n<code>────────────────────────────</code>\n"
        for idx, urow in enumerate(users_list, 1):
            ban_icon = "🚫 " if urow['banned'] else "👤 "
            text += f"{idx}. {ban_icon}<code>{urow['user_id']}</code> | +91 {urow['phone']} | {safe_html(urow['name'])}\n"
            markup.add(types.InlineKeyboardButton(f"Inspect {urow['name']} ({urow['user_id']})", callback_data=f"adm_u_{urow['user_id']}"))
        text += "<code>────────────────────────────</code>\n<i>Tap any user below to manage:</i>"
        markup.add(types.InlineKeyboardButton("« Back to Panel", callback_data="owner_panel"))
        safe_edit(chat_id, call.message.message_id, text, reply_markup=markup)
        return

    elif data.startswith("adm_u_"):
        target_id = int(data.replace("adm_u_", ""))
        show_user_card(chat_id, target_id, edit_msg_id=call.message.message_id)
        return

    elif data.startswith("adm_bn_"):
        target_id = int(data.replace("adm_bn_", ""))
        if target_id == OWNER_ID:
            bot.answer_callback_query(call.id, "Owner cannot be banned!", show_alert=True)
            return
        if is_banned(target_id):
            unban_user(target_id)
            bot.answer_callback_query(call.id, f"User {target_id} unbanned!", show_alert=True)
        else:
            ban_user(target_id)
            bot.answer_callback_query(call.id, f"User {target_id} banned!", show_alert=True)
        show_user_card(chat_id, target_id, edit_msg_id=call.message.message_id)
        return

    elif data.startswith("adm_cs_"):
        target_id = int(data.replace("adm_cs_", ""))
        clear_session(target_id)
        bot.answer_callback_query(call.id, f"Session cleared for {target_id}!", show_alert=True)
        show_user_card(chat_id, target_id, edit_msg_id=call.message.message_id)
        return

    elif data == "adm_toggle_freemode":
        curr = get_setting("free_mode", "1") == "1"
        new_val = "0" if curr else "1"
        set_setting("free_mode", new_val)
        status_text = "🟢 Mode: Public" if new_val == "1" else "🔒 Mode: Admin-Only"
        bot.answer_callback_query(call.id, f"System Access: {status_text}", show_alert=True)
        show_admin_panel(chat_id, user_id, edit_msg_id=call.message.message_id)
        return

    elif data == "adm_bcast_prompt":
        prompt_text = (
            "📢 <b>BROADCAST INSTRUCTIONS</b>\n"
            "<code>────────────────────────────</code>\n"
            "Global broadcast bhejne ke do tarike hain:\n\n"
            "1. <b>Text Message:</b>\n"
            "Chat me likhein:\n"
            "<code>/broadcast Aapka announcement message yahan</code>\n\n"
            "2. <b>Media (Photo / Video / Document):</b>\n"
            "Kisi bhi photo ya video ko reply karke likhein:\n"
            "<code>/broadcast</code>\n"
            "<code>────────────────────────────</code>"
        )
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("« Back to Panel", callback_data="owner_panel"))
        safe_edit(chat_id, call.message.message_id, prompt_text, reply_markup=markup)
        return

    if data == "act_play_2000":
        if u and u.get('cookies'):
            launch_game(chat_id, user_id, u, target_score=2000)
        else:
            execute_login(call.message)



    elif data == "act_target_menu":
        safe_edit(chat_id, call.message.message_id, "🎯 <b>Apna Target Score choose karein:</b>", reply_markup=get_target_keyboard())

    elif data.startswith("set_tgt_"):
        tgt = int(data.replace("set_tgt_", ""))
        update_target(user_id, tgt)
        if u and u.get('cookies'):
            launch_game(chat_id, user_id, u, target_score=tgt)
        else:
            execute_login(call.message)

    elif data in ["act_menu", "act_refresh"]:
        show_profile(call, edit_msg_id=call.message.message_id)

    elif data == "act_login":
        execute_login(call)

    elif data == "act_logout":
        execute_logout(call)

    elif data == "act_stop":
        with active_lock:
            if user_id in active_games:
                active_games[user_id].set()
                bot.send_message(chat_id, "🛑 <b>Game session cancel kar diya gaya hai.</b>", reply_markup=get_main_keyboard())
            else:
                bot.send_message(chat_id, "Koi active game session nahi chal raha.", reply_markup=get_main_keyboard())


# ── COMMAND HANDLERS ──
@bot.message_handler(commands=['start', 'menu', 'help'])
def handle_start_cmd(message: types.Message):
    show_profile(message)



@bot.message_handler(commands=['login'])
def handle_login_cmd(message: types.Message):
    execute_login(message)

@bot.message_handler(commands=['logout'])
def handle_logout_cmd(message: types.Message):
    execute_logout(message)

@bot.message_handler(commands=['stats'])
def handle_stats_cmd(message: types.Message):
    show_profile(message)

@bot.message_handler(commands=['stop'])
def handle_stop_cmd(message: types.Message):
    user_id = message.from_user.id
    with active_lock:
        if user_id in active_games:
            active_games[user_id].set()
            bot.send_message(message.chat.id, "🛑 Stopping game session...", reply_markup=get_main_keyboard())
            return
    bot.send_message(message.chat.id, "No active game currently running.", reply_markup=get_main_keyboard())



# ==============================================================================
# SUPER ADMIN COMMANDS
# ==============================================================================
@bot.message_handler(commands=['admin', 'panel', 'owner'])
def handle_admin_cmd(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>ACCESS DENIED:</b> Super Admin privileges required.", parse_mode="HTML")
        return
    show_admin_panel(message.chat.id, user_id)

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ <b>Unauthorized.</b> Only admins can broadcast.", parse_mode="HTML")
        return

    text = message.text.replace("/broadcast", "", 1).strip()
    is_reply = bool(message.reply_to_message)

    if not is_reply and not text:
        bot.reply_to(
            message,
            "⚠️ <b>Broadcast Usage:</b>\n\n"
            "1. Reply to ANY message/photo/sticker with <code>/broadcast</code>\n"
            "2. Or type: <code>/broadcast Your message text here</code>",
            parse_mode="HTML"
        )
        return

    all_users = get_all_user_ids()
    total = len(all_users)
    status_msg = bot.reply_to(message, f"⏳ <b>Broadcasting to {total} users...</b>", parse_mode="HTML")

    delivered = 0
    failed = 0

    for uid in all_users:
        try:
            if is_reply:
                bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
            else:
                bot.send_message(uid, f"📢 <b>ANNOUNCEMENT:</b>\n\n{safe_html(text)}", parse_mode="HTML")
            delivered += 1
        except Exception:
            failed += 1
        time.sleep(0.04)

    safe_edit(
        message.chat.id,
        status_msg.message_id,
        f"✅ <b>BROADCAST COMPLETED!</b>\n\n"
        f"• Total Targets: <code>{total}</code>\n"
        f"• Successfully Delivered: <code>{delivered}</code>\n"
        f"• Failed / Blocked: <code>{failed}</code>"
    )

@bot.message_handler(commands=['ban', 'unban'])
def handle_ban_unban(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, f"Usage: <code>{parts[0]} [USER_ID]</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
        if target_id == OWNER_ID:
            bot.reply_to(message, "❌ Cannot ban the Bot Owner.")
            return

        if parts[0].lower().startswith("/ban"):
            ban_user(target_id)
            bot.reply_to(message, f"🚫 <b>User <code>{target_id}</code> has been BANNED.</b>", parse_mode="HTML")
        else:
            unban_user(target_id)
            bot.reply_to(message, f"✅ <b>User <code>{target_id}</code> has been UNBANNED.</b>", parse_mode="HTML")
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=['addadmin', 'remadmin'])
def handle_manage_admins(message: types.Message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, "❌ <b>Owner only command.</b>", parse_mode="HTML")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, f"Usage: <code>{parts[0]} [USER_ID]</code>", parse_mode="HTML")
        return

    try:
        target_id = int(parts[1])
        if parts[0].lower().startswith("/addadmin"):
            add_admin(target_id, user_id)
            bot.reply_to(message, f"👑 <b>User <code>{target_id}</code> is now a Sub-Admin.</b>", parse_mode="HTML")
        else:
            remove_admin(target_id)
            bot.reply_to(message, f"✅ <b>User <code>{target_id}</code> removed from Admins.</b>", parse_mode="HTML")
    except ValueError:
        bot.reply_to(message, "❌ Invalid user ID.")

@bot.message_handler(commands=['freemode'])
def handle_freemode_cmd(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    curr = get_setting("free_mode", "1") == "1"
    new_val = "0" if curr else "1"
    set_setting("free_mode", new_val)
    status_str = "🟢 PUBLIC (Open to everyone)" if new_val == "1" else "🔒 ADMIN-ONLY (Maintenance Mode)"
    bot.reply_to(message, f"⚙️ <b>System Access Updated:</b> {status_str}", parse_mode="HTML")

@bot.message_handler(commands=['user', 'info'])
def handle_user_info_cmd(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    parts = message.text.split()
    target_id = None
    if len(parts) > 1 and parts[1].isdigit():
        target_id = int(parts[1])
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        target_id = user_id

    show_user_card(message.chat.id, target_id)

# ── GENERAL MESSAGE HANDLER ──
@bot.message_handler(func=lambda m: True)
def handle_text(message: types.Message):
    try:
        user_id = message.from_user.id
        if is_banned(user_id):
            bot.send_message(message.chat.id, "🚫 <b>ACCESS DENIED:</b> Aapka account banned hai. Super Admin se contact karein.")
            return

        if not is_admin(user_id) and get_setting("free_mode", "1") == "0":
            bot.send_message(message.chat.id, "🔒 <b>MAINTENANCE MODE:</b> Bot filhal Admin-Only mode me hai. Naye users ke liye jald open hoga.")
            return

        raw_text = (message.text or "").strip()

        if raw_text.startswith("/"):
            return

        lower = raw_text.lower()

        if lower in ["logout", "exit", "quit", "log out"]:
            execute_logout(message)
            return

        if lower in ["login", "log in"]:
            execute_login(message)
            return

        if lower in ["stop", "🛑 stop game", "stop game", "cancel"]:
            handle_stop_cmd(message)
            return

        if any(k in lower for k in ["stats", "my stats", "history", "profile", "menu"]):
            show_profile(message)
            return

        u = get_user(user_id)
        if not (u and u.get('cookies')):
            if try_recover_session(user_id):
                u = get_user(user_id)

        clean_digits = re.sub(r"\D", "", raw_text)

        # 1. 10-digit phone number entered -> send OTP
        if (len(clean_digits) == 10) or (len(clean_digits) == 12 and clean_digits.startswith("91")):
            phone = clean_digits[-10:]
            set_pending_phone(user_id, phone)
            msg_wait = bot.send_message(
                message.chat.id,
                f"⏳ Transmitting OTP to <b>+91 {phone}</b> ..."
            )

            client = CokeClient()
            ok, res_msg = client.send_otp(phone)
            if ok:
                safe_edit(
                    message.chat.id,
                    msg_wait.message_id,
                    f"[✔] <b>OTP Dispatched!</b>\n+91 {phone} par 6-digit OTP check karein.\n\n"
                    f"▸ <b>Enter OTP:</b>"
                )
            else:
                safe_edit(
                    message.chat.id,
                    msg_wait.message_id,
                    f"[✖] OTP send failed: {safe_html(res_msg)}\n\n"
                    f"▸ <b>Phone number (10 digits):</b>"
                )
            return

        # 2. User has a pending phone and entered an OTP (4-8 digits)
        pending_phone = u.get('pending_phone') if u else None
        if pending_phone and (4 <= len(clean_digits) <= 8):
            otp = clean_digits
            msg_wait = bot.send_message(
                message.chat.id,
                f"⏳ Verifying OTP for +91 {pending_phone} ..."
            )

            client = CokeClient()
            ok, res_msg, login_data = client.verify_otp(pending_phone, otp)

            if ok and login_data:
                save_session(user_id, login_data['phone'], login_data['name'], login_data['cookies'])
                stats = client.get_stats() or {}
                plays = stats.get('plays_remaining', 0)
                best = stats.get('best_score', 0)
                rank = stats.get('rank')
                rank_str = f"#{rank}" if rank else "UNRANKED"

                confirmed_text = (
                    f"✅ <b>LOGIN SUCCESSFUL!</b>\n"
                    f"<code>────────────────────────────</code>\n"
                    f"👤 <b>Account :</b> <code>{safe_html(login_data['name'])}</code>\n"
                    f"📱 <b>Phone   :</b> <code>+91 {safe_html(login_data['phone'])}</code>\n"
                    f"❤️ <b>Lives   :</b> <code>{plays} / 5</code>\n"
                    f"🏆 <b>Best    :</b> <code>{best} pts</code>\n"
                    f"🌐 <b>Rank    :</b> <code>{rank_str}</code>\n"
                    f"<code>────────────────────────────</code>\n\n"
                    f"🎯 <b>Neeche buttons se game shuru karein:</b>"
                )
                safe_edit(message.chat.id, msg_wait.message_id, confirmed_text, reply_markup=get_main_keyboard(plays))
            else:
                safe_edit(
                    message.chat.id,
                    msg_wait.message_id,
                    f"[✖] OTP verification failed: {safe_html(res_msg)}\n\n"
                    f"▸ <b>Re-enter correct OTP:</b>"
                )
            return

        # 3. User is logged in and entered target score number
        if u and u.get('cookies') and clean_digits.isdigit():
            try:
                target_score = int(clean_digits)
                if target_score < 50:
                    bot.reply_to(message, "Score 50 se bada hona chahiye.", reply_markup=get_main_keyboard())
                    return
                update_target(user_id, target_score)
                launch_game(message.chat.id, user_id, u, target_score)
                return
            except ValueError:
                pass

        # Fallback
        show_profile(message)

    except Exception as e:
        logger.exception("handle_text uncaught error")
        bot.send_message(message.chat.id, f"<code>[✖] Error: {safe_html(str(e))}</code>", reply_markup=get_main_keyboard())


# ==============================================================================
# ENTRY POINT & ALIVE FOREVER RECONNECT LOOP
# ==============================================================================
def main():
    print("=" * 60)
    print("  MARCO & THE DARK  ::  THUNDER AUTO-FARM BOT")
    print("  DIRECT REPLICA + AUTO-RESUME & ALIVE FOREVER v3.5")
    print("=" * 60)

    init_db()

    # Pre-recover session for owner if available
    try_recover_session(8327850869)

    try:
        bot.delete_my_commands()
        bot.set_my_commands([
            telebot.types.BotCommand("start", "Open Dashboard / Profile"),
            telebot.types.BotCommand("admin", "Super Admin Panel (Admin Only)"),
            telebot.types.BotCommand("broadcast", "Broadcast announcement"),
            telebot.types.BotCommand("stop", "Stop active game session"),
            telebot.types.BotCommand("stats", "View account rank & lives"),
            telebot.types.BotCommand("login", "Switch mobile number"),
            telebot.types.BotCommand("logout", "Logout from current account"),
        ])
        print("[✔] Telegram menu commands configured.")
    except Exception as e:
        print(f"[!] Could not set bot commands: {e}")

    try:
        bot_info = bot.get_me()
        print(f"[✔] Telegram Bot Connected: @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        print(f"[!] get_me warning: {e}")

    print(f"[✔] Database: {DB_FILE}")
    print("[✔] Fast polling with auto-recovery activated.")

    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=15, restart_on_change=False)
        except Exception as e:
            logger.error(f"Bot polling interrupted: {e}. Reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
