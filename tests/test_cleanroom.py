"""Tests for cleanroom base profile.

Original: CleanRoomServerHandler (26 lines, extends ForgeHandler, 1 override).
ForgeHandler fails to parse empty [] lines; cleanroom handles them.
"""
import unittest

from mcdreforged.handler.impl.forge_handler import ForgeHandler

from .common import load_profile, parse_line
from unified_handler.profile_loader import compile_full_profile
from unified_handler.handler import UnifiedHandler


class TestCleanroomProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('cleanroom', 'base')
        compiled = compile_full_profile(profile)
        self.handler = UnifiedHandler(ForgeHandler(), compiled, mode='wrapper')

    # ── empty brackets (the core fix) ──

    def test_empty_brackets_line(self):
        """Cleanroom outputs [] when logger name is empty."""
        info = parse_line(
            self.handler,
            '[12:34:56] [Server thread/INFO] []: Some server message'
        )
        self.assertEqual('INFO', info.logging_level)
        self.assertEqual('Some server message', info.content)
        self.assertEqual(12, info.hour)
        self.assertEqual(34, info.min)
        self.assertEqual(56, info.sec)

    def test_empty_brackets_with_player_message(self):
        """Player message on empty [] line — profile's player_message pattern fires."""
        info = parse_line(
            self.handler,
            '[12:34:56] [Server thread/INFO] []: '
            '<Fallen_Breath> hello cleanroom'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello cleanroom', info.content)

    def test_empty_brackets_with_not_secure(self):
        info = parse_line(
            self.handler,
            '[12:34:56] [Server thread/INFO] []: '
            '[Not Secure] <Steve> test'
        )
        self.assertEqual('Steve', info.player)
        self.assertEqual('test', info.content)

    # ── normal forge lines (base handler handles) ──

    def test_normal_forge_line_still_works(self):
        info = parse_line(
            self.handler,
            '[00:53:00] [Server thread/INFO] [minecraft/DedicatedServer]: '
            'Starting...'
        )
        self.assertEqual('INFO', info.logging_level)
        self.assertEqual('Starting...', info.content)

    def test_forge_startup_detected(self):
        info = parse_line(
            self.handler,
            '[01:00:17] [Server thread/INFO] [minecraft/DedicatedServer]: '
            'Done (3.985s)! For help, type "help"'
        )
        self.assertTrue(self.handler.test_server_startup_done(info))

    # ── join / left / version delegation ──

    def test_forge_join_on_empty_brackets_line(self):
        """Join detection on a []-formatted line delegates to ForgeHandler."""
        info = parse_line(
            self.handler,
            '[00:55:26] [Server thread/INFO] [minecraft/PlayerList]: '
            'Fallen_Breath[/127.0.0.1:2115] logged in with entity id 314 '
            'at (187.27, 146.79, 404.85)'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_joined(info))

    def test_forge_left_detected(self):
        """Left detection on normal forge line."""
        info = parse_line(
            self.handler,
            '[00:57:00] [Server thread/INFO] [minecraft/PlayerList]: '
            'Steve left the game'
        )
        self.assertEqual('Steve', self.handler.parse_player_left(info))
