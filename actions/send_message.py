"""
MYRA Send Message Action
=========================
Supports two WhatsApp send modes:
  1. UltraMsg API  — direct number pe message (scheduled ya instant)
  2. Desktop App   — pyautogui se WhatsApp/Telegram/Instagram open karke

UltraMsg config `config/api_keys.json` mein hona chahiye:
    "ultramsg_instance_id": "instanceXXXXX"
    "ultramsg_token":       "your_token_here"

Agar config nahi mila → fallback to desktop/pyautogui method.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pyautogui
import requests

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.08

# ── paths ───────────────────────────────────────────────────────────────────
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

CONFIG_PATH = _base_dir() / "config" / "api_keys.json"


# ═══════════════════════════════════════════════════════════════════════════
#  UltraMsg API  (direct WhatsApp send via API)
# ═══════════════════════════════════════════════════════════════════════════
def _load_ultramsg_config() -> tuple[str, str] | tuple[None, None]:
    """Returns (instance_id, token) or (None, None)."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        iid   = cfg.get("ultramsg_instance_id", "").strip()
        token = cfg.get("ultramsg_token", "").strip()
        if iid and token:
            return iid, token
    except Exception as e:
        print(f"[SendMessage] config read error: {e}")
    return None, None


def _send_via_ultramsg(phone: str, message: str) -> str:
    """
    UltraMsg API se WhatsApp message bhejo.
    phone format: 918815669176  (country code + number, no + or spaces)
    """
    instance_id, token = _load_ultramsg_config()
    if not instance_id:
        return "UltraMsg not configured — check api_keys.json"

    # Clean phone number
    phone_clean = "".join(filter(str.isdigit, phone))
    if not phone_clean:
        return f"Invalid phone number: {phone}"

    url     = f"https://api.ultramsg.com/{instance_id}/messages/chat"
    payload = {
        "token": token,
        "to":    phone_clean,
        "body":  message,
    }
    headers = {"content-type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(url, data=payload, headers=headers, timeout=15)
        print(f"[UltraMsg] Status: {resp.status_code} | {resp.text[:120]}")

        if resp.status_code == 200:
            data = resp.json() if resp.text.strip().startswith("{") else {}
            if data.get("sent") == "true" or "true" in resp.text.lower():
                return f"✅ WhatsApp message sent to {phone_clean} via UltraMsg."
            else:
                return f"⚠️ UltraMsg responded but message status unclear: {resp.text[:80]}"
        else:
            return f"❌ UltraMsg error {resp.status_code}: {resp.text[:80]}"

    except requests.exceptions.ConnectionError:
        return "❌ No internet connection — UltraMsg send failed."
    except requests.exceptions.Timeout:
        return "❌ UltraMsg request timed out."
    except Exception as e:
        return f"❌ UltraMsg exception: {e}"


def _schedule_and_send(phone: str, message: str, scheduled_time: datetime,
                       player=None) -> str:
    """
    Background thread mein wait karo phir UltraMsg se bhejo.
    """
    delay = (scheduled_time - datetime.now()).total_seconds()

    if delay <= 0:
        return _send_via_ultramsg(phone, message)

    def _run():
        mins = int(delay // 60)
        secs = int(delay % 60)
        log  = f"[Scheduler] ⏳ WhatsApp to {phone} scheduled in {mins}m {secs}s"
        print(log)
        if player:
            player.write_log(log)

        time.sleep(delay)

        result = _send_via_ultramsg(phone, message)
        print(f"[Scheduler] 📨 {result}")
        if player:
            player.write_log(f"[WhatsApp Scheduler] {result}")

    threading.Thread(target=_run, daemon=True, name="WA_Scheduler").start()

    mins = int(delay // 60)
    secs = int(delay % 60)
    return (
        f"✅ Scheduled! WhatsApp message will be sent to {phone} "
        f"in {mins} minutes {secs} seconds "
        f"(at {scheduled_time.strftime('%I:%M %p on %d %b')})."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Desktop / pyautogui methods  (fallback for contact-name based sending)
# ═══════════════════════════════════════════════════════════════════════════
def _open_app(app_name: str) -> bool:
    try:
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.write(app_name, interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2.0)
        return True
    except Exception as e:
        print(f"[SendMessage] Could not open {app_name}: {e}")
        return False


def _send_whatsapp_desktop(receiver: str, message: str) -> str:
    """WhatsApp Windows app ke through send karo (contact name se)."""
    try:
        if not _open_app("WhatsApp"):
            return "Could not open WhatsApp."
        time.sleep(1.5)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(receiver, interval=0.04)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")
        return f"Message sent to {receiver} via WhatsApp."
    except Exception as e:
        return f"WhatsApp error: {e}"


def _send_instagram(receiver: str, message: str) -> str:
    try:
        import webbrowser
        webbrowser.open("https://www.instagram.com/direct/new/")
        time.sleep(3.5)
        pyautogui.write(receiver, interval=0.05)
        time.sleep(1.5)
        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)
        for _ in range(3):
            pyautogui.press("tab")
            time.sleep(0.1)
        pyautogui.press("enter")
        time.sleep(1.5)
        pyautogui.write(message, interval=0.04)
        time.sleep(0.2)
        pyautogui.press("enter")
        return f"Message sent to {receiver} via Instagram."
    except Exception as e:
        return f"Instagram error: {e}"


def _send_telegram(receiver: str, message: str) -> str:
    try:
        if not _open_app("Telegram"):
            return "Could not open Telegram."
        time.sleep(1.5)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.write(receiver, interval=0.04)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")
        return f"Message sent to {receiver} via Telegram."
    except Exception as e:
        return f"Telegram error: {e}"


def _send_generic(platform: str, receiver: str, message: str) -> str:
    try:
        if not _open_app(platform):
            return f"Could not open {platform}."
        time.sleep(1.5)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.write(receiver, interval=0.04)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")
        return f"Message sent to {receiver} via {platform}."
    except Exception as e:
        return f"{platform} error: {e}"


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT  — called from main.py
# ═══════════════════════════════════════════════════════════════════════════
def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    MYRA tool entry point.

    parameters:
        receiver        — Contact name OR phone number (with country code)
        message_text    — Message to send
        platform        — whatsapp | instagram | telegram | <app name>
        scheduled_time  — Optional: "YYYY-MM-DD HH:MM:SS" for scheduling
        use_api         — Optional: "true" to force UltraMsg API even for names
    """
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip().lower()
    sched_str    = params.get("scheduled_time", "").strip()

    if not receiver:
        return "Sir, please batao kise message karna hai."
    if not message_text:
        return "Sir, please batao kya message bhejana hai."

    print(f"[SendMessage] 📨 {platform} → {receiver}: {message_text[:40]}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}…")

    # ── WhatsApp ─────────────────────────────────────────────────────────
    if any(kw in platform for kw in ("whatsapp", "wp", "wapp", "wa")):

        # Phone number detect karo (7+ digits)
        digits_only = "".join(filter(str.isdigit, receiver))
        is_number   = len(digits_only) >= 7

        if is_number:
            # UltraMsg API path — number se direct send
            instance_id, _ = _load_ultramsg_config()

            if instance_id:
                # Scheduled?
                if sched_str:
                    try:
                        sched_dt = datetime.strptime(sched_str, "%Y-%m-%d %H:%M:%S")
                        if sched_dt <= datetime.now():
                            return "❌ Sir, scheduled time past mein hai. Future time dena hoga."
                        result = _schedule_and_send(digits_only, message_text, sched_dt, player)
                    except ValueError:
                        return (
                            "❌ Date format galat hai Sir. "
                            "Sahi format: YYYY-MM-DD HH:MM:SS  "
                            "(Example: 2026-06-01 18:30:00)"
                        )
                else:
                    # Instant send via API
                    result = _send_via_ultramsg(digits_only, message_text)
            else:
                # Config nahi — desktop fallback
                result = _send_whatsapp_desktop(receiver, message_text)
        else:
            # Contact name — desktop WhatsApp app use karo
            result = _send_whatsapp_desktop(receiver, message_text)

    # ── Instagram ────────────────────────────────────────────────────────
    elif any(kw in platform for kw in ("instagram", "ig", "insta")):
        result = _send_instagram(receiver, message_text)

    # ── Telegram ─────────────────────────────────────────────────────────
    elif any(kw in platform for kw in ("telegram", "tg")):
        result = _send_telegram(receiver, message_text)

    # ── Other apps ───────────────────────────────────────────────────────
    else:
        result = _send_generic(platform, receiver, message_text)

    print(f"[SendMessage] ✅ {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result
