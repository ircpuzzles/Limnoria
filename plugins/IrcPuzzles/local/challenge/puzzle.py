import os
from os.path import basename, splitext
import json
import logging
logger = logging.getLogger('ircpuzzles')

from channel import Channel

class Puzzle(object):
    def __init__(self, id):
        """Initialize puzzle definition."""
        self.id = id
        self.name = None
        self.creator = None
        self.clue = None
        self.hints = None
        self.incorrect_topic = None
        self.solution = None

        self.prev = None
        self.next = None
        self.next_incorrect = []
        self.puzzle = None

    def get_correct(self):
        return self.solution.get('correct')

    def get_incorrect(self):
        return self.solution.get('incorrect', [])

    @staticmethod
    def parse(path):
        """Load specified puzzle json definition.

        Args:
            filename (str): path to puzzle json file.
        """
        id, ext = splitext(basename(path))

        logger.info('reading puzzle definition file: %s', path)
        with open(path) as f:
            content = json.load(f)
            puzzle = Puzzle(id)
            puzzle.name = content.get('name')
            puzzle.creator = content.get('creator')
            puzzle.clue = content.get('clue')
            puzzle.hints = content.get('hints', [])
            puzzle.incorrect_topic = content.get('incorrect_topic', '')
            puzzle.solution = content.get('solution')
            return puzzle

    #def get_topic(self):
    #    return self.clue

    #def get_correct_channel_name(self):
    #    return self.game.format_channel(self.correct_solution)

    #def get_incorrect_channel(self):
    #    incorrect_channel = []
    #    for name in self.incorrect_solutions:
    #        channel = Channel(self.game.format_channel(name), self.incorrect_topic)
    #        channel.name_puzzle = self
    #        incorrect_channel.append(channel)
    #    return incorrect_channel

