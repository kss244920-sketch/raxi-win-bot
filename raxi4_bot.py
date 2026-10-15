#!/usr/bin/env python3
# language: Python, file: raxi4_bot.py
# Telegram Bot wrapper for raxi4 / raxi win / Clone Sites Auto-Register
# Supports dynamic referral link auto-detection, invite code extraction, and VITE_API_URL discovery.
# Single & Multi-Registration Workflow + Token System + Admin Suite
# Requirements: pip install pyTelegramBotAPI selenium python-pillow python-numpy requests
# Run: python3 raxi4_bot.py

import os
import re
import sys
import time
import json
import html
import math
import io
import shutil
import gc
import uuid
import glob
import random
import secrets
import base64
import hashlib
import threading
import concurrent.futures
import urllib.parse
from datetime import datetime
from pathlib import Path

from typing import Optional, List, Dict, Set, Any
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import telebot
from telebot import types

# Ensure real-time unbuffered logging
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# ─── Ensure module import paths ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)
for _extra_dir in ["/home/piyush/Downloads/Telegram Desktop", "/home/piyush/Desktop"]:
    if os.path.exists(_extra_dir) and _extra_dir not in sys.path:
        sys.path.append(_extra_dir)

# Import Admin Manager (Jio Bot Architecture + Token Engine)
from admin_manager import admin_manager

# Import High-Performance Proxy Scraper & Health-Checker Daemon
from proxy_manager import proxy_manager

# Import core registration and captcha solver engine
from raxi4_register import (
    SITE,
    API,
    INVITE,
    UA_MOB,
    signed_body,
    solve_slider,
    make_track,
    log
)

# ─── Configuration ───
BOT_TOKEN = "8069923292:AAEAYSJPllY-UmxJzMqubde1NapwFyi0zgs"

def get_persistent_data_dir() -> str:
    jrnm_vol = "/app/data"
    if os.path.exists(jrnm_vol) and os.path.isdir(jrnm_vol):
        return jrnm_vol
    return BASE_DIR

DATA_DIR = get_persistent_data_dir()

def resolve_file(filename: str) -> str:
    p_vol = os.path.join(DATA_DIR, filename)
    if os.path.exists(p_vol):
        return p_vol
    local_p = os.path.join(BASE_DIR, filename)
    if os.path.exists(local_p):
        return local_p
    for alt_dir in ["/home/piyush/Desktop", "/home/piyush/Downloads/Telegram Desktop"]:
        alt_p = os.path.join(alt_dir, filename)
        if os.path.exists(alt_p):
            return alt_p
    return p_vol

ACCOUNTS_FILE = resolve_file("raxi_accounts.txt")
USED_PROXIES_FILE = resolve_file("used_proxies.txt")
CHAT_CONFIGS_FILE = os.path.join(DATA_DIR, "chat_configs.json")
def seed_persistent_file(filename: str):
    dst = os.path.join(DATA_DIR, filename)
    src = os.path.join(BASE_DIR, filename)
    if dst != src and not os.path.exists(dst) and os.path.exists(src):
        try:
            shutil.copy2(src, dst)
        except Exception:
            pass

seed_persistent_file("raxi_accounts.txt")
seed_persistent_file("used_proxies.txt")
seed_persistent_file("sx_config.json")
seed_persistent_file("chat_configs.json")
seed_persistent_file("admin_settings.json")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ─── Channel Force Join Configuration ───
REQUIRED_CHANNEL = "@owabyss"
CHANNEL_URL = "https://t.me/owabyss"

# Global single-message tracking dictionary (chat_id -> message_id)
LAST_BOT_MSG = {}

def send_or_edit(chat_id, text, reply_markup=None, message_id=None, del_incoming=None):
    """
    Guarantees the bot edits the existing message instead of sending new ones!
    Deletes the user's incoming command/link message to keep chat completely clean.
    Gracefully falls back to plain-text rendering if malformed HTML entities are encountered.
    """
    if del_incoming and hasattr(del_incoming, "message_id"):
        try:
            bot.delete_message(chat_id, del_incoming.message_id)
        except Exception:
            pass

    target_mid = message_id or LAST_BOT_MSG.get(chat_id)
    if target_mid:
        try:
            bot.edit_message_text(
                text,
                chat_id=chat_id,
                message_id=target_mid,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            LAST_BOT_MSG[chat_id] = target_mid
            return target_mid
        except Exception as e:
            err_str = str(e).lower()
            if "message is not modified" in err_str:
                return target_mid
            if "can't parse entities" in err_str or "parse mode" in err_str:
                try:
                    bot.edit_message_text(
                        text,
                        chat_id=chat_id,
                        message_id=target_mid,
                        reply_markup=reply_markup,
                        parse_mode=None
                    )
                    LAST_BOT_MSG[chat_id] = target_mid
                    return target_mid
                except Exception as e_plain:
                    err_plain = str(e_plain).lower()
                    if "message is not modified" in err_plain:
                        return target_mid

            # Telegram rate limit / FloodWait: Keep target message ID and skip tick. NEVER spam send_message!
            if "too many requests" in err_str or "retry after" in err_str or "flood" in err_str:
                log(f"[bot] edit_message_text rate limited ({err_str}), skipping tick without sending duplicate message.")
                return target_mid

            # Transient network timeouts or connection glitches: DO NOT send duplicate messages
            if "timed out" in err_str or "timeout" in err_str or "connection" in err_str:
                log(f"[bot] edit_message_text network glitch ({err_str}), keeping existing message.")
                return target_mid

            # Only fallback to send_message if the message was explicitly deleted or un-editable
            log(f"[bot] edit_message_text cannot edit message {target_mid} ({e}), falling back to send_message.")

    try:
        sent = bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        LAST_BOT_MSG[chat_id] = sent.message_id
        return sent.message_id
    except Exception as e:
        err_str = str(e).lower()
        if "can't parse entities" in err_str or "parse mode" in err_str:
            try:
                sent = bot.send_message(
                    chat_id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
                LAST_BOT_MSG[chat_id] = sent.message_id
                return sent.message_id
            except Exception as e2:
                log(f"[bot] send_or_edit fallback error: {e2}")
                return None
        log(f"[bot] send_or_edit error: {e}")
        return None

INDIAN_ISP_POOLS = [
    # Airtel Mobile / Broadband (AS45609, AS24560)
    {"isp": "Airtel", "prefix": "122", "range_b": (160, 180)},
    {"isp": "Airtel", "prefix": "106", "range_b": (192, 220)},
    {"isp": "Airtel", "prefix": "182", "range_b": (64, 79)},
    # Reliance Jio 4G/5G Mobile (AS55836)
    {"isp": "Jio", "prefix": "49", "range_b": (32, 45)},
    {"isp": "Jio", "prefix": "157", "range_b": (32, 60)},
    {"isp": "Jio", "prefix": "47", "range_b": (247, 255)},
    # Vodafone Idea Mobile (AS132335)
    {"isp": "Vi", "prefix": "27", "range_b": (56, 63)},
    {"isp": "Vi", "prefix": "115", "range_b": (96, 110)},
    {"isp": "Vi", "prefix": "152", "range_b": (57, 59)},
    # BSNL Mobile / FTTH (AS9829)
    {"isp": "BSNL", "prefix": "117", "range_b": (192, 245)},
]

SESSION_RESOLVED_IPS = {}
SESSION_LOCK = threading.Lock()

def get_session_masked_ip(session_id: str, resolved_raw_ip: str = None) -> str:
    """
    Returns a unique, masked Indian Mobile exit IP for the session:
    e.g. '122.178.***.17 (IN Mobile)' or '49.36.***.82 (IN Mobile)'
    """
    if resolved_raw_ip and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", str(resolved_raw_ip).strip()):
        parts = str(resolved_raw_ip).strip().split(".")
        return f"{parts[0]}.{parts[1]}.***.{parts[3]} (IN Mobile)"

    with SESSION_LOCK:
        if session_id in SESSION_RESOLVED_IPS:
            return SESSION_RESOLVED_IPS[session_id]

    h = int(hashlib.sha256(str(session_id).encode()).hexdigest(), 16)
    pool = INDIAN_ISP_POOLS[h % len(INDIAN_ISP_POOLS)]
    b_min, b_max = pool["range_b"]
    b = b_min + ((h >> 8) % (b_max - b_min + 1))
    d = 2 + ((h >> 24) % 250)

    masked = f"{pool['prefix']}.{b}.***.{d} (IN Mobile)"
    with SESSION_LOCK:
        SESSION_RESOLVED_IPS[session_id] = masked
    return masked


def mask_proxy(proxy_str: str) -> str:
    """
    Cleans and masks raw proxy strings to remove private credentials, session IDs, and gateway IPs.
    Displays a clean, professional masked IP string with ISP indicator.
    """
    if not proxy_str or proxy_str == "Direct":
        return "Direct"
    s = str(proxy_str).strip()
    for proto in ("http://", "https://", "socks5://", "socks4://"):
        if s.startswith(proto):
            s = s[len(proto):]
            break

    # If it's already a masked Indian Mobile IP or labeled string
    if "(IN Mobile)" in s or "(Residential)" in s:
        # If it accidentally contains the raw SX gateway IP 62.112.8.26, map to dynamic masked IP
        if "62.112.8.26" in s:
            rnd_sess = secrets.token_hex(4)
            return get_session_masked_ip(rnd_sess)
        m = re.match(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(.*)$", s)
        if m:
            parts = m.group(1).split(".")
            return f"{parts[0]}.{parts[1]}.***.{parts[3]}{m.group(2)}"
        return s

    # Handle SX proxy format (contains session-XXXXX)
    if "@" in s:
        user_pass, host = s.split("@", 1)
        sess_m = re.search(r"session-([a-zA-Z0-9]+)", user_pass)
        sess_id = sess_m.group(1) if sess_m else secrets.token_hex(4)
        return get_session_masked_ip(sess_id)

    # If it is the raw SX gateway host alone without auth
    if "62.112.8.26" in s:
        rnd_sess = secrets.token_hex(4)
        return get_session_masked_ip(rnd_sess)

    # Standard IP:Port:User:Pass
    if s.count(":") == 3:
        parts = s.split(":")
        ip = parts[0]
        port = parts[1]
        ip_parts = ip.split(".")
        if len(ip_parts) == 4:
            masked_ip = f"{ip_parts[0]}.{ip_parts[1]}.***.{ip_parts[3]}"
            return f"{masked_ip}:{port}"
        return f"{parts[0]}:{parts[1]}"

    # Standard IP:Port
    if s.count(":") == 1:
        ip, port = s.split(":")
        ip_parts = ip.split(".")
        if len(ip_parts) == 4:
            masked_ip = f"{ip_parts[0]}.{ip_parts[1]}.***.{ip_parts[3]}"
            return f"{masked_ip}:{port}"
        return s

    # Plain IP
    ip_parts = s.split(".")
    if len(ip_parts) == 4:
        return f"{ip_parts[0]}.{ip_parts[1]}.***.{ip_parts[3]}"

    return s

# Concurrency lock to prevent duplicate parallel registrations in same chat with auto-expiration
BUSY_CHATS_LOCK = threading.RLock()
BUSY_LOCK_TIMEOUT = 180.0  # 3 minutes max lock duration
BUSY_CHATS = {}  # chat_id -> timestamp
CUSTOM_REG_STATE = {}  # user_id -> {"step": "phone"|"password", "phone": str, "chat_id": int, "mid": int}
CUSTOM_SPEED_STATE = {}  # user_id -> {"count": int, "chat_id": int, "mid": int, "time": float}
CUSTOM_SCHEDULED_STATE = {}  # user_id -> {"step": "awaiting_count"|"awaiting_minutes", "chat_id": int, "mid": int, "count": int, "time": float}

def is_chat_busy(chat_id: int) -> bool:
    with BUSY_CHATS_LOCK:
        now = time.time()
        last_time = BUSY_CHATS.get(chat_id)
        if last_time is None:
            return False
        if now - last_time > BUSY_LOCK_TIMEOUT:
            BUSY_CHATS.pop(chat_id, None)
            return False
        return True

def acquire_chat_lock(chat_id: int) -> bool:
    with BUSY_CHATS_LOCK:
        now = time.time()
        last_time = BUSY_CHATS.get(chat_id)
        if last_time is not None:
            if now - last_time <= BUSY_LOCK_TIMEOUT:
                return False
        BUSY_CHATS[chat_id] = now
        return True

def refresh_chat_lock(chat_id: int):
    with BUSY_CHATS_LOCK:
        if chat_id in BUSY_CHATS:
            BUSY_CHATS[chat_id] = time.time()

def release_chat_lock(chat_id: int):
    with BUSY_CHATS_LOCK:
        BUSY_CHATS.pop(chat_id, None)

ACTIVE_SESSIONS = {}  # chat_id -> dict
ACTIVE_SESSIONS_LOCK = threading.RLock()

def register_active_session(chat_id: int, user_id: int, count: int, site: str, invite: str, mid: int = None, username: str = ""):
    with ACTIVE_SESSIONS_LOCK:
        ACTIVE_SESSIONS[chat_id] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "username": username or str(user_id),
            "count": count,
            "completed": 0,
            "failed": 0,
            "site": site,
            "invite": invite,
            "start_time": time.time(),
            "message_id": mid,
            "stop_requested": False
        }

def update_active_session(chat_id: int, completed: int = None, failed: int = None, mid: int = None):
    refresh_chat_lock(chat_id)
    with ACTIVE_SESSIONS_LOCK:
        sess = ACTIVE_SESSIONS.get(chat_id)
        if sess:
            if completed is not None:
                sess["completed"] = completed
            if failed is not None:
                sess["failed"] = failed
            if mid is not None:
                sess["message_id"] = mid

def is_session_stop_requested(chat_id: int) -> bool:
    with ACTIVE_SESSIONS_LOCK:
        sess = ACTIVE_SESSIONS.get(chat_id)
        return bool(sess and sess.get("stop_requested"))

def request_stop_session(chat_id: int) -> bool:
    with ACTIVE_SESSIONS_LOCK:
        sess = ACTIVE_SESSIONS.get(chat_id)
        if sess:
            sess["stop_requested"] = True
            return True
        return False

def request_stop_all_sessions() -> int:
    with ACTIVE_SESSIONS_LOCK:
        cnt = 0
        for sess in ACTIVE_SESSIONS.values():
            sess["stop_requested"] = True
            cnt += 1
        return cnt

def unregister_active_session(chat_id: int):
    with ACTIVE_SESSIONS_LOCK:
        return ACTIVE_SESSIONS.pop(chat_id, None)

def get_all_active_sessions() -> list:
    with ACTIVE_SESSIONS_LOCK:
        return [dict(s) for s in ACTIVE_SESSIONS.values()]

MEMBERSHIP_CACHE = {}  # user_id -> (is_member, expire_ts)

def check_user_membership(user_id: int):
    """
    Checks if user is member of REQUIRED_CHANNEL with 10-minute cache.
    Returns: (is_member: bool, reason: str)
    """
    if not user_id:
        return False, "invalid_user"
    if admin_manager.is_admin(user_id):
        return True, "admin_bypass"

    now = time.time()
    cached = MEMBERSHIP_CACHE.get(user_id)
    if cached and cached[1] > now and cached[0]:
        return True, "cached_ok"

    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in ["creator", "administrator", "member", "restricted"]:
            MEMBERSHIP_CACHE[user_id] = (True, now + 600)
            return True, "ok"
        return False, "not_member"
    except Exception as e:
        err_str = str(e).lower()
        if "member list is inaccessible" in err_str or "chat_admin_required" in err_str:
            log(f"[bot] ⚠️ Channel error: Bot lacks Admin privileges in {REQUIRED_CHANNEL} ({e})")
            return False, "bot_not_admin"
        log(f"[bot] Membership check error for {user_id} in {REQUIRED_CHANNEL}: {e}")
        return False, "api_error"

def is_user_member(user_id: int) -> bool:
    """Checks if the user has joined @owabyss channel."""
    is_mem, _ = check_user_membership(user_id)
    return is_mem

# Per-chat dynamic referral config cache:
# chat_id -> {"site": site, "api": api, "invite": invite, "domain": domain}
CHAT_CONFIGS = {}

def load_chat_configs():
    global CHAT_CONFIGS
    try:
        base_p = os.path.join(BASE_DIR, "chat_configs.json")
        if os.path.exists(base_p):
            try:
                with open(base_p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, dict):
                        for k, v in d.items():
                            cid = int(k) if str(k).lstrip("-").isdigit() else k
                            CHAT_CONFIGS[cid] = v
            except Exception as e:
                log(f"[bot] Error reading base chat_configs: {e}")

        if CHAT_CONFIGS_FILE != base_p and os.path.exists(CHAT_CONFIGS_FILE):
            try:
                with open(CHAT_CONFIGS_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, dict):
                        for k, v in d.items():
                            cid = int(k) if str(k).lstrip("-").isdigit() else k
                            CHAT_CONFIGS[cid] = v
            except Exception as e:
                log(f"[bot] Error reading persistent chat_configs: {e}")

        # Ensure both Owner and Prince have active configs, and auto-migrate expired invite
        for uid in (8327850869, 6217522461):
            if uid not in CHAT_CONFIGS or CHAT_CONFIGS[uid].get("invite") in ("265762124632", "12345678901"):
                CHAT_CONFIGS[uid] = {
                    "site": "https://www.dmfirst17.com",
                    "api": "https://api.dmfirst9api.com",
                    "api_type": "webapi",
                    "invite": "417112180491",
                    "domain": "www.dmfirst17.com",
                    "sms_required": False,
                    "switched_mirror": False,
                    "mirrors_scanned": 0
                }
        save_chat_configs()
        log(f"[bot] Loaded and synced {len(CHAT_CONFIGS)} saved chat configs")
    except Exception as e:
        log(f"[bot] Error loading chat_configs: {e}")

def save_chat_configs():
    try:
        data = {str(k): v for k, v in CHAT_CONFIGS.items()}
        for dest in [CHAT_CONFIGS_FILE, os.path.join(BASE_DIR, "chat_configs.json")]:
            try:
                tmp = dest + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp, dest)
            except Exception:
                pass
    except Exception as e:
        log(f"[bot] Error saving chat_configs: {e}")

load_chat_configs()

# Indian mobile operator prefix pool for realistic number generation
INDIAN_PREFIXES = [
    "98", "97", "96", "95", "94", "93", "92", "91", "90",
    "89", "88", "87", "86", "85", "84", "83", "82", "81", "80",
    "79", "78", "77", "76", "75", "74", "73", "72", "70",
    "63", "62"
]

# ─── Dynamic Mobile Device Fingerprint Pool ───
DEVICE_PROFILES = [
    {
        "model": "Samsung Galaxy S24 Ultra",
        "ua": "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Samsung Galaxy S23 5G",
        "ua": "Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "OnePlus 12 5G",
        "ua": "Mozilla/5.0 (Linux; Android 14; CPH2573) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.80 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "OnePlus 11R",
        "ua": "Mozilla/5.0 (Linux; Android 13; CPH2487) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.143 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="121", "Google Chrome";v="121", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Google Pixel 8 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Xiaomi 13 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 13; 2210132G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Redmi Note 13 Pro+",
        "ua": "Mozilla/5.0 (Linux; Android 14; 23090RA98G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.118 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Vivo V29 5G",
        "ua": "Mozilla/5.0 (Linux; Android 13; V2250) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.101 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="121", "Google Chrome";v="121", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Realme GT 5 5G",
        "ua": "Mozilla/5.0 (Linux; Android 13; RMX3820) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.64 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="122", "Google Chrome";v="122", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "iQOO 12 5G",
        "ua": "Mozilla/5.0 (Linux; Android 14; I2220) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.54 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Poco X6 Pro",
        "ua": "Mozilla/5.0 (Linux; Android 14; 2311DRK48G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.40 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="123", "Google Chrome";v="123", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    },
    {
        "model": "Motorola Edge 40",
        "ua": "Mozilla/5.0 (Linux; Android 13; motorola edge 40) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.164 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="121", "Google Chrome";v="121", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    }
]

# ─── Automatic Rotating Proxy Engine (Zero IP Repeat Guarantee + Auto-Scraper Daemon) ───
def mark_proxy_dead(proxy_str):
    proxy_manager.mark_proxy_dead(proxy_str)

def get_used_proxies(domain=None):
    """Returns set of all IPs/proxies ever used for registration."""
    return proxy_manager.get_used_proxies(domain=domain)

def mark_proxy_used(proxy_str, domain=None):
    """Marks proxy as permanently used for the specified website domain."""
    proxy_manager.mark_proxy_used(proxy_str, domain=domain)

def get_next_proxy(exclude=None, domain=None, session_id=None):
    """Returns a completely FRESH, verified working proxy on-demand for this website."""
    return proxy_manager.get_next_proxy(exclude=exclude, domain=domain, session_id=session_id)

def count_working_proxies(domain=None):
    """Returns total available working proxies ready in the pool for this website."""
    return proxy_manager.get_available_count(domain=domain)

def render_progress_bar(done: int, total: int, length: int = 10) -> str:
    """Renders a sleek graphical unicode progress bar."""
    if total <= 0:
        return f"<code>[{'▱' * length}]</code> <b>0%</b>"
    pct = min(100, max(0, int((done / total) * 100)))
    filled = int(length * done // total)
    filled = min(length, max(0, filled))
    bar = "▰" * filled + "▱" * (length - filled)
    return f"<code>[{bar}]</code> <b>{pct}%</b> (<code>{done}/{total}</code>)"

def format_duration(seconds: int) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if mins > 0 or hours > 0 or days > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return " ".join(parts)

def sign_arsaas(body):
    """
    Signature algorithm for AR-SAAS platforms (MaanWin, GoaGames, Tiranga, BigDaddy clones).
    Uses a 12-digit random integer and uppercase MD5 of sorted non-empty keys.
    """
    t = dict(body)
    t.pop("signature", None)
    t.pop("timestamp", None)
    t["random"] = random.randint(100000000000, 999999999999)
    ignored = {"signature", "track", "timestamp"}
    keys = sorted([k for k in t.keys() if t[k] is not None and t[k] != "" and k not in ignored])
    a = {k: (0 if t[k] == 0 else t[k]) for k in keys}
    json_str = json.dumps(a, separators=(",", ":"))
    t["signature"] = hashlib.md5(json_str.encode()).hexdigest().upper()
    t["timestamp"] = int(time.time())
    return t

def detect_and_parse_referral_link(text_or_url):
    """
    Extracts site URL, backend API, invite code, and platform engine type from ANY referral link or text
    (supports raxi4, raxi win, maanwin, 51game, and all clone sites).
    """
    clean_text = text_or_url.strip()
    if not clean_text.startswith("http://") and not clean_text.startswith("https://"):
        if clean_text.startswith("www.") or re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text):
            clean_text = f"https://{clean_text}"

    match = re.search(r"(https?://[^\s\"'<>]+)", clean_text)
    if not match:
        return None

    raw_url = match.group(1).rstrip("/#")
    parsed = urllib.parse.urlparse(raw_url)
    scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"

    # Candidate hosts (test both direct domain and www/non-www alternate)
    candidate_hosts = [parsed.netloc]
    if parsed.netloc.startswith("www."):
        candidate_hosts.append(parsed.netloc[4:])
    elif not parsed.netloc.startswith("www.") and "." in parsed.netloc:
        candidate_hosts.append(f"www.{parsed.netloc}")

    base_site = f"{scheme}://{parsed.netloc}"

    # 1. Extract Invitation Code from URL parameters / fragment / path
    invite_code = None
    inv_match = re.search(r"(?:invitationCode|invitecode|invite_code|r_code|inviteCode|code|invite|c|r)=([A-Za-z0-9]+)", raw_url, re.I)
    if inv_match:
        invite_code = inv_match.group(1)
    else:
        m_trail = re.search(r"/(?:r|register|invite|join)/([A-Za-z0-9]{4,20})(?:[/?#]|$)", raw_url, re.I)
        if m_trail:
            invite_code = m_trail.group(1)
        else:
            m_num = re.search(r"/([0-9]{5,15})(?:[/?#]|$)", raw_url)
            if m_num:
                invite_code = m_num.group(1)

    if not invite_code:
        invite_code = INVITE

    # 2. Check Platform Engine (AR-SAAS vs VITE/WEBAPI)
    # Check 2A: AR-SAAS platform (MaanWin, GoaGames, BigDaddy, Tiranga, 13l.world, etc.)
    for c_host in candidate_hosts:
        c_site = f"{scheme}://{c_host}"
        try:
            r_ar = requests.post(
                f"{c_site}/api/Home/Captcha",
                json=sign_arsaas({}),
                headers={"Origin": c_site, "Referer": f"{c_site}/register", "Content-Type": "application/json;charset=UTF-8"},
                timeout=2.5,
                allow_redirects=True
            )
            if r_ar.status_code == 200 and r_ar.json().get("data", {}).get("captchaId"):
                log(f"[bot] Detected AR-SAAS platform engine for {c_site}")
                return {
                    "site": c_site,
                    "api": f"{c_site}/api",
                    "api_type": "arsaas",
                    "invite": invite_code,
                    "domain": c_host,
                    "raw_url": raw_url,
                    "sms_required": False
                }
        except Exception:
            pass

    # Check 2B: 51game / Raxi / DMFirst clone (VITE / WEBAPI)
    api_url = None
    domain_lower = parsed.netloc.lower()

    # FAST PATH: Instant 0.01ms resolution for known platform families
    if any(k in domain_lower for k in ["raxi", "raxi4", "raxi11", "raxiqaz", "raxiwin"]):
        api_url = "https://api.raxiqaz.com"
    elif any(k in domain_lower for k in ["dmfirst", "dmfirst17", "dmfirst11", "dmfirst9", "dmfirst7"]):
        api_url = "https://api.dmfirst9api.com"
    elif any(k in domain_lower for k in [
        "51game", "51games", "51g",
        "xqtrpv51", "bqrxst51", "dxqwjtkhsyznvrb", "ewjtfy51", "cwyjdz51",
        "ajskdn51", "ybjzsw51", "rxvwpe51", "nxdyhrwjtbzsqvk", "51gamem",
        "nyjkhvztqwxrsbd", "wjyrtdxhnksqzvb", "sjnqyz51", "uyprdm51", "kzqaph51", "fzjnbx51"
    ]):
        api_url = "https://api.api51gameapi.com"
    elif "goabete" in domain_lower:
        api_url = "https://api.goa7777.com"
    else:
        try:
            resp = requests.get(base_site, timeout=3.5, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        except Exception:
            try:
                px = proxy_manager.get_next_proxy()
                px_d = {"http": f"http://{px}", "https": f"http://{px}"} if px else None
                resp = requests.get(base_site, timeout=6.5, proxies=px_d, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            except Exception as e:
                resp = None
                log(f"[bot] Auto-discovery error for {base_site}: {e}")

        if resp and resp.status_code == 200:
            html_text = resp.text

            NON_GAME_DOMAINS = ("google", "firebase", "gstatic", "cloudflare", "microsoft", "apple", "facebook", "sentry", "arbpay", "w3.org", "schema.org", "ampproject", "doubleclick")

            def _is_valid_candidate_api(cand):
                if not cand or not isinstance(cand, str) or not cand.startswith("http"):
                    return False
                low = cand.lower()
                return not any(bad in low for bad in NON_GAME_DOMAINS)

            m_vite = re.search(r'["\'](?:REQUEST_URL|VITE_API_URL|api_url|apiUrl|baseURL)["\']\s*:\s*["\']([^"\']+)["\']', html_text)
            if m_vite and _is_valid_candidate_api(m_vite.group(1)):
                api_url = m_vite.group(1)

            if not api_url:
                for m_dir in re.finditer(r'https?://[a-zA-Z0-9.-]*api[a-zA-Z0-9.-]*\.[a-zA-Z]{2,}', html_text):
                    if _is_valid_candidate_api(m_dir.group(0)):
                        api_url = m_dir.group(0)
                        break

            # If not in index HTML, scan linked JS bundle scripts (Vite/Vue build)
            if not api_url:
                script_srcs = re.findall(r'(?:src=|href=)["\']([^"\']+\.js[^"\']*)["\']', html_text)
                for s_src in script_srcs[:6]:
                    try:
                        s_url = urllib.parse.urljoin(base_site, s_src)
                        s_resp = requests.get(s_url, timeout=4, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                        m_js_vite = re.search(r'["\'](?:REQUEST_URL|VITE_API_URL|api_url|apiUrl|baseURL)["\']\s*:\s*["\']([^"\']+)["\']', s_resp.text)
                        if m_js_vite and _is_valid_candidate_api(m_js_vite.group(1)):
                            api_url = m_js_vite.group(1)
                            break
                        for m_api_match in re.finditer(r'https?://[a-zA-Z0-9.-]*api[a-zA-Z0-9.-]*\.[a-zA-Z]{2,}', s_resp.text):
                            if _is_valid_candidate_api(m_api_match.group(0)):
                                api_url = m_api_match.group(0)
                                break
                        if api_url:
                            break
                    except Exception:
                        pass

    if not api_url:
        if "51" in domain_lower:
            api_url = "https://api.api51gameapi.com"
        else:
            api_url = API

    return {
        "site": base_site,
        "api": api_url,
        "api_type": "webapi",
        "invite": invite_code,
        "domain": parsed.netloc,
        "raw_url": raw_url,
        "sms_required": False
    }

def decode_pwa_domain(raw):
    """Decodes PWA domain string (may be base64-encoded or raw URL)."""
    if not raw or not isinstance(raw, str):
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        if "." in decoded:
            return f"https://{decoded}" if not decoded.startswith("http") else decoded
    except Exception:
        pass
    return f"https://{raw}" if not raw.startswith("http") else raw

def check_platform_sms_and_mirrors(api_url, current_site, api_type=None):
    """
    Checks if target platform requires SMS OTP.
    If required, scans ALL official and candidate platform mirrors in parallel to check if an SMS-free mirror exists.
    Returns:
      sms_required: bool
      site: str
      domain: str
      switched_mirror: bool
      mirror_count: int
      api_type: str
    """
    parsed = urllib.parse.urlparse(current_site)
    if api_type == "arsaas" or "/Home" in str(api_url) or api_url == f"{current_site}/api":
        return {
            "sms_required": False,
            "site": current_site,
            "api": api_url,
            "domain": parsed.netloc,
            "switched_mirror": False,
            "mirror_count": 0,
            "api_type": "arsaas"
        }

    sms_required = False
    try:
        r = requests.post(f"{api_url}/api/webapi/RegisterState", json=signed_body({}), timeout=4)
        if r.status_code == 200:
            data = r.json().get("data", {})
            sms_required = (data.get("isOpenRegisterSMS") == "1")
    except Exception as e:
        log(f"[bot] RegisterState check error for {api_url}: {e}")

    if not sms_required:
        return {
            "sms_required": False,
            "site": current_site,
            "api": api_url,
            "domain": parsed.netloc,
            "switched_mirror": False,
            "mirror_count": 0,
            "api_type": "webapi"
        }

    # If SMS OTP is ON, scan ALL official and candidate platform mirrors in parallel
    candidates = set()

    # 1. Fetch dynamic mirrors from platform PWA domain endpoint
    try:
        r_pwa = requests.post(f"{api_url}/api/webapi/GetPwaDomainList", json=signed_body({}), timeout=4)
        if r_pwa.status_code == 200:
            raw_mirrors = r_pwa.json().get("data", [])
            if isinstance(raw_mirrors, list):
                for raw_d in raw_mirrors:
                    clean = decode_pwa_domain(raw_d)
                    if clean:
                        candidates.add(clean)
    except Exception as e:
        log(f"[bot] GetPwaDomainList error: {e}")

    # 2. Add complete known mirror catalog for platform families
    domain_lower = parsed.netloc.lower()
    if "51" in domain_lower or "51game" in api_url:
        for i in range(1, 16):
            candidates.add(f"https://51game{i}.com")
            candidates.add(f"https://www.51game{i}.com")
        candidates.add("https://51game.com")
        candidates.add("https://www.51game.com")
        candidates.add("https://51gamem.com")
        candidates.add("https://www.51gamem.com")
        candidates.add("https://51games.org")
        candidates.add("https://51games.app")
        for pwa_slug in [
            "rxvwpe51", "ewjtfy51", "nyjkhvztqwxrsbd", "wjyrtdxhnksqzvb",
            "sjnqyz51", "uyprdm51", "kzqaph51", "fzjnbx51", "xqtrpv51",
            "bqrxst51", "dxqwjtkhsyznvrb", "cwyjdz51", "ajskdn51", "ybjzsw51", "nxdyhrwjtbzsqvk"
        ]:
            candidates.add(f"https://www.{pwa_slug}.com")
            candidates.add(f"https://{pwa_slug}.com")
    elif "raxi" in domain_lower:
        for slug in ["raxi4", "raxiwin", "raxi11", "raxiqaz"]:
            candidates.add(f"https://www.{slug}.com")
            candidates.add(f"https://{slug}.com")

    # 3. High-Speed Concurrent Mirror Scanner (Parallel verification)
    def test_single_mirror(mirror_url):
        try:
            # Quick 1.8s ping to verify host is alive
            r_ping = requests.get(mirror_url, timeout=1.8, headers={"User-Agent": "Mozilla/5.0"})
            if r_ping.status_code != 200:
                return None

            m_info = detect_and_parse_referral_link(mirror_url)
            if not m_info or not m_info.get("api"):
                return None
            m_api = m_info["api"]
            # Prevent false cross-platform fallback
            if m_api == API and api_url != API:
                return None

            r_m = requests.post(f"{m_api}/api/webapi/RegisterState", json=signed_body({}), timeout=2.0)
            if r_m.status_code == 200:
                d_m = r_m.json().get("data", {})
                is_sms = (d_m.get("isOpenRegisterSMS") == "1")
                return (mirror_url, m_api, is_sms)
        except Exception:
            pass
        return None

    live_scanned = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(test_single_mirror, candidates))

    for item in results:
        if item is not None:
            live_scanned += 1
            m_url, m_api, is_sms = item
            if not is_sms:
                log(f"[bot] Found SMS-free mirror out of {live_scanned} live mirrors: {m_url} (API: {m_api})")
                parsed_m = urllib.parse.urlparse(m_url)
                return {
                    "sms_required": False,
                    "site": m_url,
                    "api": m_api,
                    "domain": parsed_m.netloc,
                    "switched_mirror": True,
                    "mirror_count": live_scanned,
                    "api_type": "webapi"
                }

    log(f"[bot] Scanned {live_scanned} live mirrors across platform - all require SMS OTP.")
    return {
        "sms_required": True,
        "site": current_site,
        "api": api_url,
        "domain": parsed.netloc,
        "switched_mirror": False,
        "mirror_count": live_scanned,
        "api_type": "webapi"
    }

def send_sms_otp(api_url, phone_10_digit, site_url=None):
    """
    Triggers SMS OTP using official platform webapi or AR-SAAS SendVerifiyCode.
    phone_10_digit: 10-digit Indian mobile number
    Returns (ok: bool, msg: str)
    """
    try:
        full_phone = f"91{phone_10_digit}"
        if "/Home" in str(api_url) or (site_url and api_url == f"{site_url}/api"):
            target = f"{site_url}/api/Home/SendVerifiyCode"
            payload = sign_arsaas({"verifyCodeType": 1, "phoneOrEmail": full_phone, "codeType": 1})
            headers = {"Origin": site_url, "Referer": f"{site_url}/register", "Content-Type": "application/json;charset=UTF-8"}
            r = requests.post(target, json=payload, headers=headers, timeout=6)
        else:
            payload = {"phone": full_phone, "codeType": 1}
            r = requests.post(f"{api_url}/api/webapi/SmsVerifyCode", json=signed_body(payload), timeout=6)

        if r.status_code == 200:
            j = r.json()
            code = j.get("code")
            msg = j.get("msg") or ""
            if code == 0 or "success" in msg.lower() or "succeed" in msg.lower():
                return True, "SMS sent successfully"
            return False, msg or f"Error code {code}"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)

def get_chat_config(chat_id):
    """Returns current active configuration for the given chat ID."""
    if chat_id not in CHAT_CONFIGS:
        CHAT_CONFIGS[chat_id] = {
            "site": SITE,
            "api": API,
            "api_type": "webapi",
            "invite": INVITE,
            "domain": urllib.parse.urlparse(SITE).netloc,
            "sms_required": False,
            "switched_mirror": False,
            "mirrors_scanned": 0
        }
    if "api_type" not in CHAT_CONFIGS[chat_id]:
        CHAT_CONFIGS[chat_id]["api_type"] = "webapi"
    return CHAT_CONFIGS[chat_id]

def generate_random_phone():
    """Generates a realistic 10-digit Indian phone number."""
    prefix = random.choice(INDIAN_PREFIXES)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return f"{prefix}{suffix}"

def generate_random_password():
    """Generates an 8-character alphanumeric password satisfying site requirements."""
    chars_letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    chars_digits = "23456789"
    p_letters = "".join(random.choices(chars_letters, k=4))
    p_digits = "".join(random.choices(chars_digits, k=4))
    return f"{p_letters}{p_digits}"

ACCOUNT_SAVE_LOCK = threading.Lock()

def save_account_to_file(phone, password, uid, token, invite, site="https://www.raxi4.com", device=None, proxy=None, creator_id=None):
    """Saves successfully created account to raxi_accounts.txt with creator isolation and thread safety."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dev = device or "Generic Android"
    ip = proxy or "Direct"
    c_str = f" | User: {creator_id}" if creator_id else ""
    entry = f"[{ts}] UID: {uid} | Phone: {phone} | Password: {password} | Device: {dev} | IP: {ip} | Invite: {invite} | Site: {site}{c_str} | Token: {token}\n"
    dests = [
        ACCOUNTS_FILE,
        os.path.join(DATA_DIR, "raxi_accounts.txt"),
        os.path.join(BASE_DIR, "raxi_accounts.txt"),
        "/home/piyush/Desktop/raxi_accounts.txt",
        "/home/piyush/Downloads/Telegram Desktop/raxi_accounts.txt"
    ]
    seen_dests = set()
    with ACCOUNT_SAVE_LOCK:
        for dest in dests:
            if dest in seen_dests:
                continue
            seen_dests.add(dest)
            try:
                with open(dest, "a", encoding="utf-8") as f:
                    f.write(entry)
            except Exception:
                pass

def get_accounts_file():
    """Finds the active accounts file from candidate paths."""
    for candidate in [
        os.path.join(DATA_DIR, "raxi_accounts.txt"),
        ACCOUNTS_FILE,
        os.path.join(BASE_DIR, "raxi_accounts.txt"),
        "/app/data/raxi_accounts.txt",
        "/home/piyush/Desktop/raxi_accounts.txt",
        "/home/piyush/Downloads/Telegram Desktop/raxi_accounts.txt"
    ]:
        if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
            return candidate
    return None

def parse_account_records(lines):
    """Parses raw account log lines into structured account dictionaries."""
    records = []
    for l in lines:
        if not l.strip() or l.startswith("#"):
            continue
        rec = {}
        ts_m = re.search(r"\[(.*?)\]", l)
        rec["time"] = ts_m.group(1).strip() if ts_m else ""
        uid_m = re.search(r"UID:\s*(\S+)", l)
        rec["uid"] = uid_m.group(1).strip() if uid_m else ""
        ph_m = re.search(r"Phone:\s*(\S+)", l)
        rec["phone"] = ph_m.group(1).strip() if ph_m else ""
        pw_m = re.search(r"Password:\s*(\S+)", l)
        rec["password"] = pw_m.group(1).strip() if pw_m else ""
        dev_m = re.search(r"Device:\s*([^|]+)", l)
        rec["device"] = dev_m.group(1).strip() if dev_m else ""
        ip_m = re.search(r"IP:\s*(\S+)", l)
        rec["ip"] = ip_m.group(1).strip() if ip_m else ""
        inv_m = re.search(r"Invite:\s*(\S+)", l)
        rec["invite"] = inv_m.group(1).strip() if inv_m else ""
        site_m = re.search(r"Site:\s*([^|]+)", l)
        rec["site"] = site_m.group(1).strip() if site_m else ""
        usr_m = re.search(r"User:\s*(\S+)", l)
        rec["user"] = usr_m.group(1).strip() if usr_m else ""
        tok_m = re.search(r"Token:\s*(\S+)", l)
        rec["token"] = tok_m.group(1).strip() if tok_m else ""
        if rec["phone"] and rec["password"]:
            records.append(rec)
    return records

def get_user_account_records(user_id, chat_id=None):
    """Retrieves and parses account records accessible to this user."""
    acc_file = get_accounts_file()
    if not acc_file:
        return []
    try:
        with open(acc_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = [l for l in f if l.strip()]
        all_recs = parse_account_records(lines)
        if admin_manager.is_admin(user_id):
            return all_recs

        cfg = get_chat_config(chat_id) if chat_id else {}
        curr_invite = str(cfg.get("invite", "")).strip()
        filtered = [
            r for r in all_recs
            if r.get("user") == str(user_id) or (curr_invite and r.get("invite") == curr_invite)
        ]
        return filtered
    except Exception as e:
        log(f"[bot] Error reading user account records: {e}")
        return []

def show_export_menu(chat_id, user, message_id=None):
    """Interactive export menu offering Combos (phone:pass), Full Report, or Both."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    if not is_user_member(user_id):
        user_info = admin_manager.user_registry.get(str(user_id), {"first_name": "User"})
        show_force_join_screen(chat_id, type('UserObj', (), {'id': user_id, 'first_name': user_info.get('first_name', 'User')})(), message_id=message_id)
        return

    recs = get_user_account_records(user_id, chat_id)
    total_accs = len(recs)
    cfg = get_chat_config(chat_id)

    if total_accs == 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
        send_or_edit(
            chat_id,
            "📭 <b>No Accounts Available for Export</b>\n\n"
            "Abhi tak koi accounts register nahi huye hain. Pehle Single ya Multi-Registration run karein.",
            reply_markup=markup,
            message_id=message_id
        )
        return

    text = (
        f"📋 <b>Accounts Export Hub</b>\n\n"
        f"• 📊 <b>Available Accounts:</b> <code>{total_accs} Accounts</code>\n"
        f"• 🌐 <b>Current Platform:</b> <code>{cfg['site']}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n\n"
        f"Apna pasandida export format choose karein:\n\n"
        f"• 📱 <b>Phone:Pass Combos:</b>\n"
        f"  Clean <code>phone:password</code> list — checkers &amp; account loaders ke liye direct ready.\n\n"
        f"• 📑 <b>Full Detailed Report:</b>\n"
        f"  Structured audit table with Phone, Password, UID, Device, IP, Invite, Site &amp; Date.\n\n"
        f"• 📦 <b>Download Both:</b> Dono files ek sath send hongi."
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("📱 Phone:Pass Combos", callback_data="do_export_combos")
    b2 = types.InlineKeyboardButton("📑 Full Report (.txt)", callback_data="do_export_full")
    b3 = types.InlineKeyboardButton("📦 Download Both Files", callback_data="do_export_both")
    b4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    markup.add(b1, b2)
    markup.add(b3)
    markup.add(b4)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)

def send_exported_combos(chat_id, user_id):
    """Sends clean Phone:Password combo file."""
    import io
    recs = get_user_account_records(user_id, chat_id)
    if not recs:
        bot.send_message(chat_id, "📭 <i>Koi accounts nahi mile export ke liye.</i>", parse_mode="HTML")
        return

    lines = [f"{r['phone']}:{r['password']}" for r in recs if r.get('phone') and r.get('password')]
    content = "\n".join(lines).encode("utf-8")

    bio = io.BytesIO(content)
    bio.name = f"combos_{user_id}.txt"
    caption = (
        f"📱 <b>Phone:Password Combos Export</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 📊 <b>Total Combos:</b> <code>{len(lines)}</code>\n"
        f"• 🔑 <b>Format:</b> <code>phone:password</code>\n"
        f"• 💡 <i>Directly usable in account checkers &amp; automation tools.</i>"
    )
    bot.send_document(chat_id, bio, caption=caption, parse_mode="HTML")

def send_exported_full_report(chat_id, user_id):
    """Sends comprehensive structured audit report."""
    import io
    recs = get_user_account_records(user_id, chat_id)
    if not recs:
        bot.send_message(chat_id, "📭 <i>Koi accounts nahi mile export ke liye.</i>", parse_mode="HTML")
        return

    cfg = get_chat_config(chat_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "================================================================================",
        "RAXI AUTOMATION - REGISTERED ACCOUNTS MASTER AUDIT REPORT",
        f"Generated: {now_str} | Total Accounts: {len(recs)}",
        f"Target Site: {cfg.get('site', 'N/A')} | Invite Code: {cfg.get('invite', 'N/A')}",
        "================================================================================\n",
        "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
    ]
    for idx, r in enumerate(recs, 1):
        report_lines.append(f"[{idx}] {r['phone']}:{r['password']}")
    report_lines.append("\n================================================================================")
    report_lines.append("--- [DETAILED ACCOUNT RECORDS] ---")
    report_lines.append("================================================================================\n")

    for idx, r in enumerate(recs, 1):
        clean_ip = mask_proxy(r.get('ip', 'Direct'))
        report_lines.append(f"[{idx}] 📱 Phone:    {r.get('phone', 'N/A')}")
        report_lines.append(f"    🔑 Password: {r.get('password', 'N/A')}")
        report_lines.append(f"    🆔 UID:      {r.get('uid', 'N/A')}")
        report_lines.append(f"    📱 Device:   {r.get('device', 'N/A')}")
        report_lines.append(f"    🌐 Proxy IP: {clean_ip}")
        report_lines.append(f"    🌐 Site:     {r.get('site', 'N/A')}")
        report_lines.append(f"    🎟️ Invite:   {r.get('invite', 'N/A')}")
        report_lines.append(f"    🕒 Time:     {r.get('time', 'N/A')}")
        report_lines.append("-" * 60)

    content = "\n".join(report_lines).encode("utf-8")
    bio = io.BytesIO(content)
    bio.name = f"accounts_report_{user_id}.txt"
    caption = (
        f"📑 <b>Master Accounts Report Export (.txt)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 📊 <b>Total Accounts:</b> <code>{len(recs)}</code>\n"
        f"• 🌐 <b>Site:</b> <code>{cfg.get('site', 'N/A')}</code>\n"
        f"• 📝 Includes: Combos + Detailed Table + Device &amp; Proxy Audit logs."
    )
    bot.send_document(chat_id, bio, caption=caption, parse_mode="HTML")

def send_exported_both(chat_id, user_id):
    """Sends both Combos and Full Report documents."""
    send_exported_combos(chat_id, user_id)
    send_exported_full_report(chat_id, user_id)

def send_exported_accounts(chat_id, user_id):
    """Maintains backward compatibility by launching the full report."""
    send_exported_full_report(chat_id, user_id)

def count_saved_accounts():
    total = 0
    accounts_file = get_accounts_file()
    if accounts_file:
        try:
            with open(accounts_file, "r", encoding="utf-8") as f:
                total = sum(1 for line in f if line.strip() and not line.strip().startswith("#"))
        except Exception:
            pass
    return total

# ═══════════════════════════════════════════════════════════════════════════
#  CORE REGISTRATION WORKER
# ═══════════════════════════════════════════════════════════════════════════

def auto_register_account(phone=None, password=None, invite=None, site=None, api=None, max_search_attempts=8, creator_id=None, smsvcode="", api_type=None, session_id=None):
    """
    Registers a new account with dynamic phone, password, device profile, and proxy rotation.
    Automatically supports both AR-SAAS (MaanWin, GoaGames, etc.) and VITE/WEBAPI (51game, Raxi).
    Supports smsvcode for OTP verification.
    """
    target_site = site or SITE
    target_api = api or API
    target_invite = invite or INVITE
    domain = urllib.parse.urlparse(target_site).netloc

    is_arsaas = (api_type == "arsaas") or ("/Home" in str(target_api)) or (target_api == f"{target_site}/api") or ("maanwin" in domain)

    is_auto = (phone is None)
    last_error = "Unknown error"

    tried_proxies = set()
    account_session_id = session_id or secrets.token_hex(6)
    for attempt in range(1, max_search_attempts + 1):
        if attempt > 1 and proxy_manager.is_sx_active():
            account_session_id = secrets.token_hex(6)
        target_phone = phone if not is_auto else generate_random_phone()
        target_pwd = password if password else generate_random_password()
        if is_arsaas and len(target_pwd) < 8:
            target_pwd = f"{target_pwd}1234"

        dev_profile = random.choice(DEVICE_PROFILES)
        dev_model = dev_profile["model"]
        dev_ua = dev_profile["ua"]
        device_id = secrets.token_hex(16)

        active_proxy = get_next_proxy(exclude=tried_proxies, domain=domain, session_id=account_session_id)
        if not active_proxy and attempt == 1:
            time.sleep(1.5)
            active_proxy = get_next_proxy(exclude=tried_proxies, domain=domain, session_id=account_session_id)
        if not active_proxy and "Direct" not in tried_proxies:
            active_proxy = None  # fallback to Direct only once if pool has no candidate

        if active_proxy:
            tried_proxies.add(active_proxy)
        else:
            tried_proxies.add("Direct")
        proxy_label = active_proxy if active_proxy else "Direct"

        log(f"[bot] Register attempt {attempt}/{max_search_attempts} (engine={'AR-SAAS' if is_arsaas else 'WEBAPI'}): phone={target_phone} dev='{dev_model}' proxy={proxy_label}")

        session = requests.Session()
        session.verify = False
        session.headers.update({
            "User-Agent": dev_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/json;charset=UTF-8",
            "Ar-Origin": target_site,
            "Origin": target_site,
            "Referer": f"{target_site}/register" if is_arsaas else f"{target_site}/",
            "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
            "sec-ch-ua": dev_profile["sec_ch_ua"],
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": dev_profile["platform"],
        })
        if active_proxy:
            if "@" in active_proxy:
                px_url = f"http://{active_proxy}"
            elif active_proxy.count(":") == 3:
                parts = active_proxy.split(":")
                px_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                px_url = f"http://{active_proxy}"
            session.proxies = {"http": px_url, "https": px_url}

        # 1. Smart-Save Captcha Fetch (0 KB proxy data if direct works, fallback to residential proxy if blocked)
        cid, bg_b64, sl_b64 = None, None, None
        last_cap_status = None
        try:
            if is_arsaas:
                cap_url = f"{target_site}/api/Home/Captcha"
                cap_payload = sign_arsaas({})
            else:
                cap_url = f"{target_api}/api/webapi/Captcha"
                cap_payload = signed_body({})

            # Step 1A: Attempt direct fetch first (Zero residential proxy data consumed)
            try:
                direct_session = requests.Session()
                direct_session.verify = False
                direct_session.headers.update(session.headers)
                r_cap = direct_session.post(cap_url, json=cap_payload, timeout=(3.0, 4.5))
                last_cap_status = r_cap.status_code
                if r_cap.status_code == 200:
                    cdata = r_cap.json().get("data") or {}
                    cid = cdata.get("captchaId")
                    bg_b64 = cdata.get("backgroundImage")
                    sl_b64 = cdata.get("sliderImage")
            except Exception:
                pass

            # Step 1B: If direct was blocked (Cloudflare 429/timeout), fallback to residential proxy
            if not cid or not bg_b64 or not sl_b64:
                if active_proxy:
                    r_cap = session.post(cap_url, json=cap_payload, timeout=(5.0, 7.5))
                    last_cap_status = r_cap.status_code
                    cdata = r_cap.json().get("data") or {}
                    cid = cdata.get("captchaId")
                    bg_b64 = cdata.get("backgroundImage")
                    sl_b64 = cdata.get("sliderImage")
        except Exception as e:
            log(f"[bot] Captcha fetch error: {e}")
            last_error = f"Captcha connection error: {str(e)[:80]}"
            time.sleep(0.2)
            continue

        if not cid or not bg_b64 or not sl_b64:
            log(f"[bot] Captcha returned empty data (status={last_cap_status})")
            last_error = "Captcha returned empty data"
            time.sleep(0.2)
            continue

        # 2. Solve slider puzzle via native PIL + NumPy contour matching
        try:
            container_x, score = solve_slider(bg_b64, sl_b64)
            track = make_track(container_x)
        except Exception as exc:
            log(f"[bot] Slider solver error: {exc}")
            container_x = random.randint(110, 210)
            track = make_track(container_x)

        # 3. Submit Register POST - Reliable 4.5s connect, 7.0s read
        if is_arsaas:
            reg_url = f"{target_site}/api/Home/Register"
            reg_dict = {
                "loginType": "Mobile",
                "userName": f"91{target_phone}",
                "password": target_pwd,
                "inviteCode": target_invite,
                "code": smsvcode or "",
                "captchaId": cid,
                "track": track
            }
            reg_payload = sign_arsaas(reg_dict)
        else:
            reg_url = f"{target_api}/api/webapi/Register"
            reg_dict = {
                "username": f"91{target_phone}",
                "smsvcode": smsvcode or "",
                "registerType": "mobile",
                "pwd": target_pwd,
                "invitecode": target_invite,
                "packId": "",
                "domainurl": domain,
                "phonetype": 1,
                "captchaId": cid,
                "track": track,
                "deviceId": device_id,
            }
            reg_payload = signed_body(reg_dict)

        try:
            r = session.post(reg_url, json=reg_payload, timeout=(4.5, 7.0))
            j = r.json()
        except Exception as e:
            log(f"[bot] Proxy {proxy_label} Register POST error: {e}")
            if active_proxy:
                mark_proxy_dead(active_proxy)
            last_error = f"Register POST error via {proxy_label}: {str(e)[:80]}"
            time.sleep(0.2)
            continue

        code = j.get("code")
        msg = j.get("msg")
        msg_code = j.get("msgCode")

        log(f"[bot] Result: code={code}, msgCode={msg_code}, msg={msg}")

        # Success!
        if code == 0 and j.get("data"):
            d = j["data"]
            token = d.get("token")
            uid = d.get("userId") or None
            if not uid and token:
                try:
                    part = token.split(".")[1]
                    part += "=" * (-len(part) % 4)
                    decoded = json.loads(base64.urlsafe_b64decode(part))
                    uid = decoded.get("UserId")
                except Exception:
                    pass

            resolved_ip = None
            if active_proxy:
                try:
                    r_ip = session.get("https://api.ipify.org?format=json", timeout=1.0)
                    if r_ip.status_code == 200:
                        resolved_ip = r_ip.json().get("ip")
                except Exception:
                    pass
            record_proxy = get_session_masked_ip(account_session_id, resolved_raw_ip=resolved_ip) if active_proxy else "Direct"

            save_account_to_file(target_phone, target_pwd, uid, token, target_invite, target_site, device=dev_model, proxy=record_proxy, creator_id=creator_id)
            if active_proxy:
                mark_proxy_used(active_proxy, domain=domain)

            return {
                "ok": True,
                "phone": target_phone,
                "password": target_pwd,
                "uid": uid,
                "token": token,
                "invite": target_invite,
                "site": target_site,
                "proxy": record_proxy,
                "device": dev_model
            }

        # If phone is already registered and in auto-mode, pick another number
        if (msg_code in (111, 5033) or "already registered" in str(msg).lower()) and is_auto:
            log("[bot] Number already registered, picking another...")
            last_error = "Number already registered"
            time.sleep(0.2)
            continue

        if (msg_code in (111, 5033) or "already registered" in str(msg).lower()) and not is_auto:
            return {"ok": False, "phone": target_phone, "msg": "Phone number is already registered"}

        # Captcha verification failed -> retry
        if msg_code in (31, 143, 5008) or "captcha" in str(msg).lower() or "verification failed" in str(msg).lower():
            log("[bot] Captcha verification failed, retrying...")
            last_error = f"Captcha verification failed ({msg})"
            time.sleep(0.2)
            continue

        # If server blocks operation or rate limits this proxy / IP forbidden (Code 114)
        if (
            msg_code in (2, 8, 13, 114)
            or "frequently" in str(msg).lower()
            or "forbidden" in str(msg).lower()
            or "the ip has been" in str(msg).lower()
            or "ip blocked" in str(msg).lower()
            or "limit" in str(msg).lower()
        ):
            is_forbidden = (
                msg_code == 114
                or "the ip has been" in str(msg).lower()
                or "forbidden" in str(msg).lower()
            )
            if is_forbidden:
                log(f"[bot] Proxy {proxy_label} permanently forbidden on {domain} ({msg}), marking burned for domain...")
                if active_proxy:
                    proxy_manager.mark_proxy_used(active_proxy, domain=domain)
                    proxy_manager.mark_proxy_cooldown(active_proxy, domain=domain, duration=300)
            else:
                log(f"[bot] Proxy {proxy_label} flagged by server ({msg}), placing on domain cooldown...")
                if active_proxy:
                    proxy_manager.mark_proxy_cooldown(active_proxy, domain=domain, duration=300)
            last_error = f"{msg} (code {msg_code})"
            time.sleep(0.3)
            continue

        # If invite code is expired or does not exist (Code 1002, 110)
        if (
            msg_code in (110, 1002)
            or "expired" in str(msg).lower()
            or "invitor not existed" in str(msg).lower()
            or "invitecode" in str(msg).lower()
            or "invite code" in str(msg).lower()
        ):
            log(f"[bot] Target site rejected invite code: {msg} (code={code}, msgCode={msg_code})")
            return {
                "ok": False,
                "fatal": True,
                "msg": f"Invite Code Expired / Invalid ({msg})"
            }

        # If site strictly requires SMS OTP (e.g. 51game)
        if msg_code == 106 or "sms" in str(msg).lower():
            log(f"[bot] Target site requires mandatory SMS OTP: {msg}")
            return {
                "ok": False,
                "fatal": True,
                "msg": f"SMS Verification Required: This platform enforces SMS OTP ({msg}). Registration cannot proceed without real SMS OTP."
            }

        last_error = msg or f"Error code {code}"
        time.sleep(0.2)

    return {"ok": False, "msg": f"Could not register after rotating multiple IPs ({last_error}). Please try again."}


# ═══════════════════════════════════════════════════════════════════════════
#  NEW WORKFLOW UI SCREENS (Link Prompt -> Single / Multi Buttons)
# ═══════════════════════════════════════════════════════════════════════════

def show_force_join_screen(chat_id, user, message_id=None, del_incoming=None):
    """Displays Force Join screen requiring membership in @owabyss."""
    first_name = html.escape(user.first_name if user else "User")

    text = (
        f"👋 <b>Namaste {first_name}!</b>\n\n"
        f"📢 <b>Channel Join Required!</b>\n"
        f"Bot ka use karne ke liye aapko hamara official channel join karna hoga:\n\n"
        f"👉 <b>Channel:</b> @owabyss\n\n"
        f"1️⃣ Niche <b>📢 Join @owabyss</b> button par click karke channel join karein.\n"
        f"2️⃣ Join karne ke baad <b>🔄 Verify Membership</b> button dabayein.\n\n"
        f"⚡ <i>Verification ke baad bot automatic unlock ho jayega!</i>"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    b_join = types.InlineKeyboardButton("📢 Join @owabyss", url=CHANNEL_URL)
    b_verify = types.InlineKeyboardButton("🔄 Verify Membership", callback_data="verify_join")
    markup.add(b_join, b_verify)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def show_link_prompt(chat_id, user, message_id=None, del_incoming=None):
    """Displays the link prompt screen asking for the platform URL."""
    user_id = user.id if user else chat_id
    first_name = html.escape(user.first_name if user else "User")
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    text = (
        f"👋 <b>Welcome {first_name}!</b>\n\n"
        f"👤 <b>User:</b> {first_name} | 🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🎫 <b>Tokens:</b> <b>{tokens_disp}</b>\n\n"
        f"🌐 <b>Current Target Site:</b> <code>{cfg['site']}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n\n"
        f"🔗 <b>Please send your Platform Referral Link / URL:</b>\n"
        f"Aap jis bhi platform ya website par registration karna chahte hain, uska <b>referral link</b> yahan chat me paste karein. "
        f"Bot automatically official backend API, mirrors, aur SMS requirement discover kar lega.\n\n"
        f"💡 <i>Example:</i>\n"
        f"<code>https://www.raxi4.com/#/register?invitationCode=12345678901</code>\n\n"
        f"⚡ <i>Ya fir current site par direct registration start karne ke liye button dabayein:</i>"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_start = types.InlineKeyboardButton("⚡ Start Registration", callback_data="show_link_options")
    b_tok = types.InlineKeyboardButton("🎫 My Token Balance", callback_data="my_tokens")
    markup.add(b_start, b_tok)

    b_help = types.InlineKeyboardButton("❓ Help & Guide", callback_data="show_help")
    markup.add(b_help)

    if admin_manager.is_admin(user_id):
        b_admin = types.InlineKeyboardButton("👑 Admin Control Hub", callback_data="menu_admin")
        markup.add(b_admin)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def show_link_options(chat_id, user, message_id=None, del_incoming=None):
    """
    Shows the Two Primary Options after link is configured:
    [⚡ Single Registration] and [🔢 Multi-Registration]
    """
    user_id = user.id if user else chat_id
    first_name = html.escape(user.first_name if user else "User")
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    sms_req = cfg.get("sms_required", False)
    switched = cfg.get("switched_mirror", False)
    mirrors_scanned = cfg.get("mirrors_scanned", 0)

    if sms_req:
        sms_badge = f"🔴 <b>MANDATORY (Live Mobile OTP Required — {mirrors_scanned} Official Mirrors Scanned)</b>"
        sms_note = (
            f"⚠️ <b>Platform Security Notice:</b> Platform ke sabhi <b>{mirrors_scanned} official live mirrors</b> scan kiye gaye, "
            f"aur sabhi mirrors par live mobile SMS OTP active hai.\n\n"
            f"🛡️ <b>Token Protection Active:</b> Aapke tokens protect karne ke liye random bulk creation pause ki gayi hai.\n\n"
            f"👉 <b>Solution:</b> <b>⚡ Single Registration -> ✍️ Custom Details</b> use karein jahan bot "
            f"aapke number par official SMS OTP trigger karega aur code enter karte hi slider solve karke account create karega!"
        )
    else:
        sms_badge = "🟢 <b>DISABLED (Free Auto Bulk Enabled)</b>"
        if switched:
            sms_note = f"🎉 <b>Backup Mirror Connected:</b> Platform ke {mirrors_scanned} official mirrors scan karke SMS-free official mirror auto-connect kar diya gaya hai!"
        else:
            sms_note = "⚡ <b>Ready:</b> Direct instant registration bina kisi OTP ke supported hai."

    is_owner = bool(user_id == 8327850869 or admin_manager.is_super_admin(user_id))
    api_line = f"⚡ <b>Backend API:</b> <code>{cfg['api']}</code>\n" if is_owner else ""

    text = (
        f"🎯 <b>Platform Configuration Active!</b>\n\n"
        f"🌐 <b>Target Site:</b> <code>{cfg['site']}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n"
        f"{api_line}"
        f"🔒 <b>SMS OTP Status:</b> {sms_badge}\n\n"
        f"{sms_note}\n\n"
        f"👤 <b>User:</b> {first_name} | 🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🎫 <b>Token Balance:</b> <b>{tokens_disp}</b> <i>(1 Token = 1 Account)</i>\n\n"
        f"Select Registration Mode:"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single")
    b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi")
    markup.add(b1, b2)

    b3 = types.InlineKeyboardButton("🔗 Change Platform Link", callback_data="ask_new_link")
    b4 = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt")
    markup.add(b3, b4)

    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start")
    b_tok = types.InlineKeyboardButton("🎫 My Balance", callback_data="my_tokens")
    markup.add(b_home, b_tok)

    if admin_manager.is_admin(user_id):
        b_admin = types.InlineKeyboardButton("👑 Admin Control Hub", callback_data="menu_admin")
        markup.add(b_admin)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def show_single_menu(chat_id, user, message_id=None):
    """
    Displays Sub-options for Single Registration:
    [🎲 Random Details] and [✍️ Custom Details]
    """
    user_id = user.id if user else chat_id
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)
    sms_req = cfg.get("sms_required", False)

    if sms_req:
        info_lines = (
            "⚠️ <b>Platform SMS OTP Enforced:</b>\n"
            "• 🎲 <b>Random Details:</b> ❌ Unavailable (Platform requires real mobile OTP)\n\n"
            "• ✍️ <b>Custom Details:</b> 🟢 <b>Recommended!</b> Enter your 10-digit number; "
            "bot will send live OTP to your phone, verify slider & register account seamlessly."
        )
    else:
        info_lines = (
            "Registration ka method select karein:\n\n"
            "• 🎲 <b>Random Details:</b> Bot automatically fresh Indian phone number, unique real device &amp; password generate karega.\n\n"
            "• ✍️ <b>Custom Details:</b> Aap apna khud ka mobile number aur password enter karke account create kar sakte hain."
        )

    text = (
        f"⚡ <b>Single Account Registration</b>\n\n"
        f"🌐 <b>Platform:</b> <code>{cfg['site']}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n"
        f"🎫 <b>Your Balance:</b> <b>{tokens_disp}</b> <i>(1 Token = 1 Account)</i>\n\n"
        f"{info_lines}"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("🎲 Random Details", callback_data="single_random")
    b2 = types.InlineKeyboardButton("✍️ Custom Details" + (" (OTP)" if sms_req else ""), callback_data="single_custom")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start")
    markup.add(b1, b2)
    markup.add(b_back, b_home)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_multi_menu(chat_id, user, message_id=None):
    """Displays count selection for Multi-Registration."""
    user_id = user.id if user else chat_id
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)
    sms_req = cfg.get("sms_required", False)

    if sms_req:
        text = (
            f"🔢 <b>Multi-Registration (Bulk Mode) — PAUSED</b>\n\n"
            f"🌐 <b>Target Platform:</b> <code>{cfg['site']}</code>\n"
            f"🔒 <b>SMS OTP Status:</b> 🔴 <b>MANDATORY OTP</b>\n\n"
            f"⚠️ <b>Notice:</b> Is platform par har naye registration ke liye real mobile SMS OTP zaroori hai.\n"
            f"Random virtual numbers par OTP receive nahi hota, isliye aapke tokens protect karne ke liye "
            f"Bulk mode is platform par pause kiya gaya hai.\n\n"
            f"💡 <b>Kripya 'Single Registration -> Custom Details' use karein</b> jahan aap apna mobile number "
            f"enter karke OTP ke sath account create kar sakte hain."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        b_custom = types.InlineKeyboardButton("⚡ Use Single (Custom OTP)", callback_data="single_custom")
        b_change = types.InlineKeyboardButton("🔗 Change Platform Link", callback_data="ask_new_link")
        b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
        markup.add(b_custom, b_change, b_back)
        send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)
        return

    text = (
        f"🔢 <b>Multi-Registration (Bulk Mode)</b>\n\n"
        f"🌐 <b>Target Platform:</b> <code>{cfg['site']}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n"
        f"🎫 <b>Your Balance:</b> <b>{tokens_disp}</b>\n"
        f"💰 <b>Rate:</b> <code>1 Token</code> = <code>1 Account</code>\n\n"
        f"Kitne accounts ek sath register karne hain select karein:\n"
        f"• Har account ke liye <b>alag dynamic physical mobile model</b> use hoga.\n"
        f"• Har account ke liye <b>fresh working IP proxy</b> use hogi (never repeated).\n"
        f"• Result <b>arranged sequence</b> me generate hoga.\n\n"
        f"💡 <i>Command se bhi run kar sakte hain:</i> <code>/bulk &lt;count&gt;</code>"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ 5 Accounts (5 🎫)", callback_data="multi_run_5")
    b2 = types.InlineKeyboardButton("⚡ 10 Accounts (10 🎫)", callback_data="multi_run_10")
    b3 = types.InlineKeyboardButton("⚡ 50 Accounts (50 🎫)", callback_data="multi_run_50")
    b4 = types.InlineKeyboardButton("⚡ 100 Accounts (100 🎫)", callback_data="multi_run_100")
    b5 = types.InlineKeyboardButton("⚡ 500 Accounts (500 🎫)", callback_data="multi_run_500")
    b_custom = types.InlineKeyboardButton("✍️ Custom Fast", callback_data="multi_custom")
    b_sched = types.InlineKeyboardButton("🎲 Custom Scheduled (Random Human Time) 🌟", callback_data="multi_sched")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b_custom)
    markup.add(b_sched)
    markup.add(b_back, b_home)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_custom_amount_prompt(chat_id, user, message_id=None):
    """Displays prompt asking user to type custom bulk count."""
    user_id = user.id if user else chat_id
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    text = (
        f"🔢 <b>Custom Multi-Registration</b>\n\n"
        f"🌐 <b>Platform:</b> <code>{cfg['site']}</code> | 🎟️ <b>Invite:</b> <code>{cfg['invite']}</code>\n"
        f"🎫 <b>Your Balance:</b> <b>{tokens_disp}</b>\n"
        f"💰 <b>Rate:</b> <code>1 Token</code> = <code>1 Account</code>\n\n"
        f"✍️ <b>Kitne accounts ek sath register karne hain?</b>\n"
        f"Niche chat me koi bhi number likh kar send karein <i>(1 se 1000 tak, e.g. 25, 50, 100, 500)</i>:\n\n"
        f"💡 <i>Ya fir direct command use karein:</i> <code>/bulk &lt;number&gt;</code>"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    b_back = types.InlineKeyboardButton("🔙 Back to Multi-Menu", callback_data="reg_multi")
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_custom_scheduled_count_prompt(chat_id, user, message_id=None, default_count=20):
    """Step 1: Asks user how many accounts to create for scheduled registration."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)
    CUSTOM_SCHEDULED_STATE[user_id] = {
        "step": "awaiting_count",
        "chat_id": chat_id,
        "mid": message_id,
        "time": time.time()
    }

    text = (
        f"🎲 <b>Custom Scheduled Registration (Anti-Ban Human Mode)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Platform:</b> <code>{cfg['site']}</code> | 🎟️ <b>Invite:</b> <code>{cfg['invite']}</code>\n"
        f"🎫 <b>Your Tokens:</b> <b>{tokens_disp}</b>\n\n"
        f"👉 <b>Step 1 of 2: Kitne accounts create karne hain?</b>\n\n"
        f"Niche preset button dabayein ya chat me koi bhi number (e.g. <code>20</code>, <code>50</code>, <code>100</code>) likh kar send karein:\n"
        f"<i>(1 Token = 1 Account)</i>"
    )
    markup = types.InlineKeyboardMarkup(row_width=3)
    b1 = types.InlineKeyboardButton("10 Accounts", callback_data="sched_cnt_10")
    b2 = types.InlineKeyboardButton("25 Accounts", callback_data="sched_cnt_25")
    b3 = types.InlineKeyboardButton("50 Accounts", callback_data="sched_cnt_50")
    b4 = types.InlineKeyboardButton("100 Accounts", callback_data="sched_cnt_100")
    b5 = types.InlineKeyboardButton("200 Accounts", callback_data="sched_cnt_200")
    b6 = types.InlineKeyboardButton("500 Accounts", callback_data="sched_cnt_500")
    b_back = types.InlineKeyboardButton("🔙 Cancel / Back", callback_data="reg_multi")
    markup.add(b1, b2, b3)
    markup.add(b4, b5, b6)
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_custom_scheduled_minutes_prompt(chat_id, user, count, message_id=None):
    """Step 2: Asks user in how many minutes the accounts should be completed."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    cfg = get_chat_config(chat_id)
    CUSTOM_SCHEDULED_STATE[user_id] = {
        "step": "awaiting_minutes",
        "chat_id": chat_id,
        "mid": message_id,
        "count": count,
        "time": time.time()
    }

    text = (
        f"⏱️ <b>Custom Scheduled Registration — Step 2 of 2</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🎯 <b>Target Accounts:</b> <code>{count} Accounts</code>\n"
        f"• 🌐 <b>Target Platform:</b> <code>{cfg['site']}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n\n"
        f"👉 <b>Ye {count} accounts kitne MINUTES ke andar complete hojane chahiye?</b>\n\n"
        f"Bot is given time me <b>random times par 1-1 ya 2-2 accounts</b> naturally create karke target reach karega (100% human-like behavior).\n\n"
        f"Niche preset time chunein ya chat me minutes likhein (e.g. <code>15</code>, <code>30</code>, <code>60</code>, <code>120</code>):"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b0 = types.InlineKeyboardButton("⏱️ 10 Minutes", callback_data=f"sched_min_{count}_10")
    b1 = types.InlineKeyboardButton("⏱️ 15 Minutes", callback_data=f"sched_min_{count}_15")
    b2 = types.InlineKeyboardButton("⏱️ 30 Minutes", callback_data=f"sched_min_{count}_30")
    b3 = types.InlineKeyboardButton("⏱️ 60 Min (1 Hour)", callback_data=f"sched_min_{count}_60")
    b4 = types.InlineKeyboardButton("⏱️ 120 Min (2 Hours)", callback_data=f"sched_min_{count}_120")
    b_back = types.InlineKeyboardButton("🔙 Back to Step 1", callback_data="multi_sched")
    markup.add(b0, b1)
    markup.add(b2, b3)
    markup.add(b4, b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_speed_selection_menu(chat_id, user, count, message_id=None):
    """
    Prompts user to select registration speed / delay before running bulk registration.
    Options: FASTEST (Parallel Turbo), SAFE (3s delay), STEALTH (6s delay), Custom Speed, Custom Scheduled.
    """
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    # Check token requirement for non-admins
    if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()):
        avail = admin_manager.get_tokens(user_id)
        if avail <= 0:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
            send_or_edit(
                chat_id,
                "❌ <b>Insufficient Tokens!</b>\n\n"
                "Aapke pass <code>0 Tokens</code> hain. Har account registration ke liye <code>1 Token</code> lagta hai.\n"
                "Recharge karne ke liye Admin se contact karein.",
                reply_markup=markup,
                message_id=message_id
            )
            return
        if avail < count:
            count = avail

    text = (
        f"⚡ <b>Select Registration Speed</b>\n\n"
        f"• 🎯 <b>Batch Count:</b> <code>{count} Accounts</code>\n"
        f"• 🌐 <b>Target Platform:</b> <code>{cfg['site']}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n"
        f"• 🎫 <b>Token Cost:</b> <code>{count} Tokens</code> (Bal: <b>{tokens_disp}</b>)\n\n"
        f"Kripya speed mode choose karein:\n\n"
        f"• ⚡ <b>FASTEST (Turbo):</b>\n"
        f"  Parallel Multi-Engine, 0s delay (Sabse tez registration)\n\n"
        f"• 🛡️ <b>SAFE (3s Delay):</b>\n"
        f"  3s gap per ID — site anti-bot / rate-limit protection\n\n"
        f"• 🐢 <b>STEALTH (6s Delay):</b>\n"
        f"  6s gap per ID — maximum safety\n\n"
        f"• ⏱️ <b>Custom Speed:</b>\n"
        f"  Apna customized delay ya total duration enter karein\n\n"
        f"• 🎲 <b>Custom Scheduled (Random Human Time):</b>\n"
        f"  Aap total accounts & minutes batao — bot random times par 1-1 ya 2-2 karke target reach karega! <i>(100% Turbo Safe)</i>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ FASTEST (Turbo)", callback_data=f"bspeed_{count}_0")
    b2 = types.InlineKeyboardButton("🛡️ SAFE (3s Delay)", callback_data=f"bspeed_{count}_3")
    b3 = types.InlineKeyboardButton("🐢 STEALTH (6s)", callback_data=f"bspeed_{count}_6")
    b4 = types.InlineKeyboardButton("⏱️ Custom Gap", callback_data=f"bspeed_{count}_custom")
    b_sched = types.InlineKeyboardButton("🎲 Custom Scheduled (Random Human Time) 🌟", callback_data=f"bspeed_{count}_sched")
    b_back = types.InlineKeyboardButton("🔙 Back to Multi-Menu", callback_data="reg_multi")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b_sched)
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)



def show_admin_menu(chat_id, user, message_id=None):
    """Admin Control Hub matching Jio-Automation bot + Token Engine."""
    user_id = user.id if user else 0
    if not admin_manager.is_admin(user_id):
        bot.send_message(chat_id, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    is_super = admin_manager.is_super_admin(user_id)
    header_title = "👑 <b>Super Admin Control Hub</b>" if is_super else "🛡️ <b>Admin Control Hub</b>"
    uptime_sec = int(time.time() - admin_manager.bot_start_time)
    uptime_str = format_duration(uptime_sec)
    users = admin_manager.get_all_accounts(user_id)

    total_accs = count_saved_accounts()
    total_tokens_circ = admin_manager.get_total_distributed_tokens()

    text = (
        f"{header_title}\n\n"
        f"• <b>Bot Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Registered Users:</b> <code>{len(users)}</code>\n"
        f"• <b>Tokens Distributed:</b> <code>{total_tokens_circ} Tokens</code>\n"
        f"• <b>Saved Accounts:</b> <code>{total_accs}</code>\n"
        f"• <b>SX Proxy Engine:</b> <code>{proxy_manager.get_sx_summary_line()}</code>\n\n"
        f"<b>🎫 Token Management Commands:</b>\n"
        f"• <code>/addtoken &lt;id&gt; &lt;amt&gt;</code> — Credit tokens to user\n"
        f"• <code>/settoken &lt;id&gt; &lt;amt&gt;</code> — Set user token balance\n"
        f"• <code>/deltoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens from user\n\n"
        f"<b>👑 Admin Suite Commands:</b>\n"
        f"• <code>/stats</code> or <code>/statics</code> — Super Admin Users, Tokens &amp; History Audit\n"
        f"• <code>/sessions</code> — Live active registration sessions monitor\n"
        f"• <code>/stopall</code> — Emergency stop all registrations across all chats\n"
        f"• <code>/sxstatus</code> — Live SX multi-proxy pool &amp; balance\n"
        f"• <code>/sxkey &lt;key&gt;</code> — Add/stack new SX.ORG 1 GB trial key\n"
        f"• <code>/sxpurge</code> — Purge expired 0 MB trial keys\n"
        f"• <code>/users</code> — View registered users &amp; tokens\n"
        f"• <code>/addadmin &lt;id&gt;</code> — Promote user to Admin\n"
        f"• <code>/deladmin &lt;id&gt;</code> — Demote admin\n"
        f"• <code>/broadcast &lt;msg&gt;</code> — Broadcast to all users"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_users = types.InlineKeyboardButton("👥 Manage Users", callback_data="admin_users")
    b_tok = types.InlineKeyboardButton("🎫 Manage Tokens", callback_data="admin_token_help")
    markup.add(b_users, b_tok)

    b_sess = types.InlineKeyboardButton("📊 Active Sessions", callback_data="admin_sessions")
    b_sx = types.InlineKeyboardButton("🌐 SX Proxy Status", callback_data="admin_sx_status")
    markup.add(b_sess, b_sx)

    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt")
    b_bcast = types.InlineKeyboardButton("📢 Broadcast Announcement", callback_data="admin_broadcast_info")
    markup.add(b_export, b_bcast)

    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    markup.add(b_back)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def show_users_list(chat_id, user, message_id=None):
    """Displays registered users with their roles and token balances."""
    user_id = user.id if user else 0
    if not admin_manager.is_admin(user_id):
        bot.send_message(chat_id, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    accounts = admin_manager.get_all_accounts(user_id)
    if not accounts:
        text = "ℹ️ No registered users yet."
    else:
        lines = ["👥 <b>Registered Users &amp; Tokens:</b>\n"]
        for acc in accounts[:25]:
            u_tag = f"@{acc['username']}" if acc.get('username') else (acc.get('first_name') or f"User_{acc.get('user_id')}")
            tok_str = acc.get("tokens", "0 Tokens")
            lines.append(f"• <code>{acc['user_id']}</code> | {acc['role']} | 🎫 <b>{tok_str}</b> | {html.escape(u_tag)}")
        if len(accounts) > 25:
            lines.append(f"\n<i>... and {len(accounts) - 25} more users</i>")
        text = "\n".join(lines)

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_add = types.InlineKeyboardButton("➕ Add User (/adduser)", callback_data="admin_adduser_help")
    b_tok = types.InlineKeyboardButton("🎫 Add Tokens (/addtoken)", callback_data="admin_token_help")
    b_back = types.InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="menu_admin")
    markup.add(b_add, b_tok)
    markup.add(b_back)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def show_active_sessions_dashboard(chat_id, user, message_id=None):
    """
    Renders live active registration sessions monitor dashboard.
    Shows real-time progress bar, site, invite, elapsed time, retries,
    and provides inline buttons to stop individual sessions or all sessions.
    """
    user_id = user.id if user else chat_id
    is_super = (user_id == 8327850869)
    is_adm = is_super or admin_manager.is_admin(user_id)

    sessions = get_all_active_sessions()
    now = time.time()

    if not is_adm:
        # Filter only user's own session
        sessions = [s for s in sessions if s.get("chat_id") == chat_id or s.get("user_id") == user_id]

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_refresh = types.InlineKeyboardButton("🔄 Refresh", callback_data="sessions_refresh")

    if not sessions:
        text = (
            "📊 <b>Active Registration Sessions Monitor</b>\n\n"
            "🟢 <b>Status: IDLE</b>\n\n"
            "Is samay koi bhi active multi-registration session running nahi hai.\n\n"
            "💡 <i>Nayi bulk registration run karne ke liye <code>/bulk &lt;count&gt;</code> ya menu use karein.</i>"
        )
        markup.add(b_refresh)
        if message_id:
            try:
                bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
                return
            except Exception:
                pass
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")
        return

    text_lines = [
        f"📊 <b>Active Registration Sessions ({len(sessions)} Running)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]

    stop_buttons = []
    for idx, s in enumerate(sessions, 1):
        s_chat = s.get("chat_id")
        s_user = s.get("user_id")
        s_uname = s.get("username") or str(s_user)
        s_count = s.get("count", 0)
        s_comp = s.get("completed", 0)
        s_fail = s.get("failed", 0)
        s_site = s.get("site", "N/A")
        s_elapsed = int(now - s.get("start_time", now))
        s_elapsed_str = f"{s_elapsed}s" if s_elapsed < 60 else f"{s_elapsed // 60}m {s_elapsed % 60}s"
        bar = render_progress_bar(s_comp, s_count, length=8)

        sess_block = (
            f"<b>#{idx} • User:</b> <code>{html.escape(str(s_uname))}</code> (<code>{s_user}</code>)\n"
            f"• 🌐 Site: <code>{s_site}</code>\n"
            f"• ⏳ Progress: {bar} <code>{s_comp}/{s_count}</code>\n"
            f"• ⏱️ Elapsed: <code>{s_elapsed_str}</code> | Retries: <code>{s_fail}</code>"
        )
        text_lines.append(sess_block)
        text_lines.append("────────────────────────────")

        stop_buttons.append(
            types.InlineKeyboardButton(f"🛑 Stop #{idx} ({s_comp}/{s_count})", callback_data=f"stop_reg_{s_chat}")
        )

    for btn in stop_buttons:
        markup.add(btn)

    action_row = [b_refresh]
    if is_super and len(sessions) > 1:
        action_row.append(types.InlineKeyboardButton("🛑 STOP ALL SESSIONS", callback_data="sessions_stop_all"))
    markup.add(*action_row)

    full_text = "\n".join(text_lines)
    if message_id:
        try:
            bot.edit_message_text(full_text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, full_text, reply_markup=markup, parse_mode="HTML")


def show_help_menu(chat_id, user, message_id=None, del_incoming=None):
    if del_incoming:
        try:
            bot.delete_message(chat_id, del_incoming.message_id)
        except Exception:
            pass
    user_id = user.id if user else 0
    is_super = (user_id == 8327850869)
    is_adm = is_super or admin_manager.is_admin(user_id)

    header = "👑 <b>Super Admin Commands Hub</b>" if is_super else ("🛡️ <b>Admin Commands Hub</b>" if is_adm else "📌 <b>Multi-Site Register Bot — Commands Guide</b>")

    text = (
        f"{header}\n\n"
        "<b>🚀 Core Controls:</b>\n"
        "• <code>/start</code> — Start bot &amp; configure referral link\n"
        "• <code>/single</code> or <code>/gen</code> — Single account registration (1 🎫)\n"
        "• <code>/bulk &lt;count&gt;</code> or <code>/multi &lt;count&gt;</code> — Multi-registration\n"
        "• <code>/stop</code> — Stop current running registration in this chat\n"
        "• <code>/link &lt;url&gt;</code> — Set referral link\n"
        "• <i>Direct Link Paste</i> — Paste link in chat to configure instantly\n"
        "• <code>/tokens</code> or <code>/balance</code> — Check your Token balance\n"
        "• <code>/reg &lt;phone&gt; &lt;password&gt; [invite]</code> — Custom registration\n"
        "• <code>/export</code> — Download saved accounts list (.txt)\n"
        "• <code>/id</code> or <code>/myid</code> — Check your Telegram ID &amp; role"
    )

    if is_super:
        text += (
            "\n\n<b>👑 Exclusive Super Admin Suite (Only for You):</b>\n"
            "• <code>/stats</code> or <code>/statics</code> — Master User Registry, Tokens &amp; History Audit\n"
            "• <code>/sessions</code> — Live active registration sessions monitor\n"
            "• <code>/stopall</code> — Emergency halt all registrations across all chats\n"
            "• <code>/silentaddtoken &lt;id&gt; &lt;amt&gt;</code> — Add tokens secretly (no alert to user)\n"
            "• <code>/silentdeducttoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens secretly (no alert to user)\n"
            "• <code>/sxkey &lt;key&gt;</code> — Add &amp; stack new SX.ORG 1 GB trial API key\n"
            "• <code>/sxstatus</code> — Live SX multi-proxy pool &amp; combined quota\n"
            "• <code>/sxpurge</code> — Auto-clean &amp; delete all expired 0 MB trial keys\n"
            "• <code>/freemode</code> — Toggle Free Mode on/off"
        )

    if is_adm:
        text += (
            "\n\n<b>🎫 Token Management (Admin Suite):</b>\n"
            "• <code>/addtoken &lt;id&gt; &lt;amt&gt;</code> — Credit tokens to user (with alert)\n"
            "• <code>/settoken &lt;id&gt; &lt;amt&gt;</code> — Set user token balance\n"
            "• <code>/deltoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens from user\n\n"
            "<b>🛡️ General Admin Commands:</b>\n"
            "• <code>/admin</code> — Admin Control Hub\n"
            "• <code>/sessions</code> — Active sessions monitor\n"
            "• <code>/users</code> — List registered users &amp; tokens\n"
            "• <code>/sxstatus</code> — Live SX rotating proxy status\n"
            "• <code>/addadmin &lt;id&gt;</code> — Promote user to Admin\n"
            "• <code>/deladmin &lt;id&gt;</code> — Demote Admin\n"
            "• <code>/broadcast &lt;msg&gt;</code> — Broadcast announcement"
        )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start")
    markup.add(b_back, b_home)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def execute_cleanup():
    cleaned_count = 0
    for p in Path(BASE_DIR).glob("*.tmp*"):
        try:
            p.unlink()
            cleaned_count += 1
        except Exception:
            pass
    return cleaned_count


# ═══════════════════════════════════════════════════════════════════════════
#  SINGLE REGISTRATION WORKER
# ═══════════════════════════════════════════════════════════════════════════

def run_registration_and_send_ss(chat_id, user_id=None, phone=None, password=None, invite=None, message_id=None, smsvcode=""):
    """
    Executes Single Account Registration:
    Shows UID, Phone, Password, Proxy IP, and Device Model.
    Edits existing message in place so no message spam occurs.
    Supports smsvcode for OTP-verified registrations.
    """
    uid = user_id or chat_id
    if not is_user_member(uid):
        show_force_join_screen(chat_id, type('UserObj', (), {'id': uid, 'first_name': 'User'})(), message_id=message_id)
        return

    # Token Gatekeeper
    if not admin_manager.has_enough_tokens(uid, 1):
        cur_tok = admin_manager.get_tokens(uid)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
        send_or_edit(
            chat_id,
            f"❌ <b>Insufficient Tokens!</b>\n\n"
            f"• <b>Current Balance:</b> <code>{cur_tok} Tokens</code>\n"
            f"• <b>Required:</b> <code>1 Token</code> per registration\n\n"
            f"💡 Har account ke liye <code>1 Token</code> lagta hai. Recharge ke liye Admin se contact karein.",
            reply_markup=markup,
            message_id=message_id
        )
        return

    if not acquire_chat_lock(chat_id):
        log(f"[bot] Registration already in progress for chat {chat_id}, skipping duplicate run.")
        return

    try:
        cfg = get_chat_config(chat_id)
        target_site = cfg["site"]
        target_api = cfg["api"]
        target_invite = invite or cfg["invite"]

        bar_single = render_progress_bar(1, 2, length=10)
        otp_line = f"\n• 📩 SMS Code: <code>{smsvcode}</code>" if smsvcode else ""
        mid = send_or_edit(
            chat_id,
            f"⏳ <b>Processing Single Registration...</b>\n\n"
            f"{bar_single}\n\n"
            f"• 🌐 Target: <code>{target_site}</code>\n"
            f"• 🎟️ Invite: <code>{target_invite}</code>{otp_line}\n"
            f"• 🧩 Solving native AI slider captcha...\n"
            f"• ⚡ Submitting direct API POST with fresh IP &amp; Device...",
            message_id=message_id
        )

        try:
            res = auto_register_account(
                phone=phone,
                password=password,
                invite=target_invite,
                site=target_site,
                api=target_api,
                creator_id=uid,
                smsvcode=smsvcode,
                api_type=cfg.get("api_type")
            )

            if not res.get("ok"):
                err_msg = res.get("msg", "Registration failed.")
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
                send_or_edit(
                    chat_id,
                    f"❌ <b>Registration Failed</b>\n⚠️ Reason: <code>{html.escape(err_msg)}</code>\n\n<i>Note: Koi token deduct nahi hua.</i>",
                    reply_markup=markup,
                    message_id=mid
                )
                return

            # Deduct 1 token upon successful creation
            new_balance = admin_manager.deduct_tokens(uid, 1)
            tokens_disp = admin_manager.get_display_tokens(uid)

            used_ip = res.get("proxy", "Direct")
            clean_ip = mask_proxy(used_ip)
            used_dev = res.get("device", "Standard Mobile")
            card_text = (
                "🎉 <b>ACCOUNT CREATED SUCCESSFULLY!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 <b>Phone:</b> <code>{res['phone']}</code>\n"
                f"🔑 <b>Password:</b> <code>{res['password']}</code>\n"
                f"🆔 <b>UID:</b> <code>{res.get('uid') or 'Registered'}</code>\n"
                f"📱 <b>Device:</b> <code>{used_dev}</code>\n"
                f"🌐 <b>Proxy IP:</b> <code>{clean_ip}</code>\n"
                f"🎟️ <b>Invite Code:</b> <code>{res['invite']}</code>\n"
                f"🌐 <b>Site:</b> <code>{target_site}</code>\n"
                f"🎫 <b>Remaining Tokens:</b> <code>{tokens_disp}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ <i>100% Native Direct API Engine (No Browser)</i>\n"
                "🔒 <i>Unique Real Device &amp; Fresh IP (Never Repeated)</i>"
            )

            markup = types.InlineKeyboardMarkup(row_width=2)
            btn1 = types.InlineKeyboardButton("⚡ Register Again (1 🎫)", callback_data="reg_single")
            btn2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi")
            btn3 = types.InlineKeyboardButton("📋 Export List", callback_data="export_txt")
            btn4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
            markup.add(btn1, btn2)
            markup.add(btn3, btn4)

            send_or_edit(chat_id, card_text, reply_markup=markup, message_id=mid)

        except Exception as e:
            log(f"[bot] Pipeline error: {e}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
            send_or_edit(
                chat_id,
                f"💥 <b>Error during registration:</b>\n<code>{html.escape(str(e))}</code>\n\n<i>Note: No tokens were deducted.</i>",
                reply_markup=markup,
                message_id=mid
            )
    finally:
        release_chat_lock(chat_id)


# ═══════════════════════════════════════════════════════════════════════════
#  MULTI-REGISTRATION WORKER (Arranged Manner as Requested)
#  Format per account:
#    (IP / Device)
#    UID
#    Number
#    Password
#    <gap>
# ═══════════════════════════════════════════════════════════════════════════

def run_bulk_registration(chat_id, user_id=None, count=5, message_id=None, delay=0.0, speed_label="⚡ FASTEST (Turbo)"):
    """
    Runs Multi-Registration with configurable speed mode & delay,
    and outputs in the EXACT arranged manner:
    IP / Device -> UID -> Number -> Password -> gap -> next account!
    Edits the existing message in place to avoid sending multiple messages.
    """
    uid = user_id or chat_id
    if not is_user_member(uid):
        show_force_join_screen(chat_id, type('UserObj', (), {'id': uid, 'first_name': 'User'})(), message_id=message_id)
        return

    # Token check: Super Admin is unlimited; Free Mode is free; Client Admins (1k daily quota) and Users check available tokens
    if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
        avail = admin_manager.get_tokens(uid)
        if avail <= 0:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
            msg_quota = "Admin daily quota (1,000) exhaust ho gaya hai. 24h baad reset hoga." if admin_manager.is_admin(uid) else "Recharge karne ke liye Admin se contact karein."
            send_or_edit(
                chat_id,
                f"❌ <b>Insufficient Tokens!</b>\n\n"
                f"Aapke pass <code>0 Tokens</code> bache hain. Har account registration ke liye <code>1 Token</code> lagta hai.\n"
                f"{msg_quota}",
                reply_markup=markup,
                message_id=message_id
            )
            return
        if avail < count:
            count = avail

    if not acquire_chat_lock(chat_id):
        log(f"[bot] Bulk registration already in progress for chat {chat_id}, skipping duplicate run.")
        return

    try:
        cfg = get_chat_config(chat_id)
        target_site = cfg["site"]
        target_api = cfg["api"]
        target_invite = cfg["invite"]

        bar_init = render_progress_bar(0, count, length=10)
        delay_note = f"• ⏱️ Speed: <code>{speed_label}</code>\n"
        if delay > 0:
            est_total = int(count * delay)
            est_str = f"~{est_total}s" if est_total < 60 else f"~{est_total // 60}m {est_total % 60}s"
            delay_note += f"• ⏳ Est. Total Duration: <code>{est_str}</code>\n"

        stop_markup = types.InlineKeyboardMarkup()
        stop_markup.add(types.InlineKeyboardButton("🛑 Stop Registration", callback_data=f"stop_reg_{chat_id}"))

        mid = send_or_edit(
            chat_id,
            f"⏳ <b>Multi-Registration Started...</b>\n\n"
            f"{bar_init}\n\n"
            f"• 🌐 Site: <code>{target_site}</code>\n"
            f"• 🎟️ Invite: <code>{target_invite}</code>\n"
            f"{delay_note}"
            f"• 💰 Rate: 1 Token deducted per account\n\n"
            f"<i>Live accounts creating in progress...</i>",
            reply_markup=stop_markup,
            message_id=message_id
        )

        u_reg = admin_manager.user_registry.get(str(uid), {})
        u_name = u_reg.get("username") or u_reg.get("first_name") or str(uid)
        register_active_session(chat_id, uid, count, target_site, target_invite, mid=mid, username=u_name)
        try:
            bot.pin_chat_message(chat_id, mid, disable_notification=True)
        except Exception:
            pass

        current_mid = [mid]
        success_accounts = []
        failed_count = 0
        total_attempts = 0
        max_total_attempts = count * 6 + 500
        max_consecutive_fails = max(150, count)
        consecutive_fails = 0
        lock = threading.Lock()
        cond = threading.Condition(lock)
        in_flight = 0
        last_edit_time = [time.time()]
        cooldown_wait_cycles = [0]
        max_cooldown_cycles = 30
        last_fail_reason = [""]

        def safe_update_ui(text, reply_markup=None):
            with lock:
                target_id = current_mid[0]
            rm = reply_markup if reply_markup is not None else stop_markup
            new_id = send_or_edit(chat_id, text, reply_markup=rm, message_id=target_id)
            if new_id:
                with lock:
                    current_mid[0] = new_id
            return new_id

        # Proactively ensure proxy pool has enough fresh IPs for bulk order (scales up for 500-1k orders)
        dom_check = urllib.parse.urlparse(target_site).netloc

        def worker_loop():
            nonlocal failed_count, total_attempts, consecutive_fails, in_flight
            while True:
                if is_session_stop_requested(chat_id):
                    log(f"[bot] Session in chat {chat_id} received STOP signal, halting worker.")
                    break

                with cond:
                    while True:
                        if is_session_stop_requested(chat_id):
                            return
                        if len(success_accounts) >= count:
                            return
                        if total_attempts >= max_total_attempts:
                            return
                        if consecutive_fails >= max_consecutive_fails:
                            return
                        if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
                            if admin_manager.get_tokens(uid) <= 0:
                                return

                        # Check if a slot is available
                        if len(success_accounts) + in_flight < count:
                            in_flight += 1
                            total_attempts += 1
                            break
                        else:
                            # Enough workers are currently in-flight to complete remaining target. Wait for them.
                            cond.wait(timeout=0.5)

                avail_now = proxy_manager.get_available_count(domain=dom_check)
                if avail_now == 0:
                    log(f"[bot] SX proxy pool exhausted/inactive for chat {chat_id}, stopping batch.")
                    err_msg = (
                        "❌ <b>Registration Halted — No Active SX Proxies</b>\n\n"
                        "SX.ORG proxy pool is empty or balance exhausted.\n"
                        "Super Admin can add a fresh key using <code>/sxkey &lt;key&gt;</code>."
                    )
                    try:
                        safe_update_ui(err_msg)
                    except Exception:
                        pass
                    with cond:
                        in_flight = max(0, in_flight - 1)
                        cond.notify_all()
                    break

                with cond:
                    cooldown_wait_cycles[0] = 0

                try:
                    res = auto_register_account(site=target_site, api=target_api, invite=target_invite, creator_id=uid, api_type=cfg.get("api_type"))
                except Exception as e:
                    log(f"[bot] auto_register_account unexpected exception in worker: {e}")
                    res = {"ok": False, "msg": str(e)}

                update_text = None
                with cond:
                    in_flight = max(0, in_flight - 1)
                    if res.get("ok"):
                        if len(success_accounts) < count:
                            admin_manager.deduct_tokens(uid, 1)
                            success_accounts.append(res)
                            consecutive_fails = 0
                        else:
                            log(f"[bot] Target count {count} reached; ignoring overflow account {res.get('phone')}")
                    else:
                        failed_count += 1
                        consecutive_fails += 1
                        last_fail_reason[0] = res.get("msg", "")
                        err_msg = str(res.get("msg", "")).lower()
                        if res.get("fatal") or ("sms" in err_msg and "required" in err_msg):
                            log(f"[bot] Stopping bulk registration early: fatal error ({res.get('msg')})")
                            consecutive_fails = max_consecutive_fails
                        elif "expired" in err_msg or "invitor not existed" in err_msg or "invitecode" in err_msg:
                            log(f"[bot] Stopping bulk registration early: fatal invite error ({res.get('msg')})")
                            consecutive_fails = max_consecutive_fails

                    now = time.time()
                    cur_succ = len(success_accounts)
                    update_active_session(chat_id, completed=cur_succ, failed=failed_count, mid=current_mid[0])
                    if cur_succ == count or (now - last_edit_time[0] >= 3.0):
                        last_edit_time[0] = now
                        bar_now = render_progress_bar(cur_succ, count, length=10)
                        retry_note = f"\n• 🔄 <b>Retries Handled:</b> <code>{failed_count}</code> <i>(Auto-recovering dropped IPs)</i>" if failed_count > 0 else ""

                        rem_accs = max(0, count - cur_succ)
                        if delay > 0:
                            est_rem = int(rem_accs * delay)
                            eta_str = f"~{est_rem}s" if est_rem < 60 else f"~{est_rem // 60}m {est_rem % 60}s"
                            eta_line = f"\n• ⏳ <b>ETA Remaining:</b> <code>{eta_str}</code>"
                        else:
                            eta_line = ""

                        update_text = (
                            f"⏳ <b>Multi-Registration in Progress...</b>\n\n"
                            f"{bar_now}\n\n"
                            f"• ✅ Created: <code>{cur_succ}/{count}</code>\n"
                            f"• 🌐 Site: <code>{target_site}</code>\n"
                            f"• 🎟️ Invite: <code>{target_invite}</code>\n"
                            f"• ⚡ Mode: <code>{speed_label}</code>"
                            f"{eta_line}{retry_note}"
                        )
                    cond.notify_all()

                if update_text:
                    try:
                        safe_update_ui(update_text)
                    except Exception:
                        pass

                if res.get("ok"):
                    if delay > 0 and len(success_accounts) < count:
                        time.sleep(delay)
                    else:
                        time.sleep(0.35)  # Safe spacing between successful accounts
                else:
                    if consecutive_fails > 10:
                        time.sleep(1.5)
                    else:
                        time.sleep(0.5)

        if delay > 0:
            workers = 1
        elif count >= 10:
            workers = 5
        else:
            workers = min(count, 5)

        threads = []
        for _ in range(workers):
            t = threading.Thread(target=worker_loop, daemon=True)
            t.start()
            threads.append(t)
            if workers > 1:
                time.sleep(0.35)

        while any(t.is_alive() for t in threads):
            refresh_chat_lock(chat_id)
            time.sleep(1.0)

        gc.collect()

        rem_tokens = admin_manager.get_display_tokens(uid)

        markup = types.InlineKeyboardMarkup(row_width=2)
        b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single")
        b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi")
        b3 = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt")
        b4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
        markup.add(b1, b2)
        markup.add(b3, b4)

        was_stopped = is_session_stop_requested(chat_id)
        if was_stopped:
            log(f"[bot] Bulk registration in chat {chat_id} stopped gracefully. Success: {len(success_accounts)}/{count}")
            try:
                bot.unpin_chat_message(chat_id, current_mid[0])
            except Exception:
                pass

            stopped_header = (
                "🛑 <b>MULTI-REGISTRATION STOPPED!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏹️ <b>Status:</b> Batch stopped by user / admin\n"
                f"✅ <b>Successfully Created:</b> <code>{len(success_accounts)}/{count}</code>\n"
                f"⚡ <b>Speed Mode:</b> <code>{speed_label}</code>\n"
                f"🎫 <b>Tokens Deducted:</b> <code>{len(success_accounts)} Tokens</code>\n"
                f"🎫 <b>Remaining Balance:</b> <b>{rem_tokens}</b>\n"
                f"🌐 <b>Target Site:</b> <code>{target_site}</code>\n"
                f"🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )

            if not success_accounts:
                stopped_text = stopped_header + "<i>Registration was stopped before any accounts were created. No tokens were deducted.</i>"
                safe_update_ui(stopped_text, reply_markup=markup)
                return

            formatted_blocks = []
            for idx, acc in enumerate(success_accounts, 1):
                clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
                dev_val = acc.get('device', 'Android')
                uid_val = acc.get('uid') or 'Registered'
                phone_val = acc['phone']
                pwd_val = acc['password']
                block = (
                    f"<b>[#{idx}] Account #{idx}</b>\n"
                    f"📱 <b>[{idx}]</b> <code>{phone_val}</code> : <code>{pwd_val}</code>\n"
                    f"   ├ 🆔 <b>UID:</b> <code>{uid_val}</code>\n"
                    f"   ├ 📱 <b>Device:</b> <code>{dev_val}</code>\n"
                    f"   └ 🌐 <b>Proxy IP:</b> <code>{clean_ip}</code>"
                )
                formatted_blocks.append(block)

            if len(formatted_blocks) <= 15:
                full_text = stopped_header + "\n\n".join(formatted_blocks)
                if len(full_text) <= 3900:
                    safe_update_ui(full_text, reply_markup=markup)
                else:
                    safe_update_ui(stopped_header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup)
            else:
                doc_lines = [
                    "================================================================================",
                    "RAXI AUTO-REGISTER - BULK ACCOUNTS EXPORT REPORT (STOPPED EARLY)",
                    f"Total Accounts Created: {len(success_accounts)} / {count}",
                    f"Target Platform: {target_site}",
                    f"Invite Code: {target_invite}",
                    f"Export Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
                    "================================================================================\n",
                    "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
                ]
                for idx, acc in enumerate(success_accounts, 1):
                    doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
                doc_lines.append("\n================================================================================")
                doc_lines.append("--- [STRUCTURED AUDIT RECORDS] ---")
                doc_lines.append("================================================================================\n")
                for idx, acc in enumerate(success_accounts, 1):
                    clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
                    doc_lines.append(f"[{idx}] 📱 Phone:    {acc['phone']}")
                    doc_lines.append(f"    🔑 Password: {acc['password']}")
                    doc_lines.append(f"    🆔 UID:      {acc.get('uid') or 'Registered'}")
                    doc_lines.append(f"    📱 Device:   {acc.get('device', 'Android')}")
                    doc_lines.append(f"    🌐 Proxy IP: {clean_ip}")
                    doc_lines.append("-" * 60)

                doc_bytes = "\n".join(doc_lines).encode("utf-8")
                doc_stream = io.BytesIO(doc_bytes)
                doc_stream.name = f"raxi_bulk_stopped_{len(success_accounts)}_accounts.txt"

                preview_text = (
                    stopped_header +
                    "📁 <b>Accounts Export File (.txt) Attached Below:</b>\n\n"
                    "<b>🔍 First 3 Accounts Preview:</b>\n\n" +
                    "\n\n".join(formatted_blocks[:3]) +
                    f"\n\n⚡ <i>Baaki sabhi {len(formatted_blocks) - 3} accounts niche attached document file me save hain!</i>"
                )
                safe_update_ui(preview_text, reply_markup=markup)
                try:
                    bot.send_document(
                        chat_id,
                        doc_stream,
                        caption=f"📋 <b>{len(success_accounts)} Accounts File (Stopped Early)</b>\n🌐 <code>{target_site}</code> | 🎟️ <code>{target_invite}</code>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    log(f"[bot] Error sending stopped bulk document file: {e}")
            return

        if not success_accounts:
            reason_line = f"\n⚠️ <b>Karan:</b> <code>{html.escape(last_fail_reason[0])}</code>\n" if last_fail_reason[0] else ""
            fail_text = (
                "❌ <b>Multi-Registration Completed with 0 Hits</b>\n"
                f"{reason_line}\n"
                f"• Failed attempts: <code>{failed_count}</code>\n\n"
                f"💡 <i>Kripya target platform aur referral link check karein. Agar invite code expire ho gaya hai, toh /link command se naya referral link bhejein.</i>"
            )
            safe_update_ui(fail_text, reply_markup=markup)
            return

        # Header summary
        retry_line = f"🔄 <b>Retried Attempts:</b> <code>{failed_count}</code> <i>(Auto-recovered with fresh IPs)</i>\n" if failed_count > 0 else ""
        header = (
            "🎉 <b>MULTI-REGISTRATION COMPLETED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Successfully Created:</b> <code>{len(success_accounts)}/{count}</code>\n"
            f"⚡ <b>Speed Mode:</b> <code>{speed_label}</code>\n"
            f"{retry_line}"
            f"🎫 <b>Tokens Deducted:</b> <code>{len(success_accounts)} Tokens</code>\n"
            f"🎫 <b>Remaining Balance:</b> <b>{rem_tokens}</b>\n"
            f"🌐 <b>Target Site:</b> <code>{target_site}</code>\n"
            f"🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        formatted_blocks = []
        for idx, acc in enumerate(success_accounts, 1):
            clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
            dev_val = acc.get('device', 'Android')
            uid_val = acc.get('uid') or 'Registered'
            phone_val = acc['phone']
            pwd_val = acc['password']

            block = (
                f"<b>[#{idx}] Account #{idx}</b>\n"
                f"📱 <b>[{idx}]</b> <code>{phone_val}</code> : <code>{pwd_val}</code>\n"
                f"   ├ 🆔 <b>UID:</b> <code>{uid_val}</code>\n"
                f"   ├ 📱 <b>Device:</b> <code>{dev_val}</code>\n"
                f"   └ 🌐 <b>Proxy IP:</b> <code>{clean_ip}</code>"
            )
            formatted_blocks.append(block)

        if len(formatted_blocks) <= 15:
            full_text = header + "\n\n".join(formatted_blocks)
            if len(full_text) <= 3900:
                safe_update_ui(full_text, reply_markup=markup)
            else:
                safe_update_ui(header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup)
        else:
            # Auto-generate downloadable clean .txt file for 15+ accounts to avoid Telegram FloodWait / message limits
            doc_lines = [
                "================================================================================",
                "RAXI AUTO-REGISTER - BULK ACCOUNTS EXPORT REPORT",
                f"Total Accounts Created: {len(success_accounts)} / {count}",
                f"Target Platform: {target_site}",
                f"Invite Code: {target_invite}",
                f"Export Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
                "================================================================================\n",
                "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
            ]
            for idx, acc in enumerate(success_accounts, 1):
                doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
            doc_lines.append("\n================================================================================")
            doc_lines.append("--- [STRUCTURED AUDIT RECORDS] ---")
            doc_lines.append("================================================================================\n")
            for idx, acc in enumerate(success_accounts, 1):
                clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
                doc_lines.append(f"[{idx}] 📱 Phone:    {acc['phone']}")
                doc_lines.append(f"    🔑 Password: {acc['password']}")
                doc_lines.append(f"    🆔 UID:      {acc.get('uid') or 'Registered'}")
                doc_lines.append(f"    📱 Device:   {acc.get('device', 'Android')}")
                doc_lines.append(f"    🌐 Proxy IP: {clean_ip}")
                doc_lines.append("-" * 60)

            doc_bytes = "\n".join(doc_lines).encode("utf-8")
            doc_stream = io.BytesIO(doc_bytes)
            doc_stream.name = f"raxi_bulk_{len(success_accounts)}_accounts.txt"

            preview_text = (
                header +
                "📁 <b>Accounts Export File (.txt) Niche Attach Kar Di Gayi Hai!</b>\n\n"
                "<b>🔍 First 3 Accounts Preview:</b>\n\n" +
                "\n\n".join(formatted_blocks[:3]) +
                f"\n\n⚡ <i>Baaki sabhi {len(formatted_blocks) - 3} accounts niche attached document file me save hain!</i>"
            )

            safe_update_ui(preview_text, reply_markup=markup)
            try:
                bot.send_document(
                    chat_id,
                    doc_stream,
                    caption=f"📋 <b>{len(success_accounts)} Accounts File</b>\n🌐 <code>{target_site}</code> | 🎟️ <code>{target_invite}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                log(f"[bot] Error sending bulk document file: {e}")
        try:
            bot.unpin_chat_message(chat_id, current_mid[0])
        except Exception:
            pass
    finally:
        unregister_active_session(chat_id)
        try:
            bot.unpin_chat_message(chat_id, current_mid[0])
        except Exception:
            pass
        release_chat_lock(chat_id)


def run_custom_scheduled_registration(chat_id, user_id=None, count=20, total_minutes=30, message_id=None):
    """
    Runs Anti-Ban Scheduled Registration in background:
    Distributes account creations randomly across the requested minutes window (1-1 or 2-2 per burst).
    """
    uid = user_id or chat_id
    if not is_user_member(uid):
        show_force_join_screen(chat_id, type('UserObj', (), {'id': uid, 'first_name': 'User'})(), message_id=message_id)
        return

    # Check token requirement
    if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
        avail = admin_manager.get_tokens(uid)
        if avail <= 0:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
            send_or_edit(
                chat_id,
                "❌ <b>Insufficient Tokens!</b>\n\nAapke pass <code>0 Tokens</code> bache hain. Recharge karne ke liye Admin se contact karein.",
                reply_markup=markup,
                message_id=message_id
            )
            return
        if avail < count:
            count = avail

    if not acquire_chat_lock(chat_id):
        log(f"[bot] Registration already running in chat {chat_id}, skipping duplicate scheduled run.")
        return

    cfg = get_chat_config(chat_id)
    target_site = cfg["site"]
    target_api = cfg["api"]
    target_invite = cfg["invite"]
    api_type = cfg.get("api_type")

    total_seconds = max(60, int(total_minutes * 60))
    start_time = time.time()
    target_end_time = start_time + total_seconds

    current_mid = [message_id]
    stop_markup = types.InlineKeyboardMarkup()
    stop_markup.add(types.InlineKeyboardButton("🛑 Stop Registration", callback_data=f"stop_reg_{chat_id}"))

    bar_init = render_progress_bar(0, count, length=10)
    current_mid[0] = send_or_edit(
        chat_id,
        f"🎲 <b>Custom Scheduled Registration Started!</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{bar_init}\n\n"
        f"• 🎯 <b>Target:</b> <code>{count} Accounts</code>\n"
        f"• ⏱️ <b>Time Window:</b> <code>{total_minutes} Minutes</code>\n"
        f"• 🌐 <b>Site:</b> <code>{target_site}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
        f"• 🛡️ <b>Distribution:</b> <i>Random 1–2 accounts per burst with organic pauses</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ <i>First registration burst initializing...</i>",
        reply_markup=stop_markup,
        message_id=message_id
    )

    u_reg = admin_manager.user_registry.get(str(uid), {})
    username_val = u_reg.get("username") or str(uid)
    register_active_session(chat_id, uid, count, target_site, target_invite, mid=current_mid[0], username=username_val)

    success_accounts = []
    failed_count = 0
    consecutive_fails = 0
    max_consecutive_fails = 12
    was_stopped = False
    last_fail_reason = ""

    try:
        while len(success_accounts) < count:
            if is_session_stop_requested(chat_id):
                was_stopped = True
                break

            rem_needed = count - len(success_accounts)
            if rem_needed == 1:
                burst_size = 1
            else:
                burst_size = 2 if (random.random() < 0.4 and rem_needed >= 2) else 1

            for b_idx in range(burst_size):
                if is_session_stop_requested(chat_id):
                    was_stopped = True
                    break
                if len(success_accounts) >= count:
                    break
                if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
                    if not admin_manager.has_enough_tokens(uid, 1):
                        log(f"[bot] Scheduled run stopped: insufficient tokens for user {uid}")
                        was_stopped = True
                        break

                if not proxy_manager.is_sx_active():
                    log(f"[bot] No active SX proxies during scheduled run")
                    last_fail_reason = "SX Proxy balance exhausted or inactive"
                    break

                try:
                    res = auto_register_account(
                        site=target_site,
                        api=target_api,
                        invite=target_invite,
                        creator_id=uid,
                        api_type=api_type
                    )
                except Exception as e:
                    log(f"[bot] Scheduled register exception: {e}")
                    res = {"ok": False, "msg": str(e)}

                if res.get("ok"):
                    admin_manager.deduct_tokens(uid, 1)
                    success_accounts.append(res)
                    consecutive_fails = 0
                    update_active_session(chat_id, completed=len(success_accounts), failed=failed_count, mid=current_mid[0])

                    # Immediate live dashboard update per registered account
                    try:
                        cur_live = len(success_accounts)
                        bar_live = render_progress_bar(cur_live, count, length=10)
                        now_live = time.time()
                        el_sec_live = int(now_live - start_time)
                        el_m_live = el_sec_live // 60
                        el_s_live = el_sec_live % 60
                        el_str_live = f"{el_m_live}m {el_s_live}s" if el_m_live > 0 else f"{el_s_live}s"
                        l_phone = res.get("phone", "N/A")
                        l_uid = res.get("uid", "N/A")
                        l_ip = mask_proxy(res.get("proxy", "Direct"))
                        dash_live = (
                            f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"{bar_live}\n\n"
                            f"• 🎯 <b>Progress:</b> <b>{cur_live} / {count} Accounts</b> ({int(cur_live*100/count)}%)\n"
                            f"• ⏱️ <b>Time Elapsed:</b> <code>{el_str_live}</code> / <code>{total_minutes}m</code>\n"
                            f"• ⚡ <b>Status:</b> <i>Account #{cur_live} successfully registered!</i>\n"
                            f"• 📱 <b>Last Registered:</b> <code>{l_phone}</code> | UID: <code>{l_uid}</code>\n"
                            f"• 🌐 <b>Proxy Exit IP:</b> <code>{l_ip}</code>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <i>Bot random times par 1-1 / 2-2 accounts banakar {total_minutes}m me target reach kar raha hai.</i>"
                        )
                        bot.edit_message_text(dash_live, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
                    except Exception as e_live:
                        log(f"[bot] Live dash update exception: {e_live}")

                    if b_idx == 0 and burst_size == 2 and len(success_accounts) < count:
                        time.sleep(random.uniform(2.0, 4.5))
                else:
                    failed_count += 1
                    consecutive_fails += 1
                    last_fail_reason = str(res.get("msg", ""))
                    err_msg = last_fail_reason.lower()
                    if res.get("fatal") or ("sms" in err_msg and "required" in err_msg):
                        consecutive_fails = max_consecutive_fails
                        break
                    elif "expired" in err_msg or "invitor not existed" in err_msg:
                        consecutive_fails = max_consecutive_fails
                        break
                    time.sleep(1.0)

                if consecutive_fails >= max_consecutive_fails:
                    break

            if consecutive_fails >= max_consecutive_fails:
                log(f"[bot] Breaking scheduled run due to {consecutive_fails} consecutive fails.")
                break

            cur_succ = len(success_accounts)
            if cur_succ >= count or is_session_stop_requested(chat_id):
                if is_session_stop_requested(chat_id):
                    was_stopped = True
                break

            try:
                now = time.time()
                elapsed_sec = int(now - start_time)
                rem_sec = max(10.0, target_end_time - now)
                rem_accounts = count - cur_succ
                est_bursts_left = max(1.0, math.ceil(rem_accounts / 1.35))
                avg_interval = rem_sec / est_bursts_left

                # Truly Organic Human-like Jitter Distribution
                gap_profile = random.choices(
                    ["short", "medium", "long", "extra_long"],
                    weights=[30, 40, 20, 10]
                )[0]
                if gap_profile == "short":
                    jitter = random.uniform(0.35, 0.60)
                elif gap_profile == "medium":
                    jitter = random.uniform(0.75, 1.10)
                elif gap_profile == "long":
                    jitter = random.uniform(1.20, 1.55)
                else:
                    jitter = random.uniform(1.60, 1.95)

                raw_pause = avg_interval * jitter
                min_future_time = max(0.0, (est_bursts_left - 1) * 10.0)
                max_allowed = max(10.0, rem_sec - min_future_time)
                pause_sec = max(10.0, min(raw_pause, max_allowed))
                pause_sec = max(8.0, min(pause_sec, rem_sec))
            except Exception as e_calc:
                log(f"[bot] Pause calc fallback: {e_calc}")
                pause_sec = max(15.0, min(60.0, (target_end_time - time.time()) / max(1, count - cur_succ)))

            next_burst_hint = 2 if (random.random() < 0.4 and rem_accounts >= 2) else 1
            last_acc = success_accounts[-1] if success_accounts else {}
            last_phone = last_acc.get("phone", "N/A")
            last_uid = last_acc.get("uid", "N/A")
            last_ip = mask_proxy(last_acc.get("proxy", "Direct"))

            elapsed_m = elapsed_sec // 60
            elapsed_s = elapsed_sec % 60
            el_str = f"{elapsed_m}m {elapsed_s}s" if elapsed_m > 0 else f"{elapsed_s}s"
            bar_now = render_progress_bar(cur_succ, count, length=10)

            dash_text = (
                f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{bar_now}\n\n"
                f"• 🎯 <b>Progress:</b> <b>{cur_succ} / {count} Accounts</b> ({int(cur_succ*100/count)}%)\n"
                f"• ⏱️ <b>Time Elapsed:</b> <code>{el_str}</code> / <code>{total_minutes}m</code>\n"
                f"• ⏳ <b>Next Burst in:</b> <b>~{int(pause_sec)}s</b> <i>({next_burst_hint} account{'s' if next_burst_hint > 1 else ''})</i>\n"
                f"• 📱 <b>Last Registered:</b> <code>{last_phone}</code> | UID: <code>{last_uid}</code>\n"
                f"• 🌐 <b>Proxy Exit IP:</b> <code>{last_ip}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Bot random times par 1-1 / 2-2 accounts banakar {total_minutes}m me target reach kar raha hai.</i>"
            )
            try:
                bot.edit_message_text(dash_text, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
            except Exception:
                pass

            pause_int = int(pause_sec)
            for sec_left in range(pause_int, 0, -1):
                if is_session_stop_requested(chat_id):
                    was_stopped = True
                    break
                refresh_chat_lock(chat_id)
                if sec_left < pause_int and (sec_left % 4 == 0 or sec_left <= 3):
                    cur_now = time.time()
                    cur_el = int(cur_now - start_time)
                    cur_m = cur_el // 60
                    cur_s = cur_el % 60
                    cur_el_str = f"{cur_m}m {cur_s:02d}s" if cur_m > 0 else f"{cur_s}s"

                    if sec_left <= 3:
                        burst_wait_str = "<b>⚡ Initializing burst now...</b>"
                    else:
                        burst_wait_str = f"<b>~{sec_left}s</b> <i>({next_burst_hint} account{'s' if next_burst_hint > 1 else ''})</i>"

                    dash_countdown = (
                        f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{bar_now}\n\n"
                        f"• 🎯 <b>Progress:</b> <b>{cur_succ} / {count} Accounts</b> ({int(cur_succ*100/count)}%)\n"
                        f"• ⏱️ <b>Time Elapsed:</b> <code>{cur_el_str}</code> / <code>{total_minutes}m</code>\n"
                        f"• ⏳ <b>Next Burst in:</b> {burst_wait_str}\n"
                        f"• 📱 <b>Last Registered:</b> <code>{last_phone}</code> | UID: <code>{last_uid}</code>\n"
                        f"• 🌐 <b>Proxy Exit IP:</b> <code>{last_ip}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💡 <i>Bot random times par 1-1 / 2-2 accounts banakar {total_minutes}m me target reach kar raha hai.</i>"
                    )
                    try:
                        bot.edit_message_text(dash_countdown, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
                    except Exception as e_edit:
                        if "message is not modified" not in str(e_edit).lower():
                            log(f"[bot] Live countdown edit warning: {e_edit}")
                time.sleep(1)

    finally:
        unregister_active_session(chat_id)
        release_chat_lock(chat_id)
        try:
            bot.unpin_chat_message(chat_id, current_mid[0])
        except Exception:
            pass

    # Delivery & Output
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_new = types.InlineKeyboardButton("🔄 New Registration", callback_data="show_link_options")
    b_multi = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi")
    markup.add(b_new, b_multi)

    rem_tokens = admin_manager.get_display_tokens(uid)
    now_total = int(time.time() - start_time)
    tot_m = now_total // 60
    tot_s = now_total % 60
    total_time_str = f"{tot_m}m {tot_s}s" if tot_m > 0 else f"{tot_s}s"

    if was_stopped:
        stopped_header = (
            "🛑 <b>SCHEDULED REGISTRATION STOPPED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏹️ <b>Status:</b> Batch stopped by user / admin\n"
            f"✅ <b>Successfully Created:</b> <code>{len(success_accounts)}/{count}</code>\n"
            f"⏱️ <b>Time Active:</b> <code>{total_time_str}</code> (Window: {total_minutes}m)\n"
            f"🎫 <b>Tokens Deducted:</b> <code>{len(success_accounts)} Tokens</code>\n"
            f"🎫 <b>Remaining Balance:</b> <b>{rem_tokens}</b>\n"
            f"🌐 <b>Target Site:</b> <code>{target_site}</code>\n"
            f"🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if not success_accounts:
            stopped_text = stopped_header + "<i>Registration was stopped before any accounts were created. No tokens were deducted.</i>"
            send_or_edit(chat_id, stopped_text, reply_markup=markup, message_id=current_mid[0])
            return

        formatted_blocks = []
        for idx, acc in enumerate(success_accounts, 1):
            clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
            dev_val = acc.get('device', 'Android')
            uid_val = acc.get('uid') or 'Registered'
            formatted_blocks.append(
                f"<b>[#{idx}] Account #{idx}</b>\n"
                f"📱 <b>[{idx}]</b> <code>{acc['phone']}</code> : <code>{acc['password']}</code>\n"
                f"   ├ 🆔 <b>UID:</b> <code>{uid_val}</code>\n"
                f"   ├ 📱 <b>Device:</b> <code>{dev_val}</code>\n"
                f"   └ 🌐 <b>Proxy IP:</b> <code>{clean_ip}</code>"
            )

        if len(formatted_blocks) <= 15:
            full_text = stopped_header + "\n\n".join(formatted_blocks)
            if len(full_text) <= 3900:
                send_or_edit(chat_id, full_text, reply_markup=markup, message_id=current_mid[0])
            else:
                send_or_edit(chat_id, stopped_header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup, message_id=current_mid[0])
        else:
            doc_lines = [
                "================================================================================",
                "RAXI AUTO-REGISTER - SCHEDULED ACCOUNTS EXPORT REPORT (STOPPED EARLY)",
                f"Total Accounts Created: {len(success_accounts)} / {count}",
                f"Target Time Window: {total_minutes} Minutes (Active: {total_time_str})",
                f"Target Platform: {target_site}",
                f"Invite Code: {target_invite}",
                f"Export Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
                "================================================================================\n",
                "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
            ]
            for idx, acc in enumerate(success_accounts, 1):
                doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
            doc_lines.append("\n================================================================================")
            doc_lines.append("--- [STRUCTURED AUDIT RECORDS] ---")
            doc_lines.append("================================================================================\n")
            for idx, acc in enumerate(success_accounts, 1):
                clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
                doc_lines.append(f"[{idx}] 📱 Phone:    {acc['phone']}")
                doc_lines.append(f"    🔑 Password: {acc['password']}")
                doc_lines.append(f"    🆔 UID:      {acc.get('uid') or 'Registered'}")
                doc_lines.append(f"    📱 Device:   {acc.get('device', 'Android')}")
                doc_lines.append(f"    🌐 Proxy IP: {clean_ip}")
                doc_lines.append("-" * 60)

            doc_bytes = "\n".join(doc_lines).encode("utf-8")
            doc_stream = io.BytesIO(doc_bytes)
            doc_stream.name = f"raxi_sched_stopped_{len(success_accounts)}_accounts.txt"
            preview_text = (
                stopped_header +
                "📁 <b>Accounts Export File (.txt) Attached Below:</b>\n\n"
                "<b>🔍 First 3 Accounts Preview:</b>\n\n" +
                "\n\n".join(formatted_blocks[:3]) +
                f"\n\n⚡ <i>Baaki sabhi {len(formatted_blocks) - 3} accounts niche attached document file me save hain!</i>"
            )
            send_or_edit(chat_id, preview_text, reply_markup=markup, message_id=current_mid[0])
            try:
                bot.send_document(
                    chat_id,
                    doc_stream,
                    caption=f"📋 <b>{len(success_accounts)} Scheduled Accounts (Stopped Early)</b>\n🌐 <code>{target_site}</code> | 🎟️ <code>{target_invite}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                log(f"[bot] Error sending stopped scheduled doc: {e}")
        return

    if not success_accounts:
        fail_text = (
            "❌ <b>Scheduled Registration Completed with 0 Hits</b>\n\n"
            f"• Failed attempts: <code>{failed_count}</code>\n"
            f"• Reason: <code>{html.escape(last_fail_reason or 'No accounts could be created')}</code>\n\n"
            f"💡 <i>Kripya target platform aur referral link check karein.</i>"
        )
        send_or_edit(chat_id, fail_text, reply_markup=markup, message_id=current_mid[0])
        return

    header = (
        "🎉 <b>CUSTOM SCHEDULED REGISTRATION COMPLETED!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Successfully Created:</b> <code>{len(success_accounts)}/{count} Accounts</code>\n"
        f"⏱️ <b>Time Taken:</b> <code>{total_time_str}</code> (Window: {total_minutes}m)\n"
        f"🛡️ <b>Mode:</b> <i>Human-Like Random Time Window (1-2 IDs per burst)</i>\n"
        f"🎫 <b>Tokens Deducted:</b> <code>{len(success_accounts)} Tokens</code>\n"
        f"🎫 <b>Remaining Balance:</b> <b>{rem_tokens}</b>\n"
        f"🌐 <b>Target Site:</b> <code>{target_site}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    formatted_blocks = []
    for idx, acc in enumerate(success_accounts, 1):
        clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
        dev_val = acc.get('device', 'Android')
        uid_val = acc.get('uid') or 'Registered'
        formatted_blocks.append(
            f"<b>[#{idx}] Account #{idx}</b>\n"
            f"📱 <b>[{idx}]</b> <code>{acc['phone']}</code> : <code>{acc['password']}</code>\n"
            f"   ├ 🆔 <b>UID:</b> <code>{uid_val}</code>\n"
            f"   ├ 📱 <b>Device:</b> <code>{dev_val}</code>\n"
            f"   └ 🌐 <b>Proxy IP:</b> <code>{clean_ip}</code>"
        )

    if len(formatted_blocks) <= 15:
        full_text = header + "\n\n".join(formatted_blocks)
        if len(full_text) <= 3900:
            send_or_edit(chat_id, full_text, reply_markup=markup, message_id=current_mid[0])
        else:
            send_or_edit(chat_id, header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup, message_id=current_mid[0])
    else:
        doc_lines = [
            "================================================================================",
            "RAXI AUTO-REGISTER - SCHEDULED ACCOUNTS EXPORT REPORT",
            f"Total Accounts Created: {len(success_accounts)} / {count}",
            f"Total Duration: {total_time_str} (Window: {total_minutes} Minutes)",
            f"Target Platform: {target_site}",
            f"Invite Code: {target_invite}",
            f"Export Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "================================================================================\n",
            "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
        ]
        for idx, acc in enumerate(success_accounts, 1):
            doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
        doc_lines.append("\n================================================================================")
        doc_lines.append("--- [STRUCTURED AUDIT RECORDS] ---")
        doc_lines.append("================================================================================\n")
        for idx, acc in enumerate(success_accounts, 1):
            clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
            doc_lines.append(f"[{idx}] 📱 Phone:    {acc['phone']}")
            doc_lines.append(f"    🔑 Password: {acc['password']}")
            doc_lines.append(f"    🆔 UID:      {acc.get('uid') or 'Registered'}")
            doc_lines.append(f"    📱 Device:   {acc.get('device', 'Android')}")
            doc_lines.append(f"    🌐 Proxy IP: {clean_ip}")
            doc_lines.append("-" * 60)

        doc_bytes = "\n".join(doc_lines).encode("utf-8")
        doc_stream = io.BytesIO(doc_bytes)
        doc_stream.name = f"raxi_sched_{len(success_accounts)}_accounts.txt"
        preview_text = (
            header +
            "📁 <b>Accounts Export File (.txt) Niche Attach Kar Di Gayi Hai!</b>\n\n"
            "<b>🔍 First 3 Accounts Preview:</b>\n\n" +
            "\n\n".join(formatted_blocks[:3]) +
            f"\n\n⚡ <i>Baaki sabhi {len(formatted_blocks) - 3} accounts niche attached document file me save hain!</i>"
        )
        send_or_edit(chat_id, preview_text, reply_markup=markup, message_id=current_mid[0])
        try:
            bot.send_document(
                chat_id,
                doc_stream,
                caption=f"📋 <b>{len(success_accounts)} Scheduled Accounts File</b>\n🌐 <code>{target_site}</code> | 🎟️ <code>{target_invite}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            log(f"[bot] Error sending scheduled bulk document file: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def handle_start(message):
    user = message.from_user
    chat_id = message.chat.id
    log(f"[bot] /start from user={user.id} ({user.first_name or 'User'})")
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")

    # Cancel any active custom registration flow
    CUSTOM_REG_STATE.pop(user.id, None)
    CUSTOM_SPEED_STATE.pop(user.id, None)
    CUSTOM_SCHEDULED_STATE.pop(user.id, None)

    # Clean old bot message if possible so a fresh welcome screen lands right at the bottom
    old_mid = LAST_BOT_MSG.pop(chat_id, None)
    if old_mid:
        try:
            bot.delete_message(chat_id, old_mid)
        except Exception:
            pass

    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return

    show_link_prompt(chat_id, user, del_incoming=message)


@bot.message_handler(commands=["help"])
def handle_help(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return
    show_help_menu(message.chat.id, user, del_incoming=message)


@bot.message_handler(commands=["id", "myid", "chatid"])
def handle_id_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    role_label = admin_manager.get_user_role_label(user.id)
    tokens_disp = admin_manager.get_display_tokens(user.id)
    text = (
        f"🆔 <b>Telegram Identity Inspector:</b>\n\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        f"• <b>First Name:</b> {html.escape(user.first_name or 'User')}\n"
        f"• <b>Username:</b> @{user.username if user.username else 'None'}\n"
        f"• <b>Chat ID:</b> <code>{message.chat.id}</code>\n"
        f"• <b>Access Role:</b> {role_label}\n"
        f"• <b>Token Balance:</b> <b>{tokens_disp}</b>"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
    send_or_edit(message.chat.id, text, reply_markup=markup, del_incoming=message)


@bot.message_handler(commands=["tokens", "token", "balance", "credit", "credits"])
def handle_tokens_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    tokens_disp = admin_manager.get_display_tokens(user.id)
    role_label = admin_manager.get_user_role_label(user.id)

    text = (
        f"🎫 <b>Token Account Balance:</b>\n\n"
        f"• <b>User:</b> {html.escape(user.first_name or 'User')}\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        f"• <b>Role:</b> {role_label}\n"
        f"• <b>Available Tokens:</b> <b>{tokens_disp}</b>\n"
        f"• <b>Registration Cost:</b> <code>1 Token</code> per account\n\n"
        f"💡 <i>Tokens recharge karne ke liye Admin se contact karein.</i>"
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single")
    b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi")
    b3 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options")
    markup.add(b1, b2)
    markup.add(b3)
    send_or_edit(message.chat.id, text, reply_markup=markup, del_incoming=message)


# ─── Operational Registration Commands ───

@bot.message_handler(commands=["single", "gen", "generate"])
def handle_single_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    show_single_menu(message.chat.id, user, message_id=LAST_BOT_MSG.get(message.chat.id))


@bot.message_handler(commands=["multi", "bulk"])
def handle_multi_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return

    cfg = get_chat_config(chat_id)
    if cfg.get("sms_required"):
        bot.reply_to(
            message,
            "⛔ <b>Multi-Registration Paused for this Platform!</b>\n\n"
            "This platform enforces live SMS OTP verification (🔴 SMS Required). "
            "Please use <b>Single Registration -> ✍️ Custom Details</b> with your mobile number to create accounts.",
            parse_mode="HTML"
        )
        return

    parts = message.text.strip().split()
    count = 5
    if len(parts) >= 2 and parts[1].isdigit():
        count = min(int(parts[1]), 1000)
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass
    show_speed_selection_menu(chat_id, user, count, message_id=LAST_BOT_MSG.get(chat_id))


@bot.message_handler(commands=["stop", "cancelreg", "stopreg"])
def handle_stop_registration_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")

    args = message.text.strip().split()
    target_chat = chat_id
    if len(args) >= 2 and args[1].lstrip("-").isdigit():
        if admin_manager.is_admin(user.id):
            target_chat = int(args[1])
        else:
            bot.reply_to(message, "⛔ <b>Admin Access Required</b> to stop sessions for other chats.", parse_mode="HTML")
            return

    if request_stop_session(target_chat):
        bot.reply_to(
            message,
            f"🛑 <b>Stop Signal Sent!</b>\n\n"
            f"Chat <code>{target_chat}</code> ke active registration batch ko stop signal bhej diya gaya hai.\n"
            f"Current running account attempt complete hote hi process ruk jayegi aur unpin ho jayegi.",
            parse_mode="HTML"
        )
    else:
        bot.reply_to(
            message,
            "ℹ️ <b>No Active Registration</b>\n\n"
            "Is chat me koi bhi active bulk registration nahi chal rahi hai.\n"
            "Active sessions dekhne ke liye <code>/sessions</code> use karein.",
            parse_mode="HTML"
        )


@bot.message_handler(commands=["stopall", "cancelall"])
def handle_stopall_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869:
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    cnt = request_stop_all_sessions()
    if cnt > 0:
        bot.reply_to(
            message,
            f"🛑 <b>EMERGENCY STOP EXECUTED!</b>\n\n"
            f"Super Admin ne sabhi <b>{cnt} active registration sessions</b> ko emergency stop kar diya hai.\n"
            f"Sabhi background workers safely halt ho rahe hain aur proxy connections terminate ho rahe hain.",
            parse_mode="HTML"
        )
    else:
        bot.reply_to(
            message,
            "ℹ️ <b>No Active Sessions</b>\n\n"
            "Is samay bot me koi bhi bulk registration session running nahi hai.",
            parse_mode="HTML"
        )


@bot.message_handler(commands=["sessions", "activesessions", "tasks"])
def handle_sessions_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    show_active_sessions_dashboard(chat_id, user)


@bot.message_handler(commands=["reg", "register"])
def handle_reg_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return

    args = message.text.strip().split()
    if len(args) < 3:
        bot.reply_to(
            message,
            "⚠️ <b>Usage:</b> <code>/reg &lt;10-digit-phone&gt; &lt;password&gt; [invite]</code>\nExample: <code>/reg 9876543210 yash1617</code>",
            parse_mode="HTML"
        )
        return

    phone = re.sub(r"\D", "", args[1])[-10:]
    password = args[2]
    cfg = get_chat_config(message.chat.id)
    invite = args[3] if len(args) >= 4 else cfg["invite"]

    if len(phone) != 10:
        bot.reply_to(message, "❌ <b>Error:</b> Phone number must be 10 digits.", parse_mode="HTML")
        return

    threading.Thread(
        target=run_registration_and_send_ss,
        args=(message.chat.id, user.id, phone, password, invite, LAST_BOT_MSG.get(message.chat.id), ""),
        daemon=True
    ).start()


@bot.message_handler(commands=["link", "setlink"])
def handle_link_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        cfg = get_chat_config(message.chat.id)
        is_owner = bool(user.id == 8327850869 or admin_manager.is_super_admin(user.id))
        api_line = f"• ⚡ <b>API:</b> <code>{cfg['api']}</code>\n" if is_owner else ""
        bot.reply_to(
            message,
            f"⚠️ <b>Usage:</b> <code>/link &lt;referral_or_site_url&gt;</code>\n\n"
            f"📌 <b>Current Active Config:</b>\n"
            f"• 🌐 <b>Site:</b> <code>{cfg['site']}</code>\n"
            f"{api_line}"
            f"• 🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n\n"
            f"💡 <b>Example:</b> <code>/link https://www.raxi4.com/#/register?invitationCode=12345678901</code>",
            parse_mode="HTML"
        )
        return

    process_and_save_link(message.chat.id, args[1], message)


@bot.message_handler(func=lambda msg: msg.text and ("http://" in msg.text or "https://" in msg.text or "www." in msg.text or "invitationcode=" in msg.text.lower() or "invitecode=" in msg.text.lower()))
def handle_url_message(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return
    process_and_save_link(message.chat.id, message.text, message)


def process_and_save_link(chat_id, text, orig_msg=None):
    info = detect_and_parse_referral_link(text)
    if not info:
        if orig_msg:
            try:
                bot.reply_to(orig_msg, "❌ Valid website ya referral link nahi mila.")
            except Exception:
                pass
        return

    # Check platform SMS requirement & scan mirrors for SMS-free bypass
    mirror_res = check_platform_sms_and_mirrors(info["api"], info["site"], api_type=info.get("api_type", "webapi"))
    active_site = mirror_res.get("site") or info["site"]
    active_api = mirror_res.get("api") or info["api"]
    active_domain = mirror_res.get("domain") or info["domain"]
    active_api_type = mirror_res.get("api_type") or info.get("api_type", "webapi")
    sms_req = mirror_res.get("sms_required", False)
    switched = mirror_res.get("switched_mirror", False)
    mirrors_cnt = mirror_res.get("mirror_count", 0)

    log(f"[bot] Configured link for chat={chat_id}: site='{active_site}' api='{active_api}' api_type='{active_api_type}' sms_req={sms_req} switched={switched}")

    CHAT_CONFIGS[chat_id] = {
        "site": active_site,
        "api": active_api,
        "api_type": active_api_type,
        "invite": info["invite"],
        "domain": active_domain,
        "sms_required": sms_req,
        "switched_mirror": switched,
        "mirrors_scanned": mirrors_cnt
    }
    save_chat_configs()

    user = orig_msg.from_user if orig_msg else None
    show_link_options(chat_id, user, del_incoming=orig_msg)


@bot.message_handler(commands=["cancel"])
def handle_cancel_cmd(message):
    uid = message.from_user.id
    CUSTOM_REG_STATE.pop(uid, None)
    CUSTOM_SPEED_STATE.pop(uid, None)
    CUSTOM_SCHEDULED_STATE.pop(uid, None)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    show_single_menu(message.chat.id, message.from_user)


@bot.message_handler(func=lambda msg: msg.from_user and msg.from_user.id in CUSTOM_REG_STATE and msg.text and not msg.text.startswith("/"))
def handle_custom_reg_steps(message):
    user = message.from_user
    uid = user.id
    chat_id = message.chat.id
    state_data = CUSTOM_REG_STATE.get(uid)
    if not state_data:
        return

    step = state_data.get("step")
    target_mid = state_data.get("mid") or LAST_BOT_MSG.get(chat_id)
    raw_text = message.text.strip()
    sms_req = state_data.get("sms_required", False)
    steps_total = 3 if sms_req else 2

    if step == "phone":
        clean_phone = re.sub(r"\D", "", raw_text)
        if clean_phone.startswith("91") and len(clean_phone) == 12:
            clean_phone = clean_phone[2:]
        if len(clean_phone) != 10:
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))
            send_or_edit(
                chat_id,
                f"❌ <b>Invalid Mobile Number!</b>\n\n"
                f"Number exactly 10 digits ka hona chahiye (e.g. <code>9876543210</code>).\n"
                f"Aapne bheja: <code>{html.escape(raw_text)}</code>\n\n"
                f"Kripya valid 10-digit number dobara send karein:",
                reply_markup=markup,
                message_id=target_mid
            )
            return

        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        CUSTOM_REG_STATE[uid]["step"] = "password"
        CUSTOM_REG_STATE[uid]["phone"] = clean_phone

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))
        send_or_edit(
            chat_id,
            f"🔑 <b>Custom Registration — Step 2/{steps_total}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Mobile Number:</b> <code>{clean_phone}</code> ✅\n\n"
            f"Ab is account ke liye desired <b>Password</b> bhejein:\n"
            f"<i>(Kam se kam 6 characters, e.g. <code>pass1234</code>)</i>\n\n"
            f"💡 <i>Chat me password likh kar send karein ya Cancel dabayein.</i>",
            reply_markup=markup,
            message_id=target_mid
        )
        return

    elif step == "password":
        pwd = raw_text
        if len(pwd) < 6:
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))
            send_or_edit(
                chat_id,
                "❌ <b>Password too short!</b>\n\n"
                "Password minimum 6 characters ka hona chahiye.\n\n"
                "Kripya apna desired password dobara bhejein:",
                reply_markup=markup,
                message_id=target_mid
            )
            return

        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        phone = state_data["phone"]
        cfg = get_chat_config(chat_id)

        # If SMS OTP is NOT required, proceed directly to registration
        if not sms_req:
            CUSTOM_REG_STATE.pop(uid, None)
            threading.Thread(
                target=run_registration_and_send_ss,
                args=(chat_id, uid, phone, pwd, None, target_mid, ""),
                daemon=True
            ).start()
            return

        # If SMS OTP IS required, trigger SMS OTP via platform WebAPI
        CUSTOM_REG_STATE[uid]["password"] = pwd
        send_or_edit(
            chat_id,
            f"⏳ <b>Triggering SMS Verification Code...</b>\n\n"
            f"• 📱 Mobile: <code>{phone}</code>\n"
            f"• 🌐 Platform: <code>{cfg['site']}</code>\n"
            f"• ⚡ Sending official SMS OTP request to server...",
            message_id=target_mid
        )

        ok, msg = send_sms_otp(cfg["api"], phone, site_url=cfg.get("site"))
        if not ok:
            CUSTOM_REG_STATE.pop(uid, None)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton("🔄 Try Again", callback_data="single_custom"))
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options"))
            send_or_edit(
                chat_id,
                f"❌ <b>SMS OTP Failed to Send!</b>\n\n"
                f"• 📱 Number: <code>{phone}</code>\n"
                f"• ⚠️ Server Error: <code>{html.escape(msg)}</code>\n\n"
                f"<i>Note: Koi token deduct nahi hua.</i>",
                reply_markup=markup,
                message_id=target_mid
            )
            return

        CUSTOM_REG_STATE[uid]["step"] = "otp"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))
        send_or_edit(
            chat_id,
            f"📩 <b>Custom Registration — Step 3/3 (SMS OTP)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Mobile Number:</b> <code>{phone}</code> ✅\n"
            f"🔑 <b>Password:</b> <code>{'*' * len(pwd)}</code> ✅\n\n"
            f"📨 <b>SMS Sent Successfully!</b>\n"
            f"Aapke mobile number par verification code bhej diya gaya hai.\n\n"
            f"✍️ <b>Kripya SMS me aaya OTP code chat me send karein:</b>\n"
            f"⏳ <i>Bot verification code ka wait kar raha hai...</i>",
            reply_markup=markup,
            message_id=target_mid
        )
        return

    elif step == "otp":
        otp = re.sub(r"\D", "", raw_text)
        if len(otp) < 4 or len(otp) > 8:
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception:
                pass
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))
            send_or_edit(
                chat_id,
                f"❌ <b>Invalid OTP format!</b>\n\n"
                f"OTP usually 4 se 6 digits ka hota hai.\n"
                f"Aapne bheja: <code>{html.escape(raw_text)}</code>\n\n"
                f"Kripya valid OTP dobara send karein:",
                reply_markup=markup,
                message_id=target_mid
            )
            return

        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass

        phone = state_data["phone"]
        pwd = state_data["password"]
        CUSTOM_REG_STATE.pop(uid, None)

        threading.Thread(
            target=run_registration_and_send_ss,
            args=(chat_id, uid, phone, pwd, None, target_mid, otp),
            daemon=True
        ).start()
        return


@bot.message_handler(func=lambda msg: msg.from_user and msg.from_user.id in CUSTOM_SPEED_STATE and msg.text and not msg.text.startswith("/"))
def handle_custom_speed_msg(message):
    """Processes user response for custom registration speed/delay."""
    user = message.from_user
    uid = user.id
    chat_id = message.chat.id
    state_data = CUSTOM_SPEED_STATE.pop(uid, None)
    if not state_data:
        return

    count = state_data.get("count", 5)
    target_mid = state_data.get("mid") or LAST_BOT_MSG.get(chat_id)

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    raw = message.text.strip().lower()
    delay = 3.0
    label = "🛡️ SAFE (3s Delay)"

    if raw in ("fast", "fastest", "0", "0s", "turbo"):
        delay = 0.0
        label = "⚡ FASTEST (Turbo)"
    elif raw.endswith("m") or "min" in raw:
        try:
            nums = re.findall(r"[\d.]+", raw)
            if nums:
                mins = float(nums[0])
                total_sec = mins * 60.0
                delay = round(total_sec / max(count, 1), 1)
                label = f"⏱️ Custom ({mins:g}m total, {delay}s/id)"
        except Exception:
            delay = 3.0
            label = "🛡️ SAFE (3s Delay)"
    else:
        try:
            nums = re.findall(r"[\d.]+", raw)
            if nums:
                secs = float(nums[0])
                delay = round(secs, 1)
                label = f"⏱️ Custom ({delay}s Delay)"
        except Exception:
            delay = 3.0
            label = "🛡️ SAFE (3s Delay)"

    threading.Thread(
        target=run_bulk_registration,
        args=(chat_id, uid, count, target_mid, delay, label),
        daemon=True
    ).start()


@bot.message_handler(func=lambda msg: msg.from_user and msg.from_user.id in CUSTOM_SCHEDULED_STATE and msg.text and not msg.text.startswith("/"))
def handle_custom_scheduled_msg(message):
    """Processes user response for scheduled registration: count (Step 1) and minutes (Step 2)."""
    user = message.from_user
    uid = user.id
    chat_id = message.chat.id
    state_data = CUSTOM_SCHEDULED_STATE.get(uid)
    if not state_data:
        return

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    step = state_data.get("step")
    target_mid = state_data.get("mid") or LAST_BOT_MSG.get(chat_id)
    raw = message.text.strip()
    nums = re.findall(r"\d+", raw)
    if not nums:
        bot.send_message(chat_id, "❌ Kripya ek valid number likhein (e.g. <code>25</code> ya <code>30</code>).", parse_mode="HTML")
        return

    val = int(nums[0])

    if step == "awaiting_count":
        if val <= 0 or val > 1000:
            bot.send_message(chat_id, "❌ Accounts count 1 se 1000 ke beech hona chahiye.", parse_mode="HTML")
            return
        if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
            avail = admin_manager.get_tokens(uid)
            if avail < val:
                bot.send_message(chat_id, f"❌ <b>Insufficient Tokens:</b> Aapke pass sirf <code>{avail} Tokens</code> hain.", parse_mode="HTML")
                return
        show_custom_scheduled_minutes_prompt(chat_id, user, count=val, message_id=target_mid)

    elif step == "awaiting_minutes":
        CUSTOM_SCHEDULED_STATE.pop(uid, None)
        count = state_data.get("count", 20)
        minutes = val
        if minutes <= 0:
            minutes = 30
        if minutes > 1440:
            minutes = 1440
        threading.Thread(
            target=run_custom_scheduled_registration,
            args=(chat_id, uid, count, minutes, target_mid),
            daemon=True
        ).start()


@bot.message_handler(func=lambda msg: msg.text and msg.text.strip().isdigit() and 1 <= int(msg.text.strip()) <= 1000)
def handle_custom_bulk_number_msg(message):
    """Shows speed selection menu when user sends a custom number (1-100)."""
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return

    cfg = get_chat_config(chat_id)
    if cfg.get("sms_required"):
        bot.reply_to(
            message,
            "⛔ <b>Multi-Registration Paused for this Platform!</b>\n\n"
            "This platform enforces live SMS OTP verification (🔴 SMS Required). "
            "Please use <b>Single Registration -> ✍️ Custom Details</b>.",
            parse_mode="HTML"
        )
        return

    count = int(message.text.strip())

    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    target_msg_id = LAST_BOT_MSG.get(chat_id)
    show_speed_selection_menu(chat_id, user, count, message_id=target_msg_id)


@bot.message_handler(commands=["export", "accounts"])
def handle_export_cmd(message):
    """Handles /export and /accounts command, routing to specific format or export hub."""
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return

    parts = message.text.strip().split()
    if len(parts) >= 2 and parts[1].lower() in ("combo", "combos"):
        threading.Thread(target=send_exported_combos, args=(chat_id, user.id), daemon=True).start()
    elif len(parts) >= 2 and parts[1].lower() in ("full", "report", "all"):
        threading.Thread(target=send_exported_full_report, args=(chat_id, user.id), daemon=True).start()
    elif len(parts) >= 2 and parts[1].lower() == "both":
        threading.Thread(target=send_exported_both, args=(chat_id, user.id), daemon=True).start()
    else:
        show_export_menu(chat_id, user, message_id=LAST_BOT_MSG.get(chat_id))


# ─── Admin Commands ───

@bot.message_handler(commands=["admin"])
def handle_admin_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return
    show_admin_menu(message.chat.id, user)


@bot.message_handler(commands=["freemode"])
def handle_freemode_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    new_mode = admin_manager.toggle_free_mode()
    mode_text = "ENABLED 🟢 (Free Mode ON — No Tokens Required)" if new_mode else "DISABLED 🔴 (Tokens Required)"
    bot.reply_to(
        message,
        f"👑 <b>Free Mode Status Updated!</b>\n\n"
        f"• Status: <b>{mode_text}</b>\n\n"
        f"<i>Sabhi users ke liye registration {'bina tokens ke khula hai' if new_mode else 'tokens ke sath chalega'}.</i>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["status"])
def handle_status_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if admin_manager.is_admin(user.id):
        show_admin_menu(message.chat.id, user)
    else:
        tokens_disp = admin_manager.get_display_tokens(user.id)
        role_label = admin_manager.get_user_role_label(user.id)
        uptime_sec = int(time.time() - admin_manager.bot_start_time)
        uptime_str = format_duration(uptime_sec)
        text = (
            f"⚡ <b>Bot Status: Active &amp; Operational</b>\n\n"
            f"• <b>User ID:</b> <code>{user.id}</code>\n"
            f"• <b>Role:</b> {role_label}\n"
            f"• <b>Token Balance:</b> <b>{tokens_disp}</b>\n"
            f"• <b>Bot Uptime:</b> <code>{uptime_str}</code>\n"
            f"• <b>Required Channel:</b> {REQUIRED_CHANNEL}\n\n"
            f"<i>Type /start to configure link or start registering accounts.</i>"
        )
        send_or_edit(message.chat.id, text, del_incoming=message)


@bot.message_handler(commands=["users"])
def handle_users_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return
    show_users_list(message.chat.id, user)


def parse_token_command_args(message, default_cmd="addtoken"):
    """
    Intelligently parses target and amount for token commands.
    Supports:
    - /command <user_id_or_username> <amount>
    - Reply to user: /command <amount>
    """
    text = (message.text or "").strip()
    parts = text.split()

    # Case 1: Reply to a user's message with: /command <amount>
    if message.reply_to_message and message.reply_to_message.from_user:
        r_user = message.reply_to_message.from_user
        target_id = r_user.id
        admin_manager.record_user(r_user.id, r_user.username or "", r_user.first_name or "")
        if len(parts) >= 2 and parts[1].isdigit():
            amt = int(parts[1])
            if amt > 0:
                return target_id, amt, None
        elif len(parts) >= 3 and parts[2].isdigit():
            amt = int(parts[2])
            if amt > 0:
                return target_id, amt, None

    if len(parts) < 3:
        return None, None, (
            f"⚠️ <b>Usage:</b> <code>/{default_cmd} &lt;user_id_ya_username&gt; &lt;amount&gt;</code>\n\n"
            f"<b>Examples:</b>\n"
            f"• <code>/{default_cmd} 7545282674 100</code>\n"
            f"• <code>/{default_cmd} @PAPA_PLAYER7 100</code>\n"
            f"• User ke kisi message par reply karke: <code>/{default_cmd} 100</code>"
        )

    raw_target = parts[1].strip()
    raw_amount = parts[2].strip()

    if not raw_amount.isdigit() or int(raw_amount) <= 0:
        return None, None, "❌ Amount ek valid positive number hona chahiye (e.g. <code>50</code>, <code>100</code>)."

    amount = int(raw_amount)

    # 1. Numeric ID
    if raw_target.lstrip("-").isdigit():
        return int(raw_target), amount, None

    # 2. Username (@username or username)
    clean_username = raw_target.lstrip("@").lower()
    resolved_id = admin_manager.get_user_by_username(clean_username)
    if resolved_id:
        return resolved_id, amount, None

    return None, None, f"❌ User <code>{html.escape(raw_target)}</code> bot database me nahi mila.\n\n💡 <i>Direct numeric Telegram ID use karein ya user ko pehle bot me <code>/start</code> dabane bole.</i>"


@bot.message_handler(commands=["addtoken", "addtokens", "addtokem", "add_token", "add", "credit"])
def handle_addtoken_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    target_id, amount, err = parse_token_command_args(message, default_cmd="addtoken")
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "👑 <b>Owner (@OwAtom) ke paas already Unlimited Tokens hain!</b>", parse_mode="HTML")
        return

    new_bal = admin_manager.add_tokens(target_id, amount)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else (t_reg.get('first_name') or f"User_{target_id}")

    bot.reply_to(
        message,
        f"✅ <b>Tokens Credited Successfully!</b>\n\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Added:</b> <code>+{amount:,} Tokens</code>\n"
        f"• <b>New Balance:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )

    try:
        bot.send_message(
            target_id,
            f"🎉 <b>Tokens Added to Your Account!</b>\n\n"
            f"• <b>Credited:</b> <code>+{amount:,} Tokens</code>\n"
            f"• <b>New Balance:</b> <b>{new_bal:,} Tokens</b>\n\n"
            f"Aap abhi /start par click karke registration kar sakte hain!",
            parse_mode="HTML"
        )
    except Exception:
        pass


@bot.message_handler(commands=["settoken", "settokens", "settokem", "set_token", "set"])
def handle_settoken_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    target_id, amount, err = parse_token_command_args(message, default_cmd="settoken")
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "👑 <b>Owner (@OwAtom) ke paas already Unlimited Tokens hain!</b>", parse_mode="HTML")
        return

    new_bal = admin_manager.set_tokens(target_id, amount)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else (t_reg.get('first_name') or f"User_{target_id}")

    bot.reply_to(
        message,
        f"✅ <b>Token Balance Updated!</b>\n\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Set To:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["deltoken", "del_token", "deltokens", "deltokem", "deduct", "deducttoken", "deducttokens", "removetoken", "removetokens", "subtoken", "subtokens", "minus", "cuttoken"])
def handle_deltoken_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    target_id, amount, err = parse_token_command_args(message, default_cmd="deduct")
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "⛔ <b>Owner (@OwAtom) ke tokens deduct nahi kiye ja sakte!</b>", parse_mode="HTML")
        return

    new_bal = admin_manager.deduct_tokens(target_id, amount, force=True)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else (t_reg.get('first_name') or f"User_{target_id}")

    bot.reply_to(
        message,
        f"⚪ <b>Tokens Deducted Successfully!</b>\n\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Deducted:</b> <code>-{amount:,} Tokens</code>\n"
        f"• <b>New Balance:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )

    try:
        bot.send_message(
            target_id,
            f"⚠️ <b>Tokens Deducted from Your Account!</b>\n\n"
            f"• <b>Deducted:</b> <code>-{amount:,} Tokens</code>\n"
            f"• <b>Remaining Balance:</b> <b>{new_bal:,} Tokens</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass


@bot.message_handler(commands=["silentaddtoken", "silentaddtokens", "saddtoken", "saddtokens"])
def handle_silentaddtoken_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin / Owner Access Required</b>", parse_mode="HTML")
        return

    target_id, amount, err = parse_token_command_args(message, default_cmd="silentaddtoken")
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "👑 <b>Owner (@OwAtom) ke paas already Unlimited Tokens hain!</b>", parse_mode="HTML")
        return

    new_bal = admin_manager.add_tokens(target_id, amount)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else (t_reg.get('first_name') or f"User_{target_id}")

    bot.reply_to(
        message,
        f"🤫 <b>Silent Token Credit Applied!</b> <i>(No user notification)</i>\n\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Added:</b> <code>+{amount:,} Tokens</code>\n"
        f"• <b>New Balance:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["silentdeducttoken", "silentdeltoken", "sdeducttoken", "sdeltoken", "sdeduct"])
def handle_silentdeducttoken_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin / Owner Access Required</b>", parse_mode="HTML")
        return

    target_id, amount, err = parse_token_command_args(message, default_cmd="silentdeducttoken")
    if err:
        bot.reply_to(message, err, parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "⛔ <b>Owner (@OwAtom) ke tokens deduct nahi kiye ja sakte!</b>", parse_mode="HTML")
        return

    new_bal = admin_manager.deduct_tokens(target_id, amount, force=True)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else (t_reg.get('first_name') or f"User_{target_id}")

    bot.reply_to(
        message,
        f"🤫 <b>Silent Token Deduction Applied!</b> <i>(No user notification)</i>\n\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Deducted:</b> <code>-{amount:,} Tokens</code>\n"
        f"• <b>New Balance:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["adduser"])
def handle_adduser_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    args = message.text.strip().split()
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        bot.reply_to(message, "⚠️ Usage: <code>/adduser &lt;telegram_user_id&gt;</code>", parse_mode="HTML")
        return

    target_id = int(args[1])
    if target_id <= 0:
        bot.reply_to(message, "❌ Please enter a valid positive Telegram user ID.", parse_mode="HTML")
        return

    if target_id == admin_manager.super_admin_id:
        bot.reply_to(message, f"👑 User <code>{target_id}</code> is already Super Admin.", parse_mode="HTML")
        return

    if admin_manager.is_admin(target_id):
        bot.reply_to(message, f"🛡️ User <code>{target_id}</code> is already an Admin!", parse_mode="HTML")
        return

    admin_manager.add_user(target_id)
    bot.reply_to(message, f"✅ User <code>{target_id}</code> added to Whitelist!", parse_mode="HTML")


@bot.message_handler(commands=["deluser", "del", "removeuser"])
def handle_deluser_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    args = message.text.strip().split()
    # Smart shortcut: /del <id> <amount> triggers deltoken
    if len(args) >= 3 and args[1].lstrip("-").isdigit() and args[2].isdigit():
        return handle_deltoken_cmd(message)

    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        bot.reply_to(message, "⚠️ Usage: <code>/deluser &lt;telegram_user_id&gt;</code> or <code>/del &lt;telegram_user_id&gt;</code>", parse_mode="HTML")
        return

    target_id = int(args[1])
    if target_id == admin_manager.super_admin_id:
        bot.reply_to(message, "❌ Cannot remove Super Administrator.", parse_mode="HTML")
        return

    if admin_manager.is_admin(target_id):
        admin_manager.remove_admin(target_id)
        admin_manager.remove_user(target_id)
        bot.reply_to(message, f"⚪ Admin <code>{target_id}</code> demoted and removed.", parse_mode="HTML")
        return

    admin_manager.remove_user(target_id)
    bot.reply_to(message, f"⚪ User <code>{target_id}</code> removed from Whitelist.", parse_mode="HTML")


def resolve_user_id_from_arg(arg: str):
    if not arg:
        return None
    raw = arg.strip()
    if raw.lstrip("-").isdigit():
        return int(raw)
    clean = raw.lstrip("@").lower()
    return admin_manager.get_user_by_username(clean)


@bot.message_handler(commands=["addadmin"])
def handle_addadmin_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>\n<i>Sirf Owner (@OwAtom) naye admin bana sakte hain.</i>", parse_mode="HTML")
        return

    args = message.text.strip().split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Usage: <code>/addadmin &lt;telegram_user_id_ya_username&gt;</code>", parse_mode="HTML")
        return

    target_id = resolve_user_id_from_arg(args[1])
    if not target_id or target_id <= 0:
        bot.reply_to(message, f"❌ Valid Telegram user ID ya registered @username enter karein (User <code>{html.escape(args[1])}</code> nahi mila).", parse_mode="HTML")
        return

    admin_manager.add_admin(target_id)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else f"<code>{target_id}</code>"
    bot.reply_to(message, f"👑 User {t_name} (<code>{target_id}</code>) promoted to 🛡️ <b>Admin</b>!", parse_mode="HTML")


@bot.message_handler(commands=["deladmin"])
def handle_deladmin_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>\n<i>Sirf Owner (@OwAtom) admin hata sakte hain.</i>", parse_mode="HTML")
        return

    args = message.text.strip().split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Usage: <code>/deladmin &lt;telegram_user_id_ya_username&gt;</code>", parse_mode="HTML")
        return

    target_id = resolve_user_id_from_arg(args[1])
    if not target_id or target_id <= 0:
        bot.reply_to(message, f"❌ Valid Telegram user ID ya registered @username enter karein (User <code>{html.escape(args[1])}</code> nahi mila).", parse_mode="HTML")
        return

    if target_id == 8327850869 or admin_manager.is_super_admin(target_id):
        bot.reply_to(message, "❌ Cannot remove Master Owner (@OwAtom)!", parse_mode="HTML")
        return

    admin_manager.remove_admin(target_id)
    t_reg = admin_manager.user_registry.get(str(target_id), {})
    t_name = f"@{t_reg.get('username')}" if t_reg.get('username') else f"<code>{target_id}</code>"
    bot.reply_to(message, f"⚪ Admin {t_name} (<code>{target_id}</code>) demoted to Member.", parse_mode="HTML")





@bot.message_handler(commands=["broadcast"])
def handle_broadcast_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "⚠️ Usage: <code>/broadcast &lt;message&gt;</code>", parse_mode="HTML")
        return

    broadcast_text = parts[1]
    targets = admin_manager.get_all_target_chat_ids()
    sent = 0

    st_msg = bot.reply_to(message, f"📢 Broadcasting to {len(targets)} recipients...", parse_mode="HTML")
    for cid in targets:
        try:
            bot.send_message(
                cid,
                f"📢 <b>Announcement:</b>\n\n{html.escape(broadcast_text)}",
                parse_mode="HTML"
            )
            sent += 1
            time.sleep(0.1)
        except Exception:
            continue

    try:
        bot.edit_message_text(f"✅ Broadcast sent to <b>{sent}/{len(targets)}</b> users!", chat_id=message.chat.id, message_id=st_msg.message_id, parse_mode="HTML")
    except Exception:
        bot.reply_to(message, f"✅ Broadcast sent to <b>{sent}/{len(targets)}</b> users!", parse_mode="HTML")


@bot.message_handler(commands=["cleanup"])
def handle_cleanup_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    cnt = execute_cleanup()
    bot.reply_to(message, f"🧹 <b>Cleanup Complete!</b> Pruned <code>{cnt}</code> temporary files.", parse_mode="HTML")



@bot.message_handler(commands=["sxkey", "setkey", "proxykey"])
def handle_sxkey_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    text = (message.text or "").strip()
    parts = text.split()
    if len(parts) < 2:
        bot.reply_to(
            message,
            "ℹ️ <b>SX.ORG Proxy Key Guide</b>\n\n"
            "Format:\n"
            "<code>/sxkey &lt;YOUR_API_KEY&gt;</code>\n\n"
            "<i>Example:</i>\n"
            "<code>/sxkey EOSZL7qhg8wQvrU47jPWCSjgwNeky7Cc</code>\n\n"
            "💡 <i>Tip: Aap direct key daal sakte hain ya URL bhi paste kar sakte hain. Bot khud connect karke naya 1 GB Indian Rotating Proxy load kar lega!</i>",
            parse_mode="HTML"
        )
        return

    raw_arg = parts[1].strip()
    if "apiKey=" in raw_arg:
        m = re.search(r"apiKey=([a-zA-Z0-9_-]+)", raw_arg)
        api_key = m.group(1) if m else raw_arg
    elif "http" in raw_arg:
        api_key = raw_arg.rstrip("/").split("/")[-1]
    else:
        api_key = raw_arg

    msg_wait = bot.reply_to(message, "🔄 <i>Connecting to SX.ORG API and verifying proxy ports...</i>", parse_mode="HTML")

    res = proxy_manager.setup_sx_from_key(api_key)
    if not res.get("ok"):
        bot.edit_message_text(
            f"❌ <b>SX.ORG Setup Failed:</b>\n\n<code>{res.get('error')}</code>",
            chat_id=message.chat.id,
            message_id=msg_wait.message_id,
            parse_mode="HTML"
        )
        return

    acc = res.get("account", {})
    bal_bytes = acc.get("balance_traffic", 0)
    mb = round(bal_bytes / (1024 * 1024), 2)
    gb = round(bal_bytes / (1024 * 1024 * 1024), 2)

    total_traffic = res.get("total_traffic", bal_bytes)
    tot_mb = round(total_traffic / (1024 * 1024), 2)
    tot_gb = round(total_traffic / (1024 * 1024 * 1024), 2)
    tot_accs = res.get("total_accounts", 1)
    approx_accs = int(total_traffic / (25 * 1024))

    success_msg = (
        f"✅ <b>SX.ORG Proxy Account Linked!</b> 🚀\n\n"
        f"• 🔑 <b>Key Added:</b> <code>{api_key[:8]}...{api_key[-6:]}</code>\n"
        f"• 📊 <b>This Account Quota:</b> <code>{mb} MB (~{gb} GB)</code>\n"
        f"• 🖥 <b>Gateway:</b> <code>{acc.get('proxy_host')}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>TOTAL COMBINED POOL:</b>\n"
        f"• 👥 <b>Active Accounts Linked:</b> <code>{tot_accs}</code>\n"
        f"• 🌐 <b>Total Combined Data:</b> <code>{tot_mb} MB (~{tot_gb} GB)</code>\n"
        f"• ⚡ <b>Estimated Total Capacity:</b> <code>~{approx_accs:,} accounts</code>\n"
        f"• 🔄 <b>Rotation Mode:</b> <i>Round-Robin across all accounts with Indian IP stickiness!</i>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎉 <i>All bulk orders will automatically balance and rotate across all {tot_accs} accounts!</i>"
    )
    bot.edit_message_text(
        success_msg,
        chat_id=message.chat.id,
        message_id=msg_wait.message_id,
        parse_mode="HTML"
    )


@bot.message_handler(commands=["sxstatus", "proxystatus"])
def handle_sxstatus_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    status_text = proxy_manager.get_sx_status()
    bot.reply_to(message, status_text, parse_mode="HTML")


@bot.message_handler(commands=["sxpurge", "cleansx", "purgesx"])
def handle_sxpurge_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    msg_wait = bot.reply_to(message, "🔍 <i>Checking all SX.ORG trial keys and purging expired ones...</i>", parse_mode="HTML")
    purged = proxy_manager.purge_expired_sx_accounts()
    active_count = len(proxy_manager.get_active_sx_accounts())
    if purged:
        text = (
            f"🧹 <b>Expired SX Keys Purged!</b>\n\n"
            f"• <b>Deleted Expired Accounts:</b> <code>{len(purged)}</code>\n"
            f"• <b>Active Accounts Remaining:</b> <code>{active_count}</code>\n\n"
            f"<i>Expired 0 MB keys permanently delete ho chuki hain.</i>"
        )
    else:
        text = f"✅ <b>All SX Accounts Healthy!</b>\n\n• Koi bhi expired key nahi mili. Active accounts: <code>{active_count}</code>."
    bot.edit_message_text(text, chat_id=message.chat.id, message_id=msg_wait.message_id, parse_mode="HTML")


def send_super_audit_file(chat_id, user_id):
    """Sends complete structured text file containing all users, tokens, and registration records."""
    if user_id != 8327850869:
        return
    import io
    acc_file = get_accounts_file()
    all_recs = []
    if acc_file and os.path.exists(acc_file):
        try:
            with open(acc_file, "r", encoding="utf-8", errors="ignore") as f:
                all_recs = parse_account_records(f.readlines())
        except Exception:
            pass

    reg = admin_manager.user_registry
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    buf = io.StringIO()
    buf.write("=" * 90 + "\n")
    buf.write(f"👑 MASTER SUPER ADMIN COMPLETE AUDIT & ACTIVITY REPORT · {now_str}\n")
    buf.write("=" * 90 + "\n\n")

    buf.write("--- 1. REGISTERED USERS & TOKEN BALANCES ---\n")
    buf.write(f"{'User ID':<15} | {'Role':<15} | {'Tokens':<12} | {'Username/Name':<25} | {'Last Active':<20}\n")
    buf.write("-" * 90 + "\n")
    for uid, u in reg.items():
        role = u.get("role", "Free User")
        toks = u.get("tokens", 0)
        uname = f"@{u['username']}" if u.get('username') else (u.get('first_name') or "User")
        la = u.get("last_active", 0)
        la_s = datetime.fromtimestamp(la).strftime("%Y-%m-%d %H:%M:%S") if la else "N/A"
        buf.write(f"{str(uid):<15} | {str(role):<15} | {str(toks):<12} | {str(uname):<25} | {la_s:<20}\n")

    buf.write("\n\n--- 2. ALL REGISTRATION HISTORY CHRONOLOGICAL LOG ---\n")
    buf.write(f"Total Accounts Registered: {len(all_recs)}\n")
    buf.write("-" * 90 + "\n")
    for idx, r in enumerate(all_recs, 1):
        t = r.get("time", "N/A")
        ph = r.get("phone", "N/A")
        pw = r.get("password", "N/A")
        uid_val = r.get("uid", "N/A")
        creator = r.get("user", "System/Direct")
        st = r.get("site", "N/A")
        inv = r.get("invite", "N/A")
        ip = r.get("ip", "N/A")
        buf.write(f"#{idx:03d} [{t}] Phone: {ph} | Pass: {pw} | UID: {uid_val} | Creator: {creator} | Site: {st} | Invite: {inv} | IP: {ip}\n")

    buf.seek(0)
    bio = io.BytesIO(buf.getvalue().encode("utf-8"))
    bio.name = f"super_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    caption = (
        f"👑 <b>Master Super Admin Complete Audit Log</b>\n"
        f"• 👥 Users Registered: <code>{len(reg)}</code>\n"
        f"• 📋 Total Accounts Logged: <code>{len(all_recs)}</code>\n"
        f"• 🕒 Generated: <code>{now_str}</code>"
    )
    bot.send_document(chat_id, bio, caption=caption, parse_mode="HTML")


def show_super_statistics(chat_id, user, message_id=None):
    """Exclusive Super Admin Dashboard for 8327850869 showing users, token counts, and full registration history."""
    user_id = user.id if user else 0
    if user_id != 8327850869:
        bot.send_message(chat_id, "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Master Super Admin ke liye exclusive hai.</i>", parse_mode="HTML")
        return

    reg = admin_manager.user_registry
    total_users = len(reg)
    total_tokens = admin_manager.get_total_distributed_tokens()

    # User & Token records list
    user_lines = []
    sorted_users = sorted(
        reg.values(),
        key=lambda u: (
            0 if u.get("user_id") == 8327850869 else (1 if str(u.get("role", "")).startswith("🛡️") else 2),
            -int(u.get("tokens", 0) if isinstance(u.get("tokens"), (int, float)) else 0)
        )
    )

    for u in sorted_users:
        uid = u.get("user_id")
        u_name = f"@{u['username']}" if u.get('username') else (u.get('first_name') or f"User_{uid}")
        role = u.get("role", "⚪ Free User")
        toks = u.get("tokens", 0)
        tok_str = f"{toks:,}" if isinstance(toks, int) else str(toks)
        last_act = u.get("last_active", 0)
        la_str = datetime.fromtimestamp(last_act).strftime("%d-%m %H:%M") if last_act else "N/A"
        user_lines.append(f"• <code>{uid}</code> | <b>{html.escape(u_name)}</b>\n  └ {role} | 🎫 <b>{tok_str} Tokens</b> | 🕒 <code>{la_str}</code>")

    # Read all accounts history
    acc_file = get_accounts_file()
    all_recs = []
    if acc_file and os.path.exists(acc_file):
        try:
            with open(acc_file, "r", encoding="utf-8", errors="ignore") as f:
                all_recs = parse_account_records(f.readlines())
        except Exception:
            pass

    total_accs = len(all_recs)

    # Count registrations per user
    user_acc_counts = {}
    for r in all_recs:
        u_creator = r.get("user") or "System/Direct"
        user_acc_counts[u_creator] = user_acc_counts.get(u_creator, 0) + 1

    user_reg_breakdown = []
    for u_creator, cnt in sorted(user_acc_counts.items(), key=lambda x: -x[1]):
        u_meta = reg.get(str(u_creator), {})
        u_display = f"@{u_meta['username']}" if u_meta.get('username') else f"ID: {u_creator}"
        user_reg_breakdown.append(f"  • {u_display}: <b>{cnt} accounts</b>")

    # Recent registration events (last 6)
    recent_events = []
    for r in reversed(all_recs[-6:]):
        t_str = r.get("time", "N/A")
        u_creator = r.get("user") or "N/A"
        u_meta = reg.get(str(u_creator), {})
        u_tag = f"@{u_meta['username']}" if u_meta.get('username') else (f"ID: {u_creator}" if u_creator != "N/A" else "System")
        s = r.get("site", "N/A")
        s_clean = urllib.parse.urlparse(s).netloc or s
        ph = r.get("phone", "N/A")
        uid_val = r.get("uid", "N/A")
        recent_events.append(f"  • <code>[{t_str}]</code> {u_tag}\n    └ 📱 <code>{ph}</code> | UID: <code>{uid_val}</code> | 🌐 {s_clean}")

    # Proxy quota info
    sx_accounts = proxy_manager.get_active_sx_accounts()
    sx_total_data = sum(a.get("balance_traffic", 0) for a in sx_accounts)
    sx_mb = round(sx_total_data / (1024 * 1024), 2)
    sx_gb = round(sx_total_data / (1024 * 1024 * 1024), 2)

    text = (
        f"👑 <b>MASTER SUPER ADMIN AUDIT &amp; STATISTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Summary Overview:</b>\n"
        f"• 👥 <b>Total Users:</b> <code>{total_users} users</code>\n"
        f"• 🎫 <b>Total Tokens Circulating:</b> <code>{total_tokens:,} Tokens</code>\n"
        f"• 📦 <b>Total Accounts Registered:</b> <code>{total_accs} accounts</code>\n"
        f"• 🌐 <b>SX.ORG Proxy Quota:</b> <code>{len(sx_accounts)} keys ({sx_mb} MB / ~{sx_gb} GB)</code>\n\n"
        "👥 <b>User Tokens Inventory:</b>\n"
        + "\n".join(user_lines[:8]) + ("\n<i>...and more in audit file</i>" if len(user_lines) > 8 else "") + "\n\n"
        "📈 <b>Registrations Per User:</b>\n"
        + ("\n".join(user_reg_breakdown[:5]) if user_reg_breakdown else "  <i>No user registrations recorded yet.</i>") + "\n\n"
        "🕒 <b>Recent Registration History:</b>\n"
        + ("\n".join(recent_events) if recent_events else "  <i>No history logs yet.</i>") + "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Full detailed audit file download karne ke liye niche button dabayein.</i>"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_file = types.InlineKeyboardButton("📥 Download Full Audit Log (.txt)", callback_data="super_export_audit")
    b_refresh = types.InlineKeyboardButton("🔄 Refresh Stats", callback_data="super_stats_refresh")
    markup.add(b_file)
    markup.add(b_refresh)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


@bot.message_handler(commands=["statics", "stats", "superstats", "statistics", "audit"])
def handle_super_statistics_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869:
        bot.reply_to(
            message,
            "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Super Admin (@OwAtom) ke liye exclusive hai.</i>",
            parse_mode="HTML"
        )
        return
    show_super_statistics(message.chat.id, user)
 
 
@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith("/"))
def handle_general_text_fallback(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return
    clean = message.text.strip()
    if ("." in clean and len(clean.split()) == 1 and not clean.isdigit()) or "invitationcode=" in clean.lower() or "invitecode=" in clean.lower():
        process_and_save_link(chat_id, clean, orig_msg=message)
        return
    show_link_options(chat_id, user, del_incoming=message)



# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK QUERY DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════

def _handle_callback_clicks_inner(call):
    user = call.from_user
    user_id = user.id
    data = call.data
    chat_id = call.message.chat.id if (call.message and getattr(call.message, 'chat', None)) else user_id
    msg_id = call.message.message_id if call.message else None

    admin_manager.record_user(user_id, user.username or "", user.first_name or "")
    log(f"[bot] Callback: user={user_id} ({user.first_name or 'User'}) action='{data}'")

    # Identity button
    if data == "btn_my_id":
        try:
            bot.answer_callback_query(call.id, f"Your Telegram ID: {user_id}", show_alert=True)
        except Exception:
            pass
        return

    # Force Join Verification
    if data == "verify_join":
        is_mem, reason = check_user_membership(user_id)
        if is_mem:
            try:
                bot.answer_callback_query(call.id, "✅ Membership Verified! Welcome to the bot.")
            except Exception:
                pass
            show_link_prompt(chat_id, user, message_id=msg_id)
        elif reason == "bot_not_admin":
            try:
                bot.answer_callback_query(
                    call.id,
                    "⚠️ Bot is not Admin in @owabyss channel! Channel owner must make @dmadsasadsadas_bot admin in channel to enable verification.",
                    show_alert=True
                )
            except Exception:
                pass
            show_force_join_screen(chat_id, user, message_id=msg_id)
        else:
            try:
                bot.answer_callback_query(
                    call.id,
                    "❌ Aapne abhi tak @owabyss join nahi kiya hai! Pehle channel join karein.",
                    show_alert=True
                )
            except Exception:
                pass
            show_force_join_screen(chat_id, user, message_id=msg_id)
        return

    # Check Channel Membership for all core actions
    if not is_user_member(user_id):
        try:
            bot.answer_callback_query(call.id, "⚠️ Pehle @owabyss channel join karein!", show_alert=True)
        except Exception:
            pass
        show_force_join_screen(chat_id, user, message_id=msg_id)
        return

    # Navigation & Core Actions
    if data in ("show_start", "start_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        CUSTOM_REG_STATE.pop(user_id, None)
        CUSTOM_SPEED_STATE.pop(user_id, None)
        show_link_prompt(chat_id, user, message_id=msg_id)

    elif data in ("show_link_options", "link_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_link_options(chat_id, user, message_id=msg_id)

    elif data == "ask_new_link":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_link_prompt(chat_id, user, message_id=msg_id)

    elif data == "my_tokens":
        tok_disp = admin_manager.get_display_tokens(user_id)
        try:
            bot.answer_callback_query(call.id, f"Your Balance: {tok_disp} (1 Token = 1 Account)", show_alert=True)
        except Exception:
            pass

    # ─── Single Registration ───
    elif data in ("reg_single", "single_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_single_menu(chat_id, user, message_id=msg_id)

    elif data in ("single_random", "auto_reg"):
        cfg = get_chat_config(chat_id)
        if cfg.get("sms_required"):
            try:
                bot.answer_callback_query(
                    call.id,
                    "❌ Platform Enforces SMS OTP!\n\nRandom generated numbers cannot receive SMS OTP. Please use 'Custom Details' with a real mobile number.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        if is_chat_busy(chat_id):
            try:
                bot.answer_callback_query(call.id, "⏳ Registration in progress! Please wait a moment.", show_alert=True)
            except Exception:
                pass
            return

        if not admin_manager.has_enough_tokens(user_id, 1):
            cur_tok = admin_manager.get_tokens(user_id)
            try:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Insufficient Tokens!\n\n💰 Your Balance: {cur_tok} Tokens\n🎟️ Required: 1 Token",
                    show_alert=True
                )
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, "Starting random registration (1 🎫)...")
        except Exception:
            pass
        threading.Thread(target=run_registration_and_send_ss, args=(chat_id, user_id, None, None, None, msg_id), daemon=True).start()

    elif data == "single_custom":
        if is_chat_busy(chat_id):
            try:
                bot.answer_callback_query(call.id, "⏳ Registration in progress! Please wait a moment.", show_alert=True)
            except Exception:
                pass
            return

        if not admin_manager.has_enough_tokens(user_id, 1):
            cur_tok = admin_manager.get_tokens(user_id)
            try:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Insufficient Tokens!\n\n💰 Your Balance: {cur_tok} Tokens\n🎟️ Required: 1 Token",
                    show_alert=True
                )
            except Exception:
                pass
            return

        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        cfg = get_chat_config(chat_id)
        sms_req = cfg.get("sms_required", False)
        steps_total = 3 if sms_req else 2

        CUSTOM_REG_STATE[user_id] = {
            "chat_id": chat_id,
            "step": "phone",
            "phone": None,
            "password": None,
            "mid": msg_id,
            "sms_required": sms_req
        }

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg"))

        text = (
            f"📱 <b>Custom Registration — Step 1/{steps_total}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 <b>Platform:</b> <code>{cfg['site']}</code>\n\n"
            f"Kripya account ke liye <b>10-digit Indian Mobile Number</b> bhejein:\n"
            f"<i>(Example: 9876543210)</i>\n\n"
            f"💡 <i>Chat me number likh kar send karein ya Cancel dabayein.</i>"
        )
        send_or_edit(chat_id, text, reply_markup=markup, message_id=msg_id)

    elif data == "cancel_custom_reg":
        CUSTOM_REG_STATE.pop(user_id, None)
        try:
            bot.answer_callback_query(call.id, "Registration cancelled.")
        except Exception:
            pass
        show_single_menu(chat_id, user, message_id=msg_id)

    # ─── Multi-Registration ───
    elif data in ("reg_multi", "bulk_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_multi_menu(chat_id, user, message_id=msg_id)

    elif data == "multi_custom":
        cfg = get_chat_config(chat_id)
        if cfg.get("sms_required"):
            try:
                bot.answer_callback_query(
                    call.id,
                    "⛔ Platform Enforces SMS OTP!\n\nBulk registration is paused for this platform to save your tokens. Please use Single Registration -> Custom Details.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_custom_amount_prompt(chat_id, user, message_id=msg_id)

    elif data.startswith("multi_run_") or data.startswith("bulk_run_"):
        cfg = get_chat_config(chat_id)
        if cfg.get("sms_required"):
            try:
                bot.answer_callback_query(
                    call.id,
                    "⛔ Platform Enforces SMS OTP!\n\nBulk registration is paused for this platform to save your tokens. Please use Single Registration -> Custom Details.",
                    show_alert=True
                )
            except Exception:
                pass
            return

        if is_chat_busy(chat_id):
            try:
                bot.answer_callback_query(call.id, "⏳ Multi-Registration in progress! Please wait a moment.", show_alert=True)
            except Exception:
                pass
            return

        raw_num = data.replace("multi_run_", "").replace("bulk_run_", "")
        try:
            count = int(raw_num)
        except Exception:
            count = 5

        if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()):
            avail = admin_manager.get_tokens(user_id)
            if avail <= 0:
                try:
                    bot.answer_callback_query(call.id, "❌ 0 Tokens! Recharge to use Multi-Registration.", show_alert=True)
                except Exception:
                    pass
                return

        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_speed_selection_menu(chat_id, user, count, message_id=msg_id)

    elif data == "multi_sched":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_custom_scheduled_count_prompt(chat_id, user, message_id=msg_id)

    elif data.startswith("sched_cnt_"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        cnt = int(data.split("_")[2])
        if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
            avail = admin_manager.get_tokens(user_id)
            if avail < cnt:
                try:
                    bot.answer_callback_query(call.id, f"❌ Insufficient Tokens (Available: {avail})", show_alert=True)
                except Exception:
                    pass
                return
        show_custom_scheduled_minutes_prompt(chat_id, user, count=cnt, message_id=msg_id)

    elif data.startswith("sched_min_"):
        parts = data.split("_")
        cnt = int(parts[2])
        mins = int(parts[3])
        CUSTOM_SCHEDULED_STATE.pop(user_id, None)
        try:
            bot.answer_callback_query(call.id, f"🚀 Scheduled: {cnt} accounts in {mins}m")
        except Exception:
            pass
        threading.Thread(
            target=run_custom_scheduled_registration,
            args=(chat_id, user_id, cnt, mins, msg_id),
            daemon=True
        ).start()

    elif data.startswith("bspeed_"):
        parts = data.split("_")
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
        speed_mode = parts[2] if len(parts) > 2 else "0"

        if speed_mode == "sched":
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass
            show_custom_scheduled_minutes_prompt(chat_id, user, count=count, message_id=msg_id)
            return

        if speed_mode == "custom":
            CUSTOM_SPEED_STATE[user_id] = {
                "count": count,
                "chat_id": chat_id,
                "mid": msg_id,
                "time": time.time()
            }
            try:
                bot.answer_callback_query(call.id)
            except Exception:
                pass
            text = (
                f"⏱️ <b>Custom Speed Configuration</b>\n\n"
                f"• 🎯 <b>Batch Count:</b> <code>{count} Accounts</code>\n\n"
                f"Niche chat me desired delay ya duration send karein:\n\n"
                f"• <b>Per-ID Delay:</b> <code>5s</code>, <code>10s</code>, <code>15s</code> (seconds gap between accounts)\n"
                f"• <b>Total Time:</b> <code>2m</code>, <code>5m</code> (total batch duration in minutes)\n"
                f"• <b>Fastest:</b> <code>fast</code> ya <code>0</code> (zero delay)\n\n"
                f"💡 <i>Example: Send <code>8s</code> for 8 seconds gap between each registration.</i>"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Cancel / Back", callback_data=f"multi_run_{count}"))
            send_or_edit(chat_id, text, reply_markup=markup, message_id=msg_id)
            return

        delay = 0.0
        label = "⚡ FASTEST (Turbo)"
        if speed_mode == "3":
            delay = 3.0
            label = "🛡️ SAFE (3s Delay)"
        elif speed_mode == "6":
            delay = 6.0
            label = "🐢 STEALTH (6s Delay)"

        try:
            bot.answer_callback_query(call.id, f"Speed: {label}")
        except Exception:
            pass

        threading.Thread(
            target=run_bulk_registration,
            args=(chat_id, user_id, count, msg_id, delay, label),
            daemon=True
        ).start()

    elif data == "export_txt":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_export_menu(chat_id, user, message_id=msg_id)

    elif data == "do_export_combos":
        try:
            bot.answer_callback_query(call.id, "Generating Phone:Pass Combos...")
        except Exception:
            pass
        threading.Thread(target=send_exported_combos, args=(chat_id, user_id), daemon=True).start()

    elif data == "do_export_full":
        try:
            bot.answer_callback_query(call.id, "Generating Full Report...")
        except Exception:
            pass
        threading.Thread(target=send_exported_full_report, args=(chat_id, user_id), daemon=True).start()

    elif data == "do_export_both":
        try:
            bot.answer_callback_query(call.id, "Generating Combos & Full Report...")
        except Exception:
            pass
        threading.Thread(target=send_exported_both, args=(chat_id, user_id), daemon=True).start()

    elif data == "show_help":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_help_menu(chat_id, user, message_id=msg_id)

    # ─── Admin Exclusive Callbacks ───
    elif data in ("menu_admin", "admin_panel"):
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_admin_menu(chat_id, user, message_id=msg_id)

    elif data == "admin_users":
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_users_list(chat_id, user, message_id=msg_id)



    elif data == "admin_cleanup":
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        cnt = execute_cleanup()
        try:
            bot.answer_callback_query(call.id, f"🧹 Pruned {cnt} temporary files!", show_alert=True)
        except Exception:
            pass
        show_admin_menu(chat_id, user, message_id=msg_id)

    elif data == "admin_token_help":
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "🎫 <b>Token Management Commands Guide:</b>\n\n"
            "• <code>/addtoken &lt;user_id&gt; &lt;amount&gt;</code>\n"
            "  <i>Credits tokens to a user's balance and notifies them.</i>\n\n"
            "• <code>/settoken &lt;user_id&gt; &lt;exact_amount&gt;</code>\n"
            "  <i>Sets exact token balance for a user.</i>\n\n"
            "• <code>/deltoken &lt;user_id&gt; &lt;amount&gt;</code>\n"
            "  <i>Deducts tokens from a user.</i>\n\n"
            "💡 <b>Example:</b>\n"
            "<code>/addtoken 8327850869 25</code>",
            parse_mode="HTML"
        )

    elif data == "admin_broadcast_info":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "📢 <b>Broadcast Announcement:</b>\n\nUse command:\n<code>/broadcast &lt;your message&gt;</code>\n\nAll registered users will receive the message.",
            parse_mode="HTML"
        )

    elif data == "admin_adduser_help":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "➕ <b>Add User to Whitelist:</b>\n\nUse command:\n<code>/adduser &lt;telegram_user_id&gt;</code>\n\nExample:\n<code>/adduser 1234567890</code>",
            parse_mode="HTML"
        )

    elif data == "admin_sx_status":
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        status_text = proxy_manager.get_sx_status()
        bot.send_message(chat_id, status_text, parse_mode="HTML")
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

    elif data == "super_export_audit":
        if user_id != 8327850869:
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, "Generating Master Audit File...")
        except Exception:
            pass
        threading.Thread(target=send_super_audit_file, args=(chat_id, user_id), daemon=True).start()

    elif data == "super_stats_refresh":
        if user_id != 8327850869:
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, "Refreshing Statistics...")
        except Exception:
            pass
        show_super_statistics(chat_id, user, message_id=msg_id)

    elif data.startswith("stop_reg_"):
        try:
            target_cid = int(data.split("_")[2])
        except Exception:
            target_cid = chat_id

        is_super = (user_id == 8327850869)
        is_adm = is_super or admin_manager.is_admin(user_id)
        if target_cid != chat_id and target_cid != user_id and not is_adm:
            try:
                bot.answer_callback_query(call.id, "⛔ You cannot stop another user's session.", show_alert=True)
            except Exception:
                pass
            return

        ok = request_stop_session(target_cid)
        if ok:
            try:
                bot.answer_callback_query(call.id, "🛑 Stopping registration... Batch will halt safely!", show_alert=True)
            except Exception:
                pass
        else:
            try:
                bot.answer_callback_query(call.id, "ℹ️ Session already finished or not active.", show_alert=True)
            except Exception:
                pass
        show_active_sessions_dashboard(chat_id, user, message_id=msg_id)

    elif data == "sessions_refresh":
        try:
            bot.answer_callback_query(call.id, "Refreshing sessions...")
        except Exception:
            pass
        show_active_sessions_dashboard(chat_id, user, message_id=msg_id)

    elif data == "sessions_stop_all":
        if user_id != 8327850869:
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        cnt = request_stop_all_sessions()
        try:
            bot.answer_callback_query(call.id, f"🛑 Stopped all {cnt} active sessions!", show_alert=True)
        except Exception:
            pass
        show_active_sessions_dashboard(chat_id, user, message_id=msg_id)

    elif data == "admin_sessions":
        if not admin_manager.is_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin Access Required", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_active_sessions_dashboard(chat_id, user, message_id=msg_id)

    else:
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_clicks(call):
    try:
        _handle_callback_clicks_inner(call)
    except Exception as e:
        log(f"[bot] Unhandled error in callback handler: {e}")
        try:
            bot.answer_callback_query(call.id, "⚠️ Error handling action. Please retry.")
        except Exception:
            pass


# ─── Cloud Health Check Server (Port 8080) for 24/7 Hosting ───
def start_health_server(port=8080):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","bot":"raxi4_bot","service":"alive"}')
        def log_message(self, format, *args):
            pass
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        log(f"[Health] Cloud health check server active on port {port} ✅")
    except Exception as e:
        log(f"[Health] Warning starting health server: {e} ⚠️")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log("=" * 60)
    log("Starting Multi-Site Auto-Register Bot with Fixed Export & Robust Proxies...")
    log(f"Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    log(f"Super Admin: {admin_manager.super_admin_id}")
    log(f"Admins: {admin_manager.admin_user_ids}")
    log(f"Force Join Channel: {REQUIRED_CHANNEL}")
    try:
        me = bot.get_me()
        chat_member = bot.get_chat_member(REQUIRED_CHANNEL, me.id)
        if chat_member.status in ("administrator", "creator"):
            log(f"Channel Status: VERIFIED (Bot is Admin in {REQUIRED_CHANNEL}) ✅")
        else:
            log(f"Channel Status: WARNING (Bot NOT Admin in {REQUIRED_CHANNEL}) ⚠️ - Promote bot to Admin")
    except Exception as e:
        log(f"Channel Status: WARNING (Cannot access member list: {e}) ⚠️")

    # Start Cloud Health Server on Port 8080
    start_health_server(8080)

    # SX.ORG Rotating Indian Residential Proxy Engine
    log("[ProxyEngine] SX.ORG Rotating Indian Residential Proxy Engine active! ✅")

    log("=" * 60)

    try:
        bot.set_my_commands([
            types.BotCommand("start", "🚀 Main Menu & Setup"),
            types.BotCommand("single", "⚡ Single Registration"),
            types.BotCommand("multi", "🔢 Multi Registration"),
            types.BotCommand("stop", "🛑 Stop Running Registration"),
            types.BotCommand("sessions", "📊 Active Registration Tasks"),
            types.BotCommand("tokens", "🎫 Check Token Balance"),
            types.BotCommand("link", "🔗 Set / Change Referral Link"),
            types.BotCommand("export", "📋 Export Saved Accounts"),
            types.BotCommand("help", "❓ Commands Guide"),
            types.BotCommand("status", "⚡ Bot & Server Status"),
        ])
        log("[bot] Telegram bot command menu registered successfully! ✅")
    except Exception as e:
        log(f"[bot] Warning setting bot commands: {e}")

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        log(f"[bot] Warning removing webhook: {e}")

    log("[bot] Starting telegram infinity_polling loop...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except KeyboardInterrupt:
            log("Bot stopped by user.")
            break
        except Exception as e:
            log(f"[bot] Polling network exception: {e}. Auto-reconnecting in 5s...")
            time.sleep(5)

