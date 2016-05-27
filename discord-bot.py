#!/usr/bin/python
import discord
import asyncio
import re
import yaml
import utils

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
    '''
    List of commands that are perfomed by the bot.

    !add channel: adds the channel to the channel.txt text file.

    !whens: Lists the currently online streams, title and current viewers.
            Based on the list of channels in channel.txt

    !simpsons caption: Returns a gif from Frinkiac containing the caption.
    '''
    if message.content.startswith('!add'):
        channel = re.search(r'^!add (\w+)', message.content).group(1)
        client.streams.add_channel(channel)
        await client.send_message(message.channel,
                                 'Added channel https://twitch.tv/%s' % channel)

    elif message.content.startswith('whens'):
        await client.send_message(message.channel,
                                  client.streams.display_stream_list())

    elif message.content.startswith('!simpsonscaption'):
        caption = message.content.strip('!simpsonscaption')
        await client.send_message(message.channel,
                            client.frinkiac.get_gif(caption, text=True))

    elif message.content.startswith('!simpsons'):
        caption = message.content.strip('!simpsons')
        await client.send_message(message.channel,
                            client.frinkiac.get_gif(caption))

    elif message.content.startswith('!sleep'):
        await asyncio.sleep(5)
        await client.send_message(message.channel, 'Done sleeping')


def main():
    client.streams = utils.Streams()
    client.frinkiac = utils.Frinkiac()
    config_path = 'bots.yaml'
    config = yaml.load(open(config_path).read())
    email = config['discord']['email']
    password = config['discord']['password']
    client.run(email, password)

if __name__ == '__main__' :
    main()
