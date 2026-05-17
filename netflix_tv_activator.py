"""
Netflix TV Activator - Remote Chrome via Browserless.io
Chrome chạy trên cloud Browserless.io, Bot chỉ gửi lệnh qua mạng.
RAM trên Render gần như bằng 0.
"""
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BROWSERLESS_TOKEN = os.environ.get("BROWSERLESS_TOKEN", "")
TV_URL = "https://www.netflix.com/tv8"


def activate_tv_code(cookie_dict, code):
    """
    Kết nối tới Chrome remote trên Browserless.io để kích hoạt TV.
    Raises ValueError nếu cookie chết hoặc mã sai.
    Raises Exception nếu lỗi mạng.
    """
    if not BROWSERLESS_TOKEN:
        raise Exception("BROWSERLESS_TOKEN chưa được cấu hình!")
    
    driver = None
    try:
        # === Kết nối tới Chrome remote ===
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--disable-extensions")
        opts.add_argument("--window-size=800,600")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        
        # Tắt hình ảnh để nhanh hơn
        prefs = {"profile.managed_default_content_settings.images": 2}
        opts.add_experimental_option("prefs", prefs)
        
        # Truyền API token qua capability (cách đúng của Browserless.io)
        opts.set_capability("browserless:token", BROWSERLESS_TOKEN)
        
        # Kết nối tới Browserless.io (Chrome chạy trên cloud của họ)
        driver = webdriver.Remote(
            command_executor="https://chrome.browserless.io/webdriver",
            options=opts
        )
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(15)
        
        # === Bước 1: Set cookie Netflix ===
        driver.get("https://www.netflix.com/browse")
        time.sleep(2)
        
        nf_id = cookie_dict.get("NetflixId") or cookie_dict.get("netflix_id", "")
        sec_id = cookie_dict.get("SecureNetflixId") or cookie_dict.get("secure_netflix_id", "")
        
        if nf_id:
            driver.add_cookie({"name": "NetflixId", "value": nf_id, "domain": ".netflix.com", "path": "/"})
        if sec_id:
            driver.add_cookie({"name": "SecureNetflixId", "value": sec_id, "domain": ".netflix.com", "path": "/"})
        
        # === Bước 2: Vào trang TV8 ===
        driver.get(TV_URL)
        
        # Chờ ô nhập mã xuất hiện
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-uia="pin-number-0"]'))
            )
        except TimeoutException:
            url = driver.current_url.lower()
            if "login" in url:
                raise ValueError("Cookie chết hoặc gói cước không hỗ trợ TV.")
            raise ValueError("Không thể tải trang TV8, cookie có thể đã hết hạn.")
        
        # === Bước 3: Nhập từng chữ số ===
        for i, digit in enumerate(code):
            try:
                pin = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, f'input[data-uia="pin-number-{i}"]'))
                )
                pin.clear()
                pin.send_keys(digit)
                time.sleep(0.15)
            except Exception:
                raise Exception(f"Không thể nhập chữ số thứ {i+1}")
        
        # === Bước 4: Bấm Submit ===
        time.sleep(0.5)
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-uia="witcher-code-submit"]'))
            )
            btn.click()
        except TimeoutException:
            raise ValueError("Invalid TV Code: Nút xác nhận không kích hoạt được.")
        
        # === Bước 5: Chờ kết quả ===
        time.sleep(6)
        
        # Kiểm tra lỗi hiển thị
        try:
            err = driver.find_element(By.CSS_SELECTOR, 'div[data-uia="witcher-code-input-error"]')
            if err.text.strip():
                raise ValueError(f"Invalid TV Code: {err.text.strip()}")
        except NoSuchElementException:
            pass
        
        url = driver.current_url.lower()
        
        # Thành công: redirect sang success/browse
        if "success" in url or "browse" in url or "tv/out" in url:
            return True
        
        # Bị redirect về login
        if "login" in url and "/tv" not in url:
            raise ValueError("Cookie bị từ chối tính năng TV.")
        
        # Form vẫn còn → mã sai
        try:
            driver.find_element(By.CSS_SELECTOR, 'input[data-uia="pin-number-0"]')
            raise ValueError("Invalid TV Code: Mã code không hợp lệ hoặc đã hết hạn (5 phút).")
        except NoSuchElementException:
            # Form biến mất → thành công!
            return True
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
