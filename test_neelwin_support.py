import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import raxi4_bot

class TestNeelwinSupport(unittest.TestCase):
    def test_neelwin_url_discovery(self):
        url = "https://neelwin77.com/?code=334042108015"
        info = raxi4_bot.detect_and_parse_referral_link(url)
        self.assertIsNotNone(info)
        self.assertEqual(info["api_type"], "neelwin")
        self.assertEqual(info["invite"], "334042108015")
        self.assertEqual(info["site"], "https://neelwin77.com")
        self.assertEqual(info["api"], "https://neelwin77.com/api")
        self.assertFalse(info["sms_required"])

    def test_neelwin_sms_check(self):
        res = raxi4_bot.check_platform_sms_and_mirrors("https://neelwin77.com/api", "https://neelwin77.com", api_type="neelwin")
        self.assertEqual(res["api_type"], "neelwin")
        self.assertFalse(res["sms_required"])

    def test_neelwin_registration_flow(self):
        info = raxi4_bot.detect_and_parse_referral_link("https://neelwin77.com/?code=334042108015")
        res = raxi4_bot.auto_register_account(
            site=info["site"],
            api=info["api"],
            invite=info["invite"],
            api_type=info["api_type"]
        )
        print("Registration result:", res)
        self.assertTrue(res.get("ok"))
        self.assertIsNotNone(res.get("uid"))
        self.assertIsNotNone(res.get("token"))

if __name__ == "__main__":
    unittest.main()
