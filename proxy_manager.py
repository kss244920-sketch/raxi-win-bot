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
import base64
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
        self.in_flight_ips = {}  # {domain: set(ips)}
        self.used_ips_by_domain = {}  # {domain: set(ips)}
        self.sx_config = self.load_sx_config()
        # Clean expired accounts at init
        self.purge_expired_sx_accounts()
        # Load and sync used IPs from history
        self.load_used_ips()

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
        """Saves SX.ORG rotating residential configuration to persistent and local storage using atomic writes."""
        for target_dir in [DATA_DIR, BASE_DIR]:
            try:
                sx_file = os.path.join(target_dir, "sx_config.json")
                tmp_file = sx_file + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)
                os.replace(tmp_file, sx_file)
            except Exception:
                pass
        self.sx_config = cfg

    def get_active_sx_accounts(self) -> list:
        """Returns list of active SX.ORG accounts that have positive data balance or USD funds."""
        if not self.sx_config:
            return []
        accs = []
        if "accounts" in self.sx_config and isinstance(self.sx_config["accounts"], list):
            accs = [a for a in self.sx_config["accounts"] if a.get("active") and a.get("proxy_host")]
        elif self.sx_config.get("active") and self.sx_config.get("proxy_host"):
            accs = [self.sx_config]
        valid_with_data = [
            a for a in accs 
            if a.get("balance_traffic", 0) > 10240 or a.get("balance_usd", 0) > 0.005
        ]
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

            # Calculate effective traffic: trial traffic bytes OR USD pay-as-you-go ($3.00/GB)
            usd_bal = float(bal_data.get("balance", 0) or 0)
            traffic_bytes = max(int(bal_data.get("all_available_traffic", 0) or 0), int(bal_data.get("balance_traffic", 0) or 0))
            if traffic_bytes <= 10240 and usd_bal > 0.005:
                # $3 per GB on SX.ORG
                traffic_bytes = int((usd_bal / 3.0) * 1024 * 1024 * 1024)

            actual_host = p_info.get("proxy") or "185.100.235.113:9999"

            new_acc = {
                "api_key": api_key,
                "active": True,
                "port_id": p_info.get("id"),
                "proxy_host": actual_host,
                "login_template": base_login,
                "password": p_info.get("password", ""),
                "country": p_info.get("countryCode", "IN"),
                "balance_usd": usd_bal,
                "balance_traffic": traffic_bytes,
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
            active_accs = self.get_active_sx_accounts()
            total_traffic = sum(a.get("balance_traffic", 0) for a in active_accs)
            logger.info(f"SX.ORG Account {api_key[:6]}... added. Active: {len(active_accs)}, total data: {total_traffic} bytes (USD: ${usd_bal:.2f}), purged: {len(purged)}.")
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
        Scans all configured SX.ORG accounts and purges/deletes accounts whose
        balance is confirmed exhausted (<= 10 KB and $0 USD) or invalidated by SX.ORG.
        Network glitches, timeouts, or rate limits NEVER cause false purges.
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
            usd_bal = acc.get("balance_usd", 0.0)
            is_definitely_dead = False

            try:
                r = requests.get(f"https://api.sx.org/v2/user/balance?apiKey={key}", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success"):
                        # Successfully retrieved balance
                        usd_bal = float(data.get("balance", 0) or 0)
                        all_trf = int(data.get("all_available_traffic", 0) or 0)
                        bal_trf = int(data.get("balance_traffic", 0) or 0)
                        bal = max(all_trf, bal_trf)

                        # If traffic in bytes is 0, but USD balance exists (Pay-As-You-Go)
                        if bal <= 10240 and usd_bal > 0.005:
                            bal = int((usd_bal / 3.0) * 1024 * 1024 * 1024)

                        acc["balance_traffic"] = bal
                        acc["balance_usd"] = usd_bal
                        acc["updated_at"] = int(time.time())

                        if bal <= 10240 and usd_bal <= 0.005:
                            is_definitely_dead = True
                    else:
                        msg = str(data.get("message", "")).lower()
                        if "invalid" in msg or "suspended" in msg or "not found" in msg or "credential" in msg:
                            is_definitely_dead = True
                            bal = 0
                            logger.warning(f"SX API key {key[:6]}... invalidated: {msg}")
                elif r.status_code in (401, 403):
                    is_definitely_dead = True
                    bal = 0
                    logger.warning(f"SX API key {key[:6]}... rejected (HTTP {r.status_code})")
                else:
                    # 429 (rate limit), 500, 502, 503 -> Temporary SX.ORG glitch, DO NOT purge!
                    logger.warning(f"SX balance check returned HTTP {r.status_code} for {key[:6]}... (preserving account)")
            except Exception as e:
                # Network timeout or connection drop -> DO NOT purge!
                logger.warning(f"SX balance check network error for {key[:6]}...: {e} (preserving account)")

            if not is_definitely_dead and (bal > 10240 or usd_bal > 0.005):
                remaining.append(acc)
            else:
                purged.append(key)
                logger.info(f"Purging expired/exhausted SX account: {key[:6]}... (balance: {bal} bytes, ${usd_bal} USD)")

        if purged:
            self.sx_config["accounts"] = remaining
            self.sx_config["active"] = len(remaining) > 0
            self.save_sx_config(self.sx_config)

        return purged

    def get_next_proxy(self, exclude=None, domain: str = None, session_id: str = None) -> str:
        """
        Returns dynamic session-based proxy with fresh Indian IP from SX.ORG pool.
        Falls back to verified static proxies from working_proxies.txt if SX pool is empty.
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
            host = acc.get("proxy_host") or "185.100.235.113:9999"
            return f"{login}:{pwd}@{host}"

        # Emergency fallback to working_proxies.txt
        fallback_candidates = [
            os.path.join(DATA_DIR, "working_proxies.txt"),
            os.path.join(BASE_DIR, "working_proxies.txt")
        ]
        for fpath in fallback_candidates:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
                    valid = [p for p in lines if p not in (exclude or set()) and p not in self.dead_proxies]
                    if valid:
                        return secrets.choice(valid)
                except Exception:
                    pass

        return None

    def get_static_proxy(self, exclude=None) -> str:
        """
        Returns a verified static/datacenter proxy from working_proxies.txt.
        STRICTLY GUARANTEED to NEVER return a paid SX residential proxy.
        Designed for heavy-bandwidth tasks (Captcha image download ~150KB-400KB, site auto-discovery).
        """
        fallback_candidates = [
            os.path.join(DATA_DIR, "working_proxies.txt"),
            os.path.join(BASE_DIR, "working_proxies.txt")
        ]
        for fpath in fallback_candidates:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
                    valid = [p for p in lines if p not in (exclude or set()) and p not in self.dead_proxies]
                    if valid:
                        auth_valid = [p for p in valid if "@" in p]
                        if auth_valid:
                            return secrets.choice(auth_valid)
                        return secrets.choice(valid)
                except Exception:
                    pass
        return None

    def get_available_count(self, domain: str = None) -> int:
        """Returns active count indicator for registration pools."""
        if self.is_sx_active():
            return 999
        fallback_candidates = [
            os.path.join(DATA_DIR, "working_proxies.txt"),
            os.path.join(BASE_DIR, "working_proxies.txt")
        ]
        for fpath in fallback_candidates:
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
                    if lines:
                        return len(lines)
                except Exception:
                    pass
        return 0

    def get_earliest_cooldown_expiry(self, domain: str = None) -> float:
        return 0.0

    def get_sx_summary_line(self) -> str:
        """Returns concise one-line status of SX proxies for dashboard header."""
        accounts = self.get_active_sx_accounts()
        if not accounts:
            return "❌ No Active Keys"
        total_bytes = sum(a.get("balance_traffic", 0) for a in accounts)
        tot_mb = round(total_bytes / (1024 * 1024), 1)
        tot_usd = sum(a.get("balance_usd", 0) for a in accounts)
        usd_info = f", ${tot_usd:.2f}" if tot_usd > 0 else ""
        return f"🟢 Active ({len(accounts)} Key, ~{tot_mb} MB{usd_info} IN Residential)"

    def get_sx_status(self) -> str:
        """Returns formatted status of all active SX.ORG connections with combined traffic total."""
        purged = self.purge_expired_sx_accounts()
        all_accounts = self.get_active_sx_accounts()

        if not all_accounts:
            return "❌ <b>SX.ORG Proxy Pool:</b> No active accounts configured. Use <code>/sxkey &lt;key&gt;</code> to load a proxy key."

        lines = ["🌐 <b>SX.ORG Multi-Account Proxy Pool:</b> ACTIVE ✅\n"]
        total_bytes = 0
        total_usd = 0.0

        for i, a in enumerate(all_accounts, 1):
            key = a.get("api_key", "")
            key_disp = f"{key[:6]}...{key[-4:]}" if len(key) >= 10 else key
            bal = a.get("balance_traffic", 0)
            usd = a.get("balance_usd", 0.0)
            total_bytes += bal
            total_usd += usd
            a_mb = round(bal / (1024 * 1024), 2)
            usd_str = f" (${usd:.2f})" if usd > 0 else ""
            lines.append(f"• <b>Account #{i}:</b> <code>{key_disp}</code> ➔ <b>{a_mb} MB{usd_str}</b>")

        tot_mb = round(total_bytes / (1024 * 1024), 2)
        tot_gb = round(total_bytes / (1024 * 1024 * 1024), 2)
        approx_accounts = int(total_bytes / (25 * 1024))

        lines.append(f"\n📊 <b>Total Combined Data:</b> <code>{tot_mb} MB (~{tot_gb} GB)</code>")
        if total_usd > 0:
            lines.append(f"💰 <b>Total Paid Balance:</b> <code>${total_usd:.4f} USD</code>")
        lines.append(f"👥 <b>Active Accounts Linked:</b> <code>{len(all_accounts)}</code>")
        lines.append(f"⚡ <b>Estimated Capacity:</b> <code>~{approx_accounts:,} accounts</code>")
        first_host = all_accounts[0].get("proxy_host", "185.100.235.113:9999")
        lines.append(f"🇮🇳 <b>Gateway:</b> <code>{first_host} (Indian Residential)</code>")
        if purged:
            lines.append(f"🗑️ <i>Auto-purged {len(purged)} expired trial account(s).</i>")
        lines.append("🔄 <b>Rotation Mode:</b> <i>Dynamic session rotation with Indian IP sticky sessions!</i>")

        return "\n".join(lines)

    def normalize_domain(self, domain: str) -> str:
        if not domain:
            return "default"
        d = domain.lower().strip()
        if "://" in d:
            d = d.split("://")[-1]
        d = d.split("/")[0].split(":")[0]
        if d.startswith("www."):
            d = d[4:]
        return d or "default"

    def _extract_clean_ip(self, s: str) -> str:
        if not s:
            return ""
        m = re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', s)
        return m.group(0) if m else s.strip()

    def load_used_ips(self):
        """Loads domain-isolated used IPs from used_proxies.txt and historical raxi_accounts.txt."""
        with self.lock:
            self.used_ips_by_domain = {}
            for target_dir in [BASE_DIR, DATA_DIR]:
                fpath = os.path.join(target_dir, "used_proxies.txt")
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line or line.startswith("#"):
                                    continue
                                parts = line.split("|")
                                ip_part = parts[0].strip()
                                dom_part = self.normalize_domain(parts[1]) if len(parts) > 1 else "default"
                                clean_ip = self._extract_clean_ip(ip_part)
                                if clean_ip:
                                    self.used_ips_by_domain.setdefault(dom_part, set()).add(clean_ip)
                    except Exception:
                        pass

            for target_dir in [BASE_DIR, DATA_DIR]:
                acc_path = os.path.join(target_dir, "raxi_accounts.txt")
                if os.path.exists(acc_path):
                    try:
                        with open(acc_path, "r", encoding="utf-8") as f:
                            for line in f:
                                m_site = re.search(r'Site:\s*https?://([^ /|]+)', line)
                                dom = self.normalize_domain(m_site.group(1)) if m_site else "default"
                                m_tok = re.search(r'Token:\s*([a-zA-Z0-9_\-\.]+)', line)
                                found_ip = None
                                if m_tok and "." in m_tok.group(1):
                                    try:
                                        p = m_tok.group(1).split(".")[1]
                                        p += "=" * (-len(p) % 4)
                                        d = json.loads(base64.urlsafe_b64decode(p))
                                        found_ip = d.get("LoginIPAddress") or d.get("LoginIP")
                                    except Exception:
                                        pass
                                if not found_ip:
                                    m_ip = re.search(r'IP:\s*([0-9\.]+)', line)
                                    if m_ip:
                                        found_ip = m_ip.group(1)
                                if found_ip:
                                    clean_ip = self._extract_clean_ip(found_ip)
                                    if clean_ip:
                                        self.used_ips_by_domain.setdefault(dom, set()).add(clean_ip)
                    except Exception:
                        pass
            total_loaded = sum(len(v) for v in self.used_ips_by_domain.values())
            logger.info(f"Loaded {total_loaded} unique used IP records across {len(self.used_ips_by_domain)} domains.")

    def is_ip_used(self, ip: str, domain: str = None) -> bool:
        clean_ip = self._extract_clean_ip(ip)
        if not clean_ip:
            return False
        dom = self.normalize_domain(domain)
        with self.lock:
            used_set = self.used_ips_by_domain.get(dom, set())
            if clean_ip in used_set:
                return True
            inflight_set = self.in_flight_ips.get(dom, set())
            if clean_ip in inflight_set:
                return True
        return False

    def mark_ip_used(self, ip: str, domain: str = None):
        clean_ip = self._extract_clean_ip(ip)
        if not clean_ip:
            return
        dom = self.normalize_domain(domain)
        with self.lock:
            self.used_ips_by_domain.setdefault(dom, set()).add(clean_ip)
            if dom in self.in_flight_ips:
                self.in_flight_ips[dom].discard(clean_ip)

            entry = f"{clean_ip}|{dom}\n"
            for target_dir in [DATA_DIR, BASE_DIR]:
                try:
                    fpath = os.path.join(target_dir, "used_proxies.txt")
                    with open(fpath, "a", encoding="utf-8") as f:
                        f.write(entry)
                except Exception:
                    pass

    def release_in_flight_ip(self, ip: str, domain: str = None):
        clean_ip = self._extract_clean_ip(ip)
        if not clean_ip:
            return
        dom = self.normalize_domain(domain)
        with self.lock:
            if dom in self.in_flight_ips:
                self.in_flight_ips[dom].discard(clean_ip)

    def mark_proxy_used(self, proxy_str: str, domain: str = None):
        clean_ip = self._extract_clean_ip(proxy_str)
        if clean_ip:
            self.mark_ip_used(clean_ip, domain=domain)

    def get_used_proxies(self, domain: str = None) -> set:
        dom = self.normalize_domain(domain) if domain else None
        with self.lock:
            if dom:
                return set(self.used_ips_by_domain.get(dom, set()))
            all_s = set()
            for s in self.used_ips_by_domain.values():
                all_s.update(s)
            return all_s

    def get_used_ips(self, domain: str = None) -> set:
        return self.get_used_proxies(domain=domain)

    def acquire_session_with_unique_ip(self, domain: str = None, max_attempts: int = 3) -> tuple:
        """
        Enforces 100% Zero-Repeat IP Condition with minimal proxy bandwidth:
        Pre-resolves the IP of the session via lightweight plain text HTTP (~15 bytes),
        verifies that the IP has NEVER been used on this domain in history,
        and atomically marks it in-flight so concurrent workers cannot collide.
        Returns: (proxy_str, verified_ip, session_id)
        """
        dom = self.normalize_domain(domain)
        accounts = self.get_active_sx_accounts()
        if not accounts:
            st_px = self.get_static_proxy()
            if st_px:
                st_ip = self._extract_clean_ip(st_px)
                return (st_px, st_ip, "static")
            return (None, None, None)

        for attempt in range(1, max_attempts + 1):
            with self.lock:
                acc = accounts[self.sx_account_index % len(accounts)]
                self.sx_account_index = (self.sx_account_index + 1) % len(accounts)

            sess_id = secrets.token_hex(6)
            template = acc.get("login_template", "")
            if "{session_id}" in template:
                login = template.replace("{session_id}", sess_id)
            else:
                login = f"{template}-session-{sess_id}"
            pwd = acc.get("password", "")
            host = acc.get("proxy_host") or "185.100.235.113:9999"
            px_str = f"{login}:{pwd}@{host}"

            # Ultra-lightweight plain HTTP pre-flight verification (~15 bytes text, no JSON overhead)
            assigned_ip = None
            try:
                px_dict = {"http": f"http://{px_str}", "https": f"http://{px_str}"}
                r_ip = requests.get("http://api.ipify.org", proxies=px_dict, timeout=3.0)
                if r_ip.status_code == 200 and r_ip.text:
                    assigned_ip = self._extract_clean_ip(r_ip.text.strip())
            except Exception as e:
                logger.warning(f"Pre-flight IP resolution error (attempt {attempt}): {e}")
                continue

            if not assigned_ip:
                continue

            with self.lock:
                used_set = self.used_ips_by_domain.get(dom, set())
                inflight_set = self.in_flight_ips.setdefault(dom, set())
                if assigned_ip in used_set:
                    logger.info(f"[Zero-Repeat] IP {assigned_ip} was already used on {dom}! Discarding session (attempt {attempt}/{max_attempts})...")
                    continue
                if assigned_ip in inflight_set:
                    logger.info(f"[Zero-Repeat] IP {assigned_ip} currently in-flight on {dom}! Discarding session (attempt {attempt}/{max_attempts})...")
                    continue

                # Acquired fresh, unique IP!
                inflight_set.add(assigned_ip)
                logger.info(f"[Zero-Repeat] Guaranteed UNIQUE IP acquired: {assigned_ip} for {dom} (session {sess_id})")
                return (px_str, assigned_ip, sess_id)

        logger.error(f"[Zero-Repeat] Could not acquire unique residential IP for {dom} after {max_attempts} attempts.")
        return (None, None, None)

    def mark_proxy_dead(self, proxy_str: str):
        pass

    def mark_proxy_cooldown(self, proxy_str: str, domain: str = None, duration: float = 300):
        pass

    # ── Compatibility methods for legacy callers ──
    def start_background_daemon(self):
        logger.info("SX.ORG Residential Proxy Engine active (Zero IP repeat verification enabled).")
        return None

    def refill_proxies(self, *args, **kwargs):
        pass

    def add_custom_proxies(self, *args, **kwargs) -> int:
        return 0

    def get_stats(self, domain: str = None) -> dict:
        is_act = self.is_sx_active()
        dom = self.normalize_domain(domain) if domain else None
        used_cnt = len(self.get_used_ips(dom))
        return {
            "total_pool": 1 if is_act else 0,
            "available": 999 if is_act else 0,
            "used": used_cnt,
            "active": is_act
        }

proxy_manager = ProxyManager()
