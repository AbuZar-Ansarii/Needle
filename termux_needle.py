import os
import sys

# Automatically prepend Termux binaries path to system environment PATH
TERMUX_BIN_PATH = "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

import subprocess
import json
import shutil
import needle

IS_TERMUX = os.path.exists("/data/data/com.termux")

# Helper function to run Termux CLI commands with desktop simulation fallback
def run_cmd(args):
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
            return "Simulated clipboard contents from desktop."
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
            return f"[Simulated Dial] Dialed voice call to: {number}"
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
                "network_operator_name": "Google Fi",
                "network_type": "LTE",
                "phone_type": "PHONE_TYPE_GSM",
                "sim_country_iso": "us",
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
# Define Termux:API Tools
# ----------------------------------------------------------------------

@needle.tool
def show_toast(message: str):
    """Display a brief toast notification popup on the phone screen."""
    print(f"-> Calling Tool: show_toast(message='{message}')")
    return run_cmd(["termux-toast", message])

@needle.tool
def show_notification(title: str, content: str):
    """Display a system notification drawer popup with a title and message content."""
    print(f"-> Calling Tool: show_notification(title='{title}', content='{content}')")
    return run_cmd(["termux-notification", "--title", title, "--content", content])

@needle.tool
def get_battery_status():
    """Retrieve details about the phone's battery (percentage, status, health, temperature)."""
    print("-> Calling Tool: get_battery_status()")
    res = run_cmd(["termux-battery-status"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def text_to_speech(text: str):
    """Speak a text string aloud using the phone's Text-to-Speech (TTS) engine."""
    print(f"-> Calling Tool: text_to_speech(text='{text}')")
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
    print(f"-> Calling Tool: set_clipboard(text='{text}')")
    return run_cmd(["termux-clipboard-set", text])

@needle.tool
def get_clipboard():
    """Retrieve the current text stored in the device's system clipboard."""
    print("-> Calling Tool: get_clipboard()")
    return run_cmd(["termux-clipboard-get"])

@needle.tool
def vibrate_device(duration_ms: int = 500):
    """Vibrate the phone device for a duration specified in milliseconds."""
    print(f"-> Calling Tool: vibrate_device(duration_ms={duration_ms})")
    return run_cmd(["termux-vibrate", "-d", str(duration_ms)])

@needle.tool
def set_torch(on: bool):
    """Turn the phone device's camera flash / torch ON (True) or OFF (False)."""
    print(f"-> Calling Tool: set_torch(on={on})")
    state = "on" if on else "off"
    return run_cmd(["termux-torch", state])

@needle.tool
def get_location():
    """Retrieve the device's current GPS location coordinates (latitude, longitude, altitude)."""
    print("-> Calling Tool: get_location()")
    res = run_cmd(["termux-location", "-p", "network", "-r", "last"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def send_sms(recipient: str, message: str):
    """Send an SMS text message to a recipient phone number."""
    print(f"-> Calling Tool: send_sms(recipient='{recipient}', message='{message}')")
    return run_cmd(["termux-sms-send", "-n", recipient, message])

@needle.tool
def make_phone_call(phone_number: str):
    """Initiate an outgoing voice call to the specified phone number."""
    print(f"-> Calling Tool: make_phone_call(phone_number='{phone_number}')")
    return run_cmd(["termux-telephony-call", phone_number])

@needle.tool
def get_wifi_info():
    """Retrieve details about the active Wi-Fi connection (SSID, IP address, speed, strength)."""
    print("-> Calling Tool: get_wifi_info()")
    res = run_cmd(["termux-wifi-connectioninfo"])
    try:
        return json.loads(res)
    except Exception:
        return res


@needle.tool
def take_camera_photo():
    """Capture a photo using the phone's back camera and save it directly to the Download folder."""
    print("-> Calling Tool: take_camera_photo()")
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
    print(f"-> Calling Tool: open_app(app_name='{app_name}')")
    
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
    print(f"-> Calling Tool: get_sms_messages(limit={limit})")
    res = run_cmd(["termux-sms-list", "-l", str(limit)])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def get_contacts():
    """Retrieve the phone's contact list (names and phone numbers)."""
    print("-> Calling Tool: get_contacts()")
    res = run_cmd(["termux-contact-list"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def download_file(url: str, title: str = "Download"):
    """Download a file from a URL using the system's download manager."""
    print(f"-> Calling Tool: download_file(url='{url}', title='{title}')")
    return run_cmd(["termux-download", "-t", title, url])

@needle.tool
def set_screen_brightness(level: str):
    """Adjust the screen brightness. Provide a value between 0 (dimmest) and 255 (brightest), or 'auto'."""
    print(f"-> Calling Tool: set_screen_brightness(level='{level}')")
    return run_cmd(["termux-brightness", str(level)])

@needle.tool
def get_volume_info():
    """Retrieve the current volume levels of all audio streams (music, ring, alarm, etc.)."""
    print("-> Calling Tool: get_volume_info()")
    res = run_cmd(["termux-volume"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def set_volume(stream: str, volume: int):
    """Set the volume level of a specific audio stream (alarm, music, notification, ring, system, call)."""
    print(f"-> Calling Tool: set_volume(stream='{stream}', volume={volume})")
    return run_cmd(["termux-volume", stream, str(volume)])

@needle.tool
def share_content(text: str = "", file_path: str = ""):
    """Share text content or a file using the Android system share sheet."""
    print(f"-> Calling Tool: share_content(text='{text}', file_path='{file_path}')")
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
    print(f"-> Calling Tool: get_call_log(limit={limit})")
    res = run_cmd(["termux-call-log", "-l", str(limit)])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def authenticate_fingerprint():
    """Prompt for fingerprint authentication on the device to verify user identity."""
    print("-> Calling Tool: authenticate_fingerprint()")
    res = run_cmd(["termux-fingerprint"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def record_audio_start(file_path: str = "recording.3gp", limit_seconds: int = 0):
    """Begin recording audio from the device microphone to a specified file. Optionally set a duration limit in seconds."""
    print(f"-> Calling Tool: record_audio_start(file_path='{file_path}', limit_seconds={limit_seconds})")
    cmd = ["termux-microphone-record", "-f", file_path]
    if limit_seconds > 0:
        cmd.extend(["-l", str(limit_seconds)])
    return run_cmd(cmd)

@needle.tool
def record_audio_stop():
    """Stop the ongoing microphone audio recording and save the file."""
    print("-> Calling Tool: record_audio_stop()")
    return run_cmd(["termux-microphone-record", "-q"])

@needle.tool
def get_telephony_info():
    """Retrieve device telephony information (network operator, SIM state, network type, IMEI/device ID)."""
    print("-> Calling Tool: get_telephony_info()")
    res = run_cmd(["termux-telephony-deviceinfo"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def scan_wifi_networks():
    """Scan and retrieve a list of nearby Wi-Fi networks and their signal strengths."""
    print("-> Calling Tool: scan_wifi_networks()")
    res = run_cmd(["termux-wifi-scaninfo"])
    try:
        return json.loads(res)
    except Exception:
        return res



current_cli_agent = None

def get_cli_agent():
    return current_cli_agent

@needle.tool
def set_wifi_state(enable: bool):
    """Turn the phone device's Wi-Fi radio ON (True) or OFF (False)."""
    print(f"-> Calling Tool: set_wifi_state(enable={enable})")
    state = "true" if enable else "false"
    return run_cmd(["termux-wifi-enable", state])

@needle.tool
def control_media(action: str, file_path: str = ""):
    """Control audio and media playback on the device. Valid actions: 'play', 'pause', 'stop', 'info'. Provide file_path when playing audio."""
    print(f"-> Calling Tool: control_media(action='{action}', file_path='{file_path}')")
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
    print(f"-> Calling Tool: get_sensors(sensor_name='{sensor_name}')")
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
    print(f"-> Calling Tool: show_dialog(title='{title}', text='{text}', dialog_type='{dialog_type}')")
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
    print(f"-> Calling Tool: set_wallpaper(file_path='{file_path}', lockscreen={lockscreen})")
    cmd = ["termux-wallpaper", "-f", file_path]
    if lockscreen:
        cmd.append("-l")
    return run_cmd(cmd)

@needle.tool
def manage_wake_lock(lock: bool = True):
    """Acquire (True) or release (False) a system wake lock to keep the phone CPU awake during long-running tasks."""
    print(f"-> Calling Tool: manage_wake_lock(lock={lock})")
    return run_cmd(["termux-wake-lock"] if lock else ["termux-wake-unlock"])

@needle.tool
def send_key_event(key: str):
    """Simulate a physical button or navigation keypress on the phone. Supported keys: 'home', 'back', 'volume_up', 'volume_down', 'power', 'play_pause', 'menu', 'enter'."""
    print(f"-> Calling Tool: send_key_event(key='{key}')")
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
    print("-> Calling Tool: take_screenshot()")
    target = "/sdcard/Download/screenshot.png"
    res = run_cmd(["screencap", "-p", target])
    if os.path.exists(target) and os.path.getsize(target) > 0:
        return f"Screenshot captured successfully and saved to: '{target}'"
    return f"Screenshot saved: {res} (Saved to {target})"

@needle.tool
def get_cell_tower_info():
    """Retrieve details on nearby cellular base station towers, signal strength (RSSI, RSRP), and cell IDs."""
    print("-> Calling Tool: get_cell_tower_info()")
    res = run_cmd(["termux-telephony-cellinfo"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def get_audio_hardware_info():
    """Check phone audio routing (whether wired headphones or Bluetooth A2DP headphones are plugged in, microphone state)."""
    print("-> Calling Tool: get_audio_hardware_info()")
    res = run_cmd(["termux-audio-info"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def read_nfc():
    """Scan for nearby NFC tags or RFID smart cards touching the back of the phone."""
    print("-> Calling Tool: read_nfc()")
    res = run_cmd(["termux-nfc", "-r"])
    try:
        return json.loads(res)
    except Exception:
        return res

@needle.tool
def extract_structured_data(text: str, extraction_type: str = "general"):
    """Extract structured data (event, contact, reminder, expense, task) from messy unstructured text using Needle 3's grammar-constrained extraction."""
    print(f"-> Calling Tool: extract_structured_data(extraction_type='{extraction_type}')")
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
        agent = get_cli_agent()
        if agent and hasattr(agent, "extract") and getattr(agent, "_generation", 3) >= 3:
            extracted = agent.extract(text, schema=schema)
            if extracted:
                return extracted
    except Exception:
        pass
    return {"extraction_type": extraction_type, "schema": schema, "source_text": text, "status": "processed"}

@needle.tool
def semantic_phone_search(query: str, target: str = "all"):
    """Perform on-device semantic search over phone data (contacts, SMS inbox, call log) using Needle 3 embeddings to find relevant records even if exact words don't match."""
    print(f"-> Calling Tool: semantic_phone_search(query='{query}', target='{target}')")
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
        agent = get_cli_agent()
        if agent and hasattr(agent, "embed") and getattr(agent, "_generation", 3) >= 3:
            import math
            def cosine_sim(v1, v2):
                dot = sum(a * b for a, b in zip(v1, v2))
                m1 = math.sqrt(sum(a * a for a in v1))
                m2 = math.sqrt(sum(b * b for b in v2))
                return dot / (m1 * m2 + 1e-9)

            query_vec = agent.embed(query)
            scored = []
            for it in items:
                it_vec = agent.embed(it)
                sim = cosine_sim(query_vec, it_vec)
                scored.append((sim, it))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [f"[{round(sim*100)}% match] {it}" for sim, it in scored[:5]]
    except Exception:
        pass

    q_words = [w.lower() for w in query.split() if len(w) > 2]
    matched = [it for it in items if any(w in it.lower() for w in q_words)]
    return matched[:5] if matched else items[:3]

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
# Main Execution Loop
# ----------------------------------------------------------------------

def get_initial_model_generation():
    # 1. CLI arguments (--model 2 / --model 3 / -m 2 / -m 3)
    for idx, arg in enumerate(sys.argv):
        if arg in ("--model", "--generation", "-m") and idx + 1 < len(sys.argv):
            try:
                val = int(sys.argv[idx + 1])
                if val in (2, 3):
                    return val
            except ValueError:
                pass
    # 2. Environment variable
    env_val = os.environ.get("NEEDLE_MODEL") or os.environ.get("NEEDLE_GENERATION")
    if env_val:
        try:
            val = int(env_val)
            if val in (2, 3):
                return val
        except ValueError:
            pass
    # 3. Interactive prompt if terminal attached
    if sys.stdin.isatty():
        try:
            print("\nSelect Needle Model Generation:")
            print("  [3] Needle 3 (Default - High Accuracy, Sliceable SAN Architecture)")
            print("  [2] Needle 2 (Legacy - 14MB Core)")
            choice = input("Enter choice [3]: ").strip()
            if choice == "2":
                return 2
            return 3
        except (KeyboardInterrupt, EOFError):
            print("\nDefaulting to Needle 3.")
            return 3
    return 3

def main():
    global current_cli_agent
    print("=" * 60)
    print("Termux Agentic Tool Calling Hub (Needle 2 & Needle 3)")
    print("=" * 60)
    
    tools = [
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

    current_generation = get_initial_model_generation()
    loaded_agents = {}

    def load_model(gen):
        global current_cli_agent
        if gen not in loaded_agents:
            desc = "Needle 3 (Laddered SAN Foundation)" if gen == 3 else "Needle 2 (Legacy 14MB Core)"
            print(f"Loading {desc}...")
            loaded_agents[gen] = needle.Needle(tools=tools, generation=gen)
            print(f"{desc} loaded successfully!")
        current_cli_agent = loaded_agents[gen]
        return loaded_agents[gen]

    try:
        agent = load_model(current_generation)
    except Exception as e:
        print(f"Failed to initialize Needle {current_generation}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nActive Model: Needle {current_generation}")
    print("How to use: Type a command for your phone, e.g.:")
    print(" - 'turn on flashlight' / 'turn off torch'")
    print(" - 'check battery level'")
    print(" - 'take a screenshot of the screen'")
    print(" - 'read live hardware sensors'")
    print(" - 'turn on wifi' / 'turn off wifi'")
    print(" - 'extract contact info from: Call Alex Vance at +15550199'")
    print(" - 'semantically search contacts for doctor or emergency'")
    print("Commands:")
    print(" - '/model 3' or '/model 2' to switch models dynamically")
    print(" - 'exit' or 'quit' to close the assistant.\n")
    
    while True:
        try:
            query = input(f"Termux Assistant (Needle {current_generation}) > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            # Handle dynamic model switching command
            q_lower = query.lower()
            if q_lower in ("/model", "model"):
                desc = "Laddered SAN / High Accuracy" if current_generation == 3 else "Legacy 14MB Core"
                print(f"Active model: Needle {current_generation} ({desc})")
                print("To switch models, type '/model 2' or '/model 3'.")
                print("-" * 60)
                continue

            if q_lower in ("/model 2", "model 2", "/model 3", "model 3"):
                target_gen = 2 if "2" in q_lower else 3
                if target_gen == current_generation:
                    print(f"Needle {target_gen} is already active.")
                else:
                    try:
                        agent = load_model(target_gen)
                        current_generation = target_gen
                        print(f"Switched active model to Needle {current_generation}!")
                    except Exception as err:
                        print(f"Failed to switch to Needle {target_gen}: {err}")
                print("-" * 60)
                continue
            
            print("Processing command...")
            # Preprocess query to wrap speech commands in quotes for correct parsing by Needle LLM
            processed_query = preprocess_query(query)
            # Run the agentic loop
            res = agent.run(processed_query)
            
            # Print execution metrics and response details
            print(f"Model: Needle {current_generation}")
            print(f"Reasoning: {res.get('reasoning')}")
            print(f"Confidence: {res.get('confidence')}")
            
            # Print results returned by any executed tools
            results = res.get("results") or []
            if results:
                print("Tool Execution Outputs:")
                for i, r in enumerate(results, 1):
                    print(f"  [{i}] {r}")
            else:
                print("No tools were called (or model confidence was too low).")
            print("-" * 60)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error executing agent query: {e}")
            print("-" * 60)

if __name__ == "__main__":
    main()
