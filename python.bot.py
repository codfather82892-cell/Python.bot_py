import os
import re
import json
import sqlite3
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8835566704:AAFhnTNVNvkJuWbT_oA_kCQ0a9zzlTjzctQ")

# আপনার Telegram numeric user id দিন
OWNER_ID = int(os.getenv("OWNER_ID", "8775125184"))

# চাইলে একাধিক admin env দিয়ে দিতে পারবেন: 123,456,789
EXTRA_ADMINS = os.getenv("ADMIN_IDS", "")

DB_FILE = "bot_data.sqlite3"

# Account verification deposit config
WALLET_NO = os.getenv("WALLET_NO", "01406314954")
VERIFY_AMOUNT = float(os.getenv("VERIFY_AMOUNT", "20"))
REFERRAL_BONUS = float(os.getenv("REFERRAL_BONUS", "7"))

MIN_WITHDRAW = float(os.getenv("MIN_WITHDRAW", "20"))
MAX_WITHDRAW = float(os.getenv("MAX_WITHDRAW", "5000"))

# Default forced join channels
DEFAULT_REQUIRED_CHANNELS = [
    ("FarinaTask Official", "@FarinaTask_Official", "https://t.me/FarinaTask_Official"),
    ("Waho Earn Official", "@Waho_Earn_officiall", "https://t.me/Waho_Earn_officiall"),
    ("Easy Earnings", "@Easy_Earnigs838", "https://t.me/Easy_Earnigs838"),
]

# ================= MENU =================

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["👤 একাউন্ট", "📋 টাস্ক আয়"],
        ["🏧 উইড্রো", "🚨 একাউন্ট ভেরিফাই"],
        ["💵 রেফার আয়"],
    ],
    resize_keyboard=True,
)

# ================= STATES =================

STATE_VERIFY_TXID = "VERIFY_TXID"

STATE_WITHDRAW_AMOUNT = "WITHDRAW_AMOUNT"
STATE_WITHDRAW_METHOD = "WITHDRAW_METHOD"
STATE_WITHDRAW_NUMBER = "WITHDRAW_NUMBER"

ADMIN_TASK_CHAT = "ADMIN_TASK_CHAT"
ADMIN_TASK_LINK = "ADMIN_TASK_LINK"
ADMIN_TASK_REWARD = "ADMIN_TASK_REWARD"
ADMIN_TASK_MAX = "ADMIN_TASK_MAX"

ADMIN_REQ_CHAT = "ADMIN_REQ_CHAT"
ADMIN_REQ_LINK = "ADMIN_REQ_LINK"

ADMIN_USER_LOOKUP = "ADMIN_USER_LOOKUP"
ADMIN_SET_BALANCE = "ADMIN_SET_BALANCE"
ADMIN_SET_REF = "ADMIN_SET_REF"
ADMIN_SET_TASK = "ADMIN_SET_TASK"

# ================= DB =================

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row


def now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat()


def fetchone(sql, params=()):
    return conn.execute(sql, params).fetchone()


def fetchall(sql, params=()):
    return conn.execute(sql, params).fetchall()


def init_db():
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                referrer_id INTEGER,
                verified INTEGER DEFAULT 0,
                banned INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                refer_income REAL DEFAULT 0,
                task_income REAL DEFAULT 0,
                referral_paid INTEGER DEFAULT 0,
                created_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS required_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                chat_id TEXT NOT NULL,
                link TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                chat_id TEXT NOT NULL,
                link TEXT NOT NULL,
                reward REAL NOT NULL,
                max_users INTEGER NOT NULL,
                completed_count INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                reward REAL NOT NULL,
                completed_at TEXT,
                deducted INTEGER DEFAULT 0,
                UNIQUE(user_id, task_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_skips (
                user_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                UNIQUE(user_id, task_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                txid TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL,
                number TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                data TEXT
            )
            """
        )

        conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (OWNER_ID,))

        for x in EXTRA_ADMINS.split(","):
            x = x.strip()
            if x.isdigit():
                conn.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (int(x),))

        count = fetchone("SELECT COUNT(*) AS c FROM required_channels")["c"]
        if count == 0:
            for title, chat_id, link in DEFAULT_REQUIRED_CHANNELS:
                conn.execute(
                    "INSERT INTO required_channels(title, chat_id, link, active) VALUES(?,?,?,1)",
                    (title, chat_id, link),
                )


# ================= HELPERS =================

def money(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "0.00"


def parse_amount(text: str):
    trans = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    text = text.translate(trans)
    text = text.replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if text.count(".") > 1:
        raise ValueError("Invalid amount")
    return float(text)


def normalize_chat_id(text: str):
    text = text.strip()
    m = re.match(r"https?://t\.me/([A-Za-z0-9_]+)", text)
    if m:
        return "@" + m.group(1)
    return text


def default_link_from_chat(chat_id: str):
    if chat_id.startswith("@"):
        return "https://t.me/" + chat_id[1:]
    return ""


def get_user(user_id: int):
    return fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))


def add_or_update_user(tg_user, referrer_id=None):
    if not tg_user:
        return

    old = get_user(tg_user.id)
    first_name = tg_user.first_name or ""
    username = tg_user.username or ""

    if old:
        with conn:
            conn.execute(
                "UPDATE users SET first_name=?, username=? WHERE user_id=?",
                (first_name, username, tg_user.id),
            )
    else:
        valid_ref = None
        if referrer_id and referrer_id != tg_user.id and get_user(referrer_id):
            valid_ref = referrer_id

        with conn:
            conn.execute(
                """
                INSERT INTO users(user_id, first_name, username, referrer_id, created_at)
                VALUES(?,?,?,?,?)
                """,
                (tg_user.id, first_name, username, valid_ref, now_iso()),
            )


def get_admins():
    rows = fetchall("SELECT user_id FROM admins")
    return [r["user_id"] for r in rows]


def is_admin_id(user_id: int):
    return fetchone("SELECT user_id FROM admins WHERE user_id=?", (user_id,)) is not None


def set_state(user_id: int, state: str, data=None):
    data = data or {}
    with conn:
        conn.execute(
            "REPLACE INTO user_states(user_id, state, data) VALUES(?,?,?)",
            (user_id, state, json.dumps(data)),
        )


def get_state(user_id: int):
    row = fetchone("SELECT state, data FROM user_states WHERE user_id=?", (user_id,))
    if not row:
        return None, {}
    try:
        data = json.loads(row["data"] or "{}")
    except Exception:
        data = {}
    return row["state"], data


def clear_state(user_id: int):
    with conn:
        conn.execute("DELETE FROM user_states WHERE user_id=?", (user_id,))


async def send_admins(bot, text, reply_markup=None):
    for admin_id in get_admins():
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception:
            pass


async def send_long(message, text):
    if len(text) <= 3900:
        await message.reply_text(text)
        return

    chunk = ""
    for line in text.splitlines():
        if len(chunk) + len(line) + 1 > 3900:
            await message.reply_text(chunk)
            chunk = ""
        chunk += line + "\n"

    if chunk.strip():
        await message.reply_text(chunk)


async def is_member(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("creator", "administrator", "member")
    except Exception:
        return False


async def check_required_join(bot, user_id):
    channels = fetchall("SELECT * FROM required_channels WHERE active=1 ORDER BY id ASC")
    missing = []

    for ch in channels:
        ok = await is_member(bot, ch["chat_id"], user_id)
        if not ok:
            missing.append(ch)

    return len(missing) == 0, missing


async def send_join_prompt(message, bot, missing=None):
    channels = missing
    if channels is None:
        channels = fetchall("SELECT * FROM required_channels WHERE active=1 ORDER BY id ASC")

    links_text = "\n".join([ch["link"] for ch in channels])

    text = (
        "👋 স্বাগতম আমাদের বটে ❤️‍🩹\n\n"
        "💒 এই বট ব্যবহার করতে হলে নিচের সকল চ্যানেল Join করতে হবে।\n\n"
        "✅ Join করার পরে Joined বাটনে ক্লিক করুন।\n\n"
        f"{links_text}\n\n"
        "জয়েন না হলে ভেরিফাই হবে না এবং বটে ডুকতে পারবে না ⚠️\n"
        "চেনেল থেকে লিভ নিলে কোনো কমান্ড কাজ করবে না আবার বলবে জয়েন করতে ⚠️"
    )

    buttons = []
    for i, ch in enumerate(channels, 1):
        buttons.append([InlineKeyboardButton(f"📢 Join Channel {i}", url=ch["link"])])

    buttons.append([InlineKeyboardButton("✅ Joined", callback_data="check_join")])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def ensure_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    add_or_update_user(user)

    dbu = get_user(user.id)
    if dbu and dbu["banned"]:
        await message.reply_text("🚫 আপনার অ্যাকাউন্ট নিষিদ্ধ করা হয়েছে।")
        return False

    ok, missing = await check_required_join(context.bot, user.id)
    if not ok:
        await send_join_prompt(message, context.bot, missing)
        return False

    await check_task_leave_for_user(context.bot, user.id)
    return True


async def send_main_menu(message):
    await message.reply_text(
        "👋 স্বাগতম....\n\nনিচের মেনু থেকে অপশন নির্বাচন করুন।",
        reply_markup=MAIN_MENU,
    )


async def require_verified(message):
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("একাউন্ট ভেরিফিকেশনে যান ☑️", callback_data="open_verify")]]
    )
    await message.reply_text(
        "আপনার একাউন্ট ভেরিফাইড নেই দয়াকরে আগে ভেরিফাই করুন তারপর সব কাজ করুন এবং ইনকাম করুন। ✅",
        reply_markup=kb,
    )


# ================= ACCOUNT =================

async def show_account(message, user_id):
    u = get_user(user_id)
    if not u:
        return

    verified = "Active 🟢" if u["verified"] else "Inactive 🚫"
    banned = "হ্যাঁ" if u["banned"] else "না"
    username = f"@{u['username']}" if u["username"] else "নেই"

    text = (
        "📊 আপনার অ্যাকাউন্ট তথ্য \n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 নাম: {u['first_name']}\n"
        f"🔗 ইউজারনেম: {username}\n"
        f"🆔 ইউজার আইডি: {u['user_id']}\n"
        f"একাউন্ট ভেরিফাই: {verified}\n"
        f"💰 ব্যালেন্স: {money(u['balance'])} টাকা\n"
        f"মোট রেফার আয় : {money(u['refer_income'])} টাকা\n"
        f"মোট টাস্ক আয়: {money(u['task_income'])} টাকা\n"
        f"🚫 নিষিদ্ধ: {banned}"
    )
    await message.reply_text(text)


# ================= TASK =================

def get_next_task(user_id):
    return fetchone(
        """
        SELECT * FROM tasks t
        WHERE t.active=1
        AND t.completed_count < t.max_users
        AND NOT EXISTS (
            SELECT 1 FROM task_completions c
            WHERE c.user_id=? AND c.task_id=t.id
        )
        AND NOT EXISTS (
            SELECT 1 FROM task_skips s
            WHERE s.user_id=? AND s.task_id=t.id
        )
        ORDER BY t.id ASC
        LIMIT 1
        """,
        (user_id, user_id),
    )


async def show_task(message, user_id):
    u = get_user(user_id)
    if not u or not u["verified"]:
        await require_verified(message)
        return

    task = get_next_task(user_id)

    if not task:
        await message.reply_text("❌ আর কোনো টাস্ক বর্তমানে উপলব্ধ নেই।")
        return

    text = (
        "NEW EARNING TASK AVAILABLE\n\n"
        f"📢 Task Channel:\n{task['link']}\n\n"
        "💰 Task Reward:\n"
        f"{money(task['reward'])} টাকা\n\n"
        "📊 Task Progress:\n"
        f"{task['completed_count']} / {task['max_users']} Users Completed\n\n"
        "⚠️ Important Notice:\n"
        "If you leave the channel within 24 hours after completing this task,\n"
        "your earned amount will be deducted/back automatically.\n\n"
        "🔥 Complete tasks and keep earning more!"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔹 Join Now", url=task["link"])],
            [
                InlineKeyboardButton("✅ Joined", callback_data=f"task_done:{task['id']}"),
                InlineKeyboardButton("⚠️ Skip Task", callback_data=f"task_skip:{task['id']}"),
            ],
        ]
    )

    await message.reply_text(text, reply_markup=kb)


async def complete_task(query, context, task_id):
    user_id = query.from_user.id
    task = fetchone("SELECT * FROM tasks WHERE id=?", (task_id,))

    if not task or not task["active"]:
        await query.message.reply_text("❌ এই টাস্কটি বর্তমানে উপলব্ধ নেই।")
        return

    if task["completed_count"] >= task["max_users"]:
        await query.message.reply_text("❌ এই টাস্কের লিমিট শেষ হয়ে গেছে।")
        return

    joined = await is_member(context.bot, task["chat_id"], user_id)
    if not joined:
        await query.message.reply_text("⚠️ You must join the channel first!")
        return

    already = fetchone(
        "SELECT id FROM task_completions WHERE user_id=? AND task_id=?",
        (user_id, task_id),
    )
    if already:
        await query.message.reply_text("✅ এই টাস্ক আগে সম্পন্ন করা হয়েছে।")
        return

    try:
        with conn:
            fresh = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

            if fresh["completed_count"] >= fresh["max_users"]:
                await query.message.reply_text("❌ এই টাস্কের লিমিট শেষ হয়ে গেছে।")
                return

            conn.execute(
                """
                INSERT INTO task_completions(user_id, task_id, reward, completed_at)
                VALUES(?,?,?,?)
                """,
                (user_id, task_id, fresh["reward"], now_iso()),
            )
            conn.execute(
                "UPDATE tasks SET completed_count=completed_count+1 WHERE id=?",
                (task_id,),
            )
            conn.execute(
                """
                UPDATE users
                SET balance=balance+?, task_income=task_income+?
                WHERE user_id=?
                """,
                (fresh["reward"], fresh["reward"], user_id),
            )
    except sqlite3.IntegrityError:
        await query.message.reply_text("✅ এই টাস্ক আগে সম্পন্ন করা হয়েছে।")
        return

    updated = fetchone("SELECT * FROM tasks WHERE id=?", (task_id,))

    await query.message.reply_text(
        "✅ Task Completed Successfully!\n\n"
        f"💰 Earned: {money(task['reward'])} টাকা\n"
        f"📊 Total Completed: {updated['completed_count']} / {updated['max_users']}"
    )

    await show_task(query.message, user_id)


async def skip_task(query, task_id):
    user_id = query.from_user.id

    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO task_skips(user_id, task_id) VALUES(?,?)",
            (user_id, task_id),
        )

    await query.message.reply_text("⚠️ Task skipped.")
    await show_task(query.message, user_id)


async def check_task_leave_for_user(bot, user_id):
    cutoff = (datetime.utcnow() - timedelta(hours=24)).replace(microsecond=0).isoformat()

    rows = fetchall(
        """
        SELECT c.id, c.reward, t.chat_id, t.link
        FROM task_completions c
        JOIN tasks t ON t.id=c.task_id
        WHERE c.user_id=?
        AND c.deducted=0
        AND c.completed_at>=?
        """,
        (user_id, cutoff),
    )

    for r in rows:
        still_joined = await is_member(bot, r["chat_id"], user_id)
        if not still_joined:
            reward = float(r["reward"])
            with conn:
                conn.execute(
                    "UPDATE task_completions SET deducted=1 WHERE id=? AND deducted=0",
                    (r["id"],),
                )
                conn.execute(
                    """
                    UPDATE users
                    SET
                        balance = CASE WHEN balance - ? < 0 THEN 0 ELSE balance - ? END,
                        task_income = CASE WHEN task_income - ? < 0 THEN 0 ELSE task_income - ? END
                    WHERE user_id=?
                    """,
                    (reward, reward, reward, reward, user_id),
                )

            try:
                await bot.send_message(
                    user_id,
                    "⚠️ আপনি 24 ঘণ্টার মধ্যে টাস্ক চ্যানেল থেকে Leave করেছেন।\n"
                    f"💰 Deducted: {money(reward)} টাকা",
                )
            except Exception:
                pass


async def periodic_leave_check(context: ContextTypes.DEFAULT_TYPE):
    cutoff = (datetime.utcnow() - timedelta(hours=24)).replace(microsecond=0).isoformat()

    rows = fetchall(
        """
        SELECT DISTINCT user_id
        FROM task_completions
        WHERE deducted=0 AND completed_at>=?
        """,
        (cutoff,),
    )

    for r in rows:
        await check_task_leave_for_user(context.bot, r["user_id"])


# ================= WITHDRAW =================

async def start_withdraw(message, user_id):
    u = get_user(user_id)
    if not u or not u["verified"]:
        await require_verified(message)
        return

    text = (
        f"🏧 উইড্রো\n\n"
        f"আপনার ব্যালেন্স : {money(u['balance'])} টাকা\n"
        f"সর্বনিম্ন উইথড্র {money(MIN_WITHDRAW)} tk\n"
        f"সর্বোচ্চ উইথড্র {money(MAX_WITHDRAW)} tk\n\n"
        "নিচে Amount লিখে পাঠান ➤"
    )

    set_state(user_id, STATE_WITHDRAW_AMOUNT)
    await message.reply_text(text)


async def process_withdraw_amount(message, user_id, text):
    try:
        amount = parse_amount(text)
    except Exception:
        await message.reply_text("❌ সঠিক Amount লিখুন।")
        return

    u = get_user(user_id)

    if amount < MIN_WITHDRAW:
        clear_state(user_id)
        await message.reply_text(f"❌ সর্বনিম্ন উইথড্র {money(MIN_WITHDRAW)} টাকা।", reply_markup=MAIN_MENU)
        return

    if amount > MAX_WITHDRAW:
        clear_state(user_id)
        await message.reply_text(f"❌ সর্বোচ্চ উইথড্র {money(MAX_WITHDRAW)} টাকা।", reply_markup=MAIN_MENU)
        return

    if float(u["balance"]) < amount:
        clear_state(user_id)
        await message.reply_text("❌ আপনার ব্যালেন্স পর্যাপ্ত নেই। উইথড্রো বাতিল করা হয়েছে।", reply_markup=MAIN_MENU)
        return

    set_state(user_id, STATE_WITHDRAW_METHOD, {"amount": amount})

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("বিকাশ", callback_data="wd_method:bkash"),
                InlineKeyboardButton("নগদ", callback_data="wd_method:nagad"),
            ],
            [InlineKeyboardButton("রকেট", callback_data="wd_method:rocket")],
            [InlineKeyboardButton("❌ Cancel", callback_data="wd_cancel")],
        ]
    )

    await message.reply_text(
        "এখন আপনার টাকা নেওয়ার মেথড সিলেক্ট করুন:",
        reply_markup=kb,
    )


async def process_withdraw_number(message, context, user_id, text):
    state, data = get_state(user_id)
    amount = float(data.get("amount", 0))
    method = data.get("method", "")

    number = re.sub(r"[^\d+]", "", text.strip())

    if len(number) < 10:
        await message.reply_text("❌ সঠিক নাম্বার দিন।")
        return

    u = get_user(user_id)
    if not u or float(u["balance"]) < amount:
        clear_state(user_id)
        await message.reply_text("❌ ব্যালেন্স পর্যাপ্ত নেই। উইথড্রো বাতিল।", reply_markup=MAIN_MENU)
        return

    with conn:
        conn.execute(
            "UPDATE users SET balance=balance-? WHERE user_id=?",
            (amount, user_id),
        )
        cur = conn.execute(
            """
            INSERT INTO withdraw_requests(user_id, amount, method, number, status, created_at)
            VALUES(?,?,?,?, 'pending', ?)
            """,
            (user_id, amount, method, number, now_iso()),
        )
        req_id = cur.lastrowid

    clear_state(user_id)

    await message.reply_text(
        "✅ আপনার উইথড্রো রিকোয়েস্ট পাঠানো হয়েছে।\n"
        "Admin approve করলে পেমেন্ট সম্পন্ন হবে।",
        reply_markup=MAIN_MENU,
    )

    username = f"@{u['username']}" if u["username"] else "নেই"

    admin_text = (
        "🏧 নতুন উইথড্রো রিকোয়েস্ট\n\n"
        f"👤 নাম: {u['first_name']}\n"
        f"🔗 ইউজারনেম: {username}\n"
        f"🆔 ইউজার আইডি: {user_id}\n"
        f"💰 Amount: {money(amount)} BDT\n"
        f"🏦 Method: {method}\n"
        f"📱 Number: {number}\n\n"
        "অ্যাকশন নিন:"
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approved ✅", callback_data=f"wa:{req_id}"),
                InlineKeyboardButton("Rejected ❌", callback_data=f"wr:{req_id}"),
            ]
        ]
    )

    await send_admins(context.bot, admin_text, kb)


# ================= VERIFICATION =================

async def show_verify_panel(message, user_id):
    u = get_user(user_id)

    if u and u["verified"]:
        await message.reply_text(
            "🚨 একাউন্ট ভেরিফাই\n\n"
            "আপনার একাউন্ট ভেরিফাইড আছে, এখন আপনি সব সার্ভিস সঠিকভাবে ব্যবহার করতে পারবেন ❤️😊"
        )
        return

    text = (
        "🧡 Lucky Nagad Deposit Panel 🧡\n\n"
        f"📌 Wallet No: {WALLET_NO}\n"
        f"(নম্বরটি কপি করতে উপরে নম্বরের উপর চাপ দিন)\n\n"
        f"{money(VERIFY_AMOUNT)} taka সেন্ডমানি পাঠান ✅\n"
        "কম বা বেশি করবেন না নাহলে আপনার ডিপোজিট ক্রিডিট পেতে সক্ষম হবেন না ⚠️\n\n"
        "⚠️ নির্দেশনা: এই নাম্বারে শুধুমাত্র Send Money প্রযোজ্য।\n"
        "আপনার কাঙ্ক্ষিত অ্যামাউন্টটি এই নম্বরে পাঠানোর পর নিচের বাটনে চাপ দিন।\n\n"
        "📝 Transaction ID (TxID):\n"
        "নিচের বাটনে চাপ দিয়ে আপনার ট্রানজেকশন আইডি প্রদান করুন।"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✍️ Enter Transaction ID", callback_data="ver_txid")],
            [InlineKeyboardButton("❌ ডিপোজিট প্রক্রিয়া বাতিল।", callback_data="ver_cancel")],
        ]
    )

    await message.reply_text(text, reply_markup=kb)


async def process_verify_txid(message, context, user_id, txid):
    txid = txid.strip()

    if len(txid) < 4:
        await message.reply_text("❌ সঠিক TxID দিন।")
        return

    u = get_user(user_id)
    if u and u["verified"]:
        clear_state(user_id)
        await message.reply_text("✅ আপনার একাউন্ট ইতিমধ্যে ভেরিফাইড।", reply_markup=MAIN_MENU)
        return

    duplicate = fetchone(
        """
        SELECT id FROM verification_requests
        WHERE txid=? AND status IN ('pending','approved')
        """,
        (txid,),
    )
    if duplicate:
        await message.reply_text("⚠️ এই TxID আগে ব্যবহার করা হয়েছে বা Pending আছে।")
        return

    with conn:
        cur = conn.execute(
            """
            INSERT INTO verification_requests(user_id, txid, amount, status, created_at)
            VALUES(?,?,?, 'pending', ?)
            """,
            (user_id, txid, VERIFY_AMOUNT, now_iso()),
        )
        req_id = cur.lastrowid

    clear_state(user_id)

    await message.reply_text(
        "⏳ আপনার ট্রানজেকশন আইডিটি ভেরিফিকেশনের জন্য পাঠানো হয়েছে।\n"
        "সঠিক তথ্য থাকলে খুব দ্রুত ব্যালেন্স যুক্ত হয়ে যাবে। অনুগ্রহ করে অপেক্ষা করুন...",
        reply_markup=MAIN_MENU,
    )

    username = f"@{u['username']}" if u and u["username"] else "নেই"
    name = u["first_name"] if u else ""

    admin_text = (
        "📥 নতুন অ্যাকাউন্ট ভেরিফাই রিকোয়েস্ট\n\n"
        f"👤 নাম: {name}\n"
        f"🔗 ইউজারনেম: {username}\n"
        f"🆔 ইউজার আইডি: {user_id}\n"
        f"💰 অ্যামাউন্ট: {money(VERIFY_AMOUNT)} BDT\n"
        f"🆔 TxID: {txid}\n\n"
        "অ্যাকশন নিন:"
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approved ✅", callback_data=f"va:{req_id}"),
                InlineKeyboardButton("Rejected ❌", callback_data=f"vr:{req_id}"),
            ]
        ]
    )

    await send_admins(context.bot, admin_text, kb)


def mark_user_verified_and_bonus(user_id):
    u = get_user(user_id)
    if not u:
        return None, 0

    ref_id = None

    if not u["verified"] and u["referrer_id"] and not u["referral_paid"]:
        ref = get_user(u["referrer_id"])
        if ref and not ref["banned"]:
            ref_id = u["referrer_id"]

    with conn:
        conn.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))

        if ref_id:
            conn.execute(
                """
                UPDATE users
                SET balance=balance+?, refer_income=refer_income+?
                WHERE user_id=?
                """,
                (REFERRAL_BONUS, REFERRAL_BONUS, ref_id),
            )
            conn.execute(
                "UPDATE users SET referral_paid=1 WHERE user_id=?",
                (user_id,),
            )

    if ref_id:
        return ref_id, REFERRAL_BONUS

    return None, 0


# ================= REFER =================

async def show_referral(message, context, user_id):
    u = get_user(user_id)

    me = await context.bot.get_me()
    bot_username = me.username
    link = f"https://t.me/{bot_username}?start={user_id}"

    total = fetchone(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=?",
        (user_id,),
    )["c"]

    verified = fetchone(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND verified=1",
        (user_id,),
    )["c"]

    text = (
        "💵 রেফার আয়\n\n"
        f"👤 Total Refer: {total} জন\n"
        f"✅ Verified Refer: {verified} জন\n"
        f"💲 Total Refer Income: {money(u['refer_income'])} BDT\n\n"
        "🔗 আপনার রেফার লিংক:\n"
        f"{link}\n\n"
        f"ℹ️ আপনি আপনার প্রতিটি রেফারেলের একাউন্ট ভেরিফাইয়ের জন্য {money(REFERRAL_BONUS)} টাকা করে পাবেন।\n"
        "📌 বিস্তারিত জানতে নিচের Rules বাটন চাপুন ⤵️"
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Rules", callback_data="ref_rules"),
                InlineKeyboardButton("রেফার নাম্বার লিস্ট", callback_data="ref_list"),
            ]
        ]
    )

    await message.reply_text(text, reply_markup=kb)


async def show_ref_list(message, user_id):
    rows = fetchall(
        "SELECT * FROM users WHERE referrer_id=? ORDER BY created_at ASC",
        (user_id,),
    )

    total = len(rows)
    verified_count = len([r for r in rows if r["verified"]])

    if not rows:
        await message.reply_text("👥 আপনার কোনো রেফারেল নেই।")
        return

    lines = [
        f"👥 আপনার মোট রেফারেল মেম্বার: {total} জন",
        f"✅ ভেরিফাই করেছে: {verified_count} জন",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for i, r in enumerate(rows, 1):
        username = f"@{r['username']}" if r["username"] else "নেই"
        status = "✅ Verified" if r["verified"] else "⏳ Not Verified"
        lines.append(f"{i}. 🆔 {r['user_id']} — ইউজারনেম {username} — {status}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    await send_long(message, "\n".join(lines))


# ================= ADMIN =================

async def admin_panel(message):
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ Task Add", callback_data="ad_add_task"),
                InlineKeyboardButton("📋 Task List", callback_data="ad_list_task"),
            ],
            [
                InlineKeyboardButton("➕ Forced Join Add", callback_data="ad_add_req"),
                InlineKeyboardButton("📌 Forced Join List", callback_data="ad_list_req"),
            ],
            [
                InlineKeyboardButton("👤 User Manage", callback_data="ad_user"),
            ],
            [
                InlineKeyboardButton("📥 Pending Verify", callback_data="ad_pver"),
                InlineKeyboardButton("🏧 Pending Withdraw", callback_data="ad_pwd"),
            ],
        ]
    )

    await message.reply_text("🔐 Admin Panel\n\nনিচের অপশন নির্বাচন করুন:", reply_markup=kb)


async def admin_list_tasks(message):
    rows = fetchall("SELECT * FROM tasks ORDER BY id DESC LIMIT 30")

    if not rows:
        await message.reply_text("কোনো task নেই।")
        return

    lines = ["📋 Task List\n"]
    buttons = []

    for r in rows:
        status = "ON ✅" if r["active"] else "OFF ❌"
        lines.append(
            f"ID: {r['id']} | {status}\n"
            f"Channel: {r['chat_id']}\n"
            f"Reward: {money(r['reward'])} | Progress: {r['completed_count']}/{r['max_users']}\n"
        )

        new_status = 0 if r["active"] else 1
        btn_text = f"{'OFF' if r['active'] else 'ON'} Task #{r['id']}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"ad_task_toggle:{r['id']}:{new_status}")])

    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def admin_list_required(message):
    rows = fetchall("SELECT * FROM required_channels WHERE active=1 ORDER BY id ASC")

    if not rows:
        await message.reply_text("Forced Join channel নেই।")
        return

    lines = ["📌 Forced Join Channels\n"]
    buttons = []

    for r in rows:
        lines.append(f"ID: {r['id']} | {r['chat_id']}\n{r['link']}\n")
        buttons.append([InlineKeyboardButton(f"❌ Delete #{r['id']}", callback_data=f"ad_req_del:{r['id']}")])

    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def show_admin_user(message, user_id):
    u = get_user(user_id)

    if not u:
        await message.reply_text("❌ User পাওয়া যায়নি।")
        return

    total_ref = fetchone("SELECT COUNT(*) AS c FROM users WHERE referrer_id=?", (user_id,))["c"]
    verified_ref = fetchone(
        "SELECT COUNT(*) AS c FROM users WHERE referrer_id=? AND verified=1",
        (user_id,),
    )["c"]

    username = f"@{u['username']}" if u["username"] else "নেই"
    verified = "YES ✅" if u["verified"] else "NO ❌"
    banned = "YES 🚫" if u["banned"] else "NO ✅"

    text = (
        "👤 User Details\n\n"
        f"নাম: {u['first_name']}\n"
        f"Username: {username}\n"
        f"ID: {u['user_id']}\n"
        f"Verified: {verified}\n"
        f"Banned: {banned}\n"
        f"Balance: {money(u['balance'])}\n"
        f"Refer Income: {money(u['refer_income'])}\n"
        f"Task Income: {money(u['task_income'])}\n"
        f"Total Refer: {total_ref}\n"
        f"Verified Refer: {verified_ref}\n"
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Ban 🚫", callback_data=f"ad_ban:{user_id}"),
                InlineKeyboardButton("Unban ✅", callback_data=f"ad_unban:{user_id}"),
            ],
            [
                InlineKeyboardButton("Verify ✅", callback_data=f"ad_verify:{user_id}"),
                InlineKeyboardButton("Unverify ❌", callback_data=f"ad_unverify:{user_id}"),
            ],
            [
                InlineKeyboardButton("Set Balance", callback_data=f"ad_setbal:{user_id}"),
            ],
            [
                InlineKeyboardButton("Set Refer Income", callback_data=f"ad_setref:{user_id}"),
                InlineKeyboardButton("Set Task Income", callback_data=f"ad_settask:{user_id}"),
            ],
        ]
    )

    await message.reply_text(text, reply_markup=kb)


async def list_pending_verify(message):
    rows = fetchall(
        """
        SELECT vr.*, u.first_name, u.username
        FROM verification_requests vr
        LEFT JOIN users u ON u.user_id=vr.user_id
        WHERE vr.status='pending'
        ORDER BY vr.id ASC
        LIMIT 20
        """
    )

    if not rows:
        await message.reply_text("✅ কোনো pending verification নেই।")
        return

    for r in rows:
        username = f"@{r['username']}" if r["username"] else "নেই"
        text = (
            "📥 Pending Verification\n\n"
            f"Req ID: {r['id']}\n"
            f"👤 {r['first_name']}\n"
            f"🔗 {username}\n"
            f"🆔 {r['user_id']}\n"
            f"💰 {money(r['amount'])} BDT\n"
            f"TxID: {r['txid']}"
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Approved ✅", callback_data=f"va:{r['id']}"),
                    InlineKeyboardButton("Rejected ❌", callback_data=f"vr:{r['id']}"),
                ]
            ]
        )

        await message.reply_text(text, reply_markup=kb)


async def list_pending_withdraw(message):
    rows = fetchall(
        """
        SELECT wr.*, u.first_name, u.username
        FROM withdraw_requests wr
        LEFT JOIN users u ON u.user_id=wr.user_id
        WHERE wr.status='pending'
        ORDER BY wr.id ASC
        LIMIT 20
        """
    )

    if not rows:
        await message.reply_text("✅ কোনো pending withdraw নেই।")
        return

    for r in rows:
        username = f"@{r['username']}" if r["username"] else "নেই"
        text = (
            "🏧 Pending Withdraw\n\n"
            f"Req ID: {r['id']}\n"
            f"👤 {r['first_name']}\n"
            f"🔗 {username}\n"
            f"🆔 {r['user_id']}\n"
            f"💰 {money(r['amount'])} BDT\n"
            f"Method: {r['method']}\n"
            f"Number: {r['number']}"
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Approved ✅", callback_data=f"wa:{r['id']}"),
                    InlineKeyboardButton("Rejected ❌", callback_data=f"wr:{r['id']}"),
                ]
            ]
        )

        await message.reply_text(text, reply_markup=kb)


async def process_admin_state(message, context, state, data, text):
    user_id = message.from_user.id

    if state == ADMIN_TASK_CHAT:
        chat_id = normalize_chat_id(text)
        link_default = default_link_from_chat(chat_id)
        set_state(user_id, ADMIN_TASK_LINK, {"chat_id": chat_id, "link_default": link_default})
        await message.reply_text(
            "এখন Task Channel-এর link দিন।\n"
            f"যদি public channel হয়, example: {link_default or 'https://t.me/channel'}"
        )
        return

    if state == ADMIN_TASK_LINK:
        data["link"] = text.strip()
        set_state(user_id, ADMIN_TASK_REWARD, data)
        await message.reply_text("এখন Task Reward amount দিন। Example: 1")
        return

    if state == ADMIN_TASK_REWARD:
        try:
            reward = parse_amount(text)
        except Exception:
            await message.reply_text("❌ সঠিক reward দিন।")
            return

        data["reward"] = reward
        set_state(user_id, ADMIN_TASK_MAX, data)
        await message.reply_text("কতজন user task complete করতে পারবে? Example: 1000")
        return

    if state == ADMIN_TASK_MAX:
        try:
            max_users = int(parse_amount(text))
        except Exception:
            await message.reply_text("❌ সঠিক সংখ্যা দিন।")
            return

        if max_users <= 0:
            await message.reply_text("❌ সংখ্যা 1 বা তার বেশি হতে হবে।")
            return

        chat_id = data["chat_id"]
        link = data["link"]
        reward = float(data["reward"])

        with conn:
            conn.execute(
                """
                INSERT INTO tasks(title, chat_id, link, reward, max_users, active, created_at)
                VALUES(?,?,?,?,?,1,?)
                """,
                (chat_id, chat_id, link, reward, max_users, now_iso()),
            )

        clear_state(user_id)
        await message.reply_text("✅ Task channel added successfully.")
        return

    if state == ADMIN_REQ_CHAT:
        chat_id = normalize_chat_id(text)
        link_default = default_link_from_chat(chat_id)
        set_state(user_id, ADMIN_REQ_LINK, {"chat_id": chat_id, "link_default": link_default})
        await message.reply_text(
            "এখন Forced Join Channel link দিন।\n"
            f"Example: {link_default or 'https://t.me/channel'}"
        )
        return

    if state == ADMIN_REQ_LINK:
        chat_id = data["chat_id"]
        link = text.strip()

        with conn:
            conn.execute(
                """
                INSERT INTO required_channels(title, chat_id, link, active)
                VALUES(?,?,?,1)
                """,
                (chat_id, chat_id, link),
            )

        clear_state(user_id)
        await message.reply_text("✅ Forced Join channel added.")
        return

    if state == ADMIN_USER_LOOKUP:
        try:
            target_id = int(parse_amount(text))
        except Exception:
            await message.reply_text("❌ সঠিক User ID দিন।")
            return

        clear_state(user_id)
        await show_admin_user(message, target_id)
        return

    if state in (ADMIN_SET_BALANCE, ADMIN_SET_REF, ADMIN_SET_TASK):
        try:
            amount = parse_amount(text)
        except Exception:
            await message.reply_text("❌ সঠিক amount দিন।")
            return

        target_id = int(data["target_id"])

        if state == ADMIN_SET_BALANCE:
            field = "balance"
        elif state == ADMIN_SET_REF:
            field = "refer_income"
        else:
            field = "task_income"

        with conn:
            conn.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (amount, target_id))

        clear_state(user_id)
        await message.reply_text("✅ Updated successfully.")
        await show_admin_user(message, target_id)
        return


# ================= COMMANDS =================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    ref_id = None
    if context.args:
        try:
            ref_id = int(context.args[0])
        except Exception:
            ref_id = None

    add_or_update_user(user, ref_id)

    if not await ensure_ready(update, context):
        return

    await send_main_menu(update.message)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_or_update_user(update.effective_user)

    if not is_admin_id(update.effective_user.id):
        await update.message.reply_text("❌ আপনি admin নন।")
        return

    clear_state(update.effective_user.id)
    await admin_panel(update.message)


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_state(update.effective_user.id)
    await update.message.reply_text("❌ প্রক্রিয়া বাতিল করা হয়েছে।", reply_markup=MAIN_MENU)


# ================= MESSAGE HANDLER =================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    add_or_update_user(user)

    state, data = get_state(user.id)

    # Admin states bypass forced join
    if state and state.startswith("ADMIN_"):
        if is_admin_id(user.id):
            await process_admin_state(update.message, context, state, data, text)
            return

    if not await ensure_ready(update, context):
        return

    state, data = get_state(user.id)

    if state == STATE_VERIFY_TXID:
        await process_verify_txid(update.message, context, user.id, text)
        return

    if state == STATE_WITHDRAW_AMOUNT:
        await process_withdraw_amount(update.message, user.id, text)
        return

    if state == STATE_WITHDRAW_NUMBER:
        await process_withdraw_number(update.message, context, user.id, text)
        return

    if text == "👤 একাউন্ট":
        await show_account(update.message, user.id)

    elif text == "📋 টাস্ক আয়":
        await show_task(update.message, user.id)

    elif text == "🏧 উইড্রো":
        await start_withdraw(update.message, user.id)

    elif text == "🚨 একাউন্ট ভেরিফাই":
        await show_verify_panel(update.message, user.id)

    elif text == "💵 রেফার আয়":
        await show_referral(update.message, context, user.id)

    else:
        await update.message.reply_text("নিচের মেনু থেকে অপশন নির্বাচন করুন।", reply_markup=MAIN_MENU)


# ================= CALLBACKS =================

async def handle_admin_callback(query, context, data):
    uid = query.from_user.id

    if not is_admin_id(uid):
        await query.message.reply_text("❌ আপনি admin নন।")
        return

    if data == "ad_add_task":
        set_state(uid, ADMIN_TASK_CHAT)
        await query.message.reply_text(
            "Task Channel username/id দিন।\n\n"
            "Example:\n"
            "@channelusername\n"
            "অথবা -100xxxxxxxxxx\n\n"
            "⚠️ Bot-কে ঐ channel-এ admin করতে হবে।"
        )
        return

    if data == "ad_list_task":
        await admin_list_tasks(query.message)
        return

    if data == "ad_add_req":
        set_state(uid, ADMIN_REQ_CHAT)
        await query.message.reply_text(
            "Forced Join Channel username/id দিন।\n\n"
            "Example:\n"
            "@channelusername\n"
            "অথবা -100xxxxxxxxxx\n\n"
            "⚠️ Bot-কে ঐ channel-এ admin করতে হবে।"
        )
        return

    if data == "ad_list_req":
        await admin_list_required(query.message)
        return

    if data == "ad_user":
        set_state(uid, ADMIN_USER_LOOKUP)
        await query.message.reply_text("User ID পাঠান:")
        return

    if data == "ad_pver":
        await list_pending_verify(query.message)
        return

    if data == "ad_pwd":
        await list_pending_withdraw(query.message)
        return

    if data.startswith("ad_task_toggle:"):
        _, task_id, new_status = data.split(":")
        with conn:
            conn.execute(
                "UPDATE tasks SET active=? WHERE id=?",
                (int(new_status), int(task_id)),
            )
        await query.message.reply_text("✅ Task status updated.")
        await admin_list_tasks(query.message)
        return

    if data.startswith("ad_req_del:"):
        req_id = int(data.split(":")[1])
        with conn:
            conn.execute("UPDATE required_channels SET active=0 WHERE id=?", (req_id,))
        await query.message.reply_text("✅ Forced join channel deleted.")
        await admin_list_required(query.message)
        return

    if data.startswith("ad_ban:"):
        target_id = int(data.split(":")[1])
        with conn:
            conn.execute("UPDATE users SET banned=1 WHERE user_id=?", (target_id,))
        await query.message.reply_text("🚫 User banned.")
        await show_admin_user(query.message, target_id)
        return

    if data.startswith("ad_unban:"):
        target_id = int(data.split(":")[1])
        with conn:
            conn.execute("UPDATE users SET banned=0 WHERE user_id=?", (target_id,))
        await query.message.reply_text("✅ User unbanned.")
        await show_admin_user(query.message, target_id)
        return

    if data.startswith("ad_verify:"):
        target_id = int(data.split(":")[1])
        ref_id, bonus = mark_user_verified_and_bonus(target_id)

        try:
            await context.bot.send_message(
                target_id,
                "✅ আপনার একাউন্ট সফলভাবে ভেরিফাই হয়েছে।",
            )
        except Exception:
            pass

        if ref_id:
            try:
                await context.bot.send_message(
                    ref_id,
                    f"🎉 আপনার রেফার করা একজন user verify করেছে।\n💰 Referral Bonus: {money(bonus)} টাকা",
                )
            except Exception:
                pass

        await query.message.reply_text("✅ User verified.")
        await show_admin_user(query.message, target_id)
        return

    if data.startswith("ad_unverify:"):
        target_id = int(data.split(":")[1])
        with conn:
            conn.execute("UPDATE users SET verified=0 WHERE user_id=?", (target_id,))
        await query.message.reply_text("❌ User unverified.")
        await show_admin_user(query.message, target_id)
        return

    if data.startswith("ad_setbal:"):
        target_id = int(data.split(":")[1])
        set_state(uid, ADMIN_SET_BALANCE, {"target_id": target_id})
        await query.message.reply_text("নতুন Balance amount পাঠান:")
        return

    if data.startswith("ad_setref:"):
        target_id = int(data.split(":")[1])
        set_state(uid, ADMIN_SET_REF, {"target_id": target_id})
        await query.message.reply_text("নতুন Refer Income amount পাঠান:")
        return

    if data.startswith("ad_settask:"):
        target_id = int(data.split(":")[1])
        set_state(uid, ADMIN_SET_TASK, {"target_id": target_id})
        await query.message.reply_text("নতুন Task Income amount পাঠান:")
        return

    # Verification approve/reject
    if data.startswith("va:") or data.startswith("vr:"):
        approve = data.startswith("va:")
        req_id = int(data.split(":")[1])

        req = fetchone("SELECT * FROM verification_requests WHERE id=?", (req_id,))
        if not req or req["status"] != "pending":
            await query.message.reply_text("⚠️ Request already processed or not found.")
            return

        status = "approved" if approve else "rejected"

        with conn:
            conn.execute(
                "UPDATE verification_requests SET status=? WHERE id=?",
                (status, req_id),
            )

        if approve:
            ref_id, bonus = mark_user_verified_and_bonus(req["user_id"])

            try:
                await context.bot.send_message(
                    req["user_id"],
                    "✅ আপনার একাউন্ট সফলভাবে ভেরিফাই হয়েছে।",
                )
            except Exception:
                pass

            if ref_id:
                try:
                    await context.bot.send_message(
                        ref_id,
                        f"🎉 আপনার রেফার করা একজন user verify করেছে।\n💰 Referral Bonus: {money(bonus)} টাকা",
                    )
                except Exception:
                    pass

            await query.message.reply_text("Approved ✅")
        else:
            try:
                await context.bot.send_message(
                    req["user_id"],
                    "❌ আপনার অ্যাকাউন্ট ভেরিফাই রিকোয়েস্ট টি বাতিল করা হয়েছে।\n"
                    "দয়া করে ট্রানজেকশন চেক করুন। কোনো সমস্যা হলে সাপোর্টে যোগাযোগ করুন।",
                )
            except Exception:
                pass

            await query.message.reply_text("Rejected ❌")

        return

    # Withdraw approve/reject
    if data.startswith("wa:") or data.startswith("wr:"):
        approve = data.startswith("wa:")
        req_id = int(data.split(":")[1])

        req = fetchone("SELECT * FROM withdraw_requests WHERE id=?", (req_id,))
        if not req or req["status"] != "pending":
            await query.message.reply_text("⚠️ Request already processed or not found.")
            return

        if approve:
            with conn:
                conn.execute(
                    "UPDATE withdraw_requests SET status='approved' WHERE id=?",
                    (req_id,),
                )

            try:
                await context.bot.send_message(
                    req["user_id"],
                    f"✅ আপনার {money(req['amount'])} টাকা উইথড্রো Approved হয়েছে।",
                )
            except Exception:
                pass

            await query.message.reply_text("Withdraw Approved ✅")
        else:
            with conn:
                conn.execute(
                    "UPDATE withdraw_requests SET status='rejected' WHERE id=?",
                    (req_id,),
                )
                conn.execute(
                    "UPDATE users SET balance=balance+? WHERE user_id=?",
                    (req["amount"], req["user_id"]),
                )

            try:
                await context.bot.send_message(
                    req["user_id"],
                    f"❌ আপনার {money(req['amount'])} টাকা উইথড্রো Rejected হয়েছে।\n"
                    "Amount আপনার balance-এ ফেরত দেওয়া হয়েছে।",
                )
            except Exception:
                pass

            await query.message.reply_text("Withdraw Rejected ❌ and refunded.")
        return


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user = query.from_user

    await query.answer()
    add_or_update_user(user)

    admin_prefixes = (
        "ad_",
        "va:",
        "vr:",
        "wa:",
        "wr:",
    )

    if data.startswith(admin_prefixes):
        await handle_admin_callback(query, context, data)
        return

    if data == "check_join":
        ok, missing = await check_required_join(context.bot, user.id)
        if ok:
            await query.message.reply_text(
                "✅ Verification successful!",
                reply_markup=MAIN_MENU,
            )
            await send_main_menu(query.message)
        else:
            await query.message.reply_text("⚠️ এখনো সব চ্যানেলে Join করেননি।")
            await send_join_prompt(query.message, context.bot, missing)
        return

    if not await ensure_ready(update, context):
        return

    if data == "open_verify":
        await show_verify_panel(query.message, user.id)
        return

    if data == "ver_txid":
        set_state(user.id, STATE_VERIFY_TXID)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ ডিপোজিট প্রক্রিয়া বাতিল।", callback_data="ver_cancel")]]
        )
        await query.message.reply_text(
            "📝 অনুগ্রহ করে আপনার account ভেরিফাই এর জন্য ট্রানজেকশন আইডি (TxID) টি চ্যাটে লিখে পাঠান:",
            reply_markup=kb,
        )
        return

    if data == "ver_cancel":
        clear_state(user.id)
        await query.message.reply_text("❌ ডিপোজিট প্রক্রিয়া বাতিল।", reply_markup=MAIN_MENU)
        return

    if data.startswith("task_done:"):
        task_id = int(data.split(":")[1])
        await complete_task(query, context, task_id)
        return

    if data.startswith("task_skip:"):
        task_id = int(data.split(":")[1])
        await skip_task(query, task_id)
        return

    if data.startswith("wd_method:"):
        method = data.split(":")[1]
        state, sdata = get_state(user.id)

        if state != STATE_WITHDRAW_METHOD:
            await query.message.reply_text("⚠️ Withdraw session পাওয়া যায়নি। আবার চেষ্টা করুন।")
            return

        sdata["method"] = method
        set_state(user.id, STATE_WITHDRAW_NUMBER, sdata)

        await query.message.reply_text(
            f"আপনি {method} সিলেক্ট করেছেন।\nএখন আপনার নাম্বার লিখে পাঠান:"
        )
        return

    if data == "wd_cancel":
        clear_state(user.id)
        await query.message.reply_text("❌ উইথড্রো বাতিল করা হয়েছে।", reply_markup=MAIN_MENU)
        return

    if data == "ref_rules":
        await query.message.reply_text(
            "Rules\n\n"
            "আপনার রেফার করা ব্যক্তি যদি আপনার রেফার লিংক দিয়ে বট ওপেন করে একাউন্ট ভেরিফাই করে "
            f"সাথে সাথে আপনি {money(REFERRAL_BONUS)} টাকা রেফার বোনাস পেয়ে যাবেন ❤️✅"
        )
        return

    if data == "ref_list":
        await show_ref_list(query.message, user.id)
        return


# ================= MAIN =================

def main():
    init_db()

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: BOT_TOKEN সেট করেননি।")
        print("Termux example:")
        print("export BOT_TOKEN='123456:ABC...'")
        print("export OWNER_ID='আপনার_numeric_telegram_id'")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    if app.job_queue:
        app.job_queue.run_repeating(periodic_leave_check, interval=600, first=60)

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
