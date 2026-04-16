from pymongo import MongoClient
import os
import datetime
import pytz

_db_client = None

def get_db():
    global _db_client
    if _db_client is None:
        mongo_uri = os.environ.get("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable is not set")
        _db_client = MongoClient(mongo_uri)
    # Using 'netflix_bot' database
    return _db_client.netflix_bot

def get_vietnam_date():
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    return datetime.datetime.now(tz).strftime('%Y-%m-%d')

# --- Cookies Management ---
def insert_cookie(netflix_id, full_cookie_dict, source_file=""):
    """Thêm một cookie mới vào DB nếu chưa tồn tại"""
    db = get_db()
    cookies_col = db.cookies
    if cookies_col.count_documents({"netflix_id": netflix_id}) == 0:
        cookies_col.insert_one({
            "netflix_id": netflix_id,
            "cookie_data": full_cookie_dict,
            "source": source_file,
            "is_alive": True,
            "times_used": 0
        })
        return True
    return False

def get_active_cookie():
    """Lấy 1 cookie còn sống (is_alive=True), ưu tiên những cookie ít được sử dụng nhất"""
    db = get_db()
    cookies_col = db.cookies
    cookie = cookies_col.find_one({"is_alive": True}, sort=[("times_used", 1)])
    
    if cookie:
        # Cập nhật số lần sử dụng
        cookies_col.update_one(
            {"_id": cookie["_id"]},
            {"$inc": {"times_used": 1}}
        )
        return cookie
    return None

def mark_cookie_as_dead(netflix_id):
    """Đánh dấu một cookie là đã chết"""
    db = get_db()
    cookies_col = db.cookies
    cookies_col.update_one(
        {"netflix_id": netflix_id},
        {"$set": {"is_alive": False}}
    )

def count_stats():
    """Lấy thống kê DB"""
    db = get_db()
    cookies_col = db.cookies
    total = cookies_col.count_documents({})
    alive = cookies_col.count_documents({"is_alive": True})
    return {"total": total, "alive": alive}

def clear_all_cookies():
    """Xóa toàn bộ cookies (chỉ dùng bởi admin)"""
    db = get_db()
    cookies_col = db.cookies
    return cookies_col.delete_many({}).deleted_count

# --- User Quota Management ---
def get_user(user_id, username=""):
    """Truy xuất hoặc khởi tạo 1 user trong Collection users"""
    db = get_db()
    users_col = db.users
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "username": username,
            "streak": 0,
            "last_checkin_date": "",
            "usage_today": 0,
            "last_usage_date": ""
        }
        users_col.insert_one(user)
    return user

def check_in_user(user_id, username=""):
    """Điểm danh User, nếu reset qua ngày sẽ được update. Streak = Số ngày."""
    user = get_user(user_id, username)
    today = get_vietnam_date()
    
    if user.get("last_checkin_date") == today:
        # Hôm nay đã điểm danh rồi
        return False, user.get("streak", 0) 
        
    db = get_db()
    new_streak = user.get("streak", 0) + 1
    db.users.update_one(
        {"user_id": user_id},
        {"$set": {"last_checkin_date": today, "streak": new_streak, "username": username}}
    )
    return True, new_streak

def can_generate_link(user_id, username=""):
    """
    Kéo thông tin ra và kiểm tra logic 1-2-3.
    Trả về bộ 3 tham số: (Can_generate_boolean, remain_quota, total_limit)
    """
    user = get_user(user_id, username)
    today = get_vietnam_date()
    db = get_db()
    
    # Kiểm tra Reset lượt trong ngày
    if user.get("last_usage_date") != today:
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"usage_today": 0, "last_usage_date": today}}
        )
        usage = 0
    else:
        usage = user.get("usage_today", 0)
        
    streak = user.get("streak", 0)
    
    # Tính hạn mức tối đa
    limit = 1
    if streak >= 3:
        limit = 2
    if streak >= 7:
        limit = 3
        
    if usage < limit:
        return True, limit - usage, limit
    return False, 0, limit

def increment_link_usage(user_id):
    """Cộng 1 vào lượt sử dụng link của hôm nay"""
    db = get_db()
    today = get_vietnam_date()
    db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": {"usage_today": 1},
            "$set": {"last_usage_date": today}
        }
    )
