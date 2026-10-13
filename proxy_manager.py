#!/usr/bin/env python3
# language: Python, file: proxy_manager.py
# High-Performance Automated Proxy Scraper & Health-Checker Daemon
# Supports 500+ on-demand verified proxies with DOMAIN-ISOLATED tracking.
# (An IP used for raxiwin is still 100% eligible for bigmumbai or other platforms!)

import os
import re
import time
import shutil
import logging
import threading
import gc
try:
    threading.stack_size(262144)  # 256 KB thread stack size (preserves low RAM in 150MB cgroup)
except Exception:
    pass
import urllib.parse
import requests
import concurrent.futures
import random
import json
import hashlib
import string
import secrets

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [ProxyEngine] %(message)s")
logger = logging.getLogger("ProxyEngine")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_persistent_data_dir() -> str:
    jrnm_vol = "/app/data"
    if os.path.exists(jrnm_vol) and os.path.isdir(jrnm_vol):
        return jrnm_vol
    return BASE_DIR

DATA_DIR = get_persistent_data_dir()

# File locations
PROXIES_FILE = os.path.join(DATA_DIR, "working_proxies.txt")
USED_PROXIES_FILE = os.path.join(DATA_DIR, "used_proxies.txt")

ALT_DIRS = ["/home/piyush/Desktop", "/home/piyush/Downloads/Telegram Desktop"]

# Curated High-Yield Multi-Protocol Sources (105+ verified direct endpoints)
SOURCES = [
    # Jetkai Global
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
    # Proxifly Protocol Lists
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
    # TheSpeedX Multi-Protocol
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    # Sunny9577 Automated Scraper
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt",
    # Ercin Dedeoglu Multi-Protocol
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
    # Monosans Verified & Anonymous
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks4.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies_anonymous/socks5.txt",
    # Roosterkid Raw Feeds
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
    # Vakhov Fresh Proxy List
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
    # Zaeem20 Protocol Lists
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
    # MuRongPIG Master Feeds
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
    # Zevtyardt Protocol Feeds
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks4.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/all.txt",
    # PrxChk Verified Lists
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
    # Saisuiu Lion Feeds
    "https://raw.githubusercontent.com/saisuiu/Lion-proxy/main/http.txt",
    "https://raw.githubusercontent.com/saisuiu/Lion-proxy/main/socks4.txt",
    "https://raw.githubusercontent.com/saisuiu/Lion-proxy/main/socks5.txt",
    # Anonym0usWork Global
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks4_proxies.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5_proxies.txt",
    # KangProxy Feeds
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/https.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks4.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/socks5.txt",
    # TuanMinPay Live Lists
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks4.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks5.txt",
    # ShiftyTR Global
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    # Mmpx12 Live Feeds
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    # B4RC0DE Multi-Protocol
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS4.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
    # Rdavydov Global Lists
    "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks5.txt",
    # Elliottophellia Checked Feeds
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks4/global/socks4_checked.txt",
    "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
    # Im-notify Verified Lists
    "https://raw.githubusercontent.com/im-notify/free-proxy-list/main/data/proxies/http.txt",
    "https://raw.githubusercontent.com/im-notify/free-proxy-list/main/data/proxies/socks4.txt",
    "https://raw.githubusercontent.com/im-notify/free-proxy-list/main/data/proxies/socks5.txt",
    # Rx443 Online Feeds
    "https://raw.githubusercontent.com/rx443/proxy-list/main/online/http.txt",
    "https://raw.githubusercontent.com/rx443/proxy-list/main/online/https.txt",
    # Diverse Curated Feeds
    "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/proxiesmaster/Free-Proxy-List/main/proxies.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
    "https://raw.githubusercontent.com/aslisk/proxyhttps/main/https.txt",
    "https://raw.githubusercontent.com/caliphdev/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/hyperbeats/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/igor-kash/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/miku996/Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/ObscureCoder/proxy-scraper/main/http.txt",
    "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/Rdewan/Free-Proxy-List/main/http.txt",
    "https://raw.githubusercontent.com/satoru8/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/scaseless/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/simon987/much-proxy/master/proxies.txt",
    "https://raw.githubusercontent.com/sourabh-bhat/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/Stamix/free-proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/uplink-dev/proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vishalsingh1997/proxies/main/proxies.txt",
    "https://raw.githubusercontent.com/yusuf864/proxies/master/proxies.txt",
    "https://raw.githubusercontent.com/casals-ar/proxy-list/main/https",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
    "https://raw.githubusercontent.com/fahimscirex/proxybd/master/proxylist/http.txt",
    # Live Proxy Scraping APIs
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=ipport&format=text",
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks4&proxy_format=ipport&format=text",
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&proxy_format=ipport&format=text",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=2500&country=all&ssl=yes&anonymity=all",
]

PLATFORM_TEST_URLS = [
    "https://api.raxiqaz.com/api/webapi/Register",
    "https://api.dmfirst9api.com/api/webapi/Captcha",
    "https://api.api51gameapi.com/api/webapi/Captcha"
]
TARGET_CHECK_URL = PLATFORM_TEST_URLS[0]
CONNECT_TIMEOUT = 2.5
READ_TIMEOUT = 3.5

POOL_TARGET = 60        # Target: 60 verified responsive working proxies (memory-safe for 150MB RAM)
POOL_MIN_THRESHOLD = 15  # Trigger gentle refill when pool drops below 15
HEALTH_CHECK_INTERVAL = 3600  # 60 minutes
POLL_INTERVAL = 60      # Active poll interval in seconds

class ProxyManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.dead_proxies = set()
        self.domain_cooldowns = {}  # domain -> {proxy_str: cooldown_until_timestamp}
        self.is_refilling = False
        self.last_refill_time = 0
        self.proxy_index = 0
        self.sx_account_index = 0
        self.sx_config = self.load_sx_config()
        self.ensure_seed_proxies()
        self.load_local_pool()

    def load_sx_config(self) -> dict:
        """Loads and merges SX.ORG rotating residential configuration from persistent and base dirs."""
        merged_accounts = {}
        is_active = False
        for target_dir in [BASE_DIR, DATA_DIR]:
            sx_file = os.path.join(target_dir, "sx_config.json")
            if os.path.exists(sx_file):
                try:
                    with open(sx_file, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if cfg.get("active"):
                            is_active = True
                        if "accounts" in cfg and isinstance(cfg["accounts"], list):
                            for a in cfg["accounts"]:
                                k = a.get("api_key")
                                if k:
                                    merged_accounts[k] = a
                        elif cfg.get("api_key"):
                            merged_accounts[cfg["api_key"]] = cfg
                except Exception:
                    pass
        if merged_accounts:
            cfg = {"active": is_active, "accounts": list(merged_accounts.values())}
            self.save_sx_config(cfg)
            return cfg
        return None

    def save_sx_config(self, cfg: dict):
        """Saves SX.ORG rotating residential configuration to persistent and local storage."""
        for target_dir in [DATA_DIR, BASE_DIR]:
            try:
                sx_file = os.path.join(target_dir, "sx_config.json")
                with open(sx_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
            except Exception:
                pass
        self.sx_config = cfg

    def get_active_sx_accounts(self) -> list:
        """Returns list of active SX.ORG accounts that have positive data balance."""
        if not self.sx_config:
            return []
        accs = []
        if "accounts" in self.sx_config and isinstance(self.sx_config["accounts"], list):
            accs = [a for a in self.sx_config["accounts"] if a.get("active") and a.get("proxy_host")]
        elif self.sx_config.get("active") and self.sx_config.get("proxy_host"):
            accs = [self.sx_config]
        valid_with_data = [a for a in accs if a.get("balance_traffic", 0) > 10240]
        return valid_with_data

    def is_sx_active(self) -> bool:
        """Returns True if at least one SX.ORG rotating residential account is enabled."""
        return len(self.get_active_sx_accounts()) > 0

    def setup_sx_from_key(self, api_key: str) -> dict:
        """Fetches active proxy port and balance from SX.ORG and saves/appends to multi-account pool."""
        api_key = api_key.strip()
        try:
            bal_url = f"https://api.sx.org/v2/user/balance?apiKey={api_key}"
            r_bal = requests.get(bal_url, timeout=12)
            bal_data = r_bal.json()
            if not bal_data.get("success"):
                return {"ok": False, "error": bal_data.get("message", "Invalid API key or balance request failed")}

            ports_url = f"https://api.sx.org/v2/proxy/ports?apiKey={api_key}"
            r_ports = requests.get(ports_url, timeout=12)
            ports_data = r_ports.json()
            if not ports_data.get("success"):
                return {"ok": False, "error": ports_data.get("message", "Could not fetch proxy ports")}

            proxies_list = ports_data.get("message", {}).get("proxies", [])
            if not proxies_list:
                # Automatically create an Indian residential/mobile port via SX.ORG API
                create_url = f"https://api.sx.org/v2/proxy/create-port?apiKey={api_key}"
                try:
                    r_create = requests.post(create_url, json={"country_code": "IN", "type_id": 2, "proxy_type_id": 2}, timeout=15)
                    c_data = r_create.json()
                    if c_data.get("success") and c_data.get("data"):
                        proxies_list = [c_data["data"]]
                except Exception:
                    pass

                if not proxies_list:
                    try:
                        r_ports2 = requests.get(ports_url, timeout=12)
                        proxies_list = r_ports2.json().get("message", {}).get("proxies", [])
                    except Exception:
                        pass

                if not proxies_list:
                    return {"ok": False, "error": "No active proxy ports found on SX.ORG. Auto-port creation failed."}

            p_info = proxies_list[0]
            raw_login = p_info.get("login", "")
            if "session-" in raw_login:
                base_login = re.sub(r"session-[a-zA-Z0-9]+", "session-{session_id}", raw_login)
            else:
                base_login = f"{raw_login}-session-{{session_id}}"

            new_acc = {
                "api_key": api_key,
                "active": True,
                "port_id": p_info.get("id"),
                "proxy_host": p_info.get("proxy", "62.112.8.26:9999"),
                "login_template": base_login,
                "password": p_info.get("password", ""),
                "country": p_info.get("countryCode", "IN"),
                "balance_traffic": bal_data.get("all_available_traffic", 0),
                "updated_at": int(time.time())
            }

            if not self.sx_config or not isinstance(self.sx_config, dict):
                self.sx_config = {"active": True, "accounts": []}
            if "accounts" not in self.sx_config or not isinstance(self.sx_config["accounts"], list):
                existing = []
                if self.sx_config.get("api_key"):
                    existing.append(dict(self.sx_config))
                self.sx_config = {"active": True, "accounts": existing}

            existing_idx = -1
            for idx, a in enumerate(self.sx_config["accounts"]):
                if a.get("api_key") == api_key:
                    existing_idx = idx
                    break

            if existing_idx >= 0:
                self.sx_config["accounts"][existing_idx] = new_acc
            else:
                self.sx_config["accounts"].append(new_acc)

            self.sx_config["active"] = True
            self.save_sx_config(self.sx_config)

            # Auto-purge any expired 0 MB trial accounts
            purged = self.purge_expired_sx_accounts()
            active_accs = [a for a in self.sx_config.get("accounts", []) if a.get("balance_traffic", 0) > 10240]
            total_traffic = sum(a.get("balance_traffic", 0) for a in active_accs)
            logger.info(f"SX.ORG Account {api_key[:6]}... added/updated. Active accounts: {len(active_accs)}, total data: {total_traffic} bytes, purged: {len(purged)}.")
            return {
                "ok": True,
                "account": new_acc,
                "total_accounts": len(active_accs),
                "total_traffic": total_traffic,
                "purged_accounts": len(purged)
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def purge_expired_sx_accounts(self) -> list:
        """
        Scans all configured SX.ORG accounts and automatically purges/deletes any
        accounts whose 1-day trial expired or balance is exhausted (<= 10 KB).
        Saves updated configuration. Returns list of purged API keys.
        """
        if not self.sx_config or not isinstance(self.sx_config, dict):
            return []

        accounts = self.sx_config.get("accounts", [])
        if not isinstance(accounts, list):
            return []

        remaining = []
        purged = []

        for acc in accounts:
            key = acc.get("api_key", "")
            if not key:
                continue
            bal = acc.get("balance_traffic", 0)
            try:
                r = requests.get(f"https://api.sx.org/v2/user/balance?apiKey={key}", timeout=5)
                data = r.json() if r.status_code == 200 else {}
                if data.get("success"):
                    bal = data.get("all_available_traffic", bal)
                    acc["balance_traffic"] = bal
                else:
                    bal = 0
            except Exception:
                pass

            if bal > 10240:
                remaining.append(acc)
            else:
                purged.append(key)
                logger.info(f"Purging expired/exhausted SX account: {key[:6]}... (balance: {bal} bytes)")

        if purged:
            self.sx_config["accounts"] = remaining
            self.sx_config["active"] = len(remaining) > 0
            self.save_sx_config(self.sx_config)

        return purged

    def get_sx_status(self) -> str:
        """Returns formatted status of all active SX.ORG connections with combined traffic total."""
        purged = self.purge_expired_sx_accounts()
        all_accounts = []
        if self.sx_config:
            if "accounts" in self.sx_config and isinstance(self.sx_config["accounts"], list):
                all_accounts = [a for a in self.sx_config["accounts"] if a.get("active") and a.get("proxy_host")]
            elif self.sx_config.get("active") and self.sx_config.get("proxy_host"):
                all_accounts = [self.sx_config]

        if not all_accounts:
            return "❌ <b>SX.ORG Proxy Pool:</b> Not configured / no active accounts (using local pool)."

        lines = ["🌐 <b>SX.ORG Multi-Account Proxy Pool:</b> " + ("ACTIVE ✅" if self.is_sx_active() else "EXHAUSTED ⚠️ (Using Local Pool)") + "\n"]
        total_bytes = 0

        for i, a in enumerate(all_accounts, 1):
            key = a.get("api_key", "")
            key_disp = f"{key[:6]}...{key[-4:]}" if len(key) >= 10 else key
            bal = a.get("balance_traffic", 0)
            total_bytes += bal
            a_mb = round(bal / (1024 * 1024), 2)
            lines.append(f"• <b>Account #{i}:</b> <code>{key_disp}</code> ➔ <b>{a_mb} MB</b>")

        tot_mb = round(total_bytes / (1024 * 1024), 2)
        tot_gb = round(total_bytes / (1024 * 1024 * 1024), 2)
        approx_accounts = int(total_bytes / (25 * 1024))

        lines.append(f"\n📊 <b>Total Combined Data:</b> <code>{tot_mb} MB (~{tot_gb} GB)</code>")
        lines.append(f"👥 <b>Active Accounts Linked:</b> <code>{len(all_accounts)}</code>")
        lines.append(f"⚡ <b>Estimated Capacity:</b> <code>~{approx_accounts:,} accounts</code>")
        if purged:
            lines.append(f"🗑️ <i>Auto-purged {len(purged)} expired trial account(s).</i>")
        if total_bytes > 10240:
            lines.append("🔄 <b>Rotation Mode:</b> <i>Round-robin across active accounts with Indian IP stickiness!</i>")
        else:
            lines.append("⚠️ <i>All SX keys are exhausted (0 MB). Bot is automatically using high-speed local proxies! Add new key with /sxkey &lt;key&gt; to reload.</i>")

        return "\n".join(lines)

    @staticmethod
    def is_auth_proxy(proxy_str: str) -> bool:
        """Returns True if the proxy is an authenticated/premium proxy (e.g. Webshare or SX.ORG)."""
        if not proxy_str or proxy_str == "Direct":
            return False
        return "@" in proxy_str or "wuqayqgc" in proxy_str or "pool-res" in proxy_str or "62.112.8.26" in proxy_str

    SEED_AUTH_PROXIES = [
        "wuqayqgc:g092ukrotff8@31.59.20.176:6754",
        "wuqayqgc:g092ukrotff8@45.38.107.97:6014",
        "wuqayqgc:g092ukrotff8@64.137.96.74:6641",
        "wuqayqgc:g092ukrotff8@198.23.243.226:6361",
        "wuqayqgc:g092ukrotff8@38.154.185.97:6370",
        "wuqayqgc:g092ukrotff8@84.247.60.125:6095",
        "wuqayqgc:g092ukrotff8@142.111.67.146:5611",
        "wuqayqgc:g092ukrotff8@191.96.254.138:6185",
    ]

    def ensure_seed_proxies(self):
        """Ensures DATA_DIR/working_proxies.txt has working seed proxies from repository."""
        repo_files = [
            os.path.join(BASE_DIR, "working_proxies.txt"),
            "/app/working_proxies.txt",
            "/home/piyush/raxi4-bot/working_proxies.txt",
            "/home/piyush/Desktop/working_proxies.txt",
            "/home/piyush/Downloads/Telegram Desktop/working_proxies.txt"
        ]
        existing = set()
        if os.path.exists(PROXIES_FILE):
            try:
                with open(PROXIES_FILE, "r", encoding="utf-8") as f:
                    existing = {l.strip() for l in f if l.strip() and not l.startswith("#")}
            except Exception:
                pass

        added = 0
        # Always seed high-speed auth proxies
        for sp in self.SEED_AUTH_PROXIES:
            if sp not in existing:
                existing.add(sp)
                added += 1

        for rf in repo_files:
            if os.path.exists(rf) and os.path.abspath(rf) != os.path.abspath(PROXIES_FILE):
                try:
                    with open(rf, "r", encoding="utf-8") as f:
                        for line in f:
                            p = line.strip()
                            if p and not p.startswith("#") and p not in existing:
                                existing.add(p)
                                added += 1
                except Exception:
                    pass
        if added > 0:
            logger.info(f"Seeded {added} proxies from repository files into {PROXIES_FILE}")
            self.save_pool(list(existing))

    def normalize_domain(self, domain_or_url: str) -> str:
        """Normalizes any domain or URL to a clean lowercase identifier (e.g. raxi, dmfirst, 51game, bigmumbai)."""
        if not domain_or_url:
            return "general"
        d = domain_or_url.strip().lower()
        if "://" in d:
            try:
                d = urllib.parse.urlparse(d).netloc.lower()
            except Exception:
                pass
        d = re.sub(r"^www\.", "", d)
        d = d.split(":")[0]  # remove port if any
        for fam in ["raxi", "dmfirst", "51game", "goagame", "maanwin", "bigmumbai", "tiranga", "bdg", "daman"]:
            if fam in d:
                return fam
        return d or "general"

    def sync_files_to_alt_dirs(self):
        """Syncs working_proxies.txt and used_proxies.txt across Desktop & Telegram Desktop."""
        for d in ALT_DIRS:
            if os.path.exists(d) and os.path.abspath(d) != os.path.abspath(BASE_DIR):
                try:
                    if os.path.exists(PROXIES_FILE):
                        shutil.copy2(PROXIES_FILE, os.path.join(d, "working_proxies.txt"))
                    if os.path.exists(USED_PROXIES_FILE):
                        shutil.copy2(USED_PROXIES_FILE, os.path.join(d, "used_proxies.txt"))
                except Exception:
                    pass

    def get_used_proxies(self, domain: str = None) -> set:
        """
        Returns set of proxies burnt for the given domain.
        If domain is specified, ONLY returns proxies used on THAT website!
        A proxy used on raxi4 is STILL 100% ELIGIBLE for bigmumbai or other sites.
        """
        target_domain = self.normalize_domain(domain) if domain else None
        used = set()
        if os.path.exists(USED_PROXIES_FILE):
            try:
                with open(USED_PROXIES_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "|" in line:
                            p_str, p_dom = line.split("|", 1)
                            p_str = p_str.strip()
                            p_dom = self.normalize_domain(p_dom)
                            if target_domain is None or p_dom == target_domain or p_dom == "all":
                                used.add(p_str)
                        else:
                            # Legacy record without pipe
                            if target_domain is None or target_domain in ("general", "raxi4.com"):
                                used.add(line)
            except Exception:
                pass
        return used

    def remove_proxy_from_pool(self, proxy_str: str):
        """Immediately removes dead or burned proxy from working_proxies.txt atomically."""
        if not proxy_str or proxy_str == "Direct":
            return
        with self.lock:
            try:
                if os.path.exists(PROXIES_FILE):
                    with open(PROXIES_FILE, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip() and l.strip() != proxy_str]
                    tmp = PROXIES_FILE + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        for p in lines:
                            f.write(f"{p}\n")
                    os.replace(tmp, PROXIES_FILE)
            except Exception:
                pass
        self.sync_files_to_alt_dirs()

    def mark_proxy_used(self, proxy_str: str, domain: str = None):
        """
        Records proxy usage in used_proxies.txt for audit/history.
        NEVER deletes or burns proxies from the working pool!
        """
        if not proxy_str or proxy_str == "Direct" or "pool-res" in proxy_str or "62.112.8.26" in proxy_str:
            return
        dom = self.normalize_domain(domain) if domain else "general"
        record = f"{proxy_str}|{dom}\n"
        try:
            with open(USED_PROXIES_FILE, "a", encoding="utf-8") as f:
                f.write(record)
        except Exception:
            pass
        self.sync_files_to_alt_dirs()

    def mark_proxy_cooldown(self, proxy_str: str, domain: str = None, duration: int = 600):
        """
        Temporarily pauses a proxy for a specific domain (e.g. Code 114 IP forbidden).
        Automatically restores after duration seconds without permanently destroying the proxy.
        """
        if not proxy_str or proxy_str == "Direct" or "pool-res" in proxy_str or "62.112.8.26" in proxy_str:
            return
        dom = self.normalize_domain(domain) if domain else "general"
        with self.lock:
            if dom not in self.domain_cooldowns:
                self.domain_cooldowns[dom] = {}
            self.domain_cooldowns[dom][proxy_str] = time.time() + duration
            logger.info(f"Proxy {proxy_str} entered {duration}s cooldown for domain '{dom}'.")

    def mark_proxy_dead(self, proxy_str: str):
        """
        Marks dead unauthenticated public proxy.
        For auth proxies (e.g. Webshare, SX.ORG), applies a brief 60s cooldown instead of destroying!
        """
        if not proxy_str or proxy_str == "Direct" or "pool-res" in proxy_str or "62.112.8.26" in proxy_str:
            return
        if self.is_auth_proxy(proxy_str):
            with self.lock:
                now = time.time()
                for dom in ["general", "all", "raxi"]:
                    if dom not in self.domain_cooldowns:
                        self.domain_cooldowns[dom] = {}
                    self.domain_cooldowns[dom][proxy_str] = now + 60
            return
        with self.lock:
            self.dead_proxies.add(proxy_str)
        self.remove_proxy_from_pool(proxy_str)

    def load_local_pool(self) -> list:
        """Reads current pool of working proxies from file with auto-seeding."""
        if not os.path.exists(PROXIES_FILE):
            self.ensure_seed_proxies()
        try:
            with open(PROXIES_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                if len(lines) < POOL_MIN_THRESHOLD:
                    self.ensure_seed_proxies()
                    with open(PROXIES_FILE, "r", encoding="utf-8") as f2:
                        lines = [l.strip() for l in f2 if l.strip() and not l.startswith("#")]
                return lines
        except Exception:
            return []

    def save_pool(self, proxies_list: list):
        """Atomically saves verified working proxies to file and syncs."""
        unique_proxies = []
        seen = set()
        # Ensure auth proxies come first
        auth_p = [p for p in proxies_list if self.is_auth_proxy(p)]
        pub_p = [p for p in proxies_list if not self.is_auth_proxy(p)]
        for p in (auth_p + pub_p):
            if p not in seen:
                seen.add(p)
                unique_proxies.append(p)
        try:
            tmp = PROXIES_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                for p in unique_proxies:
                    f.write(f"{p}\n")
            os.replace(tmp, PROXIES_FILE)
        except Exception as e:
            logger.error(f"Error saving proxies: {e}")
        self.sync_files_to_alt_dirs()

    def get_available_count(self, domain: str = None) -> int:
        """Returns how many non-dead, non-cooldown, non-used proxies are ready for the specified domain."""
        if self.is_sx_active():
            return 999  # Unlimited rotating residential pool!
        dom = self.normalize_domain(domain) if domain else "general"
        now = time.time()
        pool = self.load_local_pool()
        with self.lock:
            active_cooldowns = set()
            for d in [dom, "all", "general"]:
                if d in self.domain_cooldowns:
                    for p, until in list(self.domain_cooldowns[d].items()):
                        if until > now:
                            active_cooldowns.add(p)
                        else:
                            self.domain_cooldowns[d].pop(p, None)
        used_for_domain = self.get_used_proxies(domain)
        available = [p for p in pool if p not in active_cooldowns and p not in self.dead_proxies and p not in used_for_domain]
        return len(available)

    def get_earliest_cooldown_expiry(self, domain: str = None) -> float:
        """Returns seconds until the earliest proxy cooldown expires for the domain (capped at 30s)."""
        if self.is_sx_active():
            return 0.0
        dom = self.normalize_domain(domain) if domain else "general"
        now = time.time()
        earliest = float("inf")
        with self.lock:
            for d in [dom, "all", "general"]:
                if d in self.domain_cooldowns:
                    for p, until in self.domain_cooldowns[d].items():
                        rem = until - now
                        if 0 < rem <= 300 and until < earliest:
                            earliest = until
        if earliest == float("inf"):
            return 15.0
        return max(5.0, min(30.0, earliest - now))

    def get_next_proxy(self, exclude=None, domain: str = None, session_id: str = None) -> str:
        """
        Returns the next available, healthy working proxy.
        If SX.ORG rotating residential is active, returns dynamic session-based proxy with fresh Indian IP.
        Otherwise falls back to balanced round-robin rotation.
        """
        accounts = self.get_active_sx_accounts()
        if accounts:
            with self.lock:
                acc = accounts[self.sx_account_index % len(accounts)]
                self.sx_account_index = (self.sx_account_index + 1) % len(accounts)
            sess = session_id or secrets.token_hex(6)
            template = acc.get("login_template", "")
            if "{session_id}" in template:
                login = template.replace("{session_id}", sess)
            else:
                login = f"{template}-session-{sess}"
            pwd = acc.get("password", "")
            host = acc.get("proxy_host", "62.112.8.26:9999")
            return f"{login}:{pwd}@{host}"

        dom = self.normalize_domain(domain) if domain else "general"
        now = time.time()

        pool = self.load_local_pool()
        if len(pool) < POOL_MIN_THRESHOLD:
            self.ensure_seed_proxies()
            pool = self.load_local_pool()

        # Clean expired cooldowns
        with self.lock:
            active_cooldowns = set()
            for d in [dom, "all", "general"]:
                if d in self.domain_cooldowns:
                    for p, until in list(self.domain_cooldowns[d].items()):
                        if until > now:
                            active_cooldowns.add(p)
                        else:
                            self.domain_cooldowns[d].pop(p, None)

        used_for_domain = self.get_used_proxies(domain)

        ex = set(self.dead_proxies)
        ex.update(active_cooldowns)
        ex.update(used_for_domain)
        if exclude:
            ex.update(exclude)

        available = [p for p in pool if p not in ex]

        # Trigger gentle refill only if available is low and last refill was > 15m ago
        if len(available) < POOL_MIN_THRESHOLD and not self.is_refilling and (now - self.last_refill_time > 900):
            threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()

        if not available:
            # If no proxies available, trigger fast refill and do NOT return burned proxies
            if not self.is_refilling:
                threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET, "force": True}, daemon=True).start()
            return None

        # Interleave auth and verified public proxies for balanced rotation
        auth_avail = [p for p in available if self.is_auth_proxy(p)]
        pub_avail = [p for p in available if not self.is_auth_proxy(p)]

        ordered = []
        ai, pi = 0, 0
        while ai < len(auth_avail) or pi < len(pub_avail):
            if ai < len(auth_avail):
                ordered.append(auth_avail[ai])
                ai += 1
            if pi < len(pub_avail):
                ordered.append(pub_avail[pi])
                pi += 1

        with self.lock:
            self.proxy_index = (self.proxy_index + 1) % len(ordered)
            return ordered[self.proxy_index]

    def test_single_proxy(self, proxy_str: str) -> bool:
        """
        Verifies whether proxy can successfully connect via HTTPS.
        Auth proxies (Webshare) are inherently verified and never dropped.
        """
        if not proxy_str or proxy_str == "Direct":
            return False
        if self.is_auth_proxy(proxy_str):
            return True

        if "@" in proxy_str:
            px_url = f"http://{proxy_str}"
        elif proxy_str.count(":") == 3:
            parts = proxy_str.split(":")
            px_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        else:
            px_url = f"http://{proxy_str}"

        proxies = {
            "http": px_url,
            "https": px_url
        }

        try:
            r = requests.get(
                "https://api.ipify.org?format=json",
                proxies=proxies,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
            )
            if r.status_code == 200:
                return True
        except Exception:
            pass
        return False

    def scrape_candidates(self) -> set:
        """Scrapes fresh candidate proxies gently with bounded concurrency to fit safely in 150MB RAM."""
        candidates = set()

        def fetch_url(url):
            try:
                r = requests.get(url, timeout=3.5, headers={"User-Agent": "Mozilla/5.0"})
                return set(re.findall(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}", r.text))
            except Exception:
                return set()

        # Shuffle sources and take only 15 sources per cycle to avoid high memory spikes
        src_subset = list(SOURCES)
        random.shuffle(src_subset)
        src_subset = src_subset[:15]

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            for found in executor.map(fetch_url, src_subset):
                candidates.update(found)
                if len(candidates) >= 1500:
                    break

        # 2. Also incorporate local candidate sources and custom proxies
        local_candidate_files = [
            os.path.join(BASE_DIR, "fresh_raw_proxies.txt"),
            "/app/fresh_raw_proxies.txt",
            "/home/piyush/raxi4-bot/fresh_raw_proxies.txt",
            "/home/piyush/Desktop/fresh_raw_proxies.txt",
            "/home/piyush/Webshare 10 proxies.txt",
            "/home/piyush/gmail-bot/custom_proxies.txt"
        ]
        for lf in local_candidate_files:
            if os.path.exists(lf):
                try:
                    with open(lf, "r", encoding="utf-8") as f:
                        for line in f:
                            p = line.strip()
                            if p and not p.startswith("#"):
                                if p.count(":") == 3:
                                    parts = p.split(":")
                                    candidates.add(f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
                                else:
                                    m = re.findall(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}", p)
                                    candidates.update(m)
                            if len(candidates) >= 2000:
                                break
                except Exception:
                    pass
            if len(candidates) >= 2000:
                break

        fresh_candidates = {p for p in candidates if p not in self.dead_proxies}
        cand_list = list(fresh_candidates)
        if len(cand_list) > 1500:
            random.shuffle(cand_list)
            cand_list = cand_list[:1500]
        logger.info(f"Gathered {len(cand_list)} fresh candidates for memory-safe validation.")
        return set(cand_list)

    def add_custom_proxies(self, raw_proxies: list) -> int:
        """Adds custom user-provided proxies (e.g. from file upload or /addproxy command) directly into pool."""
        existing = set(self.load_local_pool())
        added = 0
        for item in raw_proxies:
            p = item.strip()
            if not p or p.startswith("#"):
                continue
            if p.count(":") == 3:
                parts = p.split(":")
                p = f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            if p not in existing:
                existing.add(p)
                added += 1
        if added > 0:
            self.save_pool(list(existing))
            logger.info(f"Added {added} custom proxies into pool. Total: {len(existing)}")
        return added

    def refill_proxies(self, target_count=POOL_TARGET, max_workers=20, force=False):
        """
        Scrapes candidates and validates them fast with 20 workers (well within 150MB RAM limit).
        """
        import gc
        now = time.time()
        with self.lock:
            if self.is_refilling:
                return
            if not force and (now - self.last_refill_time < 300):
                return
            self.is_refilling = True

        try:
            logger.info(f"Starting proxy pool refill (Target: {target_count}, Force={force})...")
            existing_pool = self.load_local_pool()
            active_existing = [p for p in existing_pool if p not in self.dead_proxies]

            needed = target_count - len(active_existing)
            if needed <= 0 and not force:
                logger.info(f"Pool already full and healthy ({len(active_existing)} >= {target_count}). No refill needed.")
                return

            candidates = list(self.scrape_candidates())
            if not candidates:
                logger.warning("No fresh candidates found from scraper sources.")
                return

            random.shuffle(candidates)
            new_verified = []
            active_set = set(active_existing)

            # Test in streaming batches of 35 candidates
            batch_size = 35
            max_test_candidates = min(len(candidates), 600)
            for i in range(0, max_test_candidates, batch_size):
                if len(active_existing) + len(new_verified) >= target_count:
                    break
                batch = candidates[i:i + batch_size]
                candidates_to_test = [p for p in batch if p not in active_set and p not in new_verified]

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(self.test_single_proxy, p): p for p in candidates_to_test}
                    for f in concurrent.futures.as_completed(futures):
                        p = futures[f]
                        try:
                            if f.result():
                                new_verified.append(p)
                                self.save_pool(active_existing + new_verified)
                                if len(active_existing) + len(new_verified) >= target_count:
                                    break
                        except Exception:
                            pass
                gc.collect()

            combined = active_existing + new_verified
            self.save_pool(combined)
            self.last_refill_time = time.time()
            logger.info(f"Refill complete! Added {len(new_verified)} new verified proxies. Total pool: {len(combined)}")

        except Exception as e:
            logger.error(f"Error during proxy refill: {e}")
        finally:
            gc.collect()
            with self.lock:
                self.is_refilling = False

    def health_check_pool(self):
        """
        Runs periodically: Re-tests unauthenticated proxies in pool and purges dead ones.
        ALWAYS preserves authenticated/Webshare proxies!
        """
        logger.info("Running scheduled health check on working proxies pool...")
        pool = self.load_local_pool()

        if not pool:
            self.refill_proxies(target_count=POOL_TARGET)
            return

        verified_still_alive = []
        dead_count = 0

        # Always preserve all auth proxies
        for p in pool:
            if self.is_auth_proxy(p):
                verified_still_alive.append(p)

        public_to_test = [p for p in pool if not self.is_auth_proxy(p)]
        if public_to_test:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = {executor.submit(self.test_single_proxy, p): p for p in public_to_test}
                for f in concurrent.futures.as_completed(futures):
                    p = futures[f]
                    try:
                        if f.result():
                            verified_still_alive.append(p)
                        else:
                            dead_count += 1
                            self.dead_proxies.add(p)
                    except Exception:
                        dead_count += 1
                        self.dead_proxies.add(p)

        self.save_pool(verified_still_alive)
        gc.collect()
        logger.info(f"Health check done: {len(verified_still_alive)} verified alive, {dead_count} dead removed.")

        if len(verified_still_alive) < POOL_MIN_THRESHOLD:
            logger.info(f"Pool size ({len(verified_still_alive)}) is below {POOL_MIN_THRESHOLD}. Triggering gentle refill...")
            self.refill_proxies(target_count=POOL_TARGET)

    def start_background_daemon(self):
        """Launches continuous background monitoring, gentle auto-refill, and health checks."""
        def daemon_loop():
            logger.info(f"Proxy Background Daemon started (Target: {POOL_TARGET}, Min: {POOL_MIN_THRESHOLD}, Health-Check: every {HEALTH_CHECK_INTERVAL // 60}m).")
            # Wait 60s after startup so container boots cleanly and Telegram polling begins without memory pressure
            time.sleep(60)

            last_health_check = time.time()

            while True:
                time.sleep(POLL_INTERVAL)
                try:
                    now = time.time()
                    pool_len = len(self.load_local_pool())

                    # 1. Periodic 60-Minute Health Check
                    if (now - last_health_check >= HEALTH_CHECK_INTERVAL) and not self.is_refilling:
                        self.health_check_pool()
                        last_health_check = time.time()

                    # 2. Gentle Auto-Refill only if pool drops below min threshold AND cooldown passed
                    elif pool_len < POOL_MIN_THRESHOLD and not self.is_refilling and (now - self.last_refill_time > 900):
                        logger.info(f"Pool size ({pool_len}) below threshold ({POOL_MIN_THRESHOLD}). Refilling to {POOL_TARGET}...")
                        self.refill_proxies(target_count=POOL_TARGET)

                except Exception as e:
                    logger.error(f"Daemon error: {e}")

        t = threading.Thread(target=daemon_loop, daemon=True)
        t.start()
        return t

    def get_stats(self, domain: str = None) -> dict:
        """Returns live statistics for admin dashboard with domain isolation details."""
        pool = self.load_local_pool()
        used_site = self.get_used_proxies(domain=domain)
        avail = [p for p in pool if p not in used_site and p not in self.dead_proxies]
        all_used = self.get_used_proxies()
        return {
            "total_pool": len(pool),
            "target": POOL_TARGET,
            "min_threshold": POOL_MIN_THRESHOLD,
            "available": len(avail),
            "used": len(used_site),
            "available_for_domain": len(avail),
            "used_for_domain": len(used_site),
            "total_used_records": len(all_used),
            "dead": len(self.dead_proxies),
            "is_refilling": self.is_refilling,
            "last_refill": self.last_refill_time,
            "domain": self.normalize_domain(domain) if domain else "all"
        }

proxy_manager = ProxyManager()

if __name__ == "__main__":
    print("Testing Proxy Manager with Domain-Isolation and 500 Target...")
    print("Stats for raxi4.com:", proxy_manager.get_stats("raxi4.com"))
    print("Stats for bigmumbai.com:", proxy_manager.get_stats("bigmumbai.com"))
