import os
import asyncio
import datetime
import requests
import random
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
TG_TOKEN = os.getenv("TG_TOKEN",)
TG_CHAT_ID = os.getenv("TG_CHAT_ID",)
SESSION = os.getenv("ATERNOS_SESSION",)
SERVER_ID = "qtm3k14"
URL = "https://aternos.org/servers/"

# --- KIỂM TRA STEALTH ---
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

# --- THÊM TÍNH NĂNG TỪ PHẦN DƯỚI ---
SESSION_FILE = "aternos_session.txt"
IS_GITHUB = os.getenv("GITHUB_ACTIONS") == "true"
HEADLESS = True if IS_GITHUB else False  # Tự động chọn headless

def load_auth():
    """Đọc từ Secret GitHub trước, nếu không có mới đọc file aternos_auth"""
    a_user = os.getenv("ATERNOS_USER")
    a_pass = os.getenv("ATERNOS_PASS")
    g_email = os.getenv("GOOGLE_EMAIL")
    g_pass = os.getenv("GOOGLE_PASS")
    
    if not a_user and os.path.exists("aternos_auth"):
        try:
            with open("aternos_auth", "r") as f:
                lines = f.read().strip().split("\n")
                if len(lines) >= 4:
                    return lines[0], lines[1], lines[2], lines[3]
                elif len(lines) >= 2:
                    return lines[0], lines[1], None, None
        except Exception as e:
            print(f"❌ Lỗi đọc file aternos_auth: {e}")
    return a_user, a_pass, g_email, g_pass

async def login_aternos(page, u, p, ge, gp):
    """Đăng nhập tự động từ phần dưới"""
    print("🔐 Đang tiến hành đăng nhập tự động...")
    try:
        await page.goto("https://aternos.org/go/", wait_until="networkidle")
        
        # Nếu dùng Google
        if ge and gp:
            print("🌐 Dùng Google Login...")
            google_btn = page.locator('button:has-text("Google"), a:has-text("Google"), .btn-google').first
            if await google_btn.is_visible(timeout=5000):
                await google_btn.click()
                async with page.expect_popup() as popup_info:
                    popup = await popup_info.value
                    await popup.fill('input[type="email"]', ge)
                    await popup.click('#identifierNext')
                    await asyncio.sleep(2)
                    await popup.fill('input[type="password"]', gp)
                    await popup.click('#passwordNext')
                    await asyncio.sleep(2)
                    # Xử lý 2FA nếu có
                    if await popup.locator('button:has-text("Continue")').is_visible(timeout=5000):
                        await popup.click('button:has-text("Continue")')
                await page.wait_for_load_state("networkidle")
            else:
                print("⚠️ Không tìm thấy nút Google.")
                return False
        # Nếu dùng Aternos trực tiếp
        elif u and p:
            print("🔑 Dùng Aternos Account...")
            await page.fill('#user', u)
            await page.fill('#password', p)
            await page.click('#login')
            await page.wait_for_load_state("networkidle")
        
        # Lưu Session mới
        cookies = await page.context.cookies()
        session = next((c for c in cookies if c['name'] == 'ATERNOS_SESSION'), None)
        if session:
            with open(SESSION_FILE, "w") as f: f.write(session['value'])
            print("💾 Session mới đã được lưu.")
        return True
    except Exception as e:
        print(f"❌ Lỗi Login: {e}")
        return False

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
    """Vòng lặp giải Captcha với handle frame detach và tăng attempt"""
    print("🛡️ Đang quét Cloudflare Turnstile...")
    
    for attempt in range(1, 11):  # Tăng lên 10 attempt (khoảng 5-7 phút)
        print(f"🔄 Nỗ lực vượt Captcha lần {attempt}...")
        
        try:
            # Chờ frame xuất hiện (tăng delay)
            await asyncio.sleep(15)  # Tăng lên 15s
            
            # Giả lập hành vi người dùng để tránh phát hiện
            await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await page.evaluate("window.scrollBy(0, 100);")  # Scroll nhẹ
            
            # Tìm tất cả các frame để săn lùng Turnstile
            captcha_clicked = False
            for frame in page.frames:
                try:
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
                except Exception as e:
                    if "detached" in str(e).lower():
                        print(f"⚠️ Frame detached trong attempt {attempt}, retry...")
                        continue  # Retry attempt này
                    else:
                        raise  # Re-raise nếu lỗi khác
            
            if not captcha_clicked:
                # Fallback nếu không tìm thấy frame cụ thể, click tọa độ ước lượng
                print("⚠️ Không tìm thấy Frame cụ thể, thử click tọa độ dự phòng...")
                await page.mouse.click(180, 175)

            # Kiểm tra xem đã vào được trang server chưa
            await asyncio.sleep(20)  # Tăng lên 20s
            try:
                if await page.locator(".server-name").filter(has_text=SERVER_ID).is_visible(timeout=3000):
                    print("✅ Đã vượt qua Captcha thành công!")
                    return True
            except Exception as e:
                print(f"⚠️ Lỗi kiểm tra server: {e}. Tiếp tục...")
        
        except Exception as e:
            print(f"⚠️ Lỗi trong attempt {attempt}: {e}. Tiếp tục...")
        
        # Nếu sau 5 lần vẫn kẹt, thử reload trang
        if attempt == 5:
            print("🔄 Vẫn kẹt Captcha, đang tải lại trang...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"⚠️ Lỗi reload: {e}")
            
    return False

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ])
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()
        page.set_default_timeout(120000)  # 2 phút
        
        if HAS_STEALTH:
            await stealth_async(page)
            print("🕵️ Stealth Mode: Activated")

        # Nạp Session từ file hoặc env
        session_val = None
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, "r") as f: session_val = f.read().strip()
            except Exception as e:
                print(f"❌ Lỗi đọc session file: {e}")
        
        if session_val:
            try:
                await context.add_cookies([{"name": "ATERNOS_SESSION", "value": session_val, "domain": ".aternos.org", "path": "/", "secure": True}])
                print("✅ Đã add cookie session.")
            except Exception as e:
                print(f"⚠️ Lỗi add cookie: {e}. Xóa file session và thử lại.")
                if os.path.exists(SESSION_FILE):
                    os.remove(SESSION_FILE)
                return
        elif SESSION:
            await context.add_cookies([{"name": "ATERNOS_SESSION", "value": SESSION, "domain": ".aternos.org", "path": "/", "secure": True}])

        try:
            print("🚀 Đang truy cập Aternos...")
            await page.goto(URL, wait_until="domcontentloaded", timeout=120000)
            
            # Bắt đầu giải Captcha
            success = await solve_cloudflare(page)
            await page.screenshot(path="status_after_captcha.png")
            
            if not success:
                # Fallback: Login tự động nếu captcha fail
                print("❌ Captcha fail, thử login tự động để bypass...")
                u, p, ge, gp = load_auth()
                if await login_aternos(page, u, p, ge, gp):
                    success = await solve_cloudflare(page)  # Retry captcha sau login
            
            if success:
                # Kiểm tra xem có vào được server chưa, nếu không thì Login
                server_list = page.locator(".server-name").filter(has_text=SERVER_ID)
                if not await server_list.is_visible(timeout=5000):
                    u, p, ge, gp = load_auth()
                    if await login_aternos(page, u, p, ge, gp):
                        await solve_cloudflare(page)
                
                # Tìm và vào Server
                server = page.locator(".server-name").filter(has_text=SERVER_ID).first
                await server.click()
                print("➡️ Đang vào Server...")
                await asyncio.sleep(10)
                
                # Xử lý các thông báo che khuất
                await page.mouse.click(10, 10)
                
                # Kiểm tra nút Start
                start_btn = page.locator("#start").first
                if await start_btn.is_visible():
                    status = (await page.locator(".statuslabel-label").inner_text()).strip()
                    print(f"📊 Trạng thái: {status}")
                    
                    if "Offline" in status:
                        await start_btn.click()
                        print("⚡ Đã nhấn START!")
                        send_tg(f"🚀 Server {SERVER_ID} đã được kích hoạt!", "status_after_captcha.png")
                        
                        # Chờ nút Confirm hàng chờ
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
                send_tg("❌ Thất bại: Bot không thể vượt qua Captcha sau nhiều lần thử. Khuyến nghị chạy thủ công.", "status_after_captcha.png")
                
        except Exception as e:
            print(f"💥 Lỗi: {e}")
            await page.screenshot(path="crash_debug.png")
            send_tg(f"💥 Bot gặp lỗi: {str(e)}", "crash_debug.png")
        finally:
            await browser.close()
            print("🏁 Kết thúc quy trình.")

if __name__ == "__main__":
    asyncio.run(run())
