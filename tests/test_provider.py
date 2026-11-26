import asyncio
import json
import tempfile
import unittest
from pathlib import Path
import httpx
from core import Store, provider_config, complete, APIError

class ProviderTests(unittest.TestCase):
    def test_official_default(self):
        base,key,models,default=provider_config({'OPENAI_API_KEY':'test-key'})
        self.assertEqual(base,'https://api.openai.com/v1')
        self.assertEqual(default,'gpt-5.4-mini')
        self.assertEqual(models,('gpt-5.4-mini',))
    def test_no_key_fallback_or_untrusted_host(self):
        for config in [
            {},
            {'BASE_URL':'https://example.com','OPENAI_API_KEY':'test-key'},
            {'BASE_URL':'https://api.openai.com.evil.example/v1','OPENAI_API_KEY':'test-key'},
        ]:
            with self.assertRaises(ValueError): provider_config(config)
    def test_model_migration_and_user_isolation(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path=str(Path(folder)/'db.sqlite')
            store=Store(path)
            store.db.execute("INSERT INTO users(id,model) VALUES(1,'retired-model')")
            store.db.commit()
            store.record(1,'retired-model','hello','answer',{'prompt_tokens':3,'completion_tokens':2})
            store.record(2,'gpt-5.4-mini','private','private answer',{})
            store.db.close()
            store=Store(path,models=('gpt-5.4-mini',))
            self.assertEqual(store.user(1)[1],'gpt-5.4-mini')
            self.assertEqual(len(store.context(1,'new')),2)
            self.assertEqual(store.stats(1)[:3],(1,3,2))
            self.assertNotIn('private',str(store.context(1,'new')))
            with self.assertRaises(ValueError): store.set(1,'model','retired-model')
            store.db.close()

def immediate(coroutine):
    try: coroutine.send(None)
    except StopIteration as result: return result.value
    finally: coroutine.close()
    raise AssertionError('Unexpected suspension in in-memory transport')

class FakeClient:
    def __init__(self, handler): self.handler=handler
    async def post(self, url, headers, json):
        return self.handler(httpx.Request('POST',url,headers=headers,json=json))

class HTTPTests(unittest.TestCase):
    def test_provider_payloads(self):
        for base,field in [('https://api.openai.com/v1','max_completion_tokens')]:
            def handler(request):
                self.assertEqual(str(request.url),base+'/chat/completions')
                payload=json.loads(request.content)
                self.assertEqual(payload[field],1500)
                self.assertNotIn('max_tokens' if field=='max_completion_tokens' else 'max_completion_tokens',payload)
                return httpx.Response(200,json={'choices':[{'message':{'content':'answer'}}],'usage':{'prompt_tokens':5}})
            answer,usage=immediate(complete(FakeClient(handler),base,'test-key','gpt-5.4-mini',[{'role':'user','content':'hello'}],1500))
            self.assertEqual(answer,'answer')
    def test_non_official_endpoint_never_called(self):
        def handler(request): raise AssertionError('Must not send credentials')
        with self.assertRaises(APIError):
            immediate(complete(FakeClient(handler),'https://example.com/v1','test-key','gpt-5.4-mini',[],1500))
    def test_errors_do_not_leak_response(self):
        def handler(request): return httpx.Response(401,text='secret-token')
        with self.assertRaises(APIError) as result:
            immediate(complete(FakeClient(handler),'https://api.openai.com/v1','test-key','gpt-5.4-mini',[],1500))
        self.assertEqual(str(result.exception),'HTTP 401')

if __name__=='__main__': unittest.main()
