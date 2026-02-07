import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    working_hours = [(8, 12), (14, 17), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
    except: pass

async def solve_cloudflare(page):
    """Logic tìm và click ô xác minh Cloudflare"""
    print("🔎 Đang quét tìm Captcha Cloudflare...")
    try:
        # Chờ 10s để Captcha kịp load
        await asyncio.sleep(10)
        
        # Tìm tất cả iframe trên trang
        for frame in page.frames:
            if "cloudflare" in frame.url or "turnstile" in frame.url:
                print("🚩 Phát hiện Iframe Cloudflare!")
                # Tìm ô checkbox cụ thể dựa trên cấu trúc Cloudflare Turnstile
                checkbox = frame.locator('#challenge-stage, .ctp-checkbox-label, input[type="checkbox"]')
                if await checkbox.count() > 0:
                    print("🎯 Đã thấy ô tích! Đang thực hiện click giả lập người...")
                    await checkbox.click()
                    return True
        return False
    except Exception as e:
        print(f"⚠️ Lỗi khi giải Captcha: {e}")
        return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        
        page = await context.new_page()
        # Sử dụng stealth để ẩn danh trình duyệt khỏi hệ thống quét của Cloudflare
        await stealth_async(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang mở Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Ảnh 1: Vừa vào trang (Để xem có dính Captcha không)
            await asyncio.sleep(5)
            await page.screenshot(path="debug_1_start.png")
            send_telegram_photo("debug_1_start.png", "📸 Bước 1: Vừa vào trang")

            # Xử lý xác minh con người
            if await solve_cloudflare(page):
                print("✅ Đã bấm xác minh. Đợi 15s để chuyển trang...")
                await asyncio.sleep(15)
                await page.screenshot(path="debug_2_after_captcha.png")
                send_telegram_photo("debug_2_after_captcha.png", "📸 Bước 2: Sau khi bấm Captcha")

            # Kiểm tra xem đã vào được danh sách Server chưa
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã vào được danh sách Server!")
                await server.click()
                await asyncio.sleep(10)
                
                # Kiểm tra trạng thái và Start
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    if "Offline" in status:
                        print("⚡ Server đang tắt. Nhấn Start...")
                        await page.click("#start", force=True)
                        await page.screenshot(path="debug_3_started.png")
                        send_telegram_photo("debug_3_started.png", "🚀 Đã nhấn Start Server!")
                    else:
                        print(f"Server đang {status}.")
            else:
                print("❌ Vẫn không thấy Server. Có thể Captcha chưa được giải.")
                await page.screenshot(path="debug_final_fail.png")
                send_telegram_photo("debug_final_fail.png", "❌ Lỗi: Không vượt qua được Captcha!")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
            send_telegram_photo("crash.png", f"💥 Bot gặp lỗi hệ thống: {e}")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
