import os
import time
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
from flask import Flask, request, jsonify
import database as db
import netflix_token_extractor as extractor
import netflix_tv_activator as tv_activator
import netflix_account_scraper as account_scraper
import threading
import traceback
from lang import get_text

# --- Configurations ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID") # VD: 123456789 (Int)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") # Dành cho Render
# BROWSERLESS_TOKEN được đọc trực tiếp bởi netflix_tv_activator.py
PORT = int(os.environ.get("PORT", 10000))
BOT_USERNAME = None  # Sẽ được set tự động khi khởi động

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


def get_bot_username():
    """Lấy username của bot (cache)."""
    global BOT_USERNAME
    if not BOT_USERNAME:
        try:
            BOT_USERNAME = bot.get_me().username
        except Exception:
            BOT_USERNAME = "Netflix_Loginlink_bot"
    return BOT_USERNAME


def get_ref_bonus(ref_count):
    """Tính bonus lượt từ số referral."""
    if ref_count >= 3:
        return 2
    elif ref_count >= 1:
        return 1
    return 0


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


# --- Rate Limiter (in-memory, 30s cooldown) ---
_last_usage = {}  # {user_id: timestamp}
RATE_LIMIT_SECONDS = 30

def check_rate_limit(user_id):
    """Trả về số giây còn phải chờ, hoặc 0 nếu OK."""
    if is_admin(user_id):
        return 0
    now = time.time()
    last = _last_usage.get(user_id, 0)
    diff = now - last
    if diff < RATE_LIMIT_SECONDS:
        return int(RATE_LIMIT_SECONDS - diff) + 1
    return 0

def mark_rate_limit(user_id):
    """Ghi nhận thời điểm dùng lệnh."""
    _last_usage[user_id] = time.time()


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
    username = message.from_user.username or message.from_user.first_name or ""

    # Xử lý deep link referral: /start ref_123456789
    text_parts = message.text.split()
    if len(text_parts) > 1 and text_parts[1].startswith("ref_"):
        try:
            referrer_id = int(text_parts[1].replace("ref_", ""))
            if referrer_id != user_id:
                success = db.process_referral(user_id, referrer_id, username)
                if success:
                    # Thông báo cho người mời
                    ref_count = db.get_referral_count(referrer_id)
                    bonus = get_ref_bonus(ref_count)
                    try:
                        bot.send_message(
                            referrer_id,
                            t(referrer_id, "ref_notify_referrer",
                              username=username, ref_count=ref_count, bonus=bonus),
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass
        except (ValueError, Exception):
            pass

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


@bot.message_handler(commands=['ref'])
def ref_command(message):
    user_id = message.from_user.id
    bot_name = get_bot_username()
    ref_link = f"https://t.me/{bot_name}?start=ref_{user_id}"
    ref_count = db.get_referral_count(user_id)
    bonus = get_ref_bonus(ref_count)

    bot.reply_to(
        message,
        t(user_id, "ref_info", ref_link=ref_link, ref_count=ref_count, bonus=bonus),
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "N/A"
    p = db.get_profile(user_id, username)
    bonus = get_ref_bonus(p['referral_count'])
    bot.reply_to(
        message,
        t(user_id, "profile_info",
          username=p['username'],
          uid=p['user_id'],
          created_at=p['created_at'],
          streak=p['streak'],
          streak_bonus=p['streak_bonus'],
          usage_today=p['usage_today'],
          limit=p['limit'],
          remain=p['remain'],
          total_usage=p['total_usage'],
          referral_count=p['referral_count'],
          bonus=bonus),
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['guide'])
def guide_command(message):
    user_id = message.from_user.id
    file_id = db.get_tutorial_video()
    if file_id:
        # Gửi video hướng dẫn điện thoại
        try:
            bot.send_video(message.chat.id, file_id,
                           caption=t(user_id, "tutorial_video_caption"),
                           parse_mode="Markdown",
                           reply_to_message_id=message.message_id)
        except Exception as e:
            logging.error(f"Error sending tutorial video: {e}")
            bot.reply_to(message, t(user_id, "tutorial_no_video"))
    else:
        # Chưa có video → thông báo
        bot.reply_to(message, t(user_id, "tutorial_no_video"))

    # Luôn gửi hướng dẫn text cho PC & TV
    try:
        bot.send_message(message.chat.id,
                         t(user_id, "tutorial_text_guide"),
                         parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Error sending tutorial text guide: {e}")
        # Fallback: gửi không có parse_mode
        bot.send_message(message.chat.id, t(user_id, "tutorial_text_guide"))


@bot.message_handler(commands=['checkin'])
def checkin_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    success, streak = db.check_in_user(user_id, username)
    if success:
        # Tính streak_bonus sau khi đã cập nhật streak
        user = db.get_user(user_id)
        streak_bonus = db.get_streak_bonus(user)
        bot.reply_to(message, t(user_id, "checkin_success", streak=streak, streak_bonus=streak_bonus), parse_mode="Markdown")
    else:
        user = db.get_user(user_id)
        streak_bonus = db.get_streak_bonus(user)
        bot.reply_to(message, t(user_id, "checkin_already", streak=streak, streak_bonus=streak_bonus), parse_mode="Markdown")


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
                 total_generated=s['total_generated'],
                 total_uses_today=s['total_uses_today'],
                 token_uses_today=s['token_uses_today'],
                 tv_uses_today=s['tv_uses_today'])
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

    # 0. Rate limit check (30s cooldown)
    wait = check_rate_limit(user_id)
    if wait > 0:
        bot.reply_to(message, t(user_id, "rate_limit_cooldown", seconds=wait), parse_mode="Markdown")
        return

    # 1. Check hạn mức (Admin bypass)
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, t(user_id, "quota_exceeded", cap=cap), parse_mode="Markdown")
        return

    mark_rate_limit(user_id)
    loading_msg = bot.reply_to(message, t(user_id, "token_loading"))

    # 2. Xử lý Cookies và API trong thread ngầm để tránh webhook timeout
    def _process_token():
        max_retries = 5
        for attempt in range(max_retries):
            cookie_doc = db.get_active_cookie()
            if not cookie_doc:
                try:
                    bot.edit_message_text(t(user_id, "no_cookie"),
                                          chat_id=message.chat.id, message_id=loading_msg.message_id)
                except Exception:
                    pass
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

                # === BROWSERLESS CHECK & ACCOUNT SCRAPE (Every time) ===
                try:
                    bot.edit_message_text(t(user_id, "token_verifying"),
                                          chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="Markdown")
                except Exception:
                    pass
                
                account_info = None
                try:
                    account_info = account_scraper.scrape_account_info(link)
                    status = account_info.get("status", "active")
                except Exception as check_e:
                    # Nếu Browserless lỗi (ví dụ chưa config token), bỏ qua check và trả link
                    print(f"Browserless check error [{type(check_e).__name__}]: {check_e}")
                    traceback.print_exc()
                    status = "active"

                if status == "on_hold":
                    db.mark_cookie_as_dead(cookie_doc['netflix_id'])
                    save_dead_cookie_to_file(cookie_doc)
                    try:
                        bot.edit_message_text(t(user_id, "token_on_hold"),
                                              chat_id=message.chat.id, message_id=loading_msg.message_id)
                    except Exception:
                        pass
                    time.sleep(1)
                    continue
                elif status == "dead":
                    db.mark_cookie_as_dead(cookie_doc['netflix_id'])
                    save_dead_cookie_to_file(cookie_doc)
                    try:
                        bot.edit_message_text(t(user_id, "token_switching"),
                                              chat_id=message.chat.id, message_id=loading_msg.message_id)
                    except Exception:
                        pass
                    time.sleep(1)
                    continue
                # ========================================================

                # Admin KHÔNG bị tính lượt
                if not is_admin(user_id):
                    db.increment_link_usage(user_id, "token")

                user_lang = db.get_user_lang(user_id) or "vi"
                account_info_str = account_scraper.format_account_info(account_info, lang=user_lang) if account_info else "N/A"
                result_text = t(user_id, "token_success", link=link, expiry=expiry_str, account_info=account_info_str)
                if not is_admin(user_id):
                    real_remain = remain - 1 if remain > 0 else 0
                    result_text += t(user_id, "token_remain", remain=real_remain, cap=cap)

                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(
                    t(user_id, "btn_report_error"),
                    callback_data=f"err_{str(cookie_doc['_id'])}"
                ))

                try:
                    bot.edit_message_text(result_text, chat_id=message.chat.id,
                                          message_id=loading_msg.message_id, parse_mode="Markdown", reply_markup=markup)
                except Exception:
                    # Fallback: nếu Markdown parse lỗi, gửi lại không format
                    try:
                        bot.edit_message_text(result_text, chat_id=message.chat.id,
                                              message_id=loading_msg.message_id, reply_markup=markup)
                    except Exception:
                        pass
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
                try:
                    bot.edit_message_text(t(user_id, "token_error", error=e),
                                          chat_id=message.chat.id, message_id=loading_msg.message_id)
                except Exception:
                    pass
                return

        try:
            bot.edit_message_text(t(user_id, "token_all_dead"),
                                  chat_id=message.chat.id, message_id=loading_msg.message_id)
        except Exception:
            pass

    threading.Thread(target=_process_token).start()


@bot.message_handler(commands=['tv'])
def tv_command(message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "tv_syntax"), parse_mode="Markdown")
        return
    # Gộp tất cả phần sau /tv và chỉ giữ lại chữ số
    # Hỗ trợ: /tv 5464-6464, /tv 5464 6464, /tv 54646464
    raw_code = ' '.join(parts[1:])
    tv_code = ''.join(c for c in raw_code if c.isdigit())
    
    if len(tv_code) != 8:
        bot.reply_to(message, t(user_id, "tv_syntax"), parse_mode="Markdown")
        return
    username = message.from_user.username or message.from_user.first_name

    # 0. Rate limit check (30s cooldown)
    wait = check_rate_limit(user_id)
    if wait > 0:
        bot.reply_to(message, t(user_id, "rate_limit_cooldown", seconds=wait), parse_mode="Markdown")
        return

    # 1. Check hạn mức (Admin bypass)
    can_gen, remain, cap = db.can_generate_link(user_id, username)
    if not can_gen and not is_admin(user_id):
        bot.reply_to(message, t(user_id, "tv_quota_exceeded", cap=cap), parse_mode="Markdown")
        return

    mark_rate_limit(user_id)
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

                    # Thành công! Admin KHÔNG bị tính lượt
                    if not is_admin(user_id):
                        db.increment_link_usage(user_id, "tv")
                    remain_after = remain - 1 if not is_admin(user_id) else remain
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


# Khi Admin gửi video → hỏi lưu làm tutorial
_pending_tutorial = {}  # {chat_id: file_id}

@bot.message_handler(content_types=['video'])
def handle_video(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return  # User thường gửi video thì bỏ qua

    file_id = message.video.file_id
    _pending_tutorial[message.chat.id] = file_id

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton(t(user_id, "tutorial_save_yes"), callback_data="tut_yes"),
        InlineKeyboardButton(t(user_id, "tutorial_save_no"), callback_data="tut_no")
    )
    bot.reply_to(message, t(user_id, "tutorial_save_confirm"), parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ['tut_yes', 'tut_no'])
def handle_tutorial_confirm(call):
    user_id = call.from_user.id
    if not is_admin(user_id):
        return

    if call.data == "tut_no":
        _pending_tutorial.pop(call.message.chat.id, None)
        bot.edit_message_text(t(user_id, "tutorial_cancelled"),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)
        return

    file_id = _pending_tutorial.pop(call.message.chat.id, None)
    if file_id:
        db.set_tutorial_video(file_id)
        bot.edit_message_text(t(user_id, "tutorial_saved"),
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              parse_mode="Markdown")
    else:
        bot.edit_message_text("❌ Không tìm thấy video. Hãy gửi lại.",
                              chat_id=call.message.chat.id,
                              message_id=call.message.message_id)


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
            telebot.types.BotCommand("checkin", "Daily check-in"),
            telebot.types.BotCommand("ref", "Invite friends / Mời bạn bè"),
            telebot.types.BotCommand("profile", "Your profile / Thông tin"),
            telebot.types.BotCommand("guide", "🎬 Tutorial / Hướng dẫn"),
            telebot.types.BotCommand("language", "🌐 Language / Ngôn ngữ"),
            telebot.types.BotCommand("start", "Info & Help"),
            telebot.types.BotCommand("ping", "Check bot connection")
        ])
        # Menu vip cho Admin
        if ADMIN_ID:
            bot.set_my_commands([
                telebot.types.BotCommand("get_token", "Get Netflix login link"),
                telebot.types.BotCommand("tv", "TV Login (8-digit code)"),
                telebot.types.BotCommand("checkin", "Daily check-in"),
                telebot.types.BotCommand("ref", "Invite friends / Mời bạn bè"),
                telebot.types.BotCommand("profile", "Your profile / Thông tin"),
                telebot.types.BotCommand("guide", "🎬 Tutorial / Hướng dẫn"),
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
