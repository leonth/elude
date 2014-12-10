import logging
import asyncio
import aiohttp

try:
    import elude.config as config
except ImportError:
    import elude.default_config as config

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)  # tone down asyncio debug messages


@asyncio.coroutine
def fetch_one(method, url, timeout, connector=None):
    try:
        r = yield from asyncio.wait_for(aiohttp.request(method, url, connector=connector), timeout)
        text = yield from r.text()
        return r, text
    except (aiohttp.ConnectionError, aiohttp.ProxyConnectionError, aiohttp.HttpException, asyncio.TimeoutError, ValueError):
        return None, None  # TODO retry attempts
