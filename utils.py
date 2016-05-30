#!/usr/bin/python
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from functools import wraps
import requests
import random
import base64
import yaml
import json
import time
import re


def rate_limit(time_gap):
    '''
    Decorator that limits how often a user can use
    a function.
    '''
    _time = {}

    def rate_decorator(func):
        @wraps(func)
        def func_wrapper(*args, **kwargs):

            user = args[1]
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


def memonize(cache_time):
    '''
    Decorator that memonizes the result of the function call
    for the specified time period.
    '''
    _cache = {}

    def memonize_decorator(func):
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
    return memonize_decorator


class Streams():

    def __init__(self):
        self.file = 'channel.txt'
        self.api_prefix = 'https://api.twitch.tv/kraken/streams/?channel='

    def add_channel(self, channel_name):
        with open(self.file, 'a') as file:
            file.write(' %s ' % channel_name)

    def get_channels(self):
        with open(self.file, 'r') as file:
            return file.read()

    def format_channels(self, payload):
        stream_count = len(payload['streams'])
        if stream_count == 0:
            return 'No streams online'

        message = 'Streams online:'

        for stream in payload['streams']:
            url = stream['channel']['url']
            viewers = stream['viewers']
            title = stream['channel']['status']

            channel_format = ' %s (%s) [%d] |'
            message += channel_format % (url, title, viewers)

        return message

    def display_stream_list(self):
        channels = self.get_channels()
        channel_list = (',').join(channels.split(' '))

        payload = requests.get(self.api_prefix + channel_list)
        if payload.status_code == 200:
            data = json.loads(payload.text)
            return self.format_channels(data)
        else:
            print ('Failed getting steam data with error %s' % payload.text)
            return False


class Frinkiac():

    def __init__(self, config):
        # gif/episode/start_timestamp/end_timestamp.gif?b64lines=caption_in_base64
        self.gif_url = 'https://frinkiac.com/gif/%s/%s/%s.gif'
        self.caption_url = 'https://frinkiac.com/gif/%s/%s/%s.gif?b64lines=%s'
        self.api_url = 'https://frinkiac.com/api/search?q=%s'
        self.interval = 350
        self.max_count = 31
        self.max_timespan = 6200
        self.char_limit = 20

    def get_max_sequence(self, timestamps, debug=False):
        '''
        Helper function that returns the longest consequtive
        sequence of timestamps seperated by at most self.interval
        seconds.
        '''
        total_seqs = []
        current_seq = []
        prev_value = timestamps[0]
        for value in timestamps:
            if value - prev_value > self.interval:
                total_seqs.append(current_seq)
                current_seq = []

            current_seq.append(value)
            prev_value = value
        total_seqs.append(current_seq)

        seq_lens = [len(seq) for seq in total_seqs]
        index = seq_lens.index(max(seq_lens))

        if debug:
            print('Total')
            print(timestamps)
            print('Selected')
            print(total_seqs)

        # Only return up to max count to stay under timelimit.
        return total_seqs[index][:self.max_count]

    def get_episode(self, timestamps, debug=False):
        '''
        Finds the most relevant episode for the given timestamps.
        Current alogrythm works by selecting the episode that
        has the longest sequence of consequtive timestamps
        seperated by self.interval seconds.
        '''
        seq_list = [self.get_max_sequence(sorted(ts))
                    for ep, ts in timestamps.items()]
        seq_len = [len(seq) for seq in seq_list]

        if debug:
            print('seq list')
            print(seq_list)
            print('seq len')
            print(seq_len)
        return list(timestamps)[seq_len.index(max(seq_len))]

    def get_timestamps(self, screencaps, debug=False):
        '''
        Helper function that iterates through the list returned
        by the api endpoint to find the episode and the longest
        sequence of timestamps.
        '''
        episodes = {}
        timestamps = {}

        for screencap in screencaps:
            episode = screencap['Episode']
            timestamp = screencap['Timestamp']

            if episode in episodes:
                episodes[episode] += 1
                timestamps[episode].append(timestamp)
            else:
                episodes[episode] = 1
                timestamps[episode] = [timestamp]

        episode = self.get_episode(timestamps, debug=debug)

        if debug:
            print('epside count')
            print(episodes)
            print(episode)
            print('screencaps')
            print(screencaps)
            print('timestamps')
            print(timestamps)

        max_seq = self.get_max_sequence(sorted(timestamps[episode]),
                                        debug=debug)
        return episode, max_seq

    def format_message(self, message):
        '''
        Formats the message by adding line breaks to prevent it
        from overflowing the gifs boundry. Line breaks are added
        at the end of a word to prevent it from being split.
        '''
        # Iterate thr
        char_buff = 0
        formated_msg = ''
        for word in message:
            char_buff += len(word)
            formated_msg += ' %s' % word
            if char_buff >= 20:
                char_buff = 0
                formated_msg += '/n'

        return formated_msg

    def get_gif(self, caption, text=False, debug=False):
        '''
        Main function that called to retreive a gif url.

        Args:
            caption: The message thats used hit the api endpoint.
            text: Controls wether the generated gif will contain
                  the caption.
        '''
        # Hit the api endpoint to get a list of screencaps
        # that are relevant to the caption.
        response = requests.get(self.api_url % caption)
        screen_caps = json.loads(response.text)

        if debug:
            print('search url')
            print(self.api_url % caption)
            print('response')
            print(screen_caps)

        if len(screen_caps) == 1:
            message = 'Try saying a line that actually exists.'
            return message

        # Find the most common episode and longest sequence of
        # timestamps.
        episode, timestamps = self.get_timestamps(screen_caps, debug=debug)

        seq_length = len(timestamps)
        if seq_length <= 1:
            return 'Try fixing your quote'

        if text:
            # Perform base 64 encoding if a captioned version of the gif was
            # requested.
            # caption = self.format_message(caption)
            encoded = str(base64.b64encode(str.encode(caption)), 'utf-8')
            return self.caption_url % (episode, timestamps[0],
                                       timestamps[-1], encoded)
        else:
            return self.gif_url % (episode, timestamps[0], timestamps[-1])


class Boards():

    def __init__(self):
        self.url = ('http://www.boards.ie/search/submit/'
                    '?forum=1204&subforums=1&sort=newest&date_to=&date_from='
                    '&query=casuals')

    @memonize(60 * 60)
    def get_most_recent_thead(self):
        '''
        Use the search feature to find and return the link
        for the most recent thread that was created.
        '''
        resp = requests.get(self.url)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            return soup.find('div', class_='result_wrapper').find('a').get('href')
        else:
            return False

    @memonize(60 * 15)
    def find_posters(self, thread_url):
        '''
        Returns the names of all the posters in the thread
        as a list of strings.
        '''
        resp = requests.get(thread_url)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            posters = soup.find_all('a', class_='bigusername')

            unique_posters = []
            for poster in posters:
                curr_poster = str(poster.contents[0])

                # remove the <b> and </b> tags if they exist.
                if '<b>' in curr_poster:
                    curr_poster = curr_poster[3:-4]

                if curr_poster not in unique_posters:
                    unique_posters.append(curr_poster)

            return unique_posters
        else:
            return False

    def get_thread_posters(self):
        '''
        Main function thats called when trying to get a list of
        people who have posted in the casuals thread.
        '''
        thread = self.get_most_recent_thead()
        if thread:
            posters = self.find_posters(thread)

            if posters:

                # Return the string after correctly formatting it for
                # the number of posters.
                if len(posters) == 1:
                    formated_str = ('Only %s has posted in the most'
                                    ' recent casuals thread so far.')
                else:
                    formated_str = ['%s, 'for poster in
                                    range(len(posters) - 1)]
                    formated_str = ''.join(formated_str)
                    formated_str += ('and %s have posted in the most recent'
                                     ' casuals thread so far.')

                return formated_str % tuple(posters)
            else:
                return ('Got an error when tryin to get a list of '
                        'posters. :(')
        else:
            return ('Got an error when trying to find the most recent '
                    'thread. :(')


class Arbitary():

    def __init__(self, config):
        self.config = config

    def shuffle(self, sentence, author):
        sentence = re.sub(r'\s\s+', ' ', sentence)
        word_list = sentence.split(' ')

        if word_list == ['']:
            return "Look %s You can't expect me to shuffle nothing." % author
        elif len(word_list) == 1:
            return ('Dont waste my time %s. '
                    'Shuffling 1 word is pointless') % author
        else:
            return random.choice(word_list)

    @rate_limit(60 * 60 * 24)
    def skins(self, author):
        skins_list = yaml.load(open('skins.yaml').read())
        return random.choice(skins_list.split('\n'))
