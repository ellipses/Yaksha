## Yaksha

A general purpose discord and IRC bot written in Python. Uses Async version of discord.py and IRC3 for each version of the bot.

A custom interface.py module is used instead of the discord cog extension to provide compatibility between the versions.

## Running the bot

While its possible to self host the bot, I would prefer if you invited the bot to your channel using [invite link](https://discordapp.com/oauth2/authorize?client_id=194156698150240257&scope=bot&permissions=0x00000c00).

## Commands
A sample of the commands available to the bot, see [config file](conf/bots.yaml) for the full list.

* !frames:
    Get SFV frame data for the specified char and move. ```!frames Ryu cr.mk```
* !ggst:
    Get GG Strive frame data for the specified char and move ```!ggst Sol far s```
* !simpsons: Get a simpsons gif that best matches the specified caption. ```!simpsons nothing at all```
* !futurama: Get a futurama gif that best matches the specified caption. ```!futurama Shut up and take my money! The new eyephone is wonderful```
* !help: 'Get help on a command. Usage ```!help command_name```




