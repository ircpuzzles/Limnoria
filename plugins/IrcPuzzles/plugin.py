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

    def do001(self, irc, msg):
        """Welcome to IRC, just after connecting to the irc server."""
        # requests the capabilities we use to track nickserv usernames
        self.sendCapReq(irc)
        # init running game object, will let the bot join in 
        # the channel of the currently running game (TODO).
        self._game = self.getRunningGame()

        # this should be called _after_ the bot has joined in all 
        # puzzle channel: (TODO: move after join is implemented)
        self.processChannels(irc)

    def sendCapReq(self, irc):
        """Issue a CAP REQ command to request account-notify and extended-join."""
        logger.info('queue cap req for account-notify and extended-join')
        irc.queueMsg(ircmsgs.IrcMsg(command="CAP", args=('REQ', 'account-notify extended-join')))

    def inFilter(self, irc, msg):
        if msg.command == 'CAP':
            self.doCAP(irc, msg)
        elif msg.command == 'ACCOUNT':
            self.doACCOUNT(irc, msg)
        return msg

    def doCAP(self, irc, msg):
        """CAP is received in response to our cap request:

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
            else:
                logger.error('unable to aquire caps!')

    def doACCOUNT(self, irc, msg):
        """Notifications of user login/logout in NickServ.

        The account-notify cap allows us to see when a user of a channel we are
        in is logging into or logging off of NickServ.
        """
        logger.info('account-notify received: ' + str(msg.args))
        account = msg.args[0]
        if account != '*':
            logger.info('account-notify: add account cache for %s: %s' % (msg.nick, account))
            self._cache[msg.nick] = account
        elif msg.nick in self._cache:
            logger.debug('account-notify: remove existing account cache: '+msg.nick)
            del self._cache[msg.nick]

    def processChannels(self, irc):
        """Receive NickServ username for every user whos in a channel the bot is in."""
        logger.info('process %d channels, whois users for nickserv username' %
                len(irc.state.channels))
        for (channel, c) in irc.state.channels.iteritems():
            for u in c.users:
                if u not in self._cache and u != irc.nick:
                    self.processAccount(irc, u)

    def processAccount(self, irc, nick, callback=(lambda x:None, None)):
        """Queue a /whois for the specified user (nick).

        No whois is performed if nick is present in _cache.
        Callback is called after the username was acquired."""
        if nick in self._cache:
            callback[0](*callback[1:])
        else:
            self._requests[(irc.network, nick)] = callback
            irc.queueMsg(ircmsgs.whois(nick, nick))

    def debugProcessChannels(self, irc, msg, args):
        """Does a manual process channels."""
        self.processChannels(irc)
    debugProcessChannels = wrap(debugProcessChannels, [])

    def whataccount(self, irc, msg, args, nick):
        """<nick>

        Get the account name for a nick."""
        inchan = False
        for (channel, c) in irc.state.channels.iteritems():
                if nick in c.users:
                    inchan = True

        if not inchan:
            irc.reply("\"%s\" is not in any of my channels." % nick)
            return
        self.processAccount(irc, nick, (self._whataccount, irc, msg, args, nick))

    def _whataccount(self, irc, msg, args, nick):
        if nick in self._cache:
            irc.reply("\"%s\" is identified as \"%s\"." % (nick, self._cache[nick]))
        else:
            irc.reply("\"%s\" is not identified." % nick)

    whataccount = wrap(whataccount, ['text'])

    def getcache(self, irc, msg, args):
        """Return the raw cache for debugging"""
        irc.reply(str(self._cache))

    getcache = wrap(getcache, ['admin'])

    def confirm(self, irc, msg, args, code):
        """<code>

        Confirm a user registration"""
        self.processAccount(irc, msg.nick, (self._confirm, irc, msg, args, code))

    def _confirm(self, irc, msg, args, code):
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
            #self.joinGameChannels()
            pass # TODO:join channel -apoc
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

    def doJoin(self, irc, msg):
        channel, account, realname = msg.args
        if account != '*':
            logger.debug('extended-join: add account cache for %s: %s' % (msg.nick, account))
            self._cache[msg.nick] = account
        elif msg.nick in self._cache:
            logger.debug('extended-join: remove existing account cache: '+msg.nick)
            del self._cache[msg.nick]

    def _doJoin(self, irc, nick):
        account = self._cache.get(nick,'<None>')

    def doNick(self, irc, msg):
        self.processAccount(irc, msg.args[0], (self._doNick, irc, msg))

    def _doNick(self, irc, msg):
        oldnick = msg.nick
        newnick = msg.args[0]
        if oldnick in self._cache:
            del self._cache[oldnick]

    def doPart(self, irc, msg):
        for (channel, c) in irc.state.channels.iteritems():
                if msg.nick in c.users:
                    return
        if msg.nick in self._cache:
            del self._cache[msg.nick]

    def doQuit(self, irc, msg):
        if msg.nick in self._cache:
            del self._cache[msg.nick]

    def do330(self, irc, msg):
        mynick, theirnick, theiraccount, garbage = msg.args
        try:
            callback = self._requests.pop((irc.network, theirnick))
        except KeyError:
            return
        self._cache[theirnick] = theiraccount
        callback[0](*callback[1:])

    def do318(self, irc, msg):
        mynick, theirnick, garbage = msg.args
        try:
            callback = self._requests.pop((irc.network, theirnick))
        except KeyError:
            return
        callback[0](*callback[1:])

    def do352(self, irc, msg):
        (mynick, channel, username, hostname, server, nick, perms, realname) = msg.args
        if nick not in self._cache:
            self.processAccount(irc, nick)


Class = IrcPuzzles


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
