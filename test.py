import json
import asyncio
from elude.servers import BaseServer
from elude.proxy import ProxyGatherer
gatherer = ProxyGatherer()

import logging
logging.basicConfig(level=logging.DEBUG)

class MockServer(BaseServer):
    def process_response(self, response):
        print('--- result: %s' % str(response))
        with open('a.txt', 'w') as fo:
            fo.write(response['result'])
        asyncio.get_event_loop().stop()

server = MockServer(gatherer, json.dumps, json.loads)
server.put_request({'method': 'fetch', 'params': ['http://leontius.net'], 'id': 'x'})
asyncio.get_event_loop().run_until_complete(asyncio.wait([gatherer.start_getting_proxies()]))
asyncio.get_event_loop().run_forever()