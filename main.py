import asyncio
import os
import random
import time

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
)
from dotenv import load_dotenv

# ==== Ichki modullar ====
from ai_service import ask_ai
from config import OWNER_ID, REQUIRED_CHANNELS

try:
    from config import REWARD_ALMAZ
except Exception:
    REWARD_ALMAZ = 10  # fallback qiymat

from database import (
    init_db, add_user, get_user,
    is_verified, set_verified
)

# ==== ENV / Bot ====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylda topilmadi")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==== STATES ====
class CaptchaStates(StatesGroup):
    AWAIT = State()

# ==== GLOBALLAR ====
CAPTCHA: dict[int, int] = {}
BLOCKED_USERS: dict[int, float] = {}
AI_MODE: dict[int, bool] = {}

# ==== MENYU ====
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧠 AI bilan suhbat")],
        [KeyboardButton(text="💎 Almaz ishlash"), KeyboardButton(text="📊 Profilim")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="🛒 Akkount Bozor")],
        [KeyboardButton(text="💰 Almaz sotib olish"), KeyboardButton(text="📢 Reklama va yangiliklar")],
    ],
    resize_keyboard=True
)

# =================== START HANDLER ===================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Bloklangan foydalanuvchini tekshirish
    if user_id in BLOCKED_USERS and BLOCKED_USERS[user_id] > time.time():
        qoldi = int(BLOCKED_USERS[user_id] - time.time())
        await message.answer(f"🚫 Siz {qoldi} soniya davomida qayta urinish qilolmaysiz.")
        return

    # Agar foydalanuvchi bazada bo‘lmasa, qo‘shamiz
    user = await get_user(user_id)
    if not user:
        await add_user(user_id, message.from_user.full_name)
        print(f"🆕 Yangi foydalanuvchi qo‘shildi: {message.from_user.full_name} ({user_id})")

    # Majburiy obuna tekshiruvi
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                sub_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="❗️Obuna bo‘lish", url=f"https://t.me/{channel.replace('@','')}")],
                        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")]
                    ]
                )
                await message.answer(
                    "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:",
                    reply_markup=sub_kb
                )
                return
        except Exception as e:
            print(f"⚠️ Kanalni tekshirishda xato: {e}")
            continue

    # Captcha
    if not await is_verified(user_id):
        a = random.randint(1, 9)
        b = random.randint(1, 9)
        captcha = f"{a} + {b} = ?"
        CAPTCHA[user_id] = a + b
        await message.answer(
            f"🧩 Iltimos, quyidagi misolni yeching, botdan foydalanish uchun:\n\n<b>{captcha}</b>",
            parse_mode="HTML"
        )
        await state.set_state(CaptchaStates.AWAIT)
        return

    # Agar tasdiqlangan bo‘lsa
    await message.answer(
        "👋 Salom! Quyidagi menyudan kerakli bo‘limni tanlang 👇",
        reply_markup=main_menu
    )


# =================== CAPTCHA CHECK ===================
@dp.message(CaptchaStates.AWAIT)
async def check_captcha(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        javob = int(message.text.strip())
    except:
        await message.answer("⚠️ Faqat raqam kiriting!")
        return

    if user_id not in CAPTCHA:
        await message.answer("⚠️ Captcha muddati tugagan, /start ni qayta bosing.")
        await state.clear()
        return

    if javob == CAPTCHA[user_id]:
        await set_verified(user_id)
        del CAPTCHA[user_id]
        await state.clear()
        await message.answer(
            "✅ To‘g‘ri! Endi botdan foydalanishingiz mumkin.",
            reply_markup=main_menu
        )
    else:
        BLOCKED_USERS[user_id] = time.time() + 60
        await message.answer(
            "❌ Noto‘g‘ri javob! Siz 1 daqiqaga vaqtincha bloklandingiz."
        )

from database import (
    init_db,
    # users & refs
    add_user, get_user, add_almaz, get_leaderboard,
    get_ref_by, set_ref_by_if_empty, is_verified, set_verified,
    # admins & groups
    list_admins, is_admin, list_groups,
    # payments
    add_payment, get_pending_payments, confirm_payment,
    # dynamic texts
    get_dynamic_text, update_dynamic_text,
)

# ==== ENV / Bot ====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylda topilmadi")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# =================== GLOBAL STATES / CACHES ===================
class CaptchaStates(StatesGroup):
    AWAIT = State()

class AiStates(StatesGroup):
    ACTIVE = State()

CAPTCHA: dict[int, int] = {}
BLOCKED_USERS: dict[int, float] = {}  # user_id -> unblock_time (epoch seconds)
AI_MODE: dict[int, bool] = {}         # user_id -> True/False

# =================== MENUS ===================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧠 AI bilan suhbat")],
        [KeyboardButton(text="💎 Almaz ishlash"), KeyboardButton(text="📊 Profilim")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="🛒 Akkount Bozor")],
        [KeyboardButton(text="💰 Almaz sotib olish"), KeyboardButton(text="📢 Reklama va yangiliklar")],
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Foydalanuvchilar soni"),
            KeyboardButton(text="💎 Almaz berish")
        ],
        [
            KeyboardButton(text="📰 Reklama/Yangilik sozlash"),
            KeyboardButton(text="💰 Almaz sotib olish matni")
        ],
        [
            KeyboardButton(text="📋 Guruhlar ro‘yxati"),
            KeyboardButton(text="📢 Reklama yuborish")
        ],
        [
            KeyboardButton(text="⬅️ Chiqish")
        ],
    ],
    resize_keyboard=True
)


# =================== HELPERS ===================
async def setup_bot_commands():
    cmds = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="admin", description="Admin panel"),
    ]
    await bot.set_my_commands(cmds)

async def check_subscription(user_id: int) -> list[str]:
    """
    REQUIRED_CHANNELS ro‘yxatidagi kanallar a'zoligini tekshiradi.
    A'zo bo‘lmaganlar ro‘yxatini qaytaradi (username/ID formatida).
    """
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "administrator", "creator"):
                not_subscribed.append(channel)
        except Exception:
            not_subscribed.append(channel)
    return not_subscribed

def sub_required_markup(not_sub):
    buttons = [
        [InlineKeyboardButton(text=f"📢 Kanal {i+1}", url=f"https://t.me/{ch.lstrip('@')}")]
        for i, ch in enumerate(not_sub)
    ]
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subs")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def positive_arith():
    """Manfiy natijasiz oddiy + yoki − misol qaytaradi: (a, op, b, answer)."""
    a, b = random.randint(1, 9), random.randint(1, 9)
    op = random.choice(["+", "-"])
    if op == "-" and a < b:
        a, b = b, a
    ans = a + b if op == "+" else a - b
    return a, op, b, ans

def is_blocked(user_id: int) -> tuple[bool, int]:
    """(blocked?, remaining_seconds)"""
    until = BLOCKED_USERS.get(user_id)
    if until is None:
        return False, 0
    remaining = int(until - time.time())
    return (remaining > 0), max(remaining, 0)

# =================== SUBS CALLBACK ===================
@dp.callback_query(F.data == "check_subs")
async def recheck_subs(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    not_sub = await check_subscription(user_id)
    if not_sub:
        text = (
            "⚠️ <b>Hali barcha kanallarga obuna bo‘lmagansiz.</b>\n\n"
            "Iltimos, quyidagi rasmiy kanallarimizga obuna bo‘ling va qayta tekshiring 👇"
        )
        return await callback.message.edit_text(text, parse_mode="HTML", reply_markup=sub_required_markup(not_sub))

    await callback.message.edit_text("✅ Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin.", parse_mode="HTML")
    # /start oqimini davom ettiramiz
    await cmd_start(callback.message, state)

# =================== /start (PRIVATE ONLY) ===================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Guruhda /start ishlamasin — menyu chiqishi bagini yopamiz
    if message.chat.type != "private":
        return

    # Agar bloklangan bo‘lsa
    blocked, remain = is_blocked(user_id)
    if blocked:
        return await message.answer(
            f"🚫 Siz vaqtincha bloklangansiz.\n⏳ {remain} soniyadan so‘ng yana urinib ko‘ring."
        )

    # Majburiy obuna
    not_sub = await check_subscription(user_id)
    if not_sub:
        text = (
            "📣 <b>Hurmatli foydalanuvchi!</b>\n\n"
            "Botdan to‘liq foydalanish uchun quyidagi kanallarga a’zo bo‘ling.\n"
            "Obuna bo‘lgach, pastdagi <b>✅ Obuna bo‘ldim</b> tugmasini bosing."
        )
        return await message.answer(text, parse_mode="HTML", reply_markup=sub_required_markup(not_sub))

    # Foydalanuvchini ro‘yxatdan o‘tkazamiz + referral
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    await add_user(user_id, message.from_user.username or "Noma’lum", ref_id)
    await set_ref_by_if_empty(user_id, ref_id)

    # Agar verified bo‘lmasa — captcha
    if not await is_verified(user_id):
        a, op, b, ans = positive_arith()
        CAPTCHA[user_id] = ans
        await state.set_state(CaptchaStates.AWAIT)
        return await message.answer(
            "🧮 <b>Captcha tekshiruvi</b>\n\n"
            "Quyidagi misolni yeching va faqat javobni yuboring:\n"
            f"<b>{a} {op} {b} = ?</b>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove()
        )

    # Verified foydalanuvchi — menyu
    AI_MODE[user_id] = False
    await message.answer(
        f"👋 Salom, {message.from_user.first_name}!\nQuyidagi menyudan tanlang 👇",
        reply_markup=main_menu
    )

# =================== CAPTCHA CHECK ===================
@dp.message(CaptchaStates.AWAIT)
async def handle_captcha(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.chat.type != "private":
        return

    # Blok holati
    blocked, remain = is_blocked(user_id)
    if blocked:
        return await message.answer(f"🚫 Siz 1 daqiqaga bloklangansiz.\n⏳ {remain} soniya qoldi.")

    text = (message.text or "").strip()
    if not text.isdigit():
        return await message.answer("❌ Iltimos, faqat raqam kiriting.")

    correct = CAPTCHA.get(user_id)
    if correct is None:
        await state.clear()
        return await message.answer("⚠️ Captcha muddati tugagan. /start yuboring.")

    if int(text) == correct:
        await set_verified(user_id)
        CAPTCHA.pop(user_id, None)
        await state.clear()

        # Referral mukofot — faqat verified bo‘lganda
        ref_by = await get_ref_by(user_id)
        if ref_by and ref_by != user_id:
            await add_almaz(ref_by, REWARD_ALMAZ)
            try:
                await bot.send_message(
                    ref_by,
                    f"🎉 Siz taklif qilgan foydalanuvchi muvaffaqiyatli ro‘yxatdan o‘tdi!\n"
                    f"💎 Sizga {REWARD_ALMAZ} Almaz qo‘shildi."
                )
            except Exception:
                pass

        return await message.answer(
            "✅ To‘g‘ri javob! Endi botdan bemalol foydalanishingiz mumkin.",
            reply_markup=main_menu
        )

    # Xato — 1 daqiqa blok
    CAPTCHA.pop(user_id, None)
    BLOCKED_USERS[user_id] = time.time() + 60
    await state.clear()
    await message.answer(
        "🚫 <b>Noto‘g‘ri javob!</b>\n"
        "Siz 1 daqiqa muddatga bloklandingiz.\n"
        "⏳ 1 daqiqadan so‘ng /start yuborib qayta urinib ko‘ring.",
        parse_mode="HTML"
    )

# =================== HELP ===================
@dp.message(Command("help"))
async def user_help(message: Message):
    await message.answer(
        "🆘 <b>Yordam</b>\n\n"
        "🧠 AI bilan suhbat — Sun’iy intellekt bilan muloqot\n"
        "💎 Almaz ishlash — Do‘st chaqirib Almaz olish\n"
        "📊 Profilim — Profil ma’lumotlari\n"
        "🏆 Reyting — Top 15 foydalanuvchi\n"
        "🛒 Akkount Bozor — Tez orada\n"
        "💰 Almaz sotib olish — To‘lov variantlari\n"
        "📢 Reklama va yangiliklar — E’lonlar\n",
        parse_mode="HTML"
    )

# =================== AI MODE (PRIVATE) ===================
@dp.message(F.text == "🧠 AI bilan suhbat")
async def enter_ai_mode(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return
    AI_MODE[message.from_user.id] = True
    await state.set_state(AiStates.ACTIVE)
    await message.answer(
        "🤖 AI rejimi yoqildi. Savolingizni yozing.\n"
        "Chiqish uchun ⬅️ Orqaga tugmasini bosing.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="⬅️ Orqaga")]],
            resize_keyboard=True
        )
    )

@dp.message(F.text == "⬅️ Orqaga", AiStates.ACTIVE)
async def exit_ai_mode(message: Message, state: FSMContext):
    AI_MODE[message.from_user.id] = False
    await state.clear()
    await message.answer("🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu)

@dp.message(AiStates.ACTIVE)
async def ai_chat(message: Message, state: FSMContext):
    text = message.text or ""
    await message.answer("💭 Javob tayyorlanmoqda...")
    try:
        reply = await ask_ai(text)
        await message.answer(reply)
    except Exception:
        await message.answer("⚠️ AI bilan aloqa vaqtida xatolik yuz berdi.")

# =================== AI IN GROUP ===================
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def group_ai_handler(message: Message):
    # faqat botga reply qilinsa yoki @username bilan tilga olinganda javob beradi
    me = await bot.get_me()
    mentioned = (message.text and f"@{me.username}" in message.text)
    replied = (message.reply_to_message and message.reply_to_message.from_user.id == me.id)
    if mentioned or replied:
        try:
            reply = await ask_ai(message.text or "")
            await message.reply(reply)
        except Exception:
            pass

# =================== USER MENU: PROFILE / LEADERBOARD / EARN / NEWS / MARKET / BUY ===================
@dp.message(F.text == "📊 Profilim")
async def show_profile(message: Message):
    if message.chat.type != "private":
        return
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username or "Noma’lum")
        user = await get_user(message.from_user.id)
    almaz = user[3] if len(user) > 3 else 0
    me = await bot.get_me()
    await message.answer(
        f"👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"👤 Username: @{user[2] or 'Anonim'}\n"
        f"💎 Almaz: <b>{almaz}</b>\n\n"
        f"🔗 Taklif havolangiz:\n"
        f"https://t.me/{me.username}?start={message.from_user.id}",
        parse_mode="HTML"
    )

@dp.message(F.text == "🏆 Reyting")
async def show_leaderboard(message: Message):
    leaders = await get_leaderboard()
    if not leaders:
        return await message.answer("📉 Hozircha reyting bo‘sh.")
    text = "🏆 <b>Top 15 foydalanuvchi</b>\n\n"
    for i, (username, almaz) in enumerate(leaders[:15], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
        text += f"{medal} @{username or 'Anonim'} — 💎 {almaz}\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💎 Almaz ishlash")
async def earn_almaz(message: Message):
    me = await bot.get_me()
    await message.answer(
        "💎 <b>Almaz ishlash usullari</b>\n\n"
        f"1️⃣ Do‘stingizni taklif qiling — u botga to‘liq kirsa sizga {REWARD_ALMAZ} Almaz beriladi.\n"
        f"2️⃣ Taklif havolangiz:\n"
        f"<code>https://t.me/{me.username}?start={message.from_user.id}</code>\n\n"
        "🎁 Cheksiz miqdorda do‘st taklif qilishingiz mumkin!",
        parse_mode="HTML"
    )

@dp.message(F.text == "📢 Reklama va yangiliklar")
async def show_announcements(message: Message):
    text = await get_dynamic_text("news")
    if not text:
        text = "📭 Hozircha yangiliklar yo‘q."
    await message.answer(f"📰 <b>So‘nggi yangiliklar</b>\n\n{text}", parse_mode="HTML")

@dp.message(F.text == "🛒 Akkount Bozor")
async def account_market_menu(message: Message):
    await message.answer(
        "🛒 <b>Akkount Bozor</b>\n\n"
        "Bu bo‘lim tez orada ishga tushadi. Akkount sotish/sotib olish uchun admin tasdiqlovchi panel qo‘shamiz.",
        parse_mode="HTML"
    )

@dp.message(F.text == "💰 Almaz sotib olish")
async def buy_almaz(message: Message):
    text = await get_dynamic_text("almaz_buy")
    if not text:
        text = (
            "💰 <b>Almaz sotib olish</b>\n\n"
            "1️⃣ 10 000 so‘m → 100 Almaz\n"
            "2️⃣ 25 000 so‘m → 300 Almaz\n"
            "3️⃣ 40 000 so‘m → 500 Almaz\n\n"
            "💳 To‘lov: Click / Payme / Telegram Stars\n"
            "Raqam: <b>+998 99 123 45 67</b>\n\n"
            "To‘lovdan so‘ng quyidagicha yozing:\n"
            "<code>10000 123456789</code> (summa + ID)"
        )
    await message.answer(text, parse_mode="HTML")

# =================== ADMIN PANEL ===================
class TextEdit(StatesGroup):
    new_text = State()
    section = State()

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return await message.answer("🚫 Siz admin emassiz.")
    await message.answer("👑 <b>Admin panel</b>", parse_mode="HTML", reply_markup=admin_menu)

@dp.message(F.text == "📊 Foydalanuvchilar soni")
async def user_count(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    async with aiosqlite.connect("bot_data.db") as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
    await message.answer(f"📈 Jami foydalanuvchilar: <b>{total}</b>", parse_mode="HTML")

@dp.message(F.text == "📋 Guruhlar ro‘yxati")
async def show_groups(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    groups = await list_groups()
    if not groups:
        return await message.answer("📭 Bot hech qanday guruhda mavjud emas.")
    text = "📋 <b>Bot mavjud bo‘lgan guruhlar:</b>\n\n"
    for gid, title in groups:
        text += f"🔹 {title} — <code>{gid}</code>\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📰 Reklama/Yangilik sozlash")
async def edit_news(message: Message, state: FSMContext):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    await state.set_state(TextEdit.new_text)
    await state.update_data(section="news")
    await message.answer("📰 Yangi yangilik matnini yuboring:", reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == "💰 Almaz sotib olish matni")
async def edit_buy_text(message: Message, state: FSMContext):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    await state.set_state(TextEdit.new_text)
    await state.update_data(section="almaz_buy")
    await message.answer("💰 Almaz sotib olish bo‘limi uchun yangi matnni yuboring:", reply_markup=ReplyKeyboardRemove())

@dp.message(TextEdit.new_text)
async def save_dynamic_text(message: Message, state: FSMContext):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    data = await state.get_data()
    section = data.get("section")
    await update_dynamic_text(section, message.text)
    await state.clear()
    await message.answer("✅ Matn muvaffaqiyatli yangilandi.", reply_markup=admin_menu)

@dp.message(F.text == "📢 Reklama yuborish")
async def ask_broadcast(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    await message.answer("📢 Reply qilib reklama xabarini yuboring.")

@dp.message(F.reply_to_message)
async def broadcast_message(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    async with aiosqlite.connect("bot_data.db") as db:
        cursor = await db.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()
    sent = 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ {sent} foydalanuvchiga reklama yuborildi.")

@dp.message(F.text == "💎 Almaz berish")
async def give_almaz_prompt(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    await message.answer("💎 Foydalanuvchi ID va miqdorni kiriting (masalan: <code>123456789 50</code>)", parse_mode="HTML")

@dp.message(lambda m: (m.text or "").strip().count(" ") == 1 and all(p.isdigit() for p in (m.text or "").split()))
async def handle_give_almaz(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    uid, amount = map(int, (message.text or "").split())
    await add_almaz(uid, amount)
    await message.answer(f"✅ <code>{uid}</code> foydalanuvchiga {amount} Almaz qo‘shildi.", parse_mode="HTML")

@dp.message(F.text == "⬅️ Chiqish")
async def exit_admin(message: Message):
    if not (message.from_user.id == OWNER_ID or await is_admin(message.from_user.id)):
        return
    await message.answer("👋 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardRemove())

# =================== GROUP TRACKING ===================
@dp.my_chat_member(F.new_chat_member.status == "member")
async def bot_added_to_group(event):
    chat = event.chat
    # Sizning database.py ichida add_group mavjud deb faraz qilingan — agar bo'lmasa, olib tashlang.
    try:
        from database import add_group
        await add_group(chat.id, chat.title or "Noma’lum")
    except Exception:
        pass
    print(f"✅ Bot yangi guruhga qo‘shildi: {chat.title}")

# =================== BOOTSTRAP ===================
async def main():
    print("📂 Baza tayyorlanmoqda...")
    await init_db()
    await setup_bot_commands()
    print("✅ Baza tayyor bo‘ldi (users, admins, groups, payments)")
    print("🚀 Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
