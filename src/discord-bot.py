#!/usr/bin/python
import interface
import logging
import discord
import asyncio
import re
import yaml
import os

logging.basicConfig(level=logging.INFO)
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
            response = await client.interface.call_command(
                command, msg, user, message.channel, client
            )
            if response:
                await send_message(response, message)
            break


async def send_message(response, message):
    # Response can be a single message or a
    # tuple of message and/or embed.
    em = None
    if isinstance(response, tuple):
        msg, em = response
    else:
        msg = response
    # Prepend the message with zero width white space char to
    # avoid bot loops.
    if msg:
        msg = '\u200B' + msg

    for _ in range(client.max_retries):
        try:
            await client.send_message(message.channel, msg, embed=em)
            break
        except discord.HTTPException:
            await asyncio.sleep(0.1)
    else:
        logging.error(
            'Failed to send message %s and embed %s to %s after %s retries' % (
                msg, em, message.channel, client.max_retries
            )
        )


def main():
    config_path = os.path.join(os.path.dirname(__file__),
                               '../conf/bots.yaml')
    config = yaml.load(open(config_path).read())
    client.commands = config.get('common_actions', {})
    client.commands.update(config.get('discord_actions', {}))
    client.commands.update(config.get('admin_actions', {}))
    client.max_retries = config.get('max_retries', 3)
    client.interface = interface.Interface(config, client.commands)

    token = config['discord']['token']
    client.run(token)


if __name__ == '__main__':
    main()
