import os
import time
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
from flask import Flask, request, jsonify
import database as db
import netflix_token_extractor as extractor
import netflix_tv_activator as tv_activator

# --- Configurations ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID") # VD: 123456789 (Int)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # Dành cho Render
PORT = int(os.environ.get("PORT", 10000))

if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

import logging
logger = telebot.logger
telebot.logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)

# Lệnh kiểm tra sinh tồn cơ bản
@bot.message_handler(commands=['ping'])
def send_ping(message):
    bot.reply_to(message, "Pong! Tôi vẫn đang sống và nhận tin nhắn!")

# --- Helper Logic ---
def save_dead_cookie_to_file(cookie_doc):
    os.makedirs("Cookie_loi", exist_ok=True)
    source_file = cookie_doc.get('source', 'unknown.txt')
    safe_name = f"dead_{int(time.time())}_{source_file}"
    if not safe_name.endswith('.txt') and not safe_name.endswith('.json'):
        safe_name += '.json'
    error_path = os.path.join("Cookie_loi", safe_name)
    with open(error_path, "w", encoding="utf-8") as f:
        json.dump(cookie_doc['cookie_data'], f, indent=4)

def is_admin(user_id):
    if not ADMIN_ID:
        return True # Nếu không cấu hình Admin, ai cũng có quyền
    return user_id == ADMIN_ID

# --- Bot Command Handlers ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        text = (
            "👑 *Xin chào CHỦ NHÂN (ADMIN)!*\n\n"
            "Các lệnh hệ thống của bạn:\n"
            "🔗 `/get_token` - Rút 1 cookie sinh Link xem Netflix.\n"
            "📊 `/stats` - Xem số lượng cookie dự trữ trong DB.\n"
            "🗓 `/diemdanh` - Điểm danh ngày mới.\n"
            "📝 Nhận dạng trực tiếp: Bạn có thể đưa file `cookie` (.txt, .json) vào trực tiếp đây để nạp.\n"
            "🗑 `/clear_cookies` - Xoá toàn bộ Database Cookie.\n"
        )
    else:
        text = (
            "🎬 *Netflix Token Extractor Bot*\n\n"
            "Lệnh cung cấp:\n"
            "🔗 `/get_token` - Rút 1 cookie sinh Link xem Netflix.\n"
            "📺 `/tv <mã 8 số>` - Kích hoạt đăng nhập trực tiếp trên TV.\n"
            "🗓 `/diemdanh` - Điểm danh mỗi ngày để lấy được thêm lượt.\n\n"
            "⚡️ *Quyền lợi điểm danh:*\n"
            "- Mặc định: Được 5 lượt/ngày.\n"
            "- Điểm danh ≥ 3 ngày: Được +1 lượt/ngày.\n"
            "- Điểm danh ≥ 5 ngày: Được +2 lượt/ngày.\n"
        )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['diemdanh'])
def checkin_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    success, streak = db.check_in_user(user_id, username)
    if success:
        bot.reply_to(message, f"🎉 Bạn đã điểm danh thành công ngày hôm nay!\n🔥 Chuỗi điểm danh hiện tại: *{streak} ngày*", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"⚠️ Hôm nay bạn đã điểm danh rồi mà!\n🔥 Nhắc lại chuỗi điểm danh hiện tại: *{streak} ngày*", parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def stats_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Tính năng này chỉ dành cho Admin để kiểm tra kho phòng máy.")
        return
        
    try:
        s = db.count_stats()
        text = (
            "📊 *BÁO CÁO HỆ THỐNG NETFLIX*\n"
            "---------------------------\n"
            "👥 *Tình trạng Hoạt Động (User):*\n"
            f"- Tổng khách đã đăng ký: `{s['users_total']}` người\n"
            f"- Số khách húp link hôm nay: `{s['users_active_today']}` người\n"
            "---------------------------\n"
            "🍪 *Sức khỏe Kho Cookie:*\n"
            f"- Trữ lượng còn Sống: `{s['cookie_alive']}` / Tổng đã nạp `{s['cookie_total']}` cục\n"
            f"- 🎟 Tổng số Link đã phát ra: `{s['total_generated']} lượt`\n"
        )
        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi truy cập Database: {e}")

@bot.message_handler(commands=['clear_cookies'])
def clear_command(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Bạn không có quyền thực hiện lệnh này.")
        return
    try:
        deleted = db.clear_all_cookies()
        bot.reply_to(message, f"🗑 Đã xóa {deleted} cookies khỏi cơ sở dữ liệu.")
    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi: {e}")

@bot.message_handler(commands=['get_token'])
def get_token_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # 1. Check hạn mức
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, f"❌ Hôm nay bạn đã nhận tối đa *{cap} link* của bạn rồi!\n🗓 Hãy quay lại vào ngày mai (sau 00:00) hoặc chăm chỉ gõ `/diemdanh` để được duyệt thêm link nhé.", parse_mode="Markdown")
        return

    loading_msg = bot.reply_to(message, "⏳ Đang tìm cookie khả dụng và tạo token, vui lòng chờ...")
    
    # 2. Xử lý Cookies và API
    while True:
        cookie_doc = db.get_active_cookie()
        if not cookie_doc:
            bot.edit_message_text("❌ Không có cookie nào 'sống' trong DataBase. Liên hệ Admin để nạp thêm!", 
                                  chat_id=message.chat.id, message_id=loading_msg.message_id)
            return

        netflix_id = cookie_doc['cookie_data'].get('NetflixId') or cookie_doc['cookie_data'].get('netflix_id')
        if not netflix_id:
            # Dữ liệu hỏng
            db.mark_cookie_as_dead(cookie_doc['netflix_id'])
            save_dead_cookie_to_file(cookie_doc)
            continue
            
        try:
            # Cố gắng lấy nfToken từ netflix_id
            token, expires = extractor.fetch_nftoken(netflix_id)
            link = extractor.build_nftoken_link(token)
            expiry_str = extractor.format_expiry(expires)
            
            # Đánh dấu đã sử dụng (Ngoại trừ admin test tự do)
            if not is_admin(user_id):
                db.increment_link_usage(user_id)
            
            # Kết quả trả về
            result_text = (
                "✅ *Lấy NFToken thành công!*\n\n"
                f"🔗 *URL Đăng Nhập:* {link}\n\n"
                f"⏰ Giờ hết hạn: `{expiry_str}`\n"
            )
            if not is_admin(user_id):
                real_remain = remain - 1 if remain > 0 else 0
                result_text += f"\n🎟 Lượt lấy link còn lại hôm nay: *{real_remain}/{cap}*\n"
            
            # Thêm nút báo lỗi gửi Admin dựa theo Object ID MongoDB
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⚠️ Báo lỗi Token này", callback_data=f"err_{str(cookie_doc['_id'])}"))
            
            bot.edit_message_text(result_text, chat_id=message.chat.id, 
                                  message_id=loading_msg.message_id, parse_mode="Markdown", reply_markup=markup)
            return
            
        except (extractor.requests.exceptions.HTTPError, ValueError) as e:
            # Thông báo đổi Cookie (Làm xoa dịu người dùng)
            try:
                bot.edit_message_text(f"♻️ Cookie vừa chọn bị từ chối, đang thử tự động lục cookie khác...", 
                                      chat_id=message.chat.id, message_id=loading_msg.message_id)
            except Exception:
                pass
                
            # Đánh dấu chết và trích xuất ra file
            db.mark_cookie_as_dead(cookie_doc['netflix_id'])
            save_dead_cookie_to_file(cookie_doc)
            # Quá trình while loop lặp lại tìm cookie tiếp
            time.sleep(1) # Tránh bão API
            
        except Exception as e:
            # Lỗi mạng hoặc lỗi khác
            bot.edit_message_text(f"❌ Có lỗi khi tạo token: {e}", chat_id=message.chat.id, 
                                  message_id=loading_msg.message_id)
            return


@bot.message_handler(commands=['tv'])
def tv_command(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Sai cú pháp! Vui lòng gõ lệnh kèm mã số TV.\n\n*Ví dụ:* `/tv 12345678` hoặc `/tv 1234-5678`", parse_mode="Markdown")
        return
        
    tv_code = parts[1]
    
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # 1. Check hạn mức
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, f"❌ Hôm nay bạn đã hết hạn mức *{cap} lượt* (dùng chung cho cả Link và TV)!\n🗓 Hãy quay lại vào ngày mai nhé.", parse_mode="Markdown")
        return

    loading_msg = bot.reply_to(message, f"⏳ Đang mở trình duyệt ảo và nhập mã TV `{tv_code}`.\n🕐 Quá trình này sẽ mất khoảng 15-30 giây, vui lòng kiên nhẫn chờ...", parse_mode="Markdown")
    
    # 2. Xử lý Cookies và Kích hoạt
    while True:
        cookie_doc = db.get_active_cookie()
        if not cookie_doc:
            bot.edit_message_text("❌ Không có cookie nào 'sống' trong DataBase. Liên hệ Admin để nạp thêm!", 
                                  chat_id=message.chat.id, message_id=loading_msg.message_id)
            return

        try:
            # Thực thi kích hoạt TV
            tv_activator.activate_tv_code(cookie_doc['cookie_data'], tv_code)
            
            # Nếu chạy thành công mà không văng Exception
            db.increment_link_usage(user_id)
            remain_after = remain - 1
            
            result_text = (
                f"✅ **Kích hoạt TV Thành Công!**\n\n"
                f"📺 Hãy nhìn lên màn hình TV của bạn, Netflix đã tự động đăng nhập!\n\n"
                f"💡 Lượt dùng còn lại trong ngày: `{remain_after}/{cap}`"
            )
            bot.edit_message_text(result_text, chat_id=message.chat.id, 
                                  message_id=loading_msg.message_id, parse_mode="Markdown")
            return
            
        except ValueError as e:
            err_msg = str(e)
            if "Invalid TV Code" in err_msg or "hợp lệ" in err_msg or "hết hạn" in err_msg:
                # Lỗi do chính khách nhập sai mã -> Ko đổi cookie, trả lỗi luôn
                bot.edit_message_text(f"❌ Lỗi Mã TV: {err_msg}", chat_id=message.chat.id, 
                                      message_id=loading_msg.message_id)
                return
            else:
                # Lỗi authURL hỏng hoặc bị khoá chức năng -> Chuyển cookie
                db.mark_cookie_as_dead(cookie_doc['netflix_id'])
                save_dead_cookie_to_file(cookie_doc)
                try:
                    bot.edit_message_text("♻️ Cookie không hỗ trợ kích hoạt TV, đang đổi cookie khác...", 
                                          chat_id=message.chat.id, message_id=loading_msg.message_id)
                except Exception:
                    pass
                time.sleep(1)
                
        except Exception as e:
            # Lỗi mạng
            bot.edit_message_text(f"❌ Có lỗi kết nối Netflix: {e}", chat_id=message.chat.id, 
                                  message_id=loading_msg.message_id)
            return


@bot.callback_query_handler(func=lambda call: call.data.startswith('err_'))
def handle_error_report(call):
    cookie_obj_id = call.data.split('_')[1]
    
    # Báo phản hồi lại hộp thoại của User
    bot.answer_callback_query(call.id, "Đã gửi báo cáo lỗi đến Admin thành công!\nNếu bạn cần hỗ trợ, vui lòng liên hệ : @Mochi_Mochi05", show_alert=True)
    
    # Bắn tin nhắn chéo thẳng tới Admin
    if ADMIN_ID:
        first_name = call.from_user.first_name if call.from_user.first_name else "Ẩn danh"
        username = f"@{call.from_user.username}" if call.from_user.username else "Không có"
        user_id = call.from_user.id
        
        report_text = (
            "🚨 *CẢNH BÁO: TOKEN LỖI TỪ THÀNH VIÊN* 🚨\n"
            f"👤 Người báo cáo: {first_name}\n"
            f"👤 Username: {username}\n"
            f"🆔 Telegram ID: `{user_id}`\n"
            f"🔑 ObjectID Cookie lỗi: `{cookie_obj_id}`\n\n"
            "Hãy kiểm tra trong Database Cookie Mongo hoặc xem file trong thư mục `Cookie_loi` nếu chạy ở máy chủ cục bộ!"
        )
        try:
            bot.send_message(ADMIN_ID, report_text, parse_mode="Markdown")
        except Exception as e:
            print("Không thể báo cáo tới Admin:", e)


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ Chỉ Admin mới có quyền tải file cookie lên cơ sở dữ liệu.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Lưu ra file tạm để module extractor có thể parse
        temp_filename = f"temp_{message.document.file_id}_{message.document.file_name}"
        with open(temp_filename, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        try:
            # Parse Cookies dùng hàm đã được viết ở netflix_token_extractor.py
            cookies = extractor.read_cookies(temp_filename)
            os.remove(temp_filename)
        except Exception as parse_e:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            bot.reply_to(message, f"❌ Lỗi giải mã file Cookie: {parse_e}")
            return

        netflix_id = cookies.get('NetflixId')
        if not netflix_id:
            bot.reply_to(message, "❌ Không tìm thấy `NetflixId` hợp lệ trong file này.")
            return

        # Lưu vô DB
        success = db.insert_cookie(netflix_id, cookies, source_file=message.document.file_name)
        if success:
            bot.reply_to(message, f"✅ Đã thêm cookie từ `{message.document.file_name}` vào DB thành công!")
        else:
            bot.reply_to(message, f"ℹ️ Cookie trong file `{message.document.file_name}` đã từng được lưu vào DB trước đây rồi.")

    except Exception as e:
        bot.reply_to(message, f"❌ Lỗi xử lý file: {e}")

# --- Flask Server for Render ---
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return "Netflix Token Bot is running!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        return jsonify({"error": "Invalid content-type"}), 403

def setup_menu():
    try:
        # Menu chung cho mọi người
        bot.set_my_commands([
            telebot.types.BotCommand("get_token", "Rút 1 link xem Netflix"),
            telebot.types.BotCommand("tv", "Đăng nhập trực tiếp TV (Nhập mã 8 số)"),
            telebot.types.BotCommand("diemdanh", "Điểm danh hàng ngày"),
            telebot.types.BotCommand("start", "Xem thông tin & Hướng dẫn"),
            telebot.types.BotCommand("ping", "Kiểm tra kết nối Bot")
        ])
        # Menu vip cho Admin
        if ADMIN_ID:
            bot.set_my_commands([
                telebot.types.BotCommand("get_token", "Rút 1 link xem Netflix"),
                telebot.types.BotCommand("tv", "Đăng nhập trực tiếp TV (Nhập mã 8 số)"),
                telebot.types.BotCommand("diemdanh", "Điểm danh hàng ngày"),
                telebot.types.BotCommand("stats", "Xem thống kê DB (Admin)"),
                telebot.types.BotCommand("clear_cookies", "Xoá DB Cookie (Admin)"),
                telebot.types.BotCommand("start", "Xem thông tin & Hướng dẫn"),
                telebot.types.BotCommand("ping", "Kiểm tra kết nối Bot")
            ], scope=telebot.types.BotCommandScopeChat(ADMIN_ID))
    except Exception as e:
        print("Lỗi cài đặt menu:", e)

def set_webhook():
    if WEBHOOK_URL:
        bot.remove_webhook()
        time.sleep(1)
        full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}/{TOKEN}"
        bot.set_webhook(url=full_webhook_url)

if __name__ == '__main__':
    # Chạy cục bộ bằng Long Polling nếu không truyền WEBHOOK_URL
    setup_menu()
    if not WEBHOOK_URL:
        bot.remove_webhook()
        bot.infinity_polling()
    
# Cấu hình webhook khi chạy với gunicorn
if WEBHOOK_URL:
    set_webhook()
    setup_menu()
