import subprocess
import json
import requests
import time
import os

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'monitor_config.json')

def load_monitor_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def get_session_status():
    try:
        result = subprocess.run(['openclaw', 'session', 'status', '--json'], capture_output=True, text=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting status: {e}")
        return None

def send_discord_dm(message, config):
    token = config.get('discord_token')
    user_id = config.get('channel_id')
    if not token or not user_id:
        print("Missing Discord config.")
        return

    url = f"https://discord.com/api/v10/channels/{user_id}/messages"
    # First, create/get DM channel
    dm_url = "https://discord.com/api/v10/users/@me/channels"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(dm_url, json={"recipient_id": user_id}, headers=headers)
        channel_id = resp.json()['id']
        
        msg_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        requests.post(msg_url, json={"content": message}, headers=headers)
        print("Alert sent to Discord.")
    except Exception as e:
        print(f"Error sending Discord message: {e}")

def monitor():
    config = load_monitor_config()
    status = get_session_status()
    if not status:
        return

    threshold = config.get('threshold', 20.0)
    usage_data = status.get('usage', {})
    for model, data in usage_data.items():
        left_percent = data.get('leftPercent')
        if left_percent is not None and left_percent <= threshold:
            msg = f"⚠️ **Token 警報**\n模型 `{model}` 剩餘額度僅剩 `{left_percent}%`！\n請注意使用量或更換模型。"
            send_discord_dm(msg, config)
            print(f"Alert triggered: {left_percent}% left")
        else:
            print(f"Status OK: {model} has {left_percent}% left")

if __name__ == "__main__":
    monitor()
