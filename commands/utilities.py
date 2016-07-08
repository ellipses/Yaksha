#!/usr/bin/python
from datetime import datetime, timedelta
from functools import wraps
import aiohttp
import time



def rate_limit(time_gap):
    '''
    Decorator that limits how often a user can use
    a function.
    '''
    _time = {}

    def rate_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):

            user = args[2]
            # Use the combination of the users name and
            # and function name for the key. Simple way of handling
            # per user per function times.
            hash_key = user + func.__name__
            if hash_key in _time:

                time_diff = time.time() - _time[hash_key]
                if time_diff > time_gap:
                    _time[hash_key] = time.time()
                    return func(*args, **kwargs)
                else:
                    delta = timedelta(seconds=time_gap - time_diff)
                    time_format = datetime(1, 1, 1) + delta
                    return ("Nice try %s, but I've already done this for you. "
                            'You can ask me again in %s days, %s hours, %s'
                            ' minutes and %s seconds.') % (user,
                                                           time_format.day - 1,
                                                           time_format.hour,
                                                           time_format.minute,
                                                           time_format.second
                                                           )

            else:
                _time[hash_key] = time.time()
                return func(*args, **kwargs)

        return func_wrapper
    return rate_decorator


def memoize(cache_time):
    '''
    Decorator that memoizes the result of the function call
    for the specified time period.
    '''
    _cache = {}

    def memoize_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):
            if func in _cache:
                stored_time = _cache[func][1]

                if time.time() - stored_time > cache_time:
                    returned_result = func(*args, **kwargs)
                    _cache[func] = (returned_result, time.time())

                return _cache[func][0]

            else:
                returned_result = func(*args, **kwargs)
                _cache[func] = (returned_result, time.time())
                return returned_result

        return func_wrapper
    return memoize_decorator


async def get_request(url):
    '''
    Wrapper to handle get requests asyncronously.
    Returns the text if the status is 200, False
    otherwise.
    '''
    response = ''
    with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                response = await resp.text()
            else:
                response == False
    return response