import os
import sys

# Automatically prepend Termux binaries path to system environment PATH
TERMUX_BIN_PATH = "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

import json
import subprocess
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

# ----------------------------------------------------------------------
# Helper to run Termux CLI commands or simulate them on Windows/Desktop
# ----------------------------------------------------------------------
def run_cmd(args):
    # Try running the actual termux command first
    try:
        # Run with timeout to prevent hanging
        res = subprocess.run(args, capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            # If not found or fails, try to fall back to simulation
            raise FileNotFoundError()
        return res.stdout.strip()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        # Simulation layer for desktop testing (highly detailed mock outputs)
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
def take_camera_photo(camera_id: int = 0, filename: str = "photo.jpg"):
    """Capture a photo using the phone's front (1) or back (0) camera and save it."""
    print(f"[Agent Triggered Tool] take_camera_photo(camera_id={camera_id}, filename='{filename}')")
    return run_cmd(["termux-camera-photo", "-c", str(camera_id), filename])

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


# ----------------------------------------------------------------------
# Initialize the Needle Agent
# ----------------------------------------------------------------------
print("Loading local Needle model (14MB)...")
tools_list = [
    show_toast, show_notification, get_battery_status, 
    text_to_speech, set_clipboard, get_clipboard, 
    vibrate_device, set_torch, get_location, 
    send_sms, make_phone_call, get_wifi_info,
    take_camera_photo, get_sms_messages, get_contacts, download_file
]
agent = needle.Needle(tools=tools_list)
print("Needle model active and ready!")


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
                <span>Needle 14MB Core v2.0</span>
            </div>
        </div>
        <div class="status-container">
            <div class="status-dot"></div>
            <span>Online</span>
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
                            Welcome. I am the local agentic runtime powered by Needle. Provide any system instructions, device actions, or query commands in natural language.
                        </div>
                        <div class="meta-info">Agent Core • System</div>
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
                    </div>
                </div>

                <div style="flex-grow: 1; display: flex; flex-direction: column;">
                    <h2 class="panel-section-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        Terminal Output Monitor
                    </h2>
                    <div class="terminal-container" id="terminalLogs">
                        <div class="log-row"><span class="log-time-prefix">[System]</span> Production WSGI server active.</div>
                        <div class="log-row"><span class="log-time-prefix">[System]</span> Loaded Needle local model (14MB).</div>
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

        // Custom parser for rendering pretty tool outputs in chat bubbles
        function formatToolResult(res) {
            if (!res) return '';
            if (typeof res === 'string') {
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
                    <div class="meta-info">Agent</div>
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
    return render_template_string(HTML_TEMPLATE)

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
        res = agent.run(processed_message)
        
        return jsonify({
            "query": user_message,
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
        bot = telebot.TeleBot(token)
        print(f"[Telegram] Bot listener running. Connected to bot.")

        @bot.message_handler(func=lambda message: True)
        def handle_telegram_message(message):
            query = message.text.strip()
            print(f"[Telegram] Message received: '{query}'")
            if not query:
                return
            try:
                processed_query = preprocess_query(query)
                res = agent.run(processed_query)
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

                bot.reply_to(message, reply, parse_mode="Markdown")
            except Exception as err:
                bot.reply_to(message, f"❌ *Error executing command:*\n`{str(err)}`", parse_mode="Markdown")

        bot.infinity_polling()
    except Exception as exc:
        print(f"[Telegram Error] Failed to run bot listener: {exc}", file=sys.stderr)

if __name__ == "__main__":
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
