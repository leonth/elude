import json
from enum import Enum
import asyncio
import logging
from elude import config
from elude import fetch_one
from elude.proxy import Proxy

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Priorities used in ProxyRegistry.task_queue. (Byte-to-byte comparison will be used)"""
    failing_fetch = 'a'
    failing_prefetch = 'b'
    failing_neutral = 'c'
    neutral = 'd'
    fetch = 'e'
    prefetch = 'f'

    @classmethod
    def get_from_method_name(cls, method_name, failing=False):
        return getattr(
            cls,
            ('failing_' if failing else '') + method_name,
            cls.failing_neutral if failing else cls.neutral
        )


class BaseServer(object):
    def __init__(self, proxy_gatherer, serialize_func, deserialize_func):
        self.request_queue = asyncio.PriorityQueue()  # Queue of (priority, Request object dict)
        self.serialize = serialize_func
        self.deserialize = deserialize_func
        self.proxy_gatherer = proxy_gatherer
        # make a local copy of the configs
        self.config = dict((k, getattr(config, k)) for k in dir(config) if not k.startswith('__'))
        proxy_gatherer.new_proxy_callbacks.append(lambda proxy: asyncio.async(self.register_proxy(proxy)))

    def put_request(self, request_obj, failing=False):
        """Puts a request object in the queue for further processing."""
        # asyncio.PriorityQueue() can't accept items with same priority (it will try to compare the request_obj instead of the priority). Therefore we make the priority unique.
        priority = '%s%d' % (TaskPriority.get_from_method_name(request_obj.get('method', ''), failing).value, id(request_obj))
        self.request_queue.put_nowait((
            priority,
            request_obj
        ))

    @asyncio.coroutine
    def register_proxy(self, proxy):
        """Register a new proxy. This is where the state machine of the proxy is defined. This coroutine will run indefinitely until the asyncio loop is shut down, or the proxy can't be used anymore.
        Initial state: test if proxy is actually working. Yes: state = healthy, no = terminate usage of the proxy.
        Healthy state: perform fetches. If fetch timeouts or proxy is faulty: state = initial, yes = continue to process tasks.
        """
        #logger.debug('Registering new proxy %s' % proxy.id)
        while True:
            # Unhealthy state
            with (yield from Proxy.test_semaphore):
                r, r_text = yield from fetch_one('get', 'http://myexternalip.com/json', self.config['PROXY_TEST_TIMEOUT'],
                                                 proxy.get_connector())
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
                #yield from asyncio.sleep(0)
                logger.debug('received request: %s' % str(request_obj))
                smooth_request = yield from self.process_request(request_obj, proxy)
                if not smooth_request:
                    # This means that a retry is warranted (e.g. the proxy is somehow faulty). Return back the task to the queue and go back to unhealthy state.
                    self.put_request(request_obj, True)
                    break

    @asyncio.coroutine
    def process_request(self, request_obj, proxy):
        """Executes task based on JSON-RPC 2.0 compatible request/response constructs.
        task_obj is a Request object dict.
        Calls or schedules calls to response callbacks (even for notifications - request id will be None in this case).
        Returns False if a retry is warranted, True otherwise.
        See http://www.jsonrpc.org/specification for specs of the Request and Response objects."""
        rid = request_obj.get('id', None)  # rid None means it is a notification
        retval = True
        try:
            method_name = '_process_request_%s' % request_obj.get('method', '')
            if hasattr(self, method_name):
                retval = yield from getattr(self, method_name)(proxy, **request_obj['params'])
            else:
                self.process_response({'id': rid, 'error': {'code': -32601, 'message': 'Method not found'}})
        except Exception as e:
            import traceback

            traceback.print_exc()
            self.process_response(
                {'id': rid, 'error': {'code': -32000, 'message': '%s: %s' % (type(e).__name__, str(e))}})
        return retval

    def process_response(self, response):
        """response is a dict with JSON-RPC Response object structure.
        Override this method to process responses."""
        pass

    @asyncio.coroutine
    def _process_request_fetch(self, proxy, rid=None, url=''):
        logger.debug('processing request: rid = %s url=%s' % (str(rid), url))
        r, r_text = yield from fetch_one('get', url, self.config['FETCHER_TIMEOUT'],
                                         proxy.get_connector())
        logger.debug('processing request: rid = %s url=%s' % (str(rid), url))
        if r is None:
            return False
        else:
            self.process_response({'id': rid, 'result': r_text})
            return True

    @asyncio.coroutine
    def _process_request_prefetch(self, proxy, rid=None, url=''):
        # Note difference between this and fetch is just the priority. Priority calculation is done at put_request().
        return (yield from self._process_request_fetch(proxy, rid, url))

    @asyncio.coroutine
    def _process_request_update_config(self, proxy, config, rid=None):
        self.config.update(config)  # TODO: validate input
        return True
