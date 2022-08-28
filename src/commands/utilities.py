#!/usr/bin/python
from datetime import datetime, timedelta
from functools import wraps
import functools
import requests
import aiohttp
import logging
import time


def rate_limit(time_gap):
    """
    Decorator that limits how often a user can use
    a function.
    """
    _time = {}

    def rate_decorator(func):
        @wraps(func)
        async def func_wrapper(*args, **kwargs):

            user = args[2]
            # Use the combination of the users name and
            # and function name for the key. Simple way of handling
            # per user per function times.
            hash_key = user + func.__name__
            if hash_key in _time:

                time_diff = time.time() - _time[hash_key]
                if time_diff > time_gap:
                    _time[hash_key] = time.time()
                    return await func(*args, **kwargs)
                else:
                    delta = timedelta(seconds=time_gap - time_diff)
                    time_format = datetime(1, 1, 1) + delta
                    return (
                        "Nice try %s, but I've already done this for you. "
                        "You can ask me again in %s days, %s hours, %s"
                        " minutes and %s seconds."
                    ) % (
                        user,
                        time_format.day - 1,
                        time_format.hour,
                        time_format.minute,
                        time_format.second,
                    )

            else:
                _time[hash_key] = time.time()
                return await func(*args, **kwargs)

        return func_wrapper

    return rate_decorator


def memoize(cache_time):
    """
    Decorator that memoizes the result of the function call
    for the specified time period.
    """
    _cache = {}

    def memoize_decorator(func):
        @wraps(func)
        async def func_wrapper(*args, **kwargs):
            """
            Returns the cached value if it exists and otherwise
            it evalues the function and stores it in the cache.
            no_cache=True can be passed to the function to prevent
            retrieving from the cache.
            """
            no_cache = kwargs.get("no_cache", False)
            if func in _cache and not no_cache:
                stored_time = _cache[func][1]

                if time.time() - stored_time > cache_time:
                    logging.info("cache expired for %s so refilling", func)
                    returned_result = await func(*args, **kwargs)
                    _cache[func] = (returned_result, time.time())

                return _cache[func][0]

            else:
                logging.info("no cache for %s, so cache busting", func)
                returned_result = await func(*args, **kwargs)
                _cache[func] = (returned_result, time.time())
                return returned_result

        return func_wrapper

    return memoize_decorator


_callbacks = {}


def register(command):
    """
    _Registers_ each function with by storing the command its name
    into a dict.
    """

    def decorator(func):
        print("Registering %s with command %s" % (func.__name__, command))
        _callbacks[command] = (func.__qualname__, func.__module__)
        return func

    return decorator


def get_callbacks():
    """
    Simple getter that returns the dictionary containing
    the registered functions. Might be better to make
    registration into a class instead.
    """
    return _callbacks


async def get_request(url, response_headers):
    """
    Wrapper to handle get requests asyncronously.
    Returns the text if the status is 200, False
    otherwise.
    """
    headers = {}
    if response_headers:
        headers = {
            "etag": response_headers["etag"],
            "If-Modified-Since": response_headers["Last-Modified"],
        }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            logging.info("Request response is %s", resp.status)
            if resp.status == 200:
                return await resp.json(), resp.headers
            return False, resp.headers
