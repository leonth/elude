import logging
import asyncio
import aiohttp
from enum import Enum
from pandas.io.html import read_html

from elude import config


logger = logging.getLogger(__name__)


class Proxy(object):
    test_semaphore = None

    def __init__(self, ip=None, port=None, country=None, source=None):
        self.ip = ip
        self.port = port
        self.country = country
        self.source = source
        self._connector = None
        if Proxy.test_semaphore is None:
            Proxy.test_semaphore = asyncio.Semaphore(config.PROXY_TEST_MAX_CONCURRENT_CONN)

    @property
    def id(self):
        return '%s:%s' % (self.ip, self.port)

    def get_connector(self):
        if self._connector is None:
            self._connector = aiohttp.ProxyConnector(proxy='http://%s:%s' % (self.ip, self.port))
        return self._connector


class ProxyGatherer(object):
    def __init__(self):
        self.new_proxy_callbacks = []

    @asyncio.coroutine
    def start_getting_proxies(self):
        return asyncio.async(asyncio.gather(self._grab_proxies_from_checkerproxy(), self._grab_proxies_from_letushide()))

    @asyncio.coroutine
    def _grab_proxies_from_checkerproxy(self):
        dfs = yield from _request_and_read_html('http://checkerproxy.net/all_proxy')
        df = dfs[0][['ip:port', 'country', 'proxy type', 'proxy status']]
        df_filtered = df[(df['proxy type'] == 'HTTP') & (df['proxy status'].str.contains('Elite proxy'))].drop_duplicates(subset=['ip:port'])

        logger.info('checkerproxy: testing %d proxies out of %d parsed' % (len(df_filtered), len(df)))
        for _, row in df_filtered.iterrows():
            ip, port = row['ip:port'].split(':')
            self.register_proxy(Proxy(ip.strip(), port.strip(), row['country'], 'checkerproxy.net'))

    @asyncio.coroutine
    def _grab_proxies_from_letushide(self):
        last_page_indicator = ''  # keep track of port:ip of the first proxy. if it is the same as that of the page before, we must be at the last page.
        for page_num in range(1, 21):  # try until max of 20 pages
            dfs = yield from _request_and_read_html('http://letushide.com/filter/http,hap,all/%d/list_of_free_HTTP_High_Anonymity_proxy_servers' % page_num)
            #logger.info(dfs[1])
            df = dfs[1]
            page_indicator = '%s:%s' % (df.loc[0, 'host'], df.loc[0, 'port'])
            if last_page_indicator == page_indicator:
                logger.debug('letushide terminates at page %d' % (page_num-1))
                break
            last_page_indicator = page_indicator
            logger.info('letushide: testing %d proxies coming from page %d' % (len(df), page_num))
            for _, row in df.iterrows():
                self.register_proxy(Proxy(row['host'], row['port'], None, 'letushide.com'))
            #logger.debug('Finished inserting candidate proxies for letushide')

    def register_proxy(self, proxy):
        for cb in self.new_proxy_callbacks:
            if asyncio.iscoroutine(cb) or asyncio.iscoroutinefunction(cb):
                asyncio.async(cb(proxy))
            else:
                cb(proxy)


@asyncio.coroutine
def _request_and_read_html(url):
    # TODO cache this call
    r = yield from aiohttp.request('get', url)
    text = yield from r.text()
    dfs = read_html(text)
    return dfs