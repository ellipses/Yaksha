#!/usr/bin/python
from twisted.internet import reactor, protocol
from twisted.words.protocols.irc import IRCClient
import utils
import yaml


class Bot(IRCClient):

    def __init__(self):
        config_path = 'bots.yaml'
        config = yaml.load(open(config_path).read())

        frinkiac = utils.Frinkiac()
        arbitary = utils.Arbitary()
        gifs = utils.Gifs()
        boards = utils.Boards()

        self.simpsons_gif = frinkiac.get_gif
        self.shuffle = arbitary.shuffle
        self.casuals = boards.get_thread_posters
        self.tourney = arbitary.get_tourneys
        self.giffy_gif = gifs.get_gif

        self.commands = config['common-actions']
        self.commands.update(config['irc-actions'])

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
        for command in self.commands.keys():
            if message.startswith(command):
                message = message[len(command):].strip()
                response = getattr(self, self.commands[command])(message, user)
                self.msg(channel, response.encode('ascii', 'ignore'))
                break


class BotFactory(protocol.ClientFactory):
    '''
    Factory that creates the bots and logs various connection issues.
    '''

    protocol = Bot

    def __init__(self, channels, nickname='Yaksha-staging'):
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
