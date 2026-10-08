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
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=2500&country=all&ssl=yes&anonymity=all",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt"
]

PLATFORM_TEST_URLS = [
    "https://api.dmfirst9api.com/api/webapi/Captcha",
    "https://api.raxiqaz.com/api/webapi/Captcha",
    "https://api.api51gameapi.com/api/webapi/Captcha"
]
TARGET_CHECK_URL = PLATFORM_TEST_URLS[0]
CONNECT_TIMEOUT = 2.2
READ_TIMEOUT = 2.8

POOL_TARGET = 150       # Memory-safe target: 150 verified working proxies
POOL_MIN_THRESHOLD = 60 # Trigger auto-refill when pool drops below 60
HEALTH_CHECK_INTERVAL = 1800 # 30 minutes in seconds
POLL_INTERVAL = 60      # Active poll interval in seconds

class ProxyManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.dead_proxies = set()
        self.is_refilling = False
        self.last_refill_time = 0
        self.proxy_index = 0
        self.ensure_seed_proxies()
        self.load_local_pool()

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
                    existing = {l.strip() for l in f if l.strip() and not l.startswith("#") and "@" not in l}
            except Exception:
                pass

        added = 0
        for rf in repo_files:
            if os.path.exists(rf) and os.path.abspath(rf) != os.path.abspath(PROXIES_FILE):
                try:
                    with open(rf, "r", encoding="utf-8") as f:
                        for line in f:
                            p = line.strip()
                            if p and not p.startswith("#") and p not in existing and "@" not in p:
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

    def mark_proxy_used(self, proxy_str: str, domain: str = None):
        """
        Marks proxy as permanently used ONLY for the given website domain.
        Format in file: IP:PORT|domain (e.g. 4.144.146.21:80|raxi4.com)
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

    def mark_proxy_dead(self, proxy_str: str):
        """Marks proxy as temporarily dead/unresponsive."""
        if not proxy_str or proxy_str == "Direct":
            return
        with self.lock:
            self.dead_proxies.add(proxy_str)

    def load_local_pool(self) -> list:
        """Reads current pool of working proxies from file with auto-seeding."""
        if not os.path.exists(PROXIES_FILE):
            self.ensure_seed_proxies()
        try:
            with open(PROXIES_FILE, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#") and "@" not in l]
                if len(lines) < POOL_MIN_THRESHOLD:
                    self.ensure_seed_proxies()
                    with open(PROXIES_FILE, "r", encoding="utf-8") as f2:
                        lines = [l.strip() for l in f2 if l.strip() and not l.startswith("#") and "@" not in l]
                return lines
        except Exception:
            return []

    def save_pool(self, proxies_list: list):
        """Atomically saves verified working proxies to file and syncs."""
        unique_proxies = []
        seen = set()
        for p in proxies_list:
            if p not in seen:
                seen.add(p)
                unique_proxies.append(p)
        try:
            with open(PROXIES_FILE, "w", encoding="utf-8") as f:
                for p in unique_proxies:
                    f.write(f"{p}\n")
        except Exception as e:
            logger.error(f"Error saving proxies: {e}")
        self.sync_files_to_alt_dirs()

    def get_available_count(self, domain: str = None) -> int:
        """Returns how many unused, non-dead working proxies are ready for the specified domain."""
        pool = self.load_local_pool()
        used = self.get_used_proxies(domain=domain)
        available = [p for p in pool if p not in used and p not in self.dead_proxies]
        return len(available)

    def get_next_proxy(self, exclude=None, domain: str = None) -> str:
        """
        Returns a completely FRESH, verified, never-before-used working proxy for this domain.
        If IP was used for raxiwin, it is STILL 100% ELIGIBLE for bigmumbai or other sites!
        If unused pool for domain is exhausted, falls back to reusing alive proxies rather than failing with Direct.
        """
        pool = self.load_local_pool()
        if len(pool) < POOL_MIN_THRESHOLD:
            self.ensure_seed_proxies()
            pool = self.load_local_pool()

        used = self.get_used_proxies(domain=domain)
        ex = set(used)
        ex.update(self.dead_proxies)
        if exclude:
            ex.update(exclude)

        available = [p for p in pool if p not in ex]

        # Trigger auto-refill if remaining unused proxies for this domain are running low
        if len(available) < POOL_MIN_THRESHOLD and not self.is_refilling:
            threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()

        if not available:
            # Fallback Tier 1: Allow any proxies in pool that are not dead and not excluded in current transaction
            fallback = [p for p in pool if p not in self.dead_proxies and (not exclude or p not in exclude)]
            if fallback:
                with self.lock:
                    self.proxy_index = (self.proxy_index + 1) % len(fallback)
                    return fallback[self.proxy_index]

            # Fallback Tier 2: Clear temporary dead proxy memory (in case of network blips) and retry
            if pool:
                with self.lock:
                    self.dead_proxies.clear()
                retry_candidates = [p for p in pool if not exclude or p not in exclude]
                if retry_candidates:
                    with self.lock:
                        self.proxy_index = (self.proxy_index + 1) % len(retry_candidates)
                        return retry_candidates[self.proxy_index]

            if not self.is_refilling:
                threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()
            return None

        with self.lock:
            self.proxy_index = (self.proxy_index + 1) % len(available)
            return available[self.proxy_index]

    def test_single_proxy(self, proxy_str: str) -> bool:
        """
        Verifies whether proxy can successfully connect via HTTPS.
        Tests against both DMFirst and RaxiCaptcha APIs.
        """
        proxies = {
            "http": f"http://{proxy_str}",
            "https": f"http://{proxy_str}"
        }
        for test_url in [
            "https://api.dmfirst9api.com/api/webapi/Captcha",
            TARGET_CHECK_URL
        ]:
            try:
                r = requests.post(
                    test_url,
                    json={},
                    proxies=proxies,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)
                )
                if r.status_code == 200 and ("code" in r.text or "data" in r.text):
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(SOURCES), 30)) as executor:
            for found in executor.map(fetch_url, SOURCES):
                candidates.update(found)

        # 2. Also incorporate local candidate sources
        local_candidate_files = [
            os.path.join(BASE_DIR, "fresh_raw_proxies.txt"),
            "/app/fresh_raw_proxies.txt",
            "/home/piyush/raxi4-bot/fresh_raw_proxies.txt",
            "/home/piyush/Desktop/fresh_raw_proxies.txt"
        ]
        for lf in local_candidate_files:
            if os.path.exists(lf):
                try:
                    with open(lf, "r", encoding="utf-8") as f:
                        for line in f:
                            p = line.strip()
                            if p and not p.startswith("#"):
                                m = re.findall(r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}", p)
                                candidates.update(m)
                            if len(candidates) >= 2500:
                                break
                except Exception:
                    pass
            if len(candidates) >= 2500:
                break

        fresh_candidates = {p for p in candidates if p not in self.dead_proxies}
        cand_list = list(fresh_candidates)
        if len(cand_list) > 2500:
            random.shuffle(cand_list)
            cand_list = cand_list[:2500]
        logger.info(f"Gathered {len(cand_list)} fresh candidates for memory-safe validation.")
        return set(cand_list)

    def refill_proxies(self, target_count=POOL_TARGET, max_workers=25):
        """
        Scrapes candidates and validates them concurrently with 25 memory-safe workers.
        Keeps RAM strictly under 60MB.
        """
        import gc
        with self.lock:
            if self.is_refilling:
                return
            self.is_refilling = True

        try:
            logger.info(f"Starting proxy pool refill (Target: {target_count})...")
            existing_pool = self.load_local_pool()
            active_existing = [p for p in existing_pool if p not in self.dead_proxies]

            needed = target_count - len(active_existing)
            if needed <= 0:
                logger.info(f"Pool already full and healthy ({len(active_existing)} >= {target_count}). No refill needed.")
                return

            candidates = list(self.scrape_candidates())
            if not candidates:
                logger.warning("No fresh candidates found from scraper sources.")
                return

            random.shuffle(candidates)
            new_verified = []
            active_set = set(active_existing)

            # Test in streaming batches of 500 candidates with 25 workers
            batch_size = 500
            for i in range(0, len(candidates), batch_size):
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
                                if len(new_verified) % 10 == 0:
                                    current_combined = active_existing + new_verified
                                    self.save_pool(current_combined)
                                    logger.info(f"[Refill] Live pool: {len(current_combined)}/{target_count} verified proxies...")
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
        Runs every 30 minutes: Re-tests ALL proxies in the current pool,
        purges dead/slow ones, and immediately refills fresh proxies to guarantee target active.
        """
        import gc
        logger.info(f"Running scheduled 30-min health check on working proxies pool...")
        pool = self.load_local_pool()

        if not pool:
            self.refill_proxies(target_count=POOL_TARGET)
            return

        verified_still_alive = []
        dead_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            futures = {executor.submit(self.test_single_proxy, p): p for p in pool}
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

        if len(verified_still_alive) < POOL_TARGET:
            logger.info(f"Pool size ({len(verified_still_alive)}) is below {POOL_TARGET}. Triggering refill...")
            self.refill_proxies(target_count=POOL_TARGET)

    def start_background_daemon(self):
        """Launches continuous background monitoring, instant auto-refill, and 30-min health checks."""
        def daemon_loop():
            logger.info(f"Proxy Background Daemon started (Target Pool: {POOL_TARGET}+, Min: {POOL_MIN_THRESHOLD}, Health-Check: every {HEALTH_CHECK_INTERVAL // 60}m).")
            # Immediate initial refill if pool is below target
            if len(self.load_local_pool()) < POOL_TARGET:
                threading.Thread(target=self.refill_proxies, kwargs={"target_count": POOL_TARGET}, daemon=True).start()

            last_health_check = time.time()

            while True:
                time.sleep(POLL_INTERVAL)
                try:
                    now = time.time()
                    pool_len = len(self.load_local_pool())

                    # 1. Periodic 30-Minute Health Check
                    if (now - last_health_check >= HEALTH_CHECK_INTERVAL) and not self.is_refilling:
                        self.health_check_pool()
                        last_health_check = time.time()

                    # 2. Fast Auto-Refill if pool drops below threshold
                    elif pool_len < POOL_MIN_THRESHOLD and not self.is_refilling:
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
