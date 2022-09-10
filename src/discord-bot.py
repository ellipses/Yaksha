#!/usr/bin/python
import os
import yaml
import logging
import discord
import asyncio
import interface
from typing import Optional
from typing import Literal, List
import time

start_time = time.time()
from discord import app_commands

logging.basicConfig(level=logging.INFO)


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print("Logged in as")
        print(client.user.name)
        print(client.user.id)
        print("--------")
        for guild in client.guilds:
            print("Joined guild %s" % guild)
        print("total time")
        print(time.time() - start_time)

    async def update_playing_status(self):
        """
        Update the "Playing x" status to display bot
        commands.
        """
        await self.wait_until_ready()
        display_cmd = "/sfv | /ggst"
        game = discord.Game(name=display_cmd)
        while not self.is_closed():
            try:
                await client.change_presence(activity=game)
            except discord.HTTPException:
                # Might've gotten ratelimited so just sleep for the
                # interval and try later.
                logging.exception("Exception when trying to change status.")
            await asyncio.sleep(
                self.config.get("discord", {}).get("status_interval", 3600)
            )

    async def setup_hook(self):
        self.loop.create_task(self.update_playing_status())
        self.loop.create_task(self.tree_interface.load())
        debug_guild_id = self.config["discord"].get("debug_guild_id")
        if debug_guild_id:
            debug_guild = discord.Object(id=debug_guild_id)
            # This copies the global commands over to your guild.
            self.tree.copy_global_to(guild=debug_guild)
            await self.tree.sync(guild=debug_guild)
        else:
            await self.tree.sync()


config_path = os.path.join(os.path.dirname(__file__), "../conf/bots.yaml")
config = yaml.load(open(config_path).read())
client = MyClient(
    intents=discord.Intents.default(),
    application_id=config["discord"]["application_id"],
)


@client.tree.command()
@app_commands.describe(
    char_name="The characters name",
    move_name="The move name",
    vtrigger="Optional vtrigger mode",
)
async def sfv(
    interaction: discord.Interaction,
    char_name: str,
    move_name: str,
    vtrigger: Optional[Literal["vt1", "vt2"]],
):
    """Get SFV frame data for the specific char and move.

    Also works with stats of the char like fdash, bdash, throw range etc."""
    return await client.tree_interface.handle_slash_command(
        interaction, "sfv", char_name, move_name, vtrigger
    )


def populate_choices(values):
    return [app_commands.Choice(name=value, value=value) for value in values]


@client.tree.command()
@app_commands.describe(
    char_name="The characters name",
    move_name="The move name",
)
async def ggst(interaction: discord.Interaction, char_name: str, move_name: str):
    """Get Guilty Gear Strive frame data for the specific char and move.

    Also works with stats of the char like fdash, bdash, throw range etc."""
    return await client.tree_interface.handle_slash_command(
        interaction, "ggst", char_name, move_name
    )


@sfv.autocomplete("char_name")
async def char_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return populate_choices(
        await client.tree_interface.autocomplete_char("sfv", current)
    )


@sfv.autocomplete("move_name")
async def move_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    if not interaction.namespace.char_name:
        return populate_choices([])

    else:
        return populate_choices(
            await client.tree_interface.autocomplete_move(
                "sfv", interaction.namespace.char_name, current
            )
        )


@ggst.autocomplete("char_name")
async def char_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    return populate_choices(
        await client.tree_interface.autocomplete_char("ggst", current)
    )


@ggst.autocomplete("move_name")
async def move_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    if not interaction.namespace.char_name:
        return populate_choices([])

    else:
        return populate_choices(
            await client.tree_interface.autocomplete_move(
                "ggst", interaction.namespace.char_name, current
            )
        )


@client.tree.command()
async def charming(interaction: discord.Interaction):
    """charming"""
    return await client.tree_interface.handle_slash_command(interaction, "charming")


def main():
    client.commands = config.get("common_actions", {}).copy()
    client.commands.update(config.get("discord_actions", {}))
    client.commands.update(config.get("admin_actions", {}))
    client.max_retries = config.get("max_retries", 3)
    client.config = config
    client.tree_interface = interface.TreeHandling(client, config)
    token = config["discord"]["token"]
    client.run(token)


if __name__ == "__main__":
    main()
