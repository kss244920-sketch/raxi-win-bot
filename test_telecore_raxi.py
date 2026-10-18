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

    # 4. Maintenance mode - Regular user blocked
    admin_manager.set_maintenance_mode(True)
    res_maint = telecore_message_guard(mock_bot, mock_msg)
    assert isinstance(res_maint, CancelUpdate), "Maintenance mode must block regular user"
    print("  ✓ Maintenance mode blocked regular user.")

    # 4b. Maintenance mode - Regular Admin blocked (Owner-only rule)
    reg_admin_user = MagicMock()
    reg_admin_user.id = 6217522461
    reg_admin_user.is_bot = False
    mock_reg_admin_msg = MagicMock()
    mock_reg_admin_msg.from_user = reg_admin_user
    res_reg_admin = telecore_message_guard(mock_bot, mock_reg_admin_msg)
    assert isinstance(res_reg_admin, CancelUpdate), "Maintenance mode must block regular admins"
    print("  ✓ Maintenance mode blocked regular admin cleanly.")

    # 5. Owner / Super Admin bypasses maintenance mode
    admin_user = MagicMock()
    admin_user.id = 8327850869
    admin_user.is_bot = False
    mock_admin_msg = MagicMock()
    mock_admin_msg.from_user = admin_user

    res_admin = telecore_message_guard(mock_bot, mock_admin_msg)
    assert res_admin is None, "Owner should bypass maintenance mode"
    print("  ✓ Super Admin / Owner bypassed maintenance mode cleanly.")

    # 6. Deep Test: Background active session halts when maintenance is active
    from raxi4_bot import ACTIVE_SESSIONS, ACTIVE_SESSIONS_LOCK, register_active_session, is_session_stop_requested, unregister_active_session, halt_non_owner_sessions, bot
    from telebot import types

    admin_manager.set_maintenance_mode(False)
    # Register mock session for regular admin (6217522461)
    register_active_session(chat_id=999111, user_id=6217522461, count=10, site="example.com", invite="123")
    assert not is_session_stop_requested(999111), "Session should not be stopped yet"

    # Now activate maintenance
    admin_manager.set_maintenance_mode(True)
    # is_session_stop_requested must return True for non-owner
    assert is_session_stop_requested(999111) is True, "is_session_stop_requested must stop regular admin session"
    halt_non_owner_sessions()
    with ACTIVE_SESSIONS_LOCK:
        assert ACTIVE_SESSIONS[999111]["stop_requested"] is True
    unregister_active_session(999111)
    print("  ✓ Non-owner background registration session safely halted.")

    # 7. Deep End-to-End Pipeline Test: Verify TeleBot BaseMiddleware truly cancels handler execution
    executed_handlers = []

    @bot.message_handler(commands=["deep_audit_test"])
    def dummy_handler(m):
        executed_handlers.append((m.from_user.id, m.text))

    # Send update from regular admin while maintenance is active
    upd_admin = types.Update.de_json({
        "update_id": int(time.time() * 1000) % 100000,
        "message": {
            "message_id": 9991,
            "from": {"id": 6217522461, "is_bot": False, "first_name": "Admin"},
            "chat": {"id": 6217522461, "type": "private"},
            "date": int(time.time()),
            "text": "/deep_audit_test"
        }
    })
    bot.process_new_updates([upd_admin])

    # Send update from owner while maintenance is active
    upd_owner = types.Update.de_json({
        "update_id": (int(time.time() * 1000) + 1) % 100000,
        "message": {
            "message_id": 9992,
            "from": {"id": 8327850869, "is_bot": False, "first_name": "Owner"},
            "chat": {"id": 8327850869, "type": "private"},
            "date": int(time.time()),
            "text": "/deep_audit_test"
        }
    })
    bot.process_new_updates([upd_owner])
    time.sleep(0.15)

    assert executed_handlers == [(8327850869, "/deep_audit_test")], f"Expected only Owner execution, got: {executed_handlers}"
    print("  ✓ Full TeleBot Pipeline verified: Regular Admin's command TRULY CANCELLED, Owner ALLOWED!")

    # Reset
    admin_manager.set_maintenance_mode(False)
    admin_manager.rate_limit_seconds = 1.0
    print("🎉 ALL RAXI4 TELECORE GUARDS & DEEP AUDITS VERIFIED 100% SUCCESSFULLY!\n")


if __name__ == "__main__":
    test_raxi_guards()
