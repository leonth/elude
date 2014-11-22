import asyncio

try:
    import elude.config as config
except ImportError:
    import elude.default_config as config

_global_shutdown_event = asyncio.Event()


@asyncio.coroutine
def wait_for_shutdown(timeout):
    """Yields True if system is shutting down, False otherwise."""
    try:
        yield from asyncio.wait_for(_global_shutdown_event.wait(), timeout)
        return _global_shutdown_event.is_set()
    except asyncio.TimeoutError:
        return False


def shutdown():
    _global_shutdown_event.set()
