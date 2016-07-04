#!/usr/bin/python
from commands import ifgc,  voting
import asyncio
import irc3
import yaml

@irc3.plugin
class MyClient(object):

    def __init__(self, bot):

        print('init')
        self.bot = bot
        self.nick = self.bot.get_nick()
        self.channels = ['#tomtest']
        config_path = 'bots.yaml'
        self.config = yaml.load(open(config_path).read())
        
        '''
        frinkiac = actions.Frinkiac()
        arbitary = actions.Arbitary()
        gifs = actions.Gifs()
        tourney = actions.Tourney()
        boards = ifgc.Boards()
        frames = ifgc.Frames(self.config['frame_data'])
        commands = actions.AddCommands(self.config['add_commands']['irc'])
        '''

        votes = voting.Voting()
        '''
        self.simpsons_gif = frinkiac.get_gif
        self.captioned_gif = frinkiac.get_captioned_gif
        self.shuffle = arbitary.shuffle
        self.casuals = boards.get_thread_posters
        self.tourney = tourney.get_tourneys
        self.giffy_gif = gifs.get_gif
        self.get_frames = frames.get_frames
        self.add_command = commands.add_command
        self.get_command = commands.get_command  
        '''
        self.start_vote = votes.start_vote
        self.commands = self.config['common-actions']
        self.commands.update(self.config['async_commands'])
        self.async_commands = self.config['async_commands']
    

    @irc3.event(irc3.rfc.CONNECTED)
    def connected(self, **kw):
        for channel in self.channels:
            self.bot.join(channel)

    async def send_message(self, channel, message):
        '''
        Async send method to maintain compatibility
        with discord format.
        '''
        await self.bot.privmsg(channel, message)

    @irc3.event(irc3.rfc.PRIVMSG)
    async def on_privmsg(self, mask, data, target, **kw):
        '''
        args:
            mask: user
            data: message
            target: channel
        '''
        await self.handle_message(mask, data, target)

    async def handle_message(self, user, msg, channel):
        '''
        Main method that determines how a received message is handled.
        '''
        if channel == '#%s' % self.nick:
            await self.send_message(channel, ("Sneaky communication isn't nice,"
                                              " play with the group"))
        else:
            for command in self.commands.keys():
                if msg.lower().startswith(command.lower()):
                    msg = msg[len(command):].strip()
                    if command in self.async_commands:
                        response = await getattr(self, self.commands[command])(msg,
                                                                     user,channel, self)
                    else:
                        response = await getattr(self, self.commands[command])(msg,
                                                                     user)
                    if response:
                        await self.send_message(channel, response)
                    break
