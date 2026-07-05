import telebot
from telebot import types
import datetime
import time
import re
import sqlite3
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# ================= বটের মূল কনফিগারেশন =================
API_TOKEN = '8924739332:AAHRzl2KqTpmMnGwiFjimtsRiVp-ohJabpc'
BOT_USERNAME = 'Infinity_Earn838bot'
ADMIN_IDS = [6227950415, 7016100281]

# ১. Mandatory Join Channels
CHANNEL_1_LINK = "https://t.me/nft_earn_bot_1"
CHANNEL_2_LINK = "https://t.me/online_income_11zone"

CHANNEL_1_ID = "@nft_earn_bot_1"
CHANNEL_2_ID = "@online_income_11zone"
# ২. Task Channels
TASK_channels = [
    {
        "link": "https://t.me/online_income_11zone",
        "id": "@online_income_11zone"
    },
    {
        "link": "https://t.me/nft_earn_bot_1",
        "id": "@nft_earn_bot_1"
    }
]

NUMBER_NAGAD = '01820604705'

bot = telebot.TeleBot(API_TOKEN)
user_states = {}

# VIP Packages Configuration
VIP_CONFIG = {
    "Bronze VIP": {"price": 150, "daily_income": 8},
    "Silver VIP": {"price": 300, "daily_income": 17},
    "Gold VIP": {"price": 500, "daily_income": 30},
    "Platinum VIP": {"price": 700, "daily_income": 40},
    "Diamond VIP": {"price": 1000, "daily_income": 70},
    "Royal VIP": {"price": 1500, "daily_income": 110},
    "Legend VIP": {"price": 2500, "daily_income": 200}
}

# --- সুসংগঠিত ডাটাবেজ পাথ ---
DB_DIR = "data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_FILE = os.path.join(DB_DIR, "bot_database.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            main_balance REAL,
            bonus_balance REAL,
            deposit_balance REAL,
            task_balance REAL,
            total_deposit REAL,
            active_vips TEXT,
            task_completed INTEGER,
            completed_tasks_count INTEGER,
            last_income_time TEXT,
            referred_by INTEGER,
            total_refer INTEGER,
            refer_income REAL,
            bonus_claims_today INTEGER,
            last_bonus_time REAL,
            is_banned INTEGER,
            deposit_count_today INTEGER,
            last_deposit_reset_time REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_stats (
            stat_name TEXT PRIMARY KEY,
            stat_value REAL
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO system_stats (stat_name, stat_value) VALUES ('total_withdraw_approved', 0)")
    conn.commit()
    conn.close()

init_db()

def get_total_withdraw_approved():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT stat_value FROM system_stats WHERE stat_name = 'total_withdraw_approved'")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_total_withdraw_approved(amount):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE system_stats SET stat_value = stat_value + ? WHERE stat_name = 'total_withdraw_approved'", (amount,))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "name": row[1],
            "username": row[2],
            "main_balance": row[3],
            "bonus_balance": row[4],
            "deposit_balance": row[5],
            "task_balance": row[6],
            "total_deposit": row[7],
            "active_vips": json.loads(row[8]) if row[8] else {},
            "task_completed": bool(row[9]),
            "completed_tasks_count": row[10],
            "last_income_time": row[11],
            "referred_by": row[12],
            "total_refer": row[13],
            "refer_income": row[14],
            "bonus_claims_today": row[15],
            "last_bonus_time": row[16],
            "is_banned": bool(row[17]),
            "deposit_count_today": row[18],
            "last_deposit_reset_time": row[19]
        }
    return None

def save_user(user_id, u):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    vips_str = json.dumps(u.get("active_vips", {}))
    cursor.execute('''
        INSERT OR REPLACE INTO users (
            user_id, name, username, main_balance, bonus_balance, deposit_balance,
            task_balance, total_deposit, active_vips, task_completed,
            completed_tasks_count, last_income_time, referred_by, total_refer,
            refer_income, bonus_claims_today, last_bonus_time, is_banned,
            deposit_count_today, last_deposit_reset_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, u.get("name", "User"), u.get("username", "N/A"), u.get("main_balance", 0),
        u.get("bonus_balance", 10), u.get("deposit_balance", 0), u.get("task_balance", 0),
        u.get("total_deposit", 0), vips_str, int(u.get("task_completed", False)),
        u.get("completed_tasks_count", 0), str(u.get("last_income_time", "")), u.get("referred_by"),
        u.get("total_refer", 0), u.get("refer_income", 0), u.get("bonus_claims_today", 0),
        u.get("last_bonus_time", 0), int(u.get("is_banned", False)),
        u.get("deposit_count_today", 0), u.get("last_deposit_reset_time", 0)
    ))
    conn.commit()
    conn.close()

def escape_html(text):
    if not text:
        return "N/A"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def init_user(user_id, first_name="User", username="N/A"):
    u = get_user(user_id)
    if not u:
        u = {
            "name": escape_html(first_name) if first_name else "User",
            "username": escape_html(username) if username else "N/A",
            "main_balance": 0,
            "bonus_balance": 10,
            "deposit_balance": 0,
            "task_balance": 0,
            "total_deposit": 0,
            "active_vips": {},
            "task_completed": False,
            "completed_tasks_count": 0,
            "last_income_time": "",
            "referred_by": None,
            "total_refer": 0,
            "refer_income": 0,
            "bonus_claims_today": 0,
            "last_bonus_time": 0,
            "is_banned": False,
            "deposit_count_today": 0,
            "last_deposit_reset_time": 0
        }
        save_user(user_id, u)
    else:
        updated = False
        if first_name and first_name != "User" and u["name"] == "User":
            u["name"] = escape_html(first_name)
            updated = True
        if username and username != "N/A" and u["username"] == "N/A":
            u["username"] = escape_html(username)
            updated = True
        if updated:
            save_user(user_id, u)

def get_total_users_count():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_deposits_sum():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(total_deposit) FROM users")
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total

def get_all_user_ids():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_referred_members(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE referred_by = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_user_joined(user_id):
    try:
        member1 = bot.get_chat_member(CHANNEL_1_ID, user_id)
        member2 = bot.get_chat_member(CHANNEL_2_ID, user_id)
        status_blocked = ['left', 'kicked', 'restricted']
        if member1.status in status_blocked or member2.status in status_blocked:
            return False
        return True
    except Exception:
        return False

def is_user_joined_task_channels(user_id):
    try:
        status_blocked = ['left', 'kicked', 'restricted']
        for chan in TASK_CHANNELS:
            member = bot.get_chat_member(chan["id"], user_id)
            if member.status in status_blocked:
                return False
        return True
    except Exception:
        return False

def check_and_punish_leave(user_id, chat_id):
    u = get_user(user_id)
    if u and u["task_completed"]:
        if not is_user_joined_task_channels(user_id):
            u["task_completed"] = False
            u["bonus_balance"] = max(0, u["bonus_balance"] - 40)
            u["task_balance"] = max(0, u["task_balance"] - 40)
            if u["completed_tasks_count"] > 0:
                u["completed_tasks_count"] -= 1
            save_user(user_id, u)
            bot.send_message(
                chat_id,
                "⚠️ <b>আপনি আমাদের টাস্ক চ্যানেল থেকে লিভ নিয়েছেন!</b>\n\n"
                "তাই আপনার বোনাস ব্যালেন্স এবং টাস্ক ব্যালেন্স থেকে <b>৪০ টাকা</b> কাটা হলো। "
                "আবার ৪টি চ্যানেলে জয়েন করলে আপনি পুনরায় বোনাসটি ক্লেইম করতে পারবেন। ✅",
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )

def send_force_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔗 WahoEarnOfficial এ যোগ দিন", url=CHANNEL_1_LINK),
        types.InlineKeyboardButton("🔗 Easy Earnings 에 যোগ দিন", url=CHANNEL_2_LINK),
        types.InlineKeyboardButton("✅ জয়েন করেছি", callback_data="verify_force_join")
    )
    msg_text = (
        "⚠️ <b>বটটি ব্যবহার করার জন্য আপনাকে আমাদের চ্যানেলে জয়েন করতে হবে।</b>\n\n"
        "অনুগ্রহ করে প্রথমে চ্যানেলে যোগ দিন, তারপর নিচের \"✅ জয়েন করেছি\" বাটনে ক্লিক করুন।"
    )
    bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("📩 ডিপোজিট"), types.KeyboardButton("📤 উইথড্র"))
    markup.add(types.KeyboardButton("💰 রেফার"), types.KeyboardButton("⭐ VIP"))
    markup.add(types.KeyboardButton("📝 টাস্ক"), types.KeyboardButton("🎁 বোনাস"))
    markup.add(types.KeyboardButton("👤 অ্যাকাউন্ট"), types.KeyboardButton("💰 ভিআইপি প্রতিদিন আয়"))
    markup.add(types.KeyboardButton("📞 সাপোর্ট"), types.KeyboardButton("🎲 লটারি"))
    return markup

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ বাতিল"))
    return markup

def confirm_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("✅ নিশ্চিত করুন"), types.KeyboardButton("❌ বাতিল করুন"))
    return markup

def vip_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for name, config in VIP_CONFIG.items():
        markup.add(types.InlineKeyboardButton(f"👑 {name} কিনুন ({config['price']}৳)", callback_data=f"buy_vip_{name}_{config['price']}"))
    return markup

def withdraw_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("বিকাশ", callback_data="wth_select_বিকাশ"),
        types.InlineKeyboardButton("নগদ", callback_data="wth_select_নগদ"),
        types.InlineKeyboardButton("রকেট", callback_data="wth_select_rocket")
    )
    return markup

def admin_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚙️ ইউজার কন্ট্রোল করুন (সার্চ আইডি)", callback_data="adm_user_control"),
        types.InlineKeyboardButton("📊 বটের টোটাল স্ট্যাটাস (অরিজিনাল)", callback_data="adm_total_stats"),
        types.InlineKeyboardButton("📢 ব্রডকাস্ট করুন", callback_data="adm_broadcast")
    )
    return markup

def admin_user_control_keyboard(target_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 মোট ব্যালেন্স", callback_data=f"edit_bal_main_{target_id}"),
        types.InlineKeyboardButton("💵 রেফার ব্যালেন্স", callback_data=f"edit_bal_ref_{target_id}"),
        types.InlineKeyboardButton("🎁 বোনাস ব্যালেন্স", callback_data=f"edit_bal_bon_{target_id}"),
        types.InlineKeyboardButton("🧑‍💻 টাস্ক ব্যালেন্স", callback_data=f"edit_bal_tsk_{target_id}"),
        types.InlineKeyboardButton("📥 ডিপোজিট ব্যালেন্স", callback_data=f"edit_bal_dep_{target_id}"),
        types.InlineKeyboardButton("🎯 মোট রেফার সংখ্যা", callback_data=f"edit_cnt_cntref_{target_id}")
    )
    markup.add(
        types.InlineKeyboardButton("🚫 ব্যান করুন", callback_data=f"adm_ban_{target_id}"),
        types.InlineKeyboardButton("🟢 আনব্যান করুন", callback_data=f"adm_unban_{target_id}")
    )
    return markup

def broadcast_confirm_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Confirm Send", callback_data="bc_confirm"),
        types.InlineKeyboardButton("❌ Cancel Send", callback_data="bc_cancel")
    )
    return markup

def send_account_details(chat_id, user_id, first_name, username):
    init_user(user_id, first_name, username)
    u = get_user(user_id)

    active_vips_list = [f"{name} ({days} দিন)" for name, days in u["active_vips"].items() if days > 0]
    vips_text = ", ".join(active_vips_list) if active_vips_list else "কোনো প্যাকেজ একটিভ নেই ❌"

    account_text = (
        "📊 <b>আপনার অ্যাকাউন্ট তথ্য</b> 📊\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>নাম:</b> {u['name']}\n"
        f"🔗 <b>ইউজারনেম:</b> @{u['username']}\n"
        f"🆔 <b>ইউজার আইডি:</b> <code>{user_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>মোট রেফার:</b> {u['total_refer']} জন\n"
        f"💵 <b>রেফার ব্যালেন্স:</b> {u['refer_income']} টাকা\n"
        f"💰 <b>মোট ব্যালেন্স:</b> {u['main_balance']} টাকা\n"
        f"🎁 <b>বোনাস ব্যালেন্স:</b> {u['bonus_balance']} টাকা\n"
        f"👨‍💻 <b>টাস্ক ব্যালেন্স:</b> {u['task_balance']} টাকা\n"
        f"📥 <b>ডিপোজিট ব্যালেন্স:</b> {u['deposit_balance']} টাকা\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>ভিআইপি সদস্য:</b> {vips_text}\n"
        f"📝 <b>টাস্ক সম্পন্ন:</b> {u['completed_tasks_count']} টি\n"
        f"🚫 <b>নিষিদ্ধ:</b> {'হ্যাঁ' if u['is_banned'] else 'না'}\n"
        f"🏛️ <b>মোট ডিপোজিট অ্যামাউন্ট:</b> {u['total_deposit']} টাকা\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(chat_id, account_text, parse_mode="HTML")

def get_live_fake_stats():
    base_timestamp = 1768348800
    current_timestamp = time.time()

    elapsed_minutes = int((current_timestamp - base_timestamp) // 60)
    if elapsed_minutes < 0:
        elapsed_minutes = 0

    auto_users = elapsed_minutes * 1
    auto_deposit = elapsed_minutes * 1
    auto_withdraw = elapsed_minutes * 1

    final_users = 2197 + auto_users
    final_deposit = 25899.0 + auto_deposit
    final_withdraw = 30546.0 + auto_withdraw

    return final_users, final_deposit, final_withdraw

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.first_name, message.from_user.username)
    u = get_user(user_id)

    if u["is_banned"]:
        bot.send_message(message.chat.id, "🚫 দুঃখিত, আপনি এই বটে নিষিদ্ধ (Banned) আছেন।")
        return

    user_states.pop(user_id, None)

    start_args = message.text.split()
    if len(start_args) > 1:
        referrer_id = start_args[1]
        if referrer_id.isdigit():
            referrer_id = int(referrer_id)
            if referrer_id != user_id and u["referred_by"] is None:
                init_user(referrer_id)
                u["referred_by"] = referrer_id

                ref_u = get_user(referrer_id)
                ref_u["total_refer"] += 1
                save_user(referrer_id, ref_u)
                save_user(user_id, u)
                try:
                    bot.send_message(referrer_id, f"🔔 আপনার রেফার লিংকে ক্লিক করে নতুন মেম্বার <b>{u['name']}</b> জয়েন করেছেন!", parse_mode="HTML")
                except Exception:
                    pass

    if not is_user_joined(user_id):
        send_force_join_msg(message.chat.id)
        return

    check_and_punish_leave(user_id, message.chat.id)

    bot.send_message(
        message.chat.id,
        "👋 <b>💸 Infinity earn 💸</b> বটে আপনাকে স্বাগতম! নিচে থেকে একটি option বেছে নিন 👇",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    user_states.pop(user_id, None)
    bot.send_message(message.chat.id, "⚙️ <b>অ্যাডমিন প্যানেলে স্বাগতম:</b>", reply_markup=admin_main_keyboard(), parse_mode="HTML")

@bot.message_handler(func=lambda message: True)
def handle_inputs(message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.first_name, message.from_user.username)
    u = get_user(user_id)

    if u["is_banned"]:
        bot.send_message(message.chat.id, "🚫 আপনাকে এই বট থেকে ব্লক করা হয়েছে।")
        return

    if not is_user_joined(user_id):
        send_force_join_msg(message.chat.id)
        return

    check_and_punish_leave(user_id, message.chat.id)
    u = get_user(user_id)

    text = message.text.strip()

    if "অ্যাকাউন্ট" in text or "account" in text.lower() or "একাউন্ট" in text:
        send_account_details(message.chat.id, user_id, message.from_user.first_name, message.from_user.username)
        return

    if text in ["❌ বাতিল", "❌ বাতিল করুন"]:
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "❌ প্রসেসটি বাতিল করা হয়েছে।", reply_markup=main_keyboard())
        return

    if "বোনাস" in text or "bonus" in text.lower():
        current_time = time.time()
        one_day = 86400
        if current_time - u["last_bonus_time"] > one_day:
            u["bonus_claims_today"] = 0

        claims_done = u["bonus_claims_today"]
        if claims_done == 0:
            u["main_balance"] += 5
            u["bonus_claims_today"] = 1
            u["last_bonus_time"] = current_time
            save_user(user_id, u)
            msg = "✅ <b>অভিনন্দন! আপনি 5 টাকা বোনাস পেয়েছেন।</b>\n\nআপনি আজ আরও 1 বার বোনাস নিতে পারবেন।"
        elif claims_done == 1:
            u["main_balance"] += 5
            u["bonus_claims_today"] = 2
            u["last_bonus_time"] = current_time
            save_user(user_id, u)
            msg = "✅ <b>অভিনন্দন! আপনি 5 টাকা বোনাস পেয়েছেন।</b>\n\nআজকের জন্য আপনার বোনাস নেওয়ার লিমিট শেষ।"
        else:
            remaining_time = int(one_day - (current_time - u["last_bonus_time"]))
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            msg = f"❌ <b>দুঃখিত, আজকের জন্য আপনার বোনাস নেওয়ার লিমিট (২/২) শেষ।</b>\n\nলিমিট রিসেট হতে বাকি: প্রায় {hours} ঘণ্টা {minutes} minute।"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
        return

    if "ডিপোজিট" in text or "deposit" in text.lower():
        current_time = time.time()
        if current_time - u["last_deposit_reset_time"] > 86400:
            u["deposit_count_today"] = 0
            u["last_deposit_reset_time"] = current_time
            save_user(user_id, u)

        if u["deposit_count_today"] >= 3:
            bot.send_message(message.chat.id, " ❌ <b>দুঃখিত! ডেইলি ডিপোজিট লিমিট হচ্ছে ৩ বার।</b>\nআপনি আজ আর ডিপোজিট করতে পারবেন না। আগামীকাল আবার চেষ্টা করুন।")
            return

        user_states[user_id] = {"step": "waiting_amount"}
        bot.send_message(message.chat.id, "আপনি কত টাকা ডিপোজিট করতে চান?\nঅনুগ্রহ করে টাকার পরিমাণ লিখুন:", reply_markup=cancel_keyboard())
        return

    if "উইথড্র" in text or "withdraw" in text.lower():
        active_vips = [name for name, days in u["active_vips"].items() if days > 0]
        if not active_vips:
            bot.send_message(message.chat.id, " ❌ আপনি ভিআইপি সদস্য নন। ভিআইপি না হলে উইথড্র করা যাবে না।")
        else:
            bot.send_message(message.chat.id, f"📤 আপনার মূল ব্যালেন্স: {u['main_balance']}৳\n(সর্বনিম্ন উইথড্র ৫০৳ এবং সর্বোচ্চ ৫০০০৳)\n\nটাকা তোলার জন্য নিচের যেকোনো একটি পেমেন্ট মেথড সিলেক্ট করুন:", reply_markup=withdraw_inline_keyboard())
        return

    if "টাস্ক" in text or "task" in text.lower():
        if u["task_completed"]:
            bot.send_message(message.chat.id, " ❌ আর কোনো টাস্ক বর্তমানে উপলব্ধি নেই।")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📢 চ্যানেল ১ এ জয়েন করুন", url=TASK_CHANNELS[0]["link"]),
            types.InlineKeyboardButton("📢 চ্যানেল ২ এ জয়েন করুন", url=TASK_CHANNELS[1]["link"]),
            types.InlineKeyboardButton("📢 চ্যানেল ৩ এ জয়েন করুন", url=TASK_CHANNELS[2]["link"]),
            types.InlineKeyboardButton("📢 চ্যানেল ৪ এ জয়েন করুন", url=TASK_CHANNELS[3]["link"]),
            types.InlineKeyboardButton("✅ জয়েন করেছি চেক করুন", callback_data="check_channels_join")
        )
        task_text = (
            "📝 <b>নতুন টাস্ক:</b>\n\n"
            "নিচের ৪টি চ্যানেলে অবশ্যই জয়েন করতে হবে। জয়েন করার পর 'জয়েন করেছি চেক করুন' বাটনে চাপ দিন।\n"
            "💰 সফলভাবে ৪টি চ্যানেলে জয়েন করলে পাবেন <b>৪০ টাকা বোনাস!</b>"
        )
        bot.send_message(message.chat.id, task_text, parse_mode="HTML", reply_markup=markup)
        return

    if "রেফার" in text or "refer" in text.lower():
        refer_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        refer_text = (
            "🎁 <b>My Referrals</b>\n\n"
            f"👤 <b>Total Refer:</b> {u['total_refer']} জন\n"
            f"💲 <b>Total Refer Income:</b> {u['refer_income']} BDT\n\n"
            f"🔗 <b>আপনার রেফার লিংক:</b>\n{refer_link}\n\n"
            "ℹ️ আপনি আপনার প্রতিটি রেফারেলের ভিআইপি আপডেট বা ডিপোজিট করা ব্যালেন্স থেকে <b>২০% কমিশন</b> পাবেন।\n\n"
            "📌 বিস্তারিত জানতে নিচের Rules বাটন চাপুন ⤵️"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("👥 রেফারেল মেম্বার লিস্ট", callback_data="view_refer_list"),
            types.InlineKeyboardButton("🪵 Rules", callback_data="view_refer_rules")
        )
        bot.send_message(message.chat.id, refer_text, reply_markup=markup, parse_mode="HTML")
        return

    if "ভিআইপি" in text or "vip" in text.lower():
        if "প্রতিদিন" in text or "income" in text.lower() or "আর" in text or "আয়" in text:
            active_vips = [f"{name} ({days} দিন)" for name, days in u["active_vips"].items() if days > 0]
            if not active_vips:
                vip_income_text = "👉 দুঃখিত আপনার অ্যাক্টিভ করা কোন ভিআইপি নেই,😔 দয়া করে আগে Buy করুন তারপর আজকের ইনকাম নিন বাটনে চাপ দিন।✅"
            else:
                now = datetime.datetime.now()
                current_date_str = now.strftime("%Y-%m-%d")
                if u["last_income_time"] == current_date_str:
                    vip_income_text = "আপনি ইতিমধ্যে আজকে ইনকাম টি ক্লেইম করে নিয়েছেন,✅ কালকে সকালে ১১:০০ টায় আবার চেষ্টা করুন"
                else:
                    vips_str = ", ".join(active_vips)
                    vip_income_text = (
                        f"💰 <b>ভিআইপি প্রতিদিন আয়</b>\n\n"
                        f"👑 একটিভ ভিআইপি: {vips_str}\n\n"
                        f"⏰ <b>ক্লেইমের সময়:</b> প্রতিদিন সকাল ১১:০০ থেকে রাত ১২:০০ am পর্যন্ত যে কোন সময় আপনার ইনকাম টি ক্লেইম করতে পারবেন।\n\n"
                        f"👇 আপনার আজকের ইনকাম এক ক্লিকে নিতে নিচের বাটনে চাপুন:"
                    )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("আজকের ইনকাম নিন 💰", callback_data="claim_daily_income"))
            bot.send_message(message.chat.id, vip_income_text, reply_markup=markup, parse_mode="HTML" if "<b>" in vip_income_text else None)
        else:
            vip_msg = (
    "🏆 <b>VIP Packages</b>\n\n"
    "🥉 <b>Bronze</b> — 150৳ | 8৳/Day\n"
    "🥈 <b>Silver</b> — 300৳ | 17৳/Day\n"
    "🥇 <b>Gold</b> — 500৳ | 30৳/Day\n"
    "💠 <b>Platinum</b> — 700৳ | 40৳/Day\n"
    "💎 <b>Diamond</b> — 1000৳ | 70৳/Day\n"
    "👑 <b>Royal</b> — 1500৳ | 110৳/Day\n"
    "🔥 <b>Legend</b> — 2500৳ | 200৳/Day\n\n"
    "📅 All Packages Valid For 30 Days\n"
    "🚀 Upgrade & Earn Daily!\n\n"
    "👇 <b>প্যাকেজ কিনতে নিচে ক্লিক করুন ❤️</b>"
)

            bot.send_message(message.chat.id, vip_msg, parse_mode="HTML", reply_markup=vip_inline_keyboard())
        return

    if "সাপোর্ট" in text or "support" in text.lower():
        support_text = (
            "যেকোনো প্রয়োজনে আমাদের সাথে\nযোগাযোগ করুন:\n\n"
            "🕵️ এডমিন সাপোর্ট: জরুরী প্রয়োজনে\n"
            "সরাসরি এডমিনকে ইনবক্স করুন।\n"
            "আপডেটের জন্য আমাদের অফিশিয়াল\n"
            "চ্যানেলে যোগ দিন।"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📞 সাপোর্ট", url="https://t.me/Customer_Supportc_Bot"),
            types.InlineKeyboardButton("📢 অফিশিয়াল চ্যানেল", url="https://t.me/online_income_11zone")
        )
        bot.send_message(message.chat.id, support_text, reply_markup=markup)
        return

    if "লটারি" in text or "lottery" in text.lower():
        bot.send_message(message.chat.id, "🎲 লটারি এটি এখন চালু নেই ⛔")
        return

    if user_id in user_states:
        state = user_states[user_id]["step"]

        if state == "waiting_amount":
            if message.text.isdigit():
                user_states[user_id]["amount"] = int(message.text)
                user_states[user_id]["step"] = "waiting_method"
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("বিকাশ (Personal)", callback_data="dep_pay_bkash"),
                    types.InlineKeyboardButton("নগদ (Personal)", callback_data="dep_pay_nagad"),
                    types.InlineKeyboardButton("রকেট (Personal)", callback_data="dep_pay_rocket")
                )
                bot.send_message(message.chat.id, "📲 দয়া করে ডিপোজিট মেথড বাছাই করুন:", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক টাকার পরিমাণ সংখ্যায় লিখুন।")

        elif state == "waiting_txid":
            user_states[user_id]["txid"] = escape_html(message.text)
            user_states[user_id]["step"] = "waiting_confirmation"
            bot.send_message(message.chat.id, f"আপনার ডিপোজিট পরিমাণ {user_states[user_id]['amount']} টাকা। নিশ্চিত করতে বাটন চাপুন।", reply_markup=confirm_keyboard())

        elif state == "waiting_confirmation" and message.text == "✅ নিশ্চিত করুন":
            amount = user_states[user_id]["amount"]
            txid = user_states[user_id].get("txid", "N/A")
            user_states.pop(user_id, None)

            u["deposit_count_today"] += 1
            save_user(user_id, u)

            bot.send_message(message.chat.id, f"✅ আপনার ডিপোজিটের অনুরোধ এডমিনের কাছে পাঠানো হয়েছে। অনুমোদনের জন্য অপেক্ষা করুন।", reply_markup=main_keyboard())

            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"dep_approve_{user_id}_{amount}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"dep_reject_{user_id}_{amount}")
            )

            u_name = u.get("name", "N/A")
            u_uname = u.get("username", "N/A")
            u_bal = u.get("main_balance", 0)
            u_tot_dep = u.get("total_deposit", 0)

            for adm_id in ADMIN_IDS:
                try:
                    bot.send_message(
                        adm_id,
                        f"📥 <b>নতুন ডিপোজিট রিকোয়েস্ট!</b>\n\n"
                        f"👤 নাম: {u_name}\n"
                        f"🔗 ইউজারনেম: @{u_uname}\n"
                        f"🆔 ইউজার আইডি: <code>{user_id}</code>\n"
                        f"💰 মেইন ব্যালেন্স: {u_bal} টাকা\n"
                        f"🏛️ মোট ডিপোজিট: {u_tot_dep} টাকা\n"
                        f"💵 রিকোয়েস্ট পরিমাণ: {amount} টাকা\n"
                        f"🆔 TxID: <code>{txid}</code>\n\n"
                        f"অ্যাকশন নিন:",
                        reply_markup=admin_markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        elif state == "waiting_wth_number":
            phone_number = message.text.strip()
            if re.match(r"^01[3-9]\d{8}$", phone_number):
                user_states[user_id]["number"] = phone_number
                user_states[user_id]["step"] = "waiting_wth_amount"
                bot.send_message(message.chat.id, f"💰 <b>আপনাদের মোট ব্যালেন্স: {u['main_balance']} ৳।</b>\n\nআপনি কত টাকা উইথড্র করতে চান?\nপরিমাণ লিখুন (সর্বনিম্ন ৫০৳ - সর্বোচ্চ ৫০০০৳):", reply_markup=cancel_keyboard())
            else:
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, "❌ <b>ভুল নাম্বার!</b> প্রসেসটি অটো Cancel করা হলো। দয়া করে পরে আবার সঠিক নাম্বার দিয়ে চেষ্টা করুন।", reply_markup=main_keyboard())

        elif state == "waiting_wth_amount":
            if message.text.isdigit() and int(message.text) > 0:
                amt = int(message.text)
                if amt < 50 or amt > 5000:
                    bot.send_message(message.chat.id, f"❌ <b>দুঃখিত! উইথড্র লিমিট কাজ করেনি।</b>\nআপনি সর্বনিম্ন ৫০৳ এবং সর্বোচ্চ ৫০০০৳ পর্যন্ত উইথড্র পারবেন। আবার সঠিক পরিমাণ লিখুন:")
                    return

                if u["main_balance"] >= amt:
                    method = user_states[user_id]["method"]
                    number = user_states[user_id]["number"]
                    user_states.pop(user_id, None)

                    u["main_balance"] -= amt
                    save_user(user_id, u)
                    bot.send_message(message.chat.id, "⏳ আপনার উইথড্র রিকোয়েস্টটি অ্যাডমিনের কাছে পাঠানো হয়েছে। ✅ অনুমোদনের জন্য অপেক্ষা করুন।😊", reply_markup=main_keyboard())

                    wth_markup = types.InlineKeyboardMarkup(row_width=2)
                    wth_markup.add(
                        types.InlineKeyboardButton("✅ Approve", callback_data=f"wth_approve_{user_id}_{amt}"),
                        types.InlineKeyboardButton("❌ Reject", callback_data=f"wth_reject_{user_id}_{amt}")
                    )

                    u_name = u.get("name", "N/A")
                    u_uname = u.get("username", "N/A")
                    u_bal = u.get("main_balance", 0)
                    u_tot_dep = u.get("total_deposit", 0)

                    for adm_id in ADMIN_IDS:
                        try:
                            bot.send_message(
                                adm_id,
                                f"📤 <b>নতুন উইথড্র রিকোয়েস্ট!</b>\n\n"
                                f"👤 নাম: {u_name}\n"
                                f"🔗 ইউজারনেম: @{u_uname}\n"
                                f"🆔 ইউজার আইডি: <code>{user_id}</code>\n"
                                f"💰 অবশিষ্ট মেইন ব্যালেন্স: {u_bal} টাকা\n"
                                f"🏛️ মোট ডিপোজিট: {u_tot_dep} টাকা\n"
                                f"💵 উইথড্র পরিমাণ: {amt} টাকা\n"
                                f"📲 মেথড: {method}\n"
                                f"📞 নাম্বার: <code>{number}</code>\n\n"
                                f"অ্যাকশন নিন:",
                                reply_markup=wth_markup,
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                else:
                    bot.send_message(message.chat.id, "❌ আপনার মেইন ব্যালেন্স পর্যাপ্ত নয়।")
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক এমাউন্ট সংখ্যায় লিখুন।")

        elif state == "adm_waiting_broadcast":
            user_states[user_id]["broadcast_msg"] = message.text
            user_states[user_id]["step"] = "adm_confirm_broadcast"
            bot.send_message(message.chat.id, f"📝 <b>আপনার ব্রডকাস্ট মেসেজটি নিচে দেওয়া হলো:</b>\n\n{message.text}\n\nআপনি কি নিশ্চিত এটি সকল ইউজারের কাছে পাঠাতে চান?", reply_markup=broadcast_confirm_keyboard())

        elif state == "adm_waiting_user_id":
            user_states.pop(user_id, None)
            if message.text.isdigit():
                target = int(message.text)
                init_user(target)
                target_user_data = get_user(target)

                active_vips_list = [f"{n} ({d} দিন)" for n, d in target_user_data["active_vips"].items() if d > 0]
                vips_text = ", ".join(active_vips_list) if active_vips_list else "কোনো প্যাকেজ একটিভ নেই ❌"

                info_text = (
                    f"🕵️‍♂️ <b>ইউজার কন্ট্রোল প্যানেল</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>নাম:</b> {target_user_data['name']}\n"
                    f"🔗 <b>ইউজারনেম:</b> @{target_user_data['username']}\n"
                    f"🆔 <b>টেলিগ্রাম আইডি:</b> <code>{target}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 <b>মোট ব্যালেন্স:</b> {target_user_data['main_balance']} টাকা\n"
                    f"📥 <b>ডিপোজিট ব্যালেন্স:</b> {target_user_data['deposit_balance']} টাকা\n"
                    f"🏛️ <b>টোটাল ডিপোজিট:</b> {target_user_data['total_deposit']} টাকা\n"
                    f"💵 <b>রেফার ইনকাম:</b> {target_user_data['refer_income']} টাকা\n"
                    f"🎁 <b>বোনাস ব্যালেন্স:</b> {target_user_data['bonus_balance']} টাকা\n"
                    f"🧑‍💻 <b>টাস্ক ব্যালেন্স:</b> {target_user_data['task_balance']} টাকা\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🎯 <b>মোট রেফার সংখ্যা:</b> {target_user_data['total_refer']} জন\n"
                    f"📝 <b>টাস্ক সম্পূর্ণ করেছে:</b> {target_user_data['completed_tasks_count']} টি\n"
                    f"👑 <b>একটিভ VIP:</b> {vips_text}\n"
                    f"🚫 <b>ব্যান স্ট্যাটাস:</b> {'ব্যানড ❌' if target_user_data['is_banned'] else 'সচল ✅'}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👇 নিচের বাটনগুলো দিয়ে ডাটা পরিবর্তন করতে পারেন:"
                )
                bot.send_message(message.chat.id, info_text, reply_markup=admin_user_control_keyboard(target), parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ ভুল আইডি। অনুগ্রহ করে সঠিক সংখ্যা আইডি দিন।")

        elif state.startswith("adm_waiting_"):
            parts = state.split("_")
            if len(parts) >= 4:
                field = parts[2]
                target_id = int(parts[3])
                if message.text.isdigit() or (message.text.startswith("-") and message.text[1:].isdigit()):
                    val = int(message.text)
                    init_user(target_id)
                    t_u = get_user(target_id)

                    if field == "main": t_u["main_balance"] = val
                    elif field == "ref": t_u["refer_income"] = val
                    elif field == "bon": t_u["bonus_balance"] = val
                    elif field == "tsk": t_u["task_balance"] = val
                    elif field == "dep":
                        t_u["deposit_balance"] = val
                        t_u["total_deposit"] = val
                    elif field == "cntref": t_u["total_refer"] = val

                    save_user(target_id, t_u)
                    user_states.pop(user_id, None)
                    bot.send_message(message.chat.id, f"✅ ইউজার `{target_id}` এর তথ্য আপডেট সফল হয়েছে।", reply_markup=main_keyboard())
                else:
                    bot.send_message(message.chat.id, "❌ ইনপুটটি সঠিক সংখ্যা ছিল না। আবার চেষ্টা করুন বা '❌ বাতিল' লিখুন।")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data

    if data == "verify_force_join":
        if is_user_joined(user_id):
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(call.message.chat.id, "✅ ধন্যবাদ! সফলভাবে জয়েন করেছেন। এখন আপনি বট ব্যবহার করতে পারবেন।", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "আপনি এখনো আমাদের চ্যানেলে জয়েন করেন নি ❌ দয়া করে চেনেলে জয়েন করে, জয়েন করেছি ✅ বাটনে চাপ দিন।😊", show_alert=True)
        return

    if not is_user_joined(user_id):
        bot.answer_callback_query(call.id, "⚠️ বটের বাটন ব্যবহারের পূর্বে অবশ্যই আমাদের channelগুলোতে জয়েন থাকতে হবে!", show_alert=True)
        return

    if data == "bc_confirm":
        if user_id not in ADMIN_IDS: return
        if user_id in user_states and user_states[user_id].get("step") == "adm_confirm_broadcast":
            b_text = user_states[user_id].get("broadcast_msg", "")
            user_states.pop(user_id, None)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            count = 0
            all_ids = get_all_user_ids()
            for u_id in all_ids:
                try:
                    bot.send_message(u_id, b_text)
                    count += 1
                except Exception: pass
            bot.send_message(call.message.chat.id, f"✅ ব্রডকাস্ট সফল! মোট {count} জন ইউজারের কাছে পাঠানো হয়েছে।")
        bot.answer_callback_query(call.id)
        return

    if data == "bc_cancel":
        if user_id not in ADMIN_IDS: return
        user_states.pop(user_id, None)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        bot.send_message(call.message.chat.id, "❌ ব্রডকাস্ট বাতিল করা হয়েছে।")
        bot.answer_callback_query(call.id)
        return

    if data == "dep_pay_bkash" or data == "dep_pay_rocket":
        bot.answer_callback_query(call.id, "ডিপোজিট শুধু নগদে বিকাশে ও রকেটে কারিগরি সমস্যার কারণে বর্তমানে এটি বন্ধ রয়েছ দয়া করে নগদ ব্যবহার করুন।ধন্যবাদ ❤️🥰", show_alert=True)
        return

    if data == "dep_pay_nagad":
        user_states[user_id]["method"] = "nagad"
        user_states[user_id]["step"] = "waiting_txid"
        amount = user_states[user_id]["amount"]
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass

        dep_instructions = (
            f"আপনার ৳{amount} ডিপোজিট করার জন্য, নিচের নগদ নম্বরটিতে টাকা পাঠান (Send Money):\n\n"
            f"<code>{NUMBER_NAGAD}</code>  (কপি করতে ক্লিক করুন)\n\n"
            f"টাকা পাঠানোর পর ট্রানজেকশন আইডি (TxID) টি এখানে টাইপ করে পাঠান।"
        )
        bot.send_message(call.message.chat.id, dep_instructions, reply_markup=cancel_keyboard(), parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("dep_approve_") or data.startswith("dep_reject_"):
        if user_id not in ADMIN_IDS: return
        parts = data.split("_")
        action = parts[1]
        target_user = int(parts[2])
        amount = int(parts[3])
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        init_user(target_user)
        t_u = get_user(target_user)

        if action == "approve":
            t_u["deposit_balance"] += amount
            t_u["total_deposit"] += amount
            save_user(target_user, t_u)
            bot.send_message(call.message.chat.id, f"✅ ইউজার {target_user} এর {amount} টাকা ডিপোজিট এপ্রুভ করেছেন।")
            try: bot.send_message(target_user, f"আপনার {amount} টাকা ডিপোজিট সফলভাবে এপ্রুভ হয়েছে দয়া করে ডিপোজিট ব্যালেন্স চেক করুন। ধন্যবাদ ❤️🥰")
            except Exception: pass
        else:
            bot.send_message(call.message.chat.id, f"❌ ইউজার {target_user} এর {amount} টাকা ডিপোজিট রিজেক্ট করেছেন")
            try: bot.send_message(target_user, f"আপনার {amount} টাকা ডিপোজিট বাতিল করা হয়েছে, বিস্তারিত জানতে কাস্টমার কেয়ারে কথা বলুন।✅")
            except Exception: pass
        bot.answer_callback_query(call.id)
        return

    if data.startswith("wth_approve_") or data.startswith("wth_reject_"):
        if user_id not in ADMIN_IDS: return
        parts = data.split("_")
        action = parts[1]
        target_user = int(parts[2])
        amount = int(parts[3])
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        init_user(target_user)
        t_u = get_user(target_user)

        if action == "approve":
            add_total_withdraw_approved(amount)
            bot.send_message(call.message.chat.id, f"✅ ইউজার {target_user} এর {amount} টাকা উইথড্র সফল এপ্রুভ।")
            try: bot.send_message(target_user, f"আপনার {amount} টাকা উইড্রো রিকোয়েস্ট টি সফলভাবে এপ্রুভ হয়েছে দয়া করে আপনার কাঙ্খিত ওয়ালেট চেক করুন,আমাদের সাথে থাকার জন্য আপনাকে অসংখ্য ধন্যবাদ ❤️❤️")
            except Exception: pass
        else:
            t_u["main_balance"] += amount
            save_user(target_user, t_u)
            bot.send_message(call.message.chat.id, f"❌ ইউজার {target_user} এর {amount} টাকা উইথড্র রিজেক্ট করেছেন।")
            try:
                bot.send_message(target_user, f"{amount}টাকা উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে এবং {amount}টাকা রিফান্ড করা হয়েছে বিস্তারিত জানতে কাস্টমার কেয়ারে যোগাযোগ করুন।❤️😊")
            except Exception: pass
        bot.answer_callback_query(call.id)
        return

    if data == "adm_user_control":
        user_states[user_id] = {"step": "adm_waiting_user_id"}
        bot.send_message(call.message.chat.id, "🔍 অনুগ্রহ করে ইউজারের টেলিগ্রাম আইডি (ID) দিন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_total_stats":
        total_users = get_total_users_count()
        total_dep = get_total_deposits_sum()
        total_wth = get_total_withdraw_approved()
        stat_text = f"📊 <b>বটের রিয়েল এডমিন স্ট্যাটাস:</b>\n\n👥 মোট ইউজার: {total_users} জন\n📥 মোট ডিপোজিট: {total_dep} টাকা\n💸 মোট উইথড্রো: {total_wth} টাকা"
        bot.send_message(call.message.chat.id, stat_text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_broadcast":
        user_states[user_id] = {"step": "adm_waiting_broadcast"}
        bot.send_message(call.message.chat.id, "📢 ব্রডকাস্ট মেসেজটি লিখুন (যা সবার কাছে চলে যাবে):")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("edit_bal_") or data.startswith("edit_cnt_"):
        parts = data.split("_")
        field = parts[2]
        target_id = parts[3]
        user_states[user_id] = {"step": f"adm_waiting_{field}_{target_id}"}
        bot.send_message(call.message.chat.id, f"📝 নতুন ভ্যালু/সংখ্যাটি টাইপ করে পাঠান:")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_ban_"):
        target_id = int(data.split("_")[2])
        init_user(target_id)
        t_u = get_user(target_id)
        t_u["is_banned"] = True
        save_user(target_id, t_u)
        bot.send_message(call.message.chat.id, f"🚫 ইউজার `{target_id}` সফলভাবে ব্যান হয়েছে।")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_unban_"):
        target_id = int(data.split("_")[2])
        init_user(target_id)
        t_u = get_user(target_id)
        t_u["is_banned"] = False
        save_user(target_id, t_u)
        bot.send_message(call.message.chat.id, f"🟢 ইউজার `{target_id}` আনব্যান করা হয়েছে।")
        bot.answer_callback_query(call.id)
        return

    if data == "view_refer_list":
        members = get_referred_members(user_id)
        if not members:
            bot.send_message(call.message.chat.id, "❌ আপনার রেফার লিংকে ব্যবহার করে এখনো কেউ জয়েন করেনি।")
        else:
            list_text = f"👥 <b>আপনার মোট রেফারেল মেম্বার: {len(members)} জন</b>\n\n"
            list_text += "━━━━━━━━━━━━━━━━━━━━━━\n"
            for index, member in enumerate(members, start=1):
                m_id = member[0]
                m_username = f"@{member[1]}" if member[1] and member[1] != "N/A" else "ইউজারনেম নেই"
                list_text += f"{index}. 🆔 <code>{m_id}</code> — {m_username}\n"
            list_text += "━━━━━━━━━━━━━━━━━━━━━━"
            bot.send_message(call.message.chat.id, list_text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "claim_daily_income":
        init_user(user_id)
        u = get_user(user_id)
        active_vips = [name for name, days in u["active_vips"].items() if days > 0]

        if not active_vips:
            bot.answer_callback_query(
                call.id,
                "👉 দুঃখিত আপনার অ্যাক্টিভ করা কোন ভিআইপি নেই,❌ দয়া করে আগে Buy করুন তারপর আজকের ইনকাম নিন বাটনে চাপ দিন।✅",
                show_alert=True
            )
            return

        now = datetime.datetime.now()
        current_hour = now.hour
        current_date_str = now.strftime("%Y-%m-%d")

        if u["last_income_time"] != "NEW_PACKAGE_CLAIM_PENDING":
            if current_hour < 11:
                bot.answer_callback_query(
                    call.id,
                    "আজকের ইনকাম সকাল ১১:০০ থেকে রাত ১২:০০ am পর্যন্ত যে কোন সময় আপনার ইনকাম টি ক্লেইম করতে পারবেন।",
                    show_alert=True
                )
                return

            if u["last_income_time"] == current_date_str:
                bot.answer_callback_query(
                    call.id,
                    "আপনি ইতিমধ্যে আজকে ইনকাম টি ক্লেইম করে নিয়েছেন 🟢 কালকে সকালে ১১:০০ টায় আবার চেষ্টা করুন",
                    show_alert=True
                )
                return

        total_daily_income = 0
        for vip_name in active_vips:
            total_daily_income += VIP_CONFIG[vip_name]["daily_income"]

        u["main_balance"] += round(total_daily_income, 2)
        u["last_income_time"] = current_date_str
        save_user(user_id, u)

        bot.answer_callback_query(call.id, f"🎉 সফলভাবে আপনার একটিভ সকল ভিআইপি-র আজকের মোট {total_daily_income} টাকা মেইন ব্যালেন্সে যুক্ত হয়েছে!", show_alert=True)
        return

    elif data.startswith('wth_select_'):
        method = data.split('_')[2]
        if method == "rocket":
            bot.answer_callback_query(call.id, "⚠️ কারিগরি সমস্যার কারণে বর্তমানে এটি বন্ধ রয়েছে দয়া করে নগদ ও বিকাশ ব্যবহার করুন ।।", show_alert=True)
            return
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass

        user_states[user_id] = {"step": "waiting_wth_number", "method": method}
        wth_msg = f"✅ আপনি {method} সিলেক্ট করেছেন। এখন ১১ ডিজিটের নাম্বার দিন ☑️ (01xxxxxxxxx):"
        bot.send_message(call.message.chat.id, wth_msg, reply_markup=cancel_keyboard())
        bot.answer_callback_query(call.id)

    elif data == "check_channels_join":
        init_user(user_id)
        u = get_user(user_id)

        if is_user_joined_task_channels(user_id):
            u["bonus_balance"] += 20
            u["task_balance"] += 20
            u["task_completed"] = True
            u["completed_tasks_count"] += 1
            save_user(user_id, u)
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(call.message.chat.id, "🎉 অভিনন্দন! টাস্ক সফল হয়েছে এবং ২০ টাকা টাস্ক ব্যালেন্সে অ্যাড করা হয়েছে।", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো সবকয়টি চ্যানেলে জয়েন করেননি! দয়া করে ৪টি চ্যানেলেই জয়েন করে আবার চেষ্টা করুন।", show_alert=True)
        return

    elif data.startswith('buy_vip_'):
        _, _, name, price = data.split('_')
        price = int(price)
        init_user(user_id)
        u = get_user(user_id)

        if name in u["active_vips"] and u["active_vips"][name] > 0:
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(
                call.message.chat.id,
                f"❌ **দুঃখিত! আপনার এই `{name}` প্যাকেজটি ইতিমধ্যে সচল রয়েছে।**\n"
                f"বর্তমান এই প্যাকেজের মেয়াদ শেষ না হওয়া পর্যন্ত এটি আর কিনতে পারবেন না। তবে চাইলে অন্য প্যাকেজগুলো কিনতে পারেন। ⚠️",
                reply_markup=main_keyboard()
            )
            bot.answer_callback_query(call.id)
            return

        if u["deposit_balance"] < price:
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(call.message.chat.id, f"❌ পর্যাপ্ত ডিপোজিট ব্যালেন্স নেই। দয়া করে ডিপোজিট করে চেষ্টা করুন।", reply_markup=main_keyboard())
        else:
            u["deposit_balance"] -= price
            u["active_vips"][name] = 15
            u["last_income_time"] = "NEW_PACKAGE_CLAIM_PENDING"
            save_user(user_id, u)

            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(
                call.message.chat.id,
                f"🎉 অভিনন্দন! সফলভাবে আপনার {name} একটিভ হয়েছে।\n\n"
                f"💰 আপনি এখনই <b>'💰 ভিআইপি প্রতিদিন আয়'</b> বাটনে গিয়ে আজকের ইনকাম ক্লেইম করে নিতে পারবেন!",
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )

            referrer = u.get("referred_by")
            if referrer is not None:
                init_user(referrer)
                ref_u = get_user(referrer)
                commission = int(price * 0.20)
                ref_u["main_balance"] += commission
                ref_u["refer_income"] += commission
                save_user(referrer, ref_u)
                try:
                    bot.send_message(referrer, f"🎉 <b>রেফার কমিশন নোটিফিকেশন!</b>\n\nআপনার লিংকে জয়েন করা মেম্বার <b>{u['name']}</b> একটি প্যাকেজ <code>{name}</code> কিনেছেন। আপনি তার থেকে <b>২০% কমিশন ({commission} টাকা)</b> সরাসরি মেইন ব্যালেন্সে পেয়েছেন।", parse_mode="HTML")
                except Exception: pass

        bot.answer_callback_query(call.id)

    elif data == "view_refer_rules":
        bot.answer_callback_query(call.id, "📜 রেফারেল নিয়মাবলী: ২০% কমিশন সরাসরি আপনার মেইন ব্যালেন্সে পাবেন।", show_alert=True)

# ===== Web Server logic for hosting =====
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is alive and running fine!")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebServer)
    print(f"Web Server triggered on port {port} for cloud hosting compatibility.")
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

print("Bot is successfully running...")
bot.infinity_polling(allowed_updates=['message', 'callback_query'], timeout=60, long_polling_timeout=30)
