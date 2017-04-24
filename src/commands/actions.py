#!/usr/bin/python
from commands.utilities import rate_limit, memoize, get_request, register, get_callbacks
from dateparser.date import DateDataParser
from datetime import datetime, timedelta
from fuzzywuzzy import process
from bs4 import BeautifulSoup
import aiofiles
import aiohttp
import requests
import asyncio
import random
import base64
import yaml
import json
import time
import re
import os


class Streams():

    def __init__(self, config={}):
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

    @register('!whens')
    async def display_stream_list(self, msg, user, *args):
        channels = self.get_channels()
        channel_list = (',').join(channels.split(' '))

        resp = await get_request(self.api_prefix + channel_list)
        if resp:
            data = json.loads(resp)
            return self.format_channels(data)
        else:
            print ('Failed getting steam data with error %s' % payload.text)
            return False


class Shows():

    def __init__(self, config={}):
        # gif/episode/start_timestamp/end_timestamp.gif?b64lines=caption_in_base64
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
        char_buff = 0
        formated_msg = ''
        for word in message.split(' '):
            char_buff += len(word)
            formated_msg += ' %s' % word
            if char_buff >= 18:
                char_buff = 0
                formated_msg += u"\u000A"

        return formated_msg

    async def handle_caption(self, caption):
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
        response = await get_request(self.api_url % caption)
        screen_caps = json.loads(response)

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

    async def get_gif(self, caption, user, *args, **kwargs):
        '''
        Method thats called when trying to get a Frinkiac url.
        Does basic error handling and calls handle_caption
        which does most of the actual work.
        '''
        resp = await self.handle_caption(caption)
        if not resp:
            return 'Try fixing your quote.'
        episode, timestamps, caption = resp
        return self.gif_url % (episode,
                               timestamps[0], timestamps[-1])

    async def get_captioned_gif(self, caption, user, *args, **kwargs):
        '''
        Method thats called when trying to get a gif with
        a caption. Does basic error handling and base 64
        encoding and formatting of the caption.
        '''
        resp = await self.handle_caption(caption)
        if not resp:
            return 'Try fixing your quote.'

        episode, timestamps, caption = resp
        caption = self.format_message(caption)
        try:
            encoded = str(base64.b64encode(str.encode(caption)), 'utf-8')
        except TypeError:
            encoded = str(base64.b64encode(str.encode(caption)))
        return self.caption_url % (episode, timestamps[0],
                                   timestamps[-1], encoded)


class Simpsons(Shows):

    def __init__(self, config={}):
        super(Simpsons, self).__init__(config)
        self.gif_url = 'https://frinkiac.com/gif/%s/%s/%s.gif'
        self.caption_url = 'https://frinkiac.com/gif/%s/%s/%s.gif?b64lines=%s'
        self.api_url = 'https://frinkiac.com/api/search?q=%s'

    @register('!simpsons')
    async def get_simpsons_gif(self, *args, **kwargs):
        return await super(Simpsons, self).get_gif(*args, **kwargs)

    @register('!scaption')
    async def get_captioned_simpsons_gif(self, *args, **kwargs):
        return await super(Simpsons, self).get_captioned_gif(*args, **kwargs)


class Futurama(Shows):

    def __init__(self, config={}):
        super(Futurama, self).__init__(config)
        self.gif_url = 'https://morbotron.com/gif/%s/%s/%s.gif'
        self.caption_url = 'https://morbotron.com/gif/%s/%s/%s.gif?b64lines=%s'
        self.api_url = 'https://morbotron.com/api/search?q=%s'

    @register('!futurama')
    async def get_futurame_gif(self, *args, **kwargs):
        return await super(Futurama, self).get_gif(*args, **kwargs)

    @register('!fcaption')
    async def get_captioned_futurama_gif(self, *args, **kwargs):
        return await super(Futurama, self).get_captioned_gif(*args, **kwargs)


class Arbitary():

    def __init__(self, config={}):
        self.config = config
        self.tourney_url = 'http://shoryuken.com/tournament-calendar/'
        self.history_limit = 500
        self.mention_regex = r'-(\d)'

    @register('!shuffle')
    async def shuffle(self, sentence, author, *args):
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
    @register('!skins')
    async def skins(self, message, author, *args):
        skins_list = yaml.load(open('skins.yaml').read())
        return random.choice(skins_list.split('\n'))

    @register('!charming')
    async def charming(self, *args, **kwargs):
        return 'https://goo.gl/46MdMF'

    @register('!onion')
    async def onion(self, *args, **kwargs):
        return 'http://gifimgs.com/res/0417/58fbe9bfd0d0d338045526.gif'

    @register('!mymention')
    async def get_my_mention(self, message, user, channel, client, *args):
        '''
        Shows the last message in the channel that mentioned the user
        that uses this command.

        If an optional parameter with a number is passed is, its returns
        the last nth last mention.
        '''
        regex_result = re.search(self.mention_regex, message)
        count = 0
        if regex_result:
            count = int(regex_result.group(1))

        async for message in client.logs_from(channel,
                                              limit=self.history_limit):
            if user in message.content:
                if count == 0:
                    username = message.author.display_name
                    response = '%s _by %s_' % (message.content,
                                               username)
                    return response
                else:
                    count -= 1

        response = ('Sorry %s, I could not find any mention of you in'
                        ' the last %s messages of this channel.') % (user, self.history_limit)
        return response


class Tourney():

    def __init__(self, config={}):
        self.tourney_url = 'http://shoryuken.com/tournament-calendar/'

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
    @register('!tourney')
    async def get_tourneys(self, message, author, *args):
        '''
        Uses the list of tournaments on the srk page
        to return the upcomming tournaments.
        '''
        resp = await get_request(self.tourney_url)

        if resp:
            soup = BeautifulSoup(resp, 'html.parser')
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


class Gifs():

    def __init__(self, config={}):
        self.search_url = ('http://api.giphy.com/v1/gifs/search?q='
                           '%s&api_key=dc6zaTOxFJmzC')
        self.translate_url = ('http://api.giphy.com/v1/gifs/translate?s='
                              '%s&api_key=dc6zaTOxFJmzC')

    @register('!gif')
    async def get_gif(self, quote, author, *args):
        query = '+'.join(quote.split(' '))
        resp = await get_request(self.search_url % query)

        if resp:
            gifs = json.loads(resp)['data'][:5]
            if len(gifs) == 0:
                return "Sorry %s I could not find any gifs using that keyword :( ." % author
            urls = [gif['url'] for gif in gifs]
            return random.choice(urls)
        else:
            return 'Got an error when searching for gifs :('

    @register('!tgif')
    def get_translate_gif(self, quote, author, *args):
        query = '+'.join(quote.split(' '))
        resp = requests.get(self.translate_url % query)

        if resp.status_code == 200:
            return resp.json()['data']['url']
        else:
            return ('Got an error when trying find a translate gif :(.'
                    ' What does this even do anyway')


class AddCommands():

    def __init__(self, config={}):
        self.file = config['add_commands']['file']

    def save_command(self, command, actions):
        with open(self.file, 'a') as file:
            json.dump({command: actions}, file)
            file.write(os.linesep)
        return True

    def load_command(self, msg):
        with open(self.file, 'r') as file:
            command_list = file.readlines()

        for command in command_list:
            saved_cmd = json.loads(command)

            for cmd in saved_cmd:
                if cmd == msg:
                    return saved_cmd[cmd]

        return False

    @register('!get')
    async def get_command(self, msg, user, *args, **kwargs):
        # They might've sent multiple commands but
        # we only care about the first one.
        cmd = msg.split(' ')[0]
        resp = self.load_command(cmd)
        if resp:
            return resp
        else:
            return "Command %s doesn't exist %s" % (cmd, user)

    @register('!add')
    async def add_command(self, msg, user, *args, **kwargs):
        '''
        Main function that called when a user
        tries to add a new command.
        '''
        split_msg = msg.split(' ')
        command = split_msg[0]
        actions = ' '.join(split_msg[1:])
        if self.save_command(command, actions):
            return 'The tag _%s_ has been added.' % command
        else:
            return 'some error check traceback, too sleepy to write sensible error message'


class Reminder():

    def __init__(self, config={}):
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

    @register('!remindme')
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


class Help():

    def __init__(self, config={}):
        self.config = config
        self.cmd_ratio_thresh = 80

    @register('?help')
    async def get_help_message(self, msg, *args, **kwargs):
        available_commands = kwargs.get('commands_dict', False)

        if available_commands:
            # Try fuzzy matching on the msg to determine the cmd
            # the user is trying to get help on.
            cmd, ratio = process.extractOne(msg, available_commands.keys())

            # If the ratio is too low we assume the user made
            # an error.
            if ratio < self.cmd_ratio_thresh:
                return ('Allows you to get help on a command. The avaliable'
                        ' commands are ```%s```' % list(available_commands.keys()))
            else:
                return available_commands[cmd]
        else:
            return 'Dict of commands missing :/ .'


class Blacklist():

    def __init__(self, config={}):
        self.blacklist_file = config.get('blacklist_file')

    @register('!blacklist')
    async def blacklist(self, message, *args, **kwargs):
        '''
        Blacklists the user by adding their 'uid' to the
        currently maintained list of blacklisted users and updates the file.
        '''
        blacklisted_users = kwargs['blacklisted_users']
        users = message.split(' ')
        # Remove users who might have already been blacklisted.
        users = [user for user in users if user not in blacklisted_users]
        blacklisted_users.extend(users)

        users = [user + '\n' for user in users]
        async with aiofiles.open(self.blacklist_file, mode='a') as f:
            await f.writelines(users)

    @register('!unblacklist')
    async def unblacklist(self, message, *args, **kwargs):
        '''
        Unblacklists the user by removing their 'uid' from the currently maintained
        list of blacklisted users and removes it from the file.
        '''
        users = message.split(' ')
        blacklisted_users = kwargs['blacklisted_users']
        users = [user for user in users if user in blacklisted_users]

        for user in users:
            del blacklisted_users[blacklisted_users.index(user)]

        users = [user + '\n' for user in users]
        async with aiofiles.open(self.blacklist_file, mode='r') as f:
            saved_users = await f.readlines()
            for user in users:
                del saved_users[saved_users.index(user)]

        async with aiofiles.open(self.blacklist_file, mode='w') as f:
            await f.writelines(saved_users)
