"""
Netflix TV Activator - Requests Version (Lightweight)
Gửi POST request trực tiếp lên Netflix /tv8 endpoint.
"""
import requests
import re
import urllib3
urllib3.disable_warnings()

TV_URL = "https://www.netflix.com/tv8"

def activate_tv_code(cookie_dict, code):
    """
    Thực hiện luồng GET lấy authURL và POST gửi mã code lên máy chủ.
    cookie_dict: Dictionary chứa NetflixId và (tuỳ chọn) SecureNetflixId
    code: Chuỗi 8 chữ số từ Tivi
    
    Raises:
        ValueError: Nếu cookie hỏng hoặc mã code sai.
        Exception: Lỗi mạng.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    # Nạp cookies
    cookies = {}
    if "NetflixId" in cookie_dict: cookies["NetflixId"] = cookie_dict["NetflixId"]
    elif "netflix_id" in cookie_dict: cookies["NetflixId"] = cookie_dict["netflix_id"]
        
    if "SecureNetflixId" in cookie_dict: cookies["SecureNetflixId"] = cookie_dict["SecureNetflixId"]
    elif "secure_netflix_id" in cookie_dict: cookies["SecureNetflixId"] = cookie_dict["secure_netflix_id"]

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    # Bước 1: Trích xuất authURL từ trang /tv8
    resp = session.get(TV_URL, timeout=15, verify=False)
    resp.raise_for_status()
    
    match = re.search(r'"authURL":"([^"]+)"', resp.text)
    if not match:
        raise ValueError("No authURL: Cookie chết hoặc gói cước không hỗ trợ TV.")
        
    auth_url = match.group(1)
    
    # Kiểm tra xem cookie có đăng nhập thành công không (membershipStatus != ANONYMOUS)
    if '"membershipStatus":"ANONYMOUS"' in resp.text:
        raise ValueError("No authURL: Cookie chết, Netflix không nhận dạng được tài khoản.")
    
    # Bước 2: Gửi POST kích hoạt
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
    post_headers["Origin"] = "https://www.netflix.com"
    
    resp_post = session.post(TV_URL, data=post_data, headers=post_headers, 
                              timeout=15, verify=False, allow_redirects=True)
    resp_post.raise_for_status()
    
    # Bước 3: Phân tích kết quả
    final_url = resp_post.url.lower()
    body = resp_post.text
    
    # Thành công: Netflix redirect sang /tv/out/success hoặc /browse
    if "success" in final_url or "browse" in final_url or "tv/out" in final_url:
        return True
    
    # Nếu bị redirect về login → Cookie chết
    if "/login" in final_url and "/tv" not in final_url:
        raise ValueError("Cookie bị từ chối tính năng TV8.")
    
    # Kiểm tra lỗi trong JavaScript response
    if '"error_code_entry_failed"' in body or "wasn't right" in body.lower() or "not right" in body.lower():
        raise ValueError("Invalid TV Code: Mã code không đúng. Hãy thử lại.")
    
    # Nếu trang vẫn còn form nhập mã → mã chưa được xử lý hoặc sai
    if 'data-uia="witcher-code-title"' in body or 'tvsignup-title' in body:
        # Kiểm tra xem có thông báo lỗi cụ thể không
        error_match = re.search(r'data-uia="witcher-code-input-error"[^>]*>([^<]+)', body)
        if error_match and error_match.group(1).strip():
            raise ValueError(f"Invalid TV Code: {error_match.group(1).strip()}")
        raise ValueError("Invalid TV Code: Mã code không hợp lệ hoặc đã hết hạn (chỉ có tác dụng 5 phút).")
    
    # Nếu trang đã thay đổi hoàn toàn (form biến mất) → Có thể thành công
    return True
