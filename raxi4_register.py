# language: Python, file: raxi4_register.py
# raxi4.com auto-register — Termux native. Pure PIL + numpy. No Playwright, no OpenCV.
# install: pkg install python-pillow python-numpy
#          pip install requests
# run: python raxi4_register.py --phone 9876543210 --password yash1617

import re
import io
import sys
import json
import time
import uuid
import base64
import hashlib
import random
import secrets
import argparse
from datetime import datetime, timezone

import requests
import numpy as np
from PIL import Image, ImageFilter

# ─── config ───
SITE     = "https://www.raxi4.com"
API      = "https://api.raxiqaz.com"
INVITE   = "12345678901"
NEELWIN_SECRET = "9ALalE51IJxxkK0Pg0ejgbwYvM2sUaGf"
UA_MOB   = ("Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get_neelwin_sign(data, secret=NEELWIN_SECRET):
    ts = str(int(time.time()))
    nonce = str(random.randint(1, 9)) + "".join([str(random.randint(0, 9)) for _ in range(19)])
    t = dict(data)
    t["timestamp"] = ts
    t["nonce"] = nonce
    o = {k: v for k, v in t.items() if v is not None and v != ""}
    sorted_keys = sorted([k for k in o if k != "sign"])
    to_sign = "".join(f"{k}{o[k]}" for k in sorted_keys) + secret
    sig = hashlib.md5(to_sign.encode("utf-8")).hexdigest().upper()
    return sig, ts, nonce


# ═══════════════════════════════════════════════════════════════════════════
#  1. SIGNATURE GENERATION (Reverse-Engineered from Frontend JS)
# ═══════════════════════════════════════════════════════════════════════════

def mz():
    """Matches frontend mz() function: UUID v4 without hyphens."""
    return uuid.uuid4().hex


def signed_body(body):
    """
    Reverse-engineered API signature algorithm from index-IgG58Lcm.js.
    Sorts payload keys alphabetically excluding signature/track/xosoBettingData,
    concatenates into compact JSON, and computes uppercase MD5 hash.
    """
    t = dict(body)
    t.pop("signature", None)
    t.pop("timestamp", None)
    t["language"] = 0
    t["random"] = mz()

    # Ignored keys in frontend signature generation
    gue = {"signature", "track", "xosoBettingData"}
    n = {}
    for k in sorted(t.keys()):
        v = t[k]
        if v is not None and v != "" and k not in gue:
            n[k] = 0 if v == 0 else v

    json_str = json.dumps(n, separators=(",", ":"))
    sig = hashlib.md5(json_str.encode()).hexdigest().upper()

    t["signature"] = sig
    t["timestamp"] = int(time.time())
    return t


# ═══════════════════════════════════════════════════════════════════════════
#  2. CAPTCHA PUZZLE SOLVER — Pure PIL + NumPy Contour Matching
# ═══════════════════════════════════════════════════════════════════════════

def solve_slider(bg_b64, slider_b64, debug=False):
    """
    Solves the slider puzzle challenge with high precision:
    - Extracts the exact cutout contour from the slider RGBA alpha channel.
    - Matches contour against the background image edge map in the known Y slice.
    - Scales natural coordinates (552x344) down to frontend container (340x212),
      correctly compensating for piece offset x0.
    Returns: (container_gap_x, score)
    """
    try:
        bg_bytes = base64.b64decode(bg_b64.split(",")[-1])
        sl_bytes = base64.b64decode(slider_b64.split(",")[-1])

        bg = Image.open(io.BytesIO(bg_bytes)).convert("L")
        sl = Image.open(io.BytesIO(sl_bytes)).convert("RGBA")

        bg_w, bg_h = bg.size
        sl_arr = np.array(sl)

        if sl_arr.ndim != 3 or sl_arr.shape[2] < 4:
            return random.randint(100, 220), 0

        alpha = sl_arr[:, :, 3]
        y_idx, x_idx = np.where(alpha > 100)
        if len(y_idx) == 0 or len(x_idx) == 0:
            y_idx, x_idx = np.where(alpha > 30)
        if len(y_idx) == 0 or len(x_idx) == 0:
            return random.randint(100, 220), 0

        y0, y1 = int(y_idx.min()), int(y_idx.max())
        x0, x1 = int(x_idx.min()), int(x_idx.max())

        piece_mask = (alpha[y0:y1 + 1, x0:x1 + 1] > 50).astype(np.uint8)
        pw = x1 - x0 + 1

        # Extract sharp boundary contours using 3x3 edge filter
        mask_edges = np.array(Image.fromarray(piece_mask * 255).filter(ImageFilter.FIND_EDGES)) > 100
        bg_edges = np.array(bg.filter(ImageFilter.FIND_EDGES))[y0:y1 + 1, :]

        best_x, best_score = 0, -1
        # Search positions (ignoring left spawn region < 50)
        for x in range(50, bg_w - pw):
            s = int((bg_edges[:, x:x + pw] * mask_edges).sum())
            if s > best_score:
                best_score = s
                best_x = x

        # Frontend container scale: 340px width container vs 552px natural background
        scale = 340.0 / bg_w
        container_x = round((best_x - x0) * scale)
        container_x = max(25, min(container_x, 300))

        if debug:
            try:
                vis = bg.copy().convert("RGB")
                arr = np.array(vis)
                arr[y0:y1 + 1, best_x:best_x + 2, 0] = 255
                arr[y0:y1 + 1, best_x:best_x + 2, 1:] = 0
                arr[y0:y1 + 1, best_x + pw - 2:best_x + pw, 0] = 255
                arr[y0:y1 + 1, best_x + pw - 2:best_x + pw, 1:] = 0
                Image.fromarray(arr).save("slider_debug.jpg")
                log(f"  [captcha] debug image saved to slider_debug.jpg (natural_x={best_x}, container_x={container_x})")
            except Exception:
                pass

        return container_x, best_score
    except Exception as exc:
        log(f"  [captcha] solve_slider exception: {exc}")
        return random.randint(100, 220), 0


def make_track(gap_x, bg_w=340, bg_h=212, sl_w=68, sl_h=212):
    """
    Synthesizes a realistic human drag movement with ease-in-out easing,
    subtle vertical tremor, and accurate ISO start/end timestamps.
    """
    duration = random.randint(700, 950)       # drag duration in ms
    n = random.randint(14, 18)                 # ultra-compact trajectory points (~600 bytes vs ~1500 bytes)
    pts = []

    for i in range(n + 1):
        p = i / n
        # Cubic bezier easing
        eased = 4 * p ** 3 if p < 0.5 else 1 - pow(-2 * p + 2, 3) / 2
        x = round(gap_x * eased)
        y = round(random.uniform(-1.0, 1.0))
        t = int(duration * p)
        pts.append({"x": x, "y": y, "t": t})

    # Realistic human micro-overshoot and landing adjustment
    if len(pts) >= 3:
        pts[-2]["x"] = min(pts[-2]["x"] + random.randint(1, 2), bg_w - sl_w)
        pts[-2]["t"] = pts[-2]["t"] + random.randint(25, 45)
        pts[-1]["x"] = gap_x
        pts[-1]["t"] = pts[-2]["t"] + random.randint(25, 45)

    start_time = time.time()
    end_time = start_time + (pts[-1]["t"] / 1000.0)

    def to_iso(t_sec):
        dt = datetime.fromtimestamp(t_sec, timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"

    return {
        "backgroundImageWidth": bg_w,
        "backgroundImageHeight": bg_h,
        "sliderImageWidth": sl_w,
        "sliderImageHeight": sl_h,
        "startTime": to_iso(start_time),
        "endTime": to_iso(end_time),
        "tracks": pts,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. FLOW & REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════

def build_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA_MOB,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Ar-Origin": SITE,
        "Origin": SITE,
        "Referer": f"{SITE}/",
        "Accept-Language": "en-IN,en;q=0.9",
    })
    return s


def register_once(session, phone, password, invite, site="https://www.raxi4.com", api="https://api.raxiqaz.com", max_captcha_retries=3):
    import urllib.parse
    domain = urllib.parse.urlparse(site).netloc or "www.raxi4.com"
    target_api = api or API

    result = {
        "ok": False,
        "phone": phone,
        "password": password,
        "invite": invite,
        "token": None,
        "userId": None,
        "msg": None,
        "captcha_x": None
    }

    if "neelwin" in site.lower() or "neelwin" in str(target_api).lower() or "18822.shop" in str(target_api).lower():
        log("[+] Running Neelwin platform registration...")
        base_api = target_api.rstrip("/")
        if not base_api.endswith("/api"):
            base_api = f"{base_api}/api"
        reg_url = f"{base_api}/member/register"
        reg_dict = {
            "mobile": phone,
            "password": password,
            "confirmPassword": password,
            "spreaderId": invite,
            "areaCode": "+91",
            "registrationMethod": "phone",
            "regSource": "direct"
        }
        sig, ts, nonce = get_neelwin_sign(reg_dict)
        headers = {
            "device": "H5",
            "language": "en",
            "version": "app_v2",
            "sign": sig,
            "timestamp": ts,
            "nonce": nonce,
            "Origin": site,
            "Referer": f"{site}/?code={invite}"
        }
        r = session.post(reg_url, json=reg_dict, headers=headers, timeout=20)
        j = r.json()
        result["msg"] = j.get("msg")
        if j.get("code") == 0 and j.get("data"):
            d = j["data"]
            result["ok"] = True
            result["token"] = d.get("token")
            try:
                part = result["token"].split(".")[1]
                part += "=" * (-len(part) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(part))
                if "user_info" in decoded:
                    uinfo = json.loads(decoded["user_info"]) if isinstance(decoded["user_info"], str) else decoded["user_info"]
                    result["userId"] = uinfo.get("userId") or uinfo.get("uid")
                else:
                    result["userId"] = decoded.get("UserId")
            except Exception:
                pass
            log("  ═══════════════ SUCCESS ═══════════════")
            log(f"  userId : {result['userId']}")
            log(f"  token  : {result['token'][:70]}...")
            log("  ═══════════════════════════════════════")
        return result

    log("[+] Checking RegisterState...")
    body = signed_body({})
    r = session.post(f"{target_api}/api/webapi/RegisterState", json=body, timeout=15)
    state = r.json()
    log(f"    code={state.get('code')}  msg={state.get('msg')}")
    if state.get("code") != 0:
        result["msg"] = state.get("msg")
        return result

    device_id = secrets.token_hex(16)

    for attempt in range(1, max_captcha_retries + 1):
        if attempt > 1:
            log(f"[+] Retrying captcha challenge (attempt {attempt}/{max_captcha_retries})...")
            time.sleep(1.5)

        log("[+] Fetching Captcha...")
        c_body = signed_body({})
        r = session.post(f"{target_api}/api/webapi/Captcha", json=c_body, timeout=15)
        c = r.json()
        if c.get("code") != 0:
            log(f"    captcha fetch failed: {c.get('msg')}")
            result["msg"] = c.get("msg")
            continue

        cd = c["data"]
        captcha_id = cd["captchaId"]
        bg_b64     = cd["backgroundImage"]
        sl_b64     = cd["sliderImage"]
        log(f"    captchaId = {captcha_id}")

        log("[+] Solving slider puzzle...")
        gap_x, score = solve_slider(bg_b64, sl_b64, debug=True)
        log(f"    container_gap_x = {gap_x}  score = {score}")
        result["captcha_x"] = gap_x

        track = make_track(gap_x)

        reg_body = {
            "username": f"91{phone}",
            "smsvcode": "",
            "registerType": "mobile",
            "pwd": password,
            "invitecode": invite,
            "packId": "",
            "domainurl": domain,
            "phonetype": 1,
            "captchaId": captcha_id,
            "track": track,
            "deviceId": device_id,
            "couponNum": "",
            "pixelId": "",
            "fbcId": "",
            "fbc": "",
            "fbp": "",
            "adId": "",
        }
        payload = signed_body(reg_body)

        log("[+] Submitting Register POST...")
        r = session.post(f"{target_api}/api/webapi/Register", json=payload, timeout=20)
        j = r.json()
        code = j.get("code")
        msg = j.get("msg")
        msg_code = j.get("msgCode")
        log(f"    code={code}  msgCode={msg_code}  msg={msg}")
        result["msg"] = msg

        # msgCode 31 = 'Verification failed, please try again' -> retry captcha
        if msg_code == 31:
            log("    [!] Captcha verification failed, requesting new captcha...")
            continue

        # Rate limit protection
        if "frequently" in str(msg).lower():
            log("    [!] Rate limited, waiting 3s before retry...")
            time.sleep(3.0)
            continue

        if code == 0 and j.get("data"):
            d = j["data"]
            result["ok"] = True
            result["token"] = d.get("token")
            # Try to decode userId from token JWT
            try:
                part = result["token"].split(".")[1]
                part += "=" * (-len(part) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(part))
                result["userId"] = decoded.get("UserId")
            except Exception:
                pass

            log("  ═══════════════ SUCCESS ═══════════════")
            log(f"  userId : {result['userId']}")
            log(f"  token  : {result['token'][:70]}...")
            log("  ═══════════════════════════════════════")
            break
        else:
            # Registration responded with non-zero (e.g. Phone already registered, etc.)
            break

    return result


def main():
    ap = argparse.ArgumentParser(description="raxi4 auto-register with native slider captcha solving")
    ap.add_argument("--phone", required=True, help="10-digit phone number")
    ap.add_argument("--password", required=True, help="Account password (letters and numbers, 8-30 chars)")
    ap.add_argument("--invite", default=INVITE, help="Invitation code")
    ap.add_argument("--site", default=SITE, help="Target website URL")
    ap.add_argument("--api", default=None, help="Target API URL")
    ap.add_argument("--count", type=int, default=1, help="Number of registrations")
    args = ap.parse_args()

    phone = re.sub(r"\D", "", args.phone)[-10:]
    if len(phone) != 10:
        sys.exit("[!] phone must be 10 digits")

    # Validate password format required by platform: 8-30 alphanumeric chars
    if not re.match(r"^(?=.*[a-zA-Z])(?=.*\d)[a-zA-Z\d]{8,30}$", args.password):
        log("[!] Warning: Password should contain both letters and digits, 8-30 characters.")

    target_site = args.site or SITE
    target_api = args.api or (f"{target_site}/api" if "neelwin" in target_site.lower() else API)

    log("=" * 60)
    log(f"raxi4 auto-register · {phone} · invite={args.invite} · site={target_site}")
    log("=" * 60)

    session = build_session()

    # Warm-up request to establish cookies
    try:
        session.get(target_site, timeout=15)
    except Exception:
        pass

    results = []
    for i in range(args.count):
        if i > 0:
            log(f"\n─── run {i+1}/{args.count} ───")
            p = str(int(phone) + i)[-10:]
        else:
            p = phone

        try:
            r = register_once(session, p, args.password, args.invite, site=target_site, api=target_api)
        except Exception as e:
            log(f"[!] Crash: {e}")
            r = {"ok": False, "phone": p, "error": str(e)}
        results.append(r)

        if i < args.count - 1:
            time.sleep(random.uniform(3, 5))

    ok = sum(1 for r in results if r.get("ok"))
    log(f"\nSUMMARY: {ok}/{len(results)} succeeded")

    with open("raxi4_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log("[saved] raxi4_results.json")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nstopped")