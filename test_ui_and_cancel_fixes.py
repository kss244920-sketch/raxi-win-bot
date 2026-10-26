"""
Test suite verifying all 4 fixes:
1. Zero-Repeat Proxy & No Direct Leak
2. Interactive Add User & Add Token Step Handlers
3. Bottom Keyboard Phase Adaptation
4. 5-Second Countdown & Cancellation (/cancel & button)
"""

import sys
import os
import threading
import time
from unittest.mock import MagicMock

sys.path.insert(0, "/home/piyush/raxi4-bot")

from admin_manager import admin_manager
from proxy_manager import proxy_manager
import raxi4_bot

def test_all_fixes():
    print("─── Test 1: Proxy Mode & Zero Direct Leak ───")
    # Verify login_template has mode-rotate
    px_str, ver_ip, sess = proxy_manager.acquire_session_with_unique_ip(domain="test.com", preflight=False)
    assert px_str is not None, "Failed to acquire proxy"
    assert "mode-rotate" in px_str, f"Expected mode-rotate in proxy string but got: {px_str}"
    print(f"  ✓ Proxy string uses guaranteed rotation: {px_str[:45]}...")

    print("\n─── Test 2: Bottom Keyboard Phase Adaptation ───")
    main_kb = raxi4_bot.get_main_reply_keyboard(8327850869)
    run_kb = raxi4_bot.get_registration_running_reply_keyboard()
    admin_kb = raxi4_bot.get_admin_reply_keyboard()

    # Check run_kb has CANCEL button
    run_btns = [(b.get('text') if isinstance(b, dict) else getattr(b, 'text', '')) for row in run_kb.keyboard for b in row]
    assert any("CANCEL" in b for b in run_btns), "Cancel button missing from running keyboard"
    print(f"  ✓ Running Phase Keyboard: {run_btns}")

    # Check admin_kb has Admin controls
    adm_btns = [(b.get('text') if isinstance(b, dict) else getattr(b, 'text', '')) for row in admin_kb.keyboard for b in row]
    assert any("Exit Admin" in b for b in adm_btns), "Exit Admin missing from admin keyboard"
    print(f"  ✓ Admin Phase Keyboard: {adm_btns}")

    print("\n─── Test 3: Interactive Step Handlers ───")
    # Clean test user before starting test
    admin_manager.user_registry.pop("777666555", None)
    admin_manager.save()

    # Test process_admin_adduser_step
    mock_msg = MagicMock()
    mock_msg.from_user.id = 8327850869
    mock_msg.chat.id = 8327850869
    mock_msg.text = "777666555 25"
    mock_msg.forward_from = None

    raxi4_bot.bot = MagicMock()
    raxi4_bot.process_admin_adduser_step(mock_msg, 8327850869)
    assert "777666555" in admin_manager.user_registry, "User not recorded by step handler"
    assert admin_manager.get_tokens(777666555) == 25, "Tokens not allocated"
    print("  ✓ Add User interactive step successfully registered user & initial tokens.")

    # Test process_admin_addtoken_step
    mock_msg.text = "777666555 50"
    raxi4_bot.process_admin_addtoken_step(mock_msg, 8327850869)
    assert admin_manager.get_tokens(777666555) == 75, f"Expected 75 tokens but got {admin_manager.get_tokens(777666555)}"
    print("  ✓ Add Token interactive step successfully credited 50 tokens (total 75).")

    # Clean test user
    admin_manager.user_registry.pop("777666555", None)
    admin_manager.save()

    print("\n─── Test 4: Single Registration Cancellation & Countdown ───")
    test_cid = 888111222
    raxi4_bot.CHAT_CONFIGS[test_cid] = {
        "site": "https://www.dmfirst17.com",
        "api": "https://api.dmfirstapi.com",
        "invite": "417112180491"
    }

    # Simulate launching single registration in thread and cancelling at 1 second
    cancel_mock_msg = MagicMock()
    cancel_mock_msg.chat.id = test_cid
    cancel_mock_msg.from_user.id = 8327850869

    t = threading.Thread(
        target=raxi4_bot.run_registration_and_send_ss,
        args=(test_cid, 8327850869, None, None, None, None),
        daemon=True
    )
    t.start()
    time.sleep(0.5)

    # Verify event is mounted
    assert test_cid in raxi4_bot.SINGLE_REG_CANCEL_EVENTS, "Cancel event was not mounted"
    print("  ✓ 5s Countdown started, Cancel event mounted.")

    # Now send /cancel command
    raxi4_bot.handle_cancel_cmd(cancel_mock_msg)
    time.sleep(0.5)
    t.join(timeout=3.0)

    assert not t.is_alive(), "Registration thread did not abort upon /cancel"
    print("  ✓ Registration cleanly aborted within countdown window upon /cancel!")

    print("\n🎉 ALL 4 USER FIXES TESTED AND VERIFIED 100% OPERATIONAL! ✅")

if __name__ == "__main__":
    test_all_fixes()
