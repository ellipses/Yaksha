#!/usr/bin/python
from commands import ifgc, actions, voting
import discord
import asyncio
import re
import yaml

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
    if message.author == client.user:
        return



    for command in client.commands.keys():
        msg = message.content
        user = message.author.mention
        if msg.lower().startswith(command.lower()):
            msg = msg[len(command):].strip()
            if command in client.async_commands:
                response = await getattr(client,
                                         client.commands[command])(msg, user, message.channel, client)
            else:
                response = getattr(client, client.commands[command])(msg, user)

            if response:
                await client.send_message(message.channel, response)
            break


def add_functions(config):
    '''
    '''
    streams = actions.Streams()
    frinkiac = actions.Frinkiac()
    gifs = actions.Gifs()
    arbitary = actions.Arbitary()
    tourney = actions.Tourney()
    boards = ifgc.Boards()
    frames = ifgc.Frames(config['frame_data'])

    commands = actions.AddCommands(config['add_commands']['discord'])
    votes = voting.Voting()
    reminders = actions.Reminder()

    client.get_frames = frames.get_frames
    client.simpsons_gif = frinkiac.get_gif
    client.captioned_gif = frinkiac.get_captioned_gif
    client.shuffle = arbitary.shuffle
    client.casuals = boards.get_thread_posters
    client.tourney = tourney.get_tourneys
    client.giffy_gif = gifs.get_gif

    client.translate_gif = gifs.get_translate_gif
    client.skins = arbitary.skins
    client.whens = streams.display_stream_list
    client.add_stream = streams.add_channel
    client.add_command = commands.add_command
    client.get_command = commands.get_command

    client.start_vote = votes.start_vote
    client.set_reminder = reminders.set_reminder
    client.my_mention = arbitary.get_my_mention

    client.commands = config['common-actions']
    client.commands.update(config['discord-actions'])
    client.commands.update(config['async_commands'])
    client.async_commands = config['async_commands']


def main():
    config_path = 'bots.yaml'
    config = yaml.load(open(config_path).read())
    add_functions(config)

    email = config['discord']['email']
    password = config['discord']['password']
    token = 'MTk0MTU2NzMwMjI4Mjc3MjQ4.CkikCg.NDRe0hFxOu_RGHenDordH-U6nQo'
    client.run(token)

if __name__ == '__main__':
    main()
