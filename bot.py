import os
import time
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
from flask import Flask, request, jsonify
import database as db
import netflix_token_extractor as extractor
import netflix_tv_activator as tv_activator
import threading
from lang import get_text

# --- Configurations ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID") # VD: 123456789 (Int)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # Dành cho Render
# BROWSERLESS_TOKEN được đọc trực tiếp bởi netflix_tv_activator.py
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


# --- Language Helper ---
def t(user_id, key, **kwargs):
    """Shortcut to get translated text for a user."""
    lang = db.get_user_lang(user_id)
    return get_text(lang, key, **kwargs)


def send_language_picker(chat_id, reply_to_id=None):
    """Gửi inline keyboard chọn ngôn ngữ."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🇻🇳 Tiếng Việt", callback_data="lang_vi"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    )
    text = "🌐 Vui lòng chọn ngôn ngữ:\nPlease choose your language:"
    if reply_to_id:
        bot.send_message(chat_id, text, reply_markup=markup, reply_to_message_id=reply_to_id)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


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

# Lệnh kiểm tra sinh tồn cơ bản
@bot.message_handler(commands=['ping'])
def send_ping(message):
    bot.reply_to(message, t(message.from_user.id, "pong"))


@bot.message_handler(commands=['language'])
def language_command(message):
    send_language_picker(message.chat.id, reply_to_id=message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('lang_'))
def handle_language_select(call):
    user_id = call.from_user.id
    username = call.from_user.username or call.from_user.first_name or ""
    lang_code = call.data.split('_')[1]  # "vi" or "en"

    db.set_user_lang(user_id, lang_code, username)

    # Xác nhận bằng ngôn ngữ vừa chọn
    confirm_key = f"lang_set_{lang_code}"
    bot.edit_message_text(
        get_text(lang_code, confirm_key),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )

    # Gửi welcome message sau khi chọn ngôn ngữ
    if is_admin(user_id):
        welcome_text = get_text(lang_code, "welcome_admin")
    else:
        welcome_text = get_text(lang_code, "welcome_user")
    bot.send_message(call.message.chat.id, welcome_text, parse_mode="Markdown")


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    lang = db.get_user_lang(user_id)

    if lang is None:
        # User mới, chưa chọn ngôn ngữ → hỏi trước
        send_language_picker(message.chat.id, reply_to_id=message.message_id)
        return

    # User đã chọn ngôn ngữ → hiện welcome
    if is_admin(user_id):
        text = t(user_id, "welcome_admin")
    else:
        text = t(user_id, "welcome_user")
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(commands=['diemdanh'])
def checkin_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    success, streak = db.check_in_user(user_id, username)
    if success:
        bot.reply_to(message, t(user_id, "checkin_success", streak=streak), parse_mode="Markdown")
    else:
        bot.reply_to(message, t(user_id, "checkin_already", streak=streak), parse_mode="Markdown")


@bot.message_handler(commands=['stats'])
def stats_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, t(user_id, "stats_no_perm"))
        return

    try:
        s = db.count_stats()
        text = t(user_id, "stats_report",
                 users_total=s['users_total'],
                 users_active_today=s['users_active_today'],
                 cookie_alive=s['cookie_alive'],
                 cookie_total=s['cookie_total'],
                 total_generated=s['total_generated'])
        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, t(user_id, "stats_error", error=e))


@bot.message_handler(commands=['clear_cookies'])
def clear_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, t(user_id, "clear_no_perm"))
        return
    # Hỏi xác nhận trước khi xóa
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(t(user_id, "clear_confirm_yes"), callback_data="clear_yes"),
        InlineKeyboardButton(t(user_id, "clear_confirm_no"), callback_data="clear_no")
    )
    bot.reply_to(message, t(user_id, "clear_confirm"), parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ['clear_yes', 'clear_no'])
def handle_clear_confirm(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, t(user_id, "clear_no_perm"))
        return

    if call.data == "clear_no":
        bot.edit_message_text(t(user_id, "clear_cancelled"),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
        return

    try:
        deleted = db.clear_all_cookies()
        bot.edit_message_text(t(user_id, "clear_done", count=deleted),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
    except Exception as e:
        bot.edit_message_text(t(user_id, "clear_error", error=e),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)


@bot.message_handler(commands=['get_token'])
def get_token_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    # 1. Check hạn mức
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, t(user_id, "quota_exceeded", cap=cap), parse_mode="Markdown")
        return

    loading_msg = bot.reply_to(message, t(user_id, "token_loading"))

    # 2. Xử lý Cookies và API
    max_retries = 5
    for attempt in range(max_retries):
        cookie_doc = db.get_active_cookie()
        if not cookie_doc:
            bot.edit_message_text(t(user_id, "no_cookie"),
                                  chat_id=message.chat.id, message_id=loading_msg.message_id)
            return

        netflix_id = cookie_doc['cookie_data'].get('NetflixId') or cookie_doc['cookie_data'].get('netflix_id')
        if not netflix_id:
            db.mark_cookie_as_dead(cookie_doc['netflix_id'])
            save_dead_cookie_to_file(cookie_doc)
            continue

        try:
            token, expires = extractor.fetch_nftoken(netflix_id)
            link = extractor.build_nftoken_link(token)
            expiry_str = extractor.format_expiry(expires)

            if not is_admin(user_id):
                db.increment_link_usage(user_id)

            result_text = t(user_id, "token_success", link=link, expiry=expiry_str)
            if not is_admin(user_id):
                real_remain = remain - 1 if remain > 0 else 0
                result_text += t(user_id, "token_remain", remain=real_remain, cap=cap)

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton(
                t(user_id, "btn_report_error"),
                callback_data=f"err_{str(cookie_doc['_id'])}"
            ))

            bot.edit_message_text(result_text, chat_id=message.chat.id,
                                  message_id=loading_msg.message_id, parse_mode="Markdown", reply_markup=markup)
            return

        except (extractor.requests.exceptions.HTTPError, ValueError) as e:
            try:
                bot.edit_message_text(t(user_id, "token_switching"),
                                      chat_id=message.chat.id, message_id=loading_msg.message_id)
            except Exception:
                pass
            db.mark_cookie_as_dead(cookie_doc['netflix_id'])
            save_dead_cookie_to_file(cookie_doc)
            time.sleep(1)

        except Exception as e:
            bot.edit_message_text(t(user_id, "token_error", error=e),
                                  chat_id=message.chat.id, message_id=loading_msg.message_id)
            return

    try:
        bot.edit_message_text(t(user_id, "token_all_dead"),
                              chat_id=message.chat.id, message_id=loading_msg.message_id)
    except Exception:
        pass


@bot.message_handler(commands=['tv'])
def tv_command(message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "tv_syntax"), parse_mode="Markdown")
        return

    tv_code = parts[1]
    username = message.from_user.username or message.from_user.first_name

    # 1. Check hạn mức
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, t(user_id, "tv_quota_exceeded", cap=cap), parse_mode="Markdown")
        return

    loading_msg = bot.reply_to(message, t(user_id, "tv_loading", code=tv_code), parse_mode="Markdown")

    # Chạy trong thread nền để webhook không bị timeout
    def _process_tv():
        try:
            max_retries = 5
            for attempt in range(max_retries):
                cookie_doc = db.get_active_cookie()
                if not cookie_doc:
                    bot.edit_message_text(t(user_id, "no_cookie"),
                                          chat_id=message.chat.id, message_id=loading_msg.message_id)
                    return

                try:
                    tv_activator.activate_tv_code(cookie_doc['cookie_data'], tv_code)

                    # Thành công!
                    db.increment_link_usage(user_id)
                    remain_after = remain - 1
                    bot.edit_message_text(
                        t(user_id, "tv_success", remain=remain_after, cap=cap),
                        chat_id=message.chat.id,
                        message_id=loading_msg.message_id, parse_mode="Markdown")
                    return

                except ValueError as e:
                    err_msg = str(e)
                    if "Invalid TV Code" in err_msg or "hợp lệ" in err_msg or "hết hạn" in err_msg:
                        bot.edit_message_text(
                            t(user_id, "tv_invalid_code", error=err_msg),
                            chat_id=message.chat.id, message_id=loading_msg.message_id)
                        return
                    else:
                        db.mark_cookie_as_dead(cookie_doc['netflix_id'])
                        save_dead_cookie_to_file(cookie_doc)
                        try:
                            bot.edit_message_text(
                                t(user_id, "tv_cookie_switch", attempt=attempt+1),
                                chat_id=message.chat.id, message_id=loading_msg.message_id)
                        except Exception:
                            pass
                        time.sleep(1)

                except Exception as e:
                    bot.edit_message_text(
                        t(user_id, "tv_connection_error", error=e),
                        chat_id=message.chat.id, message_id=loading_msg.message_id)
                    return

            # Hết max retries
            try:
                bot.edit_message_text(t(user_id, "tv_all_dead"),
                                      chat_id=message.chat.id, message_id=loading_msg.message_id)
            except Exception:
                pass
        except Exception as e:
            try:
                bot.edit_message_text(
                    t(user_id, "tv_unexpected", error=e),
                    chat_id=message.chat.id, message_id=loading_msg.message_id)
            except Exception:
                pass

    thread = threading.Thread(target=_process_tv, daemon=True)
    thread.start()


@bot.callback_query_handler(func=lambda call: call.data.startswith('err_'))
def handle_error_report(call):
    user_id = call.from_user.id
    cookie_obj_id = call.data.split('_')[1]

    bot.answer_callback_query(call.id, t(user_id, "report_sent"), show_alert=True)

    if ADMIN_ID:
        first_name = call.from_user.first_name if call.from_user.first_name else "N/A"
        username = f"@{call.from_user.username}" if call.from_user.username else "N/A"

        report_text = t(user_id, "report_admin",
                        first_name=first_name,
                        username=username,
                        user_id=user_id,
                        cookie_id=cookie_obj_id)
        try:
            bot.send_message(ADMIN_ID, report_text, parse_mode="Markdown")
        except Exception as e:
            print("Cannot report to Admin:", e)


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, t(user_id, "doc_no_perm"))
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_filename = f"temp_{message.document.file_id}_{message.document.file_name}"
        with open(temp_filename, 'wb') as new_file:
            new_file.write(downloaded_file)

        try:
            cookies = extractor.read_cookies(temp_filename)
            os.remove(temp_filename)
        except Exception as parse_e:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
            bot.reply_to(message, t(user_id, "doc_parse_error", error=parse_e))
            return

        netflix_id = cookies.get('NetflixId')
        if not netflix_id:
            bot.reply_to(message, t(user_id, "doc_no_netflix_id"))
            return

        success = db.insert_cookie(netflix_id, cookies, source_file=message.document.file_name)
        if success:
            bot.reply_to(message, t(user_id, "doc_success", filename=message.document.file_name))
        else:
            bot.reply_to(message, t(user_id, "doc_duplicate", filename=message.document.file_name))

    except Exception as e:
        bot.reply_to(message, t(user_id, "doc_error", error=e))


# --- Flask Server for Render ---
@app.route('/', methods=['GET', 'HEAD'])
def index():
    return "Netflix Token Bot is running!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    # LUÔN trả 200 để Telegram không retry request bị lỗi (gây vòng lặp chết chóc)
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
    except Exception as e:
        print(f"⚠️ Webhook error (swallowed to prevent retry loop): {e}")
    return '', 200

def setup_menu():
    try:
        # Menu chung cho mọi người
        bot.set_my_commands([
            telebot.types.BotCommand("get_token", "Get Netflix login link"),
            telebot.types.BotCommand("tv", "TV Login (8-digit code)"),
            telebot.types.BotCommand("diemdanh", "Daily check-in"),
            telebot.types.BotCommand("language", "🌐 Language / Ngôn ngữ"),
            telebot.types.BotCommand("start", "Info & Help"),
            telebot.types.BotCommand("ping", "Check bot connection")
        ])
        # Menu vip cho Admin
        if ADMIN_ID:
            bot.set_my_commands([
                telebot.types.BotCommand("get_token", "Get Netflix login link"),
                telebot.types.BotCommand("tv", "TV Login (8-digit code)"),
                telebot.types.BotCommand("diemdanh", "Daily check-in"),
                telebot.types.BotCommand("language", "🌐 Language / Ngôn ngữ"),
                telebot.types.BotCommand("stats", "DB Stats (Admin)"),
                telebot.types.BotCommand("clear_cookies", "Clear Cookie DB (Admin)"),
                telebot.types.BotCommand("start", "Info & Help"),
                telebot.types.BotCommand("ping", "Check bot connection")
            ], scope=telebot.types.BotCommandScopeChat(ADMIN_ID))
    except Exception as e:
        print("Menu setup error:", e)

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
