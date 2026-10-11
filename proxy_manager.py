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
import urllib.parse
import requests
import concurrent.futures
import random
import json
import hashlib
import string

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

# Curated High-Speed HTTPS & HTTP Sources (Curated for low memory & high speed)
SOURCES = [
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
    "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
    "https://raw.githubusercontent.com/proxiesmaster/Free-Proxy-List/main/proxies.txt",
    "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=ipport&format=text",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=2500&country=all&ssl=yes&anonymity=all",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
    "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
    "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
    "https://raw.githubusercontent.com/saisuiu/Lion-proxy/main/http.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/KangProxy/http.txt",
    "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
]

PLATFORM_TEST_URLS = [
    "https://api.raxiqaz.com/api/webapi/Register",
    "https://api.dmfirst9api.com/api/webapi/Captcha",
    "https://api.api51gameapi.com/api/webapi/Captcha"
]
TARGET_CHECK_URL = PLATFORM_TEST_URLS[0]
CONNECT_TIMEOUT = 3.5
READ_TIMEOUT = 4.5

POOL_TARGET = 35        # Target: 35 verified responsive working proxies
POOL_MIN_THRESHOLD = 10  # Trigger gentle refill when pool drops below 10
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
        self.ensure_seed_proxies()
        self.load_local_pool()

    @staticmethod
    def is_auth_proxy(proxy_str: str) -> bool:
        """Returns True if the proxy is an authenticated/premium proxy (e.g. Webshare)."""
        if not proxy_str or proxy_str == "Direct":
            return False
        return "@" in proxy_str or "wuqayqgc" in proxy_str

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
        """Normalizes any domain or URL to a clean lowercase identifier (e.g. raxi4.com, bigmumbai.com)."""
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
        if "raxi" in d:
            return "raxi"
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
        if not proxy_str or proxy_str == "Direct":
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
        if not proxy_str or proxy_str == "Direct":
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
        For auth proxies (e.g. Webshare), applies a brief 60s cooldown instead of destroying!
        """
        if not proxy_str or proxy_str == "Direct":
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
        """Returns how many non-dead, non-cooldown proxies are ready for the specified domain."""
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
        available = [p for p in pool if p not in active_cooldowns and p not in self.dead_proxies]
        return len(available)

    def get_earliest_cooldown_expiry(self, domain: str = None) -> float:
        """Returns seconds until the earliest proxy cooldown expires for the domain."""
        dom = self.normalize_domain(domain) if domain else "general"
        now = time.time()
        earliest = float("inf")
        with self.lock:
            for d in [dom, "all", "general"]:
                if d in self.domain_cooldowns:
                    for p, until in self.domain_cooldowns[d].items():
                        if until > now and until < earliest:
                            earliest = until
        if earliest == float("inf"):
            return 0.0
        return max(0.0, earliest - now)

    def get_next_proxy(self, exclude=None, domain: str = None) -> str:
        """
        Returns the next available, healthy working proxy using priority round-robin rotation.
        Auth proxies (Webshare) are prioritized.
        Skips proxies currently in cooldown for the given domain.
        """
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

        ex = set(self.dead_proxies)
        ex.update(active_cooldowns)
        if exclude:
            ex.update(exclude)

        available = [p for p in pool if p not in ex]

        # Trigger gentle refill only if available is low and last refill was > 15m ago
        if len(available) < POOL_MIN_THRESHOLD and not self.is_refilling and (now - self.last_refill_time > 900):
            threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()

        if not available:
            # Fallback: allow auth proxies whose cooldown has mostly elapsed
            auth_fallback = [p for p in pool if self.is_auth_proxy(p) and p not in self.dead_proxies]
            if auth_fallback:
                available = auth_fallback
            else:
                return None

        # Prioritize auth proxies
        auth_avail = [p for p in available if self.is_auth_proxy(p)]
        pub_avail = [p for p in available if not self.is_auth_proxy(p)]

        ordered = auth_avail + pub_avail
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
        """Scrapes fresh candidate proxies from all public sources and local candidate files in parallel."""
        candidates = set()

        # 1. Scrape from 35+ online public sources concurrently
        def fetch_url(url):
            try:
                r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                return set(re.findall(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}", r.text))
            except Exception:
                return set()

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(SOURCES), 12)) as executor:
            for found in executor.map(fetch_url, SOURCES):
                candidates.update(found)

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
                            if len(candidates) >= 12000:
                                break
                except Exception:
                    pass
            if len(candidates) >= 12000:
                break

        fresh_candidates = {p for p in candidates if p not in self.dead_proxies}
        cand_list = list(fresh_candidates)
        if len(cand_list) > 10000:
            random.shuffle(cand_list)
            cand_list = cand_list[:10000]
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

    def refill_proxies(self, target_count=POOL_TARGET, max_workers=6, force=False):
        """
        Scrapes candidates and validates them gently with max workers to preserve CPU.
        """
        import gc
        now = time.time()
        with self.lock:
            if self.is_refilling:
                return
            if not force and (now - self.last_refill_time < 600):
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

            # Test in streaming batches of 50 candidates, dynamically scaled for target_count
            batch_size = 50
            max_test_candidates = min(len(candidates), max(500, target_count * 15))
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
        import gc
        logger.info(f"Running scheduled health check on working proxies pool...")
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
            # Immediate initial refill only if pool is strictly below min threshold
            if len(self.load_local_pool()) < POOL_MIN_THRESHOLD:
                threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()

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
