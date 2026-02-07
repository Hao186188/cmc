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
        # Tăng độ phân giải màn hình để ép Aternos hiện giao diện Desktop đầy đủ
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
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(20) # Chờ load hoàn tất

            # Cách tìm server mới: Tìm tất cả các link có chứa "/server/"
            server_link = page.locator('a[href*="/server/"]').first
            
            if await server_link.count() > 0:
                print("Đã tìm thấy link server, đang truy cập...")
                await server_link.click()
                await page.wait_for_load_state("domcontentloaded", timeout=60000)
                await asyncio.sleep(10)
            else:
                # Nếu không tìm thấy, thử tìm class cũ .server-body
                server_entry = page.locator(".server-body, .server-name")
                if await server_entry.count() > 0:
                    print("Đã tìm thấy server qua class, đang truy cập...")
                    await server_entry.first.click()
                    await asyncio.sleep(10)
                else:
                    print("❌ LỖI: Không tìm thấy bất kỳ server nào trong danh sách.")
                    await page.screenshot(path="debug_screen.png")
                    return

            # Kiểm tra trạng thái và nhấn Start
            status_locator = page.locator(".statuslabel-label")
            if await status_locator.count() > 0:
                status = (await status_locator.inner_text()).strip()
                print(f"Trạng thái hiện tại: {status}")

                if "Offline" in status:
                    print("Phát hiện Server đang tắt. Đang nhấn Start...")
                    # Click nút Start và xử lý lỗi nếu bị che bởi quảng cáo
                    start_btn = page.locator("#start")
                    await start_btn.scroll_into_view_if_needed()
                    await start_btn.click(force=True)
                    
                    if TELEGRAM_TOKEN:
                        send_telegram("🚀 *Aternos:* Server đang được bật từ GitHub Actions!")
                    
                    # Chờ xác nhận hàng chờ
                    for _ in range(30):
                        await asyncio.sleep(10)
                        confirm = page.locator("#confirm, .btn-success, .btn-primary")
                        if await confirm.is_visible():
                            print("Xuất hiện nút xác nhận, đang bấm...")
                            await asyncio.sleep(random.randint(5, 10))
                            await confirm.click(force=True)
                            if TELEGRAM_TOKEN:
                                send_telegram("✅ *Thành công:* Đã xác nhận hàng chờ server!")
                            break
                else:
                    print(f"Server đang {status}, không cần can thiệp.")
            else:
                print("⚠️ Không tìm thấy nhãn trạng thái. Có thể Session đã bị thoát.")
                await page.screenshot(path="debug_screen.png")

        except Exception as e:
            print(f"Lỗi thực thi: {e}")
            await page.screenshot(path="debug_screen.png")
        finally:
            await browser.close()
            print("Đã đóng Bot.")
if __name__ == "__main__":
    asyncio.run(run_logic())
