import random
import json
import logging
import asyncio
import aiohttp
from enum import Enum
from pandas.io.html import read_html

from elude import config, wait_for_shutdown

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)  # tone down asyncio debug messages


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


class TaskPriority(Enum):
    """Priorities used in ProxyRegistry.task_queue. """
    failing_fetch = -3
    failing_prefetch = -2
    failing_neutral = -1
    neutral = 0
    fetch = 1
    prefetch = 2

    @classmethod
    def get_from_method_name(cls, method_name, failing=False):
        return getattr(
            cls,
            ('failing_' if failing else '') + method_name,
            cls.failing_neutral if failing else cls.neutral
        )


class ProxyRegistry(object):
    def __init__(self):
        self.request_queue = asyncio.PriorityQueue()  # Queue of (priority, Request object dict)
        self.result_callbacks = []

    def put_request(self, request_obj, failing=False):
        self.request_queue.put_nowait((
            TaskPriority.get_from_method_name(request_obj.get('method', ''), failing).value,
            request_obj
        ))

    @asyncio.coroutine
    def register_proxy(self, proxy):
        """Register a new proxy. This is where the state machine of the proxy is defined. This coroutine will run indefinitely until the asyncio loop is shut down, or the proxy can't be used anymore.
        Initial state: test if proxy is actually working. Yes: state = healthy, no = terminate usage of the proxy.
        Healthy state: perform fetches. If fetch timeouts or proxy is faulty: state = initial, yes = continue to process tasks.
        """
        while True:
            # Unhealthy state
            with (yield from Proxy.test_semaphore):
                r, r_text = yield from _fetch_one('get', 'http://myexternalip.com/json', config.PROXY_TEST_TIMEOUT, proxy.get_connector())
                if r is None:
                    break  # Terminate usage of the proxy.
                try:
                    ip = (json.loads(r_text)).get('ip', '')
                    if ip != proxy.ip:
                        break  # There is indirection, or the JSON is garbled.
                except ValueError:
                    break  # This proxy is malignant.

            # Healthy state
            logger.debug('%s is healthy' % proxy.id)
            while True:
                yield from asyncio.sleep(0)
                _, request_obj = yield from self.request_queue.get()
                yield from asyncio.sleep(0)
                logger.debug('received request: %s' % str(request_obj))
                smooth_request = yield from self.execute_request(request_obj, proxy)
                if not smooth_request:
                    # This means that the proxy is somehow faulty. Return back the task to the queue and go back to unhealthy state.
                    self.put_request(request_obj, True)
                    break

    @asyncio.coroutine
    def execute_request(self, request_obj, proxy):
        """Executes task based on JSON-RPC 2.0 compatible request/response constructs.
        task_obj is a Request object dict.
        Calls or schedules calls to response callbacks (even for notifications - request id will be None in this case).
        Returns False if error is suspected due to proxy, True otherwise.
        See http://www.jsonrpc.org/specification for specs of the Request and Response objects."""
        rid = request_obj.get('id', None)  # rid None means it is a notification
        try:
            method = request_obj['method']
            if method in ('fetch', 'prefetch'):
                '''Parameters: (url: string)
                '''
                logger.debug('processing request: %s' % str(request_obj))
                r, r_text = yield from _fetch_one('get', request_obj['params'][0], config.FETCHER_TIMEOUT, proxy.get_connector())
                logger.debug('finished request: %s' % (str(request_obj)))
                if r is None:
                    return False
                else:
                    self.process_response({'id': rid, 'result': r_text})
            else:
                self.process_response({'id': rid, 'error': {'code': -32601, 'message': 'Method not found'}})
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.process_response({'id': rid, 'error': {'code': -32000, 'message': '%s: %s' % (type(e).__name__, str(e))}})
        return True

    def process_response(self, response):
        """response is a dict with JSON-RPC Response object structure."""
        #logger.debug('responding with: %s' % str(response))
        for cb in self.result_callbacks:
            cb(response)

    @asyncio.coroutine
    def start_getting_proxies(self):
        # TODO: refactor this to ProxyGatherer
        return asyncio.async(asyncio.gather(self._grab_proxies_from_checkerproxy(), self._grab_proxies_from_letushide()))

    @asyncio.coroutine
    def _grab_proxies_from_checkerproxy(self):
        dfs = yield from _request_and_read_html('http://checkerproxy.net/all_proxy')
        df = dfs[0][['ip:port', 'country', 'proxy type', 'proxy status']]
        df_filtered = df[(df['proxy type'] == 'HTTP') & (df['proxy status'].str.contains('Elite proxy'))].drop_duplicates(subset=['ip:port'])

        logger.info('checkerproxy: testing %d proxies out of %d parsed' % (len(df_filtered), len(df)))
        for _, row in df_filtered.iterrows():
            ip, port = row['ip:port'].split(':')
            asyncio.async(self.register_proxy(Proxy(ip.strip(), port.strip(), row['country'], 'checkerproxy.net')))

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
                asyncio.async(self.register_proxy(Proxy(row['host'], row['port'], None, 'letushide.com')))
            #logger.debug('Finished inserting candidate proxies for letushide')


@asyncio.coroutine
def _fetch_one(method, url, timeout, connector=None):
    try:
        r = yield from asyncio.wait_for(aiohttp.request(method, url, connector=connector), timeout)
        text = yield from r.text()
        return r, text
    except (aiohttp.ConnectionError, aiohttp.ProxyConnectionError, aiohttp.HttpException, asyncio.TimeoutError, ValueError):
        return None, None  # TODO retry attempts


@asyncio.coroutine
def _request_and_read_html(url):
    # TODO cache this call
    r = yield from aiohttp.request('get', url)
    text = yield from r.text()
    dfs = read_html(text)
    return dfs