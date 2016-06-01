#!/usr/bin/python
from twisted.internet import reactor, protocol
from twisted.words.protocols.irc import IRCClient
import utils
import re


class Bot(IRCClient):

    def __init__(self):
        self.frinkiac = utils.Frinkiac({})
        self.arbitary = utils.Arbitary({})
        self.gifs = utils.Gifs()
        self.boards = utils.Boards()
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
        if message[:9] == '!simpsons':
            response = self.frinkiac.get_gif(message[9:])
            self.msg(channel, response.encode('ascii', 'ignore'))

        elif message[:8] == '!shuffle':
            response = self.arbitary.shuffle(message[9:], user)
            self.msg(channel, response.encode('ascii', 'ignore'))

        elif message[:len('!gif')] == '!gif':
            response = self.gifs.get_gif(message[len('!gif'):], user)
            self.msg(channel, response.encode('ascii', 'ignore'))

        elif message[:len('!casuals')] == '!casuals':
            response = self.boards.get_thread_posters()
            self.msg(channel, response.encode('ascii', 'ignore'))

        elif message[:len('!tourney')] == '!tourney':
            response = self.arbitary.get_tourneys()
            self.msg(channel, response.encode('ascii', 'ignore'))


class BotFactory(protocol.ClientFactory):
    '''
    Factory that creates the bots and logs various connection issues.
    '''

    protocol = Bot

    def __init__(self, channels, nickname='Yaksha'):
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
    channels = ['tomtest', 'sakurasf', 'irishfightinggames']
    reactor.connectTCP('irc.quakenet.org', 6667,
                       BotFactory(channels))
    reactor.run()

# Standard python boilerplate.
if __name__ == '__main__':
    main()
