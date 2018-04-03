#!/usr/bin/python
import re
import json
import discord
import requests
from itertools import chain
from bs4 import BeautifulSoup
from fuzzywuzzy import process
from collections import OrderedDict
from commands.utilities import memoize, get_request, register



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
        self.regex = r'(^\S*)\s*(vt1|vt2)?\s+(.+)'
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

        self.vt_mappings = {'1': 'vtOne', '2': 'vtTwo'}
        self.custom_fields = [
            'vtc2DashOnHit', 'runstopOB', 'vtc1OnHit', 'vtc2OnHit',
            'ocOnBlock', 'ssOnHit', 'vscoH', 'vtc1OnBlockD',
            'vtc1GapOnBlock', 'LKorMKDashOH', 'vscoB', 'LKorMKDashOB',
            'ssOnBlock', 'vtcOnBlock', 'lmaoB', 'VSKGapBlock',
            'vtcOnHitD', 'lmaoH', 'vt1dashOB', 'vtc2OnBlock',
            'vtc1OnBlockB', 'vtcOnBlockD', 'vtc1OnBlock', 'hopsOnBlock',
            'VSKGapHit', 'vtc1OnHitB', 'ocOnHit', 'vtc1OnHitF',
            'rollcOnBlock', 'transfOH', 'exDashOB', 'VSPGapHit', 'lkDashOH',
            'vtc1GapOnHit', 'vtc1OnBlockF', 'transfOB', 'lkDashOB',
            'vtcOnHit', 'exDashOH', 'mkDashOB', 'runstopOH', 'vt1dashOH',
            'rollcOnHit', 'vtc1OnHitD', 'hopsOnHit', 'vtcOnHitF',
            'vtcOnBlockB', 'vtcOnHitB', 'vtc2GapOnBlock', 'vtcOnBlockF',
            'vtc2DashOnBlock', 'VSPGapBlock', 'mkDashOH'
        ]

        self.stats_mapping = {
            'dash': ('bDash', 'fDash', 'bDashDist', 'fDashDist'),
            'walk': ('bWalk', 'fWalk'),
            'jump': ('bJump', 'fJump', 'nJump', 'bJumpDist', 'fJumpDist'),
            'throw': ('throwHurt', 'throwRange')
        }

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
        v_triggers = ['vtTwo', 'vtOne']
        for char in data.keys():

            char_moves = {}
            # Its possible that the vtrigger moves even with the
            # same name are lowercased. To avoid duplication, we
            # enforce that all the moves are lower cased.
            moves = list(data[char]['moves']['normal'].keys())
            for m in moves:
                v = data[char]['moves']['normal'][m]
                char_moves[m.lower()] = v
                data[char]['moves']['normal'].pop(m)
                data[char]['moves']['normal'][m.lower()] = v

            vt_moves = {}
            for v_trigger in v_triggers:
                v_moves = list(data[char]['moves'][v_trigger].keys())
                for vt_move in v_moves:
                    v = data[char]['moves'][v_trigger][vt_move]
                    vt_moves[vt_move.lower()] = v
                    data[char]['moves'][v_trigger][vt_move.lower()] = v
                    data[char]['moves'][v_trigger].pop(vt_move)

            vt_only_moves = set(vt_moves) - set(char_moves)

            for move in chain(char_moves.keys(), vt_only_moves):
                if move == 'undefined':
                    continue
                # Add the common name of the move to the dict.
                try:
                    common_name = char_moves[move]['cmnCmd']
                    common_name_dict[common_name] = move
                # Some moves dont have common name so just pass.
                except KeyError:
                    pass

                try:
                    command = char_moves[move]['plnCmd']
                except KeyError:
                    command = vt_moves[move]['plnCmd']

                # Add the numpad notation
                try:
                    numpad_dict[str(char_moves[move]['numCmd'])] = move
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
            move = re.sub(
                self.short_regex, self.short_mapping[matched[:-1]], move
            )

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
                    move_data = data[char_match]['moves'][self.vt_mappings[vt]][move]
                except KeyError:
                    move_data = data[char_match]['moves']['normal'][move]
            else:
                try:
                    move_data = data[char_match]['moves']['normal'][move]
                # Might be a vtrigger only move.
                except KeyError:
                    try:
                        move_data = data[char_match]['moves']['vtOne'][move]
                    except KeyError:
                        move_data = data[char_match]['moves']['vtTwo'][move]

            return char_match, move, move_data

    def format_stats_output(self, char, move, move_data, data, searched_move):
        match, ratio = process.extractOne(
            searched_move, self.stats_mapping.keys()
        )
        if ratio > 85:

            related_fields = {}
            for field in self.stats_mapping[match]:
                try:
                    related_fields[field] = data[char]['stats'][field]
                except KeyError:
                    pass

            output = ''.join(
                [' [%s] - %s' % (key, value)
                 for key, value in related_fields.items()]
            )
            output = '%s -' % char + output

        else:
            output = self.stats_format % (char, move, move_data[0])

        return output

    def escape_chars(self, value):
        '''
        Escape characters like * to prevent discord from using it
        for formatting.
        '''
        try:
            return value.replace('*', '\*')
        except AttributeError:
            return value

    def format_output(self, char, move, vt, move_data, data, searched_move):
        '''
        Formats the msg to a nicely spaced string for
        presentation.
        '''
        if 'char_stat' in move_data:
            output = self.format_stats_output(
                char, move, move_data, data, searched_move
            )
        else:
            cmds = [
                'plnCmd', 'startup', 'active', 'recovery', 'onHit',
                'onBlock'
            ]
            msg_format = self.output_format
            # Have to parse knockdown advantage frames if it causes one.
            if 'kd' in move_data and move_data['onHit'] == 'KD':
                msg_format = self.output_format + self.knockdown_format
                cmds.extend(['kd', 'kdr', 'kdrb'])

            moves = [char, move]
            moves.extend(
                self.escape_chars(move_data.get(cmd, '-')) for cmd in cmds
            )
            output = msg_format % tuple(moves)

        return output

    def format_embeded_message(self, char, move, vt, data):
        em = discord.Embed(
            title='%s' % char,
            description='%s - %s' % (move, data['plnCmd']),
            colour=0x3998C6
        )

        fields = ['startup', 'active', 'recovery', 'onHit', 'onBlock']
        if data.get('onHit') == 'KD' and 'kd' in data:
            fields += ['kd', 'kdr', 'kdrb']

        field_mapping = {
            'startup': 'Startup', 'active': 'Active',
            'recovery': 'Recovery', 'onHit': 'On Hit',
            'onBlock': 'On Block', 'kd': 'Knockdown Adv',
            'kdr': 'Quick Rise Adv', 'kdrb': 'Back Roll Adv'
        }


        for field in fields:
            if field in data:
                em.add_field(
                    name=field_mapping[field], value=self.escape_chars(data[field])
                )

        if 'extraInfo' in data:
            # Maybe they messed up the encoding so attemtpt to handle it.
            if type(data['extraInfo']) == str:
                data['extraInfo'] = json.loads(data['extraInfo'])
            em.set_footer(text=', '.join(data['extraInfo']))
        return em

    def add_custom_fields(self, data, text_output, embed_output):
        # Use an ordered dict here because we want to display stats in
        # the order we defined them.
        custom_fields = OrderedDict()
        for field in self.custom_fields:
            if field in data:
                custom_fields[field] = self.escape_chars(data[field])

        text_output = text_output + (
            ''.join(
                [' [%s]: %s' % (key, value)
                 for key, value in custom_fields.items()]
            )
        )

        if 'extraInfo' in data:
            if type(data['extraInfo']) == str:
                data['extraInfo'] = json.loads(data['extraInfo'])
            info = ' ```%s``` ' % ', '.join(data['extraInfo'])
            text_output = text_output + info

        for field, value in custom_fields.items():
            embed_output.add_field(name=field, value=value)

        return text_output, embed_output

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
                    "[vt1/vt2] move_name") % user

        char_name = result.group(1)
        move_name = result.group(3)
        if result.group(2):
            # If either of the vtriggers matched, then we will
            # pass the number of the matched one.
            vtrigger = result.group(2)[-1]
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
            text_output = self.format_output(
                char, move, vtrigger, data, frame_data, move_name
            )
            if verbose and 'char_stat' not in data:
                embed_output = self.format_embeded_message(
                    char, move, vtrigger, data
                )
                return self.add_custom_fields(data, text_output, embed_output)
            else:
                return text_output
