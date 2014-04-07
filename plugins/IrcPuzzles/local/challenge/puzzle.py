
import os
from os.path import join, isfile
import json
import logging
logger = logging.getLogger('ircpuzzles')

import dateutil.parser # pip install dateutil

from channel import Channel

class Puzzle(object):
    def __init__(self, game, filename):
        """Load puzzle data.

        Args:
           filename (str): Path to puzzle json file.
        """
        self.game = game
        self.id = os.path.basename(filename)[0:-5]

        logger.info('load puzzle definition file: %s', filename)
        with open(filename) as f:
            parsed = json.load(f)
        self.name = parsed['name']
        self.creator = parsed['creator']
        self.clue = parsed['clue']
        self.incorrect_topic = parsed['incorrect_topic'] if 'incorrect_topic' in parsed else ''
        self.hints = parsed['hints'] if 'hints' in parsed else []
        solution = parsed['solution']
        self.correct_solution = solution['correct']
        self.incorrect_solutions = solution['incorrect'] if 'incorrect' in solution else []

    def get_topic(self):
        return self.clue

    def get_correct_channel_name(self):
        return self.game.prefix_channel(self.correct_solution)

    def get_incorrect_channel(self):
        return [
            Channel(self.game.prefix_channel(name), self.incorrect_topic)\
                    for name in self.incorrect_solutions ]

