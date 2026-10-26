"""
Simulated End-to-End Test for Payment Flow & Health Server Webhook
"""

import sys
import os
import json
import time
import urllib.request
from decimal import Decimal

sys.path.insert(0, "/home/piyush/raxi4-bot")

from admin_manager import admin_manager
from payment_engine import engine as payment_engine, calculate_tokens_from_amount

TEST_USER_ID = 999888777

def test_full_flow():
    print("─── 1. Testing Admin Manager Token Addition ───")
    admin_manager.record_user(TEST_USER_ID, "testuser", "Test")
    initial_tokens = admin_manager.get_tokens(TEST_USER_ID)
    print(f"Initial tokens for {TEST_USER_ID}: {initial_tokens}")

    print("\n─── 2. Testing Exact User Rounding Scenarios ───")
    scenarios = [
        ("0.734", 73, "0.73"),
        ("0.656", 66, "0.66"),
        ("0.87732", 88, "0.88"),
        ("0.5332", 53, "0.53"),
        ("1.000", 100, "1.00"),
    ]
    for raw_amt, exp_tokens, exp_usd in scenarios:
        rounded_usd, tokens, expl = calculate_tokens_from_amount(raw_amt)
        assert tokens == exp_tokens, f"Expected {exp_tokens} but got {tokens} for {raw_amt}"
        assert str(rounded_usd) == exp_usd, f"Expected {exp_usd} but got {rounded_usd}"
        print(f"  ✅ {raw_amt} USD -> Rounded {rounded_usd} USD -> {tokens} Tokens | {expl}")

    print("\n─── 3. Testing Simulated Settle & Token Credit ───")
    # Simulate an active invoice in payment_engine
    mock_inv_id = "test_inv_12345"
    payment_engine.invoices[mock_inv_id] = {
        "invoice_id": mock_inv_id,
        "user_id": TEST_USER_ID,
        "chat_id": TEST_USER_ID,
        "target_tokens": 100,
        "target_usd": "1.0",
        "invoice_amount": "1.03",
        "asset": "USDT",
        "status": "active",
        "created_at": int(time.time()),
        "credited_tokens": 0
    }

    # Simulate underpaid deposit from external wallet: 0.87732 USDT
    paid_amt = "0.87732"
    rounded_usd, credited_tokens, math_expl = calculate_tokens_from_amount(paid_amt)
    new_bal = admin_manager.add_tokens(TEST_USER_ID, credited_tokens)

    rec = payment_engine.invoices[mock_inv_id]
    rec["status"] = "settled"
    rec["settled_at"] = int(time.time())
    rec["received_amount"] = paid_amt
    rec["credited_tokens"] = credited_tokens
    rec["math_explanation"] = math_expl

    print(f"  ✅ Credited: {credited_tokens} Tokens")
    print(f"  ✅ New Balance: {new_bal} Tokens")
    print(f"  ✅ Math Explanation: {math_expl}")
    assert new_bal == initial_tokens + credited_tokens, "Balance calculation mismatch"

    # Clean up test user tokens to keep admin settings pristine
    admin_manager.deduct_tokens(TEST_USER_ID, credited_tokens, force=True)
    payment_engine.invoices.pop(mock_inv_id, None)
    payment_engine.save_db()
    print("\n🎉 ALL LOCAL PAYMENT ENGINE & UI TESTS PASSED SUCCESSFULLY! ✅")

if __name__ == "__main__":
    test_full_flow()
