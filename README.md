## Yaksha

A general purpose discord and IRC bot written in Python. Uses Async version of discord.py and IRC3 for each version of the bot. 

A custom interface.py module is used instead of the discord cog extension to provide compatibility between the versions. 

## Running the bot

While its possible to self host the bot, I would prefer if you invited the bot to your channel using [invite link](https://discordapp.com/oauth2/authorize?client_id=194156698150240257&scope=bot&permissions=0x00000c00).

## Commands
A sample of the commands available to the bot, see [config file](conf/bots.yaml) for the full list. 

* '!gif': Returns the most relevant gif for the caption using Giffy. ```!gif obama mic drop```
* '!frames': 
    Get SFV frame data for the specified char and move. ```!frames Ryu cr.mk```
* '!simpsons': Get a simpsons gif that matches the specified caption. ```!simpsons nothing at all```
* '!vote': Start a vote in the channel for the specified length and
    topic, and options. ```!vote[--time] Vote topic [parameter1, parm2] ```  
* '!remindme': 
    Get Yaksha to remind to at a specified time similar to slackbot. ```!remindme <time period> [optional string]```
* '!whens': 'Get status of registered streams. Usage ```!whens```'
* '!shuffle': >
    Randomly select a word from a supplied list of words.
    Usage ```!shuffle yes no maybe```'
* '!help': 'Get help on a command. Usage ```!help command_name```'

  


