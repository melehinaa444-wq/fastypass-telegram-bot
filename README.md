# Fastypass Telegram Bot

Python 3.12 Telegram assistant using the Fastypass OpenAI-compatible endpoint.

## Features

- Nine provider model names, selected with /model.
- Per-user SQLite conversations, /new, personal /prompt.
- Default-deny allowlist and admin commands: /allow, /deny, /users, /globalstats.
- Provider-reported usage with /stats. No dollar balance estimates.
- Private chats only. Media disabled pending verified API compatibility.

Model names are provider identifiers; model identity and pricing are not independently verified.

## Setup

Create a virtual environment and install requirements.txt. Copy .env.example to .env, then fill TELEGRAM_TOKEN, FASTYPASS_API_KEY and ADMIN_IDS. Never commit .env. On Linux use chmod 600 .env. Start with python bot.py.

Commands: /start /help /id /model /new /stats /prompt /admin.
Changing model or prompt clears the user's conversation. /new preserves usage statistics.
ALLOWLIST_IDS is applied at every startup; remove an ID from this setting as well when revoking persistent access.

## Railway

Create a separate service for this repository, with one replica and its own volume mounted at /data. Set DB_PATH=/data/bot.sqlite3. Configure secrets through service variables; do not upload .env. No public domain or port is required. Do not reuse the existing bot's token, service or volume.

## Verification status

Fastypass guide and token pages were reachable on 2026-11-26. Unauthenticated GET /v1/models returned 401. Authenticated completion and Telegram end-to-end checks are pending credentials/configuration. Photo, document and voice support is not verified and is disabled.

Sources: https://chat.fastypass.com:8444/guide and https://chat.fastypass.com:8444/tokens
