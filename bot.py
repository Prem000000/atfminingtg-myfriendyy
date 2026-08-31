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
TELEGRAM_BOT_TOKEN = "8411649204:AAGPnQhIMKKB1rhfoSgGz2ZBtBokNZX1eH4"  # Replace with your bot token only!
TELEGRAM_ENABLED = True

ACCOUNTS = []
PROXIES_LIST = []
lock = threading.Lock()
last_update_id = 0
authorized_chat_id = None

# ============================================================
#  PRODUCTION MODE - Auto-detect
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
        response = requests.post(url, json=payload, timeout=10)
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
            
            if "Tap" in boost_status or "+" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> ✅ Active (Next in <code>{boost_time}</code>)\n"
                tap_active += 1
            elif "Busy" in boost_status or "Cooldown" in boost_status:
                msg += f"  🚀 <b>Auto-Tap:</b> ⏳ {boost_status}\n"
            else:
                msg += f"  🚀 <b>Auto-Tap:</b> {boost_status}\n"
            
            task_status = acc.get('task_status', 'Unknown')
            task_end = acc.get('task_end', 0)
            task_time = format_time_remaining(task_end)
            
            if "Done" in task_status:
                msg += f"  📋 <b>Tasks:</b> ✅ {task_status}\n"
            else:
                msg += f"  📋 <b>Tasks:</b> {task_status} (next in <code>{task_time}</code>)\n"
            
            if acc.get('proxy'):
                msg += f"  🔗 <b>Proxy:</b> ✅ Connected\n"
            
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

def api(session: requests.Session, action: str, acc: dict, extra: dict = None, retries: int = 3):
    url = f"{BASE_URL}?action={action}&t={int(time.time() * 1000)}"
    payload = {"initData": acc["query"]}
    if extra: payload.update(extra)

    for attempt in range(1, retries + 1):
        try:
            r = session.post(url, json=payload, timeout=30)
            r.raise_for_status()
            try: 
                response = r.json()
                return response
            except: 
                return {"raw": r.text}
        except requests.exceptions.HTTPError as e:
            try: 
                return r.json()
            except: 
                pass
            if attempt < retries: 
                time.sleep(3)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ProxyError) as e:
            if PROXIES_LIST:
                new_p = random.choice(PROXIES_LIST)
                acc["proxy"] = new_p
                session.proxies.update({"http": new_p, "https": new_p})
                with lock: 
                    acc["mining_status"] = "Proxy Error, Rotating..."
            if attempt < retries: 
                time.sleep(5 * attempt)
            else: 
                return None
        except requests.RequestException as e:
            if attempt < retries: 
                time.sleep(5 * attempt)
            else: 
                return None
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

def get_tg_id(acc):
    """Extract tg_id from query"""
    try:
        parsed = dict(urllib.parse.parse_qsl(acc["query"]))
        user_str = parsed.get("user", "{}")
        user_data = json.loads(urllib.parse.unquote(user_str))
        return user_data.get("id", "")
    except:
        return ""

def process_mining(acc):
    with lock: 
        acc["mining_status"] = "Logging in..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
        
    # Login
    login_res = api(sess, "login", acc)
    if not login_res:
        with lock: 
            acc["mining_status"] = "Login Failed (Retrying)"
        acc["mining_end"] = time.time() + 5
        return
        
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: 
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    # Get balance
    bal = extract_balance(login_res)
    if bal is not None:
        with lock: 
            acc["balance"] = str(bal)
    
    # Get user data
    user_data = login_res.get("user", {})
    if not user_data and "data" in login_res:
        user_data = login_res["data"].get("user", {})
    
    tg_id = get_tg_id(acc)
    
    # Check mining status
    mining_start = user_data.get("mining_cycle_started_at") or user_data.get("last_mining_start") or 0
    try:
        mining_start = float(mining_start)
    except:
        mining_start = 0
    
    now = time.time()
    
    # If mining is active and not finished, wait
    if mining_start > 0:
        mining_end = mining_start + 3600  # 1 hour mining cycle
        if now < mining_end:
            wait_time = mining_end - now
            with lock:
                acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
                acc["mining_end"] = now + max(wait_time, 10)
            sess.close()
            return
    
    # Claim and start new mining
    with lock: 
        acc["mining_status"] = "Claiming Reward..."
    
    # Claim reward
    claim_res = api(sess, "claim", acc)
    time.sleep(1)
    
    # Solve captcha
    with lock: 
        acc["mining_status"] = "Solving Captcha..."
    
    challenge_res = api(sess, "get_math_challenge", acc, extra={'tg_id': tg_id, 'scope': 'start_mine'})
    start_payload = {
        'tg_id': tg_id,
        'request_id': str(uuid.uuid4())
    }
    
    if challenge_res and challenge_res.get("status") == "success":
        try:
            cid = challenge_res['challenge_id']
            q_str = challenge_res['question'].replace('=', '').replace('?', '').strip()
            ans = str(eval(q_str))
            start_payload['math_challenge_id'] = cid
            start_payload['math_answer'] = ans
        except Exception as e:
            print(f"Captcha error: {e}")
    
    # Start mining
    with lock: 
        acc["mining_status"] = "Starting New Mining..."
    
    start_res = api(sess, "start_mine", acc, extra=start_payload)
    
    if start_res and start_res.get("status") == "success":
        with lock:
            acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
            acc["mining_end"] = time.time() + 3600  # 1 hour
    else:
        error_msg = start_res.get("message", start_res.get("reason", "Unknown error")) if start_res else "HTTP Error"
        with lock:
            acc["mining_status"] = f"Error: {error_msg}"
            acc["mining_end"] = time.time() + 60
    
    sess.close()

def process_boost(acc):
    with lock: 
        acc["boost_status"] = "Tapping..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    # Login
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock:
            acc["boost_status"] = "Login Failed"
            acc["boost_end"] = time.time() + 5
        sess.close()
        return
    
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: 
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    # Get balance after login
    bal = extract_balance(login_res)
    if bal is not None:
        with lock: 
            acc["balance"] = str(bal)
    
    tg_id = get_tg_id(acc)
    
    # Prepare boost/tap payload
    payload = {
        "tg_id": tg_id,
        "request_id": str(uuid.uuid4()),
        "display_preview": round(random.uniform(0.24, 0.35), 4)
    }
    
    # Call activate_boost (this is the tap action)
    boost_res = api(sess, "activate_boost", acc, extra=payload, retries=2)
    
    if boost_res:
        if boost_res.get("status") == "success":
            pending = boost_res.get("pending_reward", 0)
            
            # Update balance if available
            new_balance = boost_res.get("new_balance")
            if new_balance is not None:
                with lock:
                    acc["balance"] = str(new_balance)
            
            with lock:
                acc["boost_status"] = f"+{pending} ATF"
                # Send notification to Telegram
                if authorized_chat_id:
                    send_telegram_message(f"✅ <b>Tap Successful!</b>\nAccount: {acc['username']}\n+{pending} ATF\nBalance: {acc['balance']} ATF")
            
            # Check boost_ready_at for cooldown
            ready_at = boost_res.get("boost_ready_at", 0)
            if ready_at:
                try:
                    wait_time = float(ready_at) - time.time()
                    wait_time = max(wait_time, 2)
                except:
                    wait_time = 10
            else:
                wait_time = 10
                
            with lock:
                acc["boost_end"] = time.time() + max(wait_time, 2)
                
        elif boost_res.get("status") == "cooldown":
            ready_at = boost_res.get("boost_ready_at", 0)
            if ready_at:
                try:
                    wait_time = float(ready_at) - time.time()
                    wait_time = max(wait_time, 2)
                except:
                    wait_time = 10
            else:
                wait_time = 10
                
            with lock:
                acc["boost_status"] = f"Cooldown ({int(wait_time)}s)"
                acc["boost_end"] = time.time() + max(wait_time, 2)
                
        elif boost_res.get("status") == "busy":
            with lock:
                acc["boost_status"] = "Busy, retrying..."
                acc["boost_end"] = time.time() + 3
        else:
            error_msg = boost_res.get("message", "Unknown error")
            with lock:
                acc["boost_status"] = f"Error: {error_msg}"
                acc["boost_end"] = time.time() + 5
    else:
        with lock:
            acc["boost_status"] = "HTTP Failed"
            acc["boost_end"] = time.time() + 5
    
    sess.close()

def process_tasks(acc):
    with lock: 
        acc["task_status"] = "Preparing Tasks..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    # Login
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock: 
            acc["task_status"] = "Login failed"
            acc["task_end"] = time.time() + 30
        sess.close()
        return
    
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: 
        sess.headers.update({"Authorization": f"Bearer {token}"})
    
    tg_id = get_tg_id(acc)
    if not tg_id:
        with lock: 
            acc["task_status"] = "No TG ID"
            acc["task_end"] = time.time() + 60
        sess.close()
        return
    
    # Get completed tasks from user data
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
        
        with lock: 
            acc["task_status"] = f"Starting: {tid}"
        
        # Start task
        start_res = api(sess, "start_task", acc, extra={"tg_id": tg_id, "task_id": tid}, retries=1)
        time.sleep(1)
        
        # Claim task
        with lock: 
            acc["task_status"] = f"Claiming: {tid}"
        
        claim_res = api(sess, "claim_task", acc, extra={
            "tg_id": tg_id, 
            "task_id": tid, 
            "client_started_at": int(time.time()),
            "request_id": str(uuid.uuid4())
        }, retries=1)
        
        if claim_res and claim_res.get("status") == "success":
            start_count += 1
            completed_tasks.append(tid)
        
        time.sleep(1)
    
    with lock:
        acc["task_status"] = f"Done (+{start_count})"
        acc["task_end"] = time.time() + 120  # 2 minutes
    
    sess.close()

def worker_thread(acc):
    # Initialize with immediate first run
    time.sleep(random.uniform(0.5, 3.0))
    
    # Set initial times to run immediately
    with lock:
        acc["mining_end"] = 0
        acc["boost_end"] = 0
        acc["task_end"] = time.time() + 30
    
    while True:
        now = time.time()
        
        # Check and run mining (every hour)
        if now >= acc["mining_end"]:
            process_mining(acc)
            continue
        
        # Check and run boost/tap (every 10-15 seconds)
        if now >= acc["boost_end"]:
            process_boost(acc)
            continue
        
        # Check and run tasks (every 2 minutes)
        if now >= acc["task_end"]:
            process_tasks(acc)
            continue
        
        time.sleep(0.5)

def handle_message(message):
    global authorized_chat_id
    
    if 'text' not in message:
        return
    
    text = message['text'].strip()
    chat_id = message['chat']['id']
    
    if not authorized_chat_id:
        authorized_chat_id = chat_id
        print(f"✅ Authorized chat ID: {authorized_chat_id}")
        send_telegram_message("🚀 <b>ATF Miners Bot Authorized!</b>\n\nSend /status to check real-time mining info\nSend /help for available commands")
        return
    
    if chat_id != authorized_chat_id:
        return
    
    if text.lower() == '/status':
        status_msg = get_status_message()
        send_telegram_message(status_msg)
    
    elif text.lower() == '/help':
        help_msg = """<b>🤖 ATF Miners Bot Commands:</b>

/status - Show real-time mining status for all accounts
/help - Show this help message
/start - Show bot info

<b>Bot Features:</b>
• ⛏️ Auto-mining every hour
• 🚀 Auto-tap every 10-15 seconds  
• 📋 Auto-task completion
• 💰 Real-time balance updates"""
        send_telegram_message(help_msg)
    
    elif text.lower() == '/start':
        start_msg = f"""🚀 <b>ATF Miners Bot is Active!</b>

📊 <b>Status:</b> Running
👥 <b>Accounts:</b> {len(ACCOUNTS)} account(s)

Use /status to check real-time mining status
Use /help for available commands

Bot is automatically mining, tapping, and completing tasks!"""
        send_telegram_message(start_msg)

def polling_loop():
    global last_update_id
    print("📡 Started polling for Telegram commands...")
    print("💬 Send /start to your bot to authorize")
    
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
    print("🚀 ATF Miners Bot")
    print("=" * 50)
    
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("⚠️  Telegram bot not configured. Set TELEGRAM_BOT_TOKEN")
        TELEGRAM_ENABLED = False
    else:
        print(f"✅ Telegram bot enabled!")
        print("   Send /start to your bot to authorize")
    
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
            "mining_status": "Starting...",
            "mining_end": 0,
            "task_status": "Starting...",
            "task_end": 0,
            "boost_status": "Starting...",
            "boost_end": 0
        })
        
    print(f"[+] Loaded {len(ACCOUNTS)} account(s)")
    print("=" * 50)

    # Start Telegram polling
    if TELEGRAM_ENABLED:
        polling_thread = threading.Thread(target=polling_loop, daemon=True)
        polling_thread.start()

    # Start worker threads
    for acc in ACCOUNTS:
        t = threading.Thread(target=worker_thread, args=(acc,), daemon=True)
        t.start()
        time.sleep(0.5)  # Stagger thread starts

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
        print("🔄 Bot running in production mode...")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            print("\n🛑 Bot stopped")
            sys.exit(0)

if __name__ == "__main__":
    main()
