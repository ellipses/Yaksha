#!/usr/bin/python
import asyncio
import discord
import logging
from commands import ifgc, actions


class TreeHandling:
    def __init__(self, client, config):
        self.client = client
        sf_module = ifgc.Frames(config)
        gg_module = ifgc.GGFrames(config)
        actions_module = actions.Arbitary(config)
        self.command_mapping = {
            "sfv": sf_module.slash_sfv,
            "strive": gg_module.slash_strive,
            "ggst": gg_module.slash_strive,
            "charming": actions_module.charming,
        }

    async def handle_slash_command(self, interaction, command, *args, **kwargs):

        response = await self.command_mapping[command](*args, **kwargs)
        await self.send_message(interaction, response)

    async def send_message(self, interaction, response):
        # Response can be a single message or a
        # tuple of message and/or embed.
        em = None
        client = self.client

        if isinstance(response, tuple):
            msg, em = response
        else:
            msg = response
        # Prepend the message with zero width white space char to
        # avoid bot loops.
        if msg:
            msg = "\u200B" + msg

        for _ in range(client.max_retries):
            try:
                # Try sending only the embed message if it exists and fall
                # back to the text message.
                if em:
                    await interaction.response.send_message(None, embed=em)
                else:
                    await interaction.response.send_message(msg)

                break
            except discord.HTTPException as e:
                # Empty message error code which happens if you don't
                # have permission to send embed message.
                if e.code in [50006, 50013]:
                    try:
                        await interaction.response.send_message(msg)
                        break
                    except discord.HTTPException:
                        pass
                logging.exception("failed to send message")
                await asyncio.sleep(0.1)
        else:
            logging.error(
                "Failed sending %s and %s after %s retries"
                % (msg, em, client.max_retries)
            )
