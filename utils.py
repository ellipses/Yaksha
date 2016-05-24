#!/usr/bin/python
import requests
import json


class Streams():

    def __init__(self):
        self.file = 'channels.txt'
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
            return 'No streams online'.encode('ascii', 'ignore')

        message = 'Streams online:'

        for stream in payload['streams']:
            url = stream['channel']['url']
            viewers = stream['viewers']
            title = stream['channel']['status']

            channel_format = ' %s (%s) [%d] |'
            message += channel_format % (url, title, viewers)

        return message.encode('ascii', 'ignore')

    def display_stream_list(self):
        channels = self.get_channels()
        channel_list = (',').join(channels.split(' '))

        payload = requests.get(self.api_prefix + channel_list)
        if payload.status_code == 200:
            data = json.loads(payload.content)
            return self.format_channels(data)
        else:
            print 'Failed getting steam data with error %s' % payload.content
            return False
