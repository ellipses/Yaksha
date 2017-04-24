#!/usr/bin/python
from fuzzywuzzy import process
from commands.utilities import memoize, get_request, register
from bs4 import BeautifulSoup
from itertools import chain
import requests
import discord
import json
import re


class Boards():

    def __init__(self, config=None):
        self.url = ('http://www.boards.ie/vbulletin/forumdisplay.php?f=1204')

    @memoize(60 * 60)
    async def get_most_recent_thead(self):
        '''
        Use the search feature to find and return the link
        for the most recent thread that was created.
        '''
        resp = await get_request(self.url)

        if resp:
            soup = BeautifulSoup(resp, 'html.parser')

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
    async def find_posters(self, thread_url):
        '''
        Returns the names of all the posters in the thread
        as a list of strings.
        '''
        resp = await get_request(thread_url)

        if resp:
            soup = BeautifulSoup(resp, 'html.parser')
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

    @register('!casuals')
    async def get_thread_posters(self, *args, **kwargs):
        '''
        Main method thats called when trying to get a list of
        people who have posted in the casuals thread.
        '''
        thread = await self.get_most_recent_thead()
        if thread:
            posters = await self.find_posters(thread)

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


class Frames():

    def __init__(self, config=None):
        config = config or {}
        self.url = config['frame_data']['url']
        self.info_regex = r'^-v'
        self.regex = r'(^\S*)\s*(vtrigger|vt)?\s+(.+)'
        self.char_ratio_thresh = 65
        self.move_ratio_thresh = 65
        self.short_mapping = {
            'cr': 'crouch ',
            'st': 'stand ',
            'jp': 'jump ',
            'c': 'crouch ',
            's': 'stand ',
            'j': 'jump '
        }
        # Regex to capture input that starts in the form "cr.", "cr ", "c."
        #  and "c " for cr, st and jp.
        self.short_regex = r'((^cr|^c)(\s|\.))|((^st|^s)(\s|\.))|((^jp|^j)(\s|\.))'
        self.output_format = ('%s - (%s - %s) - [Startup]: %s [Active]: %s [Recovery]: %s '
                              '[On Hit]: %s [On Block]: %s')
        self.stats_format = '%s - [%s] - %s'
        self.knockdown_format = ' [KD Adv]: %s [Quick Rise Adv]: %s [Back Rise Adv]: %s '

    @memoize(60 * 60 * 24 * 7)
    async def get_data(self, **kwargs):
        '''
        Simple helper function that hits the frame data dump
        endpoint and returns the contents in json format.
        '''
        resp = await get_request(self.url)
        if resp:
            frame_data = json.loads(resp)
            self.add_reverse_mapping(frame_data)
            return frame_data
        else:
            return False

    def add_reverse_mapping(self, data):
        '''
        Create a reverse mapping between common names,
        move command and the actual name of the moves.
        Increases the time on the first queury but the result
        is cached for subsequent ones.
        '''
        common_name_dict = {}
        numpad_dict = {}
        commands_dict = {}
        for char in data.keys():

            char_moves = data[char]['moves']['normal']
            vt_moves = data[char]['moves']['vtrigger']
            vt_only_moves = set(vt_moves) - set(char_moves)

            for move in chain(char_moves.keys(), vt_only_moves):
                # Add the common name of the move to the dict.
                try:
                    common_name = char_moves[move]['commonName']
                    common_name_dict[common_name] = move
                # Some moves dont have common name so just pass.
                except KeyError:
                    pass

                try:
                    command = char_moves[move]['plainCommand']
                except KeyError:
                    command = vt_moves[move]['plainCommand']

                # Add the numpad notation
                try:
                    numpad_dict[char_moves[move]['aCom']] = move
                except KeyError:
                    pass
                # Wierd edge case where a vt only move has the
                # same plain command. In this case don't overwrite
                # the already existing normal command. Depends on
                # the iteration order being normal moves -> vt moves.
                if command in commands_dict:
                    continue


                commands_dict[command] = move

            common_name_dict.update(commands_dict)
            common_name_dict.update(numpad_dict)
            data[char]['reverse_mapping'] = common_name_dict
            # Also add a set of keys/values with official name
            offical_names = dict(zip(char_moves.keys(), char_moves.keys()))
            data[char]['reverse_mapping'].update(offical_names)
            # Update the reverse mapping with vtrigger only moves.
            data[char]['reverse_mapping'].update(
                dict(zip(vt_only_moves, vt_only_moves))
            )
            # Add the stats of the char to the mapping as well. The extra value
            # 'char_stat' is added to later determine if the matched move is a
            # stat or not.
            stats_mapping = {stat: (value, 'char_stat')
                             for stat, value in data[char]['stats'].items()}
            data[char]['reverse_mapping'].update(stats_mapping)

            common_name_dict = {}
            commands_dict = {}
            numpad_dict = {}

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
            # Slice to the second last char because the matched move might
            # be 'cr. 'or 'cr ' but the  mapping only contains cr.
            move = re.sub(self.short_regex, self.short_mapping[matched[:-1]], move)

        # Use the reverse mapping to determine which move they
        # were looking for.
        moves = data[char_match]['reverse_mapping']
        move_match, move_ratio = process.extractOne(move, moves.keys())

        if move_ratio < self.move_ratio_thresh:
            return False

        move = data[char_match]['reverse_mapping'][move_match]

        # Check if the matched name was a char stat or a move.
        if 'char_stat' in move:
            return char_match, move_match, move
        else:
            # Find the move they want.
            if vt:
                # The move might not have any difference in vtrigger
                # so just return the normal version.
                try:
                    move_data = data[char_match]['moves']['vtrigger'][move]
                except KeyError:
                    move_data = data[char_match]['moves']['normal'][move]
            else:
                try:
                    move_data = data[char_match]['moves']['normal'][move]
                # Might be a vtrigger only move.
                except KeyError:
                    move_data = data[char_match]['moves']['vtrigger'][move]

            return char_match, move, move_data

    def format_output(self, char, move, vt, data, verbose=False):
        '''
        Formats the msg to a nicely spaced string for
        presentation.
        '''
        if 'char_stat' in data:
            output = self.stats_format % (char, move, data[0])
        else:
            # Have to parse knockdown advantage frames if it causes one.
            if data['onHit'] == 'KD' and 'kd' in data:
                mg_format = self.output_format + self.knockdown_format
                output = mg_format % (
                    char, move, data['plainCommand'],
                    data['startup'], data['active'],
                    data['recovery'], data['onHit'],
                    data['onBlock'], data['kd'],
                    data['kdr'], data['kdrb']
                )

            else:
                output = self.output_format % (
                    char, move, data['plainCommand'],
                    data['startup'], data['active'],
                    data['recovery'], data['onHit'],
                    data['onBlock']
                )

        if verbose and 'extraInfo' in data:
            info = '```%s```' % ', '.join(data['extraInfo'])
            output = output + info

        return output

    def format_embeded_message(self, char, move, vt, data):
        em = discord.Embed(
            title='%s' % char,
            description='%s - %s' % (move, data['plainCommand']),
            colour=0x3998C6
        )

        fields = ['startup', 'active', 'recovery', 'onHit', 'onBlock']
        if data['onHit'] == 'KD' and 'kd' in data:
            fields += ['kd', 'kdr', 'kdrb']

        field_mapping = {
            'startup': 'Startup', 'active': 'Active',
            'recovery': 'Recovery', 'onHit': 'On Hit',
            'onBlock': 'On Block', 'kd': 'Knockdown Adv',
            'kdr': 'Quick Rise Adv', 'kdrb': 'Back Roll Adv'
        }

        for field in fields:
            em.add_field(name=field_mapping[field], value=data[field])

        if 'extraInfo' in data:
            em.set_footer(text=', '.join(data['extraInfo']))
        return em

    @register('!frames')
    async def get_frames(self, msg, user, *args, **kwargs):
        '''
        Main method thats called for the frame data function.
        Currently works only for SFV data thanks to Pauls nicely
        formatted data <3.
        '''
        # Check if they want verbose output.
        verbose = False
        info_result = re.search(self.info_regex, msg)
        if info_result:
            verbose = True
            msg = re.sub(self.info_regex, '', msg).strip()
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

        frame_data = await self.get_data(**kwargs)
        if not frame_data:
            return 'Got an error when trying to get frame data :(.'

        matched_value = self.match_move(char_name, move_name,
                                        vtrigger, frame_data)
        if not matched_value:
            return ("Don't waste my time %s. %s with %s is not a valid "
                    "character/move combination for SFV.") % (user,
                                                              char_name,
                                                              move_name)
        else:
            char, move, data = matched_value
            msg_output = self.format_output(
                char, move, vtrigger, data, verbose
            )
            if verbose and 'char_stat' not in data:
                return msg_output, self.format_embeded_message(
                    char, move, vtrigger, data
                )
            else:
                return msg_output
