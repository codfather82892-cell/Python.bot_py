import datetime
import json
import os
import random
import re
import sqlite3
import threading
import time
import telebot
from telebot import types

# ⚠️ আপনার আসল Bot Token দিয়ে এটি পরিবর্তন করুন
API_TOKEN = "8692563741:AAHUpABl5IpMEiU45ASu-kIqc9q7BcY0StA"
BOT_USERNAME = "wahoearn2026bot"

# মেইন এডমিন লিস্ট (সুপার এডমিন)
ADMIN_IDS = [2037461288, 7657001009]

HISTORY_CHANNEL_ID = "@All_History_Channel"
PERMANENT_CHANNEL_LINK = "https://t.me/WahoEarnOfficial"

# ভেরিফিকেশন চ্যানেলসমূহ
DEFAULT_MUST_JOIN_CHANNELS = [
    {"link": "https://t.me/Easy_Earnigs838", "id": "@Easy_Earnigs838"},
    {"link": "https://t.me/Waho_Earn_officiall", "id": "@Waho_Earn_officiall"},
]

DEFAULT_TASK_CHANNELS = [
    {"link": "https://t.me/Easy_Earnigs838", "id": "@Easy_Earnigs838"},
    {"link": "https://t.me/Online_Earnings_Bd", "id": "@Online_Earnings_Bd"},
    {"link": "https://t.me/Cpa_marketing_18", "id": "@Cpa_marketing_18"},
    {"link": "https://t.me/Waho_Free_income", "id": "@Waho_Free_income"},
    {"link": "https://t.me/OnlineIncomeCommunity01", "id": "@OnlineIncomeCommunity01"},
]

DEFAULT_VIP_CONFIG = {
    "Bronze": {"price": 150, "daily_income": 12, "days": 15},
    "Silver": {"price": 300, "daily_income": 25, "days": 15},
    "Gold": {"price": 500, "daily_income": 40, "days": 15},
    "Platinum": {"price": 700, "daily_income": 60, "days": 15},
    "Diamond": {"price": 1000, "daily_income": 90, "days": 15},
    "Royal": {"price": 1500, "daily_income": 140, "days": 15},
    "Legend": {"price": 2500, "daily_income": 250, "days": 15},
}

bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=20)
user_states = {}

DB_DIR = "data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_FILE = os.path.join(DB_DIR, "bot_database.db")

db_lock = threading.Lock()
SETTINGS_CACHE = {}

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def run_async(target, *args, **kwargs):
    threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True).start()

def build_grid(markup, buttons, per_row=2):
    for i in range(0, len(buttons), per_row):
        markup.row(*buttons[i:i + per_row])
    return markup

def init_db():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT, username TEXT,
            main_balance REAL, bonus_balance REAL, deposit_balance REAL,
            task_balance REAL, total_deposit REAL, active_vips TEXT,
            task_completed INTEGER, completed_tasks_count INTEGER,
            last_income_time TEXT, referred_by INTEGER, total_refer INTEGER,
            refer_income REAL, bonus_claims_today INTEGER, last_bonus_time REAL,
            is_banned INTEGER, deposit_count_today INTEGER,
            last_deposit_reset_time REAL)""")
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS tx_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, tx_type TEXT,
            method TEXT, amount REAL, txid_or_num TEXT, order_number TEXT,
            status TEXT, timestamp TEXT)""")
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS system_stats (
            stat_name TEXT PRIMARY KEY, stat_value TEXT)""")
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS bot_commands_control (
            command_name TEXT PRIMARY KEY, is_active INTEGER, command_desc TEXT)""")
            
        cursor.execute("""CREATE TABLE IF NOT EXISTS admin_roles (
            user_id INTEGER PRIMARY KEY, role TEXT)""")

        defaults = [
            ("total_withdraw_approved", "0"),
            ("withdraw_status", "on"),
            ("deposit_status", "on"),
            ("bot_status", "on"),
            ("min_deposit", "150"),
            ("max_deposit_limit", "3"),
            ("min_withdraw", "50"),
            ("max_withdraw", "5000"),
            ("task_reward", "40"),
            ("task_channels", json.dumps(DEFAULT_TASK_CHANNELS)),
            ("must_join_channels", json.dumps(DEFAULT_MUST_JOIN_CHANNELS)),
            ("vip_config", json.dumps(DEFAULT_VIP_CONFIG)),
            ("bkash_number", "01406314954"),
            ("nagad_number", "01406314954"),
            ("bkash_status", "on"),
            ("nagad_status", "on"),
            ("wth_bkash_status", "on"),
            ("wth_nagad_status", "on"),
            ("wth_rocket_status", "on"),
            ("wth_upay_status", "on"),
        ]
        for k, v in defaults:
            cursor.execute(
                "INSERT OR IGNORE INTO system_stats (stat_name, stat_value) VALUES (?, ?)",
                (k, v))

        conn.commit()
        
        cursor.execute("SELECT stat_name, stat_value FROM system_stats")
        for row in cursor.fetchall():
            SETTINGS_CACHE[row[0]] = str(row[1]).strip() if row[1] is not None else None
            
        conn.close()

init_db()

def get_system_setting(stat_name):
    if stat_name in SETTINGS_CACHE:
        val = SETTINGS_CACHE[stat_name]
        if val and val.endswith(".0"):
            val = val[:-2]
        return val
    
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stat_value FROM system_stats WHERE stat_name = ?", (stat_name,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] is not None:
            val = str(row[0]).strip()
            SETTINGS_CACHE[stat_name] = val
            if val.endswith(".0"):
                val = val[:-2]
            return val
    return None

def set_system_setting(stat_name, stat_value):
    val_str = str(stat_value)
    SETTINGS_CACHE[stat_name] = val_str
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO system_stats (stat_name, stat_value) VALUES (?, ?)",
            (stat_name, val_str))
        conn.commit()
        conn.close()

def get_vip_config():
    val = get_system_setting("vip_config")
    try:
        return json.loads(val)
    except Exception:
        return DEFAULT_VIP_CONFIG

def set_vip_config(config_dict):
    set_system_setting("vip_config", json.dumps(config_dict))

def get_admin_role(user_id):
    if user_id in ADMIN_IDS:
        return "super_admin"
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM admin_roles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    return None

def set_admin_role(user_id, role):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        if role == "remove":
            cursor.execute("DELETE FROM admin_roles WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("INSERT OR REPLACE INTO admin_roles (user_id, role) VALUES (?, ?)", (user_id, role))
        conn.commit()
        conn.close()

def get_admins_by_role(role):
    admins = [uid for uid in ADMIN_IDS]
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admin_roles WHERE role = ? OR role = 'full_admin'", (role,))
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            if r[0] not in admins:
                admins.append(r[0])
    return admins

def format_phone_number(val):
    if not val:
        return "01406314954"
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    if len(val_str) == 10 and val_str.startswith("1"):
        val_str = "0" + val_str
    return val_str

def is_command_active(cmd_name):
    return True

def get_task_channels():
    val = get_system_setting("task_channels")
    try:
        channels = json.loads(val)
    except Exception:
        channels = DEFAULT_TASK_CHANNELS
    return channels

def get_must_join_channels():
    val = get_system_setting("must_join_channels")
    try:
        channels = json.loads(val)
    except Exception:
        channels = DEFAULT_MUST_JOIN_CHANNELS
    return channels

def generate_order_number():
    now = datetime.datetime.now()
    rand_part = "".join([str(random.randint(0, 9)) for _ in range(10)])
    return "RC" + now.strftime('%Y%m%d%H%M%S') + rand_part

def add_to_history(user_id, tx_type, method, amount, txid_or_num, order_number, status):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO tx_history (user_id, tx_type, method, amount, txid_or_num, order_number, status, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, tx_type, method, amount, txid_or_num, order_number, status, timestamp))
        conn.commit()
        conn.close()

def update_history_status(order_number, new_status, new_txid=""):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        if new_txid:
            cursor.execute("UPDATE tx_history SET status = ?, txid_or_num = ? WHERE order_number = ?",
                           (new_status, new_txid, order_number))
        else:
            cursor.execute("UPDATE tx_history SET status = ? WHERE order_number = ?",
                           (new_status, order_number))
        conn.commit()
        conn.close()

def get_total_withdraw_approved():
    return float(get_system_setting("total_withdraw_approved") or 0)

def add_total_withdraw_approved(amount):
    current = get_total_withdraw_approved()
    set_system_setting("total_withdraw_approved", current + amount)

def get_user(user_id):
    with db_lock:
        conn = get_db_connection()
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
                "last_deposit_reset_time": row[19],
            }
        return None

def save_user(user_id, u):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        vips_str = json.dumps(u.get("active_vips", {}))
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, name, username, main_balance, bonus_balance, deposit_balance, task_balance, total_deposit, active_vips, task_completed, completed_tasks_count, last_income_time, referred_by, total_refer, refer_income, bonus_claims_today, last_bonus_time, is_banned, deposit_count_today, last_deposit_reset_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, u.get("name", "User"), u.get("username", "N/A"),
             u.get("main_balance", 0), u.get("bonus_balance", 10),
             u.get("deposit_balance", 0), u.get("task_balance", 0),
             u.get("total_deposit", 0), vips_str,
             int(u.get("task_completed", False)), u.get("completed_tasks_count", 0),
             str(u.get("last_income_time", "")), u.get("referred_by"),
             u.get("total_refer", 0), u.get("refer_income", 0),
             u.get("bonus_claims_today", 0), u.get("last_bonus_time", 0),
             int(u.get("is_banned", False)), u.get("deposit_count_today", 0),
             u.get("last_deposit_reset_time", 0)))
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
            "last_deposit_reset_time": 0,
        }
        save_user(user_id, u)

def get_total_users_count():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count

def get_total_deposits_sum():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_deposit) FROM users")
        total = cursor.fetchone()[0] or 0
        conn.close()
        return total

def get_total_vip_buyers_count():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT active_vips FROM users")
        rows = cursor.fetchall()
        conn.close()
        count = 0
        for row in rows:
            if row[0]:
                try:
                    vips = json.loads(row[0])
                    if any(days > 0 for days in vips.values()):
                        count += 1
                except Exception:
                    pass
        return count

def get_all_user_ids():
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

def get_referred_members(user_id):
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username FROM users WHERE referred_by = ?", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows

def check_must_join_channels(user_id):
    try:
        blocked = ["left", "kicked", "restricted"]
        for chan in get_must_join_channels():
            member = bot.get_chat_member(chan["id"], user_id)
            if member.status in blocked:
                return False
        return True
    except Exception:
        return True

# FIX 1: Strict Check for Task Channels
def is_user_joined_task_channels(user_id):
    try:
        blocked = ["left", "kicked", "restricted"]
        for chan in get_task_channels():
            member = bot.get_chat_member(chan["id"], user_id)
            if member.status in blocked:
                return False
        return True
    except Exception as e:
        return False

def send_welcome_join_message(chat_id):
    must_channels = get_must_join_channels()

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 অফিশিয়াল চ্যানেল", url=PERMANENT_CHANNEL_LINK))

    i = 1
    for chan in must_channels:
        markup.add(types.InlineKeyboardButton(f"📢 চ্যানেল {i}", url=chan["link"]))
        i += 1

    markup.add(types.InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_start_join"))

    text = (
        "✨ <b>স্বাগতম আমাদের অফিশিয়াল আনিং বটে!</b> ✨\n\n"
        "বটটি সম্পূর্ণরূপে ব্যবহার করার জন্য অনুগ্রহ করে আমাদের অফিশিয়াল চ্যানেলে জয়েন করুন। "
        "জয়েন করা সম্পন্ন হলে নিচের <b>'✅ জয়েন করেছি'</b> বাটনে ক্লিক করুন। 👇"
    )
    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row1 = [types.KeyboardButton("📥 ডিপোজিট"), types.KeyboardButton("📤 উইথড্র")]
    row2 = [types.KeyboardButton("💰 রেফার"), types.KeyboardButton("⭐ ভিআইপি")]
    row3 = [types.KeyboardButton("📝 টাস্ক"), types.KeyboardButton("🎁 বোনাস")]
    row4 = [types.KeyboardButton("👤 একাউন্ট"), types.KeyboardButton("📈 VIP Daily Earnings")]
    row5 = [types.KeyboardButton("📞 সাপোর্ট"), types.KeyboardButton("💸 লটারি")]
    row6 = [types.KeyboardButton("💸 ব্যালেন্স ট্রান্সফার")]
    markup.add(*row1)
    markup.add(*row2)
    markup.add(*row3)
    markup.add(*row4)
    markup.add(*row5)
    markup.add(*row6)
    return markup

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("❌ বাতিল"))
    return markup

def vip_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    vip_cfg = get_vip_config()
    btns = []
    for name, info in vip_cfg.items():
        price = info.get("price", 0)
        btns.append(types.InlineKeyboardButton(f"⭐ {name} {price}৳", callback_data=f"buy_vip_{name}_{price}"))
    build_grid(markup, btns, 2)
    return markup

def deposit_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    b_stat = get_system_setting("bkash_status")
    n_stat = get_system_setting("nagad_status")
    btns = []
    if b_stat == "on":
        btns.append(types.InlineKeyboardButton("💳 বিকাশ (bKash)", callback_data="web_dep_bkash"))
    if n_stat == "on":
        btns.append(types.InlineKeyboardButton("🧡 নগদ (Nagad)", callback_data="web_dep_nagad"))
    if not btns:
        return None
    build_grid(markup, btns, 2)
    return markup

# FIX 4: Withdraw Methods Dynamic Keyboard
def withdraw_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    btns = []
    if get_system_setting("wth_bkash_status") == "on":
        btns.append(types.InlineKeyboardButton("💳 বিকাশ", callback_data="wth_select_বিকাশ"))
    if get_system_setting("wth_nagad_status") == "on":
        btns.append(types.InlineKeyboardButton("🧡 নগদ", callback_data="wth_select_নগদ"))
    if get_system_setting("wth_rocket_status") == "on":
        btns.append(types.InlineKeyboardButton("💜 রকেট", callback_data="wth_select_rocket"))
    if get_system_setting("wth_upay_status") == "on":
        btns.append(types.InlineKeyboardButton("💙 উপায়", callback_data="wth_select_উপায়"))
    
    if not btns:
        return None
    build_grid(markup, btns, 2)
    return markup

def admin_main_keyboard(user_id):
    role = get_admin_role(user_id)
    markup = types.InlineKeyboardMarkup()
    btns = []

    # Withdraw Admin View
    if role == "withdraw_admin":
        w_status = get_system_setting("withdraw_status")
        btns.append(types.InlineKeyboardButton("📤 উইথড্র " + ("🟢" if w_status == "on" else "🔴"), callback_data="adm_toggle_withdraw"))
        build_grid(markup, btns, 2)
        return markup

    # Deposit Admin View
    if role == "deposit_admin":
        d_status = get_system_setting("deposit_status")
        btns.append(types.InlineKeyboardButton("📥 ফান্ড " + ("🟢" if d_status == "on" else "🔴"), callback_data="adm_toggle_deposit"))
        build_grid(markup, btns, 2)
        return markup

    # Super Admin / Full Admin View
    w_status = get_system_setting("withdraw_status")
    d_status = get_system_setting("deposit_status")
    b_status = get_system_setting("bot_status") or "on"
    b_stat = get_system_setting("bkash_status") or "on"
    n_stat = get_system_setting("nagad_status") or "on"
    
    w_b_stat = get_system_setting("wth_bkash_status") or "on"
    w_n_stat = get_system_setting("wth_nagad_status") or "on"
    w_r_stat = get_system_setting("wth_rocket_status") or "on"
    w_u_stat = get_system_setting("wth_upay_status") or "on"

    min_dep = get_system_setting("min_deposit") or "150"
    max_dep_limit = get_system_setting("max_deposit_limit") or "3"
    min_wth = get_system_setting("min_withdraw") or "50"
    max_wth = get_system_setting("max_withdraw") or "5000"
    t_reward = get_system_setting("task_reward") or "40"

    btns = [
        types.InlineKeyboardButton("⚙️ ইউজার কন্ট্রোল", callback_data="adm_user_control"),
        types.InlineKeyboardButton("👨‍💼 অ্যাডমিন রোল ম্যানেজ", callback_data="adm_manage_roles"),
        types.InlineKeyboardButton("📊 টোটাল স্ট্যাটাস", callback_data="adm_total_stats"),
        types.InlineKeyboardButton("📢 ব্রডকাস্ট", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("⭐ VIP প্যাকেজ সেটিংস", callback_data="adm_manage_vips"),
        types.InlineKeyboardButton("🤖 বট " + ("🟢" if b_status == "on" else "🔴"), callback_data="adm_toggle_bot_status"),
        types.InlineKeyboardButton("📥 ফান্ড " + ("🟢" if d_status == "on" else "🔴"), callback_data="adm_toggle_deposit"),
        types.InlineKeyboardButton("📤 উইথড্র " + ("🟢" if w_status == "on" else "🔴"), callback_data="adm_toggle_withdraw"),
        
        # Deposit controls
        types.InlineKeyboardButton("💳 dep বিকাশ " + ("🟢" if b_stat == "on" else "🔴"), callback_data="adm_toggle_bkash"),
        types.InlineKeyboardButton("🧡 dep নগদ " + ("🟢" if n_stat == "on" else "🔴"), callback_data="adm_toggle_nagad"),
        
        # Withdraw controls
        types.InlineKeyboardButton("💳 wth বিকাশ " + ("🟢" if w_b_stat == "on" else "🔴"), callback_data="adm_toggle_wth_bkash"),
        types.InlineKeyboardButton("🧡 wth নগদ " + ("🟢" if w_n_stat == "on" else "🔴"), callback_data="adm_toggle_wth_nagad"),
        types.InlineKeyboardButton("💜 wth রকেট " + ("🟢" if w_r_stat == "on" else "🔴"), callback_data="adm_toggle_wth_rocket"),
        types.InlineKeyboardButton("💙 wth উপায় " + ("🟢" if w_u_stat == "on" else "🔴"), callback_data="adm_toggle_wth_upay"),
        types.InlineKeyboardButton("🚫 সব উইথড্র On/Off", callback_data="adm_toggle_all_withdraw_methods"),

        types.InlineKeyboardButton("📝 বিকাশ নম্বর সেট", callback_data="adm_set_bkash_num"),
        types.InlineKeyboardButton("📝 নগদ নম্বর সেট", callback_data="adm_set_nagad_num"),
        types.InlineKeyboardButton("💰 Min Dep (" + str(min_dep) + "৳)", callback_data="adm_set_min_deposit"),
        types.InlineKeyboardButton("🔄 Dep লিমিট (" + str(max_dep_limit) + " বার)", callback_data="adm_set_max_deposit_limit"),
        types.InlineKeyboardButton("📤 Min Wth (" + str(min_wth) + "৳)", callback_data="adm_set_min_withdraw"),
        types.InlineKeyboardButton("📤 Max Wth (" + str(max_wth) + "৳)", callback_data="adm_set_max_withdraw"),
        types.InlineKeyboardButton("🎁 রিওয়ার্ড (" + str(t_reward) + "৳)", callback_data="adm_set_task_reward"),
        types.InlineKeyboardButton("📢 টাস্ক চ্যানেল", callback_data="adm_manage_task_channels"),
        types.InlineKeyboardButton("📢 বাধ্য চ্যালেন কন্ট্রোল", callback_data="adm_manage_must_channels"),
    ]
    build_grid(markup, btns, 2)
    return markup

def admin_user_control_keyboard(target_id):
    markup = types.InlineKeyboardMarkup()
    btns = [
        types.InlineKeyboardButton("👑 VIP এডিট", callback_data="adm_edit_vip_menu_" + str(target_id)),
        types.InlineKeyboardButton("💰 মোট ব্যালেন্স", callback_data="edit_bal_main_" + str(target_id)),
        types.InlineKeyboardButton("💵 রেফার ব্যালেন্স", callback_data="edit_bal_ref_" + str(target_id)),
        types.InlineKeyboardButton("🎁 বোনাস ব্যালেন্স", callback_data="edit_bal_bon_" + str(target_id)),
        types.InlineKeyboardButton("🧑‍💻 টাস্ক ব্যালেন্স", callback_data="edit_bal_tsk_" + str(target_id)),
        types.InlineKeyboardButton("📥 ফান্ড ব্যালেন্স", callback_data="edit_bal_dep_" + str(target_id)),
        types.InlineKeyboardButton("🎯 রেফার সংখ্যা", callback_data="edit_cnt_cntref_" + str(target_id)),
        types.InlineKeyboardButton("🚫 ব্যান", callback_data="adm_ban_" + str(target_id)),
        types.InlineKeyboardButton("🟢 আনব্যান", callback_data="adm_unban_" + str(target_id)),
    ]
    build_grid(markup, btns, 2)
    return markup

def broadcast_confirm_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Confirm", callback_data="bc_confirm"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel"))
    return markup

def send_account_details(chat_id, user_id, first_name, username):
    init_user(user_id, first_name, username)
    u = get_user(user_id)
    active_vips_list = [n + " (" + str(d) + " দিন)" for n, d in u["active_vips"].items() if d > 0]
    vips_text = ", ".join(active_vips_list) if active_vips_list else "কোনো প্যাকেজ একটিভ নেই ❌"

    account_text = (
        "📊 <b>আপনার অ্যাকাউন্ট তথ্য</b> 📊\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>নাম:</b> " + str(u['name']) + "\n"
        "🔗 <b>ইউজারনেম:</b> @" + str(u['username']) + "\n"
        "🆔 <b>ইউজার আইডি:</b> <code>" + str(user_id) + "</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 <b>মোট রেফার:</b> " + str(u['total_refer']) + " জন\n"
        "💵 <b>রেফার ব্যালেন্স:</b> " + str(int(u['refer_income']) if u['refer_income'].is_integer() else u['refer_income']) + " টাকা\n"
        "💰 <b>মোট ব্যালেন্স:</b> " + str(int(u['main_balance']) if u['main_balance'].is_integer() else u['main_balance']) + " টাকা\n"
        "🎁 <b>বোনাস ব্যালেন্স:</b> " + str(int(u['bonus_balance']) if u['bonus_balance'].is_integer() else u['bonus_balance']) + " টাকা\n"
        "👨‍💻 <b>টাস্ক ব্যালেন্স:</b> " + str(int(u['task_balance']) if u['task_balance'].is_integer() else u['task_balance']) + " টাকা\n"
        "📥 <b>ফান্ড ব্যালেন্স:</b> " + str(int(u['deposit_balance']) if u['deposit_balance'].is_integer() else u['deposit_balance']) + " টাকা\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👑 <b>ভিআইপি সদস্য:</b> " + vips_text + "\n"
        "📝 <b>টাস্ক সম্পন্ন:</b> " + str(u['completed_tasks_count']) + " টি\n"
        "🚫 <b>নিষিদ্ধ:</b> " + ("হ্যাঁ" if u['is_banned'] else "না") + "\n"
        "🏛️ <b>মোট ফান্ড অ্যামাউন্ট:</b> " + str(int(u['total_deposit']) if u['total_deposit'].is_integer() else u['total_deposit']) + " টাকা\n"
        "━━━━━━━━━━━━━━━━━━━━━━")
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][0].file_id
            bot.send_photo(chat_id, file_id, caption=account_text, parse_mode="HTML")
            return
    except Exception:
        pass
    bot.send_message(chat_id, account_text, parse_mode="HTML")

# FIX 3: Role-Based Admin Notification Routing
def _notify_withdraw_request(u, user_id, amt, method, number, order_num):
    u_name = u.get("name", "N/A")
    u_uname = u.get("username", "N/A")
    u_bal = int(u.get("main_balance", 0)) if str(u.get("main_balance", 0)).replace('.','',1).isdigit() and float(u.get("main_balance", 0)).is_integer() else u.get("main_balance", 0)
    u_tot_dep = int(u.get("total_deposit", 0)) if str(u.get("total_deposit", 0)).replace('.','',1).isdigit() and float(u.get("total_deposit", 0)).is_integer() else u.get("total_deposit", 0)

    try:
        channel_wth_text = (
            "📤 <b>নতুন উইথড্র রিকোয়েস্ট! (Pending)</b>\n\n"
            "👤 নাম: " + str(u_name) + "\n🔗 ইউজারনেম: @" + str(u_uname) + "\n"
            "🆔 ইউজার আইডি: <code>" + str(user_id) + "</code>\n"
            "💰 উইথড্র পরিমাণ: " + str(amt) + " টাকা\n📲 মেথড: " + str(method) + "\n"
            "📞 নাম্বার: <code>" + str(number) + "</code>\n"
            "🆔 Order No: <code>" + str(order_num) + "</code>\n⏳ স্ট্যাটাস: Pending")
        bot.send_message(HISTORY_CHANNEL_ID, channel_wth_text, parse_mode="HTML")
    except Exception:
        pass

    wth_markup = types.InlineKeyboardMarkup()
    wth_markup.row(
        types.InlineKeyboardButton("✅ Approve", callback_data="wth_approve_" + str(order_num)),
        types.InlineKeyboardButton("❌ Reject", callback_data="wth_reject_" + str(order_num)))

    # Notify super admins & withdraw admins only
    wth_admins = get_admins_by_role("withdraw_admin")
    for adm_id in wth_admins:
        try:
            bot.send_message(adm_id,
                "📤 <b>নতুন উইথড্র রিকোয়েস্ট!</b>\n\n"
                "👤 নাম: " + str(u_name) + "\n🔗 ইউজারনেম: @" + str(u_uname) + "\n"
                "🆔 ইউজার আইডি: <code>" + str(user_id) + "</code>\n"
                "💰 অবশিষ্ট মেইন ব্যালেন্স: " + str(u_bal) + " টাকা\n"
                "🏛️ মোট ফান্ড: " + str(u_tot_dep) + " টাকা\n"
                "💵 উইথড্র পরিমাণ: " + str(amt) + " টাকা\n📲 মেথড: " + str(method) + "\n"
                "📞 নাম্বার: <code>" + str(number) + "</code>\n"
                "🆔 Order No: <code>" + str(order_num) + "</code>\n\nঅ্যাকশন নিন:",
                reply_markup=wth_markup, parse_mode="HTML")
        except Exception:
            pass

def _notify_deposit_request(u, user_id, method_type, amt, txid, order_num):
    u_name = u.get("name", "N/A")
    u_uname = u.get("username", "N/A")

    try:
        channel_dep_text = (
            "📥 <b>নতুন ইনলাইন ফান্ড রিকোয়েস্ট! (Pending)</b>\n\n"
            "👤 নাম: " + str(u_name) + "\n🔗 ইউজারনেম: @" + str(u_uname) + "\n"
            "🆔 ইউজার আইডি: <code>" + str(user_id) + "</code>\n"
            "⚙️ মেথড: <b>" + str(method_type) + "</b>\n"
            "💰 অ্যামাউন্ট: <code>" + str(amt) + "</code> BDT\n"
            "🆔 TxID: <code>" + str(txid) + "</code>\n"
            "📝 Order No: <code>" + str(order_num) + "</code>\n⏳ স্ট্যাটাস: Pending")
        bot.send_message(HISTORY_CHANNEL_ID, channel_dep_text, parse_mode="HTML")
    except Exception:
        pass

    admin_markup = types.InlineKeyboardMarkup()
    admin_markup.row(
        types.InlineKeyboardButton("✅ Approve", callback_data="inline_approve_" + str(order_num)),
        types.InlineKeyboardButton("❌ Reject", callback_data="inline_reject_" + str(order_num)))

    # Notify super admins & deposit admins only
    dep_admins = get_admins_by_role("deposit_admin")
    for adm_id in dep_admins:
        try:
            bot.send_message(adm_id,
                "📥 <b>নতুন ইনলাইন ফান্ড রিকোয়েস্ট!</b>\n\n"
                "👤 নাম: " + str(u_name) + "\n🔗 ইউজারনেম: @" + str(u_uname) + "\n"
                "🆔 ইউজার আইডি: <code>" + str(user_id) + "</code>\n"
                "⚙️ মেথড: <b>" + str(method_type) + "</b>\n"
                "💰 অ্যামাউন্ট: <code>" + str(amt) + "</code> BDT\n"
                "🆔 TxID: <code>" + str(txid) + "</code>\n"
                "📝 Order No: <code>" + str(order_num) + "</code>\n\nঅ্যাকশন নিন:",
                reply_markup=admin_markup, parse_mode="HTML")
        except Exception:
            pass

@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = message.from_user.id
    role = get_admin_role(user_id)
    
    if not is_command_active("start") and not role:
        bot.send_message(message.chat.id, "❌ এই কমান্ডটি বর্তমানে বন্ধ রাখা হয়েছে।")
        return

    b_status = get_system_setting("bot_status") or "on"
    if b_status == "off" and not role:
        bot.send_message(message.chat.id, "🔴 বট বর্তমানে রক্ষণাবেক্ষণ বা বন্ধ রয়েছে। দয়া করে পরে চেষ্টা করুন।")
        return

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
                run_async(lambda: bot.send_message(referrer_id,
                    "🔔 আপনার রেফার লিংকে ক্লিক করে নতুন মেম্বার <b>" + str(u['name']) + "</b> জয়েন করেছেন!",
                    parse_mode="HTML"))

    if not check_must_join_channels(user_id):
        send_welcome_join_message(message.chat.id)
        return

    bot.send_message(message.chat.id,
        "👋 স্বাগতম! নিচে থেকে একটি অপশন বেছে নিন 👇",
        reply_markup=main_keyboard(), parse_mode="HTML")

@bot.message_handler(commands=["admin"])
def admin_panel_command(message):
    user_id = message.from_user.id
    role = get_admin_role(user_id)
    if not role:
        return
    user_states.pop(user_id, None)
    bot.send_message(message.chat.id, "⚙️ <b>অ্যাডমিন প্যানেলে স্বাগতম:</b>",
                     reply_markup=admin_main_keyboard(user_id), parse_mode="HTML")

@bot.message_handler(func=lambda message: True)
def handle_inputs(message):
    user_id = message.from_user.id
    role = get_admin_role(user_id)

    b_status = get_system_setting("bot_status") or "on"
    if b_status == "off" and not role:
        return

    init_user(user_id, message.from_user.first_name, message.from_user.username)
    u = get_user(user_id)

    if u["is_banned"]:
        bot.send_message(message.chat.id, "🚫 আপনাকে এই বট থেকে ব্লক করা হয়েছে।")
        return

    text = message.text.strip()

    if user_id in user_states:
        state = user_states[user_id]["step"]

        if text in ["❌ বাতিল", "❌ বাতিল করুন"]:
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "❌ প্রসেসটি বাতিল করা হয়েছে।",
                             reply_markup=main_keyboard())
            return

        # ================= ADMIN SETTINGS INPUTS =================
        if state == "adm_waiting_min_deposit":
            if text.isdigit() and int(text) > 0:
                set_system_setting("min_deposit", text)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ সর্বনিম্ন ফান্ড যোগ সফলভাবে {text} ৳ সেট করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক অ্যামাউন্ট সংখ্যায় লিখুন:")
            return

        if state == "adm_waiting_max_deposit_limit":
            if text.isdigit() and int(text) > 0:
                set_system_setting("max_deposit_limit", text)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ ডেইলি ফান্ড লিমিট সফলভাবে {text} বার সেট করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক সংখ্যায় লিখুন:")
            return

        # FIX 2: Dynamic Withdraw Limit Inputs
        if state == "adm_waiting_min_withdraw":
            if text.isdigit() and int(text) > 0:
                set_system_setting("min_withdraw", text)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ সর্বনিম্ন উইথড্র সফলভাবে {text} ৳ সেট করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক সংখ্যায় লিখুন:")
            return

        if state == "adm_waiting_max_withdraw":
            if text.isdigit() and int(text) > 0:
                set_system_setting("max_withdraw", text)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ সর্বোচ্চ উইথড্র সফলভাবে {text} ৳ সেট করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক সংখ্যায় লিখুন:")
            return

        if state == "adm_waiting_task_reward":
            if text.isdigit() or (text.replace('.', '', 1).isdigit() and float(text) > 0):
                set_system_setting("task_reward", text)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ টাস্ক রিওয়ার্ড সফলভাবে {text} ৳ সেট করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক অ্যামাউন্ট সংখ্যায় লিখুন:")
            return

        if state == "adm_waiting_bkash_num":
            set_system_setting("bkash_number", format_phone_number(text))
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ বিকাশ নাম্বার সফলভাবে আপডেট করা হয়েছে!", reply_markup=main_keyboard())
            return

        if state == "adm_waiting_nagad_num":
            set_system_setting("nagad_number", format_phone_number(text))
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id, "✅ নগদ নাম্বার সফলভাবে আপডেট করা হয়েছে!", reply_markup=main_keyboard())
            return

        if state == "adm_waiting_new_must_channel":
            parts = text.split("|")
            if len(parts) == 2:
                c_link = parts[0].strip()
                c_id = parts[1].strip()
                channels = get_must_join_channels()
                channels.append({"link": c_link, "id": c_id})
                set_system_setting("must_join_channels", json.dumps(channels))
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, "✅ নতুন বাধ্যতামূলক জয়েন চ্যানেল যুক্ত করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ ফরম্যাট সঠিক নয়! আবার ট্রাই করুন:\n`https://t.me/channel | @channel`", parse_mode="HTML")
            return

        if state == "adm_waiting_new_channel":
            parts = text.split("|")
            if len(parts) == 2:
                c_link = parts[0].strip()
                c_id = parts[1].strip()
                channels = get_task_channels()
                channels.append({"link": c_link, "id": c_id})
                set_system_setting("task_channels", json.dumps(channels))
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, "✅ নতুন টাস্ক চ্যানেল যুক্ত করা হয়েছে!", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ ফরম্যাট সঠিক নয়! আবার ট্রাই করুন:\n`https://t.me/channel | @channel`", parse_mode="HTML")
            return

        # FIX 3: Admin Role Setting Handler
        if state == "adm_waiting_role_assign":
            parts = text.split("|")
            if len(parts) == 2 and parts[0].strip().isdigit():
                target_uid = int(parts[0].strip())
                r_type = parts[1].strip().lower()
                role_map = {
                    "wth": "withdraw_admin",
                    "withdraw": "withdraw_admin",
                    "dep": "deposit_admin",
                    "deposit": "deposit_admin",
                    "full": "full_admin",
                    "remove": "remove"
                }
                if r_type in role_map:
                    assigned = role_map[r_type]
                    set_admin_role(target_uid, assigned)
                    user_states.pop(user_id, None)
                    bot.send_message(message.chat.id, f"✅ ইউজার {target_uid} এর জন্য রোল '{assigned}' সফলভাবে আপডেট হয়েছে।", reply_markup=main_keyboard())
                else:
                    bot.send_message(message.chat.id, "❌ রোল টাইপ ভুল! লিখুন: wth / dep / full / remove")
            else:
                bot.send_message(message.chat.id, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `12345678 | wth`", parse_mode="HTML")
            return

        # FIX 5: Dynamic VIP Addition Handler
        if state == "adm_waiting_add_vip":
            parts = text.split("|")
            if len(parts) == 4 and parts[1].strip().isdigit() and parts[2].strip().isdigit() and parts[3].strip().isdigit():
                v_name = parts[0].strip()
                v_price = int(parts[1].strip())
                v_inc = int(parts[2].strip())
                v_days = int(parts[3].strip())
                
                cfg = get_vip_config()
                cfg[v_name] = {"price": v_price, "daily_income": v_inc, "days": v_days}
                set_vip_config(cfg)
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, f"✅ নতুন VIP প্যাকেজ <b>{v_name}</b> সফলভাবে যুক্ত হয়েছে!", parse_mode="HTML", reply_markup=main_keyboard())
            else:
                bot.send_message(message.chat.id, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `Bronze | 150 | 12 | 15`", parse_mode="HTML")
            return

        if state == "waiting_inline_dep_amount":
            min_dep_val = int(float(get_system_setting("min_deposit") or 150))
            if message.text.isdigit() and int(message.text) >= min_dep_val:
                amt = int(message.text)
                method_title = user_states[user_id]["method_type"]
                
                raw_wallet = get_system_setting("bkash_number" if "বিকাশ" in method_title else "nagad_number")
                wallet_num = format_phone_number(raw_wallet)
                
                order_num = generate_order_number()
                user_states[user_id]["amount"] = amt
                user_states[user_id]["order_number"] = order_num
                user_states[user_id]["step"] = "waiting_inline_txid"

                deposit_instructions = (
                    "💳 <b>" + str(method_title) + " Fund Panel</b> 💳\n\n"
                    "📌 <b>Wallet No:</b> <code>" + str(wallet_num) + "</code>\n"
                    "<i>(নাম্বারটিতে ট্যাপ করে সহজেই কপি করতে পারেন)</i>\n\n"
                    "⚠️ <b>নির্দেশনা:</b> এই নাম্বারে শুধুমাত্র সেন্ডমানি প্রযোজ্য। "
                    "আপনার কাঙ্ক্ষিত অ্যামাউন্টটি এই নম্বরে পাঠানোর পর নিচের বাটনে চাপ দিন।\n\n"
                    "📝 <b>Transaction ID (TxID) :</b>\n"
                    "নিচের বাটনে চাপ দিয়ে আপনার ট্রানজেকশন আইডি প্রদান করুন।\n\n"
                    "🆔 <b>Order number:</b> <code>" + str(order_num) + "</code> ✅")

                markup = types.InlineKeyboardMarkup()
                dep_btns = [
                    types.InlineKeyboardButton("✍️ Enter TxID", callback_data="prompt_txid_now"),
                    types.InlineKeyboardButton("🔙 প্রধান মেনু", callback_data="web_cancel_to_main"),
                ]
                build_grid(markup, dep_btns, 2)
                bot.send_message(message.chat.id, deposit_instructions,
                                 reply_markup=markup, parse_mode="HTML")
            else:
                bot.send_message(message.chat.id,
                    "❌ সর্বনিম্ন ফান্ড যোগ " + str(min_dep_val) + " টাকা। অনুগ্রহ করে সঠিক অ্যামাউন্ট সংখ্যায় লিখুন:")
            return

        if state == "waiting_inline_txid":
            raw_txid = message.text.strip()
            if not re.match(r"^[A-Za-z0-9]{8,12}$", raw_txid):
                bot.send_message(
                    message.chat.id,
                    "❌ <b>অবৈধ ট্রানজেকশন আইডি (TxID)!</b>\n\n"
                    "অনুগ্রহ করে শুধুমাত্র সঠিক ও সুনির্দিষ্ট TxID প্রদান করুন। আবার সঠিক TxID লিখে পাঠান:"
                )
                return

            txid = escape_html(raw_txid)
            method_type = str(user_states[user_id].get("method_type", "বিকাশ"))
            amt = user_states[user_id].get("amount", 150)
            order_num = user_states[user_id].get("order_number")
            user_states[user_id]["txid"] = txid
            user_states[user_id]["step"] = "waiting_inline_confirmation"

            confirm_text = (
                "💳 <b>" + str(method_type) + " Fund Confirmation</b> 💳\n\n"
                "💰 <b>পরিমাণ:</b> <code>" + str(amt) + "</code> BDT\n"
                "📝 <b>প্রদানকৃত TxID:</b> <code>" + str(txid) + "</code>\n"
                "🆔 <b>Order number:</b> <code>" + str(order_num) + "</code> ✅\n\n"
                "আপনি কি তথ্যটি নিশ্চিত করতে চান? নিচে <b>নিশ্চিত করুন</b> বাটনে চাপ দিলে ভেরিফিকেশন সম্পন্ন হবে।")

            markup = types.InlineKeyboardMarkup()
            conf_btns = [
                types.InlineKeyboardButton("✅ নিশ্চিত করুন", callback_data="submit_inline_deposit"),
                types.InlineKeyboardButton("❌ বাতিল করুন", callback_data="cancel_inline_deposit"),
            ]
            build_grid(markup, conf_btns, 2)
            bot.send_message(message.chat.id, confirm_text, reply_markup=markup, parse_mode="HTML")
            return

        elif state == "waiting_wth_number":
            phone_number = message.text.strip()
            if re.match(r"^01[3-9]\d{8}$", phone_number):
                user_states[user_id]["number"] = phone_number
                user_states[user_id]["step"] = "waiting_wth_amount"
                method_name = str(user_states[user_id]["method"])
                bal_disp = int(u['main_balance']) if u['main_balance'].is_integer() else u['main_balance']
                
                min_wth = int(float(get_system_setting("min_withdraw") or 50))
                max_wth = int(float(get_system_setting("max_withdraw") or 5000))

                wth_prompt_text = (
                    "💳 <b>উইথড্র করুন</b>\n\n"
                    "💰 <b>আপনার বর্তমান ব্যালেন্স:</b> " + str(bal_disp) + "৳\n\n"
                    f"📌 <b>উইথড্র সীমা:</b>\n"
                    f"• সর্বনিম্ন: {min_wth}৳\n"
                    f"• সর্বোচ্চ: {max_wth}৳\n\n"
                    "💸 <b>" + str(method_name) + "</b> এর জন্য আপনার সঠিক ১১ ডিজিটের নাম্বারটি দেওয়া হয়েছে। এখন ঠিক কত টাকা উইথড্র করতে চান নিচে সংখ্যায় লিখে পাঠান:")
                bot.send_message(message.chat.id, wth_prompt_text,
                                 parse_mode="HTML", reply_markup=cancel_keyboard())
            else:
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id,
                    "❌ <b>ভুল নাম্বার!</b> প্রসেসটি অটো Cancel করা হলো। দয়া করে পরে আবার সঠিক নাম্বার দিয়ে চেষ্টা করুন।",
                    reply_markup=main_keyboard(), parse_mode="HTML")

        elif state == "waiting_wth_amount":
            if message.text.isdigit() and int(message.text) > 0:
                amt = int(message.text)
                min_wth = int(float(get_system_setting("min_withdraw") or 50))
                max_wth = int(float(get_system_setting("max_withdraw") or 5000))

                if amt < min_wth or amt > max_wth:
                    bot.send_message(message.chat.id,
                        f"❌ <b>দুঃখিত! উইথড্র লিমিট পূর্ণ হয়নি।</b>\nআপনি সর্বনিম্ন {min_wth}৳ এবং সর্বোচ্চ {max_wth}৳ পর্যন্ত উইথড্র করতে পারবেন। আবার সঠিক পরিমাণ লিখুন:",
                        parse_mode="HTML")
                    return

                if u["main_balance"] >= amt:
                    method = user_states[user_id]["method"]
                    number = user_states[user_id]["number"]
                    order_num = generate_order_number()
                    user_states.pop(user_id, None)

                    u["main_balance"] -= amt
                    save_user(user_id, u)
                    add_to_history(user_id, "Withdraw", method, amt, number, order_num, "Pending")

                    bot.send_message(message.chat.id,
                        "⏳ আপনার উইথড্র রিকোয়েস্টটি সফলভাবে সাবমিট করা হয়েছে। অনুমোদনের জন্য অপেক্ষা করুন।😊",
                        reply_markup=main_keyboard())

                    run_async(_notify_withdraw_request, u, user_id, amt, method, number, order_num)
                else:
                    bot.send_message(message.chat.id, "❌ আপনার মেইন ব্যালেন্স পর্যাপ্ত নয়।")
            else:
                bot.send_message(message.chat.id, "❌ অনুগ্রহ করে সঠিক এমাউন্ট সংখ্যায় লিখুন।")

        elif state == "adm_waiting_broadcast":
            user_states[user_id]["broadcast_msg"] = message.text
            user_states[user_id]["step"] = "adm_confirm_broadcast"
            bot.send_message(message.chat.id,
                "📝 <b>আপনার ব্রডকাস্ট মেসেজটি নিচে দেওয়া হলো:</b>\n\n" + str(message.text) + "\n\nআপনি কি নিশ্চিত এটি সকল ইউজারের কাছে পাঠাতে চান?",
                reply_markup=broadcast_confirm_keyboard(), parse_mode="HTML")

        elif state == "adm_waiting_user_id":
            user_states.pop(user_id, None)
            if message.text.isdigit():
                target = int(message.text)
                init_user(target)
                t = get_user(target)

                active_vips_list = [n + " (" + str(d) + " দিন)" for n, d in t["active_vips"].items() if d > 0]
                vips_text = ", ".join(active_vips_list) if active_vips_list else "কোনো প্যাকেজ একটিভ নেই ❌"

                t_main = int(t['main_balance']) if t['main_balance'].is_integer() else t['main_balance']
                t_dep = int(t['deposit_balance']) if t['deposit_balance'].is_integer() else t['deposit_balance']
                t_tot_dep = int(t['total_deposit']) if t['total_deposit'].is_integer() else t['total_deposit']
                t_ref_inc = int(t['refer_income']) if t['refer_income'].is_integer() else t['refer_income']
                t_bon = int(t['bonus_balance']) if t['bonus_balance'].is_integer() else t['bonus_balance']
                t_tsk = int(t['task_balance']) if t['task_balance'].is_integer() else t['task_balance']

                info_text = (
                    "🕵️‍♂️ <b>ইউজার কন্ট্রোল প্যানেল</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👤 <b>নাম:</b> " + str(t['name']) + "\n"
                    "🔗 <b>ইউজারনেম:</b> @" + str(t['username']) + "\n"
                    "🆔 <b>টেলিগ্রাম আইডি:</b> <code>" + str(target) + "</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "💰 <b>মোট ব্যালেন্স:</b> " + str(t_main) + " টাকা\n"
                    "📥 <b>ফান্ড ব্যালেন্স:</b> " + str(t_dep) + " টাকা\n"
                    "🏛️ <b>টোটাল ফান্ড:</b> " + str(t_tot_dep) + " টাকা\n"
                    "💵 <b>রেফার ইনকাম:</b> " + str(t_ref_inc) + " টাকা\n"
                    "🎁 <b>বোনাস ব্যালেন্স:</b> " + str(t_bon) + " টাকা\n"
                    "🧑‍💻 <b>টাস্ক ব্যালেন্স:</b> " + str(t_tsk) + " টাকা\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🎯 <b>মোট রেফার সংখ্যা:</b> " + str(t['total_refer']) + " জন\n"
                    "📝 <b>টাস্ক সম্পন্ন করেছে:</b> " + str(t['completed_tasks_count']) + " টি\n"
                    "👑 <b>একটিভ VIP:</b> " + str(vips_text) + "\n"
                    "🚫 <b>ব্যান স্ট্যাটাস:</b> " + ("ব্যানড ❌" if t['is_banned'] else "সচল ✅") + "\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 নিচের বাটনগুলো দিয়ে ডাটা পরিবর্তন করতে পারেন:")
                bot.send_message(message.chat.id, info_text,
                                 reply_markup=admin_user_control_keyboard(target), parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "❌ ভুল আইডি। অনুগ্রহ করে সঠিক সংখ্যা আইডি দিন।")

        elif state.startswith("adm_waiting_val_"):
            parts = state.split("_")
            if len(parts) >= 5:
                field = parts[3]
                target_id = int(parts[4])
                if message.text.isdigit() or (message.text.startswith("-") and message.text[1:].isdigit()):
                    val = int(message.text)
                    init_user(target_id)
                    t_u = get_user(target_id)
                    if field == "main":
                        t_u["main_balance"] = val
                    elif field == "ref":
                        t_u["refer_income"] = val
                    elif field == "bon":
                        t_u["bonus_balance"] = val
                    elif field == "tsk":
                        t_u["task_balance"] = val
                    elif field == "dep":
                        t_u["deposit_balance"] = val
                        t_u["total_deposit"] = val
                    elif field == "cntref":
                        t_u["total_refer"] = val
                    save_user(target_id, t_u)
                    user_states.pop(user_id, None)
                    bot.send_message(message.chat.id,
                        "✅ ইউজার " + str(target_id) + " এর তথ্য আপডেট সফল হয়েছে।",
                        reply_markup=main_keyboard())
                else:
                    bot.send_message(message.chat.id,
                        "❌ ইনপুটটি সঠিক সংখ্যা ছিল না। আবার চেষ্টা করুন বা '❌ বাতিল' লিখুন।")
        return

    if not check_must_join_channels(user_id):
        send_welcome_join_message(message.chat.id)
        return

    if text == "👤 একাউন্ট":
        send_account_details(message.chat.id, user_id,
                             message.from_user.first_name, message.from_user.username)
        return

    if text in ["❌ বাতিল", "❌ বাতিল করুন"]:
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "❌ প্রসেসটি বাতিল করা হয়েছে।",
                         reply_markup=main_keyboard())
        return

    if text == "🎁 বোনাস":
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
            msg = "❌ <b>দুঃখিত, আজকের জন্য আপনার বোনাস নেওয়ার লিমিট (২/২) শেষ।</b>\n\nলিমিট রিসেট হতে বাকি: প্রায় " + str(hours) + " ঘণ্টা " + str(minutes) + " মিনিট।"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
        return

    if text == "📥 ডিপোজিট":
        if get_system_setting("deposit_status") == "off":
            bot.send_message(message.chat.id,
                "❌ বর্তমানে ফান্ড যোগ করার সিস্টেম বন্ধ রয়েছে। অনুগ্রহ করে পরে চেষ্টা করুন।")
            return

        current_time = time.time()
        if current_time - u["last_deposit_reset_time"] > 86400:
            u["deposit_count_today"] = 0
            u["last_deposit_reset_time"] = current_time
            save_user(user_id, u)

        max_dep_limit = int(float(get_system_setting("max_deposit_limit") or 3))
        if u["deposit_count_today"] >= max_dep_limit:
            bot.send_message(message.chat.id,
                "❌ <b>দুঃখিত! ডেইলি ফান্ড যোগ লিমিট হচ্ছে " + str(max_dep_limit) + " বার।</b>\nআপনি আজ আর ফান্ড যোগ করতে পারবেন না। আগামীকাল আবার চেষ্টা করুন।",
                parse_mode="HTML")
            return

        markup = deposit_inline_keyboard()
        if not markup:
            bot.send_message(message.chat.id, "📲 দয়া করে ডিপোজিট মেথড বাছাই করুন:\n\nকোনো ওয়ালেট নম্বর পাওয়া যায় নি 🥺", parse_mode="HTML")
            return

        bot.send_message(message.chat.id,
            "📲 <b>দয়া করে ডিপোজিট মেথড বাছাই করুন:</b>",
            reply_markup=markup, parse_mode="HTML")
        return

    if text == "📤 উইথড্র":
        if get_system_setting("withdraw_status") == "off":
            bot.send_message(message.chat.id,
                "❌ বর্তমানে উইথড্র সিস্টেম বন্ধ রয়েছে। অনুগ্রহ করে পরে চেষ্টা করুন।")
            return

        active_vips = [n for n, d in u["active_vips"].items() if d > 0]
        if not active_vips:
            bot.send_message(message.chat.id,
                "❌ আপনি ভিআইপি সদস্য নন। ভিআইপি না হলে উইথড্র করা যাবে না।")
        else:
            bal_disp = int(u['main_balance']) if u['main_balance'].is_integer() else u['main_balance']
            min_wth = get_system_setting("min_withdraw") or "50"
            max_wth = get_system_setting("max_withdraw") or "5000"
            
            markup = withdraw_inline_keyboard()
            if not markup:
                bot.send_message(message.chat.id, "❌ বর্তমানে সকল উইথড্র অপশন বন্ধ রয়েছে।", parse_mode="HTML")
                return

            wth_text = (
                "💳 <b>উইথড্র করুন</b>\n\n"
                "💰 <b>আপনার বর্তমান ব্যালেন্স:</b> " + str(bal_disp) + "৳\n\n"
                "📌 <b>উইথড্র সীমা:</b>\n"
                f"• সর্বনিম্ন: {min_wth}৳\n"
                f"• সর্বোচ্চ: {max_wth}৳\n\n"
                "💸 টাকা উত্তোলনের জন্য নিচের বাটন থেকে আপনার পছন্দের পেমেন্ট মেথড নির্বাচন করুন।"
            )
            bot.send_message(message.chat.id, wth_text, parse_mode="HTML",
                             reply_markup=markup)
        return

    if text == "📝 টাস্ক":
        if u["task_completed"]:
            bot.send_message(message.chat.id,
                "❌ আপনি ইতিমধ্যে টাস্ক সম্পন্ন করেছেন। আর কোনো টাস্ক উপলব্ধ নেই।")
            return

        task_channels = get_task_channels()
        reward_val = float(get_system_setting("task_reward") or 40)
        reward_amt = str(int(reward_val)) if reward_val.is_integer() else str(reward_val)

        markup = types.InlineKeyboardMarkup()
        chan_btns = []
        i = 1
        for chan in task_channels:
            chan_btns.append(types.InlineKeyboardButton("📢 চ্যানেল " + str(i), url=chan["link"]))
            i += 1
        build_grid(markup, chan_btns, 2)
        markup.row(types.InlineKeyboardButton("✅ জয়েন করেছি চেক করুন", callback_data="check_channels_join"))

        task_text = ("📝 <b>নতুন টাস্ক:</b>\n\nনিচের চ্যানেলগুলোতে অবশ্যই জয়েন করতে হবে। জয়েন করার পর 'জয়েন করেছি চেক করুন' বাটনে চাপ দিন।\n💰 সফলভাবে চ্যানেলগুলোতে জয়েন করলে পাবেন <b>" + str(reward_amt) + " টাকা বোনাস!</b>")
        bot.send_message(message.chat.id, task_text, parse_mode="HTML", reply_markup=markup)
        return

    if text == "💰 রেফার":
        refer_link = "https://t.me/" + str(BOT_USERNAME) + "?start=" + str(user_id)
        ref_inc_disp = int(u['refer_income']) if u['refer_income'].is_integer() else u['refer_income']
        refer_text = (
            "👥 <b>বন্ধু আমন্ত্রণ ও রেফারেল তথ্য</b> 👥\n\n"
            "👤 <b>মোট রেফার:</b> " + str(u['total_refer']) + " জন\n"
            "💲 <b>মোট রেফার ইনকাম:</b> " + str(ref_inc_disp) + " BDT\n\n"
            "🔗 <b>আপনার রেফার লিংক:</b>\n" + str(refer_link) + "\n\n"
            "ℹ️ আপনি আপনার প্রতিটি রেফারেলের ভিআইপি আপডেট বা ফান্ড যোগ করা ব্যালেন্স থেকে <b>২০% কমিশন</b> পাবেন।\n\n"
            "📌 বিস্তারিত জানতে নিচের Rules বাটন চাপুন ⤵️")
        markup = types.InlineKeyboardMarkup()
        ref_btns = [
            types.InlineKeyboardButton("👥 মেম্বার লিস্ট", callback_data="view_refer_list"),
            types.InlineKeyboardButton("🪵 Rules", callback_data="view_refer_rules"),
        ]
        build_grid(markup, ref_btns, 2)
        bot.send_message(message.chat.id, refer_text, reply_markup=markup, parse_mode="HTML")
        return

    if text == "📈 VIP Daily Earnings":
        active_vips = [n + " (" + str(d) + " দিন)" for n, d in u["active_vips"].items() if d > 0]
        if not active_vips:
            vip_income_text = (
                "⚠️ <b>VIP Not Found!</b> 😔\n\n"
                "❌ দুঃখিত, আপনার কোনো অ্যাক্টিভ VIP প্যাকেজ খুঁজে পাওয়া যায়নি।\n\n"
                "🛒 দৈনিক ইনকাম সংগ্রহ করতে প্রথমে একটি VIP Package ক্রয় করুন।\n\n"
                "💸 এরপর <b>'📈 VIP Daily Earnings'</b> অপশনে এসে আপনার দৈনিক ইনকাম খুব সহজেই ক্লেইম করে নিন! ✅"
            )
        else:
            vips_str = ", ".join(active_vips)
            vip_income_text = (
                "👑 <b>ভিআইপি দৈনিক ইনকাম পোর্টাল</b> 👑\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "✨ <b>অ্যাক্টিভ ভিআইপি:</b> " + str(vips_str) + "\n\n"
                "⏰ <b>সময়সীমা:</b> বাংলাদেশ স্ট্যান্ডার্ড টাইম (BST) অনুযায়ী প্রতিদিন সকাল ১০:০০ টার পর আপনার দৈনিক ইনকাম সংগ্রহ করতে পারবেন।\n\n"
                "👇 আপনার আজকের ইনকাম এক ক্লিকে নিতে নিচের বাটনে চাপুন:")
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("আজকের ইনকাম নিন 💰", callback_data="claim_daily_income"))
        bot.send_message(message.chat.id, vip_income_text, parse_mode="HTML", reply_markup=markup)
        return

    if text == "⭐ ভিআইপি":
        vip_cfg = get_vip_config()
        vip_msg = "🏆 <b>VIP Packages</b>\n\n"
        for name, info in vip_cfg.items():
            p = info.get("price", 0)
            inc = info.get("daily_income", 0)
            days = info.get("days", 15)
            tot = inc * days
            prof = tot - p
            vip_msg += f"⭐ <b>{name}</b> — {p}৳ | {inc}৳/Day\n💰 Total Income: {tot}৳\n🎁 Profit: {prof}৳\n📅 Validity: {days} Days\n\n"
        
        vip_msg += "🚀 Upgrade & Earn Daily!\n\n👇 <b>প্যাকেজ কিনতে নিচে ক্লিক করুন ❤️</b>"
        bot.send_message(message.chat.id, vip_msg, parse_mode="HTML",
                         reply_markup=vip_inline_keyboard())
        return

    if text == "📞 সাপোর্ট":
        support_text = "যেকোনো প্রয়োজনে আমাদের সাথে\nযোগাযোগ করুন:\n\n🕵️ এডমিন সাপোর্ট: জরুরী প্রয়োজনে\nসরাসরি এডমিনকে ইনবক্স করুন।\nআপডেটের জন্য আমাদের অফিশিয়াল\nচ্যানেলে যোগ দিন।"
        markup = types.InlineKeyboardMarkup()
        sup_btns = [
            types.InlineKeyboardButton("📞 সাপোর্ট", url="https://t.me/CustomerSupport11Bot"),
            types.InlineKeyboardButton("📢 চ্যানেল", url=PERMANENT_CHANNEL_LINK),
        ]
        build_grid(markup, sup_btns, 2)
        bot.send_message(message.chat.id, support_text, reply_markup=markup)
        return

    if text == "💸 লটারি":
        bot.send_message(message.chat.id, "🎲 লটারি এটি এখন চালু নেই ⛔")
        return

    if text == "💸 ব্যালেন্স ট্রান্সফার":
        bot.send_message(message.chat.id, "💸 ব্যালেন্স ট্রান্সফার অপশনটি শীঘ্রই আসছে...")
        return

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    role = get_admin_role(user_id)
    init_user(user_id)
    u = get_user(user_id)

    if data == "check_start_join":
        if check_must_join_channels(user_id):
            bot.answer_callback_query(call.id, "স্বাগতম!", show_alert=False)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
            bot.send_message(call.message.chat.id,
                "স্বাগতম! নিচে থেকে একটি অপশন বেছে নিন 👇",
                reply_markup=main_keyboard(), parse_mode="HTML")
        else:
            bot.answer_callback_query(
                call.id,
                "⚠️ দুঃখিত! আপনি এখনো আমাদের অফিশিয়াল চ্যানেলে জয়েন করেননি।\n"
                "অনুগ্রহ করে চ্যানেলে জয়েন করে পুনরায় '✅ জয়েন করেছি' বাটনে ক্লিক করুন। 😊",
                show_alert=True
            )
        return

    if data.startswith("wth_select_"):
        method_name = data.split("_")[2]
        user_states[user_id] = {"step": "waiting_wth_number", "method": method_name}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            "💳 আপনি <b>" + str(method_name) + "</b> সিলেক্ট করেছেন।\n\n📲 এখন আপনার সঠিক ১১ ডিজিটের বিকাশ/নগদ নাম্বারটি নিচে লিখে পাঠান (যেমন: 017xxxxxxxx):",
            parse_mode="HTML", reply_markup=cancel_keyboard())
        return

    if data.startswith("edit_bal_") or data.startswith("edit_cnt_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        parts = data.split("_")
        field = parts[2]
        target_id = int(parts[3])
        user_states[user_id] = {"step": f"adm_waiting_val_{field}_{target_id}"}
        field_names = {
            "main": "মোট ব্যালেন্স",
            "ref": "রেফার ব্যালেন্স",
            "bon": "বোনাস ব্যালেন্স",
            "tsk": "টাস্ক ব্যালেন্স",
            "dep": "ফান্ড ব্যালেন্স",
            "cntref": "রেফার সংখ্যা"
        }
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"✍️ ইউজার ID: <code>{target_id}</code> এর জন্য নতুন {field_names.get(field, field)} সংখ্যায় লিখে পাঠান:", parse_mode="HTML", reply_markup=cancel_keyboard())
        return

    if data.startswith("buy_vip_"):
        parts = data.split("_")
        vip_name = parts[2]
        vip_price = int(parts[3])
        vip_cfg = get_vip_config()
        valid_days = vip_cfg.get(vip_name, {}).get("days", 15)

        if vip_name in u["active_vips"] and u["active_vips"][vip_name] > 0:
            bot.answer_callback_query(call.id, f"দুঃখিত! আপনার এই {vip_name} প্যাকেজটি ইতিমধ্যে সচল রয়েছে।", show_alert=True)
            bot.send_message(call.message.chat.id, f"❌ দুঃখিত! আপনার এই <b>{vip_name}</b> প্যাকেজটি ইতিমধ্যে সচল রয়েছে।\nবর্তমান এই প্যাকেজের মেয়াদ শেষ না হওয়া পর্যন্ত এটি আর কিনতে পারেন না। তবে চাইলে অন্য প্যাকেজগুলো কিনতে পারেন। ⚠️", parse_mode="HTML")
            return

        total_available_balance = u["main_balance"] + u["deposit_balance"]

        if total_available_balance >= vip_price:
            if u["deposit_balance"] >= vip_price:
                u["deposit_balance"] -= vip_price
            else:
                remaining = vip_price - u["deposit_balance"]
                u["deposit_balance"] = 0
                u["main_balance"] -= remaining

            u["active_vips"][vip_name] = valid_days
            save_user(user_id, u)

            if u["referred_by"]:
                ref_id = u["referred_by"]
                init_user(ref_id)
                ref_u = get_user(ref_id)
                commission = vip_price * 0.20
                ref_u["refer_income"] += commission
                ref_u["main_balance"] += commission
                save_user(ref_id, ref_u)
                run_async(lambda: bot.send_message(ref_id, f"🎉 আপনার রেফারেল মেম্বার একটি VIP প্যাকেজ ({vip_name}) ক্রয় করায় আপনি {commission} টাকা কমিশন পেয়েছেন! 💰", parse_mode="HTML"))

            bot.answer_callback_query(call.id, f"অভিনন্দন! সফলভাবে {vip_name} প্যাকেজটি একটিভ হয়েছে।", show_alert=True)
            success_msg = (
                f"🎉 অভিনন্দন! সফলভাবে আপনার <b>{vip_name}</b> প্যাকেজটি একটিভ হয়েছে।\n\n"
                f"💰 আপনি এখন প্যাকেজ অনুযায়ী আজকের ইনকাম ক্লেইম করতে পারবেন। নিচের '📈 VIP Daily Earnings' বাটনে গিয়ে এখনই আপনার ইনকামটি লুফে নিন! ✅"
            )
            bot.send_message(call.message.chat.id, success_msg, parse_mode="HTML")
        else:
            bot.answer_callback_query(call.id, "আপনার ডিপোজিট balance এ পর্যাপ্ত টাকা নেই দয়া করে আগে যোগ করুন পরে আবার চেষ্টা করুন ধন্যবাদ। ❤️", show_alert=True)
            bot.send_message(call.message.chat.id, "❌ আপনার ডিপোজিট balance এ পর্যাপ্ত টাকা নেই দয়া করে আগে যোগ করুন পরে আবার চেষ্টা করুন ধন্যবাদ। ❤️", parse_mode="HTML")
        return

    if data == "claim_daily_income":
        active_vips = [n for n, d in u["active_vips"].items() if d > 0]
        if not active_vips:
            bot.answer_callback_query(call.id, "আপনার কোনো অ্যাক্টিভ VIP প্যাকেজ নেই!", show_alert=True)
            return

        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        if u.get("last_income_time") == today_str:
            bot.answer_callback_query(call.id, "আপনি আজকের দৈনিক ইনকাম ইতিমধ্যে সংগ্রহ করেছেন! আগামীকাল আবার চেষ্টা করুন.", show_alert=True)
            return

        vip_cfg = get_vip_config()
        total_daily_income = 0
        for vip in active_vips:
            if vip in vip_cfg:
                total_daily_income += vip_cfg[vip]["daily_income"]

        u["main_balance"] += total_daily_income
        u["last_income_time"] = today_str
        save_user(user_id, u)

        bot.answer_callback_query(call.id, f"সফলভাবে {total_daily_income} টাকা দৈনিক ইনকাম যোগ হয়েছে!", show_alert=True)
        bot.send_message(call.message.chat.id, f"🎁 <b>অভিনন্দন!</b> আপনার সকল অ্যাক্টিভ ভিআইপি প্যাকেজ থেকে আজকের দৈনিক ইনকাম বাবদ <b>{total_daily_income} টাকা</b> আপনার মেইন ব্যালেন্সে যোগ করা হয়েছে। ✅", parse_mode="HTML")
        return

    # FIX 1: Strict Task Join Verification
    if data == "check_channels_join":
        if is_user_joined_task_channels(user_id):
            if not u["task_completed"]:
                reward_val = float(get_system_setting("task_reward") or 40)
                reward_amt = int(reward_val) if reward_val.is_integer() else reward_val
                u["task_balance"] += reward_val
                u["main_balance"] += reward_val
                u["task_completed"] = True
                u["completed_tasks_count"] += 1
                save_user(user_id, u)
                bot.answer_callback_query(call.id, f"অভিনন্দন! টাস্ক সফল হয়েছে এবং {reward_amt} টাকা যোগ হয়েছে।", show_alert=True)
                bot.send_message(call.message.chat.id, f"🎉 <b>টাস্ক সম্পন্ন হয়েছে!</b> আপনার অ্যাকাউন্টে রিওয়ার্ড বাবদ <b>{reward_amt} টাকা</b> যোগ করা হয়েছে। ✅", parse_mode="HTML")
            else:
                bot.answer_callback_query(call.id, "আপনি ইতিমধ্যে এই টাস্কের রিওয়ার্ড গ্রহণ করেছেন!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনো সকল টাস্ক চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।", show_alert=True)
        return

    if data == "view_refer_list":
        refs = get_referred_members(user_id)
        if refs:
            ref_list_str = "👥 <b>আপনার রেফারকৃত মেম্বারগণ:</b>\n\n"
            for idx, (r_id, r_uname) in enumerate(refs, 1):
                ref_list_str += f"{idx}. ID: <code>{r_id}</code> | @{r_uname}\n"
        else:
            ref_list_str = "👥 আপনি এখনো কাউকে রেফার করেন নি।"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, ref_list_str, parse_mode="HTML")
        return

    if data == "view_refer_rules":
        rules_text = "🪵 <b>রেফার রুলস ও শর্তাবলী:</b>\n\n1. প্রতি রেফারের ভিআইপি বা ডিপোজিট থেকে আপনি পাবেন ২০% কমিশন।\n2. ফেইক বা একই আইডি রেফার করলে ব্যালেন্স কাটা হতে পারে।"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, rules_text, parse_mode="HTML")
        return

    # FIX 3: Admin Role Management Controls
    if data == "adm_manage_roles":
        if role != "super_admin":
            bot.answer_callback_query(call.id, "শুধুমাত্র সুপার এডমিন এটি দেখতে পারবে!", show_alert=True)
            return
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("➕ নতুন এডমিন রোল সেট", callback_data="adm_assign_role_prompt"))
        bot.send_message(call.message.chat.id, "👨‍💼 <b>এডমিন রোল ম্যানেজমেন্ট</b>\n\nইউজার আইডি দিয়ে নির্দিষ্ট রোল এসাইন করতে নিচের বাটনে ক্লিক করুন।", reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_assign_role_prompt":
        if role != "super_admin":
            return
        user_states[user_id] = {"step": "adm_waiting_role_assign"}
        msg = "📝 এডমিন আইডি এবং রোল লিখে পাঠান:\n\nফরম্যাট: `User_ID | Role`\n\nউপলব্ধ রোলস:\n- `wth` (শুধু উইথড্র রিকোয়েস্ট)\n- `dep` (শুধু ডিপোজিট রিকোয়েস্ট)\n- `full` (সব এক্সেস)\n- `remove` (এডমিন বাদ দিতে)"
        bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    # FIX 5: Admin Dynamic VIP Management Callbacks
    if data == "adm_manage_vips":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        vip_cfg = get_vip_config()
        msg = "⭐ <b>বর্তমান VIP প্যাকেজসমূহ:</b>\n\n"
        markup = types.InlineKeyboardMarkup()
        del_btns = []
        for name, info in vip_cfg.items():
            msg += f"• <b>{name}</b>: {info['price']}৳ | {info['daily_income']}৳/Day | {info['days']} Days\n"
            del_btns.append(types.InlineKeyboardButton(f"❌ ডিলিট {name}", callback_data=f"adm_del_vip_{name}"))
        build_grid(markup, del_btns, 2)
        markup.row(types.InlineKeyboardButton("➕ নতুন VIP প্যাকেজ যোগ করুন", callback_data="adm_add_vip_prompt"))
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_del_vip_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        v_name = data.split("_")[3]
        cfg = get_vip_config()
        if v_name in cfg:
            del cfg[v_name]
            set_vip_config(cfg)
            bot.answer_callback_query(call.id, f"{v_name} প্যাকেজ ডিলিট করা হয়েছে!", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        return

    if data == "adm_add_vip_prompt":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_add_vip"}
        bot.send_message(call.message.chat.id, "➕ নতুন VIP যোগ করার জন্য তথ্য দিন:\nফরম্যাট: `Name | Price | DailyIncome | ValidityDays`\nউদাহরণ: `Diamond | 1000 | 90 | 15`", parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_toggle_bot_status":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        cur = get_system_setting("bot_status") or "on"
        new_status = "off" if cur == "on" else "on"
        set_system_setting("bot_status", new_status)
        bot.answer_callback_query(call.id,
            "বট সফলভাবে " + ("🟢 চালু" if new_status == "on" else "🔴 বন্ধ") + " করা হয়েছে!",
            show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_toggle_bkash":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        cur = get_system_setting("bkash_status") or "on"
        new_status = "off" if cur == "on" else "on"
        set_system_setting("bkash_status", new_status)
        bot.answer_callback_query(call.id, "বিকাশ ডিপোজিট " + str(new_status), show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_toggle_nagad":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        cur = get_system_setting("nagad_status") or "on"
        new_status = "off" if cur == "on" else "on"
        set_system_setting("nagad_status", new_status)
        bot.answer_callback_query(call.id, "নগদ ডিপোজিট " + str(new_status), show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    # FIX 4: Individual & Global Withdraw Methods Toggles
    if data.startswith("adm_toggle_wth_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        m_name = data.split("_")[3]
        setting_key = f"wth_{m_name}_status"
        cur = get_system_setting(setting_key) or "on"
        new_status = "off" if cur == "on" else "on"
        set_system_setting(setting_key, new_status)
        bot.answer_callback_query(call.id, f"উইথড্র {m_name} {new_status}", show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_toggle_all_withdraw_methods":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        cur_b = get_system_setting("wth_bkash_status") or "on"
        new_status = "off" if cur_b == "on" else "on"
        set_system_setting("wth_bkash_status", new_status)
        set_system_setting("wth_nagad_status", new_status)
        set_system_setting("wth_rocket_status", new_status)
        set_system_setting("wth_upay_status", new_status)
        bot.answer_callback_query(call.id, f"সকল উইথড্র মেথড {new_status} করা হয়েছে!", show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_set_bkash_num":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_bkash_num"}
        bot.send_message(call.message.chat.id, "📝 নতুন বিকাশ নাম্বারটি লিখে পাঠান:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_nagad_num":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_nagad_num"}
        bot.send_message(call.message.chat.id, "📝 নতুন নগদ নাম্বারটি লিখে পাঠান:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_manage_must_channels":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        channels = get_must_join_channels()
        msg = "📢 <b>বর্তমান বাধ্যতামূলক জয়েন চ্যানেলসমূহ:</b>\n\n"
        markup = types.InlineKeyboardMarkup()
        del_btns = []
        idx = 0
        for ch in channels:
            msg += str(idx + 1) + ". লিংক: " + str(ch['link']) + " (ID: " + str(ch['id']) + ")\n"
            del_btns.append(types.InlineKeyboardButton("❌ ডিলিট #" + str(idx + 1),
                                                       callback_data="adm_del_must_chan_" + str(idx)))
            idx += 1
        build_grid(markup, del_btns, 2)
        markup.row(types.InlineKeyboardButton("➕ নতুন চ্যানেল যোগ করুন", callback_data="adm_add_must_chan"))
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_add_must_chan":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_new_must_channel"}
        bot.send_message(call.message.chat.id, "➕ নতুন বাধ্য চ্যানেল যোগ করতে লিংক ও আইডি পাঠান:\nফরম্যাট: `https://t.me/channel | @channel`", parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_del_must_chan_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        idx = int(data.split("_")[4])
        channels = get_must_join_channels()
        if 0 <= idx < len(channels):
            channels.pop(idx)
            set_system_setting("must_join_channels", json.dumps(channels))
            bot.answer_callback_query(call.id, "চ্যানেল সফলভাবে ডিলিট করা হয়েছে!", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        return

    if data.startswith("adm_edit_vip_menu_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        target_id = data.split("_")[4]
        markup = types.InlineKeyboardMarkup()
        vip_cfg = get_vip_config()
        vip_btns = []
        for name in vip_cfg.keys():
            vip_btns.append(types.InlineKeyboardButton(f"⭐ {name}", callback_data=f"adm_set_vip_{target_id}_{name}"))
        vip_btns.append(types.InlineKeyboardButton("❌ VIP রিমুভ", callback_data="adm_remove_vip_" + str(target_id)))
        build_grid(markup, vip_btns, 2)
        bot.send_message(call.message.chat.id,
            "ইউজার আইডি: <code>" + str(target_id) + "</code> এর জন্য ভিআইপি প্যাকেজ এডিট করুন:",
            reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_set_vip_") or data.startswith("adm_remove_vip_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        parts = data.split("_")
        if "remove" in data:
            target_id = int(parts[3])
            init_user(target_id)
            t_u = get_user(target_id)
            t_u["active_vips"] = {}
            save_user(target_id, t_u)
            bot.answer_callback_query(call.id, "ভিআইপি সফলভাবে রিমুভ করা হয়েছে!", show_alert=True)
            bot.send_message(call.message.chat.id,
                "✅ ইউজার " + str(target_id) + " এর সকল ভিআইপি প্যাকেজ রিমুভ করা হয়েছে।")
        else:
            target_id = int(parts[3])
            vip_name = "_".join(parts[4:])
            vip_cfg = get_vip_config()
            v_days = vip_cfg.get(vip_name, {}).get("days", 15)
            init_user(target_id)
            t_u = get_user(target_id)
            t_u["active_vips"][vip_name] = v_days
            save_user(target_id, t_u)
            bot.answer_callback_query(call.id, str(vip_name) + " সফলভাবে সেট করা হয়েছে!", show_alert=True)
            bot.send_message(call.message.chat.id,
                "✅ ইউজার " + str(target_id) + " কে " + str(vip_name) + " প্যাকেজ প্রদান করা হয়েছে।")
        return

    if data in ["web_dep_bkash", "web_dep_nagad"]:
        if get_system_setting("deposit_status") == "off":
            bot.answer_callback_query(call.id, "❌ বর্তমানে ফান্ড যোগ করার সিস্টেম বন্ধ রয়েছে।",
                                      show_alert=True)
            return
        bot.answer_callback_query(call.id)
        method_title = "বিকাশ (bKash)" if data == "web_dep_bkash" else "নগদ (Nagad)"

        min_dep_val = get_system_setting("min_deposit") or "150"
        user_states[user_id] = {"step": "waiting_inline_dep_amount", "method_type": method_title}
        
        logo_url = "https://i.ibb.co.com/84j7q4L/bkash.png" if data == "web_dep_bkash" else "https://i.ibb.co.com/7g2109x/nagad.png"
        
        prompt_text = "✍️ " + str(method_title) + "-এ কত টাকা ফান্ড যোগ করতে চান লিখুন (সর্বনিম্ন " + str(min_dep_val) + " টাকা):"
        try:
            bot.send_photo(call.message.chat.id, logo_url, caption=prompt_text, reply_markup=cancel_keyboard())
        except Exception:
            bot.send_message(call.message.chat.id, prompt_text, reply_markup=cancel_keyboard())
        return

    if data == "prompt_txid_now":
        bot.answer_callback_query(call.id)
        if user_id in user_states and user_states[user_id]["step"] == "waiting_inline_txid":
            method_title = user_states[user_id]["method_type"]
            bot.send_message(call.message.chat.id,
                "📝 অনুগ্রহ করে আপনার " + str(method_title) + "-এর সঠিক ট্রানজেকশন আইডি (TxID) টি চ্যাটে লিখে পাঠান:")
        return

    if data == "web_cancel_to_main":
        bot.answer_callback_query(call.id)
        user_states.pop(user_id, None)
        bot.send_message(call.message.chat.id, "প্রধান মেনু:", reply_markup=main_keyboard())
        return

    if data == "cancel_inline_deposit":
        bot.answer_callback_query(call.id, "ফান্ড যোগ রিকোয়েস্ট বাতিল করা হয়েছে।")
        user_states.pop(user_id, None)
        bot.send_message(call.message.chat.id, "❌ ফান্ড যোগ প্রক্রিয়া বাতিল।",
                         reply_markup=main_keyboard())
        return

    if data == "submit_inline_deposit":
        bot.answer_callback_query(call.id)
        if user_id not in user_states:
            bot.send_message(call.message.chat.id, "❌ সেশন শেষ হয়ে গেছে। দয়া করে আবার চেষ্টা করুন।")
            return

        txid = user_states[user_id].get("txid", "N/A")
        method_type = user_states[user_id].get("method_type", "বিকাশ")
        amt = user_states[user_id].get("amount", 150)
        order_num = user_states[user_id].get("order_number")
        user_states.pop(user_id, None)

        u = get_user(user_id)
        u["deposit_count_today"] += 1
        save_user(user_id, u)

        add_to_history(user_id, "Deposit", method_type, amt, txid, order_num, "Pending")

        bot.send_message(call.message.chat.id,
            "⏳ আপনার ট্রানজেকশন আইডিটি ভেরিফিকেশনের জন্য পাঠানো হয়েছে। সঠিক তথ্য থাকলে খুব দ্রুত ব্যালেন্স যুক্ত হয়ে যাবে। অনুগ্রহ করে অপেক্ষা করুন...",
            reply_markup=main_keyboard())

        run_async(_notify_deposit_request, u, user_id, method_type, amt, txid, order_num)
        return

    if data.startswith("inline_approve_") or data.startswith("inline_reject_"):
        if not role or role == "withdraw_admin":
            return
        bot.answer_callback_query(call.id)

        parts = data.split("_")
        action = parts[1]
        deposit_key = "_".join(parts[2:])

        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, amount, txid_or_num, method, status FROM tx_history WHERE order_number = ?",
                (deposit_key,))
            row = cursor.fetchone()
            conn.close()

        if not row or row[4] != "Pending":
            bot.send_message(call.message.chat.id, "❌ এই রিকোয়েস্টটি অলরেডি প্রসেস করা হয়েছে।")
            return

        target_user, amount, txid, method_type, _ = row
        init_user(target_user)
        t_u = get_user(target_user)

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        if action == "approve":
            update_history_status(deposit_key, "Complete")
            t_u["deposit_balance"] += amount
            t_u["total_deposit"] += amount
            save_user(target_user, t_u)

            bot.send_message(call.message.chat.id,
                "✅ ইউজার " + str(target_user) + " এর " + str(amount) + " টাকা ফান্ড এপ্রুভ করা হয়েছে।")

            run_async(lambda: bot.send_message(HISTORY_CHANNEL_ID,
                "✅ <b>Fund Approved!</b>\n\n👤 ইউজার আইডি: <code>" + str(target_user) + "</code>\n⚙️ মেথড: <b>" + str(method_type) + "</b>\n💰 অ্যামাউন্ট: <code>" + str(amount) + "</code> BDT\n📝 TxID: <code>" + str(txid) + "</code>\n🆔 Order No: <code>" + str(deposit_key) + "</code>\n🟢 স্ট্যাটাস: Complete",
                parse_mode="HTML"))

            run_async(lambda: bot.send_message(target_user,
                "🎉 <b>Fund Added Success!</b> 🎉\n\nআপনার " + str(method_type) + " ফান্ড যোগটি সফলভাবে সম্পন্ন হয়েছে।\n💰 <b>অ্যামাউন্ট:</b> <code>" + str(amount) + "</code> BDT\n📝 <b>TxID:</b> <code>" + str(txid) + "</code>\n🆔 <b>Order No:</b> <code>" + str(deposit_key) + "</code>\n\nআপনার মূল অ্যাকাউন্টে ব্যালেন্স যোগ করা হয়েছে। ধন্যবাদ! ❤️",
                parse_mode="HTML"))
        else:
            update_history_status(deposit_key, "Failed")
            bot.send_message(call.message.chat.id,
                "❌ ইউজার " + str(target_user) + " এর ফান্ড রিকোয়েস্ট রিজেক্ট করা হয়েছে।")

            run_async(lambda: bot.send_message(HISTORY_CHANNEL_ID,
                "❌ <b>Fund Failed!</b>\n\n👤 ইউজার আইডি: <code>" + str(target_user) + "</code>\n⚙️ মেথড: <b>" + str(method_type) + "</b>\n💰 অ্যামাউন্ট: <code>" + str(amount) + "</code> BDT\n🆔 Order No: <code>" + str(deposit_key) + "</code>\n🔴 স্ট্যাটাস: Failed",
                parse_mode="HTML"))

            run_async(lambda: bot.send_message(target_user,
                "❌ <b>Fund Failed!</b> ❌\n\nআপনার প্রদানকৃত ট্রানজেকশন আইডি বা অর্ডার নম্বরটি সঠিক ছিল না।\n🆔 <b>Order No:</b> <code>" + str(deposit_key) + "</code>\n\n🔄 অনুগ্রহ করে সঠিক ট্রানজেকশন আইডি দিয়ে আবার চেষ্টা করুন।",
                parse_mode="HTML"))
        return

    if data.startswith("wth_approve_") or data.startswith("wth_reject_"):
        if not role or role == "deposit_admin":
            return
        bot.answer_callback_query(call.id)

        parts = data.split("_")
        action = parts[1]
        order_num = parts[2]

        with db_lock:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, amount, status, method, txid_or_num FROM tx_history WHERE order_number = ?",
                (order_num,))
            row = cursor.fetchone()
            conn.close()

        if not row or row[2] != "Pending":
            bot.send_message(call.message.chat.id, "❌ এই রিকোয়েস্টটি অলরেডি প্রসেস করা হয়েছে।")
            return

        target_user, amount, _, method_name, phone_num = row
        init_user(target_user)
        t_u = get_user(target_user)

        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        if action == "approve":
            update_history_status(order_num, "Complete")
            add_total_withdraw_approved(amount)
            bot.send_message(call.message.chat.id,
                "✅ উইথড্র অর্ডার " + str(order_num) + " সফলভাবে এপ্রুভ করা হয়েছে।")

            run_async(lambda: bot.send_message(HISTORY_CHANNEL_ID,
                "✅ <b>Withdraw Approved!</b>\n\n👤 ইউজার আইডি: <code>" + str(target_user) + "</code>\n📲 মেথড: <b>" + str(method_name) + "</b>\n📞 নাম্বার: <code>" + str(phone_num) + "</code>\n💰 পরিমাণ: <code>" + str(amount) + "</code> BDT\n🆔 Order No: <code>" + str(order_num) + "</code>\n🟢 স্ট্যাটাস: Complete",
                parse_mode="HTML"))

            run_async(lambda: bot.send_message(target_user,
                "✅ উইথড্র সফল হয়েছে! 🎉\n\nআপনার " + str(amount) + " ৳ উইথড্র রিকোয়েস্ট সফলভাবে অনুমোদন করা হয়েছে। 💸\n\nদয়া করে আপনার নির্ধারিত ওয়ালেট চেক করুন। 📲\n\n❤️ আমাদের সাথে থাকার জন্য আপনাকে অসংখ্য ধন্যবাদ।\n✨ আপনার বিশ্বাস ও সহযোগিতাই আমাদের অনুপ্রেরণা। ✨"))
        else:
            update_history_status(order_num, "Failed")
            t_u["main_balance"] += amount
            save_user(target_user, t_u)
            bot.send_message(call.message.chat.id,
                "❌ উইথড্র অর্ডার " + str(order_num) + " রিজেক্ট করা হয়েছে এবং ব্যালেন্স রিফান্ড করা হয়েছে।")

            run_async(lambda: bot.send_message(HISTORY_CHANNEL_ID,
                "❌ <b>Withdraw Failed!</b>\n\n👤 ইউজার আইডি: <code>" + str(target_user) + "</code>\n📲 মেথড: <b>" + str(method_name) + "</b>\n💰 পরিমাণ: <code>" + str(amount) + "</code> BDT\n🆔 Order No: <code>" + str(order_num) + "</code>\n🔴 স্ট্যাটাস: Failed",
                parse_mode="HTML"))

            run_async(lambda: bot.send_message(target_user,
                "⚠️ উইথড্র রিকোয়েস্ট বাতিল করা হয়েছে\n\nআপনার " + str(amount) + " ৳ উইথড্র রিকোয়েস্টটি সফলভাবে বাতিল করা হয়েছে।\n\n💰 উক্ত পরিমাণ " + str(amount) + " ৳ রিফান্ড করে আপনার ব্যালেন্সে ফেরত দেওয়া হয়েছে। ✅\n\nআরও বিস্তারিত তথ্যের জন্য আমাদের কাস্টমার কেয়ারে যোগাযোগ করুন। 📞\n\n❤️😊 আমাদের সাথে থাকার জন্য ধন্যবাদ।"))
        return

    if data == "bc_confirm":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        if user_id in user_states and user_states[user_id].get("step") == "adm_confirm_broadcast":
            b_text = user_states[user_id].get("broadcast_msg", "")
            user_states.pop(user_id, None)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass

            def _async_broadcast(b_msg):
                count = 0
                all_uids = get_all_user_ids()
                for u_id in all_uids:
                    try:
                        bot.send_message(u_id, b_msg)
                        count += 1
                        time.sleep(0.04) 
                    except Exception:
                        pass
                bot.send_message(user_id, f"✅ ব্রডকাস্ট সফল! মোট {count} জন ইউজারের কাছে পাঠানো হয়েছে।")

            run_async(_async_broadcast, b_text)
            bot.send_message(call.message.chat.id, "🚀 ব্রডকাস্ট প্রক্রিয়া ব্যাকগ্রাউন্ডে শুরু হয়েছে। শেষ হলে মেসেজ পাবেন।")

        bot.answer_callback_query(call.id)
        return

    if data == "bc_cancel":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states.pop(user_id, None)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(call.message.chat.id, "❌ ব্রডকাস্ট বাতিল করা হয়েছে।")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_user_control":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_user_id"}
        bot.send_message(call.message.chat.id, "🔍 অনুগ্রহ করে ইউজারের টেলিগ্রাম আইডি (ID) দিন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_total_stats":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        total_users = get_total_users_count()
        total_dep = int(get_total_deposits_sum()) if float(get_total_deposits_sum()).is_integer() else get_total_deposits_sum()
        total_wth = int(get_total_withdraw_approved()) if float(get_total_withdraw_approved()).is_integer() else get_total_withdraw_approved()
        total_vip_buyers = get_total_vip_buyers_count()
        stat_text = (
            "📊 <b>বটের রিয়েল এডমিন স্ট্যাটাস:</b>\n\n"
            "👥 মোট ইউজার: " + str(total_users) + " জন\n"
            "👑 মোট ভিআইপি প্যাকেজ কিনেছে: " + str(total_vip_buyers) + " জন\n"
            "📥 মোট ফান্ড: " + str(total_dep) + " টাকা\n"
            "💸 মোট উইথড্রো: " + str(total_wth) + " টাকা")
        bot.send_message(call.message.chat.id, stat_text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_broadcast":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_broadcast"}
        bot.send_message(call.message.chat.id, "📢 ব্রডকাস্ট মেসেজটি লিখুন (যা সবার কাছে চলে যাবে):")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_ban_") or data.startswith("adm_unban_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        parts = data.split("_")
        target_id = int(parts[2])
        is_b = 1 if parts[1] == "ban" else 0
        init_user(target_id)
        t_u = get_user(target_id)
        t_u["is_banned"] = is_b
        save_user(target_id, t_u)
        bot.answer_callback_query(call.id, "সফলভাবে স্ট্যাটাস আপডেট করা হয়েছে!", show_alert=True)
        bot.send_message(call.message.chat.id, f"✅ ইউজার ID: <code>{target_id}</code> এর ব্যান স্ট্যাটাস আপডেট করা হয়েছে।", parse_mode="HTML")
        return

    if data == "adm_toggle_deposit":
        if not role or role == "withdraw_admin":
            return
        cur = get_system_setting("deposit_status")
        new_status = "off" if cur == "on" else "on"
        set_system_setting("deposit_status", new_status)
        bot.answer_callback_query(call.id, "ফান্ড সিস্টেম এখন " + str(new_status) + " করা হয়েছে।",
                                  show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_toggle_withdraw":
        if not role or role == "deposit_admin":
            return
        cur = get_system_setting("withdraw_status")
        new_status = "off" if cur == "on" else "on"
        set_system_setting("withdraw_status", new_status)
        bot.answer_callback_query(call.id, "উইথড্র সিস্টেম এখন " + str(new_status) + " করা হয়েছে।",
                                  show_alert=True)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id,
                                          reply_markup=admin_main_keyboard(user_id))
        except Exception:
            pass
        return

    if data == "adm_set_min_deposit":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_min_deposit"}
        bot.send_message(call.message.chat.id, "💰 সর্বনিম্ন ফান্ড অ্যামাউন্ট সংখ্যায় লিখুন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_max_deposit_limit":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_max_deposit_limit"}
        bot.send_message(call.message.chat.id, "🔄 ডেইলি ফান্ড লিমিট সংখ্যায় লিখুন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_min_withdraw":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_min_withdraw"}
        bot.send_message(call.message.chat.id, "📤 সর্বনিম্ন উইথড্র অ্যামাউন্ট সংখ্যায় লিখুন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_max_withdraw":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_max_withdraw"}
        bot.send_message(call.message.chat.id, "📤 সর্বোচ্চ উইথড্র অ্যামাউন্ট সংখ্যায় লিখুন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_set_task_reward":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_task_reward"}
        bot.send_message(call.message.chat.id, "🎁 টাস্ক রিওয়ার্ড অ্যামাউন্ট সংখ্যায় লিখুন:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_manage_task_channels":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        channels = get_task_channels()
        msg = "📢 <b>বর্তমান টাস্ক চ্যানেলসমূহ:</b>\n\n"
        markup = types.InlineKeyboardMarkup()
        del_btns = []
        idx = 0
        for ch in channels:
            msg += str(idx + 1) + ". লিংক: " + str(ch['link']) + " (ID: " + str(ch['id']) + ")\n"
            del_btns.append(types.InlineKeyboardButton("❌ ডিলিট #" + str(idx + 1),
                                                       callback_data="adm_del_chan_" + str(idx)))
            idx += 1
        build_grid(markup, del_btns, 2)
        markup.row(types.InlineKeyboardButton("➕ নতুন চ্যানেল যোগ করুন", callback_data="adm_add_chan"))
        bot.send_message(call.message.chat.id, msg, reply_markup=markup, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_del_chan_"):
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        idx = int(data.split("_")[3])
        channels = get_task_channels()
        if 0 <= idx < len(channels):
            channels.pop(idx)
            set_system_setting("task_channels", json.dumps(channels))
            bot.answer_callback_query(call.id, "টাস্ক চ্যানেল ডিলিট করা হয়েছে!", show_alert=True)
            try:
                bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception:
                pass
        return

    if data == "adm_add_chan":
        if not role or role in ["withdraw_admin", "deposit_admin"]:
            return
        user_states[user_id] = {"step": "adm_waiting_new_channel"}
        bot.send_message(call.message.chat.id, "➕ নতুন টাস্ক চ্যানেল যোগ করতে লিংক ও আইডি পাঠান:\nফরম্যাট: `https://t.me/channel | @channel`", parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

if __name__ == "__main__":
    print("🤖 Bot is starting cleanly...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10, logger_level=None)
        except Exception as e:
            print(f"⚠️ Connection issue encountered: {e}. Auto-reconnecting in 3 seconds...")
            time.sleep(3)
