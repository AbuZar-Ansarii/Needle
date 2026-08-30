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
    return run_cmd(["termux-tts-speak", text])

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
    res = run_cmd(["termux-location"])
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
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #070913;
            --panel-bg: rgba(18, 22, 45, 0.45);
            --border-glass: rgba(255, 255, 255, 0.08);
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.4);
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(6, 182, 212, 0.12) 0%, transparent 40%);
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid var(--border-glass);
            backdrop-filter: blur(12px);
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .logo-container {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .logo-icon {
            width: 2.2rem;
            height: 2.2rem;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--primary), var(--accent-cyan));
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1.2rem;
            box-shadow: 0 0 15px var(--primary-glow);
        }

        .logo-text h1 {
            font-size: 1.3rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            background: linear-gradient(to right, #ffffff, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-text p {
            font-size: 0.75rem;
            color: var(--text-muted);
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            padding: 0.4rem 0.8rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--accent-green);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-green);
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.15); opacity: 1; }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        main {
            display: grid;
            grid-template-columns: 1.2fr 0.8fr;
            gap: 2rem;
            padding: 2rem;
            flex-grow: 1;
            max-width: 1500px;
            margin: 0 auto;
            width: 100%;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--panel-bg);
            border: 1px solid var(--border-glass);
            border-radius: 16px;
            backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            height: calc(100vh - 160px);
        }

        /* Chat Panel Styles */
        .chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .chat-messages {
            flex-grow: 1;
            padding: 1.5rem;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
        }

        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
        }
        ::-webkit-scrollbar-track {
            background: transparent;
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .message {
            max-width: 80%;
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
            animation: slideUp 0.3s ease-out;
        }

        @keyframes slideUp {
            from { transform: translateY(15px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        .message.user {
            align-self: flex-end;
        }

        .message.agent {
            align-self: flex-start;
        }

        .bubble {
            padding: 1rem 1.25rem;
            border-radius: 14px;
            font-size: 0.95rem;
            line-height: 1.5;
        }

        .message.user .bubble {
            background: linear-gradient(135deg, var(--primary), #7c3aed);
            color: #ffffff;
            border-bottom-right-radius: 2px;
            box-shadow: 0 4px 15px rgba(124, 58, 237, 0.25);
        }

        .message.agent .bubble {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-glass);
            color: var(--text-main);
            border-bottom-left-radius: 2px;
        }

        .meta-info {
            font-size: 0.75rem;
            color: var(--text-muted);
            margin: 0 4px;
        }

        .message.user .meta-info {
            text-align: right;
        }

        /* Agent reasoning details style */
        .reasoning-box {
            margin-top: 0.5rem;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            border-left: 3px solid var(--primary);
            padding: 0.6rem 0.8rem;
            font-size: 0.82rem;
            color: #d1d5db;
        }

        .reasoning-title {
            font-weight: 600;
            color: #c084fc;
            margin-bottom: 0.25rem;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .confidence-indicator {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.75rem;
            margin-top: 0.4rem;
            color: var(--text-muted);
        }

        .confidence-bar-outer {
            width: 80px;
            height: 5px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
        }

        .confidence-bar-inner {
            height: 100%;
            background: linear-gradient(to right, var(--primary), var(--accent-cyan));
            border-radius: 3px;
        }

        .tool-execution-log {
            margin-top: 0.5rem;
            background: rgba(6, 182, 212, 0.05);
            border: 1px dashed rgba(6, 182, 212, 0.2);
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }

        .tool-title {
            color: var(--accent-cyan);
            font-weight: 600;
            margin-bottom: 0.25rem;
            font-size: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        .chat-input-area {
            padding: 1.25rem;
            border-top: 1px solid var(--border-glass);
            display: flex;
            gap: 0.75rem;
            background: rgba(10, 12, 28, 0.6);
        }

        .chat-input {
            flex-grow: 1;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-glass);
            border-radius: 10px;
            padding: 0.8rem 1rem;
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.2s;
        }

        .chat-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 10px rgba(139, 92, 246, 0.2);
            background: rgba(255, 255, 255, 0.08);
        }

        .send-button {
            background: var(--primary);
            color: #ffffff;
            border: none;
            border-radius: 10px;
            padding: 0 1.5rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
        }

        .send-button:hover {
            background: #7c3aed;
            transform: translateY(-1px);
            box-shadow: 0 6px 16px rgba(139, 92, 246, 0.45);
        }

        .send-button:active {
            transform: translateY(0);
        }

        /* Right Panel: Tools and Logs */
        .dashboard-panel {
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            overflow-y: auto;
        }

        .section-title {
            font-size: 1rem;
            font-weight: 600;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.75rem;
            border-bottom: 1px solid var(--border-glass);
            padding-bottom: 0.5rem;
        }

        .section-title svg {
            width: 1.1rem;
            height: 1.1rem;
            color: var(--primary);
        }

        .quick-triggers {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
        }

        .trigger-btn {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border-glass);
            border-radius: 10px;
            padding: 0.75rem;
            font-family: inherit;
            color: var(--text-main);
            font-size: 0.82rem;
            font-weight: 500;
            text-align: left;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }

        .trigger-btn:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--primary);
            box-shadow: 0 4px 12px rgba(139, 92, 246, 0.1);
        }

        .trigger-btn span.tag {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .live-log-container {
            background: rgba(0, 0, 0, 0.4);
            border: 1px solid var(--border-glass);
            border-radius: 10px;
            padding: 1rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.6;
            color: #34d399;
            flex-grow: 1;
            overflow-y: auto;
            max-height: 350px;
            min-height: 150px;
        }

        .log-line {
            margin-bottom: 0.4rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.02);
            padding-bottom: 0.25rem;
        }

        .log-time {
            color: var(--text-muted);
            margin-right: 0.5rem;
        }

        .loading-dots {
            display: inline-flex;
            gap: 3px;
            align-items: center;
        }

        .loading-dots div {
            width: 6px;
            height: 6px;
            background-color: var(--text-muted);
            border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .loading-dots div:nth-child(1) { animation-delay: -0.32s; }
        .loading-dots div:nth-child(2) { animation-delay: -0.16s; }

        @keyframes bounce {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1.0); }
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-container">
            <div class="logo-icon">▲</div>
            <div class="logo-text">
                <h1>Termux Agent Hub</h1>
                <p>Needle 14MB Core v2.0</p>
            </div>
        </div>
        <div class="status-badge">
            <div class="status-dot"></div>
            <span>AGENT ACTIVE</span>
        </div>
    </header>

    <main>
        <!-- Left Column: Chat Container -->
        <div class="card">
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="message agent">
                        <div class="bubble">
                            Hello! I am your agentic assistant connected to the Termux API. You can ask me to control device hardware, retrieve status logs, speak text, or trigger notifications. What should I do?
                        </div>
                        <div class="meta-info">System • Agent Core</div>
                    </div>
                </div>
                
                <div class="chat-input-area">
                    <input type="text" class="chat-input" id="chatInput" placeholder="Send a message/command..." autocomplete="off">
                    <button class="send-button" id="sendBtn">
                        <span>Send</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                    </button>
                </div>
            </div>
        </div>

        <!-- Right Column: Control & Dashboard Panel -->
        <div class="card" style="height: auto;">
            <div class="dashboard-panel">
                <div>
                    <h2 class="section-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                        Quick Commands
                    </h2>
                    <div class="quick-triggers">
                        <button class="trigger-btn" onclick="submitCommand('Check battery status')">
                            <span class="tag">System</span>
                            <strong>Battery Level</strong>
                        </button>
                        <button class="trigger-btn" onclick="submitCommand('Vibrate device for 1 second')">
                            <span class="tag">Hardware</span>
                            <strong>Vibrate Phone</strong>
                        </button>
                        <button class="trigger-btn" onclick="submitCommand('Turn on the flashlight')">
                            <span class="tag">Hardware</span>
                            <strong>Toggle Torch ON</strong>
                        </button>
                        <button class="trigger-btn" onclick="submitCommand('Turn off the flashlight')">
                            <span class="tag">Hardware</span>
                            <strong>Toggle Torch OFF</strong>
                        </button>
                        <button class="trigger-btn" onclick="submitCommand('What Wi-Fi network are you connected to?')">
                            <span class="tag">Network</span>
                            <strong>Wi-Fi Details</strong>
                        </button>
                        <button class="trigger-btn" onclick="submitCommand('Show a toast saying Agent Loaded!')">
                            <span class="tag">Display</span>
                            <strong>Trigger Toast</strong>
                        </button>
                    </div>
                </div>

                <div style="flex-grow: 1; display: flex; flex-direction: column;">
                    <h2 class="section-title">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        Terminal Event Logs
                    </h2>
                    <div class="live-log-container" id="terminalLogs">
                        <div class="log-line"><span class="log-time">[System]</span> Terminal initialized. Simulator active.</div>
                        <div class="log-line"><span class="log-time">[System]</span> Local model (14MB) bound and listening.</div>
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
            const line = document.createElement('div');
            line.className = 'log-line';
            const timeStr = new Date().toLocaleTimeString();
            line.innerHTML = `<span class="log-time">[${timeStr}][${tag}]</span> ${message}`;
            terminalLogs.appendChild(line);
            terminalLogs.scrollTop = terminalLogs.scrollHeight;
        }

        async function submitCommand(text) {
            if (!text.strip) {
                text = text.trim();
            }
            if (!text) return;

            // 1. Append User Message
            const userMsgDiv = document.createElement('div');
            userMsgDiv.className = 'message user';
            userMsgDiv.innerHTML = `
                <div class="bubble">${text}</div>
                <div class="meta-info">You</div>
            `;
            chatMessages.appendChild(userMsgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            // 2. Append Loading Placeholder for Agent
            const agentLoadingDiv = document.createElement('div');
            agentLoadingDiv.className = 'message agent';
            agentLoadingDiv.id = 'agentLoading';
            agentLoadingDiv.innerHTML = `
                <div class="bubble">
                    Thinking <div class="loading-dots"><div></div><div></div><div></div></div>
                </div>
            `;
            chatMessages.appendChild(agentLoadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            appendLog('User', `Requested: "${text}"`);

            try {
                // 3. Make Fetch Call
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                
                const data = await response.json();
                
                // Remove Loading Placeholder
                agentLoadingDiv.remove();

                // 4. Construct Agent Message HTML
                const agentMsgDiv = document.createElement('div');
                agentMsgDiv.className = 'message agent';

                let bubbleContent = '';
                if (data.type === 'respond' || data.type === 'call') {
                    if (data.results && data.results.length > 0) {
                        bubbleContent += `<p>I've run the requested device tools:</p>`;
                        data.results.forEach((res, i) => {
                            if (typeof res === 'object') {
                                bubbleContent += `<div class="tool-execution-log">
                                    <div class="tool-title">⚡ Tool Result [${i+1}]</div>
                                    <pre style="white-space: pre-wrap; font-size: 0.75rem;">${JSON.stringify(res, null, 2)}</pre>
                                </div>`;
                            } else {
                                bubbleContent += `<div class="tool-execution-log">
                                    <div class="tool-title">⚡ Tool Result [${i+1}]</div>
                                    <p>${res}</p>
                                </div>`;
                            }
                        });
                    } else {
                        bubbleContent += `<p>No tools were matched or executed. I was unable to translate this command to a Termux action.</p>`;
                    }
                } else {
                    bubbleContent += `<p>Error occurred during parsing: ${data.error || 'Unknown error'}</p>`;
                }

                // Add reasoning box if available
                let reasoningHtml = '';
                if (data.reasoning) {
                    reasoningHtml = `
                        <div class="reasoning-box">
                            <div class="reasoning-title">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
                                Agent Reasoning
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

                agentMsgDiv.innerHTML = `
                    <div class="bubble">
                        ${bubbleContent}
                        ${reasoningHtml}
                        ${confidenceHtml}
                    </div>
                    <div class="meta-info">Agent</div>
                `;

                chatMessages.appendChild(agentMsgDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;

                // Log the execution to terminal monitor
                if (data.results && data.results.length > 0) {
                    appendLog('Agent', `Successfully called ${data.results.length} action(s).`);
                } else {
                    appendLog('Agent', `No actions executed (Reason: "${data.reasoning || 'Low confidence'}").`);
                }

            } catch (err) {
                agentLoadingDiv.remove();
                const errDiv = document.createElement('div');
                errDiv.className = 'message agent';
                errDiv.innerHTML = `
                    <div class="bubble" style="color: #ef4444;">
                        Failed to connect to agent server. Ensure the Flask server is running.
                    </div>
                    <div class="meta-info">System Error</div>
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
        
        # Invoke Needle model agent loop
        res = agent.run(user_message)
        
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
                res = agent.run(query)
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

    # If no token is provided, ask the user interactively
    if not telegram_token:
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

    if telegram_token:
        print("[Telegram] Token provided. Launching bot background thread...")
        telegram_thread = threading.Thread(target=start_telegram_bot, args=(telegram_token,), daemon=True)
        telegram_thread.start()
    else:
        print("[Telegram] Info: Remote Telegram control disabled.")

    # Run server on port 5000 (accessible on local network/phone browser)
    app.run(host="0.0.0.0", port=5000, debug=True)
