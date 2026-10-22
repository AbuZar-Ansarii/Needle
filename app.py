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

def run_cmd(args):
    # Try running the actual termux command first with 15s timeout for hardware warm-up
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            return res.stdout.strip() if res.stdout.strip() else "Success"
        else:
            if IS_TERMUX:
                err_msg = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
                return f"Error ({args[0]}): {err_msg}"
            raise FileNotFoundError()
    except subprocess.TimeoutExpired:
        if IS_TERMUX:
            return f"Error ({args[0]}): Command timed out after 15 seconds. Termux API might be hanging or lack permissions."
        raise FileNotFoundError()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Termux Agent Hub</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #090a0f;
            --panel-bg: #11131e;
            --border-subtle: rgba(255, 255, 255, 0.05);
            --primary: #4f46e5;
            --primary-light: #6366f1;
            --primary-glow: rgba(79, 70, 229, 0.15);
            --accent-cyan: #0891b2;
            --accent-green: #10b981;
            --text-main: #f1f5f9;
            --text-muted: #64748b;
            --chat-bubble-agent: #161824;
            --chat-bubble-user: #4f46e5;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 2rem;
            border-bottom: 1px solid var(--border-subtle);
            background: rgba(9, 10, 15, 0.85);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-mark {
            width: 1.8rem;
            height: 1.8rem;
            border-radius: 6px;
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            color: #fff;
            box-shadow: 0 0 10px var(--primary-glow);
        }

        .logo-text h1 {
            font-size: 1.1rem;
            font-weight: 600;
            letter-spacing: -0.2px;
            color: #ffffff;
        }

        .logo-text span {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 0.85rem;
        }

        .model-selector-group {
            display: flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-subtle);
            padding: 0.25rem 0.35rem;
            border-radius: 20px;
        }

        .model-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-left: 0.4rem;
            font-weight: 500;
        }

        .model-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.25rem 0.65rem;
            border-radius: 14px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .model-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }

        .model-btn.active {
            background: var(--primary);
            color: #ffffff;
            box-shadow: 0 0 10px var(--primary-glow);
        }

        .status-container {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            color: var(--accent-green);
        }

        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse-dot 2s infinite;
        }

        @keyframes pulse-dot {
            0% { transform: scale(0.95); opacity: 0.6; }
            50% { transform: scale(1.1); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.6; }
        }

        main {
            display: grid;
            grid-template-columns: 1.3fr 0.7fr;
            gap: 1.5rem;
            padding: 1.5rem;
            flex-grow: 1;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 768px) {
            main {
                padding: 0.75rem;
                gap: 1rem;
            }
            header {
                padding: 1rem;
            }
            .card {
                height: 550px; /* Limit height of chat container on mobile so triggers are easily scrollable underneath */
            }
            .triggers-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .terminal-container {
                max-height: 200px;
                min-height: 150px;
            }
        }

        @media (max-width: 480px) {
            .triggers-grid {
                grid-template-columns: 1fr; /* Single column on tiny phones for tap comfort */
            }
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            height: calc(100vh - 120px);
        }

        /* Chat Panel Styles */
        .chat-layout {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .chat-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .chat-header-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: #ffffff;
        }

        .chat-messages {
            flex-grow: 1;
            padding: 1.5rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        /* Custom Scrollbars */
        ::-webkit-scrollbar {
            width: 5px;
            height: 5px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.12);
        }

        .message {
            max-width: 85%;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
            animation: fadeIn 0.25s ease-out;
        }

        @keyframes fadeIn {
            from { transform: translateY(8px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .message.user {
            align-self: flex-end;
        }

        .message.agent {
            align-self: flex-start;
            width: 100%;
        }

        .bubble {
            padding: 0.85rem 1.1rem;
            border-radius: 10px;
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .message.user .bubble {
            background-color: var(--chat-bubble-user);
            color: #ffffff;
            border-bottom-right-radius: 2px;
        }

        .message.agent .bubble {
            background-color: var(--chat-bubble-agent);
            border: 1px solid var(--border-subtle);
            color: var(--text-main);
            border-bottom-left-radius: 2px;
            width: 100%;
        }

        .meta-info {
            font-size: 0.72rem;
            color: var(--text-muted);
            margin: 0 4px;
        }

        .message.user .meta-info {
            text-align: right;
        }

        /* Agent reasoning details style */
        .reasoning-box {
            margin-top: 0.65rem;
            background: rgba(0, 0, 0, 0.15);
            border-radius: 6px;
            border-left: 2px solid var(--primary);
            padding: 0.5rem 0.75rem;
            font-size: 0.8rem;
            color: #94a3b8;
        }

        .reasoning-title {
            font-weight: 600;
            color: #a5b4fc;
            margin-bottom: 0.2rem;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 0.35rem;
        }

        .confidence-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.72rem;
            margin-top: 0.5rem;
            color: var(--text-muted);
        }

        .confidence-bar-outer {
            width: 60px;
            height: 4px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 2px;
            overflow: hidden;
        }

        .confidence-bar-inner {
            height: 100%;
            background: linear-gradient(to right, var(--primary), var(--accent-cyan));
            border-radius: 2px;
        }

        /* Formatted Tools UI */
        .tool-results-container {
            margin-top: 0.65rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .tool-result-item {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 0.6rem 0.8rem;
            font-size: 0.85rem;
            color: #cbd5e1;
        }

        .tool-icon {
            margin-right: 0.4rem;
        }

        .tool-result-item ul {
            margin-left: 1.25rem;
            margin-top: 0.35rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .tool-result-item li {
            font-size: 0.8rem;
            color: #94a3b8;
        }

        /* Accordion for Raw JSON output */
        details.raw-json-details {
            margin-top: 0.5rem;
            border-top: 1px dashed rgba(255, 255, 255, 0.05);
            padding-top: 0.4rem;
        }

        details.raw-json-details summary {
            font-size: 0.72rem;
            color: var(--text-muted);
            cursor: pointer;
            outline: none;
            user-select: none;
            display: inline-block;
        }

        details.raw-json-details summary:hover {
            color: var(--text-main);
        }

        details.raw-json-details pre {
            margin-top: 0.4rem;
            background: rgba(0, 0, 0, 0.25);
            border-radius: 4px;
            padding: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            color: #38bdf8;
            overflow-x: auto;
            max-height: 150px;
        }

        .chat-input-area {
            padding: 1.25rem 1.5rem;
            border-top: 1px solid var(--border-subtle);
            display: flex;
            gap: 0.75rem;
            background: rgba(14, 16, 27, 0.4);
        }

        .chat-input {
            flex-grow: 1;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            transition: all 0.15s;
        }

        .chat-input:focus {
            border-color: var(--primary-light);
            background: rgba(255, 255, 255, 0.05);
        }

        .send-btn {
            background: var(--primary);
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 0 1.25rem;
            font-weight: 500;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.4rem;
        }

        .send-btn:hover {
            background: var(--primary-light);
        }

        /* Right Panel: Tools and Logs */
        .dashboard-panel {
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            overflow-y: auto;
            height: 100%;
        }

        .panel-section-title {
            font-size: 0.82rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.75px;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .panel-section-title svg {
            width: 1rem;
            height: 1rem;
            color: var(--primary-light);
        }

        .triggers-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.6rem;
        }

        .trigger-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 0.75rem;
            font-family: inherit;
            color: var(--text-main);
            font-size: 0.8rem;
            font-weight: 500;
            text-align: left;
            cursor: pointer;
            transition: all 0.15s;
            display: flex;
            flex-direction: column;
            gap: 0.15rem;
        }

        .trigger-card:hover {
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--primary-light);
        }

        .trigger-card span.tag-label {
            font-size: 0.65rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .terminal-container {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 0.85rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            line-height: 1.5;
            color: #10b981;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 350px;
            min-height: 200px;
        }

        .log-row {
            margin-bottom: 0.35rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.01);
            padding-bottom: 0.2rem;
            word-break: break-all;
        }

        .log-time-prefix {
            color: var(--text-muted);
            margin-right: 0.4rem;
        }

        .loading-animation {
            display: inline-flex;
            gap: 2px;
            align-items: center;
        }

        .loading-animation div {
            width: 4px;
            height: 4px;
            background-color: var(--text-muted);
            border-radius: 50%;
            animation: wave 1.2s infinite ease-in-out both;
        }

        .loading-animation div:nth-child(1) { animation-delay: -0.3s; }
        .loading-animation div:nth-child(2) { animation-delay: -0.15s; }

        @keyframes wave {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
            40% { transform: scale(1.2); opacity: 1; }
        }
    </style>
</head>
<body>
    <header>
        <div class="header-left">
            <div class="logo-mark">▲</div>
            <div class="logo-text">
                <h1>Termux Agent Hub</h1>
                <span id="modelBadge">Needle Core v{{ active_model }}.0</span>
            </div>
        </div>
        <div class="header-right">
            <div class="model-selector-group">
                <span class="model-label">Model:</span>
                <button class="model-btn {% if active_model == 3 %}active{% endif %}" id="btnModel3" onclick="selectModel(3)">Needle 3</button>
                <button class="model-btn {% if active_model == 2 %}active{% endif %}" id="btnModel2" onclick="selectModel(2)">Needle 2</button>
            </div>
            <div class="status-container">
                <div class="status-dot"></div>
                <span>Online</span>
            </div>
        </div>
    </header>

    <main>
        <!-- Left Panel: Chat Interface -->
        <div class="card">
            <div class="chat-layout">
                <div class="chat-header">
                    <div class="chat-header-title">Agent Console</div>
                    <div class="meta-info" style="font-size:0.75rem;">Local Session</div>
                </div>
                
                <div class="chat-messages" id="chatMessages">
                    <div class="message agent">
                        <div class="bubble">
                            Welcome. I am the local agentic runtime powered by Needle. You can seamlessly switch between Needle 3 (new) and Needle 2 (legacy) anytime. Provide any system instructions, device actions, or query commands in natural language.
                        </div>
                        <div class="meta-info" id="chatHeaderMeta">Agent Core • Needle v{{ active_model }}.0</div>
                    </div>
                </div>
                
                <div class="chat-input-area">
                    <input type="text" class="chat-input" id="chatInput" placeholder="Enter command or action..." autocomplete="off">
                    <button class="send-btn" id="sendBtn">
                        <span>Execute</span>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
            </div>
        </div>

        <!-- Right Panel: Diagnostics & Actions -->
        <div class="card" style="height: auto;">
            <div class="dashboard-panel">
                <div>
                    <h2 class="panel-section-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                        Device Control Triggers
                    </h2>
                    <div class="triggers-grid">
                        <button class="trigger-card" onclick="submitCommand('Check phone battery status')">
                            <span class="tag-label">System</span>
                            <strong>Battery Status</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Vibrate the phone for 500ms')">
                            <span class="tag-label">Hardware</span>
                            <strong>Haptic Vibrate</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Turn on the camera flashlight')">
                            <span class="tag-label">Hardware</span>
                            <strong>Torch ON</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Turn off the camera flashlight')">
                            <span class="tag-label">Hardware</span>
                            <strong>Torch OFF</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('What Wi-Fi network are you connected to?')">
                            <span class="tag-label">Network</span>
                            <strong>Wi-Fi Details</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Get phone GPS location coordinates')">
                            <span class="tag-label">Location</span>
                            <strong>GPS Coordinates</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('List phone contacts')">
                            <span class="tag-label">Data</span>
                            <strong>Contacts List</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Retrieve last 5 text messages')">
                            <span class="tag-label">Messages</span>
                            <strong>Inbox SMS</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Take a camera photo')">
                            <span class="tag-label">Camera</span>
                            <strong>Capture Photo</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Show a toast saying Agent Runtime Online!')">
                            <span class="tag-label">Alert</span>
                            <strong>Trigger Toast</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Set screen brightness to 150')">
                            <span class="tag-label">Display</span>
                            <strong>Brightness (Mid)</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Get volume levels info')">
                            <span class="tag-label">Audio</span>
                            <strong>Volume Info</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Set music stream volume to 10')">
                            <span class="tag-label">Audio</span>
                            <strong>Set Volume (10)</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Share text Hello from Termux Agent!')">
                            <span class="tag-label">System</span>
                            <strong>Share Text</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Show recent call logs')">
                            <span class="tag-label">Telephony</span>
                            <strong>Call Logs</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Authenticate fingerprint')">
                            <span class="tag-label">Security</span>
                            <strong>Fingerprint Auth</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Start audio recording to recording.3gp')">
                            <span class="tag-label">Audio</span>
                            <strong>Record Start</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Stop audio recording')">
                            <span class="tag-label">Audio</span>
                            <strong>Record Stop</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Get telephony device info')">
                            <span class="tag-label">Telephony</span>
                            <strong>Device Info</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Scan for nearby wifi networks')">
                            <span class="tag-label">Network</span>
                            <strong>Wi-Fi Scan</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Open whatsapp app')">
                            <span class="tag-label">Apps</span>
                            <strong>Open WhatsApp</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Open youtube app')">
                            <span class="tag-label">Apps</span>
                            <strong>Open YouTube</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Open chrome app')">
                            <span class="tag-label">Apps</span>
                            <strong>Open Chrome</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Take a screenshot of the phone screen')">
                            <span class="tag-label">Display</span>
                            <strong>Take Screenshot</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Read live phone hardware sensors data')">
                            <span class="tag-label">Sensors</span>
                            <strong>Hardware Sensors</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Turn on device Wi-Fi')">
                            <span class="tag-label">Network</span>
                            <strong>Wi-Fi ON</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Turn off device Wi-Fi')">
                            <span class="tag-label">Network</span>
                            <strong>Wi-Fi OFF</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Get audio hardware routing info')">
                            <span class="tag-label">Audio</span>
                            <strong>Headset / Audio</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Check cellular tower cellinfo')">
                            <span class="tag-label">Telephony</span>
                            <strong>Cell Tower Info</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Acquire CPU wake lock')">
                            <span class="tag-label">Power</span>
                            <strong>Wake Lock</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Scan for nearby NFC tags')">
                            <span class="tag-label">NFC</span>
                            <strong>Scan NFC</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Semantically search contacts for doctor or emergency')">
                            <span class="tag-label">Needle 3</span>
                            <strong>Semantic Search</strong>
                        </button>
                        <button class="trigger-card" onclick="submitCommand('Extract contact info from: Call Alex Vance at +15550199 alex@city17.org')">
                            <span class="tag-label">Needle 3</span>
                            <strong>Extract Info</strong>
                        </button>
                    </div>
                </div>

                <div style="flex-grow: 1; display: flex; flex-direction: column;">
                    <h2 class="panel-section-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        Terminal Output Monitor
                    </h2>
                    <div class="terminal-container" id="terminalLogs">
                        <div class="log-row"><span class="log-time-prefix">[System]</span> Production WSGI server active.</div>
                        <div class="log-row" id="initialModelLog"><span class="log-time-prefix">[System]</span> Active model: Needle v{{ active_model }}.0 Core.</div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <script>
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        const terminalLogs = document.getElementById('terminalLogs');

        function appendLog(tag, message) {
            const row = document.createElement('div');
            row.className = 'log-row';
            const time = new Date().toLocaleTimeString();
            row.innerHTML = `<span class="log-time-prefix">[${time}][${tag}]</span> ${message}`;
            terminalLogs.appendChild(row);
            terminalLogs.scrollTop = terminalLogs.scrollHeight;
        }

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
                    if (chatMeta) chatMeta.innerText = `Agent Core • Needle v${data.active_generation}.0`;
                    appendLog('System', `Model switched to Needle ${data.active_generation} (${data.description})`);
                } else {
                    appendLog('Error', `Failed to switch model: ${data.error || 'Unknown error'}`);
                }
            } catch (err) {
                appendLog('Error', `Network error switching model: ${err.message}`);
            }
        }

        // Custom parser for rendering pretty tool outputs in chat bubbles
        function formatToolResult(res) {
            if (!res) return '';
            if (typeof res === 'string') {
                if (res.toLowerCase().includes('screenshot')) {
                    return `
                        <div class="tool-result-item">
                            <span class="tool-icon">📸</span> <strong>Screenshot Captured:</strong>
                            <div style="margin-top: 0.5rem;"><img src="/screenshot.png?t=${Date.now()}" style="max-width: 100%; max-height: 250px; border-radius: 6px; border: 1px solid var(--border-subtle);" alt="Screenshot"></div>
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem;">${res}</div>
                        </div>
                    `;
                }
                return `<div class="tool-result-item"><span class="tool-icon">⚡</span> ${res}</div>`;
            }
            if (res.percentage !== undefined) {
                return `
                    <div class="tool-result-item">
                        <span class="tool-icon">🔋</span> 
                        <strong>Battery Status:</strong> ${res.percentage}% (${res.status}, Temp: ${res.temperature}°C, Health: ${res.health})
                    </div>
                `;
            }
            if (res.ssid !== undefined) {
                return `
                    <div class="tool-result-item">
                        <span class="tool-icon">📶</span> 
                        <strong>Wi-Fi Details:</strong> Connected to "${res.ssid}" (IP: ${res.ip}, RSSI: ${res.rssi}dBm)
                    </div>
                `;
            }
            if (res.latitude !== undefined) {
                return `
                    <div class="tool-result-item">
                        <span class="tool-icon">📍</span> 
                        <strong>GPS Location:</strong> Latitude: ${res.latitude.toFixed(5)}, Longitude: ${res.longitude.toFixed(5)} (Altitude: ${res.altitude}m)
                    </div>
                `;
            }
            if (Array.isArray(res)) {
                if (res.length === 0) {
                    return `<div class="tool-result-item"><span class="tool-icon">📁</span> <strong>List Output:</strong> Empty list returned.</div>`;
                }
                if (res[0].address !== undefined) {
                    // SMS list
                    let html = `<div class="tool-result-item"><span class="tool-icon">✉️</span> <strong>Recent SMS Inbox:</strong><ul>`;
                    res.forEach(sms => {
                        html += `<li><strong>${sms.address}</strong>: "${sms.body}" <span class="meta-info">(${sms.date})</span></li>`;
                    });
                    html += `</ul></div>`;
                    return html;
                }
                if (res[0].name !== undefined) {
                    // Contacts list
                    let html = `<div class="tool-result-item"><span class="tool-icon">👤</span> <strong>Contacts Found:</strong><ul>`;
                    res.forEach(c => {
                        html += `<li><strong>${c.name}</strong>: ${c.number}</li>`;
                    });
                    html += `</ul></div>`;
                    return html;
                }
            }
            // Standard JSON fallback
            return `
                <div class="tool-result-item">
                    <span class="tool-icon">⚙️</span> <strong>System Output:</strong>
                    <pre style="font-family: inherit; font-size: 0.75rem; margin-top: 0.25rem;">${JSON.stringify(res, null, 2)}</pre>
                </div>
            `;
        }

        async function submitCommand(text) {
            text = text.trim();
            if (!text) return;

            // User message bubble
            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            userDiv.innerHTML = `
                <div class="bubble">${text}</div>
                <div class="meta-info">You</div>
            `;
            chatMessages.appendChild(userDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // Loading state bubble
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message agent';
            loadingDiv.innerHTML = `
                <div class="bubble">
                    Executing <div class="loading-animation"><div></div><div></div><div></div></div>
                </div>
            `;
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            appendLog('User', `Executing: "${text}"`);

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();
                loadingDiv.remove();

                const agentDiv = document.createElement('div');
                agentDiv.className = 'message agent';

                let bubbleContent = '';
                if (data.type === 'respond' || data.type === 'call') {
                    if (data.results && data.results.length > 0) {
                        bubbleContent += `<div class="tool-results-container">`;
                        data.results.forEach((res, i) => {
                            bubbleContent += formatToolResult(res);
                            
                            // Collapsible details for raw JSON
                            if (typeof res === 'object') {
                                bubbleContent += `
                                    <details class="raw-json-details">
                                        <summary>View raw JSON</summary>
                                        <pre>${JSON.stringify(res, null, 2)}</pre>
                                    </details>
                                `;
                            }
                        });
                        bubbleContent += `</div>`;
                    } else {
                        bubbleContent += `<p style="color: var(--text-muted);">No matching tools were executed. Please rephrase the command.</p>`;
                    }
                } else {
                    bubbleContent += `<p style="color: #ef4444;">Runtime execution failure: ${data.error || 'Unknown error'}</p>`;
                }

                // Add reasoning
                let reasoningHtml = '';
                if (data.reasoning) {
                    reasoningHtml = `
                        <div class="reasoning-box">
                            <div class="reasoning-title">
                                <svg width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                                reasoning
                            </div>
                            <p>${data.reasoning}</p>
                        </div>
                    `;
                }

                // Add confidence bar
                let confidenceHtml = '';
                if (data.confidence !== null && data.confidence !== undefined) {
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
                    <div class="meta-info">${data.model || 'Agent Core'}</div>
                `;

                chatMessages.appendChild(agentDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                if (data.results && data.results.length > 0) {
                    appendLog('Agent', `Executed ${data.results.length} action(s).`);
                } else {
                    appendLog('Agent', `No actions run (Reasoning: "${data.reasoning || 'Low confidence'}").`);
                }

            } catch (err) {
                loadingDiv.remove();
                const errDiv = document.createElement('div');
                errDiv.className = 'message agent';
                errDiv.innerHTML = `
                    <div class="bubble" style="color: #ef4444;">
                        Failed to connect to agent server. Check connection.
                    </div>
                    <div class="meta-info">Runtime Error</div>
                `;
                chatMessages.appendChild(errDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                appendLog('Error', `Network fail: ${err.message}`);
            }
        }

        sendBtn.addEventListener('click', () => {
            const val = chatInput.value;
            chatInput.value = '';
            submitCommand(val);
        });

        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const val = chatInput.value;
                chatInput.value = '';
                submitCommand(val);
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

@app.route("/api/embed", methods=["POST"])
def embed_api():
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()
        if not text:
            return jsonify({"status": "error", "error": "Empty text parameter"}), 400
        current_agent = get_agent()
        if hasattr(current_agent, "embed") and getattr(current_agent, "_generation", 3) >= 3:
            vec = current_agent.embed(text)
            return jsonify({"status": "ok", "dimensions": len(vec), "vector_preview": vec[:8]})
        return jsonify({"status": "error", "error": "Active model does not support embeddings (Needle 3 required)"}), 400
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

@app.route("/api/chat", methods=["POST"])
def chat_api():
    try:
        data = request.get_json() or {}
        user_message = data.get("message", "").strip()
        if not user_message:
            return jsonify({"type": "error", "error": "Empty message parameter"}), 400
        
        # Preprocess query to wrap speech commands in quotes for correct parsing by Needle LLM
        processed_message = preprocess_query(user_message)
        # Invoke Needle model agent loop
        current_agent = get_agent()
        res = current_agent.run(processed_message)
        
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
