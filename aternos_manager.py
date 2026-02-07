import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async  # Nếu vẫn lỗi, tui sẽ dùng cách tiêm script trực tiếp bên dưới

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    # CẬP NHẬT GIỜ: (8-12), (14-17), (19-23)
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
    print("🔎 Đang tìm ô xác minh Cloudflare...")
    try:
        await asyncio.sleep(10)
        for frame in page.frames:
            if "cloudflare" in frame.url or "turnstile" in frame.url:
                checkbox = frame.locator('#challenge-stage, .ctp-checkbox-label, input[type="checkbox"]')
                if await checkbox.count() > 0:
                    print("🎯 Đã thấy ô tích! Đang click...")
                    await checkbox.click()
                    return True
        return False
    except: return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        
        page = await context.new_page()
        
        # FIX LỖI IMPORT: Sử dụng stealth_async chuẩn hoặc script dự phòng
        try:
            await stealth_async(page)
        except:
            # Nếu thư viện lỗi, tự tiêm script để ẩn danh
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            await asyncio.sleep(15)
            await page.screenshot(path="debug_1.png")
            send_telegram_photo("debug_1.png", "📸 Bước 1: Check Captcha")

            await solve_cloudflare(page)
            await asyncio.sleep(10)

            # Kiểm tra login/server
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã vào danh sách Server!")
                await server.click()
                await asyncio.sleep(10)
                
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    if "Offline" in status:
                        await page.click("#start", force=True)
                        await page.screenshot(path="debug_2.png")
                        send_telegram_photo("debug_2.png", "🚀 Đã nhấn Start!")
                    else:
                        print(f"Server đang {status}.")
            else:
                # Nếu dính trang Sign Up như trong ảnh bro gửi, chứng tỏ Session sai
                if "signup" in page.url:
                    print("⚠️ Session bị sai hoặc hết hạn. Đang ở trang Sign Up.")
                    send_telegram_photo("debug_1.png", "⚠️ Sai Session (Cookie)! Bot đang kẹt ở trang đăng ký.")
                else:
                    await page.screenshot(path="debug_fail.png")
                    send_telegram_photo("debug_fail.png", "❌ Không vượt qua được Captcha.")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
