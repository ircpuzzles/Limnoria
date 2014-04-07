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
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('IrcPuzzles')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x:x

class IrcPuzzles(callbacks.Plugin):
    """A plugin to facilitate IRC Puzzles channel management and stats tracking"""
    threaded = True
    def __init__(self, irc):
        super(IrcPuzzles, self).__init__(irc)
        self._requests = {}
        self._cache = {}
        self.processChannels(irc)

    def processChannels(self, irc):
        for (channel, c) in irc.state.channels.iteritems():
            for u in c.users:
                if u not in self._cache and u != 'ircpuzzlesbot':
                    self.processAccount(irc, u)


    def processAccount(self, irc, nick, callback=(lambda x:None, None)):
        if nick in self._cache:
            callback[0](*callback[1:])
        else:
            self._requests[(irc.network, nick)] = callback
            irc.queueMsg(ircmsgs.whois(nick, nick))

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

    getcache = wrap(getcache, [])

    def confirm(self, irc, msg, args, code):
        self.processAccount(irc, msg.nick, (self._confirm, irc, msg, args, code))

    def _confirm(self, irc, msg, args, code):
        """<code>

        Confirm a user registration"""
        if msg.nick not in self._cache:
            irc.reply("You are not identified to NickServ. Please identify and try again.")
            return
        account = self._cache[msg.nick]
        code_found = False
        users = session.query(User).filter(User.account == account)
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

    def doJoin(self, irc, msg):
        nick = msg.nick
        if nick == 'ircpuzzlesbot':
            return
        self.processAccount(irc, nick,(self._doJoin, irc, nick))

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
