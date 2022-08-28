#!/usr/bin/python
from googleapiclient.discovery import build
import functools
import isodate
import logging
import interface
import asyncio
import irc3
import yaml
import os
import re


@irc3.plugin
class MyClient(object):
    def __init__(self, bot):
        self.bot = bot
        self.nick = self.bot.get_nick()
        config_path = os.path.join(os.path.dirname(__file__), "../conf/bots.yaml")
        self.config = yaml.load(open(config_path).read())
        self.channels = self.config["irc"]["channels"]
        self.commands = self.config.get("common_actions", {})
        self.commands.update(self.config.get("irc_actions", {}))
        self.commands.update(self.config.get("admin_actions", {}))
        self.url_enabled_channels = self.config.get("youtube", {}).get(
            "url_enabled_channels", []
        )
        self.interface = interface.Interface(self.config, self.commands)
        self.youtube_regex = (
            "(?:https?://)?(?:www.)?(?:youtube.com|youtu.be)/(?:watch\?)?v=([^\s]+)"
        )
        self.build_youtube_service()

    def build_youtube_service(self):
        try:
            self.service = build(
                "youtube", "v3", developerKey=self.config["youtube"]["api_key"]
            )
        except KeyError:
            logging.info("Starting without youtube service")
            self.service = None

    @irc3.event(irc3.rfc.CONNECTED)
    def connected(self, **kw):
        for channel in self.channels:
            self.bot.join(channel)
            print("Joined %s" % channel)

    async def send_message(self, channel, message):
        """
        Async send method to maintain compatibility
        with discord format.
        """
        await self.bot.privmsg(channel, message)

    @irc3.event(irc3.rfc.PRIVMSG)
    async def on_privmsg(self, mask, data, target, **kw):
        """
        irc3 method thats called everytime there is a message.
        Doesn't do anything except pass it on to method that
        actually handles it.
        args:
            mask: user
            data: message
            target: channel
        """
        await self.handle_message(mask, data, target)

    async def check_url_parsing(self, msg, channel):
        if channel in self.url_enabled_channels:
            match_obj = re.search(self.youtube_regex, msg)
            if match_obj:
                await self.return_youtube_title(channel, match_obj.group(1))

    async def return_youtube_title(self, channel, video_id):
        if self.service:
            result = await asyncio.get_event_loop().run_in_executor(
                None, functools.partial(self.perform_youtube_request, video_id)
            )
            if result:
                msg = "YouTube: %s (%s)" % result
                await self.send_message(channel, msg)

    def perform_youtube_request(self, video_id):
        try:
            result = (
                self.service.videos()
                .list(part="snippet, contentDetails", id=video_id)
                .execute()["items"][0]
            )
            title = result["snippet"]["title"]
            duration = isodate.parse_duration(result["contentDetails"]["duration"])
            mins = int(duration.seconds / 60)
            seconds = int(duration.seconds - mins * 60)
            return (title, "%s:%s" % (mins, seconds))
        # Pokemon exception catching because we dont care as much about parsing
        # youtube titles.
        except Exception:
            logging.exception("failed to obtain youtube title")
            return None

    async def handle_message(self, user, msg, channel):
        """
        Main method that determines how a received message is handled.
        """
        # Don't bother doing anything with msgs sent by us.
        if self.nick != user[: len(self.nick)]:
            # Only bother with non private msgs.
            if channel != self.nick:
                await self.check_url_parsing(msg, channel)
                for command in self.commands.keys():
                    if msg.lower().startswith(command.lower()):
                        msg = msg[len(command) :].strip()
                        command = command.lower()
                        response = await self.interface.call_command(
                            command, msg, user, channel, self
                        )

                        if response:
                            if isinstance(response, tuple):
                                response, _ = response
                            await self.send_message(channel, response)
                        break
