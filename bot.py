#!/usr/bin/python
from commands import ifgc, actions, voting
import pydle
import yaml
import time


class MessageLogger:
    '''
    Very basic logger class, that does what it says on the box.
    '''
    def __init__(self, file):
        self.file = file

    def log(self, message):
        timestamp = time.strftime("[%H:%M:%S]", time.localtime(time.time()))
        self.file.write('%s %s\n' % (timestamp, message))
        # self.file.flush()

    def close(self):
        self.file.close()

'''
class Bot():

    def __init__(self):
        config_path = 'bots.yaml'
        config = yaml.load(open(config_path).read())
        self.loggers = {}
        frinkiac = utils.Frinkiac()
        arbitary = utils.Arbitary()
        gifs = utils.Gifs()
        boards = utils.Boards()
        frames = utils.Frames(config['frame_data'])
        commands = utils.AddCommands(config['add_commands']['irc'])  

        self.simpsons_gif = frinkiac.get_gif
        self.captioned_gif = frinkiac.get_captioned_gif
        self.shuffle = arbitary.shuffle
        self.casuals = boards.get_thread_posters
        self.tourney = arbitary.get_tourneys
        self.giffy_gif = gifs.get_gif
        self.get_frames = frames.get_frames
        self.add_command = commands.add_command
        self.get_command = commands.get_command

        self.commands = config['common-actions']
        # self.commands.update(config['irc-actions'])

    def _get_nickname(self):
        return self.factory.nickname

    nickname = property(_get_nickname)

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)
            filename = '%s_logs.txt' % channel
            self.loggers[channel] = MessageLogger(open(filename, "a"))

        print ('Signed on as %s' % self.nickname)

    def joined(self, channel):
        print ('Joined %s' % channel)

    def privmsg(self, user, channel, message):

        if channel == self.nickname:
            self.msg(channel, ("Sneaky communication isn't nice,"
                               " play with the group"))
        else:
            for command in self.commands.keys():
                if message.lower().startswith(command.lower()):
                    message = message[len(command):].strip()
                    response = getattr(self, self.commands[command])(message,
                                                                     user)
                    self.msg(channel, response.encode('ascii', 'ignore'))
                    break
            user = user.split('!', 1)[0]
            self.loggers[channel[1:].lower()].log("<%s> %s" % (user, message))
'''

class MyClient(pydle.Client):

    def __init__(self, channels, *args, **kwawgs):
        '''
        '''
        self.channels_to_join = channels
        config_path = 'bots.yaml'
        self.config = yaml.load(open(config_path).read())

        frinkiac = actions.Frinkiac()
        arbitary = actions.Arbitary()
        gifs = actions.Gifs()
        tourney = actions.Tourney()
        boards = ifgc.Boards()
        frames = ifgc.Frames(self.config['frame_data'])
        commands = actions.AddCommands(self.config['add_commands']['irc'])

        self.simpsons_gif = frinkiac.get_gif
        self.captioned_gif = frinkiac.get_captioned_gif
        self.shuffle = arbitary.shuffle
        self.casuals = boards.get_thread_posters
        self.tourney = tourney.get_tourneys
        self.giffy_gif = gifs.get_gif
        self.get_frames = frames.get_frames
        self.add_command = commands.add_command
        self.get_command = commands.get_command  

        self.commands = self.config['common-actions']

        super().__init__(*args, **kwawgs)

    def add_commands(self):
        '''
        '''
        pass

    def on_connect(self):
        '''
        '''
        for channel in self.channels_to_join:
            self.join(channel)
            print('Connected to %s' % channel) 

    def on_message(self, channel, user, msg):
        '''
        '''
        if channel == self.nickname:
            self.message(channel, ("Sneaky communication isn't nice,"
                                   " play with the group"))
        else:
            for command in self.commands.keys():
                if msg.lower().startswith(command.lower()):
                    msg = msg[len(command):].strip()
                    response = getattr(self, self.commands[command])(msg,
                                                                     user)
                    self.message(channel, response)
                    break


def main():
    print ('Starting up the bot.')

    channels = ['#tomtest']
    client = MyClient(channels, nickname='Yaksha',
                      username='Yaksha', realname='Yaksha')
    # Client.connect() is a blocking function.
    client.connect('irc.quakenet.org', 6667)
    print('Finished Connecting')
    client.handle_forever()


if __name__ == '__main__':
    main()
