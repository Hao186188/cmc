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
    # Khung giờ làm việc của bro
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
    print("🔎 Đang áp dụng kỹ thuật truy quét Iframe Cloudflare...")
    try:
        # Chờ 10s cho Captcha load hẳn
        await asyncio.sleep(10)
        
        # Kỹ thuật tiền bối: Truy quét các Frame từ challenges.cloudflare.com
        target_frame = None
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                target_frame = frame
                break
        
        if target_frame:
            print("🎯 Đã bắt được Iframe Cloudflare!")
            # Các selector phổ biến của ô tích xanh
            selectors = ["#challenge-stage", ".mark", "input[type='checkbox']", "#ctp-checksum-container"]
            for s in selectors:
                locator = target_frame.locator(s)
                if await locator.count() > 0:
                    print(f"✅ Đã tìm thấy nút xác minh ({s}). Đang click...")
                    # Di chuyển chuột ngẫu nhiên để đánh lừa hệ thống
                    box = await locator.bounding_box()
                    if box:
                        await page.mouse.move(box['x'] + random.randint(1,5), box['y'] + random.randint(1,5))
                    await locator.click()
                    return True
        return False
    except Exception as e:
        print(f"⚠️ Lỗi giải captcha: {e}")
        return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        # Khởi tạo trình duyệt với các tham số ẩn danh
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768}
        )
        
        page = await context.new_page()
        # Áp dụng Stealth để xóa dấu vết bot
        await stealth_async(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Ảnh 1: Kiểm tra xem có dính Captcha hay không
            await asyncio.sleep(5)
            await page.screenshot(path="debug_1_start.png")
            
            # Thực thi giải Captcha
            if await solve_cloudflare(page):
                print("✅ Đã bấm xác minh. Đợi trang chuyển hướng...")
                await asyncio.sleep(15)
                await page.screenshot(path="debug_2_after_captcha.png")
                send_telegram_photo("debug_2_after_captcha.png", "📸 Đã vượt qua bước Captcha!")

            # Quét server (Nếu vào được trang chủ)
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã thấy server! Đang tiến vào...")
                await server.click()
                await asyncio.sleep(10)
                
                # Kiểm tra trạng thái và Start
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    if "Offline" in status:
                        await page.click("#start", force=True)
                        await page.screenshot(path="debug_3_success.png")
                        send_telegram_photo("debug_3_success.png", "✅ Server đang tắt. Bot đã nhấn START!")
                    else:
                        print(f"Server đang {status}.")
            else:
                # Nếu dính trang Sign Up (như ảnh bro gửi), báo lỗi Session
                if "signup" in page.url or await page.locator(".signup-form").is_visible():
                    send_telegram_photo("debug_1_start.png", "⚠️ *Lỗi:* Cookie hết hạn. Bot bị đẩy ra trang Đăng ký!")
                else:
                    await page.screenshot(path="debug_fail.png")
                    send_telegram_photo("debug_fail.png", "❌ *Lỗi:* Không tìm thấy server (Có thể kẹt Captcha).")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
            send_telegram_photo("crash.png", f"💥 Bot crash: {str(e)[:100]}")
        finally:
            await browser.close()
            print("🏁 Đã đóng trình duyệt.")

if __name__ == "__main__":
    asyncio.run(run_logic())
