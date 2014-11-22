import random
import logging
import asyncio
import aiohttp
from pandas.io.html import read_html

from elude import config, wait_for_shutdown

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.WARNING)  # tone down asyncio debug messages


class Proxy(object):
    test_semaphore = None

    def __init__(self, ip=None, port=None, country=None, source=None):
        self.ip = ip
        self.port = port
        self.country = country
        self.source = source
        self.is_working = False
        if Proxy.test_semaphore is None:
            Proxy.test_semaphore = asyncio.Semaphore(config.PROXY_TEST_MAX_CONCURRENT_CONN)

    @property
    def id(self):
        return '%s:%s' % (self.ip, self.port)

    @asyncio.coroutine
    def test(self):
        #logging.debug('Attempting to start proxy test for %s:%s' % (self.ip, self.port))
        with (yield from Proxy.test_semaphore):
            try:
                #logging.debug('Starting proxy test for %s:%s' % (self.ip, self.port))
                conn = aiohttp.ProxyConnector(proxy='http://%s:%s' % (self.ip, self.port))
                r = yield from asyncio.wait_for(aiohttp.request('head', config.PROXY_TEST_URL, connector=conn), config.PROXY_TEST_TIMEOUT)
                if r.status == 200:
                    self.is_working = True
                    return True

            except (aiohttp.ConnectionError, aiohttp.ProxyConnectionError, aiohttp.HttpException, asyncio.TimeoutError, ValueError):
                self.is_working = False
        return False


class ProxyRegistry(object):
    def __init__(self):
        self.proxies = {}

    @asyncio.coroutine
    def add_proxy(self, proxy):
        if (yield from proxy.test()):
            self.proxies[proxy.id] = proxy
            asyncio.async(self._monitor_proxy(proxy))

    def _remove_proxy(self, proxy):
        del self.proxies[proxy.id]

    @asyncio.coroutine
    def _monitor_proxy(self, proxy):
        print('Starting to monitor ' + proxy.id)
        while True:
            if (yield from wait_for_shutdown(config.PROXY_HEARTBEAT)):
                return
            if not proxy.test():
                self._remove_proxy(proxy)  # TODO: give it one more chance to retry?
                return

    @asyncio.coroutine
    def get_random_proxies(self, max_k, blacklist_ids=None):
        proxies = self.proxies
        if blacklist_ids:
            proxies = {k: v for k, v in proxies.items() if k not in blacklist_ids}
        if len(proxies) == 0:
            return None  # TODO: wait for new proxies, and then return the new ones
        else:
            return random.sample(proxies.values(), max_k)

    @asyncio.coroutine
    def start_getting_proxies(self):
        @asyncio.coroutine
        def grab_then_monitor(coro):
            while True:
                try:
                    task = yield from asyncio.wait_for(coro, 60)
                except asyncio.TimeoutError:
                    pass
                if (yield from wait_for_shutdown(config.PROXY_REFRESH_LIST_INTERVAL)):  # refresh
                    return

        return asyncio.async(asyncio.wait([grab_then_monitor(self._grab_proxies_from_checkerproxy()), grab_then_monitor(self._grab_proxies_from_letushide())]))

    @asyncio.coroutine
    def _grab_proxies_from_checkerproxy(self):
        dfs = yield from _request_and_read_html('http://checkerproxy.net/all_proxy')
        df = dfs[0][['ip:port', 'country', 'proxy type', 'proxy status']]
        df_filtered = df[(df['proxy type'] == 'HTTP') & (df['proxy status'].str.contains('Elite proxy'))].drop_duplicates(subset=['ip:port'])

        logging.info('checkerproxy: testing %d proxies out of %d parsed' % (len(df_filtered), len(df)))
        for _, row in df_filtered.iterrows():
            ip, port = row['ip:port'].split(':')
            asyncio.async(self.add_proxy(Proxy(ip.strip(), port.strip(), row['country'], 'checkerproxy.net')))

    @asyncio.coroutine
    def _grab_proxies_from_letushide(self):
        last_page_indicator = ''  # keep track of port:ip of the first proxy. if it is the same as that of the page before, we must be at the last page.
        for page_num in range(1, 21):  # try until max of 20 pages
            dfs = yield from _request_and_read_html('http://letushide.com/filter/http,hap,all/%d/list_of_free_HTTP_High_Anonymity_proxy_servers' % page_num)
            #logging.info(dfs[1])
            df = dfs[1]
            page_indicator = '%s:%s' % (df.loc[0, 'host'], df.loc[0, 'port'])
            if last_page_indicator == page_indicator:
                logging.debug('letushide terminates at page %d' % (page_num-1))
                break
            last_page_indicator = page_indicator
            logging.info('letushide: testing %d proxies coming from page %d' % (len(df), page_num))
            for _, row in df.iterrows():
                asyncio.async(self.add_proxy(Proxy(row['host'], row['port'], None, 'letushide.com')))
            #logging.debug('Finished inserting candidate proxies for letushide')


@asyncio.coroutine
def _request_and_read_html(url):
    # TODO cache this call
    r = yield from aiohttp.request('get', url)
    text = yield from r.text()
    dfs = read_html(text)
    return dfs