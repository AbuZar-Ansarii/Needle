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
        # Run command with timeout of 10s to prevent hanging
        res = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return f"Error: {res.stderr.strip()}"
        return res.stdout.strip()
    except subprocess.TimeoutExpired:
        return "Error: Command timed out. Termux API might be hanging or lack permissions."
    except FileNotFoundError:
        return f"Error: Command '{args[0]}' not found. Make sure termux-api is installed in Termux and PATH is configured."
    except Exception as e:
        return f"Error: {str(e)}"

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
def take_camera_photo(camera_id: int = 0, filename: str = "needle_photo.jpg"):
    """Capture a photo using the phone's front (1) or back (0) camera and save it. Prevents storage permission errors."""
    home_dir = os.path.expanduser("~")
    safe_target = os.path.join(home_dir, "needle_photo.jpg")
    
    print(f"-> Calling Tool: take_camera_photo(camera_id={camera_id}, filename='{safe_target}')")
    res = run_cmd(["termux-camera-photo", "-c", str(camera_id), safe_target])
    
    # Try copying to Downloads folder if available
    downloads_dir = os.path.join(home_dir, "storage", "downloads")
    if os.path.exists(downloads_dir):
        try:
            dest = os.path.join(downloads_dir, os.path.basename(filename) if filename else "needle_photo.jpg")
            shutil.copy2(safe_target, dest)
            return f"Photo captured successfully and saved to Download folder: '{dest}' (Home backup: '{safe_target}')"
        except Exception:
            pass
            
    return res if res else f"Photo captured successfully and saved to: '{safe_target}'"

@needle.tool
def open_app(app_name: str):
    """Open an application on the phone by its name or Android package name (e.g. 'whatsapp', 'youtube', 'chrome', 'instagram', 'spotify', 'com.whatsapp')."""
    print(f"-> Calling Tool: open_app(app_name='{app_name}')")
    
    app_map = {
        "whatsapp": "com.whatsapp",
        "youtube": "com.google.android.youtube",
        "chrome": "com.android.chrome",
        "instagram": "com.instagram.android",
        "spotify": "com.spotify.music",
        "telegram": "org.telegram.messenger",
        "facebook": "com.facebook.katana",
        "twitter": "com.twitter.android",
        "x": "com.twitter.android",
        "gmail": "com.google.android.gm",
        "maps": "com.google.android.apps.maps",
        "google maps": "com.google.android.apps.maps",
        "camera": "com.android.camera",
        "photos": "com.google.android.apps.photos",
        "gallery": "com.google.android.apps.photos",
        "settings": "com.android.settings",
        "play store": "com.android.vending",
        "playstore": "com.android.vending",
        "clock": "com.google.android.deskclock",
        "calculator": "com.google.android.calculator"
    }
    
    key = app_name.strip().lower()
    package_name = app_map.get(key, app_name.strip())
    
    res = run_cmd(["monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    if "Error" not in res and "No activities" not in res and "error" not in res.lower():
        return f"Successfully opened app: '{app_name}' ({package_name})"
    
    res_am = run_cmd(["am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-n", f"{package_name}/.MainActivity"])
    return f"Opened app: '{app_name}' ({package_name})"

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
