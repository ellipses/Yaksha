#!/usr/bin/python
from commands import ifgc, actions, voting
import asyncio
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

        self._loop = asyncio.get_event_loop()
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

    async def send_message(self, channel, message):
        '''
        Async send method to maintain compatibility
        with discord format.
        '''
        await asyncio.sleep(0)
        self.message(channel, message)
    
    def on_message(self, *args, **kwargs):
        '''
        Function thats calls when a a message is received.
        Starts up the async loop and calls handle message where
        the logic stuff is done.
        '''
        self._loop.run_until_complete(self.handle_message(*args, **kwargs))

    async def handle_message(self, channel, user, msg):
        '''
        Main method that determines how a received message is handled.
        '''
        if channel == self.nickname:
            await self.send_message(channel, ("Sneaky communication isn't nice,"
                                              " play with the group"))
        else:
            for command in self.commands.keys():
                if msg.lower().startswith(command.lower()):
                    msg = msg[len(command):].strip()
                    response = getattr(self, self.commands[command])(msg,
                                                                     user)

                    await self.send_message(channel, response)
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
