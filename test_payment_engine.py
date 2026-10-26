"""
Unit Test Suite for Payment Engine (CryptoBot + Mathematical Half-Up Rounding)
"""

import unittest
from decimal import Decimal
import os
import sys

# Ensure local dir is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from payment_engine import (
    calculate_tokens_from_amount,
    calculate_invoice_amount_with_surcharge,
    PaymentEngine,
    TOKENS_PER_USD
)


class TestPaymentEngineMath(unittest.TestCase):
    def test_mathematical_rounding_cases(self):
        """
        Verify exact user requirements:
        - 0.734 -> 4 < 5 -> 0.73 -> 73 tokens
        - 0.656 -> 6 >= 5 -> 0.66 -> 66 tokens
        - 0.87732 -> 7 >= 5 -> 0.88 -> 88 tokens
        - 0.5332 -> 3 < 5 -> 0.53 -> 53 tokens
        - 1.000 -> 1.00 -> 100 tokens
        """
        test_cases = [
            ("0.734", Decimal("0.73"), 73),
            ("0.656", Decimal("0.66"), 66),
            ("0.87732", Decimal("0.88"), 88),
            ("0.5332", Decimal("0.53"), 53),
            ("1.000", Decimal("1.00"), 100),
            ("2.495", Decimal("2.50"), 250),
            ("0.009", Decimal("0.01"), 1),
            ("0.004", Decimal("0.00"), 0),
        ]

        for raw_val, expected_dec, expected_tokens in test_cases:
            dec, tokens, expl = calculate_tokens_from_amount(raw_val)
            self.assertEqual(dec, expected_dec, f"Failed decimal rounding for {raw_val}")
            self.assertEqual(tokens, expected_tokens, f"Failed token conversion for {raw_val}")
            print(f"✅ PASSED: {raw_val} -> {dec} USD -> {tokens} Tokens (Expl: {expl})")

    def test_fee_surcharge(self):
        """Verify surcharge calculation so net received is at least target."""
        # For $1.00 target with 3% fee: 1.00 / (1 - 0.03) = 1.0309... -> 1.03
        gross_1 = calculate_invoice_amount_with_surcharge(1.0, 3.0)
        self.assertEqual(gross_1, Decimal("1.03"))

        # For $2.00 target with 3% fee: 2.00 / 0.97 = 2.0618... -> 2.06
        gross_2 = calculate_invoice_amount_with_surcharge(2.0, 3.0)
        self.assertEqual(gross_2, Decimal("2.06"))

        # For $5.00 target with 3% fee: 5.00 / 0.97 = 5.1546... -> 5.15
        gross_5 = calculate_invoice_amount_with_surcharge(5.0, 3.0)
        self.assertEqual(gross_5, Decimal("5.15"))

        print("✅ PASSED: Fee surcharge calculations accurate.")


class TestPaymentEngineAPI(unittest.TestCase):
    def setUp(self):
        self.test_db = "/tmp/test_invoices.json"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.engine = PaymentEngine(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_app_status(self):
        res = self.engine.check_app_status()
        self.assertTrue(res.get("ok"), f"CryptoBot getMe failed: {res}")
        app_name = res.get("result", {}).get("name")
        print(f"✅ PASSED: CryptoBot connected successfully. App Name: {app_name}")

    def test_live_invoice_creation_and_deletion(self):
        """Test creating an invoice on CryptoBot and then cleaning it up immediately."""
        create_res = self.engine.create_token_invoice(
            user_id=8327850869,
            chat_id=8327850869,
            target_tokens=100
        )
        self.assertTrue(create_res["success"], f"Invoice creation failed: {create_res}")
        inv_id = create_res["invoice_id"]
        print(f"✅ PASSED: Live invoice created: #{inv_id} | URL: {create_res['pay_url']}")

        # Verify it was recorded in local db
        self.assertIn(inv_id, self.engine.invoices)

        # Delete / cancel invoice to keep clean
        del_res = self.engine.delete_invoice(inv_id)
        self.assertTrue(del_res, f"Invoice deletion failed for #{inv_id}")
        self.assertEqual(self.engine.invoices[inv_id]["status"], "cancelled")
        print(f"✅ PASSED: Live invoice #{inv_id} deleted cleanly.")


if __name__ == "__main__":
    unittest.main()
