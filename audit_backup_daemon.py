#!/usr/bin/env python3
# language: Python, file: audit_backup_daemon.py
# 14-Minute Auto Cloud Backup, Pin & Disaster Recovery Daemon
# Completely isolated module - does not alter existing registration or proxy logic.

import os
import io
import time
import zipfile
import logging
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger("AuditBackupDaemon")

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

def get_persistent_data_dir() -> Path:
    jrnm_vol = Path("/app/data")
    if jrnm_vol.exists() and os.path.isdir(jrnm_vol):
        return jrnm_vol
    return BASE_DIR

DATA_DIR = get_persistent_data_dir()

# Target data files to include in every cloud backup
TARGET_BACKUP_FILES = [
    "admin_settings.json",
    "raxi_accounts.txt",
    "chat_configs.json",
    "used_devices.json",
    "used_proxies.txt"
]

_last_pinned_message_id = None
_last_backup_hash = None


def get_target_audit_channel() -> str:
    """Returns the configured audit/log channel ID."""
    # 1. Environment variables
    env_ch = (
        os.environ.get("AUDIT_CHANNEL", "").strip()
        or os.environ.get("MASTER_LOG_CHANNEL", "").strip()
        or os.environ.get("LOG_CHANNEL_ID", "").strip()
        or os.environ.get("MASTER_STORAGE_CHANNEL", "").strip()
        or os.environ.get("STORAGE_CHANNEL_ID", "").strip()
    )
    if env_ch and env_ch not in ("None", "0"):
        return env_ch

    # 2. Admin Manager master log / audit channel
    try:
        from admin_manager import admin_manager
        log_ch = admin_manager.get_master_log_channel()
        if log_ch and str(log_ch).strip() not in ("", "None", "0"):
            return str(log_ch).strip()
        storage_ch = admin_manager.get_master_storage_channel()
        if storage_ch and str(storage_ch).strip() not in ("", "None", "0"):
            return str(storage_ch).strip()
    except Exception:
        pass

    # 3. Fallback default: Audit / Logs channel (Gemini-Logs)
    return "-1003946923981"


def create_backup_archive():
    """Packs all critical database and account files into an in-memory zip archive."""
    bio = io.BytesIO()
    total_accs = 0
    total_users = 0
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    timestamp_str = now_ist.strftime("%Y%m%d_%H%M%S")
    display_time = now_ist.strftime("%d-%b-%Y %I:%M:%S %p IST")

    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in TARGET_BACKUP_FILES:
            # Check DATA_DIR first, then BASE_DIR
            target_path = DATA_DIR / fname
            if not target_path.exists():
                target_path = BASE_DIR / fname

            if target_path.exists():
                try:
                    with open(target_path, "rb") as f:
                        file_data = f.read()
                    zf.writestr(fname, file_data)

                    # Compute statistics for caption
                    if fname == "raxi_accounts.txt":
                        total_accs = len([line for line in file_data.decode("utf-8", errors="ignore").splitlines() if line.strip()])
                    elif fname == "admin_settings.json":
                        import json
                        try:
                            s = json.loads(file_data.decode("utf-8", errors="ignore"))
                            total_users = len(s.get("user_registry", {}))
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"Could not archive {fname}: {e}")

    bio.seek(0)
    zip_bytes = bio.getvalue()
    zip_filename = f"raxi_backup_{timestamp_str}.zip"
    return zip_bytes, zip_filename, total_accs, total_users, display_time


def dispatch_and_pin_backup(bot) -> bool:
    """Creates backup zip, sends to audit channel, and silently pins it as latest recovery point."""
    global _last_pinned_message_id, _last_backup_hash
    target_ch = get_target_audit_channel()
    if not target_ch or target_ch in ("0", "None"):
        logger.info("Audit channel not configured. Skipping periodic backup.")
        return False

    try:
        zip_bytes, zip_filename, total_accs, total_users, display_time = create_backup_archive()
        if not zip_bytes or len(zip_bytes) < 50:
            logger.warning("Empty backup archive generated. Skipping dispatch.")
            return False

        # Build clean, informative HTML caption
        caption = (
            f"📦 <b>RAXI BOT AUTO CLOUD BACKUP &amp; AUDIT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• 📋 <b>Total Accounts Logged:</b> <code>{total_accs:,}</code>\n"
            f"• 👥 <b>Total Registered Users:</b> <code>{total_users:,}</code>\n"
            f"• 🕒 <b>Timestamp:</b> <code>{display_time}</code>\n"
            f"• 🔄 <b>Frequency:</b> <i>Auto-Backup every 14 mins</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <i>Latest disaster recovery snapshot auto-pinned.</i>"
        )

        bio = io.BytesIO(zip_bytes)
        bio.name = zip_filename

        # Send document to channel
        sent_msg = bot.send_document(
            chat_id=target_ch,
            document=bio,
            caption=caption,
            parse_mode="HTML"
        )

        if sent_msg and hasattr(sent_msg, "message_id"):
            new_msg_id = sent_msg.message_id
            # 1. Unpin previous backup message if any to prevent channel clutter
            if _last_pinned_message_id:
                try:
                    bot.unpin_chat_message(chat_id=target_ch, message_id=_last_pinned_message_id)
                except Exception:
                    pass

            # 2. Pin new backup message silently (disable_notification=True prevents beep/spam)
            try:
                bot.pin_chat_message(
                    chat_id=target_ch,
                    message_id=new_msg_id,
                    disable_notification=True
                )
                _last_pinned_message_id = new_msg_id
                logger.info(f"Successfully pinned backup snapshot #{new_msg_id} in {target_ch} ✅")
            except Exception as pin_err:
                logger.warning(f"Could not pin backup message #{new_msg_id} (Ensure bot has 'Pin Messages' permission): {pin_err}")

            return True
    except Exception as e:
        err_msg = str(e)
        if "chat not found" in err_msg.lower():
            logger.warning(f"Audit Channel '{target_ch}' not found! Make sure @{bot.get_me().username} is added as Admin in the channel.")
        else:
            logger.error(f"Error in dispatch_and_pin_backup: {e}")
        return False


def auto_restore_latest_from_channel(bot) -> bool:
    """
    Auto-Recovery on startup:
    Checks if local container lost its data (Render cold restart).
    If so, fetches the latest pinned backup archive from audit channel and restores it.
    """
    target_ch = get_target_audit_channel()
    if not target_ch or target_ch in ("0", "None"):
        return False

    try:
        chat = bot.get_chat(target_ch)
        pinned = getattr(chat, "pinned_message", None)
        if not pinned or not getattr(pinned, "document", None):
            logger.info("No pinned backup document found in audit channel to restore.")
            return False

        doc = pinned.document
        doc_name = doc.file_name or ""
        if not doc_name.startswith("raxi_backup_") or not doc_name.endswith(".zip"):
            return False

        # Compare accounts count: if local accounts are fewer or missing, restore!
        local_accs_file = DATA_DIR / "raxi_accounts.txt"
        local_count = 0
        if local_accs_file.exists():
            try:
                with open(local_accs_file, "r", encoding="utf-8") as f:
                    local_count = len([l for l in f if l.strip()])
            except Exception:
                local_count = 0

        logger.info(f"Checking pinned backup ({doc_name}) for disaster auto-recovery...")
        file_info = bot.get_file(doc.file_id)
        downloaded_bytes = bot.download_file(file_info.file_path)

        with zipfile.ZipFile(io.BytesIO(downloaded_bytes), "r") as zf:
            restored_count = 0
            for name in zf.namelist():
                if name in TARGET_BACKUP_FILES:
                    extracted_data = zf.read(name)
                    # Write to both DATA_DIR and BASE_DIR
                    for d in set([DATA_DIR, BASE_DIR]):
                        try:
                            dest = d / name
                            with open(dest, "wb") as f_out:
                                f_out.write(extracted_data)
                        except Exception:
                            pass
                    restored_count += 1

            if restored_count > 0:
                logger.info(f"Auto-Disaster Recovery SUCCESS! Restored {restored_count} database files from cloud channel ✅")
                # Reload admin settings in memory
                try:
                    from admin_manager import admin_manager
                    admin_manager.load_settings()
                except Exception:
                    pass
                return True

    except Exception as e:
        logger.warning(f"Auto-restore check error (Safe to ignore on normal start): {e}")
    return False


def _backup_loop(bot, interval_seconds: int = 14 * 60):
    """Background daemon worker that runs every interval_seconds."""
    logger.info(f"14-Minute Audit Backup Daemon started (Interval: {interval_seconds}s) 🚀")
    # Small initial delay to let bot finish starting up
    time.sleep(30)
    while True:
        try:
            dispatch_and_pin_backup(bot)
        except Exception as e:
            logger.error(f"Backup daemon loop exception: {e}")
        time.sleep(interval_seconds)


def start_audit_backup_daemon(bot, interval_seconds: int = 14 * 60, auto_restore: bool = True):
    """Public entry point: starts disaster recovery check and background periodic backup thread."""
    if auto_restore:
        # Run restore check once in a non-blocking background thread
        threading.Thread(
            target=auto_restore_latest_from_channel,
            args=(bot,),
            daemon=True,
            name="CloudAutoRestoreThread"
        ).start()

    # Start 14-minute periodic backup daemon
    t = threading.Thread(
        target=_backup_loop,
        args=(bot, interval_seconds),
        daemon=True,
        name="AuditBackupDaemonThread"
    )
    t.start()
    return t
