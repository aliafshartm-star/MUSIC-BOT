
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ChatMemberStatus
import asyncio
import yt_dlp
import os
import sqlite3

TOKEN = "PUT_BOT_TOKEN_HERE"
CHANNEL_USERNAME = "@YOUR_CHANNEL"
ADMIN_ID = 123456789

bot = Bot(TOKEN)
dp = Dispatcher()

user_lang = {}

# ---------------- DATABASE ----------------

db = sqlite3.connect("users.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

db.commit()

# ---------------- KEYBOARDS ----------------

def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="فارسی 🇮🇷", callback_data="lang_fa"),
            InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en")
        ]
    ])

def join_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}")],
        [InlineKeyboardButton(text="بررسی عضویت", callback_data="check_join")]
    ])

def main_menu(lang):
    if lang == "fa":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 دانلود آهنگ", callback_data="music")],
            [InlineKeyboardButton(text="📚 راهنما", callback_data="help")],
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Download Music", callback_data="music")],
            [InlineKeyboardButton(text="📚 Help", callback_data="help")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="back")]
        ])

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer(
        "لطفا زبان را انتخاب کنید\nChoose your language",
        reply_markup=language_keyboard()
    )

# ---------------- LANGUAGE ----------------

@dp.callback_query(F.data.startswith("lang_"))
async def choose_lang(call: CallbackQuery):
    lang = call.data.split("_")[1]
    user_lang[call.from_user.id] = lang

    await call.message.edit_text(
        "برای استفاده باید عضو کانال شوید"
        if lang == "fa"
        else "You must join channel first",
        reply_markup=join_keyboard()
    )

# ---------------- CHECK JOIN ----------------

@dp.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):

    lang = user_lang.get(call.from_user.id, "fa")

    try:
        member = await bot.get_chat_member(
            CHANNEL_USERNAME,
            call.from_user.id
        )

        if member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        ]:

            await call.message.edit_text(
                "به ربات خوش اومدی ❤️"
                if lang == "fa"
                else "Welcome ❤️",
                reply_markup=main_menu(lang)
            )

        else:
            raise Exception()

    except:
        await call.answer(
            "هنوز عضو کانال نشدی!"
            if lang == "fa"
            else "You are not joined!",
            show_alert=True
        )

# ---------------- HELP ----------------

@dp.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):

    lang = user_lang.get(call.from_user.id, "fa")

    text = (
        "اسم خواننده و آهنگ را ارسال کن 🎵\n\nمثال:\nShadmehr - Taghdir"
        if lang == "fa"
        else
        "Send singer and song name 🎵\n\nExample:\nAdele - Hello"
    )

    await call.message.edit_text(
        text,
        reply_markup=main_menu(lang)
    )

# ---------------- BACK ----------------

@dp.callback_query(F.data == "back")
async def back_menu(call: CallbackQuery):

    lang = user_lang.get(call.from_user.id, "fa")

    await call.message.edit_text(
        "منوی اصلی"
        if lang == "fa"
        else "Main Menu",
        reply_markup=main_menu(lang)
    )

# ---------------- MUSIC ----------------

@dp.callback_query(F.data == "music")
async def music_menu(call: CallbackQuery):

    lang = user_lang.get(call.from_user.id, "fa")

    await call.message.edit_text(
        "اسم آهنگ را ارسال کن 🎵"
        if lang == "fa"
        else "Send music name 🎵",
        reply_markup=main_menu(lang)
    )

# ---------------- DOWNLOAD ----------------

@dp.message()
async def download_music(message: Message):

    query = message.text

    lang = user_lang.get(message.from_user.id, "fa")

    wait = await message.answer(
        "درحال دانلود آهنگ..."
        if lang == "fa"
        else "Downloading..."
    )

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'music.%(ext)s',
        'quiet': True,
        'noplaylist': True
    }

    try:

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                f"ytsearch1:{query}",
                download=True
            )

            video = info['entries'][0]

            filename = ydl.prepare_filename(video)

        await message.answer_audio(
            audio=open(filename, 'rb'),
            title=video.get("title", "Music")
        )

        os.remove(filename)

        await wait.delete()

    except Exception as e:

        await wait.edit_text(
            "خطا در دانلود آهنگ ❌"
            if lang == "fa"
            else "Error downloading music ❌"
        )

# ---------------- STATS ----------------

@dp.message(F.text == "/stats")
async def stats(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")

    users = cursor.fetchone()[0]

    await message.answer(
        f"👥 Total Users: {users}"
    )

# ---------------- RUN ----------------

async def main():
    print("Bot Started...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
