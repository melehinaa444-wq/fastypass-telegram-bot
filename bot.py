import asyncio
import logging
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from core import Store, MODELS, complete, APIError

HELP = '/model — модель\n/new — очистить историю\n/stats — токены\n/prompt текст — личный системный промпт\n/prompt reset — сброс\n/id — ваш ID\n/admin — админка'

def ids(name):
    try:
        values = {int(x.strip()) for x in os.getenv(name,'').split(',') if x.strip()}
        if any(x <= 0 for x in values): raise ValueError()
        return values
    except ValueError:
        raise SystemExit(name + ': нужны положительные числовые Telegram ID через запятую') from None

async def main():
    os.umask(0o077)
    env = Path('.env')
    if os.name != 'nt' and env.exists() and env.stat().st_mode & 0o077:
        raise SystemExit('Установите права 600 на .env')
    load_dotenv(dotenv_path=env)
    token, key = os.getenv('TELEGRAM_TOKEN',''), os.getenv('FASTYPASS_API_KEY','')
    admins = ids('ADMIN_IDS')
    missing = [name for name, value in [('TELEGRAM_TOKEN',token),('FASTYPASS_API_KEY',key),('ADMIN_IDS',admins)] if not value]
    if missing: raise SystemExit('Не заданы переменные: ' + ', '.join(missing))
    base = os.getenv('BASE_URL','https://api.fastypass.com:8444/v1').rstrip('/')
    if base != 'https://api.fastypass.com:8444/v1': raise SystemExit('Неподтвержденный BASE_URL')
    default = os.getenv('DEFAULT_MODEL','gpt-5.4-mini')
    if default not in MODELS: raise SystemExit('Неверная модель')
    store = Store(os.getenv('DB_PATH','data/bot.sqlite3'),default,os.getenv('SYSTEM_PROMPT','Ты полезный ассистент.'))
    for uid in ids('ALLOWLIST_IDS') | admins: store.allow(uid,True)
    limit, output = int(os.getenv('MAX_HISTORY_CHARS','24000')), int(os.getenv('MAX_OUTPUT_TOKENS','1500'))
    if not 4000 <= limit <= 100000 or not 1 <= output <= 16000: raise SystemExit('Неверные лимиты')
    bot, dp = Bot(token), Dispatcher()
    busy = set()
    semaphore = asyncio.Semaphore(4)
    def allowed(uid): return uid in admins or bool(store.user(uid)[0])
    def stats(uid):
        n,i,o,missing = store.stats(uid)
        return f'Успешных запросов: {n}\nВход: {i}; выход: {o}\nБез полной статистики API: {missing or 0}\nЭто данные usage провайдера, не баланс и не сумма в долларах. Ошибки и проверки могут также оплачиваться.'
    async def send(message,text):
        for start in range(0,len(text),3500): await message.answer(text[start:start+3500])
    @dp.callback_query()
    async def callback(q: CallbackQuery):
        uid = q.from_user.id
        if not q.message or q.message.chat.type != 'private' or not allowed(uid):
            await q.answer('Нет доступа'); return
        if uid in busy: await q.answer('Дождитесь ответа'); return
        if q.data and q.data.startswith('model:') and q.data[6:] in MODELS:
            store.set(uid,'model',q.data[6:])
            await q.answer('Модель выбрана; история очищена')
            await q.message.answer('Модель: '+q.data[6:])
        else: await q.answer()
    @dp.message()
    async def handle(m: Message):
        if not m.from_user or m.chat.type != 'private': return
        uid = m.from_user.id
        text = m.text or ''
        command, _, arg = text.partition(' ')
        command = command.split('@')[0].lower()
        if command == '/id': await m.answer(str(uid)); return
        if not allowed(uid): await m.answer(f'Доступ закрыт. Ваш ID: {uid}'); return
        if uid in busy: await m.answer('Дождитесь завершения предыдущего запроса.'); return
        if command in ('/start','/help'):
            await m.answer('Ассистент через Fastypass. Сообщения передаются провайдеру. Названия моделей заявлены провайдером; подлинность не подтверждена.\n'+HELP); return
        if command == '/new': store.clear(uid); await m.answer('История очищена.'); return
        if command == '/stats': await m.answer(stats(uid)); return
        if command == '/model':
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x,callback_data='model:'+x)] for x in MODELS])
            await m.answer('Текущая: '+store.user(uid)[1]+'\nПри смене история очищается.',reply_markup=keyboard); return
        if command == '/prompt':
            if not arg: await m.answer('Текущий промпт:\n'+(store.user(uid)[2] or store.prompt)); return
            if len(arg)>3000: await m.answer('Максимум 3000 символов.'); return
            store.set(uid,'prompt',None if arg=='reset' else arg)
            await m.answer('Промпт сохранён; история очищена.'); return
        if command in ('/admin','/allow','/deny','/users','/globalstats'):
            if uid not in admins: await m.answer('Только администратор.'); return
            if command == '/admin': await m.answer('/allow ID\n/deny ID\n/users\n/globalstats'); return
            if command == '/globalstats': await m.answer(stats(None)); return
            if command == '/users':
                rows = store.db.execute('SELECT id,allowed,model FROM users ORDER BY id LIMIT 200').fetchall()
                await send(m,'Первые 200 пользователей:\n'+'\n'.join(f'{a}: {b}, {c}' for a,b,c in rows)); return
            try:
                target = int(arg)
                if target <= 0 or target in admins: raise ValueError()
            except ValueError: await m.answer('Укажите положительный ID обычного пользователя.'); return
            store.allow(target,command=='/allow'); await m.answer('Доступ обновлён.'); return
        if text.startswith('/'): await m.answer(HELP); return
        if not text: await m.answer('Фото, документы и голос пока отключены: совместимость API не подтверждена.'); return
        if len(text)>4000: await m.answer('Максимум 4000 символов за запрос.'); return
        busy.add(uid)
        try:
            async with semaphore:
                if not allowed(uid): await m.answer('Доступ отозван.'); return
                model = store.user(uid)[1]
                answer,usage = await complete(client,base,key,model,store.context(uid,text,limit),output)
                store.record(uid,model,text,answer,usage)
            await send(m,answer)
        except APIError as e:
            await m.answer(f'Запрос не завершён: {e}. Автоповтор отключён. История не изменена.')
        except Exception:
            await m.answer('Ошибка обработки или доставки. Запрос мог быть оплачен; проверьте /stats.')
        finally: busy.discard(uid)
    async with httpx.AsyncClient(timeout=90,follow_redirects=False,trust_env=False) as client:
        try:
            if (await bot.get_webhook_info()).url: raise SystemExit('У этого бота включён webhook; запуск остановлен.')
            print('Telegram подключён. Бот начинает получать сообщения.', flush=True)
            await dp.start_polling(bot,allowed_updates=['message','callback_query'],tasks_concurrency_limit=32)
        finally:
            store.db.close()
            await bot.session.close()

if __name__ == '__main__':
    # Third-party exceptions may contain request URLs or tokens. Never log them.
    logging.disable(logging.CRITICAL)
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print('Ошибка запуска: ' + exc.code, flush=True)
            raise SystemExit(1) from None
        raise
    except Exception as exc:
        # Print only the exception class, never its message or request URL.
        print('Ошибка запуска (' + type(exc).__name__ + '). Проверьте переменные, Telegram и хранилище.', flush=True)
        raise SystemExit(1) from None
