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

# Helper function to run Termux CLI commands
def run_cmd(args):
    try:
        # Run command with timeout of 15s to allow hardware sensor warm up
        res = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
            return f"Error ({args[0]}): {err_msg}"
        return res.stdout.strip() if res.stdout.strip() else "Success"
    except subprocess.TimeoutExpired:
        return f"Error ({args[0]}): Command timed out after 15 seconds. Termux API might be hanging or lack permissions."
    except FileNotFoundError:
        return f"Error ({args[0]}): Command '{args[0]}' not found. Make sure termux-api package is installed."
    except Exception as e:
        return f"Error ({args[0]}): {str(e)}"

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
    """Open an application on the phone (e.g. 'whatsapp', 'youtube', 'chrome', 'instagram', 'spotify', 'telegram', 'facebook', 'twitter', 'gmail', 'maps', 'calculator', 'settings')."""
    print(f"-> Calling Tool: open_app(app_name='{app_name}')")
    
    app_key = app_name.strip().lower()
    
    app_urls = {
        "whatsapp": "whatsapp://",
        "youtube": "https://www.youtube.com",
        "chrome": "https://www.google.com",
        "browser": "https://www.google.com",
        "instagram": "https://instagram.com",
        "spotify": "https://open.spotify.com",
        "telegram": "https://t.me",
        "facebook": "https://facebook.com",
        "twitter": "https://twitter.com",
        "x": "https://x.com",
        "gmail": "mailto:",
        "maps": "https://maps.google.com",
        "google maps": "https://maps.google.com"
    }

    app_packages = {
        "whatsapp": "com.whatsapp/.HomeActivity",
        "youtube": "com.google.android.youtube/com.google.android.youtube.PlayerActivity",
        "chrome": "com.android.chrome/com.google.android.apps.chrome.Main",
        "instagram": "com.instagram.android/com.instagram.mainactivity.LauncherActivity",
        "spotify": "com.spotify.music/com.spotify.music.MainActivity",
        "telegram": "org.telegram.messenger/org.telegram.ui.LaunchActivity",
        "facebook": "com.facebook.katana/com.facebook.katana.LoginActivity",
        "gmail": "com.google.android.gm/com.google.android.gm.ConversationListActivityGmail",
        "settings": "com.android.settings/.Settings",
        "calculator": "com.google.android.calculator/com.android.calculator2.Calculator",
        "camera": "com.android.camera/com.android.camera.Camera"
    }

    # Attempt 1: am start --user 0 -n <package/activity>
    if app_key in app_packages:
        res1 = run_cmd(["am", "start", "--user", "0", "-n", app_packages[app_key]])
        if "Error" not in res1 and ("Starting: Intent" in res1 or "Status: ok" in res1 or res1 == "Success"):
            return f"Successfully opened {app_name} on device screen."

    # Attempt 2: am start --user 0 -a android.intent.action.VIEW -d <url>
    if app_key in app_urls:
        res2 = run_cmd(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", app_urls[app_key]])
        if "Error" not in res2 and ("Starting: Intent" in res2 or res2 == "Success"):
            return f"Successfully opened {app_name} on device screen."

    # Attempt 3: termux-open-url
    if app_key in app_urls:
        res3 = run_cmd(["termux-open-url", app_urls[app_key]])
        if "Error" not in res3:
            return f"Successfully opened {app_name} on device screen."

    # Attempt 4: monkey --user 0
    pkg = app_packages[app_key].split("/")[0] if app_key in app_packages else (app_key if "." in app_key else f"com.{app_key}")
    res4 = run_cmd(["monkey", "-p", pkg, "--user", "0", "-c", "android.intent.category.LAUNCHER", "1"])
    return f"Triggered app launch for {app_name}."

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

def main():
    print("=" * 60)
    print("Termux Agentic Tool Calling Hub (Needle 14MB LLM)")
    print("=" * 60)
    
    # Initialize the Needle Agent with all tools
    # If run for the first time, it downloads the model from Hugging Face automatically.
    print("Loading Needle model...")
    try:
        tools = [
            show_toast, show_notification, get_battery_status, 
            text_to_speech, set_clipboard, get_clipboard, 
            vibrate_device, set_torch, get_location, 
            send_sms, make_phone_call, get_wifi_info,
            take_camera_photo, get_sms_messages, get_contacts, download_file,
            set_screen_brightness, get_volume_info, set_volume, share_content,
            get_call_log, authenticate_fingerprint, record_audio_start,
            record_audio_stop, get_telephony_info, scan_wifi_networks,
            open_app
        ]
        agent = needle.Needle(tools=tools)
        print("Needle model loaded successfully!")
    except Exception as e:
        print(f"Failed to initialize Needle: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nHow to use: Type a command for your phone, e.g.:")
    print(" - 'show a toast saying Hello from Needle'")
    print(" - 'vibrate for 1 second and turn on the torch'")
    print(" - 'check the battery level'")
    print(" - 'say out loud the current clipboard contents'")
    print("Type 'exit' or 'quit' to close the assistant.\n")
    
    while True:
        try:
            query = input("Termux Assistant > ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            
            print("Processing command...")
            # Preprocess query to wrap speech commands in quotes for correct parsing by Needle LLM
            processed_query = preprocess_query(query)
            # Run the agentic loop
            res = agent.run(processed_query)
            
            # Print execution metrics and response details
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
