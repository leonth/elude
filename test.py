import asyncio
from elude.proxy import ProxyRegistry

proxy_registry = ProxyRegistry()
coros = [proxy_registry.start_getting_proxies()]

def result_cb(result):
    print('--- result: %s' % str(result))
    with open('a.txt', 'w') as fo:
        fo.write(result['result'])

proxy_registry.result_callbacks.append(result_cb)
proxy_registry.put_request({'method': 'fetch', 'params': ['http://leontius.net'], 'id': 'x'})
asyncio.get_event_loop().run_until_complete(asyncio.wait(coros))
asyncio.get_event_loop().run_forever()