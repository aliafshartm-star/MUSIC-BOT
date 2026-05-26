import telebot
from telebot import types
import sqlite3
import os
from flask import Flask
from threading import Thread
import yt_dlp

# ----------------- ایجاد یک سرور وب مجازی برای رندر -----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ----------------- دریافت تنظیمات از رندر -----------------
API_TOKEN = os.getenv('API_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')      
CHANNEL_LINK = os.getenv('CHANNEL_LINK')  
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))  

bot = telebot.TeleBot(API_TOKEN)

# ----------------- مدیریت دیتابیس (SQLite) -----------------
DB_NAME = 'bot_database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            lang TEXT DEFAULT 'FA',
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

def update_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lang = ? WHERE user_id = ?', (lang, user_id))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'FA'

def get_bot_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    conn.close()
    return total_users

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

init_db()

# ----------------- متون ربات -----------------
MESSAGES = {
    'FA': {
        'welcome': "سلام! به ربات حرفه‌ای دانلود آهنگ خوش آمدید. لطفا ابتدا عضو کانال ما شوید تا ربات برای شما فعال شود.",
        'join_btn': "📢 عضویت در کانال",
        'check_join_btn': "✅ عضو شدم (بررسی مجدد)",
        'not_joined': "❌ شما هنوز عضو کانال نشده‌اید! لطفاً ابتدا عضو شوید و سپس دکمه بررسی را بزنید.",
        'search_prompt': "🎵 لطفا نام خواننده یا آهنگ مورد نظر خود را (فارسی یا انگلیسی) ارسال کنید:",
        'back_btn': "🔙 برگشت به منوی اصلی",
        'searching': "🔍 در حال جستجوی آهنگ «{}» در واش‌موزیک... لطفا کمی صبور باشید.",
        'not_found': "😔 متأسفانه آهنگی یافت نشد یا در دانلود مشکلی پیش آمد.",
        'main_menu': "🏠 به منوی اصلی برگشتید. چه کاری می‌توانم برایتان انجام دهم؟",
        'uploading': "⚡ آهنگ پیدا شد! در حال آپلود و ارسال فایل صوتی..."
    },
    'EN': {
        'welcome': "Hello! Welcome to the professional Music Downloader Bot. Please join our channel first to activate the bot.",
        'join_btn': "📢 Join Channel",
        'check_join_btn': "✅ I have joined",
        'not_joined': "❌ You haven't joined the channel yet! Please join and try again.",
        'search_prompt': "🎵 Please send the artist name or song title (English or Persian):",
        'back_btn': "🔙 Back to Main Menu",
        'searching': "🔍 Searching for '{}'... Please wait.",
        'not_found': "😔 Sorry, no song was found or an error occurred.",
        'main_menu': "🏠 Back to main menu. How can I help you?",
        'uploading': "⚡ Song found! Uploading the audio file..."
    }
}

# ----------------- توابع کمکی ربات -----------------
def check_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception:
        return False

def get_lang_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("فارسی 🇮🇷", callback_data="lang_FA"),
               types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_EN"))
    return markup

def get_join_keyboard(lang):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(MESSAGES[lang]['join_btn'], url=CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton(MESSAGES[lang]['check_join_btn'], callback_data="check_join"))
    return markup

def get_main_keyboard(lang):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton(MESSAGES[lang]['back_btn']))
    return markup

def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 آمار کاربران", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 ارسال پیام همگانی", callback_data="admin_broadcast"))
    return markup

# ----------------- موتور جستجو و دانلود آهنگ -----------------
def download_music(query):
    # تنظیمات ابزار دانلودر برای تبدیل به ام‌پی‌تری کیفیت بالا
    ydl_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1:', # جستجوی اولین نتیجه در یوتیوب موزیک
        'outtmpl': 'music_file.%(ext)s', # نام موقت فایل ذخیره شده
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            # گرفتن عنوان واقعی آهنگ
            if 'entries' in info:
                title = info['entries'][0]['title']
            else:
                title = info.get('title', query)
            
            return 'music_file.mp3', title
    except Exception as e:
        print(f"Download Error: {e}")
        return None, None

# ----------------- هندلرهای ربات -----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    add_user(user_id, username)
    
    bot.send_message(
        message.chat.id, 
        "🌐 لطفا زبان خود را انتخاب کنید / Please choose your language:", 
        reply_markup=get_lang_keyboard()
    )

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 به پنل مدیریت ربات خوش آمدید:", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ شما دسترسی به این بخش را ندارید.")

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    user_id = call.from_user.id
    
    if call.data.startswith("lang_"):
        lang = call.data.split("_")[1]
        update_user_lang(user_id, lang)
        
        if check_membership(user_id):
            bot.send_message(user_id, MESSAGES[lang]['search_prompt'], reply_markup=get_main_keyboard(lang))
        else:
            bot.send_message(user_id, MESSAGES[lang]['welcome'], reply_markup=get_join_keyboard(lang))
            
    elif call.data == "check_join":
        lang = get_user_lang(user_id)
        if check_membership(user_id):
            bot.send_message(user_id, MESSAGES[lang]['search_prompt'], reply_markup=get_main_keyboard(lang))
        else:
            bot.answer_callback_query(call.id, MESSAGES[lang]['not_joined'], show_alert=True)

    elif call.data == "admin_stats" and user_id == ADMIN_ID:
        total = get_bot_stats()
        bot.send_message(ADMIN_ID, f"📊 **آمار ربات شما:**\n\n👥 کل کاربران ثبت شده: {total} نفر")
        
    elif call.data == "admin_broadcast" and user_id == ADMIN_ID:
        msg = bot.send_message(ADMIN_ID, "📢 لطفاً پیام خود را ارسال کنید (متن، عکس یا فیلم) یا برای لغو دستور `/cancel` را بفرستید:")
        bot.register_next_step_handler(msg, start_broadcasting)

def start_broadcasting(message):
    if message.text == '/cancel':
        bot.send_message(ADMIN_ID, "❌ عملیات لغو شد.")
        return
    
    users = get_all_users()
    success = 0
    failed = 0
    
    bot.send_message(ADMIN_ID, f"⏳ در حال ارسال پیام به {len(users)} کاربر... لطفا منتظر بمانید.")
    
    for u_id in users:
        try:
            bot.copy_message(chat_id=u_id, from_chat_id=ADMIN_ID, message_id=message.message_id)
            success += 1
        except Exception:
            failed += 1
            
    bot.send_message(ADMIN_ID, f"📢 **گزارش ارسال همگانی:**\n\n✅ ارسال موفق: {success}\n❌ ناموفق (بلاک شده): {failed}")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.chat.id
    lang = get_user_lang(user_id)
    
    if not check_membership(user_id):
        bot.send_message(user_id, MESSAGES[lang]['welcome'], reply_markup=get_join_keyboard(lang))
        return

    if message.text in [MESSAGES['FA']['back_btn'], MESSAGES['EN']['back_btn']]:
        bot.send_message(user_id, MESSAGES[lang]['main_menu'], reply_markup=get_main_keyboard(lang))
        bot.send_message(user_id, "🌐 Change Language / تغییر زبان:", reply_markup=get_lang_keyboard())
        return

    query = message.text
    # پیام در حال جستجو
    status_msg = bot.send_message(user_id, MESSAGES[lang]['searching'].format(query))
    
    # شروع پروسه واقعی دانلود و آپلود آهنگ
    file_path, song_title = download_music(query)
    
    if file_path and os.path.exists(file_path):
        try:
            bot.edit_message_text(MESSAGES[lang]['uploading'], user_id, status_msg.message_id)
            
            # ارسال فایل صوتی واقعی به تلگرام کاربر
            with open(file_path, 'rb') as audio:
                bot.send_audio(
                    chat_id=user_id, 
                    audio=audio, 
                    title=song_title, 
                    caption=f"🎵 {song_title}\n\n🆔 @{bot.get_me().username}"
                )
            
            # حذف فایل از روی هارد سرور برای پر نشدن حافظه رندر
            os.remove(file_path)
            bot.delete_message(user_id, status_msg.message_id)
            
        except Exception as e:
            print(f"Upload Error: {e}")
            bot.send_message(user_id, MESSAGES[lang]['not_found'])
    else:
        bot.send_message(user_id, MESSAGES[lang]['not_found'])

if __name__ == "__main__":
    keep_alive()
    print("Professional Music Bot is running on Web Service...")
    bot.infinity_polling()
