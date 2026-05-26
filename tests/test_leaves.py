"""Tests for leaves base profile.

Original: LeavesHandler (50 lines, extends BukkitHandler, 3 overrides).
"""
import unittest

from mcdreforged.handler.impl.bukkit_handler import BukkitHandler

from .common import load_profile, parse_line
from unified_handler.profile_loader import compile_full_profile
from unified_handler.handler import UnifiedHandler


LEAVES_LIFECYCLE = r'''
[00:11:21 INFO]: Starting minecraft server version 1.13.2
[00:11:21 INFO]: Loading properties
[00:11:22 INFO]: Starting Minecraft server on *:25565
[00:11:34 WARN]: **** SERVER IS RUNNING IN OFFLINE/INSECURE MODE!
[00:11:46 INFO]: Done (12.080s)! For help, type "help"
[00:11:46 INFO]: RCON running on 0.0.0.0:25575
[00:11:54 INFO]: Fallen_Breath[/127.0.0.1:11115] logged in with entity id 665 at (0,0,0)
[00:12:10 INFO]: <Fallen_Breath> hello
[00:12:25 INFO]: Fallen_Breath lost connection: Disconnected
[00:12:25 INFO]: Fallen_Breath left the game
[00:12:27 INFO]: Stopping server
'''.strip()


class TestLeavesProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('leaves', 'base')
        compiled = compile_full_profile(profile)
        self.handler = UnifiedHandler(BukkitHandler(), compiled, mode='wrapper')

    # ── ANSI stripping ──

    def test_ansi_stripping(self):
        info = parse_line(
            self.handler,
            '\x1b[33m[00:12:10 INFO]:\x1b[0m <Fallen_Breath> hello'
        )
        self.assertEqual('Fallen_Breath', info.player)
        self.assertEqual('hello', info.content)

    def test_ansi_in_server_messages(self):
        info = parse_line(
            self.handler,
            '\x1b[32m[00:11:46 INFO]:\x1b[0m '
            'Done (12.080s)! For help, type "help"'
        )
        self.assertEqual('INFO', info.logging_level)
        self.assertEqual('Done (12.080s)! For help, type "help"', info.content)

    def test_ansi_in_join_line(self):
        """ANSI before a join line — stripping happens before parsing."""
        info = parse_line(
            self.handler,
            '\x1b[32m[00:11:54 INFO]:\x1b[0m '
            'Fallen_Breath[/127.0.0.1:11115] logged in with entity id 665 '
            'at (0, 0, 0)'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_joined(info))

    # ── player left detection ──

    def test_lost_connection_detected(self):
        """Leaves outputs 'lost connection:' for disconnects."""
        info = parse_line(
            self.handler,
            '[00:12:25 INFO]: Fallen_Breath lost connection: Disconnected'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_left(info))

    def test_bukkit_left_still_works(self):
        """Normal Bukkit left detection via base handler."""
        info = parse_line(
            self.handler,
            '[00:12:25 INFO]: Fallen_Breath left the game'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_left(info))

    # ── join detection ──

    def test_bukkit_join_still_works(self):
        info = parse_line(
            self.handler,
            '[00:11:54 INFO]: '
            'Fallen_Breath[/127.0.0.1:11115] logged in with entity id 665 '
            'at (187.27, 146.79, 404.85)'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_joined(info))

    # ── startup / rcon delegation ──

    def test_startup_detected(self):
        info = parse_line(
            self.handler,
            '[00:11:46 INFO]: Done (12.080s)! For help, type "help"'
        )
        self.assertTrue(self.handler.test_server_startup_done(info))

    def test_rcon_detected(self):
        """RCON detection delegates to BukkitHandler."""
        info = parse_line(
            self.handler,
            '[00:11:46 INFO]: RCON running on 0.0.0.0:25575'
        )
        self.assertTrue(self.handler.test_rcon_started(info))

    # ── full lifecycle ──

    def test_normal_bukkit_lifecycle(self):
        for line in LEAVES_LIFECYCLE.splitlines():
            info = parse_line(self.handler, line)
            self.assertIsNotNone(info)
            self.assertIn(info.logging_level, {'INFO', 'WARN', 'ERROR'})
