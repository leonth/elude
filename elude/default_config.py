
PROXY_TEST_MAX_CONCURRENT_CONN = 20
PROXY_TEST_URL = 'http://finance.yahoo.com'
PROXY_TEST_TIMEOUT = 10  # timeout for proxy tests in seconds
PROXY_HEARTBEAT = 120  # interval between periodical check of proxies in seconds
PROXY_REFRESH_LIST_INTERVAL = 300  # interval between refreshing list of proxies from proxy websites in seconds

FETCHER_FETCH_INTERVAL_PER_PROXY = 3  # interval between fetches for one proxy in seconds
FETCHER_GLOBAL_CONCURRENT_CONN = 1000  # maximum number of concurrent outgoing connections globally
FETCHER_TIMEOUT = 20

STDIO_ENABLE = True  # receive commands via stdin and send responses to stdout

SERVER_WEBSOCKET_ENABLE = True
SERVER_WEBSOCKET_HOST = 'localhost'
SERVER_WEBSOCKET_PORT = '7654'

SERVER_ZEROMQ_ENABLE = True
SERVER_ZEROMQ_BIND_ADDRESS = 'ipc:///tmp/python-elude'

SERVER_REDIS_ENABLE = True
SERVER_REDIS_HOST = 'localhost'
SERVER_REDIS_PORT = 6379
SERVER_REDIS_PASSWORD = None
SERVER_REDIS_DB = 0
SERVER_REDIS_REQUEST_KEY = 'elude:request'  # The key of the list in Redis to monitor for new tasks.
SERVER_REDIS_RESPONSE_KEY_PREFIX = 'elude:result:'  # Responses are pushed in a list with this prefix + request ID.
