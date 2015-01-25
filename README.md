elude
=====

**This is alpha quality software, use at your own risk.**

[`elude`](https://github.com/leonth/elude) helps you download web pages quickly and anonymously for further processing e.g. scraping. The initial groundwork was inspired by [Elite Proxy Finder](https://github.com/DanMcInerney/elite-proxy-finder) project which attempted to find elite anonymous proxies. `elude` builds upon this idea to provide a daemon that automatically finds these proxies and uses them to perform requests. It uses the [`asyncio`](https://docs.python.org/3/library/asyncio.html) module extensively for handling concurrent connections.

For now, it provides the following:

* Grabs proxies from [letushide](http://letushide.com) and [checkerproxy](http://checkerproxy.net) and performs regular test requests to make sure that they are still alive.
* Merges requests to the same URL so the target server only gets one request.
* Caches results in-memory to satisfy requests to the same URL (cache expiry is configurable).
* Prefetch feature where URLs can be queued to be requested and cached in the background and then retrieved on-demand later.
* Interface using pure Python (Python 3 only) and Redis.

The aim is to make this usable within [Apache Spark](http://spark.apache.org/) jobs. The Spark driver program can first send prefetch requests to `elude` daemon, and then the real Spark jobs can query the daemon in real-time as necessary. This enables Apache Spark to perform jobs directly on the downloaded data but it won't be limited to one request per worker thread/process.

Planned future improvements
===========================

* Documentation!
* Also fake user agent strings.
* Deposit fetched results to databases.
* Support for binary data and other mimetypes.

