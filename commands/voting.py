#!/usr/bin/python


class Voting():

    def __init__(self):
        # regex to match a number at the start of the message.
        # Being a float is optional.
        self.length_re = r'--((\d*)?(\.\d*)?)'
        # regex to atch and capture vote options in square bracket.
        self.options_re = r'\[(.+)\]'
        self.vote_length = 0.5
        self.default_options = ['yes', 'no']
        self.active_votes = {}

    def apply_regex(self, msg, regex):
        '''
        Applies the regex and removes the matched
        elements from the message.
        Returns the matched group.
        '''
        result = re.search(regex, msg)
        if result:
            msg = re.sub(regex, '', msg).strip()
            return msg, result.group(0)
        else:
            return False

    def handle_input(self, msg):
        '''
        Parses the supplied message to determine the vote
        length and supplied parameteres(if any).

        Expected vote format:
            !vote[--time] String of the vote [[parameter1, parm2]]
        '''
        # Check if the user supplied a length
        regex_result = self.apply_regex(msg, self.length_re)
        if regex_result:
            msg, matched_length = regex_result
            # start at the second index to avoid the -- at the start
            # of the time parameter.
            vote_length = float(matched_length[2:])
        else:
            vote_length = self.vote_length

        # Check if the user supplied extra parameters
        regex_result = self.apply_regex(msg, self.options_re)
        if regex_result:
            msg, extra_options = regex_result

            # remove square brackets, split on comma and strip whitespace
            extra_options = extra_options.replace('[', '').replace(']', '')
            options = extra_options.lower().split(',')
            options = [word.strip() for word in options]

            # Storing length in a variable here to later compare
            # after forming a dictionary to ensure there were no
            # duplicates.
            option_len = len(options)
            if len(options) < 2:
                return False

            # Create a dictionary with the voter counts set to 0
            values = [0 for option in options]
            vote_options = dict(zip(options, values))

            # Make sure the options aren't repeated by comparing length
            # before the dictionary was created.
            if option_len != len(vote_options):
                return False
        else:
            values = [0 for index in self.default_options]
            vote_options = dict(zip(self.default_options, values))

        # What remains of the msg should be the vote question.
        if len(msg.strip()) < 1:
            return False

        return msg, vote_length, vote_options

    async def send_start_message(self, client, channel, vote_length, msg):
        '''
        Simple function that sends a message that a
        vote has started asyncronously.
        '''
        vote_parms = self.active_votes[channel][1]
        start_string = 'Starting vote ```%s``` with options ' % msg
        param_string = ' '.join(['%s' for index in range(len(vote_parms))])
        start_string += '[ ' + param_string % tuple(vote_parms.keys()) + ' ]'
        start_string += ' For %s minutes.' % vote_length

        await client.send_message(channel, start_string)

    async def end_vote(self, client, channel, msg):
        '''
        Counts the votes to determine the winner and sends
        the finish message. Cant simply check the max value
        because there might be a draw. Should probably break
        it up.
        '''
        vote_parms = self.active_votes[channel][1]
        end_string = 'Voting for ```%s``` completed.' % msg

        max_value = max(vote_parms.values())
        winners = [key for key, value in vote_parms.items()
                   if value == max_value]

        if len(winners) == 1:
            end_string += ' The winner is **%s**' % tuple(winners)
        else:
            winner_string = ' '.join(['%s' for index in range(len(winners))])
            end_string += ' The winners are [ **' + winner_string % tuple(winners) + '** ]'

        await client.send_message(channel, end_string)

    async def run_vote(self, client, channel, vote_length, msg):
        '''
        Simple async function that sleeps for the vote length
        and calls the start and end voting functions.
        '''
        await self.send_start_message(client, channel, vote_length, msg)        
        # sleep for the vote length.
        await asyncio.sleep(vote_length * 60)
        # Count the votes and send the ending message
        await self.end_vote(client, channel, msg)
        # Delete the dictionary entry now that the vote is finished.
        del self.active_votes[channel]

    async def start_vote(self, msg, user, channel, client):
        '''
        Main function that handles the vote function. Makes sure
        that only vote is going at a time in a channel.

        Calls from a channel that has a vote going on are
        considered to be a vote for the ongoing vote.

        dict entry: active_votes(client, {option: count}, [voters])
        '''
        if channel not in self.active_votes:
            processed_input = self.handle_input(msg)
            if processed_input:
                msg, vote_len, params = processed_input
                # Save a reference to the sleep function, the valid params
                # for the specific vote and an empty list which will contain
                # the name of users who have already voted.
                self.active_votes[channel] = (self.run_vote, params, [])
                # print('starting vote with ', params)
                # Start the actual vote.
                await self.active_votes[channel][0](client, channel, vote_len, msg)
            else:
                return ('Invalid format for starting a vote. The correct format is '
                        '```!vote[--time] Vote question [vote options]``` '
                        '**eg:** !vote start a vote on some topic? [yes, no, maybe]')
        else:
            # An active vote already exists for this channel.
            # First check if the user has already voted in it.
            if user in self.active_votes[channel][2]:
                return ("Stop attempting electoral fraud %s, "
                        "you've already voted") % user
            else:
                # Check if the supplied argument is a valid vote option.
                vote_option = msg.lower().strip()
                valid_options = self.active_votes[channel][1]
     
                if vote_option in valid_options:
                    self.active_votes[channel][1][vote_option] += 1
                    # Add the user to the list of users.
                    self.active_votes[channel][2].append(user)
                    # return 'Increasing %s vote :)' % vote_option
                else:
                    error_str = 'Invalid vote option %s. ' % user
                    error_str += 'The options are ' + str(tuple(valid_options.keys()))
                    return error_str
