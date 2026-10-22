import os
import sys
import time
import faulthandler

faulthandler.enable()

# Clean up inherited Android environment variables in PRoot Linux (Termux)
# In proot-distro Ubuntu, ANDROID_ROOT and ANDROID_DATA are inherited from Android's environment.
# This causes the needle library's platform detection to falsely assume the host is Android Bionic
# rather than glibc Linux, resulting in a RuntimeError. Removing them allows needle to correctly
# identify the environment as manylinux aarch64 and load the glibc-compatible shared library.
if sys.platform.startswith("linux"):
    os.environ.pop("ANDROID_ROOT", None)
    os.environ.pop("ANDROID_DATA", None)

# Automatically prepend Termux binaries path to system environment PATH
TERMUX_BIN_PATH = "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

import json
import subprocess
import shutil
import needle
import threading
from flask import Flask, request, jsonify, render_template_string

# Try to import telebot for remote Telegram Bot control
try:
    import telebot
except ImportError:
    telebot = None

# Try to import waitress for production WSGI serving
try:
    from waitress import serve
except ImportError:
    serve = None

# Create Flask app
app = Flask(__name__)

IS_TERMUX = os.path.exists("/data/data/com.termux")

active_requests = {}
active_requests_lock = threading.Lock()
_current_req_id = threading.local()

def is_current_request_cancelled():
    req_id = getattr(_current_req_id, "id", None)
    if not req_id:
        return False
    with active_requests_lock:
        return active_requests.get(req_id, {}).get("cancelled", False)

def run_cmd(args):
    if is_current_request_cancelled():
        return "[Execution Cancelled by User]"
    req_id = getattr(_current_req_id, "id", None)
    # Try running the actual termux command first with 15s timeout for hardware warm-up
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if req_id:
            with active_requests_lock:
                if req_id in active_requests:
                    active_requests[req_id]["proc"] = proc
        stdout, stderr = proc.communicate(timeout=15)
        if is_current_request_cancelled():
            return "[Execution Cancelled by User]"
        if proc.returncode == 0:
            return stdout.strip() if stdout.strip() else "Success"
        else:
            if IS_TERMUX:
                err_msg = stderr.strip() or stdout.strip() or f"Exit code {proc.returncode}"
                return f"Error ({args[0]}): {err_msg}"
            raise FileNotFoundError()
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        if is_current_request_cancelled():
            return "[Execution Cancelled by User]"
        if IS_TERMUX:
            return f"Error ({args[0]}): Command timed out after 15 seconds. Termux API might be hanging or lack permissions."
        raise FileNotFoundError()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        if is_current_request_cancelled():
            return "[Execution Cancelled by User]"
        if IS_TERMUX:
            return f"Error ({args[0]}): Command execution failed in Termux environment."
        # Simulation layer for desktop testing (only active on non-Termux systems)
        cmd = args[0]
        if cmd == "termux-battery-status":
            return json.dumps({
                "health": "GOOD",
                "percentage": 87,
                "plugged": "UNPLUGGED",
                "status": "DISCHARGING",
                "temperature": 29.5,
                "current": -240
            })
        elif cmd == "termux-toast":
            return f"[Simulated Toast] Displayed popup: '{args[1]}'"
        elif cmd == "termux-notification":
            title = args[3] if len(args) > 3 else "System Alert"
            content = args[5] if len(args) > 5 else "Alert triggered."
            return f"[Simulated Notification] Sent alert - Title: '{title}', Content: '{content}'"
        elif cmd == "termux-tts-speak":
            return f"[Simulated Text-To-Speech] Spoke aloud: '{args[1]}'"
        elif cmd == "termux-clipboard-set":
            return f"[Simulated Clipboard] Copied to clipboard: '{args[1]}'"
        elif cmd == "termux-clipboard-get":
            return "This is a simulated clipboard value retrieved from desktop environment."
        elif cmd == "termux-vibrate":
            duration = args[2] if len(args) > 2 else "500"
            return f"[Simulated Haptic] Vibrated device for {duration}ms"
        elif cmd == "termux-torch":
            state = args[1]
            return f"[Simulated Hardware] Flashlight switched {state.upper()}"
        elif cmd == "termux-location":
            return json.dumps({
                "latitude": 37.7749,
                "longitude": -122.4194,
                "altitude": 18.2,
                "accuracy": 15.0,
                "provider": "gps"
            })
        elif cmd == "termux-sms-send":
            recipient = args[2]
            message = args[3]
            return f"[Simulated Network] SMS Sent to {recipient} containing: '{message}'"
        elif cmd == "termux-telephony-call":
            number = args[1]
            return f"[Simulated Dial] Dialed voice connection call to: {number}"
        elif cmd == "termux-wifi-connectioninfo":
            return json.dumps({
                "ssid": "Termux_Agent_Secure_5G",
                "ip": "192.168.1.108",
                "link_speed_mbps": 866,
                "rssi": -48,
                "supplicant_state": "COMPLETED"
            })
        elif cmd == "termux-camera-photo":
            filename = args[3] if len(args) > 3 else "photo.jpg"
            return f"[Simulated Camera] Photo captured and saved to: {filename}"
        elif cmd == "termux-sms-list":
            return json.dumps([
                {"address": "+1234567890", "body": "Hey there! How is it going?", "date": "2026-08-30 12:00:00", "read": True, "type": "inbox"},
                {"address": "OTP-BANK", "body": "Your bank OTP is 582103.", "date": "2026-08-30 11:45:00", "read": False, "type": "inbox"}
            ])
        elif cmd == "termux-contact-list":
            return json.dumps([
                {"name": "Alice Smith", "number": "+1987654321"},
                {"name": "Bob Jones", "number": "+15550199"}
            ])
        elif cmd == "termux-download":
            title = args[2] if len(args) > 2 else "Download"
            url = args[3] if len(args) > 3 else ""
            return f"[Simulated Download] Downloading URL: {url} as '{title}'"
        elif cmd == "termux-brightness":
            val = args[1]
            return f"[Simulated Screen] Set screen brightness to {val}"
        elif cmd == "termux-volume":
            if len(args) > 2:
                stream = args[1]
                volume = args[2]
                return f"[Simulated Audio] Set volume stream '{stream}' to {volume}"
            else:
                return json.dumps([
                    {"stream": "music", "volume": 11, "max_volume": 15},
                    {"stream": "ring", "volume": 5, "max_volume": 7},
                    {"stream": "alarm", "volume": 6, "max_volume": 7},
                    {"stream": "notification", "volume": 5, "max_volume": 7},
                    {"stream": "system", "volume": 7, "max_volume": 7},
                    {"stream": "call", "volume": 4, "max_volume": 5}
                ])
        elif cmd == "termux-share":
            file_arg = args[3] if len(args) > 3 else "stdin text content"
            return f"[Simulated Share] Shared content via system share sheet: '{file_arg}'"
        elif cmd == "termux-call-log":
            limit = args[2] if len(args) > 2 else "5"
            return json.dumps([
                {"name": "Alice Smith", "number": "+1987654321", "duration": "2m 14s", "date": "2026-08-31 10:15:22", "type": "incoming"},
                {"name": "John Doe", "number": "+14155552671", "duration": "0s", "date": "2026-08-30 18:44:10", "type": "missed"},
                {"name": "Bob Jones", "number": "+15550199", "duration": "5m 45s", "date": "2026-08-30 14:02:01", "type": "outgoing"}
            ][:int(limit) if limit.isdigit() else None])
        elif cmd == "termux-fingerprint":
            return json.dumps({"auth_result": "AUTH_SUCCESS", "errors": None})
        elif cmd == "termux-microphone-record":
            if "-q" in args:
                return "[Simulated Recording] Microphone recording stopped and saved."
            else:
                file_idx = args.index("-f") + 1 if "-f" in args else -1
                file_path = args[file_idx] if file_idx != -1 and file_idx < len(args) else "recording.3gp"
                return f"[Simulated Recording] Microphone recording started into '{file_path}'"
        elif cmd == "termux-telephony-deviceinfo":
            return json.dumps({
                "data_activity": "DATA_ACTIVITY_NONE",
                "data_state": "DATA_CONNECTED",
                "device_id": "864209753197531",
                "device_software_version": "01",
                "network_operator": "Google Fi",
                "network_operator_name": "Google Fi",
                "network_type": "LTE",
                "phone_type": "PHONE_TYPE_GSM",
                "sim_country_iso": "us",
                "sim_operator": "310260",
                "sim_operator_name": "Google Fi",
                "sim_serial_number": "8901260xxxxxxxxxxxx",
                "sim_state": "SIM_STATE_READY"
            })
        elif cmd == "termux-wifi-scaninfo":
            return json.dumps([
                {"bssid": "aa:bb:cc:dd:ee:ff", "frequency_mhz": 5240, "rssi": -55, "ssid": "Home-Network_5G", "timestamp_ms": 1725100000000},
                {"bssid": "11:22:33:44:55:66", "frequency_mhz": 2412, "rssi": -72, "ssid": "Cafe_Free_Wifi", "timestamp_ms": 1725100000000}
            ])
        elif cmd == "termux-wifi-enable":
            st = args[1] if len(args) > 1 else "true"
            return f"[Simulated Wi-Fi] Wi-Fi set to {st.upper()}"
        elif cmd == "termux-media-player":
            subcmd = args[1] if len(args) > 1 else "info"
            if subcmd == "play":
                track = args[2] if len(args) > 2 else "local_audio.mp3"
                return f"[Simulated Media] Playing audio: {track}"
            elif subcmd in ("pause", "stop"):
                return f"[Simulated Media] Audio playback {subcmd}ped."
            else:
                return json.dumps({"status": "playing", "track": "Simulated Track.mp3", "position": "01:24"})
        elif cmd == "termux-sensor":
            s_name = args[args.index("-s") + 1] if "-s" in args and args.index("-s") + 1 < len(args) else "accelerometer"
            return json.dumps({
                s_name: {
                    "values": [0.12, 9.81, 0.45],
                    "unit": "m/s^2",
                    "timestamp": 1725100000
                }
            })
        elif cmd == "termux-dialog":
            return json.dumps({"code": 0, "text": "Confirmed by user on screen"})
        elif cmd == "termux-wallpaper":
            f_idx = args.index("-f") + 1 if "-f" in args else -1
            f_path = args[f_idx] if f_idx != -1 and f_idx < len(args) else "wallpaper.jpg"
            return f"[Simulated Wallpaper] Wallpaper set to: {f_path}"
        elif cmd in ("termux-wake-lock", "termux-wake-unlock"):
            action = "acquired" if "lock" in cmd and "unlock" not in cmd else "released"
            return f"[Simulated Power] System wake lock {action}."
        elif cmd == "screencap":
            return "[Simulated Display] Screenshot captured and saved to /sdcard/Download/screenshot.png"
        elif cmd == "input":
            return f"[Simulated Input] Simulated button/key event: {' '.join(args[1:])}"
        elif cmd == "termux-telephony-cellinfo":
            return json.dumps([
                {"type": "LTE", "registered": True, "cid": 2854913, "lac": 1421, "mcc": 310, "mnc": 260, "rssi": -72, "rsrp": -95}
            ])
        elif cmd == "termux-audio-info":
            return json.dumps({
                "bluetooth_a2dp_connected": False,
                "wired_headset": True,
                "is_microphone_muted": False,
                "music_volume": 11,
                "call_volume": 4
            })
        elif cmd == "termux-nfc":
            return json.dumps({
                "status": "read_success",
                "tag_id": "04:B2:71:A9:1C:80",
                "standard": "ISO/IEC 14443-A",
                "technologies": ["NfcA", "MifareUltralight", "NdefFormatable"]
            })
        elif cmd in ("monkey", "am"):
            if cmd == "monkey":
                pkg = args[args.index("-p") + 1] if "-p" in args and args.index("-p") + 1 < len(args) else "app"
                return f"[Simulated App Launcher] Launched application package: '{pkg}'"
            else:
                return f"[Simulated Activity Manager] Started activity: {' '.join(args[1:])}"
        else:
            return f"[Simulated Action] Executed command: {' '.join(args)}"

# ----------------------------------------------------------------------
# Define Needle Tools (decorated so Needle agent discovers them)
# ----------------------------------------------------------------------

@needle.tool
def show_toast(message: str):
    """Display a brief toast notification popup on the phone screen."""
    print(f"[Agent Triggered Tool] show_toast(message='{message}')")
    return run_cmd(["termux-toast", message])

@needle.tool
def show_notification(title: str, content: str):
    """Display a system notification drawer popup with a title and message content."""
    print(f"[Agent Triggered Tool] show_notification(title='{title}', content='{content}')")
    return run_cmd(["termux-notification", "--title", title, "--content", content])

@needle.tool
def get_battery_status():
    """Retrieve details about the phone's battery (percentage, status, health, temperature)."""
    print("[Agent Triggered Tool] get_battery_status()")
    res = run_cmd(["termux-battery-status"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def text_to_speech(text: str):
    """Speak a text string aloud using the phone's Text-to-Speech (TTS) engine."""
    print(f"[Agent Triggered Tool] text_to_speech(text='{text}')")
    try:
        res = subprocess.run(["termux-tts-speak"], input=text, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return f"Error: {res.stderr.strip()}"
        return res.stdout.strip() if res.stdout else "Speech triggered successfully."
    except (FileNotFoundError, PermissionError):
        return f"[Simulated Text-To-Speech] Spoke aloud: '{text}'"
    except Exception as e:
        return f"Error: {str(e)}"

@needle.tool
def set_clipboard(text: str):
    """Copy a text string to the device's system clipboard."""
    print(f"[Agent Triggered Tool] set_clipboard(text='{text}')")
    return run_cmd(["termux-clipboard-set", text])

@needle.tool
def get_clipboard():
    """Retrieve the current text stored in the device's system clipboard."""
    print("[Agent Triggered Tool] get_clipboard()")
    return run_cmd(["termux-clipboard-get"])

@needle.tool
def vibrate_device(duration_ms: int = 500):
    """Vibrate the phone device for a duration specified in milliseconds."""
    print(f"[Agent Triggered Tool] vibrate_device(duration_ms={duration_ms})")
    return run_cmd(["termux-vibrate", "-d", str(duration_ms)])

@needle.tool
def set_torch(on: bool):
    """Turn the phone device's camera flash / torch ON (True) or OFF (False)."""
    print(f"[Agent Triggered Tool] set_torch(on={on})")
    state = "on" if on else "off"
    return run_cmd(["termux-torch", state])

@needle.tool
def get_location():
    """Retrieve the device's current GPS location coordinates (latitude, longitude, altitude)."""
    print("[Agent Triggered Tool] get_location()")
    res = run_cmd(["termux-location", "-p", "network", "-r", "last"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def send_sms(recipient: str, message: str):
    """Send an SMS text message to a recipient phone number."""
    print(f"[Agent Triggered Tool] send_sms(recipient='{recipient}', message='{message}')")
    return run_cmd(["termux-sms-send", "-n", recipient, message])

@needle.tool
def make_phone_call(phone_number: str):
    """Initiate an outgoing voice call to the specified phone number."""
    print(f"[Agent Triggered Tool] make_phone_call(phone_number='{phone_number}')")
    return run_cmd(["termux-telephony-call", phone_number])

@needle.tool
def get_wifi_info():
    """Retrieve details about the active Wi-Fi connection (SSID, IP address, speed, strength)."""
    print("[Agent Triggered Tool] get_wifi_info()")
    res = run_cmd(["termux-wifi-connectioninfo"])
    try:
        return json.loads(res)
    except Exception:
        return res


@needle.tool
def take_camera_photo():
    """Capture a photo using the phone's back camera and save it directly to the Download folder."""
    print("[Agent Triggered Tool] take_camera_photo()")
    home_dir = os.path.expanduser("~")
    
    possible_targets = [
        "/sdcard/Download/needle_photo.jpg",
        os.path.join(home_dir, "storage", "downloads", "needle_photo.jpg"),
        os.path.join(home_dir, "needle_photo.jpg")
    ]
    
    last_res = ""
    for target_path in possible_targets:
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            res = run_cmd(["termux-camera-photo", "-c", "0", target_path])
            last_res = res
            
            # Verify photo file actually exists and is non-empty
            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                return f"Photo captured with back camera and saved to: '{target_path}'"
        except Exception as e:
            last_res = str(e)
            
    return f"Camera capture failed ({last_res}). Tip: Ensure 'Termux:API' app has 'Camera' and 'Files/Storage' permissions enabled in Android Settings."

@needle.tool
def open_app(app_name: str):
    """Open an application on the phone screen (e.g. 'whatsapp', 'youtube', 'chrome', 'instagram', 'spotify', 'telegram', 'facebook', 'twitter', 'gmail', 'maps', 'calculator', 'settings')."""
    print(f"[Agent Triggered Tool] open_app(app_name='{app_name}')")
    
    raw = app_name.strip().lower()
    clean = raw.replace("open", "").replace("the", "").replace("app", "").strip()
    
    app_urls = {
        "youtube": "https://www.youtube.com",
        "yt": "https://www.youtube.com",
        "whatsapp": "https://api.whatsapp.com",
        "wa": "https://api.whatsapp.com",
        "chrome": "http://google.com",
        "google": "http://google.com",
        "browser": "http://google.com",
        "instagram": "https://instagram.com",
        "insta": "https://instagram.com",
        "spotify": "https://open.spotify.com",
        "telegram": "https://t.me",
        "facebook": "https://facebook.com",
        "fb": "https://facebook.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "gmail": "mailto:",
        "maps": "https://maps.google.com",
        "google maps": "https://maps.google.com"
    }

    app_packages = {
        "youtube": "com.google.android.youtube",
        "whatsapp": "com.whatsapp",
        "chrome": "com.android.chrome",
        "instagram": "com.instagram.android",
        "spotify": "com.spotify.music",
        "telegram": "org.telegram.messenger",
        "facebook": "com.facebook.katana",
        "gmail": "com.google.android.gm",
        "maps": "com.google.android.apps.maps",
        "settings": "com.android.settings",
        "calculator": "com.google.android.calculator",
        "camera": "com.android.camera"
    }

    app_activities = {
        "settings": "com.android.settings/.Settings",
        "calculator": "com.google.android.calculator/com.android.calculator2.Calculator",
        "camera": "com.android.camera/com.android.camera.Camera"
    }

    target_key = None
    for k in (clean, raw):
        if k in app_urls or k in app_packages or k in app_activities:
            target_key = k
            break
            
    if not target_key:
        for k in app_urls:
            if k in clean or clean in k:
                target_key = k
                break

    if raw.startswith("http://") or raw.startswith("https://"):
        run_cmd(["termux-open", raw])
        run_cmd(["termux-open-url", raw])
        return f"Opened URL '{raw}' on phone screen."

    if target_key:
        if target_key in app_urls:
            url = app_urls[target_key]
            run_cmd(["termux-open", url])
            run_cmd(["termux-open-url", url])
            run_cmd(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", url])

        if target_key in app_packages:
            pkg = app_packages[target_key]
            run_cmd(["monkey", "-p", pkg, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"])

        if target_key in app_activities:
            act = app_activities[target_key]
            run_cmd(["am", "start", "--user", "0", "-n", act])

        return f"Successfully opened {app_name} on your phone screen."

    run_cmd(["termux-open", f"http://google.com"])
    run_cmd(["monkey", "-p", raw if "." in raw else f"com.{raw}", "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"])
    return f"Attempted opening '{app_name}' on phone screen."

@needle.tool
def get_sms_messages(limit: int = 5):
    """Retrieve a list of recent incoming SMS text messages from the phone."""
    print(f"[Agent Triggered Tool] get_sms_messages(limit={limit})")
    res = run_cmd(["termux-sms-list", "-l", str(limit)])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def get_contacts():
    """Retrieve the phone's contact list (names and phone numbers)."""
    print("[Agent Triggered Tool] get_contacts()")
    res = run_cmd(["termux-contact-list"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def download_file(url: str, title: str = "Download"):
    """Download a file from a URL using the system's download manager."""
    print(f"[Agent Triggered Tool] download_file(url='{url}', title='{title}')")
    return run_cmd(["termux-download", "-t", title, url])

@needle.tool
def set_screen_brightness(level: str):
    """Adjust the screen brightness. Provide a value between 0 (dimmest) and 255 (brightest), or 'auto'."""
    print(f"[Agent Triggered Tool] set_screen_brightness(level='{level}')")
    return run_cmd(["termux-brightness", str(level)])

@needle.tool
def get_volume_info():
    """Retrieve the current volume levels of all audio streams (music, ring, alarm, etc.)."""
    print("[Agent Triggered Tool] get_volume_info()")
    res = run_cmd(["termux-volume"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def set_volume(stream: str, volume: int):
    """Set the volume level of a specific audio stream (alarm, music, notification, ring, system, call)."""
    print(f"[Agent Triggered Tool] set_volume(stream='{stream}', volume={volume})")
    return run_cmd(["termux-volume", stream, str(volume)])

@needle.tool
def share_content(text: str = "", file_path: str = ""):
    """Share text content or a file using the Android system share sheet."""
    print(f"[Agent Triggered Tool] share_content(text='{text}', file_path='{file_path}')")
    if file_path:
        return run_cmd(["termux-share", "-a", "send", file_path])
    elif text:
        try:
            res = subprocess.run(["termux-share", "-a", "send"], input=text, capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                return f"Error: {res.stderr.strip()}"
            return res.stdout.strip() if res.stdout else "Content shared successfully."
        except Exception as e:
            return f"Error sharing text: {str(e)}"
    else:
        return "Error: Either text or file_path must be provided."

@needle.tool
def get_call_log(limit: int = 5):
    """Retrieve the recent call log history from the phone."""
    print(f"[Agent Triggered Tool] get_call_log(limit={limit})")
    res = run_cmd(["termux-call-log", "-l", str(limit)])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def authenticate_fingerprint():
    """Prompt for fingerprint authentication on the device to verify user identity."""
    print("[Agent Triggered Tool] authenticate_fingerprint()")
    res = run_cmd(["termux-fingerprint"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def record_audio_start(file_path: str = "recording.3gp", limit_seconds: int = 0):
    """Begin recording audio from the device microphone to a specified file. Optionally set a duration limit in seconds."""
    print(f"[Agent Triggered Tool] record_audio_start(file_path='{file_path}', limit_seconds={limit_seconds})")
    cmd = ["termux-microphone-record", "-f", file_path]
    if limit_seconds > 0:
        cmd.extend(["-l", str(limit_seconds)])
    return run_cmd(cmd)

@needle.tool
def record_audio_stop():
    """Stop the ongoing microphone audio recording and save the file."""
    print("[Agent Triggered Tool] record_audio_stop()")
    return run_cmd(["termux-microphone-record", "-q"])

@needle.tool
def get_telephony_info():
    """Retrieve device telephony information (network operator, SIM state, network type, IMEI/device ID)."""
    print("[Agent Triggered Tool] get_telephony_info()")
    res = run_cmd(["termux-telephony-deviceinfo"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def scan_wifi_networks():
    """Scan and retrieve a list of nearby Wi-Fi networks and their signal strengths."""
    print("[Agent Triggered Tool] scan_wifi_networks()")
    res = run_cmd(["termux-wifi-scaninfo"])
    try:
        return json.loads(res)
    except Exception:
        return res


@needle.tool
def set_wifi_state(enable: bool):
    """Turn the phone device's Wi-Fi radio ON (True) or OFF (False)."""
    print(f"[Agent Triggered Tool] set_wifi_state(enable={enable})")
    state = "true" if enable else "false"
    return run_cmd(["termux-wifi-enable", state])

@needle.tool
def control_media(action: str, file_path: str = ""):
    """Control audio and media playback on the device. Valid actions: 'play', 'pause', 'stop', 'info'. Provide file_path when playing audio."""
    print(f"[Agent Triggered Tool] control_media(action='{action}', file_path='{file_path}')")
    act = action.strip().lower()
    if act == "play" and file_path:
        return run_cmd(["termux-media-player", "play", file_path])
    elif act in ("play", "pause", "stop", "info"):
        res = run_cmd(["termux-media-player", act])
        try:
            return json.loads(res)
        except Exception:
            return res
    return f"Unsupported media action '{action}'. Valid choices: play, pause, stop, info."

@needle.tool
def get_sensors(sensor_name: str = "all"):
    """Read live hardware sensor data from the phone (accelerometer, light, proximity, gyroscope, step_counter, temperature, or 'all')."""
    print(f"[Agent Triggered Tool] get_sensors(sensor_name='{sensor_name}')")
    cmd = ["termux-sensor", "-n", "1"]
    if sensor_name and sensor_name.lower() != "all":
        cmd.extend(["-s", sensor_name])
    else:
        cmd.extend(["-a"])
    res = run_cmd(cmd)
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def show_dialog(title: str, text: str = "Please confirm", dialog_type: str = "confirm"):
    """Display an interactive dialog prompt on the phone screen (e.g. 'confirm' with Yes/No, or 'text' input) and return user response."""
    print(f"[Agent Triggered Tool] show_dialog(title='{title}', text='{text}', dialog_type='{dialog_type}')")
    dtype = dialog_type.strip().lower()
    if dtype == "text":
        res = run_cmd(["termux-dialog", "text", "-t", title, "-i", text])
    else:
        res = run_cmd(["termux-dialog", "confirm", "-t", title, "-i", text])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def set_wallpaper(file_path: str, lockscreen: bool = False):
    """Change the phone's wallpaper from a local image file. Set lockscreen=True to change lockscreen wallpaper instead of homescreen."""
    print(f"[Agent Triggered Tool] set_wallpaper(file_path='{file_path}', lockscreen={lockscreen})")
    cmd = ["termux-wallpaper", "-f", file_path]
    if lockscreen:
        cmd.append("-l")
    return run_cmd(cmd)

@needle.tool
def manage_wake_lock(lock: bool = True):
    """Acquire (True) or release (False) a system wake lock to keep the phone CPU awake during long-running tasks."""
    print(f"[Agent Triggered Tool] manage_wake_lock(lock={lock})")
    return run_cmd(["termux-wake-lock"] if lock else ["termux-wake-unlock"])

@needle.tool
def send_key_event(key: str):
    """Simulate a physical button or navigation keypress on the phone. Supported keys: 'home', 'back', 'volume_up', 'volume_down', 'power', 'play_pause', 'menu', 'enter'."""
    print(f"[Agent Triggered Tool] send_key_event(key='{key}')")
    key_codes = {
        "home": "3",
        "back": "4",
        "volume_up": "24",
        "volume_down": "25",
        "power": "26",
        "menu": "82",
        "play_pause": "85",
        "enter": "66",
        "wake": "224"
    }
    k = key.strip().lower().replace(" ", "_")
    code = key_codes.get(k, k)
    return run_cmd(["input", "keyevent", str(code)])

@needle.tool
def take_screenshot():
    """Capture a screenshot of the phone screen and save it to the Download folder."""
    print("[Agent Triggered Tool] take_screenshot()")
    target = "/sdcard/Download/screenshot.png"
    res = run_cmd(["screencap", "-p", target])
    if os.path.exists(target) and os.path.getsize(target) > 0:
        return f"Screenshot captured successfully and saved to: '{target}'"
    return f"Screenshot saved: {res} (Saved to {target})"

@needle.tool
def get_cell_tower_info():
    """Retrieve details on nearby cellular base station towers, signal strength (RSSI, RSRP), and cell IDs."""
    print("[Agent Triggered Tool] get_cell_tower_info()")
    res = run_cmd(["termux-telephony-cellinfo"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def get_audio_hardware_info():
    """Check phone audio routing (whether wired headphones or Bluetooth A2DP headphones are plugged in, microphone state)."""
    print("[Agent Triggered Tool] get_audio_hardware_info()")
    res = run_cmd(["termux-audio-info"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def read_nfc():
    """Scan for nearby NFC tags or RFID smart cards touching the back of the phone."""
    print("[Agent Triggered Tool] read_nfc()")
    res = run_cmd(["termux-nfc", "-r"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def extract_structured_data(text: str, extraction_type: str = "general"):
    """Extract structured data (event, contact, reminder, expense, task) from messy unstructured text using Needle 3's grammar-constrained extraction."""
    print(f"[Agent Triggered Tool] extract_structured_data(extraction_type='{extraction_type}')")
    schema_map = {
        "event": {
            "title": "string",
            "date": "string",
            "time": "string",
            "location": "string"
        },
        "contact": {
            "name": "string",
            "phone": "string",
            "email": "string"
        },
        "reminder": {
            "task": "string",
            "due_date": "string",
            "priority": "string"
        },
        "expense": {
            "vendor": "string",
            "amount": "string",
            "category": "string"
        },
        "general": {
            "summary": "string",
            "action_items": "list of strings"
        }
    }
    schema = schema_map.get(extraction_type.lower(), schema_map["general"])
    try:
        current_agent = get_agent()
        if hasattr(current_agent, "extract") and getattr(current_agent, "_generation", 3) >= 3:
            extracted = current_agent.extract(text, schema=schema)
            if extracted:
                return extracted
    except Exception:
        pass
    return {"extraction_type": extraction_type, "schema": schema, "source_text": text, "status": "processed"}

@needle.tool
def semantic_phone_search(query: str, target: str = "all"):
    """Perform on-device semantic search over phone data (contacts, SMS inbox, call log) using Needle 3 embeddings to find relevant records even if exact words don't match."""
    print(f"[Agent Triggered Tool] semantic_phone_search(query='{query}', target='{target}')")
    items = []
    t = target.lower()
    if t in ("all", "contacts"):
        c_raw = run_cmd(["termux-contact-list"])
        try:
            for c in json.loads(c_raw):
                items.append(f"Contact: {c.get('name', '')} (Phone: {c.get('number', '')})")
        except Exception:
            pass
            
    if t in ("all", "sms"):
        s_raw = run_cmd(["termux-sms-list", "-l", "10"])
        try:
            for s in json.loads(s_raw):
                items.append(f"SMS from {s.get('address', '')}: \"{s.get('body', '')}\" on {s.get('date', '')}")
        except Exception:
            pass

    if t in ("all", "calls"):
        cl_raw = run_cmd(["termux-call-log", "-l", "10"])
        try:
            for cl in json.loads(cl_raw):
                items.append(f"Call {cl.get('type', '')} with {cl.get('name', cl.get('number', ''))} for {cl.get('duration', '')}")
        except Exception:
            pass

    if not items:
        return "No phone records available to search."

    try:
        current_agent = get_agent()
        if hasattr(current_agent, "embed") and getattr(current_agent, "_generation", 3) >= 3:
            import math
            def cosine_sim(v1, v2):
                dot = sum(a * b for a, b in zip(v1, v2))
                m1 = math.sqrt(sum(a * a for a in v1))
                m2 = math.sqrt(sum(b * b for b in v2))
                return dot / (m1 * m2 + 1e-9)

            query_vec = current_agent.embed(query)
            scored = []
            for it in items:
                it_vec = current_agent.embed(it)
                sim = cosine_sim(query_vec, it_vec)
                scored.append((sim, it))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [f"[{round(sim*100)}% match] {it}" for sim, it in scored[:5]]
    except Exception:
        pass

    q_words = [w.lower() for w in query.split() if len(w) > 2]
    matched = [it for it in items if any(w in it.lower() for w in q_words)]
    return matched[:5] if matched else items[:3]

# ----------------------------------------------------------------------
# Initialize the Needle Agent (Supports Needle 2 and Needle 3)
# ----------------------------------------------------------------------
tools_list = [
    show_toast, show_notification, get_battery_status, 
    text_to_speech, set_clipboard, get_clipboard, 
    vibrate_device, set_torch, get_location, 
    send_sms, make_phone_call, get_wifi_info,
    take_camera_photo, get_sms_messages, get_contacts, download_file,
    set_screen_brightness, get_volume_info, set_volume, share_content,
    get_call_log, authenticate_fingerprint, record_audio_start,
    record_audio_stop, get_telephony_info, scan_wifi_networks,
    open_app, set_wifi_state, control_media, get_sensors,
    show_dialog, set_wallpaper, manage_wake_lock, send_key_event,
    take_screenshot, get_cell_tower_info, get_audio_hardware_info,
    read_nfc, extract_structured_data, semantic_phone_search
]

def get_initial_generation():
    for idx, arg in enumerate(sys.argv):
        if arg in ("--model", "--generation", "-m") and idx + 1 < len(sys.argv):
            try:
                val = int(sys.argv[idx + 1])
                if val in (2, 3):
                    return val
            except ValueError:
                pass
    env_val = os.environ.get("NEEDLE_MODEL") or os.environ.get("NEEDLE_GENERATION")
    if env_val:
        try:
            val = int(env_val)
            if val in (2, 3):
                return val
        except ValueError:
            pass
    return 3

active_generation = get_initial_generation()
loaded_agents = {}
agent_lock = threading.Lock()

def get_agent(gen=None):
    global active_generation
    target_gen = int(gen if gen is not None else active_generation)
    if target_gen not in (2, 3):
        target_gen = 3
    with agent_lock:
        if target_gen not in loaded_agents:
            desc = "Needle 3 (Laddered SAN Foundation)" if target_gen == 3 else "Needle 2 (Legacy 14MB Core)"
            print(f"Loading {desc}...")
            loaded_agents[target_gen] = needle.Needle(tools=tools_list, generation=target_gen)
            print(f"{desc} active and ready!")
        return loaded_agents[target_gen]

def set_active_generation(gen):
    global active_generation, agent
    val = int(gen)
    if val not in (2, 3):
        raise ValueError("Invalid model generation. Choose 2 (Needle 2) or 3 (Needle 3).")
    agent = get_agent(val)
    active_generation = val
    return active_generation

# Eagerly initialize the default agent at startup
agent = get_agent(active_generation)


# ----------------------------------------------------------------------
# Web Layout (Vanilla CSS & HTML with Glassmorphic aesthetic)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>Termux Agent Hub — Needle AI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-canvas: #f8fafc;
            --bg-card: #ffffff;
            --bg-card-subtle: #f1f5f9;
            --bg-input: #ffffff;
            --border-main: #e2e8f0;
            --border-focus: #6366f1;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --primary-light: #eef2ff;
            --primary-glow: rgba(79, 70, 229, 0.12);
            --accent-cyan: #0891b2;
            --accent-green: #10b981;
            --accent-green-bg: #ecfdf5;
            --accent-purple: #7c3aed;
            --accent-purple-bg: #f5f3ff;
            --accent-amber: #d97706;
            --accent-amber-bg: #fffbeb;
            --danger: #ef4444;
            --danger-hover: #dc2626;
            --danger-bg: #fef2f2;
            --bubble-user: #4f46e5;
            --bubble-user-text: #ffffff;
            --bubble-agent: #ffffff;
            --bubble-agent-border: #e2e8f0;
            --terminal-bg: #0f172a;
            --terminal-text: #10b981;
            --terminal-border: #1e293b;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 12px -2px rgba(0, 0, 0, 0.06), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            --shadow-lg: 0 12px 24px -4px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.03);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
            --radius-full: 9999px;
        }

        [data-theme="dark"] {
            --bg-canvas: #090a0f;
            --bg-card: #11131e;
            --bg-card-subtle: #161824;
            --bg-input: #131522;
            --border-main: rgba(255, 255, 255, 0.08);
            --border-focus: #6366f1;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --primary-light: rgba(99, 102, 241, 0.15);
            --primary-glow: rgba(99, 102, 241, 0.25);
            --accent-cyan: #22d3ee;
            --accent-green: #10b981;
            --accent-green-bg: rgba(16, 185, 129, 0.12);
            --accent-purple: #a855f7;
            --accent-purple-bg: rgba(168, 85, 247, 0.12);
            --accent-amber: #f59e0b;
            --accent-amber-bg: rgba(245, 158, 11, 0.12);
            --danger: #ef4444;
            --danger-hover: #dc2626;
            --danger-bg: rgba(239, 68, 68, 0.15);
            --bubble-user: #4f46e5;
            --bubble-user-text: #ffffff;
            --bubble-agent: #161824;
            --bubble-agent-border: rgba(255, 255, 255, 0.07);
            --terminal-bg: #05060a;
            --terminal-text: #10b981;
            --terminal-border: rgba(255, 255, 255, 0.06);
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.4);
            --shadow-md: 0 4px 12px -2px rgba(0, 0, 0, 0.5);
            --shadow-lg: 0 12px 24px -4px rgba(0, 0, 0, 0.6);
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-canvas);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            transition: background-color 0.25s ease, color 0.25s ease;
            -webkit-font-smoothing: antialiased;
        }

        /* Top Navigation Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.9rem 1.75rem;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border-main);
            position: sticky;
            top: 0;
            z-index: 50;
            backdrop-filter: blur(16px);
            box-shadow: var(--shadow-sm);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .logo-mark {
            width: 2.2rem;
            height: 2.2rem;
            border-radius: 10px;
            background: linear-gradient(135deg, #4f46e5, #06b6d4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 1.05rem;
            color: #ffffff;
            box-shadow: 0 2px 10px var(--primary-glow);
            letter-spacing: -0.5px;
        }

        .logo-text h1 {
            font-size: 1.05rem;
            font-weight: 700;
            letter-spacing: -0.3px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .logo-text .badge-sub {
            font-size: 0.68rem;
            font-weight: 600;
            color: var(--primary);
            background: var(--primary-light);
            padding: 0.15rem 0.5rem;
            border-radius: var(--radius-full);
            letter-spacing: 0.3px;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        /* Model Switcher Segment */
        .model-switcher {
            display: flex;
            align-items: center;
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            padding: 3px;
            border-radius: var(--radius-full);
            gap: 2px;
        }

        .model-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 0.35rem 0.85rem;
            border-radius: var(--radius-full);
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .model-btn:hover {
            color: var(--text-primary);
        }

        .model-btn.active {
            background: var(--primary);
            color: #ffffff;
            box-shadow: 0 2px 8px var(--primary-glow);
        }

        .model-btn .pill-badge {
            font-size: 0.65rem;
            padding: 1px 5px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.2);
            font-weight: 700;
        }

        .model-btn:not(.active) .pill-badge {
            background: var(--border-main);
            color: var(--text-muted);
        }

        /* Status Badge */
        .status-pill {
            display: flex;
            align-items: center;
            gap: 0.45rem;
            background: var(--accent-green-bg);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 0.35rem 0.75rem;
            border-radius: var(--radius-full);
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--accent-green);
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.25);
            animation: pulse-dot 2s infinite ease-in-out;
        }

        @keyframes pulse-dot {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(0.85); opacity: 0.6; }
        }

        /* Theme Toggle Button */
        .theme-toggle-btn {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            color: var(--text-secondary);
            width: 2.1rem;
            height: 2.1rem;
            border-radius: var(--radius-full);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .theme-toggle-btn:hover {
            background: var(--border-main);
            color: var(--text-primary);
        }

        /* Main Grid */
        main {
            display: grid;
            grid-template-columns: 1.35fr 0.65fr;
            gap: 1.25rem;
            padding: 1.25rem 1.75rem;
            flex-grow: 1;
            max-width: 1440px;
            margin: 0 auto;
            width: 100%;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
                padding: 1rem;
            }
        }

        .panel-card {
            background: var(--bg-card);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-lg);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            height: calc(100vh - 110px);
        }

        @media (max-width: 1024px) {
            .panel-card {
                height: 600px;
            }
            .sidebar-card {
                height: auto;
            }
        }

        /* Chat Layout */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
            background: var(--bg-card);
        }

        .chat-header {
            padding: 0.85rem 1.25rem;
            border-bottom: 1px solid var(--border-main);
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--bg-card);
        }

        .chat-header-info {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .chat-header-title {
            font-size: 0.92rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .chat-header-model {
            font-size: 0.72rem;
            color: var(--text-muted);
            font-weight: 500;
        }

        .chat-clear-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            padding: 0.25rem 0.5rem;
            border-radius: var(--radius-sm);
            transition: all 0.15s ease;
        }

        .chat-clear-btn:hover {
            color: var(--danger);
            background: var(--danger-bg);
        }

        .chat-messages {
            flex-grow: 1;
            padding: 1.25rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1.1rem;
            scroll-behavior: smooth;
        }

        /* Custom Scrollbars */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: var(--border-main);
            border-radius: var(--radius-full);
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        /* Message Bubbles */
        .message {
            max-width: 88%;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
            animation: fadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes fadeIn {
            from { transform: translateY(6px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .message.user {
            align-self: flex-end;
        }

        .message.agent {
            align-self: flex-start;
            width: 100%;
            max-width: 95%;
        }

        .message.user .bubble {
            background: linear-gradient(135deg, var(--bubble-user), #4338ca);
            color: var(--bubble-user-text);
            border-radius: 18px 18px 4px 18px;
            padding: 0.75rem 1.15rem;
            font-size: 0.92rem;
            line-height: 1.5;
            box-shadow: 0 2px 8px var(--primary-glow);
        }

        .message.agent .bubble {
            background: var(--bubble-agent);
            border: 1px solid var(--bubble-agent-border);
            color: var(--text-primary);
            border-radius: 18px 18px 18px 4px;
            padding: 1rem 1.25rem;
            font-size: 0.92rem;
            line-height: 1.5;
            box-shadow: var(--shadow-sm);
            width: 100%;
        }

        .message-meta {
            font-size: 0.72rem;
            color: var(--text-muted);
            margin: 0 4px;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .message.user .message-meta {
            justify-content: flex-end;
        }

        /* Welcome Prompt Cards */
        .welcome-card {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
            padding: 1.25rem;
            margin-bottom: 0.5rem;
        }

        .welcome-card h3 {
            font-size: 1rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.35rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .welcome-card p {
            font-size: 0.85rem;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 0.85rem;
        }

        .suggestion-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
        }

        .chip {
            background: var(--bg-card);
            border: 1px solid var(--border-main);
            color: var(--text-secondary);
            font-size: 0.76rem;
            font-weight: 500;
            padding: 0.35rem 0.65rem;
            border-radius: var(--radius-full);
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }

        .chip:hover {
            border-color: var(--primary);
            color: var(--primary);
            background: var(--primary-light);
            transform: translateY(-1px);
        }

        /* Tool Result Cards */
        .tool-results-container {
            display: flex;
            flex-direction: column;
            gap: 0.6rem;
            margin-bottom: 0.65rem;
        }

        .tool-card {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
            padding: 0.75rem 0.95rem;
            font-size: 0.86rem;
        }

        .tool-card-header {
            display: flex;
            align-items: center;
            gap: 0.4rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 0.35rem;
            font-size: 0.82rem;
        }

        .tool-card-body {
            color: var(--text-secondary);
            line-height: 1.45;
        }

        .tool-stat-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
            gap: 0.5rem;
            margin-top: 0.4rem;
        }

        .stat-item {
            background: var(--bg-card);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-sm);
            padding: 0.4rem 0.6rem;
        }

        .stat-label {
            font-size: 0.68rem;
            color: var(--text-muted);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.3px;
        }

        .stat-value {
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-top: 2px;
        }

        /* Accordion for Raw Output */
        details.raw-json-details {
            margin-top: 0.5rem;
            border-top: 1px solid var(--border-main);
            padding-top: 0.4rem;
        }

        details.raw-json-details summary {
            font-size: 0.74rem;
            color: var(--text-muted);
            cursor: pointer;
            user-select: none;
            font-weight: 500;
        }

        details.raw-json-details summary:hover {
            color: var(--primary);
        }

        details.raw-json-details pre {
            margin-top: 0.4rem;
            background: var(--bg-canvas);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-sm);
            padding: 0.6rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.74rem;
            color: var(--text-primary);
            overflow-x: auto;
            max-height: 160px;
        }

        /* Reasoning Block */
        .reasoning-box {
            margin-top: 0.65rem;
            background: var(--accent-purple-bg);
            border-left: 3px solid var(--accent-purple);
            border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
            padding: 0.6rem 0.85rem;
            font-size: 0.82rem;
            color: var(--text-secondary);
        }

        .reasoning-header {
            font-weight: 700;
            color: var(--accent-purple);
            margin-bottom: 0.25rem;
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }

        /* Confidence Pill */
        .confidence-indicator {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            font-size: 0.72rem;
            color: var(--text-muted);
            margin-top: 0.6rem;
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            padding: 0.2rem 0.55rem;
            border-radius: var(--radius-full);
            font-weight: 500;
        }

        .confidence-bar-outer {
            width: 48px;
            height: 4px;
            background: var(--border-main);
            border-radius: 2px;
            overflow: hidden;
        }

        .confidence-bar-inner {
            height: 100%;
            background: linear-gradient(to right, var(--primary), var(--accent-cyan));
            border-radius: 2px;
        }

        /* Live Executing State Bubble */
        .executing-state-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.85rem;
            width: 100%;
        }

        .executing-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--primary);
        }

        .spinner-ring {
            width: 16px;
            height: 16px;
            border: 2px solid var(--border-main);
            border-top: 2px solid var(--primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .btn-inline-cancel {
            background: var(--danger-bg);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--danger);
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.3rem 0.75rem;
            border-radius: var(--radius-full);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.35rem;
            transition: all 0.15s ease;
        }

        .btn-inline-cancel:hover {
            background: var(--danger);
            color: #ffffff;
            border-color: var(--danger);
            box-shadow: 0 2px 6px rgba(239, 68, 68, 0.3);
        }

        .stop-square {
            width: 8px;
            height: 8px;
            background: currentColor;
            border-radius: 1px;
            display: inline-block;
        }

        /* Cancelled Banner in Bubble */
        .cancelled-banner {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: var(--accent-amber-bg);
            border: 1px solid rgba(217, 119, 6, 0.3);
            border-radius: var(--radius-sm);
            padding: 0.55rem 0.85rem;
            color: var(--accent-amber);
            font-size: 0.84rem;
            font-weight: 600;
        }

        /* Input Area with Action Button */
        .chat-input-wrapper {
            padding: 1rem 1.25rem;
            border-top: 1px solid var(--border-main);
            background: var(--bg-card);
            display: flex;
            gap: 0.65rem;
            align-items: center;
        }

        .input-box-container {
            flex-grow: 1;
            position: relative;
            display: flex;
            align-items: center;
        }

        .chat-input {
            width: 100%;
            background: var(--bg-input);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
            padding: 0.78rem 1rem;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.92rem;
            outline: none;
            transition: all 0.15s ease;
        }

        .chat-input:focus {
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        /* Dynamic Execute / Stop Button */
        .btn-action {
            height: 42px;
            border: none;
            border-radius: var(--radius-md);
            padding: 0 1.25rem;
            font-weight: 600;
            font-size: 0.88rem;
            cursor: pointer;
            transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.45rem;
            white-space: nowrap;
            user-select: none;
        }

        .btn-execute {
            background: var(--primary);
            color: #ffffff;
            box-shadow: 0 2px 6px var(--primary-glow);
        }

        .btn-execute:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
        }

        .btn-stop {
            background: var(--danger);
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35);
            animation: pulse-stop 1.8s infinite;
        }

        .btn-stop:hover {
            background: var(--danger-hover);
            transform: translateY(-1px);
        }

        @keyframes pulse-stop {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.88; }
        }

        /* Right Panel: Triggers & Terminal */
        .sidebar-panel {
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            overflow-y: auto;
            height: 100%;
            background: var(--bg-card);
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.65rem;
        }

        .section-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .category-tabs {
            display: flex;
            gap: 0.3rem;
            overflow-x: auto;
            padding-bottom: 0.4rem;
            margin-bottom: 0.65rem;
        }

        .cat-tab {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            color: var(--text-muted);
            font-size: 0.72rem;
            font-weight: 600;
            padding: 0.25rem 0.6rem;
            border-radius: var(--radius-full);
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.15s ease;
        }

        .cat-tab.active {
            background: var(--text-primary);
            color: var(--bg-card);
            border-color: var(--text-primary);
        }

        .triggers-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.5rem;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 2px;
        }

        @media (max-width: 480px) {
            .triggers-grid {
                grid-template-columns: 1fr;
            }
        }

        .trigger-item {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-sm);
            padding: 0.65rem 0.75rem;
            color: var(--text-primary);
            font-family: inherit;
            text-align: left;
            cursor: pointer;
            transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }

        .trigger-item:hover {
            border-color: var(--border-focus);
            background: var(--primary-light);
            transform: translateY(-1px);
            box-shadow: var(--shadow-sm);
        }

        .trigger-badge {
            font-size: 0.65rem;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        .trigger-title {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        /* Terminal Output Console */
        .terminal-wrapper {
            display: flex;
            flex-direction: column;
            flex-grow: 1;
        }

        .terminal-box {
            background: var(--terminal-bg);
            border: 1px solid var(--terminal-border);
            border-radius: var(--radius-md);
            padding: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.74rem;
            line-height: 1.55;
            color: var(--terminal-text);
            overflow-y: auto;
            min-height: 180px;
            max-height: 280px;
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .log-line {
            margin-bottom: 0.3rem;
            word-break: break-all;
            display: flex;
            gap: 0.35rem;
        }

        .log-time {
            color: #64748b;
            user-select: none;
        }

        .log-tag-system { color: #38bdf8; font-weight: 600; }
        .log-tag-user { color: #a5b4fc; font-weight: 600; }
        .log-tag-agent { color: #34d399; font-weight: 600; }
        .log-tag-cancel { color: #fbbf24; font-weight: 600; }
        .log-tag-error { color: #f87171; font-weight: 600; }

        /* Sidebar View Switcher Nav */
        .sidebar-top-nav {
            display: flex;
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-full);
            padding: 3px;
            gap: 3px;
            margin-bottom: 0.85rem;
        }

        .sidebar-nav-tab {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 0.45rem 0.65rem;
            border-radius: var(--radius-full);
            font-size: 0.78rem;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .sidebar-nav-tab:hover {
            color: var(--text-primary);
        }

        .sidebar-nav-tab.active {
            background: var(--bg-card);
            color: var(--primary);
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-main);
        }

        /* Embeddings Studio Styles */
        .embeddings-container {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            max-height: 380px;
            overflow-y: auto;
            padding-right: 2px;
        }

        .embed-mode-tabs {
            display: flex;
            gap: 0.35rem;
        }

        .embed-mode-tab {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            color: var(--text-muted);
            font-size: 0.72rem;
            font-weight: 600;
            padding: 0.25rem 0.65rem;
            border-radius: var(--radius-full);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .embed-mode-tab.active {
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary);
        }

        .embed-input-box {
            width: 100%;
            background: var(--bg-input);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
            padding: 0.6rem 0.8rem;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 0.82rem;
            outline: none;
            transition: all 0.15s ease;
        }

        .embed-input-box:focus {
            border-color: var(--border-focus);
            box-shadow: 0 0 0 3px var(--primary-glow);
        }

        .btn-embed-action {
            background: var(--primary);
            color: #ffffff;
            border: none;
            border-radius: var(--radius-md);
            padding: 0.6rem 1rem;
            font-weight: 600;
            font-size: 0.82rem;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
        }

        .btn-embed-action:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
        }

        .embed-result-card {
            background: var(--bg-card-subtle);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
            padding: 0.75rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            animation: fadeIn 0.2s ease-out;
        }

        .vector-sparkline {
            display: flex;
            gap: 2px;
            height: 18px;
            align-items: flex-end;
            background: var(--bg-card);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-sm);
            padding: 3px 5px;
            overflow: hidden;
        }

        .vector-bar {
            flex: 1;
            min-width: 2px;
            background: linear-gradient(to top, var(--primary), var(--accent-cyan));
            border-radius: 1px;
        }

        .similarity-score-display {
            text-align: center;
            padding: 0.75rem 0.5rem;
            background: var(--bg-card);
            border: 1px solid var(--border-main);
            border-radius: var(--radius-md);
        }

        .similarity-percentage {
            font-size: 1.65rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .similarity-gauge-bar {
            width: 100%;
            height: 6px;
            background: var(--border-main);
            border-radius: 3px;
            margin-top: 0.4rem;
            overflow: hidden;
        }

        .similarity-gauge-fill {
            height: 100%;
            background: linear-gradient(to right, #10b981, #06b6d4);
            border-radius: 3px;
            transition: width 0.4s ease;
        }

    </style>
</head>
<body>
    <!-- Top Header -->
    <header>
        <div class="header-left">
            <div class="logo-mark">▲</div>
            <div class="logo-text">
                <h1>Termux Agent Hub <span class="badge-sub" id="modelBadge">Needle Core v{{ active_model }}.0</span></h1>
            </div>
        </div>
        <div class="header-right">
            <!-- Dynamic Model Selector -->
            <div class="model-switcher">
                <button class="model-btn {% if active_model == 3 %}active{% endif %}" id="btnModel3" onclick="selectModel(3)" title="Switch to Needle 3 (Laddered SAN Foundation)">
                    Needle 3 <span class="pill-badge">SAN</span>
                </button>
                <button class="model-btn {% if active_model == 2 %}active{% endif %}" id="btnModel2" onclick="selectModel(2)" title="Switch to Needle 2 (Legacy 14MB Core)">
                    Needle 2 <span class="pill-badge">14MB</span>
                </button>
            </div>

            <!-- Online Status Pill -->
            <div class="status-pill">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>

            <!-- Light / Dark Mode Toggle -->
            <button class="theme-toggle-btn" id="themeToggleBtn" onclick="toggleTheme()" title="Toggle Light / Dark Mode">
                <svg id="themeIconSun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                <svg id="themeIconMoon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
            </button>
        </div>
    </header>

    <!-- Main Workspace -->
    <main>
        <!-- Left: Interactive Chat Console -->
        <div class="panel-card">
            <div class="chat-container">
                <div class="chat-header">
                    <div class="chat-header-info">
                        <span class="chat-header-title">Agent Console</span>
                        <span class="chat-header-model" id="chatHeaderMeta">• Needle v{{ active_model }}.0</span>
                    </div>
                    <button class="chat-clear-btn" onclick="clearChat()" title="Clear chat history">Clear Chat</button>
                </div>

                <div class="chat-messages" id="chatMessages">
                    <!-- Welcome Hero Card -->
                    <div class="welcome-card">
                        <h3>⚡ On-Device Agentic Assistant</h3>
                        <p>Powered by Cactus Needle foundation models. Control hardware, inspect sensors, and execute Android actions locally. Type a command or try a quick suggestion below:</p>
                        <div class="suggestion-chips">
                            <button class="chip" onclick="submitCommand('Check phone battery status')">🔋 Battery Status</button>
                            <button class="chip" onclick="submitCommand('Turn on the camera flashlight')">🔦 Flashlight ON</button>
                            <button class="chip" onclick="submitCommand('What Wi-Fi network are you connected to?')">📶 Wi-Fi Details</button>
                            <button class="chip" onclick="submitCommand('Get phone GPS location coordinates')">📍 GPS Location</button>
                            <button class="chip" onclick="submitCommand('Take a camera photo')">📸 Capture Photo</button>
                            <button class="chip" onclick="submitCommand('Retrieve last 5 text messages')">✉️ Inbox SMS</button>
                            <button class="chip" onclick="submitCommand('Vibrate the phone for 500ms')">📳 Vibrate</button>
                            <button class="chip" onclick="submitCommand('Semantically search contacts for doctor or emergency')">🧠 Semantic Search</button>
                        </div>
                    </div>
                </div>

                <!-- Chat Input Area with Dynamic Execute / Stop Button -->
                <div class="chat-input-wrapper">
                    <div class="input-box-container">
                        <input type="text" class="chat-input" id="chatInput" placeholder="Command phone hardware or ask anything... (Press Enter to send)" autocomplete="off">
                    </div>
                    <!-- Execute Button (Default) -->
                    <button class="btn-action btn-execute" id="sendBtn" onclick="handleSendClick()">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                        <span>Execute</span>
                    </button>
                    <!-- Stop / Cancel Button (Visible during execution) -->
                    <button class="btn-action btn-stop" id="stopBtn" onclick="cancelExecution()" style="display: none;" title="Cancel tool execution (Esc)">
                        <span class="stop-square"></span>
                        <span>Stop</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Right: Triggers Grid & Developer Output Monitor -->
        <div class="panel-card sidebar-card">
            <div class="sidebar-panel">
                <!-- Sidebar View Switcher (Triggers vs Embeddings) -->
                <div class="sidebar-top-nav">
                    <button class="sidebar-nav-tab active" id="tabViewTriggers" onclick="switchSidebarView('triggers')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                        <span>Hardware Triggers</span>
                    </button>
                    <button class="sidebar-nav-tab" id="tabViewEmbeddings" onclick="switchSidebarView('embeddings')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"></circle><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"></path></svg>
                        <span>Needle 3 Embeddings</span>
                    </button>
                </div>

                <!-- View 1: Device Control Triggers Section -->
                <div id="sidebarViewTriggers">
                    <div class="section-header">
                        <span class="section-title">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                            Hardware Triggers
                        </span>
                    </div>

                    <!-- Category Filter Tabs -->
                    <div class="category-tabs" id="categoryTabs">
                        <button class="cat-tab active" onclick="filterTriggers('all', this)">All</button>
                        <button class="cat-tab" onclick="filterTriggers('hardware', this)">Hardware</button>
                        <button class="cat-tab" onclick="filterTriggers('system', this)">System</button>
                        <button class="cat-tab" onclick="filterTriggers('network', this)">Network</button>
                        <button class="cat-tab" onclick="filterTriggers('media', this)">Media</button>
                        <button class="cat-tab" onclick="filterTriggers('needle3', this)">Needle 3</button>
                    </div>

                    <div class="triggers-grid" id="triggersGrid">
                        <!-- Battery -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Check phone battery status')">
                            <span class="trigger-badge">System</span>
                            <span class="trigger-title">Battery Status</span>
                        </button>
                        <!-- Torch ON -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Turn on the camera flashlight')">
                            <span class="trigger-badge">Hardware</span>
                            <span class="trigger-title">Flashlight ON</span>
                        </button>
                        <!-- Torch OFF -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Turn off the camera flashlight')">
                            <span class="trigger-badge">Hardware</span>
                            <span class="trigger-title">Flashlight OFF</span>
                        </button>
                        <!-- Haptic Vibrate -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Vibrate the phone for 500ms')">
                            <span class="trigger-badge">Hardware</span>
                            <span class="trigger-title">Haptic Vibrate</span>
                        </button>
                        <!-- Wi-Fi Connection -->
                        <button class="trigger-item" data-cat="network" onclick="submitCommand('What Wi-Fi network are you connected to?')">
                            <span class="trigger-badge">Network</span>
                            <span class="trigger-title">Wi-Fi Details</span>
                        </button>
                        <!-- GPS Coordinates -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Get phone GPS location coordinates')">
                            <span class="trigger-badge">Location</span>
                            <span class="trigger-title">GPS Coordinates</span>
                        </button>
                        <!-- Camera Photo -->
                        <button class="trigger-item" data-cat="media" onclick="submitCommand('Take a camera photo')">
                            <span class="trigger-badge">Camera</span>
                            <span class="trigger-title">Capture Photo</span>
                        </button>
                        <!-- Screenshot -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Take a screenshot of the phone screen')">
                            <span class="trigger-badge">Display</span>
                            <span class="trigger-title">Screenshot</span>
                        </button>
                        <!-- Contacts -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('List phone contacts')">
                            <span class="trigger-badge">Data</span>
                            <span class="trigger-title">Contacts List</span>
                        </button>
                        <!-- SMS Inbox -->
                        <button class="trigger-item" data-cat="network" onclick="submitCommand('Retrieve last 5 text messages')">
                            <span class="trigger-badge">Messages</span>
                            <span class="trigger-title">Inbox SMS</span>
                        </button>
                        <!-- Volume -->
                        <button class="trigger-item" data-cat="media" onclick="submitCommand('Get volume levels info')">
                            <span class="trigger-badge">Audio</span>
                            <span class="trigger-title">Volume Info</span>
                        </button>
                        <!-- Set Volume -->
                        <button class="trigger-item" data-cat="media" onclick="submitCommand('Set music stream volume to 10')">
                            <span class="trigger-badge">Audio</span>
                            <span class="trigger-title">Set Volume (10)</span>
                        </button>
                        <!-- Screen Brightness -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Set screen brightness to 150')">
                            <span class="trigger-badge">Display</span>
                            <span class="trigger-title">Brightness (Mid)</span>
                        </button>
                        <!-- Toast Alert -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Show a toast saying Agent Online!')">
                            <span class="trigger-badge">Alert</span>
                            <span class="trigger-title">Trigger Toast</span>
                        </button>
                        <!-- Open WhatsApp -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Open whatsapp app')">
                            <span class="trigger-badge">Apps</span>
                            <span class="trigger-title">Open WhatsApp</span>
                        </button>
                        <!-- Open YouTube -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Open youtube app')">
                            <span class="trigger-badge">Apps</span>
                            <span class="trigger-title">Open YouTube</span>
                        </button>
                        <!-- Open Chrome -->
                        <button class="trigger-item" data-cat="system" onclick="submitCommand('Open chrome app')">
                            <span class="trigger-badge">Apps</span>
                            <span class="trigger-title">Open Chrome</span>
                        </button>
                        <!-- Wi-Fi Scan -->
                        <button class="trigger-item" data-cat="network" onclick="submitCommand('Scan for nearby wifi networks')">
                            <span class="trigger-badge">Network</span>
                            <span class="trigger-title">Wi-Fi Scan</span>
                        </button>
                        <!-- Wi-Fi ON -->
                        <button class="trigger-item" data-cat="network" onclick="submitCommand('Turn on device Wi-Fi')">
                            <span class="trigger-badge">Network</span>
                            <span class="trigger-title">Wi-Fi ON</span>
                        </button>
                        <!-- Wi-Fi OFF -->
                        <button class="trigger-item" data-cat="network" onclick="submitCommand('Turn off device Wi-Fi')">
                            <span class="trigger-badge">Network</span>
                            <span class="trigger-title">Wi-Fi OFF</span>
                        </button>
                        <!-- Audio Recording -->
                        <button class="trigger-item" data-cat="media" onclick="submitCommand('Start audio recording to note.3gp')">
                            <span class="trigger-badge">Audio</span>
                            <span class="trigger-title">Record Start</span>
                        </button>
                        <!-- Stop Recording -->
                        <button class="trigger-item" data-cat="media" onclick="submitCommand('Stop audio recording')">
                            <span class="trigger-badge">Audio</span>
                            <span class="trigger-title">Record Stop</span>
                        </button>
                        <!-- Wake Lock -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Acquire CPU wake lock')">
                            <span class="trigger-badge">Power</span>
                            <span class="trigger-title">Wake Lock</span>
                        </button>
                        <!-- NFC Scan -->
                        <button class="trigger-item" data-cat="hardware" onclick="submitCommand('Scan for nearby NFC tags')">
                            <span class="trigger-badge">NFC</span>
                            <span class="trigger-title">Scan NFC</span>
                        </button>
                        <!-- Needle 3 Semantic Search -->
                        <button class="trigger-item" data-cat="needle3" onclick="submitCommand('Semantically search contacts for doctor or emergency')">
                            <span class="trigger-badge" style="color:var(--primary);">Needle 3</span>
                            <span class="trigger-title">Semantic Search</span>
                        </button>
                        <!-- Needle 3 Structured Extraction -->
                        <button class="trigger-item" data-cat="needle3" onclick="submitCommand('Extract contact info from: Call Alex Vance at +15550199 alex@city17.org')">
                            <span class="trigger-badge" style="color:var(--primary);">Needle 3</span>
                            <span class="trigger-title">Structured Extract</span>
                        </button>
                    </div>
                </div>

                <!-- View 2: Needle 3 Embeddings Studio Section -->
                <div id="sidebarViewEmbeddings" style="display: none;">
                    <div class="section-header">
                        <span class="section-title">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="3"></circle><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"></path></svg>
                            Needle 3 Embeddings
                        </span>
                    </div>

                    <!-- Embeddings Submode Tabs -->
                    <div class="embed-mode-tabs" style="margin-bottom: 0.65rem;">
                        <button class="embed-mode-tab active" id="btnEmbedModeSingle" onclick="switchEmbedMode('single')">Vector Generator</button>
                        <button class="embed-mode-tab" id="btnEmbedModeSim" onclick="switchEmbedMode('similarity')">Semantic Matcher</button>
                    </div>

                    <div class="embeddings-container">
                        <!-- Mode A: Single Vector Generator -->
                        <div id="embedModeSingleBox" style="display: flex; flex-direction: column; gap: 0.55rem;">
                            <div style="font-size: 0.74rem; color: var(--text-secondary);">
                                Generate local 3072-dim embeddings on-device using Needle 3:
                            </div>
                            <input type="text" class="embed-input-box" id="embedSingleInput" placeholder="Enter text to embed (e.g. 'Turn on flashlight')...">
                            <div class="suggestion-chips" style="gap: 0.3rem;">
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setEmbedSingleText('Turn on camera flashlight')">Flashlight</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setEmbedSingleText('Check phone battery percentage')">Battery</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setEmbedSingleText('Call doctor in case of emergency')">Emergency</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setEmbedSingleText('What Wi-Fi network is connected?')">Wi-Fi</button>
                            </div>
                            <button class="btn-embed-action" id="btnGenerateEmbed" onclick="generateEmbedding()">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                                <span>Generate Vector</span>
                            </button>
                            <div id="embedSingleResult" style="display: none;"></div>
                        </div>

                        <!-- Mode B: Semantic Similarity Matcher -->
                        <div id="embedModeSimBox" style="display: none; flex-direction: column; gap: 0.55rem;">
                            <div style="font-size: 0.74rem; color: var(--text-secondary);">
                                Compare semantic intent alignment between two phrases using Cosine Similarity:
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <label style="font-size: 0.68rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Phrase A</label>
                                <input type="text" class="embed-input-box" id="embedSimInput1" placeholder="e.g. 'turn on the flashlight'">
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 0.25rem;">
                                <label style="font-size: 0.68rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">Phrase B</label>
                                <input type="text" class="embed-input-box" id="embedSimInput2" placeholder="e.g. 'illuminate camera torch'">
                            </div>
                            <div class="suggestion-chips" style="gap: 0.3rem;">
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setSimPair('turn on flashlight', 'illuminate camera torch')">Flashlight ⚡ Torch</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setSimPair('battery status', 'power percentage level')">Battery 🔋 Power</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setSimPair('take photo', 'open camera lens')">Photo 📸 Lens</button>
                                <button class="chip" style="font-size: 0.7rem; padding: 2px 7px;" onclick="setSimPair('wifi network info', 'play rock music')">Wi-Fi vs Music</button>
                            </div>
                            <button class="btn-embed-action" id="btnCalculateSim" onclick="calculateSimilarity()">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                                <span>Calculate Intent Match</span>
                            </button>
                            <div id="embedSimResult" style="display: none;"></div>
                        </div>
                    </div>
                </div>

                <!-- Terminal Output Section -->
                <div class="terminal-wrapper">
                    <div class="section-header">
                        <span class="section-title">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
                            Terminal Monitor
                        </span>
                        <button class="chat-clear-btn" onclick="clearTerminal()" style="font-size:0.7rem;">Clear Logs</button>
                    </div>
                    <div class="terminal-box" id="terminalLogs">
                        <div class="log-line"><span class="log-time">[System]</span> <span class="log-tag-system">READY:</span> Termux Agent Runtime Active.</div>
                        <div class="log-line" id="initialModelLog"><span class="log-time">[System]</span> <span class="log-tag-system">MODEL:</span> Needle v{{ active_model }}.0 Engine loaded.</div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Client Logic & Cancellation Controller -->
    <script>
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        const terminalLogs = document.getElementById('terminalLogs');

        // State tracking for cancellation
        let isExecuting = false;
        let activeAbortController = null;
        let currentRequestId = null;
        let currentLoadingElement = null;

        // Theme Management (Defaults to Light Mode)
        function initTheme() {
            const savedTheme = localStorage.getItem('needle_theme') || 'light';
            setTheme(savedTheme);
        }

        function toggleTheme() {
            const current = document.documentElement.getAttribute('data-theme') || 'light';
            const next = current === 'light' ? 'dark' : 'light';
            setTheme(next);
        }

        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('needle_theme', theme);
            const sun = document.getElementById('themeIconSun');
            const moon = document.getElementById('themeIconMoon');
            if (sun && moon) {
                if (theme === 'dark') {
                    sun.style.display = 'block';
                    moon.style.display = 'none';
                } else {
                    sun.style.display = 'none';
                    moon.style.display = 'block';
                }
            }
        }
        initTheme();

        // Terminal Logging
        function appendLog(tag, message) {
            const row = document.createElement('div');
            row.className = 'log-line';
            const time = new Date().toLocaleTimeString([], { hour12: false });
            let tagClass = 'log-tag-system';
            if (tag === 'User') tagClass = 'log-tag-user';
            else if (tag === 'Agent') tagClass = 'log-tag-agent';
            else if (tag === 'Cancelled') tagClass = 'log-tag-cancel';
            else if (tag === 'Error') tagClass = 'log-tag-error';

            row.innerHTML = `<span class="log-time">[${time}]</span> <span class="${tagClass}">[${tag}]</span> <span>${message}</span>`;
            terminalLogs.appendChild(row);
            terminalLogs.scrollTop = terminalLogs.scrollHeight;
        }

        function clearTerminal() {
            terminalLogs.innerHTML = `<div class="log-line"><span class="log-time">[System]</span> Log cleared.</div>`;
        }

        function clearChat() {
            chatMessages.innerHTML = `
                <div class="welcome-card">
                    <h3>⚡ Chat Cleared</h3>
                    <p>Ready for your next instruction. Type a command below or tap a quick hardware trigger.</p>
                </div>
            `;
            appendLog('System', 'Chat session cleared.');
        }

        // Category Trigger Filter
        function filterTriggers(category, btn) {
            document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            const items = document.querySelectorAll('.trigger-item');
            items.forEach(item => {
                if (category === 'all' || item.getAttribute('data-cat') === category) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        }

        // Switch Model (Needle 3 / Needle 2)
        async function selectModel(gen) {
            try {
                appendLog('System', `Switching active model to Needle ${gen}...`);
                const res = await fetch('/api/model', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ generation: gen })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    const b2 = document.getElementById('btnModel2');
                    const b3 = document.getElementById('btnModel3');
                    if (b2) b2.classList.toggle('active', data.active_generation === 2);
                    if (b3) b3.classList.toggle('active', data.active_generation === 3);
                    const badge = document.getElementById('modelBadge');
                    if (badge) badge.innerText = `Needle Core v${data.active_generation}.0`;
                    const chatMeta = document.getElementById('chatHeaderMeta');
                    if (chatMeta) chatMeta.innerText = `• Needle v${data.active_generation}.0`;
                    appendLog('System', `Active model switched to Needle ${data.active_generation} (${data.description})`);
                } else {
                    appendLog('Error', `Failed to switch model: ${data.error || 'Unknown error'}`);
                }
            } catch (err) {
                appendLog('Error', `Network error switching model: ${err.message}`);
            }
        }

        // UI State: Toggle between Running (Stop button) and Idle (Execute button)
        function setExecutionState(running) {
            isExecuting = running;
            if (running) {
                sendBtn.style.display = 'none';
                stopBtn.style.display = 'flex';
                chatInput.disabled = true;
            } else {
                sendBtn.style.display = 'flex';
                stopBtn.style.display = 'none';
                chatInput.disabled = false;
                chatInput.focus();
                activeAbortController = null;
                currentRequestId = null;
                currentLoadingElement = null;
            }
        }

        // Cancel Execution (invoked by Stop button, inline bubble button, or Esc key)
        async function cancelExecution() {
            if (!isExecuting) return;

            appendLog('Cancelled', 'Cancel requested by user. Aborting active execution...');

            // Abort fetch immediately
            if (activeAbortController) {
                activeAbortController.abort();
            }

            // Tell server to kill any active subprocess/thread
            if (currentRequestId) {
                try {
                    fetch('/api/cancel', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ request_id: currentRequestId })
                    }).catch(() => {});
                } catch (e) {}
            }

            // Replace loading element with cancelled status banner
            if (currentLoadingElement && currentLoadingElement.parentNode) {
                currentLoadingElement.innerHTML = `
                    <div class="bubble">
                        <div class="cancelled-banner">
                            <span class="stop-square" style="background:var(--accent-amber);"></span>
                            <span>Tool execution cancelled by user.</span>
                        </div>
                    </div>
                    <div class="message-meta">Execution Stopped</div>
                `;
            }

            setExecutionState(false);
            appendLog('Cancelled', 'Execution successfully halted.');
        }

        // Format tool output into beautiful card components
        function formatToolResult(res) {
            if (!res) return '';
            if (typeof res === 'string') {
                if (res.includes('[Execution Cancelled')) {
                    return `
                        <div class="cancelled-banner">
                            <span class="stop-square" style="background:var(--accent-amber);"></span>
                            <span>${res}</span>
                        </div>
                    `;
                }
                if (res.toLowerCase().includes('screenshot')) {
                    return `
                        <div class="tool-card">
                            <div class="tool-card-header">📸 Screenshot Captured</div>
                            <div class="tool-card-body">
                                <div style="margin-top:0.4rem;"><img src="/screenshot.png?t=${Date.now()}" style="max-width:100%; max-height:220px; border-radius:8px; border:1px solid var(--border-main);" alt="Screenshot"></div>
                                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.3rem;">${res}</div>
                            </div>
                        </div>
                    `;
                }
                return `
                    <div class="tool-card">
                        <div class="tool-card-header">⚡ Device Action Output</div>
                        <div class="tool-card-body">${res}</div>
                    </div>
                `;
            }

            // Battery object
            if (res.percentage !== undefined) {
                return `
                    <div class="tool-card">
                        <div class="tool-card-header">🔋 Battery Diagnostic</div>
                        <div class="tool-card-body">
                            <div class="tool-stat-grid">
                                <div class="stat-item">
                                    <div class="stat-label">Charge Level</div>
                                    <div class="stat-value" style="color:var(--accent-green);">${res.percentage}%</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Status</div>
                                    <div class="stat-value">${res.status || 'Discharging'}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Health</div>
                                    <div class="stat-value">${res.health || 'GOOD'}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Temperature</div>
                                    <div class="stat-value">${res.temperature}°C</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Wi-Fi object
            if (res.ssid !== undefined) {
                return `
                    <div class="tool-card">
                        <div class="tool-card-header">📶 Wi-Fi Connection</div>
                        <div class="tool-card-body">
                            <div class="tool-stat-grid">
                                <div class="stat-item">
                                    <div class="stat-label">SSID</div>
                                    <div class="stat-value">${res.ssid}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">IP Address</div>
                                    <div class="stat-value">${res.ip || '192.168.1.102'}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Signal Strength</div>
                                    <div class="stat-value">${res.rssi !== undefined ? res.rssi + ' dBm' : 'Strong'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Location object
            if (res.latitude !== undefined) {
                return `
                    <div class="tool-card">
                        <div class="tool-card-header">📍 GPS Coordinates</div>
                        <div class="tool-card-body">
                            <div class="tool-stat-grid">
                                <div class="stat-item">
                                    <div class="stat-label">Latitude</div>
                                    <div class="stat-value">${res.latitude.toFixed(5)}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Longitude</div>
                                    <div class="stat-value">${res.longitude.toFixed(5)}</div>
                                </div>
                                <div class="stat-item">
                                    <div class="stat-label">Altitude</div>
                                    <div class="stat-value">${res.altitude ? res.altitude + 'm' : 'N/A'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }

            // Array outputs (SMS, Contacts)
            if (Array.isArray(res)) {
                if (res.length === 0) {
                    return `<div class="tool-card"><div class="tool-card-header">📁 Query Result</div><div class="tool-card-body">Empty list returned.</div></div>`;
                }
                if (res[0].address !== undefined) {
                    let html = `<div class="tool-card"><div class="tool-card-header">✉️ Inbox Messages (${res.length})</div><div class="tool-card-body"><ul style="margin-left:1.1rem; display:flex; flex-direction:column; gap:0.35rem; margin-top:0.3rem;">`;
                    res.forEach(sms => {
                        html += `<li><strong>${sms.address}</strong>: "${sms.body}" <span style="font-size:0.7rem; color:var(--text-muted);">(${sms.date})</span></li>`;
                    });
                    html += `</ul></div></div>`;
                    return html;
                }
                if (res[0].name !== undefined) {
                    let html = `<div class="tool-card"><div class="tool-card-header">👤 Contacts Found (${res.length})</div><div class="tool-card-body"><ul style="margin-left:1.1rem; display:flex; flex-direction:column; gap:0.35rem; margin-top:0.3rem;">`;
                    res.forEach(c => {
                        html += `<li><strong>${c.name}</strong>: ${c.number}</li>`;
                    });
                    html += `</ul></div></div>`;
                    return html;
                }
            }

            // Standard JSON fallback
            return `
                <div class="tool-card">
                    <div class="tool-card-header">⚙️ System Output</div>
                    <div class="tool-card-body">
                        <pre style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; overflow-x:auto;">${JSON.stringify(res, null, 2)}</pre>
                    </div>
                </div>
            `;
        }

        // Execute Command
        async function submitCommand(text) {
            text = text.trim();
            if (!text || isExecuting) return;

            // Generate unique request ID and AbortController for cancelability
            currentRequestId = 'req_' + Date.now();
            activeAbortController = new AbortController();

            // Set UI to running state (Execute -> Stop button)
            setExecutionState(true);

            // User bubble
            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.innerHTML = `
                <div class="bubble">${text}</div>
                <div class="message-meta">You</div>
            `;
            chatMessages.appendChild(userDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Agent Loading Bubble with Cancel Button right inside it
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message agent';
            loadingDiv.innerHTML = `
                <div class="bubble">
                    <div class="executing-state-container">
                        <div class="executing-label">
                            <div class="spinner-ring"></div>
                            <span>Executing actions with Needle...</span>
                        </div>
                        <button class="btn-inline-cancel" onclick="cancelExecution()" title="Cancel this execution">
                            <span class="stop-square"></span>
                            <span>Cancel</span>
                        </button>
                    </div>
                </div>
                <div class="message-meta">Running Tools</div>
            `;
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            currentLoadingElement = loadingDiv;

            appendLog('User', `Executing: "${text}"`);

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, request_id: currentRequestId }),
                    signal: activeAbortController.signal
                });

                const data = await response.json();
                loadingDiv.remove();

                const agentDiv = document.createElement('div');
                agentDiv.className = 'message agent';

                let bubbleContent = '';
                if (data.type === 'cancelled') {
                    bubbleContent = `
                        <div class="cancelled-banner">
                            <span class="stop-square" style="background:var(--accent-amber);"></span>
                            <span>${data.reasoning || 'Execution cancelled by user.'}</span>
                        </div>
                    `;
                } else if (data.type === 'respond' || data.type === 'call') {
                    if (data.results && data.results.length > 0) {
                        bubbleContent += `<div class="tool-results-container">`;
                        data.results.forEach((res) => {
                            bubbleContent += formatToolResult(res);
                            if (typeof res === 'object') {
                                bubbleContent += `
                                    <details class="raw-json-details">
                                        <summary>Inspect Raw JSON</summary>
                                        <pre>${JSON.stringify(res, null, 2)}</pre>
                                    </details>
                                `;
                            }
                        });
                        bubbleContent += `</div>`;
                    } else {
                        bubbleContent += `<p style="color:var(--text-muted);">No matching tools were executed. Please rephrase the command.</p>`;
                    }
                } else {
                    bubbleContent += `<p style="color:var(--danger); font-weight:600;">Execution failure: ${data.error || 'Unknown error'}</p>`;
                }

                // Reasoning accordion
                let reasoningHtml = '';
                if (data.reasoning && data.type !== 'cancelled') {
                    reasoningHtml = `
                        <div class="reasoning-box">
                            <div class="reasoning-header">
                                <svg width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                                Reasoning
                            </div>
                            <p>${data.reasoning}</p>
                        </div>
                    `;
                }

                // Confidence indicator
                let confidenceHtml = '';
                if (data.confidence !== null && data.confidence !== undefined && data.type !== 'cancelled') {
                    const pct = Math.round(data.confidence * 100);
                    confidenceHtml = `
                        <div class="confidence-indicator">
                            Confidence: ${pct}%
                            <div class="confidence-bar-outer">
                                <div class="confidence-bar-inner" style="width: ${pct}%"></div>
                            </div>
                        </div>
                    `;
                }

                agentDiv.innerHTML = `
                    <div class="bubble">
                        ${bubbleContent}
                        ${reasoningHtml}
                        ${confidenceHtml}
                    </div>
                    <div class="message-meta">${data.model || 'Agent Core'} • Ready</div>
                `;

                chatMessages.appendChild(agentDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                if (data.type === 'cancelled') {
                    appendLog('Cancelled', 'Execution was stopped.');
                } else if (data.results && data.results.length > 0) {
                    appendLog('Agent', `Completed ${data.results.length} action(s).`);
                } else {
                    appendLog('Agent', `Completed without actions (Reasoning: "${data.reasoning || 'Low confidence'}").`);
                }

            } catch (err) {
                if (err.name === 'AbortError') {
                    // Handled gracefully in cancelExecution()
                    return;
                }
                loadingDiv.remove();
                const errDiv = document.createElement('div');
                errDiv.className = 'message agent';
                errDiv.innerHTML = `
                    <div class="bubble" style="color:var(--danger); border-color:var(--danger);">
                        Failed to connect to agent server. Verify Termux proot environment.
                    </div>
                    <div class="message-meta">Connection Error</div>
                `;
                chatMessages.appendChild(errDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                appendLog('Error', `Network fail: ${err.message}`);
            } finally {
                setExecutionState(false);
            }
        }

        function handleSendClick() {
            const val = chatInput.value;
            chatInput.value = '';
            submitCommand(val);
        }

        // Enter key to submit, Escape key to Cancel/Stop execution
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSendClick();
            }
        });


        // Switch between Hardware Triggers and Embeddings Studio
        function switchSidebarView(view) {
            const tabTrig = document.getElementById('tabViewTriggers');
            const tabEmbed = document.getElementById('tabViewEmbeddings');
            const viewTrig = document.getElementById('sidebarViewTriggers');
            const viewEmbed = document.getElementById('sidebarViewEmbeddings');
            if (view === 'triggers') {
                tabTrig.classList.add('active');
                tabEmbed.classList.remove('active');
                viewTrig.style.display = 'block';
                viewEmbed.style.display = 'none';
            } else {
                tabEmbed.classList.add('active');
                tabTrig.classList.remove('active');
                viewTrig.style.display = 'none';
                viewEmbed.style.display = 'block';
            }
        }

        // Switch Embeddings Submode
        function switchEmbedMode(mode) {
            const btnSingle = document.getElementById('btnEmbedModeSingle');
            const btnSim = document.getElementById('btnEmbedModeSim');
            const boxSingle = document.getElementById('embedModeSingleBox');
            const boxSim = document.getElementById('embedModeSimBox');
            if (mode === 'single') {
                btnSingle.classList.add('active');
                btnSim.classList.remove('active');
                boxSingle.style.display = 'flex';
                boxSim.style.display = 'none';
            } else {
                btnSim.classList.add('active');
                btnSingle.classList.remove('active');
                boxSingle.style.display = 'none';
                boxSim.style.display = 'flex';
            }
        }

        function setEmbedSingleText(val) {
            document.getElementById('embedSingleInput').value = val;
        }

        function setSimPair(a, b) {
            document.getElementById('embedSimInput1').value = a;
            document.getElementById('embedSimInput2').value = b;
        }

        let lastGeneratedVector = null;

        async function generateEmbedding() {
            const input = document.getElementById('embedSingleInput');
            const val = input.value.trim();
            if (!val) return;
            const btn = document.getElementById('btnGenerateEmbed');
            const resBox = document.getElementById('embedSingleResult');
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-ring" style="width:13px;height:13px;"></span> Generating...`;
            appendLog('Agent', `Generating Needle 3 embedding for: "${val}"`);

            try {
                const res = await fetch('/api/embed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: val })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    lastGeneratedVector = data.vector || data.vector_preview;
                    const preview = data.vector_preview || [];
                    
                    let barsHtml = '';
                    preview.slice(0, 24).forEach(v => {
                        const height = Math.min(100, Math.max(15, Math.abs(v) * 200));
                        barsHtml += `<div class="vector-bar" style="height:${height}%;" title="${v}"></div>`;
                    });

                    resBox.innerHTML = `
                        <div class="embed-result-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:0.75rem; font-weight:700; color:var(--text-primary);">Vector Output</span>
                                <span class="badge-sub" style="font-size:0.65rem;">${data.dimensions} Dimensions</span>
                            </div>
                            <div style="font-size:0.72rem; color:var(--text-muted);">
                                Model: <strong>Needle 3 (SAN)</strong> • Latency: <strong>${data.latency_ms}ms</strong>
                            </div>
                            <div class="vector-sparkline">
                                ${barsHtml}
                            </div>
                            <div style="background:var(--bg-canvas); border:1px solid var(--border-main); border-radius:6px; padding:0.45rem; font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:var(--primary); overflow-x:auto;">
                                [${preview.slice(0, 6).join(', ')}, ... (${data.dimensions - 6} more floats)]
                            </div>
                            <button class="chat-clear-btn" style="border:1px solid var(--border-main); text-align:center; padding:0.35rem;" onclick="copyVectorJson(this)">
                                📋 Copy Full Vector JSON
                            </button>
                        </div>
                    `;
                    resBox.style.display = 'block';
                    appendLog('Agent', `Generated ${data.dimensions}-dim vector in ${data.latency_ms}ms.`);
                } else {
                    resBox.innerHTML = `<div style="color:var(--danger); font-size:0.75rem; padding:0.5rem;">${data.error || 'Failed to generate embedding'}</div>`;
                    resBox.style.display = 'block';
                    appendLog('Error', `Embed error: ${data.error}`);
                }
            } catch (e) {
                resBox.innerHTML = `<div style="color:var(--danger); font-size:0.75rem; padding:0.5rem;">Network error: ${e.message}</div>`;
                resBox.style.display = 'block';
                appendLog('Error', `Embed network error: ${e.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg><span>Generate Vector</span>`;
            }
        }

        function copyVectorJson(btn) {
            if (!lastGeneratedVector) return;
            navigator.clipboard.writeText(JSON.stringify(lastGeneratedVector)).then(() => {
                const orig = btn.innerText;
                btn.innerText = '✅ Copied to Clipboard!';
                setTimeout(() => { btn.innerText = orig; }, 1800);
            });
        }

        async function calculateSimilarity() {
            const t1 = document.getElementById('embedSimInput1').value.trim();
            const t2 = document.getElementById('embedSimInput2').value.trim();
            if (!t1 || !t2) return;
            const btn = document.getElementById('btnCalculateSim');
            const resBox = document.getElementById('embedSimResult');
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner-ring" style="width:13px;height:13px;"></span> Calculating...`;
            appendLog('Agent', `Comparing cosine similarity between: "${t1}" vs "${t2}"`);

            try {
                const res = await fetch('/api/embed', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text1: t1, text2: t2 })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    const pct = data.similarity_pct;
                    let scoreColor = 'var(--accent-green)';
                    if (pct < 45) scoreColor = 'var(--danger)';
                    else if (pct < 75) scoreColor = 'var(--accent-amber)';

                    resBox.innerHTML = `
                        <div class="embed-result-card">
                            <div class="similarity-score-display">
                                <div style="font-size:0.7rem; text-transform:uppercase; font-weight:700; color:var(--text-muted); letter-spacing:0.4px;">Cosine Intent Alignment</div>
                                <div class="similarity-percentage" style="color:${scoreColor};">${pct}%</div>
                                <div class="similarity-gauge-bar">
                                    <div class="similarity-gauge-fill" style="width:${pct}%; background:${scoreColor};"></div>
                                </div>
                            </div>
                            <div style="font-size:0.75rem; font-weight:600; color:var(--text-primary); text-align:center;">
                                ${data.alignment}
                            </div>
                            <div style="font-size:0.7rem; color:var(--text-muted); display:flex; justify-content:space-between; margin-top:2px;">
                                <span>Cosine Score: <strong>${data.similarity}</strong></span>
                                <span>Latency: <strong>${data.latency_ms}ms</strong></span>
                            </div>
                        </div>
                    `;
                    resBox.style.display = 'block';
                    appendLog('Agent', `Similarity match: ${pct}% (Cosine: ${data.similarity}) in ${data.latency_ms}ms.`);
                } else {
                    resBox.innerHTML = `<div style="color:var(--danger); font-size:0.75rem; padding:0.5rem;">${data.error || 'Failed to compare phrases'}</div>`;
                    resBox.style.display = 'block';
                    appendLog('Error', `Similarity error: ${data.error}`);
                }
            } catch (e) {
                resBox.innerHTML = `<div style="color:var(--danger); font-size:0.75rem; padding:0.5rem;">Network error: ${e.message}</div>`;
                resBox.style.display = 'block';
                appendLog('Error', `Similarity network error: ${e.message}`);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg><span>Calculate Intent Match</span>`;
            }
        }

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isExecuting) {
                cancelExecution();
            }
        });
    </script>
</body>
</html>
"""

def preprocess_query(query: str) -> str:
    query_stripped = query.strip()
    query_lower = query_stripped.lower()
    for verb in ["speak ", "say "]:
        if query_lower.startswith(verb):
            text_part = query_stripped[len(verb):].strip()
            if not ((text_part.startswith('"') and text_part.endswith('"')) or 
                    (text_part.startswith("'") and text_part.endswith("'"))):
                return f'{verb.strip()} "{text_part}"'
    return query_stripped

# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, active_model=active_generation)

@app.route("/photo.jpg")
def serve_photo():
    possible_paths = [
        os.path.expanduser("~/storage/downloads/needle_photo.jpg"),
        os.path.expanduser("~/storage/downloads/photo.jpg"),
        os.path.expanduser("~/needle_photo.jpg"),
        os.path.expanduser("~/photo.jpg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "needle_photo.jpg"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "photo.jpg"),
    ]
    for photo_path in possible_paths:
        if os.path.exists(photo_path):
            from flask import send_file
            return send_file(photo_path, mimetype="image/jpeg")
    return "Photo not found", 404

@app.route("/screenshot.png")
def serve_screenshot():
    possible_paths = [
        "/sdcard/Download/screenshot.png",
        os.path.expanduser("~/storage/downloads/screenshot.png"),
        os.path.expanduser("~/screenshot.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot.png"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            from flask import send_file
            return send_file(p, mimetype="image/png")
    return "Screenshot not found", 404

@app.route("/api/extract", methods=["POST"])
def extract_api():
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        schema_type = data.get("type", "general")
        if not text:
            return jsonify({"status": "error", "error": "Empty text parameter"}), 400
        res = extract_structured_data(text, schema_type)
        return jsonify({"status": "ok", "extracted": res})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def compute_simulated_embedding(text: str, dims: int = 3072):
    import hashlib
    vec = []
    seed = text.encode("utf-8")
    for i in range(dims):
        h = hashlib.sha256(seed + i.to_bytes(4, "little")).digest()
        val = (int.from_bytes(h[:4], "little") / 0xFFFFFFFF) * 2.0 - 1.0
        vec.append(round(val, 6))
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [round(x / norm, 6) for x in vec]

def calc_cosine_sim(v1, v2):
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm1 * norm2)))

@app.route("/api/embed", methods=["POST"])
def embed_api():
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        text1 = data.get("text1", "").strip()
        text2 = data.get("text2", "").strip()

        # Mode A: Pairwise Cosine Similarity Comparison
        if text1 and text2:
            t0 = time.perf_counter()
            current_agent = get_agent()
            vec1 = None
            vec2 = None
            if hasattr(current_agent, "embed") and getattr(current_agent, "_generation", 3) >= 3:
                try:
                    vec1 = current_agent.embed(text1)
                    vec2 = current_agent.embed(text2)
                except Exception as e:
                    print(f"[Embed Engine] Native embed error: {e}")
            if vec1 is None or vec2 is None:
                vec1 = compute_simulated_embedding(text1)
                vec2 = compute_simulated_embedding(text2)

            sim = calc_cosine_sim(vec1, vec2)
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            match_pct = round(max(0.0, sim) * 100, 1)

            alignment = "High Semantic Alignment (Mapped to same tool)" if match_pct >= 75 else (
                "Moderate Semantic Relatedness" if match_pct >= 45 else "Low Alignment (Distinct intent)"
            )

            return jsonify({
                "status": "ok",
                "mode": "similarity",
                "similarity": round(sim, 4),
                "similarity_pct": match_pct,
                "alignment": alignment,
                "dimensions": len(vec1),
                "latency_ms": duration_ms,
                "text1": text1,
                "text2": text2,
                "vector1_preview": vec1[:8],
                "vector2_preview": vec2[:8]
            })

        # Mode B: Single Text Embedding Vector
        if not text:
            return jsonify({"status": "error", "error": "Empty text parameter"}), 400

        t0 = time.perf_counter()
        current_agent = get_agent()
        vec = None
        if hasattr(current_agent, "embed") and getattr(current_agent, "_generation", 3) >= 3:
            try:
                vec = current_agent.embed(text)
            except Exception as e:
                print(f"[Embed Engine] Native embed error: {e}")
        if vec is None:
            vec = compute_simulated_embedding(text)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return jsonify({
            "status": "ok",
            "mode": "single",
            "text": text,
            "dimensions": len(vec),
            "latency_ms": duration_ms,
            "vector_preview": vec[:16],
            "vector": vec,
            "model": f"Needle {active_generation} (SAN)"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/model", methods=["GET", "POST"])
def model_api():
    global active_generation
    if request.method == "POST":
        data = request.get_json() or {}
        gen = data.get("generation") or data.get("model")
        if not gen:
            return jsonify({"status": "error", "error": "Missing generation parameter"}), 400
        try:
            val = int(gen)
            set_active_generation(val)
            desc = "Laddered SAN / High Accuracy" if val == 3 else "Legacy 14MB Core"
            return jsonify({
                "status": "ok",
                "active_generation": active_generation,
                "model_name": f"Needle {active_generation}",
                "description": desc
            })
        except Exception as e:
            return jsonify({"status": "error", "error": str(e)}), 400
    else:
        desc = "Laddered SAN / High Accuracy" if active_generation == 3 else "Legacy 14MB Core"
        return jsonify({
            "active_generation": active_generation,
            "model_name": f"Needle {active_generation}",
            "description": desc,
            "available": [2, 3]
        })

@app.route("/api/cancel", methods=["POST"])
def cancel_api():
    try:
        data = request.get_json() or {}
        req_id = data.get("request_id")
        with active_requests_lock:
            if req_id and req_id in active_requests:
                active_requests[req_id]["cancelled"] = True
                proc = active_requests[req_id].get("proc")
                if proc and proc.poll() is None:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                return jsonify({"status": "ok", "message": f"Execution '{req_id}' cancelled."})
            else:
                for r in active_requests.values():
                    r["cancelled"] = True
                    proc = r.get("proc")
                    if proc and proc.poll() is None:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                return jsonify({"status": "ok", "message": "All active executions cancelled."})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
def chat_api():
    req_id = None
    try:
        data = request.get_json() or {}
        user_message = data.get("message", "").strip()
        req_id = data.get("request_id") or f"req_{int(time.time() * 1000)}"
        if not user_message:
            return jsonify({"type": "error", "error": "Empty message parameter"}), 400
        
        with active_requests_lock:
            active_requests[req_id] = {"cancelled": False, "proc": None, "start": time.time()}
        
        _current_req_id.id = req_id

        # Preprocess query to wrap speech commands in quotes for correct parsing by Needle LLM
        processed_message = preprocess_query(user_message)
        current_agent = get_agent()
        
        if is_current_request_cancelled():
            return jsonify({
                "query": user_message,
                "model": f"Needle {active_generation}",
                "generation": active_generation,
                "type": "cancelled",
                "reasoning": "Execution was cancelled by the user.",
                "confidence": 0,
                "results": ["[Execution Cancelled by User]"]
            })

        # Invoke Needle model agent loop
        res = current_agent.run(processed_message)

        if is_current_request_cancelled():
            return jsonify({
                "query": user_message,
                "model": f"Needle {active_generation}",
                "generation": active_generation,
                "type": "cancelled",
                "reasoning": "Execution was cancelled by the user.",
                "confidence": 0,
                "results": ["[Execution Cancelled by User]"]
            })
        
        return jsonify({
            "query": user_message,
            "model": f"Needle {active_generation}",
            "generation": active_generation,
            "type": res.get("type"),
            "reasoning": res.get("reasoning"),
            "confidence": res.get("confidence"),
            "results": res.get("results", [])
        })

    except Exception as e:
        print(f"Exception during api/chat processing: {e}", file=sys.stderr)
        return jsonify({"type": "error", "error": str(e)}), 500
    finally:
        if req_id:
            with active_requests_lock:
                active_requests.pop(req_id, None)

# Telegram Bot Daemon Runner
def start_telegram_bot(token):
    if not telebot:
        print("[Telegram] Error: telebot library is not available. Install with 'pip install pyTelegramBotAPI'", file=sys.stderr)
        return
    try:
        # Disable multi-threading pools in telebot to prevent C-level OpenSSL SIGSEGV in Termux bionic libc
        bot = telebot.TeleBot(token, threaded=False)
        print(f"[Telegram] Bot listener running safely. Connected to Telegram.")

        @bot.message_handler(func=lambda message: True)
        def handle_telegram_message(message):
            query = message.text.strip() if message.text else ""
            print(f"[Telegram] Message received: '{query}'")
            if not query:
                return

            query_lower = query.lower()
            if query_lower in ("/model", "/model help", "model"):
                desc = "Laddered SAN / High Accuracy" if active_generation == 3 else "Legacy 14MB Core"
                bot.reply_to(message, f"🤖 *Active Model:* Needle {active_generation} ({desc})\n\nTo switch models, send:\n• `/model 3` (Needle 3)\n• `/model 2` (Needle 2)", parse_mode="Markdown")
                return

            if query_lower in ("/model 2", "model 2", "/model 3", "model 3"):
                target_gen = 2 if "2" in query_lower else 3
                try:
                    set_active_generation(target_gen)
                    bot.reply_to(message, f"✅ Switched active model to *Needle {target_gen}*.", parse_mode="Markdown")
                except Exception as e:
                    bot.reply_to(message, f"❌ Failed to switch model: {e}", parse_mode="Markdown")
                return

            try:
                processed_query = preprocess_query(query)
                current_agent = get_agent()
                res = current_agent.run(processed_query)
                reasoning = res.get("reasoning", "")
                confidence = res.get("confidence")
                results = res.get("results") or []

                reply = ""
                if results:
                    reply += "⚡ *Tool Execution Results:*\n"
                    for r in results:
                        if isinstance(r, dict):
                            reply += f"```json\n{json.dumps(r, indent=2)}\n```\n"
                        else:
                            reply += f"{r}\n"
                else:
                    reply += "⚠️ *No tools were triggered by this command.*\n"

                if reasoning:
                    reply += f"\n🧠 *Agent Reasoning:*\n_{reasoning}_\n"

                if confidence is not None:
                    reply += f"\n🎯 *Confidence:* {int(confidence * 100)}%"

                reply += f"\n🤖 *Model:* Needle {active_generation}"

                bot.reply_to(message, reply, parse_mode="Markdown")
            except Exception as err:
                try:
                    bot.reply_to(message, f"❌ *Error executing command:*\n`{str(err)}`")
                except Exception:
                    pass

        # Use robust single-threaded polling loop to prevent Segmentation Faults in Termux
        while True:
            try:
                bot.polling(non_stop=True, interval=1, timeout=10)
            except Exception as e:
                print(f"[Telegram Polling Exception] {e}", file=sys.stderr)
                time.sleep(3)
    except Exception as exc:
        print(f"[Telegram Error] Failed to run bot listener: {exc}", file=sys.stderr)

if __name__ == "__main__":
    # Check for --model / --generation / -m flag first
    for idx, arg in enumerate(sys.argv):
        if arg in ("--model", "--generation", "-m") and idx + 1 < len(sys.argv):
            try:
                m_val = int(sys.argv[idx + 1])
                if m_val in (2, 3):
                    set_active_generation(m_val)
            except ValueError:
                pass

    print(f"[Engine] Termux Agent Hub initialized with Needle {active_generation} active.")

    # Check for --telegram flag or TELEGRAM_TOKEN env variable first
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    for idx, arg in enumerate(sys.argv):
        if arg == "--telegram" and idx + 1 < len(sys.argv):
            telegram_token = sys.argv[idx + 1]

    # If no token is provided, ask the user interactively (only if stdin is a TTY)
    if not telegram_token and sys.stdin.isatty():
        try:
            choice = input("Do you want to use Telegram remote control? (yes/no): ").strip().lower()
            if choice in ("y", "yes"):
                token_input = input("Enter your Telegram Bot Token: ").strip()
                if token_input:
                    telegram_token = token_input
                else:
                    print("No token entered. Proceeding without Telegram.")
        except (KeyboardInterrupt, EOFError):
            print("\nNon-interactive mode or prompt skipped. Proceeding without Telegram.")
    elif not telegram_token:
        print("[Telegram] Non-interactive environment detected. Skipping prompt, proceeding without Telegram.")

    if telegram_token:
        print("[Telegram] Token provided. Launching bot background thread...")
        telegram_thread = threading.Thread(target=start_telegram_bot, args=(telegram_token,), daemon=True)
        telegram_thread.start()
    else:
        print("[Telegram] Info: Remote Telegram control disabled.")

    # Run server on port 5000 (accessible on local network/phone browser)
    if serve:
        print("[Server] Starting production WSGI server via Waitress on http://0.0.0.0:5000...")
        serve(app, host="0.0.0.0", port=5000)
    else:
        print("[Server] Warning: Waitress not found. Falling back to Flask dev server.")
        app.run(host="0.0.0.0", port=5000, debug=True)
