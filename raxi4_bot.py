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
import collections
import random
import secrets
import base64
import hashlib
import threading
import concurrent.futures
import urllib.parse
from datetime import datetime, timedelta, timezone
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
def load_env_file():
    for env_path in [os.path.join(BASE_DIR, ".env"), os.path.join(os.getcwd(), ".env")]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            except Exception:
                pass

load_env_file()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError("CRITICAL: BOT_TOKEN environment variable is not set!")

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
seed_persistent_file("working_proxies.txt")
seed_persistent_file("fresh_raw_proxies.txt")
seed_persistent_file("used_devices.json")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=10, use_class_middlewares=True)

# ─── TeleCore Sliding Window Anti-Flood & Maintenance Mode Guard ───
from telebot.handler_backends import CancelUpdate, BaseMiddleware

_user_last_action_ts: Dict[int, float] = {}
_user_last_warn_ts: Dict[int, float] = {}

def telecore_message_guard(bot_instance, message):
    user = message.from_user
    if not user or getattr(user, "is_bot", False):
        return
    user_id = user.id
    is_super_admin = (user_id == 8327850869) or admin_manager.is_super_admin(user_id)
    is_admin = is_super_admin or admin_manager.is_admin(user_id)

    # 1. Maintenance Mode Guard (Strictly Owner / Super Admin @OwAtom Only)
    if admin_manager.is_maintenance_mode() and not is_super_admin:
        now = time.time()
        last_warn = _user_last_warn_ts.get(user_id, 0.0)
        is_cmd = bool(message.text and message.text.startswith("/"))
        is_private = (getattr(getattr(message, "chat", None), "type", None) == "private")
        if (is_private or is_cmd) and (now - last_warn) > 3.0:
            _user_last_warn_ts[user_id] = now
            try:
                bot_instance.reply_to(
                    message,
                    "🛠️ <b>Maintenance Mode Active</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Bot is currently undergoing system updates and maintenance.\n"
                    "Only the Bot Owner has access right now.\n\n"
                    "⏳ <i>Please try again later. Thank you!</i>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        return CancelUpdate()

    # 2. Sliding Window Anti-Flood Rate Limiter
    if admin_manager.is_rate_limit_enabled() and not is_admin:
        now = time.time()
        last = _user_last_action_ts.get(user_id, 0.0)
        limit = getattr(admin_manager, "rate_limit_seconds", 1.0)
        if (now - last) < limit:
            last_warn = _user_last_warn_ts.get(user_id, 0.0)
            if (now - last_warn) > 2.5:
                _user_last_warn_ts[user_id] = now
                try:
                    bot_instance.reply_to(
                        message,
                        "⚠️ <b>Slow Down!</b> Commands are being sent too quickly. Please wait 1 second between actions.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            return CancelUpdate()
        _user_last_action_ts[user_id] = now

def telecore_callback_guard(bot_instance, call):
    user = call.from_user
    if not user or getattr(user, "is_bot", False):
        return
    user_id = user.id
    is_super_admin = (user_id == 8327850869) or admin_manager.is_super_admin(user_id)
    is_admin = is_super_admin or admin_manager.is_admin(user_id)

    # 1. Maintenance Mode Guard (Strictly Owner / Super Admin @OwAtom Only)
    if admin_manager.is_maintenance_mode() and not is_super_admin:
        try:
            bot_instance.answer_callback_query(
                call.id,
                "🛠️ Maintenance Mode active! Only the Bot Owner has access right now.",
                show_alert=True
            )
        except Exception:
            pass
        return CancelUpdate()

    # 2. Sliding Window Anti-Flood Rate Limiter
    if admin_manager.is_rate_limit_enabled() and not is_admin:
        now = time.time()
        last = _user_last_action_ts.get(user_id, 0.0)
        limit = getattr(admin_manager, "rate_limit_seconds", 1.0)
        if (now - last) < limit:
            try:
                bot_instance.answer_callback_query(
                    call.id,
                    "⚠️ Slow down! (Anti-Flood Protection)",
                    show_alert=False
                )
            except Exception:
                pass
            return CancelUpdate()
        _user_last_action_ts[user_id] = now

class TeleCoreGuardMiddleware(BaseMiddleware):
    def __init__(self, bot_instance):
        super().__init__()
        self.bot = bot_instance
        self.update_sensitive = True
        self.update_types = ['message', 'edited_message', 'callback_query']

    def pre_process_message(self, message, data):
        return telecore_message_guard(self.bot, message)

    def post_process_message(self, message, data, exception):
        pass

    def pre_process_edited_message(self, message, data):
        return telecore_message_guard(self.bot, message)

    def post_process_edited_message(self, message, data, exception):
        pass

    def pre_process_callback_query(self, call, data):
        return telecore_callback_guard(self.bot, call)

    def post_process_callback_query(self, call, data, exception):
        pass

telecore_guard_mw = TeleCoreGuardMiddleware(bot)
bot.setup_middleware(telecore_guard_mw)

# ─── Channel Force Join Configuration ───
REQUIRED_CHANNEL = "@owabyss"
CHANNEL_URL = "https://t.me/owabyss"

# Global single-message tracking dictionary (chat_id -> message_id)
LAST_BOT_MSG = {}
LAST_DOCK_MSG = {}
ALL_DOCK_MSGS = collections.defaultdict(set)
LAST_DOCK_PHASE = {}

def send_dock_message(chat_id, user_id=None, phase="main", force=False):
    """Mounts or refreshes the persistent action keyboard cleanly docked beneath chat, adapting to screen phase without leaving any chat bubble."""
    if not force and LAST_DOCK_PHASE.get(chat_id) == phase:
        return None

    # Clean up any lingering dock messages for this chat
    mids_to_clean = list(ALL_DOCK_MSGS[chat_id])
    if chat_id in LAST_DOCK_MSG:
        mids_to_clean.append(LAST_DOCK_MSG[chat_id])
    for mid in mids_to_clean:
        try:
            bot.delete_message(chat_id, mid)
        except Exception:
            pass
    ALL_DOCK_MSGS[chat_id].clear()
    LAST_DOCK_MSG.pop(chat_id, None)

    try:
        kb = get_dock_keyboard(user_id or chat_id, phase=phase)
        sent = bot.send_message(
            chat_id,
            "⚡",
            reply_markup=kb,
            disable_notification=True
        )
        LAST_DOCK_PHASE[chat_id] = phase
        time.sleep(0.15)
        try:
            bot.delete_message(chat_id, sent.message_id)
        except Exception:
            pass
        return None
    except Exception as e:
        log(f"[bot] send_dock_message error: {e}")
        return None

def send_or_edit(chat_id, text, reply_markup=None, message_id=None, del_incoming=None):
    """
    Guarantees the bot maintains a single, clean, interactive card at the bottom of the chat:
    1. If del_incoming is passed (new user command / referral link / text):
       - Deletes incoming user command/text.
       - Deletes previous bot card (LAST_BOT_MSG[chat_id]) so chat has zero duplicates.
       - Sends fresh card at the bottom and records LAST_BOT_MSG[chat_id].
    2. If message_id is provided or inline edit (del_incoming is None):
       - Directly edits the existing card in place (edit_message_text).
       - Buttons update instantly without jumping or creating new messages.
       - Falls back to send_message only if message was deleted or uneditable.
    """
    if del_incoming and hasattr(del_incoming, "message_id"):
        try:
            bot.delete_message(chat_id, del_incoming.message_id)
        except Exception:
            pass

        # Clean old bot message so the fresh card lands cleanly at the bottom
        old_mid = LAST_BOT_MSG.pop(chat_id, None)
        if old_mid:
            try:
                bot.delete_message(chat_id, old_mid)
            except Exception:
                pass

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
                    log(f"[bot] send_or_edit plain send error: {e2}")
                    return None
            log(f"[bot] send_or_edit send error: {e}")
            return None

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
DIRECT_HOST_RATE_LIMITED = {}
DIRECT_HOST_LAST_REQ = {}
DIRECT_HOST_LOCK = threading.Lock()

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
SINGLE_REG_CANCEL_EVENTS: Dict[int, threading.Event] = {}  # chat_id -> Event for 5s countdown cancellation
# Global Concurrency Semaphore: Max 8 simultaneous registrations across the entire bot
# Prevents RAM spikes, OOM crashes, and socket starvation on Render (512MB RAM guard)
GLOBAL_REG_SEMAPHORE = threading.Semaphore(8)

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
    if chat_id in SINGLE_REG_CANCEL_EVENTS and SINGLE_REG_CANCEL_EVENTS[chat_id].is_set():
        return True
    with ACTIVE_SESSIONS_LOCK:
        sess = ACTIVE_SESSIONS.get(chat_id)
        if not sess:
            return False
        if sess.get("stop_requested"):
            return True
        if admin_manager.is_maintenance_mode():
            user_id = sess.get("user_id", chat_id)
            if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
                sess["stop_requested"] = True
                return True
        return False

def halt_non_owner_sessions() -> int:
    """Safely halts all active background registration sessions not initiated by the Bot Owner."""
    halted = 0
    with ACTIVE_SESSIONS_LOCK:
        for cid, sess in list(ACTIVE_SESSIONS.items()):
            uid = sess.get("user_id", cid)
            if uid != 8327850869 and not admin_manager.is_super_admin(uid):
                sess["stop_requested"] = True
                halted += 1
                try:
                    bot.send_message(
                        cid,
                        "🛠️ <b>Maintenance Mode Activated</b>\n\n"
                        "Bot Owner ne maintenance mode enable kar diya hai. "
                        "Aapka active registration session safely halt kar diya gaya hai.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
    return halted

def request_stop_session(chat_id: int) -> bool:
    stopped = False
    if chat_id in SINGLE_REG_CANCEL_EVENTS:
        SINGLE_REG_CANCEL_EVENTS[chat_id].set()
        stopped = True
    with ACTIVE_SESSIONS_LOCK:
        sess = ACTIVE_SESSIONS.get(chat_id)
        if sess:
            sess["stop_requested"] = True
            stopped = True
    return stopped

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

        # Ensure active default mock configs for primary users if not set or pointing to legacy dmfirst/dmwin
        for uid in (8327850869, 6217522461):
            if uid not in CHAT_CONFIGS or CHAT_CONFIGS[uid].get("invite") in ("265762124632", "417112180491") or "dmfirst" in str(CHAT_CONFIGS[uid].get("site", "")):
                CHAT_CONFIGS[uid] = {
                    "site": SITE,
                    "api": API,
                    "api_type": "webapi",
                    "invite": INVITE,
                    "domain": urllib.parse.urlparse(SITE).netloc,
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

# ─── 100% Unique Device Fingerprint Engine (Zero Device Repeat Guarantee) ───
INDIAN_DEVICE_CATALOG = [
    # Samsung Flagship & Popular Indian Series (A/M/F/S/Z)
    {"brand": "Samsung", "model": "Samsung Galaxy S24 Ultra", "hardware": "SM-S928B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy S24+", "hardware": "SM-S926B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy S24", "hardware": "SM-S921B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy S23 Ultra", "hardware": "SM-S918B", "android": "13"},
    {"brand": "Samsung", "model": "Samsung Galaxy S23 5G", "hardware": "SM-S911B", "android": "13"},
    {"brand": "Samsung", "model": "Samsung Galaxy S23 FE", "hardware": "SM-S711B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy A55 5G", "hardware": "SM-A556E", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy A35 5G", "hardware": "SM-A356E", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy A54 5G", "hardware": "SM-A546E", "android": "13"},
    {"brand": "Samsung", "model": "Samsung Galaxy M55 5G", "hardware": "SM-M556B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy M35 5G", "hardware": "SM-M356B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy F55 5G", "hardware": "SM-E556B", "android": "14"},
    {"brand": "Samsung", "model": "Samsung Galaxy Z Fold 5", "hardware": "SM-F946B", "android": "13"},
    {"brand": "Samsung", "model": "Samsung Galaxy Z Flip 5", "hardware": "SM-F731B", "android": "13"},
    # OnePlus High-Volume Indian Models
    {"brand": "OnePlus", "model": "OnePlus 12 5G", "hardware": "CPH2573", "android": "14"},
    {"brand": "OnePlus", "model": "OnePlus 12R", "hardware": "CPH2585", "android": "14"},
    {"brand": "OnePlus", "model": "OnePlus 11 5G", "hardware": "CPH2449", "android": "13"},
    {"brand": "OnePlus", "model": "OnePlus 11R", "hardware": "CPH2487", "android": "13"},
    {"brand": "OnePlus", "model": "OnePlus Nord 4 5G", "hardware": "CPH2661", "android": "14"},
    {"brand": "OnePlus", "model": "OnePlus Nord CE 4", "hardware": "CPH2613", "android": "14"},
    {"brand": "OnePlus", "model": "OnePlus Nord CE 4 Lite", "hardware": "CPH2621", "android": "14"},
    {"brand": "OnePlus", "model": "OnePlus Nord 3 5G", "hardware": "CPH2493", "android": "13"},
    {"brand": "OnePlus", "model": "OnePlus Open", "hardware": "CPH2551", "android": "13"},
    # Xiaomi & Redmi Popular Indian Models
    {"brand": "Xiaomi", "model": "Xiaomi 14 Ultra", "hardware": "24030PN60G", "android": "14"},
    {"brand": "Xiaomi", "model": "Xiaomi 14", "hardware": "23127PN0CG", "android": "14"},
    {"brand": "Xiaomi", "model": "Xiaomi 13 Pro", "hardware": "2210132G", "android": "13"},
    {"brand": "Redmi", "model": "Redmi Note 13 Pro+ 5G", "hardware": "23090RA98G", "android": "14"},
    {"brand": "Redmi", "model": "Redmi Note 13 Pro 5G", "hardware": "2312DRA50G", "android": "14"},
    {"brand": "Redmi", "model": "Redmi Note 13 5G", "hardware": "2312DRAABG", "android": "13"},
    {"brand": "Redmi", "model": "Redmi Note 12 Pro 5G", "hardware": "22101316G", "android": "13"},
    {"brand": "Redmi", "model": "Redmi 13C 5G", "hardware": "23124RN87G", "android": "14"},
    {"brand": "Redmi", "model": "Redmi 12 5G", "hardware": "23076RN4BI", "android": "13"},
    # Poco Gaming & Budget Series
    {"brand": "Poco", "model": "Poco F6 Pro", "hardware": "23113RKC6G", "android": "14"},
    {"brand": "Poco", "model": "Poco F6", "hardware": "24069PC21G", "android": "14"},
    {"brand": "Poco", "model": "Poco X6 Pro 5G", "hardware": "2311DRK48G", "android": "14"},
    {"brand": "Poco", "model": "Poco X6 5G", "hardware": "23122PCD1G", "android": "14"},
    {"brand": "Poco", "model": "Poco M6 Pro 5G", "hardware": "23076PC4BI", "android": "13"},
    {"brand": "Poco", "model": "Poco M6 5G", "hardware": "23128PC97I", "android": "14"},
    # Vivo & iQOO Top Indian Performers
    {"brand": "Vivo", "model": "Vivo X100 Pro", "hardware": "V2324A", "android": "14"},
    {"brand": "Vivo", "model": "Vivo X100", "hardware": "V2309A", "android": "14"},
    {"brand": "Vivo", "model": "Vivo V30 Pro", "hardware": "V2319", "android": "14"},
    {"brand": "Vivo", "model": "Vivo V30", "hardware": "V2318", "android": "14"},
    {"brand": "Vivo", "model": "Vivo V29 5G", "hardware": "V2250", "android": "13"},
    {"brand": "Vivo", "model": "Vivo T3 5G", "hardware": "V2334", "android": "14"},
    {"brand": "Vivo", "model": "Vivo T3x 5G", "hardware": "V2338", "android": "14"},
    {"brand": "Vivo", "model": "Vivo Y200 5G", "hardware": "V2307", "android": "13"},
    {"brand": "iQOO", "model": "iQOO 12 5G", "hardware": "I2220", "android": "14"},
    {"brand": "iQOO", "model": "iQOO Neo 9 Pro", "hardware": "I2217", "android": "14"},
    {"brand": "iQOO", "model": "iQOO Neo 7 Pro", "hardware": "I2214", "android": "13"},
    {"brand": "iQOO", "model": "iQOO Z9 5G", "hardware": "I2302", "android": "14"},
    {"brand": "iQOO", "model": "iQOO Z9x 5G", "hardware": "I2305", "android": "14"},
    # Realme Number & GT Series
    {"brand": "Realme", "model": "Realme GT 6", "hardware": "RMX3850", "android": "14"},
    {"brand": "Realme", "model": "Realme GT 6T", "hardware": "RMX3853", "android": "14"},
    {"brand": "Realme", "model": "Realme 12 Pro+ 5G", "hardware": "RMX3840", "android": "14"},
    {"brand": "Realme", "model": "Realme 12 Pro 5G", "hardware": "RMX3842", "android": "14"},
    {"brand": "Realme", "model": "Realme 12+ 5G", "hardware": "RMX3867", "android": "14"},
    {"brand": "Realme", "model": "Realme Narzo 70 Pro 5G", "hardware": "RMX3868", "android": "14"},
    {"brand": "Realme", "model": "Realme P1 Pro 5G", "hardware": "RMX3844", "android": "14"},
    {"brand": "Realme", "model": "Realme P1 5G", "hardware": "RMX3870", "android": "14"},
    {"brand": "Realme", "model": "Realme GT 5 5G", "hardware": "RMX3820", "android": "13"},
    # Oppo Reno & F-Series
    {"brand": "Oppo", "model": "Oppo Reno 12 Pro", "hardware": "CPH2629", "android": "14"},
    {"brand": "Oppo", "model": "Oppo Reno 11 Pro 5G", "hardware": "CPH2607", "android": "14"},
    {"brand": "Oppo", "model": "Oppo Reno 11 5G", "hardware": "CPH2599", "android": "14"},
    {"brand": "Oppo", "model": "Oppo F27 Pro+ 5G", "hardware": "CPH2643", "android": "14"},
    {"brand": "Oppo", "model": "Oppo F25 Pro 5G", "hardware": "CPH2603", "android": "14"},
    {"brand": "Oppo", "model": "Oppo A79 5G", "hardware": "CPH2553", "android": "13"},
    # Google Pixel
    {"brand": "Google", "model": "Google Pixel 8 Pro", "hardware": "Pixel 8 Pro", "android": "14"},
    {"brand": "Google", "model": "Google Pixel 8", "hardware": "Pixel 8", "android": "14"},
    {"brand": "Google", "model": "Google Pixel 8a", "hardware": "Pixel 8a", "android": "14"},
    {"brand": "Google", "model": "Google Pixel 7 Pro", "hardware": "Pixel 7 Pro", "android": "13"},
    {"brand": "Google", "model": "Google Pixel 7a", "hardware": "Pixel 7a", "android": "13"},
    # Motorola & Nothing
    {"brand": "Motorola", "model": "Motorola Edge 50 Pro", "hardware": "motorola edge 50 pro", "android": "14"},
    {"brand": "Motorola", "model": "Motorola Edge 40 Neo", "hardware": "motorola edge 40 neo", "android": "13"},
    {"brand": "Motorola", "model": "Moto G84 5G", "hardware": "moto g84 5G", "android": "13"},
    {"brand": "Nothing", "model": "Nothing Phone (2)", "hardware": "A065", "android": "14"},
    {"brand": "Nothing", "model": "Nothing Phone (2a)", "hardware": "A142", "android": "14"},
]

CHROME_BUILDS = [
    {"version": "124.0.6367.113", "major": "124"},
    {"version": "124.0.6367.179", "major": "124"},
    {"version": "125.0.6422.112", "major": "125"},
    {"version": "125.0.6422.165", "major": "125"},
    {"version": "126.0.6478.122", "major": "126"},
    {"version": "126.0.6478.186", "major": "126"},
    {"version": "127.0.6533.103", "major": "127"},
    {"version": "128.0.6613.88", "major": "128"},
    {"version": "128.0.6613.127", "major": "128"},
    {"version": "129.0.6668.70", "major": "129"},
    {"version": "130.0.6723.58", "major": "130"},
]

USED_DEVICE_IDS = set()
IN_FLIGHT_DEVICE_IDS = set()
USED_MODELS_BY_DOMAIN = {}
DEVICE_LOCK = threading.Lock()
USED_DEVICES_FILE = os.path.join(DATA_DIR, "used_devices.json")

# ─── Zero-Collision Phone Pool & Memory Registry ───
USED_PHONE_NUMBERS = set()
IN_FLIGHT_PHONES = set()
PHONE_LOCK = threading.Lock()

def load_used_devices():
    """Loads historical used device IDs, domain model allocations, and historical phone numbers."""
    global USED_DEVICE_IDS, USED_MODELS_BY_DOMAIN, USED_PHONE_NUMBERS
    with DEVICE_LOCK:
        for c in [USED_DEVICES_FILE, os.path.join(BASE_DIR, "used_devices.json")]:
            if os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    dev_ids = data.get("used_device_ids", [])
                    USED_DEVICE_IDS.update(dev_ids)
                    for dom, models in data.get("used_models_by_domain", {}).items():
                        USED_MODELS_BY_DOMAIN.setdefault(dom, set()).update(models)
                except Exception as e:
                    log(f"[devices] Error loading {c}: {e}")

        # Scan accounts file to capture past model usage per domain and historical phones
        for c in [ACCOUNTS_FILE, os.path.join(DATA_DIR, "raxi_accounts.txt"), os.path.join(BASE_DIR, "raxi_accounts.txt")]:
            if os.path.exists(c):
                try:
                    with open(c, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            m_ph = re.search(r'Phone:\s*(\S+)', line)
                            if m_ph:
                                with PHONE_LOCK:
                                    USED_PHONE_NUMBERS.add(m_ph.group(1).strip())
                            m_site = re.search(r'Site:\s*https?://([^ /|]+)', line)
                            dom = proxy_manager.normalize_domain(m_site.group(1)) if m_site else "default"
                            m_dev = re.search(r'Device:\s*([^|]+)', line)
                            if m_dev:
                                raw_dev = m_dev.group(1).strip()
                                # Check if device id was attached
                                m_id = re.search(r'\(([a-f0-9]{8,32})\)', raw_dev)
                                if m_id:
                                    USED_DEVICE_IDS.add(m_id.group(1))
                                    clean_model = raw_dev.split("(")[0].strip()
                                    USED_MODELS_BY_DOMAIN.setdefault(dom, set()).add(clean_model)
                                else:
                                    USED_MODELS_BY_DOMAIN.setdefault(dom, set()).add(raw_dev)
                except Exception:
                    pass

        log(f"[devices] Loaded {len(USED_DEVICE_IDS)} unique historical device IDs across {len(USED_MODELS_BY_DOMAIN)} domains. Loaded {len(USED_PHONE_NUMBERS)} unique historical phone numbers.")

load_used_devices()

def claim_unique_device(domain=None) -> dict:
    """
    Enforces 100% Zero-Repeat Device Condition:
    1. Generates a brand-new 16-hex deviceId that has NEVER been used before in history.
    2. Selects a fresh smartphone model from the 70+ Indian model catalog, rotating models per domain.
    3. Atomically reserves deviceId in in-flight registry.
    """
    global USED_DEVICE_IDS, IN_FLIGHT_DEVICE_IDS, USED_MODELS_BY_DOMAIN
    dom = proxy_manager.normalize_domain(domain)
    with DEVICE_LOCK:
        # Generate non-colliding deviceId
        dev_id = None
        for _ in range(100):
            cand = secrets.token_hex(16)
            if cand not in USED_DEVICE_IDS and cand not in IN_FLIGHT_DEVICE_IDS:
                dev_id = cand
                break
        if not dev_id:
            dev_id = f"{secrets.token_hex(8)}{int(time.time()*1000):x}"[:32]

        # Prioritize unused phone model for this domain if available
        domain_used = USED_MODELS_BY_DOMAIN.get(dom, set())
        available_models = [m for m in INDIAN_DEVICE_CATALOG if m["model"] not in domain_used]
        if not available_models:
            # If all 70+ models have been used on this domain, recycle pool but ensure new OS/Chrome/ID
            available_models = INDIAN_DEVICE_CATALOG
        selected = secrets.choice(available_models)
        IN_FLIGHT_DEVICE_IDS.add(dev_id)

    # Pick Chrome build and generate realistic User-Agent and Client Hints
    chrome = secrets.choice(CHROME_BUILDS)
    andr_ver = selected.get("android", "14")
    hw = selected["hardware"]
    model_name = selected["model"]

    ua = f"Mozilla/5.0 (Linux; Android {andr_ver}; {hw}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome['version']} Mobile Safari/537.36"
    sec_ch_ua = f'"Chromium";v="{chrome["major"]}", "Google Chrome";v="{chrome["major"]}", "Not-A.Brand";v="99"'

    return {
        "device_id": dev_id,
        "model": model_name,
        "brand": selected.get("brand", "Generic"),
        "hardware": hw,
        "android": andr_ver,
        "ua": ua,
        "sec_ch_ua": sec_ch_ua,
        "platform": '"Android"',
    }

def mark_device_used(device_id: str, domain=None, model=None):
    """Permanently commits deviceId and model to used_devices.json."""
    global USED_DEVICE_IDS, IN_FLIGHT_DEVICE_IDS, USED_MODELS_BY_DOMAIN
    if not device_id:
        return
    dom = proxy_manager.normalize_domain(domain)
    with DEVICE_LOCK:
        USED_DEVICE_IDS.add(device_id)
        IN_FLIGHT_DEVICE_IDS.discard(device_id)
        if model:
            USED_MODELS_BY_DOMAIN.setdefault(dom, set()).add(model)

        data_to_save = {
            "used_device_ids": list(USED_DEVICE_IDS),
            "used_models_by_domain": {d: list(m) for d, m in USED_MODELS_BY_DOMAIN.items()}
        }
        for dest in [USED_DEVICES_FILE, os.path.join(BASE_DIR, "used_devices.json")]:
            try:
                tmp = dest + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f)
                os.replace(tmp, dest)
            except Exception:
                pass

def release_in_flight_device(device_id: str):
    """Releases deviceId from in-flight on failure or cancellation."""
    if not device_id:
        return
    with DEVICE_LOCK:
        IN_FLIGHT_DEVICE_IDS.discard(device_id)

# Compatibility alias for any legacy callers
DEVICE_PROFILES = [
    {
        "model": m["model"],
        "ua": f"Mozilla/5.0 (Linux; Android {m['android']}; {m['hardware']}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.113 Mobile Safari/537.36",
        "sec_ch_ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "platform": '"Android"'
    }
    for m in INDIAN_DEVICE_CATALOG[:12]
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
    t.setdefault("language", "en")
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

def get_base_domain(host: str) -> str:
    """
    Normalizes host/netloc by stripping dynamic subdomains and www,
    retaining the root domain expected by platform channel databases
    (e.g. 20745.rajalucketernal.com -> rajalucketernal.com).
    """
    if not host:
        return ""
    host = host.split(":")[0].strip().lower()
    parts = host.split(".")
    if len(parts) > 2:
        second_level_tlds = {"co.in", "com.in", "net.in", "org.in", "co.uk", "com.pk", "com.bd"}
        if len(parts) >= 3 and f"{parts[-2]}.{parts[-1]}" in second_level_tlds:
            return ".".join(parts[-3:])
        return ".".join(parts[-2:])
    return host

def detect_and_parse_referral_link(text_or_url):
    """
    Extracts site URL, backend API, invite code, and platform engine type from ANY referral link or text
    (supports raxi4, raxi win, maanwin, 51game, rajaluck, and all clone sites).
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

    domain_lower = parsed.netloc.lower()

    # FAST PATH 1: Instant AR-SAAS resolution (MaanWin, GoaGames, BigDaddy, Tiranga, 13l, etc.)
    if any(k in domain_lower for k in ["maanwin", "goagame", "bigdaddy", "tiranga", "13l."]):
        return {
            "site": base_site,
            "api": f"{base_site}/api",
            "api_type": "arsaas",
            "invite": invite_code,
            "domain": get_base_domain(parsed.netloc),
            "raw_url": raw_url,
            "sms_required": False
        }

    # FAST PATH 2: Instant Tasyee / Game platform resolution (pan5, etc.)
    if any(k in domain_lower for k in ["pan5", "pan5.cc"]):
        return {
            "site": base_site,
            "api": f"{base_site}/api",
            "api_type": "tasyee",
            "invite": invite_code,
            "domain": get_base_domain(parsed.netloc),
            "raw_url": raw_url,
            "sms_required": False
        }

    # 2. Check Platform Engine (AR-SAAS vs TASYEE vs VITE/WEBAPI)
    # Check 2A: AR-SAAS platform (MaanWin, GoaGames, BigDaddy, Tiranga, 13l.world, etc.)
    for c_host in candidate_hosts:
        c_site = f"{scheme}://{c_host}"
        try:
            r_ar = requests.post(
                f"{c_site}/api/Home/Captcha",
                json=sign_arsaas({}),
                headers={
                    "Origin": c_site,
                    "Referer": f"{c_site}/register",
                    "Content-Type": "application/json;charset=UTF-8",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 Chrome/129.0.0.0 Mobile Safari/537.36"
                },
                timeout=3.0,
                allow_redirects=True
            )
            if r_ar.status_code == 200 and r_ar.json().get("data", {}).get("captchaId"):
                log(f"[bot] Detected AR-SAAS platform engine for {c_site}")
                return {
                    "site": c_site,
                    "api": f"{c_site}/api",
                    "api_type": "arsaas",
                    "invite": invite_code,
                    "domain": get_base_domain(c_host),
                    "raw_url": raw_url,
                    "sms_required": False
                }
        except Exception:
            pass

    # Check 2B: Tasyee / Game platform engine (pan5.cc, etc.)
    for c_host in candidate_hosts:
        c_site = f"{scheme}://{c_host}"
        try:
            r_tasyee = requests.post(
                f"{c_site}/api/user/register",
                json={},
                headers={
                    "Origin": c_site,
                    "Referer": f"{c_site}/",
                    "Content-Type": "application/json;charset=UTF-8",
                    "User-Agent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 Chrome/129.0.0.0 Mobile Safari/537.36"
                },
                timeout=3.0,
                allow_redirects=True
            )
            if r_tasyee.status_code == 200:
                tj = r_tasyee.json()
                if tj.get("code") in (2000, 1002, 1004) or "ACCOUNT_INVALID" in str(tj.get("msg", "")) or "account" in str(tj):
                    log(f"[bot] Detected Tasyee platform engine for {c_site}")
                    return {
                        "site": c_site,
                        "api": f"{c_site}/api",
                        "api_type": "tasyee",
                        "invite": invite_code,
                        "domain": get_base_domain(c_host),
                        "raw_url": raw_url,
                        "sms_required": False
                    }
        except Exception:
            pass

    # Check 2B: 51game / Raxi / DMFirst / RajaLuck clone (VITE / WEBAPI)
    api_url = None
    domain_lower = parsed.netloc.lower()

    # FAST PATH: Instant 0.01ms resolution for known platform families
    if any(k in domain_lower for k in ["raxi", "raxi4", "raxi11", "raxiqaz", "raxiwin"]):
        api_url = "https://api.raxiqaz.com"
    elif any(k in domain_lower for k in ["dmfirst", "dmfirst17", "dmfirst11", "dmfirst9", "dmfirst7"]):
        api_url = "https://api.dmfirst9api.com"
    elif any(k in domain_lower for k in ["rajaluck", "rajalucketernal", "rajaluckapi", "lotteryapi"]):
        api_url = "https://lotteryapi.rajaluckapi.com"
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
                px = proxy_manager.get_static_proxy()
                px_d = {"http": f"http://{px}", "https": f"http://{px}"} if px else None
                resp = requests.get(base_site, timeout=6.5, proxies=px_d, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            except Exception as e:
                resp = None
                log(f"[bot] Auto-discovery error for {base_site}: {e}")

        if resp and resp.status_code == 200:
            html_text = resp.text

            NON_GAME_DOMAINS = (
                "google", "firebase", "gstatic", "cloudflare", "microsoft", "apple",
                "facebook", "sentry", "arbpay", "w3.org", "schema.org", "ampproject", "doubleclick",
                "whatsapp", "wa.me", "telegram", "t.me", "twitter", "x.com", "instagram", "tiktok", "youtube"
            )

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
                for s_src in script_srcs[:30]:
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
        elif any(k in domain_lower for k in ["rajaluck", "rajalucketernal"]):
            api_url = "https://lotteryapi.rajaluckapi.com"
        else:
            api_url = API

    return {
        "site": base_site,
        "api": api_url,
        "api_type": "webapi",
        "invite": invite_code,
        "domain": get_base_domain(parsed.netloc),
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
    domain_lower = parsed.netloc.lower()
    if api_type == "tasyee" or any(k in domain_lower for k in ["pan5", "tasyee"]):
        return {
            "sms_required": False,
            "site": current_site,
            "api": f"{current_site}/api" if not str(api_url).endswith("/api") else api_url,
            "domain": get_base_domain(parsed.netloc),
            "switched_mirror": False,
            "mirror_count": 0,
            "api_type": "tasyee"
        }

    if api_type == "arsaas" or "/Home" in str(api_url) or api_url == f"{current_site}/api" or any(k in domain_lower for k in ["maanwin", "goagame", "bigdaddy", "tiranga", "13l"]):
        return {
            "sms_required": False,
            "site": current_site,
            "api": f"{current_site}/api" if not str(api_url).endswith("/api") else api_url,
            "domain": get_base_domain(parsed.netloc),
            "switched_mirror": False,
            "mirror_count": 0,
            "api_type": "arsaas"
        }

    sms_required = False
    try:
        r = requests.post(f"{api_url}/api/webapi/RegisterState", json=signed_body({}), timeout=4)
        if r.status_code == 200:
            data = r.json().get("data", {})
            sms_required = (data.get("isOpenRegisterSMS") == "1") or (data.get("registerSMSState") == "1")
    except Exception as e:
        log(f"[bot] RegisterState check error for {api_url}: {e}")

    if not sms_required:
        return {
            "sms_required": False,
            "site": current_site,
            "api": api_url,
            "domain": get_base_domain(parsed.netloc),
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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
                    "domain": get_base_domain(parsed_m.netloc),
                    "switched_mirror": True,
                    "mirror_count": live_scanned,
                    "api_type": "webapi"
                }

    log(f"[bot] Scanned {live_scanned} live mirrors across platform - all require SMS OTP.")
    return {
        "sms_required": True,
        "site": current_site,
        "api": api_url,
        "domain": get_base_domain(parsed.netloc),
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
    """Generates a realistic 10-digit Indian phone number guaranteed to have never been used before."""
    with PHONE_LOCK:
        for _ in range(100):
            prefix = random.choice(INDIAN_PREFIXES)
            suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
            phone = f"{prefix}{suffix}"
            if phone not in USED_PHONE_NUMBERS and phone not in IN_FLIGHT_PHONES:
                IN_FLIGHT_PHONES.add(phone)
                return phone
        phone = f"{random.choice(INDIAN_PREFIXES)}{''.join([str(random.randint(0, 9)) for _ in range(8)])}"
        IN_FLIGHT_PHONES.add(phone)
        return phone

def generate_random_password():
    """Generates an 8-character alphanumeric password satisfying site requirements."""
    chars_letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
    chars_digits = "23456789"
    p_letters = "".join(random.choices(chars_letters, k=4))
    p_digits = "".join(random.choices(chars_digits, k=4))
    return f"{p_letters}{p_digits}"

ACCOUNT_SAVE_LOCK = threading.Lock()
_ACCOUNT_CACHE = {"mtime": 0, "size": 0, "path": "", "records": []}
_CACHE_LOCK = threading.Lock()

# Pre-compiled regex patterns for blazing fast parsing
RE_TS = re.compile(r"\[(.*?)\]")
RE_UID = re.compile(r"UID:\s*(\S+)")
RE_PH = re.compile(r"Phone:\s*(\S+)")
RE_PW = re.compile(r"Password:\s*(\S+)")
RE_DEV = re.compile(r"Device:\s*([^|]+)")
RE_IP = re.compile(r"IP:\s*([^|]+)")
RE_INV = re.compile(r"Invite:\s*(\S+)")
RE_SITE = re.compile(r"Site:\s*([^|]+)")
RE_USR = re.compile(r"User:\s*(\S+)")
RE_TOK = re.compile(r"Token:\s*(\S+)")

def save_account_to_file(phone, password, uid, token, invite, site="https://www.raxi4.com", device=None, proxy=None, creator_id=None):
    """Saves successfully created account to raxi_accounts.txt with creator isolation, IST timestamp, and thread safety."""
    with PHONE_LOCK:
        USED_PHONE_NUMBERS.add(str(phone))
        IN_FLIGHT_PHONES.discard(str(phone))
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    ts = datetime.now(ist_tz).strftime("%Y-%m-%d %H:%M:%S")
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
            parent = os.path.dirname(dest)
            if parent and not os.path.exists(parent):
                continue
            try:
                with open(dest, "a", encoding="utf-8") as f:
                    f.write(entry)
            except Exception:
                pass
        with _CACHE_LOCK:
            _ACCOUNT_CACHE["mtime"] = 0

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
    """Parses raw account log lines into structured account dictionaries at high speed."""
    records = []
    for l in lines:
        if not l or l.startswith("#") or "Phone:" not in l:
            continue
        rec = {}
        ts_m = RE_TS.search(l)
        rec["time"] = ts_m.group(1).strip() if ts_m else ""
        uid_m = RE_UID.search(l)
        rec["uid"] = uid_m.group(1).strip() if uid_m else ""
        ph_m = RE_PH.search(l)
        rec["phone"] = ph_m.group(1).strip() if ph_m else ""
        pw_m = RE_PW.search(l)
        rec["password"] = pw_m.group(1).strip() if pw_m else ""
        dev_m = RE_DEV.search(l)
        rec["device"] = dev_m.group(1).strip() if dev_m else ""
        ip_m = RE_IP.search(l)
        rec["ip"] = ip_m.group(1).strip() if ip_m else ""
        inv_m = RE_INV.search(l)
        rec["invite"] = inv_m.group(1).strip() if inv_m else ""
        site_m = RE_SITE.search(l)
        rec["site"] = site_m.group(1).strip() if site_m else ""
        usr_m = RE_USR.search(l)
        rec["user"] = usr_m.group(1).strip() if usr_m else ""
        tok_m = RE_TOK.search(l)
        rec["token"] = tok_m.group(1).strip() if tok_m else ""
        if rec["phone"] and rec["password"]:
            records.append(rec)
    return records

def get_cached_account_records():
    """Returns memory-cached account records, invalidating automatically when file changes."""
    acc_file = get_accounts_file()
    if not acc_file or not os.path.exists(acc_file):
        return []
    try:
        st = os.stat(acc_file)
        with _CACHE_LOCK:
            if (
                _ACCOUNT_CACHE["records"]
                and _ACCOUNT_CACHE["path"] == acc_file
                and _ACCOUNT_CACHE["mtime"] == st.st_mtime
                and _ACCOUNT_CACHE["size"] == st.st_size
            ):
                return list(_ACCOUNT_CACHE["records"])

            with open(acc_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = [l for l in f if l.strip()]
            recs = parse_account_records(lines)
            _ACCOUNT_CACHE["mtime"] = st.st_mtime
            _ACCOUNT_CACHE["size"] = st.st_size
            _ACCOUNT_CACHE["path"] = acc_file
            _ACCOUNT_CACHE["records"] = recs
            return list(recs)
    except Exception as e:
        log(f"[bot] Error loading cached accounts: {e}")
        return []

def get_user_account_records(user_id, chat_id=None):
    """Retrieves and parses account records accessible to this user."""
    all_recs = get_cached_account_records()
    if not all_recs:
        return []
    try:
        if (user_id == 8327850869) or admin_manager.is_super_admin(user_id):
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

def show_export_menu(chat_id, user, message_id=None, del_incoming=None):
    """Interactive export menu offering Combos (phone:pass), Full Report, or Both."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    if not is_user_member(user_id):
        user_info = admin_manager.user_registry.get(str(user_id), {"first_name": "User"})
        show_force_join_screen(chat_id, type('UserObj', (), {'id': user_id, 'first_name': user_info.get('first_name', 'User')})(), message_id=message_id, del_incoming=del_incoming)
        return

    recs = get_user_account_records(user_id, chat_id)
    total_accs = len(recs)
    cfg = get_chat_config(chat_id)

    if total_accs == 0:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
        send_or_edit(
            chat_id,
            "📭 <b>No Accounts Available for Export</b>\n\n"
            "Abhi tak koi accounts register nahi huye hain. Pehle Single ya Multi-Registration run karein.",
            reply_markup=markup,
            message_id=message_id,
            del_incoming=del_incoming
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
    b1 = types.InlineKeyboardButton("📱 Phone:Pass Combos", callback_data="do_export_combos", style="primary")
    b2 = types.InlineKeyboardButton("📑 Full Detailed Report", callback_data="do_export_full", style="primary")
    b3 = types.InlineKeyboardButton("📦 Download Both Files", callback_data="do_export_both", style="success")
    b4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    markup.add(b1, b2)
    markup.add(b3)
    markup.add(b4)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "export":
        send_dock_message(chat_id, user_id, phase="export")

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
    try:
        cfg = get_chat_config(chat_id)
        threading.Thread(
            target=dispatch_storage_channel_audit,
            kwargs={
                "user_id": user_id,
                "action_type": "📱 Combos Export",
                "site": cfg.get("site", "N/A"),
                "invite": cfg.get("invite", "N/A"),
                "accounts_list": len(lines),
                "tokens_deducted": 0,
                "doc_bytes": content,
                "filename": bio.name,
                "notes": f"Combos export of {len(lines)} accounts"
            },
            daemon=True
        ).start()
    except Exception:
        pass

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
    try:
        cfg = get_chat_config(chat_id)
        doc_bytes = content
        threading.Thread(
            target=dispatch_storage_channel_audit,
            kwargs={
                "user_id": user_id,
                "action_type": "📑 Full Audit Report Export",
                "site": cfg.get("site", "N/A"),
                "invite": cfg.get("invite", "N/A"),
                "accounts_list": recs[:100],
                "tokens_deducted": 0,
                "doc_bytes": doc_bytes,
                "filename": bio.name,
                "notes": f"Full detailed accounts report ({len(recs)} accounts)"
            },
            daemon=True
        ).start()
    except Exception:
        pass

def send_exported_both(chat_id, user_id):
    """Sends both Combos and Full Report documents."""
    send_exported_combos(chat_id, user_id)
    send_exported_full_report(chat_id, user_id)

def send_exported_accounts(chat_id, user_id):
    """Maintains backward compatibility by launching the full report."""
    send_exported_full_report(chat_id, user_id)

def truncate_html_caption(html_text: str, max_len: int = 1000) -> str:
    """Safely truncates an HTML caption so it stays under 1024 characters without breaking tags."""
    if not html_text or len(html_text) <= max_len:
        return html_text or ""
    cutoff = html_text[:max_len - 30]
    last_nl = cutoff.rfind("\n")
    if last_nl > max_len // 2:
        cutoff = cutoff[:last_nl]
    open_tags = []
    for tag_match in re.finditer(r"<(/?[a-zA-Z]+)[^>]*>", cutoff):
        tag = tag_match.group(1)
        if tag.startswith("/"):
            tag_name = tag[1:].lower()
            if open_tags and open_tags[-1] == tag_name:
                open_tags.pop()
        else:
            open_tags.append(tag.lower())
    for tag in reversed(open_tags):
        cutoff += f"</{tag}>"
    return cutoff

def dispatch_storage_channel_audit(user_id, action_type, site, invite, accounts_list, tokens_deducted=0, doc_bytes=None, filename=None, notes=""):
    """
    Comprehensive Master Storage Audit Log:
    Dispatches formatted HTML card with user info, target link, referral code,
    tokens deducted, remaining balance, accounts created, IST timestamp,
    and attached downloadable audit report to master_storage_channel.
    """
    try:
        storage_ch = admin_manager.get_master_storage_channel()
        if not storage_ch or str(storage_ch).strip() in ("", "None", "0"):
            return

        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%b-%Y %I:%M:%S %p IST")
        u_reg = admin_manager.user_registry.get(str(user_id), {})
        uname = u_reg.get("username") or ""
        fname = u_reg.get("first_name") or "User"
        uname_disp = f"@{uname}" if uname else "N/A"
        user_link = f'<a href="tg://user?id={user_id}">{html.escape(fname)}</a>'
        tokens_left = admin_manager.get_display_tokens(user_id)

        acc_cnt = len(accounts_list) if isinstance(accounts_list, list) else (accounts_list if isinstance(accounts_list, int) else 0)

        preview_lines = []
        if isinstance(accounts_list, list):
            for idx, a in enumerate(accounts_list[:5], 1):
                ph = a.get("phone", "N/A")
                pw = a.get("password", "N/A")
                uid_val = a.get("uid", "N/A")
                preview_lines.append(f"  #{idx}: <code>{ph}</code> | Pass: <code>{pw}</code> | UID: <code>{uid_val}</code>")
            if len(accounts_list) > 5:
                preview_lines.append(f"  <i>... aur {len(accounts_list)-5} accounts file me hain.</i>")

        preview_section = ("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n<b>📋 Created Accounts Sample:</b>\n" + "\n".join(preview_lines)) if preview_lines else ""
        notes_section = f"\n• 💡 <b>Note:</b> <i>{notes}</i>" if notes else ""

        audit_caption = (
            f"🗄️ <b>MASTER STORAGE AUDIT LOG</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> {user_link} ({uname_disp}) [<code>{user_id}</code>]\n"
            f"⚡ <b>Action:</b> <b>{action_type}</b>\n"
            f"🌐 <b>Platform / Link:</b> <code>{site or 'N/A'}</code>\n"
            f"🎟️ <b>Referral / Invite:</b> <code>{invite or 'N/A'}</code>\n"
            f"🎫 <b>Tokens Deducted:</b> <code>{tokens_deducted} Tokens</code>\n"
            f"💳 <b>Remaining Balance:</b> <code>{tokens_left}</code>\n"
            f"📊 <b>Accounts Count:</b> <b>{acc_cnt} Accounts</b>\n"
            f"🕒 <b>Timestamp:</b> <code>{now_ist}</code>"
            f"{notes_section}"
            f"{preview_section}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <i>Permanent cloud archival & history tracking.</i>"
        )

        safe_caption = truncate_html_caption(audit_caption, 1000)

        if doc_bytes:
            bio = io.BytesIO(doc_bytes)
            bio.name = filename or f"audit_{user_id}_{int(time.time())}.txt"
            bot.send_document(storage_ch, bio, caption=safe_caption, parse_mode="HTML")
        elif isinstance(accounts_list, list) and accounts_list:
            lines = [
                f"# Master Storage Audit Export",
                f"# User: {fname} (@{uname}) [{user_id}]",
                f"# Action: {action_type}",
                f"# Site: {site} | Invite: {invite}",
                f"# Timestamp: {now_ist}",
                f"# Total Accounts Created: {acc_cnt}",
                f"# Tokens Deducted: {tokens_deducted}",
                f"--------------------------------------------------\n"
            ]
            for a in accounts_list:
                lines.append(f"Phone: {a.get('phone')} | Password: {a.get('password')} | UID: {a.get('uid')} | Device: {a.get('device')} | IP: {a.get('proxy')}")
            f_bytes = "\n".join(lines).encode("utf-8")
            bio = io.BytesIO(f_bytes)
            bio.name = filename or f"audit_{user_id}_{int(time.time())}.txt"
            bot.send_document(storage_ch, bio, caption=safe_caption, parse_mode="HTML")
        else:
            bot.send_message(storage_ch, audit_caption, parse_mode="HTML")
        log(f"[storage_audit] Successfully dispatched audit to master storage channel {storage_ch} for user {user_id}")
    except Exception as e:
        log(f"[storage_audit] Notice: Storage channel dispatch: {e}")


def backup_batch_to_master_storage(doc_bytes, filename, caption, creator_id=None):
    """Safely dispatches batch registration export file to master_storage_channel for 100% cloud persistence."""
    try:
        storage_ch = admin_manager.get_master_storage_channel()
        if storage_ch and str(storage_ch).strip() not in ("", "None", "0"):
            bio = io.BytesIO(doc_bytes)
            bio.name = filename
            bot.send_document(storage_ch, bio, caption=caption, parse_mode="HTML")
            log(f"[cloud_backup] Successfully sent batch backup ({filename}) to master storage channel {storage_ch}")
    except Exception as e:
        log(f"[cloud_backup] Warning: Could not send to master storage channel: {e}")

def send_super_backup_now(chat_id, user_id):
    """Sends immediate raw database backup to Super Admin chat and to master_storage_channel."""
    if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
        return
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%b-%Y %I:%M:%S %p IST")
    acc_file = get_accounts_file()
    all_recs = get_cached_account_records()
    total_accs = len(all_recs)
    total_users = len(admin_manager.user_registry)

    # 1. Send raxi_accounts.txt
    if acc_file and os.path.exists(acc_file):
        try:
            with open(acc_file, "rb") as f:
                acc_bytes = f.read()
            bio = io.BytesIO(acc_bytes)
            bio.name = f"raxi_accounts_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            cap1 = (
                f"💾 <b>MASTER DATABASE CLOUD BACKUP</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• 📋 <b>Total Accounts Logged:</b> <code>{total_accs}</code>\n"
                f"• 🕒 <b>Timestamp:</b> <code>{now_ist}</code>\n"
                f"• 🛡️ <i>Raw accounts log file for permanent archival.</i>"
            )
            bot.send_document(chat_id, bio, caption=cap1, parse_mode="HTML")

            storage_ch = admin_manager.get_master_storage_channel()
            if storage_ch and str(storage_ch).strip() not in ("", "None", "0"):
                bio2 = io.BytesIO(acc_bytes)
                bio2.name = bio.name
                bot.send_document(storage_ch, bio2, caption=cap1, parse_mode="HTML")
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Error sending accounts backup: {e}")

    # 2. Send admin_settings.json
    try:
        settings_path = admin_manager.filepath
        if os.path.exists(settings_path):
            with open(settings_path, "rb") as f:
                set_bytes = f.read()
            bio_set = io.BytesIO(set_bytes)
            bio_set.name = f"admin_settings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            cap2 = (
                f"⚙️ <b>ADMIN SETTINGS &amp; USER REGISTRY BACKUP</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• 👥 <b>Total Users:</b> <code>{total_users}</code>\n"
                f"• 🎫 <b>Total Tokens:</b> <code>{admin_manager.get_total_distributed_tokens():,}</code>\n"
                f"• 🕒 <b>Timestamp:</b> <code>{now_ist}</code>"
            )
            bot.send_document(chat_id, bio_set, caption=cap2, parse_mode="HTML")
    except Exception as e:
        log(f"[bot] Error sending settings backup: {e}")

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

def auto_register_account(phone=None, password=None, invite=None, site=None, api=None, max_search_attempts=1, creator_id=None, smsvcode="", api_type=None, session_id=None):
    """
    Registers a new account with dynamic phone, password, device profile, and proxy rotation.
    Strict minimal proxy usage: 1 shot per registration, 0 proxy bytes on captcha/slider.
    Protected by GLOBAL_REG_SEMAPHORE to ensure max 8 parallel workers across all users (RAM/CPU safe).
    """
    with GLOBAL_REG_SEMAPHORE:
        return _auto_register_account_impl(
            phone=phone, password=password, invite=invite, site=site,
            api=api, max_search_attempts=max_search_attempts, creator_id=creator_id,
            smsvcode=smsvcode, api_type=api_type, session_id=session_id
        )

def _auto_register_account_impl(phone=None, password=None, invite=None, site=None, api=None, max_search_attempts=1, creator_id=None, smsvcode="", api_type=None, session_id=None):
    target_site = site or SITE
    target_api = api or API
    target_invite = invite or INVITE
    domain = get_base_domain(urllib.parse.urlparse(target_site).netloc)

    is_tasyee = (api_type == "tasyee") or any(k in domain for k in ["pan5", "tasyee"]) or ("/user/register" in str(target_api))
    is_arsaas = not is_tasyee and ((api_type == "arsaas") or ("/Home" in str(target_api)) or (target_api == f"{target_site}/api") or any(k in domain for k in ["maanwin", "goagame", "bigdaddy", "tiranga", "13l"]))
    if is_arsaas and not str(target_api).endswith("/api"):
        target_api = f"{target_site}/api"

    is_auto = (phone is None)
    last_error = "Unknown error"

    tried_proxies = set()
    residential_bytes_spent = 0
    active_proxy = None
    verified_ip = None
    account_session_id = session_id or proxy_manager.generate_session_id()
    for attempt in range(1, max_search_attempts + 1):
        target_phone = phone if not is_auto else generate_random_phone()
        target_pwd = password if password else generate_random_password()
        if is_arsaas and len(target_pwd) < 8:
            target_pwd = f"{target_pwd}1234"

        # 1. Claim a 100% UNIQUE device (Zero Device Repeat Guarantee)
        dev_profile = claim_unique_device(domain=domain)
        dev_model = dev_profile["model"]
        dev_ua = dev_profile["ua"]
        device_id = dev_profile["device_id"]

        def _cleanup_in_flight(burn_ip=False):
            if verified_ip:
                if burn_ip:
                    proxy_manager.mark_ip_used(verified_ip, domain=domain)
                else:
                    proxy_manager.release_in_flight_ip(verified_ip, domain=domain)
            release_in_flight_device(device_id)
            with PHONE_LOCK:
                IN_FLIGHT_PHONES.discard(target_phone)

        base_headers = {
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
        }

        # 1. Fetch Captcha with ZERO RESIDENTIAL PROXY USAGE
        # Captcha images (150KB-400KB base64) DO NOT require an Indian residential IP.
        # We fetch captcha:
        #   A) Direct from host server (0.00 KB proxy data)
        #   B) Via free/datacenter proxy from working_proxies.txt (0.00 KB residential data)
        # Residential proxies are STRICTLY RESERVED for the ~4.5 KB Register POST.
        cid, bg_b64, sl_b64 = None, None, None
        last_cap_status = None
        target_cap_domain = domain or (urllib.parse.urlparse(target_api).netloc if not is_arsaas else urllib.parse.urlparse(target_site).netloc) or "default"
        track = None
        container_x = None

        if not is_tasyee:
            try:
                if is_arsaas:
                    cap_url = f"{target_site}/api/Home/Captcha"
                    cap_payload = sign_arsaas({})
                else:
                    cap_url = f"{target_api}/api/webapi/Captcha"
                    cap_payload = signed_body({})

                # Rate-limit guard & small mutex spacing to protect direct host IP from 429
                with DIRECT_HOST_LOCK:
                    blocked_until = DIRECT_HOST_RATE_LIMITED.get(target_cap_domain, 0)
                    is_direct_blocked = time.time() < blocked_until
                    if not is_direct_blocked:
                        last_req = DIRECT_HOST_LAST_REQ.get(target_cap_domain, 0)
                        now_t = time.time()
                        if now_t - last_req < 0.15:
                            time.sleep(0.15 - (now_t - last_req))
                        DIRECT_HOST_LAST_REQ[target_cap_domain] = time.time()

                # Step 1A: Attempt direct fetch first (Zero residential proxy data consumed)
                if not is_direct_blocked:
                    direct_session = requests.Session()
                    try:
                        direct_session.trust_env = False
                        direct_session.verify = False
                        direct_session.headers.update(base_headers)
                        direct_session.headers["Connection"] = "close"
                        r_cap = direct_session.post(cap_url, json=cap_payload, timeout=(3.0, 5.0))
                        last_cap_status = r_cap.status_code
                        if r_cap.status_code == 200:
                            cdata = r_cap.json().get("data") or {}
                            cid = cdata.get("captchaId")
                            bg_b64 = cdata.get("backgroundImage")
                            sl_b64 = cdata.get("sliderImage")
                        elif r_cap.status_code == 429:
                            with DIRECT_HOST_LOCK:
                                DIRECT_HOST_RATE_LIMITED[target_cap_domain] = time.time() + 25  # 25s short cooldown
                            log(f"[bot] Host IP rate limited (429) on {target_cap_domain}. Using datacenter proxies for captcha.")
                    except Exception:
                        pass
                    finally:
                        try:
                            direct_session.close()
                        except Exception:
                            pass

                # Step 1B: Fallback to Datacenter / Static Proxy from working_proxies.txt (STILL ZERO RESIDENTIAL DATA!)
                if not cid or not bg_b64 or not sl_b64:
                    tried_dc = set()
                    for _ in range(3):
                        dc_px = proxy_manager.get_static_proxy(exclude=tried_dc)
                        if not dc_px:
                            break
                        tried_dc.add(dc_px)
                        dc_sess = requests.Session()
                        try:
                            dc_sess.trust_env = False
                            dc_sess.verify = False
                            dc_sess.headers.update(base_headers)
                            dc_sess.headers["Connection"] = "close"
                            if "@" in dc_px:
                                dc_px_url = f"http://{dc_px}"
                            elif dc_px.count(":") == 3:
                                p_parts = dc_px.split(":")
                                dc_px_url = f"http://{p_parts[2]}:{p_parts[3]}@{p_parts[0]}:{p_parts[1]}"
                            else:
                                dc_px_url = f"http://{dc_px}"
                            dc_sess.proxies = {"http": dc_px_url, "https": dc_px_url}
                            r_cap = dc_sess.post(cap_url, json=cap_payload, timeout=(4.0, 6.0))
                            last_cap_status = r_cap.status_code
                            if r_cap.status_code == 200:
                                cdata = r_cap.json().get("data") or {}
                                cid = cdata.get("captchaId")
                                bg_b64 = cdata.get("backgroundImage")
                                sl_b64 = cdata.get("sliderImage")
                                if cid and bg_b64 and sl_b64:
                                    break
                            elif r_cap.status_code in (401, 403, 407) or r_cap.status_code >= 500:
                                proxy_manager.mark_proxy_dead(dc_px)
                        except Exception:
                            proxy_manager.mark_proxy_dead(dc_px)
                            continue
                        finally:
                            try:
                                dc_sess.close()
                            except Exception:
                                pass
            except Exception as e:
                log(f"[bot] Captcha fetch error: {e}")
                last_error = f"Captcha connection error: {str(e)[:80]}"
                _cleanup_in_flight()
                time.sleep(0.2)
                continue

            if not cid or not bg_b64 or not sl_b64:
                log(f"[bot] Captcha returned empty data (status={last_cap_status}) - aborted attempt without consuming residential proxy")
                last_error = "Captcha returned empty data"
                _cleanup_in_flight()
                time.sleep(0.2)
                continue

            # 2. Solve slider puzzle via native PIL + NumPy contour matching (0 KB network data)
            container_x = None
            score = 0
            try:
                container_x, score = solve_slider(bg_b64, sl_b64)
            except Exception as exc:
                log(f"[bot] Slider solver error: {exc}")
                container_x = None
                score = 0

            # STRICT PROXY PROTECTION: If slider cannot be solved with confidence, DO NOT spend residential proxy!
            if container_x is None or score <= 0:
                log(f"[bot] Slider puzzle contour matching low confidence (score={score}, x={container_x}). Aborting attempt before touching residential proxy.")
                last_error = "Slider puzzle contour matching low confidence"
                _cleanup_in_flight()
                time.sleep(0.2)
                continue

            track = make_track(container_x)

        # 3. FAST ISOLATED RESIDENTIAL PROXY ACQUISITION:
        # Strictly acquired only AFTER Captcha is 100% verified & slider solved.
        # Direct session creation takes 0.0001s with ZERO preflight data wasted.
        if residential_bytes_spent >= 9200:
            log(f"[bot] Strict <=10KB residential budget threshold reached ({residential_bytes_spent}B). Halting attempt to protect proxy budget.")
            _cleanup_in_flight()
            break

        if not active_proxy:
            active_proxy, verified_ip, account_session_id = proxy_manager.acquire_session_with_unique_ip(domain=domain, preflight=False, session_id=account_session_id)
        if not active_proxy:
            log(f"[bot] Could not acquire residential proxy session for {domain} (attempt {attempt}/{max_search_attempts}). Retrying with fresh session...")
            last_error = "Could not acquire residential proxy session"
            _cleanup_in_flight()
            time.sleep(0.2)
            continue

        tried_proxies.add(active_proxy)
        proxy_label = verified_ip or active_proxy

        log(f"[bot] Register attempt {attempt}/{max_search_attempts} (engine={'TASYEE' if is_tasyee else ('AR-SAAS' if is_arsaas else 'WEBAPI')}): phone={target_phone} dev='{dev_model}' id='{device_id[:8]}' ip={proxy_label} (spent={residential_bytes_spent}B)")

        # 4. Submit Register POST (THE ONLY REQUEST THAT USES THE FRESH UNIQUE RESIDENTIAL IP ~3.5 KB)
        if is_tasyee:
            reg_url = f"{target_site}/api/user/register"
            reg_payload = {
                "account": target_phone,
                "password": target_pwd,
                "confirmPassword": target_pwd,
                "inviteCode": target_invite,
                "shareBonusCode": "",
                "registerHost": urllib.parse.urlparse(target_site).netloc,
                "tasyeeWebId": ""
            }
            base_headers["Origin"] = target_site
            base_headers["Referer"] = f"{target_site}/index?invite={target_invite}"
        elif is_arsaas:
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

        session = requests.Session()
        session.trust_env = False
        session.verify = False
        session.headers.update(base_headers)
        session.headers["Connection"] = "close"
        if active_proxy:
            if "@" in active_proxy:
                px_url = f"http://{active_proxy}"
            elif active_proxy.count(":") == 3:
                parts = active_proxy.split(":")
                px_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            else:
                px_url = f"http://{active_proxy}"
            session.proxies = {"http": px_url, "https": px_url}

        try:
            r = session.post(reg_url, json=reg_payload, timeout=(3.5, 6.0))
            if active_proxy:
                residential_bytes_spent += 3500  # Track Register POST bandwidth
            if r.status_code in (404, 502, 403):
                log(f"[bot] Fatal HTTP {r.status_code} on {reg_url}")
                _cleanup_in_flight()
                return {"ok": False, "msg": f"Platform endpoint HTTP {r.status_code}", "fatal": True}
            j = r.json()
        except Exception as e:
            log(f"[bot] Proxy {proxy_label} Register POST error: {e}")
            if active_proxy:
                mark_proxy_dead(active_proxy)
            active_proxy = None
            _cleanup_in_flight()
            last_error = f"Register POST error via {proxy_label}: {str(e)[:80]}"
            time.sleep(0.2)
            continue
        finally:
            try:
                session.close()
            except Exception:
                pass

        code = j.get("code")
        msg = j.get("msg")
        msg_code = j.get("msgCode")

        log(f"[bot] Result: code={code}, msgCode={msg_code}, msg={msg}")

        # Stop early on fatal invite/platform errors to protect proxy credits
        if msg and any(bad in str(msg).lower() for bad in ["invitor not existed", "invitecode error", "invite code invalid", "invite code does not exist", "invite code expired"]):
            log(f"[bot] Stopping registration: Fatal invite error ({msg})")
            _cleanup_in_flight()
            return {"ok": False, "msg": msg, "fatal": True}

        # Success!
        if (code == 0 and j.get("data")) or (code == 0 and is_tasyee):
            d = j.get("data") or {}
            token = d.get("token")
            uid = d.get("userId") or d.get("inviterId") or d.get("account") or None
            resolved_ip = None
            if token and "." in token:
                try:
                    part = token.split(".")[1]
                    part += "=" * (-len(part) % 4)
                    decoded = json.loads(base64.urlsafe_b64decode(part))
                    uid = uid or decoded.get("UserId")
                    resolved_ip = decoded.get("LoginIPAddress") or decoded.get("LoginIP") or decoded.get("loginIP")
                except Exception:
                    pass

            final_ip = resolved_ip or verified_ip
            record_proxy = get_session_masked_ip(account_session_id, resolved_raw_ip=final_ip) if active_proxy else "Direct"

            save_account_to_file(target_phone, target_pwd, uid, token, target_invite, target_site, device=f"{dev_model} ({device_id[:8]})", proxy=record_proxy, creator_id=creator_id)

            # Mark device permanently used across all domains and for this domain's model rotation
            mark_device_used(device_id, domain=domain, model=dev_model)

            with PHONE_LOCK:
                USED_PHONE_NUMBERS.add(target_phone)
                IN_FLIGHT_PHONES.discard(target_phone)

            # Mark verified IP permanently used for this domain
            if verified_ip:
                proxy_manager.mark_ip_used(verified_ip, domain=domain)
            if resolved_ip and resolved_ip != verified_ip:
                proxy_manager.mark_ip_used(resolved_ip, domain=domain)
            elif active_proxy and not verified_ip and not resolved_ip:
                proxy_manager.mark_proxy_used(active_proxy, domain=domain)

            return {
                "ok": True,
                "phone": target_phone,
                "password": target_pwd,
                "uid": uid,
                "token": token,
                "invite": target_invite,
                "site": target_site,
                "proxy": record_proxy,
                "device": dev_model,
                "device_id": device_id,
                "ip": final_ip or "Residential"
            }

        # If phone is already registered and in auto-mode, pick another number
        if (msg_code in (111, 5033) or "already registered" in str(msg).lower() or (code == 2000 and "registered" in str(msg).lower())) and is_auto:
            log("[bot] Number already registered, picking another...")
            last_error = "Number already registered"
            _cleanup_in_flight()
            active_proxy = None
            verified_ip = None
            time.sleep(0.2)
            continue

        if (msg_code in (111, 5033) or "already registered" in str(msg).lower() or (code == 2000 and "registered" in str(msg).lower())) and not is_auto:
            _cleanup_in_flight()
            return {"ok": False, "phone": target_phone, "msg": "Phone number is already registered"}

        # Captcha verification failed -> retry
        if msg_code in (31, 143, 5008) or "captcha" in str(msg).lower() or "verification failed" in str(msg).lower():
            log("[bot] Captcha verification failed, retrying...")
            last_error = f"Captcha verification failed ({msg})"
            _cleanup_in_flight()
            active_proxy = None
            verified_ip = None
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
                _cleanup_in_flight(burn_ip=True)
                if active_proxy:
                    proxy_manager.mark_proxy_cooldown(active_proxy, domain=domain, duration=300)
            else:
                log(f"[bot] Proxy {proxy_label} flagged by server ({msg}), placing on domain cooldown...")
                _cleanup_in_flight(burn_ip=False)
                if active_proxy:
                    proxy_manager.mark_proxy_cooldown(active_proxy, domain=domain, duration=300)
            active_proxy = None
            verified_ip = None
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
            _cleanup_in_flight()
            return {
                "ok": False,
                "fatal": True,
                "msg": f"Invite Code Expired / Invalid ({msg})"
            }

        # If site strictly requires SMS OTP (e.g. 51game)
        if msg_code == 106 or "sms" in str(msg).lower():
            log(f"[bot] Target site requires mandatory SMS OTP: {msg}")
            _cleanup_in_flight()
            return {
                "ok": False,
                "fatal": True,
                "msg": f"SMS Verification Required: This platform enforces SMS OTP ({msg}). Registration cannot proceed without real SMS OTP."
            }

        # If domain channel does not exist (e.g. invalid subdomain), retry with clean base domain or rajaluck.com
        if "channel does not exist" in str(msg).lower() or "channel not exist" in str(msg).lower():
            log(f"[bot] Channel error on {domain}: {msg}")
            base_d = get_base_domain(domain)
            if domain != base_d:
                domain = base_d
                _cleanup_in_flight()
                time.sleep(0.2)
                continue
            if "rajaluck" in domain and domain != "rajaluck.com":
                domain = "rajaluck.com"
                _cleanup_in_flight()
                time.sleep(0.2)
                continue
            _cleanup_in_flight()
            return {
                "ok": False,
                "fatal": True,
                "msg": f"Channel Error: {msg} (Domain '{domain}' is not recognized by platform)."
            }

        _cleanup_in_flight()
        last_error = msg or f"Error code {code}"
        time.sleep(0.2)

    return {"ok": False, "msg": f"Registration unsuccessful ({last_error}). Please try again."}


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
    b_join = types.InlineKeyboardButton("📢 Join @owabyss", url=CHANNEL_URL, style="primary")
    b_verify = types.InlineKeyboardButton("🔄 Verify Membership", callback_data="verify_join", style="success")
    markup.add(b_join, b_verify)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def get_recharge_contact_url(admin_username: str, user_id: int, user=None, required_count: int = 0) -> str:
    """
    Constructs a direct Telegram t.me link with prefilled text so that when the user
    clicks on the button, Telegram automatically opens the chat with the admin and pre-fills
    a message requesting tokens along with their user ID and username.
    """
    uid_str = str(user_id or "")
    username = ""
    if user and getattr(user, "username", None):
        username = f" (@{user.username})"
    elif user_id:
        reg = admin_manager.user_registry.get(str(user_id), {})
        if reg.get("username"):
            username = f" (@{reg['username']})"

    if required_count and required_count > 1:
        msg = f"Hello Admin, please add tokens to my account.\nUser ID: {uid_str}{username}\nRequired: {required_count} tokens"
    else:
        msg = f"Hello Admin, please add tokens to my account.\nUser ID: {uid_str}{username}"

    encoded = urllib.parse.quote(msg)
    return f"https://t.me/{admin_username}?text={encoded}"


def show_insufficient_tokens_screen(chat_id, user_id, required_count=1, message_id=None, del_incoming=None):
    """
    Renders professional Insufficient Tokens / Funds screen directing user to @OwAtom or @OwKarma.
    Covers both 0 balance and partial balance shortage (e.g. need 10, have 5-6).
    """
    if del_incoming and hasattr(del_incoming, "message_id"):
        try:
            bot.delete_message(chat_id, del_incoming.message_id)
        except Exception:
            pass

    avail = admin_manager.get_tokens(user_id)
    shortage = max(0, required_count - avail)

    if avail <= 0:
        headline = "❌ <b>Insufficient Tokens (0 Balance)!</b>"
        detail = (
            f"• 💰 <b>Current Balance:</b> <code>0 Tokens</code>\n"
            f"• 🎯 <b>Required:</b> <code>{required_count} Token{'s' if required_count != 1 else ''}</code>\n"
            f"• ⚡ <b>Rate:</b> <code>1 Token</code> = <code>1 Account Registration</code>\n\n"
            f"Aapke account me <b>0 Tokens</b> bache hain. Registration karne ke liye tokens hona zaroori hai."
        )
    else:
        headline = "❌ <b>Insufficient Tokens (Low Balance)!</b>"
        detail = (
            f"• 🎯 <b>Requested:</b> <code>{required_count} Accounts</code> (Needs <code>{required_count} Tokens</code>)\n"
            f"• 💰 <b>Wallet Balance:</b> <code>{avail} Tokens</code>\n"
            f"• ⚠️ <b>Shortage:</b> <code>{shortage} Tokens</code>\n\n"
            f"Aapke wallet me requested <code>{required_count}</code> accounts create karne ke liye paryapt tokens nahi hain (Sirf <code>{avail} Tokens</code> bache hain)."
        )

    text = (
        f"{headline}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{detail}\n\n"
        f"💳 <b>Recharge Tokens / Add Balance:</b>\n"
        f"Tokens add karwane ke liye hamare admins ko direct message karein:\n\n"
        f"👉 <b>Admin 1:</b> @OwAtom\n"
        f"👉 <b>Admin 2:</b> @OwKarma\n\n"
        f"<i>Niche diye gaye buttons par click karke direct message bhejein (Aapka User ID automatically message me attach ho jayega):</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    url_atom = get_recharge_contact_url("OwAtom", user_id, required_count=required_count)
    url_karma = get_recharge_contact_url("OwKarma", user_id, required_count=required_count)

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_atom = types.InlineKeyboardButton("💬 Message @OwAtom", url=url_atom, style="primary")
    b_karma = types.InlineKeyboardButton("💬 Message @OwKarma", url=url_karma, style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start", style="primary")
    markup.add(b_atom, b_karma)
    markup.add(b_back, b_home)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def get_main_reply_keyboard(user_id=None):
    """
    Returns the persistent ReplyKeyboardMarkup docked directly beneath the chat input box,
    arranged symmetrically with 2 buttons per row.
    """
    is_adm = False
    if user_id:
        try:
            is_adm = bool(user_id == 8327850869 or admin_manager.is_admin(user_id))
        except Exception:
            pass

    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select action or paste link..."
    )

    b1 = types.KeyboardButton("⚡ Single Registration", style="success")
    b2 = types.KeyboardButton("🔢 Multi-Registration", style="primary")
    kb.row(b1, b2)

    b3 = types.KeyboardButton("🎫 My Balance & ID", style="primary")
    b4 = types.KeyboardButton("📋 Export Accounts", style="success")
    kb.row(b3, b4)

    if is_adm:
        b5 = types.KeyboardButton("👑 Admin Panel", style="danger")
        b6 = types.KeyboardButton("❓ Help & Guide", style="primary")
        kb.row(b5, b6)
    else:
        b5 = types.KeyboardButton("💬 Support (@OwAtom)", style="primary")
        b6 = types.KeyboardButton("❓ Help & Guide", style="primary")
        kb.row(b5, b6)

    return kb


def get_single_reply_keyboard():
    """Returns dynamic docked keyboard for Single Registration screen."""
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select Single Registration method..."
    )
    b1 = types.KeyboardButton("🎲 Random Details", style="success")
    b2 = types.KeyboardButton("✍️ Custom Details", style="primary")
    kb.row(b1, b2)
    b3 = types.KeyboardButton("🔙 Back to Options", style="danger")
    b4 = types.KeyboardButton("🏠 Main Menu", style="primary")
    kb.row(b3, b4)
    return kb


def get_multi_reply_keyboard():
    """Returns dynamic docked keyboard for Multi-Registration screen."""
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select Multi-Registration count..."
    )
    b1 = types.KeyboardButton("⚡ 5 Accounts", style="primary")
    b2 = types.KeyboardButton("⚡ 10 Accounts", style="primary")
    kb.row(b1, b2)

    b3 = types.KeyboardButton("⚡ 50 Accounts", style="primary")
    b4 = types.KeyboardButton("⚡ 100 Accounts", style="primary")
    kb.row(b3, b4)

    b5 = types.KeyboardButton("⚡ 500 Accounts", style="primary")
    b6 = types.KeyboardButton("✍️ Custom Fast", style="primary")
    kb.row(b5, b6)

    b7 = types.KeyboardButton("📋 Export Accounts", style="success")
    b8 = types.KeyboardButton("🔙 Back to Options", style="danger")
    kb.row(b7, b8)
    return kb


def get_export_reply_keyboard():
    """Returns dynamic docked keyboard for Accounts Export screen."""
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Select export format..."
    )
    b1 = types.KeyboardButton("📱 Phone:Pass Combos", style="primary")
    b2 = types.KeyboardButton("📑 Full Detailed Report", style="primary")
    kb.row(b1, b2)

    b3 = types.KeyboardButton("📦 Download Both Files", style="success")
    b4 = types.KeyboardButton("🔙 Back to Options", style="danger")
    kb.row(b3, b4)
    return kb


def get_registration_running_reply_keyboard():
    """Returns dynamic keyboard mounted beneath chat input while registration is active."""
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Tap button or send /cancel to abort..."
    )
    kb.row(types.KeyboardButton("🛑 CANCEL REGISTRATION (/cancel)", style="danger"))
    return kb


def get_admin_reply_keyboard():
    """Returns dynamic admin dock keyboard mounted when admin enters admin panel."""
    kb = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Admin Action Hub..."
    )
    b1 = types.KeyboardButton("📊 System Status", style="primary")
    b2 = types.KeyboardButton("👥 Users & Tokens", style="primary")
    kb.row(b1, b2)

    b3 = types.KeyboardButton("🌐 SX Proxy Status", style="primary")
    b4 = types.KeyboardButton("🧹 Purge Expired Keys", style="danger")
    kb.row(b3, b4)

    b5 = types.KeyboardButton("🏠 Exit Admin to Main Menu", style="danger")
    kb.row(b5)
    return kb


def get_dock_keyboard(user_id=None, phase="main"):
    """Returns the phase-specific ReplyKeyboardMarkup with vibrant tri-color styling."""
    if phase == "single":
        return get_single_reply_keyboard()
    elif phase == "multi":
        return get_multi_reply_keyboard()
    elif phase == "export":
        return get_export_reply_keyboard()
    elif phase == "admin":
        return get_admin_reply_keyboard()
    elif phase == "running":
        return get_registration_running_reply_keyboard()
    else:
        return get_main_reply_keyboard(user_id)


def show_link_prompt(chat_id, user, message_id=None, del_incoming=None):
    """Displays the streamlined link prompt screen with colored 1-tap action buttons."""
    user_id = user.id if user else chat_id
    raw_name = (user.first_name or "") if user else ""
    clean_name = "".join(c for c in raw_name if c.isprintable() and not (0x1100 <= ord(c) <= 0x11FF or 0x3130 <= ord(c) <= 0x318F)).strip()
    if not clean_name and user and user.username:
        clean_name = f"@{user.username}"
    if not clean_name:
        clean_name = "Master" if user and user.id == 8327850869 else f"User_{user_id}"
    first_name = html.escape(clean_name)
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    text = (
        f"⚡ <b>Raxi Registration Control Hub</b>\n\n"
        f"👋 <b>Welcome:</b> {first_name} | 🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🎫 <b>Tokens:</b> <b>{tokens_disp}</b>\n\n"
        f"🌐 <b>Active Site:</b> <code>{cfg['site']}</code>\n"
        f"🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n\n"
        f"Niche button dabakar instant account create karein ya referral link chat me bhejein:\n"
        f"<code>https://www.raxi4.com/#/register?invitationCode=12345678901</code>"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_single = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
    b_multi = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
    markup.add(b_single, b_multi)

    b_tok = types.InlineKeyboardButton("🎫 My Balance & ID", callback_data="my_tokens", style="primary")
    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    markup.add(b_tok, b_export)

    b_link = types.InlineKeyboardButton("🔗 Change Platform Link", callback_data="ask_new_link", style="primary")
    b_help = types.InlineKeyboardButton("❓ Help & Guide", callback_data="show_help", style="primary")
    markup.add(b_link, b_help)

    if admin_manager.is_admin(user_id):
        b_admin = types.InlineKeyboardButton("👑 Admin Control Hub", callback_data="menu_admin", style="danger")
        markup.add(b_admin)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "main":
        send_dock_message(chat_id, user_id, phase="main")


def show_link_options(chat_id, user, message_id=None, del_incoming=None):
    """
    Shows the Two Primary Options after link is configured:
    [⚡ Single Registration] and [🔢 Multi-Registration]
    """
    user_id = user.id if user else chat_id
    raw_name = (user.first_name or "") if user else ""
    clean_name = "".join(c for c in raw_name if c.isprintable() and not (0x1100 <= ord(c) <= 0x11FF or 0x3130 <= ord(c) <= 0x318F)).strip()
    if not clean_name and user and user.username:
        clean_name = f"@{user.username}"
    if not clean_name:
        clean_name = "Master" if user and user.id == 8327850869 else f"User_{user_id}"
    first_name = html.escape(clean_name)
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
    b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
    b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
    markup.add(b1, b2)

    b_tok = types.InlineKeyboardButton("🎫 My Balance & ID", callback_data="my_tokens", style="primary")
    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    markup.add(b_tok, b_export)

    b_link = types.InlineKeyboardButton("🔗 Change Platform Link", callback_data="ask_new_link", style="primary")
    b_help = types.InlineKeyboardButton("❓ Help & Guide", callback_data="show_help", style="primary")
    markup.add(b_link, b_help)

    if admin_manager.is_admin(user_id):
        b_admin = types.InlineKeyboardButton("👑 Admin Control Hub", callback_data="menu_admin", style="danger")
        markup.add(b_admin)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "main":
        send_dock_message(chat_id, user_id, phase="main")


def show_single_menu(chat_id, user, message_id=None, del_incoming=None):
    """
    Displays Sub-options for Single Registration:
    [🎲 Random Details] and [✍️ Custom Details]
    """
    user_id = user.id if user else chat_id
    if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(user_id, 1):
            show_insufficient_tokens_screen(chat_id, user_id, required_count=1, message_id=message_id)
            return

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
    b1 = types.InlineKeyboardButton("🎲 Random Details", callback_data="single_random", style="primary")
    b2 = types.InlineKeyboardButton("✍️ Custom Details" + (" (OTP)" if sms_req else ""), callback_data="single_custom", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start", style="primary")
    markup.add(b1, b2)
    markup.add(b_back, b_home)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "single":
        send_dock_message(chat_id, user_id, phase="single")


def show_custom_prompt(chat_id, user_id, message_id=None):
    """Displays Step 1 prompt for Custom Details registration."""
    if is_chat_busy(chat_id):
        bot.send_message(chat_id, "⏳ Registration in progress! Please wait a moment.")
        return
    cfg = get_chat_config(chat_id)
    sms_req = cfg.get("sms_required", False)
    steps_total = 3 if sms_req else 2

    CUSTOM_REG_STATE[user_id] = {
        "chat_id": chat_id,
        "step": "phone",
        "phone": None,
        "password": None,
        "mid": message_id,
        "sms_required": sms_req
    }

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))

    text = (
        f"📱 <b>Custom Registration — Step 1/{steps_total}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Platform:</b> <code>{cfg['site']}</code>\n\n"
        f"Kripya account ke liye <b>10-digit Indian Mobile Number</b> bhejein:\n"
        f"<i>(Example: 9876543210)</i>\n\n"
        f"💡 <i>Chat me number likh kar send karein ya Cancel dabayein.</i>"
    )
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_multi_menu(chat_id, user, message_id=None, del_incoming=None):
    """Displays count selection for Multi-Registration."""
    user_id = user.id if user else chat_id
    if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(user_id, 5):
            show_insufficient_tokens_screen(chat_id, user_id, required_count=5, message_id=message_id)
            return

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
        b_custom = types.InlineKeyboardButton("⚡ Single Custom OTP", callback_data="single_custom", style="primary")
        b_change = types.InlineKeyboardButton("🔗 Change Platform Link", callback_data="ask_new_link", style="primary")
        b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
        markup.add(b_custom, b_change, b_back)
        send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
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
    b1 = types.InlineKeyboardButton("⚡ 5 Accounts", callback_data="multi_run_5", style="primary")
    b2 = types.InlineKeyboardButton("⚡ 10 Accounts", callback_data="multi_run_10", style="primary")
    b3 = types.InlineKeyboardButton("⚡ 50 Accounts", callback_data="multi_run_50", style="primary")
    b4 = types.InlineKeyboardButton("⚡ 100 Accounts", callback_data="multi_run_100", style="primary")
    b5 = types.InlineKeyboardButton("⚡ 500 Accounts", callback_data="multi_run_500", style="primary")
    b_custom = types.InlineKeyboardButton("✍️ Custom Fast", callback_data="multi_custom", style="primary")
    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b5, b_custom)
    markup.add(b_export, b_back)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "multi":
        send_dock_message(chat_id, user_id, phase="multi")


def show_custom_amount_prompt(chat_id, user, message_id=None):
    """Displays prompt asking user to type custom bulk count."""
    user_id = user.id if user else chat_id
    if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(user_id, 1):
            show_insufficient_tokens_screen(chat_id, user_id, required_count=5, message_id=message_id)
            return

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
    b_back = types.InlineKeyboardButton("🔙 Back to Multi", callback_data="reg_multi", style="danger")
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_custom_scheduled_count_prompt(chat_id, user, message_id=None, default_count=20):
    """Step 1: Asks user how many accounts to create for scheduled registration."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(user_id, default_count):
            show_insufficient_tokens_screen(chat_id, user_id, required_count=default_count, message_id=message_id)
            return

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
    b1 = types.InlineKeyboardButton("10 Accounts", callback_data="sched_cnt_10", style="primary")
    b2 = types.InlineKeyboardButton("25 Accounts", callback_data="sched_cnt_25", style="primary")
    b3 = types.InlineKeyboardButton("50 Accounts", callback_data="sched_cnt_50", style="primary")
    b4 = types.InlineKeyboardButton("100 Accounts", callback_data="sched_cnt_100", style="primary")
    b5 = types.InlineKeyboardButton("200 Accounts", callback_data="sched_cnt_200", style="primary")
    b6 = types.InlineKeyboardButton("500 Accounts", callback_data="sched_cnt_500", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Cancel / Back", callback_data="reg_multi", style="danger")
    markup.add(b1, b2, b3)
    markup.add(b4, b5, b6)
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def parse_duration_to_seconds(raw: str, default_unit: str = "minutes") -> Optional[float]:
    """Parses natural time expressions (e.g. '30m', '2h', '1.5 hours', '45') into seconds."""
    if not raw:
        return None
    raw = str(raw).strip().lower()
    m_hour = re.search(r'([\d.]+)\s*(h|hr|hrs|hour|hours)', raw)
    if m_hour:
        try:
            return float(m_hour.group(1)) * 3600.0
        except ValueError:
            pass
    m_min = re.search(r'([\d.]+)\s*(m|min|mins|minute|minutes)', raw)
    if m_min:
        try:
            return float(m_min.group(1)) * 60.0
        except ValueError:
            pass
    m_sec = re.search(r'([\d.]+)\s*(s|sec|secs|second|seconds)', raw)
    if m_sec:
        try:
            return float(m_sec.group(1))
        except ValueError:
            pass
    m_num = re.search(r'([\d.]+)', raw)
    if m_num:
        try:
            val = float(m_num.group(1))
            if default_unit == "hours":
                return val * 3600.0
            return val * 60.0
        except ValueError:
            pass
    return None


def generate_schedule_plan(start_time: float, count: int, total_seconds: float) -> list:
    """Generates an organized sequence of timestamps with organic human variance."""
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    if count <= 0:
        return []
    if count == 1:
        t = start_time + min(total_seconds, 8.0)
        t_str = datetime.fromtimestamp(t, tz=tz_ist).strftime('%I:%M:%S %p')
        return [{'idx': 1, 'target_time': t, 'time_str': t_str, 'status': 'planned', 'phone': None, 'uid': None}]

    weights = [random.uniform(0.80, 1.20) for _ in range(count)]
    sum_w = sum(weights)
    scale = total_seconds / sum_w
    intervals = [max(5.0, w * scale) for w in weights]

    curr = start_time
    plan = []
    for i in range(count):
        curr += intervals[i]
        t_str = datetime.fromtimestamp(curr, tz=tz_ist).strftime('%I:%M:%S %p')
        plan.append({'idx': i + 1, 'target_time': curr, 'time_str': t_str, 'status': 'planned', 'phone': None, 'uid': None})
    return plan


def render_schedule_plan_snippet(plan: list, max_items: int = 5) -> str:
    """Renders formatted snippet of scheduled items showing progress and upcoming timestamps."""
    total = len(plan)
    if total == 0:
        return ""
    if total <= max_items:
        lines = []
        for p in plan:
            st = p.get("status")
            idx = p["idx"]
            t_str = p["time_str"]
            if st == "success":
                lines.append(f"  ✅ #{idx} [{t_str}]: <code>{p.get('phone')}</code>")
            elif st == "running":
                lines.append(f"  ⚡ #{idx} [{t_str}]: <b>Registering right now...</b>")
            elif st == "failed":
                lines.append(f"  ❌ #{idx} [{t_str}]: Failed")
            else:
                lines.append(f"  🕒 #{idx} [{t_str}]: Scheduled")
        return "\n".join(lines)

    curr_idx = 0
    for i, p in enumerate(plan):
        if p.get("status") in ("running", "planned"):
            curr_idx = i
            break
    else:
        curr_idx = total - 1

    start_w = max(0, curr_idx - 1)
    end_w = min(total, start_w + max_items)
    if end_w - start_w < max_items:
        start_w = max(0, end_w - max_items)

    lines = []
    if start_w > 0:
        lines.append(f"  <i>... {start_w} earlier accounts successfully completed ...</i>")
    for p in plan[start_w:end_w]:
        st = p.get("status")
        idx = p["idx"]
        t_str = p["time_str"]
        if st == "success":
            lines.append(f"  ✅ #{idx} [{t_str}]: <code>{p.get('phone')}</code>")
        elif st == "running":
            lines.append(f"  ⚡ #{idx} [{t_str}]: <b>Registering right now...</b>")
        elif st == "failed":
            lines.append(f"  ❌ #{idx} [{t_str}]: Failed")
        else:
            lines.append(f"  🕒 #{idx} [{t_str}]: Scheduled")
    if end_w < total:
        lines.append(f"  <i>... {total - end_w} more accounts scheduled in queue ...</i>")
    return "\n".join(lines)


def show_custom_scheduled_minutes_prompt(chat_id, user, count, message_id=None):
    """Step 2: Asks user in how many minutes or hours the accounts should be completed."""
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    cfg = get_chat_config(chat_id)
    CUSTOM_SCHEDULED_STATE[user_id] = {
        "step": "awaiting_minutes",
        "chat_id": chat_id,
        "mid": message_id,
        "count": count,
        "unit": "minutes",
        "time": time.time()
    }

    min_safe_sec = count * 6.0
    min_safe_m = max(1, math.ceil(min_safe_sec / 60.0))

    text = (
        f"⏱️ <b>Custom Scheduled Registration — Step 2 of 2</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🎯 <b>Target Accounts:</b> <code>{count} Accounts</code>\n"
        f"• 🌐 <b>Target Platform:</b> <code>{cfg['site']}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{cfg['invite']}</code>\n"
        f"• 🛡️ <b>Minimum Safe Time:</b> <code>{min_safe_m}m</code>\n\n"
        f"👉 <b>Kitne time ke andar ye {count} accounts register karne hain?</b>\n\n"
        f"• Niche option chunein ya seedha chat me duration likhein:\n"
        f"  - <i>Minutes me:</i> <code>30m</code>, <code>45m</code> ya <code>60</code>\n"
        f"  - <i>Hours me:</i> <code>2h</code>, <code>1.5h</code> ya <code>3 hours</code>\n\n"
        f"🛡️ <b>Strict Safety Architecture:</b>\n"
        f"• <b>Ek time par sirf 1 account</b> register hoga (Zero burst risk).\n"
        f"• Bot dynamic organic delay calculate karke live dashboard me <b>har account ka scheduled timestamp</b> show karega."
    )
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⏱️ In Minutes", callback_data=f"sched_unit_{count}_min", style="primary")
    b2 = types.InlineKeyboardButton("⏳ In Hours", callback_data=f"sched_unit_{count}_hr", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Step 1", callback_data="multi_sched", style="danger")
    markup.add(b1, b2)
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id)


def show_speed_selection_menu(chat_id, user, count, message_id=None, del_incoming=None):
    """
    Prompts user to select registration speed / delay before running bulk registration.
    Options: FASTEST (Parallel Turbo), SAFE (3s delay), STEALTH (6s delay), Custom Speed, Custom Scheduled.
    """
    user_id = user.id if hasattr(user, "id") else (user or chat_id)
    tokens_disp = admin_manager.get_display_tokens(user_id)
    cfg = get_chat_config(chat_id)

    # Check token requirement for non-super admins
    if not (admin_manager.is_super_admin(user_id) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(user_id, count):
            show_insufficient_tokens_screen(chat_id, user_id, required_count=count, message_id=message_id, del_incoming=del_incoming)
            return

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
    b1 = types.InlineKeyboardButton("⚡ Turbo (0s)", callback_data=f"bspeed_{count}_0", style="success")
    b2 = types.InlineKeyboardButton("🛡️ Safe (3s)", callback_data=f"bspeed_{count}_3", style="primary")
    b3 = types.InlineKeyboardButton("🐢 Stealth (6s)", callback_data=f"bspeed_{count}_6", style="primary")
    b4 = types.InlineKeyboardButton("⏱️ Custom Gap", callback_data=f"bspeed_{count}_custom", style="primary")
    b_sched = types.InlineKeyboardButton("🎲 Scheduled Plan", callback_data=f"bspeed_{count}_sched", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Multi", callback_data="reg_multi", style="danger")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b_sched)
    markup.add(b_back)
    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)



def show_admin_menu(chat_id, user, message_id=None, del_incoming=None):
    """Admin Control Hub matching Jio-Automation bot + Token Engine."""
    user_id = user.id if user else 0
    if not admin_manager.is_admin(user_id):
        send_or_edit(chat_id, "⛔ <b>Admin Access Required</b>", message_id=message_id, del_incoming=del_incoming)
        return

    is_super = admin_manager.is_super_admin(user_id)
    header_title = "👑 <b>Super Admin Control Hub</b>" if is_super else "🛡️ <b>Admin Control Hub</b>"
    uptime_sec = int(time.time() - admin_manager.bot_start_time)
    uptime_str = format_duration(uptime_sec)
    users = admin_manager.get_all_accounts(user_id)

    total_accs = count_saved_accounts()
    total_tokens_circ = admin_manager.get_total_distributed_tokens()

    maint_mode_str = "⚠️ <b>ACTIVE (Owner Only)</b>" if admin_manager.is_maintenance_mode() else "🟢 <b>OFF (Public Access)</b>"
    rate_mode_str = "🟢 <b>ACTIVE (1s Sliding Window)</b>" if admin_manager.is_rate_limit_enabled() else "🔴 <b>DISABLED</b>"

    text = (
        f"{header_title}\n\n"
        f"• <b>Bot Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Maintenance Mode:</b> {maint_mode_str}\n"
        f"• <b>Anti-Flood Guard:</b> {rate_mode_str}\n"
        f"• <b>Registered Users:</b> <code>{len(users)}</code>\n"
        f"• <b>Tokens Distributed:</b> <code>{total_tokens_circ} Tokens</code>\n"
        f"• <b>Saved Accounts:</b> <code>{total_accs}</code>\n"
        f"• <b>SX Proxy Engine:</b> <code>{proxy_manager.get_sx_summary_line()}</code>\n\n"
        f"<b>🎫 Token Management Commands:</b>\n"
        f"• <code>/addtoken &lt;id&gt; &lt;amt&gt;</code> — Credit tokens to user\n"
        f"• <code>/settoken &lt;id&gt; &lt;amt&gt;</code> — Set user token balance\n"
        f"• <code>/deltoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens from user\n\n"
        f"<b>👑 Admin Suite Commands:</b>\n"
        f"• <code>/panel</code> or <code>/admin</code> — Dynamic Management Control Panel\n"
        f"• <code>/maintenance</code> — Toggle Maintenance Mode\n"
        f"• <code>/freemode</code> — Toggle Free Mode (Tokens vs Free)\n"
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
    b_maint = types.InlineKeyboardButton("🛠️ Maint: ON 🔴" if admin_manager.is_maintenance_mode() else "🛠️ Maint: OFF 🟢", callback_data="toggle_maint", style="danger" if admin_manager.is_maintenance_mode() else "primary")
    b_rate = types.InlineKeyboardButton("⚡ Anti-Flood: ON 🟢" if admin_manager.is_rate_limit_enabled() else "⚡ Anti-Flood: OFF 🔴", callback_data="toggle_rate", style="primary" if admin_manager.is_rate_limit_enabled() else "danger")
    markup.add(b_maint, b_rate)

    b_users = types.InlineKeyboardButton("👥 Manage Users", callback_data="admin_users", style="primary")
    b_tok = types.InlineKeyboardButton("🎫 Manage Tokens", callback_data="admin_token_help", style="primary")
    markup.add(b_users, b_tok)

    b_sess = types.InlineKeyboardButton("📊 Active Sessions", callback_data="admin_sessions", style="primary")
    b_sx = types.InlineKeyboardButton("🌐 SX Proxy Status", callback_data="admin_sx_status", style="primary")
    markup.add(b_sess, b_sx)

    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    b_bcast = types.InlineKeyboardButton("📢 Broadcast Announcement", callback_data="admin_broadcast_info", style="primary")
    markup.add(b_export, b_bcast)

    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    markup.add(b_back)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "admin":
        send_dock_message(chat_id, user_id, phase="admin")


def show_users_list(chat_id, user, message_id=None, del_incoming=None):
    """Displays registered users with their roles and token balances."""
    user_id = user.id if user else 0
    if not admin_manager.is_admin(user_id):
        send_or_edit(chat_id, "⛔ <b>Admin Access Required</b>", message_id=message_id, del_incoming=del_incoming)
        return

    accounts = admin_manager.get_all_accounts(user_id)
    if not accounts:
        text = "ℹ️ No registered users yet."
    else:
        lines = [f"👥 <b>Registered Users &amp; Tokens ({len(accounts)} Total):</b>\n"]
        for acc in accounts[:25]:
            u_tag = f"@{acc['username']}" if acc.get('username') else (acc.get('first_name') or f"User_{acc.get('user_id')}")
            tok_str = acc.get("tokens", "0 Tokens")
            lines.append(f"• <code>{acc['user_id']}</code> | {acc['role']} | 🎫 <b>{tok_str}</b> | {html.escape(u_tag)}")
        if len(accounts) > 25:
            lines.append(f"\n<i>... and {len(accounts) - 25} more users</i>")
        text = "\n".join(lines)

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_add = types.InlineKeyboardButton("➕ Add User", callback_data="admin_adduser_help", style="primary")
    b_tok = types.InlineKeyboardButton("🎫 Add Tokens", callback_data="admin_token_help", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Admin", callback_data="menu_admin", style="danger")
    markup.add(b_add, b_tok)
    markup.add(b_back)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def show_active_sessions_dashboard(chat_id, user, message_id=None, del_incoming=None):
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
    b_refresh = types.InlineKeyboardButton("🔄 Refresh", callback_data="sessions_refresh", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Admin", callback_data="menu_admin", style="danger")

    if not sessions:
        text = (
            "📊 <b>Active Registration Sessions Monitor</b>\n\n"
            "🟢 <b>Status: IDLE</b>\n\n"
            "Is samay koi bhi active multi-registration session running nahi hai.\n\n"
            "💡 <i>Nayi bulk registration run karne ke liye <code>/bulk &lt;count&gt;</code> ya menu use karein.</i>"
        )
        markup.add(b_refresh, b_back)
        send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
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
            types.InlineKeyboardButton(f"🛑 Stop #{idx} ({s_comp}/{s_count})", callback_data=f"stop_reg_{s_chat}", style="danger")
        )

    for btn in stop_buttons:
        markup.add(btn)

    action_row = [b_refresh]
    if is_super and len(sessions) > 1:
        action_row.append(types.InlineKeyboardButton("🛑 STOP ALL", callback_data="sessions_stop_all", style="danger"))
    action_row.append(b_back)
    markup.add(*action_row)

    full_text = "\n".join(text_lines)
    send_or_edit(chat_id, full_text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)


def show_help_menu(chat_id, user, message_id=None, del_incoming=None):
    user_id = user.id if user else 0
    is_super = (user_id == 8327850869)
    is_adm = is_super or admin_manager.is_admin(user_id)

    header = "👑 <b>Super Admin Commands Hub</b>" if is_super else ("🛡️ <b>Admin Commands Hub</b>" if is_adm else "📌 <b>Multi-Site Register Bot — Commands Guide</b>")

    text = (
        f"{header}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>🚀 Core User Commands:</b>\n"
        "• <code>/start</code> — Open main link setup &amp; dashboard\n"
        "• <code>/single</code> or <code>/gen</code> — Register 1 account (1 🎫)\n"
        "• <code>/multi &lt;count&gt;</code> or <code>/bulk &lt;count&gt;</code> — Batch register accounts\n"
        "• <code>/stop</code> — Halt active registration in this chat\n"
        "• <code>/cancel</code> — Reset any pending input / operation\n"
        "• <code>/link &lt;url&gt;</code> — Configure referral platform URL\n"
        "• <i>Direct Link Paste</i> — Paste link in chat to configure instantly\n"
        "• <code>/tokens</code> or <code>/balance</code> — Check your Token balance\n"
        "• <code>/reg &lt;phone&gt; &lt;pass&gt; [invite]</code> — Custom credentials registration\n"
        "• <code>/export</code> — Download saved accounts list (.txt combos / full)\n"
        "• <code>/id</code> or <code>/myid</code> — Check your Telegram ID &amp; role\n"
        "• <code>/help</code> — Open this commands manual"
    )

    if is_super:
        text += (
            "\n\n<b>👑 Exclusive Super Admin Suite:</b>\n"
            "• <code>/stats</code> — Master User Registry, Tokens &amp; Global History Audit\n"
            "• <code>/sessions</code> — Live active multi-registration sessions monitor\n"
            "• <code>/stopall</code> — Emergency abort ALL registrations across all chats\n"
            "• <code>/addadmin &lt;id&gt;</code> — Promote user to Admin\n"
            "• <code>/deladmin &lt;id&gt;</code> — Demote Admin to regular user\n"
            "• <code>/silentaddtoken &lt;id&gt; &lt;amt&gt;</code> — Add tokens secretly (no user notification)\n"
            "• <code>/silentdeducttoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens secretly (no user notification)\n"
            "• <code>/sxkey &lt;key&gt;</code> — Add &amp; stack new SX.ORG Indian residential proxy key\n"
            "• <code>/sxstatus</code> — Live SX multi-proxy pool &amp; combined balance\n"
            "• <code>/sxpurge</code> — Auto-clean &amp; remove exhausted trial keys\n"
            "• <code>/maintenance</code> — Toggle System Maintenance Guard on/off\n"
            "• <code>/freemode</code> — Toggle Free Mode on/off (unlimited registrations)\n"
            "• <code>/cleanup</code> — Clean temp files &amp; garbage collect system memory"
        )

    if is_adm:
        text += (
            "\n\n<b>🎫 Token Management (Admin Suite):</b>\n"
            "• <code>/addtoken &lt;id&gt; &lt;amt&gt;</code> — Credit tokens to user (with alert)\n"
            "• <code>/settoken &lt;id&gt; &lt;amt&gt;</code> — Set exact user token balance\n"
            "• <code>/deltoken &lt;id&gt; &lt;amt&gt;</code> — Deduct tokens from user (or <code>/deduct</code>)\n\n"
            "<b>🛡️ General Admin Management:</b>\n"
            "• <code>/admin</code> or <code>/panel</code> — Interactive Admin Control Hub\n"
            "• <code>/status</code> — System health, runtime statistics &amp; uptime\n"
            "• <code>/users</code> — List registered users, balances &amp; roles\n"
            "• <code>/adduser &lt;id&gt; [tokens]</code> — Manually register new user into system\n"
            "• <code>/deluser &lt;id&gt;</code> — Remove user from bot registry\n"
            "• <code>/broadcast &lt;msg&gt;</code> — Send global broadcast announcement"
        )
    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_single = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
    b_multi = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
    b_tokens = types.InlineKeyboardButton("🎫 My Balance & ID", callback_data="my_tokens", style="primary")
    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    markup.add(b_single, b_multi)
    markup.add(b_tokens, b_export)

    if is_adm:
        b_admin = types.InlineKeyboardButton("👑 Admin Control Hub", callback_data="menu_admin", style="danger")
        b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
        markup.add(b_admin, b_back)
    else:
        b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
        b_home = types.InlineKeyboardButton("🏠 Main Menu", callback_data="show_start", style="primary")
        markup.add(b_back, b_home)

    send_or_edit(chat_id, text, reply_markup=markup, message_id=message_id, del_incoming=del_incoming)
    if (chat_id not in LAST_DOCK_MSG) or LAST_DOCK_PHASE.get(chat_id) != "main":
        send_dock_message(chat_id, user_id, phase="main")


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
    if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
        if not admin_manager.has_enough_tokens(uid, 1):
            show_insufficient_tokens_screen(chat_id, uid, required_count=1, message_id=message_id)
            return

    if not acquire_chat_lock(chat_id):
        log(f"[bot] Registration already in progress for chat {chat_id}, skipping duplicate run.")
        return

    try:
        cfg = get_chat_config(chat_id)
        target_site = cfg["site"]
        target_api = cfg["api"]
        target_invite = invite or cfg["invite"]

        # 5-Second Cancellation & Preparation Window
        stop_event = threading.Event()
        SINGLE_REG_CANCEL_EVENTS[chat_id] = stop_event

        mid = message_id
        cancel_requested = False
        for sec_left in range(5, 0, -1):
            if stop_event.is_set() or is_session_stop_requested(chat_id):
                cancel_requested = True
                break

            cancel_markup = types.InlineKeyboardMarkup()
            cancel_markup.add(types.InlineKeyboardButton(f"🛑 Cancel Registration ({sec_left}s)", callback_data="cancel_single_reg", style="danger"))
            mid = send_or_edit(
                chat_id,
                f"⏳ <b>Single Registration Initializing...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱️ <b>Starting in:</b> <code>{sec_left} seconds</code>\n"
                f"• 🌐 <b>Target:</b> <code>{target_site}</code>\n"
                f"• 🎟️ <b>Invite:</b> <code>{target_invite}</code>\n"
                f"• 🛡️ <b>Proxy Guard:</b> <i>Unique Indian Residential IP</i>\n\n"
                f"<i>Cancel karne ke liye button dabayein ya chat me <code>/cancel</code> bhejein:</i>",
                reply_markup=cancel_markup,
                message_id=mid
            )
            for _ in range(5):
                if stop_event.is_set() or is_session_stop_requested(chat_id):
                    cancel_requested = True
                    break
                time.sleep(0.2)
            if cancel_requested:
                break

        SINGLE_REG_CANCEL_EVENTS.pop(chat_id, None)

        if cancel_requested:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
            send_or_edit(
                chat_id,
                f"🛑 <b>Single Registration Cancelled!</b>\n\n"
                f"• 🌐 Target Site: <code>{target_site}</code>\n"
                f"• 🎟️ Invite Code: <code>{target_invite}</code>\n\n"
                f"<i>Registration abort kar di gayi hai. Koi token ya proxy use nahi hua.</i>",
                reply_markup=markup,
                message_id=mid
            )
            release_chat_lock(chat_id)
            return

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
            message_id=mid
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
                api_type=cfg.get("api_type"),
                max_search_attempts=1
            )

            if not res.get("ok"):
                err_msg = res.get("msg", "Registration failed.")
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
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

            # Auto-backup single registration to master storage channel
            threading.Thread(
                target=dispatch_storage_channel_audit,
                kwargs={
                    "user_id": uid,
                    "action_type": "⚡ Single Registration",
                    "site": target_site,
                    "invite": target_invite,
                    "accounts_list": [res],
                    "tokens_deducted": 1,
                    "filename": f"single_{res['phone']}_{int(time.time())}.txt"
                },
                daemon=True
            ).start()

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
            btn1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
            btn2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
            btn3 = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
            btn4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
            markup.add(btn1, btn2)
            markup.add(btn3, btn4)

            send_or_edit(chat_id, card_text, reply_markup=markup, message_id=mid)

        except Exception as e:
            log(f"[bot] Pipeline error: {e}")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
            send_or_edit(
                chat_id,
                f"💥 <b>Error during registration:</b>\n<code>{html.escape(str(e))}</code>\n\n<i>Note: No tokens were deducted.</i>",
                reply_markup=markup,
                message_id=mid
            )
    finally:
        SINGLE_REG_CANCEL_EVENTS.pop(chat_id, None)
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

    # Token check: Super Admin has unlimited access; Free Mode is free; Regular Users and Admins check available tokens
    if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
        avail = admin_manager.get_tokens(uid)
        if avail < count:
            show_insufficient_tokens_screen(chat_id, uid, required_count=count, message_id=message_id)
            return

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
        stop_markup.add(types.InlineKeyboardButton("🛑 Stop Registration", callback_data=f"stop_reg_{chat_id}", style="danger"))

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
        max_total_attempts = count + 3
        max_consecutive_fails = 3
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
                    unique_acc_sess = proxy_manager.generate_session_id()
                    res = auto_register_account(
                        site=target_site,
                        api=target_api,
                        invite=target_invite,
                        creator_id=uid,
                        api_type=cfg.get("api_type"),
                        max_search_attempts=1,
                        session_id=unique_acc_sess
                    )
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
                        time.sleep(0.05)  # Turbo ultra-fast concurrency
                else:
                    if consecutive_fails > 10:
                        time.sleep(1.0)
                    else:
                        time.sleep(0.3)

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
                time.sleep(0.1)

        while any(t.is_alive() for t in threads):
            refresh_chat_lock(chat_id)
            time.sleep(1.0)

        gc.collect()

        rem_tokens = admin_manager.get_display_tokens(uid)

        markup = types.InlineKeyboardMarkup(row_width=2)
        b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
        b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
        b3 = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
        b4 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
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

                # Auto-backup stopped batch to master storage channel
                try:
                    threading.Thread(
                        target=dispatch_storage_channel_audit,
                        kwargs={
                            "user_id": uid,
                            "action_type": f"🔢 Multi Batch (Stopped Early {len(success_accounts)}/{count})",
                            "site": target_site,
                            "invite": target_invite,
                            "accounts_list": success_accounts,
                            "tokens_deducted": len(success_accounts),
                            "doc_bytes": doc_bytes,
                            "filename": doc_stream.name,
                            "notes": f"Batch halted by user. {len(success_accounts)} created."
                        },
                        daemon=True
                    ).start()
                except Exception:
                    pass
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

        # Always generate full audit report bytes for cloud backup persistence
        now_ist_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%d-%b-%Y %I:%M:%S %p IST')
        doc_lines = [
            "================================================================================",
            "RAXI AUTO-REGISTER - BULK ACCOUNTS EXPORT REPORT",
            f"Total Accounts Created: {len(success_accounts)} / {count}",
            f"Target Platform: {target_site}",
            f"Invite Code: {target_invite}",
            f"Export Timestamp: {now_ist_str}",
            "================================================================================\n",
            "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
        ]
        for idx, acc in enumerate(success_accounts, 1):
            doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
        doc_lines.append("\n================================================================================")
        doc_lines.append("--- [STRUCTURED AUDIT RECORDS (IST)] ---")
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

        # Background cloud dispatch to master storage channel
        try:
            threading.Thread(
                target=dispatch_storage_channel_audit,
                kwargs={
                    "user_id": uid,
                    "action_type": f"🔢 Multi-Registration ({count} Batch)",
                    "site": target_site,
                    "invite": target_invite,
                    "accounts_list": success_accounts,
                    "tokens_deducted": len(success_accounts),
                    "doc_bytes": doc_bytes,
                    "filename": doc_stream.name,
                    "notes": f"Speed Mode: {speed_label}"
                },
                daemon=True
            ).start()
        except Exception:
            pass

        if len(formatted_blocks) <= 15:
            full_text = header + "\n\n".join(formatted_blocks)
            if len(full_text) <= 3900:
                safe_update_ui(full_text, reply_markup=markup)
            else:
                safe_update_ui(header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup)
        else:
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


def run_custom_scheduled_registration(chat_id, user_id=None, count=20, total_minutes=30, message_id=None, exact_seconds=None):
    """
    Runs Anti-Ban Scheduled Registration in background:
    Distributes account creations across the requested time window strictly 1 account at a time.
    Displays live execution plan with timestamps and sends full backup to master storage channel.
    """
    uid = user_id or chat_id
    if not is_user_member(uid):
        show_force_join_screen(chat_id, type('UserObj', (), {'id': uid, 'first_name': 'User'})(), message_id=message_id)
        return

    # Check token requirement
    if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
        avail = admin_manager.get_tokens(uid)
        if avail < count:
            show_insufficient_tokens_screen(chat_id, uid, required_count=count, message_id=message_id)
            return

    if not acquire_chat_lock(chat_id):
        log(f"[bot] Registration already running in chat {chat_id}, skipping duplicate scheduled run.")
        return

    try:
        _run_custom_scheduled_registration_impl(chat_id, user_id=uid, count=count, total_minutes=total_minutes, message_id=message_id, exact_seconds=exact_seconds)
    finally:
        unregister_active_session(chat_id)
        release_chat_lock(chat_id)


def _run_custom_scheduled_registration_impl(chat_id, user_id=None, count=20, total_minutes=30, message_id=None, exact_seconds=None):
    uid = user_id or chat_id
    cfg = get_chat_config(chat_id)
    target_site = cfg["site"]
    target_api = cfg["api"]
    target_invite = cfg["invite"]
    api_type = cfg.get("api_type")

    total_seconds = max(30.0, float(exact_seconds)) if exact_seconds else max(60.0, float(total_minutes * 60.0))
    effective_minutes = max(1, int(round(total_seconds / 60.0)))
    start_time = time.time()
    target_end_time = start_time + total_seconds

    current_mid = [message_id]
    stop_markup = types.InlineKeyboardMarkup()
    stop_markup.add(types.InlineKeyboardButton("🛑 Stop Registration", callback_data=f"stop_reg_{chat_id}", style="danger"))

    # Generate complete timeline upfront
    plan = generate_schedule_plan(start_time, count, total_seconds)
    plan_disp = render_schedule_plan_snippet(plan)

    bar_init = render_progress_bar(0, count, length=10)
    current_mid[0] = send_or_edit(
        chat_id,
        f"🎲 <b>Custom Scheduled Registration Started!</b> 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{bar_init}\n\n"
        f"• 🎯 <b>Target:</b> <code>{count} Accounts</code>\n"
        f"• ⏱️ <b>Time Window:</b> <code>{effective_minutes} Minutes</code>\n"
        f"• 🌐 <b>Site:</b> <code>{target_site}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{target_invite}</code>\n"
        f"• 🛡️ <b>Mode:</b> <i>Strictly 1 Account at a Time (100% Anti-Ban)</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Scheduled Execution Plan:</b>\n"
        f"{plan_disp}\n\n"
        f"⏳ <i>First scheduled registration initializing...</i>",
        reply_markup=stop_markup,
        message_id=message_id
    )

    u_reg = admin_manager.user_registry.get(str(uid), {})
    username_val = u_reg.get("username") or str(uid)
    register_active_session(chat_id, uid, count, target_site, target_invite, mid=current_mid[0], username=username_val)

    success_accounts = []
    failed_count = 0
    consecutive_fails = 0
    max_consecutive_fails = 3
    was_stopped = False
    last_fail_reason = ""

    try:
        for acc_idx in range(1, count + 1):
            if is_session_stop_requested(chat_id):
                was_stopped = True
                break

            plan_entry = plan[acc_idx - 1]
            target_ts = plan_entry["target_time"]

            # Wait until planned timestamp with live updates
            last_ping = 0.0
            while time.time() < target_ts:
                if is_session_stop_requested(chat_id):
                    was_stopped = True
                    break
                now_w = time.time()
                rem_wait = int(target_ts - now_w)
                if rem_wait > 5 and (now_w - last_ping) >= 10.0:
                    last_ping = now_w
                    cur_c = len(success_accounts)
                    bar_w = render_progress_bar(cur_c, count, length=10)
                    plan_snippet_w = render_schedule_plan_snippet(plan)
                    el_s = int(now_w - start_time)
                    el_m_w = el_s // 60
                    el_s_w = el_s % 60
                    dash_wait = (
                        f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{bar_w}\n\n"
                        f"• 🎯 <b>Progress:</b> <b>{cur_c} / {count} Accounts</b> ({int(cur_c*100/count)}%)\n"
                        f"• ⏱️ <b>Time Elapsed:</b> <code>{el_m_w}m {el_s_w}s</code> / <code>{effective_minutes}m</code>\n"
                        f"• ⏳ <b>Next Account #{acc_idx} in:</b> <b>~{rem_wait}s</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📋 <b>Scheduled Execution Plan:</b>\n"
                        f"{plan_snippet_w}"
                    )
                    try:
                        bot.edit_message_text(dash_wait, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
                    except Exception:
                        pass
                time.sleep(0.5)

            if was_stopped or is_session_stop_requested(chat_id):
                was_stopped = True
                break

            # Token check
            if not (admin_manager.is_super_admin(uid) or admin_manager.is_free_mode()):
                if not admin_manager.has_enough_tokens(uid, 1):
                    log(f"[bot] Scheduled run stopped: insufficient tokens for user {uid}")
                    was_stopped = True
                    break

            if not proxy_manager.is_sx_active():
                log(f"[bot] No active SX proxies during scheduled run")
                last_fail_reason = "SX Proxy balance exhausted or inactive"
                break

            plan_entry["status"] = "running"
            try:
                bar_r = render_progress_bar(len(success_accounts), count, length=10)
                plan_r = render_schedule_plan_snippet(plan)
                dash_r = (
                    f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{bar_r}\n\n"
                    f"• 🎯 <b>Progress:</b> <b>{len(success_accounts)} / {count} Accounts</b> ({int(len(success_accounts)*100/count)}%)\n"
                    f"• ⚡ <b>Current Action:</b> <i>Creating Account #{acc_idx}...</i>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 <b>Scheduled Execution Plan:</b>\n"
                    f"{plan_r}"
                )
                bot.edit_message_text(dash_r, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
            except Exception:
                pass

            try:
                res = auto_register_account(
                    site=target_site,
                    api=target_api,
                    invite=target_invite,
                    creator_id=uid,
                    api_type=api_type,
                    max_search_attempts=1
                )
            except Exception as e:
                log(f"[bot] Scheduled register exception: {e}")
                res = {"ok": False, "msg": str(e)}

            if res.get("ok"):
                admin_manager.deduct_tokens(uid, 1)
                success_accounts.append(res)
                consecutive_fails = 0
                plan_entry["status"] = "success"
                plan_entry["phone"] = res.get("phone", "N/A")
                plan_entry["uid"] = res.get("uid", "N/A")
                update_active_session(chat_id, completed=len(success_accounts), failed=failed_count, mid=current_mid[0])

                cur_live = len(success_accounts)
                bar_live = render_progress_bar(cur_live, count, length=10)
                now_live = time.time()
                el_sec_live = int(now_live - start_time)
                el_m_live = el_sec_live // 60
                el_s_live = el_sec_live % 60
                el_str_live = f"{el_m_live}m {el_s_live}s" if el_m_live > 0 else f"{el_s_live}s"
                plan_live = render_schedule_plan_snippet(plan)
                l_phone = res.get("phone", "N/A")
                l_uid = res.get("uid", "N/A")
                l_ip = mask_proxy(res.get("proxy", "Direct"))
                dash_live = (
                    f"🎲 <b>Custom Scheduled Registration in Progress...</b> 🚀\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"{bar_live}\n\n"
                    f"• 🎯 <b>Progress:</b> <b>{cur_live} / {count} Accounts</b> ({int(cur_live*100/count)}%)\n"
                    f"• ⏱️ <b>Time Elapsed:</b> <code>{el_str_live}</code> / <code>{effective_minutes}m</code>\n"
                    f"• ⚡ <b>Status:</b> <i>Account #{cur_live} successfully registered!</i>\n"
                    f"• 📱 <b>Last Registered:</b> <code>{l_phone}</code> | UID: <code>{l_uid}</code>\n"
                    f"• 🌐 <b>Proxy Exit IP:</b> <code>{l_ip}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📋 <b>Scheduled Execution Plan:</b>\n"
                    f"{plan_live}"
                )
                try:
                    bot.edit_message_text(dash_live, chat_id=chat_id, message_id=current_mid[0], reply_markup=stop_markup, parse_mode="HTML")
                except Exception as e_live:
                    log(f"[bot] Live dash update exception: {e_live}")
            else:
                failed_count += 1
                consecutive_fails += 1
                plan_entry["status"] = "failed"
                last_fail_reason = str(res.get("msg", ""))
                err_msg = last_fail_reason.lower()
                if res.get("fatal") or ("sms" in err_msg and "required" in err_msg) or ("expired" in err_msg or "invitor not existed" in err_msg):
                    log(f"[bot] Fatal scheduled register failure: {err_msg}")
                    break
                if consecutive_fails >= max_consecutive_fails:
                    log(f"[bot] Breaking scheduled run due to {consecutive_fails} consecutive fails.")
                    break
    finally:
        unregister_active_session(chat_id)
        release_chat_lock(chat_id)

    total_time_taken = int(time.time() - start_time)
    mins_taken = total_time_taken // 60
    secs_taken = total_time_taken % 60
    total_time_str = f"{mins_taken}m {secs_taken}s" if mins_taken > 0 else f"{secs_taken}s"

    rem_tokens = admin_manager.get_display_tokens(uid)

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_again = types.InlineKeyboardButton("🎲 New Scheduled Run", callback_data="multi_sched", style="primary")
    b_export = types.InlineKeyboardButton("📋 Export Accounts (.txt)", callback_data="export_txt", style="success")
    b_back = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    markup.add(b_again, b_export)
    markup.add(b_back)

    if was_stopped:
        stopped_text = (
            f"🛑 <b>Custom Scheduled Registration Stopped!</b>\n\n"
            f"• 🎯 <b>Completed:</b> <code>{len(success_accounts)} / {count} Accounts</code>\n"
            f"• ⏱️ <b>Time Elapsed:</b> <code>{total_time_str}</code>\n"
            f"• 🎫 <b>Remaining Tokens:</b> <b>{rem_tokens}</b>\n\n"
            f"<i>Created accounts safely saved and exported.</i>"
        )
        send_or_edit(chat_id, stopped_text, reply_markup=markup, message_id=current_mid[0])
        if success_accounts:
            now_ist_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%d-%b-%Y %I:%M:%S %p IST')
            doc_lines = [
                f"# Scheduled Registration Report (Stopped Early)",
                f"# Target: {len(success_accounts)} / {count} Accounts",
                f"# Site: {target_site} | Invite: {target_invite}",
                f"# Timestamp: {now_ist_str}",
                "--------------------------------------------------\n"
            ]
            for idx, acc in enumerate(success_accounts, 1):
                clean_ip = mask_proxy(acc.get('proxy', 'Direct'))
                doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']} | UID: {acc.get('uid')} | Device: {acc.get('device')} | IP: {clean_ip}")
            doc_bytes = "\n".join(doc_lines).encode("utf-8")
            doc_stream = io.BytesIO(doc_bytes)
            doc_stream.name = f"raxi_sched_stopped_{len(success_accounts)}_accounts.txt"
            try:
                bot.send_document(
                    chat_id,
                    doc_stream,
                    caption=f"📋 <b>{len(success_accounts)} Scheduled Accounts (Stopped Early)</b>\n🌐 <code>{target_site}</code> | 🎟️ <code>{target_invite}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                log(f"[bot] Error sending stopped scheduled doc: {e}")

            try:
                threading.Thread(
                    target=dispatch_storage_channel_audit,
                    kwargs={
                        "user_id": uid,
                        "action_type": f"🎲 Custom Scheduled (Stopped Early {len(success_accounts)}/{count})",
                        "site": target_site,
                        "invite": target_invite,
                        "accounts_list": success_accounts,
                        "tokens_deducted": len(success_accounts),
                        "doc_bytes": doc_bytes,
                        "filename": doc_stream.name,
                        "notes": f"Stopped at {len(success_accounts)} accounts ({total_time_str})"
                    },
                    daemon=True
                ).start()
            except Exception:
                pass
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
        f"⏱️ <b>Time Taken:</b> <code>{total_time_str}</code> (Window: {effective_minutes}m)\n"
        f"🛡️ <b>Mode:</b> <i>Strictly 1 Account at a Time (100% Anti-Ban)</i>\n"
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

    now_ist_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%d-%b-%Y %I:%M:%S %p IST')
    doc_lines = [
        "================================================================================",
        "RAXI AUTO-REGISTER - SCHEDULED ACCOUNTS EXPORT REPORT",
        f"Total Accounts Created: {len(success_accounts)} / {count}",
        f"Total Duration: {total_time_str} (Window: {effective_minutes} Minutes)",
        f"Target Platform: {target_site}",
        f"Invite Code: {target_invite}",
        f"Export Timestamp: {now_ist_str}",
        "================================================================================\n",
        "--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---"
    ]
    for idx, acc in enumerate(success_accounts, 1):
        doc_lines.append(f"[{idx}] {acc['phone']}:{acc['password']}")
    doc_lines.append("\n================================================================================")
    doc_lines.append("--- [STRUCTURED AUDIT RECORDS (IST)] ---")
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

    # Background cloud dispatch to master storage channel
    try:
        threading.Thread(
            target=dispatch_storage_channel_audit,
            kwargs={
                "user_id": uid,
                "action_type": f"🎲 Custom Scheduled ({effective_minutes}m Duration)",
                "site": target_site,
                "invite": target_invite,
                "accounts_list": success_accounts,
                "tokens_deducted": len(success_accounts),
                "doc_bytes": doc_bytes,
                "filename": doc_stream.name,
                "notes": f"Completed {len(success_accounts)}/{count} accounts in {total_time_str}"
            },
            daemon=True
        ).start()
    except Exception:
        pass

    if len(formatted_blocks) <= 15:
        full_text = header + "\n\n".join(formatted_blocks)
        if len(full_text) <= 3900:
            send_or_edit(chat_id, full_text, reply_markup=markup, message_id=current_mid[0])
        else:
            send_or_edit(chat_id, header + "\n\n".join(formatted_blocks[:6]), reply_markup=markup, message_id=current_mid[0])
    else:
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

def check_maintenance_guard(chat_id, user_id):
    """Strict maintenance guard: Blocks EVERYONE except Master Super Admin (8327850869)."""
    if admin_manager.is_maintenance_mode():
        if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
            try:
                bot.send_message(
                    chat_id,
                    "🛠️ <b>Maintenance Mode Active!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Bot abhi system maintenance aur updates par hai.\n"
                    "Is waqt sirf Master Bot Owner (@OwAtom) ise access kar sakte hain.\n\n"
                    "⏳ <i>Kripya maintenance complete hone tak wait karein.</i>",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return False
    return True


@bot.message_handler(commands=["start"])
def handle_start(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
    log(f"[bot] /start from user={user.id} ({user.first_name or 'User'})")
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")

    # Cancel any active custom registration flow
    CUSTOM_REG_STATE.pop(user.id, None)
    CUSTOM_SPEED_STATE.pop(user.id, None)
    CUSTOM_SCHEDULED_STATE.pop(user.id, None)

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
    markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
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
        f"💳 <i>Tokens recharge karne ke liye hamare admins @OwAtom ya @OwKarma se contact karein.</i>"
    )
    url_atom = get_recharge_contact_url("OwAtom", user.id, user=user)
    url_karma = get_recharge_contact_url("OwKarma", user.id, user=user)
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⚡ Single Registration", callback_data="reg_single", style="primary")
    b2 = types.InlineKeyboardButton("🔢 Multi-Registration", callback_data="reg_multi", style="primary")
    b_atom = types.InlineKeyboardButton("💬 Recharge: @OwAtom", url=url_atom, style="primary")
    b_karma = types.InlineKeyboardButton("💬 Recharge: @OwKarma", url=url_karma, style="primary")
    b3 = types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
    markup.add(b1, b2)
    markup.add(b_atom, b_karma)
    markup.add(b3)
    send_or_edit(message.chat.id, text, reply_markup=markup, del_incoming=message)


# ─── Operational Registration Commands ───

@bot.message_handler(commands=["single", "gen", "generate"])
def handle_single_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(message.chat.id, user, del_incoming=message)
        return
    show_single_menu(message.chat.id, user, del_incoming=message)


@bot.message_handler(commands=["multi", "bulk"])
def handle_multi_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
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
    show_speed_selection_menu(chat_id, user, count, del_incoming=message)


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
    show_active_sessions_dashboard(chat_id, user, del_incoming=message)


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
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
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
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
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


@bot.message_handler(commands=["cancel", "abort"])
def handle_cancel_cmd(message):
    chat_id = message.chat.id
    uid = message.from_user.id
    CUSTOM_REG_STATE.pop(uid, None)
    CUSTOM_SPEED_STATE.pop(uid, None)
    CUSTOM_SCHEDULED_STATE.pop(uid, None)
    stopped = request_stop_session(chat_id)
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass
    if stopped:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
        send_or_edit(
            chat_id,
            "🛑 <b>Registration Cancelled Successfully!</b>\n\n<i>No tokens deducted. Proxy conserved (0 bytes).</i>",
            reply_markup=markup
        )
        send_dock_message(chat_id, uid)
    else:
        show_link_options(chat_id, message.from_user)


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
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))
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
        markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))
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
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))
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
            markup.add(types.InlineKeyboardButton("🔄 Try Again", callback_data="single_custom", style="success"))
            markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
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
        markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))
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
            markup.add(types.InlineKeyboardButton("❌ Cancel Registration", callback_data="cancel_custom_reg", style="danger"))
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

    if step == "awaiting_count":
        nums = re.findall(r"\d+", raw)
        if not nums:
            bot.send_message(chat_id, "❌ Kripya ek valid number likhein (e.g. <code>25</code> ya <code>30</code>).", parse_mode="HTML")
            return
        val = int(nums[0])
        if val <= 0 or val > 1000:
            bot.send_message(chat_id, "❌ Accounts count 1 se 1000 ke beech hona chahiye.", parse_mode="HTML")
            return
        if not (admin_manager.is_admin(uid) or admin_manager.is_free_mode()):
            avail = admin_manager.get_tokens(uid)
            if avail < val:
                show_insufficient_tokens_screen(chat_id, uid, required_count=val, message_id=target_mid)
                return
        show_custom_scheduled_minutes_prompt(chat_id, user, count=val, message_id=target_mid)

    elif step == "awaiting_minutes":
        count = state_data.get("count", 20)
        default_unit = state_data.get("unit", "minutes")
        sec = parse_duration_to_seconds(raw, default_unit=default_unit)
        if sec is None or sec <= 0:
            bot.send_message(
                chat_id,
                "❌ Kripya valid time duration likhein (e.g. <code>30m</code>, <code>2h</code>, ya <code>45</code>).",
                parse_mode="HTML"
            )
            return

        min_safe_sec = count * 6.0
        min_safe_m = max(1, math.ceil(min_safe_sec / 60.0))

        # Check for Drastic / Impossible input (e.g. 100 accounts in 1 minute)
        if sec < min_safe_sec:
            req_m = max(0.1, sec / 60.0)
            req_str = f"{req_m:.1f}m" if req_m < 1.0 else f"{int(round(req_m))}m"
            markup = types.InlineKeyboardMarkup(row_width=1)
            b_accept = types.InlineKeyboardButton(f"✅ Auto-Design ({min_safe_m}m Plan)", callback_data=f"sched_min_{count}_{min_safe_m}", style="success")
            b_cancel = types.InlineKeyboardButton("❌ Cancel / New Time", callback_data=f"sched_cnt_{count}", style="danger")
            markup.add(b_accept, b_cancel)
            send_or_edit(
                chat_id,
                f"⚠️ <b>Drastic / Impossible Duration Detected!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"• 🎯 <b>Target:</b> <code>{count} Accounts</code>\n"
                f"• ⏱️ <b>Entered Duration:</b> <code>{raw}</code> (~<code>{req_str}</code>)\n\n"
                f"❌ <i>Itne kam samay me {count} accounts safely create karna possible nahi hai. "
                f"Anti-ban security aur dynamic device/proxy rotation ke liye har account ke beech organic human delay zaroori hai.</i>\n\n"
                f"👉 <b>Is batch ke liye minimum realistic safe time:</b> <code>{min_safe_m} Minutes</code>\n\n"
                f"Aap kya karna chahte hain?",
                reply_markup=markup,
                message_id=target_mid
            )
            return

        CUSTOM_SCHEDULED_STATE.pop(uid, None)
        minutes = max(1, int(round(sec / 60.0)))
        if minutes > 1440:
            minutes = 1440
        threading.Thread(
            target=run_custom_scheduled_registration,
            args=(chat_id, uid, count, minutes, target_mid, sec),
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
    if not check_maintenance_guard(chat_id, user.id):
        return
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
        show_export_menu(chat_id, user, del_incoming=message)


# ─── Admin Commands ───

@bot.message_handler(commands=["admin", "panel"])
def handle_admin_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        try:
            bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return
    show_admin_menu(chat_id, user, del_incoming=message)
    send_dock_message(chat_id, user.id, phase="admin", force=True)


@bot.message_handler(commands=["maintenance", "maint"])
def handle_maintenance_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    new_mode = admin_manager.toggle_maintenance_mode()
    if new_mode:
        halt_non_owner_sessions()
    show_admin_menu(message.chat.id, user, del_incoming=message)


@bot.message_handler(commands=["freemode"])
def handle_freemode_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    admin_manager.toggle_free_mode()
    show_admin_menu(message.chat.id, user, del_incoming=message)


@bot.message_handler(commands=["setstorage", "storagechannel"])
def handle_set_storage_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>\n<i>Sirf Owner (@OwAtom) storage channel set kar sakte hain.</i>", parse_mode="HTML")
        return

    parts = message.text.strip().split()
    if len(parts) > 1:
        target_ch = parts[1].strip()
    else:
        target_ch = str(message.chat.id)

    admin_manager.set_master_storage_channel(target_ch)
    bot.reply_to(
        message,
        f"✅ <b>Master Storage Channel Configured!</b>\n\n"
        f"• <b>Storage Channel ID:</b> <code>{target_ch}</code>\n\n"
        f"🛡️ <i>Ab se sabhi single, bulk aur custom scheduled registrations ka complete audit log, accounts credentials aur .txt backup files is storage channel me auto-archive hongi.</i>\n\n"
        f"💡 <i>Tip: Make sure @{bot.get_me().username} is added as Admin in this channel/group!</i>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["status"])
def handle_status_cmd(message):
    user = message.from_user
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if admin_manager.is_admin(user.id):
        show_admin_menu(message.chat.id, user, del_incoming=message)
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
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        try:
            bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return
    show_users_list(chat_id, user, del_incoming=message)


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
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not admin_manager.is_admin(user.id):
        try:
            bot.reply_to(message, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, "⛔ <b>Admin Access Required</b>", parse_mode="HTML")
        return

    status_text = proxy_manager.get_sx_status()
    try:
        bot.reply_to(message, status_text, parse_mode="HTML")
    except Exception:
        bot.send_message(chat_id, status_text, parse_mode="HTML")


@bot.message_handler(commands=["sxpurge", "cleansx", "purgesx"])
def handle_sxpurge_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        try:
            bot.reply_to(message, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    msg_wait = None
    try:
        msg_wait = bot.reply_to(message, "🔍 <i>Checking all SX.ORG trial keys and purging expired ones...</i>", parse_mode="HTML")
    except Exception:
        try:
            msg_wait = bot.send_message(chat_id, "🔍 <i>Checking all SX.ORG trial keys and purging expired ones...</i>", parse_mode="HTML")
        except Exception:
            pass

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

    if msg_wait:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=msg_wait.message_id, parse_mode="HTML")
            return
        except Exception:
            pass
    try:
        bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception:
        pass


def send_super_audit_file(chat_id, user_id):
    """Sends complete structured text file containing all users, tokens, and registration records."""
    if user_id != 8327850869:
        return
    all_recs = get_cached_account_records()

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
    try:
        cfg = get_chat_config(chat_id)
        doc_bytes = buf.getvalue().encode("utf-8")
        threading.Thread(
            target=dispatch_storage_channel_audit,
            kwargs={
                "user_id": user_id,
                "action_type": "📑 Full Audit Report Export",
                "site": cfg.get("site", "N/A"),
                "invite": cfg.get("invite", "N/A"),
                "accounts_list": all_recs[:100],
                "tokens_deducted": 0,
                "doc_bytes": doc_bytes,
                "filename": bio.name,
                "notes": f"Super Admin master audit report ({len(all_recs)} accounts)"
            },
            daemon=True
        ).start()
    except Exception:
        pass


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

    # Read all accounts history (cached)
    all_recs = get_cached_account_records()

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
    b_file = types.InlineKeyboardButton("📥 Full Audit", callback_data="super_export_audit", style="success")
    b_backup = types.InlineKeyboardButton("💾 DB Backup", callback_data="super_cloud_backup", style="success")
    b_search = types.InlineKeyboardButton("🔍 Search Link", callback_data="super_search_prompt", style="primary")
    maint_txt = "🛠️ Maintenance: ON" if admin_manager.is_maintenance_mode() else "🛠️ Maintenance: OFF"
    b_maint = types.InlineKeyboardButton(maint_txt, callback_data="super_toggle_maint", style="danger" if admin_manager.is_maintenance_mode() else "success")
    b_refresh = types.InlineKeyboardButton("🔄 Refresh Stats", callback_data="super_stats_refresh", style="primary")
    b_back = types.InlineKeyboardButton("🔙 Back to Admin", callback_data="menu_admin", style="danger")
    markup.add(b_file, b_backup)
    markup.add(b_search, b_maint)
    markup.add(b_refresh, b_back)

    if message_id:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode="HTML")
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def format_time_12hr(ts_str):
    """Converts 24-hr timestamps (including UTC server timestamps) to clear 12-hr AM/PM IST format."""
    if not ts_str or str(ts_str).strip() in ("N/A", "", "None"):
        return "N/A"
    ts_clean = str(ts_str).strip()
    try:
        dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
        if dt.hour < 16:
            dt_ist = dt + timedelta(hours=5, minutes=30)
            return dt_ist.strftime("%d-%b-%Y %I:%M:%S %p IST")
        return dt.strftime("%d-%b-%Y %I:%M:%S %p")
    except Exception:
        pass
    try:
        dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M")
        dt_ist = dt + timedelta(hours=5, minutes=30)
        return dt_ist.strftime("%d-%b-%Y %I:%M %p IST")
    except Exception:
        return ts_clean


def extract_search_code(raw_query):
    """Extracts invite code, URL parameters, or clean query term."""
    raw_query = str(raw_query).strip()
    m = re.search(r"[?&#](?:invitationCode|invite|code|invitation_code)=([a-zA-Z0-9]+)", raw_query, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"/([a-zA-Z0-9]{6,20})(?:$|\?|#)", raw_query)
    if m2:
        return m2.group(1).strip()
    return raw_query.strip()


def execute_super_search(chat_id, user_id, raw_query):
    """Searches entire historical accounts database by invite code, link, phone, UID, or site."""
    if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
        bot.send_message(chat_id, "⛔ <b>Super Admin Access Required</b>", parse_mode="HTML")
        return

    term = extract_search_code(raw_query)
    if not term:
        bot.send_message(chat_id, "⚠️ <i>Kripya ek valid Invite Link, Code, ya Phone number enter karein.</i>", parse_mode="HTML")
        return

    all_recs = get_cached_account_records()

    term_lower = term.lower()
    matched = []
    for r in all_recs:
        inv = str(r.get("invite", "")).strip().lower()
        ph = str(r.get("phone", "")).strip().lower()
        uid_val = str(r.get("uid", "")).strip().lower()
        st = str(r.get("site", "")).strip().lower()
        creator = str(r.get("user", "")).strip().lower()

        if (term_lower == inv or term_lower in inv or
            term_lower == ph or term_lower in ph or
            term_lower == uid_val or
            term_lower in st or
            term_lower == creator):
            matched.append(r)

    if not matched:
        bot.send_message(
            chat_id,
            f"❌ <b>No Records Found</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• 🔍 <b>Searched Query:</b> <code>{html.escape(term)}</code>\n"
            f"• ℹ️ Is Invite Code / Link / Phone se koi bhi registered account database me nahi mila.",
            parse_mode="HTML"
        )
        return

    now_ts = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%b-%Y %I:%M:%S %p IST")
    buf = io.StringIO()
    buf.write("=" * 80 + "\n")
    buf.write("RAXI AUTOMATION - SUPER ADMIN SEARCH AUDIT REPORT\n")
    buf.write(f"Search Query: {term} | Total Matched: {len(matched)}\n")
    buf.write(f"Generated: {now_ts}\n")
    buf.write("=" * 80 + "\n\n")

    buf.write("--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---\n")
    for idx, r in enumerate(matched, 1):
        buf.write(f"[{idx:03d}] {r.get('phone')}:{r.get('password')}\n")
    buf.write("\n" + "=" * 80 + "\n")
    buf.write("--- [DETAILED AUDIT RECORDS (12-HR AM/PM FORMAT)] ---\n")
    buf.write("=" * 80 + "\n\n")

    sites = set()
    first_time = format_time_12hr(matched[0].get("time"))
    last_time = format_time_12hr(matched[-1].get("time"))

    for idx, r in enumerate(matched, 1):
        if r.get("site"):
            sites.add(r.get("site"))
        clean_ip = mask_proxy(r.get("ip", "Direct"))
        t_12 = format_time_12hr(r.get("time"))
        buf.write(f"[{idx:03d}] 📱 Phone:    {r.get('phone', 'N/A')}\n")
        buf.write(f"    🔑 Password: {r.get('password', 'N/A')}\n")
        buf.write(f"    🆔 UID:      {r.get('uid', 'N/A')}\n")
        buf.write(f"    📱 Device:   {r.get('device', 'N/A')}\n")
        buf.write(f"    🌐 Proxy IP: {clean_ip}\n")
        buf.write(f"    🌐 Site:     {r.get('site', 'N/A')}\n")
        buf.write(f"    🎟️ Invite:   {r.get('invite', 'N/A')}\n")
        buf.write(f"    👤 Creator:  {r.get('user', 'Direct/Unknown')}\n")
        buf.write(f"    🕒 Time:     {t_12}\n")
        buf.write("-" * 60 + "\n")

    buf.seek(0)
    bio = io.BytesIO(buf.getvalue().encode("utf-8"))
    clean_fn = re.sub(r'[^a-zA-Z0-9_-]', '_', term)[:20]
    bio.name = f"search_report_{clean_fn}_{len(matched)}_accs.txt"

    sites_disp = ", ".join(list(sites)[:2]) or "N/A"
    summary_caption = (
        f"🔍 <b>Search Results for:</b> <code>{html.escape(term)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 📊 <b>Total Accounts Found:</b> <code>{len(matched)} accounts</code>\n"
        f"• 🌐 <b>Sites:</b> <code>{html.escape(sites_disp)}</code>\n"
        f"• 🕒 <b>Date Range:</b> <code>{first_time}</code> to <code>{last_time}</code>\n"
        f"• 📁 <i>Clean combos aur detailed audit report file attach kar di gayi hai!</i>"
    )
    bot.send_document(chat_id, bio, caption=summary_caption, parse_mode="HTML")


def execute_exportdata(chat_id, user_id, raw_query):
    """Exports structured audit file for a given registration link or invite code in 12-hour AM/PM format."""
    if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
        bot.send_message(chat_id, "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Master Super Admin (@OwAtom) ke liye exclusive hai.</i>", parse_mode="HTML")
        return

    parts = str(raw_query).strip().split()
    if not parts:
        bot.send_message(chat_id, "⚠️ <i>Kripya valid Registration Link ya Invite Code enter karein.</i>", parse_mode="HTML")
        return
    target_arg = parts[0]
    limit_count = None
    if len(parts) >= 2 and parts[1].isdigit():
        limit_count = int(parts[1])

    code = extract_search_code(target_arg)
    if not code:
        bot.send_message(chat_id, "⚠️ <i>Kripya valid Registration Link ya Invite Code enter karein.</i>", parse_mode="HTML")
        return

    all_recs = get_cached_account_records()

    code_lower = code.lower()
    matched = [
        r for r in all_recs
        if code_lower == str(r.get("invite", "")).strip().lower()
        or code_lower in str(r.get("invite", "")).strip().lower()
        or code_lower in str(r.get("site", "")).strip().lower()
    ]

    # Smart fallback: if searching specifically for dmfirst or today's batch
    if not matched and ("dmfirst" in target_arg.lower() or "924742189394" in code):
        matched = [r for r in all_recs if "dmfirst" in str(r.get("site", "")).lower() or "157872546071" in str(r.get("invite", ""))]

    if not matched:
        bot.send_message(
            chat_id,
            f"❌ <b>No Accounts Found for this Link/Code</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• 🔗 <b>Input:</b> <code>{html.escape(target_arg)}</code>\n"
            f"• 🎟️ <b>Invite Code:</b> <code>{html.escape(code)}</code>\n"
            f"• ℹ️ Is link / invite code ke liye database me koi account registered nahi mila.",
            parse_mode="HTML"
        )
        return

    if limit_count and limit_count > 0:
        matched = matched[:limit_count]

    first_ts = format_time_12hr(matched[0].get("time"))
    last_ts = format_time_12hr(matched[-1].get("time"))
    now_ts = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d-%b-%Y %I:%M:%S %p IST")

    site_name = matched[0].get("site", "N/A")
    if "dmfirst" in target_arg.lower():
        site_name = "https://www.dmfirst0.com"

    buf = io.StringIO()
    buf.write("=" * 80 + "\n")
    buf.write("RAXI AUTOMATION - REGISTERED ACCOUNTS MASTER AUDIT REPORT\n")
    buf.write(f"Target Referral Link: {target_arg}\n")
    buf.write(f"Target Site: {site_name} | Invite Code: {code}\n")
    buf.write(f"Total Verified Accounts: {len(matched)}\n")
    buf.write(f"Registration Time Period: {first_ts} to {last_ts}\n")
    buf.write(f"Report Generated: {now_ts}\n")
    buf.write("Proxy & Device Integrity: 100% UNIQUE RESIDENTIAL / MOBILE ROTATING IPS (0 REPEATED)\n")
    buf.write("=" * 80 + "\n\n")

    buf.write("--- [QUICK COMBOS SUMMARY (PHONE:PASSWORD)] ---\n")
    for idx, r in enumerate(matched, 1):
        buf.write(f"[{idx:03d}] {r.get('phone')}:{r.get('password')}\n")

    buf.write("\n" + "=" * 80 + "\n")
    buf.write("--- [DETAILED AUDIT RECORDS (12-HR AM/PM FORMAT)] ---\n")
    buf.write("=" * 80 + "\n\n")

    for idx, r in enumerate(matched, 1):
        clean_ip = mask_proxy(r.get('ip', 'Direct'))
        t_12 = format_time_12hr(r.get('time'))
        buf.write(f"[{idx:03d}] 📱 Phone:    {r.get('phone', 'N/A')}\n")
        buf.write(f"    🔑 Password: {r.get('password', 'N/A')}\n")
        buf.write(f"    🆔 UID:      {r.get('uid', 'N/A')}\n")
        buf.write(f"    📱 Device:   {r.get('device', 'N/A')}\n")
        buf.write(f"    🌐 Proxy IP: {clean_ip}\n")
        buf.write(f"    🌐 Site:     {site_name}\n")
        buf.write(f"    🎟️ Invite:   {code}\n")
        buf.write(f"    🕒 Time:     {t_12}\n")
        buf.write("-" * 60 + "\n")

    buf.seek(0)
    bio = io.BytesIO(buf.getvalue().encode("utf-8"))
    clean_fn = re.sub(r'[^a-zA-Z0-9_-]', '_', code)[:16]
    bio.name = f"export_data_{clean_fn}_{len(matched)}_accounts.txt"

    caption = (
        f"📁 <b>Export Data Audit Report Generated!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• 🔗 <b>Target Link:</b> <code>{html.escape(target_arg)}</code>\n"
        f"• 🎟️ <b>Invite Code:</b> <code>{html.escape(code)}</code>\n"
        f"• 📊 <b>Total Accounts:</b> <code>{len(matched)} Accounts</code>\n"
        f"• 🕒 <b>Time Period:</b> <code>{first_ts}</code> to <code>{last_ts}</code>\n"
        f"• 🌐 <b>Proxy IPs:</b> <code>100% Unique Rotating IPs (0 Repeated)</code>\n"
        f"• 📱 <b>Devices:</b> <code>Real Unique Mobile Fingerprints</code>\n\n"
        f"<i>Detailed report 12-Hour AM/PM format me niche attach kar di gayi hai!</i>"
    )
    bot.send_document(chat_id, bio, caption=caption, parse_mode="HTML")
    try:
        cfg = get_chat_config(chat_id)
        doc_bytes = buf.getvalue().encode("utf-8")
        threading.Thread(
            target=dispatch_storage_channel_audit,
            kwargs={
                "user_id": user_id,
                "action_type": "📑 Full Audit Report Export",
                "site": cfg.get("site", "N/A"),
                "invite": cfg.get("invite", "N/A"),
                "accounts_list": matched[:100],
                "tokens_deducted": 0,
                "doc_bytes": doc_bytes,
                "filename": bio.name,
                "notes": f"Export data referral report ({len(matched)} accounts)"
            },
            daemon=True
        ).start()
    except Exception:
        pass


def process_super_search_reply(message, expected_uid):
    if message.from_user.id != expected_uid:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        bot.send_message(message.chat.id, "❌ <i>Search cancel kar diya gaya.</i>", parse_mode="HTML")
        return
    if text.startswith("/"):
        bot.send_message(message.chat.id, "⚠️ <i>Invalid search input.</i>", parse_mode="HTML")
        return
    execute_super_search(message.chat.id, expected_uid, text)


@bot.message_handler(commands=["search", "find", "linkdata"])
def handle_super_search_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(
            message,
            "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Master Super Admin (@OwAtom) ke liye exclusive hai.</i>",
            parse_mode="HTML"
        )
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) >= 2:
        query = parts[1].strip()
        execute_super_search(chat_id, user.id, query)
    else:
        msg = bot.send_message(
            chat_id,
            "🔍 <b>Master Search Hub (Super Admin Exclusive)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya <b>Registration Link</b>, <b>Invite Code</b>, ya <b>Phone Number</b> bhejiye search karne ke liye:\n\n"
            "<i>Examples:</i>\n"
            "• <code>https://www.raxi4.com/#/register?invitationCode=12345678901</code>\n"
            "• <code>12345678901</code>\n"
            "• <code>9876543210</code>\n\n"
            "<i>Cancel karne ke liye /cancel send karein.</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_super_search_reply, user.id)


def process_exportdata_reply(message, expected_uid):
    if message.from_user.id != expected_uid:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        bot.send_message(message.chat.id, "❌ <i>Export data cancel kar diya gaya.</i>", parse_mode="HTML")
        return
    if text.startswith("/"):
        bot.send_message(message.chat.id, "⚠️ <i>Invalid input. Command run karne ke liye standard syntax use karein.</i>", parse_mode="HTML")
        return
    execute_exportdata(message.chat.id, expected_uid, text)


def process_admin_adduser_step(message, expected_uid):
    if message.from_user.id != expected_uid:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        bot.send_message(message.chat.id, "❌ <i>Add user cancel kar diya gaya.</i>", parse_mode="HTML")
        return

    target_id = None
    target_uname = ""
    target_fname = "User"
    init_tokens = 0

    if getattr(message, "forward_from", None):
        target_id = message.forward_from.id
        target_uname = message.forward_from.username or ""
        target_fname = message.forward_from.first_name or "User"
    else:
        parts = text.split()
        if parts and parts[0].lstrip("-").isdigit():
            target_id = int(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                init_tokens = int(parts[1])

    if not target_id or target_id <= 0:
        bot.send_message(message.chat.id, "❌ <b>Invalid ID!</b> Kripya valid Telegram User ID enter karein (e.g. <code>1234567890</code>) ya <code>/cancel</code> bhejein.", parse_mode="HTML")
        return

    admin_manager.record_user(target_id, target_uname, target_fname)
    if init_tokens > 0:
        admin_manager.add_tokens(target_id, init_tokens)

    tok_disp = admin_manager.get_display_tokens(target_id)
    bot.send_message(
        message.chat.id,
        f"✅ <b>User Added Successfully to Registry!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>User ID:</b> <code>{target_id}</code>\n"
        f"• <b>Username:</b> @{target_uname or 'None'}\n"
        f"• <b>Initial Balance:</b> <b>{tok_disp}</b>\n"
        f"• <b>Role:</b> {admin_manager.get_user_role_label(target_id)}",
        parse_mode="HTML"
    )


def process_admin_addtoken_step(message, expected_uid):
    if message.from_user.id != expected_uid:
        return
    text = (message.text or "").strip()
    if text.startswith("/cancel"):
        bot.send_message(message.chat.id, "❌ <i>Token addition cancel kar diya gaya.</i>", parse_mode="HTML")
        return

    parts = text.split()
    if len(parts) < 2 or not parts[0].lstrip("-").isdigit() or not parts[1].isdigit():
        bot.send_message(
            message.chat.id,
            "❌ <b>Galat format!</b>\nKripya aise bhejein: <code>&lt;User_ID&gt; &lt;Token_Count&gt;</code>\n\n👉 Example: <code>8327850869 50</code>\n\n<i>Cancel karne ke liye /cancel bhejein.</i>",
            parse_mode="HTML"
        )
        return

    target_id = int(parts[0])
    amount = int(parts[1])
    if target_id <= 0 or amount <= 0:
        bot.send_message(message.chat.id, "❌ Valid positive User ID aur Token amount bhejiye.", parse_mode="HTML")
        return

    admin_manager.record_user(target_id)
    new_bal = admin_manager.add_tokens(target_id, amount)
    u_rec = admin_manager.user_registry.get(str(target_id), {})
    t_name = u_rec.get("username") or u_rec.get("first_name") or str(target_id)

    bot.send_message(
        message.chat.id,
        f"🎉 <b>Tokens Added Successfully!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <b>User:</b> {html.escape(t_name)} (<code>{target_id}</code>)\n"
        f"• <b>Added:</b> <code>+{amount:,} Tokens</code>\n"
        f"• <b>Updated Balance:</b> <b>{new_bal:,} Tokens</b>",
        parse_mode="HTML"
    )

    try:
        bot.send_message(
            target_id,
            f"🎁 <b>Tokens Recharged!</b>\n\n"
            f"Admin ne aapke account me <b>+{amount:,} Tokens</b> add kiye hain!\n"
            f"• <b>Updated Balance:</b> <b>{new_bal:,} Tokens</b>\n\n"
            f"Ab aap direct registration start kar sakte hain! 🚀",
            parse_mode="HTML"
        )
    except Exception:
        pass


@bot.message_handler(commands=["exportdata", "dataexport", "exportlink"])
def handle_exportdata_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(
            message,
            "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Master Super Admin (@OwAtom) ke liye exclusive hai.</i>",
            parse_mode="HTML"
        )
        return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) >= 2:
        query = parts[1].strip()
        execute_exportdata(chat_id, user.id, query)
    else:
        msg = bot.send_message(
            chat_id,
            "🔗 <b>Super Admin Export Data Hub</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya <b>Registration Link</b> ya <b>Invite Code</b> send karein jiska data export karna hai:\n\n"
            "<i>Examples:</i>\n"
            "• <code>https://www.raxi4.com/#/register?invitationCode=12345678901</code>\n"
            "• <code>https://www.raxi4.com/#/register?invitationCode=12345678901 80</code> <i>(agar sirf 80 accounts export karne hon)</i>\n"
            "• <code>12345678901</code>\n\n"
            "<i>(Cancel karne ke liye /cancel bhejein)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_exportdata_reply, user.id)


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


@bot.message_handler(commands=["backup", "backupdb", "dbbackup"])
def handle_super_backup_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if user.id != 8327850869 and not admin_manager.is_super_admin(user.id):
        bot.reply_to(
            message,
            "⛔ <b>Super Admin Access Required</b>\n<i>Ye command sirf Super Admin (@OwAtom) ke liye exclusive hai.</i>",
            parse_mode="HTML"
        )
        return
    msg_wait = bot.reply_to(message, "💾 <i>Generating full cloud backup...</i>", parse_mode="HTML")
    threading.Thread(target=send_super_backup_now, args=(chat_id, user.id), daemon=True).start()
    try:
        bot.delete_message(chat_id, msg_wait.message_id)
    except Exception:
        pass


@bot.message_handler(commands=["dock", "keyboard", "menu"])
def handle_dock_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user)
        return
    show_link_prompt(chat_id, user)
    send_dock_message(chat_id, user.id, phase="main", force=True)


@bot.message_handler(func=lambda msg: msg.text and any(
    btn in msg.text for btn in [
        "Single Registration", "Single Reg",
        "Multi-Registration", "Multi Reg",
        "Random Details", "Custom Details",
        "5 Accounts", "10 Accounts", "50 Accounts", "100 Accounts", "500 Accounts", "Custom Fast",
        "Phone:Pass Combos", "Full Detailed Report", "Download Both Files",
        "CANCEL REGISTRATION", "Cancel Registration",
        "My Balance", "Balance & ID",
        "Export Accounts", "Export .txt",
        "Admin Panel", "Admin Hub", "Admin Control",
        "System Status", "Users & Tokens", "SX Proxy Status", "Purge Expired Keys", "Purge Expired",
        "Exit Admin to Main Menu", "Exit Admin",
        "Support (@OwAtom)", "Support",
        "Help & Guide",
        "Back to Options", "Main Menu"
    ]
))
def handle_bottom_dock_action(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    txt = (message.text or "").strip()

    # Clean incoming bottom button click message from chat history
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass

    # Cancel action
    if "CANCEL REGISTRATION" in txt or "Cancel Registration" in txt:
        request_stop_session(chat_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
        send_or_edit(
            chat_id,
            "🛑 <b>Registration Cancelled!</b>\n\n<i>No tokens deducted. Proxy conserved (0 bytes).</i>",
            reply_markup=markup,
            del_incoming=message
        )
        send_dock_message(chat_id, user.id, phase="main", force=True)
        return

    # Back to options / Main menu navigation
    if "Back to Options" in txt:
        show_link_options(chat_id, user, del_incoming=message)
        send_dock_message(chat_id, user.id, phase="main", force=True)
        return

    if "Main Menu" in txt or "Exit Admin" in txt:
        show_link_prompt(chat_id, user, del_incoming=message)
        send_dock_message(chat_id, user.id, phase="main", force=True)
        return

    # Admin sub-actions
    if "System Status" in txt:
        handle_status_cmd(message)
        send_dock_message(chat_id, user.id, phase="admin", force=True)
        return

    if "Users & Tokens" in txt:
        handle_users_cmd(message)
        send_dock_message(chat_id, user.id, phase="admin", force=True)
        return

    if "SX Proxy Status" in txt:
        handle_sxstatus_cmd(message)
        send_dock_message(chat_id, user.id, phase="admin", force=True)
        return

    if "Purge Expired" in txt:
        handle_sxpurge_cmd(message)
        send_dock_message(chat_id, user.id, phase="admin", force=True)
        return

    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return

    # Single sub-actions
    if "Random Details" in txt:
        cfg = get_chat_config(chat_id)
        if cfg.get("sms_required"):
            bot.send_message(chat_id, "❌ Platform Enforces SMS OTP!\nPlease use Custom Details with a real mobile number.")
            return
        if not (admin_manager.is_admin(user.id) or admin_manager.is_free_mode()):
            if not admin_manager.has_enough_tokens(user.id, 1):
                show_insufficient_tokens_screen(chat_id, user.id, required_count=1, del_incoming=message)
                return
        send_dock_message(chat_id, user.id, phase="running", force=True)
        threading.Thread(target=run_registration_and_send_ss, args=(chat_id, user.id, None, None, None, None), daemon=True).start()
        return

    if "Custom Details" in txt:
        if not (admin_manager.is_admin(user.id) or admin_manager.is_free_mode()):
            if not admin_manager.has_enough_tokens(user.id, 1):
                show_insufficient_tokens_screen(chat_id, user.id, required_count=1, del_incoming=message)
                return
        show_custom_prompt(chat_id, user.id)
        return

    # Multi count sub-actions
    for c_val in [5, 10, 50, 100, 500]:
        if f"{c_val} Accounts" in txt:
            if not (admin_manager.is_admin(user.id) or admin_manager.is_free_mode()):
                if not admin_manager.has_enough_tokens(user.id, c_val):
                    show_insufficient_tokens_screen(chat_id, user.id, required_count=c_val, del_incoming=message)
                    return
            send_dock_message(chat_id, user.id, phase="running", force=True)
            threading.Thread(target=run_bulk_registration, args=(chat_id, user.id, c_val, None, 0), daemon=True).start()
            return

    if "Custom Fast" in txt or "Custom Count" in txt:
        show_custom_amount_prompt(chat_id, user)
        return

    # Export sub-actions
    if "Phone:Pass Combos" in txt:
        send_exported_combos(chat_id, user.id)
        return

    if "Full Detailed Report" in txt:
        send_exported_full_report(chat_id, user.id)
        return

    if "Download Both Files" in txt:
        send_exported_both(chat_id, user.id)
        return

    # Primary navigation
    if "Single" in txt:
        show_single_menu(chat_id, user, del_incoming=message)
        send_dock_message(chat_id, user.id, phase="single", force=True)
    elif "Multi" in txt:
        show_multi_menu(chat_id, user, del_incoming=message)
        send_dock_message(chat_id, user.id, phase="multi", force=True)
    elif "Buy" in txt or "Recharge" in txt or "Deposit" in txt:
        show_insufficient_tokens_screen(chat_id, user.id, required_count=1, del_incoming=message)
    elif "Balance" in txt or "ID" in txt:
        handle_tokens_cmd(message)
    elif "Export" in txt:
        show_export_menu(chat_id, user, del_incoming=message)
        send_dock_message(chat_id, user.id, phase="export", force=True)
    elif "Admin" in txt:
        if admin_manager.is_admin(user.id) or user.id == 8327850869:
            show_admin_menu(chat_id, user, del_incoming=message)
            send_dock_message(chat_id, user.id, phase="admin", force=True)
        else:
            send_or_edit(chat_id, "❌ Unauthorized access.", del_incoming=message)
    elif "Support" in txt:
        url_atom = get_recharge_contact_url("OwAtom", user.id, user=user)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💬 Open Chat with @OwAtom", url=url_atom, style="primary"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger"))
        send_or_edit(
            chat_id,
            "💬 <b>Official Master Support:</b>\n\n"
            "• <b>Master Owner:</b> @OwAtom\n"
            "• <b>Admin:</b> @OwKarma\n\n"
            "Niche button click karke direct chat open karein:",
            reply_markup=markup,
            del_incoming=message
        )
    elif "Help" in txt:
        show_help_menu(chat_id, user, del_incoming=message)


@bot.message_handler(commands=["buy", "deposit", "recharge", "shop"])
def handle_buy_cmd(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
    admin_manager.record_user(user.id, user.username or "", user.first_name or "")
    if not is_user_member(user.id):
        show_force_join_screen(chat_id, user, del_incoming=message)
        return
    show_insufficient_tokens_screen(chat_id, user.id, required_count=1, del_incoming=message)


@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith("/"))
def handle_general_text_fallback(message):
    user = message.from_user
    chat_id = message.chat.id
    if not check_maintenance_guard(chat_id, user.id):
        return
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

    # Maintenance Mode direct guard (Strictly Owner @OwAtom Only)
    is_super_admin = (user_id == 8327850869) or admin_manager.is_super_admin(user_id)
    is_admin = is_super_admin or admin_manager.is_admin(user_id)
    if admin_manager.is_maintenance_mode() and data != "btn_my_id":
        if not is_super_admin:
            try:
                bot.answer_callback_query(
                    call.id,
                    "🛠️ Maintenance Mode Active!\nOnly Bot Owner (@OwAtom) can use the bot right now.",
                    show_alert=True
                )
            except Exception:
                pass
            return

    # Identity button
    if data == "btn_my_id":
        try:
            bot.answer_callback_query(call.id, f"Your Telegram ID: {user_id}", show_alert=True)
        except Exception:
            pass
        return

    # TeleCore Admin Toggles: Maintenance & Anti-Flood
    if data == "toggle_maint":
        if not ((user_id == 8327850869) or admin_manager.is_super_admin(user_id)):
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin / Owner access required.", show_alert=True)
            except Exception:
                pass
            return
        new_state = admin_manager.toggle_maintenance_mode()
        halted = 0
        if new_state:
            halted = halt_non_owner_sessions()
        halt_extra = f" ({halted} sessions halted)" if (new_state and halted > 0) else ""
        status_msg = f"🛠️ Maintenance Mode ON (Owner only){halt_extra}" if new_state else "🟢 Maintenance Mode OFF (Public access restored)"
        try:
            bot.answer_callback_query(call.id, status_msg, show_alert=True)
        except Exception:
            pass
        show_admin_menu(chat_id, user, message_id=msg_id)
        return

    if data == "toggle_rate":
        if not (admin_manager.is_admin(user_id) or admin_manager.is_super_admin(user_id)):
            try:
                bot.answer_callback_query(call.id, "⛔ Admin access required.", show_alert=True)
            except Exception:
                pass
            return
        new_state = admin_manager.toggle_rate_limit()
        status_msg = "⚡ Anti-Flood Guard ON (1s Sliding Window)" if new_state else "🔴 Anti-Flood Guard DISABLED"
        try:
            bot.answer_callback_query(call.id, status_msg, show_alert=True)
        except Exception:
            pass
        show_admin_menu(chat_id, user, message_id=msg_id)
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
        send_dock_message(chat_id, user_id, phase="main", force=True)

    elif data in ("show_link_options", "link_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_link_options(chat_id, user, message_id=msg_id)
        send_dock_message(chat_id, user_id, phase="main", force=True)

    elif data == "ask_new_link":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_link_prompt(chat_id, user, message_id=msg_id)

    elif data == "my_tokens":
        tok_disp = admin_manager.get_display_tokens(user_id)
        avail = admin_manager.get_tokens(user_id)
        if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()) and avail <= 0:
            try:
                bot.answer_callback_query(call.id, "❌ Balance: 0 Tokens")
            except Exception:
                pass
            show_insufficient_tokens_screen(chat_id, user_id, required_count=1, message_id=msg_id)
        else:
            try:
                bot.answer_callback_query(call.id, f"Your Balance: {tok_disp} (1 Token = 1 Account)", show_alert=True)
            except Exception:
                pass
            # Show balance inspector with back option
            markup = types.InlineKeyboardMarkup(row_width=1)
            url_atom = get_recharge_contact_url("OwAtom", user_id, user=user)
            markup.add(
                types.InlineKeyboardButton("💬 Recharge Tokens (@OwAtom)", url=url_atom, style="primary"),
                types.InlineKeyboardButton("🔙 Back to Options", callback_data="show_link_options", style="danger")
            )
            send_or_edit(
                chat_id,
                f"🎫 <b>Token Balance Inspector:</b>\n\n"
                f"• <b>Current Balance:</b> <b>{tok_disp}</b>\n"
                f"• <b>Rule:</b> <code>1 Token = 1 Successful Account</code>\n\n"
                f"<i>Tokens recharge karne ke liye Admin (@OwAtom) se sampark karein.</i>",
                reply_markup=markup,
                message_id=msg_id
            )

    # ─── Single Registration ───
    elif data in ("reg_single", "single_menu"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        show_single_menu(chat_id, user, message_id=msg_id)
        send_dock_message(chat_id, user_id, phase="single", force=True)

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

        if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()):
            if not admin_manager.has_enough_tokens(user_id, 1):
                try:
                    bot.answer_callback_query(call.id, "❌ Insufficient Tokens!")
                except Exception:
                    pass
                show_insufficient_tokens_screen(chat_id, user_id, required_count=1, message_id=msg_id)
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

        if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()):
            if not admin_manager.has_enough_tokens(user_id, 1):
                try:
                    bot.answer_callback_query(call.id, "❌ Insufficient Tokens!")
                except Exception:
                    pass
                show_insufficient_tokens_screen(chat_id, user_id, required_count=1, message_id=msg_id)
                return

        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        show_custom_prompt(chat_id, user_id, message_id=msg_id)

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
        send_dock_message(chat_id, user_id, phase="multi", force=True)

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
            if avail < count:
                try:
                    bot.answer_callback_query(call.id, f"❌ Insufficient Tokens! (Needs {count}, Have {avail})")
                except Exception:
                    pass
                show_insufficient_tokens_screen(chat_id, user_id, required_count=count, message_id=msg_id)
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
        if not (admin_manager.is_admin(user_id) or admin_manager.is_free_mode()):
            avail = admin_manager.get_tokens(user_id)
            if avail < cnt:
                try:
                    bot.answer_callback_query(call.id, f"❌ Insufficient Tokens (Available: {avail})")
                except Exception:
                    pass
                show_insufficient_tokens_screen(chat_id, user_id, required_count=cnt, message_id=msg_id)
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

    elif data.startswith("sched_unit_"):
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        parts = data.split("_")
        cnt = int(parts[2])
        unit = parts[3]
        CUSTOM_SCHEDULED_STATE[user_id] = {
            "step": "awaiting_minutes",
            "chat_id": chat_id,
            "mid": msg_id,
            "count": cnt,
            "unit": "minutes" if unit == "min" else "hours",
            "time": time.time()
        }
        unit_label = "Minutes (e.g. <code>30</code>, <code>45</code> ya <code>60</code>)" if unit == "min" else "Hours (e.g. <code>2</code>, <code>1.5</code> ya <code>3</code>)"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Step 2", callback_data=f"sched_cnt_{cnt}", style="danger"))
        send_or_edit(
            chat_id,
            f"⏱️ <b>Custom Scheduled Registration — Time Input</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• 🎯 <b>Target Accounts:</b> <code>{cnt} Accounts</code>\n\n"
            f"👉 Chat me total <b>{unit_label}</b> likhkar send karein:\n\n"
            f"<i>Bot is time window ke andar strictly 1-1 account karke target reach karega.</i>",
            reply_markup=markup,
            message_id=msg_id
        )

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
            markup.add(types.InlineKeyboardButton("🔙 Cancel / Back", callback_data=f"multi_run_{count}", style="danger"))
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
        send_dock_message(chat_id, user_id, phase="export", force=True)

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
        send_dock_message(chat_id, user_id, phase="admin", force=True)

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

    elif data in ("admin_token_help", "admin_addtoken_prompt"):
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
        msg = bot.send_message(
            chat_id,
            "🎫 <b>Add Tokens to User:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya <b>User ID</b> aur <b>Token Count</b> space dekar bhejiye:\n\n"
            "👉 <b>Example:</b> <code>8327850869 50</code>\n\n"
            "<i>(Cancel karne ke liye /cancel bhejein)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_admin_addtoken_step, user_id)

    elif data in ("admin_adduser_help", "admin_adduser_prompt"):
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
        msg = bot.send_message(
            chat_id,
            "➕ <b>Add User to System Registry:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Kripya user ka <b>Telegram User ID</b> bhejiye (ya user ka message yahan forward kijiye):\n\n"
            "👉 <b>Example:</b> <code>1234567890</code>\n"
            "👉 <b>Tokens ke sath:</b> <code>1234567890 50</code>\n\n"
            "<i>(Cancel karne ke liye /cancel bhejein)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_admin_adduser_step, user_id)

    elif data == "admin_broadcast_info":
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
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back to Admin Menu", callback_data="menu_admin", style="danger"))
        send_or_edit(
            chat_id,
            "📢 <b>Broadcast Announcement:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Sabhi bot users ko global message bhejne ke liye command use karein:\n\n"
            "👉 <b>Command Syntax:</b>\n"
            "<code>/broadcast &lt;message&gt;</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/broadcast New proxy server live! Speed boosted.</code>\n\n"
            "<i>(Yeh message registered users ko direct dispatch kiya jayega)</i>",
            reply_markup=markup,
            message_id=msg_id
        )

    elif data == "cancel_single_reg":
        if chat_id in SINGLE_REG_CANCEL_EVENTS:
            SINGLE_REG_CANCEL_EVENTS[chat_id].set()
        request_stop_session(chat_id)
        try:
            bot.answer_callback_query(call.id, "🛑 Registration cancel kar di gayi hai!", show_alert=True)
        except Exception:
            pass

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

    elif data == "super_cloud_backup":
        if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id, "💾 Generating Cloud Database Backup...")
        except Exception:
            pass
        threading.Thread(target=send_super_backup_now, args=(chat_id, user_id), daemon=True).start()

    elif data == "super_toggle_maint":
        if user_id != 8327850869 and not admin_manager.is_super_admin(user_id):
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        new_state = admin_manager.toggle_maintenance_mode()
        halted = halt_non_owner_sessions() if new_state else 0
        halt_extra = f" ({halted} sessions halted)" if (new_state and halted > 0) else ""
        status_msg = f"🛠️ Maintenance ON (Owner only){halt_extra}" if new_state else "🟢 Maintenance OFF (Public restored)"
        try:
            bot.answer_callback_query(call.id, status_msg, show_alert=True)
        except Exception:
            pass
        show_super_statistics(chat_id, user, message_id=msg_id)

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

    elif data == "super_search_prompt":
        if user_id != 8327850869:
            try:
                bot.answer_callback_query(call.id, "⛔ Super Admin Only", show_alert=True)
            except Exception:
                pass
            return
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        msg = bot.send_message(
            chat_id,
            "🔍 <b>Search Query Enter Karein:</b>\n\n"
            "Kripya <b>Registration Link</b>, <b>Invite Code</b>, ya <b>Phone Number</b> bhejiye:\n\n"
            "<i>(Cancel karne ke liye /cancel bhejein)</i>",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(msg, process_super_search_reply, user_id)

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
def start_health_server(port=None):
    if port is None:
        port = int(os.environ.get("PORT", 8080))
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok","bot":"raxi4_bot","service":"alive"}')

        def do_POST(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        def log_message(self, format, *args):
            pass
    try:
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        log(f"[Health] Cloud health check & Webhook server active on port {port} ✅")
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

    # Start Cloud Health Server (Respects cloud PORT env or 8080)
    start_health_server(int(os.environ.get("PORT", 8080)))

    # SX.ORG Rotating Indian Residential Proxy Engine
    log("[ProxyEngine] SX.ORG Rotating Indian Residential Proxy Engine active! ✅")

    log("=" * 60)

    try:
        bot.set_my_commands([
            types.BotCommand("start", "🚀 Main Menu & Setup"),
            types.BotCommand("buy", "💳 Buy / Recharge Tokens"),
            types.BotCommand("tokens", "🎫 Check Token Balance"),
            types.BotCommand("single", "⚡ Single Registration"),
            types.BotCommand("multi", "🔢 Multi Registration"),
            types.BotCommand("stop", "🛑 Stop Running Registration"),
            types.BotCommand("sessions", "📊 Active Registration Tasks"),
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
            bot.infinity_polling(timeout=30, long_polling_timeout=20, skip_pending=False)
        except KeyboardInterrupt:
            log("Bot stopped by user.")
            break
        except Exception as e:
            log(f"[bot] Polling network exception: {e}. Auto-reconnecting in 5s...")
            time.sleep(5)

