"""Tests for commandblock feature profile.

Original: Commandblock-Handler (42 lines, dynamic parent, 2 overrides).
"""
import unittest

from mcdreforged.handler.impl.bukkit_handler import BukkitHandler
from mcdreforged.handler.impl.forge_handler import ForgeHandler
from mcdreforged.handler.impl.vanilla_handler import VanillaHandler

from .common import load_profile, make_handler, parse_line


class TestCommandblockProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('commandblock')
        self.base = VanillaHandler()
        self.handler = make_handler(profile, self.base)

    # ── pseudo player detection ──

    def test_function_pseudo_player(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: [Server] say hello'
        )
        self.assertEqual('"!function"', info.player)
        self.assertEqual('say hello', info.content)

    def test_commandblock_pseudo_player(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: [@] time set day'
        )
        self.assertEqual('"!commandblock"', info.player)
        self.assertEqual('time set day', info.content)

    # ── normal player ──

    def test_normal_player_unaffected(self):
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: <Steve> hello'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('hello', info.content)

    def test_player_detection_intercepts_before_pseudo(self):
        """VanillaHandler detects <Server> as real player before pseudo player runs."""
        info = parse_line(
            self.handler,
            '[09:00:00] [Server thread/INFO]: <Server> hello'
        )
        self.assertEqual('Server', info.player)

    # ── with other base handlers ──

    def test_works_with_forge(self):
        profile = load_profile('commandblock')
        handler = make_handler(profile, ForgeHandler())
        info = parse_line(
            handler,
            '[00:53:00] [Server thread/INFO] [minecraft/DedicatedServer]: [@] help'
        )
        self.assertEqual('"!commandblock"', info.player)
        self.assertEqual('help', info.content)

    def test_works_with_bukkit(self):
        profile = load_profile('commandblock')
        handler = make_handler(profile, BukkitHandler())
        info = parse_line(
            handler,
            '[00:12:10 INFO]: [Server] list'
        )
        self.assertEqual('"!function"', info.player)
        self.assertEqual('list', info.content)
