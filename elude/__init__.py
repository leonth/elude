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
        r = yield from asyncio.wait_for(aiohttp.request(method, url, allow_redirects=True, connector=connector), timeout)
        if r.status == 200:
            text = yield from r.text()
            return r, text
        else:
            return None, None
    except (aiohttp.ClientError, aiohttp.ProxyConnectionError, asyncio.TimeoutError, ValueError):
        return None, None  # TODO retry attempts
