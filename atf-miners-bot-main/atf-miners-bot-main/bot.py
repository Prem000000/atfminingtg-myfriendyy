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

ACCOUNTS = []
PROXIES_LIST = []
lock = threading.Lock()

def format_time_remaining(end_time):
    if end_time <= 0: return "Ready"
    sisa = end_time - time.time()
    if sisa <= 0: return "Waiting.."
    m, s = divmod(int(sisa), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

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
                with lock: acc["mining_status"] = "Proxy Error, Rotating..."
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

def process_mining(acc):
    with lock: acc["mining_status"] = "Logging in..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
        
    login_res = api(sess, "login", acc)
    if not login_res:
        with lock: acc["mining_status"] = "Login Failed (Retrying)"
        acc["mining_end"] = time.time() + 2
        return
        
    token = login_res.get("token") or (login_res.get("data") or {}).get("token")
    if token: sess.headers.update({"Authorization": f"Bearer {token}"})
    
    bal = extract_balance(login_res)
    if bal is not None:
        with lock: acc["balance"] = str(bal)
        
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
        with lock: acc["mining_status"] = "Claiming Reward..."
        claim_res = api(sess, "claim", acc)
        time.sleep(2)
        
        with lock: acc["mining_status"] = "Solving Captcha..."
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
        
        with lock: acc["mining_status"] = "Starting New Mining..."
        start_res = api(sess, "start_mine", acc, extra=start_payload)
        
        has_error = False
        error_msg = ""
        
        if start_res:
            if start_res.get("status") == "success":
                wait_secs = 3600.0
            else:
                has_error = True
                error_msg = start_res.get("message", start_res.get("reason", "Gagal Start"))
                wait_secs = 60.0
        else:
            has_error = True
            error_msg = "Gagal HTTP Start"
            wait_secs = 60.0
            
    with lock: 
        if can_claim and has_error:
            acc["mining_status"] = f"Error: {error_msg}"
        else:
            acc["mining_status"] = f"Mining ({acc['balance']} ATF)"
        acc["mining_end"] = time.time() + max(wait_secs, 60.0)
    sess.close()

def process_boost(acc):
    with lock: acc["boost_status"] = "Starting Tap..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
        
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock:
            acc["boost_status"] = "Login Failed"
            acc["boost_end"] = time.time() + 5.0
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
            
            ready_at = br.get("boost_ready_at", 0)
            if ready_at:
                sisa = ready_at - time.time()
                if sisa > 0: wait_time = sisa
        elif br.get("status") == "busy":
            status_msg = "Busy (Cooldown)"
            wait_time = 2.0
        elif br.get("status") == "cooldown":
            status_msg = "Sistem Cooldown"
            ready_at = br.get("boost_ready_at", 0)
            if ready_at:
                sisa = ready_at - time.time()
                if sisa > 0: wait_time = sisa
    else:
        status_msg = "HTTP Failed"
        wait_time = 5.0
        
    with lock:
        acc["boost_status"] = status_msg
        acc["boost_end"] = time.time() + max(wait_time, 2.0)
    sess.close()

def process_tasks(acc):
    with lock: acc["task_status"] = "Preparing Tasks..."
    
    sess = requests.Session()
    sess.headers.update(HEADERS_TEMPLATE)
    if acc.get("proxy"):
        sess.proxies.update({"http": acc["proxy"], "https": acc["proxy"]})
    
    # Login to get valid token
    login_res = api(sess, "login", acc, retries=1)
    if not login_res:
        with lock: acc["task_status"] = "Login failed, retrying..."
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
        with lock: acc["task_status"] = "Failed parsing TG ID"
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
    
    for tid in task_ids:
        if tid in completed_tasks:
            continue
            
        with lock: acc["task_status"] = f"Start: {tid}"
        sr = api(sess, "start_task", acc, extra={"tg_id": tg_id, "task_id": tid}, retries=1)
        
        # Selalu coba claim, baik start-nya success maupun sudah pernah di-start (cooldown)
        with lock: acc["task_status"] = f"Claim: {tid}"
        cr = api(sess, "claim_task", acc, extra={
            "tg_id": tg_id, 
            "task_id": tid, 
            "client_started_at": int(time.time()),
            "request_id": str(uuid.uuid4())
        }, retries=1)
        
        if cr and cr.get("status") == "success":
            start_count += 1
            completed_tasks.append(tid)
            
        time.sleep(1)
            
    with lock:
        acc["task_status"] = f"Done (+{start_count} Claimed)"
        acc["task_end"] = time.time() + 60.0

def worker_thread(acc):
    time.sleep(random.uniform(0.5, 5.0)) # Stagger thread starts
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

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("🚀 ATF Miners Bot")
    
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

    # Kosongkan layar sebelum menjalankan UI Live
    os.system("cls" if os.name == "nt" else "clear")

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
        sys.exit(0)

if __name__ == "__main__":
    main()
