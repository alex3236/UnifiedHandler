"""Tests for bedrock_bds base profile.

Original: BedrockLiteloaderHandler (~250 lines, extends AbstractMinecraftHandler,
~13 overrides). Full profile mode — no base handler delegation.
"""
import unittest

from mcdreforged.handler.impl.basic_handler import BasicHandler
from mcdreforged.minecraft.rtext.text import RText

from .common import load_profile, parse_line
from unified_handler.profile_loader import compile_full_profile
from unified_handler.handler import UnifiedHandler


BDS_LIFECYCLE = r'''
[2024-01-15 12:34:50.123 INFO] [Dedicated Server] Starting Server
[2024-01-15 12:34:50.456 INFO] [Dedicated Server] Version: 1.21.0.03(Server)
[2024-01-15 12:34:51.789 INFO] [Dedicated Server] IPv4 supported, port: 19132
[2024-01-15 12:34:55.000 INFO] [Dedicated Server] IPv6 supported, port: 19133
[2024-01-15 12:34:56.000 INFO] [Dedicated Server] Session ID 1234567890
[2024-01-15 12:34:56.789 INFO] [Dedicated Server] Level Name: Bedrock level
[2024-01-15 12:34:57.000 INFO] [Dedicated Server] Game mode: 0 Survival
[2024-01-15 12:34:57.500 INFO] [Dedicated Server] Difficulty: 1 EASY
[2024-01-15 12:34:58.000 INFO] [Dedicated Server] Server started.
[2024-01-15 12:35:00.000 INFO] [Dedicated Server] Player Spawned: Fallen_Breath xuid: 1234567890
[2024-01-15 12:35:10.000 INFO] [Dedicated Server] <Fallen_Breath> hello bds
[2024-01-15 12:35:20.000 INFO] [Dedicated Server] Player disconnected: Fallen_Breath, xuid: 1234567890
[2024-01-15 12:35:30.000 INFO] [Dedicated Server] Stopping server...
[2024-01-15 12:35:31.000 INFO] [Dedicated Server] Quitting
'''.strip()


class TestBedrockBDSProfile(unittest.TestCase):
    def setUp(self):
        profile = load_profile('bedrock_bds', 'base')
        compiled = compile_full_profile(profile)
        self.handler = UnifiedHandler(
            BasicHandler(), compiled, mode='full_profile'
        )

    # ── log_format ──

    def test_log_format(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Server started.'
        )
        self.assertEqual(12, info.hour)
        self.assertEqual(34, info.min)
        self.assertEqual(56, info.sec)
        self.assertEqual('INFO', info.logging_level)
        self.assertEqual('Server started.', info.content)

    # ── player message ──

    def test_player_message(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '<Fallen_Breath> hello bds'
        )
        self.assertEqual('"Fallen_Breath"', info.player)
        self.assertEqual('hello bds', info.content)

    def test_player_with_spaces(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '<Alex 3236> hi'
        )
        self.assertEqual('"Alex 3236"', info.player)

    def test_command_echo_ignored(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '/time set day'
        )
        self.assertEqual('', info.content)

    # ── player name validation ──

    def test_name_too_short_rejected(self):
        """Name shorter than 3 chars should not be detected as player."""
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '<ab> test'
        )
        self.assertIsNone(info.player)

    def test_name_too_long_rejected(self):
        """Name longer than 16 chars should not be detected as player."""
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '<ThisNameIsWayTooLong123> test'
        )
        self.assertIsNone(info.player)

    # ── player join / leave ──

    def test_player_joined(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Player Spawned: Fallen_Breath xuid: 1234567890'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_joined(info))

    def test_player_left(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Player disconnected: Fallen_Breath, xuid: 1234567890'
        )
        self.assertEqual('Fallen_Breath',
                         self.handler.parse_player_left(info))

    # ── server version ──

    def test_server_version(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Version: 1.21.0.03(Server)'
        )
        self.assertEqual('1.21.0.03',
                         self.handler.parse_server_version(info))

    # ── server address (IPv4 only, first_only) ──

    def test_server_address_without_ip_group(self):
        """Pattern has no 'ip' capture group — defaults to 127.0.0.1."""
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'IPv4 supported, port: 19132'
        )
        result = self.handler.parse_server_address(info)
        self.assertEqual(('127.0.0.1', 19132), result)

    def test_server_address_first_only(self):
        """Second detection is suppressed by first_only mode."""
        # First detection
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'IPv4 supported, port: 19132'
        )
        result = self.handler.parse_server_address(info)
        self.assertEqual(('127.0.0.1', 19132), result)
        # Second detection suppressed
        info2 = parse_line(
            self.handler,
            '[2024-01-15 12:34:57.000 INFO] [Dedicated Server] '
            'IPv4 supported, port: 19133'
        )
        self.assertIsNone(self.handler.parse_server_address(info2))

    def test_ipv6_not_detected(self):
        """Only IPv4 pattern exists; IPv6 line returns None."""
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:55.000 INFO] [Dedicated Server] '
            'IPv6 supported, port: 19133'
        )
        self.assertIsNone(self.handler.parse_server_address(info))

    # ── server state ──

    def test_startup_done(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Server started.'
        )
        self.assertTrue(self.handler.test_server_startup_done(info))

    def test_rcon_disabled(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'RCON running on 0.0.0.0:25575'
        )
        self.assertFalse(self.handler.test_rcon_started(info))

    def test_stopping(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            'Stopping server...'
        )
        self.assertTrue(self.handler.test_server_stopping(info))

    # ── commands ──

    def test_stop_command(self):
        self.assertEqual('stop', self.handler.get_stop_command())

    def test_ansi_stripped(self):
        info = parse_line(
            self.handler,
            '[2024-01-15 12:34:56.789 INFO] [Dedicated Server] '
            '\x1b[32mGreen text\x1b[0m'
        )
        self.assertEqual('Green text', info.content)

    def test_bedrock_rawtext_format(self):
        msg = RText('Hello')
        cmd = self.handler.get_send_message_command('Player', msg, None)
        self.assertIsNotNone(cmd)
        self.assertIn('tellraw', cmd)
        self.assertIn('rawtext', cmd)

    # ── full lifecycle ──

    def test_bds_lifecycle(self):
        for line in BDS_LIFECYCLE.splitlines():
            info = parse_line(self.handler, line)
            self.assertIsNotNone(info)
