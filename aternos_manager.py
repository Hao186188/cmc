import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
SESSION = os.getenv("ATERNOS_SESSION")
SERVER_ID = "qtm3k14"
URL = "https://aternos.org/servers/"

# --- KIỂM TRA STEALTH ---
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

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
    """Vòng lặp giải Captcha cho đến khi thành công"""
    print("🛡️ Đang quét Cloudflare Turnstile...")
    
    for attempt in range(1, 7): # Thử tối đa 6 lần (khoảng 1-2 phút)
        print(f"🔄 Nỗ lực vượt Captcha lần {attempt}...")
        
        # Chờ frame xuất hiện
        await asyncio.sleep(7)
        
        # Tìm tất cả các frame để săn lùng Turnstile
        captcha_clicked = False
        for frame in page.frames:
            if "challenges" in frame.url or "turnstile" in frame.url:
                # Selector tìm ô xác minh
                target = frame.locator('.ctp-checkbox-label, #challenge-stage, input[type="checkbox"]').first
                box = await target.bounding_box()
                
                if box:
                    # Tính toán tọa độ tâm
                    cx = box['x'] + box['width'] / 2
                    cy = box['y'] + box['height'] / 2
                    
                    # Giả lập di chuyển và click bồi
                    await page.mouse.move(cx + random.randint(-5, 5), cy + random.randint(-5, 5), steps=10)
                    await page.mouse.click(cx, cy)
                    await asyncio.sleep(1)
                    await page.mouse.click(cx, cy)
                    print(f"🎯 Đã click vào Frame tại: {cx}, {cy}")
                    captcha_clicked = True
                    break
        
        if not captcha_clicked:
            # Fallback nếu không tìm thấy frame cụ thể, click tọa độ ước lượng
            print("⚠️ Không tìm thấy Frame cụ thể, thử click tọa độ dự phòng...")
            await page.mouse.click(180, 175)

        # Kiểm tra xem đã vào được trang server chưa
        await asyncio.sleep(10)
        if await page.get_by_text(SERVER_ID).count() > 0:
            print("✅ Đã vượt qua Captcha thành công!")
            return True
        
        # Nếu sau 3 lần vẫn kẹt, thử reload trang
        if attempt == 3:
            print("🔄 Vẫn kẹt Captcha, đang tải lại trang...")
            await page.reload()
            
    return False

async def run():
    async with async_playwright() as p:
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
            print("🕵️ Stealth Mode: Activated")

        if SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])

        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            
            # Bắt đầu giải Captcha
            success = await solve_cloudflare(page)
            await page.screenshot(path="status_after_captcha.png")
            
            if success:
                # Tìm và vào Server
                server = page.get_by_text(SERVER_ID).first
                await server.click()
                print("➡️ Đang vào Server...")
                await asyncio.sleep(10)
                
                # Kiểm tra nút Start
                start_btn = page.locator("#start").first
                if await start_btn.is_visible():
                    status = (await page.locator(".statuslabel-label").inner_text()).strip()
                    print(f"📊 Trạng thái: {status}")
                    
                    if "Offline" in status:
                        await start_btn.click()
                        print("⚡ Đã nhấn START!")
                        send_tg(f"🚀 Server {SERVER_ID} đã được kích hoạt!", "status_after_captcha.png")
                        
                        # Chờ nút Confirm hàng chờ (nếu có)
                        for _ in range(15): 
                            await asyncio.sleep(20)
                            confirm = page.locator("#confirm")
                            if await confirm.is_visible():
                                await confirm.click()
                                print("✅ Đã xác nhận hàng chờ!")
                                send_tg("✅ Đã bấm Confirm hàng chờ!")
                                break
                    else:
                        send_tg(f"✅ Server đã Online/Loading (Status: {status})")
                else:
                    send_tg("⚠️ Không thấy nút Start. Có thể do lỗi giao diện.", "status_after_captcha.png")
            else:
                send_tg("❌ Thất bại: Bot không thể vượt qua Captcha sau nhiều lần thử.", "status_after_captcha.png")
                
        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash_debug.png")
            send_tg(f"💥 Bot gặp lỗi: {str(e)}", "crash_debug.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc quy trình.")

if __name__ == "__main__":
    asyncio.run(run())
