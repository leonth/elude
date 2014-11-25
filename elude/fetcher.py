from collections import OrderedDict
import asyncio
import aiohttp
from elude import config, wait_for_shutdown


class FetchTaskTracker(object):
    def __init__(self, proxy_registry, max_concurrent_conn):
        self.low_prio_tasks = OrderedDict()  # url => params. We use the keys as a deque.
        self.high_prio_tasks = OrderedDict()
        self.cached_results = {}
        self.proxies_used = []  # ids of proxies we are using in this tracker
        self.proxy_registry = proxy_registry
        self.monitor_semaphore = asyncio.Semaphore(max_concurrent_conn)
        self._new_result_event = asyncio.Event()  # Emits whenever there is new result in self.cached_results.

    def prefetch(self, urls, params, high_prio=False):
        task_dict = self.high_prio_tasks if high_prio else self.low_prio_tasks
        for url in urls:
            task_dict[url] = params
            # Remove the task from low priority queue if we put it in the high priority queue.
            if high_prio and url in self.low_prio_tasks:
                del self.low_prio_tasks[url]
        # Get as many new proxies as possible, limited by the number of URLs we want to fetch.
        new_proxies = self.proxy_registry.get_random_proxies(len(urls), self.proxies_used)
        if new_proxies is not None:
            for proxy in new_proxies:
                asyncio.async(self._monitor_tasks_with_proxy(proxy))
        else:
            pass  # TODO: no proxy available!

    @asyncio.coroutine
    def fetch(self, urls, params):
        out = {}
        urls_need_fetching = urls[:]
        while True:
            # For each of the URLs, we first check whether they are already prefetched.
            urls_still_need_fetching = []
            for url in urls_need_fetching:
                if url in self.cached_results:
                    # Cache hit
                    out[url] = self.cached_results[url]
                    # TODO: purge cache
                else:
                    # Cache miss
                    urls_still_need_fetching.append(url)
            # For cache misses, we "prefetch" them in high priority mode, and wait for them to arrive.
            if len(urls_still_need_fetching) > 0:
                self.prefetch(urls_still_need_fetching, params, True)
                urls_need_fetching = urls_still_need_fetching
                print('fetcher: waiting for new result to fetch ', urls_need_fetching)
                yield from self._new_result_event.wait()  # wait for new results coming in and scan the result cache again.
                self._new_result_event.clear()
                print('fetcher: new result available! ', urls_need_fetching)
            else:
                break  # We are ready to return the results.

        return out

    @asyncio.coroutine
    def _monitor_tasks_with_proxy(self, proxy):
        print('fetcher: commissioning proxy ', proxy.id)
        self.proxies_used.append(proxy.id)
        while True:
            with (yield from self.monitor_semaphore):
                task_dict = self.high_prio_tasks if len(self.high_prio_tasks) > 0 else self.low_prio_tasks
                if len(task_dict) > 0:
                    url, params = task_dict.popitem(last=False)
                    result = yield from _fetch_one(url, params, proxy)
                    self.cached_results[url] = result
                    self._new_result_event.set()
                else:
                    # There are no more tasks. End using this proxy. On the next call to prefetch(), this proxy may possibly be used again if proxy_registry.get_random_proxies() returns this proxy again.
                    break
            # TODO: configurable end-of-life for monitor tasks / automatic cycling of proxies?
            if (yield from wait_for_shutdown(config.FETCHER_FETCH_INTERVAL_PER_PROXY)):
                break
        print('fetcher: decommissioning proxy ', proxy.id)
        self.proxies_used.remove(proxy.id)


def _fetch_one(url, params, proxy):
    r = yield from aiohttp.request('get', url, connector=proxy.get_connector())
    text = yield from r.text()
    return {
        'content': text,
        'url': url,
        'status': r.status,  # response HTTP status code
    }
