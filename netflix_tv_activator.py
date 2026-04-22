import requests
import re
import urllib3
urllib3.disable_warnings()

TV_URL = "https://www.netflix.com/tv8"

def activate_tv_code(cookie_dict, code):
    """
    Thực hiện luồng GET lấy authURL và POST gửi mã code lên máy chủ.
    cookie_dict: Dictionary chứa NetflixId và (tuỳ chọn) SecureNetflixId
    code: Chuỗi 8 chữ số (hoặc ký tự) từ Tivi
    
    Raises:
        ValueError: Nếu cookie hỏng (không lấy được authURL), bị khoá TV, hoặc mã code sai.
        HTTPError: Lỗi mạng.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # Nạp cookies từ Database (Thường là dict có key NetflixId, SecureNetflixId...)
    cookies = {}
    if "NetflixId" in cookie_dict: cookies["NetflixId"] = cookie_dict["NetflixId"]
    elif "netflix_id" in cookie_dict: cookies["NetflixId"] = cookie_dict["netflix_id"]
        
    if "SecureNetflixId" in cookie_dict: cookies["SecureNetflixId"] = cookie_dict["SecureNetflixId"]
    elif "secure_netflix_id" in cookie_dict: cookies["SecureNetflixId"] = cookie_dict["secure_netflix_id"]

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    # ----------------------------------------------------
    # Bước 1: Trích xuất authURL (CSRF Token) từ trang /tv8
    # ----------------------------------------------------
    resp = session.get(TV_URL, timeout=15, verify=False)
    resp.raise_for_status()
    
    match = re.search(r'"authURL":"([^"]+)"', resp.text)
    if not match:
        raise ValueError(f"No authURL: Cookie chết hoặc gói cước không hỗ trợ TV.")
        
    auth_url = match.group(1)
    
    # ----------------------------------------------------
    # Bước 2: Gửi gói tin POST kích hoạt
    # ----------------------------------------------------
    post_data = {
        "authURL": auth_url,
        "tvLoginRendezvousCode": code,
        "flow": "websiteSignUp",
        "flowMode": "enterTvLoginRendezvousCode",
        "withFields": "tvLoginRendezvousCode,isTvUrl2",
        "action": "nextAction",
        "code": ""
    }
    
    post_headers = dict(headers)
    post_headers["Content-Type"] = "application/x-www-form-urlencoded"
    post_headers["Referer"] = TV_URL
    
    resp_post = session.post(TV_URL, data=post_data, headers=post_headers, timeout=15, verify=False)
    resp_post.raise_for_status()
    
    # Bước 3: Đọc phản hồi HTML để xem có lỗi về mã code không
    text_lower = resp_post.text.lower()
    
    # Danh sách các từ khoá lỗi phổ biến của Netflix khi mã sai hoặc hết hạn
    error_keywords = [
        "not valid", 
        "invalid code", 
        "mã không hợp lệ", 
        "mã đã hết hạn",
        "check the code",
        "expired"
    ]
    
    # Tuy nhiên, nếu mã đúng, nó thường tự redirect hoặc ra trang "You're all set", "Ready to watch"
    if any(keyword in text_lower for keyword in error_keywords):
        raise ValueError("Invalid TV Code: Mã code không hợp lệ hoặc đã hết hạn (chỉ có tác dụng 5 phút).")
        
    # Có 1 trường hợp là Cookie bị block tính năng đăng nhập, có thể báo error khác
    if "error" in text_lower and ("sign_in" in text_lower or "login" in text_lower):
        raise ValueError("Cookie bị từ chối tính năng TV8.")

    return True
