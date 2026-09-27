import requests
import json
import time
import random
import base64
import hmac
import hashlib
import math
import os
import sys
import re
import threading
from typing import Optional

# ── AES-256-GCM via pycryptodome / cryptography ──
try:
    from Crypto.Cipher import AES as _AES

    class AESGCM:
        """Same API as cryptography AESGCM, backed by pycryptodome."""
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


# ╔══════════════════════════════════════════════════════════════════╗
# ║              MATRIX / HACKER TERMINAL PALETTE                    ║
# ╚══════════════════════════════════════════════════════════════════╝

_ANSI_RE = re.compile(r"\033\[[0-9;]*[A-Za-z]")

def _vis(s: str) -> int:
    return len(_ANSI_RE.sub("", s))


def _center(text: str, width: int) -> str:
    pad = max(0, width - _vis(text))
    left = pad // 2
    return " " * left + text + " " * (pad - left)


class C:
    R = "\033[0m"
    B = "\033[1m"
    D = "\033[2m"
    I = "\033[3m"
    U = "\033[4m"

    # matrix greens
    MX  = "\033[38;5;46m"    # hot matrix green
    MX2 = "\033[38;5;40m"
    MX3 = "\033[38;5;34m"
    MX4 = "\033[38;5;28m"
    MX5 = "\033[38;5;22m"

    RED = "\033[38;5;196m"
    DRED= "\033[38;5;88m"
    YEL = "\033[38;5;226m"
    ORA = "\033[38;5;208m"
    CYA = "\033[38;5;51m"
    MAG = "\033[38;5;201m"
    PUR = "\033[38;5;93m"
    WH  = "\033[38;5;231m"
    GRY = "\033[38;5;244m"
    DG  = "\033[38;5;240m"

    BG_MX  = "\033[48;5;22m"
    BG_DK  = "\033[48;5;16m"
    BG_RED = "\033[48;5;52m"
    BG_YEL = "\033[48;5;58m"
    BG_MG  = "\033[48;5;53m"

    BK = "\033[38;5;16m"

    @staticmethod
    def enable():
        if sys.platform == "win32":
            try:
                import ctypes
                k = ctypes.windll.kernel32
                k.SetConsoleMode(k.GetStdHandle(-11), 7)
            except Exception:
                pass


# ── Box visual map (only used in final report) ──
BOX_COLORS = {
    'thunder':  (C.CYA,  "⚡"),
    'thunder2': (C.MX,   "⚡"),
    'heart':    (C.MX,   "♥"),
    'trap':     (C.RED,  "☠"),
    'gully':    (C.YEL,  "◈"),
    'firefox':  (C.ORA,  "✦"),
}

BOX_TYPES  = ['thunder', 'thunder2', 'heart', 'trap', 'gully', 'firefox']
DIRECTIONS = ['up', 'down', 'left', 'right']
OPPOSITE   = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}

DEFAULT_MIN_DURATION_S = 90
DEFAULT_MAX_BOXES      = 9999

# ── Branding ──
BRAND_TITLE   = "MARCO & THE DARK"
BRAND_TAGLINE = "AUTO-FARM ENGINE  ::  DARKNET BUILD v3.0"
CHANNEL_1     = "@SmartEarning_77"
CHANNEL_2     = "@owatom"


# ╔══════════════════════════════════════════════════════════════════╗
# ║                       API LOGGER                                 ║
# ╚══════════════════════════════════════════════════════════════════╝

class APILogger:
    def __init__(self, log_file="responses.json"):
        self.log_file = log_file
        self.logs = []
        self.lock = threading.Lock()
        self._patched = False

    def patch_requests(self):
        if self._patched:
            return
        original = requests.Session.request
        logger = self

        def logged_request(session, method, url, *args, **kwargs):
            req_data = kwargs.get('json') or kwargs.get('data')
            t0 = time.time()
            try:
                resp = original(session, method, url, *args, **kwargs)
                t1 = time.time()
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = resp.text
                logger._append({
                    "timestamp": t0,
                    "latency_ms": round((t1 - t0) * 1000, 2),
                    "method": method.upper(),
                    "url": url,
                    "request": req_data,
                    "status_code": resp.status_code,
                    "response": resp_data,
                })
                return resp
            except Exception as e:
                t1 = time.time()
                logger._append({
                    "timestamp": t0,
                    "latency_ms": round((t1 - t0) * 1000, 2),
                    "method": method.upper(),
                    "url": url,
                    "request": req_data,
                    "error": str(e),
                })
                raise

        requests.Session.request = logged_request
        self._patched = True

    def _append(self, entry):
        with self.lock:
            self.logs.append(entry)
            try:
                with open(self.log_file, "w") as f:
                    json.dump(self.logs, f, indent=2)
            except Exception:
                pass


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     CONFIGURATION                                ║
# ╚══════════════════════════════════════════════════════════════════╝

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

TU_KEY = os.environ.get("TU_KEY", "a9rc/DSXunC5PdkYlDB6KkX/evwfSTDUD8PQdaepxe0=")
BASE_URL = os.environ.get("TU_BASE_URL", "https://thunder-zone.coke2home.com")
SESSION_FILE = os.environ.get("TU_SESSION_FILE", "session.json")


def get_tier(elapsed_ms):
    for t in GAME_CONFIG['tiers']:
        if elapsed_ms < t['untilMs']:
            return t
    return GAME_CONFIG['tiers'][-1]


# ╔══════════════════════════════════════════════════════════════════╗
# ║                 HACKER TERMINAL  ·  DISPLAY                      ║
# ╚══════════════════════════════════════════════════════════════════╝

class Display:
    W = 66

    # ────────────────────────────────────────────────────────────
    # low-level helpers
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _clear():
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def _type(text: str, delay: float = 0.004, end: str = "\n"):
        for ch in text:
            sys.stdout.write(ch)
            sys.stdout.flush()
            time.sleep(delay)
        sys.stdout.write(end)
        sys.stdout.flush()

    # ────────────────────────────────────────────────────────────
    # boot sequence
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def boot():
        Display._clear()
        pad = " " * 4
        print()
        print(f"{pad}{C.MX4}┌─[ SECURE SHELL INITIALIZATION ]{C.R}{C.MX4}{'─' * 32}┐{C.R}")
        print()

        steps = [
            ("loading kernel modules",        "0x00A1"),
            ("mounting encrypted vault",      "0x00F3"),
            ("routing through proxy chain",   "0x02C7"),
            ("bypassing perimeter firewall",  "0x11B9"),
            ("decrypting access tokens",      "0x0A7E"),
            ("injecting thunder payload",     "0xDEAD"),
            ("escalating privileges",         "0xROOT"),
        ]
        for label, tag in steps:
            sys.stdout.write(f"{pad}{C.MX3}[▸]{C.R} {C.DG}{label:<32}{C.R} ")
            sys.stdout.flush()
            time.sleep(random.uniform(0.10, 0.22))
            print(f"{C.MX4}{tag}{C.R}  {C.MX}{C.B}[ OK ]{C.R}")
            time.sleep(0.05)

        print()
        sys.stdout.write(f"{pad}{C.MX3}⟩{C.R} ACCESS LEVEL : ")
        time.sleep(0.25)
        print(f"{C.MX}{C.B}ROOT{C.R}")
        sys.stdout.write(f"{pad}{C.MX3}⟩{C.R} OPERATOR     : ")
        time.sleep(0.25)
        print(f"{C.MX}{C.B}{BRAND_TITLE}{C.R}")
        print()
        time.sleep(0.6)

    # ────────────────────────────────────────────────────────────
    # big banner
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def banner():
        Display._clear()
        W = Display.W
        side = f"{C.MX4}║{C.R}"

        def row(s):
            return f"{side}{_center(s, W)}{side}"

        top = f"{C.MX4}╔{'═' * W}╗{C.R}"
        bot = f"{C.MX4}╚{'═' * W}╝{C.R}"

        # ── big glitchy HARSHIT ──
        harshit = [
            "██╗  ██╗ █████╗ ██████╗ ███████╗██╗  ██╗██╗████████╗",
            "██║  ██║██╔══██╗██╔══██╗██╔════╝██║  ██║██║╚══██╔══╝",
            "███████║███████║██████╔╝███████╗███████║██║   ██║   ",
            "██╔══██║██╔══██║██╔══██╗╚════██║██╔══██║██║   ██║   ",
            "██║  ██║██║  ██║██║  ██║███████║██║  ██║██║   ██║   ",
            "╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝   ",
        ]
        dark = [
            "██████╗  █████╗ ██████╗ ██╗  ██╗",
            "██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝",
            "██║  ██║███████║██████╔╝█████╔╝ ",
            "██║  ██║██╔══██║██╔══██╗██╔═██╗ ",
            "██████╔╝██║  ██║██║  ██║██║  ██╗",
            "╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ]

        print()
        print(top)
        print(row(""))
        print(row(f"{C.MX4}[ SYSTEM ]  ◤ {C.MX}{C.B}{BRAND_TITLE}{C.R}{C.MX4}  ◢  [ ONLINE ]{C.R}"))
        print(row(f"{C.DG}{BRAND_TAGLINE}{C.R}"))
        print(row(""))
        print(f"{side}{C.MX5}{'─' * W}{C.R}{side}")
        print(row(""))

        for line in harshit:
            print(f"{side}{_center(f'{C.MX}{C.B}{line}{C.R}', W)}{side}")
        print(row(""))
        print(f"{side}{_center(f'{C.MX3}◆ ◇   A N D   ◇ ◆{C.R}', W)}{side}")
        print(row(""))
        for line in dark:
            print(f"{side}{_center(f'{C.RED}{C.B}{line}{C.R}', W)}{side}")

        print(row(""))
        print(f"{side}{C.MX5}{'─' * W}{C.R}{side}")
        print(row(""))
        print(row(f"{C.YEL}{C.B}◤ PRIVATE CHANNELS ◢{C.R}"))
        print(row(""))
        print(row(f"{C.MX}{C.B}➤  {CHANNEL_1}{C.R}"))
        print(row(f"{C.MX}{C.B}➤  {CHANNEL_2}{C.R}"))
        print(row(""))
        print(row(f"{C.DG}crafted by  The Dark  ✕  Marco{C.R}"))
        print(row(""))
        print(bot)
        print()

    # ────────────────────────────────────────────────────────────
    # section header
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def section(title: str):
        W = Display.W
        tag = f" ⟨ {title} ⟩ "
        pad = max(0, W - _vis(tag) - 2)
        left = pad // 2
        right = pad - left
        line = (
            f"{C.MX4}╺{'━' * left}{C.R}"
            f"{C.MX}{C.B}{tag}{C.R}"
            f"{C.MX4}{'━' * right}╸{C.R}"
        )
        print(f"\n{line}")

    # ────────────────────────────────────────────────────────────
    # status messages
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def ok(msg):
        print(f"  {C.MX}{C.B}[ ✔ ]{C.R} {msg}")

    @staticmethod
    def info(msg):
        print(f"  {C.CYA}{C.B}[ » ]{C.R} {msg}")

    @staticmethod
    def warn(msg):
        print(f"  {C.YEL}{C.B}[ ⚠ ]{C.R} {msg}")

    @staticmethod
    def error(msg):
        print(f"  {C.RED}{C.B}[ ✖ ]{C.R} {C.RED}{msg}{C.R}")

    @staticmethod
    def milestone(msg):
        print(f"  {C.MX5}{'─' * 60}{C.R}")
        print(f"  {C.YEL}{C.B}  ★  {msg}  ★  {C.R}")
        print(f"  {C.MX5}{'─' * 60}{C.R}")

    @staticmethod
    def tier_up(tier_id):
        print()
        print(f"  {C.MX4}┌{'─' * 58}┐{C.R}")
        print(f"  {C.MX4}│{C.R} {C.MX}{C.B}⟳  SYSTEM OVERCLOCK  ::  TIER {tier_id} ONLINE{C.R}                {C.MX4}│{C.R}")
        print(f"  {C.MX4}└{'─' * 58}┘{C.R}")
        print()

    # ────────────────────────────────────────────────────────────
    # session header (shown once at game start)
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def session_header(target, min_s, max_boxes, session_id):
        Display.section("SESSION LOADED")
        W = 62
        side = f"{C.MX4}║{C.R}"

        def row(label, value, vcol=C.MX):
            inner = f"  {C.B}{label:<16}{C.R}{vcol}{C.B}{value}{C.R}"
            pad = W - _vis(inner)
            return f"{side}{inner}{' ' * max(pad, 0)}{side}"

        print(f"{C.MX4}╔{'═' * W}╗{C.R}")
        print(row("TARGET SCORE",  str(target)))
        print(row("MIN RUNTIME",   f"{min_s}s", C.CYA))
        print(row("BOX CAP",       str(max_boxes), C.CYA))
        print(row("SESSION ID",    session_id[:32] + ("…" if len(session_id) > 32 else ""), C.DG))
        print(row("MODE",          "AUTO-FARM  ·  STEALTH", C.MX))
        print(f"{C.MX4}╚{'═' * W}╝{C.R}")
        print()

    # ────────────────────────────────────────────────────────────
    # live one-line status (updated in place)
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def live_status(sim, target, elapsed_s, status="INFILTRATING"):
        ratio = min(sim.score / max(target, 1), 1.0)
        bar_w = 22
        filled = int(bar_w * ratio)
        fill = f"{C.MX}{'█' * filled}{C.MX5}{'░' * (bar_w - filled)}{C.R}"
        pct = f"{C.MX}{C.B}{int(ratio*100):3d}%{C.R}"

        tier = get_tier(sim.elapsed_ms)['id']
        hearts = f"{C.RED}{'♥' * sim.hp}{C.DG}{'♡' * (sim.max_hp - sim.hp)}{C.R}"
        combo = f"{C.YEL}{C.B}x{sim.current_combo:<3}{C.R}" if sim.current_combo > 1 else f"{C.DG}x--{C.R}"

        return (
            f"  {C.MX4}⟩{C.R} "
            f"{C.CYA}{elapsed_s:6.1f}s{C.R} "
            f"{C.MX4}·{C.R} "
            f"{C.MX}{C.B}{sim.score:>5}{C.R}{C.DG}/{target}{C.R} "
            f"▕{fill}▏{pct} "
            f"{C.MX4}·{C.R} "
            f"{C.MX3}T{tier}{C.R} "
            f"{C.MX4}·{C.R} "
            f"{combo} "
            f"{C.MX4}·{C.R} "
            f"{hearts} "
            f"{C.MX4}·{C.R} "
            f"{C.DG}⬢ {sim.next_box_id-1:>4}{C.R}"
        )

    # ────────────────────────────────────────────────────────────
    # progress bar helper (used in wait phase)
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def progress_bar(current, target, width=40):
        ratio = min(current / max(target, 1), 1.0)
        filled = int(width * ratio)
        fill = f"{C.MX}{'█' * filled}{C.MX5}{'░' * (width - filled)}{C.R}"
        pct = f"{C.MX}{C.B}{ratio*100:5.1f}%{C.R}"
        return (
            f"  {C.MX4}▕{C.R}{fill}{C.MX4}▏{C.R}  "
            f"{C.CYA}{current:.1f}s{C.R}{C.DG}/{target}s{C.R}  {pct}"
        )

    # ────────────────────────────────────────────────────────────
    # final report
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def final_report(score, target, combo, duration_s, hit_counts, rank=None):
        Display.section("MISSION REPORT")

        W = 56
        side = f"{C.MX4}║{C.R}"

        def row(label, value_colored):
            inner = f"  {C.B}{label:<18}{C.R}{value_colored}"
            pad = W - _vis(inner)
            return f"{side}{inner}{' ' * max(pad, 0)}{side}"

        sc_color = C.MX if score >= target else C.YEL

        print(f"{C.MX4}╔{'═' * W}╗{C.R}")
        print(row("FINAL SCORE",  f"{sc_color}{C.B}{score}{C.R}"))
        print(row("TARGET",       f"{C.CYA}{target}{C.R}"))
        print(row("MAX COMBO",    f"{C.YEL}{C.B}x{combo}{C.R}"))
        print(row("RUNTIME",      f"{C.CYA}{duration_s:.1f}s{C.R}"))
        if rank is not None:
            print(row("GLOBAL RANK", f"{C.MAG}{C.B}#{rank}{C.R}"))
        print(f"{C.MX4}╚{'═' * W}╝{C.R}")

        if hit_counts:
            print(f"\n  {C.MX3}{C.B}◈  PAYLOAD BREAKDOWN{C.R}")
            print(f"  {C.MX5}{'─' * 58}{C.R}")
            for btype, count in sorted(hit_counts.items(), key=lambda x: -x[1]):
                color, icon = BOX_COLORS.get(btype, (C.WH, "·"))
                bar = f"{color}{'▓' * min(count, 40)}{C.R}"
                print(f"    {color}{C.B}{icon}{C.R}  {C.B}{btype:<12}{C.R}  {bar}  {C.B}{count}{C.R}")
            print(f"  {C.MX5}{'─' * 58}{C.R}")
        print()

    # ────────────────────────────────────────────────────────────
    # terminal helpers
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def live_write(line: str):
        sys.stdout.write("\r\033[K" + line)
        sys.stdout.flush()

    @staticmethod
    def live_clear():
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    @staticmethod
    def event_log(line: str):
        sys.stdout.write("\r\033[K")
        print(line)
        sys.stdout.flush()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                   GAME SIMULATOR                                 ║
# ╚══════════════════════════════════════════════════════════════════╝

class GameSimulator:
    def __init__(self, session_id):
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

    def add_drip_enc(self, drip_enc, drip_from_box=0):
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
            Display.warn(f"Drip decrypt failed: {e}")

    def has_enough_floats(self, required=4):
        return (len(self.floats) - self.drip_cursor) >= required

    def get_float(self):
        val = self.floats[self.drip_cursor]
        self.drip_cursor += 1
        return val

    def generate_next_box(self):
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

        total_w = sum(weights)
        target = f_type * total_w
        sel_type = eligible[-1]
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

    def play_box_correctly(self, box):
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
    def compute_chain_hash(session_id, input_log):
        items = [f"{b['boxId']}:{b['dir']}" for b in input_log]
        s = f"{session_id}|{','.join(items)}"
        return hashlib.sha256(s.encode('utf-8')).hexdigest()


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     AUTH MODULE                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

class Auth:
    def __init__(self, session):
        self.session = session
        self.base = BASE_URL

    def login(self):
        Display.section("AUTHENTICATION")

        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f:
                    cookies = json.load(f)
                self.session.cookies.update(cookies)
                Display.info("cached session found — verifying handshake...")

                resp = self.session.get(f"{self.base}/api/auth/me")
                if resp.status_code == 200 and resp.json().get("success"):
                    user = resp.json().get('user', {})
                    Display.ok(
                        f"IDENTITY CONFIRMED :: {C.MX}{C.B}{user.get('name', 'Unknown')}{C.R} "
                        f"{C.DG}({user.get('phone_number')}){C.R}"
                    )
                    self.show_stats()
                    return True
                else:
                    Display.warn("cached session expired — fresh login required.")
            except Exception as e:
                Display.warn(f"session load failed: {e}")

        phone = input(f"  {C.MX}{C.B}▸ phone number (10 digits):{C.R} ").strip()

        Display.info(f"transmitting OTP to {C.B}{phone}{C.R} ...")
        resp = self.session.post(f"{self.base}/api/auth/send-otp", json={"phone_number": phone})
        if not resp.json().get('success'):
            Display.error(f"OTP send failed: {resp.text}")
            return False
        Display.ok("OTP dispatched to target device.")

        otp = input(f"  {C.MX}{C.B}▸ enter OTP:{C.R} ").strip()

        Display.info("verifying OTP ...")
        resp = self.session.post(f"{self.base}/api/auth/verify-otp", json={
            "phone_number": phone, "otp": otp,
        })
        data = resp.json()
        if not data.get('success'):
            Display.error(f"OTP verification failed: {resp.text}")
            return False

        token = data.get('one_time_token')
        if not token:
            Display.error("no one_time_token in response.")
            return False

        Display.info("validating token ...")
        val_resp = self.session.post(f"{self.base}/api/auth/validate-token", json={"one_time_token": token})
        val_data = val_resp.json() if val_resp.status_code == 200 else {}
        requires_signup = val_data.get('requires_signup') or data.get('requiresSignup')

        if requires_signup:
            Display.info("completing auto-registration ...")
            signup_resp = self.session.post(f"{self.base}/api/auth/signup", json={
                "phone_number": phone,
                "name": "Operator"
            })
            if not signup_resp.json().get('success') and signup_resp.status_code != 200:
                Display.error(f"signup failed: {signup_resp.text}")
                return False
        else:
            Display.info("exchanging token for session ...")
            resp = self.session.post(f"{self.base}/api/auth/exchange-token", json={"one_time_token": token})
            ex_data = resp.json() if resp.status_code == 200 else {}
            if not (ex_data.get('authenticated') or ex_data.get('success') or len(self.session.cookies) > 0):
                Display.error(f"token exchange failed: {resp.text}")
                return False

        with open(SESSION_FILE, "w") as f:
            json.dump(self.session.cookies.get_dict(), f)

        resp = self.session.get(f"{self.base}/api/auth/me")
        user = resp.json().get('user', {})
        Display.ok(f"LOGGED IN :: {C.MX}{C.B}{user.get('name', 'Unknown')}{C.R} ({user.get('phone_number')})")
        Display.ok(f"session cached → {C.DG}{SESSION_FILE}{C.R}")

        self.show_stats()
        return True

    def show_stats(self):
        Display.section("OPERATOR PROFILE")
        resp = self.session.get(f"{self.base}/api/thunder-trail/me")
        if resp.status_code == 200 and resp.json().get("success"):
            data = resp.json().get("data", {})
            plays = data.get("plays_remaining", 0)
            best = data.get("best_score", 0)
            rank = data.get("rank")
            rank_str = f"#{rank}" if rank else "UNRANKED"

            W = 46
            side = f"{C.MX4}║{C.R}"

            def row(label, value_colored):
                inner = f"  {C.B}{label:<18}{C.R}{value_colored}"
                pad = W - _vis(inner)
                return f"{side}{inner}{' ' * max(pad, 0)}{side}"

            print(f"{C.MX4}╔{'═' * W}╗{C.R}")
            plays_c = C.MX if plays > 0 else C.RED
            print(row("LIVES REMAINING", f"{plays_c}{C.B}{plays}{C.R}"))
            print(row("BEST SCORE",      f"{C.YEL}{C.B}{best}{C.R}"))
            print(row("GLOBAL RANK",     f"{C.MAG}{C.B}{rank_str}{C.R}"))
            print(f"{C.MX4}╚{'═' * W}╝{C.R}")

            if plays <= 0:
                Display.warn("no lives remaining today.")
            return data
        else:
            Display.error(f"stats fetch failed: {resp.text}")
            return None


# ╔══════════════════════════════════════════════════════════════════╗
# ║                    THUNDERBOT ORCHESTRATOR                       ║
# ╚══════════════════════════════════════════════════════════════════╝

class ThunderBot:
    BOX_NAME_MAP = {
        "thunder": "thunder_box",
        "thunder2": "thunder_box",
        "thunderCan": "thunder_can",
        "gully": "gully_labs",
        "firefox": "firefox",
        "heart": "heart",
        "trap": "trap",
    }

    def __init__(self):
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
        self.auth = Auth(self.session)

    # ── Heartbeat ──
    def _heartbeat(self, session_id, session_token, sim, committed_count, start_time):
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
            )
            data = resp.json()
            if data.get('drip_enc'):
                sim.add_drip_enc(data['drip_enc'], data.get('drip_from_box', 0))
            return len(sim.input_log)
        except Exception as e:
            Display.error(f"heartbeat failed: {e}")
            return committed_count

    # ── Main game loop ──
    def play_game(self, target_score=2000,
                  min_duration_s=DEFAULT_MIN_DURATION_S,
                  max_boxes=DEFAULT_MAX_BOXES):

        Display.section("LAUNCHING SESSION")

        # ── Start session ──
        sys.stdout.write(f"  {C.MX4}▸{C.R} handshake with remote node ")
        for _ in range(3):
            time.sleep(0.15)
            sys.stdout.write(f"{C.MX}·{C.R}")
            sys.stdout.flush()
        print()

        resp = self.session.post(f"{BASE_URL}/api/thunder-trail/sessions", json={})
        data = resp.json()
        if not data.get('success'):
            Display.error(f"session start failed: {resp.text}")
            return

        session_id = data['data']['session_id']
        session_token = data['data']['session_token']
        drip_enc = data['data'].get('drip_enc')
        drip_from_box = data['data'].get('drip_from_box', 0)

        Display.ok(f"session id  → {C.DG}{session_id}{C.R}")
        Display.ok(f"token       → {C.DG}{session_token[:20]}…{C.R}")

        sim = GameSimulator(session_id)
        sim.add_drip_enc(drip_enc, drip_from_box)

        start_time = time.time()
        committed_count = 0
        prev_tier = 1
        last_milestone = 0

        # ── header ──
        Display.session_header(target_score, min_duration_s, max_boxes, session_id)

        print(f"  {C.MX4}{'─' * 68}{C.R}")
        print(f"  {C.MX3}{C.B}◤ LIVE EVENT STREAM ◢{C.R}")
        print(f"  {C.MX4}{'─' * 68}{C.R}\n")

        # ══════════════════════════════════════════════════════
        # PHASE 1 — FAST PLAY
        # ══════════════════════════════════════════════════════
        while sim.score < target_score and len(sim.input_log) < max_boxes:
            if not sim.has_enough_floats(required=4):
                committed_count = self._heartbeat(
                    session_id, session_token, sim, committed_count, start_time
                )

            box = sim.generate_next_box()
            pts, _ = sim.play_box_correctly(box)

            # ── events ──
            if box.get('tier', 1) > prev_tier:
                Display.event_log(
                    f"  {C.MX}{C.B}[⟳]{C.R} {C.MX}{C.B}SYSTEM OVERCLOCK{C.R} "
                    f"{C.DG}—{C.R} speed tier upgraded to {C.MX}{C.B}T{box['tier']}{C.R}"
                )
                prev_tier = box['tier']

            for m in [100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000]:
                if sim.score >= m > last_milestone:
                    Display.event_log(
                        f"  {C.YEL}{C.B}[★]{C.R} {C.YEL}{C.B}BREAKPOINT {m}{C.R} "
                        f"{C.DG}—{C.R} score now {C.MX}{C.B}{sim.score}{C.R}"
                    )
                    last_milestone = m

            # ── live status line ──
            elapsed_s = (time.time() - start_time)
            Display.live_write(
                Display.live_status(sim, target_score, elapsed_s)
            )

# Fast-play box complete

        played = len(sim.input_log)
        reason = "target reached" if sim.score >= target_score else f"{max_boxes}-box cap hit"
        Display.live_clear()
        Display.event_log(
            f"  {C.MX}{C.B}[✓]{C.R} fast-play complete {C.DG}—{C.R} "
            f"{C.B}{played}{C.R} payloads  {C.DG}·{C.R}  score {C.MX}{C.B}{sim.score}{C.R}  "
            f"{C.DG}({reason}){C.R}"
        )

        # ══════════════════════════════════════════════════════
        # PHASE 2 — WAIT until min runtime
        # ══════════════════════════════════════════════════════
        elapsed = time.time() - start_time
        if elapsed < min_duration_s:
            wait_needed = min_duration_s - elapsed
            Display.event_log(
                f"  {C.CYA}{C.B}[⌛]{C.R} cooling down {C.B}{wait_needed:.1f}s{C.R} "
                f"to satisfy min runtime {C.DG}({min_duration_s}s){C.R}"
            )

            while True:
                elapsed = time.time() - start_time
                if elapsed >= min_duration_s:
                    break

                Display.live_write(Display.progress_bar(elapsed, min_duration_s))
                time.sleep(1.0)

            Display.live_clear()
            Display.event_log(
                f"  {C.MX}{C.B}[✓]{C.R} min runtime achieved {C.DG}({min_duration_s}s){C.R}"
            )
        else:
            Display.event_log(
                f"  {C.MX}{C.B}[✓]{C.R} min runtime already met "
                f"{C.DG}({elapsed:.1f}s ≥ {min_duration_s}s){C.R}"
            )

        # ══════════════════════════════════════════════════════
        # PHASE 3 — SUBMIT
        # ══════════════════════════════════════════════════════
        print()
        Display.section("SUBMISSION")

        mapped_hits = {}
        for k, v in sim.hit_counts.items():
            mk = self.BOX_NAME_MAP.get(k, k)
            mapped_hits[mk] = mapped_hits.get(mk, 0) + v

        duration_ms = sim.next_spawn_at_ms + 1000

        score_payload = {
            "session_token": session_token,
            "final_score": sim.score,
            "duration_ms": duration_ms,
            "max_combo": sim.max_combo,
            "box_counts": mapped_hits,
            "seed": 0,
            "input_log": sim.input_log,
        }

        Display.info(f"transmitting payload {C.B}{sim.score}{C.R} pts ...")
        resp = self.session.post(
            f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/score",
            json=score_payload,
        )
        score_resp = resp.json()
        if score_resp.get('success'):
            Display.ok("payload accepted by server.")
        else:
            Display.error(f"score response: {score_resp}")

        max_tier = 1
        for idx, t in enumerate(GAME_CONFIG['tiers'][:-1]):
            if duration_ms >= t['untilMs']:
                max_tier = idx + 2

        journey_payload = {
            "session_token": session_token,
            "seed": 0,
            "input_log": sim.input_log,
            "final_score": sim.score,
            "duration_ms": duration_ms,
            "max_combo": sim.max_combo,
            "hit_counts": mapped_hits,
            "max_tier_reached": max_tier,
        }

        resp = self.session.post(
            f"{BASE_URL}/api/thunder-trail/sessions/{session_id}/journey",
            json=journey_payload,
        )
        journey_resp = resp.json()
        valid = journey_resp.get('success') and journey_resp.get('data', {}).get('score_valid')

        if valid:
            print()
            print(f"  {C.BG_MX}{C.BK}{C.B}                                                          {C.R}")
            print(f"  {C.BG_MX}{C.BK}{C.B}      ✔  PAYLOAD VERIFIED  ·  UPLOADED TO SERVER  ✔        {C.R}")
            print(f"  {C.BG_MX}{C.BK}{C.B}                                                          {C.R}")
            print()
        else:
            Display.warn(f"journey response: {journey_resp}")

        rank = None
        try:
            me = self.session.get(f"{BASE_URL}/api/thunder-trail/me").json()
            if me.get('success'):
                rank = me.get('data', {}).get('rank')
        except Exception:
            pass

        Display.final_report(
            score=sim.score,
            target=target_score,
            combo=sim.max_combo,
            duration_s=time.time() - start_time,
            hit_counts=sim.hit_counts,
            rank=rank,
        )


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        ENTRY POINT                               ║
# ╚══════════════════════════════════════════════════════════════════╝

def _footer():
    print(f"\n  {C.MX4}{'─' * 62}{C.R}")
    print(
        f"  {C.MX}{C.B}◤ {BRAND_TITLE} ◢{C.R}   "
        f"{C.DG}|{C.R}   "
        f"{C.MX}{CHANNEL_1}{C.R}   "
        f"{C.DG}|{C.R}   "
        f"{C.MX}{CHANNEL_2}{C.R}"
    )
    print(f"  {C.MX4}{'─' * 62}{C.R}\n")


def main():
    C.enable()
    Display.boot()
    Display.banner()

    logger = APILogger()
    logger.patch_requests()

    target_score = None
    min_duration_s = DEFAULT_MIN_DURATION_S
    max_boxes = DEFAULT_MAX_BOXES

    if len(sys.argv) > 1:
        try:
            target_score = int(sys.argv[1])
            if target_score > 0:
                Display.ok(f"target score from arg → {C.MX}{C.B}{target_score}{C.R}")
            else:
                target_score = None
        except ValueError:
            Display.warn(f"invalid arg '{sys.argv[1]}', will ask interactively.")

    if len(sys.argv) > 2:
        try:
            min_duration_s = int(sys.argv[2])
            if min_duration_s > 0:
                Display.ok(f"min runtime from arg → {C.CYA}{C.B}{min_duration_s}s{C.R}")
        except ValueError:
            Display.warn(f"invalid runtime '{sys.argv[2]}', using default {DEFAULT_MIN_DURATION_S}s.")

    if len(sys.argv) > 3:
        try:
            max_boxes = int(sys.argv[3])
            if max_boxes > 0:
                Display.ok(f"box cap from arg → {C.CYA}{C.B}{max_boxes}{C.R}")
        except ValueError:
            Display.warn(f"invalid cap '{sys.argv[3]}', using default {DEFAULT_MAX_BOXES}.")

    bot = ThunderBot()

    if not bot.auth.login():
        Display.error("authentication failed — aborting.")
        _footer()
        sys.exit(1)

    if target_score is None:
        Display.section("MISSION PARAMETERS")
        while True:
            score_input = input(
                f"\n  {C.MX}{C.B}▸ target score{C.R} "
                f"{C.DG}(e.g. 500, 1000, 2000){C.R}: "
            ).strip()
            try:
                target_score = int(score_input)
                if target_score <= 0:
                    Display.warn("score must be greater than 0. try again.")
                    continue
                break
            except ValueError:
                Display.warn("please enter a valid number. try again.")

    print()
    Display.ok(f"target score  → {C.MX}{C.B}{target_score}{C.R}")
    Display.ok(f"min runtime   → {C.CYA}{C.B}{min_duration_s}s{C.R}")
    Display.ok(f"box cap       → {C.CYA}{C.B}{max_boxes}{C.R}")
    Display.info(f"{C.YEL}fast-play · cool-down · auto-submit{C.R}")

    bot.play_game(
        target_score=target_score,
        min_duration_s=min_duration_s,
        max_boxes=max_boxes,
    )

    Display.section("DONE")
    Display.ok("session complete. api logs → responses.json")
    _footer()


if __name__ == "__main__":
    main()