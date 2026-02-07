import os
import asyncio
import requests
from playwright.async_api import async_playwright

# --- CẤU HÌNH BẢO MẬT ---
# Code sẽ ưu tiên lấy từ GitHub Secret, nếu không có sẽ lấy từ biến cục bộ (để bạn test)
TELEGRAM_TOKEN = os.getenv("TG_TOKEN", "8464001667:AAGTwSFaaaPxaKh56-HhJNEKTp-NV_iExTE")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID", "8123911002")
ATERNOS_URL = "https://aternos.org/server/"

# Tự động xác định môi trường chạy (GitHub hay Local)
IS_GITHUB = "GITHUB_ACTIONS" in os.environ
USER_DATA_DIR = "./aternos_auth"

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

async def run_logic():
    async with async_playwright() as p:
        # Nếu chạy trên GitHub, dùng chế độ không cửa sổ (headless)
        # Nếu chạy trên máy bạn, ban đầu để headless=False để đăng nhập
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=IS_GITHUB,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()
        
        try:
            print("Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, timeout=60000)

            # Kiểm tra trạng thái đăng nhập
            if "login" in page.url:
                if IS_GITHUB:
                    send_telegram("⚠️ *LỖI:* GitHub Action hết hạn Session. Bạn cần chạy local để cập nhật aternos_auth!")
                else:
                    print("!!! VUI LÒNG ĐĂNG NHẬP TRÊN TRÌNH DUYỆT ĐANG MỞ !!!")
                    await asyncio.sleep(120) # Chờ bạn 2 phút để đăng nhập bằng tay
                return

            # Xử lý bật Server
            status_label = page.locator(".statuslabel-label")
            await status_label.wait_for(state="visible", timeout=20000)
            status = (await status_label.inner_text()).strip()
            print(f"Trạng thái: {status}")

            if "Offline" in status:
                await page.click("#start")
                # Chờ nút Confirm (EULA hoặc Queue)
                try:
                    confirm = page.locator("#confirm, .btn-success")
                    await confirm.wait_for(state="visible", timeout=10000)
                    await confirm.click()
                    send_telegram("✅ *Aternos:* Đã bấm Start và Xác nhận hàng chờ!")
                except:
                    send_telegram("🚀 *Aternos:* Đang khởi động Server...")
            
        except Exception as e:
            send_telegram(f"❌ *Lỗi:* {str(e)[:100]}")
        finally:
            await context.close()

if __name__ == "__main__":
    send_telegram("🤖 *Hệ thống khởi động:* Kiểm tra Aternos...")
    asyncio.run(run_logic())