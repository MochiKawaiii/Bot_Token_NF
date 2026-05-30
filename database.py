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
    cookie_total = cookies_col.count_documents({})
    cookie_alive = cookies_col.count_documents({"is_alive": True})
    
    # Tính tổng số link đã phát từ trước đến nay
    pipeline = [{"$group": {"_id": None, "total_generated": {"$sum": "$times_used"}}}]
    res = list(cookies_col.aggregate(pipeline))
    total_generated = res[0]["total_generated"] if len(res) > 0 else 0
    
    # Thống kê lượng User
    users_col = db.users
    users_total = users_col.count_documents({})
    
    # Số users có hoạt động điểm danh hoặc lấy link hôm nay
    today = get_vietnam_date()
    active_today = users_col.count_documents({
        "$or": [
            {"last_usage_date": today, "usage_today": {"$gt": 0}},
            {"last_checkin_date": today}
        ]
    })
    
    # Thống kê chi tiết: bao nhiêu lượt token vs TV hôm nay
    token_pipeline = [{"$match": {"last_usage_date": today}}, {"$group": {"_id": None, "total": {"$sum": "$token_today"}}}]
    tv_pipeline = [{"$match": {"last_usage_date": today}}, {"$group": {"_id": None, "total": {"$sum": "$tv_today"}}}]
    
    token_res = list(users_col.aggregate(token_pipeline))
    tv_res = list(users_col.aggregate(tv_pipeline))
    
    token_uses_today = token_res[0]["total"] if len(token_res) > 0 else 0
    tv_uses_today = tv_res[0]["total"] if len(tv_res) > 0 else 0
    
    return {
        "cookie_total": cookie_total, 
        "cookie_alive": cookie_alive,
        "users_total": users_total,
        "users_active_today": active_today,
        "total_generated": total_generated,
        "token_uses_today": token_uses_today,
        "tv_uses_today": tv_uses_today
    }

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
            "last_usage_date": "",
            "total_usage": 0,
            "referral_count": 0,
            "referred_by": None,
            "created_at": get_vietnam_date()
        }
        users_col.insert_one(user)
    else:
        # Tự động cập nhật các trường còn thiếu nếu có (Self-healing DB)
        updated = False
        updates = {}
        defaults = {
            "streak": 0,
            "last_checkin_date": "",
            "usage_today": 0,
            "token_today": 0,
            "tv_today": 0,
            "last_usage_date": "",
            "total_usage": 0,
            "referral_count": 0,
            "referred_by": None,
            "created_at": "N/A"
        }
        for key, val in defaults.items():
            if key not in user:
                user[key] = val
                updates[key] = val
                updated = True
        if updated:
            users_col.update_one({"user_id": user_id}, {"$set": updates})
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
    Kiểm tra quota. Tính cả bonus từ referral.
    Trả về bộ 3: (Can_generate_boolean, remain_quota, total_limit)
    """
    user = get_user(user_id, username)
    today = get_vietnam_date()
    db = get_db()
    
    # Kiểm tra Reset lượt trong ngày
    if user.get("last_usage_date") != today:
        db.users.update_one(
            {"user_id": user_id},
            {"$set": {"usage_today": 0, "token_today": 0, "tv_today": 0, "last_usage_date": today}}
        )
        usage = 0
    else:
        usage = user.get("usage_today", 0)
        
    streak = user.get("streak", 0)
    referral_count = user.get("referral_count", 0)
    
    # Tính hạn mức tối đa: base 5
    limit = 5
    
    # Bonus từ referral: 1 ref = +1, 3+ ref = +2
    if referral_count >= 3:
        limit += 2
    elif referral_count >= 1:
        limit += 1
        
    if usage < limit:
        return True, limit - usage, limit
    return False, 0, limit

def increment_link_usage(user_id, usage_type="token"):
    """Cộng 1 vào lượt sử dụng link của hôm nay + tổng all-time.
    usage_type: 'token' hoặc 'tv'
    """
    db = get_db()
    today = get_vietnam_date()
    inc_fields = {"usage_today": 1, "total_usage": 1}
    if usage_type == "tv":
        inc_fields["tv_today"] = 1
    else:
        inc_fields["token_today"] = 1
    db.users.update_one(
        {"user_id": user_id},
        {
            "$inc": inc_fields,
            "$set": {"last_usage_date": today}
        }
    )

def get_profile(user_id, username=""):
    """Lấy thông tin profile đầy đủ cho /profile"""
    user = get_user(user_id, username)
    today = get_vietnam_date()
    
    # Reset usage nếu qua ngày
    if user.get("last_usage_date") != today:
        usage_today = 0
    else:
        usage_today = user.get("usage_today", 0)
    
    ref_count = user.get("referral_count", 0)
    
    # Tính limit
    limit = 5
    if ref_count >= 3:
        limit += 2
    elif ref_count >= 1:
        limit += 1
    
    return {
        "user_id": user_id,
        "username": user.get("username", username),
        "streak": user.get("streak", 0),
        "usage_today": usage_today,
        "limit": limit,
        "remain": max(0, limit - usage_today),
        "total_usage": user.get("total_usage", 0),
        "referral_count": ref_count,
        "created_at": user.get("created_at", "N/A")
    }

# --- Referral System ---
def get_referral_count(user_id):
    """Lấy số người đã mời thành công"""
    user = get_user(user_id)
    return user.get("referral_count", 0)

def process_referral(new_user_id, referrer_id, username=""):
    """
    Xử lý khi user mới join qua referral link.
    Trả về: True nếu thành công, False nếu đã tồn tại hoặc tự mời mình.
    """
    if new_user_id == referrer_id:
        return False  # Không tự mời mình
    
    db = get_db()
    user = db.users.find_one({"user_id": new_user_id})
    
    # User đã tồn tại trong DB → không tính ref
    if user:
        return False
    
    # Tạo user mới với referred_by
    db.users.insert_one({
        "user_id": new_user_id,
        "username": username,
        "streak": 0,
        "last_checkin_date": "",
        "usage_today": 0,
        "last_usage_date": "",
        "total_usage": 0,
        "referral_count": 0,
        "referred_by": referrer_id,
        "created_at": get_vietnam_date()
    })
    
    # +1 referral_count cho người mời
    db.users.update_one(
        {"user_id": referrer_id},
        {"$inc": {"referral_count": 1}}
    )
    
    return True

# --- Language Preference ---
def get_user_lang(user_id):
    """Lấy ngôn ngữ đã chọn của user. Trả về None nếu chưa chọn."""
    db = get_db()
    user = db.users.find_one({"user_id": user_id}, {"lang": 1})
    if user:
        return user.get("lang")  # "vi", "en", or None
    return None

def set_user_lang(user_id, lang_code, username=""):
    """Lưu ngôn ngữ cho user. Tạo user mới nếu chưa tồn tại."""
    db = get_db()
    db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {"lang": lang_code, "username": username},
            "$setOnInsert": {
                "streak": 0,
                "last_checkin_date": "",
                "usage_today": 0,
                "last_usage_date": "",
                "total_usage": 0,
                "referral_count": 0,
                "referred_by": None,
                "created_at": get_vietnam_date()
            }
        },
        upsert=True
    )

# --- Bot Settings (Tutorial Video, etc.) ---
def get_tutorial_video():
    """Lấy file_id của video hướng dẫn. Trả về None nếu chưa set."""
    db = get_db()
    setting = db.settings.find_one({"key": "tutorial_video"})
    if setting:
        return setting.get("file_id")
    return None

def set_tutorial_video(file_id):
    """Lưu file_id của video hướng dẫn."""
    db = get_db()
    db.settings.update_one(
        {"key": "tutorial_video"},
        {"$set": {"file_id": file_id}},
        upsert=True
    )
