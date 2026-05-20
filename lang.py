"""
Multi-language support for Netflix Token Bot.
Keys: vi (Vietnamese), en (English)
"""

TEXTS = {
    "vi": {
        # === Language Selection ===
        "choose_language": "🌐 Vui lòng chọn ngôn ngữ:\nPlease choose your language:",
        "lang_set_vi": "✅ Ngôn ngữ đã được đặt thành: *Tiếng Việt* 🇻🇳",
        "lang_set_en": "✅ Ngôn ngữ đã được đặt thành: *English* 🇬🇧",
        "btn_vi": "🇻🇳 Tiếng Việt",
        "btn_en": "🇬🇧 English",

        # === /start - /help ===
        "welcome_admin": (
            "👑 *Xin chào CHỦ NHÂN (ADMIN)!*\n\n"
            "Các lệnh hệ thống của bạn:\n"
            "🔗 `/get_token` - Rút 1 cookie sinh Link xem Netflix.\n"
            "📺 `/tv <mã 8 số>` - Kích hoạt đăng nhập trực tiếp trên TV.\n"
            "📊 `/stats` - Xem số lượng cookie dự trữ trong DB.\n"
            "🗓 `/diemdanh` - Điểm danh ngày mới.\n"
            "🌐 `/language` - Đổi ngôn ngữ.\n"
            "📝 Nhận dạng trực tiếp: Bạn có thể đưa file `cookie` (.txt, .json) vào trực tiếp đây để nạp.\n"
            "🗑 `/clear_cookies` - Xoá toàn bộ Database Cookie.\n"
        ),
        "welcome_user": (
            "🎬 *Netflix Token Extractor Bot*\n\n"
            "Lệnh cung cấp:\n"
            "🔗 `/get_token` - Rút 1 cookie sinh Link xem Netflix.\n"
            "📺 `/tv <mã 8 số>` - Kích hoạt đăng nhập trực tiếp trên TV.\n"
            "🗓 `/diemdanh` - Điểm danh mỗi ngày để lấy được thêm lượt.\n"
            "🌐 `/language` - Đổi ngôn ngữ.\n\n"
            "⚡️ *Quyền lợi điểm danh:*\n"
            "- Mặc định: Được 5 lượt/ngày.\n"
            "- Điểm danh ≥ 3 ngày: Được +1 lượt/ngày.\n"
            "- Điểm danh ≥ 5 ngày: Được +2 lượt/ngày.\n"
        ),

        # === /ping ===
        "pong": "Pong! Tôi vẫn đang sống và nhận tin nhắn!",

        # === /diemdanh ===
        "checkin_success": "🎉 Bạn đã điểm danh thành công ngày hôm nay!\n🔥 Chuỗi điểm danh hiện tại: *{streak} ngày*",
        "checkin_already": "⚠️ Hôm nay bạn đã điểm danh rồi mà!\n🔥 Nhắc lại chuỗi điểm danh hiện tại: *{streak} ngày*",

        # === /stats (Admin) ===
        "stats_no_perm": "❌ Tính năng này chỉ dành cho Admin để kiểm tra kho phòng máy.",
        "stats_report": (
            "📊 *BÁO CÁO HỆ THỐNG NETFLIX*\n"
            "---------------------------\n"
            "👥 *Tình trạng Hoạt Động (User):*\n"
            "- Tổng khách đã đăng ký: `{users_total}` người\n"
            "- Số khách húp link hôm nay: `{users_active_today}` người\n"
            "---------------------------\n"
            "🍪 *Sức khỏe Kho Cookie:*\n"
            "- Trữ lượng còn Sống: `{cookie_alive}` / Tổng đã nạp `{cookie_total}` cục\n"
            "- 🎟 Tổng số Link đã phát ra: `{total_generated} lượt`\n"
        ),
        "stats_error": "❌ Lỗi truy cập Database: {error}",

        # === /clear_cookies (Admin) ===
        "clear_no_perm": "❌ Bạn không có quyền thực hiện lệnh này.",
        "clear_confirm": "⚠️ *BẠN CÓ CHẮC CHẮN MUỐN XÓA TOÀN BỘ COOKIE?*\n\nHành động này không thể hoàn tác!",
        "clear_confirm_yes": "✅ Xác nhận xóa",
        "clear_confirm_no": "❌ Hủy bỏ",
        "clear_done": "🗑 Đã xóa {count} cookies khỏi cơ sở dữ liệu.",
        "clear_cancelled": "👍 Đã hủy. Không có cookie nào bị xóa.",
        "clear_error": "❌ Lỗi: {error}",

        # === /get_token ===
        "quota_exceeded": "❌ Hôm nay bạn đã nhận tối đa *{cap} link* của bạn rồi!\n🗓 Hãy quay lại vào ngày mai (sau 00:00) hoặc chăm chỉ gõ `/diemdanh` để được duyệt thêm link nhé.",
        "token_loading": "⏳ Đang tìm cookie khả dụng và tạo token, vui lòng chờ...",
        "no_cookie": "❌ Không có cookie nào 'sống' trong DataBase. Liên hệ Admin để nạp thêm!",
        "token_switching": "♻️ Cookie vừa chọn bị từ chối, đang thử tự động lục cookie khác...",
        "token_success": (
            "✅ *Lấy NFToken thành công!*\n\n"
            "🔗 *URL Đăng Nhập:* {link}\n\n"
            "⏰ Giờ hết hạn: `{expiry}`\n"
        ),
        "token_remain": "\n🎟 Lượt lấy link còn lại hôm nay: *{remain}/{cap}*\n",
        "token_error": "❌ Có lỗi khi tạo token: {error}",
        "token_all_dead": "❌ Đã thử nhiều cookie nhưng không cái nào hoạt động. Vui lòng thử lại sau!",
        "btn_report_error": "⚠️ Báo lỗi Token này",

        # === /tv ===
        "tv_syntax": "❌ Sai cú pháp! Vui lòng gõ lệnh kèm mã số TV.\n\n*Ví dụ:* `/tv 12345678` hoặc `/tv 1234-5678`",
        "tv_quota_exceeded": "❌ Hôm nay bạn đã hết hạn mức *{cap} lượt* (dùng chung cho cả Link và TV)!\n🗓 Hãy quay lại vào ngày mai nhé.",
        "tv_loading": "⏳ Đang kết nối Chrome và xử lý mã TV `{code}`.\n🕐 Quá trình này mất 15-30 giây, vui lòng chờ...",
        "tv_success": "✅ **Kích hoạt TV Thành Công!**\n\n📺 Hãy nhìn lên màn hình TV của bạn, Netflix đã tự động đăng nhập!\n\n💡 Lượt dùng còn lại trong ngày: `{remain}/{cap}`",
        "tv_invalid_code": "❌ Lỗi Mã TV: {error}",
        "tv_cookie_switch": "♻️ Cookie #{attempt} không hỗ trợ, đang đổi cookie khác...",
        "tv_connection_error": "❌ Lỗi kết nối: {error}",
        "tv_all_dead": "❌ Đã thử nhiều cookie nhưng không cái nào hỗ trợ TV. Vui lòng thử lại sau!",
        "tv_unexpected": "❌ Lỗi không mong đợi: {error}",

        # === Error Report Callback ===
        "report_sent": "Đã gửi báo cáo lỗi đến Admin thành công!\nNếu bạn cần hỗ trợ, vui lòng liên hệ : @Mochi_Mochi05",
        "report_admin": (
            "🚨 *CẢNH BÁO: TOKEN LỖI TỪ THÀNH VIÊN* 🚨\n"
            "👤 Người báo cáo: {first_name}\n"
            "👤 Username: {username}\n"
            "🆔 Telegram ID: `{user_id}`\n"
            "🔑 ObjectID Cookie lỗi: `{cookie_id}`\n\n"
            "Hãy kiểm tra trong Database Cookie Mongo hoặc xem file trong thư mục `Cookie_loi` nếu chạy ở máy chủ cục bộ!"
        ),

        # === Document Upload (Admin) ===
        "doc_no_perm": "❌ Chỉ Admin mới có quyền tải file cookie lên cơ sở dữ liệu.",
        "doc_parse_error": "❌ Lỗi giải mã file Cookie: {error}",
        "doc_no_netflix_id": "❌ Không tìm thấy `NetflixId` hợp lệ trong file này.",
        "doc_success": "✅ Đã thêm cookie từ `{filename}` vào DB thành công!",
        "doc_duplicate": "ℹ️ Cookie trong file `{filename}` đã từng được lưu vào DB trước đây rồi.",
        "doc_error": "❌ Lỗi xử lý file: {error}",

        # === Menu Commands ===
        "menu_get_token": "Rút 1 link xem Netflix",
        "menu_tv": "Đăng nhập trực tiếp TV (Nhập mã 8 số)",
        "menu_checkin": "Điểm danh hàng ngày",
        "menu_language": "Đổi ngôn ngữ",
        "menu_start": "Xem thông tin & Hướng dẫn",
        "menu_ping": "Kiểm tra kết nối Bot",
        "menu_stats": "Xem thống kê DB (Admin)",
        "menu_clear": "Xoá DB Cookie (Admin)",
    },

    "en": {
        # === Language Selection ===
        "choose_language": "🌐 Please choose your language:\nVui lòng chọn ngôn ngữ:",
        "lang_set_vi": "✅ Language set to: *Tiếng Việt* 🇻🇳",
        "lang_set_en": "✅ Language set to: *English* 🇬🇧",
        "btn_vi": "🇻🇳 Tiếng Việt",
        "btn_en": "🇬🇧 English",

        # === /start - /help ===
        "welcome_admin": (
            "👑 *Welcome, ADMIN!*\n\n"
            "Your system commands:\n"
            "🔗 `/get_token` - Extract a cookie to generate a Netflix login link.\n"
            "📺 `/tv <8-digit code>` - Activate Netflix login directly on TV.\n"
            "📊 `/stats` - View cookie stock in DB.\n"
            "🗓 `/diemdanh` - Daily check-in.\n"
            "🌐 `/language` - Change language.\n"
            "📝 Direct upload: Send a `cookie` file (.txt, .json) here to import.\n"
            "🗑 `/clear_cookies` - Clear all cookies from Database.\n"
        ),
        "welcome_user": (
            "🎬 *Netflix Token Extractor Bot*\n\n"
            "Available commands:\n"
            "🔗 `/get_token` - Get a Netflix login link.\n"
            "📺 `/tv <8-digit code>` - Activate Netflix login directly on TV.\n"
            "🗓 `/diemdanh` - Daily check-in to earn extra uses.\n"
            "🌐 `/language` - Change language.\n\n"
            "⚡️ *Check-in benefits:*\n"
            "- Default: 5 uses/day.\n"
            "- 3+ day streak: +1 use/day.\n"
            "- 5+ day streak: +2 uses/day.\n"
        ),

        # === /ping ===
        "pong": "Pong! I'm alive and receiving messages!",

        # === /diemdanh ===
        "checkin_success": "🎉 You have successfully checked in today!\n🔥 Current streak: *{streak} days*",
        "checkin_already": "⚠️ You have already checked in today!\n🔥 Current streak: *{streak} days*",

        # === /stats (Admin) ===
        "stats_no_perm": "❌ This feature is for Admin only.",
        "stats_report": (
            "📊 *NETFLIX SYSTEM REPORT*\n"
            "---------------------------\n"
            "👥 *User Activity:*\n"
            "- Total registered users: `{users_total}`\n"
            "- Active users today: `{users_active_today}`\n"
            "---------------------------\n"
            "🍪 *Cookie Health:*\n"
            "- Alive: `{cookie_alive}` / Total imported `{cookie_total}`\n"
            "- 🎟 Total links generated: `{total_generated}`\n"
        ),
        "stats_error": "❌ Database access error: {error}",

        # === /clear_cookies (Admin) ===
        "clear_no_perm": "❌ You don't have permission to do this.",
        "clear_confirm": "⚠️ *ARE YOU SURE YOU WANT TO DELETE ALL COOKIES?*\n\nThis action cannot be undone!",
        "clear_confirm_yes": "✅ Confirm delete",
        "clear_confirm_no": "❌ Cancel",
        "clear_done": "🗑 Deleted {count} cookies from the database.",
        "clear_cancelled": "👍 Cancelled. No cookies were deleted.",
        "clear_error": "❌ Error: {error}",

        # === /get_token ===
        "quota_exceeded": "❌ You've used all *{cap} links* for today!\n🗓 Come back tomorrow (after 00:00) or use `/diemdanh` daily to earn more.",
        "token_loading": "⏳ Finding an available cookie and generating token, please wait...",
        "no_cookie": "❌ No active cookies in the Database. Contact Admin to add more!",
        "token_switching": "♻️ Cookie rejected, automatically trying another one...",
        "token_success": (
            "✅ *NFToken generated successfully!*\n\n"
            "🔗 *Login URL:* {link}\n\n"
            "⏰ Expires at: `{expiry}`\n"
        ),
        "token_remain": "\n🎟 Remaining uses today: *{remain}/{cap}*\n",
        "token_error": "❌ Error generating token: {error}",
        "token_all_dead": "❌ Tried multiple cookies but none worked. Please try again later!",
        "btn_report_error": "⚠️ Report this token",

        # === /tv ===
        "tv_syntax": "❌ Wrong syntax! Please include the TV code.\n\n*Example:* `/tv 12345678` or `/tv 1234-5678`",
        "tv_quota_exceeded": "❌ You've used all *{cap} uses* today (shared between Link and TV)!\n🗓 Please come back tomorrow.",
        "tv_loading": "⏳ Connecting to Chrome and processing TV code `{code}`.\n🕐 This takes 15-30 seconds, please wait...",
        "tv_success": "✅ **TV Activation Successful!**\n\n📺 Check your TV screen — Netflix has been logged in automatically!\n\n💡 Remaining uses today: `{remain}/{cap}`",
        "tv_invalid_code": "❌ TV Code Error: {error}",
        "tv_cookie_switch": "♻️ Cookie #{attempt} not supported, switching to another...",
        "tv_connection_error": "❌ Connection error: {error}",
        "tv_all_dead": "❌ Tried multiple cookies but none support TV. Please try again later!",
        "tv_unexpected": "❌ Unexpected error: {error}",

        # === Error Report Callback ===
        "report_sent": "Error report sent to Admin successfully!\nIf you need support, please contact: @Mochi_Mochi05",
        "report_admin": (
            "🚨 *ALERT: BROKEN TOKEN REPORTED BY USER* 🚨\n"
            "👤 Reporter: {first_name}\n"
            "👤 Username: {username}\n"
            "🆔 Telegram ID: `{user_id}`\n"
            "🔑 Cookie ObjectID: `{cookie_id}`\n\n"
            "Check the MongoDB Cookie Database or the `Cookie_loi` folder on the local server!"
        ),

        # === Document Upload (Admin) ===
        "doc_no_perm": "❌ Only Admin can upload cookie files to the database.",
        "doc_parse_error": "❌ Error parsing cookie file: {error}",
        "doc_no_netflix_id": "❌ No valid `NetflixId` found in this file.",
        "doc_success": "✅ Successfully added cookie from `{filename}` to DB!",
        "doc_duplicate": "ℹ️ Cookie from `{filename}` already exists in the DB.",
        "doc_error": "❌ Error processing file: {error}",

        # === Menu Commands ===
        "menu_get_token": "Get a Netflix login link",
        "menu_tv": "TV Login (Enter 8-digit code)",
        "menu_checkin": "Daily check-in",
        "menu_language": "Change language",
        "menu_start": "Info & Help",
        "menu_ping": "Check bot connection",
        "menu_stats": "View DB stats (Admin)",
        "menu_clear": "Clear Cookie DB (Admin)",
    }
}

DEFAULT_LANG = "vi"


def get_text(lang, key, **kwargs):
    """Get translated text by language code and key, with optional format args."""
    lang = lang or DEFAULT_LANG
    text_dict = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    text = text_dict.get(key, TEXTS[DEFAULT_LANG].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
