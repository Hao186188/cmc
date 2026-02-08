import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# Cố gắng ép buộc import
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

# --- CONFIG ---
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
SESSION = os.getenv("ATERNOS_SESSION")
SERVER_ID = "qtm3k14"
URL = "https://aternos.org/servers/"

def send_tg(msg, img=None):
    if not TG_TOKEN: return
    try:
        if img and os.path.exists(img):
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
            with open(img, "rb") as f:
                requests.post(url, data={"chat_id": TG_CHAT_ID, "caption": msg}, files={"photo": f}, timeout=15)
        else:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=15)
    except: pass

async def solve_cloudflare(page):
    print("🛡️ Đang xử lý Cloudflare...")
    for attempt in range(1, 6):
        print(f"🔄 Lần thử {attempt}...")
        
        # Chờ frame load
        await asyncio.sleep(5)
        
        for frame in page.frames:
            if "challenges" in frame.url or "turnstile" in frame.url:
                # Cách 1: Tìm selector chuẩn
                checkpoint = frame.locator('#challenge-stage, .ctp-checkbox-label, input').first
                box = await checkpoint.bounding_box()
                
                if box:
                    target_x = box['x'] + box['width'] / 2
                    target_y = box['y'] + box['height'] / 2
                else:
                    # Cách 2: Nếu không lấy được box, click vào tọa độ tương đối trong frame
                    # Cloudflare thường nằm giữa frame
                    print("⚠️ Không lấy được box, click vào tọa độ ước tính giữa frame.")
                    target_x = 150 # Ước tính trong frame
                    target_y = 30  # Ước tính trong frame
                
                await page.mouse.move(target_x, target_y, steps=10)
                await page.mouse.click(target_x, target_y)
                print(f"🎯 Đã click vào tọa độ: {target_x}, {target_y}")
                
                await asyncio.sleep(10) # Chờ xác minh
                
                # Kiểm tra nếu đã vượt qua (không còn frame challenge)
                if not any("challenges" in f.url for f in page.frames):
                    print("✅ Có vẻ đã vượt qua Cloudflare.")
                    return True
        
        # Nếu chưa được, thử refresh nhẹ
        if attempt == 3:
            print("🔄 Refresh trang để làm mới Captcha...")
            await page.reload()
            await asyncio.sleep(5)
            
    return False

async def run():
    async with async_playwright() as p:
        # Khởi động với cấu hình ẩn danh tối đa
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()
        if HAS_STEALTH:
            await stealth_async(page)
            print("🕵️ Stealth Mode: Hoạt động")
        else:
            print("🚨 CẢNH BÁO: Stealth Mode thất bại. Cloudflare sẽ chặn.")

        if SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])

        try:
            await page.goto(URL, wait_until="domcontentloaded")
            
            # Giải captcha
            await solve_cloudflare(page)
            await page.screenshot(path="debug.png")
            
            # Kiểm tra server
            server = page.get_by_text(SERVER_ID).first
            if await server.is_visible():
                print("✅ Đã thấy server!")
                await server.click()
                await asyncio.sleep(5)
                
                # Click Start
                start_btn = page.locator("#start")
                if await start_btn.is_visible():
                    await start_btn.click()
                    send_tg(f"🚀 Server {SERVER_ID} đang khởi động!", "debug.png")
            else:
                print("❌ Không thấy server. Kiểm tra ảnh debug.")
                send_tg("❌ Không tìm thấy nút Server. Có thể kẹt Captcha.", "debug.png")
                
        except Exception as e:
            print(f"💥 Lỗi: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
