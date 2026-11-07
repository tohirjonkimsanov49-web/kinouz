
import asyncio
import json
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramNotFound
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ═══════════════════════════════════════════════════════════
# 📝 LOGGING
# ═══════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# ⚙️ CONFIG
# ═══════════════════════════════════════════════════════════
#BOT_TOKEN = "8619863394:AAGsndNgj27TjdCPhAEAICBC9AB4Gms-u-g"
INITIAL_ADMIN = 1776898092 #men
#INITIAL_ADMIN = 5235660635

# File paths
DATA_DIR = "data"
STATUS_FILE = DATA_DIR + "/status.json"
MOVIES_FILE = DATA_DIR + "/movies.json"
ADMINS_FILE = DATA_DIR + "/admins.json"
PREMIUM_FILE = DATA_DIR + "/premium.json"
CHANNELS_FILE = DATA_DIR + "/channels.json"
USERS_FILE = DATA_DIR + "/users.json"
BLOCKED_FILE = DATA_DIR + "/blocked.json"
STATS_FILE = DATA_DIR + "/stats.json"
TARIFFS_FILE = DATA_DIR + "/tariffs.json"

# Default Tariffs (keyinchalik ozgartiriladi)
DEFAULT_TARIFFS = {
    "t1": {"name": "1 hafta", "price": "45000", "days": 7},
    "t2": {"name": "1 oy", "price": "100000", "days": 30},
    "t3": {"name": "1 yil", "price": "450000", "days": 365}
}

# Payment info
PAYMENT_TEXT = (
    "💳 <b>TOLOV MALUMOTLARI</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🏦 <b>Uzcard:</b>\n"
    "<code>5614681282862568</code>\n\n"
    "🏦 <b>Humo:</b>\n"
    "<code>9860012114370609</code>\n\n"
    
    
    "📸 Tolovdan song <b>chek rasmini</b> yuboring"
)

# ═══════════════════════════════════════════════════════════
# 🗄️ DATABASE
# ═══════════════════════════════════════════════════════════
class Database:
    def __init__(self):
        self._ensure_data_dir()
        self._cache = {}
        self._load_all()
    
    def _ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def _load_json(self, filepath, default=None):
        if default is None:
            default = {}
        if not os.path.exists(filepath):
            self._save_json(filepath, default)
            return default.copy() if isinstance(default, (dict, list)) else default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default.copy() if isinstance(default, (dict, list)) else default
    
    def _save_json(self, filepath, data):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("JSON save error: " + str(e))
    
    def _load_all(self):
        self._cache = {
            "users": self._load_json(USERS_FILE, {}),
            "movies": self._load_json(MOVIES_FILE, {}),
            "admins": self._load_json(ADMINS_FILE, [INITIAL_ADMIN]),
            "premium": self._load_json(PREMIUM_FILE, {}),
            "channels": self._load_json(CHANNELS_FILE, []),
            "blocked": self._load_json(BLOCKED_FILE, []),
            "status": self._load_json(STATUS_FILE, {}),
            "stats": self._load_json(STATS_FILE, {"total_views": 0, "total_searches": 0}),
            "tariffs": self._load_json(TARIFFS_FILE, DEFAULT_TARIFFS)
        }
        if INITIAL_ADMIN not in self._cache["admins"]:
            self._cache["admins"].append(INITIAL_ADMIN)
            self.save("admins")
    
    def get(self, key):
        return self._cache.get(key, {})
    
    def set(self, key, data):
        self._cache[key] = data
        self.save(key)
    
    def save(self, key):
        file_map = {
            "users": USERS_FILE, "movies": MOVIES_FILE, "admins": ADMINS_FILE,
            "premium": PREMIUM_FILE, "channels": CHANNELS_FILE, "blocked": BLOCKED_FILE,
            "status": STATUS_FILE, "stats": STATS_FILE, "tariffs": TARIFFS_FILE
        }
        if key in file_map:
            self._save_json(file_map[key], self._cache[key])
    
    def save_all(self):
        for key in self._cache:
            self.save(key)

db = Database()

# ═══════════════════════════════════════════════════════════
# 🎨 UI
# ═══════════════════════════════════════════════════════════
def get_tariffs():
    return db.get("tariffs")

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Bepul obuna", callback_data="free_sub")],
        [InlineKeyboardButton(text="⭐ Premium obuna", callback_data="premium_sub")],
        [InlineKeyboardButton(text="🔍 Kino qidirish", callback_data="search_movie")],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="user_stats"),
            InlineKeyboardButton(text="❓ Yordam", callback_data="help")
        ]
    ])

def back_kb(callback="back_main"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Ortga", callback_data=callback)]
    ])

def channels_kb(channels):
    buttons = []
    for ch in channels:
        ch_name = ch.replace("@", "")
        buttons.append([InlineKeyboardButton(text="📢 " + ch, url="https://t.me/" + ch_name)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    buttons.append([InlineKeyboardButton(text="◀️ Ortga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tariffs_kb():
    tariffs = get_tariffs()
    buttons = []
    for key, t in tariffs.items():
        price_fmt = format_price(t["price"])
        text = "💎 " + t["name"] + " — " + price_fmt + " som"
        buttons.append([InlineKeyboardButton(text=text, callback_data="tariff_" + key)])
    buttons.append([InlineKeyboardButton(text="◀️ Ortga", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def movie_kb(code):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Ulashish", switch_inline_query=code)],
        [
            InlineKeyboardButton(text="⭐ Sevimli", callback_data="fav_" + code),
            InlineKeyboardButton(text="📥 Yuklab olish", callback_data="dl_" + code)
        ],
        [InlineKeyboardButton(text="🔍 Boshqa kino", callback_data="search_movie")]
    ])

def admin_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Foydalanuvchilar"), KeyboardButton(text="👨‍💼 Adminlar")],
        [KeyboardButton(text="📢 Kanallar"), KeyboardButton(text="💎 Premium")],
        [KeyboardButton(text="🎬 Kinolar"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="📤 Broadcast"), KeyboardButton(text="⚙️ Sozlamalar")],
        [KeyboardButton(text="🚪 Chiqish")]
    ], resize_keyboard=True)

def users_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 User statistika"), KeyboardButton(text="🔍 User qidirish")],
        [KeyboardButton(text="🔴 Bloklash"), KeyboardButton(text="🟢 Blokdan olish")],
        [KeyboardButton(text="📋 Bloklangan royxat")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)

def movies_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Kino qoshish"), KeyboardButton(text="➖ Kino ochirish")],
        [KeyboardButton(text="📋 Kinolar royxati"), KeyboardButton(text="🔍 Kino qidirish")],
        [KeyboardButton(text="📊 Top kinolar")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)

def broadcast_panel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Oddiy xabar"), KeyboardButton(text="📸 Rasm bilan")],
        [KeyboardButton(text="🎬 Video bilan"), KeyboardButton(text="📄 Fayl bilan")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)

def premium_panel_kb():
    """Premium boshqaruv paneli"""
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👑 Premium royxati")],
        [KeyboardButton(text="📨 Premium xabar"), KeyboardButton(text="➕ Premium berish")],
        [KeyboardButton(text="💰 Narxlarni ozgartirish"), KeyboardButton(text="➖ Premium olish")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="❌ Bekor qilish")]
    ], resize_keyboard=True)

# ═══════════════════════════════════════════════════════════
# 🛡️ HELPERS
# ═══════════════════════════════════════════════════════════
def is_admin(user_id):
    admins = db.get("admins")
    return int(user_id) in [int(x) for x in admins]

def is_blocked(user_id):
    blocked = db.get("blocked")
    return int(user_id) in [int(x) for x in blocked]

def get_user_status(user_id):
    status = db.get("status")
    return status.get(str(user_id), {"status": None, "premium_until": None})

def set_user_status(user_id, status, premium_until=None):
    data = db.get("status")
    data[str(user_id)] = {"status": status, "premium_until": premium_until}
    db.set("status", data)

def check_premium(user_id):
    s = get_user_status(user_id)
    if s.get("status") != "premium":
        return False
    until = s.get("premium_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now()
    except:
        return False

def register_user(user_id, username=None, full_name=None):
    users = db.get("users")
    uid = str(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in users:
        users[uid] = {
            "user_id": user_id, "username": username, "full_name": full_name,
            "join_date": today, "last_active": today, "active": True,
            "movies_watched": 0, "favorites": []
        }
    else:
        users[uid]["last_active"] = today
        users[uid]["active"] = True
    db.set("users", users)

def inc_views(code):
    movies = db.get("movies")
    if code in movies:
        movies[code]["views"] = movies[code].get("views", 0) + 1
        db.set("movies", movies)

def fmt_num(n):
    if n >= 1000000:
        return str(round(n/1000000, 1)) + "M"
    elif n >= 1000:
        return str(round(n/1000, 1)) + "K"
    return str(n)

def format_price(price):
    """Narxni formatlash: 45000 -> 45,000"""
    try:
        p = int(str(price).replace(",", "").replace(" ", ""))
        return "{:,}".format(p).replace(",", ",")
    except:
        return str(price)

def time_left(exp_str):
    try:
        exp = datetime.fromisoformat(exp_str)
        rem = exp - datetime.now()
        if rem.total_seconds() <= 0:
            return "Tugagan"
        d = rem.days
        h = rem.seconds // 3600
        m = (rem.seconds % 3600) // 60
        if d > 0:
            return str(d) + " kun " + str(h) + " soat"
        elif h > 0:
            return str(h) + " soat " + str(m) + " daq"
        return str(m) + " daqiqa"
    except:
        return "Nomalum"

def get_active_premium_users():
    """Faol premium foydalanuvchilar royxati"""
    premium = db.get("premium")
    active = {}
    for uid, p in premium.items():
        try:
            exp = datetime.strptime(p.get("expires", "2000-01-01 00:00"), "%Y-%m-%d %H:%M")
            if exp > datetime.now():
                active[uid] = p
        except:
            pass
    return active

def get_stats():
    users = db.get("users")
    movies = db.get("movies")
    premium = db.get("premium")
    
    total_users = len(users)
    active = sum(1 for u in users.values() if u.get("active"))
    total_movies = len(movies)
    total_views = sum(m.get("views", 0) for m in movies.values())
    
    active_prem = len(get_active_premium_users())
    
    return {
        "total_users": total_users, "active_users": active,
        "total_movies": total_movies, "total_views": total_views,
        "active_premium": active_prem
    }

# ═══════════════════════════════════════════════════════════
# 🤖 BOT
# ═══════════════════════════════════════════════════════════
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# ═══════════════════════════════════════════════════════════
# 📋 STATES
# ═══════════════════════════════════════════════════════════
class AddMovie(StatesGroup):
    video = State()
    name = State()
    lang = State()
    year = State()
    genre = State()
    code = State()

class DelMovie(StatesGroup):
    code = State()

class SearchMovie(StatesGroup):
    query = State()

class PremiumPay(StatesGroup):
    check = State()

class Broadcast(StatesGroup):
    msg = State()

class PremiumBroadcast(StatesGroup):
    msg = State()

class BlockUser(StatesGroup):
    uid = State()

class UnblockUser(StatesGroup):
    uid = State()

class AdminAdd(StatesGroup):
    uid = State()

class AdminDel(StatesGroup):
    uid = State()

class ChannelAdd(StatesGroup):
    ch = State()

class SendMsg(StatesGroup):
    msg = State()

class GivePremium(StatesGroup):
    uid = State()
    tariff = State()

class RemovePremium(StatesGroup):
    uid = State()

class EditTariff(StatesGroup):
    select = State()
    price = State()

# ═══════════════════════════════════════════════════════════
# 🎬 HANDLERS
# ═══════════════════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    
    if is_blocked(uid):
        await message.answer("🚫 Siz bloklangansiz!")
        return
    
    register_user(uid, message.from_user.username, message.from_user.full_name)
    
    if check_premium(uid):
        s = get_user_status(uid)
        left = time_left(s.get("premium_until", ""))
        text = "👑 <b>Premium foydalanuvchi</b>\n\n⏰ Qolgan: <b>" + left + "</b>\n\n🎬 Kino kodini yuboring:"
        await message.answer(text, reply_markup=back_kb())
        return
    
    us = get_user_status(uid)
    if us.get("status") == "free":
        await message.answer("🎬 Xush kelibsiz!\n\nKino kodini yuboring:", reply_markup=main_menu_kb())
        return
    
    name = message.from_user.first_name
    text = (
        "🎬 <b>KINO BOT PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Salom, <b>" + name + "</b>! 👋\n\n"
        "Botdan foydalanish uchun obuna tanlang:\n\n"
        "🔓 <b>Bepul</b> — Kanallarga obuna\n"
        "⭐ <b>Premium</b> — Kanalsiz\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(text, reply_markup=main_menu_kb())

@dp.callback_query(F.data == "back_main")
async def cb_back(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("🎬 <b>KINO BOT PRO</b>\n\nTanlang:", reply_markup=main_menu_kb())
    await query.answer()

@dp.callback_query(F.data == "free_sub")
async def cb_free(query: CallbackQuery):
    channels = db.get("channels")
    if not channels:
        set_user_status(query.from_user.id, "free")
        await query.message.edit_text("✅ Kanallar yoq.\n\n🎬 Kino kodini yuboring:", reply_markup=back_kb())
        await query.answer()
        return
    text = "📢 <b>BEPUL OBUNA</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\nKanallarga obuna boling:"
    await query.message.edit_text(text, reply_markup=channels_kb(channels))
    await query.answer()

@dp.callback_query(F.data == "check_sub")
async def cb_check(query: CallbackQuery):
    uid = query.from_user.id
    channels = db.get("channels")
    not_sub = []
    for ch in channels:
        try:
            m = await bot.get_chat_member(chat_id=ch, user_id=uid)
            if m.status not in ("member", "administrator", "creator"):
                not_sub.append(ch)
        except:
            continue
    if not_sub:
        t = "❌ Obuna bolmagansiz:\n\n" + "\n".join(["• " + c for c in not_sub])
        await query.answer(t, show_alert=True)
        return
    set_user_status(uid, "free")
    await query.message.edit_text("✅ Obuna tasdiqlandi!\n\n🎬 Kino kodini yuboring:", reply_markup=back_kb())
    await query.answer("✅ Tayyor!")

@dp.callback_query(F.data == "premium_sub")
async def cb_premium(query: CallbackQuery):
    text = (
        "💎 <b>PREMIUM OBUNA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Afzalliklar:\n"
        "✅ Kanalsiz\n"
        "✅ Reklama yoq\n"
        "✅ Tez yuklanish\n\n"
        "Tarifni tanlang:"
    )
    await query.message.edit_text(text, reply_markup=tariffs_kb())
    await query.answer()

@dp.callback_query(F.data.startswith("tariff_"))
async def cb_tariff(query: CallbackQuery, state: FSMContext):
    key = query.data.replace("tariff_", "")
    tariffs = get_tariffs()
    t = tariffs.get(key)
    if not t:
        await query.answer("❌ Topilmadi!", show_alert=True)
        return
    await state.set_state(PremiumPay.check)
    await state.update_data(tariff=key)
    price_fmt = format_price(t["price"])
    text = "💎 <b>Tarif: " + t["name"] + "</b>\n💰 <b>Narx: " + price_fmt + " som</b>\n\n" + PAYMENT_TEXT
    await query.message.edit_text(text, reply_markup=back_kb())
    await query.answer()

@dp.message(F.photo, PremiumPay.check)
async def pay_check(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data.get("tariff")
    tariffs = get_tariffs()
    t = tariffs.get(key, {})
    admins = db.get("admins")
    
    uname = message.from_user.username or "yoq"
    fname = str(message.from_user.full_name)
    tname = t.get("name", "Nomalum")
    tprice = format_price(t.get("price", "???"))
    
    caption = (
        "💰 <b>YANGI TOLOV!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 User: <code>" + str(message.from_user.id) + "</code>\n"
        "📝 Username: @" + uname + "\n"
        "👤 Ism: " + fname + "\n"
        "💎 Tarif: " + tname + "\n"
        "💰 Summa: " + tprice + " som"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="approve_" + str(message.from_user.id) + "_" + key)],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data="reject_" + str(message.from_user.id))],
        [InlineKeyboardButton(text="💬 Xabar", callback_data="sendmsg_" + str(message.from_user.id))]
    ])
    
    for aid in admins:
        try:
            await bot.send_photo(aid, message.photo[-1].file_id, caption=caption, reply_markup=kb)
        except:
            pass
    
    await message.answer("✅ Chek qabul qilindi!\n\n⏳ Admin tekshirmoqda...")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def cb_approve(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin emassiz!", show_alert=True)
        return
    
    parts = query.data.split("_")
    uid = int(parts[1])
    key = parts[2] if len(parts) > 2 else "t1"
    tariffs = get_tariffs()
    t = tariffs.get(key, {"days": 7, "name": "1 hafta"})
    
    exp = datetime.now() + timedelta(days=t["days"])
    exp_str = exp.strftime("%Y-%m-%d %H:%M")
    
    prem = db.get("premium")
    prem[str(uid)] = {"user_id": uid, "tariff": key, "start": datetime.now().strftime("%Y-%m-%d %H:%M"), "expires": exp_str}
    db.set("premium", prem)
    set_user_status(uid, "premium", exp.isoformat())
    
    try:
        msg = "🎉 <b>Premium aktivlashtirildi!</b>\n\n💎 Tarif: <b>" + t["name"] + "</b>\n⏰ Tugash: <b>" + exp_str + "</b>\n\n🎬 Kino kodini yuboring!"
        await bot.send_message(uid, msg)
    except:
        pass
    
    await query.message.edit_caption(query.message.caption + "\n\n✅ <b>TASDIQLANDI</b>", reply_markup=None)
    await query.answer("✅ Tayyor!")

@dp.callback_query(F.data.startswith("reject_"))
async def cb_reject(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin emassiz!", show_alert=True)
        return
    uid = int(query.data.split("_")[1])
    try:
        await bot.send_message(uid, "❌ <b>Tolov rad etildi!</b>\n\nAdmin bilan boglaning.")
    except:
        pass
    await query.message.edit_caption(query.message.caption + "\n\n❌ <b>RAD ETILDI</b>", reply_markup=None)
    await query.answer("❌ Rad etildi!")

@dp.callback_query(F.data.startswith("sendmsg_"))
async def cb_sendmsg(query: CallbackQuery, state: FSMContext):
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin emassiz!", show_alert=True)
        return
    uid = int(query.data.split("_")[1])
    await state.set_state(SendMsg.msg)
    await state.update_data(target=uid)
    await query.message.answer("✍️ Xabar yozing (user: " + str(uid) + "):")
    await query.answer()

@dp.message(SendMsg.msg)
async def send_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("target")
    try:
        await bot.send_message(uid, "📩 <b>Admin xabari:</b>\n\n" + message.text)
        await message.answer("✅ Yuborildi!")
    except:
        await message.answer("❌ Yuborilmadi!")
    await state.clear()

@dp.callback_query(F.data == "search_movie")
async def cb_search(query: CallbackQuery, state: FSMContext):
    await state.set_state(SearchMovie.query)
    await query.message.edit_text("🔍 <b>KINO QIDIRISH</b>\n\nNomini yoki kodini yuboring:", reply_markup=back_kb())
    await query.answer()

@dp.message(SearchMovie.query)
async def do_search(message: Message, state: FSMContext):
    q = message.text.lower().strip()
    movies = db.get("movies")
    
    results = []
    for code, m in movies.items():
        mname = m.get("name", "").lower()
        if q in code.lower() or q in mname:
            results.append((code, m))
    
    if not results:
        await message.answer("❌ Topilmadi!\n\nBoshqa qidiring.", reply_markup=back_kb())
        return
    
    if len(results) == 1:
        code, m = results[0]
        await send_movie(message, code, m)
        await state.clear()
        return
    
    text = "🔍 <b>Topildi: " + str(len(results)) + " ta</b>\n\n"
    buttons = []
    for code, m in results[:10]:
        mname = m.get("name", "Nomalum")
        text += "🎬 <b>" + mname + "</b> — <code>" + code + "</code>\n"
        buttons.append([InlineKeyboardButton(text="🎬 " + mname[:30], callback_data="movie_" + code)])
    buttons.append([InlineKeyboardButton(text="◀️ Ortga", callback_data="back_main")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()

@dp.callback_query(F.data.startswith("movie_"))
async def cb_movie(query: CallbackQuery):
    code = query.data.replace("movie_", "")
    movies = db.get("movies")
    if code not in movies:
        await query.answer("❌ Topilmadi!", show_alert=True)
        return
    try:
        await query.message.delete()
    except:
        pass
    await send_movie(query.message, code, movies[code])
    await query.answer()

async def send_movie(message: Message, code, movie):
    inc_views(code)
    
    users = db.get("users")
    uid = str(message.chat.id)
    if uid in users:
        users[uid]["movies_watched"] = users[uid].get("movies_watched", 0) + 1
        db.set("users", users)
    
    mname = movie.get("name", "Nomalum")
    mlang = movie.get("lang", "Nomalum")
    myear = movie.get("year", "Nomalum")
    mgenre = movie.get("genre", "Nomalum")
    mviews = fmt_num(movie.get("views", 0))
    
    me = await bot.get_me()
    
    caption = (
        "🎬 <b>" + mname + "</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌐 Til: <b>" + mlang + "</b>\n"
        "📅 Yil: <b>" + myear + "</b>\n"
        "🎭 Janr: <b>" + mgenre + "</b>\n"
        "👁 Korishlar: <b>" + mviews + "</b>\n\n"
        "🔢 Kod: <code>" + code + "</code>\n"
        "🤖 Bot: @" + me.username
    )
    
    await message.answer_video(movie.get("video"), caption=caption, reply_markup=movie_kb(code))

@dp.callback_query(F.data.startswith("fav_"))
async def cb_fav(query: CallbackQuery):
    code = query.data.replace("fav_", "")
    uid = str(query.from_user.id)
    users = db.get("users")
    if uid not in users:
        users[uid] = {"favorites": []}
    if "favorites" not in users[uid]:
        users[uid]["favorites"] = []
    
    if code in users[uid]["favorites"]:
        users[uid]["favorites"].remove(code)
        db.set("users", users)
        await query.answer("❌ Olib tashlandi!")
    else:
        users[uid]["favorites"].append(code)
        db.set("users", users)
        await query.answer("⭐ Qoshildi!")

@dp.callback_query(F.data == "help")
async def cb_help(query: CallbackQuery):
    text = (
        "❓ <b>YORDAM</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Obuna tanlang\n"
        "2️⃣ Kino kodini yuboring\n"
        "3️⃣ Tomosha qiling!\n\n"
        "/start — Boshlash\n"
        "/help — Yordam\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(text, reply_markup=back_kb())
    await query.answer()

@dp.callback_query(F.data == "user_stats")
async def cb_ustats(query: CallbackQuery):
    uid = str(query.from_user.id)
    users = db.get("users")
    u = users.get(uid, {})
    s = get_user_status(int(uid))
    
    st = "👑 Premium" if s.get("status") == "premium" else "🆓 Bepul"
    if s.get("status") == "premium" and s.get("premium_until"):
        st += "\n⏰ Qoldi: " + time_left(s["premium_until"])
    
    text = (
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 ID: <code>" + uid + "</code>\n"
        "📅 Qoshilgan: " + u.get("join_date", "Nomalum") + "\n"
        "🎬 Korilgan: " + str(u.get("movies_watched", 0)) + "\n"
        "⭐ Sevimli: " + str(len(u.get("favorites", []))) + "\n\n"
        "💫 Status: " + st + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await query.message.edit_text(text, reply_markup=back_kb())
    await query.answer()

# ═══════════════════════════════════════════════════════════
# 🔐 ADMIN
# ═══════════════════════════════════════════════════════════
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Admin emassiz!")
        return
    
    st = get_stats()
    text = (
        "👨‍💼 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 Userlar: " + str(st["total_users"]) + "\n"
        "🎬 Kinolar: " + str(st["total_movies"]) + "\n"
        "👁 Korishlar: " + fmt_num(st["total_views"]) + "\n"
        "💎 Premium: " + str(st["active_premium"]) + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(text, reply_markup=admin_panel_kb())

@dp.message(F.text == "👥 Foydalanuvchilar")
async def admin_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("👥 Foydalanuvchilar:", reply_markup=users_panel_kb())

@dp.message(F.text == "🎬 Kinolar")
async def admin_movies(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🎬 Kinolar:", reply_markup=movies_panel_kb())

@dp.message(F.text == "📤 Broadcast")
async def admin_bc(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📤 Broadcast:", reply_markup=broadcast_panel_kb())

@dp.message(F.text == "📊 Statistika")
async def admin_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    st = get_stats()
    now = datetime.now().strftime("%H:%M:%S")
    text = (
        "📊 <b>STATISTIKA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 Jami: " + str(st["total_users"]) + "\n"
        "✅ Faol: " + str(st["active_users"]) + "\n\n"
        "🎬 Kinolar: " + str(st["total_movies"]) + "\n"
        "👁 Korishlar: " + fmt_num(st["total_views"]) + "\n\n"
        "💎 Premium: " + str(st["active_premium"]) + "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🕐 " + now
    )
    await message.answer(text, reply_markup=admin_panel_kb())

# ═══════════════════════════════════════════════════════════
# 💎 PREMIUM PANEL (YANGILANGAN)
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "💎 Premium")
async def admin_premium(message: Message):
    """Premium boshqaruv paneli"""
    if not is_admin(message.from_user.id):
        return
    
    active = get_active_premium_users()
    tariffs = get_tariffs()
    
    text = (
        "💎 <b>PREMIUM BOSHQARUVI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👑 Faol premium: <b>" + str(len(active)) + " ta</b>\n\n"
        "💰 <b>Joriy narxlar:</b>\n"
    )
    
    for key, t in tariffs.items():
        price_fmt = format_price(t["price"])
        text += "• " + t["name"] + ": <b>" + price_fmt + "</b> som\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━"
    
    await message.answer(text, reply_markup=premium_panel_kb())

@dp.message(F.text == "👑 Premium royxati")
async def premium_list(message: Message):
    """Premium foydalanuvchilar royxati"""
    if not is_admin(message.from_user.id):
        return
    
    active = get_active_premium_users()
    
    if not active:
        await message.answer("❌ Faol premium foydalanuvchilar yoq!")
        return
    
    text = "👑 <b>PREMIUM FOYDALANUVCHILAR</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Jami: <b>" + str(len(active)) + " ta</b>\n\n"
    
    tariffs = get_tariffs()
    users = db.get("users")
    
    for i, (uid, p) in enumerate(list(active.items())[:20], 1):
        tkey = p.get("tariff", "t1")
        tname = tariffs.get(tkey, {}).get("name", "?")
        exp = p.get("expires", "?")
        
        # Username olish
        user_info = users.get(uid, {})
        uname = user_info.get("username", "")
        if uname:
            uname = " (@" + uname + ")"
        
        text += str(i) + ". <code>" + uid + "</code>" + uname + "\n"
        text += "   💎 " + tname + " | ⏰ " + exp + "\n\n"
    
    if len(active) > 20:
        text += "... va yana " + str(len(active) - 20) + " ta"
    
    await message.answer(text, reply_markup=premium_panel_kb())

@dp.message(F.text == "📨 Premium xabar")
async def premium_broadcast_start(message: Message, state: FSMContext):
    """Premium foydalanuvchilarga xabar yuborish"""
    if not is_admin(message.from_user.id):
        return
    
    active = get_active_premium_users()
    if not active:
        await message.answer("❌ Faol premium foydalanuvchilar yoq!")
        return
    
    await state.set_state(PremiumBroadcast.msg)
    text = (
        "📨 <b>PREMIUM BROADCAST</b>\n\n"
        "👑 Premium userlar: <b>" + str(len(active)) + " ta</b>\n\n"
        "Xabaringizni yuboring (matn, rasm, video):"
    )
    await message.answer(text, reply_markup=cancel_kb())

@dp.message(PremiumBroadcast.msg)
async def premium_broadcast_send(message: Message, state: FSMContext):
    """Premium userlarga xabar yuborish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    active = get_active_premium_users()
    
    await message.answer("📤 Yuborilmoqda...")
    
    start = time.time()
    ok = 0
    bad = 0
    
    for uid in active.keys():
        try:
            await bot.copy_message(int(uid), message.chat.id, message.message_id)
            ok += 1
        except:
            bad += 1
        await asyncio.sleep(0.05)
    
    dur = round(time.time() - start, 2)
    await state.clear()
    
    text = (
        "✅ <b>Premium broadcast tugadi!</b>\n\n"
        "📤 Yuborildi: <b>" + str(ok) + "</b>\n"
        "❌ Xato: <b>" + str(bad) + "</b>\n"
        "⏱ Vaqt: <b>" + str(dur) + "s</b>"
    )
    await message.answer(text, reply_markup=premium_panel_kb())

@dp.message(F.text == "➕ Premium berish")
async def give_premium_start(message: Message, state: FSMContext):
    """Foydalanuvchiga premium berish"""
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(GivePremium.uid)
    await message.answer("👤 User ID sini kiriting:", reply_markup=cancel_kb())

@dp.message(GivePremium.uid)
async def give_premium_uid(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("❌ ID raqam bolishi kerak!")
        return
    
    await state.update_data(uid=uid)
    await state.set_state(GivePremium.tariff)
    
    tariffs = get_tariffs()
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t["name"])] for t in tariffs.values()
    ] + [[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    
    await message.answer("💎 Tarifni tanlang:", reply_markup=kb)

@dp.message(GivePremium.tariff)
async def give_premium_finish(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    data = await state.get_data()
    uid = data.get("uid")
    
    tariffs = get_tariffs()
    selected = None
    for key, t in tariffs.items():
        if t["name"] == message.text:
            selected = (key, t)
            break
    
    if not selected:
        await message.answer("❌ Tarif topilmadi!")
        return
    
    key, t = selected
    exp = datetime.now() + timedelta(days=t["days"])
    exp_str = exp.strftime("%Y-%m-%d %H:%M")
    
    prem = db.get("premium")
    prem[str(uid)] = {
        "user_id": uid,
        "tariff": key,
        "start": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "expires": exp_str
    }
    db.set("premium", prem)
    set_user_status(uid, "premium", exp.isoformat())
    
    try:
        await bot.send_message(uid, "🎉 Sizga <b>" + t["name"] + "</b> premium berildi!\n⏰ Tugash: " + exp_str)
    except:
        pass
    
    await state.clear()
    await message.answer("✅ <code>" + str(uid) + "</code> ga premium berildi!", reply_markup=premium_panel_kb())

@dp.message(F.text == "➖ Premium olish")
async def remove_premium_start(message: Message, state: FSMContext):
    """Premium olib tashlash"""
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(RemovePremium.uid)
    await message.answer("👤 User ID sini kiriting:", reply_markup=cancel_kb())

@dp.message(RemovePremium.uid)
async def remove_premium_finish(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("❌ ID raqam bolishi kerak!")
        return
    
    prem = db.get("premium")
    uid_str = str(uid)
    
    if uid_str not in prem:
        await message.answer("❌ Bu user premium emas!")
        await state.clear()
        return
    
    del prem[uid_str]
    db.set("premium", prem)
    set_user_status(uid, None, None)
    
    try:
        await bot.send_message(uid, "❌ Sizning premium obunangiz olib tashlandi!")
    except:
        pass
    
    await state.clear()
    await message.answer("✅ <code>" + str(uid) + "</code> dan premium olindi!", reply_markup=premium_panel_kb())

@dp.message(F.text == "💰 Narxlarni ozgartirish")
async def edit_tariff_start(message: Message, state: FSMContext):
    """Tarif narxlarini ozgartirish"""
    if not is_admin(message.from_user.id):
        return
    
    tariffs = get_tariffs()
    
    text = "💰 <b>NARXLARNI OZGARTIRISH</b>\n\n"
    text += "Qaysi tarifni ozgartirmoqchisiz?\n\n"
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 " + t["name"] + " (" + format_price(t["price"]) + ")")] for t in tariffs.values()
    ] + [[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    
    await state.set_state(EditTariff.select)
    await message.answer(text, reply_markup=kb)

@dp.message(EditTariff.select)
async def edit_tariff_select(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    tariffs = get_tariffs()
    selected = None
    
    for key, t in tariffs.items():
        if t["name"] in message.text:
            selected = key
            break
    
    if not selected:
        await message.answer("❌ Tarif topilmadi!")
        return
    
    await state.update_data(tariff_key=selected)
    await state.set_state(EditTariff.price)
    
    t = tariffs[selected]
    text = (
        "💰 <b>" + t["name"] + "</b>\n\n"
        "Joriy narx: <b>" + format_price(t["price"]) + "</b> som\n\n"
        "Yangi narxni kiriting (faqat raqam):"
    )
    await message.answer(text, reply_markup=cancel_kb())

@dp.message(EditTariff.price)
async def edit_tariff_price(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=premium_panel_kb())
        return
    
    try:
        new_price = int(message.text.strip().replace(",", "").replace(" ", ""))
    except:
        await message.answer("❌ Faqat raqam kiriting!")
        return
    
    data = await state.get_data()
    key = data.get("tariff_key")
    
    tariffs = get_tariffs()
    old_price = tariffs[key]["price"]
    tariffs[key]["price"] = str(new_price)
    db.set("tariffs", tariffs)
    
    await state.clear()
    
    text = (
        "✅ <b>Narx ozgartirildi!</b>\n\n"
        "💎 Tarif: <b>" + tariffs[key]["name"] + "</b>\n"
        "💰 Eski: <b>" + format_price(old_price) + "</b> som\n"
        "💰 Yangi: <b>" + format_price(new_price) + "</b> som"
    )
    await message.answer(text, reply_markup=premium_panel_kb())

# ═══════════════════════════════════════════════════════════
# 🎬 KINO QOSHISH/OCHIRISH
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "➕ Kino qoshish")
async def add_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AddMovie.video)
    await message.answer("🎬 <b>KINO QOSHISH</b>\n\n1️⃣ Video yuboring:", reply_markup=cancel_kb())

@dp.message(AddMovie.video, F.video | F.document)
async def add_movie_video(message: Message, state: FSMContext):
    fid = message.video.file_id if message.video else message.document.file_id
    await state.update_data(video=fid)
    await state.set_state(AddMovie.name)
    await message.answer("2️⃣ Kino nomi:")

@dp.message(AddMovie.name)
async def add_movie_name(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    await state.update_data(name=message.text)
    await state.set_state(AddMovie.lang)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 Uzbek"), KeyboardButton(text="🇷🇺 Rus")],
        [KeyboardButton(text="🇺🇸 Ingliz"), KeyboardButton(text="🌐 Boshqa")],
        [KeyboardButton(text="❌ Bekor qilish")]
    ], resize_keyboard=True)
    await message.answer("3️⃣ Til:", reply_markup=kb)

@dp.message(AddMovie.lang)
async def add_movie_lang(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    lmap = {"🇺🇿 Uzbek": "Uzbek", "🇷🇺 Rus": "Rus", "🇺🇸 Ingliz": "Ingliz", "🌐 Boshqa": "Boshqa"}
    await state.update_data(lang=lmap.get(message.text, message.text))
    await state.set_state(AddMovie.year)
    await message.answer("4️⃣ Yil (masalan: 2024):", reply_markup=cancel_kb())

@dp.message(AddMovie.year)
async def add_movie_year(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    await state.update_data(year=message.text)
    await state.set_state(AddMovie.genre)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎭 Drama"), KeyboardButton(text="😂 Komediya")],
        [KeyboardButton(text="💥 Boevik"), KeyboardButton(text="😱 Qorqinchli")],
        [KeyboardButton(text="❤️ Romantika"), KeyboardButton(text="🔬 Fantastika")],
        [KeyboardButton(text="❌ Bekor qilish")]
    ], resize_keyboard=True)
    await message.answer("5️⃣ Janr:", reply_markup=kb)

@dp.message(AddMovie.genre)
async def add_movie_genre(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    gmap = {"🎭 Drama": "Drama", "😂 Komediya": "Komediya", "💥 Boevik": "Boevik", 
            "😱 Qorqinchli": "Qorqinchli", "❤️ Romantika": "Romantika", "🔬 Fantastika": "Fantastika"}
    await state.update_data(genre=gmap.get(message.text, message.text))
    await state.set_state(AddMovie.code)
    await message.answer("6️⃣ Kod (masalan: 101):", reply_markup=cancel_kb())

@dp.message(AddMovie.code)
async def add_movie_code(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    
    code = message.text.strip()
    movies = db.get("movies")
    
    if code in movies:
        await message.answer("❌ <code>" + code + "</code> mavjud!\nBoshqa kod:")
        return
    
    data = await state.get_data()
    movies[code] = {
        "video": data["video"], "name": data["name"], "lang": data["lang"],
        "year": data.get("year", "Nomalum"), "genre": data.get("genre", "Nomalum"),
        "views": 0, "added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    db.set("movies", movies)
    await state.clear()
    
    text = (
        "✅ <b>Kino qoshildi!</b>\n\n"
        "🎬 Nom: <b>" + data["name"] + "</b>\n"
        "🔢 Kod: <code>" + code + "</code>\n"
        "🌐 Til: " + data["lang"] + "\n"
        "📅 Yil: " + data.get("year", "Nomalum") + "\n"
        "🎭 Janr: " + data.get("genre", "Nomalum")
    )
    await message.answer(text, reply_markup=movies_panel_kb())

@dp.message(F.text == "➖ Kino ochirish")
async def del_movie_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(DelMovie.code)
    await message.answer("🗑 Kino kodini yuboring:", reply_markup=cancel_kb())

@dp.message(DelMovie.code)
async def del_movie_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=movies_panel_kb())
        return
    
    code = message.text.strip()
    movies = db.get("movies")
    
    if code not in movies:
        await message.answer("❌ Topilmadi!")
        return
    
    name = movies[code].get("name", "Nomalum")
    del movies[code]
    db.set("movies", movies)
    await state.clear()
    await message.answer("✅ <b>" + name + "</b> ochirildi!", reply_markup=movies_panel_kb())

@dp.message(F.text == "📋 Kinolar royxati")
async def list_movies(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    movies = db.get("movies")
    if not movies:
        await message.answer("❌ Kinolar yoq!")
        return
    
    text = "🎬 <b>KINOLAR</b> (" + str(len(movies)) + " ta)\n" + "━" * 25 + "\n\n"
    for i, (code, m) in enumerate(list(movies.items())[:20], 1):
        text += str(i) + ". <b>" + m.get("name", "Nomalum") + "</b>\n"
        text += "   📌 <code>" + code + "</code> | 👁 " + str(m.get("views", 0)) + "\n\n"
    
    if len(movies) > 20:
        text += "... va yana " + str(len(movies) - 20) + " ta"
    
    await message.answer(text)

@dp.message(F.text == "📊 Top kinolar")
async def top_movies(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    movies = db.get("movies")
    if not movies:
        await message.answer("❌ Kinolar yoq!")
        return
    
    sorted_m = sorted(movies.items(), key=lambda x: x[1].get("views", 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"]
    
    text = "🏆 <b>TOP 10</b>\n" + "━" * 25 + "\n\n"
    for i, (code, m) in enumerate(sorted_m, 1):
        med = medals[i-1] if i <= 3 else str(i) + "."
        text += med + " <b>" + m.get("name", "Nomalum") + "</b>\n"
        text += "    👁 " + fmt_num(m.get("views", 0)) + " | <code>" + code + "</code>\n\n"
    
    await message.answer(text)

# ═══════════════════════════════════════════════════════════
# 📤 BROADCAST
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "📝 Oddiy xabar")
async def bc_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.msg)
    await message.answer("📝 Xabar yozing:", reply_markup=cancel_kb())

@dp.message(Broadcast.msg)
async def bc_send(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=broadcast_panel_kb())
        return
    
    users = db.get("users")
    await message.answer("📤 Yuborilmoqda...")
    
    start = time.time()
    ok = 0
    bad = 0
    
    for uid in users.keys():
        try:
            await bot.copy_message(int(uid), message.chat.id, message.message_id)
            ok += 1
        except:
            bad += 1
        await asyncio.sleep(0.05)
    
    dur = round(time.time() - start, 2)
    await state.clear()
    
    text = "✅ <b>Broadcast tugadi!</b>\n\n📤 Yuborildi: <b>" + str(ok) + "</b>\n❌ Xato: <b>" + str(bad) + "</b>\n⏱ Vaqt: <b>" + str(dur) + "s</b>"
    await message.answer(text, reply_markup=broadcast_panel_kb())

# ═══════════════════════════════════════════════════════════
# 👥 USER MANAGEMENT
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "🔴 Bloklash")
async def block_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BlockUser.uid)
    await message.answer("🔴 User ID:", reply_markup=cancel_kb())

@dp.message(BlockUser.uid)
async def block_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=users_panel_kb())
        return
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("❌ Raqam kiriting!")
        return
    
    blocked = db.get("blocked")
    if uid in blocked:
        await message.answer("❌ Allaqachon bloklangan!")
        return
    
    blocked.append(uid)
    db.set("blocked", blocked)
    await state.clear()
    await message.answer("✅ <code>" + str(uid) + "</code> bloklandi!", reply_markup=users_panel_kb())

@dp.message(F.text == "🟢 Blokdan olish")
async def unblock_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(UnblockUser.uid)
    await message.answer("🟢 User ID:", reply_markup=cancel_kb())

@dp.message(UnblockUser.uid)
async def unblock_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=users_panel_kb())
        return
    try:
        uid = int(message.text.strip())
    except:
        await message.answer("❌ Raqam kiriting!")
        return
    
    blocked = db.get("blocked")
    if uid not in blocked:
        await message.answer("❌ Blokda emas!")
        return
    
    blocked.remove(uid)
    db.set("blocked", blocked)
    await state.clear()
    await message.answer("✅ <code>" + str(uid) + "</code> blokdan olindi!", reply_markup=users_panel_kb())

@dp.message(F.text == "📋 Bloklangan royxat")
async def blocked_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    blocked = db.get("blocked")
    if not blocked:
        await message.answer("✅ Bloklangan yoq!")
        return
    
    text = "🔴 <b>BLOKLANGAN</b> (" + str(len(blocked)) + " ta)\n\n"
    for i, uid in enumerate(blocked[:50], 1):
        text += str(i) + ". <code>" + str(uid) + "</code>\n"
    
    await message.answer(text)

# ═══════════════════════════════════════════════════════════
# 👨‍💼 ADMIN MANAGEMENT
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "👨‍💼 Adminlar")
async def admin_admins(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    admins = db.get("admins")
    text = "👨‍💼 <b>ADMINLAR</b> (" + str(len(admins)) + " ta)\n\n"
    for i, aid in enumerate(admins, 1):
        text += str(i) + ". <code>" + str(aid) + "</code>\n"
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Admin qoshish"), KeyboardButton(text="➖ Admin ochirish")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)
    await message.answer(text, reply_markup=kb)

@dp.message(F.text == "➕ Admin qoshish")
async def add_admin_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminAdd.uid)
    await message.answer("➕ Yangi admin ID:", reply_markup=cancel_kb())

@dp.message(AdminAdd.uid)
async def add_admin_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_panel_kb())
        return
    try:
        aid = int(message.text.strip())
    except:
        await message.answer("❌ Raqam kiriting!")
        return
    
    admins = db.get("admins")
    if aid in admins:
        await message.answer("❌ Allaqachon admin!")
        return
    
    admins.append(aid)
    db.set("admins", admins)
    try:
        await bot.send_message(aid, "🎉 Siz admin boldingiz!")
    except:
        pass
    await state.clear()
    await message.answer("✅ <code>" + str(aid) + "</code> admin boldi!", reply_markup=admin_panel_kb())

@dp.message(F.text == "➖ Admin ochirish")
async def del_admin_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminDel.uid)
    await message.answer("➖ Admin ID:", reply_markup=cancel_kb())

@dp.message(AdminDel.uid)
async def del_admin_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_panel_kb())
        return
    try:
        aid = int(message.text.strip())
    except:
        await message.answer("❌ Raqam kiriting!")
        return
    
    admins = db.get("admins")
    if aid not in admins:
        await message.answer("❌ Admin emas!")
        return
    if aid == INITIAL_ADMIN:
        await message.answer("❌ Asosiy adminni ochirib bolmaydi!")
        return
    
    admins.remove(aid)
    db.set("admins", admins)
    try:
        await bot.send_message(aid, "❌ Adminlikdan oldingiz!")
    except:
        pass
    await state.clear()
    await message.answer("✅ <code>" + str(aid) + "</code> adminlikdan olindi!", reply_markup=admin_panel_kb())

# ═══════════════════════════════════════════════════════════
# 📢 KANAL MANAGEMENT
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "📢 Kanallar")
async def admin_channels(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    channels = db.get("channels")
    text = "📢 <b>KANALLAR</b> (" + str(len(channels)) + " ta)\n\n"
    if channels:
        for i, ch in enumerate(channels, 1):
            text += str(i) + ". " + ch + "\n"
    else:
        text += "<i>Kanallar yoq</i>"
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Kanal qoshish"), KeyboardButton(text="➖ Kanal ochirish")],
        [KeyboardButton(text="◀️ Ortga")]
    ], resize_keyboard=True)
    await message.answer(text, reply_markup=kb)

@dp.message(F.text == "➕ Kanal qoshish")
async def add_ch_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(ChannelAdd.ch)
    await message.answer("➕ Kanal (@kanal_nomi):", reply_markup=cancel_kb())

@dp.message(ChannelAdd.ch)
async def add_ch_do(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_panel_kb())
        return
    
    ch = message.text.strip()
    if not ch.startswith("@"):
        await message.answer("❌ @ bilan boshlang!")
        return
    
    channels = db.get("channels")
    if ch in channels:
        await message.answer("❌ Allaqachon qoshilgan!")
        return
    
    channels.append(ch)
    db.set("channels", channels)
    await state.clear()
    await message.answer("✅ " + ch + " qoshildi!", reply_markup=admin_panel_kb())

@dp.message(F.text == "➖ Kanal ochirish")
async def del_ch(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    channels = db.get("channels")
    if not channels:
        await message.answer("❌ Kanallar yoq!")
        return
    
    buttons = [[InlineKeyboardButton(text="❌ " + ch, callback_data="delch_" + ch)] for ch in channels]
    await message.answer("Ochirish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("delch_"))
async def del_ch_do(query: CallbackQuery):
    if not is_admin(query.from_user.id):
        await query.answer("❌ Admin emassiz!")
        return
    
    ch = query.data.replace("delch_", "")
    channels = db.get("channels")
    if ch in channels:
        channels.remove(ch)
        db.set("channels", channels)
        await query.message.edit_text("✅ " + ch + " ochirildi!")
    else:
        await query.answer("❌ Topilmadi!")

# ═══════════════════════════════════════════════════════════
# 🚪 EXIT & BACK
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "🚪 Chiqish")
async def exit_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎬 Kino kodini yuboring:", reply_markup=ReplyKeyboardRemove())

@dp.message(F.text == "◀️ Ortga")
async def back_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("👨‍💼 Admin panel:", reply_markup=admin_panel_kb())

# ═══════════════════════════════════════════════════════════
# 🎬 CATCH-ALL
# ═══════════════════════════════════════════════════════════
@dp.message(F.text)
async def catch_all(message: Message, state: FSMContext):
    current = await state.get_state()
    if current:
        return
    
    btns = ["👥", "👨‍💼", "📢", "💎", "🎬", "📊", "📤", "⚙️", "🚪", "◀️", "➕", "➖", "📋", "🔴", "🟢", "📝", "❌", "👑", "📨", "💰"]
    for b in btns:
        if b in message.text:
            return
    
    uid = message.from_user.id
    if is_blocked(uid):
        await message.answer("🚫 Bloklangansiz!")
        return
    
    us = get_user_status(uid)
    has_access = check_premium(uid) or us.get("status") == "free" or is_admin(uid)
    
    if not has_access:
        await message.answer("🔒 Avval obuna boling!", reply_markup=main_menu_kb())
        return
    
    code = message.text.strip()
    movies = db.get("movies")
    
    if code in movies:
        await send_movie(message, code, movies[code])
    else:
        results = [(c, m) for c, m in movies.items() if code.lower() in m.get("name", "").lower()]
        if results:
            text = "🔍 <b>Topildi:</b>\n\n"
            buttons = []
            for c, m in results[:5]:
                text += "🎬 " + m.get("name", "?") + " — <code>" + c + "</code>\n"
                buttons.append([InlineKeyboardButton(text="🎬 " + m.get("name", "?")[:25], callback_data="movie_" + c)])
            buttons.append([InlineKeyboardButton(text="◀️ Ortga", callback_data="back_main")])
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        else:
            await message.answer("❌ <code>" + code + "</code> topilmadi!\n\nTogri kiriting.", reply_markup=back_kb())

# ═══════════════════════════════════════════════════════════
# 🚀 MAIN
# ═══════════════════════════════════════════════════════════
async def on_start():
    logger.info("🚀 Bot ishga tushdi...")
    me = await bot.get_me()
    logger.info("🤖 Bot: @" + me.username)
    logger.info("✅ Tayyor!")

async def on_stop():
    logger.info("💾 Saqlanmoqda...")
    db.save_all()
    logger.info("👋 Toxtatildi!")

async def main():
    dp.startup.register(on_start)
    dp.shutdown.register(on_stop)
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        db.save_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Toxtatildi!")
    except Exception as e:
        logger.error("❌ Xato: " + str(e))
    finally:
        db.save_all()