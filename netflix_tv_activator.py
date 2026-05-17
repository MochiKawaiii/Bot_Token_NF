"""
Netflix TV Activator - Selenium Version
Dùng trình duyệt headless thật sự để kích hoạt mã TV 8 chữ số.
"""
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

TV_URL = "https://www.netflix.com/tv8"

def _create_driver(cookie_dict):
    """Tạo một phiên trình duyệt headless Chrome với cookie đã nạp."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    
    # Trên Render (Linux), Chrome được cài sẵn qua render-build.sh
    # Trên local (Windows), dùng webdriver-manager tự tải
    chrome_bin = os.environ.get("CHROME_BIN")
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    
    if chrome_bin:
        chrome_options.binary_location = chrome_bin
    
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
    else:
        # Trên Local/Windows: tự tìm chromedriver
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
        except Exception:
            service = Service()  # Dùng chromedriver trong PATH
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Nạp trang Netflix trước để set domain cookie
    driver.get("https://www.netflix.com")
    time.sleep(1)
    
    # Inject cookies vào trình duyệt
    netflix_id = cookie_dict.get("NetflixId") or cookie_dict.get("netflix_id", "")
    secure_id = cookie_dict.get("SecureNetflixId") or cookie_dict.get("secure_netflix_id", "")
    
    if netflix_id:
        driver.add_cookie({"name": "NetflixId", "value": netflix_id, "domain": ".netflix.com", "path": "/"})
    if secure_id:
        driver.add_cookie({"name": "SecureNetflixId", "value": secure_id, "domain": ".netflix.com", "path": "/"})
    
    return driver


def activate_tv_code(cookie_dict, code):
    """
    Dùng Selenium headless để mô phỏng việc nhập mã TV trên netflix.com/tv8.
    
    Raises:
        ValueError: Nếu cookie hỏng, mã code sai, hoặc TV không được hỗ trợ.
        Exception: Lỗi mạng / trình duyệt.
    """
    driver = None
    try:
        driver = _create_driver(cookie_dict)
        
        # =============================================
        # Bước 1: Truy cập trang /tv8
        # =============================================
        driver.get(TV_URL)
        
        # Chờ trang tải xong (chờ ô nhập mã đầu tiên xuất hiện)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-uia="pin-number-0"]'))
            )
        except TimeoutException:
            # Trang không hiện form nhập mã -> Cookie chết hoặc bị redirect login
            current_url = driver.current_url.lower()
            if "login" in current_url:
                raise ValueError("No authURL: Cookie chết hoặc gói cước không hỗ trợ TV.")
            raise ValueError("No authURL: Không thể tải trang TV8, cookie có thể đã hết hạn.")
        
        # =============================================
        # Bước 2: Nhập từng chữ số vào 8 ô input
        # =============================================
        for i, digit in enumerate(code):
            pin_input = driver.find_element(By.CSS_SELECTOR, f'input[data-uia="pin-number-{i}"]')
            pin_input.clear()
            pin_input.send_keys(digit)
            time.sleep(0.1)  # Delay nhỏ cho tự nhiên
        
        # =============================================
        # Bước 3: Chờ nút Submit kích hoạt rồi bấm
        # =============================================
        time.sleep(0.5)
        
        # Chờ nút không còn disabled
        try:
            submit_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-uia="witcher-code-submit"]'))
            )
            submit_btn.click()
        except TimeoutException:
            # Nút vẫn disabled → mã chưa đủ 8 ký tự hoặc có lỗi
            raise ValueError("Invalid TV Code: Mã code không hợp lệ, nút xác nhận không kích hoạt được.")
        
        # =============================================
        # Bước 4: Chờ kết quả (trang chuyển hướng hoặc hiện lỗi)
        # =============================================
        time.sleep(4)  # Chờ Netflix xử lý
        
        # Kiểm tra lỗi hiển thị trên trang
        try:
            error_box = driver.find_element(By.CSS_SELECTOR, 'div[data-uia="witcher-code-input-error"]')
            error_text = error_box.text.strip()
            if error_text:
                raise ValueError(f"Invalid TV Code: {error_text}")
        except NoSuchElementException:
            pass  # Không có error box → có thể thành công
        
        # Kiểm tra xem trang đã chuyển đi chưa
        current_url = driver.current_url.lower()
        page_source = driver.page_source
        
        # Nếu vẫn còn ở trang witcher-code (form nhập mã) → Thất bại
        if 'data-uia="witcher-code-title"' in page_source and 'tvsignup-title' in page_source:
            # Trang chưa chuyển, nhưng không có lỗi rõ ràng → có thể mã sai hoặc cookie yếu
            raise ValueError("Invalid TV Code: Mã code không hợp lệ hoặc đã hết hạn (chỉ có tác dụng 5 phút).")
        
        # Nếu bị redirect về login → Cookie chết
        if "login" in current_url and "/tv" not in current_url:
            raise ValueError("Cookie bị từ chối tính năng TV8.")
        
        # Nếu URL chuyển sang trang thành công (/tv/out/success hoặc /browse)
        if "success" in current_url or "browse" in current_url or "tv/out" in current_url:
            return True
        
        # Nếu form đã biến mất (trang đã chuyển sang nội dung khác) → Thành công
        try:
            driver.find_element(By.CSS_SELECTOR, 'input[data-uia="pin-number-0"]')
            # Vẫn còn form → Không rõ kết quả, coi như lỗi mã
            raise ValueError("Invalid TV Code: Mã code không hợp lệ hoặc đã hết hạn (chỉ có tác dụng 5 phút).")
        except NoSuchElementException:
            # Form đã biến mất → Trang đã chuyển → Thành công!
            return True
    
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
