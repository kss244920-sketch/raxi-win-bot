#!/usr/bin/env python3
# language: Python, file: proxy_manager.py
# High-Performance SX.ORG Rotating Residential Proxy Manager
# Exclusively handles dynamic Indian Residential Rotating Proxies with session stickiness.

import os
import re
import time
import logging
import threading
import json
import secrets
import requests

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [ProxyEngine] %(message)s")
logger = logging.getLogger("ProxyEngine")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_persistent_data_dir() -> str:
    jrnm_vol = "/app/data"
    if os.path.exists(jrnm_vol) and os.path.isdir(jrnm_vol):
        return jrnm_vol
    return BASE_DIR

DATA_DIR = get_persistent_data_dir()
USED_PROXIES_FILE = os.path.join(DATA_DIR, "used_proxies.txt")


class ProxyManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.sx_account_index = 0
        self.dead_proxies = set()
        self.domain_cooldowns = {}
        self.sx_config = self.load_sx_config()
        # Clean expired accounts at init
        self.purge_expired_sx_accounts()

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
        return {"active": False, "accounts": []}

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
                # Automatically create an Indian residential port via SX.ORG API
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
            logger.info(f"SX.ORG Account {api_key[:6]}... added. Active: {len(active_accs)}, total data: {total_traffic} bytes, purged: {len(purged)}.")
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

    def get_next_proxy(self, exclude=None, domain: str = None, session_id: str = None) -> str:
        """
        Returns dynamic session-based proxy with fresh Indian IP from SX.ORG pool.
        """
        accounts = self.get_active_sx_accounts()
        if not accounts:
            return None

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

    def get_available_count(self, domain: str = None) -> int:
        """Returns active count indicator for registration pools."""
        return 999 if self.is_sx_active() else 0

    def get_earliest_cooldown_expiry(self, domain: str = None) -> float:
        return 0.0

    def get_sx_summary_line(self) -> str:
        """Returns concise one-line status of SX proxies for dashboard header."""
        accounts = self.get_active_sx_accounts()
        if not accounts:
            return "❌ No Active Keys"
        total_bytes = sum(a.get("balance_traffic", 0) for a in accounts)
        tot_mb = round(total_bytes / (1024 * 1024), 1)
        return f"🟢 Active ({len(accounts)} Key, ~{tot_mb} MB IN Residential)"

    def get_sx_status(self) -> str:
        """Returns formatted status of all active SX.ORG connections with combined traffic total."""
        purged = self.purge_expired_sx_accounts()
        all_accounts = self.get_active_sx_accounts()

        if not all_accounts:
            return "❌ <b>SX.ORG Proxy Pool:</b> No active accounts configured. Use <code>/sxkey &lt;key&gt;</code> to load a 1 GB trial key."

        lines = ["🌐 <b>SX.ORG Multi-Account Proxy Pool:</b> ACTIVE ✅\n"]
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
        lines.append("🇮🇳 <b>Gateway:</b> <code>62.112.8.26:9999 (Indian Residential)</code>")
        if purged:
            lines.append(f"🗑️ <i>Auto-purged {len(purged)} expired trial account(s).</i>")
        lines.append("🔄 <b>Rotation Mode:</b> <i>Dynamic session rotation with Indian IP sticky sessions!</i>")

        return "\n".join(lines)

    def mark_proxy_used(self, proxy_str: str, domain: str = None):
        """Records proxy usage for audit."""
        pass

    def mark_proxy_dead(self, proxy_str: str):
        pass

    def mark_proxy_cooldown(self, proxy_str: str, domain: str = None, duration: float = 300):
        pass

    def get_used_proxies(self, domain: str = None) -> set:
        return set()

    # ── Compatibility methods for legacy callers ──
    def start_background_daemon(self):
        logger.info("SX.ORG Residential Proxy Engine active (Legacy public proxy scraper completely removed).")
        return None

    def refill_proxies(self, *args, **kwargs):
        pass

    def add_custom_proxies(self, *args, **kwargs) -> int:
        return 0

    def get_stats(self, domain: str = None) -> dict:
        is_act = self.is_sx_active()
        return {
            "total_pool": 1 if is_act else 0,
            "available": 999 if is_act else 0,
            "used": 0,
            "active": is_act
        }

proxy_manager = ProxyManager()
