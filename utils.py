#!/usr/bin/python
from dateparser.date import DateDataParser
from datetime import datetime, timedelta
from fuzzywuzzy import process
from bs4 import BeautifulSoup
from functools import wraps
import requests
import asyncio
import random
import base64
import yaml
import json
import time
import re
import os


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


class Streams():

    def __init__(self):
        self.file = 'channel.txt'
        self.api_prefix = 'https://api.twitch.tv/kraken/streams/?channel='

    def add_channel(self, msg, user):
        with open(self.file, 'a') as file:
            file.write(' %s ' % msg)
        return 'Added channel %s' % msg

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

    def display_stream_list(self, msg, user):
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

    def __init__(self, config={}):
        # gif/episode/start_timestamp/end_timestamp.gif?b64lines=caption_in_base64
        self.gif_url = 'https://frinkiac.com/gif/%s/%s/%s.gif'
        self.caption_url = 'https://frinkiac.com/gif/%s/%s/%s.gif?b64lines=%s'
        self.api_url = 'https://frinkiac.com/api/search?q=%s'
        self.interval = 500
        self.max_count = 31
        self.max_timespan = 6800
        self.char_limit = 20
        self.extend_regex = r'^-ex(\d?\.?\d?)?'
        self.max_extend = 6.9

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
        for word in message.split(' '):
            char_buff += len(word)
            formated_msg += ' %s' % word
            if char_buff >= 20:
                char_buff = 0
                formated_msg += '/n'

        return formated_msg

    def handle_caption(self, caption):
        '''
        '''
        extend = False
        extend_amount = self.max_extend
        result = re.search(self.extend_regex, caption)
        caption = re.sub(self.extend_regex, '', caption).strip()
        # Matched an extend command at the start
        if result:
            extend = True
            # Matched a value attached to extend
            if result.group(1):
                extend_value = float(result.group(1))

                # Only change the default extend value if they passed in
                # valid values.
                if extend_value <= self.max_extend and extend_value > 0:
                    extend_amount = extend_value

        # Hit the api endpoint to get a list of screencaps
        # that are relevant to the caption.
        response = requests.get(self.api_url % caption)
        screen_caps = json.loads(response.text)

        if len(screen_caps) <= 1:
            return False

        # Find the most common episode and longest sequence of
        # timestamps.
        episode, timestamps = self.get_timestamps(screen_caps)

        seq_length = len(timestamps)
        if seq_length <= 1:
            return False

        if extend:
            # Convert it to seconds and cast to int to truncate
            # decimal values.
            extend_amount = int(extend_amount * 1000)
            # Make sure we stay under the gif time limit
            # even after extending.
            difference = timestamps[-1] - timestamps[0]
            extendable_amount = self.max_timespan - difference

            if extend_amount > extendable_amount:
                extend_amount = extendable_amount

            timestamps[-1] = timestamps[-1] + extend_amount

        return (episode, timestamps, caption)

    def get_gif(self, caption, user, text=False):
        '''
        Main function that called to retreive a gif url.

        Args:
            caption: The message thats used hit the api endpoint.
            text: Controls wether the generated gif will contain
                  the caption.
        '''
        resp = self.handle_caption(caption)
        if not resp:
            return 'Try fixing your quote.'
        episode, timestamps, caption = resp
        return self.gif_url % (episode,
                               timestamps[0], timestamps[-1])

    def get_captioned_gif(self, caption, user):
        '''
        '''
        resp = self.handle_caption(caption)
        if not resp:
            return 'Try fixing your quote.'

        episode, timestamps, caption = resp
        # caption = self.format_message(caption)
        try:
            encoded = str(base64.b64encode(str.encode(caption)), 'utf-8')
        except TypeError:
            encoded = str(base64.b64encode(str.encode(caption)))
        return self.caption_url % (episode, timestamps[0],
                                   timestamps[-1], encoded)


class Boards():

    def __init__(self):
        self.url = ('http://www.boards.ie/vbulletin/forumdisplay.php?f=1204')

    @memoize(60 * 60)
    def get_most_recent_thead(self, nocache=False):
        '''
        Use the search feature to find and return the link
        for the most recent thread that was created.
        '''
        resp = requests.get(self.url)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')


            # Find the second tbody which containts the threads
            threads = soup.findAll('tbody')[1].findAll('tr')

            for thread in threads:
                thread_titles = thread.find('div').find('a')
                title = thread_titles.contents[0]
                if 'casual' in title.lower():
                    href = thread_titles.get('href')
                    link = 'http://www.boards.ie/vbulletin/%s' % href
                    return link
        else:
            return False

    @memoize(60 * 15)
    def find_posters(self, thread_url, nocache=False):
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

    def get_thread_posters(self, *args, **kwargs):
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

                formated_str = formated_str % tuple(posters)
                formated_str += ' %s ' % thread
                return formated_str
            else:
                return ('Got an error when tryin to get a list of '
                        'posters. :(')
        else:
            return ('Got an error when trying to find the most recent '
                    'thread. :(')


class Arbitary():

    def __init__(self, config={}):
        self.config = config
        self.tourney_url = 'http://shoryuken.com/tournament-calendar/'
        self.history_limit = 500

    def shuffle(self, sentence, author):
        '''
        '''
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
    def skins(self, message, author):
        '''
        '''
        skins_list = yaml.load(open('skins.yaml').read())
        return random.choice(skins_list.split('\n'))

    def convert_times(self, times):
        new_times = []
        for prev_time in times:
            new_time = (prev_time[3:5] + '/' + prev_time[:2] +
                        ' - ' + prev_time[11:] + '/' + prev_time[8:10])
            new_times.append(new_time)
        return new_times

    def remove_older_months(self, tourney_list):
        '''
        Deletes every month previous of the current one
        from the tourney_list.
        '''
        # Find the current month.
        current_month = datetime.now().month
        month_index = 0
        for index in range(len(tourney_list)):
            tourney = tourney_list[index]
            first_date = tourney[1].contents[0]
            if current_month == int(first_date[:2]):
                month_index = index
                break
        del tourney_list[:month_index]
        return tourney_list

    def remove_older_days(self, tourney_list):
        '''
        Deletes every tourney entry from the current month
        whos starting date was before today.
        '''
        curr_day = datetime.now().day
        day_index = 0
        for days in tourney_list[0][1::4]:
            date = days.contents[0]
            if int(date[3:5]) > curr_day:
                break
            day_index += 1

        del tourney_list[0][:day_index * 4]
        return tourney_list

    @memoize(60 * 60 * 24)
    def get_tourneys(self, message, author):
        '''
        Uses the list of tournaments on the srk page
        to return the upcomming tournaments.
        '''
        resp = requests.get(self.tourney_url)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            soup = soup.find_all('tbody')
            tourney_list = [month.find_all('td') for month in soup]

            tourney_list = self.remove_older_months(tourney_list)
            tourney_list = self.remove_older_days(tourney_list)
            # Only care about first two months.
            tourneys = tourney_list[0] + tourney_list[1]
            # Only get the first 5 if there are more than 5.
            if len(tourneys) > 20:
                tourneys = tourneys[:20]

            # Create lists of tourneys
            tourney_list = [tourney.contents[0] for tourney in tourneys]
            # Delete the links
            del tourney_list[3::4]

            # Convert the time format
            names = [time for time in tourney_list[0::3]]
            times = [time for time in tourney_list[1::3]]
            locations = [time for time in tourney_list[2::3]]

            times = self.convert_times(times)
            formated_tourneys = tuple(zip(names, times, locations))
            formated_str = ''.join([' %s (%s) [%s]  |  ' % tourney for
                                    tourney in formated_tourneys])

            return 'The upcoming tourneys are ' + formated_str[:-4]
        else:
            return ('Got %s when trying to get list of'
                    ' tourneys') % resp.status_code

    async def get_my_mention(self, message, user, channel, client):
        '''
        Shows the last message in the channel that mentioned the user
        that uses this command.
        '''
        found = False
        async for message in client.logs_from(channel,
                                              limit=self.history_limit):
            if user in message.content:
                await client.send_message(channel, message.content)
                found = True
                break

        if not found:
            response = ('Sorry %s, I could not find any mention of you in'
                        ' the last %s messages of this channel.') % (user, self.history_limit)
            await client.send_start_message(channel, 'not found')


class Gifs():

    def __init__(self):
        self.search_url = ('http://api.giphy.com/v1/gifs/search?q='
                           '%s&api_key=dc6zaTOxFJmzC')
        self.translate_url = ('http://api.giphy.com/v1/gifs/translate?s='
                              '%s&api_key=dc6zaTOxFJmzC')

    def get_gif(self, quote, author):
        query = '+'.join(quote.split(' '))
        resp = requests.get(self.search_url % query)

        if resp.status_code == 200:
            gifs = resp.json()['data'][:5]
            if len(gifs) == 0:
                return "Sorry %s I could not find any gifs using that keyword :( ." % author
            urls = [gif['url'] for gif in gifs]
            return random.choice(urls)
        else:
            return 'Got an error when searching for gifs :('

    def get_translate_gif(self, quote, author):
        query = '+'.join(quote.split(' '))
        resp = requests.get(self.translate_url % query)

        if resp.status_code == 200:
            return resp.json()['data']['url']
        else:
            return ('Got an error when trying find a translate gif :(.'
                    ' What does this even do anyway')


class Frames():

    def __init__(self, config={}):
        self.url = config['url']
        self.regex = r'(^\S*)\s*(vtrigger|vt)?\s+(.+)'
        self.char_ratio_thresh = 65
        self.move_ratio_thresh = 65
        self.short_mapping = {'cr': 'crouch ',
                              'st': 'stand ',
                              'jp': 'jump '}
        self.short_regex = r'(^cr(\s|\.))|(^st(\s|\.))|(^jp(\s|\.))'
        self.output_format = ('%s - (%s) - [Startup]: %s [Active]: %s [Recovery]: %s '
                              '[On Hit]: %s [On Block]: %s')

    @memoize(60 * 60 * 24 * 7)
    def get_data(self):
        '''
        Simple helper function that hits the frame data dump
        endpoint and returns the contents in json format.
        '''
        resp = requests.get(self.url)
        if resp.status_code == 200:
            return json.loads(resp.text)
        else:
            return False

    @memoize(60 * 60 * 24 * 7)
    def add_reverse_mapping(self, data):
        '''
        Create a reverse mapping between common names,
        move command and the actual name of the moves.
        Increases the time on the first queury but the result
        is cached for subsequent ones.
        '''
        common_name_dict = {}
        commands_dict = {}
        for char in data.keys():
            char_moves = data[char]['moves']['normal']
            for move in char_moves:
                # Add the common name of the move to the dict.
                try:
                    common_name = char_moves[move]['commonName']
                    common_name_dict[common_name] = move
                # Some moves dont have common name so just pass.
                except KeyError:
                    pass
                command = char_moves[move]['plainCommand']
                commands_dict[command] = move

            common_name_dict.update(commands_dict)
            data[char]['reverse_mapping'] = common_name_dict
            # Also add a set of keys/values with official name
            offical_names = dict(zip(char_moves.keys(), char_moves.keys()))
            data[char]['reverse_mapping'].update(offical_names)
            common_name_dict = {}
            commands_dict = {}

    def match_move(self, char, move, vt, data):
        '''
        Main helper function that handles matching the move.
        Uses the reverse mapping of the common name, input command
        and short form converter to increase the chances of a better
        match.
        '''
        # First find the char they want.
        char_match, char_ratio = process.extractOne(char,
                                                    data.keys())
        if char_ratio < self.char_ratio_thresh:
            return False

        # They might have supplied the move name in shortened format
        # so convert it to how the frame data dump expects.
        result = re.search(self.short_regex, move)
        if result:
            matched = result.group(0)
            move = re.sub(matched, self.short_mapping[matched[:-1]], move)

        # Use the reverse mapping to determine which move they
        # were looking for.
        moves = data[char_match]['reverse_mapping']
        move_match, move_ratio = process.extractOne(move, moves.keys())

        if move_ratio < self.move_ratio_thresh:
            return False

        move = data[char_match]['reverse_mapping'][move_match]

        # Next find the move they want.
        if vt:
            # The move might not have any difference in vtrigger
            # so just return the normal version.
            try:
                move_data = data[char_match]['moves']['vtrigger'][move]
            except KeyError:
                move_data = data[char_match]['moves']['normal'][move]
        else:
            move_data = data[char_match]['moves']['normal'][move]

        return char_match, move, move_data

    def format_output(self, char, move, vt, data):
        '''
        Formats the msg to a nicely spaced string for
        presentation.
        '''
        output = self.output_format % (char, move,
                                       data['startup'], data['active'],
                                       data['recovery'], data['onHit'],
                                       data['onBlock'])
        return output

    def get_frames(self, msg, user):
        '''
        Main function thats called for the frame data function.
        Currently works only for SFV data thanks to Pauls nicely
        formatted data <3.
        '''
        result = re.search(self.regex, msg)
        if not result:
            return ("You've passed me an incorrect format %s. "
                    "The correct format is !frames character_name "
                    "[vtrigger] move_name") % user

        char_name = result.group(1)
        move_name = result.group(3)
        if result.group(2):
            vtrigger = True
        else:
            vtrigger = False

        frame_data = self.get_data()
        if not frame_data:
            return 'Got an error when trying to get frame data :(.'
        else:
            result = re.search(self.regex, msg)
            self.add_reverse_mapping(frame_data)

        matched_value = self.match_move(char_name, move_name,
                                        vtrigger, frame_data)
        if not matched_value:
            return ("Don't waste my time %s. %s with %s is not a valid "
                    "character/move combination for SFV.") % (user,
                                                              char_name,
                                                              move_name)
        else:
            char, move, data = matched_value
            return self.format_output(char, move, vtrigger, data)


class AddCommands():

    def __init__(self, config={}):
        self.file = config['file']

    def save_command(self, command, actions):
        with open(self.file, 'a') as file:
            json.dump({command: actions}, file)
            file.write(os.linesep)
        return True

    def load_command(self, msg):
        '''
        switch to read indead to readlines.stoping in memeory bad when too big
        '''
        with open(self.file, 'r') as file:
            command_list = file.readlines()

        for command in command_list:
            saved_cmd = json.loads(command)

            for cmd in saved_cmd:
                if cmd == msg:
                    value = saved_cmd[cmd]
                    if len(value) > 1:
                        return random.choice(value)
                    else:
                        return value[0]
        return False

    def get_command(self, msg, user):
        '''
        '''
        # They might've sent multiple commands but
        # we only care about the first one.
        cmd = msg.split(' ')[0]
        resp = self.load_command(cmd)
        if resp:
            return resp
        else:
            return 'I am too sleepy to write reasonable error message, just stop doing wrong things.'

    def add_command(self, msg, user):
        '''
        Main function that called when a user
        tries to add a new command.
        '''
        split_msg = msg.split(' ')
        command = split_msg[0]
        actions = split_msg[1:]
        if self.save_command(command, actions):
            return 'The command %s has been added.' % command
        else:
            return 'some error check traceback, too sleepy to write sensible error message'


class Voting():

    def __init__(self):
        # regex to match a number at the start of the message.
        # Being a float is optional.
        self.length_re = r'--((\d*)?(\.\d*)?)'
        # regex to atch and capture vote options in square bracket.
        self.options_re = r'\[(.+)\]'
        self.vote_length = 0.5
        self.default_options = ['yes', 'no']
        self.active_votes = {}

    def apply_regex(self, msg, regex):
        '''
        Applies the regex and removes the matched
        elements from the message.
        Returns the matched group.
        '''
        result = re.search(regex, msg)
        if result:
            msg = re.sub(regex, '', msg).strip()
            return msg, result.group(0)
        else:
            return False

    def handle_input(self, msg):
        '''
        Parses the supplied message to determine the vote
        length and supplied parameteres(if any).

        Expected vote format:
            !vote[--time] String of the vote [[parameter1, parm2]]
        '''
        # Check if the user supplied a length
        regex_result = self.apply_regex(msg, self.length_re)
        if regex_result:
            msg, matched_length = regex_result
            # start at the second index to avoid the -- at the start
            # of the time parameter.
            vote_length = float(matched_length[2:])
        else:
            vote_length = self.vote_length

        # Check if the user supplied extra parameters
        regex_result = self.apply_regex(msg, self.options_re)
        if regex_result:
            msg, extra_options = regex_result
            # They might have used commas to seperate the parameters
            # so parse it out.
            extra_options = extra_options.replace('[', '').replace(']', '')
            options = extra_options.lower().split(',')

            option_len = len(options)
            if option_len < 2:
                return False

            # Create a dictionary with the voter counts set to 0
            values = [0 for option in options]
            vote_options = dict(zip(options, values))

            # Make sure the options aren't repeated by comparing length
            # before the dictionary was created.
            if option_len != len(vote_options):
                return False
        else:
            values = [0 for index in self.default_options]
            vote_options = dict(zip(self.default_options, values))

        # What remains of the msg should be the vote question.
        if len(msg.strip()) < 1:
            return False

        return msg, vote_length, vote_options

    async def send_start_message(self, client, channel, vote_length, msg):
        '''
        Simple function that sends a message that a
        vote has started asyncronously.
        '''
        vote_parms = self.active_votes[channel][1]
        start_string = 'Starting vote ```%s``` with options ' % msg
        param_string = ' '.join(['%s' for index in range(len(vote_parms))])
        start_string += '[ ' + param_string % tuple(vote_parms.keys()) + ' ]'
        start_string += ' For %s minutes.' % vote_length

        await client.send_message(channel, start_string)

    async def end_vote(self, client, channel, msg):
        '''
        Counts the votes to determine the winner and sends
        the finish message. Cant simply check the max value
        because there might be a draw. Should probably break
        it up.
        '''
        vote_parms = self.active_votes[channel][1]
        end_string = 'Voting for ```%s``` completed.' % msg

        max_value = max(vote_parms.values())
        winners = [key for key, value in vote_parms.items()
                   if value == max_value]

        if len(winners) == 1:
            end_string += ' The winner is **%s**' % tuple(winners)
        else:
            winner_string = ' '.join(['%s' for index in range(len(winners))])
            end_string += ' The winners are [ **' + winner_string % tuple(winners) + '** ]'

        await client.send_message(channel, end_string)

    async def run_vote(self, client, channel, vote_length, msg):
        '''
        Simple async function that sleeps for the vote length
        and calls the start and end voting functions.
        '''
        await self.send_start_message(client, channel, vote_length, msg)        
        # sleep for the vote length.
        await asyncio.sleep(vote_length * 60)
        # Count the votes and send the ending message
        await self.end_vote(client, channel, msg)
        # Delete the dictionary entry now that the vote is finished.
        del self.active_votes[channel]

    async def start_vote(self, msg, user, channel, client):
        '''
        Main function that handles the vote function. Makes sure
        that only vote is going at a time in a channel.

        Calls from a channel that has a vote going on are
        considered to be a vote for the ongoing vote.

        dict entry: active_votes(client, {option: count}, [voters])
        '''
        if channel not in self.active_votes:
            processed_input = self.handle_input(msg)
            if processed_input:
                msg, vote_len, params = processed_input
                # Save a reference to the sleep function, the valid params
                # for the specific vote and an empty list which will contain
                # the name of users who have already voted.
                self.active_votes[channel] = (self.run_vote, params, [])
                # print('starting vote with ', params)
                # Start the actual vote.
                await self.active_votes[channel][0](client, channel, vote_len, msg)
            else:
                return ('Invalid format for starting a vote. The correct format is '
                        '```!vote[--time] Vote question [vote options]``` '
                        '**eg:** !vote start a vote on some topic? [yes, no, maybe]')
        else:
            # An active vote already exists for this channel.
            # First check if the user has already voted in it.
            if user in self.active_votes[channel][2]:
                return ("Stop attempting electoral fraud %s, "
                        "you've already voted") % user
            else:
                # Check if the supplied argument is a valid vote option.
                vote_option = msg.lower().strip()
                valid_options = self.active_votes[channel][1]
                if vote_option in valid_options:
                    self.active_votes[channel][1][vote_option] += 1
                    # Add the user to the list of users.
                    self.active_votes[channel][2].append(user)
                    # return 'Increasing %s vote :)' % vote_option
                else:
                    error_str = 'Invalid vote option %s. ' % user
                    error_str += 'The options are ' + str(tuple(valid_options.keys()))
                    return error_str


class Reminder():

    def __init__(self):
        self.active_reminder = {}
        self.regex = r'\[(.*)\]'
        self.settings = {'PREFER_DATES_FROM': 'future',
                         'DATE_ORDER': 'DMY'}
        self.parser = DateDataParser(languages=['en'],
                                     allow_redetect_language=False,
                                     settings=self.settings)

    async def send_reminder_start_msg(self, user, channel, client, time):
        '''
        Gives an acknowledgement that the reminder has been set.
        '''
        time = time.replace(microsecond=0)
        msg = ":+1: %s I'll remind you at %s UTC." % (user, str(time))
        await client.send_message(channel, msg)

    async def send_reminder_end_msg(self, user, channel, client, text):
        '''
        Sends the message when the reminder finishes with the text
        if it was passed in.
        '''
        if text:
            msg = 'Hello %s, you asked me to remind you of **%s**.' % (user,
                                                                      text)
        else:
            msg = 'Hello %s, you asked me to remind you at this time.' % user
        await client.send_message(channel, msg)

    async def start_reminder_sleep(self, delta, user, channel, client, text, time):
        '''
        Asyncronously sleeps for the reminder length.
        '''
        # Send a message that the reminder is going to be set.
        await self.send_reminder_start_msg(user, channel, client, time)
        await asyncio.sleep(delta.total_seconds())
        await self.send_reminder_end_msg(user, channel, client, text)

    def apply_regex(self, msg):
        '''
        Applies the regex to check if the user passed
        in a optional string in square brackets.
        Returns the original message with the string
        removed and the captured msg.
        '''
        regex_result = re.search(self.regex, msg)
        if regex_result:
            msg = re.sub(self.regex, '', msg).strip()
            return msg, regex_result.group(1)
        else:
            return False

    def parse_msg(self, msg, user):
        '''
        Parses the message passed along with the !remind command.
        Uses the dateparser library to check if the time string
        is valid
        Format: !remindme <time period> [optional string]
        '''
        parsed_time = self.parser.get_date_data(msg)['date_obj']
        if not parsed_time:
            error_msg = ('I could not interept your message %s, try specifing '
                         'the time period in a different format.') % user
            return (False, error_msg)
        now = datetime.utcnow()
        if parsed_time < now:
            error_msg = ("Dont waste my time %s, you can't expect "
                         "me to remind you of an event in the past.") % user
            return (False, error_msg)
        difference = parsed_time - now
        return (True, difference, parsed_time)

    async def set_reminder(self, msg, user, channel, client):
        '''
        Main function that called to set a reminder. Calls the
        helper functions to parse and to check if its valid.

        If the message is valid, the asyncronous sleep function
        is called.

        Currently loses state on restart ;_; could write/load
        to a file.
        '''
        reminder_txt = None
        optional_string = self.apply_regex(msg)
        if optional_string:
            msg, reminder_txt = optional_string

        parsed_msg = self.parse_msg(msg, user)
        if not parsed_msg[0]:
            return parsed_msg[1]
        else:
            await self.start_reminder_sleep(parsed_msg[1], user,
                                            channel, client, reminder_txt,
                                            parsed_msg[2])

