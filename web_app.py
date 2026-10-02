import hashlib
import hmac
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bot as core

app = FastAPI(title="NIKAN EARN Mini App", docs_url=None, redoc_url=None)
BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def validate_init_data(init_data: str):
    if not init_data:
        raise HTTPException(401, "Telegram authorization data missing.")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Invalid Telegram authorization data.")
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", core.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        raise HTTPException(401, "Telegram authorization validation failed.")
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(401, "Invalid auth_date.")
    if not auth_date or datetime.now(timezone.utc).timestamp() - auth_date > 86400:
        raise HTTPException(401, "Telegram authorization has expired.")
    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(401, "Invalid Telegram user data.")
    if not user.get("id"):
        raise HTTPException(401, "Telegram user not found.")
    return user, pairs


def current_user(x_telegram_init_data: str):
    user, pairs = validate_init_data(x_telegram_init_data)
    return int(user["id"]), user, pairs


def ensure_user(uid, user, start_param=""):
    con = core.db()
    cur = con.cursor()
    row = cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        ref_id = 0
        m = re.fullmatch(r"ref_(\d+)", start_param or "")
        if m:
            ref_id = int(m.group(1))
            if ref_id == uid:
                ref_id = 0
        cur.execute(
            "INSERT INTO users(user_id,name,username,created_at,referrer_id) VALUES(?,?,?,?,?)",
            (uid, user.get("first_name","") + ((" " + user.get("last_name","")) if user.get("last_name") else ""),
             user.get("username",""), core.now_iso(), ref_id)
        )
        if ref_id:
            cur.execute("UPDATE users SET referral_count=referral_count+1 WHERE user_id=?", (ref_id,))
            try:
                if core.getset("referral_enabled","0") == "1" and core.getset("bonus_enabled","0") == "1":
                    bonus = Decimal(core.getset("bonus_amount","0") or "0")
                    if bonus > 0:
                        cur.execute(
                            "UPDATE users SET referral_balance=referral_balance+?,main_balance=main_balance+?,total_earnings=total_earnings+? WHERE user_id=?",
                            (float(bonus), float(bonus), float(bonus), ref_id)
                        )
                        cur.execute(
                            "INSERT INTO bonuses(user_id,amount,type,created_at) VALUES(?,?,?,?)",
                            (ref_id, float(bonus), "referral_signup", core.now_iso())
                        )
            except Exception:
                pass
    else:
        cur.execute("UPDATE users SET name=?,username=? WHERE user_id=?",
                    (user.get("first_name","") + ((" " + user.get("last_name","")) if user.get("last_name") else ""),
                     user.get("username",""), uid))
    con.commit()
    row = cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    con.close()
    return row


def force_join_ok(uid):
    # The existing Telegram bot remains the source of truth for Force Join.
    # The Mini App checks it asynchronously through a lightweight endpoint.
    return None


def user_json(uid):
    core.expire_user_plans(uid)
    con = core.db()
    r = con.execute("""
        SELECT user_id,name,username,main_balance,deposit_balance,bonus_balance,
               referral_balance,total_earnings,created_at,referrer_id,task_balance,
               referral_count,completed_tasks,banned,suspended
        FROM users WHERE user_id=?
    """, (uid,)).fetchone()
    plans = con.execute("""
        SELECT id,plan,amount,activated_at,expires_at,last_claim_date,active,
               COALESCE(daily_rate,?)
        FROM plans WHERE user_id=? ORDER BY id DESC
    """, (float(core.DEMO_DAILY_RATE), uid)).fetchall()
    con.close()
    if not r:
        raise HTTPException(404, "User not found.")
    return {
        "id": r[0], "name": r[1] or "", "username": r[2] or "",
        "main_balance": float(r[3] or 0), "deposit_balance": float(r[4] or 0),
        "bonus_balance": float(r[5] or 0), "referral_balance": float(r[6] or 0),
        "total_earnings": float(r[7] or 0), "created_at": r[8],
        "referrer_id": r[9] or 0, "task_balance": float(r[10] or 0),
        "referral_count": r[11] or 0, "completed_tasks": r[12] or 0,
        "banned": bool(r[13]), "suspended": bool(r[14]),
        "plans": [
            {"id": p[0], "plan": p[1], "amount": float(p[2]), "activated_at": p[3],
             "expires_at": p[4], "last_claim_date": p[5], "active": bool(p[6]),
             "daily_rate": float(p[7] or core.DEMO_DAILY_RATE)}
            for p in plans if p[6]
        ]
    }


def require_access(uid):
    u = user_json(uid)
    if u["banned"] or u["suspended"]:
        raise HTTPException(403, "এই অ্যাকাউন্ট বর্তমানে ব্যবহার করা যাবে না।")
    return u


class AmountBody(BaseModel):
    amount: str


class DepositSubmit(BaseModel):
    session_id: str
    txid: str


class WithdrawBody(BaseModel):
    method: str
    account: str
    amount: str


class PlanBuy(BaseModel):
    plan: str


@app.get("/")
async def index():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/bootstrap")
async def bootstrap(x_telegram_init_data: str = Header(default="")):
    uid, tg_user, pairs = current_user(x_telegram_init_data)
    start_param = pairs.get("start_param", "")
    ensure_user(uid, tg_user, start_param)
    u = require_access(uid)
    con = core.db()
    dep_methods = con.execute("""
        SELECT name,logo,number,gateway,manual_enabled,COALESCE(gateway_enabled,0)
        FROM payment_methods WHERE kind='deposit' AND enabled=1 ORDER BY sort_order,id
    """).fetchall()
    wd_methods = con.execute("""
        SELECT name,logo,number FROM payment_methods
        WHERE kind='withdraw' AND enabled=1 ORDER BY sort_order,id
    """).fetchall()
    commands = con.execute("""
        SELECT command,title,enabled,position,message_key
        FROM bot_commands WHERE enabled=1 ORDER BY command
    """).fetchall()
    con.close()
    return {
        "user": u,
        "settings": {
            "bot_enabled": core.getset("bot_enabled","1") == "1",
            "fund_enabled": core.getset("fund_enabled","1") == "1",
            "withdraw_enabled": core.getset("withdraw_enabled","1") == "1",
            "bonus_enabled": core.getset("bonus_enabled","1") == "1",
            "bonus_amount": core.getset("bonus_amount","5"),
            "bonus_expiry_days": core.getset("bonus_expiry_days","1"),
            "min_dep": core.getset("min_dep","50"),
            "max_dep": core.getset("max_dep","10000"),
            "min_wth": core.getset("min_wth","100"),
            "max_wth": core.getset("max_wth","25000"),
            "referral_enabled": core.getset("referral_enabled","0") == "1",
            "referral_bonus": core.getset("referral_bonus","0"),
            "support": "@Nikan_Support01",
            "channel": "https://t.me/NIKAN_EARN"
        },
        "deposit_methods": [
            {"name":x[0],"logo":x[1],"number":x[2],"gateway":x[3],
             "manual":bool(x[4]),"gateway_on":bool(x[5] and x[3])}
            for x in dep_methods
            if (x[0].lower() == "binance" or bool(x[4]) or bool(x[5] and x[3]))
        ],
        "withdraw_methods": [{"name":x[0],"logo":x[1],"number":x[2]} for x in wd_methods],
        "commands": [{"command":x[0],"title":x[1],"position":x[3],"message":x[4]} for x in commands]
    }


@app.get("/api/account")
async def account_api(x_telegram_init_data: str = Header(default="")):
    uid, _, _ = current_user(x_telegram_init_data)
    return {"user": require_access(uid)}


@app.get("/api/plans")
async def plans_api(x_telegram_init_data: str = Header(default="")):
    uid, _, _ = current_user(x_telegram_init_data)
    require_access(uid)
    con = core.db()
    rows = con.execute("""
        SELECT name,amount,emoji,days,enabled,COALESCE(daily_rate,?)
        FROM plan_catalog WHERE enabled=1 ORDER BY rowid
    """, (float(core.DEMO_DAILY_RATE),)).fetchall()
    con.close()
    return {"plans":[{"name":x[0],"amount":float(x[1]),"emoji":x[2],"days":x[3],
                      "daily_rate":float(x[5])} for x in rows]}


@app.post("/api/plan/buy")
async def plan_buy(body: PlanBuy, x_telegram_init_data: str = Header(default="")):
    uid, _, _ = current_user(x_telegram_init_data)
    require_access(uid)
    plan = body.plan.strip()
    con = core.db()
    cur = con.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        core.expire_user_plans(uid, con)
        row = cur.execute("""
            SELECT amount,days,COALESCE(daily_rate,?) FROM plan_catalog
            WHERE name=? AND enabled=1
        """, (float(core.DEMO_DAILY_RATE), plan)).fetchone()
        if not row:
            raise ValueError("Plan পাওয়া যায়নি।")
        price, days, rate = Decimal(str(row[0])), int(row[1]), Decimal(str(row[2]))
        active_count = cur.execute(
            "SELECT COUNT(*) FROM plans WHERE user_id=? AND plan=? AND active=1", (uid,plan)
        ).fetchone()[0]
        if active_count >= 2:
            raise ValueError(f"{plan} Plan-এর সর্বোচ্চ ২টি active instance অনুমোদিত।")
        u = cur.execute("SELECT main_balance,deposit_balance FROM users WHERE user_id=?", (uid,)).fetchone()
        main, dep = Decimal(str(u[0] or 0)), Decimal(str(u[1] or 0))
        available = main + dep
        if available < price:
            raise ValueError(f"আপনার ব্যালেন্সে পর্যাপ্ত টাকা নেই। প্রয়োজন আরও {core.money(price-available)}৳।")
        from_main = min(main, price)
        from_dep = price - from_main
        changed = cur.execute("""
            UPDATE users SET main_balance=main_balance-?,deposit_balance=deposit_balance-?
            WHERE user_id=? AND main_balance>=? AND deposit_balance>=?
        """, (float(from_main),float(from_dep),uid,float(from_main),float(from_dep))).rowcount
        if changed != 1:
            raise ValueError("Balance changed; please retry.")
        activated = datetime.now(timezone.utc)
        expires = activated + timedelta(days=days)
        cur.execute("""
            INSERT INTO plans(user_id,plan,amount,activated_at,expires_at,last_claim_date,active,daily_rate)
            VALUES(?,?,?,?,?,'',1,?)
        """, (uid,plan,float(price),activated.isoformat(),expires.isoformat(),float(rate)))
        pid = cur.lastrowid
        cur.execute("""
            INSERT INTO balance_ledger(user_id,field,operation,amount,balance_before,balance_after,admin_id,reference,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (uid,"plan_purchase","remove",float(price),float(available),float(available-price),uid,f"PLAN-{pid}",core.now_iso()))
        con.commit()
    except Exception as e:
        con.rollback()
        con.close()
        raise HTTPException(400, str(e))
    con.close()
    try:
        await core.send_history_event("PLAN_PURCHASE", actor_id=uid, user_id=uid,
            reference=f"PLAN-{pid}", details=f"Plan: {plan}; Price: {core.money(price)}৳; Duration: {days} days; Daily: {core.money(price*rate)}৳")
    except Exception:
        pass
    return {"ok":True,"message":"Plan Successfully Activated!","user":user_json(uid)}


@app.get("/api/deposit/methods")
async def deposit_methods(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    if core.getset("fund_enabled") != "1":
        raise HTTPException(400,"বর্তমানে Deposit System বন্ধ আছে।")
    con=core.db()
    rows=con.execute("""
        SELECT name,logo,number,gateway,manual_enabled,COALESCE(gateway_enabled,0)
        FROM payment_methods WHERE kind='deposit' AND enabled=1 ORDER BY sort_order,id
    """).fetchall()
    con.close()
    out=[]
    for n,l,num,gw,manual,gwon in rows:
        if n.lower()=="binance" or manual or (gwon and gw):
            out.append({"name":n,"logo":l,"number":num,"gateway":gw,
                        "manual":bool(manual),"gateway_on":bool(gwon and gw)})
    return {"methods":out}


@app.post("/api/deposit/create")
async def deposit_create(body: dict, x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    method=str(body.get("method","")).strip()
    try: amount=Decimal(str(body.get("amount","")))
    except (InvalidOperation,ValueError): raise HTTPException(400,"সঠিক amount দিন।")
    if method.lower()=="binance":
        if amount<1 or amount>50: raise HTTPException(400,"USDT $1 থেকে $50 এর মধ্যে হতে হবে।")
        bdt=amount*core.USDT_RATE_BDT
    else:
        min_d=Decimal(core.getset("min_dep","50")); max_d=Decimal(core.getset("max_dep","10000"))
        if amount<min_d or amount>max_d: raise HTTPException(400,f"Deposit {core.money(min_d)}৳ থেকে {core.money(max_d)}৳ এর মধ্যে হতে হবে।")
        cfg=core.get_payment_method_config(method,"deposit")
        if not cfg: raise HTTPException(400,"এই Deposit Method বন্ধ আছে।")
        gateway_on=bool(cfg[5] and cfg[3]); manual=bool(cfg[4])
        if not gateway_on and not manual: raise HTTPException(400,"Manual ও Gateway দুটোই OFF।")
        bdt=amount
    gateway=""
    if method.lower()!="binance":
        cfg=core.get_payment_method_config(method,"deposit")
        gateway=cfg[3] if cfg and cfg[5] else ""
    sid,expires=core.create_payment_session(uid,bdt,method,gateway)
    payment_url=core.build_payment_url(gateway,bdt,uid,method,sid,sid) if gateway else ""
    manual_number=""
    if method.lower()!="binance":
        cfg=core.get_payment_method_config(method,"deposit")
        manual_number=cfg[2] if cfg and cfg[4] else ""
    return {"ok":True,"session_id":sid,"expires_at":expires,"amount_bdt":float(bdt),
            "method":method,"payment_url":payment_url,"manual_number":manual_number,
            "binance_address":core.BINANCE_DEPOSIT_ADDRESS if method.lower()=="binance" else "",
            "usdt_rate":float(core.USDT_RATE_BDT)}


@app.post("/api/deposit/submit")
async def deposit_submit(body: DepositSubmit, x_telegram_init_data: str = Header(default="")):
    uid, tg, _=current_user(x_telegram_init_data); require_access(uid)
    txid=core.normalize_txid(body.txid)
    if len(txid)<3 or len(txid)>128 or not re.fullmatch(r"[a-z0-9._:/-]+",txid):
        raise HTTPException(400,"Transaction ID-এর format সঠিক নয়।")
    con=core.db(); cur=con.cursor(); cur.execute("BEGIN IMMEDIATE")
    try:
        sess=cur.execute("""
            SELECT id,user_id,amount,payment_method,status,expires_at
            FROM payment_sessions WHERE session_id=?
        """,(body.session_id,)).fetchone()
        if not sess or int(sess[1])!=uid or sess[4]!="ACTIVE":
            raise ValueError("এই Deposit Session বর্তমানে উপলব্ধ নেই।")
        if datetime.now(timezone.utc)>=core.utc_dt(sess[5]):
            cur.execute("UPDATE payment_sessions SET status='EXPIRED' WHERE session_id=? AND status='ACTIVE'",(body.session_id,))
            con.commit(); raise ValueError("এই Session-এর মেয়াদ শেষ হয়ে গেছে।")
        if cur.execute("SELECT id FROM deposits WHERE lower(trim(txid))=? LIMIT 1",(txid,)).fetchone():
            raise ValueError("এই Transaction ID ইতিমধ্যে ব্যবহার করা হয়েছে।")
        created=core.now_iso()
        cur.execute("""
            INSERT INTO deposits(user_id,method,amount,txid,order_no,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
        """,(uid,sess[3],sess[2],txid,body.session_id,"Pending",created,created))
        cur.execute("""
            UPDATE payment_sessions SET status='PENDING',transaction_id=?,submitted_at=?
            WHERE session_id=? AND status='ACTIVE'
        """,(txid,created,body.session_id))
        if cur.rowcount!=1: raise ValueError("Session closed.")
        con.commit()
    except sqlite3.IntegrityError:
        con.rollback(); con.close(); raise HTTPException(400,"এই Transaction ID ইতিমধ্যে ব্যবহার করা হয়েছে।")
    except ValueError as e:
        con.rollback(); con.close(); raise HTTPException(400,str(e))
    finally:
        try: con.close()
        except Exception: pass
    try:
        await core.send_admin_deposit(
            type("WebUser",(),{"username":tg.get("username",""),"full_name":(tg.get("first_name","") + (" "+tg.get("last_name","") if tg.get("last_name") else "")),"id":uid})(),
            sess[3], Decimal(str(sess[2])), txid, body.session_id
        )
    except Exception:
        pass
    return {"ok":True,"message":"Transaction ID যাচাইয়ের জন্য পাঠানো হয়েছে।"}


@app.post("/api/deposit/cancel")
async def deposit_cancel(body: dict, x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    sid=str(body.get("session_id",""))
    con=core.db(); cur=con.cursor(); cur.execute("BEGIN IMMEDIATE")
    row=cur.execute("SELECT user_id,status FROM payment_sessions WHERE session_id=?",(sid,)).fetchone()
    if not row or int(row[0])!=uid:
        con.rollback(); con.close(); raise HTTPException(400,"Invalid session.")
    changed=cur.execute("UPDATE payment_sessions SET status='CANCELLED' WHERE session_id=? AND status='ACTIVE'",(sid,)).rowcount==1
    if changed: con.commit()
    else: con.rollback()
    con.close()
    if not changed: raise HTTPException(400,"এই Session বর্তমানে উপলব্ধ নেই।")
    return {"ok":True,"message":"Deposit Session বাতিল করা হয়েছে।"}


@app.post("/api/withdraw")
async def withdraw(body: WithdrawBody, x_telegram_init_data: str = Header(default="")):
    uid,tg,_=current_user(x_telegram_init_data); require_access(uid)
    if core.getset("withdraw_enabled")!="1": raise HTTPException(400,"Withdraw System বন্ধ আছে।")
    if not re.fullmatch(r"01[3-9]\d{8}", body.account.strip()):
        raise HTTPException(400,"সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন।")
    try: amount=Decimal(body.amount.strip())
    except (InvalidOperation,ValueError): raise HTTPException(400,"সঠিক amount দিন।")
    mn=Decimal(core.getset("min_wth","100")); mx=Decimal(core.getset("max_wth","25000"))
    con=core.db(); cur=con.cursor(); cur.execute("BEGIN IMMEDIATE")
    try:
        cfg=cur.execute("SELECT 1 FROM payment_methods WHERE name=? AND kind='withdraw' AND enabled=1",(body.method,)).fetchone()
        if not cfg: raise ValueError("এই Withdraw Method বন্ধ আছে।")
        if amount<mn or amount>mx: raise ValueError(f"Withdraw {core.money(mn)}৳ থেকে {core.money(mx)}৳ এর মধ্যে হতে হবে।")
        changed=cur.execute(
            "UPDATE users SET main_balance=main_balance-? WHERE user_id=? AND main_balance>=?",
            (float(amount),uid,float(amount))
        ).rowcount
        if changed!=1: raise ValueError("পর্যাপ্ত main balance নেই।")
        now=core.now_iso()
        wid=cur.execute("""
            INSERT INTO withdrawals(user_id,method,account,amount,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?)
        """,(uid,body.method,body.account.strip(),float(amount),"Pending",now,now)).lastrowid
        con.commit()
    except Exception as e:
        con.rollback(); con.close(); raise HTTPException(400,str(e))
    con.close()
    try:
        await core.send_history_event("WITHDRAW_REQUEST",actor_id=uid,user_id=uid,reference=str(wid),
            details=f"Method: {body.method}; Account: {body.account.strip()}; Amount: {core.money(amount)}৳")
        web_user=type("WebUser",(),{"username":tg.get("username",""),"full_name":(tg.get("first_name","") + (" "+tg.get("last_name","") if tg.get("last_name") else "")),"id":uid})()
        await core.send_admin_withdraw(web_user,wid,body.method,body.account.strip(),amount)
    except Exception:
        pass
    return {"ok":True,"message":"Withdraw request সফলভাবে জমা হয়েছে।","user":user_json(uid)}


@app.get("/api/earnings")
async def earnings_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    core.expire_user_plans(uid)
    con=core.db()
    rows=con.execute("""
        SELECT id,plan,amount,activated_at,expires_at,last_claim_date,
               COALESCE(daily_rate,?)
        FROM plans WHERE user_id=? AND active=1 ORDER BY id DESC
    """,(float(core.DEMO_DAILY_RATE),uid)).fetchall()
    con.close()
    now=datetime.now(timezone.utc)
    out=[]
    for p in rows:
        exp=core.utc_dt(p[4])
        if exp<=now: continue
        daily=Decimal(str(p[2]))*Decimal(str(p[6]))
        out.append({"id":p[0],"plan":p[1],"amount":float(p[2]),"daily":float(daily),
                    "expires_at":p[4],"last_claim_date":p[5]})
    return {"plans":out,"claim_window":"08:00–24:00 UTC"}


@app.post("/api/earnings/claim")
async def earnings_claim(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    now=datetime.now(timezone.utc)
    if now.hour<8: raise HTTPException(400,"Claim window সকাল ৮টা থেকে শুরু হবে।")
    today=now.date().isoformat()
    con=core.db(); cur=con.cursor(); cur.execute("BEGIN IMMEDIATE")
    try:
        cur.execute("UPDATE plans SET active=0 WHERE user_id=? AND active=1 AND expires_at<=?",(uid,core.now_iso()))
        rows=cur.execute("""
            SELECT id,plan,amount,last_claim_date,expires_at,COALESCE(daily_rate,?)
            FROM plans WHERE user_id=? AND active=1
        """,(float(core.DEMO_DAILY_RATE),uid)).fetchall()
        total=Decimal("0"); count=0
        for pid,plan,amount,last_claim,expires,rate in rows:
            if core.utc_dt(expires)<=now or last_claim==today: continue
            earning=Decimal(str(amount))*Decimal(str(rate))
            changed=cur.execute("""
                UPDATE plans SET last_claim_date=?
                WHERE id=? AND active=1 AND (last_claim_date IS NULL OR last_claim_date<>?)
            """,(today,pid,today)).rowcount
            if changed!=1: continue
            total+=earning; count+=1
            cur.execute("INSERT INTO earnings(user_id,plan_id,amount,claim_date,created_at) VALUES(?,?,?,?,?)",
                        (uid,pid,float(earning),today,core.now_iso()))
        if total>0:
            cur.execute("UPDATE users SET main_balance=main_balance+?,total_earnings=total_earnings+? WHERE user_id=?",
                        (float(total),float(total),uid))
        con.commit()
    except Exception:
        con.rollback(); con.close(); raise
    con.close()
    if total<=0: raise HTTPException(400,"আজকের earnings claim করা হয়েছে অথবা কোনো active plan নেই।")
    return {"ok":True,"amount":float(total),"plans_claimed":count,"user":user_json(uid)}


@app.get("/api/bonus")
async def bonus_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    con=core.db()
    row=con.execute("SELECT bonus_balance FROM users WHERE user_id=?",(uid,)).fetchone()
    hist=con.execute("SELECT amount,type,created_at FROM bonuses WHERE user_id=? ORDER BY id DESC LIMIT 5",(uid,)).fetchall()
    con.close()
    return {"enabled":core.get_setting_bool("bonus_enabled",True),"balance":float(row[0] if row else 0),
            "amount":core.getset("bonus_amount","5"),"expiry_days":core.getset("bonus_expiry_days","1"),
            "history":[{"amount":float(x[0]),"type":x[1],"created_at":x[2]} for x in hist]}


@app.post("/api/bonus/claim")
async def bonus_claim_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    if not core.get_setting_bool("bonus_enabled",True): raise HTTPException(400,"Bonus বর্তমানে বন্ধ।")
    amount=Decimal(core.getset("bonus_amount","5") or "0")
    days=int(core.getset("bonus_expiry_days","1") or 1)
    if amount<=0: raise HTTPException(400,"কোনো Bonus চালু নেই।")
    con=core.db(); cur=con.cursor()
    old=cur.execute("""SELECT 1 FROM bonuses WHERE user_id=? AND type='daily'
                       AND datetime(created_at)>=datetime('now',?)""",(uid,f"-{days} day")).fetchone()
    if old:
        con.close(); raise HTTPException(400,"Bonus ইতিমধ্যে নেওয়া হয়েছে।")
    cur.execute("UPDATE users SET bonus_balance=bonus_balance+? WHERE user_id=?",(float(amount),uid))
    cur.execute("INSERT INTO bonuses(user_id,amount,type,created_at) VALUES(?,?,?,?)",(uid,float(amount),"daily",core.now_iso()))
    con.commit(); con.close()
    try:
        await core.send_history_event("BONUS_CLAIM",actor_id=uid,user_id=uid,reference=f"BONUS-{uid}",
            details=f"Daily bonus claimed: {core.money(amount)}৳")
    except Exception: pass
    return {"ok":True,"amount":float(amount),"user":user_json(uid)}


@app.get("/api/referral")
async def referral_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data)
    u=require_access(uid)
    try:
        me=await core.bot.get_me()
        bot_username=me.username or ""
    except Exception:
        bot_username=""
    link=f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else ""
    return {"link":link,"count":u["referral_count"],"balance":u["referral_balance"],
            "enabled":core.get_setting_bool("referral_enabled"),
            "bonus":core.getset("referral_bonus","0")}

@app.get("/api/history")
async def history_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    con=core.db()
    deps=con.execute("""SELECT method,amount,status,order_no,created_at FROM deposits
                        WHERE user_id=? ORDER BY id DESC LIMIT 7""",(uid,)).fetchall()
    wds=con.execute("""SELECT method,amount,status,created_at FROM withdrawals
                       WHERE user_id=? ORDER BY id DESC LIMIT 7""",(uid,)).fetchall()
    earns=con.execute("""SELECT amount,claim_date,created_at FROM earnings
                         WHERE user_id=? ORDER BY id DESC LIMIT 7""",(uid,)).fetchall()
    con.close()
    return {
        "deposits":[{"method":x[0],"amount":float(x[1]),"status":x[2],"order":x[3],"created_at":x[4]} for x in deps],
        "withdrawals":[{"method":x[0],"amount":float(x[1]),"status":x[2],"created_at":x[3]} for x in wds],
        "earnings":[{"amount":float(x[0]),"claim_date":x[1],"created_at":x[2]} for x in earns]
    }


@app.get("/api/help")
async def help_api(x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    return {"title":"🆘 Help & Support","categories":["Account Problem","Deposit Problem","Withdraw Problem","Referral Problem","Other Issues"],
            "support":"@Nikan_Support01","channel":"https://t.me/NIKAN_EARN",
            "rules":"🌐 About NIKAN\n\nNIKAN একটি online earning service demo interface."}


@app.get("/api/command/{command}")
async def command_api(command: str, x_telegram_init_data: str = Header(default="")):
    uid,_,_=current_user(x_telegram_init_data); require_access(uid)
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,32}",command):
        raise HTTPException(400,"Invalid command.")
    con=core.db()
    row=con.execute("SELECT title,message_key,enabled FROM bot_commands WHERE command=?",(command.lower(),)).fetchone()
    con.close()
    if not row or not row[2]:
        raise HTTPException(404,"Command not found.")
    return {"command":command.lower(),"title":row[0],"message":row[1] or ""}
