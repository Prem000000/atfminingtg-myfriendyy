# ATF Miners Bot 🚀

**🔗 Register & Play ATF Miners:** [https://t.me/ATF_AIRDROP_bot](https://t.me/ATF_AIRDROP_bot?start=740497999)

An automation bot for the **ATF Miners** Telegram game. Built using Python with a clean, real-time, flicker-free terminal User Interface (UI) powered by the `rich` library.

## ✨ Key Features

- **[Multi-Account Support]** Run unlimited accounts simultaneously without issues.
- **[Auto Mining]** Automatically claims and starts a new mining cycle every hour.
- **[Auto Captcha Bypass]** Equipped with a built-in solver to crack the newly implemented *Math Captcha* (e.g., `11 - 3 = ?`) required before starting the mining process.
- **[Smart Proxy Support]** Full support for HTTP and SOCKS5 proxies (`proxies.txt`). Includes an **auto-rotate feature** that automatically switches to a new, healthy proxy if a network error or connection timeout occurs.
- **[Auto Tap / Boost]** Automatically taps the ATF coin to earn additional balance based on available energy, while strictly respecting server cooldowns and rate limits to avoid temporary bans.
- **[Auto Tasks]** Automatically clicks "Go" on all unfinished tasks and relentlessly attempts to "Claim" them every minute. This perfectly bypasses the ATF server's hidden ~2-hour cooldown system for tasks.
- **[Live Dashboard]** An elegant, organized, and non-flickering 3-column terminal UI to monitor **Mining**, **Auto-Tap**, and **Tasks** in real-time.

---

## 📋 Prerequisites

Make sure you have installed **Python 3.10** or a newer version on your operating system.

## ⚙️ Installation

1. **Clone this repository** (or download the ZIP):
   ```bash
   git clone https://github.com/imorekt/atf-miners-bot.git
   cd atf-miners-bot
   ```

2. **Install the required dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(The primary external modules used are `requests` and `rich`)*

3. **Input your account data**:
   Open the `query.txt` file and enter your `query_id=...` data.
   - You can add multiple accounts.
   - Separate each account with a new line (Enter).

   *(How to get your `query_id`: Open the ATF Miners bot on Telegram Web/Desktop, inspect element (F12) -> Application -> Session Storage or Network tab, and look for the string starting with `query_id=` or `user=`)*

---

## 🚀 How to Run

Execute the following command in your terminal / command prompt:
```bash
python bot.py
```

### 🌍 Running 24/7 on a VPS (Using `screen`)

If you want the bot to keep running after you close your SSH terminal, it is highly recommended to use `screen`.

1. **Install Screen** (if not already installed):
   ```bash
   sudo apt-get install screen -y
   ```
2. **Start a New Screen Session** (named `atf-bot`):
   ```bash
   screen -S atf-bot
   ```
3. **Run the Bot** inside the screen session:
   ```bash
   python bot.py
   ```
4. **Detach from the Screen** (leave it running in the background):
   Press `Ctrl + A`, then press `D`. You can now safely close your SSH connection.
5. **Reattach / View the Screen later**:
   To view the bot's live terminal again, simply type:
   ```bash
   screen -r atf-bot
   ```

---

## ⚠️ Disclaimer

- **Do With Your Own Risk**. Use this bot at your own discretion.
- Aggressive botting may trigger ban mechanisms from the ATF Miners developers. This bot is equipped with built-in rate limit handling to minimize such risks, but safety is never 100% guaranteed.
- This project was created purely for educational and learning purposes.

## 🤝 Contributing

Pull requests are highly welcome. For major changes, please open an issue first to discuss what you would like to change.
