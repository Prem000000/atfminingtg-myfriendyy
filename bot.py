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

# ============================================================
#  ATF MINERS AUTO BOT (FIXED TAPPING)
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
TELEGRAM_ENABLED = True

ACCOUNTS = []
PROXIES_LIST = []
lock = threading.Lock()
last_update_id = 0
authorized_chat_id = None

# ============================================================
#  PRODUCTION MODE
# ============================================================
def is_production():
    if not sys.stdin.isatty():
        return True
    if os.environ.get('DYNO') or os.environ.get('RAILWAY_ENVIRONMENT'):
        return True
    if os.environ.get('KUBERNETES_SERVICE_HOST') or os.environ.get('DOCKER'):
        return True
    return False

PRODUCTION_MODE = is_production()

def send_telegram_message(message, parse_mode="HTML"):
    global authorized_chat_id
    
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return False
    
    if not authorized_chat_id:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": authorized_chat_id,
            "text": message,
            "parse_mode": parse_mode
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False

def get_status_message():
    with lock:
        if not ACCOUNTS:
            return "❌ No accounts loaded"
        
        msg = "📊 <b>ATF MINERS STATUS REPORT</b>\n"
        msg += "═" * 30 + "\n\n"
        
        total_balance = 0.0
        mining_active = 0
        tap_active = 0
        
        for i, acc in enumerate(ACCOUNTS, 1):
            msg += f"<b>👤 Account {i}: {acc['username']}</b>\n"
            
            balance = float(acc.get('balance', '0.0'))
            total_balance += balance
            msg += f"  💰 <b>Balance:</b> <code>{balance:.6f}</code> ATF\n"
            
            mining_status = acc.get('mining_status', 'Unknown')
            mining_end = acc.get('mining_end', 0)
            mining_time = format_time_remaining(mining_end)
            
            if "Mining" in mining_status:
                msg += f"  ⛏️ <b>Mining:</b> ✅ Active (Next claim in <code>{mining_time}</code>)\n"
                mining_active += 1
            elif "Error" in mining_status:
                msg += f"  ⛏️ <b>Mining:</b> ❌ {mining_status}\n"
            else:
                msg += f"  ⛏️ <b>Mining:</b> {mining_status}\n"
            
            boost_status = acc.get('boost_status', 'Unknown')
            boost_end = acc.get('boost_end', 0)
            boost_time = format_time_remaining(boost_end)
            
            if "✅" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> ✅ Success ({acc.get('real_taps', 0)} real taps)\n"
                tap_active += 1
            elif "❌" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> ❌ {boost_status}\n"
            else:
                msg += f"  🚀 <b>Auto-Tap:</b> {boost_status}\n"
            
            task_status = acc.get('task_status', 'Unknown')
            task_end = acc.get('task_end', 0)
            task_time = format_time_remaining(task_end)
            
            if "Done" in task_status:
                msg += f"  📋 <b>Tasks:</b> ✅ {task_status}\n"
            else:
                msg += f"  📋 <b>Tasks:</b> {task_status}\n"
            
            msg += "\n"
        
        msg += "═" * 30 + "\n"
        msg += f"<b>📈 SUMMARY</b>\n"
        msg += f"  👥 Total Accounts: <b>{len(ACCOUNTS)}</b>\n"
        msg += f"  ⛏️ Mining Active: <b>{mining_active}</b>\n"
        msg += f"  🚀 Auto-Tap Active: <b>{tap_active}</b>\n"
        msg += f"  💰 Total Balance: <b>{total_balance:.6f}</b> ATF\n"
        msg += f"  🕐 Last Update: <code>{time.strftime('%H:%M:%S')}</code>"
        
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
    
    if "://" in proxy_str:
        return proxy_str
        
    parts = proxy_str.split(":")
    if len(parts) == 4:
        ip, port, user, pw = parts
        return f"http://{user}:{pw}@{ip}:{port}"
    elif "@" in proxy_str:
        return f"http://{proxy_str}"
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
        
        table_mining = Table(expand=True, show_edge=False)
        table_mining.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_mining.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_mining.add_column("Mining", style="magenta", no_wrap=True, overflow="ellipsis")
        
        table_boost = Table(expand=True, show_edge=False)
        table_boost.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_boost.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_boost.add_column("Boost", style="red", no_wrap=True, overflow="ellipsis")
        
        table_tasks = Table(expand=True, show_edge=False)
        table_tasks.add_column("Account", style="cyan", width=10, no_wrap=True, overflow="ellipsis")
        table_tasks.add_column("Time", style="yellow", width=8, no_wrap=True)
        table_tasks.add_column("Task", style="green", no_wrap=True, overflow="ellipsis")
        
        for acc in ACCOUNTS:
            rm = format_time_remaining(acc["mining_end"])
            rb = format_time_remaining(acc["boost_end"])
            rt = format_time_remaining(acc["task_end"])
            
            table_mining.add_row(acc["username"], rm, acc["mining_status"])
            table_boost.add_row(acc["username"], rb, acc["boost_status"])
            table_tasks.add_row(acc["username"], rt, acc["task_status"])
        
        layout["mining"].update(Panel(table_mining, title="[bold cyan]MONITORING MINING[/]"))
        layout["boost"].update(Panel(table_boost, title="[bold red]MONITORING AUTO-TAP[/]"))
        layout["tasks"].update(Panel(table_tasks, title="[bold green]MONITORING TASKS[/]"))
        return layout

def api(session: requests.Session, action: str, acc: dict, extra: dict = None, retries: int = 2):
    url = f"{BASE_URL}?action={action}&t={int(time.time() * 1000)}"
    payload = {"initData": acc["query"]}
    if extra: payload.update(extra)

    for attempt in range(1, retries + 1):
        try:
            r = session.post(url, json=payload, timeout=10)
            r.raise_for_status()
            try: 
                return r.json()
            except: 
                return {"raw": r.text}
        except:
            if attempt < retries: 
                time.sleep(0.5)
            else: 
                return None
    return None

def extract_balance(d):
    if not isinstance(d, dict): 
        return None
    
    balance_paths = [
        "mined_balance",
        "balance", 
        "atf",
        "amount",
        "user.mined_balance",
        "user.balance",
        "data.mined_balance",
        "data.balance",
        "data.user.mined_balance",
        "data.user.balance"
    ]
    
    for path in balance_paths:
        parts = path.split('.')
        value = d
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break
        if value is not None:
            try:
                return float(value)
            except:
                return value
    
    return None

def parse_username(init_data: str) -> str:
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data))
        user = json.loads(urllib.parse.unquote(parsed.get("user", "{}")))
        return user.get("username") or user.get("first_name") or "Account"
    except:
        return "Account"

def get_tg_id(acc):
    try:
        parsed = dict(urllib.parse.parse_qsl(acc["query"]))
        user_str = parsed.get("user", "{}")
        user_data = json.loads(urllib.parse.unquote(user_str))
        return user_data.get("id", "")
    except:
        return ""

def update_balance_from_response(acc, response):
    if not response:
        return False
    
    new_balance = extract_balance(response)
    
    if new_balance is not None:
        try:
            with lock:
                acc["balance"] = f"{float(new_balance):.6f}"
                return True
        except:
            pass
    
    return False

def process_mining_fast(acc):
    with lock: 
        acc["mining_status"] = "Mining..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    login_res = api(sess, "login", acc, retries=1)
    if not login_res or login_res.get('status') == 'error':
        with lock:
            acc["mining_status"] = "Login Error"
            acc["mining_end"] = time.time() + 60
        sess.close()
        return
    
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token:
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    update_balance_from_response(acc, login_res)
    
    tg_id = get_tg_id(acc)
    
    # Check if mining is already running
    user_data = login_res.get("user", {})
    if not user_data and "data" in login_res:
        user_data = login_res["data"].get("user", {})
    
    mining_start = user_data.get("mining_cycle_started_at") or user_data.get("last_mining_start") or 0
    try:
        mining_start = float(mining_start)
    except:
        mining_start = 0
    
    now = time.time()
    
    if mining_start > 0:
        mining_end = mining_start + 3600
        if now < mining_end:
            with lock:
                acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
                acc["mining_end"] = mining_end
            sess.close()
            return
    
    # Claim and restart
    claim_res = api(sess, "claim", acc, retries=1)
    time.sleep(0.3)
    
    challenge_res = api(sess, "get_math_challenge", acc, extra={'tg_id': tg_id, 'scope': 'start_mine'}, retries=1)
    start_payload = {'tg_id': tg_id, 'request_id': str(uuid.uuid4())}
    
    if challenge_res and challenge_res.get("status") == "success":
        try:
            cid = challenge_res['challenge_id']
            q_str = challenge_res['question'].replace('=', '').replace('?', '').strip()
            ans = str(eval(q_str))
            start_payload['math_challenge_id'] = cid
            start_payload['math_answer'] = ans
        except:
            pass
    
    start_res = api(sess, "start_mine", acc, extra=start_payload, retries=1)
    
    if start_res and start_res.get("status") == "success":
        update_balance_from_response(acc, start_res)
        with lock:
            acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
            acc["mining_end"] = time.time() + 3600
    else:
        with lock:
            acc["mining_status"] = "Mining Error"
            acc["mining_end"] = time.time() + 60
    
    sess.close()

def process_boost_fast(acc):
    """Real tapping - only counts successful taps"""
    with lock: 
        acc["boost_status"] = "Tapping..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    # Login
    login_res = api(sess, "login", acc, retries=1)
    if not login_res or login_res.get('status') == 'error':
        with lock:
            acc["boost_status"] = "❌ Login Failed"
            acc["boost_end"] = time.time() + 3
        sess.close()
        return
    
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token:
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    # Update balance
    update_balance_from_response(acc, login_res)
    
    tg_id = get_tg_id(acc)
    
    # Tap payload
    payload = {
        "tg_id": tg_id,
        "request_id": str(uuid.uuid4()),
        "display_preview": round(random.uniform(0.24, 0.35), 4)
    }
    
    # Execute tap
    boost_res = api(sess, "activate_boost", acc, extra=payload, retries=1)
    
    if boost_res:
        status = boost_res.get("status", "")
        
        if status == "success":
            pending = boost_res.get("pending_reward", 0)
            new_balance = extract_balance(boost_res)
            
            with lock:
                # Only count REAL successful taps
                if new_balance is not None:
                    acc["balance"] = f"{float(new_balance):.6f}"
                    acc["real_taps"] = acc.get("real_taps", 0) + 1
                    acc["boost_status"] = f"✅ +{pending} ATF"
                    
                    # Send real tap notification (every 5 successful taps)
                    if authorized_chat_id and acc.get("real_taps", 0) % 5 == 0:
                        send_telegram_message(
                            f"✅ <b>Real Tap Success!</b>\n"
                            f"Account: {acc['username']}\n"
                            f"+{pending} ATF\n"
                            f"Balance: {acc['balance']} ATF\n"
                            f"Total taps: {acc['real_taps']}"
                        )
                else:
                    acc["boost_status"] = f"✅ +{pending} ATF (balance not updated)"
            
            # Cooldown check
            ready_at = boost_res.get("boost_ready_at", 0)
            if ready_at:
                try:
                    wait_time = float(ready_at) - time.time()
                    wait_time = max(wait_time, 1)
                except:
                    wait_time = 2
            else:
                wait_time = 2
                
            with lock:
                acc["boost_end"] = time.time() + max(wait_time, 1)
        
        elif status == "cooldown":
            ready_at = boost_res.get("boost_ready_at", 0)
            if ready_at:
                try:
                    wait_time = float(ready_at) - time.time()
                    wait_time = max(wait_time, 0.5)
                except:
                    wait_time = 2
            else:
                wait_time = 2
                
            with lock:
                acc["boost_status"] = "⏳ Cooldown"
                acc["boost_end"] = time.time() + max(wait_time, 0.5)
        
        elif status == "busy":
            with lock:
                acc["boost_status"] = "⏳ Busy"
                acc["boost_end"] = time.time() + 1
        
        else:
            error_msg = boost_res.get("message", "Unknown")
            with lock:
                acc["boost_status"] = f"❌ {error_msg[:20]}"
                acc["boost_end"] = time.time() + 2
    else:
        with lock:
            acc["boost_status"] = "❌ HTTP Failed"
            acc["boost_end"] = time.time() + 2
    
    sess.close()

def process_tasks_fast(acc):
    with lock: 
        acc["task_status"] = "Tasks..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    login_res = api(sess, "login", acc, retries=1)
    if not login_res or login_res.get('status') == 'error':
        with lock:
            acc["task_status"] = "Login Error"
            acc["task_end"] = time.time() + 30
        sess.close()
        return
    
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token:
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    update_balance_from_response(acc, login_res)
    
    tg_id = get_tg_id(acc)
    if not tg_id:
        with lock:
            acc["task_status"] = "No TG ID"
            acc["task_end"] = time.time() + 60
        sess.close()
        return
    
    user_data = login_res.get("user", {})
    if not user_data and "data" in login_res:
        user_data = login_res["data"].get("user", {})
    
    completed_tasks = user_data.get("completed_tasks", [])
    if isinstance(completed_tasks, str):
        try: 
            completed_tasks = json.loads(completed_tasks)
        except: 
            completed_tasks = []
    
    task_ids = [
        'telegram_join', 'telegram_channel', 'twitter_follow', 
        'youtube_subscribe', 'youtube_like_comment', 'twitter_retweet',
        'website_visit', 'telegram_join_fa', 'telegram_react_latest'
    ]
    
    start_count = 0
    
    for tid in task_ids:
        if tid in completed_tasks:
            continue
        
        start_res = api(sess, "start_task", acc, extra={"tg_id": tg_id, "task_id": tid}, retries=1)
        time.sleep(0.2)
        
        claim_res = api(sess, "claim_task", acc, extra={
            "tg_id": tg_id, 
            "task_id": tid, 
            "client_started_at": int(time.time()),
            "request_id": str(uuid.uuid4())
        }, retries=1)
        
        if claim_res and claim_res.get("status") == "success":
            start_count += 1
            completed_tasks.append(tid)
            update_balance_from_response(acc, claim_res)
        
        time.sleep(0.3)
    
    with lock:
        acc["task_status"] = f"Done (+{start_count})"
        acc["task_end"] = time.time() + 60
    
    sess.close()

def worker_thread(acc):
    """Optimized worker with real tap tracking"""
    time.sleep(random.uniform(0.1, 1.0))
    
    with lock:
        acc["real_taps"] = 0
        acc["mining_end"] = time.time() + 5
        acc["boost_end"] = time.time() + 1
        acc["task_end"] = time.time() + 10
    
    while True:
        now = time.time()
        
        if now >= acc["mining_end"]:
            process_mining_fast(acc)
            continue
        
        if now >= acc["boost_end"]:
            process_boost_fast(acc)
            continue
        
        if now >= acc["task_end"]:
            process_tasks_fast(acc)
            continue
        
        time.sleep(0.1)

def handle_message(message):
    global authorized_chat_id
    
    if 'text' not in message:
        return
    
    text = message['text'].strip()
    chat_id = message['chat']['id']
    
    if not authorized_chat_id:
        authorized_chat_id = chat_id
        print(f"✅ Authorized chat ID: {authorized_chat_id}")
        send_telegram_message("🚀 <b>ATF Miners Bot Authorized!</b>\n\n✅ <b>Real Tapping Mode</b>\nOnly successful taps are counted!\n\nSend /status to check progress")
        return
    
    if chat_id != authorized_chat_id:
        return
    
    if text.lower() == '/status':
        status_msg = get_status_message()
        send_telegram_message(status_msg)
    
    elif text.lower() == '/help':
        help_msg = """<b>🤖 ATF Miners Bot</b>

/status - Show real-time mining status
/help - Show this help message

<b>✅ Features:</b>
• Real tapping (only successful)
• Accurate balance tracking
• Mining every hour
• Task completion

Taps are counted only when successful!"""
        send_telegram_message(help_msg)
    
    elif text.lower() == '/start':
        start_msg = f"""🚀 <b>ATF Miners Bot</b>

✅ <b>Status:</b> Running
👥 <b>Accounts:</b> {len(ACCOUNTS)} account(s)

✅ Real tapping - only successful taps counted
✅ Accurate balance tracking
✅ Auto-mining every hour
✅ Task completion

Send /status to check progress"""
        send_telegram_message(start_msg)

def polling_loop():
    global last_update_id
    print("📡 Started polling for Telegram commands...")
    print("✅ REAL TAP MODE - Only counting successful taps!")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {
                "timeout": 30,
                "offset": last_update_id + 1,
                "allowed_updates": ["message"]
            }
            response = requests.get(url, json=params, timeout=35)
            
            if response.status_code == 200:
                updates = response.json()
                for update in updates.get('result', []):
                    last_update_id = update['update_id']
                    if 'message' in update:
                        handle_message(update['message'])
            else:
                print(f"Polling error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)
        
        time.sleep(1)

def main():
    global TELEGRAM_ENABLED
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("✅ ATF Miners Bot - REAL TAP MODE")
    print("=" * 50)
    
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️  Telegram bot not configured. Set TELEGRAM_BOT_TOKEN")
        TELEGRAM_ENABLED = False
    else:
        print(f"✅ Telegram bot enabled!")
        print("   Send /start to your bot to authorize")
    
    print("=" * 50)
    print("✅ REAL TAP MODE: Only counting successful taps!")
    print("=" * 50)
    
    # Load proxies
    proxies_list = []
    if os.path.exists("proxies.txt"):
        with open("proxies.txt", "r", encoding="utf-8") as f:
            for line in f:
                p = parse_proxy(line)
                if p: 
                    proxies_list.append(p)
                    PROXIES_LIST.append(p)
        print(f"[+] Loaded {len(proxies_list)} proxies")
    else:
        print("[!] No proxies.txt found")
    
    # Load queries
    if not os.path.exists("query.txt"):
        print("❌ query.txt not found!")
        sys.exit(1)
        
    with open("query.txt", "r", encoding="utf-8") as f:
        queries = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    
    if not queries:
        print("❌ query.txt is empty!")
        sys.exit(1)
    
    for i, q in enumerate(queries):
        proxy = proxies_list[i % len(proxies_list)] if proxies_list else None
        
        ACCOUNTS.append({
            "query": q,
            "proxy": proxy,
            "username": parse_username(q),
            "balance": "0.0",
            "real_taps": 0,
            "mining_status": "Starting...",
            "mining_end": 0,
            "task_status": "Starting...",
            "task_end": 0,
            "boost_status": "Starting...",
            "boost_end": 0
        })
        
    print(f"[+] Loaded {len(ACCOUNTS)} account(s)")
    print("=" * 50)
    print("✅ Starting REAL TAP MODE workers...")
    print("   Only successful taps will be counted!")
    print("=" * 50)

    # Start Telegram polling
    if TELEGRAM_ENABLED:
        polling_thread = threading.Thread(target=polling_loop, daemon=True)
        polling_thread.start()

    # Start worker threads
    for acc in ACCOUNTS:
        t = threading.Thread(target=worker_thread, args=(acc,), daemon=True)
        t.start()
        time.sleep(0.2)

    # Main loop
    if not PRODUCTION_MODE:
        try:
            with Live(generate_layout(), refresh_per_second=2) as live:
                while True:
                    live.update(generate_layout())
                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            sys.exit(0)
    else:
        print("✅ Bot running in REAL TAP MODE...")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            sys.exit(0)

if __name__ == "__main__":
    main()
