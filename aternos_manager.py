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

# Thông tin server của bro
SERVER_ID = "qtm3k14" 
# Tọa độ Cloudflare từ ảnh của bro
CF_X = 180
CF_Y = 175

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    # Giờ chạy: 9-11h, 14-16h, 19-23h
    working_hours = [(9, 11), (14, 16), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
    except: pass

async def solve_cloudflare_by_coord(page):
    """Click vào tọa độ Cloudflare chính xác (Ảnh 1000005433)"""
    print(f"🎯 Đang click vào tọa độ Captcha: X={CF_X}, Y={CF_Y}...")
    try:
        # Đợi 10s để trang load hẳn lớp Captcha
        await asyncio.sleep(10)
        # Di chuyển chuột và click
        await page.mouse.move(CF_X, CF_Y)
        await page.mouse.click(CF_X, CF_Y)
        return True
    except: return False

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động.")
        return

    async with async_playwright() as p:
        # Chạy headless=True để tiết kiệm tài nguyên GitHub
        browser = await p.chromium.launch(headless=True)
        # Giả lập màn hình giống hệt ảnh bro đã đo tọa độ
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1000, 'height': 600} # Set kích thước chuẩn để tọa độ không bị lệch
        )
        page = await context.new_page()
        await stealth_async(page)

        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print("🚀 Truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # BƯỚC 1: CLICK TỌA ĐỘ CAPTCHA
            await solve_cloudflare_by_coord(page)
            await asyncio.sleep(15) # Đợi load xong sau khi click
            await page.screenshot(path="step1_after_click.png")
            
            # BƯỚC 2: CLICK VÀO SERVER (Ảnh 5434)
            print(f"🔎 Tìm thẻ server {SERVER_ID}...")
            # Sử dụng JavaScript click trực tiếp để không bị quảng cáo che
            clicked = await page.evaluate(f"""(id) => {{
                const cards = document.querySelectorAll('.server-body, .server-name, div');
                for (let c of cards) {{
                    if (c.innerText.includes(id)) {{
                        c.click();
                        return true;
                    }}
                }}
                return false;
            }}""", SERVER_ID)

            if clicked:
                print("✅ Đã click vào Server card.")
                await asyncio.sleep(12)
            else:
                send_telegram_photo("step1_after_click.png", "❌ Click tọa độ xong vẫn không thấy Server!")
                return

            # BƯỚC 3: NHẤN NÚT START (Ảnh 5435)
            start_btn = page.locator(".btn.btn-lg.btn-success.start, #start")
            if await start_btn.is_visible():
                status = (await page.locator(".statuslabel-label").inner_text()).strip()
                print(f"Trạng thái: {status}")
                
                if "Offline" in status:
                    print("⚡ Nhấn START!")
                    await start_btn.click(force=True)
                    await asyncio.sleep(5)
                    await page.screenshot(path="step3_done.png")
                    send_telegram_photo("step3_done.png", f"✅ Bot đã nhấn Start cho {SERVER_ID} thành công!")
                else:
                    print(f"Server đã {status}, không cần bật.")
            else:
                await page.screenshot(path="step2_error.png")
                send_telegram_photo("step2_error.png", "⚠️ Không thấy nút Start sau khi vào trang server.")

        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash.png")
            send_telegram_photo("crash.png", f"💥 Bot crash: {str(e)}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_logic())
