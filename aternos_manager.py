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
    # Khung giờ làm việc của ông
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
    print("🔎 Đang quét Cloudflare theo kỹ thuật Sniper...")
    try:
        # Đợi 10s cho challenge render
        await asyncio.sleep(10)
        
        # Lấy tất cả frame, tìm thằng chứa challenges.cloudflare.com
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                print("🎯 Đã bắt được Iframe Cloudflare!")
                # Các selector mục tiêu trong Turnstile
                selectors = ["#challenge-stage", ".mark", "input[type='checkbox']", "#ctp-checksum-container"]
                for s in selectors:
                    locator = frame.locator(s)
                    if await locator.count() > 0:
                        print(f"✅ Thấy mục tiêu: {s}. Đang giả lập click người thật...")
                        box = await locator.bounding_box()
                        if box:
                            # Di chuyển chuột zic-zac tới điểm click
                            await page.mouse.move(box['x'] - random.randint(5,15), box['y'] - random.randint(5,15))
                            await asyncio.sleep(0.5)
                            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                            print("🖱️ Click thành công!")
                            return True
        return False
    except Exception as e:
        print(f"⚠️ Lỗi giải Captcha: {e}")
        return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động. Bot tạm nghỉ.")
        return

    async with async_playwright() as p:
        # ARGS SIÊU ẨN DANH CỦA TIỀN BỐI
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors"
            ]
        )
        
        # User Agent mới nhất để khớp với cờ ẩn danh
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        
        context = await browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh"
        )
        
        page = await context.new_page()
        # Áp dụng Stealth mặt nạ
        await stealth_async(page)

        # Nạp Cookie (Phải đảm bảo ATERNOS_SESSION trong Secret là mới nhất)
        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print(f"🚀 Đang truy cập: {ATERNOS_URL}")
            # Dùng domcontentloaded để né lỗi Timeout 60s
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Ảnh check-in đầu tiên
            await asyncio.sleep(5)
            await page.screenshot(path="debug_1.png")
            send_telegram_photo("debug_1.png", "📸 Bước 1: Vừa vào trang")

            # Xử lý Cloudflare
            if await solve_cloudflare(page):
                print("⏳ Đợi xác minh chuyển hướng (20s)...")
                await asyncio.sleep(20)
                await page.screenshot(path="debug_2.png")
                send_telegram_photo("debug_2.png", "📸 Bước 2: Sau khi xử lý Cloudflare")

            # Tìm và tương tác Server
            server = page.locator(".server-body, .server-name, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã vào được danh sách server!")
                await server.click()
                await asyncio.sleep(10)
                
                # Check status và bật máy
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    print(f"Trạng thái hiện tại: {status}")
                    
                    if "Offline" in status:
                        await page.click("#start", force=True)
                        await asyncio.sleep(5)
                        await page.screenshot(path="debug_3.png")
                        send_telegram_photo("debug_3.png", f"✅ Đã bấm START! (Server đang {status})")
                    else:
                        print("Server đã bật sẵn rồi bro.")
            else:
                # Nếu thấy trang Sign up/Login là do Cookie tèo
                if "signup" in page.url or "login" in page.url:
                    send_telegram_photo("debug_1.png", "⚠️ Lỗi: Cookie ATERNOS_SESSION đã hết hạn!")
                else:
                    await page.screenshot(path="debug_fail.png")
                    send_telegram_photo("debug_fail.png", "❌ Kẹt Cloudflare hoặc không thấy nút Server.")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc phiên chạy.")

if __name__ == "__main__":
    asyncio.run(run_logic())
