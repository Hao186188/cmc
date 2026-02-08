import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# Kiểm tra và import thư viện stealth
try:
    from playwright_stealth import stealth_async
except ImportError:
    print("❌ LỖI: Thiếu thư viện 'playwright-stealth'.")
    print("👉 Hãy thêm 'playwright-stealth' vào file requirements.txt hoặc lệnh pip install.")
    stealth_async = None

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"

# Thông tin server và tọa độ đã xác định
SERVER_ID = "qtm3k14" 
CF_X = 180
CF_Y = 175

def is_working_time():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Giờ VN: {vn_now}h")
    # Khung giờ chạy: 9-11h, 14-16h, 19-23h
    working_hours = [(9, 11), (14, 16), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
    except Exception as e:
        print(f"❌ Không gửi được ảnh Telegram: {e}")

async def run_logic():
    if not is_working_time():
        print(">> Ngoài giờ hoạt động. Bot nghỉ.")
        return

    async with async_playwright() as p:
        # Khởi tạo trình duyệt
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        
        # CỰC KỲ QUAN TRỌNG: Viewport phải khớp với lúc bro đo tọa độ
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1000, 'height': 600} 
        )
        
        page = await context.new_page()
        
        # Kích hoạt Stealth nếu có thư viện
        if stealth_async:
            await stealth_async(page)
        else:
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Nạp Cookie
        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print(f"🚀 Truy cập Aternos (Server: {SERVER_ID})...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # --- BƯỚC 1: CLICK TỌA ĐỘ CAPTCHA (Ảnh 5433) ---
            print(f"🎯 Đang click Captcha tại tọa độ: X={CF_X}, Y={CF_Y}")
            await asyncio.sleep(12) # Chờ Captcha hiện ra
            await page.mouse.click(CF_X, CF_Y)
            
            await asyncio.sleep(15) # Đợi trang load sau khi giải Captcha
            await page.screenshot(path="after_captcha.png")
            
            # --- BƯỚC 2: TÌM VÀ VÀO SERVER (Ảnh 5434) ---
            print(f"🔎 Đang tìm thẻ server chứa text: {SERVER_ID}")
            # Dùng evaluate để click trực tiếp vào element chứa tên server
            success_click = await page.evaluate(f"""(sid) => {{
                const elements = document.querySelectorAll('.server-body, .server-name, div');
                for (let el of elements) {{
                    if (el.innerText.includes(sid)) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }}""", SERVER_ID)

            if success_click:
                print("✅ Đã click vào thẻ Server thành công.")
                await asyncio.sleep(10)
            else:
                print("❌ Không tìm thấy thẻ server. Có thể kẹt Captcha.")
                send_telegram_photo("after_captcha.png", "⚠️ Click tọa độ xong vẫn không thấy Server qtm3k14!")
                return

            # --- BƯỚC 3: BẬT SERVER (Ảnh 5435) ---
            start_btn = page.locator(".btn.btn-lg.btn-success.start, #start").first
            if await start_btn.is_visible():
                status = (await page.locator(".statuslabel-label").inner_text()).strip()
                print(f"📊 Trạng thái hiện tại: {status}")
                
                if "Offline" in status:
                    print("⚡ Đang nhấn START...")
                    await start_btn.click(force=True)
                    await asyncio.sleep(5)
                    await page.screenshot(path="final_result.png")
                    send_telegram_photo("final_result.png", f"✅ Đã nhấn START cho server {SERVER_ID}!")
                else:
                    print(f"Server không Offline (đang {status}). Không nhấn Start.")
            else:
                await page.screenshot(path="error_no_start.png")
                send_telegram_photo("error_no_start.png", "⚠️ Không tìm thấy nút Start trong trang điều khiển.")

        except Exception as e:
            print(f"💥 Lỗi thực thi: {e}")
            await page.screenshot(path="crash_debug.png")
            send_telegram_photo("crash_debug.png", f"💥 Bot gặp lỗi: {str(e)}")
        finally:
            await browser.close()
            print("🏁 Kết thúc luồng.")

if __name__ == "__main__":
    asyncio.run(run_logic())
