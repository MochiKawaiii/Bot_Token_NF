"""
Netflix TV Activator - Remote Chrome via Browserless.io (V2 - Playwright)
Chrome chạy trên cloud Browserless.io, Bot chỉ gửi lệnh qua mạng.
RAM trên Render gần như bằng 0.
"""
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import netflix_account_scraper as account_scraper

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")
TV_URL = "https://www.netflix.com/tv8"

# Browserless V2 endpoint (WebSocket)
BROWSERLESS_WS = f"wss://production-sfo.browserless.io/chrome/playwright?token={BROWSERLESS_TOKEN}"


def activate_tv_code(cookie_dict, code):
    """
    Kết nối tới Chrome remote trên Browserless.io để kích hoạt TV.
    Raises ValueError nếu cookie chết hoặc mã sai.
    Raises Exception nếu lỗi mạng.
    """
    # Chỉ giữ lại chữ số, bỏ dấu - và ký tự khác
    code = ''.join(c for c in str(code) if c.isdigit())
    if len(code) != 8:
        raise ValueError(f"TV code must be exactly 8 digits, got {len(code)}: '{code}'")
    if not BROWSERLESS_TOKEN:
        raise Exception("BROWSERLESS_TOKEN is not configured!")
    
    with sync_playwright() as pw:
        browser = None
        try:
            # === Kết nối tới Chrome remote (Browserless V2) ===
            browser = pw.chromium.connect(BROWSERLESS_WS)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 800, "height": 600}
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            
            # === Bước 1: Set cookie Netflix ===
            nf_id = cookie_dict.get("NetflixId") or cookie_dict.get("netflix_id", "")
            sec_id = cookie_dict.get("SecureNetflixId") or cookie_dict.get("secure_netflix_id", "")
            
            cookies_to_add = []
            if nf_id:
                cookies_to_add.append({"name": "NetflixId", "value": nf_id, "domain": ".netflix.com", "path": "/"})
            if sec_id:
                cookies_to_add.append({"name": "SecureNetflixId", "value": sec_id, "domain": ".netflix.com", "path": "/"})
            
            if cookies_to_add:
                context.add_cookies(cookies_to_add)

            # === Bước 1.5: Kiểm tra On-Hold / Dead TRƯỚC khi kích hoạt TV ===
            # Tài khoản on-hold vẫn có thể "link" được thiết bị TV nhưng không xem
            # được, nên cần bỏ qua và để bot tự chuyển sang cookie khác.
            # Dùng chung logic phát hiện với luồng /get_token (không phụ thuộc ngôn ngữ).
            try:
                hold_status = account_scraper.get_account_hold_status(page)
            except Exception:
                # Nếu bước check lỗi (mạng/timeout), cứ thử kích hoạt như cũ.
                hold_status = "active"
            if hold_status == "on_hold":
                raise ValueError("Account is on-hold (payment failure), switching account.")
            if hold_status == "dead":
                raise ValueError("Cookie is dead, switching account.")

            # === Bước 2: Vào trang TV8 ===
            page.goto(TV_URL, wait_until="domcontentloaded")
            
            # Chờ ô nhập mã xuất hiện
            try:
                page.wait_for_selector('input[data-uia="pin-number-0"]', timeout=20000)
            except PlaywrightTimeoutError:
                url = page.url.lower()
                if "login" in url:
                    raise ValueError("Cookie expired or plan does not support TV.")
                raise ValueError("Cannot load TV8 page, cookie may have expired.")
            
            # === Bước 3: Nhập từng chữ số ===
            for i, digit in enumerate(code):
                try:
                    pin = page.wait_for_selector(f'input[data-uia="pin-number-{i}"]', timeout=5000)
                    pin.fill("")
                    pin.type(digit, delay=50)
                    page.wait_for_timeout(150)
                except Exception:
                    raise Exception(f"Cannot enter digit {i+1}")
            
            # === Bước 4: Bấm Submit ===
            page.wait_for_timeout(500)
            try:
                btn = page.wait_for_selector('button[data-uia="witcher-code-submit"]', timeout=5000)
                btn.click()
            except PlaywrightTimeoutError:
                raise ValueError("Invalid TV Code: Submit button not clickable.")
            
            # === Bước 5: Chờ kết quả ===
            page.wait_for_timeout(6000)
            
            # Kiểm tra lỗi hiển thị
            err_el = page.query_selector('div[data-uia="witcher-code-input-error"]')
            if err_el:
                err_text = err_el.inner_text().strip()
                if err_text:
                    raise ValueError(f"Invalid TV Code: {err_text}")
            
            url = page.url.lower()
            
            # Thành công: redirect sang success/browse
            if "success" in url or "browse" in url or "tv/out" in url:
                return True
            
            # Bị redirect về login
            if "login" in url and "/tv" not in url:
                raise ValueError("Cookie rejected for TV feature.")
            
            # Form vẫn còn → mã sai
            form_el = page.query_selector('input[data-uia="pin-number-0"]')
            if form_el:
                raise ValueError("Invalid TV Code: Code is invalid or expired (5 min limit).")
            
            # Form biến mất → thành công!
            return True
        
        finally:
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
