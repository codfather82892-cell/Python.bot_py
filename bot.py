import asyncio
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "2"))
MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_SECONDS", "3600"))
PYTHON = sys.executable
DATA_DIR.mkdir(parents=True, exist_ok=True)
BOT_DIR = DATA_DIR / "user_bots"
BOT_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "hosting.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vortexa-host")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add it to Railway Variables.")

bot = Bot(TOKEN)
dp = Dispatcher()
processes = {}  # bot_id -> subprocess; runtime only
upload_wait = set()

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📤 Deploy Bot"), KeyboardButton(text="🤖 My Bots")],
        [KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="💎 Subscription")],
        [KeyboardButton(text="🆘 Help & Support")]
    ], resize_keyboard=True
)

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS user_bots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'stopped',
            created_at TEXT NOT NULL,
            last_exit INTEGER,
            last_error TEXT DEFAULT ''
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL
        )""")
init_db()

def now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

def owned_bot(user_id: int, bot_id: int):
    with db() as con:
        return con.execute("SELECT * FROM user_bots WHERE id=? AND owner_id=?", (bot_id, user_id)).fetchone()

def bot_buttons(row):
    running = row["status"] == "running" and row["id"] in processes and processes[row["id"]].returncode is None
    controls = [
        InlineKeyboardButton(text="⏹ Stop" if running else "▶️ Start", callback_data=f"toggle:{row['id']}"),
        InlineKeyboardButton(text="📄 View Logs", callback_data=f"logs:{row['id']}"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        controls,
        [InlineKeyboardButton(text="🔄 Restart", callback_data=f"restart:{row['id']}"),
         InlineKeyboardButton(text="🗑 Delete", callback_data=f"delete:{row['id']}")]
    ])

async def send_log(user_id, text):
    try:
        await bot.send_message(user_id, text)
    except Exception:
        log.exception("Could not send user log notification")

async def monitor_process(bot_id: int, owner_id: int, proc: asyncio.subprocess.Process):
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=MAX_RUNTIME_SECONDS)
        code = proc.returncode
        output = ((stdout or b"").decode("utf-8", "replace") + "\n" +
                  (stderr or b"").decode("utf-8", "replace")).strip()
        output = output[-3500:] or "(No output)"
        with db() as con:
            con.execute("UPDATE user_bots SET status='stopped', last_exit=?, last_error=? WHERE id=?",
                        (code, output[-1500:], bot_id))
        processes.pop(bot_id, None)
        if code != 0:
            await send_log(owner_id,
                "🚨 <b>Your Bot Crashed!</b>\n━━━━━━━━━━━━━━━━\n"
                f"📋 Name: <code>{escape_html(Path(str(bot_id)).name)}</code>\n"
                f"🚫 Exit Code: <b>{code}</b>\n🕔 Time: {now()}\n\n"
                "🔴 <b>Last Error</b>\n<pre>" + escape_html(output[-2500:]) +
                "</pre>\n\nCheck logs and restart after fixing the issue.")
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        processes.pop(bot_id, None)
        with db() as con:
            con.execute("UPDATE user_bots SET status='stopped', last_exit=-9, last_error='Runtime limit exceeded' WHERE id=?", (bot_id,))
        await send_log(owner_id, f"⏱ Bot #{bot_id} stopped: runtime limit exceeded.")

def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

async def start_bot(row, notify=True):
    bot_id = row["id"]
    if bot_id in processes and processes[bot_id].returncode is None:
        return False, "এই বটটি ইতিমধ্যে চলছে।"
    path = Path(row["file_path"])
    if not path.exists():
        return False, "ফাইলটি পাওয়া যায়নি। আবার আপলোড করুন।"
    # Syntax check before launch. This detects syntax errors but does not prove code is safe.
    check = await asyncio.create_subprocess_exec(
        PYTHON, "-m", "py_compile", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, err = await check.communicate()
    if check.returncode != 0:
        error = err.decode("utf-8", "replace")[-2500:]
        with db() as con:
            con.execute("UPDATE user_bots SET status='error', last_exit=?, last_error=? WHERE id=?",
                        (check.returncode, error, bot_id))
        return False, "🚨 <b>PRE-LAUNCH SYNTAX ERROR</b>\n<pre>" + escape_html(error) + "</pre>"
    # IMPORTANT: This starter launches user code as the same OS account. Only use with trusted uploads.
    # Production hosting must run each uploaded project inside a separate locked-down container/sandbox.
    workdir = path.parent
    proc = await asyncio.create_subprocess_exec(
        PYTHON, "-u", str(path),
        cwd=str(workdir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True
    )
    processes[bot_id] = proc
    with db() as con:
        con.execute("UPDATE user_bots SET status='running', last_exit=NULL, last_error='' WHERE id=?", (bot_id,))
    asyncio.create_task(monitor_process(bot_id, row["owner_id"], proc))
    if notify:
        return True, f"✅ Bot #{bot_id} চালু করার কমান্ড পাঠানো হয়েছে। Process শুরু হয়েছে; পুরোপুরি কাজ করছে কি না Logs-এ দেখুন।"
    return True, "started"

async def stop_bot(bot_id):
    proc = processes.get(bot_id)
    if proc and proc.returncode is None:
        try:
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
    processes.pop(bot_id, None)
    with db() as con:
        con.execute("UPDATE user_bots SET status='stopped' WHERE id=?", (bot_id,))

class UploadFlow(StatesGroup):
    waiting_file = State()

@dp.message(CommandStart())
async def start(message: Message):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users(user_id,created_at) VALUES(?,?)", (message.from_user.id, now()))
    await message.answer(
        "☁️ <b>Vortexa Smart Hosting</b>\n━━━━━━━━━━━━━━━━━━\n"
        "📤 Python ফাইল আপলোড করুন, Syntax Check হবে, তারপর Run করার চেষ্টা করবে।\n"
        "⚠️ এই starter version-এ শুধু .py ফাইল সমর্থিত।",
        reply_markup=MAIN_KB
    )

@dp.message(F.text == "📤 Deploy Bot")
async def deploy_prompt(message: Message, state: FSMContext):
    await state.set_state(UploadFlow.waiting_file)
    await message.answer("📤 এখন একটি <b>.py</b> ফাইল পাঠাও। সর্বোচ্চ ফাইল সাইজ: " + str(MAX_FILE_MB) + " MB।")

@dp.message(UploadFlow.waiting_file, F.document)
async def receive_file(message: Message, state: FSMContext):
    doc = message.document
    filename = Path(doc.file_name or "bot.py").name
    if not filename.lower().endswith(".py"):
        await message.answer("❌ আপাতত শুধু .py ফাইল সাপোর্ট করে। ZIP/অন্যান্য ফাইলের জন্য sandbox build লাগবে।")
        return
    if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await message.answer(f"❌ ফাইল বড়। সর্বোচ্চ {MAX_FILE_MB} MB অনুমোদিত।")
        return
    user_dir = BOT_DIR / str(message.from_user.id) / f"upload_{int(time.time())}"
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / filename
    try:
        tg_file = await bot.get_file(doc.file_id)
        await bot.download_file(tg_file.file_path, destination=dest)
    except Exception as e:
        shutil.rmtree(user_dir, ignore_errors=True)
        await message.answer("❌ ফাইল ডাউনলোড করা যায়নি: " + escape_html(str(e)[:300]))
        return
    with db() as con:
        cur = con.execute(
            "INSERT INTO user_bots(owner_id,filename,file_path,status,created_at) VALUES(?,?,?,?,?)",
            (message.from_user.id, filename, str(dest), "stopped", now())
        )
        bot_id = cur.lastrowid
        row = con.execute("SELECT * FROM user_bots WHERE id=?", (bot_id,)).fetchone()
    await state.clear()
    await message.answer(f"✅ <b>FILE UPLOADED!</b>\n📄 <code>{escape_html(filename)}</code>\n🆔 Bot ID: <code>{bot_id}</code>\n🔍 Syntax check চলছে…")
    ok, result = await start_bot(row)
    await message.answer(result, reply_markup=bot_buttons(row))
    if ok:
        await message.answer("💡 লাইব্রেরি না থাকলে startup error আসতে পারে। requirements.txt স্বয়ংক্রিয়ভাবে ইনস্টল করা হচ্ছে না।")

@dp.message(F.text == "🤖 My Bots")
async def my_bots(message: Message):
    with db() as con:
        rows = con.execute("SELECT * FROM user_bots WHERE owner_id=? ORDER BY id DESC LIMIT 20", (message.from_user.id,)).fetchall()
    if not rows:
        await message.answer("এখনো কোনো বট আপলোড করোনি। 📤 Deploy Bot চাপো।")
        return
    await message.answer("🤖 <b>Your Bots</b>\n━━━━━━━━━━━━━━━━")
    for row in rows:
        proc = processes.get(row["id"])
        live = bool(proc and proc.returncode is None)
        await message.answer(
            f"📄 <b>{escape_html(row['filename'])}</b>\n🆔 #{row['id']}\n"
            f"Status: {'🟢 Running' if live else '🔴 Stopped'}",
            reply_markup=bot_buttons(row)
        )

@dp.callback_query(F.data.startswith(("toggle:", "restart:", "logs:", "delete:")))
async def bot_action(call: CallbackQuery):
    action, raw_id = call.data.split(":", 1)
    try:
        bot_id = int(raw_id)
    except ValueError:
        await call.answer("Invalid ID", show_alert=True); return
    row = owned_bot(call.from_user.id, bot_id)
    if not row:
        await call.answer("এই বটটি তোমার নয় বা পাওয়া যায়নি।", show_alert=True); return
    if action == "toggle":
        proc = processes.get(bot_id)
        if proc and proc.returncode is None:
            await stop_bot(bot_id)
            await call.message.answer(f"⏹ Bot #{bot_id} বন্ধ করা হয়েছে।")
        else:
            ok, result = await start_bot(row)
            await call.message.answer(result)
    elif action == "restart":
        await stop_bot(bot_id)
        row = owned_bot(call.from_user.id, bot_id)
        ok, result = await start_bot(row)
        await call.message.answer("🔄 " + result)
    elif action == "logs":
        proc = processes.get(bot_id)
        if proc and proc.returncode is None:
            await call.message.answer("ℹ️ Live stdout/stderr-এর জন্য আলাদা log streaming প্রয়োজন। এই starter-এ process শেষ হলে শেষ error সংরক্ষণ হয়।")
        else:
            text = row["last_error"] or "(এখনো কোনো error সংরক্ষিত নেই)"
            await call.message.answer("📄 <b>Logs / Last Error</b>\n<pre>" + escape_html(text[-3500:]) + "</pre>")
    elif action == "delete":
        await stop_bot(bot_id)
        with db() as con:
            con.execute("DELETE FROM user_bots WHERE id=?", (bot_id,))
        try:
            shutil.rmtree(Path(row["file_path"]).parent, ignore_errors=True)
        except Exception:
            pass
        await call.message.answer(f"🗑 Bot #{bot_id} মুছে ফেলা হয়েছে।")
    await call.answer()

@dp.message(F.text == "📊 Dashboard")
async def dashboard(message: Message):
    with db() as con:
        total = con.execute("SELECT COUNT(*) n FROM user_bots WHERE owner_id=?", (message.from_user.id,)).fetchone()["n"]
    live = sum(1 for k, p in processes.items() if p.returncode is None and (owned_bot(message.from_user.id, k) is not None))
    await message.answer(
        "📊 <b>Dashboard</b>\n━━━━━━━━━━━━━━━━\n"
        f"🤖 Total bots: {total}\n🟢 Live: {live}\n"
        f"📦 Plan: Free (demo UI)\n💾 Max upload: {MAX_FILE_MB} MB"
    )

@dp.message(F.text == "💎 Subscription")
async def subscription(message: Message):
    await message.answer(
        "💎 <b>SUBSCRIPTION</b>\n━━━━━━━━━━━━━━━━━━\n"
        "📦 Your Plan: 🆓 Free\n📅 Expires: ♾️ Demo\n🤖 Slots: 1\n"
        "💾 Memory: not enforced in this starter\n\n"
        "📋 <b>Available Plans (display only)</b>\n"
        "🟢 Starter — 1 bot\n⭐ Basic — 2 bots\n💎 Pro — 4 bots\n"
        "🏢 Enterprise — 8 bots\n🚀 Ultra — 12 bots\n\n"
        "⚠️ Payments and actual resource quotas are not enabled."
    )

@dp.message(F.text == "🆘 Help & Support")
async def help_message(message: Message):
    await message.answer(
        "🆘 <b>Help</b>\n"
        "• Deploy Bot চাপুন, তারপর .py ফাইল পাঠান\n"
        "• My Bots থেকে Start/Stop/Restart/Logs\n"
        "• Syntax error হলে ফাইল ঠিক করে আবার আপলোড করুন\n"
        "• নিরাপত্তার জন্য অপরিচিত কোড production-এ চালাবেন না"
    )

@dp.message(Command("status"))
async def status_cmd(message: Message):
    await dashboard(message)

async def main():
    log.info("Vortexa Smart Hosting bot starting")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
