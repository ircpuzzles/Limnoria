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

class IrcPuzzles(callbacks.Plugin):
    """A plugin to facilitate IRC Puzzles channel management and stats tracking"""
    threaded = True
    def __init__(self, irc):
        super(IrcPuzzles, self).__init__(irc)
        self._requests = {}
        self._cache = {}
        logger.info('plugin initialized!')
        # NOTE: the bot is not connected to IRC yet.

    def getRunningGame(self):
        """Return the Game instance of the running GameInfo record."""
        res = session.query(GameInfo).filter(GameInfo.running == True)
        if res.count() == 1:
            try:
                return Game(res.one().path)
            except Exception, e:
                logger.error('unable to intialize game, path='+res.one().path)

    def joinGameChannels(self, irc):
        logger.info('join game channels')
        # TODO: ...

    def do001(self, irc, msg):
        """Welcome to IRC, just after connecting to the irc server."""
        # requests the capabilities we use to track nickserv usernames
        self.sendCapRequest(irc)
        # init running game object, will let the bot join in 
        # the channel of the currently running game (TODO).
        self._game = self.getRunningGame()

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
                self.joinGameChannel(irc)
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

    def gameStop(self, irc, msg, args, path):
        """Stopps the currently running game."""
        if self._game:
            pass # TODO: -apoc
        else:
            irc.reply('No game currently running.')

    gameStop = wrap(gameStop, [('admin'), optional('filename')], 'game stop')

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
            self.joinGameChannels(irc)
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
        channel, account, realname = msg.args

        if msg.nick == irc.nick:
            logger.debug('bot joined channel=%s, send WHO request for account names' % (channel,))
            irc.queueMsg(ircmsgs.IrcMsg(command='WHO', args=(channel, '%na')))
            return

        if account == '*' and msg.nick in self._cache:
            logger.debug('account cache: remove nick=%s (extended-join)' % (msg.nick,))
            del self._cache[msg.nick]
        else:
            logger.debug('account cache: set nick=%s with account=%s (extended-join)' % (msg.nick, account))
            self._cache[msg.nick] = account

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
        else:
            logger.debug('account cache: set nick=%s with account=%s (account-notify)' % (msg.nick, account))
            self._cache[msg.nick] = account

Class = IrcPuzzles


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
