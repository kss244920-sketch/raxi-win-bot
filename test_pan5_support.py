import unittest
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

import raxi4_bot

class TestPan5Support(unittest.TestCase):
    def test_pan5_url_discovery(self):
        url = "https://www.pan5.cc/index?invite=96GWL924FP"
        info = raxi4_bot.detect_and_parse_referral_link(url)
        self.assertIsNotNone(info)
        self.assertEqual(info["api_type"], "tasyee")
        self.assertEqual(info["invite"], "96GWL924FP")
        self.assertFalse(info["sms_required"])
        self.assertNotIn("whatsapp", info["api"])

    def test_check_platform_sms_and_mirrors(self):
        res = raxi4_bot.check_platform_sms_and_mirrors("https://www.pan5.cc/api", "https://www.pan5.cc", api_type="tasyee")
        self.assertEqual(res["api_type"], "tasyee")
        self.assertFalse(res["sms_required"])

if __name__ == "__main__":
    unittest.main()
