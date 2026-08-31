# -*- coding: utf-8 -*-
import requests
import json
import time
import os
import sys
import urllib.parse
import uuid
import random
import threading
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console
from flask import Flask, request
from threading import Thread

# ============================================================
#  ATF MINERS AUTO BOT (3-COLUMN DASHBOARD VERSION)
# ============================================================

BASE_URL   = "https://atfminers.asloni.online/miner/index.php"
QUERY_FILE = os.path.join(os.path.dirname(__file__), "query.txt")

HEADERS_TEMPLATE = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "origin": "https://atfminers.asloni.online",
    "referer": "https://atfminers.asloni.online/",
    "sec-ch-ua": '"Not=A?Brand";v="99", "Brave";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    ),
}

# ============================================================
#  TELEGRAM BOT CONFIGURATION
# ============================================================
TELEGRAM_BOT_TOKEN = "8411649204:AAGPnQhIMKKB1rhfoSgGz2ZBtBokNZX1eH4"  # Replace with your bot token
TELEGRAM_CHAT_ID = "-1003628097142"      # Replace with your chat ID
TELEGRAM_ENABLED = True                     # Set to False to disable Telegram notifications

ACCOUNTS = []
PROXIES_LIST = []
lock = threading.Lock()
last_telegram_update = {}  # Track last update time per account to avoid spam

# Flask app for webhook
app = Flask(__name__)

def send_telegram_message(message, parse_mode="HTML", reply_to=None):
    """Send message to Telegram bot"""
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode
        }
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False

def get_status_message():
    """Generate comprehensive status report for all accounts"""
    with lock:
        if not ACCOUNTS:
            return "❌ No accounts loaded"
        
        msg = "📊 <b>ATF MINERS STATUS REPORT</b>\n"
        msg += "═" * 30 + "\n\n"
        
        total_balance = 0.0
        
        for i, acc in enumerate(ACCOUNTS, 1):
            msg += f"<b>👤 Account {i}: {acc['username']}</b>\n"
            
            # Balance
            balance = float(acc.get('balance', '0.0'))
            total_balance += balance
            msg += f"  💰 <b>Balance:</b> {balance:.4f} ATF\n"
            
            # Mining Status
            mining_status = acc.get('mining_status', 'Unknown')
            mining_end = acc.get('mining_end', 0)
            mining_time = format_time_remaining(mining_end)
            
            if "Mining" in mining_status:
                msg += f"  ⛏️ <b>Mining:</b> Active (Next claim in {mining_time})\n"
            elif "Error" in mining_status:
                msg += f"  ⛏️ <b>Mining:</b> ❌ {mining_status}\n"
            else:
                msg += f"  ⛏️ <b>Mining:</b> {mining_status}\n"
            
            # Boost Status
            boost_status = acc.get('boost_status', 'Unknown')
            boost_end = acc.get('boost_end', 0)
            boost_time = format_time_remaining(boost_end)
            
            if "Tap" in boost_status or "+" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> Active (Next in {boost_time})\n"
            elif "Busy" in boost_status or "Cooldown" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> ⏳ {boost_status} ({boost_time})\n"
            else:
                msg += f"  🚀 <b>Auto-Tap:</b> {boost_status}\n"
            
            # Task Status
            task_status = acc.get('task_status', 'Unknown')
            task_end = acc.get('task_end', 0)
            task_time = format_time_remaining(task_end)
            
            if "Done" in task_status:
                msg += f"  📋 <b>Tasks:</b> ✅ {task_status}\n"
            else:
                msg += f"  📋 <b>Tasks:</b> {task_status} ({task_time})\n"
            
            # Proxy info
            if acc.get('proxy'):
                msg += f"  🔗 <b>Proxy:</b> {acc['proxy'][:30]}...\n"
            
            msg += "\n"
        
        # Summary
        msg += "═" * 30 + "\n"
        msg += f"<b>📈 Summary:</b>\n"
        msg += f"  👥 Total Accounts: {len(ACCOUNTS)}\n"
        msg += f"  💰 Total Balance: {total_balance:.4f} ATF\n"
        msg += f"  🕐 Last Update: {time.strftime('%H:%M:%S')}"
        
        return msg

def format_time_remaining(end_time):
    if end_time <= 0: return "Ready"
    sisa = end_time - time.time()
    if sisa <= 0: return "Ready"
    m, s = divmod(int(sisa), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def parse_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str: return None
    
    # Jika sudah menggunakan skema (http://, socks5://, dll)
    if "://" in proxy_str:
        return proxy_str
        
    # Jika format ip:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        ip, port, user, pw = parts
        return f"http://{user}:{pw}@{ip}:{port}"
    # Jika format user:pass@ip:port
    elif "@" in proxy_str:
        return f"http://{proxy_str}"
    # Jika format ip:port
    elif len(parts) == 2:
        ip, port = parts
        return f"http://{ip}:{port}"
        
    return f"http://{proxy_str}"

def generate_layout():
    with lock:
        layout = Layout()
        layout.split_row(
            Layout(name="mining", ratio=1),
            Layout(name="boost", ratio=1),
            Layout(name="tasks", ratio=1)
        )
        
        # Kolom Mining
        table_mining = Table(expand=True, show_edge=False)
        table_mining.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_mining.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_mining.add_column("Mining", style="magenta", no_wrap=True, overflow="ellipsis")
        
        # Kolom Boost
        table_boost = Table(expand=True, show_edge=False)
        table_boost.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_boost.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_boost.add_column("Boost", style="red", no_wrap=True, overflow="ellipsis")
        
        # Kolom Tasks
        table_tasks = Table(expand=True, show_edge=False)
        table_tasks.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_tasks.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_tasks.add_column("Task", style="green", no_wrap=True, overflow="ellipsis")
        
        for acc in ACCOUNTS:
            rm = format_time_remaining(acc["mining_end"])
            rb = format_time_remaining(acc["boost_end"])
            rt = format_time_remaining(acc["task_end"])
            
            table_mining.add_row(
                acc["username"], 
                rm, 
                acc["mining_status"]
            )
            
            table_boost.add_row(
                acc["username"], 
                rb, 
                acc["boost_status"]
            )
            
            table_tasks.add_row(
                acc["username"], 
                rt, 
                acc["task_status"]
            )
        
        layout["mining"].update(Panel(table_mining, title="[bold cyan]MONITORING MINING[/]"))
        layout["boost"].update(Panel(table_boost, title="[bold red]MONITORING AUTO-TAP[/]"))
        layout["tasks"].update(Panel(table_tasks, title="[bold green]MONITORING TASKS[/]"))
        return layout

def api(session: requests.Session, action: str, acc: dict, extra: dict = None, retries: int = 3):
    url = f"{BASE_URL}?action={action}&t={int(time.time() * 1000)}"
    payload = {"initData": acc["query"]}
    if extra: payload.update(extra)

    for attempt in range(1, retries + 1):
        try:
            r = session.post(url, json=payload, timeout=30)
            r.raise_for_status()
            try: return r.json()
            except: return {"raw": r.text}
        except requests.exceptions.HTTPError as e:
            try: return r.json()
            except: pass
            if attempt < retries: time.sleep(3)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ProxyError) as e:
            if PROXIES_LIST:
                new_p = random.choice(PROXIES_LIST)
                acc["proxy"] = new_p
                session.proxies.update({"http": new_p, "https": new_p})
                with lock: 
                    acc["mining_status"] = "Proxy Error, Rotating..."
            if attempt < retries: time.sleep(5 * attempt)
            else: return None
        except requests.RequestException as e:
            if attempt < retries: time.sleep(5 * attempt)
            else: return None
    return None

def extract_balance(d):
    if not isinstance(d, dict): return None
    for k in ["mined_balance", "balance", "atf", "amount"]:
        if k in d: return d[k]
        if "user" in d and k in d["user"]: return d["user"][k]
        if "data" in d and isinstance(d["data"], dict) and k in d["data"]: return d["data"][k]
    return None

def parse_username(init_data: str) -> str:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        user = json.loads(urllib.parse.unquote(parsed.get("user", "{}")))
        return user.get("username") or user.get("first_name") or "Account"
    except:
        return "Account"

def send_status_update(acc, status_type, message, send_always=False):
    """Send status update with rate limiting (max once per 30 seconds per account per type)"""
    if not TELEGRAM_ENABLED:
        return
    
    key = f"{acc['username']}_{status_type}"
    current_time = time.time()
    
    # Rate limit: only send if 30 seconds have passed or send_always is True
    if not send_always and key in last_telegram_update:
        if current_time - last_telegram_update[key] < 30:
            return
    
    last_telegram_update[key] = current_time
    
    # Format message
    msg = f"<b>🔄 {status_type.upper()} Update</b>\n"
    msg += f"<b>Account:</b> {acc['username']}\n"
    msg += f"<b>Status:</b> {message}\n"
    msg += f"<b>Balance:</b> {acc.get('balance', '0.0')} ATF\n"
    msg += f"<b>Time:</b> {time.strftime('%H:%M:%S')}"
    
    send_telegram_message(msg)

def process_mining(acc):
    with lock: 
        acc["mining_status"] = "Logging in..."
        send_status_update(acc, "mining", "Logging in...")
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
        
    login_res = api(sess, "login", acc)
    if not login_res:
        with lock: 
            acc["mining_status"] = "Login Failed (Retrying)"
            send_status_update(acc, "mining", "❌ Login Failed, retrying...")
        acc["mining_end"] = time.time() + 2
        return
        
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: sess.headers.update({"Authorization": f"Bearer {token}"})
    
    bal = extract_balance(login_res)
    if bal is not None:
        with lock: 
            acc["balance"] = str(bal)
            send_status_update(acc, "balance", f"💰 Balance updated: {bal} ATF", send_always=True)
        
    user_data = login_res.get("user", {})
    if not user_data and "data" in login_res:
        user_data = login_res["data"].get("user", {})
        
    started_at_str = user_data.get("mining_cycle_started_at") or user_data.get("last_mining_start") or 0
    
    try:
        started_at = float(started_at_str)
    except:
        started_at = 0.0
        
    wait_secs = 3600.0
    now = time.time()
    
    # Mining cycle is exactly 1 hour
    if started_at > 0:
        sisa = (started_at + 3600.0) - now
        if sisa > 0:
            wait_secs = sisa
            can_claim = False
        else:
            can_claim = True
            wait_secs = 0.0
    else:
        can_claim = True
        wait_secs = 0.0
            
    if can_claim:
        with lock: 
            acc["mining_status"] = "Claiming Reward..."
            send_status_update(acc, "mining", "🔄 Claiming mining reward...")
        claim_res = api(sess, "claim", acc)
        time.sleep(2)
        
        with lock: 
            acc["mining_status"] = "Solving Captcha..."
            send_status_update(acc, "mining", "🧩 Solving captcha...")
        tg_id = user_data.get("tg_id", "")
        if not tg_id:
            try:
                parsed = dict(urllib.parse.parse_qsl(acc["query"]))
                user_str = parsed.get("user", "{}")
                tg_id = json.loads(urllib.parse.unquote(user_str)).get("id", "")
            except: pass
            
        cr = api(sess, "get_math_challenge", acc, extra={'tg_id': tg_id, 'scope': 'start_mine'})
        start_payload = {'tg_id': tg_id, 'request_id': str(uuid.uuid4())}
        
        if cr and cr.get("status") == "success":
            try:
                cid = cr['challenge_id']
                q_str = cr['question'].replace('=', '').replace('?', '').strip()
                ans = str(eval(q_str))
                start_payload['math_challenge_id'] = cid
                start_payload['math_answer'] = ans
            except: pass
        
        with lock: 
            acc["mining_status"] = "Starting New Mining..."
            send_status_update(acc, "mining", "⛏️ Starting new mining cycle...")
        start_res = api(sess, "start_mine", acc, extra=start_payload)
        
        has_error = False
        error_msg = ""
        
        if start_res:
            if start_res.get("status") == "success":
                wait_secs = 3600.0
                with lock:
                    send_status_update(acc, "mining", "✅ Mining started successfully! Next claim in 1 hour")
            else:
                has_error = True
                error_msg = start_res.get("message", start_res.get("reason", "Gagal Start"))
                wait_secs = 60.0
                with lock:
                    send_status_update(acc, "mining", f"❌ Mining failed: {error_msg}")
        else:
            has_error = True
            error_msg = "Gagal HTTP Start"
            wait_secs = 60.0
            with lock:
                send_status_update(acc, "mining", f"❌ HTTP error starting mining")
            
    with lock: 
        if can_claim and has_error:
            acc["mining_status"] = f"Error: {error_msg}"
        else:
            acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
        acc["mining_end"] = time.time() + max(wait_secs, 60.0)
    sess.close()

def process_boost(acc):
    with lock: 
        acc["boost_status"] = "Starting Tap..."
        send_status_update(acc, "boost", "🔄 Starting auto-tap...")
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
        
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock:
            acc["boost_status"] = "Login Failed"
            acc["boost_end"] = time.time() + 5.0
            send_status_update(acc, "boost", "❌ Login failed")
        sess.close()
        return
        
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: sess.headers.update({"Authorization": f"Bearer {token}"})
        
    parsed = dict(urllib.parse.parse_qsl(acc["query"]))
    user_str = parsed.get("user", "{}")
    try:
        user_data = json.loads(urllib.parse.unquote(user_str))
        tg_id = user_data.get("id", "")
    except:
        tg_id = ""

    payload = {
        "tg_id": tg_id,
        "request_id": str(uuid.uuid4()),
        "display_preview": round(random.uniform(0.24, 0.35), 4)
    }
    
    br = api(sess, "activate_boost", acc, extra=payload, retries=1)
    wait_time = 10.0
    status_msg = "Tap Success!"
    
    if br:
        if br.get("status") == "success":
            wait_time = 10.0
            pending = br.get("pending_reward", 0)
            status_msg = f"+{pending} ATF"
            with lock:
                send_status_update(acc, "boost", f"✅ Tap successful! +{pending} ATF")
            
            ready_at = br.get("boost_ready_at", 0)
            if ready_at:
                sisa = ready_at - time.time()
                if sisa > 0: wait_time = sisa
        elif br.get("status") == "busy":
            status_msg = "Busy (Cooldown)"
            wait_time = 2.0
            with lock:
                send_status_update(acc, "boost", "⏳ Busy, cooldown active")
        elif br.get("status") == "cooldown":
            status_msg = "Sistem Cooldown"
            ready_at = br.get("boost_ready_at", 0)
            if ready_at:
                sisa = ready_at - time.time()
                if sisa > 0: wait_time = sisa
            with lock:
                send_status_update(acc, "boost", f"⏳ Cooldown, ready in {int(wait_time)}s")
    else:
        status_msg = "HTTP Failed"
        wait_time = 5.0
        with lock:
            send_status_update(acc, "boost", "❌ HTTP request failed")
        
    with lock:
        acc["boost_status"] = status_msg
        acc["boost_end"] = time.time() + max(wait_time, 2.0)
    sess.close()

def process_tasks(acc):
    with lock: 
        acc["task_status"] = "Preparing Tasks..."
        send_status_update(acc, "tasks", "🔄 Preparing to check tasks...")
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    # Login to get valid token
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock: 
            acc["task_status"] = "Login failed, retrying..."
            send_status_update(acc, "tasks", "❌ Login failed")
        acc["task_end"] = time.time() + 2
        return
        
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: sess.headers.update({"Authorization": f"Bearer {token}"})
    
    parsed = dict(urllib.parse.parse_qsl(acc["query"]))
    user_str = parsed.get("user", "{}")
    try:
        user_data = json.loads(urllib.parse.unquote(user_str))
        tg_id = user_data.get("id", "")
    except:
        tg_id = ""
        
    if not tg_id:
        with lock: 
            acc["task_status"] = "Failed parsing TG ID"
            send_status_update(acc, "tasks", "❌ Failed to parse Telegram ID")
        acc["task_end"] = time.time() + 60.0
        return
        
    completed_tasks = user_data.get("completed_tasks", [])
    if isinstance(completed_tasks, str):
        try: completed_tasks = json.loads(completed_tasks)
        except: completed_tasks = []
        
    task_ids = [
        'telegram_join', 'telegram_channel', 'twitter_follow', 
        'youtube_subscribe', 'youtube_like_comment', 'twitter_retweet',
        'website_visit', 'telegram_join_fa', 'telegram_react_latest'
    ]
    
    start_count = 0
    claimed_tasks = []
    
    for tid in task_ids:
        if tid in completed_tasks:
            continue
            
        with lock: 
            acc["task_status"] = f"Start: {tid}"
            send_status_update(acc, "tasks", f"🔄 Starting task: {tid}")
        sr = api(sess, "start_task", acc, extra={"tg_id": tg_id, "task_id": tid}, retries=1)
        
        # Selalu coba claim, baik start-nya success maupun sudah pernah di-start (cooldown)
        with lock: 
            acc["task_status"] = f"Claim: {tid}"
            send_status_update(acc, "tasks", f"🔄 Claiming task: {tid}")
        cr = api(sess, "claim_task", acc, extra={
            "tg_id": tg_id, 
            "task_id": tid, 
            "client_started_at": int(time.time()),
            "request_id": str(uuid.uuid4())
        }, retries=1)
        
        if cr and cr.get("status") == "success":
            start_count += 1
            completed_tasks.append(tid)
            claimed_tasks.append(tid)
            with lock:
                send_status_update(acc, "tasks", f"✅ Task completed: {tid}")
            
        time.sleep(1)
            
    with lock:
        acc["task_status"] = f"Done (+{start_count} Claimed)"
        acc["task_end"] = time.time() + 60.0
        if start_count > 0:
            send_status_update(acc, "tasks", f"✅ Completed {start_count} tasks: {', '.join(claimed_tasks)}", send_always=True)

def worker_thread(acc):
    time.sleep(random.uniform(0.5, 5.0)) # Stagger thread starts
    
    # Send initial status
    with lock:
        send_status_update(acc, "start", "🚀 Bot started successfully!", send_always=True)
    
    while True:
        now = time.time()
        
        # 1. Prioritaskan Mining
        if now >= acc["mining_end"]:
            process_mining(acc)
            continue # Kembali ke awal loop
        
        # 2. Prioritaskan Boost
        if now >= acc["boost_end"]:
            process_boost(acc)
            continue
            
        # 3. Terakhir Task
        if now >= acc["task_end"]:
            process_tasks(acc)
            continue
            
        time.sleep(1.0)

# ============================================================
#  TELEGRAM WEBHOOK / STATUS COMMAND HANDLER
# ============================================================

@app.route('/', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates"""
    try:
        update = request.get_json()
        
        if not update or 'message' not in update:
            return 'OK', 200
        
        message = update['message']
        
        # Check if it's a command
        if 'text' not in message:
            return 'OK', 200
        
        text = message['text'].strip()
        chat_id = message['chat']['id']
        
        # Only respond to our chat ID
        if str(chat_id) != str(TELEGRAM_CHAT_ID):
            return 'OK', 200
        
        # Handle /status command
        if text.lower() == '/status':
            status_msg = get_status_message()
            send_telegram_message(status_msg)
        
        # Handle /help command
        elif text.lower() == '/help':
            help_msg = """<b>🤖 ATF Miners Bot Commands:</b>

/status - Show real-time mining status for all accounts
/help - Show this help message

<b>Bot Features:</b>
• Automatic mining every hour
• Auto-tap every 10 seconds
• Automatic task completion
• Real-time balance updates
• Proxy support for multiple accounts

<b>Status Indicators:</b>
⛏️ Mining status
🚀 Auto-tap status
📋 Task status
💰 Balance information
🕐 Time until next action"""
            send_telegram_message(help_msg)
        
        # Handle /start command
        elif text.lower() == '/start':
            start_msg = """🚀 <b>ATF Miners Bot is Running!</b>

Use /status to check real-time mining status
Use /help for available commands

Bot is automatically mining, tapping, and completing tasks for your accounts."""
            send_telegram_message(start_msg)
            
    except Exception as e:
        print(f"Webhook error: {e}")
    
    return 'OK', 200

def run_flask():
    """Run Flask webhook server"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def set_webhook():
    """Set the webhook URL for Telegram bot"""
    if not TELEGRAM_ENABLED or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return
    
    # You need to set this to your public URL
    # For local testing, use ngrok: https://ngrok.com/
    webhook_url = "YOUR_PUBLIC_URL_HERE"  # e.g., "https://your-domain.com"
    
    if webhook_url == "YOUR_PUBLIC_URL_HERE":
        print("⚠️  Webhook URL not configured. /status command will use polling instead.")
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
        response = requests.post(url, json={"url": webhook_url})
        if response.status_code == 200:
            print(f"✅ Webhook set to: {webhook_url}")
        else:
            print(f"❌ Failed to set webhook: {response.text}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 ATF Miners Bot")
    print("=" * 50)
    
    # Check Telegram configuration
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or TELEGRAM_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("⚠️  Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        print("   Status updates will only be shown in the terminal dashboard")
    elif TELEGRAM_ENABLED:
        print(f"✅ Telegram bot enabled! Chat ID: {TELEGRAM_CHAT_ID}")
        print("   Send /status to check real-time mining info")
        # Send startup message
        send_telegram_message("🚀 <b>ATF Miners Bot Started!</b>\n\nBot is now running and monitoring your accounts.\nSend /status to check real-time mining info.")
    
    print("=" * 50)
    
    use_proxy = input("Use proxies from proxies.txt? (y/n): ").strip().lower()
    proxies_list = []
    
    if use_proxy == 'y':
        if os.path.exists("proxies.txt"):
            with open("proxies.txt", "r", encoding="utf-8") as f:
                for line in f:
                    p = parse_proxy(line)
                    if p: 
                        proxies_list.append(p)
                        PROXIES_LIST.append(p)
            print(f"[+] Found {len(proxies_list)} proxies.")
        else:
            print("[-] File proxies.txt tidak ditemukan, berjalan tanpa proxies.")
            time.sleep(2)
            
    with open("query.txt", "r", encoding="utf-8") as f:
        queries = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    
    for i, q in enumerate(queries):
        proxy = proxies_list[i % len(proxies_list)] if proxies_list else None
        
        ACCOUNTS.append({
            "query": q,
            "proxy": proxy,
            "username": parse_username(q),
            "balance": "0.0",
            "mining_status": "Waiting...",
            "mining_end": 0,
            "task_status": "Waiting...",
            "task_end": 0,
            "boost_status": "Waiting...",
            "boost_end": 0
        })
        
    if not ACCOUNTS:
        print("query.txt kosong!")
        sys.exit(1)

    # Send account info to Telegram
    if TELEGRAM_ENABLED:
        account_list = "\n".join([f"• {acc['username']}" for acc in ACCOUNTS])
        msg = f"📊 <b>Loaded {len(ACCOUNTS)} account(s):</b>\n{account_list}"
        send_telegram_message(msg)

    # Kosongkan layar sebelum menjalankan UI Live
    os.system("cls" if os.name == "nt" else "clear")

    # Start Flask webhook server in a separate thread
    if TELEGRAM_ENABLED:
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("📡 Telegram webhook server running on port 5000")

    # Start worker per account
    for acc in ACCOUNTS:
        t = threading.Thread(target=worker_thread, args=(acc,), daemon=True)
        t.start()

    # Start UI
    try:
        with Live(generate_layout(), refresh_per_second=2) as live:
            while True:
                live.update(generate_layout())
                time.sleep(0.5)
    except KeyboardInterrupt:
        if TELEGRAM_ENABLED:
            send_telegram_message("🛑 <b>Bot Stopped</b>\nBot has been stopped by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
