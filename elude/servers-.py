import asyncio
from elude import shutdown, config
from elude.proxy import ProxyRegistry
#from elude.fetcher import FetchTaskTracker
import aiozmq
import zmq


class ZmqServer(aiozmq.ZmqProtocol):
    def __init__(self, task_tracker, on_close_future):
        self.on_close_future = on_close_future
        self.task_tracker = task_tracker
        self.transport = None

    def connection_made(self, transport):
        print('-- connection made %s' % transport)
        self.transport = transport

    def msg_received(self, msg):
        print('-- received: %s' % msg)
        ident, _, content = msg  # Structure of a REQ message: identity frame, blank frame, message content

        def write_result(fut):
            print('Writing result: %s' % fut.result())
            self.transport.write([ident, b'', repr(fut.result()).encode('utf8')])

        task = asyncio.async(self.task_tracker.fetch([content.decode('utf8')], {}))
        task.add_done_callback(write_result)

    def connection_lost(self, exc):
        print('-- connection lost %s' % exc)
        self.on_close_future.set_result(exc)


@asyncio.coroutine
def zmq_serve(task_tracker):
    on_close_future = asyncio.Future()
    print('Serving ZeroMQ at %s' % config.SERVER_ZEROMQ_BIND_ADDRESS)
    router, _ = yield from aiozmq.create_zmq_connection(lambda: ZmqServer(task_tracker, on_close_future), zmq.ROUTER, bind=config.SERVER_ZEROMQ_BIND_ADDRESS)
    exc = yield from on_close_future
    print('ZeroMQ: close: ', exc)


if __name__ == '__main__':
    proxy_registry = ProxyRegistry()
    #tracker = FetchTaskTracker(proxy_registry, config.FETCHER_GLOBAL_CONCURRENT_CONN)
    coros = [proxy_registry.start_getting_proxies()] # [ProxyRegistry().start_getting_proxies()]

    #if config.SERVER_ZEROMQ_ENABLE:
    #    coros.append(zmq_serve(tracker))

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.wait(coros))
    except KeyboardInterrupt:
        shutdown()
