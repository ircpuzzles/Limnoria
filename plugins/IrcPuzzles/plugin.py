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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.ircmsgs as ircmsgs
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

    def processAccount(self, irc, msg, nick, callback):
        if nick in self._cache:
            self._whatAccount(irc, msg)
        else:
            self._requests[(irc.network, nick)] = (callback, irc, msg, args, nick)
            irc.queueMsg(ircmsgs.whois(nick, nick))

    def whatAccount(self, irc, msg, args, nick):
        """Get the account name for a nick."""
        self.processAccount(nick, (self._whatAccount, irc, msg, args, nick))

    def _whatAccount(self, irc, msg, args, nick):
        if nick not in self._cache:
            irc.reply("\"%s\" is not identified with NickServ." % nick)
        else:
            irc.reply("\"%s\" is identified as \"%s\"." % (nick, self._cache[nick]))

    whatAccount = wrap(whatAccount, ['text'])

    def doJoin(self, irc, msg):
        nick = msg.nick
        self.processAccount(nick,(self._doJoin, irc, msg))

    def _doJoin(self, irc, msg):
        nick = msg.nick
        prefix = msg.prefix
        account = self._cache.get(nick,'<None>')
        for channel in msg.args[0].split(','):
            irc.queueMsg(ircmsgs.privmsg(channel,"I saw %s join with nickserv account %s" % (prefix, account)))

    def do330(self, irc, msg):
        mynick, theirnick, theiraccount, garbage = msg.args
        # I would like to use a dict comprehension, but we have to support
        # Python 2.6 :(
        try:
            callback = self._requests.pop((irc.network, theirnick))
        except KeyError:
            return
        self._cache[theirnick] = theiraccount
        callback[0](*callback[1:])


Class = IrcPuzzles


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
