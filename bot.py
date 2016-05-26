#!/usr/bin/python
from twisted.internet import reactor, protocol
from twisted.words.protocols.irc import IRCClient
from utils import Streams
import re


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
        print ('Signed on as %s' % self.nickname)

    def joined(self, channel):
        print ('Joined %s' % channel)

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
        print ('Started connecting')

    def clientConnectionFailed(self, connector, reason):
        print ('Connection failed because of %s. Trying to reconnect' % reason)
        connector.connect()

    def clientConnectionLost(self, connector, reason):
        print ('Connection failed because of %s. Trying to reconnect' % reason)
        connector.connect()


def main():
    print ('Starting up the bot.')
    channels = ['tomtest']
    reactor.connectTCP('irc.quakenet.org', 6667,
                       BotFactory(channels))
    reactor.run()

# Standard python boilerplate.
if __name__ == '__main__':
    main()
