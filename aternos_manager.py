import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
# Trên GitHub, các biến này phải được cài trong Settings > Secrets and variables > Actions
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    # Kiểm tra khung giờ hoạt động (Ví dụ: 9h-11h, 14h-16h, 19h-23h)
    working_hours = [(9, 11), (14, 16), (19, 23)]
    for start, end in working_hours:
        if start <= vn_now < end: return True
    return False

def send_telegram(message):
    # Sửa logic: In ra log để debug nếu thiếu Token
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"⚠️ Telegram chưa gửi được: Thiếu TG_TOKEN hoặc TG_CHAT_ID trong Secrets!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Đã gửi thông báo Telegram thành công.")
        else:
            print(f"❌ Telegram phản hồi lỗi: {response.text}")
    except Exception as e:
        print(f"❌ Lỗi kết nối Telegram: {e}")

async def apply_stealth(page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động. Bot thoát.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        await apply_stealth(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("Đang truy cập danh sách Server...")
            # Sử dụng wait_until="load" để đảm bảo mọi script quan trọng đã chạy
            await page.goto(ATERNOS_URL, wait_until="load", timeout=90000)
            await asyncio.sleep(20) # Chờ thêm 20s cho chắc

            # QUÉT SERVER: Tìm bất cứ thẻ nào có class chứa chữ "server" hoặc link dẫn đến /server/
            server_selectors = [".server-body", ".server-name", "a[href*='/server/']", ".server-id"]
            found_server = False

            for selector in server_selectors:
                locator = page.locator(selector).first
                if await locator.count() > 0:
                    print(f"🎯 Đã tìm thấy server qua selector: {selector}")
                    await locator.click()
                    found_server = True
                    break

            if not found_server:
                print("❌ LỖI: Không tìm thấy bất kỳ server nào. Đang chụp ảnh debug...")
                await page.screenshot(path="debug_screen.png")
                send_telegram("⚠️ *Bot Aternos:* Đã đăng nhập nhưng không thấy server nào trong danh sách!")
                return

            # Chờ chuyển trang vào bảng điều khiển
            await page.wait_for_load_state("load", timeout=60000)
            await asyncio.sleep(10)

            # Kiểm tra trạng thái và Start
            status_locator = page.locator(".statuslabel-label")
            if await status_locator.count() > 0:
                status = (await status_locator.inner_text()).strip()
                print(f"Trạng thái hiện tại: {status}")

                if "Offline" in status:
                    print("Bắt đầu khởi động server...")
                    await page.click("#start", force=True)
                    send_telegram(f"📉 *Aternos:* Server đang Offline. Bot đang tiến hành bật lại cho bạn!")
                    
                    # Xác nhận hàng chờ
                    for _ in range(25):
                        await asyncio.sleep(10)
                        confirm = page.locator("#confirm, .btn-success, .btn-primary")
                        if await confirm.is_visible():
                            await asyncio.sleep(5)
                            await confirm.click(force=True)
                            send_telegram("✅ *Aternos:* Đã bấm xác nhận hàng chờ thành công!")
                            break
                else:
                    print(f"Server đang {status}. Không cần can thiệp.")
            else:
                print("⚠️ Không thấy nhãn trạng thái. Có thể trang chưa load xong.")
                await page.screenshot(path="debug_screen.png")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="debug_screen.png")
        finally:
            await browser.close()
            print("Đã đóng Bot.")

if __name__ == "__main__":
    asyncio.run(run_logic())
