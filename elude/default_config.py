
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
