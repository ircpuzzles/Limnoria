
from game import Game

import unittest

class TestGame(unittest.TestCase):
    def setUp(self):
        # load game.json file (example/puzzle/*.json must exist!)
        self.game = Game('example/game.json')

    def test_track_access(self):
        self.assertEqual(self.game.tracks[0].get_start().name, '####_TEST_first_path')
        # ...

if __name__ == '__main__':
    unittest.main()

