import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION") # Mã session bro vừa dùng thành công
ATERNOS_URL = "https://aternos.org/servers/"

WORKING_HOURS = [(9, 11), (14, 16), (19, 23)]

async def apply_stealth(page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    for start, end in WORKING_HOURS:
        if start <= vn_now < end: return True
    return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await apply_stealth(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("Đang truy cập danh sách Server...")
            await page.goto(ATERNOS_URL, wait_until="networkidle")
            await asyncio.sleep(5)

            # 1. Tìm và click vào server đầu tiên trong danh sách
            server_entry = page.locator(".server-body")
            if await server_entry.count() > 0:
                print("Đã tìm thấy server, đang truy cập vào bảng điều khiển...")
                await server_entry.first.click()
                await asyncio.sleep(5) # Chờ chuyển trang
            else:
                print("Chưa thấy server nào. Bạn hãy tạo server trên web trước nhé!")
                await page.screenshot(path="debug_screen.png")
                return

            # 2. Kiểm tra trạng thái và bật server
            status_locator = page.locator(".statuslabel-label")
            if await status_locator.count() > 0:
                status = (await status_locator.inner_text()).strip()
                print(f"Trạng thái: {status}")

                if "Offline" in status:
                    print("Đang khởi động...")
                    await page.click("#start")
                    # Gửi thông báo Telegram tại đây...
                    
                    # Chờ nút xác nhận hàng chờ
                    for _ in range(20):
                        await asyncio.sleep(10)
                        confirm = page.locator("#confirm, .btn-success")
                        if await confirm.is_visible():
                            await asyncio.sleep(random.randint(5, 10))
                            await confirm.click()
                            print("Đã xác nhận hàng chờ!")
                            break
            else:
                print("Không tìm thấy nút Start. Check debug_screen.png")
                await page.screenshot(path="debug_screen.png")

        except Exception as e:
            print(f"Lỗi: {e}")
        finally:
            await browser.close()
            print("Đã đóng Bot.")

if __name__ == "__main__":
    asyncio.run(run_logic())