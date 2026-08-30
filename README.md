# Termux Agentic Assistant (Needle LLM)

An ultra-lightweight, local agentic assistant for Android/Termux that controls phone hardware and parses queries in plain English. Powered by Cactus Compute's **Needle (14MB)** local LLM.

---

## 🌟 Features
- **Interactive Chat Web UI:** Sleek glassmorphic dashboard built using Flask for testing commands and monitoring live logs.
- **Remote Telegram Bot Control:** Start a background Telegram listener that lets you text your phone commands remotely and receive results instantly.
- **Natural Language Translation:** Translates commands like *"turn on flashlight"* or *"tell me the battery status"* to phone API calls.
- **Hassle-Free Path Setup:** Dynamically detects and prepends Termux binary folders (`/data/data/com.termux/files/usr/bin`) to the environment path at runtime.
- **Desktop Simulator Mode:** Simulated output layer allowing fully functional testing on Windows/macOS if run outside Termux.

---

## 📁 Project Structure
- `app.py`: Flask Web Server hosting the Web UI + background Telegram bot listener.
- `termux_needle.py`: Lightweight interactive command-line assistant.
- `requirements.txt`: Python package dependencies list.

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



### 2. Install  Dependencies
```
apt install git python3 python3-pip python3-venv -y
```

Clone this repository and install the dependencies:
```bash
git clone https://github.com/AbuZar-Ansarii/Needle.git
cd Needle
python3 -m venv myenv
source myenv/bin/activate
```
```
pip3 install -r requirements.txt
```

### 3. Run the Agent

#### Option A: Launch Interactive Web UI
Start the Flask server:
```bash
python3 app.py
```
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

#### Option B: Launch CLI Mode
Run the terminal-only interface:
```bash
python termux_needle.py
```

#### Option C: Activate Remote Telegram Bot Control
When launching `app.py`, the terminal will ask if you want to activate Telegram remote control:
```text
Do you want to use Telegram remote control? (yes/no): yes
Enter your Telegram Bot Token: <YOUR_BOT_TOKEN>
```
*Alternatively, you can skip the prompt by setting the environment variable or using arguments:*
```bash
python3 app.py --telegram YOUR_BOT_TOKEN
```
Once connected, you can message your bot on Telegram in plain English to control your phone remotely!

---

## ⚡ Supported Commands
- **Toast Notifications:** *"show a toast saying Hello"*
- **Vibration:** *"vibrate phone for 1 second"*
- **Torch Control:** *"turn on the flashlight"* / *"turn off flashlight"*
- **Battery Status:** *"what is the battery level?"*
- **Speech Synthesis:** *"say out loud that battery is low"*
- **Location Status:** *"where am I right now?"* (GPS location coordinates)
- **Clipboard Management:** *"copy Hello World to clipboard"* / *"what's on my clipboard?"*
- **Wi-Fi Information:** *"what network is the phone connected to?"*
- **Call & SMS:** *"call +1234567"* / *"send sms to +1234567 saying Hello"*
- **Camera Access:** *"take a photo using back camera"* / *"capture front camera photo"*
- **SMS Reading:** *"get my last 5 text messages"*
- **Contacts:** *"list my contacts"*
- **Downloads:** *"download file from https://example.com/file.zip"*
