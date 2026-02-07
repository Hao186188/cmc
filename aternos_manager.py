import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    # Khung giờ làm việc (Khớp với yêu cầu của bro)
    working_hours = [(9, 11), (14, 16), (19, 23)]
    for start, end in working_hours:
        if start <= vn_now < end: return True
    return False

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Lỗi Telegram: {e}")

def send_telegram_photo(photo_path, caption="Debug screenshot"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or not os.path.exists(photo_path):
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            requests.post(url, files=files, data=data, timeout=15)
    except Exception as e:
        print(f"❌ Lỗi gửi ảnh: {e}")

async def apply_stealth(page):
    # SỬA LỖI: Trả về giá trị false cho navigator.webdriver để tránh bị check bot
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
    """)

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động. Bot thoát.")
        return

    async with async_playwright() as p:
        # Thêm các args chuẩn để vượt qua sandbox của GitHub
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        await apply_stealth(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("Đang truy cập danh sách Server...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(15)

            # Kiểm tra xem có bị văng ra trang Login không
            if "login" in page.url or await page.locator("input[name='username']").is_visible():
                print("⚠️ Cookie hết hạn!")
                await page.screenshot(path="debug_login.png")
                send_telegram_photo("debug_login.png", "⚠️ *Bot Aternos:* Session đã hết hạn, hãy cập nhật mã mới!")
                return

            # QUÉT SERVER
            server_selectors = [".server-body", ".server-name", "a[href*='/server/']", ".server-card"]
            found_server = False

            for selector in server_selectors:
                locator = page.locator(selector).first
                if await locator.is_visible():
                    print(f"🎯 Đã tìm thấy server: {selector}")
                    await locator.click()
                    found_server = True
                    break

            if not found_server:
                print("❌ Không tìm thấy server nào.")
                await page.screenshot(path="debug_screen.png", full_page=True)
                send_telegram_photo("debug_screen.png", "❌ *Bot Aternos:* Không tìm thấy server nào trong danh sách!")
                return

            # Chờ vào bảng điều khiển
            await page.wait_for_load_state("domcontentloaded", timeout=60000)
            await asyncio.sleep(10)

            # KIỂM TRA TRẠNG THÁI
            status_locator = page.locator(".statuslabel-label").first
            if await status_locator.is_visible():
                status = (await status_locator.inner_text()).strip()
                print(f"Trạng thái: {status}")

                if "Offline" in status:
                    print("Đang nhấn Start...")
                    # Click nút Start (sử dụng force=True để bỏ qua quảng cáo che khuất)
                    await page.click("#start", force=True)
                    send_telegram("📉 *Aternos:* Server đang Offline. Đang bật lại...")
                    
                    # Xác nhận hàng chờ
                    for i in range(25):
                        await asyncio.sleep(10)
                        confirm = page.locator("#confirm, .btn-success")
                        if await confirm.is_visible():
                            await asyncio.sleep(random.randint(5, 10))
                            await confirm.click(force=True)
                            send_telegram("✅ *Thành công:* Đã xác nhận hàng chờ!")
                            break
                else:
                    print(f"Server đang {status}.")
            else:
                print("⚠️ Không thấy trạng thái.")
                await page.screenshot(path="debug_status.png")
                send_telegram_photo("debug_status.png", "⚠️ *Bot Aternos:* Không thấy nhãn trạng thái server!")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="debug_error.png")
            send_telegram_photo("debug_error.png", f"💥 *Bot Aternos:* Lỗi script: `{str(e)[:100]}`")
        finally:
            await browser.close()
            print("Đã đóng Bot.")

if __name__ == "__main__":
    asyncio.run(run_logic())
