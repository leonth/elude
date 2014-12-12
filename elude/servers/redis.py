import asyncio
import asyncio_redis
from elude import config
from elude.servers import BaseServer

REDIS_REQUEST_WIP_KEY = '_elude:request_wip'


class RedisServer(BaseServer):
    def __init__(self, proxy_gatherer, serialize_func, deserialize_func):
        super().__init__(proxy_gatherer)
        self.serialize = serialize_func
        self.deserialize = deserialize_func
        self._request_cache = {}
        self._conn = None

    @asyncio.coroutine
    def connect(self):
        if self._conn is None:
            self._conn = yield from asyncio_redis.Pool.create(host=config.SERVER_REDIS_HOST, port=config.SERVER_REDIS_PORT, password=config.SERVER_REDIS_PASSWORD, db=config.SERVER_REDIS_DB, poolsize=3)
        return self._conn

    @asyncio.coroutine
    def serve(self):
        conn = yield from self.connect()
        while True:
            request_obj_raw = yield from conn.brpoplpush(config.SERVER_REDIS_REQUEST_KEY, REDIS_REQUEST_WIP_KEY)
            try:
                request_obj = self.deserialize(request_obj_raw)
                self.put_request(request_obj)
            except ValueError:
                self.process_response({'id': None, 'error': {'code': -32700, 'message': 'Parse error'}})
        conn.close()

    def process_response(self, result):
        @asyncio.coroutine
        def really_process():
            conn = yield from self.connect()
            yield from conn.lpush(config.SERVER_REDIS_RESPONSE_KEY_PREFIX + str(result['id']), [self.serialize(result)])
            #yield from self.conn.lrem(REDIS_REQUEST_WIP_KEY, , -1)

        asyncio.async(really_process())