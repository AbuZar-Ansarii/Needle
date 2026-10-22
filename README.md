# Termux Agentic Assistant (Needle 3 & Needle 2 LLM)

An ultra-lightweight, local agentic assistant for Android/Termux that controls phone hardware and parses queries in plain English. Powered by Cactus Compute's foundation models with full support for **Needle 3** (new Laddered SAN architecture) and **Needle 2** (legacy 14MB Core).

<a href="https://youtu.be/xiZ3LbOfAh8?si=FvSEW7hxTwoj3IdO">
  <img width="2880" height="1620" alt="14 mb agentic llm" src="https://github.com/user-attachments/assets/8453d53a-71f4-49bf-90b6-35c5b7524bbe" />
</a>

---

## 🌟 Features
- **Dual Model Support (Needle 3 & Needle 2):** Use the latest **Needle 3** model for superior reasoning, sliceable depth, and grammar-constrained tool calling, or choose **Needle 2** for the ultra-compact 14MB legacy core.
- **🎙️ Offline "Jarvis" Voice Loop:** Hands-free voice input via speech recognition with spoken audio responses using Android Text-to-Speech (`termux-tts-speak`).
- **🧠 Offline Personal Knowledge Base (Local RAG):** Store personal notes, credentials, and memories in a local SQLite database with on-device 3,072-dimensional Needle 3 embeddings and semantic search.
- **📸 Smart Camera Document Extractor:** Photograph receipts, invoices, business cards, and badges, and extract structured JSON schemas completely offline.
- **🛡️ Smart SMS & Notification Triage:** Intelligently categorizes SMS into OTP, Bank Transactions, Spam, and Personal chats, and automatically extracts verification codes straight to your Android clipboard.
- **Dynamic On-The-Fly Model Switching:** Switch between Needle 3 and Needle 2 anytime via the Web UI header toggle, CLI commands, or Telegram bot messages without restarting the server.
- **Interactive Chat Web UI:** Sleek light/dark dashboard with tool execution cancellation, live logs, and sidebar studios.
- **Remote Telegram Bot Control:** Start a background Telegram listener that lets you text your phone commands remotely and receive results instantly, with support for `/model` commands.
- **Natural Language Translation:** Translates commands like *"turn on flashlight"* or *"tell me the battery status"* to phone API calls.
- **Hassle-Free Path Setup:** Dynamically detects and prepends Termux binary folders (`/data/data/com.termux/files/usr/bin`) to the environment path at runtime.
- **Desktop Simulator Mode:** Simulated output layer allowing fully functional testing on Windows/macOS if run outside Termux.

---

## 📁 Project Structure
- `app.py`: Flask Web Server hosting the Web UI + background Telegram bot listener + Model API.
- `termux_needle.py`: Lightweight interactive command-line assistant with model selector and dynamic switching.
- `requirements.txt`: Python package dependencies list (`cactus-needle>=3.0.0`).

---

## 🚀 Setup Guide

### 1. Prerequisites (on Android Phone)
Inside Termux, install the required packages:
```bash
pkg update && pkg upgrade
pkg install termux-api python git
pkg install proot-distro
proot-distro install ubuntu
proot-distro login ubuntu
```
Make sure you have the [Termux:API app](https://f-droid.org/en/packages/com.termux.api/) installed on your Android device.

### 2. Install Dependencies
```bash
apt update && apt upgrade -y
apt install git python3 python3-pip python3-venv ca-certificates -y
```

Clone this repository and install the dependencies:
```bash
git clone https://github.com/AbuZar-Ansarii/Needle.git
cd Needle
python3 -m venv myenv
source myenv/bin/activate
pip3 install -r requirements.txt
```

> **Note on PRoot Ubuntu:** `app.py` and `termux_needle.py` automatically sanitize inherited Termux environment variables (`ANDROID_ROOT` and `ANDROID_DATA`) at runtime so that `needle` correctly detects the Ubuntu ARM64 (`manylinux2014_aarch64`) environment and loads the engine seamlessly.

---

## 🧠 Selecting & Switching Models

You can choose whether to run **Needle 3** (default) or **Needle 2** across all modes:

### 1. Launch Interactive Web UI
Start the Flask server:
```bash
# Default (Needle 3)
python3 app.py

# Or launch directly with Needle 2
python3 app.py --model 2
```
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```
> **Tip:** You can switch between **Needle 3** and **Needle 2** anytime by clicking the model toggle buttons in the top header of the web page!

### 2. Launch CLI Mode
Run the terminal-only interface:
```bash
# Interactive selection prompt at startup
python termux_needle.py

# Or specify your model explicitly
python termux_needle.py --model 3
python termux_needle.py --model 2
```
* **Dynamic CLI Switch:** Inside the assistant prompt, simply type `/model 2` or `/model 3` to switch models instantly without closing the session.

### 3. Remote Telegram Bot Control
Launch `app.py` with the Telegram token:
```bash
python3 app.py --telegram YOUR_BOT_TOKEN
# Or specify a model at the same time:
python3 app.py --model 3 --telegram YOUR_BOT_TOKEN
```
* **Remote Model Switch:** Message `/model` to see the current model, or `/model 2` / `/model 3` to change models remotely from Telegram.

---

## ⚡ Supported Commands & Capabilities

### 📱 Phone Hardware & Sensor Controls
- **Torch Control:** *"turn on the flashlight"* / *"turn off torch"*
- **Battery Status:** *"what is the battery percentage and health?"*
- **Screen Brightness:** *"set screen brightness to 180"* / *"set brightness to auto"*
- **Haptic Vibration:** *"vibrate phone for 500ms"*
- **Hardware Sensors:** *"read phone accelerometer and light sensors"*
- **Screen Capture:** *"take a screenshot of the phone screen"*
- **Wallpaper Setting:** *"set home wallpaper to /sdcard/Download/photo.jpg"*
- **System Wake Lock:** *"acquire wake lock to prevent phone sleep"* / *"release wake lock"*
- **Button Simulation:** *"press home button"* / *"press volume up"* / *"press back"*
- **Biometric Authentication:** *"authenticate with fingerprint"*

### 📶 Connectivity & Radio Management
- **Wi-Fi Details & Scanning:** *"what wifi network is connected?"* / *"scan nearby wifi networks"*
- **Wi-Fi Toggle:** *"turn on wifi"* / *"turn off wifi"*
- **Telephony & SIM Status:** *"get SIM operator and device network info"*
- **Cell Tower Radio Info:** *"show nearby cellular towers and signal strengths"*
- **NFC Tag Scanner:** *"scan for nearby NFC tags"*
- **Location Status:** *"where am I right now?"* (GPS latitude, longitude, altitude)

### 🎵 Audio, Speech & Media
- **Text-to-Speech (TTS):** *"say out loud that battery is low"*
- **Volume Control:** *"check current volume levels"* / *"set music volume to 12"*
- **Media Player Control:** *"play audio file song.mp3"* / *"pause music"* / *"stop playback"*
- **Microphone Recording:** *"start recording audio to note.3gp"* / *"stop recording"*
- **Audio Routing & Hardware:** *"check if headphones or Bluetooth are connected"*

### ✉️ Messaging, Calling & Contacts
- **SMS Messaging:** *"send sms to +1234567 saying Hello"* / *"get my last 5 text messages"*
- **Voice Calling:** *"call +1234567"* / *"show recent call logs"*
- **Contact Book:** *"list my contacts"*
- **On-Screen Popups:** *"show a toast saying Done"* / *"send a notification titled Alert saying Battery Low"*
- **Interactive Prompts:** *"display a confirmation dialog asking to proceed"*
- **Clipboard Management:** *"copy Hello World to clipboard"* / *"what's on my clipboard?"*

### 🚀 Apps, System & Needle 3 Intelligence
- **App Launcher:** *"open WhatsApp"* / *"open YouTube"* / *"open Chrome"* / *"open Google Maps"*
- **File Downloads & Sharing:** *"download file from https://example.com/file.zip"* / *"share text Hello World"*
- **Needle 3 Structured Extraction:** *"extract contact info from: Call Alex Vance at +15550199 alex@city17.org"*
- **Needle 3 Semantic Search:** *"semantically search contacts for doctor or emergency"*
- **Native Embedding Engine:** Vector search and on-device text routing via `/api/embed` (3072-dim embeddings).
