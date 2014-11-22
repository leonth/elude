import asyncio
import aiohttp
from elude import shutdown
from elude.proxy import ProxyRegistry

if __name__ == '__main__':
    print('Hello')
    registry = ProxyRegistry()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(registry.start_getting_proxies())
    except KeyboardInterrupt:
        shutdown()
