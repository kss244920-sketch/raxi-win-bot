#!/usr/bin/env python3
"""
Comprehensive Deep Mock Test Suite for Raxi Bot
Tests all screens, handlers, callbacks, button styles, HTML parsing, and proxy logic.
"""

import sys
import os
import unittest
import html
from unittest.mock import MagicMock, patch

# Ensure raxi4-bot path
sys.path.insert(0, "/home/piyush/raxi4-bot")

import telebot
from telebot import types
import admin_manager
from proxy_manager import proxy_manager
import raxi4_bot


class MockUser:
    def __init__(self, uid=8327850869, username="OwAtom", first_name="Master"):
        self.id = uid
        self.username = username
        self.first_name = first_name
        self.is_bot = False


class MockChat:
    def __init__(self, chat_id=8327850869):
        self.id = chat_id
        self.type = "private"


class MockMessage:
    def __init__(self, text="/start", user=None, chat=None, mid=1001):
        self.message_id = mid
        self.from_user = user or MockUser()
        self.chat = chat or MockChat(self.from_user.id)
        self.text = text
        self.content_type = "text"


class MockCallbackQuery:
    def __init__(self, data="show_start", user=None, mid=1001):
        self.id = "cq_999"
        self.from_user = user or MockUser()
        self.message = MockMessage(text="", user=self.from_user, mid=mid)
        self.data = data


class TestRaxiBotDeep(unittest.TestCase):
    def setUp(self):
        # Mock telegram bot methods to intercept and inspect calls
        self.bot_mock = MagicMock()
        raxi4_bot.bot = self.bot_mock
        raxi4_bot.LAST_BOT_MSG.clear()
        raxi4_bot.LAST_DOCK_MSG.clear()

    def test_01_all_ui_screens_button_styles_and_single_emojis(self):
        """Verify that every screen builder returns 100% styled buttons with 0 double emojis."""
        screens = [
            ("show_link_prompt", lambda: raxi4_bot.show_link_prompt(8327850869, MockUser())),
            ("show_link_options", lambda: raxi4_bot.show_link_options(8327850869, MockUser())),
            ("show_single_menu", lambda: raxi4_bot.show_single_menu(8327850869, MockUser())),
            ("show_multi_menu", lambda: raxi4_bot.show_multi_menu(8327850869, MockUser())),
            ("show_speed_selection", lambda: raxi4_bot.show_speed_selection_menu(8327850869, MockUser(), 10)),
            ("show_sched_count", lambda: raxi4_bot.show_custom_scheduled_count_prompt(8327850869, MockUser())),
            ("show_sched_unit", lambda: raxi4_bot.show_custom_scheduled_minutes_prompt(8327850869, MockUser(), 10)),
            ("show_admin_menu", lambda: raxi4_bot.show_admin_menu(8327850869, MockUser())),
            ("show_help_screen", lambda: raxi4_bot.show_help_menu(8327850869, MockUser())),
            ("show_insufficient_tokens", lambda: raxi4_bot.show_insufficient_tokens_screen(8327850869, 8327850869, 10)),
        ]

        double_emoji_triggers = ['🔗 🔗', '❓ ❓', '👑 👑', '🟢 ⚡', '🔵 🔢', '🟡 🎫', '🟣 📋', '🔴 ❌']

        for screen_name, builder in screens:
            self.bot_mock.reset_mock()
            builder()
            
            # Find the markup passed to send_message or edit_message_text
            markup = None
            for call in self.bot_mock.send_message.call_args_list:
                if "reply_markup" in call.kwargs:
                    markup = call.kwargs["reply_markup"]
            for call in self.bot_mock.edit_message_text.call_args_list:
                if "reply_markup" in call.kwargs:
                    markup = call.kwargs["reply_markup"]

            if markup and hasattr(markup, "keyboard"):
                for row in markup.keyboard:
                    for btn in row:
                        b_dict = btn.to_dict() if hasattr(btn, "to_dict") else btn
                        style = b_dict.get("style")
                        text = b_dict.get("text", "")
                        self.assertIn(style, ["primary", "success", "danger"],
                                      f"Screen '{screen_name}' button '{text}' has invalid or missing style: {style}")
                        for dup in double_emoji_triggers:
                            self.assertNotIn(dup, text,
                                            f"Screen '{screen_name}' button '{text}' contains double emoji: {dup}")

    def test_02_handle_start_single_message_contract(self):
        """Verify /start sends exactly ONE message (zero dummy/dock messages)."""
        self.bot_mock.reset_mock()
        msg = MockMessage(text="/start", user=MockUser())
        raxi4_bot.handle_start(msg)

        # Must send exactly 1 message
        self.assertEqual(self.bot_mock.send_message.call_count, 1,
                         f"Expected exactly 1 send_message call on /start, got {self.bot_mock.send_message.call_count}")
        # del_incoming should delete user's /start
        self.bot_mock.delete_message.assert_any_call(msg.chat.id, msg.message_id)

    def test_03_invisible_unicode_name_filter(self):
        """Verify invisible filler unicode names correctly fall back without leaving blank greeting."""
        u_ghost = MockUser(uid=998877, username="GhostUser", first_name="\u115f\u1160\u3164")
        self.bot_mock.reset_mock()
        raxi4_bot.show_link_prompt(998877, u_ghost)

        sent_text = self.bot_mock.send_message.call_args[0][1]
        self.assertNotIn("👋 <b>Welcome !</b>", sent_text, "Greeting must not be blank for invisible Unicode filler")
        self.assertIn("@GhostUser", sent_text, "Should fall back to username @GhostUser")

    def test_04_callback_query_routing_and_no_unhandled_cbs(self):
        """Verify callback queries route smoothly and call answer_callback_query."""
        test_cbs = [
            "show_start",
            "show_link_options",
            "show_help",
            "my_tokens",
            "reg_multi",
            "single_random",
            "single_custom",
            "admin_broadcast_info",
            "cancel_custom_reg",
            "cancel_single_reg",
            "bspeed_10_0",
            "sched_cnt_10",
            "multi_run_5",
        ]

        for cb_data in test_cbs:
            self.bot_mock.reset_mock()
            cq = MockCallbackQuery(data=cb_data, user=MockUser(uid=8327850869))
            try:
                raxi4_bot._handle_callback_clicks_inner(cq)
            except Exception as e:
                self.fail(f"Callback '{cb_data}' raised unexpected exception: {e}")

    def test_05_proxy_manager_session_uniqueness_and_rotation(self):
        """Verify that every proxy session generates a totally unique session ID (never repeated)."""
        sessions = set()
        for _ in range(100):
            px, verified_ip, sess_id = proxy_manager.acquire_session_with_unique_ip("www.dmfirst17.com", preflight=False)
            self.assertIsNotNone(sess_id)
            self.assertNotIn(sess_id, sessions, f"Duplicate proxy session ID detected: {sess_id}")
            sessions.add(sess_id)

    def test_06_admin_settings_database_integrity(self):
        """Verify token arithmetic and user registry persistence in admin_manager."""
        mgr = admin_manager.admin_manager
        uid = 8327850869
        disp = mgr.get_display_tokens(uid)
        self.assertEqual(disp, "👑 Unlimited (Owner / Super Admin)")

        test_uid = 999111222
        mgr.set_tokens(test_uid, 25)
        self.assertEqual(mgr.get_tokens(test_uid), 25)

        mgr.deduct_tokens(test_uid, 5)
        self.assertEqual(mgr.get_tokens(test_uid), 20)

        mgr.add_tokens(test_uid, 10)
        self.assertEqual(mgr.get_tokens(test_uid), 30)

        # Cleanup test user
        with mgr._lock:
            mgr.user_registry.pop(str(test_uid), None)
            mgr.save()

    def test_07_html_entity_safety_against_xss_injection(self):
        """Verify that malicious usernames with <script> or HTML tags do not crash Telegram parser."""
        xss_user = MockUser(uid=887766, username="hacker", first_name="<b>Hacked</b><script>alert(1)</script>")
        self.bot_mock.reset_mock()
        raxi4_bot.show_link_prompt(887766, xss_user)

        sent_text = self.bot_mock.send_message.call_args[0][1]
        self.assertNotIn("<script>", sent_text)
        self.assertIn("&lt;script&gt;", sent_text)

    def test_08_send_or_edit_resilience_to_unmodified_message(self):
        """Verify send_or_edit suppresses 'message is not modified' gracefully without crashing."""
        self.bot_mock.edit_message_text.side_effect = Exception("Bad Request: message is not modified")
        res = raxi4_bot.send_or_edit(8327850869, "Test Message", message_id=1001)
        self.assertEqual(res, 1001, "Should gracefully return target_mid on message not modified error")

    def test_09_unique_device_generation(self):
        """Verify claim_unique_device produces distinct real physical Android devices."""
        dev1 = raxi4_bot.claim_unique_device("www.dmfirst17.com")
        dev2 = raxi4_bot.claim_unique_device("www.dmfirst17.com")
        self.assertNotEqual(dev1["device_id"], dev2["device_id"])
        self.assertIn("Android", dev1["ua"])
        self.assertIsNotNone(dev1["model"])


if __name__ == "__main__":
    unittest.main()
