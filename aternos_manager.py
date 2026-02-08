import os
import asyncio
import datetime
import requests
import random
import json
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")
ATERNOS_SESSION = os.getenv("ATERNOS_SESSION")
ATERNOS_URL = "https://aternos.org/servers/"
SERVER_ID = "qtm3k14"  # Tên server để tìm

# --- CẤU HÌNH HỆ THỐNG GIẢ LẬP ---
# Kích thước màn hình chuẩn HD để tọa độ không bị lệch
VIEWPORT_SIZE = {'width': 1280, 'height': 720}
# User Agent của Chrome thật trên Windows
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

def is_working_time():
    """Kiểm tra giờ hoạt động theo giờ VN"""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    vn_now = (now_utc + datetime.timedelta(hours=7)).hour
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🕒 Giờ VN hiện tại: {vn_now}h")
    working_hours = [(9, 11), (14, 16), (19, 23)]
    return any(start <= vn_now < end for start, end in working_hours)

def send_telegram_photo(photo_path, caption=""):
    """Gửi ảnh báo cáo về Telegram"""
    if not TELEGRAM_TOKEN or not os.path.exists(photo_path): return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(photo_path, "rb") as photo:
            requests.post(url, files={"photo": photo}, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption}, timeout=15)
        print(f"📤 Đã gửi ảnh: {caption}")
    except Exception as e:
        print(f"⚠️ Lỗi gửi Telegram: {e}")

async def smart_click_cloudflare(page):
    """
    Thuật toán tìm và click chính xác vào Cloudflare Widget
    Thay vì đoán tọa độ, nó tìm vị trí thực tế của phần tử (Bounding Box)
    """
    print("🛡️ Đang quét Cloudflare Turnstile...")
    found_widget = False
    
    # Đợi iframe xuất hiện
    await asyncio.sleep(5)
    
    for frame in page.frames:
        # Tìm iframe chứa Cloudflare
        if "cloudflare" in frame.url or "turnstile" in frame.url or "challenge" in frame.url:
            print(f"🔎 Phát hiện frame nghi vấn: {frame.url[:50]}...")
            
            # Các selector phổ biến của nút checkbox Cloudflare
            selectors = [
                "input[type='checkbox']", 
                ".ctp-checkbox-label", 
                "#challenge-stage", 
                "body" # Trường hợp click vào body của iframe con
            ]
            
            for selector in selectors:
                try:
                    element = frame.locator(selector).first
                    if await element.count() > 0:
                        # Lấy tọa độ thực tế của phần tử này
                        box = await element.bounding_box()
                        if box:
                            x = box["x"] + box["width"] / 2
                            y = box["y"] + box["height"] / 2
                            print(f"🎯 Tìm thấy mục tiêu tại: X={x}, Y={y}")
                            
                            # Di chuyển chuột tới đó (giả lập người)
                            await page.mouse.move(x, y, steps=10)
                            await asyncio.sleep(0.5)
                            await page.mouse.click(x, y)
                            found_widget = True
                            return True
                except:
                    continue
    
    # [PHƯƠNG ÁN DỰ PHÒNG] Nếu không tìm thấy element, click theo tọa độ thống kê
    if not found_widget:
        print("⚠️ Không lấy được element cụ thể, kích hoạt CLICK TỌA ĐỘ MÙ...")
        # Tọa độ này dựa trên Viewport 1280x720 và vị trí mặc định của Aternos
        fallback_x = 300
        fallback_y = 300
        await page.mouse.move(fallback_x, fallback_y, steps=10)
        await page.mouse.click(fallback_x, fallback_y)
        return True
        
    return False

async def run_logic():
    if not is_working_time():
        print("💤 Ngoài giờ hoạt động. Tắt bot.")
        return

    # Khởi tạo Playwright với stealth
    try:
        from playwright_stealth import stealth_async
        print("✅ Đã nạp module Stealth.")
    except ImportError:
        print("❌ LỖI NGHIÊM TRỌNG: Thiếu 'playwright-stealth'. Bot sẽ dễ bị phát hiện!")
        stealth_async = None

    async with async_playwright() as p:
        # Launch với các args chống phát hiện bot
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-size=1280,720"
            ]
        )
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT_SIZE,
            device_scale_factor=1,
            has_touch=False
        )
        
        page = await context.new_page()
        
        # Tiêm script ẩn danh
        if stealth_async:
            await stealth_async(page)
        
        # Xóa thuộc tính webdriver (lớp bảo vệ thủ công)
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Nạp Cookie
        if ATERNOS_SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": ATERNOS_SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])
        
        try:
            print(f"🚀 Truy cập Aternos...")
            await page.goto(ATERNOS_URL, wait_until="domcontentloaded", timeout=60000)
            
            # --- GIAI ĐOẠN 1: VƯỢT TƯỜNG LỬA ---
            await asyncio.sleep(8) # Chờ Cloudflare load
            await smart_click_cloudflare(page)
            
            # Chờ kết quả sau khi click
            print("⏳ Đang chờ xác minh...")
            await asyncio.sleep(10)
            await page.screenshot(path="step1_debug.png")
            send_telegram_photo("step1_debug.png", "📸 Tình trạng sau khi xử lý Captcha")

            # --- GIAI ĐOẠN 2: TÌM SERVER ---
            # Kiểm tra xem đã vào được chưa bằng cách tìm thẻ server
            print(f"🔎 Đang tìm server: {SERVER_ID}")
            
            # Logic tìm server thông minh hơn
            server_found = await page.evaluate(f"""(sid) => {{
                // Tìm tất cả các thẻ div có chứa text là ID server
                const allDivs = document.querySelectorAll('div, .server-body, .server-name');
                for (let div of allDivs) {{
                    if (div.innerText && div.innerText.includes(sid)) {{
                        // Scroll tới nó cho chắc
                        div.scrollIntoView();
                        div.click();
                        return true;
                    }}
                }}
                return false;
            }}""", SERVER_ID)

            if server_found:
                print("✅ Đã click vào Server.")
                await asyncio.sleep(10)
            else:
                # Nếu không thấy server, có thể do chưa qua được Captcha
                # Thử refresh trang 1 lần
                print("🔄 Không thấy server, thử tải lại trang...")
                await page.reload()
                await asyncio.sleep(10)
                # Thử tìm lại lần 2
                retry_found = await page.get_by_text(SERVER_ID).first.is_visible()
                if retry_found:
                    await page.get_by_text(SERVER_ID).first.click()
                else:
                    print("❌ Thất bại: Không tìm thấy server sau khi reload.")
                    await page.screenshot(path="step2_failed.png")
                    send_telegram_photo("step2_failed.png", "❌ Không tìm thấy server (Có thể kẹt Captcha)")
                    return

            # --- GIAI ĐOẠN 3: BẬT VÀ CONFIRM ---
            # Chờ trang quản lý server load
            await page.wait_for_load_state("networkidle")
            
            start_btn = page.locator("#start").first
            if await start_btn.is_visible():
                status_element = page.locator(".statuslabel-label").first
                status = "Unknown"
                if await status_element.is_visible():
                    status = (await status_element.inner_text()).strip()
                
                print(f"📊 Trạng thái Server: {status}")

                if "Offline" in status:
                    print("⚡ Phát hiện Offline. Nhấn START...")
                    await start_btn.click(force=True)
                    send_telegram_photo("step1_debug.png", f"🚀 Đã nhấn Start! (Status: {status})")
                    
                    # Vòng lặp chờ xác nhận (Confirm)
                    print("⏳ Đang canh nút Confirm...")
                    for _ in range(30): # Canh trong 5 phút (30 * 10s)
                        await asyncio.sleep(10)
                        
                        # Check nút confirm
                        confirm_btn = page.locator("#confirm").first
                        if await confirm_btn.is_visible():
                            await confirm_btn.click()
                            print("✅ Đã bấm CONFIRM!")
                            await page.screenshot(path="confirmed.png")
                            send_telegram_photo("confirmed.png", "✅ Đã xác nhận hàng chờ thành công!")
                            break
                        
                        # Check nếu server đã online
                        current_status = await page.locator(".statuslabel-label").first.inner_text()
                        if "Online" in current_status or "Loading" in current_status:
                            print("✅ Server đang chạy.")
                            break
                else:
                    print("✅ Server đã Online hoặc đang xử lý.")
            else:
                print("⚠️ Không thấy nút Start. (Có thể đang trong hàng chờ hoặc lỗi load)")
                await page.screenshot(path="no_start.png")
                send_telegram_photo("no_start.png", "⚠️ Vào được server nhưng không thấy nút Start.")

        except Exception as e:
            print(f"💥 Bot gặp lỗi: {e}")
            await page.screenshot(path="crash.png")
            send_telegram_photo("crash.png", f"💥 Bot Crash: {str(e)}")
        finally:
            await browser.close()
            print("🏁 Kết thúc quy trình.")

if __name__ == "__main__":
    asyncio.run(run_logic())
