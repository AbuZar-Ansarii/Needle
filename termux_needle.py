import os
import sys

# Automatically prepend Termux binaries path to system environment PATH
TERMUX_BIN_PATH = "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

import subprocess
import json
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
    return run_cmd(["termux-tts-speak", text])

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
    res = run_cmd(["termux-location"])
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
            send_sms, make_phone_call, get_wifi_info
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
            # Run the agentic loop
            res = agent.run(query)
            
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
