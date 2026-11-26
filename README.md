# Telegram assistant — OpenAI / Fastypass

Default provider: official OpenAI, https://api.openai.com/v1.

## Railway variables

- TELEGRAM_TOKEN: separate Telegram bot token.
- OPENAI_API_KEY: OpenAI API key; set directly in Railway, never commit it.
- BASE_URL: https://api.openai.com/v1
- DEFAULT_MODEL: gpt-5.4-mini
- ADMIN_IDS: positive numeric Telegram user IDs separated by commas.
- DB_PATH: /data/bot.sqlite3 (attach a separate volume mounted at /data).
- SYSTEM_PROMPT: your assistant instructions, including a standup writing prompt.
- MAX_OUTPUT_TOKENS: 1500
- MAX_HISTORY_CHARS: 24000
- ALLOWLIST_IDS: optional permitted users, reapplied on startup.

Remove FASTYPASS_API_KEY when switching to OpenAI. Old provider model selections are reset to the default, clearing the affected conversation but preserving usage. /new clears conversation; /prompt reset returns to SYSTEM_PROMPT. A personal prompt overrides SYSTEM_PROMPT.

## Local setup

Python 3.12. Create a virtual environment, install requirements.txt, copy .env.example to .env, fill it locally and run python bot.py. On Linux restrict .env to mode 600. Never commit secrets.

## Features

Private chats, per-user SQLite history and prompts, model menu, /new, /stats and admin /allow /deny /users /globalstats. Usage comes from API responses and does not represent dollar balance. Attachments remain disabled pending end-to-end verification.

## Optional Fastypass mode

Explicitly set BASE_URL=https://api.fastypass.com:8444/v1 and FASTYPASS_API_KEY. OpenAI credentials are never used as a fallback for Fastypass. Nine original provider model identifiers remain supported in this mode; their identity and pricing are not independently verified.

## Deployment

Dockerfile included. Use one replica in a separate Railway service with its own persistent volume. No public domain is needed. Existing bot services must remain separate.

## Validation

Provider routing, payload fields, missing-key handling, model migration and credential isolation are tested with mocked HTTP responses. Live OpenAI completion testing requires a fresh key configured by the user; published chat keys are not used.

Official API reference: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
