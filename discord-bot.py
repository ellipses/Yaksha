#!/usr/bin/python
import discord
import asyncio
import re
from utils import Streams

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
		print(server)


@client.event
async def on_message(message):
	if message.content.startswith('!add'):
		channel = re.search(r'^!add (\w+)', message.content).group(1)
		client.streams.add_channel(channel)
		await client.send_message(message.channel, 'Added channel %s' % channel)
	elif message.content.startswith('whens'):
		await client.send_message(message.channel, client.streams.display_stream_list())
	elif message.content.startswith('!sleep'):
		await asyncio.sleep(5)
		await client.send_message(message.channel, 'Done sleeping')


def main():
	client.streams = Streams()
	# NEED TO MAKE THIS CONFIG
	email = ''
	password = ''
	client.run(email, password)


if __name__ == '__main__' :
	main()



