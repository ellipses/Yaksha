#!/usr/bin/python
import requests
import base64
import json


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

    def __init__(self):
        # gif/episode/start_timestamp/end_timestamp.gif?b64lines=caption_in_base64
        self.gif_url = 'https://frinkiac.com/gif/%s/%s/%s.gif'
        self.caption_url = 'https://frinkiac.com/gif/%s/%s/%s.gif?b64lines=%s'
        self.api_url = 'https://frinkiac.com/api/search?q=%s'
        self.interval = 350
        self.max_count = 31
        self.max_timespan = 6200  # 31 * 200

    def get_max_sequence(self, timestamps):
        '''
        '''
        # Find the longest sequence
        total_seqs = []
        current_seq = []
        prev_value = timestamps[0]
        for value in timestamps[1:]:
            if value - prev_value > self.interval:
                total_seqs.append(current_seq)
                current_seq = []

            current_seq.append(value)
            prev_value = value
        total_seqs.append(current_seq)

        seq_lens = [len(seq) for seq in total_seqs]
        index = seq_lens.index(max(seq_lens))
        # Only return up to max count to stay under timelimit
        return total_seqs[index][:self.max_count]

    def get_timestamps(self, screencaps):
        '''
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

        # If the most common episode
        # Get the first one if more than 1 exist.
        max_count = max(episodes.values())
        for name, count in episodes.items():
            if count == max_count:
                episode = name
                break

        max_seq = self.get_max_sequence(sorted(timestamps[episode]))
        return episode, max_seq

    def get_gif(self, caption, text=False):
        # Hit the api endpoint to get a list of screencaps
        # that the relevant to the caption.
        response = requests.get(self.api_url % caption)
        screen_caps = json.loads(response.text)

        if len(screen_caps) == 0:
            message = 'Try saying a line that actually exists'
            return message

        # Find the most common episode and longest sequence of
        # timestamps.
        episode, timestamps = self.get_timestamps(screen_caps)

        if text:
            encoded = str(base64.b64encode(str.encode(caption)), 'utf-8')
            return self.caption_url % (episode, timestamps[0], timestamps[-1], encoded)
        else:
            return self.gif_url % (episode, timestamps[0], timestamps[-1])
