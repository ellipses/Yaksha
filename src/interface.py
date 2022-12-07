#!/usr/bin/python
import asyncio
import discord
import logging
import libhoney
from functools import wraps
from commands import ifgc, actions
import time

CLIENT = None


def build_event(interaction, command, start_time):
    return libhoney.Event(
        data={
            "guild_name": interaction.guild.name,
            "guild_member_count": interaction.guild.member_count,
            "command": command,
            "response_time": time.time() - start_time,
            "message_time": time.time() - interaction.created_at.timestamp(),
            "user_response_time": time.time() - interaction.created_at.timestamp(),
            "latency": CLIENT.latency,
        }
    )

def monitor_slash_command(func):
    @wraps(func)
    async def func_wrapper(self, interaction, command, *args, **kwargs):
        start_time = time.time()
        result = await func(self, interaction, command, *args, **kwargs)
        ev = build_event(interaction, command, start_time)
        if len(args) == 2:
            ev.add({"char_name": args[0], "move_name": args[1]})
        return result

    return func_wrapper


def monitor_autocomplete(func):
    @wraps(func)
    async def func_wrapper(self, module_name, interaction, *args):
        start_time = time.time()
        ev = build_event(interaction, func.__name__, start_time)
        ev.add({"module_name": module_name, "char_name": args[0]})
        try:
            ev.add({"move_name": args[1]})
        except IndexError:
            pass

        result = await func(self, module_name, interaction, *args)

        ev.send()
        return result

    return func_wrapper


class TreeHandling:
    def __init__(self, client, config):
        self.client = client
        self.sf_module = ifgc.Frames(config)
        self.gg_module = ifgc.GGFrames(config)
        self.sf6_module = ifgc.SF6Frames(config)
        actions_module = actions.Arbitary(config)
        self.module_mapping = {
            "sfv": self.sf_module,
            "ggst": self.gg_module,
            "sf6": self.sf6_module,
        }
        self.command_mapping = {
            "sfv": self.sf_module.slash_sfv,
            "ggst": self.gg_module.slash_strive,
            "charming": actions_module.charming,
            "sf6": self.sf6_module.slash_sf6,
        }
        libhoney.init(
            writekey=config["honeycomb"]["api_key"],
            dataset=config["honeycomb"]["api_key"],
        )

    async def load(self, client):
        global CLIENT
        CLIENT = client
        start_time = time.time()
        for _, module in self.module_mapping.items():
            await module.get_data()
        print("Interface init time is")
        print(time.time() - start_time)

    @monitor_autocomplete
    async def autocomplete_char(self, module_name, _interaction, char_name):
        return await self.module_mapping[module_name].autocomplete_char(char_name)

    @monitor_autocomplete
    async def autocomplete_move(self, module_name, _interaction, char_name, move_name):
        return await self.module_mapping[module_name].autocomplete_move(
            char_name, move_name
        )

    @monitor_autocomplete
    async def autocomplete_char_state(
        self, module_name, _interaction, char_name, state_name
    ):
        return await self.module_mapping[module_name].autocomplete_char_state(
            char_name, state_name
        )

    @monitor_slash_command
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
