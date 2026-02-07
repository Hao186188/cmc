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
    working_hours = [(8, 12), (14, 17), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
        print(f"✅ Đã gửi ảnh: {photo_path}")
    except Exception as e:
        print(f"❌ Lỗi gửi ảnh: {e}")

async def solve_cloudflare(page):
    print("🔎 Đang tìm ô xác minh Cloudflare...")
    try:
        # Đợi các iframe load xong
        await asyncio.sleep(5)
        frames = page.frames
        for frame in frames:
            if "turnstile" in frame.url or "challenge" in frame.url:
                # Thử tìm ô checkbox trong iframe
                checkbox = frame.locator('input[type="checkbox"], #challenge-stage, .ctp-checkbox-label')
                if await checkbox.is_visible():
                    print("🎯 Thấy ô tích rồi! Đang click...")
                    # Di chuyển chuột ngẫu nhiên trước khi click để giống người hơn
                    box = await checkbox.bounding_box()
                    if box:
                        await page.mouse.move(box['x'] + random.randint(1,10), box['y'] + random.randint(1,10))
                        await checkbox.click()
                        return True
        # Nếu không thấy iframe, có thể là trang bị trắng hoặc lỗi load
        return False
    except: return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        # Dùng thêm các flag để trình duyệt trông "thật" hơn
        browser = await p.chromium.launch(headless=True, args=[
            "--no-sandbox", 
            "--disable-blink-features=AutomationControlled"
        ])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        # Xóa dấu vết bot
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(15)

            # --- CHỤP ẢNH KIỂM TRA ĐẦU TIÊN ---
            await page.screenshot(path="step1_initial.png", full_page=True)
            send_telegram_photo("step1_initial.png", "📸 Bước 1: Vừa vào trang")

            # Xử lý Captcha
            captcha_solved = await solve_cloudflare(page)
            if captcha_solved:
                print("✅ Đã bấm vào Captcha, đợi load...")
                await asyncio.sleep(15)
            
            # Kiểm tra sau khi giải Captcha
            await page.screenshot(path="step2_after_captcha.png", full_page=True)

            # QUÉT SERVER (Dùng lại danh sách selector chi tiết của bro)
            server_selectors = [".server-body", ".server-name", "a[href*='/server/']", ".server-card"]
            found_server = False
            for selector in server_selectors:
                locator = page.locator(selector).first
                if await locator.is_visible():
                    print(f"🎯 Thấy server qua: {selector}")
                    await locator.click()
                    found_server = True
                    break

            if not found_server:
                send_telegram_photo("step2_after_captcha.png", "❌ Không thấy server. Có thể kẹt Captcha!")
                return

            # Vào trang Start
            await asyncio.sleep(10)
            status_label = page.locator(".statuslabel-label").first
            if await status_label.is_visible():
                status = (await status_label.inner_text()).strip()
                print(f"Trạng thái: {status}")
                if "Offline" in status:
                    await page.click("#start", force=True)
                    send_telegram("🔄 Đang bật server...")
                    # Chờ confirm...
                else:
                    send_telegram(f"✅ Server đang {status}")
            else:
                await page.screenshot(path="step3_status_error.png")
                send_telegram_photo("step3_status_error.png", "⚠️ Không thấy nút Start")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash_error.png")
            send_telegram_photo("crash_error.png", f"💥 Lỗi: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_logic())
