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
        # Chờ thêm 15s sau khi load trang để Captcha render ổn định
        await asyncio.sleep(15)
        
        target_frame = None
        for frame in page.frames:
            if "challenges.cloudflare.com" in frame.url:
                target_frame = frame
                break
        
        if target_frame:
            print("🎯 Đã xác định được Iframe Cloudflare.")
            selectors = ["#challenge-stage", ".mark", ".ctp-checkbox-label", "input[type='checkbox']"]
            
            for s in selectors:
                locator = target_frame.locator(s)
                if await locator.count() > 0:
                    print(f"✅ Phát hiện mục tiêu: {s}")
                    box = await locator.bounding_box()
                    if box:
                        # Di chuyển chuột zic-zac
                        await page.mouse.move(box['x'] - random.randint(5,15), box['y'] - random.randint(5,15))
                        await asyncio.sleep(1)
                        # Click vào tâm
                        await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
                        print("🖱️ Đã thực hiện Click giả lập.")
                        return True
        else:
            print("⚠️ Không tìm thấy Frame Captcha cụ thể.")
    except Exception as e:
        print(f"❌ Lỗi giải captcha: {e}")
    return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1366, 'height': 768},
            locale="vi-VN"
        )
        
        page = await context.new_page()
        await stealth_async(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Đang truy cập Aternos (Chế độ load nhanh)...")
            # Thay đổi wait_until thành domcontentloaded để tránh Timeout mạng
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Chụp ảnh trạng thái ban đầu
            await asyncio.sleep(5) 
            await page.screenshot(path="debug_1_start.png")
            send_telegram_photo("debug_1_start.png", "📸 Bước 1: Vừa load trang xong")

            # Giải Captcha
            await solve_cloudflare(page)
            
            # Đợi kết quả sau click
            print("⏳ Chờ hệ thống xác nhận (20s)...")
            await asyncio.sleep(20)
            await page.screenshot(path="debug_2_after.png")
            send_telegram_photo("debug_2_after.png", "📸 Bước 2: Sau khi xử lý Captcha")

            # Kiểm tra Server
            server = page.locator(".server-body, a[href*='/server/']").first
            if await server.is_visible():
                print("🎯 Đã vượt rào thành công!")
                await server.click()
                await asyncio.sleep(8)
                
                status_label = page.locator(".statuslabel-label").first
                if await status_label.is_visible():
                    status = (await status_label.inner_text()).strip()
                    if "Offline" in status:
                        await page.click("#start", force=True)
                        send_telegram_photo("debug_2_after.png", f"✅ Đã bấm START (Server: {status})")
                    else:
                        print(f"Server đang {status}.")
            else:
                print("❌ Không thấy Server. Có thể kẹt Captcha hoặc Cookie hỏng.")
                await page.screenshot(path="debug_final_fail.png")
                send_telegram_photo("debug_final_fail.png", "❌ Thất bại: Không vào được danh sách server.")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
