#!/usr/bin/python
import re
import json
import discord
import logging
from itertools import chain
from itertools import islice
from fuzzywuzzy import process
from collections import OrderedDict
from commands.utilities import memoize, get_request, register


class Frames:
    def __init__(self, config=None):
        config = config or {}
        self.embed_footer_length = 2000
        self.url = config["frame_data"]["sf5_url"]
        self.detail_url = config["frame_data"]["sf5_detail_url"]
        self.info_regex = r"^-v"
        self.regex = r"(^\S*)\s*(vt1|vt2)?\s+(.+)"
        self.char_ratio_thresh = 65
        self.move_ratio_thresh = 65
        self.short_mapping = {
            "cr": "crouch ",
            "st": "stand ",
            "jp": "jump ",
            "c": "crouch ",
            "s": "stand ",
            "j": "jump ",
        }
        # Regex to capture input that starts in the form "cr.", "cr ", "c."
        #  and "c " for cr, st and jp.
        self.short_regex = r"((^cr|^c)(\s|\.))|((^st|^s)(\s|\.))|((^jp|^j)(\s|\.))"
        self.output_format = (
            "%s - (%s - %s) - [Startup]: %s [Active]: %s [Recovery]: %s "
            "[On Hit]: %s [On Block]: %s"
        )
        self.stats_format = "%s - [%s] - %s"
        self.knockdown_format = (
            " [KD Adv]: %s [Quick Rise Adv]: %s [Back Rise Adv]: %s "
        )

        self.vt_mappings = {"1": "vtOne", "2": "vtTwo"}
        self.custom_fields = [
            "vtc2DashOnHit",
            "runstopOB",
            "vtc1OnHit",
            "vtc2OnHit",
            "ocOnBlock",
            "ssOnHit",
            "vscoH",
            "vtc1OnBlockD",
            "vtc1GapOnBlock",
            "LKorMKDashOH",
            "vscoB",
            "LKorMKDashOB",
            "ssOnBlock",
            "vtcOnBlock",
            "lmaoB",
            "VSKGapBlock",
            "vtcOnHitD",
            "lmaoH",
            "vt1dashOB",
            "vtc2OnBlock",
            "vtc1OnBlockB",
            "vtcOnBlockD",
            "vtc1OnBlock",
            "hopsOnBlock",
            "VSKGapHit",
            "vtc1OnHitB",
            "ocOnHit",
            "vtc1OnHitF",
            "rollcOnBlock",
            "transfOH",
            "exDashOB",
            "VSPGapHit",
            "lkDashOH",
            "vtc1GapOnHit",
            "vtc1OnBlockF",
            "transfOB",
            "lkDashOB",
            "vtcOnHit",
            "exDashOH",
            "mkDashOB",
            "runstopOH",
            "vt1dashOH",
            "rollcOnHit",
            "vtc1OnHitD",
            "hopsOnHit",
            "vtcOnHitF",
            "vtcOnBlockB",
            "vtcOnHitB",
            "vtc2GapOnBlock",
            "vtcOnBlockF",
            "vtc2DashOnBlock",
            "VSPGapBlock",
            "mkDashOH",
            "KnifeReloadOH",
            "KnifeReloadOB",
            "BeanBallOH",
            "BeanBallOB",
        ]
        self.custom_fields.sort()

        self.stats_mapping = {
            "dash": ("bDash", "fDash", "bDashDist", "fDashDist"),
            "walk": ("bWalk", "fWalk"),
            "jump": ("bJump", "fJump", "nJump", "bJumpDist", "fJumpDist"),
            "throw": ("throwHurt", "throwRange"),
        }
        self.request_headers = {}
        self.previous_data = None
        self.special_states = {}

    def update_headers(self, headers):
        self.request_headers = {
            "etag": headers.get("etag"),
            "Last-Modified": headers.get("Last-Modified"),
        }

    async def _get_data(self, **kwargs):
        """
        Simple helper function that hits the frame data dump
        endpoint and returns the contents in json format.
        """
        resp, headers = await get_request(
            self.url,
            self.request_headers,
        )
        if resp:
            self.update_headers(headers)
            detail_resp = None
            if self.detail_url:
                detail_resp, _ = await get_request(self.detail_url)
            self.add_reverse_mapping(resp, detail=detail_resp, **kwargs)
            self.previous_data = resp
            return self.previous_data
        else:
            return self.previous_data

    @memoize(300)
    async def get_sf_data(self, **kwargs):
        return await self._get_data(**kwargs)

    async def get_data(self, **kwargs):
        return await self.get_sf_data(**kwargs)

    def get_char_moves(self, char_states, specific_char_states, char, data):
        char_moves = {}
        # It's possible that the special status moves
        # with the same name are lower cased.
        # To avoid duplication, we
        # enforce that all the moves are lower cased.
        moves = list(data[char]["moves"]["normal"].keys())
        for m in moves:
            v = data[char]["moves"]["normal"][m]
            char_moves[m.lower()] = v
            data[char]["moves"]["normal"].pop(m)
            data[char]["moves"]["normal"][m.lower()] = v

        state_moves = {}
        specific_states = []
        if specific_char_states:
            specific_states = specific_char_states.get(char, [])

        for state in chain(char_states, specific_states):
            try:
                s_moves = list(data[char]["moves"][state].keys())
            except KeyError:
                logging.exception(
                    "failed to build specific state info for %s-%s", char, state
                )
                continue
            for s_move in s_moves:
                v = data[char]["moves"][state][s_move]
                state_moves[s_move.lower()] = v
                data[char]["moves"][state].pop(s_move)
                data[char]["moves"][state][s_move.lower()] = v

        return char_moves, state_moves, set(state_moves) - set(char_moves)

    def add_reverse_mapping(self, data, detail=None, **kwargs):
        """
        Create a reverse mapping between common names,
        move command and the actual name of the moves.
        Increases the time on the first queury but the result
        is cached for subsequent ones.
        """
        common_name_dict = {}
        numpad_dict = {}
        commands_dict = {}
        char_states = detail["characterStates"]
        specific_char_states = detail["specificCharacterStates"]
        char_states.remove("normal")

        self.special_states = specific_char_states if specific_char_states else {}
        self.char_states = char_states
        # Handle chars with dots in their names by creating
        # a copy with the dots stripped out.
        update = []
        for char in data.keys():
            if "." in char:
                update.append(char)
        for char in update:
            data[char.replace(".", "")] = data[char]

        for char in data.keys():

            char_moves, vt_moves, vt_only_moves = self.get_char_moves(
                char_states, specific_char_states, char, data
            )

            for move in chain(char_moves.keys(), vt_only_moves):
                if move == "undefined":
                    continue
                # Add the common name of the move to the dict.
                try:
                    common_name = char_moves[move]["cmnName"]
                    common_name_dict[common_name] = move
                # Some moves dont have common name so just pass.
                except KeyError:
                    pass

                try:
                    command = char_moves[move]["plnCmd"]
                except KeyError:
                    try:
                        command = vt_moves[move]["plnCmd"]
                    except KeyError:
                        pass

                # Add the numpad notation
                try:
                    numpad_dict[str(char_moves[move]["numCmd"])] = move
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
            data[char]["reverse_mapping"] = common_name_dict
            # Also add a set of keys/values with official name
            offical_names = dict(zip(char_moves.keys(), char_moves.keys()))
            data[char]["reverse_mapping"].update(offical_names)
            # Update the reverse mapping with vtrigger only moves.
            data[char]["reverse_mapping"].update(
                dict(zip(vt_only_moves, vt_only_moves))
            )
            # Add the stats of the char to the mapping as well. The extra value
            # 'char_stat' is added to later determine if the matched move is a
            # stat or not.
            stats_mapping = {
                stat: (value, "char_stat")
                for stat, value in data[char]["stats"].items()
            }

            data[char]["reverse_mapping"].update(stats_mapping)

            common_name_dict = {}
            commands_dict = {}
            numpad_dict = {}

    def match_move(self, char, move, state, data):
        """
        Main helper function that handles matching the move.
        Uses the reverse mapping of the common name, input command
        and short form converter to increase the chances of a better
        match.
        """
        # First find the char they want.
        char_match, char_ratio = process.extractOne(char, data.keys())
        if char_ratio < self.char_ratio_thresh:
            return False

        # They might have supplied the move name in shortened format
        # so convert it to how the frame data dump expects.
        if self.short_regex:
            result = re.search(self.short_regex, move)
            if result:
                matched = result.group(0)
                # Slice to the second last char because the matched move might
                # be 'cr. 'or 'cr ' but the  mapping only contains cr.
                move = re.sub(self.short_regex, self.short_mapping[matched[:-1]], move)

        # Use the reverse mapping to determine which move they
        # were looking for.
        moves = data[char_match]["reverse_mapping"]
        move_match, move_ratio = process.extractOne(move, moves.keys())

        if move_ratio < self.move_ratio_thresh:
            return False

        move = data[char_match]["reverse_mapping"][move_match]

        # Check if the matched name was a char stat or a move.
        if "char_stat" in move:
            return char_match, move_match, move
        else:
            # Find the move they want.
            if state:
                # The move might not have any difference in vtrigger
                # so just return the normal version.
                try:
                    move_data = data[char_match]["moves"][state][move]
                except KeyError:
                    move_data = data[char_match]["moves"]["normal"][move]
            else:
                try:
                    move_data = data[char_match]["moves"]["normal"][move]
                # Might be a special status only move.
                except KeyError:
                    if self.char_states:
                        for state in self.char_states:
                            try:
                                move_data = data[char_match]["moves"][state][move]
                                break
                            except KeyError:
                                pass

                    elif self.special_states:
                        for state in self.special_states[char_match]:
                            try:
                                move_data = data[char_match]["moves"][state][move]
                                break
                            except KeyError:
                                pass

            return char_match, move, move_data

    def format_stats_output(self, char, move, move_data, data, searched_move):
        match, ratio = process.extractOne(searched_move, self.stats_mapping.keys())
        if ratio > 85:

            related_fields = {}
            for field in self.stats_mapping[match]:
                try:
                    related_fields[field] = data[char]["stats"][field]
                except KeyError:
                    pass
            output = "".join(
                [" [%s] - %s" % (key, value) for key, value in related_fields.items()]
            )
            if not related_fields:
                output = self.stats_format % (char, move, move_data[0])
            else:
                output = "%s -" % char + output

        else:
            output = self.stats_format % (char, move, move_data[0])

        return output

    def escape_chars(self, value):
        """
        Escape characters like * to prevent discord from using it
        for formatting.
        """
        try:
            return value.replace("*", "\*")
        except AttributeError:
            return value

    def format_output(
        self, char, move, vt, move_data, data, searched_move, cmd_type="plnCmd"
    ):
        """
        Formats the msg to a nicely spaced string for
        presentation.
        """
        if "char_stat" in move_data:
            output = self.format_stats_output(
                char, move, move_data, data, searched_move
            )
        else:
            cmds = [cmd_type, "startup", "active", "recovery", "onHit", "onBlock"]
            msg_format = self.output_format
            # Have to parse knockdown advantage frames if it causes one.
            if "kd" in move_data and move_data["onHit"] == "KD":
                msg_format = self.output_format + self.knockdown_format
                cmds.extend(["kd", "kdr", "kdrb"])

            moves = [char, move]
            moves.extend(self.escape_chars(move_data.get(cmd, "-")) for cmd in cmds)
            output = msg_format % tuple(moves)

        return output

    def format_embeded_message(self, char, move, vt, data, cmd_type="plnCmd"):
        em = discord.Embed(
            title="%s" % char,
            description="%s - %s" % (move, data[cmd_type]),
            colour=0x3998C6,
        )

        fields = ["startup", "active", "recovery", "onHit", "onBlock"]
        sf_fields = ["kd", "kdr", "kdrb", "hcWinSpCa", "hcWinVt", "hcWinTc"]
        ggst_field = ["riscGain", "prorate", "guardLevel", "gatling", "kda"]
        for field in sf_fields + ggst_field:
            if field in data:
                fields.append(field)

        field_mapping = {
            "startup": "Startup",
            "active": "Active",
            "recovery": "Recovery",
            "onHit": "On Hit",
            "onBlock": "On Block",
            "kd": "Knockdown Adv",
            "kdr": "Quick Rise Adv",
            "kdrb": "Back Roll Adv",
            "hcWinSpCa": "Specials & CAs Hit Confirm",
            "hcWinVt": "V-Trigger Hit Confirm",
            "hcWinTc": "Target Combos Hit Confirm",
            "riscGain": "Risc Gain",
            "guardLevel": "Guard Level",
            "cancelsTo": "Cancels To",
            "gatling": "Gatling",
            "prorate": "Prorate",
            "kda": "Knockdown Adv",
        }

        for field in fields:
            if field in data:
                em.add_field(
                    name=field_mapping[field], value=self.escape_chars(data[field])
                )

        if "extraInfo" in data:
            # Maybe they messed up the encoding so attempt to handle it.
            if type(data["extraInfo"]) == str:
                data["extraInfo"] = json.loads(data["extraInfo"])
            presented_info = ", ".join(data["extraInfo"])
            if len(presented_info) > self.embed_footer_length:
                presented_info = presented_info[:self.embed_footer_length] + " ..."
            em.set_footer(text=presented_info)
        return em

    def add_custom_fields(self, data, text_output, embed_output):
        # Use an ordered dict here because we want to display stats in
        # the order we defined them.
        custom_fields = OrderedDict()
        for field in self.custom_fields:
            if field in data:
                custom_fields[field] = self.escape_chars(data[field])

        text_output = text_output + (
            "".join(
                [" [%s]: %s" % (key, value) for key, value in custom_fields.items()]
            )
        )

        if "extraInfo" in data:
            if type(data["extraInfo"]) == str:
                data["extraInfo"] = json.loads(data["extraInfo"])
            info = " ```%s``` " % ", ".join(data["extraInfo"])
            text_output = text_output + info

        for field, value in custom_fields.items():
            embed_output.add_field(name=field, value=value)

        return text_output, embed_output

    @register("frames")
    async def get_frames(self, msg, user, *args, **kwargs):
        """
        Main method thats called for the frame data function.
        Currently works only for SFV data thanks to Pauls nicely
        formatted data <3.
        """
        # Check if they want verbose output.
        verbose = False
        info_result = re.search(self.info_regex, msg)
        if info_result:
            verbose = True
            msg = re.sub(self.info_regex, "", msg).strip()
        result = re.search(self.regex, msg)

        if not result:
            return (
                "You've passed me an incorrect format %s. "
                "The correct format is !frames character_name "
                "[vt1/vt2] move_name"
            ) % user

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
            return "Got an error when trying to get frame data :(."

        matched_value = self.match_move(char_name, move_name, vtrigger, frame_data)
        if not matched_value:
            return (
                "%s with %s is not a valid " "character/move combination for SFV."
            ) % (char_name, move_name)
        else:
            char, move, data = matched_value
            text_output = self.format_output(
                char, move, vtrigger, data, frame_data, move_name
            )
            if verbose and "char_stat" not in data:
                embed_output = self.format_embeded_message(char, move, vtrigger, data)
                return self.add_custom_fields(data, text_output, embed_output)
            else:
                return text_output

    @register("sfv")
    async def _get_frames(self, *args, **kwargs):
        return await self.get_frames(*args, **kwargs)

    async def slash_sfv(self, char_name, move_name, vt, **kwargs):
        frame_data = await self.get_data(**kwargs)
        if not frame_data:
            return "Got an error when trying to get frame data :(."

        if vt:
            vt = self.vt_mappings[vt]

        matched_value = self.match_move(char_name, move_name, vt, frame_data)
        if not matched_value:
            return (
                "%s with %s is not a valid " "character/move combination for SFV."
            ) % (char_name, move_name)
        else:
            char, move, data = matched_value
            text_output = self.format_output(
                char, move, vt, data, frame_data, move_name, cmd_type="numCmd"
            )
            if "char_stat" not in data:
                embed_output = self.format_embeded_message(char, move, vt, data)
                return self.add_custom_fields(data, text_output, embed_output)
            return text_output

    async def autocomplete_char(self, name):
        data = await self.get_data()

        if not data:
            return []

        if not name:
            return list(islice(data.keys(), 5))

        return [
            char
            for (char, ratio) in process.extract(name, data.keys())
            if ratio > self.char_ratio_thresh
        ]

    async def autocomplete_move(self, char_name, move_name):
        data = await self.get_data()
        if not data:
            return []

        try:
            char_match, _ = process.extractOne(char_name, data.keys())
            moves = data[char_match]["reverse_mapping"]
        except KeyError:
            return []

        if not move_name:
            return list(islice(moves.keys(), 5))

        return [
            move
            for (move, ratio) in process.extract(move_name, moves.keys())
            if ratio > self.move_ratio_thresh
        ]

    async def autocomplete_char_state(self, char_name, _):
        data = await self.get_data()
        if not data:
            return []

        return self.special_states.get(char_name)


class GGFrames(Frames):
    def __init__(self, config):
        super().__init__(config)
        self.url = config["frame_data"]["ggst_url"]
        self.detail_url = config["frame_data"]["ggst_detail_url"]
        self.short_regex = None

    @memoize(300)
    async def get_gg_data(self, **kwargs):
        return await self._get_data(**kwargs)

    async def get_data(self):
        return await self.get_gg_data()

    async def slash_strive(self, char_name, move_name, *args, **kwargs):
        vtrigger = False
        frame_data = await self.get_data()
        if not frame_data:
            return "Got an error when trying to get frame data :(."
        matched_value = self.match_move(char_name, move_name, vtrigger, frame_data)

        if not matched_value:
            return (
                "%s with %s is not a valid " "character/move combination for GGST"
            ) % (char_name, move_name)
        else:
            char, move, data = matched_value
            text_output = self.format_output(
                char, move, vtrigger, data, frame_data, move_name, cmd_type="numCmd"
            )
            if "char_stat" not in data:
                embed_output = self.format_embeded_message(
                    char, move, vtrigger, data, cmd_type="numCmd"
                )
                return self.add_custom_fields(data, text_output, embed_output)
            return text_output


class SF6Frames(Frames):
    def __init__(self, config):
        super().__init__(config)
        self.url = config["frame_data"]["sf6_url"]
        self.detail_url = config["frame_data"]["sf6_detail_url"]

    @memoize(300)
    async def get_sf6_data(self, **kwargs):
        return await self._get_data(**kwargs)

    async def get_data(self, **kwargs):
        return await self.get_sf6_data()

    async def slash_sf6(self, char_name, move_name, state, **kwargs):
        frame_data = await self.get_data()
        if not frame_data:
            return "Got an error when trying to get frame data :(."

        matched_value = self.match_move(char_name, move_name, state, frame_data)

        if not matched_value:
            return (
                "%s with %s is not a valid " "character/move combination for SF6"
            ) % (char_name, move_name)
        else:
            char, move, data = matched_value
            text_output = self.format_output(
                char, move, state, data, frame_data, move_name, cmd_type="numCmd"
            )
            if "char_stat" not in data:
                embed_output = self.format_embeded_message(
                    char, move, state, data, cmd_type="numCmd"
                )
                return self.add_custom_fields(data, text_output, embed_output)
            return text_output
