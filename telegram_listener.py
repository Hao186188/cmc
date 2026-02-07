import requests
import subprocess
import time
import os
import datetime

TOKEN = os.getenv("TG_TOKEN", "8464001667:AAGTwSFaaaPxaKh56-HhJNEKTp-NV_iExTE")
CHAT_ID = os.getenv("TG_CHAT_ID", "8123911002")
API = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None
last_command_time = 0

def send_telegram(message):
    requests.post(f"{API}/sendMessage", data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"})

def get_updates():
    global last_update_id
    try:
        params = {"timeout": 30, "offset": last_update_id + 1 if last_update_id else None}
        r = requests.get(f"{API}/getUpdates", params=params, timeout=35).json()
        return r.get("result", [])
    except:
        return []

print("🤖 Bot đã sẵn sàng nghe lệnh...")
send_telegram("🚀 *Hệ thống quản lý Aternos đã Online!*")

while True:
    updates = get_updates()
    for u in updates:
        last_update_id = u["update_id"]
        msg = u.get("message", {})
        text = msg.get("text", "")
        
        if text == "/start_server":
            # Chống spam: 5 phút mới cho dùng lệnh 1 lần
            if time.time() - last_command_time < 300:
                send_telegram("⏳ *Chờ chút:* Server đang được xử lý, đừng spam nhé!")
            else:
                send_telegram("⚡ *Lệnh nhận được:* Đang khởi chạy quy trình bật Server...")
                subprocess.Popen(["python", "aternos_manager.py"])
                last_command_time = time.time()

        if text == "/status":
            send_telegram("🔍 *Đang kiểm tra...* (Vui lòng đợi 30s)")
            subprocess.Popen(["python", "aternos_manager.py"])

    time.sleep(2)