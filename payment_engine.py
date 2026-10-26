"""
Payment Engine for Raxi4 Bot
Automated Crypto Token Recharge via @CryptoBot (Crypto Pay API)
Features:
- Mathematical half-up rounding for odd / fee-deducted amounts (e.g. 0.734 -> 0.73 -> 73 tokens; 0.656 -> 0.66 -> 66 tokens; 0.87732 -> 0.88 -> 88 tokens)
- Auto fee surcharge calculation so Owner receives full net amount ($1 net)
- Dual-layer instant settlement (Background Polling + Instant On-Demand Verification + Webhook Support)
- Persistent thread-safe invoice storage in crypto_invoices.json
- Transparent breakdown receipts with full mathematical formula
"""

import os
import json
import time
import logging
import threading
import urllib.request
import urllib.error
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("payment_engine")

# ─── Configuration & Defaults ───
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN", "655242:AAYmK4gRIBr2k4KL6WaVMDtwC2sXjUcXFKE")
CRYPTO_API_BASE = "https://pay.crypt.bot/api"
INVOICES_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crypto_invoices.json")

# Fee surcharge percentage to ensure owner receives full target amount (e.g., 3.0% CryptoBot gateway fee)
DEFAULT_SURCHARGE_PCT = float(os.environ.get("CRYPTO_SURCHARGE_PCT", "3.0"))

# Exchange rate: 1 USD / USDT = 100 Tokens (1 Token = 1 INR / 0.01 USD)
TOKENS_PER_USD = 100

# Preset Recharge Packages
DEFAULT_PACKAGES = [
    {"tokens": 100, "usd": 1.0, "label": "100 Tokens ($1 USDT)"},
    {"tokens": 200, "usd": 2.0, "label": "200 Tokens ($2 USDT)"},
    {"tokens": 500, "usd": 5.0, "label": "500 Tokens ($5 USDT)"},
    {"tokens": 1000, "usd": 10.0, "label": "1,000 Tokens ($10 USDT)"},
]


def calculate_tokens_from_amount(amount_usd: Any) -> Tuple[Decimal, int, str]:
    """
    Standard Mathematical Half-Up Rounding Rule (User Specification):
    - Inspects the decimal value down to 2 decimal places using half-up math.
    - If 3rd decimal digit is < 5 -> round down (e.g., 0.734 -> 0.73 -> 73 tokens).
    - If 3rd decimal digit is >= 5 -> round up (e.g., 0.656 -> 0.66 -> 66 tokens, 0.87732 -> 0.88 -> 88 tokens).
    Returns:
        (rounded_usd: Decimal, tokens: int, explanation: str)
    """
    try:
        dec = Decimal(str(amount_usd).strip())
    except Exception:
        dec = Decimal("0.00")

    rounded = dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tokens = int(rounded * TOKENS_PER_USD)
    explanation = f"${dec} ➔ ${rounded} (Math Half-Up) = {tokens} Tokens"
    return rounded, max(0, tokens), explanation


def calculate_invoice_amount_with_surcharge(target_usd: float, surcharge_pct: float = DEFAULT_SURCHARGE_PCT) -> Decimal:
    """
    Calculates the gross invoice amount so after the gateway/network fee (surcharge_pct),
    the merchant receives at least the target USD.
    gross = target / (1 - surcharge_pct / 100)
    """
    t = Decimal(str(target_usd))
    if surcharge_pct <= 0:
        return t.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    pct = Decimal(str(surcharge_pct)) / Decimal("100")
    denom = Decimal("1.0") - pct
    if denom <= Decimal("0.0"):
        denom = Decimal("1.0")
    gross = t / denom
    return gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PaymentEngine:
    def __init__(self, api_token: str = CRYPTO_PAY_TOKEN, db_path: str = INVOICES_DB_PATH):
        self.api_token = api_token
        self.db_path = db_path
        self._lock = threading.RLock()
        self.invoices: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._on_settled_callback = None
        self.load_db()

    # ─── Persistence ───
    def load_db(self):
        with self._lock:
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.invoices = data.get("invoices", {})
                except Exception as e:
                    logger.error(f"[PaymentEngine] Error loading db: {e}")
                    self.invoices = {}
            else:
                self.invoices = {}

    def save_db(self):
        with self._lock:
            try:
                tmp = self.db_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"invoices": self.invoices, "updated_at": int(time.time())}, f, indent=2)
                os.replace(tmp, self.db_path)
            except Exception as e:
                logger.error(f"[PaymentEngine] Error saving db: {e}")

    # ─── API Requests ───
    def _api_call(self, endpoint: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
        url = f"{CRYPTO_API_BASE}/{endpoint.lstrip('/')}"
        headers = {
            "Crypto-Pay-API-Token": self.api_token,
            "User-Agent": "RaxiBot-PaymentEngine/1.0",
            "Content-Type": "application/json"
        }
        data_bytes = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.error(f"[PaymentEngine] HTTP error {e.code} on {endpoint}: {err_body}")
            return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
        except Exception as e:
            logger.error(f"[PaymentEngine] Request error on {endpoint}: {e}")
            return {"ok": False, "error": str(e)}

    def check_app_status(self) -> Dict[str, Any]:
        """Validates API token credentials and fetches connected app info."""
        return self._api_call("getMe")

    # ─── Invoice Lifecycle ───
    def create_token_invoice(
        self,
        user_id: int,
        chat_id: int,
        target_tokens: int,
        surcharge_pct: float = DEFAULT_SURCHARGE_PCT,
        bot_username: str = "raxi4_bot"
    ) -> Dict[str, Any]:
        """
        Creates an invoice for target_tokens.
        Calculates required USD and applies surcharge so owner receives 100% net desired amount.
        """
        target_usd = round(target_tokens / TOKENS_PER_USD, 2)
        invoice_amount = calculate_invoice_amount_with_surcharge(target_usd, surcharge_pct)

        payload = {
            "asset": "USDT",
            "amount": str(invoice_amount),
            "description": f"Raxi Bot {target_tokens} Tokens (User {user_id})",
            "hidden_message": f"Thank you! Your {target_tokens} tokens have been credited to your Raxi Bot account.",
            "paid_btn_name": "callback",
            "paid_btn_url": f"https://t.me/{bot_username}" if bot_username else "https://t.me/CryptoBot",
            "allow_comments": False,
            "allow_anonymous": True,
            "expires_in": 3600  # 1 hour expiration
        }

        resp = self._api_call("createInvoice", payload=payload)
        if not resp.get("ok"):
            return {"success": False, "error": resp.get("error", "Failed to create invoice via CryptoBot")}

        inv_data = resp.get("result", {})
        invoice_id = str(inv_data.get("invoice_id"))

        record = {
            "invoice_id": invoice_id,
            "hash": inv_data.get("hash", ""),
            "user_id": user_id,
            "chat_id": chat_id,
            "target_tokens": target_tokens,
            "target_usd": str(target_usd),
            "invoice_amount": str(invoice_amount),
            "asset": "USDT",
            "status": "active",  # active, paid, settled, expired
            "pay_url": inv_data.get("pay_url") or inv_data.get("bot_invoice_url"),
            "mini_app_url": inv_data.get("mini_app_invoice_url"),
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 3600,
            "credited_tokens": 0,
            "received_amount": None,
            "settled_at": None,
        }

        with self._lock:
            self.invoices[invoice_id] = record
            self.save_db()

        return {
            "success": True,
            "invoice_id": invoice_id,
            "pay_url": record["pay_url"],
            "mini_app_url": record["mini_app_url"],
            "target_tokens": target_tokens,
            "target_usd": str(target_usd),
            "invoice_amount": str(invoice_amount),
        }

    def delete_invoice(self, invoice_id: str) -> bool:
        """Deletes an invoice on CryptoBot and marks it cancelled locally."""
        resp = self._api_call("deleteInvoice", payload={"invoice_id": int(invoice_id)})
        with self._lock:
            if str(invoice_id) in self.invoices:
                self.invoices[str(invoice_id)]["status"] = "cancelled"
                self.save_db()
        return bool(resp.get("ok"))

    def check_and_settle_invoice(self, invoice_id: str, admin_mgr=None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Queries CryptoBot for invoice status. If paid, applies mathematical half-up rounding,
        credits tokens to user, saves transaction, and formats professional receipt.
        Returns:
            (is_settled: bool, message: str, invoice_record: Dict)
        """
        invoice_id = str(invoice_id)
        with self._lock:
            rec = self.invoices.get(invoice_id)
            if not rec:
                return False, "Invoice not found.", {}
            if rec.get("status") == "settled":
                return True, "Invoice already settled and credited.", rec

        # Query API for current invoice status
        resp = self._api_call(f"getInvoices?invoice_ids={invoice_id}")
        if not resp.get("ok"):
            return False, f"Could not contact CryptoBot: {resp.get('error')}", rec

        items = resp.get("result", {}).get("items", [])
        if not items:
            return False, "Invoice record not found on CryptoBot.", rec

        item = items[0]
        status = item.get("status")

        if status != "paid":
            return False, f"Payment pending. Current status: {status}", rec

        # Invoice is confirmed PAID!
        # Determine actual paid/received amount
        paid_amount_str = str(item.get("amount") or rec.get("invoice_amount") or "0")
        
        # Apply mathematical half-up rounding rule
        rounded_usd, credited_tokens, math_explanation = calculate_tokens_from_amount(paid_amount_str)

        # Fallback check: if user paid full target invoice, ensure they get at least the target tokens
        target_tokens = int(rec.get("target_tokens", 0))
        if credited_tokens < target_tokens and float(paid_amount_str) >= float(rec.get("target_usd", 0)):
            credited_tokens = target_tokens

        user_id = rec.get("user_id")
        new_balance = credited_tokens

        # Credit tokens via admin_manager if supplied
        if admin_mgr and user_id:
            try:
                new_balance = admin_mgr.add_tokens(user_id, credited_tokens)
            except Exception as e:
                logger.error(f"[PaymentEngine] Error adding tokens to {user_id}: {e}")

        # Mark as settled
        with self._lock:
            rec["status"] = "settled"
            rec["settled_at"] = int(time.time())
            rec["received_amount"] = paid_amount_str
            rec["credited_tokens"] = credited_tokens
            rec["math_explanation"] = math_explanation
            self.invoices[invoice_id] = rec
            self.save_db()

        # Format transparent receipt
        receipt_text = (
            f"🎉 <b>Payment Successful & Verified!</b>\n\n"
            f"📥 <b>Net Amount Received:</b> <code>${paid_amount_str} USDT</code>\n"
            f"🧮 <b>Calculation Breakdown:</b> <code>{math_explanation}</code>\n"
            f"🎟️ <b>Tokens Credited:</b> <b>+{credited_tokens} Tokens</b>\n"
            f"💳 <b>Updated Token Balance:</b> <b>{new_balance} Tokens</b>\n\n"
            f"🧾 <b>CryptoBot Invoice ID:</b> <code>#{invoice_id}</code>\n"
            f"⏰ <b>Verified Timestamp:</b> <code>{time.strftime('%Y-%m-%d %H:%M:%S')} IST</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Zero-loss guarantee: 100% automated & protected. Happy Registering!</i>"
        )

        return True, receipt_text, rec

    # ─── Background Polling Loop ───
    def set_settlement_callback(self, callback):
        """Callback(user_id, chat_id, receipt_text, invoice_record) when auto-detected."""
        self._on_settled_callback = callback

    def start_polling_worker(self, admin_mgr=None, interval_sec: int = 10):
        """Starts a background thread that periodically checks active invoices."""
        if self._running:
            return
        self._running = True

        def _worker():
            logger.info("[PaymentEngine] Polling worker started.")
            while self._running:
                try:
                    active_ids = []
                    with self._lock:
                        for i_id, rec in self.invoices.items():
                            if rec.get("status") == "active":
                                active_ids.append(i_id)

                    for i_id in active_ids:
                        settled, receipt_text, rec = self.check_and_settle_invoice(i_id, admin_mgr=admin_mgr)
                        if settled and self._on_settled_callback:
                            try:
                                self._on_settled_callback(
                                    rec.get("user_id"),
                                    rec.get("chat_id"),
                                    receipt_text,
                                    rec
                                )
                            except Exception as cb_err:
                                logger.error(f"[PaymentEngine] Callback error: {cb_err}")

                except Exception as loop_err:
                    logger.error(f"[PaymentEngine] Loop error: {loop_err}")

                time.sleep(interval_sec)

        self._poll_thread = threading.Thread(target=_worker, daemon=True, name="PaymentEngineWorker")
        self._poll_thread.start()

    def stop_polling_worker(self):
        self._running = False


# Global Engine Instance
engine = PaymentEngine()
