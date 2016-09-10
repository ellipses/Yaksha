#!/usr/bin/python
import interface
import logging
import discord
import asyncio
import re
import yaml
import os

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
                # Append the message with zero with white space char to
                # avoid bot loops. 
                response = '\u200B' + response
                await client.send_message(message.channel, response)
            break


def main():
    config_path = os.path.join(os.path.dirname(__file__),
                               '../conf/bots.yaml')
    config = yaml.load(open(config_path).read())

    client.commands = config.get('common_actions', {})
    client.commands.update(config.get('discord_actions', {}))
    client.commands.update(config.get('admin_actions', {}))

    client.interface = interface.Interface(config, client.commands)

    token = config['discord']['token']
    client.run(token)

if __name__ == '__main__':
    main()
