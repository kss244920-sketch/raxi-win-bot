import time
from unittest.mock import MagicMock
from telebot.handler_backends import CancelUpdate

from admin_manager import admin_manager
from raxi4_bot import telecore_message_guard, telecore_callback_guard, _user_last_action_ts


def test_raxi_guards():
    print("--- [TEST] Testing raxi4-bot TeleCore Guards ---")
    mock_bot = MagicMock()

    # Regular user mock
    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.is_bot = False

    mock_msg = MagicMock()
    mock_msg.from_user = mock_user

    # 1. Normal allowed
    admin_manager.set_maintenance_mode(False)
    admin_manager.set_rate_limit_enabled(True)
    admin_manager.rate_limit_seconds = 0.5
    _user_last_action_ts.clear()

    res = telecore_message_guard(mock_bot, mock_msg)
    assert res is None, "Normal message should not be cancelled"
    print("  ✓ Initial message passed through.")

    # 2. Flood detection
    res2 = telecore_message_guard(mock_bot, mock_msg)
    assert isinstance(res2, CancelUpdate), "Rapid flood should return CancelUpdate"
    print("  ✓ Anti-flood caught rapid spam and cancelled update.")

    # 3. Spaced message
    time.sleep(0.55)
    res3 = telecore_message_guard(mock_bot, mock_msg)
    assert res3 is None, "Spaced message should be allowed"
    print("  ✓ Spaced message allowed through.")

    # 4. Maintenance mode
    admin_manager.set_maintenance_mode(True)
    res_maint = telecore_message_guard(mock_bot, mock_msg)
    assert isinstance(res_maint, CancelUpdate), "Maintenance mode must block regular user"
    print("  ✓ Maintenance mode blocked regular user.")

    # 5. Admin bypasses maintenance mode
    admin_user = MagicMock()
    admin_user.id = 8327850869
    admin_user.is_bot = False
    mock_admin_msg = MagicMock()
    mock_admin_msg.from_user = admin_user

    res_admin = telecore_message_guard(mock_bot, mock_admin_msg)
    assert res_admin is None, "Admin should bypass maintenance mode"
    print("  ✓ Super Admin bypassed maintenance mode cleanly.")

    # Reset
    admin_manager.set_maintenance_mode(False)
    admin_manager.rate_limit_seconds = 1.0
    print("🎉 ALL RAXI4 TELECORE GUARDS VERIFIED SUCCESSFULLY!\n")


if __name__ == "__main__":
    test_raxi_guards()
