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
    print("🔎 Đang thực hiện kỹ thuật phá rào Cloudflare...")
    try:
        # Chờ 15s cho Captcha ổn định
        await asyncio.sleep(15)
        
        # Tìm tất cả frame để định vị Cloudflare
        target_frame = None
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                target_frame = frame
                break
        
        if target_frame:
            print("🎯 Đã xác định được Iframe Cloudflare.")
            # Danh sách các điểm cần thử click (Selector của tiền bối + dự phòng)
            selectors = ["#challenge-stage", ".mark", ".ctp-checkbox-label", "input[type='checkbox']"]
            
            for s in selectors:
                locator = target_frame.locator(s)
                if await locator.count() > 0:
                    print(f"✅ Phát hiện mục tiêu: {s}")
                    box = await locator.bounding_box()
                    if box:
                        # Di chuyển chuột zic-zac để giống người
                        await page.mouse.move(box['x'] - 10, box['y'] - 10)
                        await asyncio.sleep(1)
                        await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                        await asyncio.sleep(0.5)
                        # Click vào tâm của box
                        await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                        print("🖱️ Đã thực hiện Click giả lập.")
                        return True
        else:
            print("⚠️ Không tìm thấy Frame, có thể Captcha dạng khác. Thử click tọa độ mặc định...")
            # Click vào vùng thường xuất hiện captcha (giữa trang, hơi lệch trên)
            await page.mouse.click(300, 300)
    except Exception as e:
        print(f"❌ Lỗi giải captcha: {e}")
    return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        # Bật trình duyệt với các thông số cực kỳ quan trọng
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled", # Quan trọng nhất để giấu bot
                "--disable-infobars"
            ]
        )
        # Sử dụng locale vi-VN để giống người dùng thật từ Việt Nam
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale="vi-VN"
        )
        
        page = await context.new_page()
        await stealth_async(page) # Mặt nạ cho trình duyệt

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="networkidle", timeout=60000)
            
            # Chụp ảnh 1: Kiểm tra tình hình
            await page.screenshot(path="debug_1_start.png")
            send_telegram_photo("debug_1_start.png", "📸 Bước 1: Trạng thái Cloudflare")

            # Giải Captcha
            if await solve_cloudflare(page):
                print("⏳ Đợi Cloudflare duyệt (20s)...")
                await asyncio.sleep(20)
                await page.screenshot(path="debug_2_after.png")
                send_telegram_photo("debug_2_after.png", "📸 Bước 2: Kết quả sau khi click")

            # Kiểm tra xem đã thấy server chưa
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Thành công vượt Captcha!")
                await server.click()
                await asyncio.sleep(10)
                
                # Logic Start Server
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    if "Offline" in status:
                        await page.click("#start", force=True)
                        send_telegram_photo("debug_2_after.png", "✅ Đã bấm START thành công!")
                    else:
                        print(f"Server đang {status}.")
            else:
                print("❌ Không thấy Server. Chụp ảnh debug cuối.")
                await page.screenshot(path="debug_final_fail.png")
                send_telegram_photo("debug_final_fail.png", "❌ Vẫn chưa qua được Cloudflare.")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
