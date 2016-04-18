#!/usr/bin/python
from twisted.internet import reactor, protocol
from twisted.words.protocols.irc import IRCClient
import requests
import json
import re


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

        payload = requests.get(self.api_prefix+channel_list)
        if payload.status_code == 200:
            data = json.loads(payload.content)
            return self.format_channels(data)
        else:
            print 'Failed getting steam data with error %s' % payload.content
            return False


class Bot(IRCClient):

    def __init__(self):
        self.stream = Streams()
        self.stream_re = r'^whens'

    def _get_nickname(self):
        return self.factory.nickname

    nickname = property(_get_nickname)

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)
        print 'Signed on as %s' % (self.nickname)

    def joined(self, channel):
        print 'Joined %s' % (channel)

    def privmsg(self, user, channel, message):
        if message == 'whens':
            self.msg(channel, self.stream.display_stream_list())
        if re.match(r'^!add', message):
            channel = re.search(r'^!add (\w+)', message).group(1)
            self.stream.add_channel(channel)


class BotFactory(protocol.ClientFactory):
    '''
    Factory that creates the bots and logs various connection issues.
    '''

    protocol = Bot

    def __init__(self, channels, nickname='Makara'):
        self.channels = channels
        self.nickname = nickname

    def startedConnecting(self, connector):
        print 'Started connecting'

    def clientConnectionFailed(self, connector, reason):
        print 'Connection failed because of %s. Trying to reconnect' % (reason)
        connector.connect()

    def clientConnectionLost(self, connector, reason):
        print 'Connection failed because of %s. Trying to reconnect' % (reason)
        connector.connect()


def main():
    print 'Hello World'
    channels = ['#irishfightinggames', '#sakurasf']
    reactor.connectTCP('irc.quakenet.org', 6667,
                       BotFactory(channels))
    reactor.run()

# Standard python boilerplate.
if __name__ == '__main__':
    main()
