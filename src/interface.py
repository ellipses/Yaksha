#!/usr/bin/python
'''
Module that functions as an interface between the commands and the irc/discord
libaries. Provides a common inteface that allows the commands to function the
same regardless of which version of the bot is instantiated.

There are three main components to the interface class. remap_functions which
creates a dictionary of commands and the functions, call_command which
handles each valid command received by the bot and user_has_permission
which checks if the user has permission to call the specific command.
'''
from commands import ifgc, voting, actions
from commands import utilities
from graphiteudp import GraphiteUDPClient
import asyncio
import re

class Interface():

    def __init__(self, config, bot_commands):
        self._func_mapping = {}
        self._class_mapping = {}
        self.no_cache_pattern = r'--nocache'
        self._modules = [ifgc, voting, actions]
        self.config = config
        self.registered_commands = bot_commands

        self.remap_functions()

        self.blacklisted_users = self.get_blacklisted_users()
        self.admin_actions = self.config.get('admin_actions', {}).keys()
        self.admins = self.config.get('admins', [])

        try:
            prefix = '%s.yaksha' % config['graphite']['key']
            self.metrics = GraphiteUDPClient(host=config['graphite']['host'],
                                             port=config['graphite']['port'],
                                             prefix=prefix)
            self.invalid_metric_chars = r'[\s?!-/.#]'
        except KeyError:
            self.metrics = None

    def remap_functions(self):
        '''
        Utilities.get_callbacks() returns a dictionary mapping of
        each command with the name of the function to be called.

        The name of the function is replaced by this function
        with a reference to the function and the class it belongs
        to. This is later used by self.call_command when handling 
        messages.
        '''
        name_mapping = utilities.get_callbacks()

        for key, value in name_mapping.items():
            class_name, func_name = value[0].split('.')
            module_name = value[1]
            # Go through the imported modules to determine which
            # module the class belongs to.
            for module in self._modules:
                if module.__name__ != module_name:
                    continue
                else:
                    class_ref = getattr(module, class_name)
                    func_ref = getattr(class_ref, func_name)

                    # Check if we already have a reference to
                    # this class and add it if not.
                    if class_name not in self._class_mapping:
                        self._class_mapping[class_name] = class_ref

                    # Replace the function name with a tuple
                    # containing a reference to the function and
                    # the class name. The class name will be used
                    # get the correct class from self._class_mapping.
                    self._func_mapping[key] = (func_ref, class_name)

                    # We found the module so there is no need for further
                    # iterations.
                    break

        # Go through the class mapping and replace references to the classes
        # with their instances.
        for name, instance in self._class_mapping.items():
            self._class_mapping[name] = instance(self.config)

    async def call_command(self, command, msg, user, channel, *args, **kwargs):
        '''
        Determines which function to call from the func_mapping
        dict using the command arg as the key.
        Also allows you to 'refresh' the cache by passing '--nocache' in
        the message.
        '''
        func, class_name = self._func_mapping[command]
        await self.send_metrics(command, channel)
        # First check if the user is allowed to call this
        # function.
        if self.user_has_permission(user, command):

            # Check if we shouldn't use the cache.
            if re.search(self.no_cache_pattern, msg):
                msg = re.sub(self.no_cache_pattern, '', msg).strip()
                kwargs['no_cache'] = True

            # Special case if its the help command that requires you
            # to pass in the available commands.
            if command == '?help':
                kwargs['commands_dict'] = self.registered_commands
            # Another special case for the blacklist commands that requires
            # current list of blacklisted to be passed in so it can be updated.
            # Could instead have a seperate thread that periodically reads from
            # the file to update it, not sure. Suggestions welcome.
            elif command in ['!blacklist', '!unblacklist']:
                kwargs['blacklisted_users'] = self.blacklisted_users
            # Call the actual function passing the instance of the
            # class as the first argument.
            return await func(self._class_mapping[class_name], msg, user,
                              channel, *args, **kwargs)

    def user_has_permission(self, user, command):
        '''
        Performs various checks on the user and the
        command to determine if they're allowed to use it.
        '''
        discord_regex = r'<@([0-9]+)>'
        # Determine if the requst is done by discord or irc bot        
        regex_match = re.match(discord_regex, user)
        if regex_match:
            uid = regex_match.group(1)
        else:
            # If its irc the user is in the format
            # username@ip. We use the ip to uniquely identify them.
            uid = user.split('@')[1]

        # Check if the user has been blacklisted.
        if uid in self.blacklisted_users:
            return False
        # Check if the user is an admin and if the command is
        # an admin command.
        if command in self.admin_actions and uid not in self.admins:
            return False
        # User passed all the tests so they're allowed to
        # call the function.
        return True

    async def send_metrics(self, command, channel):
        '''
        Sends metrics for each command thats invoked.
        '''
        if not self.metrics:
            return None
        else:
            try:
                channel = channel.server
            except AttributeError:
                pass
            channel = re.sub(self.invalid_metric_chars, '_', str(channel))
            command = re.sub(self.invalid_metric_chars, '_', command)
            metric_name = '%s.%s' % (channel, command)
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(None, self.metrics.send,
                                          metric_name, 1)
            await future

    def get_blacklisted_users(self):
        '''
        Updates the in-memory list of blacklisted users when
        the bot starts up.
        '''
        try:
            with open(self.config['blacklist_file'], 'r') as f:
                users = f.readlines()
        except IOError:
            return []

        # Return the list of users after stripping the new line char.
        return [user[:-2] for user in users]
