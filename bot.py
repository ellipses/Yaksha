#!/usr/bin/python
from twisted.internet import reactor, protocol
from twisted.words.protocols.irc import IRCClient


class Bot(IRCClient):

    def _get_nickname(self):
        return self.factory.nickname

    nickname = property(_get_nickname)

    def signedOn(self):
        self.join(self.factory.channel)
        print 'Signed on as %s' % (self.nickname)


class BotFactory(protocol.ClientFactory):

    protocol = Bot

    def __init__(self, channel, nickname='Makara'):
        self.channel = channel
        self.nickname = nickname


def main():
    print 'Hello World'
    reactor.connectTCP('irc.quakenet.org', 6667,
                       BotFactory('#sakurasf'))
    reactor.run()

# Standard python boilerplate.
if __name__ == '__main__':
    main()
