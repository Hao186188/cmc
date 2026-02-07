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
    except: pass

async def solve_cloudflare(page):
    """Thử click vào ô Verify của Cloudflare nếu xuất hiện"""
    try:
        # Tìm iframe của Turnstile/Cloudflare
        frames = page.frames
        for frame in frames:
            if "turnstile" in frame.url or "cloudflare" in frame.url:
                print("🚩 Phát hiện thấy Captcha Cloudflare, đang thử click...")
                checkbox = frame.locator('#challenge-stage, .ctp-checkbox-label')
                if await checkbox.is_visible():
                    await checkbox.click()
                    return True
        # Nếu không thấy iframe, thử click đại vào tọa độ phổ biến
        await page.mouse.click(200, 200) 
    except: pass
    return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Tiêm script ẩn danh nâng cao
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Chờ Cloudflare xử lý
            await asyncio.sleep(20)
            await solve_cloudflare(page)
            await asyncio.sleep(10)

            # Kiểm tra nếu vẫn kẹt Captcha
            if await page.locator("iframe").count() > 0 and not await page.locator(".server-body").is_visible():
                print("❌ Vẫn bị kẹt Captcha.")
                await page.screenshot(path="captcha_stuck.png", full_page=True)
                send_telegram_photo("captcha_stuck.png", "⚠️ *Bot Aternos:* Bị kẹt Captcha Cloudflare!")
                return

            # Tìm và Click Server
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã thấy server, đang truy cập...")
                await server.click()
                await asyncio.sleep(10)
            else:
                print("❌ Không thấy danh sách server.")
                await page.screenshot(path="no_server.png")
                return

            # Kiểm tra Status và Start
            status_label = page.locator(".statuslabel-label").first
            if await status_label.is_visible():
                status = (await status_label.inner_text()).strip()
                print(f"Trạng thái: {status}")

                if "Offline" in status:
                    print("⚡ Đang nhấn START...")
                    await page.click("#start", force=True)
                    send_telegram("🔄 *Aternos:* Phát hiện server Offline. Đang bật lại...")
                    
                    # Xác nhận hàng chờ
                    for _ in range(30):
                        await asyncio.sleep(10)
                        confirm = page.locator("#confirm, .btn-success")
                        if await confirm.is_visible():
                            await confirm.click(force=True)
                            send_telegram("✅ *Thành công:* Đã vượt qua hàng chờ!")
                            break
                else:
                    print(f"Server đang {status}.")
            else:
                print("⚠️ Không thấy nút trạng thái.")
                await page.screenshot(path="status_error.png")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="error.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
