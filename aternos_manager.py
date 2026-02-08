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
SERVER_ID = "qtm3k14"

# --- KIỂM TRA THƯ VIỆN STEALTH ---
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

def is_working_time():
    """Kiểm tra giờ hoạt động theo giờ VN"""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🕒 Giờ VN hiện tại: {vn_now}h")
    # Khung giờ chạy: 9-11h, 14-16h, 19-23h
    working_hours = [(9, 11), (14, 16), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram_photo(photo_path, caption=""):
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
    except: pass

async def random_mouse_move(page):
    """Di chuyển chuột ngẫu nhiên để giả làm người"""
    for _ in range(3):
        x = random.randint(100, 1000)
        y = random.randint(100, 600)
        await page.mouse.move(x, y, steps=10)
        await asyncio.sleep(0.2)

async def solve_captcha(page):
    """Logic giải Captcha 'lì lợm' - Thử lại cho đến khi qua"""
    print("🛡️ Bắt đầu quy trình vượt Cloudflare...")
    
    for attempt in range(1, 6): # Thử tối đa 5 lần
        print(f"🔄 Nỗ lực giải Captcha lần {attempt}...")
        
        # 1. Tìm iframe chứa Captcha
        captcha_frame = None
        for frame in page.frames:
            if "challenges" in frame.url or "turnstile" in frame.url:
                captcha_frame = frame
                break
        
        if captcha_frame:
            # 2. Tìm checkbox
            checkbox = captcha_frame.locator("input[type='checkbox'], .ctp-checkbox-label, #challenge-stage").first
            if await checkbox.is_visible():
                box = await checkbox.bounding_box()
                if box:
                    # Di chuột lòng vòng rồi mới click
                    await random_mouse_move(page)
                    
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    print(f"🎯 Click vào tọa độ thực: X={x:.1f}, Y={y:.1f}")
                    
                    await page.mouse.move(x, y, steps=15)
                    await page.mouse.click(x, y)
                    await asyncio.sleep(5) # Chờ phản hồi sau click
            else:
                print("⚠️ Thấy frame nhưng không thấy nút bấm.")
        else:
            print("⚠️ Không tìm thấy frame Captcha (Có thể đã vượt qua hoặc chưa load).")

        # 3. Kiểm tra xem đã qua chưa (Bằng cách tìm thẻ Server)
        try:
            # Nếu tìm thấy text server nghĩa là đã vào trong
            if await page.get_by_text(SERVER_ID, exact=False).first.is_visible():
                print("✅ ĐÃ VƯỢT QUA CAPTCHA THÀNH CÔNG!")
                return True
        except: pass
        
        await asyncio.sleep(3) # Nghỉ trước khi thử lại

    print("❌ Đã thử 5 lần nhưng thất bại.")
    return False

async def run_logic():
    if not is_working_time():
        print("💤 Ngoài giờ hoạt động. Bot nghỉ.")
        return

    async with async_playwright() as p:
        # Khởi tạo browser với các flag chống bot
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--window-size=1280,720"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            device_scale_factor=1,
        )
        page = await context.new_page()
        
        # Kích hoạt Stealth (Quan trọng nhất)
        if HAS_STEALTH:
            await stealth_async(page)
            print("🕵️ Stealth Mode: ON")
        else:
            print("⚠️ CẢNH BÁO: Không có Stealth Mode!")

        # Nạp Cookie
        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])

        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8) # Đợi trang ổn định

            # --- GIAI ĐOẠN 1: GIẢI CAPTCHA ---
            success = await solve_captcha(page)
            
            # Chụp ảnh báo cáo sau khi giải
            await page.screenshot(path="after_captcha_attempt.png")
            if not success:
                send_telegram_photo("after_captcha_attempt.png", "❌ Bot bó tay với Captcha rồi ông giáo ạ!")
                return
            else:
                send_telegram_photo("after_captcha_attempt.png", "✅ Đã vượt Captcha! Đang tìm server...")

            # --- GIAI ĐOẠN 2: CHỌN SERVER ---
            print(f"🔎 Đang tìm server chứa: {SERVER_ID}")
            server_card = page.get_by_text(SERVER_ID, exact=False).first
            
            if await server_card.is_visible():
                await server_card.click()
                print("➡️ Đang vào trang quản lý...")
                await asyncio.sleep(8)
                
                # --- GIAI ĐOẠN 3: BẬT VÀ CONFIRM ---
                start_btn = page.locator("#start").first
                if await start_btn.is_visible():
                    status = (await page.locator(".statuslabel-label").inner_text()).strip()
                    print(f"📊 Trạng thái hiện tại: {status}")
                    
                    if "Offline" in status:
                        await start_btn.click()
                        print("⚡ Đã nhấn START!")
                        send_telegram_photo("after_captcha_attempt.png", "🚀 Đã kích hoạt Server!")
                        
                        # Canh Confirm
                        print("⏳ Đang canh nút Xác nhận (Confirm)...")
                        for _ in range(30): # Canh 5 phút
                            await asyncio.sleep(10)
                            if await page.locator("#confirm").is_visible():
                                await page.locator("#confirm").click()
                                print("✅ Đã bấm Confirm!")
                                send_telegram_photo("after_captcha_attempt.png", "✅ Đã xác nhận hàng chờ!")
                                break
                    else:
                        print("✅ Server đã Online/Loading.")
                else:
                    print("⚠️ Vào được nhưng không thấy nút Start.")
                    await page.screenshot(path="no_start_btn.png")
                    send_telegram_photo("no_start_btn.png", "⚠️ Lỗi: Không thấy nút Start")
            else:
                print("❌ Lỗi lạ: Đã vượt Captcha nhưng không thấy thẻ server.")
                
        except Exception as e:
            print(f"💥 Lỗi Crash: {e}")
            await page.screenshot(path="crash.png")
            send_telegram_photo("crash.png", f"💥 Bot sập nguồn: {e}")
        finally:
            await browser.close()
            print("🏁 Kết thúc.")

if __name__ == "__main__":
    asyncio.run(run_logic())
