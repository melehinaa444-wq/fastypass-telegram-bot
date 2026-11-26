import os
import sqlite3
from pathlib import Path

MODELS = ('gpt-6-astra','gpt-5.6-sol','gpt-5.6-terra','gpt-5.6-luna','gpt-5.5','gpt-5.4','gpt-5.4-mini','gpt-oss-120b','codex-auto-review')

class Store:
    def __init__(self, path, default='gpt-5.4-mini', prompt='Ты полезный ассистент.'):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, allowed INTEGER NOT NULL DEFAULT 0, model TEXT NOT NULL, prompt TEXT);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, uid INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY, uid INTEGER NOT NULL, model TEXT NOT NULL, input INTEGER, output INTEGER, created TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        self.default, self.prompt = default, prompt
    def user(self, uid):
        self.db.execute('INSERT OR IGNORE INTO users(id,model) VALUES(?,?)',(uid,self.default))
        self.db.commit()
        return self.db.execute('SELECT allowed,model,prompt FROM users WHERE id=?',(uid,)).fetchone()
    def allow(self, uid, value):
        self.user(uid)
        self.db.execute('UPDATE users SET allowed=? WHERE id=?',(int(value),uid)); self.db.commit()
    def set(self, uid, field, value):
        if field not in ('model','prompt'): raise ValueError('field')
        if field == 'model' and value not in MODELS: raise ValueError('model')
        self.user(uid)
        self.db.execute(f'UPDATE users SET {field}=? WHERE id=?',(value,uid))
        self.db.execute('DELETE FROM messages WHERE uid=?',(uid,)); self.db.commit()
    def clear(self, uid):
        self.db.execute('DELETE FROM messages WHERE uid=?',(uid,)); self.db.commit()
    def context(self, uid, text, limit=24000):
        _, _, prompt = self.user(uid)
        history = self.db.execute('SELECT role,content FROM messages WHERE uid=? ORDER BY id',(uid,)).fetchall()
        # Remove whole turns, preserving user/assistant alternation.
        while history and sum(len(c) for _,c in history)+len(text) > limit:
            history = history[2:]
        return [{'role':'system','content':prompt or self.prompt}]+[{'role':r,'content':c} for r,c in history]+[{'role':'user','content':text}]
    def record(self, uid, model, text, answer, usage):
        def count(key):
            value = usage.get(key)
            return value if type(value) is int and value >= 0 else None
        with self.db:
            self.db.executemany('INSERT INTO messages(uid,role,content) VALUES(?,?,?)',[(uid,'user',text),(uid,'assistant',answer)])
            self.db.execute('INSERT INTO usage(uid,model,input,output) VALUES(?,?,?,?)',(uid,model,count('prompt_tokens'),count('completion_tokens')))
            # Keep storage bounded as well as outgoing context.
            self.db.execute('DELETE FROM messages WHERE uid=? AND id NOT IN (SELECT id FROM messages WHERE uid=? ORDER BY id DESC LIMIT 100)',(uid,uid))
    def stats(self, uid=None):
        clause, args = (' WHERE uid=?',(uid,)) if uid is not None else ('',())
        return self.db.execute('SELECT COUNT(*),COALESCE(SUM(input),0),COALESCE(SUM(output),0),SUM(CASE WHEN input IS NULL OR output IS NULL THEN 1 ELSE 0 END) FROM usage'+clause,args).fetchone()

class APIError(Exception): pass

async def complete(client, base, key, model, messages, max_tokens):
    try:
        response = await client.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key},json={'model':model,'messages':messages,'max_tokens':max_tokens,'stream':False})
        if response.status_code != 200: raise APIError('HTTP '+str(response.status_code))
        data = response.json()
        answer = data['choices'][0]['message']['content']
        if not isinstance(answer,str) or not answer.strip() or len(answer)>100000: raise ValueError()
        usage = data.get('usage') or {}
        if not isinstance(usage,dict): usage = {}
        return answer, usage
    except APIError: raise
    except Exception: raise APIError('Ошибка связи или неподдерживаемый ответ API') from None
