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

# ================= à¦¬à¦Ÿà§‡à¦° à¦®à§‚à¦² à¦•à¦¨à¦«à¦¿à¦—à¦¾à¦°à§‡à¦¶à¦¨ =================
API_TOKEN = '8924739332:AAHRzl2KqTpmMnGwiFjimtsRiVp-ohJabpc'
BOT_USERNAME ='Infinity_Earn838bot'
ADMIN_IDS = [6227950415, 7016100281]

# à§§. Mandatory Join Channels
CHANNEL_1_LINK = "https://t.me/nft_earn_bot_1"
CHANNEL_2_LINK = "https://t.me/online_income_11zone"

CHANNEL_1_ID = "@nft_earn_bot_1"
CHANNEL_2_ID = "@online_income_11zone"
# à§¨. Task Channels
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

# --- à¦¸à§à¦¸à¦‚à¦—à¦ à¦¿à¦¤ à¦¡à¦¾à¦Ÿà¦¾à¦¬à§‡à¦œ à¦ªà¦¾à¦¥ ---
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
                "âš ï¸ <b>à¦†à¦ªà¦¨à¦¿ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦Ÿà¦¾à¦¸à§à¦• à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à¦¥à§‡à¦•à§‡ à¦²à¦¿à¦­ à¦¨à¦¿à¦¯à¦¼à§‡à¦›à§‡à¦¨!</b>\n\n"
                "à¦¤à¦¾à¦‡ à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§‹à¦¨à¦¾à¦¸ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦à¦¬à¦‚ à¦Ÿà¦¾à¦¸à§à¦• à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¥à§‡à¦•à§‡ <b>à§ªà§¦ à¦Ÿà¦¾à¦•à¦¾</b> à¦•à¦¾à¦Ÿà¦¾ à¦¹à¦²à§‹à¥¤ "
                "à¦†à¦¬à¦¾à¦° à§ªà¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à¦²à§‡ à¦†à¦ªà¦¨à¦¿ à¦ªà§à¦¨à¦°à¦¾à¦¯à¦¼ à¦¬à§‹à¦¨à¦¾à¦¸à¦Ÿà¦¿ à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤ âœ…",
                reply_markup=main_keyboard(),
                parse_mode="HTML"
            )

def send_force_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("ðŸ”— online income à¦ à¦¯à§‹à¦— à¦¦à¦¿à¦¨", url=CHANNEL_1_LINK),
        types.InlineKeyboardButton("ðŸ”— INFINITY EARN à¦  à¦¯à§‹à¦— à¦¦à¦¿à¦¨", url=CHANNEL_2_LINK),
        types.InlineKeyboardButton("âœ… à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à¦¿", callback_data="verify_force_join")
    )
    msg_text = (
        "âš ï¸ <b>à¦¬à¦Ÿà¦Ÿà¦¿ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¾à¦° à¦œà¦¨à§à¦¯ à¦†à¦ªà¦¨à¦¾à¦•à§‡ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à¦¤à§‡ à¦¹à¦¬à§‡à¥¤</b>\n\n"
        "à¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦ªà§à¦°à¦¥à¦®à§‡ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦¯à§‹à¦— à¦¦à¦¿à¦¨, à¦¤à¦¾à¦°à¦ªà¦° à¦¨à¦¿à¦šà§‡à¦° \"âœ… à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à¦¿\" à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨à¥¤"
    )
    bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(types.KeyboardButton("ðŸ“© à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ"), types.KeyboardButton("ðŸ“¤ à¦‰à¦‡à¦¥à¦¡à§à¦°"))
    markup.add(types.KeyboardButton("ðŸ’° à¦°à§‡à¦«à¦¾à¦°"), types.KeyboardButton("â­ VIP"))
    markup.add(types.KeyboardButton("ðŸ“ à¦Ÿà¦¾à¦¸à§à¦•"), types.KeyboardButton("ðŸŽ à¦¬à§‹à¦¨à¦¾à¦¸"))
    markup.add(types.KeyboardButton("ðŸ‘¤ à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ"), types.KeyboardButton("ðŸ’° à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦ªà§à¦°à¦¤à¦¿à¦¦à¦¿à¦¨ à¦†à¦¯à¦¼"))
    markup.add(types.KeyboardButton("ðŸ“ž à¦¸à¦¾à¦ªà§‹à¦°à§à¦Ÿ"), types.KeyboardButton("ðŸŽ² à¦²à¦Ÿà¦¾à¦°à¦¿"))
    return markup

def cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("âŒ à¦¬à¦¾à¦¤à¦¿à¦²"))
    return markup

def confirm_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("âœ… à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦•à¦°à§à¦¨"), types.KeyboardButton("âŒ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à§à¦¨"))
    return markup

def vip_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for name, config in VIP_CONFIG.items():
        markup.add(types.InlineKeyboardButton(f"ðŸ‘‘ {name} à¦•à¦¿à¦¨à§à¦¨ ({config['price']}à§³)", callback_data=f"buy_vip_{name}_{config['price']}"))
    return markup

def withdraw_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("à¦¬à¦¿à¦•à¦¾à¦¶", callback_data="wth_select_à¦¬à¦¿à¦•à¦¾à¦¶"),
        types.InlineKeyboardButton("à¦¨à¦—à¦¦", callback_data="wth_select_à¦¨à¦—à¦¦"),
        types.InlineKeyboardButton("à¦°à¦•à§‡à¦Ÿ", callback_data="wth_select_rocket")
    )
    return markup

def admin_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("âš™ï¸ à¦‡à¦‰à¦œà¦¾à¦° à¦•à¦¨à§à¦Ÿà§à¦°à§‹à¦² à¦•à¦°à§à¦¨ (à¦¸à¦¾à¦°à§à¦š à¦†à¦‡à¦¡à¦¿)", callback_data="adm_user_control"),
        types.InlineKeyboardButton("ðŸ“Š à¦¬à¦Ÿà§‡à¦° à¦Ÿà§‹à¦Ÿà¦¾à¦² à¦¸à§à¦Ÿà§à¦¯à¦¾à¦Ÿà¦¾à¦¸ (à¦…à¦°à¦¿à¦œà¦¿à¦¨à¦¾à¦²)", callback_data="adm_total_stats"),
        types.InlineKeyboardButton("ðŸ“¢ à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦•à¦°à§à¦¨", callback_data="adm_broadcast")
    )
    return markup

def admin_user_control_keyboard(target_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("ðŸ’° à¦®à§‹à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸", callback_data=f"edit_bal_main_{target_id}"),
        types.InlineKeyboardButton("ðŸ’µ à¦°à§‡à¦«à¦¾à¦° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸", callback_data=f"edit_bal_ref_{target_id}"),
        types.InlineKeyboardButton("ðŸŽ à¦¬à§‹à¦¨à¦¾à¦¸ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸", callback_data=f"edit_bal_bon_{target_id}"),
        types.InlineKeyboardButton("ðŸ§‘â€ðŸ’» à¦Ÿà¦¾à¦¸à§à¦• à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸", callback_data=f"edit_bal_tsk_{target_id}"),
        types.InlineKeyboardButton("ðŸ“¥ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸", callback_data=f"edit_bal_dep_{target_id}"),
        types.InlineKeyboardButton("ðŸŽ¯ à¦®à§‹à¦Ÿ à¦°à§‡à¦«à¦¾à¦° à¦¸à¦‚à¦–à§à¦¯à¦¾", callback_data=f"edit_cnt_cntref_{target_id}")
    )
    markup.add(
        types.InlineKeyboardButton("ðŸš« à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à§à¦¨", callback_data=f"adm_ban_{target_id}"),
        types.InlineKeyboardButton("ðŸŸ¢ à¦†à¦¨à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à§à¦¨", callback_data=f"adm_unban_{target_id}")
    )
    return markup

def broadcast_confirm_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("âœ… Confirm Send", callback_data="bc_confirm"),
        types.InlineKeyboardButton("âŒ Cancel Send", callback_data="bc_cancel")
    )
    return markup

def send_account_details(chat_id, user_id, first_name, username):
    init_user(user_id, first_name, username)
    u = get_user(user_id)

    active_vips_list = [f"{name} ({days} à¦¦à¦¿à¦¨)" for name, days in u["active_vips"].items() if days > 0]
    vips_text = ", ".join(active_vips_list) if active_vips_list else "à¦•à§‹à¦¨à§‹ à¦ªà§à¦¯à¦¾à¦•à§‡à¦œ à¦à¦•à¦Ÿà¦¿à¦­ à¦¨à§‡à¦‡ âŒ"

    account_text = (
        "ðŸ“Š <b>à¦†à¦ªà¦¨à¦¾à¦° à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ à¦¤à¦¥à§à¦¯</b> ðŸ“Š\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"ðŸ‘¤ <b>à¦¨à¦¾à¦®:</b> {u['name']}\n"
        f"ðŸ”— <b>à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦®:</b> @{u['username']}\n"
        f"ðŸ†” <b>à¦‡à¦‰à¦œà¦¾à¦° à¦†à¦‡à¦¡à¦¿:</b> <code>{user_id}</code>\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"ðŸŽ¯ <b>à¦®à§‹à¦Ÿ à¦°à§‡à¦«à¦¾à¦°:</b> {u['total_refer']} à¦œà¦¨\n"
        f"ðŸ’µ <b>à¦°à§‡à¦«à¦¾à¦° à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {u['refer_income']} à¦Ÿà¦¾à¦•à¦¾\n"
        f"ðŸ’° <b>à¦®à§‹à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {u['main_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
        f"ðŸŽ <b>à¦¬à§‹à¦¨à¦¾à¦¸ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {u['bonus_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
        f"ðŸ‘¨â€ðŸ’» <b>à¦Ÿà¦¾à¦¸à§à¦• à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {u['task_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
        f"ðŸ“¥ <b>à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {u['deposit_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
        f"ðŸ‘‘ <b>à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦¸à¦¦à¦¸à§à¦¯:</b> {vips_text}\n"
        f"ðŸ“ <b>à¦Ÿà¦¾à¦¸à§à¦• à¦¸à¦®à§à¦ªà¦¨à§à¦¨:</b> {u['completed_tasks_count']} à¦Ÿà¦¿\n"
        f"ðŸš« <b>à¦¨à¦¿à¦·à¦¿à¦¦à§à¦§:</b> {'à¦¹à§à¦¯à¦¾à¦' if u['is_banned'] else 'à¦¨à¦¾'}\n"
        f"ðŸ›ï¸ <b>à¦®à§‹à¦Ÿ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦…à§à¦¯à¦¾à¦®à¦¾à¦‰à¦¨à§à¦Ÿ:</b> {u['total_deposit']} à¦Ÿà¦¾à¦•à¦¾\n"
        "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
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
        bot.send_message(message.chat.id, "ðŸš« à¦¦à§à¦ƒà¦–à¦¿à¦¤, à¦†à¦ªà¦¨à¦¿ à¦à¦‡ à¦¬à¦Ÿà§‡ à¦¨à¦¿à¦·à¦¿à¦¦à§à¦§ (Banned) à¦†à¦›à§‡à¦¨à¥¤")
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
                    bot.send_message(referrer_id, f"ðŸ”” à¦†à¦ªà¦¨à¦¾à¦° à¦°à§‡à¦«à¦¾à¦° à¦²à¦¿à¦‚à¦•à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§‡ à¦¨à¦¤à§à¦¨ à¦®à§‡à¦®à§à¦¬à¦¾à¦° <b>{u['name']}</b> à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à§‡à¦¨!", parse_mode="HTML")
                except Exception:
                    pass

    if not is_user_joined(user_id):
        send_force_join_msg(message.chat.id)
        return

    check_and_punish_leave(user_id, message.chat.id)

    bot.send_message(
        message.chat.id,
        "ðŸ‘‹ <b>ðŸ’¸ Infinity earn ðŸ’¸</b> à¦¬à¦Ÿà§‡ à¦†à¦ªà¦¨à¦¾à¦•à§‡ à¦¸à§à¦¬à¦¾à¦—à¦¤à¦®! à¦¨à¦¿à¦šà§‡ à¦¥à§‡à¦•à§‡ à¦à¦•à¦Ÿà¦¿ option à¦¬à§‡à¦›à§‡ à¦¨à¦¿à¦¨ ðŸ‘‡",
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    user_states.pop(user_id, None)
    bot.send_message(message.chat.id, "âš™ï¸ <b>à¦…à§à¦¯à¦¾à¦¡à¦®à¦¿à¦¨ à¦ªà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦¸à§à¦¬à¦¾à¦—à¦¤à¦®:</b>", reply_markup=admin_main_keyboard(), parse_mode="HTML")

@bot.message_handler(func=lambda message: True)
def handle_inputs(message):
    user_id = message.from_user.id
    init_user(user_id, message.from_user.first_name, message.from_user.username)
    u = get_user(user_id)

    if u["is_banned"]:
        bot.send_message(message.chat.id, "ðŸš« à¦†à¦ªà¦¨à¦¾à¦•à§‡ à¦à¦‡ à¦¬à¦Ÿ à¦¥à§‡à¦•à§‡ à¦¬à§à¦²à¦• à¦•à¦°à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤")
        return

    if not is_user_joined(user_id):
        send_force_join_msg(message.chat.id)
        return

    check_and_punish_leave(user_id, message.chat.id)
    u = get_user(user_id)

    text = message.text.strip()

    if "à¦…à§à¦¯à¦¾à¦•à¦¾à¦‰à¦¨à§à¦Ÿ" in text or "account" in text.lower() or "à¦à¦•à¦¾à¦‰à¦¨à§à¦Ÿ" in text:
        send_account_details(message.chat.id, user_id, message.from_user.first_name, message.from_user.username)
        return

    if text in ["âŒ à¦¬à¦¾à¦¤à¦¿à¦²", "âŒ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à§à¦¨"]:
        user_states.pop(user_id, None)
        bot.send_message(message.chat.id, "âŒ à¦ªà§à¦°à¦¸à§‡à¦¸à¦Ÿà¦¿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤", reply_markup=main_keyboard())
        return

    if "à¦¬à§‹à¦¨à¦¾à¦¸" in text or "bonus" in text.lower():
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
            msg = "âœ… <b>à¦…à¦­à¦¿à¦¨à¦¨à§à¦¦à¦¨! à¦†à¦ªà¦¨à¦¿ 5 à¦Ÿà¦¾à¦•à¦¾ à¦¬à§‹à¦¨à¦¾à¦¸ à¦ªà§‡à¦¯à¦¼à§‡à¦›à§‡à¦¨à¥¤</b>\n\nà¦†à¦ªà¦¨à¦¿ à¦†à¦œ à¦†à¦°à¦“ 1 à¦¬à¦¾à¦° à¦¬à§‹à¦¨à¦¾à¦¸ à¦¨à¦¿à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤"
        elif claims_done == 1:
            u["main_balance"] += 5
            u["bonus_claims_today"] = 2
            u["last_bonus_time"] = current_time
            save_user(user_id, u)
            msg = "âœ… <b>à¦…à¦­à¦¿à¦¨à¦¨à§à¦¦à¦¨! à¦†à¦ªà¦¨à¦¿ 5 à¦Ÿà¦¾à¦•à¦¾ à¦¬à§‹à¦¨à¦¾à¦¸ à¦ªà§‡à¦¯à¦¼à§‡à¦›à§‡à¦¨à¥¤</b>\n\nà¦†à¦œà¦•à§‡à¦° à¦œà¦¨à§à¦¯ à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§‹à¦¨à¦¾à¦¸ à¦¨à§‡à¦“à¦¯à¦¼à¦¾à¦° à¦²à¦¿à¦®à¦¿à¦Ÿ à¦¶à§‡à¦·à¥¤"
        else:
            remaining_time = int(one_day - (current_time - u["last_bonus_time"]))
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            msg = f"âŒ <b>à¦¦à§à¦ƒà¦–à¦¿à¦¤, à¦†à¦œà¦•à§‡à¦° à¦œà¦¨à§à¦¯ à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§‹à¦¨à¦¾à¦¸ à¦¨à§‡à¦“à¦¯à¦¼à¦¾à¦° à¦²à¦¿à¦®à¦¿à¦Ÿ (à§¨/à§¨) à¦¶à§‡à¦·à¥¤</b>\n\nà¦²à¦¿à¦®à¦¿à¦Ÿ à¦°à¦¿à¦¸à§‡à¦Ÿ à¦¹à¦¤à§‡ à¦¬à¦¾à¦•à¦¿: à¦ªà§à¦°à¦¾à¦¯à¦¼ {hours} à¦˜à¦£à§à¦Ÿà¦¾ {minutes} minuteà¥¤"
        bot.send_message(message.chat.id, msg, parse_mode="HTML")
        return

    if "à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ" in text or "deposit" in text.lower():
        current_time = time.time()
        if current_time - u["last_deposit_reset_time"] > 86400:
            u["deposit_count_today"] = 0
            u["last_deposit_reset_time"] = current_time
            save_user(user_id, u)

        if u["deposit_count_today"] >= 3:
            bot.send_message(message.chat.id, " âŒ <b>à¦¦à§à¦ƒà¦–à¦¿à¦¤! à¦¡à§‡à¦‡à¦²à¦¿ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦²à¦¿à¦®à¦¿à¦Ÿ à¦¹à¦šà§à¦›à§‡ à§© à¦¬à¦¾à¦°à¥¤</b>\nà¦†à¦ªà¦¨à¦¿ à¦†à¦œ à¦†à¦° à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨ à¦¨à¦¾à¥¤ à¦†à¦—à¦¾à¦®à§€à¦•à¦¾à¦² à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤")
            return

        user_states[user_id] = {"step": "waiting_amount"}
        bot.send_message(message.chat.id, "à¦†à¦ªà¦¨à¦¿ à¦•à¦¤ à¦Ÿà¦¾à¦•à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦•à¦°à¦¤à§‡ à¦šà¦¾à¦¨?\nà¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦Ÿà¦¾à¦•à¦¾à¦° à¦ªà¦°à¦¿à¦®à¦¾à¦£ à¦²à¦¿à¦–à§à¦¨:", reply_markup=cancel_keyboard())
        return

    if "à¦‰à¦‡à¦¥à¦¡à§à¦°" in text or "withdraw" in text.lower():
        active_vips = [name for name, days in u["active_vips"].items() if days > 0]
        if not active_vips:
            bot.send_message(message.chat.id, " âŒ à¦†à¦ªà¦¨à¦¿ à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦¸à¦¦à¦¸à§à¦¯ à¦¨à¦¨à¥¤ à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦¨à¦¾ à¦¹à¦²à§‡ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦•à¦°à¦¾ à¦¯à¦¾à¦¬à§‡ à¦¨à¦¾à¥¤")
        else:
            bot.send_message(message.chat.id, f"ðŸ“¤ à¦†à¦ªà¦¨à¦¾à¦° à¦®à§‚à¦² à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: {u['main_balance']}à§³\n(à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨ à¦‰à¦‡à¦¥à¦¡à§à¦° à§«à§¦à§³ à¦à¦¬à¦‚ à¦¸à¦°à§à¦¬à§‹à¦šà§à¦š à§«à§¦à§¦à§¦à§³)\n\nà¦Ÿà¦¾à¦•à¦¾ à¦¤à§‹à¦²à¦¾à¦° à¦œà¦¨à§à¦¯ à¦¨à¦¿à¦šà§‡à¦° à¦¯à§‡à¦•à§‹à¦¨à§‹ à¦à¦•à¦Ÿà¦¿ à¦ªà§‡à¦®à§‡à¦¨à§à¦Ÿ à¦®à§‡à¦¥à¦¡ à¦¸à¦¿à¦²à§‡à¦•à§à¦Ÿ à¦•à¦°à§à¦¨:", reply_markup=withdraw_inline_keyboard())
        return

    if "à¦Ÿà¦¾à¦¸à§à¦•" in text or "task" in text.lower():
        if u["task_completed"]:
            bot.send_message(message.chat.id, " âŒ à¦†à¦° à¦•à§‹à¦¨à§‹ à¦Ÿà¦¾à¦¸à§à¦• à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦‰à¦ªà¦²à¦¬à§à¦§à¦¿ à¦¨à§‡à¦‡à¥¤")
            return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("ðŸ“¢ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à§§ à¦ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§à¦¨", url=TASK_CHANNELS[0]["link"]),
            types.InlineKeyboardButton("ðŸ“¢ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à§¨ à¦ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§à¦¨", url=TASK_CHANNELS[1]["link"]),
            types.InlineKeyboardButton("ðŸ“¢ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à§© à¦ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§à¦¨", url=TASK_CHANNELS[2]["link"]),
            types.InlineKeyboardButton("ðŸ“¢ à¦šà§à¦¯à¦¾à¦¨à§‡à¦² à§ª à¦ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§à¦¨", url=TASK_CHANNELS[3]["link"]),
            types.InlineKeyboardButton("âœ… à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à¦¿ à¦šà§‡à¦• à¦•à¦°à§à¦¨", callback_data="check_channels_join")
        )
        task_text = (
            "ðŸ“ <b>à¦¨à¦¤à§à¦¨ à¦Ÿà¦¾à¦¸à§à¦•:</b>\n\n"
            "à¦¨à¦¿à¦šà§‡à¦° à§ªà¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦…à¦¬à¦¶à§à¦¯à¦‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à¦¤à§‡ à¦¹à¦¬à§‡à¥¤ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à¦¾à¦° à¦ªà¦° 'à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à¦¿ à¦šà§‡à¦• à¦•à¦°à§à¦¨' à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦šà¦¾à¦ª à¦¦à¦¿à¦¨à¥¤\n"
            "ðŸ’° à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à§ªà¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à¦²à§‡ à¦ªà¦¾à¦¬à§‡à¦¨ <b>à§ªà§¦ à¦Ÿà¦¾à¦•à¦¾ à¦¬à§‹à¦¨à¦¾à¦¸!</b>"
        )
        bot.send_message(message.chat.id, task_text, parse_mode="HTML", reply_markup=markup)
        return

    if "à¦°à§‡à¦«à¦¾à¦°" in text or "refer" in text.lower():
        refer_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        refer_text = (
            "ðŸŽ <b>My Referrals</b>\n\n"
            f"ðŸ‘¤ <b>Total Refer:</b> {u['total_refer']} à¦œà¦¨\n"
            f"ðŸ’² <b>Total Refer Income:</b> {u['refer_income']} BDT\n\n"
            f"ðŸ”— <b>à¦†à¦ªà¦¨à¦¾à¦° à¦°à§‡à¦«à¦¾à¦° à¦²à¦¿à¦‚à¦•:</b>\n{refer_link}\n\n"
            "â„¹ï¸ à¦†à¦ªà¦¨à¦¿ à¦†à¦ªà¦¨à¦¾à¦° à¦ªà§à¦°à¦¤à¦¿à¦Ÿà¦¿ à¦°à§‡à¦«à¦¾à¦°à§‡à¦²à§‡à¦° à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦†à¦ªà¦¡à§‡à¦Ÿ à¦¬à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦•à¦°à¦¾ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¥à§‡à¦•à§‡ <b>à§¨à§¦% à¦•à¦®à¦¿à¦¶à¦¨</b> à¦ªà¦¾à¦¬à§‡à¦¨à¥¤\n\n"
            "ðŸ“Œ à¦¬à¦¿à¦¸à§à¦¤à¦¾à¦°à¦¿à¦¤ à¦œà¦¾à¦¨à¦¤à§‡ à¦¨à¦¿à¦šà§‡à¦° Rules à¦¬à¦¾à¦Ÿà¦¨ à¦šà¦¾à¦ªà§à¦¨ â¤µï¸"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("ðŸ‘¥ à¦°à§‡à¦«à¦¾à¦°à§‡à¦² à¦®à§‡à¦®à§à¦¬à¦¾à¦° à¦²à¦¿à¦¸à§à¦Ÿ", callback_data="view_refer_list"),
            types.InlineKeyboardButton("ðŸªµ Rules", callback_data="view_refer_rules")
        )
        bot.send_message(message.chat.id, refer_text, reply_markup=markup, parse_mode="HTML")
        return

    if "à¦­à¦¿à¦†à¦‡à¦ªà¦¿" in text or "vip" in text.lower():
        if "à¦ªà§à¦°à¦¤à¦¿à¦¦à¦¿à¦¨" in text or "income" in text.lower() or "à¦†à¦°" in text or "à¦†à¦¯à¦¼" in text:
            active_vips = [f"{name} ({days} à¦¦à¦¿à¦¨)" for name, days in u["active_vips"].items() if days > 0]
            if not active_vips:
                vip_income_text = "ðŸ‘‰ à¦¦à§à¦ƒà¦–à¦¿à¦¤ à¦†à¦ªà¦¨à¦¾à¦° à¦…à§à¦¯à¦¾à¦•à§à¦Ÿà¦¿à¦­ à¦•à¦°à¦¾ à¦•à§‹à¦¨ à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦¨à§‡à¦‡,ðŸ˜” à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦†à¦—à§‡ Buy à¦•à¦°à§à¦¨ à¦¤à¦¾à¦°à¦ªà¦° à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦¨à¦¿à¦¨ à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦šà¦¾à¦ª à¦¦à¦¿à¦¨à¥¤âœ…"
            else:
                now = datetime.datetime.now()
                current_date_str = now.strftime("%Y-%m-%d")
                if u["last_income_time"] == current_date_str:
                    vip_income_text = "à¦†à¦ªà¦¨à¦¿ à¦‡à¦¤à¦¿à¦®à¦§à§à¦¯à§‡ à¦†à¦œà¦•à§‡ à¦‡à¦¨à¦•à¦¾à¦® à¦Ÿà¦¿ à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à§‡ à¦¨à¦¿à¦¯à¦¼à§‡à¦›à§‡à¦¨,âœ… à¦•à¦¾à¦²à¦•à§‡ à¦¸à¦•à¦¾à¦²à§‡ à§§à§§:à§¦à§¦ à¦Ÿà¦¾à§Ÿ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨"
                else:
                    vips_str = ", ".join(active_vips)
                    vip_income_text = (
                        f"ðŸ’° <b>à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦ªà§à¦°à¦¤à¦¿à¦¦à¦¿à¦¨ à¦†à¦¯à¦¼</b>\n\n"
                        f"ðŸ‘‘ à¦à¦•à¦Ÿà¦¿à¦­ à¦­à¦¿à¦†à¦‡à¦ªà¦¿: {vips_str}\n\n"
                        f"â° <b>à¦•à§à¦²à§‡à¦‡à¦®à§‡à¦° à¦¸à¦®à¦¯à¦¼:</b> à¦ªà§à¦°à¦¤à¦¿à¦¦à¦¿à¦¨ à¦¸à¦•à¦¾à¦² à§§à§§:à§¦à§¦ à¦¥à§‡à¦•à§‡ à¦°à¦¾à¦¤ à§§à§¨:à§¦à§¦ am à¦ªà¦°à§à¦¯à¦¨à§à¦¤ à¦¯à§‡ à¦•à§‹à¦¨ à¦¸à¦®à¦¯à¦¼ à¦†à¦ªà¦¨à¦¾à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦Ÿà¦¿ à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤\n\n"
                        f"ðŸ‘‡ à¦†à¦ªà¦¨à¦¾à¦° à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦à¦• à¦•à§à¦²à¦¿à¦•à§‡ à¦¨à¦¿à¦¤à§‡ à¦¨à¦¿à¦šà§‡à¦° à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦šà¦¾à¦ªà§à¦¨:"
                    )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦¨à¦¿à¦¨ ðŸ’°", callback_data="claim_daily_income"))
            bot.send_message(message.chat.id, vip_income_text, reply_markup=markup, parse_mode="HTML" if "<b>" in vip_income_text else None)
        else:
            vip_msg = (
    "ðŸ† <b>VIP Packages</b>\n\n"
    "ðŸ¥‰ <b>Bronze</b> â€” 150à§³ | 8à§³/Day\n"
    "ðŸ¥ˆ <b>Silver</b> â€” 300à§³ | 17à§³/Day\n"
    "ðŸ¥‡ <b>Gold</b> â€” 500à§³ | 30à§³/Day\n"
    "ðŸ’  <b>Platinum</b> â€” 700à§³ | 40à§³/Day\n"
    "ðŸ’Ž <b>Diamond</b> â€” 1000à§³ | 70à§³/Day\n"
    "ðŸ‘‘ <b>Royal</b> â€” 1500à§³ | 110à§³/Day\n"
    "ðŸ”¥ <b>Legend</b> â€” 2500à§³ | 200à§³/Day\n\n"
    "ðŸ“… All Packages Valid For 30 Days\n"
    "ðŸš€ Upgrade & Earn Daily!\n\n"
    "ðŸ‘‡ <b>à¦ªà§à¦¯à¦¾à¦•à§‡à¦œ à¦•à¦¿à¦¨à¦¤à§‡ à¦¨à¦¿à¦šà§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨ â¤ï¸</b>"
)

            bot.send_message(message.chat.id, vip_msg, parse_mode="HTML", reply_markup=vip_inline_keyboard())
        return

    if "à¦¸à¦¾à¦ªà§‹à¦°à§à¦Ÿ" in text or "support" in text.lower():
        support_text = (
            "à¦¯à§‡à¦•à§‹à¦¨à§‹ à¦ªà§à¦°à¦¯à¦¼à§‹à¦œà¦¨à§‡ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦¸à¦¾à¦¥à§‡\nà¦¯à§‹à¦—à¦¾à¦¯à§‹à¦— à¦•à¦°à§à¦¨:\n\n"
            "ðŸ•µï¸ à¦à¦¡à¦®à¦¿à¦¨ à¦¸à¦¾à¦ªà§‹à¦°à§à¦Ÿ: à¦œà¦°à§à¦°à§€ à¦ªà§à¦°à¦¯à¦¼à§‹à¦œà¦¨à§‡\n"
            "à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦à¦¡à¦®à¦¿à¦¨à¦•à§‡ à¦‡à¦¨à¦¬à¦•à§à¦¸ à¦•à¦°à§à¦¨à¥¤\n"
            "à¦†à¦ªà¦¡à§‡à¦Ÿà§‡à¦° à¦œà¦¨à§à¦¯ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦…à¦«à¦¿à¦¶à¦¿à¦¯à¦¼à¦¾à¦²\n"
            "à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦¯à§‹à¦— à¦¦à¦¿à¦¨à¥¤"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("ðŸ“ž à¦¸à¦¾à¦ªà§‹à¦°à§à¦Ÿ", url="https://t.me/Customer_Supportc_Bot"),
            types.InlineKeyboardButton("ðŸ“¢ à¦…à¦«à¦¿à¦¶à¦¿à¦¯à¦¼à¦¾à¦² à¦šà§à¦¯à¦¾à¦¨à§‡à¦²", url="https://t.me/online_income_11zone")
        )
        bot.send_message(message.chat.id, support_text, reply_markup=markup)
        return

    if "à¦²à¦Ÿà¦¾à¦°à¦¿" in text or "lottery" in text.lower():
        bot.send_message(message.chat.id, "ðŸŽ² à¦²à¦Ÿà¦¾à¦°à¦¿ à¦à¦Ÿà¦¿ à¦à¦–à¦¨ à¦šà¦¾à¦²à§ à¦¨à§‡à¦‡ â›”")
        return

    if user_id in user_states:
        state = user_states[user_id]["step"]

        if state == "waiting_amount":
            if message.text.isdigit():
                user_states[user_id]["amount"] = int(message.text)
                user_states[user_id]["step"] = "waiting_method"
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("à¦¬à¦¿à¦•à¦¾à¦¶ (Personal)", callback_data="dep_pay_bkash"),
                    types.InlineKeyboardButton("à¦¨à¦—à¦¦ (Personal)", callback_data="dep_pay_nagad"),
                    types.InlineKeyboardButton("à¦°à¦•à§‡à¦Ÿ (Personal)", callback_data="dep_pay_rocket")
                )
                bot.send_message(message.chat.id, "ðŸ“² à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦®à§‡à¦¥à¦¡ à¦¬à¦¾à¦›à¦¾à¦‡ à¦•à¦°à§à¦¨:", reply_markup=markup)
            else:
                bot.send_message(message.chat.id, "âŒ à¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦¸à¦ à¦¿à¦• à¦Ÿà¦¾à¦•à¦¾à¦° à¦ªà¦°à¦¿à¦®à¦¾à¦£ à¦¸à¦‚à¦–à§à¦¯à¦¾à¦¯à¦¼ à¦²à¦¿à¦–à§à¦¨à¥¤")

        elif state == "waiting_txid":
            user_states[user_id]["txid"] = escape_html(message.text)
            user_states[user_id]["step"] = "waiting_confirmation"
            bot.send_message(message.chat.id, f"à¦†à¦ªà¦¨à¦¾à¦° à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦ªà¦°à¦¿à¦®à¦¾à¦£ {user_states[user_id]['amount']} à¦Ÿà¦¾à¦•à¦¾à¥¤ à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦•à¦°à¦¤à§‡ à¦¬à¦¾à¦Ÿà¦¨ à¦šà¦¾à¦ªà§à¦¨à¥¤", reply_markup=confirm_keyboard())

        elif state == "waiting_confirmation" and message.text == "âœ… à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦•à¦°à§à¦¨":
            amount = user_states[user_id]["amount"]
            txid = user_states[user_id].get("txid", "N/A")
            user_states.pop(user_id, None)

            u["deposit_count_today"] += 1
            save_user(user_id, u)

            bot.send_message(message.chat.id, f"âœ… à¦†à¦ªà¦¨à¦¾à¦° à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿà§‡à¦° à¦…à¦¨à§à¦°à§‹à¦§ à¦à¦¡à¦®à¦¿à¦¨à§‡à¦° à¦•à¦¾à¦›à§‡ à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤ à¦…à¦¨à§à¦®à§‹à¦¦à¦¨à§‡à¦° à¦œà¦¨à§à¦¯ à¦…à¦ªà§‡à¦•à§à¦·à¦¾ à¦•à¦°à§à¦¨à¥¤", reply_markup=main_keyboard())

            admin_markup = types.InlineKeyboardMarkup(row_width=2)
            admin_markup.add(
                types.InlineKeyboardButton("âœ… Approve", callback_data=f"dep_approve_{user_id}_{amount}"),
                types.InlineKeyboardButton("âŒ Reject", callback_data=f"dep_reject_{user_id}_{amount}")
            )

            u_name = u.get("name", "N/A")
            u_uname = u.get("username", "N/A")
            u_bal = u.get("main_balance", 0)
            u_tot_dep = u.get("total_deposit", 0)

            for adm_id in ADMIN_IDS:
                try:
                    bot.send_message(
                        adm_id,
                        f"ðŸ“¥ <b>à¦¨à¦¤à§à¦¨ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦°à¦¿à¦•à§‹à¦¯à¦¼à§‡à¦¸à§à¦Ÿ!</b>\n\n"
                        f"ðŸ‘¤ à¦¨à¦¾à¦®: {u_name}\n"
                        f"ðŸ”— à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦®: @{u_uname}\n"
                        f"ðŸ†” à¦‡à¦‰à¦œà¦¾à¦° à¦†à¦‡à¦¡à¦¿: <code>{user_id}</code>\n"
                        f"ðŸ’° à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: {u_bal} à¦Ÿà¦¾à¦•à¦¾\n"
                        f"ðŸ›ï¸ à¦®à§‹à¦Ÿ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ: {u_tot_dep} à¦Ÿà¦¾à¦•à¦¾\n"
                        f"ðŸ’µ à¦°à¦¿à¦•à§‹à¦¯à¦¼à§‡à¦¸à§à¦Ÿ à¦ªà¦°à¦¿à¦®à¦¾à¦£: {amount} à¦Ÿà¦¾à¦•à¦¾\n"
                        f"ðŸ†” TxID: <code>{txid}</code>\n\n"
                        f"à¦…à§à¦¯à¦¾à¦•à¦¶à¦¨ à¦¨à¦¿à¦¨:",
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
                bot.send_message(message.chat.id, f"ðŸ’° <b>à¦†à¦ªà¦¨à¦¾à¦¦à§‡à¦° à¦®à§‹à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: {u['main_balance']} à§³à¥¤</b>\n\nà¦†à¦ªà¦¨à¦¿ à¦•à¦¤ à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦•à¦°à¦¤à§‡ à¦šà¦¾à¦¨?\nà¦ªà¦°à¦¿à¦®à¦¾à¦£ à¦²à¦¿à¦–à§à¦¨ (à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨ à§«à§¦à§³ - à¦¸à¦°à§à¦¬à§‹à¦šà§à¦š à§«à§¦à§¦à§¦à§³):", reply_markup=cancel_keyboard())
            else:
                user_states.pop(user_id, None)
                bot.send_message(message.chat.id, "âŒ <b>à¦­à§à¦² à¦¨à¦¾à¦®à§à¦¬à¦¾à¦°!</b> à¦ªà§à¦°à¦¸à§‡à¦¸à¦Ÿà¦¿ à¦…à¦Ÿà§‹ Cancel à¦•à¦°à¦¾ à¦¹à¦²à§‹à¥¤ à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦ªà¦°à§‡ à¦†à¦¬à¦¾à¦° à¦¸à¦ à¦¿à¦• à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¦à¦¿à¦¯à¦¼à§‡ à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤", reply_markup=main_keyboard())

        elif state == "waiting_wth_amount":
            if message.text.isdigit() and int(message.text) > 0:
                amt = int(message.text)
                if amt < 50 or amt > 5000:
                    bot.send_message(message.chat.id, f"âŒ <b>à¦¦à§à¦ƒà¦–à¦¿à¦¤! à¦‰à¦‡à¦¥à¦¡à§à¦° à¦²à¦¿à¦®à¦¿à¦Ÿ à¦•à¦¾à¦œ à¦•à¦°à§‡à¦¨à¦¿à¥¤</b>\nà¦†à¦ªà¦¨à¦¿ à¦¸à¦°à§à¦¬à¦¨à¦¿à¦®à§à¦¨ à§«à§¦à§³ à¦à¦¬à¦‚ à¦¸à¦°à§à¦¬à§‹à¦šà§à¦š à§«à§¦à§¦à§¦à§³ à¦ªà¦°à§à¦¯à¦¨à§à¦¤ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤ à¦†à¦¬à¦¾à¦° à¦¸à¦ à¦¿à¦• à¦ªà¦°à¦¿à¦®à¦¾à¦£ à¦²à¦¿à¦–à§à¦¨:")
                    return

                if u["main_balance"] >= amt:
                    method = user_states[user_id]["method"]
                    number = user_states[user_id]["number"]
                    user_states.pop(user_id, None)

                    u["main_balance"] -= amt
                    save_user(user_id, u)
                    bot.send_message(message.chat.id, "â³ à¦†à¦ªà¦¨à¦¾à¦° à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à¦¯à¦¼à§‡à¦¸à§à¦Ÿà¦Ÿà¦¿ à¦…à§à¦¯à¦¾à¦¡à¦®à¦¿à¦¨à§‡à¦° à¦•à¦¾à¦›à§‡ à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤ âœ… à¦…à¦¨à§à¦®à§‹à¦¦à¦¨à§‡à¦° à¦œà¦¨à§à¦¯ à¦…à¦ªà§‡à¦•à§à¦·à¦¾ à¦•à¦°à§à¦¨à¥¤ðŸ˜Š", reply_markup=main_keyboard())

                    wth_markup = types.InlineKeyboardMarkup(row_width=2)
                    wth_markup.add(
                        types.InlineKeyboardButton("âœ… Approve", callback_data=f"wth_approve_{user_id}_{amt}"),
                        types.InlineKeyboardButton("âŒ Reject", callback_data=f"wth_reject_{user_id}_{amt}")
                    )

                    u_name = u.get("name", "N/A")
                    u_uname = u.get("username", "N/A")
                    u_bal = u.get("main_balance", 0)
                    u_tot_dep = u.get("total_deposit", 0)

                    for adm_id in ADMIN_IDS:
                        try:
                            bot.send_message(
                                adm_id,
                                f"ðŸ“¤ <b>à¦¨à¦¤à§à¦¨ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à¦¯à¦¼à§‡à¦¸à§à¦Ÿ!</b>\n\n"
                                f"ðŸ‘¤ à¦¨à¦¾à¦®: {u_name}\n"
                                f"ðŸ”— à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦®: @{u_uname}\n"
                                f"ðŸ†” à¦‡à¦‰à¦œà¦¾à¦° à¦†à¦‡à¦¡à¦¿: <code>{user_id}</code>\n"
                                f"ðŸ’° à¦…à¦¬à¦¶à¦¿à¦·à§à¦Ÿ à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸: {u_bal} à¦Ÿà¦¾à¦•à¦¾\n"
                                f"ðŸ›ï¸ à¦®à§‹à¦Ÿ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ: {u_tot_dep} à¦Ÿà¦¾à¦•à¦¾\n"
                                f"ðŸ’µ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦ªà¦°à¦¿à¦®à¦¾à¦£: {amt} à¦Ÿà¦¾à¦•à¦¾\n"
                                f"ðŸ“² à¦®à§‡à¦¥à¦¡: {method}\n"
                                f"ðŸ“ž à¦¨à¦¾à¦®à§à¦¬à¦¾à¦°: <code>{number}</code>\n\n"
                                f"à¦…à§à¦¯à¦¾à¦•à¦¶à¦¨ à¦¨à¦¿à¦¨:",
                                reply_markup=wth_markup,
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                else:
                    bot.send_message(message.chat.id, "âŒ à¦†à¦ªà¦¨à¦¾à¦° à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦ªà¦°à§à¦¯à¦¾à¦ªà§à¦¤ à¦¨à¦¯à¦¼à¥¤")
            else:
                bot.send_message(message.chat.id, "âŒ à¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦¸à¦ à¦¿à¦• à¦à¦®à¦¾à¦‰à¦¨à§à¦Ÿ à¦¸à¦‚à¦–à§à¦¯à¦¾à¦¯à¦¼ à¦²à¦¿à¦–à§à¦¨à¥¤")

        elif state == "adm_waiting_broadcast":
            user_states[user_id]["broadcast_msg"] = message.text
            user_states[user_id]["step"] = "adm_confirm_broadcast"
            bot.send_message(message.chat.id, f"ðŸ“ <b>à¦†à¦ªà¦¨à¦¾à¦° à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦®à§‡à¦¸à§‡à¦œà¦Ÿà¦¿ à¦¨à¦¿à¦šà§‡ à¦¦à§‡à¦“à¦¯à¦¼à¦¾ à¦¹à¦²à§‹:</b>\n\n{message.text}\n\nà¦†à¦ªà¦¨à¦¿ à¦•à¦¿ à¦¨à¦¿à¦¶à§à¦šà¦¿à¦¤ à¦à¦Ÿà¦¿ à¦¸à¦•à¦² à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦•à¦¾à¦›à§‡ à¦ªà¦¾à¦ à¦¾à¦¤à§‡ à¦šà¦¾à¦¨?", reply_markup=broadcast_confirm_keyboard())

        elif state == "adm_waiting_user_id":
            user_states.pop(user_id, None)
            if message.text.isdigit():
                target = int(message.text)
                init_user(target)
                target_user_data = get_user(target)

                active_vips_list = [f"{n} ({d} à¦¦à¦¿à¦¨)" for n, d in target_user_data["active_vips"].items() if d > 0]
                vips_text = ", ".join(active_vips_list) if active_vips_list else "à¦•à§‹à¦¨à§‹ à¦ªà§à¦¯à¦¾à¦•à§‡à¦œ à¦à¦•à¦Ÿà¦¿à¦­ à¦¨à§‡à¦‡ âŒ"

                info_text = (
                    f"ðŸ•µï¸â€â™‚ï¸ <b>à¦‡à¦‰à¦œà¦¾à¦° à¦•à¦¨à§à¦Ÿà§à¦°à§‹à¦² à¦ªà§à¦¯à¦¾à¦¨à§‡à¦²</b>\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"ðŸ‘¤ <b>à¦¨à¦¾à¦®:</b> {target_user_data['name']}\n"
                    f"ðŸ”— <b>à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦®:</b> @{target_user_data['username']}\n"
                    f"ðŸ†” <b>à¦Ÿà§‡à¦²à¦¿à¦—à§à¦°à¦¾à¦® à¦†à¦‡à¦¡à¦¿:</b> <code>{target}</code>\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"ðŸ’° <b>à¦®à§‹à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {target_user_data['main_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"ðŸ“¥ <b>à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {target_user_data['deposit_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"ðŸ›ï¸ <b>à¦Ÿà§‹à¦Ÿà¦¾à¦² à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ:</b> {target_user_data['total_deposit']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"ðŸ’µ <b>à¦°à§‡à¦«à¦¾à¦° à¦‡à¦¨à¦•à¦¾à¦®:</b> {target_user_data['refer_income']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"ðŸŽ <b>à¦¬à§‹à¦¨à¦¾à¦¸ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {target_user_data['bonus_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"ðŸ§‘â€ðŸ’» <b>à¦Ÿà¦¾à¦¸à§à¦• à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸:</b> {target_user_data['task_balance']} à¦Ÿà¦¾à¦•à¦¾\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"ðŸŽ¯ <b>à¦®à§‹à¦Ÿ à¦°à§‡à¦«à¦¾à¦° à¦¸à¦‚à¦–à§à¦¯à¦¾:</b> {target_user_data['total_refer']} à¦œà¦¨\n"
                    f"ðŸ“ <b>à¦Ÿà¦¾à¦¸à§à¦• à¦¸à¦®à§à¦ªà§‚à¦°à§à¦£ à¦•à¦°à§‡à¦›à§‡:</b> {target_user_data['completed_tasks_count']} à¦Ÿà¦¿\n"
                    f"ðŸ‘‘ <b>à¦à¦•à¦Ÿà¦¿à¦­ VIP:</b> {vips_text}\n"
                    f"ðŸš« <b>à¦¬à§à¦¯à¦¾à¦¨ à¦¸à§à¦Ÿà§à¦¯à¦¾à¦Ÿà¦¾à¦¸:</b> {'à¦¬à§à¦¯à¦¾à¦¨à¦¡ âŒ' if target_user_data['is_banned'] else 'à¦¸à¦šà¦² âœ…'}\n"
                    f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
                    f"ðŸ‘‡ à¦¨à¦¿à¦šà§‡à¦° à¦¬à¦¾à¦Ÿà¦¨à¦—à§à¦²à§‹ à¦¦à¦¿à§Ÿà§‡ à¦¡à¦¾à¦Ÿà¦¾ à¦ªà¦°à¦¿à¦¬à¦°à§à¦¤à¦¨ à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à§‡à¦¨:"
                )
                bot.send_message(message.chat.id, info_text, reply_markup=admin_user_control_keyboard(target), parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, "âŒ à¦­à§à¦² à¦†à¦‡à¦¡à¦¿à¥¤ à¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦†à¦‡à¦¡à¦¿ à¦¦à¦¿à¦¨à¥¤")

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
                    bot.send_message(message.chat.id, f"âœ… à¦‡à¦‰à¦œà¦¾à¦° `{target_id}` à¦à¦° à¦¤à¦¥à§à¦¯ à¦†à¦ªà¦¡à§‡à¦Ÿ à¦¸à¦«à¦² à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤", reply_markup=main_keyboard())
                else:
                    bot.send_message(message.chat.id, "âŒ à¦‡à¦¨à¦ªà§à¦Ÿà¦Ÿà¦¿ à¦¸à¦ à¦¿à¦• à¦¸à¦‚à¦–à§à¦¯à¦¾ à¦›à¦¿à¦² à¦¨à¦¾à¥¤ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨ à¦¬à¦¾ 'âŒ à¦¬à¦¾à¦¤à¦¿à¦²' à¦²à¦¿à¦–à§à¦¨à¥¤")

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data

    if data == "verify_force_join":
        if is_user_joined(user_id):
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(call.message.chat.id, "âœ… à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦! à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à§‡à¦¨à¥¤ à¦à¦–à¦¨ à¦†à¦ªà¦¨à¦¿ à¦¬à¦Ÿ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "à¦†à¦ªà¦¨à¦¿ à¦à¦–à¦¨à§‹ à¦†à¦®à¦¾à¦¦à§‡à¦° à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦¨ à¦¨à¦¿ âŒ à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦šà§‡à¦¨à§‡à¦²à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡, à¦œà¦¯à¦¼à§‡à¦¨ à¦•à¦°à§‡à¦›à¦¿ âœ… à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦šà¦¾à¦ª à¦¦à¦¿à¦¨à¥¤ðŸ˜Š", show_alert=True)
        return

    if not is_user_joined(user_id):
        bot.answer_callback_query(call.id, "âš ï¸ à¦¬à¦Ÿà§‡à¦° à¦¬à¦¾à¦Ÿà¦¨ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦°à§‡à¦° à¦ªà§‚à¦°à§à¦¬à§‡ à¦…à¦¬à¦¶à§à¦¯à¦‡ à¦†à¦®à¦¾à¦¦à§‡à¦° channelà¦—à§à¦²à§‹à¦¤à§‡ à¦œà¦¯à¦¼à§‡à¦¨ à¦¥à¦¾à¦•à¦¤à§‡ à¦¹à¦¬à§‡!", show_alert=True)
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
            bot.send_message(call.message.chat.id, f"âœ… à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦¸à¦«à¦²! à¦®à§‹à¦Ÿ {count} à¦œà¦¨ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦•à¦¾à¦›à§‡ à¦ªà¦¾à¦ à¦¾à¦¨à§‹ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤")
        bot.answer_callback_query(call.id)
        return

    if data == "bc_cancel":
        if user_id not in ADMIN_IDS: return
        user_states.pop(user_id, None)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        bot.send_message(call.message.chat.id, "âŒ à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à¦¯à¦¼à§‡à¦›à§‡à¥¤")
        bot.answer_callback_query(call.id)
        return

    if data == "dep_pay_bkash" or data == "dep_pay_rocket":
        bot.answer_callback_query(call.id, "à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¶à§à¦§à§ à¦¨à¦—à¦¦à§‡ à¦¬à¦¿à¦•à¦¾à¦¶à§‡ à¦“ à¦°à¦•à§‡à¦Ÿà§‡ à¦•à¦¾à¦°à¦¿à¦—à¦°à¦¿ à¦¸à¦®à¦¸à§à¦¯à¦¾à¦° à¦•à¦¾à¦°à¦£à§‡ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦à¦Ÿà¦¿ à¦¬à¦¨à§à¦§ à¦°à§Ÿà§‡à¦› à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¨à¦—à¦¦ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§à¦¨à¥¤à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦ â¤ï¸ðŸ¥°", show_alert=True)
        return

    if data == "dep_pay_nagad":
        user_states[user_id]["method"] = "nagad"
        user_states[user_id]["step"] = "waiting_txid"
        amount = user_states[user_id]["amount"]
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass

        dep_instructions = (
            f"à¦†à¦ªà¦¨à¦¾à¦° à§³{amount} à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦•à¦°à¦¾à¦° à¦œà¦¨à§à¦¯, à¦¨à¦¿à¦šà§‡à¦° à¦¨à¦—à¦¦ à¦¨à¦®à§à¦¬à¦°à¦Ÿà¦¿à¦¤à§‡ à¦Ÿà¦¾à¦•à¦¾ à¦ªà¦¾à¦ à¦¾à¦¨ (Send Money):\n\n"
            f"<code>{NUMBER_NAGAD}</code>  (à¦•à¦ªà¦¿ à¦•à¦°à¦¤à§‡ à¦•à§à¦²à¦¿à¦• à¦•à¦°à§à¦¨)\n\n"
            f"à¦Ÿà¦¾à¦•à¦¾ à¦ªà¦¾à¦ à¦¾à¦¨à§‹à¦° à¦ªà¦° à¦Ÿà§à¦°à¦¾à¦¨à¦œà§‡à¦•à¦¶à¦¨ à¦†à¦‡à¦¡à¦¿ (TxID) à¦Ÿà¦¿ à¦à¦–à¦¾à¦¨à§‡ à¦Ÿà¦¾à¦‡à¦ª à¦•à¦°à§‡ à¦ªà¦¾à¦ à¦¾à¦¨à¥¤"
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
            bot.send_message(call.message.chat.id, f"âœ… à¦‡à¦‰à¦œà¦¾à¦° {target_user} à¦à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦à¦ªà§à¦°à§à¦­ à¦•à¦°à§‡à¦›à§‡à¦¨à¥¤")
            try: bot.send_message(target_user, f"à¦†à¦ªà¦¨à¦¾à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦à¦ªà§à¦°à§à¦­ à¦¹à§Ÿà§‡à¦›à§‡ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦šà§‡à¦• à¦•à¦°à§à¦¨à¥¤ à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦ â¤ï¸ðŸ¥°")
            except Exception: pass
        else:
            bot.send_message(call.message.chat.id, f"âŒ à¦‡à¦‰à¦œà¦¾à¦° {target_user} à¦à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦°à¦¿à¦œà§‡à¦•à§à¦Ÿ à¦•à¦°à§‡à¦›à§‡à¦¨")
            try: bot.send_message(target_user, f"à¦†à¦ªà¦¨à¦¾à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡, à¦¬à¦¿à¦¸à§à¦¤à¦¾à¦°à¦¿à¦¤ à¦œà¦¾à¦¨à¦¤à§‡ à¦•à¦¾à¦¸à§à¦Ÿà¦®à¦¾à¦° à¦•à§‡à§Ÿà¦¾à¦°à§‡ à¦•à¦¥à¦¾ à¦¬à¦²à§à¦¨à¥¤âœ…")
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
            bot.send_message(call.message.chat.id, f"âœ… à¦‡à¦‰à¦œà¦¾à¦° {target_user} à¦à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦¸à¦«à¦² à¦à¦ªà§à¦°à§à¦­à¥¤")
            try: bot.send_message(target_user, f"à¦†à¦ªà¦¨à¦¾à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¡à§à¦°à§‹ à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿ à¦Ÿà¦¿ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦à¦ªà§à¦°à§à¦­ à¦¹à§Ÿà§‡à¦›à§‡ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦•à¦¾à¦™à§à¦–à¦¿à¦¤ à¦“à§Ÿà¦¾à¦²à§‡à¦Ÿ à¦šà§‡à¦• à¦•à¦°à§à¦¨,à¦†à¦®à¦¾à¦¦à§‡à¦° à¦¸à¦¾à¦¥à§‡ à¦¥à¦¾à¦•à¦¾à¦° à¦œà¦¨à§à¦¯ à¦†à¦ªà¦¨à¦¾à¦•à§‡ à¦…à¦¸à¦‚à¦–à§à¦¯ à¦§à¦¨à§à¦¯à¦¬à¦¾à¦¦ â¤ï¸â¤ï¸")
            except Exception: pass
        else:
            t_u["main_balance"] += amount
            save_user(target_user, t_u)
            bot.send_message(call.message.chat.id, f"âŒ à¦‡à¦‰à¦œà¦¾à¦° {target_user} à¦à¦° {amount} à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦œà§‡à¦•à§à¦Ÿ à¦•à¦°à§‡à¦›à§‡à¦¨à¥¤")
            try:
                bot.send_message(target_user, f"{amount}à¦Ÿà¦¾à¦•à¦¾ à¦‰à¦‡à¦¥à¦¡à§à¦° à¦°à¦¿à¦•à§‹à§Ÿà§‡à¦¸à§à¦Ÿ à¦¬à¦¾à¦¤à¦¿à¦² à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡ à¦à¦¬à¦‚ {amount}à¦Ÿà¦¾à¦•à¦¾ à¦°à¦¿à¦«à¦¾à¦¨à§à¦¡ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡ à¦¬à¦¿à¦¸à§à¦¤à¦¾à¦°à¦¿à¦¤ à¦œà¦¾à¦¨à¦¤à§‡ à¦•à¦¾à¦¸à§à¦Ÿà¦®à¦¾à¦° à¦•à§‡à§Ÿà¦¾à¦°à§‡ à¦¯à§‹à¦—à¦¾à¦¯à§‹à¦— à¦•à¦°à§à¦¨à¥¤â¤ï¸ðŸ˜Š")
            except Exception: pass
        bot.answer_callback_query(call.id)
        return

    if data == "adm_user_control":
        user_states[user_id] = {"step": "adm_waiting_user_id"}
        bot.send_message(call.message.chat.id, "ðŸ” à¦…à¦¨à§à¦—à§à¦°à¦¹ à¦•à¦°à§‡ à¦‡à¦‰à¦œà¦¾à¦°à§‡à¦° à¦Ÿà§‡à¦²à¦¿à¦—à§à¦°à¦¾à¦® à¦†à¦‡à¦¡à¦¿ (ID) à¦¦à¦¿à¦¨:")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_total_stats":
        total_users = get_total_users_count()
        total_dep = get_total_deposits_sum()
        total_wth = get_total_withdraw_approved()
        stat_text = f"ðŸ“Š <b>à¦¬à¦Ÿà§‡à¦° à¦°à¦¿à¦¯à¦¼à§‡à¦² à¦à¦¡à¦®à¦¿à¦¨ à¦¸à§à¦Ÿà§à¦¯à¦¾à¦Ÿà¦¾à¦¸:</b>\n\nðŸ‘¥ à¦®à§‹à¦Ÿ à¦‡à¦‰à¦œà¦¾à¦°: {total_users} à¦œà¦¨\nðŸ“¥ à¦®à§‹à¦Ÿ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ: {total_dep} à¦Ÿà¦¾à¦•à¦¾\nðŸ’¸ à¦®à§‹à¦Ÿ à¦‰à¦‡à¦¥à¦¡à§à¦°à§‹: {total_wth} à¦Ÿà¦¾à¦•à¦¾"
        bot.send_message(call.message.chat.id, stat_text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
        return

    if data == "adm_broadcast":
        user_states[user_id] = {"step": "adm_waiting_broadcast"}
        bot.send_message(call.message.chat.id, "ðŸ“¢ à¦¬à§à¦°à¦¡à¦•à¦¾à¦¸à§à¦Ÿ à¦®à§‡à¦¸à§‡à¦œà¦Ÿà¦¿ à¦²à¦¿à¦–à§à¦¨ (à¦¯à¦¾ à¦¸à¦¬à¦¾à¦° à¦•à¦¾à¦›à§‡ à¦šà¦²à§‡ à¦¯à¦¾à¦¬à§‡):")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("edit_bal_") or data.startswith("edit_cnt_"):
        parts = data.split("_")
        field = parts[2]
        target_id = parts[3]
        user_states[user_id] = {"step": f"adm_waiting_{field}_{target_id}"}
        bot.send_message(call.message.chat.id, f"ðŸ“ à¦¨à¦¤à§à¦¨ à¦­à§à¦¯à¦¾à¦²à§/à¦¸à¦‚à¦–à§à¦¯à¦¾à¦Ÿà¦¿ à¦Ÿà¦¾à¦‡à¦ª à¦•à¦°à§‡ à¦ªà¦¾à¦ à¦¾à¦¨:")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_ban_"):
        target_id = int(data.split("_")[2])
        init_user(target_id)
        t_u = get_user(target_id)
        t_u["is_banned"] = True
        save_user(target_id, t_u)
        bot.send_message(call.message.chat.id, f"ðŸš« à¦‡à¦‰à¦œà¦¾à¦° `{target_id}` à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦¬à§à¦¯à¦¾à¦¨ à¦¹à§Ÿà§‡à¦›à§‡à¥¤")
        bot.answer_callback_query(call.id)
        return

    if data.startswith("adm_unban_"):
        target_id = int(data.split("_")[2])
        init_user(target_id)
        t_u = get_user(target_id)
        t_u["is_banned"] = False
        save_user(target_id, t_u)
        bot.send_message(call.message.chat.id, f"ðŸŸ¢ à¦‡à¦‰à¦œà¦¾à¦° `{target_id}` à¦†à¦¨à¦¬à§à¦¯à¦¾à¦¨ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤")
        bot.answer_callback_query(call.id)
        return

    if data == "view_refer_list":
        members = get_referred_members(user_id)
        if not members:
            bot.send_message(call.message.chat.id, "âŒ à¦†à¦ªà¦¨à¦¾à¦° à¦°à§‡à¦«à¦¾à¦° à¦²à¦¿à¦‚à¦•à§‡ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§‡ à¦à¦–à¦¨à§‹ à¦•à§‡à¦‰ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡à¦¨à¦¿à¥¤")
        else:
            list_text = f"ðŸ‘¥ <b>à¦†à¦ªà¦¨à¦¾à¦° à¦®à§‹à¦Ÿ à¦°à§‡à¦«à¦¾à¦°à§‡à¦² à¦®à§‡à¦®à§à¦¬à¦¾à¦°: {len(members)} à¦œà¦¨</b>\n\n"
            list_text += "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”\n"
            for index, member in enumerate(members, start=1):
                m_id = member[0]
                m_username = f"@{member[1]}" if member[1] and member[1] != "N/A" else "à¦‡à¦‰à¦œà¦¾à¦°à¦¨à§‡à¦® à¦¨à§‡à¦‡"
                list_text += f"{index}. ðŸ†” <code>{m_id}</code> â€” {m_username}\n"
            list_text += "â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
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
                "ðŸ‘‰ à¦¦à§à¦ƒà¦–à¦¿à¦¤ à¦†à¦ªà¦¨à¦¾à¦° à¦…à§à¦¯à¦¾à¦•à§à¦Ÿà¦¿à¦­ à¦•à¦°à¦¾ à¦•à§‹à¦¨ à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦¨à§‡à¦‡,âŒ à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦†à¦—à§‡ Buy à¦•à¦°à§à¦¨ à¦¤à¦¾à¦°à¦ªà¦° à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦¨à¦¿à¦¨ à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦šà¦¾à¦ª à¦¦à¦¿à¦¨à¥¤âœ…",
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
                    "à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦¸à¦•à¦¾à¦² à§§à§§:à§¦à§¦ à¦¥à§‡à¦•à§‡ à¦°à¦¾à¦¤ à§§à§¨:à§¦à§¦ am à¦ªà¦°à§à¦¯à¦¨à§à¦¤ à¦¯à§‡ à¦•à§‹à¦¨ à¦¸à¦®à¦¯à¦¼ à¦†à¦ªà¦¨à¦¾à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦Ÿà¦¿ à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨à¥¤",
                    show_alert=True
                )
                return

            if u["last_income_time"] == current_date_str:
                bot.answer_callback_query(
                    call.id,
                    "à¦†à¦ªà¦¨à¦¿ à¦‡à¦¤à¦¿à¦®à¦§à§à¦¯à§‡ à¦†à¦œà¦•à§‡ à¦‡à¦¨à¦•à¦¾à¦® à¦Ÿà¦¿ à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à§‡ à¦¨à¦¿à¦¯à¦¼à§‡à¦›à§‡à¦¨ ðŸŸ¢ à¦•à¦¾à¦²à¦•à§‡ à¦¸à¦•à¦¾à¦²à§‡ à§§à§§:à§¦à§¦ à¦Ÿà¦¾à§Ÿ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨",
                    show_alert=True
                )
                return

        total_daily_income = 0
        for vip_name in active_vips:
            total_daily_income += VIP_CONFIG[vip_name]["daily_income"]

        u["main_balance"] += round(total_daily_income, 2)
        u["last_income_time"] = current_date_str
        save_user(user_id, u)

        bot.answer_callback_query(call.id, f"ðŸŽ‰ à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦†à¦ªà¦¨à¦¾à¦° à¦à¦•à¦Ÿà¦¿à¦­ à¦¸à¦•à¦² à¦­à¦¿à¦†à¦‡à¦ªà¦¿-à¦° à¦†à¦œà¦•à§‡à¦° à¦®à§‹à¦Ÿ {total_daily_income} à¦Ÿà¦¾à¦•à¦¾ à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸à§‡ à¦¯à§à¦•à§à¦¤ à¦¹à§Ÿà§‡à¦›à§‡!", show_alert=True)
        return

    elif data.startswith('wth_select_'):
        method = data.split('_')[2]
        if method == "rocket":
            bot.answer_callback_query(call.id, "âš ï¸ à¦•à¦¾à¦°à¦¿à¦—à¦°à¦¿ à¦¸à¦®à¦¸à§à¦¯à¦¾à¦° à¦•à¦¾à¦°à¦£à§‡ à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨à§‡ à¦à¦Ÿà¦¿ à¦¬à¦¨à§à¦§ à¦°à§Ÿà§‡à¦›à§‡ à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à¦¨à¦—à¦¦ à¦“ à¦¬à¦¿à¦•à¦¾à¦¶ à¦¬à§à¦¯à¦¬à¦¹à¦¾à¦° à¦•à¦°à§à¦¨ à¥¤à¥¤", show_alert=True)
            return
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass

        user_states[user_id] = {"step": "waiting_wth_number", "method": method}
        wth_msg = f"âœ… à¦†à¦ªà¦¨à¦¿ {method} à¦¸à¦¿à¦²à§‡à¦•à§à¦Ÿ à¦•à¦°à§‡à¦›à§‡à¦¨à¥¤ à¦à¦–à¦¨ à§§à§§ à¦¡à¦¿à¦œà¦¿à¦Ÿà§‡à¦° à¦¨à¦¾à¦®à§à¦¬à¦¾à¦° à¦¦à¦¿à¦¨ â˜‘ï¸ (01xxxxxxxxx):"
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
            bot.send_message(call.message.chat.id, "ðŸŽ‰ à¦…à¦­à¦¿à¦¨à¦¨à§à¦¦à¦¨! à¦Ÿà¦¾à¦¸à§à¦• à¦¸à¦«à¦² à¦¹à§Ÿà§‡à¦›à§‡ à¦à¦¬à¦‚ à§¨à§¦ à¦Ÿà¦¾à¦•à¦¾ à¦Ÿà¦¾à¦¸à§à¦• à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸à§‡ à¦…à§à¦¯à¦¾à¦¡ à¦•à¦°à¦¾ à¦¹à§Ÿà§‡à¦›à§‡à¥¤", reply_markup=main_keyboard())
        else:
            bot.answer_callback_query(call.id, "âŒ à¦†à¦ªà¦¨à¦¿ à¦à¦–à¦¨à§‹ à¦¸à¦¬à¦•à§Ÿà¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡à¦¨à¦¨à¦¿! à¦¦à§Ÿà¦¾ à¦•à¦°à§‡ à§ªà¦Ÿà¦¿ à¦šà§à¦¯à¦¾à¦¨à§‡à¦²à§‡à¦‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à§‡ à¦†à¦¬à¦¾à¦° à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤", show_alert=True)
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
                f"âŒ **à¦¦à§à¦ƒà¦–à¦¿à¦¤! à¦†à¦ªà¦¨à¦¾à¦° à¦à¦‡ `{name}` à¦ªà§à¦¯à¦¾à¦•à§‡à¦œà¦Ÿà¦¿ à¦‡à¦¤à¦¿à¦®à¦§à§à¦¯à§‡ à¦¸à¦šà¦² à¦°à§Ÿà§‡à¦›à§‡à¥¤**\n"
                f"à¦¬à¦°à§à¦¤à¦®à¦¾à¦¨ à¦à¦‡ à¦ªà§à¦¯à¦¾à¦•à§‡à¦œà§‡à¦° à¦®à§‡à§Ÿà¦¾à¦¦ à¦¶à§‡à¦· à¦¨à¦¾ à¦¹à¦“à§Ÿà¦¾ à¦ªà¦°à§à¦¯à¦¨à§à¦¤ à¦à¦Ÿà¦¿ à¦†à¦° à¦•à¦¿à¦¨à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨ à¦¨à¦¾à¥¤ à¦¤à¦¬à§‡ à¦šà¦¾à¦‡à¦²à§‡ à¦…à¦¨à§à¦¯ à¦ªà§à¦¯à¦¾à¦•à§‡à¦œà¦—à§à¦²à§‹ à¦•à¦¿à¦¨à¦¤à§‡ à¦ªà¦¾à¦°à§‡à¦¨à¥¤ âš ï¸",
                reply_markup=main_keyboard()
            )
            bot.answer_callback_query(call.id)
            return

        if u["deposit_balance"] < price:
            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(call.message.chat.id, f"âŒ à¦ªà¦°à§à¦¯à¦¾à¦ªà§à¦¤ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸ à¦¨à§‡à¦‡à¥¤ à¦¦à¦¯à¦¼à¦¾ à¦•à¦°à§‡ à¦¡à¦¿à¦ªà§‹à¦œà¦¿à¦Ÿ à¦•à¦°à§‡ à¦šà§‡à¦·à§à¦Ÿà¦¾ à¦•à¦°à§à¦¨à¥¤", reply_markup=main_keyboard())
        else:
            u["deposit_balance"] -= price
            u["active_vips"][name] = 15
            u["last_income_time"] = "NEW_PACKAGE_CLAIM_PENDING"
            save_user(user_id, u)

            try: bot.delete_message(call.message.chat.id, call.message.message_id)
            except Exception: pass
            bot.send_message(
                call.message.chat.id,
                f"ðŸŽ‰ à¦…à¦­à¦¿à¦¨à¦¨à§à¦¦à¦¨! à¦¸à¦«à¦²à¦­à¦¾à¦¬à§‡ à¦†à¦ªà¦¨à¦¾à¦° {name} à¦à¦•à¦Ÿà¦¿à¦­ à¦¹à§Ÿà§‡à¦›à§‡à¥¤\n\n"
                f"ðŸ’° à¦†à¦ªà¦¨à¦¿ à¦à¦–à¦¨à¦‡ <b>'ðŸ’° à¦­à¦¿à¦†à¦‡à¦ªà¦¿ à¦ªà§à¦°à¦¤à¦¿à¦¦à¦¿à¦¨ à¦†à¦¯à¦¼'</b> à¦¬à¦¾à¦Ÿà¦¨à§‡ à¦—à¦¿à§Ÿà§‡ à¦†à¦œà¦•à§‡à¦° à¦‡à¦¨à¦•à¦¾à¦® à¦•à§à¦²à§‡à¦‡à¦® à¦•à¦°à§‡ à¦¨à¦¿à¦¤à§‡ à¦ªà¦¾à¦°à¦¬à§‡à¦¨!",
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
                    bot.send_message(referrer, f"ðŸŽ‰ <b>à¦°à§‡à¦«à¦¾à¦° à¦•à¦®à¦¿à¦¶à¦¨ à¦¨à§‹à¦Ÿà¦¿à¦«à¦¿à¦•à§‡à¦¶à¦¨!</b>\n\nà¦†à¦ªà¦¨à¦¾à¦° à¦²à¦¿à¦‚à¦•à§‡ à¦œà§Ÿà§‡à¦¨ à¦•à¦°à¦¾ à¦®à§‡à¦®à§à¦¬à¦¾à¦° <b>{u['name']}</b> à¦à¦•à¦Ÿà¦¿ à¦ªà§à¦¯à¦¾à¦•à§‡à¦œ <code>{name}</code> à¦•à¦¿à¦¨à§‡à¦›à§‡à¦¨à¥¤ à¦†à¦ªà¦¨à¦¿ à¦¤à¦¾à¦° à¦¥à§‡à¦•à§‡ <b>à§¨à§¦% à¦•à¦®à¦¿à¦¶à¦¨ ({commission} à¦Ÿà¦¾à¦•à¦¾)</b> à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸à§‡ à¦ªà§‡à§Ÿà§‡à¦›à§‡à¦¨à¥¤", parse_mode="HTML")
                except Exception: pass

        bot.answer_callback_query(call.id)

    elif data == "view_refer_rules":
        bot.answer_callback_query(call.id, "ðŸ“œ à¦°à§‡à¦«à¦¾à¦°à§‡à¦² à¦¨à¦¿à§Ÿà¦®à¦¾à¦¬à¦²à§€: à§¨à§¦% à¦•à¦®à¦¿à¦¶à¦¨ à¦¸à¦°à¦¾à¦¸à¦°à¦¿ à¦†à¦ªà¦¨à¦¾à¦° à¦®à§‡à¦‡à¦¨ à¦¬à§à¦¯à¦¾à¦²à§‡à¦¨à§à¦¸à§‡ à¦ªà¦¾à¦¬à§‡à¦¨à¥¤", show_alert=True)

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
