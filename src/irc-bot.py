#!/usr/bin/python
import interface
import asyncio
import irc3
import yaml
import os


@irc3.plugin
class MyClient(object):

    def __init__(self, bot):
        self.bot = bot
        self.nick = self.bot.get_nick()
        self.channels = ['#tomtest']
        config_path = os.path.join(os.path.dirname(__file__),
                                   '../conf/bots.yaml')
        self.config = yaml.load(open(config_path).read())

        self.commands = self.config['common_actions']
        irc_commands = self.config['irc_actions']
        admin_commands = self.config['admin_actions']
        if irc_commands:
            self.commands.update(irc_commands)
        if admin_commands:
            self.commands.update(admin_commands)
        self.interface = interface.Interface(self.config, self.commands)

    @irc3.event(irc3.rfc.CONNECTED)
    def connected(self, **kw):
        for channel in self.channels:
            self.bot.join(channel)
            print('Joined %s' % channel)

    async def send_message(self, channel, message):
        '''
        Async send method to maintain compatibility
        with discord format.
        '''
        await self.bot.privmsg(channel, message)

    @irc3.event(irc3.rfc.PRIVMSG)
    async def on_privmsg(self, mask, data, target, **kw):
        '''
        irc3 method thats called everytime there is a message.
        Doesn't do anything except pass it on to method that
        actually handles it.
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
        # Don't bother doing anything with msgs sent by us.
        if self.nick != user[:len(self.nick)]:
            # Only bother with non private msgs.
            if channel != self.nick:
                for command in self.commands.keys():
                    if msg.lower().startswith(command.lower()):
                        msg = msg[len(command):].strip()
                        command = command.lower()
                        response = await self.interface.call_command(command,
                                                                     msg, user,
                                                                     channel,
                                                                     self)

                        if response:
                            await self.send_message(channel, response)
                        break
