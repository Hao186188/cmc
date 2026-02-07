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

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
    except: pass

async def apply_stealth(page):
    """Hàm tự chế để xóa dấu vết bot thay cho thư viện lỗi"""
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['vi-VN', 'vi', 'en-US', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    """)

async def solve_cloudflare(page):
    print("🔎 Đang quét Cloudflare theo kỹ thuật Sniper...")
    try:
        await asyncio.sleep(12)
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                print("🎯 Đã thấy Iframe Cloudflare!")
                selectors = ["#challenge-stage", ".mark", "input[type='checkbox']"]
                for s in selectors:
                    locator = frame.locator(s)
                    if await locator.count() > 0:
                        box = await locator.bounding_box()
                        if box:
                            # Di chuyển chuột zic-zac
                            await page.mouse.move(box['x'] - 5, box['y'] - 5)
                            await asyncio.sleep(0.5)
                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                            print(f"✅ Đã click vào {s}!")
                            return True
        return False
    except: return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ]
        )
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        # Áp dụng ẩn danh tự chế
        await apply_stealth(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print(f"🚀 Truy cập: {ATERNOS_URL}")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            await asyncio.sleep(10)
            await page.screenshot(path="debug_1.png")
            send_telegram_photo("debug_1.png", "📸 Bước 1: Check Captcha")

            if await solve_cloudflare(page):
                print("⏳ Đợi xử lý (20s)...")
                await asyncio.sleep(20)
                await page.screenshot(path="debug_2.png")
                send_telegram_photo("debug_2.png", "📸 Bước 2: Sau khi xử lý")

            # Click vào server đầu tiên
            server = page.locator(".server-body, .server-name, a[href*='/server/']").first
            if await server.is_visible():
                await server.click()
                await asyncio.sleep(10)
                
                status = (await page.locator(".statuslabel-label").first.inner_text()).strip()
                if "Offline" in status:
                    await page.click("#start", force=True)
                    send_telegram_photo("debug_2.png", "✅ Đã nhấn START!")
                else:
                    print(f"Server đang {status}")
            else:
                print("❌ Không thấy server.")
                await page.screenshot(path="debug_fail.png")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_logic())
