import ast
import asyncio
import importlib.util
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
import venv
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
INSTALL_TIMEOUT_SECONDS = int(os.getenv("INSTALL_TIMEOUT_SECONDS", "60"))
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
processes = {}  # bot_id -> subprocess; process handles are not persistent across Railway redeploys

MAIN_KB = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="📤 Deploy Bot"), KeyboardButton(text="🤖 My Bots")],
    [KeyboardButton(text="📊 Dashboard"), KeyboardButton(text="💎 Subscription")],
    [KeyboardButton(text="🆘 Help & Support")]
], resize_keyboard=True)
SKIP_KB = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(text="⏭ Skip — Auto Detect", callback_data="depskip")
]])

# Common import-name -> PyPI package-name mappings. Unknown third-party imports are
# included using their import name; auto-detection is best-effort, not perfect AI.
PACKAGE_MAP = {
    "PIL": "Pillow", "cv2": "opencv-python-headless", "yaml": "PyYAML",
    "dotenv": "python-dotenv", "telegram": "python-telegram-bot",
    "aiogram": "aiogram", "telebot": "pyTelegramBotAPI", "Crypto": "pycryptodome",
    "bs4": "beautifulsoup4", "sklearn": "scikit-learn", "fitz": "PyMuPDF",
    "google": "google-api-python-client", "googleapiclient": "google-api-python-client",
    "openai": "openai", "anthropic": "anthropic", "requests": "requests",
    "httpx": "httpx", "aiohttp": "aiohttp", "numpy": "numpy", "pandas": "pandas",
    "matplotlib": "matplotlib", "flask": "flask", "fastapi": "fastapi",
    "uvicorn": "uvicorn", "sqlalchemy": "sqlalchemy", "redis": "redis",
    "motor": "motor", "pymongo": "pymongo", "psycopg2": "psycopg2-binary",
    "websockets": "websockets", "websocket": "websocket-client", "selenium": "selenium",
    "playwright": "playwright", "lxml": "lxml", "orjson": "orjson",
}
STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {
    "__future__", "typing_extensions", "pkg_resources", "setuptools", "pip"
}

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
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
            last_error TEXT DEFAULT '',
            requirements_path TEXT DEFAULT '',
            install_status TEXT DEFAULT 'pending'
        )""")
        # Migrate older starter databases without deleting existing records.
        cols = {r[1] for r in con.execute("PRAGMA table_info(user_bots)").fetchall()}
        if "requirements_path" not in cols:
            con.execute("ALTER TABLE user_bots ADD COLUMN requirements_path TEXT DEFAULT ''")
        if "install_status" not in cols:
            con.execute("ALTER TABLE user_bots ADD COLUMN install_status TEXT DEFAULT 'pending'")
        con.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL
        )""")
init_db()

def now():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def owned_bot(user_id: int, bot_id: int):
    with db() as con:
        return con.execute("SELECT * FROM user_bots WHERE id=? AND owner_id=?", (bot_id, user_id)).fetchone()

def get_bot(bot_id: int):
    with db() as con:
        return con.execute("SELECT * FROM user_bots WHERE id=?", (bot_id,)).fetchone()

def update_bot(bot_id: int, **fields):
    allowed = {"status", "last_exit", "last_error", "requirements_path", "install_status"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sql = ", ".join(f"{k}=?" for k in fields)
    with db() as con:
        con.execute(f"UPDATE user_bots SET {sql} WHERE id=?", (*fields.values(), bot_id))

def bot_folder(row):
    return Path(row["file_path"]).parent

def venv_python(row):
    vdir = bot_folder(row) / ".venv"
    return vdir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

def log_path(row):
    return bot_folder(row) / "runtime.log"

def bot_buttons(row):
    proc = processes.get(row["id"])
    running = bool(proc and proc.returncode is None)
    controls = [
        InlineKeyboardButton(text="⏹ Stop" if running else "▶️ Start", callback_data=f"toggle:{row['id']}"),
        InlineKeyboardButton(text="📄 View Logs", callback_data=f"logs:{row['id']}")
    ]
    return InlineKeyboardMarkup(inline_keyboard=[controls, [
        InlineKeyboardButton(text="🔄 Restart", callback_data=f"restart:{row['id']}"),
        InlineKeyboardButton(text="🗑 Delete", callback_data=f"delete:{row['id']}")
    ]])

async def send_log(user_id, text):
    try:
        await bot.send_message(user_id, text)
    except Exception:
        log.exception("Could not send user log notification")

def infer_requirements(source: str):
    """Best-effort import scan. Produces probable PyPI names, not guaranteed dependencies."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], "Python syntax error: automatic import scan could not parse this file."
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    packages = set()
    for name in names:
        if name in STDLIB or name.startswith("_"):
            continue
        # If a module is installed in the host interpreter, it may still not exist in the bot venv;
        # known package mapping is used, otherwise use the import name as a best-effort PyPI name.
        packages.add(PACKAGE_MAP.get(name, name.replace("_", "-")))
    return sorted(packages, key=str.lower), None

async def run_command(args, cwd=None, timeout=60, env=None):
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env
    )
    try:
        output, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        output, _ = await proc.communicate()
        return -9, (output or b"").decode("utf-8", "replace") + f"\nTimed out after {timeout}s"
    return proc.returncode, (output or b"").decode("utf-8", "replace")

async def prepare_environment(row):
    path = Path(row["file_path"])
    if not path.exists():
        return False, "আপলোড করা Python ফাইলটি পাওয়া যাচ্ছে না। Persistent Volume `/app/data`-এ মাউন্ট করা আছে কি না এবং DATA_DIR একই আছে কি না যাচাই করো।"
    folder = path.parent
    vdir = folder / ".venv"
    py = venv_python(row)
    if not py.exists():
        update_bot(row["id"], install_status="installing")
        code, out = await run_command([PYTHON, "-m", "venv", str(vdir)], cwd=folder, timeout=45)
        if code != 0 or not py.exists():
            update_bot(row["id"], install_status="error", last_error=out[-3000:])
            return False, "❌ Bot-এর virtual environment তৈরি হয়নি।\n<pre>" + escape_html(out[-2500:]) + "</pre>"
    req = Path(row["requirements_path"]) if row["requirements_path"] else folder / "requirements.txt"
    if req.exists() and req.read_text(encoding="utf-8", errors="replace").strip():
        install = True
        req_text = req.read_text(encoding="utf-8", errors="replace")
    else:
        source = path.read_text(encoding="utf-8", errors="replace")
        packages, syntax_problem = infer_requirements(source)
        if syntax_problem:
            return False, "❌ " + escape_html(syntax_problem)
        req_text = "\n".join(packages) + ("\n" if packages else "")
        req.write_text(req_text, encoding="utf-8")
        update_bot(row["id"], requirements_path=str(req), install_status="auto-detected")
        install = bool(packages)
    if install:
        update_bot(row["id"], install_status="installing")
        await send_log(row["owner_id"], f"📦 <b>Dependencies installing</b> for bot #{row['id']}…\nসময় লাগতে পারে; {INSTALL_TIMEOUT_SECONDS} সেকেন্ডে শেষ না হলে লগ দেখো।")
        code, out = await run_command([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(req)], cwd=folder, timeout=INSTALL_TIMEOUT_SECONDS)
        (folder / "install.log").write_text(out[-12000:], encoding="utf-8")
        if code != 0:
            update_bot(row["id"], install_status="error", last_error=out[-3000:])
            return False, "❌ <b>লাইব্রেরি ইনস্টল হয়নি</b>\nrequirements.txt ঠিক করো বা View Logs দেখো।\n<pre>" + escape_html(out[-2500:]) + "</pre>"
    update_bot(row["id"], install_status="ready")
    return True, "ready"

async def monitor_process(bot_id: int, owner_id: int, proc: asyncio.subprocess.Process, filename: str):
    try:
        try:
            code = await asyncio.wait_for(proc.wait(), timeout=MAX_RUNTIME_SECONDS)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            code = -9
            with open(log_path(get_bot(bot_id)), "a", encoding="utf-8") as f:
                f.write(f"\n[Host] Runtime limit exceeded ({MAX_RUNTIME_SECONDS}s).\n")
        processes.pop(bot_id, None)
        row = get_bot(bot_id)
        if row:
            try:
                output = log_path(row).read_text(encoding="utf-8", errors="replace")[-3500:]
            except Exception:
                output = "(log file unavailable)"
            update_bot(bot_id, status="stopped", last_exit=code, last_error=output[-1500:])
        else:
            output = "Bot record was deleted while process was running."
        if code != 0 and row:
            await send_log(owner_id,
                "🚨 <b>Your Bot Stopped / Crashed</b>\n━━━━━━━━━━━━━━━━\n"
                f"📋 Name: <code>{escape_html(filename)}</code>\n🆔 Bot ID: <code>{bot_id}</code>\n"
                f"🚫 Exit Code: <b>{code}</b>\n🕔 Time: {now()}\n\n"
                "🔴 <b>Last Logs</b>\n<pre>" + escape_html(output[-2500:]) + "</pre>")
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception("Process monitor failed for bot %s", bot_id)

async def start_bot(row, notify=True):
    bot_id = row["id"]
    current = processes.get(bot_id)
    if current and current.returncode is None:
        return False, "এই বটটি ইতিমধ্যে চলছে।"
    row = get_bot(bot_id)
    if not row:
        return False, "বটের রেকর্ড ডাটাবেসে নেই। পুরোনো বাটন হলে My Bots থেকে নতুন বাটন নাও।"
    path = Path(row["file_path"])
    if not path.exists():
        return False, "আপলোড করা ফাইলটি পাওয়া যাচ্ছে না। DATA_DIR ও Persistent Volume ঠিক আছে কি না দেখো; ফাইলটি আবার আপলোড করতে হতে পারে।"
    check, err = await run_command([PYTHON, "-m", "py_compile", str(path)], cwd=path.parent, timeout=15)
    if check != 0:
        update_bot(bot_id, status="error", last_exit=check, last_error=err[-3000:])
        return False, "🚨 <b>SYNTAX ERROR</b>\n<pre>" + escape_html(err[-2500:]) + "</pre>"
    ok, detail = await prepare_environment(row)
    if not ok:
        return False, detail
    row = get_bot(bot_id)
    py = venv_python(row)
    try:
        logfile = log_path(row).open("a", encoding="utf-8")
        logfile.write(f"\n\n[Host] Started at {now()}\n")
        logfile.flush()
        # Do not use PIPE for a long-running process: a full pipe can freeze the uploaded bot.
        proc = await asyncio.create_subprocess_exec(
            str(py), "-u", str(path), cwd=str(path.parent),
            stdout=logfile, stderr=logfile, start_new_session=True
        )
        # Parent can close its file handle after subprocess inherits it.
        logfile.close()
    except Exception as e:
        update_bot(bot_id, status="error", last_error=str(e))
        return False, "❌ Bot start করা যায়নি: " + escape_html(str(e)[:1000])
    processes[bot_id] = proc
    update_bot(bot_id, status="running", last_exit=None, last_error="")
    asyncio.create_task(monitor_process(bot_id, row["owner_id"], proc, row["filename"]))
    return True, f"✅ Bot #{bot_id} start command দেওয়া হয়েছে। পুরোপুরি কাজ করছে কি না View Logs-এ দেখো।"

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
    if get_bot(bot_id):
        update_bot(bot_id, status="stopped")

class UploadFlow(StatesGroup):
    waiting_file = State()
    waiting_requirements = State()

@dp.message(CommandStart())
async def start(message: Message):
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users(user_id,created_at) VALUES(?,?)", (message.from_user.id, now()))
    await message.answer(
        "☁️ <b>Vortexa Smart Hosting</b>\n━━━━━━━━━━━━━━━━━━\n"
        "📤 Python .py ফাইল আপলোড করো। এরপর requirements.txt দিতে পারবে অথবা Skip করলে import দেখে dependency অনুমান করা হবে।\n"
        "⚠️ Auto-detection সব লাইব্রেরি নিখুঁতভাবে শনাক্ত করতে পারে না। শুধু বিশ্বাসযোগ্য কোড আপলোড করো।",
        reply_markup=MAIN_KB)

@dp.message(F.text == "📤 Deploy Bot")
async def deploy_prompt(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(UploadFlow.waiting_file)
    await message.answer(f"📤 এখন একটি .py ফাইল পাঠাও। সর্বোচ্চ {MAX_FILE_MB} MB।")

@dp.message(UploadFlow.waiting_file, F.document)
async def receive_file(message: Message, state: FSMContext):
    doc = message.document
    filename = Path(doc.file_name or "bot.py").name
    if not filename.lower().endswith(".py"):
        await message.answer("❌ প্রথমে Python-এর .py ফাইল পাঠাও।")
        return
    if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await message.answer(f"❌ ফাইল বড়। সর্বোচ্চ {MAX_FILE_MB} MB অনুমোদিত।")
        return
    user_dir = BOT_DIR / str(message.from_user.id) / f"bot_{int(time.time())}_{time.time_ns() % 100000}"
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
            "INSERT INTO user_bots(owner_id,filename,file_path,status,created_at,install_status) VALUES(?,?,?,?,?,?)",
            (message.from_user.id, filename, str(dest.resolve()), "stopped", now(), "pending")
        )
        bot_id = cur.lastrowid
    await state.update_data(pending_bot_id=bot_id)
    await state.set_state(UploadFlow.waiting_requirements)
    await message.answer(
        f"✅ <b>Python ফাইল আপলোড হয়েছে!</b>\n📄 <code>{escape_html(filename)}</code>\n🆔 Bot ID: <code>{bot_id}</code>\n\n"
        "📦 এখন চাইলে <code>requirements.txt</code> ফাইল পাঠাও।\n"
        "এতে কোন লাইব্রেরি লাগবে সেগুলো এক লাইনে থাকবে।\n\n"
        "ফাইল না থাকলে নিচের <b>Skip — Auto Detect</b> চাপো। কোডের import দেখে requirements তৈরি ও install করার চেষ্টা করবে।",
        reply_markup=SKIP_KB)

async def finish_dependency_setup(message: Message, state: FSMContext, bot_id: int, requirements_content=None):
    row = owned_bot(message.from_user.id, bot_id)
    if not row:
        await message.answer("❌ আপলোডের রেকর্ড পাওয়া যাচ্ছে না। My Bots খুলে আবার চেষ্টা করো।")
        await state.clear()
        return
    folder = bot_folder(row)
    if requirements_content is not None:
        req = folder / "requirements.txt"
        req.write_text(requirements_content, encoding="utf-8")
        update_bot(bot_id, requirements_path=str(req.resolve()), install_status="pending")
        await message.answer("📦 requirements.txt সংরক্ষণ হয়েছে। এখন dependency install ও deploy শুরু করছি…")
    else:
        await message.answer("🔎 কোডের import scan করে requirements.txt বানাচ্ছি, তারপর install/deploy চেষ্টা করব…")
    await state.clear()
    # Run in the background so Telegram callback/message does not hang; report result when ready.
    row = get_bot(bot_id)
    ok, result = await start_bot(row)
    row = get_bot(bot_id)
    await message.answer(result, reply_markup=bot_buttons(row) if row else MAIN_KB)
    if ok:
        await message.answer("📄 Generated/provided requirements file ও runtime log সংরক্ষিত আছে। View Logs চাপলে লগ দেখতে পারবে।")

@dp.message(UploadFlow.waiting_requirements, F.document)
async def receive_requirements(message: Message, state: FSMContext):
    doc = message.document
    filename = (doc.file_name or "").lower()
    if not filename.endswith(".txt") or ("requirements" not in filename and filename != "requirements.txt"):
        await message.answer("❌ requirements.txt (বা requirements নামসহ .txt ফাইল) পাঠাও, অথবা Skip চাপো।")
        return
    if doc.file_size and doc.file_size > 100 * 1024:
        await message.answer("❌ requirements ফাইলটি 100 KB-এর নিচে হতে হবে।")
        return
    data = await state.get_data()
    bot_id = data.get("pending_bot_id")
    if not bot_id:
        await state.clear()
        await message.answer("আপলোড সেশন পাওয়া যায়নি। আবার Deploy Bot চাপো।")
        return
    try:
        tg_file = await bot.get_file(doc.file_id)
        content = await bot.download_file(tg_file.file_path)
        raw = content.read().decode("utf-8", "replace")
    except Exception as e:
        await message.answer("ফাইল পড়া যায়নি: " + escape_html(str(e)[:300]))
        return
    # Reject obvious pip options/URLs to reduce accidental unsafe installs; only package lines accepted.
    lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if any(line.startswith(("-", "git+", "http://", "https://")) for line in lines):
        await message.answer("❌ নিরাপত্তার জন্য requirements-এ URL/git/installer option গ্রহণ করা হয়নি। সাধারণ package==version লাইন ব্যবহার করো বা Skip চাপো।")
        return
    await finish_dependency_setup(message, state, int(bot_id), "\n".join(lines) + ("\n" if lines else ""))

@dp.callback_query(F.data == "depskip")
async def skip_requirements(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bot_id = data.get("pending_bot_id")
    if not bot_id:
        await call.answer("Upload session expired. Deploy Bot থেকে আবার শুরু করো।", show_alert=True)
        return
    row = owned_bot(call.from_user.id, int(bot_id))
    if not row:
        await call.answer("আপলোডের রেকর্ড পাওয়া যায়নি; My Bots দেখো।", show_alert=True)
        await state.clear()
        return
    await call.answer("Auto-detect শুরু হচ্ছে…")
    await call.message.answer("⏭ Skip নেওয়া হয়েছে। এখন import দেখে requirements.txt তৈরি ও install করব…")
    await state.clear()
    ok, result = await start_bot(get_bot(int(bot_id)))
    row = get_bot(int(bot_id))
    await call.message.answer(result, reply_markup=bot_buttons(row) if row else MAIN_KB)
    if ok:
        await call.message.answer("📄 My Bots থেকে Start/Stop/Restart/View Logs ব্যবহার করতে পারবে।")

@dp.message(UploadFlow.waiting_requirements)
async def requirements_invalid(message: Message):
    await message.answer("📦 requirements.txt ফাইল পাঠাও অথবা Skip — Auto Detect বাটন চাপো।")

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
            f"Status: {'🟢 Running' if live else '🔴 Stopped'}\n📦 Dependencies: {escape_html(row['install_status'] or 'pending')}",
            reply_markup=bot_buttons(row))

@dp.callback_query(F.data.startswith(("toggle:", "restart:", "logs:", "delete:")))
async def bot_action(call: CallbackQuery):
    action, raw_id = call.data.split(":", 1)
    try:
        bot_id = int(raw_id)
    except ValueError:
        await call.answer("Invalid ID", show_alert=True)
        return
    row = owned_bot(call.from_user.id, bot_id)
    if not row:
        # Distinguish stale/removed records from a real ownership mismatch.
        any_row = get_bot(bot_id)
        if any_row:
            await call.answer("এই বটটি অন্য ইউজারের; নিজের My Bots থেকে বট চালাও।", show_alert=True)
        else:
            await call.answer("বটের রেকর্ড পাওয়া যায়নি। সম্ভবত পুরোনো DB/Volume হারিয়েছে বা পুরোনো বাটন। My Bots রিফ্রেশ করো; না থাকলে আবার upload করো।", show_alert=True)
        return
    if action == "toggle":
        proc = processes.get(bot_id)
        if proc and proc.returncode is None:
            await stop_bot(bot_id)
            await call.message.answer(f"⏹ Bot #{bot_id} বন্ধ করা হয়েছে।", reply_markup=bot_buttons(get_bot(bot_id)))
        else:
            ok, result = await start_bot(row)
            await call.message.answer(result, reply_markup=bot_buttons(get_bot(bot_id)))
    elif action == "restart":
        await stop_bot(bot_id)
        row = get_bot(bot_id)
        ok, result = await start_bot(row)
        await call.message.answer("🔄 " + result, reply_markup=bot_buttons(get_bot(bot_id)))
    elif action == "logs":
        row = get_bot(bot_id)
        parts = []
        lp = log_path(row)
        ip = bot_folder(row) / "install.log"
        for label, p in (("Runtime log", lp), ("Install log", ip)):
            if p.exists():
                parts.append(f"--- {label} ---\n" + p.read_text(encoding="utf-8", errors="replace")[-5000:])
        if row["last_error"]:
            parts.append("--- Last error ---\n" + row["last_error"])
        text = "\n\n".join(parts) or "এখনো কোনো লগ নেই। Start চাপো, তারপর আবার View Logs দেখো।"
        await call.message.answer("📄 <b>Logs</b>\n<pre>" + escape_html(text[-3500:]) + "</pre>")
    elif action == "delete":
        await stop_bot(bot_id)
        # Re-check ownership in the database transaction before deleting.
        with db() as con:
            con.execute("DELETE FROM user_bots WHERE id=? AND owner_id=?", (bot_id, call.from_user.id))
        try:
            shutil.rmtree(bot_folder(row), ignore_errors=True)
        except Exception:
            log.exception("Could not remove bot folder %s", bot_id)
        await call.message.answer(f"🗑 Bot #{bot_id} ও তার ফাইল মুছে ফেলা হয়েছে।")
    await call.answer()

@dp.message(F.text == "📊 Dashboard")
async def dashboard(message: Message):
    with db() as con:
        total = con.execute("SELECT COUNT(*) n FROM user_bots WHERE owner_id=?", (message.from_user.id,)).fetchone()["n"]
    live = sum(1 for k, p in processes.items() if p.returncode is None and owned_bot(message.from_user.id, k) is not None)
    await message.answer("📊 <b>Dashboard</b>\n━━━━━━━━━━━━━━━━\n"
                         f"🤖 Total bots: {total}\n🟢 Live: {live}\n📦 Plan: Free (demo UI)\n💾 Max upload: {MAX_FILE_MB} MB")

@dp.message(F.text == "💎 Subscription")
async def subscription(message: Message):
    await message.answer("💎 <b>SUBSCRIPTION</b>\n━━━━━━━━━━━━━━━━━━\n"
                         "📦 Your Plan: 🆓 Free\n📅 Expires: ♾️ Demo\n🤖 Slots: 1\n"
                         "📋 <b>Available Plans (display only)</b>\n🟢 Starter — 1 bot\n⭐ Basic — 2 bots\n"
                         "💎 Pro — 4 bots\n🏢 Enterprise — 8 bots\n🚀 Ultra — 12 bots\n\n"
                         "⚠️ Payments and actual resource quotas are not enabled.")

@dp.message(F.text == "🆘 Help & Support")
async def help_message(message: Message):
    await message.answer("🆘 <b>Help</b>\n"
                         "• Deploy Bot → .py ফাইল → requirements.txt দিন অথবা Skip করুন\n"
                         "• Skip করলে import দেখে dependency অনুমান করা হবে\n"
                         "• My Bots থেকে Start/Stop/Restart/Logs/Delete\n"
                         "• Logs-এ runtime ও dependency install error দেখা যাবে\n"
                         "• Persistent Volume mount `/app/data` এবং `DATA_DIR=/app/data` দরকার\n"
                         "• অচেনা কোড চালাবেন না; এই starter আলাদা sandbox container নয়।")

@dp.message(Command("status"))
async def status_cmd(message: Message):
    await dashboard(message)

async def main():
    log.info("Vortexa Smart Hosting bot starting; DATA_DIR=%s DB_PATH=%s", DATA_DIR, DB_PATH)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
