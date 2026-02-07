import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# Thử import stealth an toàn
try:
    from playwright_stealth import stealth_async
    USE_STEALTH_LIB = True
except ImportError:
    USE_STEALTH_LIB = False

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
    except: pass

async def solve_cloudflare(page):
    print("🔎 Đang tìm ô xác minh Cloudflare...")
    try:
        await asyncio.sleep(10) # Chờ captcha load
        for frame in page.frames:
            if "cloudflare" in frame.url or "turnstile" in frame.url:
                # Selector cho ô checkbox của Cloudflare
                checkbox = frame.locator('#challenge-stage, .ctp-checkbox-label, input[type="checkbox"]')
                if await checkbox.count() > 0:
                    print("🎯 Thấy ô tích rồi! Đang click giả lập...")
                    box = await checkbox.bounding_box()
                    if box:
                        await page.mouse.move(box['x'] + 5, box['y'] + 5)
                    await checkbox.click()
                    return True
        return False
    except: return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động. Nghỉ ngơi thôi!")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        page = await context.new_page()

        # Áp dụng stealth ẩn danh
        if USE_STEALTH_LIB:
            await stealth_async(page)
        else:
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Nạp Cookie Session
        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(15)

            # Chụp ảnh check xem dính gì (Captcha hay Sign up)
            await page.screenshot(path="debug_start.png")
            
            # Xử lý Captcha
            if await solve_cloudflare(page):
                print("✅ Đã bấm Captcha, chờ load tiếp...")
                await asyncio.sleep(15)
                await page.screenshot(path="debug_after_captcha.png")

            # Quét tìm Server
            server = page.locator(".server-body, .server-name, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã thấy server, đang vào bảng điều khiển...")
                await server.click()
                await asyncio.sleep(10)

                # Kiểm tra trạng thái
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    print(f"Trạng thái: {status}")

                    if "Offline" in status:
                        print("⚡ Đang nhấn START...")
                        await page.click("#start", force=True)
                        send_telegram_photo("debug_start.png", "🚀 *Aternos:* Phát hiện server Offline. Đang bật lại!")
                        
                        # Xác nhận hàng chờ
                        for _ in range(25):
                            await asyncio.sleep(10)
                            confirm = page.locator("#confirm, .btn-success")
                            if await confirm.is_visible():
                                await confirm.click(force=True)
                                send_telegram("✅ *Aternos:* Đã xác nhận hàng chờ thành công!")
                                break
                    else:
                        print(f"Server đang {status}. Không can thiệp.")
            else:
                print("❌ Không thấy Server. Chụp ảnh báo cáo.")
                send_telegram_photo("debug_start.png", "❌ Không thấy server. Kiểm tra lại Captcha hoặc Session!")

        except Exception as e:
            print(f"💥 Lỗi thực thi: {e}")
            await page.screenshot(path="debug_error.png")
            send_telegram_photo("debug_error.png", f"💥 Lỗi bot: `{str(e)[:100]}`")
        finally:
            await browser.close()
            print("🏁 Kết thúc bot.")

if __name__ == "__main__":
    asyncio.run(run_logic())
