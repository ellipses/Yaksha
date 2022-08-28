#!/usr/bin/python
import re
import base64
from urllib.parse import quote
from fuzzywuzzy import process
from commands.utilities import rate_limit, memoize, get_request, register, get_callbacks


class Shows:
    def __init__(self, config=None):
        # gif/episode/start_timestamp/end_timestamp.gif?b64lines=caption_in_base64
        self.interval = 500
        self.max_count = 31
        self.max_timespan = 6800
        self.char_limit = 20
        self.extend_regex = r"^-ex(\d?\.?\d?)?"
        self.max_extend = 6.9

    def get_max_sequence(self, timestamps, debug=False):
        """
        Helper function that returns the longest consequtive
        sequence of timestamps seperated by at most self.interval
        seconds.
        """
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
            print("Total")
            print(timestamps)
            print("Selected")
            print(total_seqs)

        # Only return up to max count to stay under timelimit.
        return total_seqs[index][: self.max_count]

    def get_episode(self, timestamps, debug=False):
        """
        Finds the most relevant episode for the given timestamps.
        Current alogrythm works by selecting the episode that
        has the longest sequence of consequtive timestamps
        seperated by self.interval seconds.
        """
        seq_list = [self.get_max_sequence(sorted(ts)) for ep, ts in timestamps.items()]
        seq_len = [len(seq) for seq in seq_list]

        if debug:
            print("seq list")
            print(seq_list)
            print("seq len")
            print(seq_len)
        return list(timestamps)[seq_len.index(max(seq_len))]

    def get_timestamps(self, screencaps, debug=False):
        """
        Helper function that iterates through the list returned
        by the api endpoint to find the episode and the longest
        sequence of timestamps.
        """
        episodes = {}
        timestamps = {}

        for screencap in screencaps:
            episode = screencap["Episode"]
            timestamp = screencap["Timestamp"]

            if episode in episodes:
                episodes[episode] += 1
                timestamps[episode].append(timestamp)
            else:
                episodes[episode] = 1
                timestamps[episode] = [timestamp]

        episode = self.get_episode(timestamps, debug=debug)

        if debug:
            print("epside count")
            print(episodes)
            print(episode)
            print("screencaps")
            print(screencaps)
            print("timestamps")
            print(timestamps)

        max_seq = self.get_max_sequence(sorted(timestamps[episode]), debug=debug)
        return episode, max_seq

    def format_message(self, message):
        """
        Formats the message by adding line breaks to prevent it
        from overflowing the gifs boundry. Line breaks are added
        at the end of a word to prevent it from being split.
        """
        char_buff = 0
        formated_msg = ""
        for word in message.split(" "):
            char_buff += len(word)
            formated_msg += " %s" % word
            if char_buff >= 18:
                char_buff = 0
                formated_msg += "\u000A"

        return formated_msg

    async def handle_caption(self, caption):
        """ """
        extend = False
        extend_amount = self.max_extend
        result = re.search(self.extend_regex, caption)
        caption = re.sub(self.extend_regex, "", caption).strip()
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
        screen_caps = await get_request(self.api_url % quote(caption), True)
        if not screen_caps or len(screen_caps) <= 1:
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
        """
        Method thats called when trying to get a Frinkiac url.
        Does basic error handling and calls handle_caption
        which does most of the actual work.
        """
        resp = await self.handle_caption(caption)
        if not resp:
            return "Try fixing your quote."
        episode, timestamps, caption = resp
        return self.gif_url % (episode, timestamps[0], timestamps[-1])

    async def get_captioned_gif(self, caption, user, *args, **kwargs):
        """
        Method thats called when trying to get a gif with
        a caption. Does basic error handling and base 64
        encoding and formatting of the caption.
        """
        resp = await self.handle_caption(caption)
        if not resp:
            return "Try fixing your quote."

        episode, timestamps, caption = resp
        caption = self.format_message(caption)
        try:
            encoded = str(base64.b64encode(str.encode(caption)), "utf-8")
        except TypeError:
            encoded = str(base64.b64encode(str.encode(caption)))
        return self.caption_url % (episode, timestamps[0], timestamps[-1], encoded)


class Simpsons(Shows):
    def __init__(self, config=None):
        config = config or {}
        super(Simpsons, self).__init__(config)
        self.gif_url = "https://frinkiac.com/gif/%s/%s/%s.gif"
        self.caption_url = "https://frinkiac.com/gif/%s/%s/%s.gif?b64lines=%s"
        self.api_url = "https://frinkiac.com/api/search?q=%s"

    @register("!simpsons")
    async def get_captioned_simpsons_gif(self, *args, **kwargs):
        return await super(Simpsons, self).get_captioned_gif(*args, **kwargs)


class Futurama(Shows):
    def __init__(self, config=None):
        config = config or {}
        super(Futurama, self).__init__(config)
        self.gif_url = "https://morbotron.com/gif/%s/%s/%s.gif"
        self.caption_url = "https://morbotron.com/gif/%s/%s/%s.gif?b64lines=%s"
        self.api_url = "https://morbotron.com/api/search?q=%s"

    @register("!futurama")
    async def get_captioned_futurama_gif(self, *args, **kwargs):
        return await super(Futurama, self).get_captioned_gif(*args, **kwargs)


class Arbitary:
    def __init__(self, config=None):
        self.config = config or {}

    async def charming(self, *args, **kwargs):
        return "https://goo.gl/46MdMF"


class Help:
    def __init__(self, config=None):
        self.config = config or {}
        self.cmd_ratio_thresh = 80

    @register("help")
    async def get_help_message(self, msg, *args, **kwargs):
        available_commands = kwargs.get("commands_dict", False)

        if available_commands:
            # Try fuzzy matching on the msg to determine the cmd
            # the user is trying to get help on.
            cmd, ratio = process.extractOne(msg, available_commands.keys())

            # If the ratio is too low we assume the user made
            # an error.
            if ratio < self.cmd_ratio_thresh:
                return (
                    "Allows you to get help on a command. The avaliable"
                    " commands are ```%s```" % list(available_commands.keys())
                )
            else:
                return available_commands[cmd]
        else:
            return "Dict of commands missing :/ ."
