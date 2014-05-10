###
# Copyright (c) 2014, Irc Puzzles Team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import time
import sqlalchemy
import re

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs

from .database import *
from .local.challenge import Game
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('IrcPuzzles')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x:x

import logging
logger = logging.getLogger('ircpuzzles')
owners = ['affiliated', 'yano', 'sdamashek', 'apoc', 'furry', 'JoseeAntonioR']
ownerflags = '+AOiortv'
channelmlock = '+Ccntrsmz'

def remove(channel, nick, s=''):
    return ircmsgs.IrcMsg(prefix='', command='REMOVE', args=(channel, nick, s), msg=None)

class IrcPuzzles(callbacks.Plugin):
    """A plugin to facilitate IRC Puzzles channel management and stats tracking"""
    threaded = True
    def __init__(self, irc):
        super(IrcPuzzles, self).__init__(irc)
        self._requests = {}
        self._cache = {}
        self._game = self.getRunningGame()
        logger.info('plugin initialized!')
        self.updatecache(irc, [], []) # If the bot is already connected, update the cache from joined channels.
        # NOTE: the bot is not connected to IRC yet.

    def updatecache(self, irc, msg, args):
        for (channel, c) in irc.state.channels.iteritems():
            irc.queueMsg(ircmsgs.IrcMsg(command='WHO', args=(channel, '%na')))
            if self._game:
                channel_obj = self._game.get_channel(channel)
                if channel_obj:
                    self.joinedGameChannel(irc, channel_obj)
    updatecache = wrap(updatecache, ['admin'])

    def getRunningGame(self):
        """Return the Game instance of the running GameInfo record."""
        res = session.query(GameInfo).filter(GameInfo.running == True)
        if res.count() == 1:
            try:
                return Game(res.one().path)
            except Exception, e:
                logger.error('unable to intialize game, path='+res.one().path)

    def joinGameChannels(self, irc):
        if not self._game:
            logger.info('no game currently running')
            return
        logger.info('join running game channels...')
        channels = [self._game.lobby.name]
        self.joinChannel(irc, self._game.lobby.name)
        for track in self._game.tracks:
            for channel in track.channels:
                self.joinChannel(irc, channel.name)
                channels.append(channel.name)
        logger.info('joined ' + ', '.join(channels))
        return channels

    def partGameChannels(self, irc):
        if not self._game:
            logger.info('no game currently running')
            return
        logger.info('part running game channels...')
        channels = [self._game.lobby.name]
        self.partChannel(irc, self._game.lobby.name)
        #irc.queueMsg(ircmsgs.privmsg("ChanServ","DROP %s" %
        #    self._game.lobby.name))
        # Do not drop lobby
        for track in self._game.tracks:
            for channel in track.channels:
                self.partChannel(irc, channel.name)
                irc.queueMsg(ircmsgs.privmsg("ChanServ","DROP %s" % channel.name))
                channels.append(channel.name)
        logger.info('parted ' + ', '.join(channels))
        return channels

    def getChannels(self):
        if not self._game:
            return []
        channels = []
        for track in self._game.tracks:
            for channel in track.channels:
                channels.append(channel.name)
        return channels

    def partChannel(self, irc, channel):
        if not self.botInChannel(irc, channel):
            logger.info('already parted '+channel)
        else:
            logger.info('part channel '+channel)
            irc.queueMsg(ircmsgs.part(channel,'Game stopped'))

    def joinChannel(self, irc, channel):
        if not self.botInChannel(irc, channel):
            logger.info('join channel '+channel)
            irc.queueMsg(ircmsgs.join(channel))
        else:
            logger.info('bot already joined in '+channel)

    def joinedGameChannel(self, irc, channel_obj):
        """Called after a game-associated channel has been joined by the bot.

        The bot should setup the channel with ChanServ,
        set the topic, op bot admins and (TODO) log users
        in the channel."""

        if not self._game:
            return
        irc.queueMsg(ircmsgs.topic(channel_obj.name, channel_obj.topic))
        if channel_obj.name != self._game.lobby.name:
            self.register(irc,channel_obj.name)

    def handleUserJoin(self, irc, msg):
        if len(msg.args) > 1:
            channel, account, realname = msg.args
        else:
            channel, account, realname = (msg.args[0],'*','*')
        gameChannels = self.getChannels()    
        if msg.nick == irc.nick:
            return
        if account in owners:
            logger.debug('user %s is owner, not handling join' % msg.nick)
            return
        if not self._game:
            return
        game = self._game
        if channel == game.lobby.name:
            logger.debug('nick %s (account %s) joined lobby %s' % (msg.nick,account,channel))
            if account == '*':
                irc.reply('Welcome %s! You must be identified to compete. All game channels are set +r.' % msg.nick) # Notify user as a friendly warning
        elif channel in gameChannels:
            if account == '*':
                irc.queueMsg(remove(channel,msg.nick,'You must be identified with NickServ to play ircpuzzles.')) # Should never be reached as channels are +r
                return
            user = list(session.query(User).filter(User.account == account).filter(User.confirmed == True))
            if len(user) < 1:
                irc.queueMsg(remove(channel,msg.nick,'You must be registered with the bot to compete. Please register at http://ircpuzzles.org.'))
                return
            u = user[0]
            joins_cur = list(session.query(Join).filter(Join.channel == channel).filter(Join.user == u))
            if len(joins_cur) > 0:
                return # User has already joined this channel
            channel_obj = game.get_channel(channel)
            prev = channel_obj.prev

            the_track = None
            the_number = 0
            for track in self._game.tracks:
                for idx, chan in enumerate(track.channels):
                    if channel == chan:
                        the_track = track.name
                        the_number = idx
            joinmsg = ircmsgs.privmsg(self._game.lobby.name, "%s joins channel %d in track %s" % (u,the_number,the_track))
            irc.queueMsg(joinmsg)

            if not prev:
                logger.debug('user %s joined channel %s (first in track)' % (u,channel))
                join = Join(user=u,channel=channel)
                logger.debug('adding join obj for %s to %s' % (u,channel))
                session.add(join)
                session.commit()
                return # Channel is first in track, user is good
            joins = list(session.query(Join).filter(Join.channel == prev.name).filter(Join.user == u))
            if len(joins) < 1:
                irc.queueMsg(remove(channel,msg.nick,'You must complete tracks in order.'))
                return
            join = Join(user=u,channel=channel)
            logger.debug('adding join obj for %s to %s' % (u,channel))
            session.add(join)
            session.commit()
        
    def register(self, irc, channel):
        irc.queueMsg(ircmsgs.privmsg("ChanServ","REGISTER %s" % channel))

    def do001(self, irc, msg):
        """Welcome to IRC, just after connecting to the irc server."""
        # init running game object, will let the bot join in 
        # the channel of the currently running game
        self._game = self.getRunningGame()
        # requests the capabilities we use to track nickserv usernames
        self.sendCapRequest(irc)
        # we join the game channels after the caps are confirmed by the server

    def sendCapRequest(self, irc):
        """Issue a CAP REQ command to request account-notify and extended-join."""
        logger.info('send cap req for account-notify and extended-join')
        irc.queueMsg(ircmsgs.IrcMsg(command="CAP", args=('REQ', 'account-notify extended-join')))

    def doCap(self, irc, msg):
        """CAP ACK is received in response to our cap request:

        account-notify -- notifies us if a user in a channel the bot is in,
        identifies with nickserv, it tells us its username.

        extended-join -- tells us the users nickserv username when he joins
        a channel the bot is in.
        """
        nick, command, caps = msg.args
        if nick == irc.nick and command == 'ACK':
            caps = caps.split(' ')
            if 'account-notify' in caps and 'extended-join' in caps:
                logger.info('success! aquired caps: '+','.join(caps))
                self.joinGameChannels(irc)
            else:
                logger.error('fatal! unable to aquire caps! (network unsupported)')

    def whataccount(self, irc, msg, args, nick):
        """<nick>

        Get the account name for a nick."""
        if not self.nickInAnyChannel(irc, nick):
            irc.reply("\"%s\" is not in any of my channels." % nick)
            return
        if nick in self._cache:
            irc.reply("\"%s\" is identified as \"%s\"." % (nick, self._cache[nick]))
        else:
            irc.reply("\"%s\" is not identified." % nick)

    whataccount = wrap(whataccount, ['admin', 'text'])

    def getcache(self, irc, msg, args):
        """Return the raw cache for debugging"""
        irc.reply(str(self._cache))

    getcache = wrap(getcache, ['admin'])

    def confirm(self, irc, msg, args, code):
        """<code>

        Confirm a user registration, you must be in a channel the bot is in."""
        if msg.nick not in self._cache:
            irc.reply("You are not identified to NickServ. Please identify and try again.")
            return
        account = self._cache[msg.nick]
        logger.info("Nick %s (account %s) requesting confirmation" % (msg.nick,account))
        code_found = False
        users = list(session.query(User).filter(User.account == account))
        if len(users) < 1:
            irc.reply("No user was found with your NickServ account. Please try registering again.")
            return

        for user in users:
            if user.confirmed == True:
                irc.reply("You are already confirmed!")
                return
            if user.confirmation_code == code:
                user.confirmed = True
                session.query(User).filter(User.account == account).filter(User.id != user.id).delete()
                session.commit()
                irc.reply("Thank you, your account is now confirmed!")
                return

        irc.reply("Incorrect confirmation code.")

    confirm = wrap(confirm, ['text'])

    def gamestop(self, irc, msg, args):
        """Stops the currently running game."""
        if self._game:
            game = self._game
            irc.reply('Stopping game: '+game.name)
            channels = self.partGameChannels(irc)
            irc.reply('Parted game channels: ' + ', '.join(channels))
            res = session.query(GameInfo).filter(GameInfo.running == True)
            if res.count() > 0:
                res.one().running = False
                session.commit()
            else:
                irc.reply('Could not find game db object to stop.')
            self._game = None
            irc.reply('Game stopped.')

        else:
            irc.reply('No game currently running.')

    gamestop = wrap(gamestop, [('admin')], 'game stop')

    def game(self, irc, msg, args, path):
        """[<path>]

        Returns currently running game, or initialize a new one,
        <path> should be a path to a game.json file."""
        if self._game:
            irc.reply('Currently running game: '+self._game.name)
        else:
            if not path:
                irc.reply('No game is running, specify <path> to initialize')
                return
            irc.reply('Initalize game path: '+path)

            self._game = game = Game(path)
            irc.reply('Starting game: '+game.name)
            channels = self.joinGameChannels(irc)
            irc.reply('Joined game channels: ' + ', '.join(channels))
            res = session.query(GameInfo).filter(GameInfo.path == path)
            if res.count() > 0:
                res.one().running = True
            else:
                game_info = GameInfo()
                game_info.path = path
                game_info.running = True
                session.add(game_info)
            session.commit()

    game = wrap(game, [('admin'), optional('filename')])

    def nickInAnyChannel(self, irc, nick, excludeChannel=None):
        """Return True if the nick is seen in any channel.

        You may specify a channel that is excluded."""
        for (channel, c) in irc.state.channels.iteritems():
            if nick in c.users and channel != excludeChannel:
                return True
        return False

    def botInChannel(self, irc, channel):
        for (_channel, c) in irc.state.channels.iteritems():
            if channel == _channel:
                return True
        return False

    def doJoin(self, irc, msg):
        """Handle channel join, send WHO query and cache extended-join account data.

        When the bot itself joins a channel, a WHO is sent for
        nick and account name. (e.g. /who #example %na)
        This is an extension: http://hg.quakenet.org/snircd/file/tip/doc/readme.who

        After connecting we've enabled the extended-join capability
        this IRCv3 extension enables us to see the account name of anyone
        joining a channel. We store the account name in _cache.
        Docs: http://ircv3.org/extensions/extended-join-3.1
        """
        logger.debug('join: '+str(msg.args))
        if len(msg.args)>1:
            channel, account, realname = msg.args
        else:
            channel, account, realname = (msg.args[0],'*','*')

        if msg.nick == irc.nick:
            logger.debug('bot joined channel=%s, send WHO request for account names' % (channel,))
            irc.queueMsg(ircmsgs.IrcMsg(command='WHO', args=(channel, '%na')))
            if self._game:
                channel_obj = self._game.get_channel(channel)
                if channel_obj:
                    self.joinedGameChannel(irc, channel_obj)
            return

        if account == '*' and msg.nick in self._cache:
            logger.debug('account cache: remove nick=%s (extended-join)' % (msg.nick,))
            del self._cache[msg.nick]
        elif account == '*':
            logger.debug('account cache: user %s joined unidentified, not in cache (extended-join)' % msg.nick)
        else:
            logger.debug('account cache: set nick=%s with account=%s (extended-join)' % (msg.nick, account))
            self._cache[msg.nick] = account
        self.handleUserJoin(irc, msg)


    def doNick(self, irc, msg):
        newnick = msg.args[0]
        if msg.nick in self._cache:
            logger.debug('account cache: rename cached nick=%s to new nick=%s (NICK)' % (msg.nick, newnick))
            account = self._cache[msg.nick]
            del self._cache[msg.nick]
            self._cache[newnick] = account

    def doPart(self, irc, msg):
        channel = msg.args[0]
        if not self.nickInAnyChannel(irc, msg.nick, channel) and msg.nick in self._cache:
            logger.debug('account cache: remove nick=%s (PART from all channel)' % (msg.nick,))
            del self._cache[msg.nick]

    def doQuit(self, irc, msg):
        if msg.nick in self._cache:
            logger.debug('account cache: remove nick=%s (QUIT)' % (msg.nick,))
            del self._cache[msg.nick]

    def do354(self, irc, msg):
        """Process WHO response messages, that include account name.

        Adds account names to the cache, we use WHO to request nick and account (see onJoin)
        """
        if len(msg.args) == 3:
            (channel, nick, account) = msg.args
            if account != '0':
                logger.debug('account cache: set nick=%s with account=%s (WHO response)' % (nick, account))
                self._cache[nick] = account

    def doAccount(self, irc, msg):
        """Notifications of user login/logout in NickServ.

        The account-notify cap allows us to see when a user of a channel we are
        in is logging into or logging off of NickServ.
        Docs: http://ircv3.org/extensions/account-notify-3.1
        """
        account = msg.args[0]
        logger.debug('account-notify received: nick=%s account=%s ' % (msg.nick, account))
        if account == '*' and msg.nick in self._cache:
            logger.debug('account cache: remove nick=%s (account-notify)' % (msg.nick,))
            del self._cache[msg.nick]
            if self._game:
                channels = self.getChannels()
                for channel in channels:
                    if msg.nick in irc.state.channels[channel].users:
                        irc.queueMsg(remove(channel,msg.nick,'You unidentified. Please rejoin once you have identified.'))

        else:
            logger.debug('account cache: set nick=%s with account=%s (account-notify)' % (msg.nick, account))
            self._cache[msg.nick] = account

    def doNotice(self, irc, msg):
        logger.debug('notice from ' + msg.nick + ': ' + msg.args[1])
        if msg.nick.lower() == 'chanserv':
            registeredregex = re.compile(ur'(#[^ ]+)\x02 is now registered to',re.UNICODE)
            registered = registeredregex.findall(msg.args[1])
            drop = re.findall('/msg ChanServ DROP ([^ ]+) ([A-Za-z0-9:]+)', msg.args[1])
            if registered:
                channel = registered[0]
                irc.queueMsg(ircmsgs.privmsg("ChanServ","FLAGS %s %s +O" % (channel, irc.nick)))
                for owner in owners:
                    irc.queueMsg(ircmsgs.privmsg("ChanServ","FLAGS %s %s %s" % (channel, owner, ownerflags)))
                irc.queueMsg(ircmsgs.privmsg("ChanServ","SET %s MLOCK %s" % (channel, channelmlock)))
            if drop:
                irc.queueMsg(ircmsgs.privmsg("ChanServ","DROP %s %s" % (drop[0][0],drop[0][1])))




Class = IrcPuzzles


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
