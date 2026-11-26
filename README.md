# Telegram assistant — Groq

Default provider: official Groq, https://api.groq.com/openai/v1.

## Railway variables

- TELEGRAM_TOKEN: separate Telegram bot token.
- GROQ_API_KEY: Groq API key; set directly in Railway, never commit it.
- BASE_URL: https://api.groq.com/openai/v1
- DEFAULT_MODEL: openai/gpt-oss-120b
- ADMIN_IDS: positive numeric Telegram user IDs separated by commas.
- DB_PATH: /data/bot.sqlite3 (attach a separate volume mounted at /data).
- SYSTEM_PROMPT: your assistant instructions, including a standup writing prompt.
- MAX_OUTPUT_TOKENS: 1500
- MAX_HISTORY_CHARS: 12000
- ALLOWLIST_IDS: optional permitted users, reapplied on startup.

Unsupported model selections are reset to the default, clearing the affected conversation but preserving usage. /new clears conversation; /prompt reset returns to SYSTEM_PROMPT. A personal prompt overrides SYSTEM_PROMPT.

## Local setup

Python 3.12. Create a virtual environment, install requirements.txt, copy .env.example to .env, fill it locally and run python bot.py. On Linux restrict .env to mode 600. Never commit secrets.

## Features

Private chats, per-user SQLite history and prompts, model menu, /new, /stats and admin /allow /deny /users /globalstats. Usage comes from API responses and does not represent dollar balance. Attachments remain disabled pending end-to-end verification.

## Deployment

Dockerfile included. Use one replica in a separate Railway service with its own persistent volume. No public domain is needed. Existing bot services must remain separate.

## Validation

Official endpoint restriction, payload fields, missing-key handling, model migration and credential isolation are tested with mocked HTTP responses. Live Groq completion testing requires a fresh key configured by the user; published chat keys are not used.

Official API reference: https://console.groq.com/docs/openai
Models: https://console.groq.com/docs/models
Rate limits: https://console.groq.com/docs/rate-limits

## Model menu and migration

/model offers openai/gpt-oss-120b and openai/gpt-oss-20b. Inference runs on Groq; the openai/ prefix is part of the open-weight model ID and does not mean a request goes to the OpenAI API. Removed model selections reset automatically, clearing affected history while preserving usage and personal prompts.

Create a fresh key at https://console.groq.com/keys and enter it directly into Railway as GROQ_API_KEY. Remove the previous API key variable, set the new BASE_URL and DEFAULT_MODEL before deployment. The service does not fall back to any old key.

The free plan has request and token limits; inspect your account limits for exact availability. Photo, document and voice handlers remain disabled until tested against the API. Live completion testing is pending a user-configured Groq key.

Run tests from the project directory: python -m unittest discover -s tests -v
