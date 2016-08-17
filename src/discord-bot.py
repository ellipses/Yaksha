#!/usr/bin/python

import interface
import logging
import discord
import asyncio
import re
import yaml
import os

global client
client = discord.Client()


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('--------')
    servers = client.servers
    for server in servers:
        print('Joined server %s' % server)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    for command in client.commands.keys():
        msg = message.content
        user = message.author.mention
        if msg.lower().startswith(command.lower()):
            msg = msg[len(command):].strip()
            command = command.lower()
            response = await client.interface.call_command(command,
                                                           msg, user,
                                                           message.channel,
                                                           client)
            if response:
                await client.send_message(message.channel, response)
            break


def main():
    config_path = os.path.join(os.path.dirname(__file__),
                               '../conf/bots.yaml')
    config = yaml.load(open(config_path).read())
    client.commands = config['common_actions']
    discord_commands = config['discord_actions']
    admin_commands = config['admin_actions']

    if discord_commands:
        client.commands.update(discord_commands)
    if admin_commands:
        client.commands.update(admin_commands)

    client.interface = interface.Interface(config, client.commands)

    token = config['discord']['token']
    client.run(token)

if __name__ == '__main__':
    main()
