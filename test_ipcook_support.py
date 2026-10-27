import unittest
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from proxy_manager import ProxyManager

class TestIPcookSupport(unittest.TestCase):
    def setUp(self):
        self.pm = ProxyManager()

    def test_setup_ipcook_account(self):
        res = self.pm.setup_ipcook_account(
            username="testuser",
            password="testpassword",
            country="IN",
            traffic_mb=100.0
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("account", {}).get("provider"), "ipcook")
        self.assertEqual(res.get("account", {}).get("proxy_host"), "geo.ipcook.com:32345")
        self.assertEqual(res.get("account", {}).get("login_template"), "testuser-IN-session-{session_id}")
        self.assertEqual(res.get("account", {}).get("balance_traffic"), 100 * 1024 * 1024)

    def test_purge_protection_for_ipcook(self):
        # Ensure IPcook accounts are never purged by the SX.ORG expiration checker
        self.pm.setup_ipcook_account("keepme", "pwd123", traffic_mb=50)
        purged = self.pm.purge_expired_sx_accounts()
        self.assertNotIn("ipcook_keepme", purged)
        accs = [a for a in self.pm.get_active_sx_accounts() if a.get("api_key") == "ipcook_keepme"]
        self.assertEqual(len(accs), 1)

    def test_record_traffic_consumption(self):
        self.pm.setup_ipcook_account("usertraffic", "pwd123", traffic_mb=10)
        before = next(a["balance_traffic"] for a in self.pm.sx_config["accounts"] if a["api_key"] == "ipcook_usertraffic")
        self.pm.record_traffic_consumption("usertraffic-IN-session-123:pwd123@geo.ipcook.com:32345", bytes_spent=3500)
        after = next(a["balance_traffic"] for a in self.pm.sx_config["accounts"] if a["api_key"] == "ipcook_usertraffic")
        self.assertEqual(after, before - 3500)

if __name__ == "__main__":
    unittest.main()
