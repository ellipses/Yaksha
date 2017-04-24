#!/usr/bin/python
import re
import os
import yaml
import logging
import discord
import asyncio
import requests
import interface
import functools
import itertools


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

    if message.server.id in client.config.get('ignored_servers', []):
        return

    for command in client.commands.keys():
        msg = message.content
        user = message.author.mention
        if msg.lower().startswith(command.lower()):

            msg = msg[len(command):].strip()
            command = command.lower()
            response = await client.interface.call_command(
                command, msg, user, message.channel, client,
                server=message.server.id
            )
            if response:
                await send_message(response, message)
            break


async def change_status(config):
    """
    Update the "Playing x" status to display bot
    commands.
    """
    await client.wait_until_ready()
    commands = itertools.chain(
        config['common_actions'].keys(),
        config.get('discord_actions', {}).keys()
    )
    for cmd in itertools.cycle(commands):
        display_cmd = '?help | %s' % cmd
        game = discord.Game(name=display_cmd)
        try:
            await client.change_presence(game=game)
        except discord.HTTPException:
            # Might've gotten ratelimited so just sleep for the
            # interval and try later.
            logging.exception('Exception when trying to change status.')
            pass
        await asyncio.sleep(
            config.get('discord', {}).get('status_interval', 3600)
        )


async def post_request():
    future = client.loop.run_in_executor(
        None, functools.partial(
            requests.get, 'http://www.google.com'
        )
    )
    resp = await future
    if not resp:
        logging.error(
            'Posting stats failed with %s because %s',
            resp.status_code, resp.content
        )


async def publish_stats(config):
    """
    Publish information on the number of servers we belong
    to.
    """
    await client.wait_until_ready()
    try:
        headers = {
            'Authorization': config['stats']['token']
        }
        url = config['stats']['url'].format(bot_id=client.user.id)
    except KeyError:
        logging.error(
            'Token not present in config so starting without ability'
            ' to publish stats.'
        )
        return None

    while True:
        payload = {
            "server_count": len(client.servers)
        }
        try:
            await make_request()
        except Exception:
            # Pokemon exception catching because we dont want errors
            # with stats update to affect the normal operation.
            logging.exception('Failed to update stats')

        await asyncio.sleep(config['stats'].get('interval', 3600))


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
            # Try sending only the embded message if it exists and fall
            # back the the text message.
            if em:
                await client.send_message(message.channel, None, embed=em)
            else:
                await client.send_message(message.channel, msg)
            break
        except discord.HTTPException as e:
            # Empty message error code which happens if you don't
            # have permission to send embeded message.
            if e.code in [50006, 50013]:
                try:
                    await client.send_message(message.channel, msg)
                    break
                except discord.HTTPException:
                    pass
            logging.exception('failed to send message')
            await asyncio.sleep(0.1)
    else:
        logging.error(
            'Failed sending %s and %s to %s in %s after %s retries' % (
                msg, em, message.channel, message.server, client.max_retries
            )
        )


def main():
    config_path = os.path.join(os.path.dirname(__file__),
                               '../conf/bots.yaml')
    config = yaml.load(open(config_path).read())
    client.commands = config.get('common_actions', {}).copy()
    client.commands.update(config.get('discord_actions', {}))
    client.commands.update(config.get('admin_actions', {}))
    client.max_retries = config.get('max_retries', 3)
    client.config = config
    client.interface = interface.Interface(config, client.commands)

    token = config['discord']['token']
    client.loop.create_task(change_status(config))
    client.loop.create_task(publish_stats(config))
    client.run(token)


if __name__ == '__main__':
    main()
